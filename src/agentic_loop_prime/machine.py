"""Outer program StateChart. Same states as scripts/machine_def.py; new library."""

from __future__ import annotations

from typing import Any

from statemachine import State, StateChart

from agentic_loop_prime.context import ProgramContext

FEATURE_STATES = (
    "pending",
    "designing",
    "brief_review",
    "building",
    "verifying",
    "security",
    "blocked_retry",
    "live",
)


class Program(StateChart):
    """Coarse control plane. Substeps are not states."""

    allow_event_without_transition = False

    idle = State(initial=True)
    intake = State()
    charter_review = State()
    scoping = State()

    class feature_pipeline(State.Compound):
        pending = State(initial=True)
        designing = State()
        brief_review = State()
        building = State()
        verifying = State()
        security = State()
        blocked_retry = State()
        live = State()

    done = State(final=True)

    start_intake = idle.to(intake)
    draft_ready = intake.to(charter_review, cond="intake_artifacts_ready")
    charter_signed = charter_review.to(scoping, cond="charter_is_signed")
    backlog_ready = scoping.to(feature_pipeline, cond="backlog_has_features")
    start_design = feature_pipeline.pending.to(
        feature_pipeline.designing, cond="has_active_feature"
    )
    brief_ready = feature_pipeline.designing.to(
        feature_pipeline.brief_review, cond="design_ready"
    )
    brief_signed = feature_pipeline.brief_review.to(
        feature_pipeline.building, cond="brief_is_signed"
    )
    build_complete = feature_pipeline.building.to(
        feature_pipeline.verifying, cond="plan_complete and build_logs_ok"
    )
    tests_pass = feature_pipeline.verifying.to(
        feature_pipeline.security, cond="tests_passed"
    )
    tests_fail = feature_pipeline.verifying.to(
        feature_pipeline.blocked_retry, unless="tests_passed"
    )
    retry_build = feature_pipeline.blocked_retry.to(feature_pipeline.building)
    reopen_design = feature_pipeline.blocked_retry.to(feature_pipeline.designing)
    security_pass = feature_pipeline.security.to(
        feature_pipeline.live, cond="security_passed"
    )  # leaf covers security + judge substeps
    security_fail = feature_pipeline.security.to(
        feature_pipeline.blocked_retry, unless="security_passed"
    )
    next_feature = feature_pipeline.live.to(
        feature_pipeline.pending, cond="has_pending_features"
    )
    all_done = feature_pipeline.live.to(done, cond="all_features_live")

    def __init__(
        self,
        context: ProgramContext | None = None,
        listeners: list[Any] | None = None,
        start_value: Any = None,
        **kwargs: Any,
    ) -> None:
        self.context = context or ProgramContext()
        super().__init__(
            model=self.context,
            listeners=listeners,
            start_value=start_value,
            **kwargs,
        )

    def intake_artifacts_ready(self) -> bool:
        return self.context.intake_artifacts_ready()

    def charter_is_signed(self) -> bool:
        return self.context.charter_is_signed()

    def backlog_has_features(self) -> bool:
        return self.context.backlog_has_features()

    def has_active_feature(self) -> bool:
        return self.context.has_active_feature()

    def design_ready(self) -> bool:
        return self.context.design_ready()

    def brief_is_signed(self) -> bool:
        return self.context.brief_is_signed()

    def plan_complete(self) -> bool:
        return self.context.plan_complete()

    def build_logs_ok(self) -> bool:
        return self.context.build_logs_ok()

    def tests_passed(self) -> bool:
        return self.context.tests_passed()

    def security_passed(self) -> bool:
        return self.context.security_passed()

    def has_pending_features(self) -> bool:
        return self.context.has_pending_features()

    def all_features_live(self) -> bool:
        return self.context.all_features_live()

    def on_next_feature(self) -> None:
        self.context.on_advance_feature()

    def leaf_state(self) -> str:
        """Innermost active state id (feature leaf or program leaf)."""
        values = list(self.configuration_values)
        for name in FEATURE_STATES:
            if name in values:
                return name
        for name in ("idle", "intake", "charter_review", "scoping", "done"):
            if name in values:
                return name
        return values[-1] if values else "idle"


def current_state(program: Program) -> str:
    leaf = program.leaf_state()
    if leaf in FEATURE_STATES:
        return f"feature_pipeline/{leaf}"
    return leaf
