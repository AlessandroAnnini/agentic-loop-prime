from __future__ import annotations

import json
from pathlib import Path

import yaml
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from opentelemetry.trace import StatusCode

from agentic_loop_prime.cli import main
from agentic_loop_prime.done import CloseError, close_frame
from agentic_loop_prime.paths import load_yaml
from agentic_loop_prime.schedule import next_frame
from agentic_loop_prime.telemetry import OpenTelemetryListener


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _log_lines(memory: Path, feature_id: str) -> list[dict]:
    path = memory / "features" / feature_id / "log.jsonl"
    if not path.is_file():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def test_done_pass_clears_lock_and_next_advances(tmp_path: Path) -> None:
    brief = tmp_path / "brief"
    brief.mkdir()
    memory = tmp_path / "memory"
    framed = next_frame(memory, brief_dir=brief)
    assert framed.kind == "DELEGATE"
    _write(memory / "charter.md", "# Charter\n\nTodo CLI.\n")
    _write(
        memory / "backlog.yaml",
        "version: 1\nfeatures:\n  - id: todo-cli\n    name: Todo\n    design_track: light\n",
    )
    result = close_frame(memory, passed=True)
    assert result.passed is True
    state = load_yaml(memory / "run-state.yaml")
    assert state.get("lock") is None
    logs = _log_lines(memory, "program")
    assert logs[-1]["verification_pass"] is True
    assert logs[-1]["transition_id"] == framed.transition_id
    nxt = next_frame(memory, brief_dir=brief)
    assert nxt.reason != "transition_open"
    assert nxt.kind == "STOP"
    assert nxt.reason == "charter_review"


def test_done_wrong_id_keeps_lock(tmp_path: Path) -> None:
    brief = tmp_path / "brief"
    brief.mkdir()
    memory = tmp_path / "memory"
    framed = next_frame(memory, brief_dir=brief)
    try:
        close_frame(memory, passed=True, transition_id="not-the-id")
        raise AssertionError("expected CloseError")
    except CloseError:
        pass
    state = load_yaml(memory / "run-state.yaml")
    assert state["lock"]["transition_id"] == framed.transition_id
    code = main(
        [
            "done",
            "--memory",
            str(memory),
            "--transition-id",
            "nope",
            "--pass",
        ]
    )
    assert code == 1


def test_done_fail_retries_same_build_step(tmp_path: Path) -> None:
    brief = tmp_path / "brief"
    brief.mkdir()
    memory = tmp_path / "memory"
    memory.mkdir()
    _write(
        memory / "run-state.yaml",
        yaml.safe_dump(
            {
                "version": 1,
                "program_state": "idle",
                "active_feature": "todo-cli",
                "charter_signed": True,
                "research_track": "none",
                "lock": None,
                "loop": {"initial": 20, "remaining": 20},
                "features": [
                    {
                        "feature_id": "todo-cli",
                        "status": "pending",
                        "design_track": "light",
                    }
                ],
            },
            sort_keys=False,
        ),
    )
    _write(memory / "charter.md", "# Charter\n\nTodo.\n")
    _write(
        memory / "backlog.yaml",
        "version: 1\nfeatures:\n  - id: todo-cli\n    design_track: light\n",
    )
    feat = memory / "features" / "todo-cli"
    _write(feat / "brief.md", "# Brief\n\n**Status:** signed\n")
    _write(feat / "plan.md", "### Step 1 — Scaffold\n\n- [ ] todo\n")
    framed = next_frame(memory, brief_dir=brief)
    assert framed.skill == "build"
    assert framed.substep == "1"
    close_frame(memory, passed=False)
    state = load_yaml(memory / "run-state.yaml")
    assert state.get("lock") is None
    assert "- [ ]" in (feat / "plan.md").read_text(encoding="utf-8")
    again = next_frame(memory, brief_dir=brief)
    assert again.kind == "DELEGATE"
    assert again.skill == "build"
    assert again.substep == "1"


def test_done_pass_ticks_build_step(tmp_path: Path) -> None:
    brief = tmp_path / "brief"
    brief.mkdir()
    memory = tmp_path / "memory"
    memory.mkdir()
    _write(
        memory / "run-state.yaml",
        yaml.safe_dump(
            {
                "version": 1,
                "program_state": "idle",
                "active_feature": "todo-cli",
                "charter_signed": True,
                "research_track": "none",
                "lock": None,
                "loop": {"initial": 20, "remaining": 20},
                "features": [
                    {
                        "feature_id": "todo-cli",
                        "status": "pending",
                        "design_track": "light",
                    }
                ],
            },
            sort_keys=False,
        ),
    )
    _write(memory / "charter.md", "# Charter\n\nTodo.\n")
    _write(
        memory / "backlog.yaml",
        "version: 1\nfeatures:\n  - id: todo-cli\n    design_track: light\n",
    )
    feat = memory / "features" / "todo-cli"
    _write(feat / "brief.md", "# Brief\n\n**Status:** signed\n")
    _write(feat / "plan.md", "### Step 1 — Scaffold\n\n- [ ] todo\n")
    next_frame(memory, brief_dir=brief)
    close_frame(memory, passed=True)
    text = (feat / "plan.md").read_text(encoding="utf-8")
    assert "- [x] todo" in text
    assert "- [ ]" not in text


def test_done_fail_evaluate_is_not_error(tmp_path: Path) -> None:
    brief = tmp_path / "brief"
    brief.mkdir()
    memory = tmp_path / "memory"
    next_frame(memory, brief_dir=brief)
    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    listener = OpenTelemetryListener(tracer=provider.get_tracer("test"))
    close_frame(memory, passed=False, telemetry=listener)
    evaluate = next(s for s in exporter.get_finished_spans() if s.name == "goal.evaluate")
    assert evaluate.attributes["app.eval.passed"] is False
    assert evaluate.status.status_code != StatusCode.ERROR
    root = next(s for s in exporter.get_finished_spans() if s.name == "invoke_agent")
    assert root.status.status_code != StatusCode.ERROR


def test_cli_done_pass(tmp_path: Path, capsys) -> None:
    brief = tmp_path / "brief"
    brief.mkdir()
    memory = tmp_path / "memory"
    main(["next", "--memory", str(memory), "--brief-dir", str(brief)])
    capsys.readouterr()
    code = main(["done", "--memory", str(memory), "--pass"])
    assert code == 0
    assert "DONE pass" in capsys.readouterr().out
