"""Single-turn color grading agent for TempusLoom."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from .clients import LLMClientError, create_llm_client
from .config import AgentModelConfig
from .prompts import COLOR_GRADING_SYSTEM_PROMPT


@dataclass
class AgentRequestContext:
    image: dict[str, Any]
    style_prompt: str
    current_adjust: dict[str, Any]
    image_name: str


@dataclass
class AgentRunResult:
    payload: dict[str, Any]
    raw_text: str
    model: str
    provider: str


class AgentResponseError(RuntimeError):
    pass


class TempusLoomColorAgent:
    def __init__(self, config: AgentModelConfig) -> None:
        self.config = config
        self.client = create_llm_client(config)

    def run_single_turn(self, context: AgentRequestContext) -> AgentRunResult:
        if not self.config.is_configured():
            raise LLMClientError("请先配置 Base URL、API Key 和模型名称。")
        user_prompt = self._build_user_prompt(context)
        raw_text = self.client.complete(
            system_prompt=COLOR_GRADING_SYSTEM_PROMPT,
            user_prompt=user_prompt,
            image=context.image,
        )
        payload = self._parse_adjustment_payload(raw_text)
        meta = payload.setdefault("meta", {})
        if isinstance(meta, dict):
            meta.setdefault("source", "tempusloom-color-agent")
            meta.setdefault("model", self.config.model)
            meta.setdefault("provider", self.config.provider)
            meta.setdefault("imageName", context.image_name)
            meta.setdefault("stylePrompt", context.style_prompt)
        return AgentRunResult(
            payload=payload,
            raw_text=raw_text,
            model=self.config.model,
            provider=self.config.provider,
        )

    @staticmethod
    def _build_user_prompt(context: AgentRequestContext) -> str:
        current_adjust_json = json.dumps(context.current_adjust, ensure_ascii=False, indent=2)
        image_meta = {
            "imageName": context.image_name,
            "width": context.image.get("width"),
            "height": context.image.get("height"),
            "byteSize": context.image.get("byte_size"),
            "mimeType": context.image.get("mime_type"),
        }
        image_meta_json = json.dumps(image_meta, ensure_ascii=False, indent=2)
        return (
            f"用户风格描述：{context.style_prompt.strip()}\n\n"
            f"图片信息：\n{image_meta_json}\n\n"
            f"当前已有调色参数：\n{current_adjust_json}\n\n"
            "请结合图片预览生成新的 TempusLoom 调色 JSON。"
        )

    @staticmethod
    def _parse_adjustment_payload(raw_text: str) -> dict[str, Any]:
        text = raw_text.strip()
        if text.startswith("```"):
            lines = text.splitlines()
            if lines and lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].strip().startswith("```"):
                lines = lines[:-1]
            text = "\n".join(lines).strip()
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError:
            start = text.find("{")
            end = text.rfind("}")
            if start < 0 or end <= start:
                raise AgentResponseError(f"模型没有返回 JSON 对象：{raw_text[:600]}")
            try:
                parsed = json.loads(text[start:end + 1])
            except json.JSONDecodeError as exc:
                raise AgentResponseError(f"模型返回的 JSON 无法解析：{raw_text[:600]}") from exc
        if not isinstance(parsed, dict):
            raise AgentResponseError("模型返回的根内容不是 JSON 对象。")
        if "adjust" not in parsed:
            parsed = {"adjust": parsed}
        if not isinstance(parsed.get("adjust"), dict):
            raise AgentResponseError("模型返回的 adjust 字段不是对象。")
        return parsed
