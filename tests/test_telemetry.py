from __future__ import annotations

from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from opentelemetry.trace import StatusCode

from agentic_loop_prime import __version__
from agentic_loop_prime.context import ProgramContext
from agentic_loop_prime.machine import Program
from agentic_loop_prime.telemetry import (
    SERVICE_NAME,
    OpenTelemetryListener,
    apply_carrier_to_telemetry,
    configure_telemetry,
    export_enabled,
    make_provider,
    reset_telemetry_for_tests,
)


def _provider() -> tuple[TracerProvider, InMemorySpanExporter]:
    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    return provider, exporter


def test_evaluate_fail_is_not_error() -> None:
    provider, exporter = _provider()
    listener = OpenTelemetryListener(tracer=provider.get_tracer("test"))
    listener.start_run()
    listener.trace_evaluation("prove", passed=False, score=0)
    listener.finish_run("goal_not_met", stop_reason="evaluator_failed", error=False)

    spans = exporter.get_finished_spans()
    by_name = {s.name: s for s in spans}
    assert "invoke_agent" in by_name
    assert "goal.evaluate" in by_name
    evaluate = by_name["goal.evaluate"]
    assert evaluate.attributes["app.eval.passed"] is False
    assert evaluate.attributes["app.loop.outcome"] == "goal_not_met"
    assert evaluate.status.status_code != StatusCode.ERROR
    root = by_name["invoke_agent"]
    assert root.attributes["app.loop.product"] == "prime"
    assert root.attributes["app.loop.type"] == "goal"
    assert root.attributes["gen_ai.operation.name"] == "invoke_agent"
    assert root.status.status_code != StatusCode.ERROR


def test_listener_records_transitions_on_root_span() -> None:
    provider, exporter = _provider()
    listener = OpenTelemetryListener(tracer=provider.get_tracer("test"))
    ctx = ProgramContext(
        intake_ready=True,
        charter_signed_flag=True,
        backlog_ready_flag=True,
        active_feature="f1",
        features=[{"feature_id": "f1", "status": "pending"}],
    )
    program = Program(ctx, listeners=[listener])
    listener.start_run()
    program.send("start_intake")
    listener.finish_run("in_progress")

    spans = exporter.get_finished_spans()
    root = next(s for s in spans if s.name == "invoke_agent")
    events = [e for e in root.events if e.name == "agent.state.transition"]
    assert events
    assert events[0].attributes["app.agent.trigger"] == "start_intake"


def test_configure_without_endpoint_is_noop() -> None:
    reset_telemetry_for_tests()
    assert export_enabled() is False
    assert configure_telemetry() is False


def test_configure_disabled_env(monkeypatch) -> None:
    monkeypatch.setenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4318")
    monkeypatch.setenv("OTEL_SDK_DISABLED", "true")
    assert export_enabled() is False
    reset_telemetry_for_tests()
    assert configure_telemetry() is False


def test_make_provider_sets_service_name() -> None:
    exporter = InMemorySpanExporter()
    provider = make_provider(exporter)
    attrs = dict(provider.resource.attributes)
    assert attrs["service.name"] == SERVICE_NAME
    assert attrs["service.version"] == __version__


def test_make_provider_simple_exports_without_wait(monkeypatch) -> None:
    monkeypatch.delenv("OTEL_BSP_SCHEDULE_DELAY", raising=False)
    exporter = InMemorySpanExporter()
    provider = make_provider(exporter)
    listener = OpenTelemetryListener(tracer=provider.get_tracer("simple"))
    listener.start_run()
    listener.finish_run("ok")
    names = {s.name for s in exporter.get_finished_spans()}
    assert "invoke_agent" in names


def test_apply_carrier_overwrites_stale_last() -> None:
    block = {
        "last_traceparent": "00-old-span-01",
        "last_tracestate": "vendor=1",
    }
    apply_carrier_to_telemetry(block, {})
    assert block["last_traceparent"] is None
    assert block["last_tracestate"] is None
    apply_carrier_to_telemetry(block, {"traceparent": "00-new-span-01"})
    assert block["last_traceparent"] == "00-new-span-01"
    assert block["last_tracestate"] is None
