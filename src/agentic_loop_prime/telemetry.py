"""Loop telemetry. Listeners only; transitions do not import OpenTelemetry."""

from __future__ import annotations

import atexit
import os
from dataclasses import dataclass, field
from typing import Any, Protocol

from opentelemetry import trace
from opentelemetry.trace import Span, Status, StatusCode
from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator

TRACER_NAME = "agentic-loop-prime"
GEN_AI_INVOKE = "invoke_agent"
SERVICE_NAME = "agentic-loop-prime"

_PROPAGATOR = TraceContextTextMapPropagator()
_configured = False
_provider: Any = None


class LoopTelemetry(Protocol):
    def start_run(self, **attrs: Any) -> Any: ...

    def annotate_run(self, **attrs: Any) -> None: ...

    def finish_run(
        self,
        outcome: str,
        stop_reason: str = "",
        *,
        error: bool = False,
    ) -> None: ...

    def start_iteration(self, index: int, **attrs: Any) -> Any: ...

    def finish_iteration(self) -> None: ...

    def trace_evaluation(
        self,
        name: str,
        passed: bool,
        score: float | None = None,
    ) -> None: ...

    def record_verification(self, passed: bool, independent: bool = True) -> None: ...

    def execute_tool(
        self,
        name: str,
        *,
        success: bool,
        exit_code: int = 0,
        operational_error: bool = False,
        stderr_tail: str = "",
    ) -> None: ...

    def inject_carrier(self) -> dict[str, str]: ...

    def extract_context(self, carrier: dict[str, str]) -> Any: ...


def export_enabled() -> bool:
    if os.environ.get("OTEL_SDK_DISABLED", "").strip().lower() in (
        "1",
        "true",
        "yes",
    ):
        return False
    return bool(
        os.environ.get("OTEL_EXPORTER_OTLP_TRACES_ENDPOINT", "").strip()
        or os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT", "").strip()
    )


def _use_batch_processor() -> bool:
    return bool(os.environ.get("OTEL_BSP_SCHEDULE_DELAY", "").strip())


def make_provider(span_exporter: Any) -> Any:
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor, SimpleSpanProcessor

    from agentic_loop_prime import __version__

    resource = Resource.create(
        {
            "service.name": SERVICE_NAME,
            "service.version": __version__,
        }
    )
    provider = TracerProvider(resource=resource)
    processor = (
        BatchSpanProcessor(span_exporter)
        if _use_batch_processor()
        else SimpleSpanProcessor(span_exporter)
    )
    provider.add_span_processor(processor)
    return provider


def flush_telemetry() -> None:
    if _provider is None:
        return
    flush = getattr(_provider, "force_flush", None)
    if not callable(flush):
        return
    try:
        flush()
    except Exception:  # noqa: BLE001
        pass


def frame_attrs(
    *,
    program_id: str = "",
    feature_id: str = "",
    skill: str = "",
    substep: str = "",
    transition_id: str = "",
    program_state: str = "",
    loop_remaining: int | None = None,
    autonomous: bool | None = None,
    frame_seq: int | None = None,
    kind: str = "",
) -> dict[str, Any]:
    """Searchable identity for the root invoke_agent. Empty values omitted."""
    out: dict[str, Any] = {}
    mapping = {
        "app.program.id": program_id,
        "app.feature.id": feature_id,
        "app.skill": skill,
        "app.substep": substep,
        "app.transition_id": transition_id,
        "app.program_state": program_state,
        "app.action.kind": kind,
    }
    for key, raw in mapping.items():
        text = str(raw or "").strip()
        if text:
            out[key] = text
    if loop_remaining is not None:
        out["app.loop.remaining"] = int(loop_remaining)
    if autonomous is not None:
        out["app.loop.autonomous"] = bool(autonomous)
    if frame_seq is not None:
        out["app.loop.frame_seq"] = int(frame_seq)
    return out


def configure_telemetry(*, span_exporter: Any | None = None) -> bool:
    """Install a global TracerProvider when an OTLP endpoint is set.

    ``span_exporter`` is for tests. Production uses HTTP OTLP env config.
    """
    global _configured, _provider
    if _configured:
        return True
    if span_exporter is None and not export_enabled():
        return False
    if span_exporter is None:
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import (
            OTLPSpanExporter,
        )

        span_exporter = OTLPSpanExporter()
    provider = make_provider(span_exporter)
    trace.set_tracer_provider(provider)
    atexit.register(provider.shutdown)
    _provider = provider
    _configured = True
    return True


