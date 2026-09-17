from __future__ import annotations

from pathlib import Path

import yaml
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from opentelemetry.trace import StatusCode

from agentic_loop_prime.cli import main
from agentic_loop_prime.context import ProgramContext
from agentic_loop_prime.paths import load_yaml
from agentic_loop_prime.schedule import Action, next_frame, prompt_block
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


def test_first_next_delegates_intake_charter(tmp_path: Path) -> None:
    brief = tmp_path / "brief"
    brief.mkdir()
    (brief / "notes.md").write_text("todo cli\n", encoding="utf-8")
    memory = tmp_path / "memory"
    action = next_frame(memory, brief_dir=brief)
    assert action.kind == "DELEGATE"
    assert action.skill == "intake"
    assert action.substep == "charter"
    assert action.transition_id
    state = load_yaml(memory / "run-state.yaml")
    assert state["lock"]["skill"] == "intake"
    assert state["loop"]["remaining"] == 19
    assert state["program_state"] == "intake"
    assert state["brief_dir"] == str(brief.resolve())


def test_charter_review_stop_until_signed(tmp_path: Path) -> None:
    brief = tmp_path / "brief"
    brief.mkdir()
    memory = tmp_path / "memory"
    next_frame(memory, brief_dir=brief)
    _write(memory / "charter.md", "# Charter\n\nShip a todo CLI.\n")
    _write(
        memory / "backlog.yaml",
        "version: 1\nfeatures:\n  - id: todo-cli\n    name: Todo\n    design_track: light\n",
    )
    _clear_lock(memory)
    action = next_frame(memory, brief_dir=brief)
    assert action.kind == "STOP"
    assert action.reason == "charter_review"
    state = load_yaml(memory / "run-state.yaml")
    assert state["program_state"] == "charter_review"
    assert state.get("charter_signed") is False

    state["charter_signed"] = True
    (memory / "run-state.yaml").write_text(
        yaml.safe_dump(state, sort_keys=False), encoding="utf-8"
    )
    action = next_frame(memory, brief_dir=brief)
    assert action.kind == "DELEGATE"
    assert action.skill == "design"
    assert action.substep == "brief"


def test_light_build_no_ux_ui(tmp_path: Path) -> None:
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
    _write(memory / "charter.md", "# Charter\n\nTodo CLI.\n")
    _write(
        memory / "backlog.yaml",
        "version: 1\nfeatures:\n  - id: todo-cli\n    design_track: light\n    surface: cli\n",
    )
    feat = memory / "features" / "todo-cli"
    _write(feat / "brief.md", "# Brief\n\n**Status:** signed\n")
    _write(feat / "plan.md", "### Step 1 — Scaffold\n\n- [ ] todo\n")
    action = next_frame(memory, brief_dir=brief)
    assert action.kind == "DELEGATE"
    assert action.skill == "build"
    assert action.substep == "1"
    assert not (feat / "ux.md").exists()
    assert not (feat / "ui.md").exists()


def test_build_log_gap_stops_handoff(tmp_path: Path) -> None:
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
    _write(memory / "charter.md", "# Charter\n\nTodo CLI.\n")
    _write(
        memory / "backlog.yaml",
        "version: 1\nfeatures:\n  - id: todo-cli\n    design_track: light\n",
    )
    feat = memory / "features" / "todo-cli"
    _write(feat / "brief.md", "# Brief\n\n**Status:** signed\n")
    _write(feat / "plan.md", "### Step 1 — Scaffold\n\n- [x] done\n")
    _write(feat / "log.jsonl", "{}\n")
    action = next_frame(memory, brief_dir=brief)
    assert action.kind == "STOP"
    assert action.reason == "build_log_gap"

    _write(
        feat / "log.jsonl",
        '{"skill": "build", "substep": 1, "verification_pass": true}\n',
    )
    again = next_frame(memory, brief_dir=brief)
    assert again.kind == "HANDOFF"
    assert again.skill == "verify"


