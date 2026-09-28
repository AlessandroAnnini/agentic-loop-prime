"""Cursor CLI one-shot. Prime already decided whether a helper runs."""

from __future__ import annotations

import shutil
import sys

from agentic_loop_prime.adapters.policy import helper_instructions, load_frame, run_frame


def cursor_binary() -> str | None:
    return shutil.which("agent") or shutil.which("cursor-agent")


def cursor_writer_argv(
    prompt: str,
    binary: str = "agent",
    *,
    app_writable: bool = True,
) -> list[str]:
    argv = [binary, "-p", "--trust", "--output-format", "text"]
    if app_writable:
        argv.insert(2, "--force")
    else:
        argv.insert(2, "--mode=ask")
    argv.append(prompt)
    return argv


def cursor_helper_argv(prompt: str, binary: str = "agent") -> list[str]:
    return [binary, "-p", "--mode=ask", "--trust", "--output-format", "text", prompt]


def run() -> int:
    binary = cursor_binary()
    if binary is None:
        print("agent is not on PATH", file=sys.stderr)
        return 1
    try:
        frame = load_frame()
    except FileNotFoundError as exc:
        print(f"ERROR {exc}", file=sys.stderr)
        return 1
    helper_cmd = None
    if frame.helper == "explore":
        helper_cmd = cursor_helper_argv(helper_instructions(frame), binary)
    writer_cmd = cursor_writer_argv(frame.prompt, binary, app_writable=frame.app_writable)
    return run_frame(helper_cmd=helper_cmd, writer_cmd=writer_cmd, frame=frame)
