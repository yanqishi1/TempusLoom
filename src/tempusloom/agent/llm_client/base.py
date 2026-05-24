"""Base classes and response models for LLM clients."""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Callable

from tempusloom.agent.base.cancel import CancelToken
from tempusloom.agent.base.config import AgentModelConfig
from tempusloom.agent.base.llm_message import LLMMessage

StreamCallback = Callable[[str], None]


class LLMClientError(RuntimeError):
    """Raised when an LLM provider request fails or returns invalid data."""


@dataclass
class ToolCallInfo:
    """Provider-normalized tool call request."""

    id: str
    name: str
    arguments: str
    type: str = "function"
    reasoning_content: str = ""

    def arguments_dict(self) -> dict[str, Any]:
        if not self.arguments:
            return {}
        try:
            parsed = json.loads(self.arguments)
        except json.JSONDecodeError:
            return {}
        return parsed if isinstance(parsed, dict) else {}

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "arguments": self.arguments,
            "type": self.type,
            "reasoning_content": self.reasoning_content,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ToolCallInfo":
        return cls(
            id=str(data.get("id", "")),
            name=str(data.get("name", "")),
            arguments=str(data.get("arguments", "{}")),
            type=str(data.get("type", "function")),
            reasoning_content=str(data.get("reasoning_content", "")),
        )


@dataclass
class LLMResponse:
    """Provider-normalized LLM response."""

    content: str = ""
    tool_calls: list[ToolCallInfo] = field(default_factory=list)
    raw: dict[str, Any] | None = None
    model: str | None = None
    provider: str | None = None
    reasoning_content: str = ""
    finish_reason: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "content": self.content,
            "tool_calls": [tool_call.to_dict() for tool_call in self.tool_calls],
            "raw": self.raw,
            "model": self.model,
            "provider": self.provider,
            "reasoning_content": self.reasoning_content,
            "finish_reason": self.finish_reason,
        }


class BaseLLMClient(ABC):
    """Abstract LLM client shared by all providers."""

    def __init__(self, config: AgentModelConfig) -> None:
        self.config = config

    @abstractmethod
    def complete(self, *, system_prompt: str, user_prompt: str, image: dict[str, Any]) -> str:
        """Backward-compatible single-turn completion."""
        raise NotImplementedError

    @abstractmethod
    def complete_with_tools(
        self,
        *,
        system_prompt: str,
        messages: list[LLMMessage],
        tools: list[dict[str, Any]] | None = None,
        stream_callback: StreamCallback | None = None,
        cancel_token: CancelToken | None = None,
    ) -> LLMResponse:
        """Complete a conversation and optionally return tool calls."""
        raise NotImplementedError

    def _post_json(self, url: str, headers: dict[str, str], payload: dict[str, Any]) -> dict[str, Any]:
        if self.config.api_key.strip() == "":
            raise LLMClientError("请先配置 API Key。")
        data = json.dumps(payload).encode("utf-8")
        request = urllib.request.Request(
            url,
            data=data,
            headers={"Content-Type": "application/json", **headers},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.config.timeout_seconds) as response:
                body = response.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise LLMClientError(f"API 请求失败 HTTP {exc.code}: {detail[:600]}") from exc
        except urllib.error.URLError as exc:
            raise LLMClientError(f"API 网络请求失败：{exc.reason}") from exc
        except TimeoutError as exc:
            raise LLMClientError("API 请求超时，请检查网络或调大超时时间。") from exc

        try:
            parsed = json.loads(body)
        except json.JSONDecodeError as exc:
            raise LLMClientError(f"API 返回非 JSON 内容：{body[:600]}") from exc
        if not isinstance(parsed, dict):
            raise LLMClientError("API 返回格式不是 JSON 对象。")
        return parsed

    def _post_json_stream(
        self,
        url: str,
        headers: dict[str, str],
        payload: dict[str, Any],
        cancel_token: CancelToken | None = None,
    ):
        if self.config.api_key.strip() == "":
            raise LLMClientError("请先配置 API Key。")
        data = json.dumps(payload).encode("utf-8")
        request = urllib.request.Request(
            url,
            data=data,
            headers={"Content-Type": "application/json", **headers},
            method="POST",
        )
        try:
            response = urllib.request.urlopen(request, timeout=self.config.timeout_seconds)
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise LLMClientError(f"API 请求失败 HTTP {exc.code}: {detail[:600]}") from exc
        except urllib.error.URLError as exc:
            raise LLMClientError(f"API 网络请求失败：{exc.reason}") from exc
        except TimeoutError as exc:
            raise LLMClientError("API 请求超时，请检查网络或调大超时时间。") from exc

        try:
            for raw_line in response:
                if cancel_token:
                    cancel_token.check()
                yield raw_line.decode("utf-8", errors="replace")
        finally:
            response.close()
