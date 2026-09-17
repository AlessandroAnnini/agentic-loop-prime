from __future__ import annotations

from pathlib import Path

from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from opentelemetry.trace import StatusCode

from agentic_loop_prime.done import close_frame
from agentic_loop_prime.paths import load_yaml
from agentic_loop_prime.persist import load_run_state, save_run_state
from agentic_loop_prime.request_change import request_change
from agentic_loop_prime.schedule import next_frame
from agentic_loop_prime.telemetry import OpenTelemetryListener

from test_tools import _adr, _light_studio, _to_prove, _write, _write_passing_security


def _provider() -> tuple[TracerProvider, InMemorySpanExporter]:
    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    return provider, exporter


def _reach_prove(memory: Path, brief: Path, app: Path):
    next_frame(memory, brief_dir=brief, app_dir=app)
    close_frame(memory, passed=True)
    return _to_prove(memory, brief, app)


def _second_prove_fail(memory: Path) -> None:
    data = load_run_state(memory)
    data["lock"] = {
        "transition_id": "second-prove",
        "feature_id": "todo-cli",
        "skill": "verify",
        "substep": "prove",
    }
    save_run_state(memory, data)
    close_frame(memory, passed=False, transition_id="second-prove")


def test_prove_fail_reopens_build_then_supersedes(tmp_path: Path) -> None:
    brief, memory, app = _light_studio(tmp_path)
    _adr(memory, e2e='python3 -c "raise SystemExit(1)"')
    prove = _reach_prove(memory, brief, app)
    assert prove.substep == "prove"
    result = close_frame(memory, passed=True)
    assert result.passed is False
    state = load_yaml(memory / "run-state.yaml")
    assert state.get("lock") is None
    prove_marker = memory / "features" / "todo-cli" / "checks" / "prove.yaml"
    if prove_marker.is_file():
        assert load_yaml(prove_marker).get("tests_passed") is not True

    retry = next_frame(memory, brief_dir=brief, app_dir=app)
    assert retry.kind == "DELEGATE"
    assert retry.skill == "build"
    assert retry.substep == "1"

    _adr(memory)
    rebuilt = close_frame(memory, passed=True)
    assert rebuilt.passed is True
    nxt = next_frame(memory, brief_dir=brief, app_dir=app)
    if nxt.kind == "HANDOFF":
        nxt = next_frame(memory, brief_dir=brief, app_dir=app)
    assert nxt.kind == "DELEGATE"
    assert nxt.skill == "verify"
    assert nxt.substep == "prove"


def test_stale_prove_marker_with_fail_log_reopens(tmp_path: Path) -> None:
    brief, memory, app = _light_studio(tmp_path)
    _adr(memory, e2e='python3 -c "raise SystemExit(1)"')
    _reach_prove(memory, brief, app)
    close_frame(memory, passed=True)
    _write(
        memory / "features" / "todo-cli" / "checks" / "prove.yaml",
        "tests_passed: true\n",
    )
    retry = next_frame(memory, brief_dir=brief, app_dir=app)
    assert retry.kind == "DELEGATE"
    assert retry.skill == "build"


def test_judge_fail_reopens_build(tmp_path: Path) -> None:
    brief, memory, app = _light_studio(tmp_path)
    _adr(memory)
    next_frame(memory, brief_dir=brief, app_dir=app)
    close_frame(memory, passed=True)
    _to_prove(memory, brief, app)
    close_frame(memory, passed=True)
    next_frame(memory, brief_dir=brief, app_dir=app)
    _write_passing_security(memory)
    close_frame(memory, passed=True)
    judge = next_frame(memory, brief_dir=brief, app_dir=app)
    assert judge.substep == "judge"
    _write(app / "extra.py", "x = 1\n")
    failed = close_frame(memory, passed=True)
    assert failed.passed is False
    retry = next_frame(memory, brief_dir=brief, app_dir=app)
    assert retry.kind == "DELEGATE"
    assert retry.skill == "build"
    assert retry.substep == "1"


def test_same_prove_fail_twice_stops(tmp_path: Path) -> None:
    brief, memory, app = _light_studio(tmp_path)
    _adr(memory, e2e='python3 -c "raise SystemExit(1)"')
    _reach_prove(memory, brief, app)
    close_frame(memory, passed=True)
    _second_prove_fail(memory)
    stopped = next_frame(memory, brief_dir=brief, app_dir=app)
    assert stopped.kind == "STOP"
    assert stopped.reason == "blocked_stagnation"


