from __future__ import annotations

from pathlib import Path

import yaml

from agentic_loop_prime.cli import main
from agentic_loop_prime.paths import load_yaml
from agentic_loop_prime.request_change import RequestChangeError, request_change


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _done_studio(tmp_path: Path) -> Path:
    memory = tmp_path / "memory"
    memory.mkdir()
    _write(memory / "charter.md", "# Charter\n\nOriginal.\n")
    _write(
        memory / "backlog.yaml",
        yaml.safe_dump(
            {
                "version": 1,
                "features": [
                    {
                        "id": "todo-cli",
                        "name": "Todo",
                        "status": "live",
                        "design_track": "light",
                        "bump": "minor",
                    }
                ],
            },
            sort_keys=False,
        ),
    )
    _write(
        memory / "run-state.yaml",
        yaml.safe_dump(
            {
                "version": 1,
                "program_state": "done",
                "active_feature": "todo-cli",
                "charter_signed": True,
                "lock": None,
                "loop": {"initial": 20, "remaining": 0},
                "features": [
                    {
                        "feature_id": "todo-cli",
                        "status": "live",
                        "design_track": "light",
                    }
                ],
            },
            sort_keys=False,
        ),
    )
    feat = memory / "features" / "todo-cli"
    _write(feat / "brief.md", "# Brief\n\n**Status:** signed\n")
    _write(feat / "plan.md", "### Step 1 — Scaffold\n\n- [x] done\n")
    return memory


def test_request_change_intent_from_done(tmp_path: Path) -> None:
    memory = _done_studio(tmp_path)
    charter = (memory / "charter.md").read_text(encoding="utf-8")
    result = request_change(memory, intent="Add export to CSV")
    assert result.feature_id == "add-export-to-csv"
    assert result.mode == "queue"
    state = load_yaml(memory / "run-state.yaml")
    assert state["program_state"] == "feature_pipeline/pending"
    assert state["active_feature"] == "add-export-to-csv"
    assert state["loop"]["remaining"] >= 1
    live = next(
        r for r in state["features"] if r["feature_id"] == "todo-cli"
    )
    assert live["status"] == "live"
    backlog = load_yaml(memory / "backlog.yaml")
    ids = [f["id"] for f in backlog["features"]]
    assert "add-export-to-csv" in ids
    assert "todo-cli" in ids
    assert (memory / "charter.md").read_text(encoding="utf-8") == charter


def test_request_change_reopens_feature(tmp_path: Path) -> None:
    memory = _done_studio(tmp_path)
    state = load_yaml(memory / "run-state.yaml")
    state["now"] = {"resume_point": "HANDOFF verify todo-cli"}
    _write(memory / "run-state.yaml", yaml.safe_dump(state, sort_keys=False))
    result = request_change(memory, feature_id="todo-cli")
    assert result.mode == "reopen"
    assert result.feature_id == "todo-cli"
    assert not (memory / "features" / "todo-cli" / "brief.md").exists()
    plan = (memory / "features" / "todo-cli" / "plan.md").read_text(encoding="utf-8")
    assert "- [x]" not in plan
    assert "- [ ]" in plan
    state = load_yaml(memory / "run-state.yaml")
    assert state["program_state"] == "feature_pipeline/designing"
    assert state["active_feature"] == "todo-cli"
    assert not (state.get("now") or {}).get("resume_point")
    row = next(r for r in state["features"] if r["feature_id"] == "todo-cli")
    assert row["status"] == "designing"
    assert int(row.get("autonomous_escalate_count") or 0) == 0
    prove = memory / "features" / "todo-cli" / "checks" / "prove.yaml"
    assert prove.is_file()
    assert load_yaml(prove).get("tests_passed") is False


def test_request_change_requires_intent_or_id(tmp_path: Path) -> None:
    memory = tmp_path / "memory"
    memory.mkdir()
    try:
        request_change(memory)
        raise AssertionError("expected RequestChangeError")
    except RequestChangeError:
        pass


def test_cli_request_change(tmp_path: Path, capsys) -> None:
    memory = _done_studio(tmp_path)
    code = main(
        [
            "request-change",
            "--memory",
            str(memory),
            "--intent",
            "Add export",
        ]
    )
    assert code == 0
    assert "OK: queued change" in capsys.readouterr().out
    code = main(["request-change", "--memory", str(memory)])
    assert code == 1
