"""Image analysis tools used by the color agent."""

from __future__ import annotations

from typing import Any

from .tool_register import ToolContext, ToolRegister, ToolResult, ToolSpec


def register_analysis_tools(register: ToolRegister) -> None:
    register.register(
        ToolSpec(
            name="analyze_histogram",
            description="Return a lightweight histogram/metadata summary for the current image.",
            input_schema={"type": "object", "properties": {}},
        ),
        analyze_histogram,
    )


def analyze_histogram(args: dict[str, Any], context: ToolContext) -> ToolResult:
    context.check_cancelled()
    image = context.image or {}
    histogram = image.get("histogram")
    if histogram is not None:
        return ToolResult(success=True, data={"histogram": histogram})
    return ToolResult(
        success=True,
        data={
            "width": image.get("width"),
            "height": image.get("height"),
            "mime_type": image.get("mime_type"),
            "note": "Histogram data is not available in the current tool context.",
        },
    )
