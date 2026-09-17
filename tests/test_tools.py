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
from agentic_loop_prime.security_report import passing_security_markdown
from agentic_loop_prime.telemetry import OpenTelemetryListener


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _adr(
    memory: Path,
    *,
    e2e: str = 'python3 -c "print(2)"',
    unit: str = 'python3 -c "print(1)"',
) -> None:
    _write(
        memory / "adr" / "ADR-0005-technology-stack.md",
        "\n".join(
            [
                "```bash",
                f"export UNIT_TEST_CMD='{unit}'",
                f"export E2E_TEST_CMD='{e2e}'",
                'export SECURITY_SECRETS_CMD=\'python3 -c "print(3)"\'',
                'export SECURITY_SCA_CMD="true"',
                'export SECURITY_SAST_CMD="true"',
                "```",
                "",
            ]
        ),
    )


def _light_studio(
    tmp_path: Path,
    *,
    plan: str = "### Step 1 — Scaffold\n\n- [ ] todo\n",
) -> tuple[Path, Path, Path]:
    brief = tmp_path / "brief"
    brief.mkdir()
    memory = tmp_path / "memory"
    memory.mkdir()
    app = tmp_path / "app"
    app.mkdir()
    _write(app / "main.py", "print('hi')\n")
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
    _write(feat / "plan.md", plan)
    return brief, memory, app


def _to_prove(memory: Path, brief: Path, app: Path):
    framed = next_frame(memory, brief_dir=brief, app_dir=app)
    if framed.kind == "HANDOFF":
        framed = next_frame(memory, brief_dir=brief, app_dir=app)
    return framed


def _write_passing_security(memory: Path, feature_id: str = "todo-cli") -> None:
    fp = memory / "features" / feature_id / "checks" / "fingerprint.json"
    digest = json.loads(fp.read_text(encoding="utf-8"))["digest"]
    _write(
        memory / "features" / feature_id / "checks" / "security.md",
        passing_security_markdown(digest, feature_id),
    )


def _clear_lock(memory: Path) -> None:
    data = load_yaml(memory / "run-state.yaml")
    data["lock"] = None
    (memory / "run-state.yaml").write_text(
        yaml.safe_dump(data, sort_keys=False), encoding="utf-8"
    )


def test_build_pass_writes_fingerprint_and_invalidates(tmp_path: Path) -> None:
    brief, memory, app = _light_studio(
        tmp_path,
        plan="### Step 1\n\n- [ ] a\n\n### Step 2\n\n- [ ] b\n",
    )
    framed = next_frame(memory, brief_dir=brief, app_dir=app)
    assert framed.skill == "build"
    assert framed.substep == "1"
    close_frame(memory, passed=True)
    fp = memory / "features" / "todo-cli" / "checks" / "fingerprint.json"
    assert fp.is_file()
    digest = json.loads(fp.read_text(encoding="utf-8"))["digest"]
    assert digest
    prove = memory / "features" / "todo-cli" / "checks" / "prove.yaml"
    _write(prove, "tests_passed: true\napp_fingerprint: planted\n")
    nxt = next_frame(memory, brief_dir=brief, app_dir=app)
    assert nxt.skill == "build"
    assert nxt.substep == "2"
    _write(app / "main.py", "print('changed')\n")
    close_frame(memory, passed=True)
    data = load_yaml(prove)
    assert data.get("tests_passed") is False
    new = json.loads(fp.read_text(encoding="utf-8"))["digest"]
    assert new != digest


def test_handoff_then_delegate_prove(tmp_path: Path) -> None:
    brief, memory, app = _light_studio(tmp_path)
    _adr(memory)
    next_frame(memory, brief_dir=brief, app_dir=app)
    close_frame(memory, passed=True)
    handoff = next_frame(memory, brief_dir=brief, app_dir=app)
    assert handoff.kind == "HANDOFF"
    assert handoff.skill == "verify"
    state = load_yaml(memory / "run-state.yaml")
    assert state.get("lock") is None
    assert state.get("intent") == "verify"
    prove = next_frame(memory, brief_dir=brief, app_dir=app)
    assert prove.kind == "DELEGATE"
    assert prove.skill == "verify"
    assert prove.substep == "prove"


def test_prove_missing_adr_keeps_lock(tmp_path: Path) -> None:
    brief, memory, app = _light_studio(tmp_path)
    next_frame(memory, brief_dir=brief, app_dir=app)
    close_frame(memory, passed=True)
    prove = _to_prove(memory, brief, app)
    tid = prove.transition_id
    try:
        close_frame(memory, passed=True)
        raise AssertionError("expected CloseError")
    except CloseError:
        pass
    state = load_yaml(memory / "run-state.yaml")
    assert state["lock"]["transition_id"] == tid


