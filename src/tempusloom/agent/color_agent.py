"""Single-turn color grading agent for TempusLoom."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from .base.cancel import AgentCancelledError, CancelToken
from .base.llm_logger import LLMLogger
from .base.llm_message import ImageContent, LLMMessage, MessageRole
from .clients import LLMClientError, create_llm_client
from .config import AgentModelConfig
from .llm_client import ToolCallInfo
from .memory.conversation_store import ConversationStore
from .prompts import COLOR_GRADING_SYSTEM_PROMPT
from .tools import register_analysis_tools, register_bash_tool, register_native_tools
from .tools.tool_register import ToolContext, ToolRegister


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


@dataclass
class ToolCallRecord:
    tool_name: str
    arguments: dict[str, Any]
    success: bool
    result: Any = None
    error: str = ""
    edit_id: str | None = None
    requires_confirmation: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "toolName": self.tool_name,
            "arguments": self.arguments,
            "success": self.success,
            "result": self.result,
            "error": self.error,
            "editId": self.edit_id,
            "requiresConfirmation": self.requires_confirmation,
        }


@dataclass
class AgentTurnResult:
    success: bool
    message: str
    tool_calls: list[ToolCallRecord] = field(default_factory=list)
    edit_ids: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    cancelled: bool = False
    pending_confirmation: dict[str, Any] | None = None
    assistant_message: LLMMessage | None = None
    payload: dict[str, Any] | None = None


class AgentResponseError(RuntimeError):
    pass


class ColorAgent:
    """TempusLoom color grading agent based on a ReAct loop."""

    def __init__(
        self,
        config: AgentModelConfig,
        *,
        conversation_store: ConversationStore | None = None,
        llm_logger: LLMLogger | None = None,
    ) -> None:
        self.config = config
        self.client = create_llm_client(config)
        self.tool_register = ToolRegister()
        self.conversation_store = conversation_store or ConversationStore()
        self.llm_logger = llm_logger or LLMLogger()
        self._session_messages: dict[str, list[LLMMessage]] = {}
        self._cancel_tokens: dict[str, CancelToken] = {}
        self._tool_context_factory: Callable[[str, dict[str, Any] | None, CancelToken | None], ToolContext] | None = None
        self._register_default_tools()
        self.system_prompt = self._build_system_prompt()

    def update_config(self, config: AgentModelConfig) -> None:
        self.config = config
        self.client = create_llm_client(config)

    def set_tool_context_factory(
        self,
        factory: Callable[[str, dict[str, Any] | None, CancelToken | None], ToolContext],
    ) -> None:
        self._tool_context_factory = factory

    def chat(
        self,
        session_id: str,
        user_message: str,
        image: dict[str, Any] | None = None,
        *,
        stream_callback: Callable[[str], None] | None = None,
        cancel_token: CancelToken | None = None,
    ) -> AgentTurnResult:
        token = cancel_token or CancelToken()
        self._cancel_tokens[session_id] = token
        user_llm_message: LLMMessage | None = None
        try:
            token.check()
            messages = self._get_session_messages(session_id)
            user_llm_message = LLMMessage(
                role=MessageRole.USER,
                content=self._build_chat_user_content(user_message, image),
                images=self._image_contents_from_dict(image),
                metadata={"image": self._image_metadata_for_log(image)},
            )
            messages.append(user_llm_message)
            assistant_message, records = self._react_loop(
                session_id,
                messages,
                image=image,
                stream_callback=stream_callback,
                cancel_token=token,
            )
            self.conversation_store.save_message(session_id, user_llm_message)
            self.conversation_store.save_message(session_id, assistant_message)
            payload = self._try_parse_adjustment_payload(assistant_message.content)
            return AgentTurnResult(
                success=True,
                message=assistant_message.content,
                tool_calls=records,
                edit_ids=[record.edit_id for record in records if record.edit_id],
                assistant_message=assistant_message,
                payload=payload,
            )
        except AgentCancelledError:
            return AgentTurnResult(
                success=False,
                message="已取消。",
                errors=[],
                cancelled=True,
                assistant_message=LLMMessage(role=MessageRole.ASSISTANT, content="已取消。"),
            )
        except Exception as exc:
            return AgentTurnResult(
                success=False,
                message=str(exc),
                errors=[str(exc)],
                assistant_message=LLMMessage(role=MessageRole.ASSISTANT, content=str(exc)),
            )
        finally:
            self._cancel_tokens.pop(session_id, None)

    def cancel(self, session_id: str) -> None:
        token = self._cancel_tokens.get(session_id)
        if token is not None:
            token.cancel()

    def end_session(self, session_id: str) -> None:
        self.cancel(session_id)
        self._session_messages.pop(session_id, None)

    def close(self) -> None:
        for token in self._cancel_tokens.values():
            token.cancel()
        self._cancel_tokens.clear()
        self.conversation_store.close()

    def _get_session_messages(self, session_id: str) -> list[LLMMessage]:
        if session_id not in self._session_messages:
            history = self.conversation_store.load_messages(
                session_id,
                limit=self.config.session_message_limit,
            )
            self._session_messages[session_id] = history
        return self._session_messages[session_id]

    def _react_loop(
        self,
        session_id: str,
        messages: list[LLMMessage],
        *,
        image: dict[str, Any] | None = None,
        stream_callback: Callable[[str], None] | None = None,
        cancel_token: CancelToken | None = None,
    ) -> tuple[LLMMessage, list[ToolCallRecord]]:
        records: list[ToolCallRecord] = []
        max_iterations = max(1, int(self.config.max_react_iterations))

        for turn in range(max_iterations):
            if cancel_token:
                cancel_token.check()
            tools = self.tool_register.to_openai_tools()
            self.llm_logger.log_request(
                session_id=session_id,
                turn=turn,
                system_prompt=self.system_prompt,
                messages=messages,
                tools=tools,
                raw_payload={},
            )
            response = self.client.complete_with_tools(
                system_prompt=self.system_prompt,
                messages=messages,
                tools=tools,
                stream_callback=stream_callback,
                cancel_token=cancel_token,
            )
            self.llm_logger.log_response(session_id, response)

            if response.tool_calls:
                tool_message = LLMMessage(
                    role=MessageRole.ASSISTANT,
                    content=response.content or "",
                    tool_calls=response.tool_calls,
                    metadata={"reasoning_content": response.reasoning_content} if response.reasoning_content else {},
                )
                messages.append(tool_message)
                for tool_call in response.tool_calls:
                    if cancel_token:
                        cancel_token.check()
                    arguments, parse_error = self._parse_tool_arguments(tool_call)
                    if parse_error:
                        result_content = json.dumps({"success": False, "error": parse_error}, ensure_ascii=False)
                        records.append(
                            ToolCallRecord(
                                tool_name=tool_call.name,
                                arguments={},
                                success=False,
                                error=parse_error,
                            )
                        )
                    else:
                        context = self._build_tool_context(session_id, image, cancel_token)
                        result = self.tool_register.execute(tool_call.name, arguments, context)
                        records.append(
                            ToolCallRecord(
                                tool_name=tool_call.name,
                                arguments=arguments,
                                success=result.success,
                                result=result.data,
                                error=result.error,
                                edit_id=result.edit_id,
                                requires_confirmation=result.requires_confirmation,
                            )
                        )
                        result_content = json.dumps(result.to_dict(), ensure_ascii=False, default=str)
                    messages.append(
                        LLMMessage(
                            role=MessageRole.TOOL_RESULT,
                            content=result_content,
                            tool_call_id=tool_call.id,
                            tool_name=tool_call.name,
                        )
                    )
                continue

            if not response.content.strip():
                if response.finish_reason == "length":
                    raise LLMClientError("模型输出被 max_tokens 截断，未返回可执行调色参数。请重试或提高 Max Tokens。")
                raise LLMClientError("模型没有返回文本、JSON 或工具调用，无法应用调色。")

            assistant_message = LLMMessage(role=MessageRole.ASSISTANT, content=response.content)
            messages.append(assistant_message)
            return assistant_message, records

        assistant_message = LLMMessage(
            role=MessageRole.ASSISTANT,
            content="处理步骤过多，请简化需求或分步操作。",
        )
        messages.append(assistant_message)
        return assistant_message, records

    def _build_system_prompt(self) -> str:
        tool_lines = [
            f"- {spec.name}: {spec.description}"
            for spec in self.tool_register.list_specs()
        ]
        return (
            "你是 TempusLoom 调色助手，可以通过工具完成真实调色操作。\n"
            "需要修改图片时调用工具；只需要解释或确认时直接回答。不要在普通文本中伪造工具执行结果。\n\n"
            "多轮调色规则：每轮用户看到和你收到的图片都是当前已渲染结果，可能已经包含上一次 AI 调色。"
            "你必须根据用户措辞判断是基于上一次继续微调，还是重新设计风格。"
            "如果用户说“再、更、稍微、继续、上一版基础上”等，默认在当前编辑状态和上一次调色参数基础上做增量调整；"
            "如果用户明确说“重新、换一种、从头、不要刚才效果”，再生成新的整体方案。\n\n"
            "效率要求：需要改图时，直接调用 apply_adjustment_preview 或 create_mask_layer，"
            "不要先输出长篇分析，不要在思考中完整展开 JSON 示例，避免耗尽输出预算。\n\n"
            "调色 JSON 规则如下：\n"
            f"{COLOR_GRADING_SYSTEM_PROMPT}\n\n"
            "可用工具：\n"
            f"{chr(10).join(tool_lines)}\n\n"
            "ReAct 行为规则：先根据用户需求和图片状态判断是否需要行动；如需行动，调用最合适的工具；"
            "看到工具结果后再给出简短中文总结。参数必须克制、可逆，局部调整优先使用蒙版。"
        )

    def _register_default_tools(self) -> None:
        register_bash_tool(self.tool_register)
        register_native_tools(self.tool_register)
        register_analysis_tools(self.tool_register)

    def _build_tool_context(
        self,
        session_id: str,
        image: dict[str, Any] | None,
        cancel_token: CancelToken | None,
    ) -> ToolContext:
        if self._tool_context_factory is not None:
            return self._tool_context_factory(session_id, image, cancel_token)
        return ToolContext(
            session_id=session_id,
            image=image,
            current_adjust=(image or {}).get("current_adjust") if isinstance(image, dict) else None,
            cancel_token=cancel_token,
            workspace=str(Path.cwd()),
        )

    @staticmethod
    def _parse_tool_arguments(tool_call: ToolCallInfo) -> tuple[dict[str, Any], str | None]:
        try:
            parsed = json.loads(tool_call.arguments or "{}")
        except json.JSONDecodeError as exc:
            return {}, f"Tool arguments JSON parse error: {exc}"
        if not isinstance(parsed, dict):
            return {}, "Tool arguments must be a JSON object."
        return parsed, None

    @staticmethod
    def _image_contents_from_dict(image: dict[str, Any] | None) -> list[ImageContent]:
        image_data = ColorAgent._normalize_image_dict(image)
        if not image_data:
            return []
        file_path = image_data.get("file_path") or image_data.get("path")
        if not file_path and not image_data.get("base64"):
            return []
        return [
            ImageContent(
                file_path=str(file_path),
                mime_type=str(image_data.get("mime_type", "image/jpeg")),
                detail=str(image_data.get("detail", "low")),
                data_base64=str(image_data.get("base64", "")),
            )
        ]

    @staticmethod
    def _image_metadata_for_log(image: dict[str, Any] | None) -> dict[str, Any]:
        if not image:
            return {}
        return {
            key: value
            for key, value in image.items()
            if key not in {"base64", "data"}
        }

    @staticmethod
    def _normalize_image_dict(image: dict[str, Any] | None) -> dict[str, Any]:
        if not isinstance(image, dict):
            return {}
        nested = image.get("image")
        if isinstance(nested, dict):
            return nested
        return image

    @staticmethod
    def _build_chat_user_content(user_message: str, image: dict[str, Any] | None) -> str:
        if not isinstance(image, dict) or "current_adjust" not in image:
            return user_message.strip()
        image_meta = {
            "imageName": image.get("image_name"),
            "width": (image.get("image") or {}).get("width") if isinstance(image.get("image"), dict) else image.get("width"),
            "height": (image.get("image") or {}).get("height") if isinstance(image.get("image"), dict) else image.get("height"),
            "byteSize": (image.get("image") or {}).get("byte_size") if isinstance(image.get("image"), dict) else image.get("byte_size"),
            "mimeType": (image.get("image") or {}).get("mime_type") if isinstance(image.get("image"), dict) else image.get("mime_type"),
        }
        return (
            f"用户需求：{user_message.strip()}\n\n"
            "重要上下文：本轮附带图片是当前已渲染结果，不是原始未调色图片；"
            "如果用户要求继续微调，请基于当前渲染结果、当前编辑状态和上一次 AI 调色参数继续调整。\n\n"
            f"图片信息：\n{json.dumps(image_meta, ensure_ascii=False, indent=2)}\n\n"
            f"当前已有编辑状态（完整参数，会作为继续微调的基础）：\n"
            f"{json.dumps(image.get('current_adjust', {}), ensure_ascii=False, indent=2)}\n\n"
            f"上一次 AI 调色参数/工具 payload（如果存在，应作为“再调一点/继续微调”的基础）：\n"
            f"{json.dumps(image.get('previous_ai_payload', {}), ensure_ascii=False, indent=2)}"
        )

    @staticmethod
    def _try_parse_adjustment_payload(text: str) -> dict[str, Any] | None:
        try:
            return TempusLoomColorAgent._parse_adjustment_payload(text)
        except Exception:
            return None


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
            f"当前已有编辑状态：\n{current_adjust_json}\n\n"
            f"{TempusLoomColorAgent._build_local_adjustment_guidance(context.style_prompt)}"
            "请结合图片预览生成新的 TempusLoom 调色 JSON。"
        )

    @staticmethod
    def _build_local_adjustment_guidance(style_prompt: str) -> str:
        normalized = style_prompt.strip().lower()
        mentions_sky = any(keyword in normalized for keyword in ("天空", "sky", "蓝天"))
        mentions_ground = any(keyword in normalized for keyword in ("地面", "ground", "前景", "foreground"))
        asks_blue = any(keyword in normalized for keyword in ("蓝", "blue", "更青", "青蓝"))
        preserve_ground_exposure = mentions_ground and any(
            keyword in normalized
            for keyword in ("保持正常", "正常曝光", "曝光不变", "不要影响", "不变", "保持")
        )

        if mentions_sky and (asks_blue or preserve_ground_exposure):
            return (
                "局部调色策略：用户在调整天空，同时要求地面保持正常曝光。"
                "请优先输出完整 layers 数组，使用一个 type 为 mask 的线性渐变蒙版图层，"
                'mask 使用 {"type": "linear", "start": {"x": 0.5, "y": 0.0}, '
                '"end": {"x": 0.5, "y": 0.55}, "featherRadius": 8} 作为起点，'
                '让 "payload" 只作用于天空区域；不要在该 mask layer 的 "payload" 中提高或降低地面曝光。'
                "地面保持正常曝光，只通过蒙版衰减避免影响地面。"
                '天空变蓝可优先使用 "payload".hsl.blue、"payload".hsl.aqua、"payload".colorGrading.highlightsHue/'
                "highlightsSaturation，必要时轻微降低 highlights。"
                "\n\n"
            )

        return ""

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
        edit_root_keys = {"adjust", "mask", "layers", "imagePath", "image_path"}
        if not any(key in parsed for key in edit_root_keys):
            parsed = {"adjust": parsed}
        if not isinstance(parsed.get("adjust"), dict):
            if "adjust" in parsed:
                raise AgentResponseError("模型返回的 adjust 字段不是对象。")
        return parsed
