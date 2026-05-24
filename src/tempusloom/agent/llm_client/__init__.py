"""LLM client factory and exports."""

from __future__ import annotations

from tempusloom.agent.base.config import AgentModelConfig

from .anthropic_client import AnthropicClient
from .base import BaseLLMClient, LLMClientError, LLMResponse, ToolCallInfo
from .codex_client import CodexClient
from .google_client import GoogleClient
from .openai_compatible import OpenAICompatibleClient


def create_llm_client(config: AgentModelConfig) -> BaseLLMClient:
    if config.provider == "anthropic":
        return AnthropicClient(config)
    if config.provider == "gemini":
        return GoogleClient(config)
    if config.provider == "codex":
        return CodexClient(config)
    return OpenAICompatibleClient(config)


__all__ = [
    "AnthropicClient",
    "BaseLLMClient",
    "CodexClient",
    "GoogleClient",
    "LLMClientError",
    "LLMResponse",
    "OpenAICompatibleClient",
    "ToolCallInfo",
    "create_llm_client",
]
