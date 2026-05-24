"""Anthropic Messages API client."""

from __future__ import annotations

import base64
import json
from pathlib import Path
from typing import Any

from tempusloom.agent.base.cancel import CancelToken
from tempusloom.agent.base.llm_message import ImageContent, LLMMessage, MessageRole

from .base import BaseLLMClient, LLMClientError, LLMResponse, StreamCallback, ToolCallInfo


class AnthropicClient(BaseLLMClient):
    """Client for Anthropic native Messages API."""

    def complete(self, *, system_prompt: str, user_prompt: str, image: dict[str, Any]) -> str:
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
                                "data": self._legacy_image_base64(image),
                            },
                        },
                    ],
                }
            ],
            "temperature": self.config.temperature,
            "max_tokens": self.config.max_tokens,
        }
        response = self._post_json(
            self._messages_url(self.config.base_url),
            {
                "x-api-key": self.config.api_key.strip(),
                "anthropic-version": "2023-06-01",
            },
            payload,
        )
        return self._parse_response(response).content

    def complete_with_tools(
        self,
        *,
        system_prompt: str,
        messages: list[LLMMessage],
        tools: list[dict[str, Any]] | None = None,
        stream_callback: StreamCallback | None = None,
        cancel_token: CancelToken | None = None,
    ) -> LLMResponse:
        if cancel_token:
            cancel_token.check()
        payload: dict[str, Any] = {
            "model": self.config.model,
            "system": system_prompt,
            "messages": self._messages_to_api(messages),
            "temperature": self.config.temperature,
            "max_tokens": self.config.max_tokens,
        }
        if tools:
            payload["tools"] = [self._openai_tool_to_anthropic(tool) for tool in tools]
        response = self._post_json(
            self._messages_url(self.config.base_url),
            {
                "x-api-key": self.config.api_key.strip(),
                "anthropic-version": "2023-06-01",
            },
            payload,
        )
        if cancel_token:
            cancel_token.check()
        llm_response = self._parse_response(response)
        if stream_callback and llm_response.content:
            stream_callback(llm_response.content)
        return llm_response

    def _messages_to_api(self, messages: list[LLMMessage]) -> list[dict[str, Any]]:
        api_messages: list[dict[str, Any]] = []
        for message in messages:
            if message.role == MessageRole.SYSTEM:
                continue
            if message.role == MessageRole.USER:
                api_messages.append({"role": "user", "content": self._user_content(message)})
            elif message.role == MessageRole.ASSISTANT:
                content: list[dict[str, Any]] = []
                if message.content:
                    content.append({"type": "text", "text": message.content})
                for tool_call in message.tool_calls or []:
                    content.append(
                        {
                            "type": "tool_use",
                            "id": tool_call.id,
                            "name": tool_call.name,
                            "input": tool_call.arguments_dict(),
                        }
                    )
                api_messages.append({"role": "assistant", "content": content or [{"type": "text", "text": ""}]})
            elif message.role == MessageRole.TOOL_RESULT:
                api_messages.append(
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "tool_result",
                                "tool_use_id": message.tool_call_id or "",
                                "content": message.content,
                            }
                        ],
                    }
                )
        return api_messages

    def _user_content(self, message: LLMMessage) -> list[dict[str, Any]]:
        content: list[dict[str, Any]] = []
        if message.content:
            content.append({"type": "text", "text": message.content})
        for image in message.images:
            content.append(
                {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": image.mime_type,
                        "data": self._image_base64(image),
                    },
                }
            )
        return content or [{"type": "text", "text": ""}]

    def _parse_response(self, response: dict[str, Any]) -> LLMResponse:
        blocks = response.get("content")
        if not isinstance(blocks, list):
            raise LLMClientError(f"Anthropic 响应 content 格式异常：{response}")
        text_parts: list[str] = []
        tool_calls: list[ToolCallInfo] = []
        for block in blocks:
            if not isinstance(block, dict):
                continue
            if block.get("type") == "text":
                text_parts.append(str(block.get("text", "")))
            elif block.get("type") == "tool_use":
                tool_calls.append(
                    ToolCallInfo(
                        id=str(block.get("id", "")),
                        name=str(block.get("name", "")),
                        arguments=json.dumps(block.get("input", {}), ensure_ascii=False),
                    )
                )
        return LLMResponse(
            content="\n".join(text_parts).strip(),
            tool_calls=tool_calls,
            raw=response,
            model=str(response.get("model", self.config.model)),
            provider=self.config.provider,
        )

    @staticmethod
    def _openai_tool_to_anthropic(tool: dict[str, Any]) -> dict[str, Any]:
        function = tool.get("function") if isinstance(tool.get("function"), dict) else {}
        return {
            "name": function.get("name", tool.get("name", "")),
            "description": function.get("description", tool.get("description", "")),
            "input_schema": function.get("parameters", tool.get("input_schema", {"type": "object"})),
        }

    @staticmethod
    def _messages_url(base_url: str) -> str:
        normalized = base_url.strip().rstrip("/")
        if normalized.endswith("/messages"):
            return normalized
        return f"{normalized}/messages"

    @staticmethod
    def _image_from_legacy_dict(image: dict[str, Any]) -> ImageContent:
        return ImageContent(
            file_path=str(image.get("file_path") or image.get("path") or ""),
            mime_type=str(image.get("mime_type", "image/jpeg")),
            detail=str(image.get("detail", "low")),
        )

    @staticmethod
    def _image_base64(image: ImageContent) -> str:
        if image.data_base64:
            return image.data_base64
        data = Path(image.file_path).read_bytes() if image.file_path else b""
        return base64.b64encode(data).decode("ascii")

    @staticmethod
    def _legacy_image_base64(image: dict[str, Any]) -> str:
        image_data = str(image.get("base64", ""))
        if image_data:
            return image_data
        file_path = str(image.get("file_path") or image.get("path") or "")
        if not file_path:
            return ""
        return base64.b64encode(Path(file_path).read_bytes()).decode("ascii")