def test_autonomous_escalates_once_then_stops(tmp_path: Path) -> None:
    brief, memory, app = _light_studio(tmp_path)
    _adr(memory, e2e='python3 -c "raise SystemExit(1)"')
    _reach_prove(memory, brief, app)
    close_frame(memory, passed=True)
    _second_prove_fail(memory)
    design = next_frame(memory, brief_dir=brief, app_dir=app, autonomous=True)
    assert design.kind == "DELEGATE"
    assert design.skill == "design"
    close_frame(memory, passed=False)
    state = load_run_state(memory)
    row = next(r for r in state["features"] if r["feature_id"] == "todo-cli")
    assert int(row.get("autonomous_escalate_count") or 0) == 1

    row["fail_streak"] = 2
    row["blocked_action"] = "verify:prove"
    state["now"]["stagnation"] = "verify:prove"
    state["now"]["fail_streak"] = 2
    save_run_state(memory, state)
    stopped = next_frame(memory, brief_dir=brief, app_dir=app, autonomous=True)
    assert stopped.kind == "STOP"
    assert stopped.reason == "blocked_stagnation"
    again = load_run_state(memory)
    row2 = next(r for r in again["features"] if r["feature_id"] == "todo-cli")
    assert int(row2.get("autonomous_escalate_count") or 0) == 1


def test_human_request_change_does_not_burn_escalate(tmp_path: Path) -> None:
    brief, memory, app = _light_studio(tmp_path)
    _adr(memory)
    next_frame(memory, brief_dir=brief, app_dir=app)
    close_frame(memory, passed=True)
    request_change(memory, feature_id="todo-cli")
    state = load_run_state(memory)
    row = next(r for r in state["features"] if r["feature_id"] == "todo-cli")
    assert int(row.get("autonomous_escalate_count") or 0) == 0


def test_reopen_otel_phase_fail_not_error(tmp_path: Path) -> None:
    brief, memory, app = _light_studio(tmp_path)
    _adr(memory, e2e='python3 -c "raise SystemExit(1)"')
    _reach_prove(memory, brief, app)
    close_frame(memory, passed=True)
    provider, exporter = _provider()
    listener = OpenTelemetryListener(tracer=provider.get_tracer("test"))
    retry = next_frame(memory, brief_dir=brief, app_dir=app, telemetry=listener)
    assert retry.skill == "build"
    spans = exporter.get_finished_spans()
    evaluate = [
        s
        for s in spans
        if s.name == "goal.evaluate" and s.attributes.get("app.eval.name") == "phase_fail.prove"
    ]
    assert evaluate
    assert evaluate[0].attributes["app.eval.passed"] is False
    assert evaluate[0].status.status_code != StatusCode.ERROR
    tools = [
        s
        for s in spans
        if s.name == "execute_tool"
        and s.attributes.get("gen_ai.tool.name") == "reopen.plan_step"
    ]
    assert tools
    assert tools[0].attributes["app.tool.success"] is True
    assert tools[0].status.status_code != StatusCode.ERROR
    root = next(s for s in spans if s.name == "invoke_agent")
    assert root.status.status_code != StatusCode.ERROR


def test_stagnation_otel_not_error(tmp_path: Path) -> None:
    brief, memory, app = _light_studio(tmp_path)
    _adr(memory, e2e='python3 -c "raise SystemExit(1)"')
    _reach_prove(memory, brief, app)
    close_frame(memory, passed=True)
    _second_prove_fail(memory)
    provider, exporter = _provider()
    listener = OpenTelemetryListener(tracer=provider.get_tracer("test"))
    stopped = next_frame(memory, brief_dir=brief, app_dir=app, telemetry=listener)
    assert stopped.reason == "blocked_stagnation"
    spans = exporter.get_finished_spans()
    root = next(s for s in spans if s.name == "invoke_agent")
    assert root.status.status_code != StatusCode.ERROR
    assert root.attributes.get("app.loop.outcome") == "goal_not_met"
    evaluate = [
        s
        for s in spans
        if s.name == "goal.evaluate"
        and s.attributes.get("app.eval.name") == "blocked_stagnation"
    ]
    assert evaluate
    assert evaluate[0].attributes["app.eval.passed"] is False
    assert evaluate[0].status.status_code != StatusCode.ERROR
