from __future__ import annotations

import json
from pathlib import Path

import yaml

from agentic_loop_prime.cli import main
from agentic_loop_prime.paths import load_yaml
from agentic_loop_prime.unattended import run_unattended


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_unattended_agent_needed_intake(tmp_path: Path) -> None:
    brief = tmp_path / "brief"
    brief.mkdir()
    memory = tmp_path / "memory"
    code = run_unattended(memory, brief_dir=brief)
    assert code == 3
    prompt = memory / "now" / "next-prompt.md"
    assert prompt.is_file()
    text = prompt.read_text(encoding="utf-8")
    assert "DELEGATE" in text
    assert "intake" in text
    assert (memory / "now" / "continue.sh").is_file()
    assert (memory / "now" / "next-action.json").is_file()


def test_unattended_autonomous_skips_charter_review(tmp_path: Path) -> None:
    brief = tmp_path / "brief"
    brief.mkdir()
    memory = tmp_path / "memory"
    memory.mkdir()
    _write(memory / "charter.md", "# Charter\n\nShip a todo CLI.\n")
    _write(
        memory / "backlog.yaml",
        "version: 1\nfeatures:\n  - id: todo-cli\n    name: Todo\n    design_track: light\n",
    )
    _write(
        memory / "run-state.yaml",
        yaml.safe_dump(
            {
                "version": 1,
                "program_state": "idle",
                "charter_signed": False,
                "research_track": "none",
                "lock": None,
                "loop": {"initial": 20, "remaining": 20},
                "features": [],
            },
            sort_keys=False,
        ),
    )
    code = run_unattended(memory, brief_dir=brief, autonomous=True)
    assert code == 3
    state = load_yaml(memory / "run-state.yaml")
    assert state.get("charter_signed") is True
    payload = json.loads((memory / "now" / "next-action.json").read_text(encoding="utf-8"))
    assert payload["kind"] == "DELEGATE"
    assert payload["reason"] != "charter_review"
    assert payload["skill"] in ("design", "intake")


def test_unattended_done_exits_zero(tmp_path: Path) -> None:
    memory = tmp_path / "memory"
    memory.mkdir()
    _write(
        memory / "run-state.yaml",
        yaml.safe_dump(
            {
                "version": 1,
                "program_state": "done",
                "lock": None,
                "loop": {"initial": 20, "remaining": 0},
                "features": [],
            },
            sort_keys=False,
        ),
    )
    code = run_unattended(memory)
    assert code == 0


def test_cli_unattended_exit_3(tmp_path: Path) -> None:
    brief = tmp_path / "brief"
    brief.mkdir()
    memory = tmp_path / "memory"
    code = main(
        [
            "unattended",
            "--memory",
            str(memory),
            "--brief-dir",
            str(brief),
        ]
    )
    assert code == 3
