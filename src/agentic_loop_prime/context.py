"""Library-free program context. Guards read this, not the StateChart library."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from agentic_loop_prime.paths import (
    SIGNED,
    backlog_path,
    brief_path,
    charter_path,
    landscape_path,
    load_yaml,
    nonempty,
    plan_path,
    run_state_path,
    text_has,
    ui_path,
    ux_path,
)
from agentic_loop_prime.persist import (
    DEFAULT_LOOP,
    default_run_state,
    ensure_program_id,
    load_run_state,
    save_run_state,
)


def _research_track(state: dict[str, Any], override: str | None) -> str:
    if override:
        return override
    raw = state.get("research_track") or "none"
    return str(raw).strip().lower() or "none"


@dataclass
class ProgramContext:
    """Flags and optional memory/ disk. No python-statemachine imports."""

    memory_dir: Path | None = None
    active_feature: str = ""
    design_track: str = "light"
    research_track: str | None = None
    features: list[dict[str, Any]] = field(default_factory=list)
    brief_dir: Path | None = None
    app_dir: Path | None = None
    stop_reason: str = ""
    program_state: str = "idle"
    lock: dict[str, Any] | None = None
    loop_initial: int = DEFAULT_LOOP
    loop_remaining: int = DEFAULT_LOOP
    intent: str = ""
    now: dict[str, Any] = field(default_factory=dict)
    telemetry: dict[str, Any] = field(default_factory=dict)

    intake_ready: bool | None = None
    charter_signed_flag: bool | None = None
    backlog_ready_flag: bool | None = None
    design_ready_flag: bool | None = None
    brief_signed_flag: bool | None = None
    plan_complete_flag: bool | None = None
    build_logs_ok_flag: bool | None = None
    tests_passed_flag: bool | None = None
    security_passed_flag: bool | None = None

    def __post_init__(self) -> None:
        if self.brief_dir is not None:
            self.brief_dir = Path(self.brief_dir).resolve()
        if self.app_dir is not None:
            self.app_dir = Path(self.app_dir).resolve()
        if self.memory_dir is not None:
            self.memory_dir = Path(self.memory_dir).resolve()
            self._hydrate_from_disk()

    def _hydrate_from_disk(self) -> None:
        assert self.memory_dir is not None
        state = load_run_state(self.memory_dir)
        self.program_state = str(state.get("program_state") or "idle")
        self.active_feature = str(state.get("active_feature") or self.active_feature)
        rows = state.get("features") or []
        if rows:
            self.features = [r for r in rows if isinstance(r, dict)]
        self._sync_features_from_backlog()
        if not self.active_feature and self.features:
            self.active_feature = str(self.features[0].get("feature_id") or "")
        row = self._active_row()
        if row and row.get("design_track"):
            self.design_track = str(row["design_track"])
        self.research_track = _research_track(state, self.research_track)
        stored_brief = state.get("brief_dir")
        stored_app = state.get("app_dir")
        if self.brief_dir is not None and stored_brief:
            if Path(stored_brief).resolve() != self.brief_dir:
                self.stop_reason = "path_mismatch"
        elif self.brief_dir is None and stored_brief:
            self.brief_dir = Path(stored_brief).resolve()
        if self.app_dir is not None and stored_app:
            if Path(stored_app).resolve() != self.app_dir:
                self.stop_reason = "path_mismatch"
        elif self.app_dir is None and stored_app:
            self.app_dir = Path(stored_app).resolve()
        lock = state.get("lock")
        self.lock = lock if isinstance(lock, dict) and lock.get("transition_id") else None
        loop = state.get("loop") or {}
        self.loop_initial = int(loop.get("initial", DEFAULT_LOOP))
        self.loop_remaining = int(loop.get("remaining", DEFAULT_LOOP))
        self.intent = str(state.get("intent") or "")
        now = state.get("now")
        self.now = dict(now) if isinstance(now, dict) else {}
        tel = state.get("telemetry")
        self.telemetry = dict(tel) if isinstance(tel, dict) else {}

    def _sync_features_from_backlog(self) -> None:
        if self.memory_dir is None:
            return
        backlog = load_yaml(backlog_path(self.memory_dir))
        existing = {str(r.get("feature_id")) for r in self.features}
        for item in backlog.get("features") or []:
            if not isinstance(item, dict) or not item.get("id"):
                continue
            fid = str(item["id"])
            if fid in existing:
                continue
            self.features.append(
                {
                    "feature_id": fid,
                    "status": "pending",
                    "name": item.get("name") or fid,
                    "surface": item.get("surface") or "cli",
                    "design_track": item.get("design_track") or "light",
                }
            )
            existing.add(fid)

    def bind_loop_budget(self, budget: int | None) -> None:
        if budget is None:
            return
        self.loop_initial = int(budget)
        self.loop_remaining = int(budget)

    def consume_loop_budget(self) -> int:
        self.loop_remaining = max(0, self.loop_remaining - 1)
        return self.loop_remaining

    def persist(self, program_state: str | None = None) -> None:
        if self.memory_dir is None:
            return
        data = load_run_state(self.memory_dir)
        if program_state is not None:
            self.program_state = program_state
        data["program_state"] = self.program_state
        data["active_feature"] = self.active_feature or None
        data["features"] = self.features
        data["brief_dir"] = str(self.brief_dir) if self.brief_dir else None
        data["app_dir"] = str(self.app_dir) if self.app_dir else None
        data["charter_signed"] = self.charter_is_signed()
        data["research_track"] = self.research_track or "none"
        data["lock"] = self.lock
        data["intent"] = self.intent or None
        data["loop"] = {
            "initial": self.loop_initial,
            "remaining": self.loop_remaining,
        }
        data["now"] = {**default_run_state()["now"], **self.now}
        tel = {**default_run_state()["telemetry"], **self.telemetry}
        ensure_program_id(tel)
        self.telemetry = tel
        data["telemetry"] = tel
        save_run_state(self.memory_dir, data)

    def _active_row(self) -> dict[str, Any] | None:
        for row in self.features:
            if str(row.get("feature_id")) == self.active_feature:
                return row
        return None

    def _state(self) -> dict[str, Any]:
        if self.memory_dir is None:
            return {}
        return load_yaml(run_state_path(self.memory_dir))

    def intake_artifacts_ready(self) -> bool:
        if self.intake_ready is not None:
            return self.intake_ready
        if self.memory_dir is None:
            return False
        if not nonempty(charter_path(self.memory_dir)):
            return False
        backlog = load_yaml(backlog_path(self.memory_dir))
        feats = [
            f
            for f in (backlog.get("features") or [])
            if isinstance(f, dict) and f.get("id")
        ]
        if not feats:
            return False
        track = _research_track(self._state(), self.research_track)
        if track in ("light", "deep"):
            return nonempty(landscape_path(self.memory_dir))
        return True

    def charter_is_signed(self) -> bool:
        if self.charter_signed_flag is not None:
            return self.charter_signed_flag
        return bool(self._state().get("charter_signed"))

    def backlog_has_features(self) -> bool:
        if self.backlog_ready_flag is not None:
            return self.backlog_ready_flag
        if self.features:
            return True
        if self.memory_dir is None:
            return False
        backlog = load_yaml(backlog_path(self.memory_dir))
        return any(
            isinstance(f, dict) and f.get("id")
            for f in (backlog.get("features") or [])
        )

    def has_active_feature(self) -> bool:
        return bool(self.active_feature)

    def design_ready(self) -> bool:
        """Track-aware. Light does not require ux.md, ui.md, or technical files."""
        if self.design_ready_flag is not None:
            return self.design_ready_flag
        if self.memory_dir is None or not self.active_feature:
            return False
        fid = self.active_feature
        if not nonempty(brief_path(self.memory_dir, fid)):
            return False
        track = (self.design_track or "light").lower()
        if track == "light":
            return True
        return nonempty(ux_path(self.memory_dir, fid)) and nonempty(
            ui_path(self.memory_dir, fid)
        )

    def brief_is_signed(self) -> bool:
        if self.brief_signed_flag is not None:
            return self.brief_signed_flag
        if self.memory_dir is None or not self.active_feature:
            return False
        return text_has(brief_path(self.memory_dir, self.active_feature), SIGNED)

    def plan_complete(self) -> bool:
        if self.plan_complete_flag is not None:
            return self.plan_complete_flag
        if self.memory_dir is None or not self.active_feature:
            return False
        path = plan_path(self.memory_dir, self.active_feature)
        if not nonempty(path):
            return False
        text = path.read_text(encoding="utf-8")
        if "### Step 1" not in text:
            return False
        return "- [ ]" not in text

    def build_logs_ok(self) -> bool:
        if self.build_logs_ok_flag is not None:
            return self.build_logs_ok_flag
        if self.memory_dir is None or not self.active_feature:
            return False
        from agentic_loop_prime.plan_log import build_log_matches_plan

        return build_log_matches_plan(self.memory_dir, self.active_feature)

    def tests_passed(self) -> bool:
        if self.tests_passed_flag is not None:
            return self.tests_passed_flag
        if self.memory_dir is None or not self.active_feature:
            return False
        from agentic_loop_prime.phase_outcomes import should_reopen_for_phase_fail
        from agentic_loop_prime.tools import prove_gate

        if should_reopen_for_phase_fail(
            self.memory_dir, self.active_feature, "verify", "prove"
        ):
            return False
        return prove_gate(self.memory_dir, self.active_feature)

    def security_passed(self) -> bool:
        """Leave the security leaf only when security tools and judge both pass.

        The chart has one `security` leaf; prove / security / judge stay substeps.
        """
        if self.security_passed_flag is not None:
            return self.security_passed_flag
        if self.memory_dir is None or not self.active_feature:
            return False
        from agentic_loop_prime.phase_outcomes import should_reopen_for_phase_fail
        from agentic_loop_prime.tools import judge_gate, security_gate

        fid = self.active_feature
        if should_reopen_for_phase_fail(
            self.memory_dir, fid, "verify", "security"
        ) or should_reopen_for_phase_fail(self.memory_dir, fid, "verify", "judge"):
            return False
        return security_gate(self.memory_dir, fid) and judge_gate(self.memory_dir, fid)

    def has_pending_features(self) -> bool:
        return any(
            str(r.get("feature_id")) != self.active_feature
            and str(r.get("status") or "") != "live"
            for r in self.features
        )

    def all_features_live(self) -> bool:
        if not self.features:
            return True
        return all(
            str(r.get("feature_id")) == self.active_feature
            or str(r.get("status") or "") == "live"
            for r in self.features
        )

    def on_advance_feature(self) -> None:
        for row in self.features:
            if str(row.get("feature_id")) == self.active_feature:
                row["status"] = "live"
        nxt = next(
            (
                str(r.get("feature_id"))
                for r in self.features
                if str(r.get("status") or "") != "live"
            ),
            "",
        )
        self.active_feature = nxt
