"""Configuration storage for chatbox agent model providers."""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


CONFIG_PATH = Path.home() / ".tempusloom" / "config" / "agent_chatbox.json"

PROVIDER_PRESETS: dict[str, dict[str, str]] = {
    "openai-compatible": {
        "label": "OpenAI / 兼容接口",
        "base_url": "https://api.openai.com/v1",
        "model": "gpt-4o-mini",
    },
    "anthropic": {
        "label": "Claude / Anthropic",
        "base_url": "https://api.anthropic.com/v1",
        "model": "claude-3-5-sonnet-latest",
    },
    "deepseek": {
        "label": "DeepSeek",
        "base_url": "https://api.deepseek.com/v1",
        "model": "deepseek-chat",
    },
    "kimi": {
        "label": "Kimi / Moonshot",
        "base_url": "https://api.moonshot.cn/v1",
        "model": "moonshot-v1-8k",
    },
    "glm": {
        "label": "GLM / 智谱",
        "base_url": "https://open.bigmodel.cn/api/paas/v4",
        "model": "glm-4-flash",
    },
}


@dataclass
class AgentModelConfig:
    provider: str = "openai-compatible"
    base_url: str = PROVIDER_PRESETS["openai-compatible"]["base_url"]
    api_key: str = ""
    model: str = PROVIDER_PRESETS["openai-compatible"]["model"]
    temperature: float = 0.2
    max_tokens: int = 1400
    timeout_seconds: int = 90

    @property
    def provider_label(self) -> str:
        return PROVIDER_PRESETS.get(self.provider, PROVIDER_PRESETS["openai-compatible"])["label"]

    def is_configured(self) -> bool:
        return bool(self.base_url.strip() and self.api_key.strip() and self.model.strip())

    def display_name(self) -> str:
        if self.model.strip():
            return f"{self.provider_label} · {self.model.strip()}"
        return self.provider_label


def load_agent_config(path: Path = CONFIG_PATH) -> AgentModelConfig:
    if not path.exists():
        return AgentModelConfig()
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return AgentModelConfig()
    if not isinstance(payload, dict):
        return AgentModelConfig()

    defaults = asdict(AgentModelConfig())
    cleaned: dict[str, Any] = {key: payload.get(key, default) for key, default in defaults.items()}
    return AgentModelConfig(**cleaned)


def save_agent_config(config: AgentModelConfig, path: Path = CONFIG_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(asdict(config), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass
