from __future__ import annotations

from pathlib import Path

from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from opentelemetry.trace import StatusCode

from agentic_loop_prime.done import close_frame
from agentic_loop_prime.paths import load_yaml
from agentic_loop_prime.schedule import next_frame
from agentic_loop_prime.telemetry import OpenTelemetryListener
from agentic_loop_prime.unattended import run_unattended

from test_tools import _adr, _light_studio, _write


def _provider() -> tuple[TracerProvider, InMemorySpanExporter]:
    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    return provider, exporter


def test_next_writes_traceparent_and_done_shares_trace(tmp_path: Path) -> None:
    brief, memory, app = _light_studio(tmp_path)
    provider, exporter = _provider()
    nxt = OpenTelemetryListener(tracer=provider.get_tracer("next"))
    action = next_frame(memory, brief_dir=brief, app_dir=app, telemetry=nxt)
    assert action.kind == "DELEGATE"
    state = load_yaml(memory / "run-state.yaml")
    parent = state["lock"].get("traceparent")
    assert parent
    assert parent.startswith("00-")
    next_trace = int(parent.split("-")[1], 16)

    done_listener = OpenTelemetryListener(tracer=provider.get_tracer("done"))
    close_frame(memory, passed=False, telemetry=done_listener)
    roots = [s for s in exporter.get_finished_spans() if s.name == "invoke_agent"]
    assert len(roots) >= 2
    done_root = roots[-1]
    assert done_root.context.trace_id == next_trace
    assert done_root.attributes.get("app.loop.outcome") == "goal_not_met"
    assert done_root.status.status_code != StatusCode.ERROR


def test_unattended_emits_invoke_agent(tmp_path: Path) -> None:
    brief = tmp_path / "brief"
    brief.mkdir()
    memory = tmp_path / "memory"
    provider, exporter = _provider()
    listener = OpenTelemetryListener(tracer=provider.get_tracer("unattended"))
    code = run_unattended(memory, brief_dir=brief, telemetry=listener)
    assert code == 3
    roots = [s for s in exporter.get_finished_spans() if s.name == "invoke_agent"]
    assert roots
    assert roots[0].attributes["app.loop.product"] == "prime"


def test_next_root_has_program_and_skill(tmp_path: Path) -> None:
    brief, memory, app = _light_studio(tmp_path)
    provider, exporter = _provider()
    listener = OpenTelemetryListener(tracer=provider.get_tracer("id"))
    action = next_frame(memory, brief_dir=brief, app_dir=app, telemetry=listener)
    assert action.kind == "DELEGATE"
    root = next(s for s in exporter.get_finished_spans() if s.name == "invoke_agent")
    assert root.attributes.get("app.program.id")
    assert root.attributes.get("app.skill") == "build"
    assert root.attributes.get("app.feature.id") == "todo-cli"
    assert "loop.iteration" not in {s.name for s in exporter.get_finished_spans()}


def test_handoff_then_verify_next_shares_trace(tmp_path: Path) -> None:
    brief, memory, app = _light_studio(tmp_path)
    _adr(memory)
    provider, exporter = _provider()
    next_frame(
        memory,
        brief_dir=brief,
        app_dir=app,
        telemetry=OpenTelemetryListener(tracer=provider.get_tracer("b")),
    )
    close_frame(
        memory,
        passed=True,
        telemetry=OpenTelemetryListener(tracer=provider.get_tracer("bd")),
    )
    handoff = next_frame(
        memory,
        brief_dir=brief,
        app_dir=app,
        telemetry=OpenTelemetryListener(tracer=provider.get_tracer("h")),
    )
    assert handoff.kind == "HANDOFF"
    state = load_yaml(memory / "run-state.yaml")
    last = (state.get("telemetry") or {}).get("last_traceparent")
    assert last
    handoff_trace = int(str(last).split("-")[1], 16)
    prove = next_frame(
        memory,
        brief_dir=brief,
        app_dir=app,
        telemetry=OpenTelemetryListener(tracer=provider.get_tracer("v")),
    )
    assert prove.kind == "DELEGATE"
    assert prove.skill == "verify"
    roots = [s for s in exporter.get_finished_spans() if s.name == "invoke_agent"]
    assert roots[-1].context.trace_id == handoff_trace


def test_done_pass_execute_tool_same_trace_stderr_on_fail(tmp_path: Path) -> None:
    brief, memory, app = _light_studio(tmp_path)
    fail_py = tmp_path / "fail_unit.py"
    fail_py.write_text(
        "import sys\nsys.stderr.write('unit-boom\\n')\nsys.exit(1)\n",
        encoding="utf-8",
    )
    _write(
        memory / "adr" / "ADR-0005-technology-stack.md",
        "\n".join(
            [
                "```bash",
                f"export UNIT_TEST_CMD='python3 {fail_py}'",
                'export E2E_TEST_CMD=\'python3 -c "print(2)"\'',
                'export SECURITY_SECRETS_CMD=\'python3 -c "print(3)"\'',
                'export SECURITY_SCA_CMD="true"',
                'export SECURITY_SAST_CMD="true"',
                "```",
                "",
            ]
        ),
    )
    provider, exporter = _provider()
    next_frame(
        memory,
        brief_dir=brief,
        app_dir=app,
        telemetry=OpenTelemetryListener(tracer=provider.get_tracer("b")),
    )
    close_frame(
        memory,
        passed=True,
        telemetry=OpenTelemetryListener(tracer=provider.get_tracer("bd")),
    )
    handoff = next_frame(
        memory,
        brief_dir=brief,
        app_dir=app,
        telemetry=OpenTelemetryListener(tracer=provider.get_tracer("h")),
    )
    assert handoff.kind == "HANDOFF"
    prove = next_frame(
        memory,
        brief_dir=brief,
        app_dir=app,
        telemetry=OpenTelemetryListener(tracer=provider.get_tracer("p")),
    )
    assert prove.skill == "verify"
    state = load_yaml(memory / "run-state.yaml")
    parent = state["lock"]["traceparent"]
    prove_trace = int(parent.split("-")[1], 16)
    close_frame(
        memory,
        passed=True,
        telemetry=OpenTelemetryListener(tracer=provider.get_tracer("pd")),
    )
    tools = [s for s in exporter.get_finished_spans() if s.name == "execute_tool"]
    unit = next(s for s in tools if s.attributes.get("gen_ai.tool.name") == "UNIT_TEST_CMD")
    assert unit.context.trace_id == prove_trace
    assert unit.attributes.get("app.tool.success") is False
    assert "unit-boom" in str(unit.attributes.get("app.tool.stderr_tail") or "")
    iterations = [s for s in exporter.get_finished_spans() if s.name == "loop.iteration"]
    prove_iter = next(s for s in iterations if s.context.trace_id == prove_trace)
    assert prove_iter.attributes.get("app.skill") == "verify"
    assert "skill" not in prove_iter.attributes
