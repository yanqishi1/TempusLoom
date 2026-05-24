"""Cancellation primitives for agent execution."""

from __future__ import annotations

import threading


class AgentCancelledError(Exception):
    """Raised when an agent operation is cancelled by the user."""


class CancelToken:
    """Thread-safe cancellation token shared by UI and worker threads."""

    def __init__(self) -> None:
        self._event = threading.Event()

    def cancel(self) -> None:
        """Request cancellation."""
        self._event.set()

    @property
    def is_cancelled(self) -> bool:
        """Return True if cancellation has been requested."""
        return self._event.is_set()

    def check(self) -> None:
        """Raise AgentCancelledError if cancellation has been requested."""
        if self._event.is_set():
            raise AgentCancelledError("Agent operation cancelled.")