def reset_telemetry_for_tests() -> None:
    global _configured, _provider
    if _provider is not None:
        try:
            _provider.shutdown()
        except Exception:  # noqa: BLE001
            pass
    _provider = None
    _configured = False


def carrier_from_lock(lock: dict[str, Any] | None) -> dict[str, str]:
    if not lock:
        return {}
    carrier: dict[str, str] = {}
    raw = lock.get("traceparent")
    if raw:
        carrier["traceparent"] = str(raw)
    state = lock.get("tracestate")
    if state:
        carrier["tracestate"] = str(state)
    return carrier


def apply_carrier_to_lock(lock: dict[str, Any], carrier: dict[str, str]) -> None:
    parent = carrier.get("traceparent")
    if parent:
        lock["traceparent"] = parent
    state = carrier.get("tracestate")
    if state:
        lock["tracestate"] = state


def apply_carrier_to_telemetry(block: dict[str, Any], carrier: dict[str, str]) -> None:
    """Copy W3C carrier onto run-state telemetry.last_* (no SDK).

    Always overwrite both keys so an empty inject (NoOp or non-recording
    tracer) cannot leave a stale parent for the next HANDOFF stitch.
    """
    parent = (carrier.get("traceparent") or "").strip()
    state = (carrier.get("tracestate") or "").strip()
    block["last_traceparent"] = parent or None
    block["last_tracestate"] = state or None


def carrier_from_telemetry(block: dict[str, Any] | None) -> dict[str, str]:
    if not block:
        return {}
    carrier: dict[str, str] = {}
    raw = block.get("last_traceparent")
    if raw:
        carrier["traceparent"] = str(raw)
    state = block.get("last_tracestate")
    if state:
        carrier["tracestate"] = str(state)
    return carrier


@dataclass
class NoOpTelemetry:
    outcomes: list[dict[str, Any]] = field(default_factory=list)
    evaluations: list[dict[str, Any]] = field(default_factory=list)
    verifications: list[dict[str, Any]] = field(default_factory=list)
    iterations: list[int] = field(default_factory=list)
    transitions: list[tuple[str, str, str]] = field(default_factory=list)
    tools: list[dict[str, Any]] = field(default_factory=list)
    annotations: list[dict[str, Any]] = field(default_factory=list)
    _run_open: bool = False

    def start_run(self, **attrs: Any) -> Any:
        self._run_open = True
        return None

    def annotate_run(self, **attrs: Any) -> None:
        self.annotations.append(dict(attrs))

    def finish_run(
        self,
        outcome: str,
        stop_reason: str = "",
        *,
        error: bool = False,
    ) -> None:
        self.outcomes.append(
            {"outcome": outcome, "stop_reason": stop_reason, "error": error}
        )
        self._run_open = False

    def start_iteration(self, index: int, **attrs: Any) -> Any:
        self.iterations.append(index)
        return None

    def finish_iteration(self) -> None:
        return None

    def trace_evaluation(
        self,
        name: str,
        passed: bool,
        score: float | None = None,
    ) -> None:
        self.evaluations.append({"name": name, "passed": passed, "score": score})

    def record_verification(self, passed: bool, independent: bool = True) -> None:
        self.verifications.append({"passed": passed, "independent": independent})

    def execute_tool(
        self,
        name: str,
        *,
        success: bool,
        exit_code: int = 0,
        operational_error: bool = False,
        stderr_tail: str = "",
    ) -> None:
        rec: dict[str, Any] = {
            "name": name,
            "success": success,
            "exit_code": exit_code,
            "operational_error": operational_error,
        }
        if stderr_tail:
            rec["stderr_tail"] = stderr_tail
        self.tools.append(rec)

    def inject_carrier(self) -> dict[str, str]:
        return {}

    def extract_context(self, carrier: dict[str, str]) -> Any:
        return None

    def after_transition(self, source: Any, target: Any, event: str) -> None:
        src = getattr(source, "id", str(source))
        dst = getattr(target, "id", str(target))
        self.transitions.append((str(src), str(event), str(dst)))


def _base_run_attrs() -> dict[str, Any]:
    return {
        "gen_ai.operation.name": GEN_AI_INVOKE,
        "app.loop.type": "goal",
        "app.loop.product": "prime",
    }


