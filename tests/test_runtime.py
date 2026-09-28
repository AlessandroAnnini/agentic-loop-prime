from __future__ import annotations

from agentic_loop_prime.runtime import adapter_command, detect_runtime


def test_detect_runtime_env_keys() -> None:
    assert detect_runtime({}) == "unknown"
    assert detect_runtime({"TERM_PROGRAM": "cursor"}) == "cursor"
    assert detect_runtime({"CURSOR_AGENT": "1"}) == "cursor"
    assert detect_runtime({"CURSOR_TRACE_ID": "abc"}) == "cursor"
    assert detect_runtime({"TERM_PROGRAM": "vscode"}) == "vscode"
    assert detect_runtime({"VSCODE_PID": "99"}) == "vscode"
    assert detect_runtime({"CLAUDECODE": "1"}) == "claude"
    assert detect_runtime({"CLAUDE_CODE_ENTRYPOINT": "cli"}) == "claude"


def test_cursor_beats_vscode_and_claude() -> None:
    env = {
        "TERM_PROGRAM": "vscode",
        "VSCODE_PID": "1",
        "CURSOR_AGENT": "1",
        "CLAUDECODE": "1",
    }
    assert detect_runtime(env) == "cursor"


def test_adapter_command_names_runtime() -> None:
    cmd = adapter_command("cursor")
    assert "agentic_loop_prime.adapters" in cmd
    assert cmd.endswith("cursor") or cmd.endswith("'cursor'")