def test_open_lock_stops(tmp_path: Path) -> None:
    brief = tmp_path / "brief"
    brief.mkdir()
    memory = tmp_path / "memory"
    first = next_frame(memory, brief_dir=brief)
    assert first.kind == "DELEGATE"
    second = next_frame(memory, brief_dir=brief)
    assert second.kind == "STOP"
    assert second.reason == "transition_open"


def test_budget_zero_stops(tmp_path: Path) -> None:
    brief = tmp_path / "brief"
    brief.mkdir()
    memory = tmp_path / "memory"
    action = next_frame(memory, brief_dir=brief, loop_budget=0)
    assert action.kind == "STOP"
    assert action.reason == "session_budget"


def test_otel_delegate_and_evaluate_fail_not_error(tmp_path: Path) -> None:
    brief = tmp_path / "brief"
    brief.mkdir()
    memory = tmp_path / "memory"
    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    listener = OpenTelemetryListener(tracer=provider.get_tracer("test"))
    action = next_frame(memory, brief_dir=brief, telemetry=listener)
    assert action.kind == "DELEGATE"
    names = {s.name for s in exporter.get_finished_spans()}
    assert "invoke_agent" in names
    assert "loop.iteration" not in names
    root = next(s for s in exporter.get_finished_spans() if s.name == "invoke_agent")
    assert root.attributes.get("app.skill") == "intake"
    assert root.attributes.get("app.program.id")

    _write(memory / "charter.md", "# Charter\n\nX\n")
    _write(
        memory / "backlog.yaml",
        "version: 1\nfeatures:\n  - id: todo-cli\n    name: Todo\n",
    )
    _clear_lock(memory)
    exporter.clear()
    listener = OpenTelemetryListener(tracer=provider.get_tracer("test"))
    stop = next_frame(memory, brief_dir=brief, telemetry=listener)
    assert stop.kind == "STOP"
    assert stop.reason == "charter_review"
    spans = exporter.get_finished_spans()
    evaluate = next(s for s in spans if s.name == "goal.evaluate")
    assert evaluate.attributes["app.eval.passed"] is False
    assert evaluate.status.status_code != StatusCode.ERROR
    root = next(s for s in spans if s.name == "invoke_agent")
    assert root.attributes["app.loop.product"] == "prime"
    assert root.status.status_code != StatusCode.ERROR


def test_cli_next_exit_codes(tmp_path: Path, capsys) -> None:
    brief = tmp_path / "brief"
    brief.mkdir()
    memory = tmp_path / "memory"
    code = main(
        [
            "next",
            "--memory",
            str(memory),
            "--brief-dir",
            str(brief),
            "--prompt",
        ]
    )
    assert code == 0
    out = capsys.readouterr().out
    assert "DELEGATE intake" in out
    assert "Resume: intake charter" in out
    code = main(["next", "--memory", str(memory), "--brief-dir", str(brief)])
    assert code == 2
    assert "STOP transition_open" in capsys.readouterr().out


def test_prompt_block_loads_ux_and_ui_skills() -> None:
    ctx = ProgramContext(active_feature="dash")
    ux = prompt_block(
        Action(kind="DELEGATE", skill="design", feature_id="dash", substep="ux"),
        ctx,
        "designing",
    )
    assert "Load skill: .cursor/skills/prime-design/SKILL.md" in ux
    assert "Load skill: .cursor/skills/ux-architect/SKILL.md" in ux
    assert "Write: memory/features/dash/ux.md" in ux
    assert "Close: al-prime done --memory memory --pass" in ux
    ui = prompt_block(
        Action(kind="DELEGATE", skill="design", feature_id="dash", substep="ui"),
        ctx,
        "designing",
    )
    assert "Load skill: .cursor/skills/prime-design/SKILL.md" in ui
    assert "Load skill: .cursor/skills/ui-direction/SKILL.md" in ui
    brief = prompt_block(
        Action(kind="DELEGATE", skill="design", feature_id="dash", substep="brief"),
        ctx,
        "designing",
    )
    assert "Load skill: .cursor/skills/prime-design/SKILL.md" in brief
    assert "Write: memory/features/dash/brief.md" in brief
    assert "ux-architect" not in brief
    assert "ui-direction" not in brief


