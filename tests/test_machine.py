from __future__ import annotations

from pathlib import Path

import pytest
from statemachine.exceptions import TransitionNotAllowed

from agentic_loop_prime.context import ProgramContext
from agentic_loop_prime.machine import Program, current_state
from agentic_loop_prime.telemetry import NoOpTelemetry


HAPPY_PATH = (
    "start_intake",
    "draft_ready",
    "charter_signed",
    "backlog_ready",
    "start_design",
    "brief_ready",
    "brief_signed",
    "build_complete",
    "tests_pass",
    "security_pass",
    "all_done",
)


def test_idle_to_done_slim_memory(light_context: ProgramContext) -> None:
    recorder = NoOpTelemetry()
    program = Program(light_context, listeners=[recorder])
    assert current_state(program) == "idle"
    for event in HAPPY_PATH:
        program.send(event)
    assert current_state(program) == "done"
    assert program.done.is_active
    assert recorder.transitions
    assert recorder.transitions[0][1] == "start_intake"
    assert recorder.transitions[-1][2] == "done"


def test_light_track_has_no_ux_or_ui(slim_light_memory: Path) -> None:
    feat = slim_light_memory / "features" / "todo-cli"
    assert not (feat / "ux.md").exists()
    assert not (feat / "ui.md").exists()
    assert not (feat / "technical.md").exists()
    ctx = ProgramContext(memory_dir=slim_light_memory)
    assert ctx.design_track == "light"
    assert ctx.design_ready() is True


def test_standard_track_requires_ux_and_ui(
    slim_light_memory: Path,
) -> None:
    ctx = ProgramContext(memory_dir=slim_light_memory)
    ctx.design_track = "standard"
    ctx.design_ready_flag = None
    assert ctx.design_ready() is False
    (slim_light_memory / "features" / "todo-cli" / "ux.md").write_text(
        "# UX\n\nflows\n", encoding="utf-8"
    )
    (slim_light_memory / "features" / "todo-cli" / "ui.md").write_text(
        "# UI\n\ndials\n", encoding="utf-8"
    )
    assert ctx.design_ready() is True


def test_illegal_live_to_start_design() -> None:
    ctx = ProgramContext(
        active_feature="todo-cli",
        features=[{"feature_id": "todo-cli", "status": "live"}],
        charter_signed_flag=True,
        intake_ready=True,
        backlog_ready_flag=True,
        design_ready_flag=True,
        brief_signed_flag=True,
        plan_complete_flag=True,
        build_logs_ok_flag=True,
        tests_passed_flag=True,
        security_passed_flag=True,
    )
    program = Program(ctx, start_value="live")
    assert "live" in program.configuration_values
    with pytest.raises(TransitionNotAllowed):
        program.send("start_design")


def test_tests_fail_goes_to_blocked_retry() -> None:
    ctx = ProgramContext(
        active_feature="todo-cli",
        features=[{"feature_id": "todo-cli", "status": "verifying"}],
        tests_passed_flag=False,
    )
    program = Program(ctx, start_value="verifying")
    program.send("tests_fail")
    assert "blocked_retry" in program.configuration_values
