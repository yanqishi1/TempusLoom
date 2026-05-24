"""Tool registration and execution primitives."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

from tempusloom.agent.base.cancel import CancelToken


ToolHandler = Callable[[dict[str, Any], "ToolContext"], "ToolResult"]


@dataclass
class ToolSpec:
    """Description of a callable tool exposed to an LLM."""

    name: str
    description: str
    input_schema: dict[str, Any] = field(default_factory=lambda: {"type": "object", "properties": {}})

    def to_openai_tool(self) -> dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.input_schema or {"type": "object", "properties": {}},
            },
        }


@dataclass
class ToolResult:
    """Result returned by a tool execution."""

    success: bool = True
    data: Any = field(default_factory=dict)
    error: str = ""
    edit_id: str | None = None
    requires_confirmation: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "success": self.success,
            "data": self.data,
            "error": self.error,
            "edit_id": self.edit_id,
            "requires_confirmation": self.requires_confirmation,
            "metadata": self.metadata,
        }


@dataclass
class ToolContext:
    """Execution context passed to tools."""

    session_id: str | None = None
    image: dict[str, Any] | None = None
    current_adjust: dict[str, Any] | None = None
    cancel_token: CancelToken | None = None
    apply_payload: Callable[[dict[str, Any], str], str] | None = None
    undo_last_edit: Callable[[], bool] | None = None
    workspace: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def check_cancelled(self) -> None:
        if self.cancel_token:
            self.cancel_token.check()


class ToolRegister:
    """Registry and dispatcher for tools."""

    def __init__(self) -> None:
        self._specs: dict[str, ToolSpec] = {}
        self._handlers: dict[str, ToolHandler] = {}

    def register(self, spec: ToolSpec, handler: ToolHandler) -> None:
        if not spec.name:
            raise ValueError("Tool name cannot be empty.")
        self._specs[spec.name] = spec
        self._handlers[spec.name] = handler

    def unregister(self, name: str) -> bool:
        existed = name in self._specs
        self._specs.pop(name, None)
        self._handlers.pop(name, None)
        return existed

    def execute(self, name: str, arguments: dict[str, Any] | None, context: ToolContext | None = None) -> ToolResult:
        ctx = context or ToolContext()
        ctx.check_cancelled()
        if name not in self._handlers:
            return ToolResult(success=False, error=f"Unknown tool: {name}")
        try:
            result = self._handlers[name](arguments or {}, ctx)
            if not isinstance(result, ToolResult):
                return ToolResult(success=True, data=result)
            return result
        except Exception as exc:
            return ToolResult(success=False, error=str(exc))

    def get(self, name: str) -> ToolSpec | None:
        return self._specs.get(name)

    def tool_names(self) -> list[str]:
        return list(self._specs.keys())

    def list_specs(self) -> list[ToolSpec]:
        return list(self._specs.values())

    def to_openai_tools(self) -> list[dict[str, Any]]:
        return [spec.to_openai_tool() for spec in self._specs.values()]

    def list_for_model(self) -> list[dict[str, Any]]:
        return self.to_openai_tools()
