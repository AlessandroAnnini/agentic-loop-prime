"""Which editor this process is running in. Prime picks the adapter."""

from __future__ import annotations

import shlex
import sys
from collections.abc import Mapping

RuntimeName = str  # cursor | vscode | claude | unknown


def _present(env: Mapping[str, str], key: str) -> bool:
    return bool(str(env.get(key) or "").strip())


def detect_runtime(env: Mapping[str, str]) -> RuntimeName:
    """First match wins. Cursor beats VS Code when both are set."""
    term = str(env.get("TERM_PROGRAM") or "").strip().lower()
    if term == "cursor" or _present(env, "CURSOR_AGENT") or _present(env, "CURSOR_TRACE_ID"):
        return "cursor"
    if term == "vscode" or _present(env, "VSCODE_PID"):
        return "vscode"
    if _present(env, "CLAUDECODE") or _present(env, "CLAUDE_CODE_ENTRYPOINT"):
        return "claude"
    return "unknown"


def adapter_command(runtime: str) -> str:
    """Shell command Prime uses when it detected the editor."""
    return (
        f"{shlex.quote(sys.executable)} -m agentic_loop_prime.adapters "
        f"{shlex.quote(runtime)}"
    )