def test_prove_pass_runs_adr_and_advances(tmp_path: Path) -> None:
    brief, memory, app = _light_studio(tmp_path)
    _adr(memory)
    next_frame(memory, brief_dir=brief, app_dir=app)
    close_frame(memory, passed=True)
    prove = _to_prove(memory, brief, app)
    assert prove.kind == "DELEGATE"
    assert prove.skill == "verify"
    assert prove.substep == "prove"
    result = close_frame(memory, passed=True)
    assert result.passed is True
    harness = json.loads(
        (memory / "features" / "todo-cli" / "checks" / "harness.json").read_text(
            encoding="utf-8"
        )
    )
    assert harness["exit_code"] == 0
    marker = load_yaml(memory / "features" / "todo-cli" / "checks" / "prove.yaml")
    assert marker.get("tests_passed") is True
    nxt = next_frame(memory, brief_dir=brief, app_dir=app)
    assert nxt.kind == "DELEGATE"
    assert nxt.skill == "verify"
    assert nxt.substep == "security"


def test_prove_drift_is_done_fail(tmp_path: Path) -> None:
    brief, memory, app = _light_studio(tmp_path)
    marker = memory / "features" / "todo-cli" / "checks" / "HARNESS_RAN"
    _adr(memory, unit=f"touch {marker}")
    next_frame(memory, brief_dir=brief, app_dir=app)
    close_frame(memory, passed=True)
    prove = _to_prove(memory, brief, app)
    assert prove.substep == "prove"
    _write(app / "mutated.py", "x = 1\n")
    result = close_frame(memory, passed=True)
    assert result.passed is False
    state = load_yaml(memory / "run-state.yaml")
    assert state.get("lock") is None
    assert not marker.is_file()
    prove_marker = memory / "features" / "todo-cli" / "checks" / "prove.yaml"
    if prove_marker.is_file():
        assert load_yaml(prove_marker).get("tests_passed") is not True
    again = next_frame(memory, brief_dir=brief, app_dir=app)
    assert again.kind == "DELEGATE"
    assert again.skill == "build"


def test_prove_fail_does_not_stamp(tmp_path: Path) -> None:
    brief, memory, app = _light_studio(tmp_path)
    _adr(memory, e2e='python3 -c "raise SystemExit(1)"')
    next_frame(memory, brief_dir=brief, app_dir=app)
    close_frame(memory, passed=True)
    prove = _to_prove(memory, brief, app)
    assert prove.substep == "prove"
    result = close_frame(memory, passed=True)
    assert result.passed is False
    state = load_yaml(memory / "run-state.yaml")
    assert state.get("lock") is None
    prove = memory / "features" / "todo-cli" / "checks" / "prove.yaml"
    if prove.is_file():
        assert load_yaml(prove).get("tests_passed") is not True
    again = next_frame(memory, brief_dir=brief, app_dir=app)
    assert again.kind == "DELEGATE"
    assert again.skill == "build"
    assert again.substep == "1"
    state = load_yaml(memory / "run-state.yaml")
    assert str(state.get("now", {}).get("doing") or "").endswith(":reopen")


def test_prove_without_fingerprint_keeps_lock(tmp_path: Path) -> None:
    brief, memory, app = _light_studio(
        tmp_path, plan="### Step 1\n\n- [x] done\n"
    )
    _write(
        memory / "features" / "todo-cli" / "log.jsonl",
        '{"skill": "build", "substep": 1, "verification_pass": true}\n',
    )
    _adr(memory)
    prove = _to_prove(memory, brief, app)
    assert prove.kind == "DELEGATE"
    assert prove.substep == "prove"
    tid = prove.transition_id
    try:
        close_frame(memory, passed=True)
        raise AssertionError("expected CloseError")
    except CloseError:
        pass
    state = load_yaml(memory / "run-state.yaml")
    assert state["lock"]["transition_id"] == tid
    code = main(["done", "--memory", str(memory), "--pass"])
    assert code == 1


def test_planted_prove_marker_does_not_advance(tmp_path: Path) -> None:
    brief, memory, app = _light_studio(
        tmp_path, plan="### Step 1\n\n- [x] done\n"
    )
    _write(
        memory / "features" / "todo-cli" / "log.jsonl",
        '{"skill": "build", "substep": 1, "verification_pass": true}\n',
    )
    framed = _to_prove(memory, brief, app)
    assert framed.substep == "prove"
    _write(
        memory / "features" / "todo-cli" / "checks" / "prove.yaml",
        "tests_passed: true\n",
    )
    _clear_lock(memory)
    again = next_frame(memory, brief_dir=brief, app_dir=app)
    assert again.kind == "DELEGATE"
    assert again.skill == "verify"
    assert again.substep == "prove"


def test_security_pass_writes_tools_and_status(tmp_path: Path) -> None:
    brief, memory, app = _light_studio(tmp_path)
    _adr(memory)
    next_frame(memory, brief_dir=brief, app_dir=app)
    close_frame(memory, passed=True)
    _to_prove(memory, brief, app)
    close_frame(memory, passed=True)
    sec = next_frame(memory, brief_dir=brief, app_dir=app)
    assert sec.substep == "security"
    try:
        close_frame(memory, passed=True)
        raise AssertionError("expected CloseError until report is filled")
    except CloseError as exc:
        assert "status is not pass" in str(exc)
    tools = json.loads(
        (memory / "features" / "todo-cli" / "checks" / "tools.json").read_text(
            encoding="utf-8"
        )
    )
    assert tools["exit_code"] == 0
    seeded = (
        memory / "features" / "todo-cli" / "checks" / "security.md"
    ).read_text(encoding="utf-8")
    assert "**Status:** draft" in seeded
    assert "**Secrets clean:** pending" in seeded
    assert "**App fingerprint:**" in seeded
    _write_passing_security(memory)
    result = close_frame(memory, passed=True)
    assert result.passed is True
    text = (
        memory / "features" / "todo-cli" / "checks" / "security.md"
    ).read_text(encoding="utf-8")
    assert "**Status:** pass" in text
    assert "**App fingerprint:**" in text