def test_prompt_block_loads_taste_on_ui_build() -> None:
    ctx = ProgramContext(active_feature="dash")
    ctx.features = [{"feature_id": "dash", "surface": "ui"}]
    text = prompt_block(
        Action(kind="DELEGATE", skill="build", feature_id="dash", substep="1"),
        ctx,
        "building",
    )
    assert "Load skill: .cursor/skills/prime-build/SKILL.md" in text
    assert "Load skill: .cursor/skills/design-taste-frontend/SKILL.md" in text
    assert "Write: app/ (one plan step 1)" in text
    ctx.features = [{"feature_id": "dash", "surface": "cli"}]
    cli = prompt_block(
        Action(kind="DELEGATE", skill="build", feature_id="dash", substep="1"),
        ctx,
        "building",
    )
    assert "Load skill: .cursor/skills/prime-build/SKILL.md" in cli
    assert "design-taste-frontend" not in cli


def test_prompt_block_intake_charter() -> None:
    ctx = ProgramContext()
    text = prompt_block(
        Action(kind="DELEGATE", skill="intake", substep="charter"),
        ctx,
        "intake",
    )
    assert "Load skill: .cursor/skills/prime-intake/SKILL.md" in text
    assert "Write: memory/charter.md" in text
    assert "Close: al-prime done --memory memory --pass" in text


def test_prompt_block_security_close_outcomes() -> None:
    ctx = ProgramContext(active_feature="todo-cli")
    text = prompt_block(
        Action(
            kind="DELEGATE",
            skill="verify",
            feature_id="todo-cli",
            substep="security",
        ),
        ctx,
        "security",
    )
    assert "Load skill: .cursor/skills/prime-verify/SKILL.md" in text
    assert "Write: memory/features/todo-cli/checks/security.md after tools" in text
    assert "DONE fail" in text
    assert "ERROR, lock stays" in text


def test_prompt_block_prove_and_judge_write_hints() -> None:
    ctx = ProgramContext(active_feature="todo-cli")
    prove = prompt_block(
        Action(kind="DELEGATE", skill="verify", feature_id="todo-cli", substep="prove"),
        ctx,
        "verify",
    )
    assert "Write: do not edit app/; fill ADR-0005 if UNIT/E2E missing" in prove
    assert "prove.yaml" not in prove
    judge = prompt_block(
        Action(kind="DELEGATE", skill="verify", feature_id="todo-cli", substep="judge"),
        ctx,
        "verify",
    )
    assert "Write: do not edit app/; --pass writes memory/features/todo-cli/checks/judge.md" in judge
    assert "harness writes it" not in judge


def test_prompt_block_close_uses_memory_path(tmp_path: Path) -> None:
    memory = tmp_path / "custom-memory"
    memory.mkdir()
    (memory / "run-state.yaml").write_text("program_state: idle\n", encoding="utf-8")
    ctx = ProgramContext(memory_dir=memory)
    text = prompt_block(
        Action(kind="DELEGATE", skill="intake", substep="charter"),
        ctx,
        "intake",
    )
    assert f"Close: al-prime done --memory {memory.resolve()} --pass" in text
    assert "Close: al-prime done --memory memory --pass" not in text


def test_prompt_block_handoff_loads_verify() -> None:
    ctx = ProgramContext(active_feature="todo-cli")
    text = prompt_block(
        Action(kind="HANDOFF", skill="verify", feature_id="todo-cli"),
        ctx,
        "building",
    )
    assert "Load skill: .cursor/skills/prime-verify/SKILL.md" in text
    assert "Close:" not in text
