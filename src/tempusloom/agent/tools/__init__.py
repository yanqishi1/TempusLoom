"""Tool registry and built-in tools for TempusLoom agents."""

from .bash_tool import BashWhitelistPolicy, execute_bash_tool, register_bash_tool
from .image_analysis_tools import analyze_histogram, register_analysis_tools
from .native_color_tools import (
    apply_adjustment_preview,
    create_mask_layer,
    get_current_image_context,
    register_native_tools,
    undo_last_agent_edit,
)
from .tool_register import ToolContext, ToolRegister, ToolResult, ToolSpec

__all__ = [
    "BashWhitelistPolicy",
    "ToolContext",
    "ToolRegister",
    "ToolResult",
    "ToolSpec",
    "analyze_histogram",
    "apply_adjustment_preview",
    "create_mask_layer",
    "execute_bash_tool",
    "get_current_image_context",
    "register_analysis_tools",
    "register_bash_tool",
    "register_native_tools",
    "undo_last_agent_edit",
]
