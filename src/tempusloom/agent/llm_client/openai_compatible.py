"""OpenAI-compatible chat completions client."""

from __future__ import annotations

import base64
import json
from pathlib import Path
from typing import Any

from tempusloom.agent.base.cancel import CancelToken
from tempusloom.agent.base.llm_message import ImageContent, LLMMessage, MessageRole

from .base import BaseLLMClient, LLMClientError, LLMResponse, StreamCallback, ToolCallInfo


class OpenAICompatibleClient(BaseLLMClient):
    """Client for OpenAI Chat Completions compatible APIs."""

    def complete(self, *, system_prompt: str, user_prompt: str, image: dict[str, Any]) -> str:
        payload = self._build_payload(
            messages=[
                {"role": "system", "content": system_prompt},
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": user_prompt},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": self._legacy_image_data_url(image),
                                "detail": str(image.get("detail", "low")),
                            },
                        },
                    ],
                },
            ],
        )
        response = self._post_json(
            self._chat_completions_url(self.config.base_url),
            {"Authorization": f"Bearer {self.config.api_key.strip()}"},
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
        payload = self._build_payload(messages=self._messages_to_api(system_prompt, messages))
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"
        if stream_callback:
            payload["stream"] = True
            return self._complete_streaming(payload, stream_callback, cancel_token)

        response = self._post_json(
            self._chat_completions_url(self.config.base_url),
            {"Authorization": f"Bearer {self.config.api_key.strip()}"},
            payload,
        )
        if cancel_token:
            cancel_token.check()
        llm_response = self._parse_response(response)
        if stream_callback and llm_response.content:
            stream_callback(llm_response.content)
        return llm_response

    def _build_payload(self, *, messages: list[dict[str, Any]]) -> dict[str, Any]:
        payload = {
            "model": self.config.model,
            "messages": messages,
            "temperature": self._request_temperature(),
            "max_tokens": self._request_max_tokens(),
        }
        return payload

    def _request_temperature(self) -> float:
        model = self.config.model.strip().lower()
        provider = self.config.provider.strip().lower()
        base_url = self.config.base_url.strip().lower()
        if provider == "kimi" or "moonshot.cn" in base_url:
            if model.startswith("kimi-k2") or model.startswith("kimi-k"):
                return 1.0
        return self.config.temperature

    def _request_max_tokens(self) -> int:
        model = self.config.model.strip().lower()
        provider = self.config.provider.strip().lower()
        base_url = self.config.base_url.strip().lower()
        if (provider == "kimi" or "moonshot.cn" in base_url) and model.startswith("kimi-k"):
            return max(int(self.config.max_tokens), 256 * 1024)
        return int(self.config.max_tokens)

    def _requires_reasoning_content_on_tool_messages(self) -> bool:
        model = self.config.model.strip().lower()
        provider = self.config.provider.strip().lower()
        base_url = self.config.base_url.strip().lower()
        return (provider == "kimi" or "moonshot.cn" in base_url) and model.startswith("kimi-k")

    def _messages_to_api(self, system_prompt: str, messages: list[LLMMessage]) -> list[dict[str, Any]]:
        api_messages: list[dict[str, Any]] = [{"role": "system", "content": system_prompt}]
        for message in messages:
            if message.role == MessageRole.SYSTEM:
                api_messages.append({"role": "system", "content": message.content})
            elif message.role == MessageRole.USER:
                api_messages.append({"role": "user", "content": self._user_content(message)})
            elif message.role == MessageRole.ASSISTANT:
                content = message.content or ""
                if not content.strip() and not message.tool_calls:
                    continue
                item: dict[str, Any] = {"role": "assistant", "content": content}
                if message.tool_calls:
                    item["tool_calls"] = [self._tool_call_to_openai(tool_call) for tool_call in message.tool_calls]
                    reasoning_content = self._reasoning_content_for_message(message)
                    if reasoning_content or self._requires_reasoning_content_on_tool_messages():
                        item["reasoning_content"] = reasoning_content
                api_messages.append(item)
            elif message.role == MessageRole.TOOL_RESULT:
                api_messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": message.tool_call_id or "",
                        "name": message.tool_name or "",
                        "content": message.content,
                    }
                )
        return api_messages

    def _user_content(self, message: LLMMessage) -> str | list[dict[str, Any]]:
        if not message.images:
            return message.content
        parts: list[dict[str, Any]] = []
        if message.content:
            parts.append({"type": "text", "text": message.content})
        for image in message.images:
            parts.append(
                {
                    "type": "image_url",
                    "image_url": {
                        "url": self._image_data_url(image),
                        "detail": image.detail,
                    },
                }
            )
        return parts

    def _complete_streaming(
        self,
        payload: dict[str, Any],
        stream_callback: StreamCallback,
        cancel_token: CancelToken | None,
    ) -> LLMResponse:
        content_parts: list[str] = []
        reasoning_parts: list[str] = []
        tool_call_parts: dict[int, dict[str, Any]] = {}
        raw_chunks: list[dict[str, Any]] = []
        finish_reason: str | None = None
        for line in self._post_json_stream(
            self._chat_completions_url(self.config.base_url),
            {"Authorization": f"Bearer {self.config.api_key.strip()}"},
            payload,
            cancel_token,
        ):
            stripped = line.strip()
            if not stripped or not stripped.startswith("data:"):
                continue
            data = stripped[5:].strip()
            if data == "[DONE]":
                break
            try:
                chunk = json.loads(data)
            except json.JSONDecodeError:
                continue
            raw_chunks.append(chunk)
            choices = chunk.get("choices")
            if not isinstance(choices, list) or not choices:
                continue
            delta = choices[0].get("delta")
            if not isinstance(delta, dict):
                continue
            if choices[0].get("finish_reason"):
                finish_reason = str(choices[0].get("finish_reason"))
            reasoning_delta = delta.get("reasoning_content")
            if isinstance(reasoning_delta, str) and reasoning_delta:
                reasoning_parts.append(reasoning_delta)
            content_delta = delta.get("content")
            if isinstance(content_delta, str) and content_delta:
                content_parts.append(content_delta)
                stream_callback(content_delta)
            for tool_delta in delta.get("tool_calls") or []:
                if isinstance(tool_delta, dict):
                    self._merge_stream_tool_call(tool_call_parts, tool_delta)

        reasoning_content = "".join(reasoning_parts)
        tool_calls = self._stream_tool_calls_to_info(tool_call_parts, reasoning_content)
        return LLMResponse(
            content="".join(content_parts),
            tool_calls=tool_calls,
            raw={"stream_chunks": raw_chunks[-20:]},
            model=self.config.model,
            provider=self.config.provider,
            reasoning_content=reasoning_content,
            finish_reason=finish_reason,
        )

    @staticmethod
    def _tool_call_to_openai(tool_call: ToolCallInfo) -> dict[str, Any]:
        return {
            "id": tool_call.id,
            "type": "function",
            "function": {
                "name": tool_call.name,
                "arguments": tool_call.arguments,
            },
        }

    def _parse_response(self, response: dict[str, Any]) -> LLMResponse:
        try:
            message = response["choices"][0]["message"]
        except (KeyError, IndexError, TypeError) as exc:
            raise LLMClientError(f"无法读取 Chat Completions 响应：{response}") from exc
        content = self._content_to_text(message.get("content", ""))
        tool_calls = []
        for index, item in enumerate(message.get("tool_calls") or []):
            if not isinstance(item, dict):
                continue
            function = item.get("function") if isinstance(item.get("function"), dict) else {}
            tool_calls.append(
                ToolCallInfo(
                    id=str(item.get("id") or f"tool_call_{index}"),
                    name=str(function.get("name", "")),
                    arguments=str(function.get("arguments", "{}")),
                    reasoning_content=str(message.get("reasoning_content", "")),
                )
            )
        return LLMResponse(
            content=content,
            tool_calls=tool_calls,
            raw=response,
            model=str(response.get("model", self.config.model)),
            provider=self.config.provider,
            reasoning_content=str(message.get("reasoning_content", "")),
            finish_reason=str(response.get("choices", [{}])[0].get("finish_reason", "")) or None,
        )

    @staticmethod
    def _merge_stream_tool_call(parts: dict[int, dict[str, Any]], delta: dict[str, Any]) -> None:
        index = int(delta.get("index", 0))
        current = parts.setdefault(index, {"id": "", "name": "", "arguments": ""})
        if delta.get("id"):
            current["id"] = str(delta["id"])
        function = delta.get("function")
        if isinstance(function, dict):
            if function.get("name"):
                current["name"] += str(function["name"])
            if function.get("arguments"):
                current["arguments"] += str(function["arguments"])

    @staticmethod
    def _stream_tool_calls_to_info(parts: dict[int, dict[str, Any]], reasoning_content: str) -> list[ToolCallInfo]:
        calls: list[ToolCallInfo] = []
        for index in sorted(parts):
            item = parts[index]
            calls.append(
                ToolCallInfo(
                    id=str(item.get("id") or f"tool_call_{index}"),
                    name=str(item.get("name", "")),
                    arguments=str(item.get("arguments", "{}")),
                    reasoning_content=reasoning_content,
                )
            )
        return calls

    @staticmethod
    def _reasoning_content_for_message(message: LLMMessage) -> str:
        if isinstance(message.metadata, dict) and message.metadata.get("reasoning_content"):
            return str(message.metadata["reasoning_content"])
        for tool_call in message.tool_calls or []:
            if tool_call.reasoning_content:
                return tool_call.reasoning_content
        return ""

    @staticmethod
    def _content_to_text(content: Any) -> str:
        if isinstance(content, list):
            return "\n".join(
                str(part.get("text", part))
                for part in content
                if isinstance(part, dict)
            )
        return "" if content is None else str(content)

    @staticmethod
    def _chat_completions_url(base_url: str) -> str:
        normalized = base_url.strip().rstrip("/")
        if normalized.endswith("/chat/completions"):
            return normalized
        return f"{normalized}/chat/completions"

    @staticmethod
    def _image_from_legacy_dict(image: dict[str, Any]) -> ImageContent:
        return ImageContent(
            file_path=str(image.get("file_path") or image.get("path") or ""),
            mime_type=str(image.get("mime_type", "image/jpeg")),
            detail=str(image.get("detail", "low")),
        )

    @staticmethod
    def _image_data_url(image: ImageContent) -> str:
        encoded = image.data_base64
        if not encoded and image.file_path:
            data = Path(image.file_path).read_bytes()
            encoded = base64.b64encode(data).decode("ascii")
        return f"data:{image.mime_type};base64,{encoded}"

    @staticmethod
    def _legacy_image_data_url(image: dict[str, Any]) -> str:
        mime_type = str(image.get("mime_type", "image/jpeg"))
        image_data = str(image.get("base64", ""))
        if not image_data:
            file_path = str(image.get("file_path") or image.get("path") or "")
            if file_path:
                image_data = base64.b64encode(Path(file_path).read_bytes()).decode("ascii")
        return f"data:{mime_type};base64,{image_data}"
