"""Bash/PowerShell command execution tool with whitelist policy."""

from __future__ import annotations

import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .tool_register import ToolContext, ToolRegister, ToolResult, ToolSpec


@dataclass
class BashWhitelistPolicy:
    """Simple prefix whitelist for shell commands."""

    allowed_prefixes: list[list[str]] = field(
        default_factory=lambda: [
            ["git", "status"],
            ["git", "diff"],
            ["git", "log"],
            ["rg"],
            ["python", "-m", "pytest"],
            ["pytest"],
        ]
    )

    def is_allowed(self, command: str) -> bool:
        if self._contains_shell_control(command):
            return False
        tokens = command.strip().split()
        if not tokens:
            return False
        for prefix in self.allowed_prefixes:
            if len(tokens) >= len(prefix) and tokens[: len(prefix)] == prefix:
                return True
        return False

    @staticmethod
    def _contains_shell_control(command: str) -> bool:
        control_tokens = ("|", "&&", "||", ";", "`", "$(", ">", "<")
        return any(token in command for token in control_tokens)


def execute_bash_tool(args: dict[str, Any], context: ToolContext) -> ToolResult:
    """Execute a whitelisted command."""
    context.check_cancelled()
    command = str(args.get("command", "")).strip()
    timeout = int(args.get("timeout_seconds", 30))
    if not command:
        return ToolResult(success=False, error="Missing command.")

    policy = context.metadata.get("bash_policy")
    if not isinstance(policy, BashWhitelistPolicy):
        policy = BashWhitelistPolicy()
    if not policy.is_allowed(command):
        return ToolResult(
            success=False,
            error="Command requires user confirmation.",
            requires_confirmation=True,
            data={"command": command},
        )

    workspace = Path(context.workspace or ".").resolve()
    try:
        process = subprocess.Popen(
            command,
            cwd=str(workspace),
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        start = time.monotonic()
        while process.poll() is None:
            if time.monotonic() - start > timeout:
                process.kill()
                stdout, stderr = process.communicate()
                return ToolResult(
                    success=False,
                    error="Command execution timed out.",
                    data={"command": command, "stdout": stdout[-12000:], "stderr": stderr[-12000:]},
                )
            if context.cancel_token and context.cancel_token.is_cancelled:
                process.kill()
                process.communicate()
                context.check_cancelled()
            time.sleep(0.05)
        stdout, stderr = process.communicate()
        returncode = process.returncode
    except OSError as exc:
        return ToolResult(success=False, error=str(exc), data={"command": command})

    context.check_cancelled()
    return ToolResult(
        success=returncode == 0,
        data={
            "command": command,
            "returncode": returncode,
            "stdout": stdout[-12000:],
            "stderr": stderr[-12000:],
        },
        error=stderr.strip() if returncode != 0 else "",
    )


def register_bash_tool(register: ToolRegister) -> None:
    register.register(
        ToolSpec(
            name="execute_bash",
            description="Execute a whitelisted local shell command. Non-whitelisted commands require user confirmation.",
            input_schema={
                "type": "object",
                "properties": {
                    "command": {"type": "string", "description": "Command line to execute."},
                    "timeout_seconds": {"type": "integer", "description": "Execution timeout in seconds."},
                },
                "required": ["command"],
            },
        ),
        execute_bash_tool,
    )
