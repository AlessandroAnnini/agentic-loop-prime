"""VS Code Claude extension has no headless runner. Use the standalone CLI."""

from __future__ import annotations

import shutil
import sys

from agentic_loop_prime.adapters.claude import run as claude_run


def run() -> int:
    if shutil.which("claude") is None:
        print(
            "Install the standalone Claude Code CLI. "
            "The VS Code extension does not put claude on PATH.",
            file=sys.stderr,
        )
        return 1
    return claude_run()
