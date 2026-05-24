"""Conversation message model used by all LLM providers."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from tempusloom.agent.llm_client.base import ToolCallInfo


class MessageRole(Enum):
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    TOOL_RESULT = "tool_result"


@dataclass
class ImageContent:
    """Image reference attached to a message."""

    file_path: str
    mime_type: str
    detail: str = "low"
    data_base64: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "file_path": self.file_path,
            "mime_type": self.mime_type,
            "detail": self.detail,
            "data_base64": "",
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ImageContent":
        return cls(
            file_path=str(data.get("file_path", "")),
            mime_type=str(data.get("mime_type", "image/jpeg")),
            detail=str(data.get("detail", "low")),
            data_base64=str(data.get("data_base64", "")),
        )


@dataclass
class Attachment:
    """Non-image attachment attached to a message."""

    type: str
    data: Any
    name: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": self.type,
            "data": self.data,
            "name": self.name,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Attachment":
        return cls(
            type=str(data.get("type", "")),
            data=data.get("data"),
            name=data.get("name"),
        )


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _parse_datetime(value: Any) -> datetime:
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        try:
            parsed = datetime.fromisoformat(value)
            if parsed.tzinfo is None:
                return parsed.replace(tzinfo=timezone.utc)
            return parsed
        except ValueError:
            pass
    return _now_utc()


@dataclass
class LLMMessage:
    """A single conversation message.

    API serialization is intentionally provider-specific and lives in client
    implementations. This class only serializes for persistence/logging.
    """

    role: MessageRole
    content: str = ""
    images: list[ImageContent] = field(default_factory=list)
    attachments: list[Attachment] = field(default_factory=list)
    tool_calls: list["ToolCallInfo"] | None = None
    tool_call_id: str | None = None
    tool_name: str | None = None
    created_at: datetime = field(default_factory=_now_utc)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        from tempusloom.agent.llm_client.base import ToolCallInfo

        tool_calls: list[dict[str, Any]] | None = None
        if self.tool_calls is not None:
            tool_calls = [
                tc.to_dict() if isinstance(tc, ToolCallInfo) else dict(tc)
                for tc in self.tool_calls
            ]
        return {
            "role": self.role.value,
            "content": self.content,
            "images": [image.to_dict() for image in self.images],
            "attachments": [attachment.to_dict() for attachment in self.attachments],
            "tool_calls": tool_calls,
            "tool_call_id": self.tool_call_id,
            "tool_name": self.tool_name,
            "created_at": self.created_at.isoformat(),
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "LLMMessage":
        from tempusloom.agent.llm_client.base import ToolCallInfo

        role_value = data.get("role", MessageRole.USER.value)
        try:
            role = MessageRole(role_value)
        except ValueError:
            role = MessageRole.USER

        raw_tool_calls = data.get("tool_calls")
        tool_calls = None
        if isinstance(raw_tool_calls, list):
            tool_calls = [
                ToolCallInfo.from_dict(item)
                for item in raw_tool_calls
                if isinstance(item, dict)
            ]

        return cls(
            role=role,
            content=str(data.get("content", "")),
            images=[
                ImageContent.from_dict(item)
                for item in data.get("images", [])
                if isinstance(item, dict)
            ],
            attachments=[
                Attachment.from_dict(item)
                for item in data.get("attachments", [])
                if isinstance(item, dict)
            ],
            tool_calls=tool_calls,
            tool_call_id=data.get("tool_call_id"),
            tool_name=data.get("tool_name"),
            created_at=_parse_datetime(data.get("created_at")),
            metadata=data.get("metadata") if isinstance(data.get("metadata"), dict) else {},
        )