def test_judge_pass_and_drift_fail(tmp_path: Path) -> None:
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
    result = close_frame(memory, passed=True)
    assert result.passed is True
    text = (memory / "features" / "todo-cli" / "checks" / "judge.md").read_text(
        encoding="utf-8"
    )
    assert "**Verdict:** pass" in text

    _write(app / "extra.py", "x = 1\n")
    _write(
        memory / "features" / "todo-cli" / "checks" / "judge.md",
        "**Verdict:** stale\n",
    )
    again = next_frame(memory, brief_dir=brief, app_dir=app)
    assert again.kind == "DELEGATE"
    assert again.substep == "judge"
    failed = close_frame(memory, passed=True)
    assert failed.passed is False
    state = load_yaml(memory / "run-state.yaml")
    assert state.get("lock") is None
    retry = next_frame(memory, brief_dir=brief, app_dir=app)
    assert retry.kind == "DELEGATE"
    assert retry.skill == "build"
    assert retry.substep == "1"


def test_judge_missing_app_dir_keeps_lock(tmp_path: Path) -> None:
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
    tid = judge.transition_id
    data = load_yaml(memory / "run-state.yaml")
    data["app_dir"] = None
    (memory / "run-state.yaml").write_text(
        yaml.safe_dump(data, sort_keys=False), encoding="utf-8"
    )
    try:
        close_frame(memory, passed=True)
        raise AssertionError("expected CloseError")
    except CloseError:
        pass
    state = load_yaml(memory / "run-state.yaml")
    assert state["lock"]["transition_id"] == tid


def test_prove_otel_execute_tool_not_error_on_fail(tmp_path: Path) -> None:
    brief, memory, app = _light_studio(tmp_path)
    _adr(memory, e2e='python3 -c "raise SystemExit(1)"')
    next_frame(memory, brief_dir=brief, app_dir=app)
    close_frame(memory, passed=True)
    _to_prove(memory, brief, app)
    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    listener = OpenTelemetryListener(tracer=provider.get_tracer("test"))
    result = close_frame(memory, passed=True, telemetry=listener)
    assert result.passed is False
    spans = exporter.get_finished_spans()
    root = next(s for s in spans if s.name == "invoke_agent")
    iteration = next(s for s in spans if s.name == "loop.iteration")
    tools = [s for s in spans if s.name == "execute_tool"]
    names = [s.attributes["gen_ai.tool.name"] for s in tools]
    assert names == ["UNIT_TEST_CMD", "E2E_TEST_CMD"]
    assert iteration.parent.span_id == root.context.span_id
    for span in tools:
        assert span.parent.span_id == iteration.context.span_id
        assert span.context.trace_id == root.context.trace_id
        assert span.status.status_code != StatusCode.ERROR
    e2e = next(s for s in tools if s.attributes["gen_ai.tool.name"] == "E2E_TEST_CMD")
    assert e2e.attributes["app.tool.success"] is False
    verify = next(s for s in spans if s.name == "goal.verify")
    assert verify.attributes["app.verification.independent"] is True
    assert verify.attributes["app.verification.result"] == "failed"
    evaluate = next(s for s in spans if s.name == "goal.evaluate")
    assert evaluate.attributes["app.eval.passed"] is False
    assert evaluate.status.status_code != StatusCode.ERROR
    assert root.status.status_code != StatusCode.ERROR


def test_prove_otel_pass_unit_then_e2e(tmp_path: Path) -> None:
    brief, memory, app = _light_studio(tmp_path)
    _adr(memory)
    next_frame(memory, brief_dir=brief, app_dir=app)
    close_frame(memory, passed=True)
    _to_prove(memory, brief, app)
    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    listener = OpenTelemetryListener(tracer=provider.get_tracer("test"))
    close_frame(memory, passed=True, telemetry=listener)
    spans = exporter.get_finished_spans()
    root = next(s for s in spans if s.name == "invoke_agent")
    iteration = next(s for s in spans if s.name == "loop.iteration")
    tools = [s for s in spans if s.name == "execute_tool"]
    assert [s.attributes["gen_ai.tool.name"] for s in tools] == [
        "UNIT_TEST_CMD",
        "E2E_TEST_CMD",
    ]
    assert iteration.parent.span_id == root.context.span_id
    for span in tools:
        assert span.parent.span_id == iteration.context.span_id
        assert span.attributes["app.tool.success"] is True
    verify = next(s for s in spans if s.name == "goal.verify")
    assert verify.attributes["app.verification.result"] == "passed"
