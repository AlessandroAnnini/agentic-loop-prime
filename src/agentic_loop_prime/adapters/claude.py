"""Claude Code one-shot. Prime already decided whether a helper runs."""

from __future__ import annotations

import os
import shutil
import sys

from agentic_loop_prime.adapters.policy import helper_instructions, load_frame, run_frame


def claude_writer_argv(prompt: str, *, app_writable: bool, binary: str = "claude") -> list[str]:
    argv = [binary, "--permission-prompts", "none"]
    if not app_writable:
        argv.extend(["--disallowedTools", "Edit(app/**)"])
    argv.extend(["-p", prompt])
    return argv


def claude_helper_argv(
    prompt: str,
    *,
    bare: bool = False,
    binary: str = "claude",
) -> list[str]:
    argv = [binary]
    if bare:
        argv.append("--bare")
    argv.extend(
        [
            "--permission-mode",
            "dontAsk",
            "--permission-prompts",
            "none",
            "--tools",
            "Read,Grep,Glob",
            "--disallowedTools",
            "Edit,Write,Agent",
            "-p",
            prompt,
        ]
    )
    return argv


def run() -> int:
    if shutil.which("claude") is None:
        print("claude is not on PATH", file=sys.stderr)
        return 1
    try:
        frame = load_frame()
    except (FileNotFoundError, ValueError) as exc:
        print(f"ERROR {exc}", file=sys.stderr)
        return 1
    bare = bool(os.environ.get("ANTHROPIC_API_KEY"))
    helper_cmd = None
    if frame.helper == "explore":
        helper_cmd = claude_helper_argv(helper_instructions(frame), bare=bare)
    writer_cmd = claude_writer_argv(frame.prompt, app_writable=frame.app_writable)
    return run_frame(helper_cmd=helper_cmd, writer_cmd=writer_cmd, frame=frame)
