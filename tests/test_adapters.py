from __future__ import annotations

import json
import sys
from pathlib import Path

from agentic_loop_prime.adapters.claude import claude_helper_argv, claude_writer_argv, run as claude_run
from agentic_loop_prime.adapters.cursor import cursor_helper_argv, cursor_writer_argv
from agentic_loop_prime.adapters.policy import Frame, run_frame
from agentic_loop_prime.adapters import vscode


def test_cursor_helper_is_ask_mode_without_force() -> None:
    helper = cursor_helper_argv("look", binary="agent")
    writer = cursor_writer_argv("write", binary="agent")
    assert "--mode=ask" in helper
    assert "--force" not in helper
    assert "--resume" not in helper
    assert "--continue" not in helper
    assert "--worktree" not in helper
    assert "--force" in writer
    assert "--mode=ask" not in writer
    assert "--resume" not in writer
    readonly = cursor_writer_argv("check", binary="agent", app_writable=False)
    assert "--force" not in readonly
    assert "--mode=ask" in readonly


def test_claude_helper_cannot_edit_or_spawn() -> None:
    argv = claude_helper_argv("look", bare=False, binary="claude")
    assert "--resume" not in argv
    assert "--continue" not in argv
    assert "--agents" not in argv
    tools = argv[argv.index("--tools") + 1]
    assert "Agent" not in tools.split(",")
    denied = argv[argv.index("--disallowedTools") + 1]
    assert "Agent" in denied.split(",")
    assert "Edit" in denied.split(",")
    writer = claude_writer_argv("write", app_writable=False, binary="claude")
    assert "Edit(app/**)" in writer
    assert "--resume" not in writer


def test_claude_helper_bare_only_with_flag() -> None:
    assert "--bare" in claude_helper_argv("look", bare=True)
    assert "--bare" not in claude_helper_argv("look", bare=False)


def test_helper_app_edit_fails_before_writer(tmp_path: Path) -> None:
    app = tmp_path / "app"
    app.mkdir()
    (app / "a.py").write_text("x = 1\n", encoding="utf-8")
    out = tmp_path / "memory" / "now" / "explore.md"
    sentinel = tmp_path / "writer-ran"
    extra = app / "b.py"
    helper = [
        sys.executable,
        "-c",
        f"open({str(extra)!r}, 'w').write('y\\n'); print('map')",
    ]
    writer = [
        sys.executable,
        "-c",
        f"open({str(sentinel)!r}, 'w').write('1')",
    ]
    frame = Frame(
        prompt="build",
        helper="explore",
        helper_output=out,
        app_dir=app,
        app_writable=True,
    )
    code = run_frame(helper_cmd=helper, writer_cmd=writer, frame=frame)
    assert code == 1
    assert not sentinel.exists()


def test_helper_stdout_becomes_note_then_writer_runs(tmp_path: Path) -> None:
    app = tmp_path / "app"
    app.mkdir()
    (app / "a.py").write_text("x = 1\n", encoding="utf-8")
    out = tmp_path / "memory" / "now" / "explore.md"
    sentinel = tmp_path / "writer-ran"
    helper = [sys.executable, "-c", "print('file map')"]
    writer = [sys.executable, "-c", f"open({str(sentinel)!r}, 'w').write('1')"]
    frame = Frame(
        prompt="build",
        helper="explore",
        helper_output=out,
        app_dir=app,
        app_writable=True,
    )
    code = run_frame(helper_cmd=helper, writer_cmd=writer, frame=frame)
    assert code == 0
    assert out.read_text(encoding="utf-8").strip() == "file map"
    assert sentinel.is_file()


def test_vscode_delegates_to_claude(monkeypatch, capsys) -> None:
    monkeypatch.setattr(vscode.shutil, "which", lambda name: "/usr/bin/claude" if name == "claude" else None)
    monkeypatch.setattr(vscode, "claude_run", lambda: 7)
    assert vscode.run() == 7
    monkeypatch.setattr(vscode.shutil, "which", lambda name: None)
    assert vscode.run() == 1
    err = capsys.readouterr().err
    assert "standalone Claude Code CLI" in err


def test_claude_adapter_requires_binary_and_prompt(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.setenv("PATH", "")
    prompt = tmp_path / "prompt.md"
    prompt.write_text("do the skill\n", encoding="utf-8")
    monkeypatch.setenv("ALP_PROMPT_FILE", str(prompt))
    monkeypatch.delenv("ALP_POLICY_FILE", raising=False)
    assert claude_run() == 1
    assert "claude" in capsys.readouterr().err.lower()

    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    stub = bin_dir / "claude"
    stub.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    stub.chmod(0o755)
    monkeypatch.setenv("PATH", str(bin_dir))
    monkeypatch.delenv("ALP_PROMPT_FILE", raising=False)
    assert claude_run() == 1
    assert "ALP_PROMPT_FILE" in capsys.readouterr().err


def test_policy_roundtrip_fields(tmp_path: Path, monkeypatch) -> None:
    prompt = tmp_path / "prompt.md"
    prompt.write_text("step\n", encoding="utf-8")
    policy = tmp_path / "policy.json"
    policy.write_text(
        json.dumps(
            {
                "helper": "none",
                "app_writable": False,
                "app_dir": str(tmp_path / "app"),
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("ALP_PROMPT_FILE", str(prompt))
    monkeypatch.setenv("ALP_POLICY_FILE", str(policy))
    from agentic_loop_prime.adapters.policy import load_frame

    frame = load_frame()
    assert frame.helper == "none"
    assert frame.app_writable is False
    assert frame.app_dir == tmp_path / "app"
