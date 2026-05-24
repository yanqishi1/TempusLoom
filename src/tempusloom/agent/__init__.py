"""Agent framework primitives for TempusLoom."""

from .base.cancel import AgentCancelledError, CancelToken
from .base.llm_logger import LLMLogger
from .base.llm_message import Attachment, ImageContent, LLMMessage, MessageRole
from .config import AgentModelConfig, PROVIDER_PRESETS, load_agent_config, save_agent_config
from .color_agent import AgentRequestContext, AgentRunResult, AgentTurnResult, ColorAgent, TempusLoomColorAgent
from .llm_client import LLMClientError, create_llm_client
from .tools.tool_register import ToolContext, ToolRegister, ToolResult, ToolSpec

__all__ = [
    "AgentCancelledError",
    "AgentModelConfig",
    "AgentRequestContext",
    "AgentRunResult",
    "AgentTurnResult",
    "Attachment",
    "CancelToken",
    "ColorAgent",
    "ImageContent",
    "LLMClientError",
    "LLMLogger",
    "LLMMessage",
    "MessageRole",
    "PROVIDER_PRESETS",
    "TempusLoomColorAgent",
    "ToolContext",
    "ToolRegister",
    "ToolResult",
    "ToolSpec",
    "create_llm_client",
    "load_agent_config",
    "save_agent_config",
]
