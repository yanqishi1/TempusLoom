"""Provider clients for the first TempusLoom agent runtime."""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from abc import ABC, abstractmethod
from typing import Any

from .config import AgentModelConfig


class LLMClientError(RuntimeError):
    pass


class BaseLLMClient(ABC):
    def __init__(self, config: AgentModelConfig) -> None:
        self.config = config

    @abstractmethod
    def complete(self, *, system_prompt: str, user_prompt: str, image: dict[str, Any]) -> str:
        raise NotImplementedError

    def _post_json(self, url: str, headers: dict[str, str], payload: dict[str, Any]) -> dict[str, Any]:
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


class OpenAICompatibleClient(BaseLLMClient):
    def complete(self, *, system_prompt: str, user_prompt: str, image: dict[str, Any]) -> str:
        url = self._chat_completions_url(self.config.base_url)
        mime_type = image.get("mime_type", "image/jpeg")
        image_data = image.get("base64", "")
        messages: list[dict[str, Any]] = [
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": user_prompt},
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:{mime_type};base64,{image_data}",
                            "detail": "low",
                        },
                    },
                ],
            },
        ]
        payload = {
            "model": self.config.model,
            "messages": messages,
            "temperature": self.config.temperature,
            "max_tokens": self.config.max_tokens,
        }
        response = self._post_json(
            url,
            {"Authorization": f"Bearer {self.config.api_key.strip()}"},
            payload,
        )
        try:
            content = response["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise LLMClientError(f"无法读取 Chat Completions 响应：{response}") from exc
        if isinstance(content, list):
            return "\n".join(str(part.get("text", part)) for part in content if isinstance(part, dict))
        return str(content)

    @staticmethod
    def _chat_completions_url(base_url: str) -> str:
        normalized = base_url.strip().rstrip("/")
        if normalized.endswith("/chat/completions"):
            return normalized
        return f"{normalized}/chat/completions"


class AnthropicClient(BaseLLMClient):
    def complete(self, *, system_prompt: str, user_prompt: str, image: dict[str, Any]) -> str:
        url = self._messages_url(self.config.base_url)
        payload = {
            "model": self.config.model,
            "system": system_prompt,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": user_prompt},
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": image.get("mime_type", "image/jpeg"),
                                "data": image.get("base64", ""),
                            },
                        },
                    ],
                }
            ],
            "temperature": self.config.temperature,
            "max_tokens": self.config.max_tokens,
        }
        response = self._post_json(
            url,
            {
                "x-api-key": self.config.api_key.strip(),
                "anthropic-version": "2023-06-01",
            },
            payload,
        )
        try:
            blocks = response["content"]
        except KeyError as exc:
            raise LLMClientError(f"无法读取 Anthropic 响应：{response}") from exc
        if not isinstance(blocks, list):
            raise LLMClientError(f"Anthropic 响应 content 格式异常：{response}")
        return "\n".join(
            str(block.get("text", ""))
            for block in blocks
            if isinstance(block, dict) and block.get("type") == "text"
        ).strip()

    @staticmethod
    def _messages_url(base_url: str) -> str:
        normalized = base_url.strip().rstrip("/")
        if normalized.endswith("/messages"):
            return normalized
        return f"{normalized}/messages"


def create_llm_client(config: AgentModelConfig) -> BaseLLMClient:
    if config.provider == "anthropic":
        return AnthropicClient(config)
    return OpenAICompatibleClient(config)
