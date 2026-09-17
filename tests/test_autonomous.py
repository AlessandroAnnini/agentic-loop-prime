from __future__ import annotations

from pathlib import Path

import yaml
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from opentelemetry.trace import StatusCode

from agentic_loop_prime.paths import load_yaml
from agentic_loop_prime.schedule import next_frame
from agentic_loop_prime.telemetry import OpenTelemetryListener


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _clear_lock(memory: Path) -> None:
    data = load_yaml(memory / "run-state.yaml")
    data["lock"] = None
    (memory / "run-state.yaml").write_text(
        yaml.safe_dump(data, sort_keys=False), encoding="utf-8"
    )


def _charter_ready(memory: Path, brief: Path) -> None:
    next_frame(memory, brief_dir=brief)
    _write(memory / "charter.md", "# Charter\n\nShip a todo CLI.\n")
    _write(
        memory / "backlog.yaml",
        "version: 1\nfeatures:\n  - id: todo-cli\n    name: Todo\n    design_track: light\n",
    )
    _clear_lock(memory)


def test_autonomous_auto_signs_charter(tmp_path: Path) -> None:
    brief = tmp_path / "brief"
    brief.mkdir()
    memory = tmp_path / "memory"
    _charter_ready(memory, brief)
    action = next_frame(memory, brief_dir=brief, autonomous=True)
    assert action.kind == "DELEGATE"
    assert action.skill == "design"
    state = load_yaml(memory / "run-state.yaml")
    assert state.get("charter_signed") is True
    assert state.get("now", {}).get("autonomous") is True
    assert action.reason != "charter_review"


def test_autonomous_auto_signs_brief(tmp_path: Path) -> None:
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
    _write(
        memory / "features" / "todo-cli" / "brief.md",
        "# Brief\n\n**Status:** draft\n",
    )
    _write(
        memory / "features" / "todo-cli" / "plan.md",
        "### Step 1 — Scaffold\n\n- [ ] todo\n",
    )
    action = next_frame(memory, brief_dir=brief, autonomous=True)
    assert action.kind == "DELEGATE"
    assert action.skill == "build"
    text = (memory / "features" / "todo-cli" / "brief.md").read_text(encoding="utf-8")
    assert "**Status:** signed" in text
    assert action.reason != "brief_review"


def test_sticky_autonomous_without_flag(tmp_path: Path) -> None:
    brief = tmp_path / "brief"
    brief.mkdir()
    memory = tmp_path / "memory"
    first = next_frame(memory, brief_dir=brief, autonomous=True)
    assert first.kind == "DELEGATE"
    state = load_yaml(memory / "run-state.yaml")
    assert state.get("now", {}).get("autonomous") is True
    _write(memory / "charter.md", "# Charter\n\nShip a todo CLI.\n")
    _write(
        memory / "backlog.yaml",
        "version: 1\nfeatures:\n  - id: todo-cli\n    name: Todo\n    design_track: light\n",
    )
    _clear_lock(memory)
    action = next_frame(memory, brief_dir=brief)
    assert action.kind == "DELEGATE"
    assert action.skill == "design"
    assert load_yaml(memory / "run-state.yaml").get("charter_signed") is True


def test_open_questions_skipped_only_when_autonomous(tmp_path: Path) -> None:
    brief = tmp_path / "brief"
    brief.mkdir()
    memory = tmp_path / "memory"
    _charter_ready(memory, brief)
    _write(
        memory / "decisions.yaml",
        "version: 1\nitems:\n  - id: Q1\n    status: open\n    blocks: [charter_signoff]\n",
    )
    hitl = next_frame(memory, brief_dir=brief)
    assert hitl.kind == "STOP"
    assert hitl.reason == "open_questions"
    auto = next_frame(memory, brief_dir=brief, autonomous=True)
    assert auto.kind == "DELEGATE"
    assert auto.skill == "design"


def test_autonomous_charter_otel_evaluate_pass(tmp_path: Path) -> None:
    brief = tmp_path / "brief"
    brief.mkdir()
    memory = tmp_path / "memory"
    _charter_ready(memory, brief)
    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    listener = OpenTelemetryListener(tracer=provider.get_tracer("test"))
    action = next_frame(
        memory, brief_dir=brief, autonomous=True, telemetry=listener
    )
    assert action.kind == "DELEGATE"
    spans = exporter.get_finished_spans()
    evaluate = next(
        s
        for s in spans
        if s.name == "goal.evaluate" and s.attributes.get("app.eval.name") == "charter_signed"
    )
    assert evaluate.attributes["app.eval.passed"] is True
    assert evaluate.status.status_code != StatusCode.ERROR
    root = next(s for s in spans if s.name == "invoke_agent")
    assert root.status.status_code != StatusCode.ERROR
