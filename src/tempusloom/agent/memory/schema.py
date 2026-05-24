"""SQLite schema for agent conversation memory."""

CREATE_SESSIONS_TABLE = """
CREATE TABLE IF NOT EXISTS agent_sessions (
    session_id TEXT PRIMARY KEY,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    metadata_json TEXT NOT NULL DEFAULT '{}'
)
"""

CREATE_MESSAGES_TABLE = """
CREATE TABLE IF NOT EXISTS agent_messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    message_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY(session_id) REFERENCES agent_sessions(session_id)
)
"""

CREATE_MESSAGES_INDEX = """
CREATE INDEX IF NOT EXISTS idx_agent_messages_session_id_id
ON agent_messages(session_id, id)
"""

UPSERT_SESSION = """
INSERT INTO agent_sessions(session_id, created_at, updated_at, metadata_json)
VALUES (?, ?, ?, ?)
ON CONFLICT(session_id) DO UPDATE SET
    updated_at = excluded.updated_at,
    metadata_json = excluded.metadata_json
"""

INSERT_MESSAGE = """
INSERT INTO agent_messages(session_id, role, content, message_json, created_at)
VALUES (?, ?, ?, ?, ?)
"""

LOAD_MESSAGES = """
SELECT message_json
FROM agent_messages
WHERE session_id = ?
ORDER BY id DESC
LIMIT ?
"""

DELETE_SESSION_MESSAGES = "DELETE FROM agent_messages WHERE session_id = ?"
DELETE_SESSION = "DELETE FROM agent_sessions WHERE session_id = ?"
