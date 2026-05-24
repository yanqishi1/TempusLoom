"""SQLite-backed conversation persistence for ColorAgent."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from tempusloom.agent.base.llm_message import LLMMessage

from . import schema


class ConversationStore:
    """Persist user and assistant messages by session id."""

    def __init__(self, db_path: Path | None = None) -> None:
        self.db_path = db_path or Path.home() / ".tempusloom" / "agent" / "conversation.db"
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def save_message(self, session_id: str, message: LLMMessage) -> None:
        """Save one message. Storage failures are intentionally non-fatal."""
        try:
            now = datetime.now(timezone.utc).isoformat()
            payload = json.dumps(message.to_dict(), ensure_ascii=False)
            with sqlite3.connect(self.db_path) as conn:
                conn.execute(
                    schema.UPSERT_SESSION,
                    (session_id, now, now, json.dumps({}, ensure_ascii=False)),
                )
                conn.execute(
                    schema.INSERT_MESSAGE,
                    (session_id, message.role.value, message.content, payload, message.created_at.isoformat()),
                )
                conn.commit()
        except sqlite3.Error:
            return

    def save_messages(self, session_id: str, messages: list[LLMMessage]) -> None:
        for message in messages:
            self.save_message(session_id, message)

    def load_messages(self, session_id: str, limit: int = 20) -> list[LLMMessage]:
        try:
            with sqlite3.connect(self.db_path) as conn:
                rows = conn.execute(schema.LOAD_MESSAGES, (session_id, max(1, int(limit)))).fetchall()
        except sqlite3.Error:
            return []

        messages: list[LLMMessage] = []
        for (message_json,) in reversed(rows):
            try:
                payload = json.loads(message_json)
            except json.JSONDecodeError:
                continue
            if isinstance(payload, dict):
                messages.append(LLMMessage.from_dict(payload))
        return messages

    def delete_session(self, session_id: str) -> None:
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute(schema.DELETE_SESSION_MESSAGES, (session_id,))
                conn.execute(schema.DELETE_SESSION, (session_id,))
                conn.commit()
        except sqlite3.Error:
            return

    def close(self) -> None:
        """Kept for API symmetry; connections are short-lived."""

    def _init_db(self) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(schema.CREATE_SESSIONS_TABLE)
            conn.execute(schema.CREATE_MESSAGES_TABLE)
            conn.execute(schema.CREATE_MESSAGES_INDEX)
            conn.commit()
