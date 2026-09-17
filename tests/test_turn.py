from __future__ import annotations

from pathlib import Path

from agentic_loop_prime.fingerprint import write_fingerprint
from agentic_loop_prime.schedule import _write_hint
from agentic_loop_prime.turn import (
    app_digest,
    artifact_path,
    artifact_ready,
    should_pass_after_agent,
    turn_policy,
    verify_tree_drifted,
)


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_artifact_ready_intake_charter(tmp_path: Path) -> None:
    memory = tmp_path / "memory"
    memory.mkdir()
    assert artifact_ready(memory, "intake", "charter", "program") is False
    _write(memory / "charter.md", "   \n")
    assert artifact_ready(memory, "intake", "charter", "program") is False
    _write(memory / "charter.md", "# Charter\n\nShip it.\n")
    assert artifact_ready(memory, "intake", "charter", "program") is True


def test_app_digest_empty_and_change(tmp_path: Path) -> None:
    app = tmp_path / "app"
    empty = app_digest(app)
    assert empty == app_digest(None)
    app.mkdir()
    before = app_digest(app)
    assert before == empty
    _write(app / "main.py", "print(1)\n")
    assert app_digest(app) != before


def test_verify_tree_drifted(tmp_path: Path) -> None:
    memory = tmp_path / "memory"
    memory.mkdir()
    app = tmp_path / "app"
    app.mkdir()
    _write(app / "main.py", "print(1)\n")
    drifted, msg = verify_tree_drifted(memory, "todo-cli", app)
    assert drifted is False
    assert "baseline" in msg
    write_fingerprint(memory, "todo-cli", app)
    drifted, _ = verify_tree_drifted(memory, "todo-cli", app)
    assert drifted is False
    _write(app / "extra.py", "x = 1\n")
    drifted, msg = verify_tree_drifted(memory, "todo-cli", app)
    assert drifted is True
    assert "drifted" in msg


def test_turn_policy_build_only_writable() -> None:
    verify = turn_policy("verify", "prove")
    assert verify["app_writable"] is False
    assert verify["writable"] == ["memory/**"]
    build = turn_policy("build", "1")
    assert build["app_writable"] is True
    assert "app/**" in build["writable"]


def test_should_pass_after_agent(tmp_path: Path) -> None:
    memory = tmp_path / "memory"
    memory.mkdir()
    app = tmp_path / "app"
    app.mkdir()
    before = app_digest(app)
    assert (
        should_pass_after_agent(
            skill="intake",
            sub="charter",
            feature_id="program",
            memory=memory,
            app_dir=app,
            before_digest=before,
        )
        is False
    )
    _write(memory / "charter.md", "# Charter\n")
    assert (
        should_pass_after_agent(
            skill="intake",
            sub="charter",
            feature_id="program",
            memory=memory,
            app_dir=app,
            before_digest=before,
        )
        is True
    )
    assert (
        should_pass_after_agent(
            skill="build",
            sub="1",
            feature_id="todo-cli",
            memory=memory,
            app_dir=app,
            before_digest=before,
        )
        is False
    )
    _write(app / "main.py", "print(1)\n")
    assert (
        should_pass_after_agent(
            skill="build",
            sub="1",
            feature_id="todo-cli",
            memory=memory,
            app_dir=app,
            before_digest=before,
        )
        is True
    )


def test_artifact_path_matches_write_hint(tmp_path: Path) -> None:
    memory = tmp_path / "memory"
    cases = (
        ("intake", "charter", "program"),
        ("intake", "research", "program"),
        ("intake", "backlog", "program"),
        ("design", "brief", "todo-cli"),
        ("design", "ux", "todo-cli"),
        ("design", "ui", "todo-cli"),
    )
    for skill, sub, fid in cases:
        hint = _write_hint(skill, sub, fid)
        path = artifact_path(memory, skill, sub, fid)
        assert path is not None
        assert path == memory.parent / hint