class OpenTelemetryListener:
    """StateChart listener + LoopTelemetry. No domain imports of OTel elsewhere."""

    def __init__(self, tracer: trace.Tracer | None = None) -> None:
        self._tracer = tracer or trace.get_tracer(TRACER_NAME)
        self._run: Span | None = None
        self._iteration: Span | None = None

    def start_run(self, **attrs: Any) -> Span:
        self._end_iteration()
        context = attrs.pop("context", None)
        merged = {**_base_run_attrs(), **attrs}
        self._run = self._tracer.start_span(
            GEN_AI_INVOKE,
            context=context,
            attributes=merged,
        )
        return self._run

    def annotate_run(self, **attrs: Any) -> None:
        span = self._run
        if span is None:
            return
        for key, val in attrs.items():
            if val is None:
                continue
            if isinstance(val, bool):
                span.set_attribute(key, val)
                continue
            if isinstance(val, (int, float)):
                span.set_attribute(key, val)
                continue
            text = str(val).strip()
            if text:
                span.set_attribute(key, text)

    def finish_run(
        self,
        outcome: str,
        stop_reason: str = "",
        *,
        error: bool = False,
    ) -> None:
        self._end_iteration()
        span = self._run
        if span is None:
            flush_telemetry()
            return
        span.set_attribute("app.loop.outcome", outcome)
        if stop_reason:
            span.set_attribute("app.loop.stop_reason", stop_reason)
        if error:
            span.set_status(Status(StatusCode.ERROR, outcome))
        self._run.end()
        self._run = None
        flush_telemetry()

    def start_iteration(self, index: int, **attrs: Any) -> Span:
        self._end_iteration()
        ctx = trace.set_span_in_context(self._run) if self._run else None
        merged = {"app.loop.iteration": index, **attrs}
        self._iteration = self._tracer.start_span(
            "loop.iteration",
            context=ctx,
            attributes=merged,
        )
        return self._iteration

    def finish_iteration(self) -> None:
        self._end_iteration()

    def _end_iteration(self) -> None:
        if self._iteration is not None:
            self._iteration.end()
            self._iteration = None

    def inject_carrier(self) -> dict[str, str]:
        if self._run is None:
            return {}
        carrier: dict[str, str] = {}
        ctx = trace.set_span_in_context(self._run)
        _PROPAGATOR.inject(carrier, context=ctx)
        return carrier

    def extract_context(self, carrier: dict[str, str]) -> Any:
        if not carrier or not carrier.get("traceparent"):
            return None
        return _PROPAGATOR.extract(carrier)

    def trace_evaluation(
        self,
        name: str,
        passed: bool,
        score: float | None = None,
    ) -> None:
        parent = self._iteration or self._run
        ctx = trace.set_span_in_context(parent) if parent else None
        with self._tracer.start_as_current_span(
            "goal.evaluate",
            context=ctx,
            attributes={
                "app.eval.name": name,
                "app.eval.passed": passed,
            },
        ) as span:
            if score is not None:
                span.set_attribute("app.eval.score", score)
            if not passed:
                span.set_attribute("app.loop.outcome", "goal_not_met")
            # goal_not_met is an outcome, not StatusCode.ERROR

    def record_verification(self, passed: bool, independent: bool = True) -> None:
        parent = self._iteration or self._run
        ctx = trace.set_span_in_context(parent) if parent else None
        with self._tracer.start_as_current_span(
            "goal.verify",
            context=ctx,
            attributes={
                "app.verification.independent": independent,
                "app.verification.result": "passed" if passed else "failed",
            },
        ):
            pass

    def execute_tool(
        self,
        name: str,
        *,
        success: bool,
        exit_code: int = 0,
        operational_error: bool = False,
        stderr_tail: str = "",
    ) -> None:
        parent = self._iteration or self._run
        ctx = trace.set_span_in_context(parent) if parent else None
        attrs: dict[str, Any] = {
            "gen_ai.operation.name": "execute_tool",
            "gen_ai.tool.name": name,
            "app.tool.success": success,
            "app.tool.exit_code": exit_code,
        }
        tail = (stderr_tail or "").strip()
        if tail:
            attrs["app.tool.stderr_tail"] = tail[-200:]
        with self._tracer.start_as_current_span(
            "execute_tool",
            context=ctx,
            attributes=attrs,
        ) as span:
            if operational_error:
                span.set_status(Status(StatusCode.ERROR, name))

    def after_transition(self, source: Any, target: Any, event: str) -> None:
        span = self._iteration or self._run
        if span is None:
            return
        src = getattr(source, "id", str(source))
        dst = getattr(target, "id", str(target))
        span.add_event(
            "agent.state.transition",
            attributes={
                "app.agent.state.from": str(src),
                "app.agent.state.to": str(dst),
                "app.agent.trigger": str(event),
            },
        )
