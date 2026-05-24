"""Prompt logging for LLM requests and responses."""

from __future__ import annotations

import base64
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from .llm_message import LLMMessage


class LLMLogger:
    """Append-only LLM log writer.

    Logging failures are swallowed deliberately so diagnostics never block
    agent execution.
    """

    def __init__(self, log_dir: Path | None = None, retention_days: int = 14) -> None:
        self.log_dir = log_dir or Path.home() / ".tempusloom" / "agent"
        self.retention_days = retention_days
        try:
            self.log_dir.mkdir(parents=True, exist_ok=True)
            self.cleanup_old_logs()
        except OSError:
            pass

    def log_request(
        self,
        session_id: str,
        turn: int,
        system_prompt: str,
        messages: list[LLMMessage],
        tools: list[dict[str, Any]],
        raw_payload: dict[str, Any],
    ) -> None:
        """Record a full LLM request with image payloads redacted."""
        try:
            now = datetime.now()
            lines = [
                f"========== {now.strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]} ==========",
                f"Session: {session_id}",
                f"Turn: {turn}",
                "",
                "--- System Prompt ---",
                system_prompt,
                "",
                "--- Messages ---",
            ]
            for index, message in enumerate(messages, start=1):
                lines.append(f"[{index}] role: {message.role.value}")
                lines.append(f"    content: {message.content}")
                if message.images:
                    lines.append(f"    images: {[image.file_path for image in message.images]}")
                if message.tool_calls:
                    lines.append(
                        "    tool_calls: "
                        + json.dumps([tc.to_dict() for tc in message.tool_calls], ensure_ascii=False)
                    )
                if message.tool_call_id:
                    lines.append(f"    tool_call_id: {message.tool_call_id}")
                if message.tool_name:
                    lines.append(f"    tool_name: {message.tool_name}")

            lines.extend(
                [
                    "",
                    "--- Tools Available ---",
                    *[f"- {self._tool_name(tool)}" for tool in tools],
                    "",
                    "--- Request Payload ---",
                    json.dumps(self._redact_payload(raw_payload), ensure_ascii=False, indent=2),
                    "",
                ]
            )
            self._append("\n".join(lines))
        except Exception:
            pass

    def log_response(self, session_id: str, response: Any) -> None:
        """Record an LLM response."""
        try:
            if hasattr(response, "to_dict"):
                payload = response.to_dict()
            else:
                payload = response
            lines = [
                "--- Response ---",
                f"Session: {session_id}",
                json.dumps(self._redact_payload(payload), ensure_ascii=False, indent=2, default=str),
                "========== END ==========",
                "",
            ]
            self._append("\n".join(lines))
        except Exception:
            pass

    def cleanup_old_logs(self) -> None:
        """Delete daily log files older than retention_days."""
        cutoff = datetime.now() - timedelta(days=self.retention_days)
        try:
            for path in self.log_dir.glob("llm_*.log"):
                if datetime.fromtimestamp(path.stat().st_mtime) < cutoff:
                    path.unlink()
        except OSError:
            pass

    def _append(self, text: str) -> None:
        path = self.log_dir / f"llm_{datetime.now().strftime('%Y-%m-%d')}.log"
        with path.open("a", encoding="utf-8") as handle:
            handle.write(text)
            if not text.endswith("\n"):
                handle.write("\n")

    @staticmethod
    def _tool_name(tool: dict[str, Any]) -> str:
        function = tool.get("function")
        if isinstance(function, dict):
            return str(function.get("name", tool.get("name", "")))
        return str(tool.get("name", ""))

    def _redact_payload(self, value: Any) -> Any:
        if isinstance(value, dict):
            return {key: self._redact_value(key, item) for key, item in value.items()}
        if isinstance(value, list):
            return [self._redact_payload(item) for item in value]
        return value

    def _redact_value(self, key: str, value: Any) -> Any:
        if isinstance(value, str) and self._looks_like_image_data(key, value):
            size_kb = max(1, len(value) * 3 // 4 // 1024)
            return f"<image: base64, {size_kb}KB>"
        return self._redact_payload(value)

    @staticmethod
    def _looks_like_image_data(key: str, value: str) -> bool:
        lowered = key.lower()
        if value.startswith("data:image/"):
            return True
        if lowered in {"base64", "data"} and len(value) > 512:
            try:
                base64.b64decode(value[:512] + "==", validate=False)
                return True
            except Exception:
                return False
        return False
