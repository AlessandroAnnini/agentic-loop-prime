"""One framed action: load memory, send(), DELEGATE or STOP, persist, OTel."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from statemachine.exceptions import TransitionNotAllowed

from agentic_loop_prime.context import ProgramContext
from agentic_loop_prime.machine import FEATURE_STATES, Program, current_state
from agentic_loop_prime.paths import (
    backlog_path,
    brief_path,
    charter_path,
    decisions_path,
    landscape_path,
    load_yaml,
    nonempty,
    plan_path,
    ui_path,
    ux_path,
)
from agentic_loop_prime.persist import ensure_program_id, start_value_for
from agentic_loop_prime.phase_outcomes import should_reopen_for_phase_fail
from agentic_loop_prime.skill_roots import skill_load_line
from agentic_loop_prime.plan_log import (
    missing_build_log_steps,
    next_incomplete_step,
    reopen_plan_step,
    resolve_reopen_step,
)
from agentic_loop_prime.telemetry import (
    LoopTelemetry,
    NoOpTelemetry,
    apply_carrier_to_lock,
    apply_carrier_to_telemetry,
    carrier_from_telemetry,
    frame_attrs,
)

MAX_SCHEDULE_DEPTH = 12
AUTO_EVENTS = (
    "start_intake",
    "draft_ready",
    "charter_signed",
    "backlog_ready",
    "start_design",
    "brief_ready",
    "brief_signed",
    "tests_pass",
    "security_pass",
    "next_feature",
    "all_done",
)


@dataclass
class Action:
    kind: str  # STOP | DELEGATE | HANDOFF
    skill: str = ""
    feature_id: str = ""
    substep: str = ""
    reason: str = ""
    path: str = ""
    message: str = ""
    transition_id: str = ""
    loop_remaining: int = 0
    resume_point: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "skill": self.skill,
            "feature_id": self.feature_id,
            "substep": self.substep,
            "reason": self.reason,
            "path": self.path,
            "message": self.message,
            "transition_id": self.transition_id,
            "loop_remaining": self.loop_remaining,
            "resume_point": self.resume_point,
        }

    def format_text(self) -> str:
        if self.kind == "STOP":
            parts = ["STOP", self.reason or "stop"]
            if self.feature_id:
                parts.append(self.feature_id)
            if self.path:
                parts.append(f"path={self.path}")
            if self.message:
                parts.append(self.message)
            return " ".join(parts)
        if self.kind == "HANDOFF":
            parts = ["HANDOFF", self.skill, self.feature_id]
            if self.message:
                parts.append(self.message)
            return " ".join(parts)
        parts = ["DELEGATE", self.skill, self.feature_id or "program"]
        if self.substep:
            parts.append(f"substep={self.substep}")
        if self.transition_id:
            parts.append(f"transition_id={self.transition_id}")
        if self.loop_remaining > 0:
            parts.append(f"loop_remaining={self.loop_remaining}")
        return " ".join(parts)


def resume_point_for(action: Action) -> str:
    if action.resume_point:
        return action.resume_point
    if action.kind == "STOP":
        bits = [f"STOP {action.reason}"]
        if action.feature_id:
            bits.append(action.feature_id)
        return " ".join(bits)
    if action.kind == "HANDOFF":
        return f"HANDOFF {action.skill} {action.feature_id}".strip()
    skill = action.skill
    fid = action.feature_id
    sub = action.substep
    if skill == "intake":
        return f"intake {sub or 'charter'}"
    if skill == "design":
        return f"design {fid} {sub or 'brief'}"
    if skill == "build":
        return f"build {fid} step {sub}"
    if skill == "verify":
        return f"verify {fid} {sub or 'prove'}"
    return f"{skill} {fid} {sub}".strip()


def prompt_block(action: Action, ctx: ProgramContext, state: str) -> str:
    memory = str(ctx.memory_dir) if ctx.memory_dir else "memory"
    brief = str(ctx.brief_dir) if ctx.brief_dir else "(set --brief-dir)"
    app = str(ctx.app_dir) if ctx.app_dir else "app"
    resume = resume_point_for(action)
    lines = [
        "--- copy-paste into a new agent session ---",
        f"Resume: {resume}",
        f"Program state: {state}",
        f"Active feature: {ctx.active_feature or 'program'}",
        f"Brief dir: {brief}",
        f"App dir: {app}",
        f"Memory: {memory}",
        f"Action: {action.format_text()}",
        "",
    ]
    if action.kind == "STOP":
        lines.append("Stop. Do not invent work. Sign or fix the named gate, then re-run al-prime next.")
    elif action.kind == "HANDOFF":
        lines.append(
            f"Switch to the `{action.skill}` checker role (do not edit `app/`)."
        )
        skill = action.skill or "verify"
        lines.append(skill_load_line(skill))
        lines.append("Re-run al-prime next to DELEGATE verify.")
    else:
        lines.extend(_delegate_prompt_lines(action, ctx, memory_arg=memory))
    return "\n".join(lines) + "\n"


def _support_skill_line(action: Action, ctx: ProgramContext) -> str:
    if action.skill == "design" and action.substep == "ux":
        return skill_load_line("ux-architect")
    if action.skill == "design" and action.substep == "ui":
        return skill_load_line("ui-direction")
    if action.skill == "build":
        row = ctx._active_row()
        surface = str((row or {}).get("surface") or "cli").lower()
        if surface == "ui":
            return skill_load_line("design-taste-frontend")
    return ""


def _write_hint(skill: str, sub: str, feature_id: str) -> str:
    fid = feature_id or "program"
    if skill == "intake":
        if sub == "research":
            return "memory/research/LANDSCAPE.md"
        if sub == "backlog":
            return "memory/backlog.yaml"
        return "memory/charter.md"
    if skill == "design":
        if sub == "ux":
            return f"memory/features/{fid}/ux.md"
        if sub == "ui":
            return f"memory/features/{fid}/ui.md"
        return f"memory/features/{fid}/brief.md"
    if skill == "build":
        return f"app/ (one plan step {sub or '1'})"
    if skill == "verify":
        if sub == "prove":
            return "do not edit app/; fill ADR-0005 if UNIT/E2E missing"
        if sub == "security":
            return f"memory/features/{fid}/checks/security.md after tools"
        if sub == "judge":
            return f"do not edit app/; --pass writes memory/features/{fid}/checks/judge.md"
    return ""


def _delegate_prompt_lines(
    action: Action, ctx: ProgramContext, *, memory_arg: str
) -> list[str]:
    skill = action.skill
    sub = action.substep or ""
    fid = action.feature_id or ctx.active_feature or "program"
    lines = [
        f"Run one {skill} session for substep {sub or '-'}.",
        skill_load_line(skill),
    ]
    extra = _support_skill_line(action, ctx)
    if extra:
        lines.append(extra)
    write = _write_hint(skill, sub, fid)
    if write:
        lines.append(f"Write: {write}")
    lines.append(f"Close: al-prime done --memory {memory_arg} --pass")
    if skill == "verify" and sub == "security":
        lines.append(
            "SECURITY_* nonzero -> DONE fail (lock cleared; next may reopen build)."
        )
        lines.append(
            "Tools pass, report still draft -> ERROR, lock stays; fill findings / "
            "**Secrets clean:** / **Status:** pass, then --pass again."
        )
    return lines


def _enabled(program: Program) -> set[str]:
    return {e.id for e in program.enabled_events()}


def _auto_advance(program: Program) -> None:
    for _ in range(20):
        enabled = _enabled(program)
        progressed = False
        for event in AUTO_EVENTS:
            if event not in enabled:
                continue
            try:
                program.send(event)
            except TransitionNotAllowed:
                continue
            progressed = True
            break
        if not progressed:
            break


def _is_autonomous(ctx: ProgramContext) -> bool:
    return bool(ctx.now.get("autonomous"))


def _open_questions(memory: Path, gate: str) -> list[str]:
    data = load_yaml(decisions_path(memory))
    ids: list[str] = []
    for item in data.get("items") or []:
        if not isinstance(item, dict):
            continue
        if str(item.get("status") or "").lower() != "open":
            continue
        blocks = item.get("blocks") or []
        if gate in blocks:
            ids.append(str(item.get("id") or "?"))
    return ids


def _blockers(ctx: ProgramContext, memory: Path, gate: str) -> list[str]:
    if _is_autonomous(ctx):
        return []
    return _open_questions(memory, gate)


def _feature_row(ctx: ProgramContext, feature_id: str) -> dict[str, Any] | None:
    for row in ctx.features:
        if str(row.get("feature_id")) == feature_id:
            return row
    return None


def _stagnation_key(ctx: ProgramContext) -> str | None:
    raw = ctx.now.get("stagnation")
    if raw:
        return str(raw)
    row = _feature_row(ctx, ctx.active_feature)
    if row is not None and int(row.get("fail_streak") or 0) >= 2:
        return str(row.get("blocked_action") or "blocked")
    if int(ctx.now.get("fail_streak") or 0) >= 2:
        return str(ctx.now.get("blocked_action") or "blocked")
    return None


def _escalate_used(ctx: ProgramContext) -> bool:
    row = _feature_row(ctx, ctx.active_feature)
    if row is None:
        return False
    return int(row.get("autonomous_escalate_count") or 0) >= 1


def _apply_retry_step(ctx: ProgramContext, feature_id: str, step: int) -> None:
    ctx.now["retry_step"] = step
    row = _feature_row(ctx, feature_id)
    if row is not None:
        row["retry_step"] = step


def _reopen_after_fail(
    ctx: ProgramContext,
    program: Program,
    telemetry: LoopTelemetry,
    *,
    phase: str,
    event: str,
    depth: int,
) -> Action:
    memory = ctx.memory_dir
    assert memory is not None
    fid = ctx.active_feature
    step = resolve_reopen_step(memory, fid, phase=phase)
    reopen_plan_step(memory, fid, step)
    telemetry.execute_tool("reopen.plan_step", success=True, exit_code=0)
    telemetry.trace_evaluation(f"phase_fail.{phase}", False)
    _apply_retry_step(ctx, fid, step)
    if event in _enabled(program):
        program.send(event)
    return _schedule(ctx, program, telemetry, depth=depth + 1)


def _next_intake_substep(ctx: ProgramContext) -> str | None:
    assert ctx.memory_dir is not None
    track = (ctx.research_track or "none").lower()
    if track in ("light", "deep") and not nonempty(landscape_path(ctx.memory_dir)):
        return "research"
    if not nonempty(charter_path(ctx.memory_dir)):
        return "charter"
    backlog = load_yaml(backlog_path(ctx.memory_dir))
    feats = [
        f
        for f in (backlog.get("features") or [])
        if isinstance(f, dict) and f.get("id")
    ]
    if not feats:
        return "backlog"
    return None


def _next_design_substep(ctx: ProgramContext) -> str | None:
    assert ctx.memory_dir is not None
    fid = ctx.active_feature
    if not fid:
        return None
    track = (ctx.design_track or "light").lower()
    if track == "standard":
        if not nonempty(ux_path(ctx.memory_dir, fid)):
            return "ux"
        if not nonempty(ui_path(ctx.memory_dir, fid)):
            return "ui"
    if not nonempty(brief_path(ctx.memory_dir, fid)):
        return "brief"
    return None


def _next_build_step(ctx: ProgramContext) -> int | None:
    assert ctx.memory_dir is not None
    return next_incomplete_step(ctx.memory_dir, ctx.active_feature)


def _next_verify_substep(ctx: ProgramContext, leaf: str) -> str:
    assert ctx.memory_dir is not None
    from agentic_loop_prime.tools import judge_gate, prove_gate, security_gate

    fid = ctx.active_feature
    if not prove_gate(ctx.memory_dir, fid):
        return "prove"
    if not security_gate(ctx.memory_dir, fid):
        return "security"
    if not judge_gate(ctx.memory_dir, fid):
        return "judge"
    return "judge" if leaf == "security" else "prove"


def _stop(
    ctx: ProgramContext,
    program: Program,
    reason: str,
    *,
    feature_id: str = "",
    path: str = "",
    message: str = "",
    resume_point: str = "",
) -> Action:
    action = Action(
        kind="STOP",
        reason=reason,
        feature_id=feature_id,
        path=path,
        message=message,
        resume_point=resume_point or f"STOP {reason}",
    )
    ctx.now["doing"] = None
    ctx.now["waiting_on_human"] = reason
    ctx.now["resume_point"] = action.resume_point
    ctx.persist(current_state(program))
    return action


def _delegate(
    ctx: ProgramContext,
    program: Program,
    skill: str,
    feature_id: str,
    substep: str,
    doing: str,
    telemetry: LoopTelemetry,
) -> Action:
    if ctx.loop_remaining <= 0:
        telemetry.trace_evaluation("session_budget", False)
        return _stop(
            ctx,
            program,
            "session_budget",
            feature_id=feature_id,
            message="loop-budget exhausted — pass --loop-budget N",
        )
    if skill == "build" and feature_id:
        _start_feature_branch(ctx, feature_id)
    tid = uuid.uuid4().hex[:12]
    remaining = ctx.consume_loop_budget()
    ctx.lock = {
        "transition_id": tid,
        "feature_id": feature_id or "program",
        "skill": skill,
        "substep": substep,
    }
    carrier = telemetry.inject_carrier()
    apply_carrier_to_lock(ctx.lock, carrier)
    apply_carrier_to_telemetry(ctx.telemetry, carrier)
    action = Action(
        kind="DELEGATE",
        skill=skill,
        feature_id=feature_id or "program",
        substep=substep,
        transition_id=tid,
        loop_remaining=remaining,
    )
    action.resume_point = resume_point_for(action)
    ctx.now["doing"] = doing
    ctx.now["waiting_on_human"] = None
    ctx.now["resume_point"] = action.resume_point
    ctx.persist(current_state(program))
    telemetry.trace_evaluation(f"delegate.{skill}", True)
    return action


def _start_feature_branch(ctx: ProgramContext, feature_id: str) -> None:
    if ctx.memory_dir is None or ctx.app_dir is None:
        return
    from agentic_loop_prime.git_flow import (
        current_branch,
        feature_branch_name,
        git_config,
        is_git_repo,
        resolve_git_root,
        start_feature,
    )

    root = resolve_git_root(ctx.memory_dir, ctx.app_dir)
    if root is None or not is_git_repo(root):
        return
    if current_branch(root) == feature_branch_name(feature_id):
        return
    cfg = git_config(ctx.memory_dir)
    try:
        for line in start_feature(root, feature_id, cfg["develop_branch"]):
            print(f"GIT {line}")
    except RuntimeError as exc:
        print(f"GIT error {exc}")


def _handoff_verify(
    ctx: ProgramContext,
    program: Program,
    feature_id: str,
    telemetry: LoopTelemetry,
) -> Action:
    ctx.intent = "verify"
    action = Action(
        kind="HANDOFF",
        skill="verify",
        feature_id=feature_id,
        resume_point=f"HANDOFF verify {feature_id}",
    )
    ctx.now["doing"] = None
    ctx.now["waiting_on_human"] = None
    ctx.now["resume_point"] = action.resume_point
    apply_carrier_to_telemetry(ctx.telemetry, telemetry.inject_carrier())
    ctx.persist(current_state(program))
    return action


def _sync_feature_status(ctx: ProgramContext, program: Program) -> None:
    leaf = program.leaf_state()
    fid = ctx.active_feature
    if leaf in FEATURE_STATES and fid:
        for row in ctx.features:
            if str(row.get("feature_id")) == fid:
                row["status"] = leaf


def _schedule(
    ctx: ProgramContext,
    program: Program,
    telemetry: LoopTelemetry,
    *,
    depth: int = 0,
) -> Action:
    if depth > MAX_SCHEDULE_DEPTH:
        return _stop(
            ctx,
            program,
            "idle",
            message=f"schedule depth exceeded (state={current_state(program)})",
        )

    if ctx.stop_reason == "path_mismatch":
        path = str(ctx.memory_dir / "run-state.yaml") if ctx.memory_dir else ""
        return _stop(
            ctx,
            program,
            "path_mismatch",
            path=path,
            message="CLI --brief-dir/--app-dir disagree with run-state.yaml",
        )

    state = current_state(program)
    if state in ("idle", "intake"):
        if ctx.brief_dir is None:
            return _stop(
                ctx, program, "brief_dir_missing", message="Pass --brief-dir"
            )
        if not ctx.brief_dir.is_dir():
            return _stop(
                ctx,
                program,
                "brief_dir_missing",
                path=str(ctx.brief_dir),
                message="brief-dir is not a directory",
            )

    if ctx.lock:
        return _stop(
            ctx,
            program,
            "transition_open",
            feature_id=str(ctx.lock.get("feature_id") or ctx.active_feature),
            path=str(ctx.memory_dir / "run-state.yaml") if ctx.memory_dir else "",
            message=f"transition_id={ctx.lock.get('transition_id')}",
        )

    if ctx.memory_dir is not None and ctx.active_feature:
        stagnated = _stagnation_key(ctx)
        if stagnated:
            if _is_autonomous(ctx) and not _escalate_used(ctx):
                from agentic_loop_prime.request_change import apply_reopen_design

                if "reopen_design" in _enabled(program):
                    program.send("reopen_design")
                apply_reopen_design(
                    ctx.memory_dir, ctx.active_feature, source="autonomous"
                )
                telemetry.trace_evaluation("autonomous_reopen_design", True)
                # New StateChart: the current ctx is still bound to `program`
                # as its model, so reuse would keep the old leaf (verifying).
                new_ctx = ProgramContext(
                    memory_dir=ctx.memory_dir,
                    brief_dir=ctx.brief_dir,
                    app_dir=ctx.app_dir,
                )
                new_ctx.loop_initial = ctx.loop_initial
                new_ctx.loop_remaining = ctx.loop_remaining
                if _is_autonomous(ctx):
                    new_ctx.now["autonomous"] = True
                listeners: list[Any] = []
                if hasattr(telemetry, "after_transition"):
                    listeners.append(telemetry)
                new_prog = Program(
                    new_ctx,
                    listeners=listeners or None,
                    start_value=start_value_for(new_ctx.program_state),
                )
                return _schedule(new_ctx, new_prog, telemetry, depth=depth + 1)
            telemetry.trace_evaluation("blocked_stagnation", False)
            return _stop(
                ctx,
                program,
                "blocked_stagnation",
                feature_id=ctx.active_feature,
                message=stagnated,
                resume_point=f"STOP blocked_stagnation {ctx.active_feature}",
            )

    _auto_advance(program)
    _sync_feature_status(ctx, program)
    state = current_state(program)
    leaf = program.leaf_state()
    memory = ctx.memory_dir
    assert memory is not None

    if state == "done":
        telemetry.trace_evaluation("program_done", True)
        return _stop(ctx, program, "idle", message="program complete")

    if state == "idle":
        if "start_intake" in _enabled(program):
            program.send("start_intake")
            _sync_feature_status(ctx, program)
            return _schedule(ctx, program, telemetry, depth=depth + 1)
        return _stop(ctx, program, "idle")

    if state == "intake":
        sub = _next_intake_substep(ctx)
        if sub is None:
            telemetry.trace_evaluation("intake_artifacts_ready", True)
            _auto_advance(program)
            return _schedule(ctx, program, telemetry, depth=depth + 1)
        return _delegate(
            ctx, program, "intake", "program", sub, f"intake:{sub}", telemetry
        )

    if state == "charter_review":
        blockers = _blockers(ctx, memory, "charter_signoff")
        if blockers:
            return _stop(
                ctx,
                program,
                "open_questions",
                path=str(decisions_path(memory)),
                message=f"Answer or defer blocking decisions: {', '.join(blockers)}",
                resume_point="STOP open_questions",
            )
        if not ctx.charter_is_signed() and _is_autonomous(ctx):
            from agentic_loop_prime.signing import auto_sign_charter

            auto_sign_charter(memory)
            ctx.charter_signed_flag = True
            ctx.persist(current_state(program))
        signed = ctx.charter_is_signed()
        telemetry.trace_evaluation("charter_signed", signed)
        if not signed:
            return _stop(
                ctx,
                program,
                "charter_review",
                path=str(charter_path(memory)),
                message="Set charter_signed: true in memory/run-state.yaml",
                resume_point="STOP charter_review",
            )
        if "charter_signed" in _enabled(program):
            program.send("charter_signed")
            return _schedule(ctx, program, telemetry, depth=depth + 1)
        return _stop(ctx, program, "idle", message="charter signed but cannot advance")

    if state == "scoping":
        if "backlog_ready" in _enabled(program):
            program.send("backlog_ready")
            ctx._sync_features_from_backlog()
            if not ctx.active_feature and ctx.features:
                ctx.active_feature = str(ctx.features[0].get("feature_id") or "")
            return _schedule(ctx, program, telemetry, depth=depth + 1)
        return _stop(
            ctx, program, "idle", message="scoping but backlog empty — fix backlog.yaml"
        )

    if leaf in ("pending", "designing"):
        if not ctx.active_feature:
            return _stop(ctx, program, "idle", message="no features in backlog")
        blockers = _blockers(ctx, memory, "design")
        if blockers:
            return _stop(
                ctx,
                program,
                "open_questions",
                feature_id=ctx.active_feature,
                path=str(decisions_path(memory)),
                message=f"Answer or defer design blockers: {', '.join(blockers)}",
                resume_point="STOP open_questions",
            )
        if leaf == "pending" and "start_design" in _enabled(program):
            program.send("start_design")
            _sync_feature_status(ctx, program)
        sub = _next_design_substep(ctx)
        if sub is None:
            telemetry.trace_evaluation("design_ready", True)
            _auto_advance(program)
            return _schedule(ctx, program, telemetry, depth=depth + 1)
        return _delegate(
            ctx,
            program,
            "design",
            ctx.active_feature,
            sub,
            f"design:{ctx.active_feature}:{sub}",
            telemetry,
        )

    if leaf == "brief_review":
        blockers = _blockers(ctx, memory, "design")
        if blockers:
            return _stop(
                ctx,
                program,
                "open_questions",
                feature_id=ctx.active_feature,
                path=str(decisions_path(memory)),
                resume_point="STOP open_questions",
            )
        if not ctx.brief_is_signed() and _is_autonomous(ctx) and ctx.active_feature:
            from agentic_loop_prime.signing import auto_sign_brief

            auto_sign_brief(memory, ctx.active_feature)
            ctx.brief_signed_flag = True
            ctx.persist(current_state(program))
        signed = ctx.brief_is_signed()
        telemetry.trace_evaluation("brief_signed", signed)
        if not signed:
            return _stop(
                ctx,
                program,
                "brief_review",
                feature_id=ctx.active_feature,
                path=str(brief_path(memory, ctx.active_feature)),
                message="Sign the feature brief (**Status:** signed)",
                resume_point=f"STOP brief_review {ctx.active_feature}",
            )
        if "brief_signed" in _enabled(program):
            program.send("brief_signed")
            return _schedule(ctx, program, telemetry, depth=depth + 1)
        return _stop(ctx, program, "idle")

    if leaf == "building":
        blockers = _blockers(ctx, memory, "build")
        if blockers:
            return _stop(
                ctx,
                program,
                "open_questions",
                feature_id=ctx.active_feature,
                path=str(decisions_path(memory)),
                resume_point="STOP open_questions",
            )
        if ctx.intent == "verify" and "build_complete" in _enabled(program):
            program.send("build_complete")
            ctx.intent = ""
            return _schedule(ctx, program, telemetry, depth=depth + 1)
        if ctx.plan_complete():
            missing = missing_build_log_steps(memory, ctx.active_feature)
            if missing:
                return _stop(
                    ctx,
                    program,
                    "build_log_gap",
                    feature_id=ctx.active_feature,
                    path=str(plan_path(memory, ctx.active_feature)),
                    message=(
                        "Plan checkboxes complete but log.jsonl missing pass "
                        f"for steps {missing} — close each step with al-prime done --pass"
                    ),
                    resume_point=f"STOP build_log_gap {ctx.active_feature}",
                )
            telemetry.trace_evaluation("build_complete", True)
            return _handoff_verify(ctx, program, ctx.active_feature, telemetry)
        step = _next_build_step(ctx)
        return _delegate(
            ctx,
            program,
            "build",
            ctx.active_feature,
            str(step or 1),
            f"build:{ctx.active_feature}:{step}",
            telemetry,
        )

    if leaf in ("verifying", "security"):
        missing = missing_build_log_steps(memory, ctx.active_feature)
        if missing:
            return _stop(
                ctx,
                program,
                "build_log_gap",
                feature_id=ctx.active_feature,
                path=str(plan_path(memory, ctx.active_feature)),
                message=(
                    "Cannot verify — missing build pass logs for steps "
                    f"{missing} — close each step with al-prime done --pass"
                ),
                resume_point=f"STOP build_log_gap {ctx.active_feature}",
            )
        if ctx.intent == "verify":
            ctx.intent = ""
        fid = ctx.active_feature
        if leaf == "verifying" and should_reopen_for_phase_fail(
            memory, fid, "verify", "prove"
        ):
            return _reopen_after_fail(
                ctx, program, telemetry, phase="prove", event="tests_fail", depth=depth
            )
        if leaf == "security":
            for phase in ("security", "judge"):
                if should_reopen_for_phase_fail(memory, fid, "verify", phase):
                    return _reopen_after_fail(
                        ctx,
                        program,
                        telemetry,
                        phase=phase,
                        event="security_fail",
                        depth=depth,
                    )
        sub = _next_verify_substep(ctx, leaf)
        if leaf == "verifying" and ctx.tests_passed() and "tests_pass" in _enabled(program):
            telemetry.trace_evaluation("prove", True)
            program.send("tests_pass")
            return _schedule(ctx, program, telemetry, depth=depth + 1)
        if leaf == "security" and ctx.security_passed() and "security_pass" in _enabled(
            program
        ):
            telemetry.trace_evaluation("security", True)
            program.send("security_pass")
            return _schedule(ctx, program, telemetry, depth=depth + 1)
        return _delegate(
            ctx,
            program,
            "verify",
            ctx.active_feature,
            sub,
            f"verify:{ctx.active_feature}:{sub}",
            telemetry,
        )

    if leaf == "blocked_retry":
        step = ctx.now.get("retry_step")
        row = _feature_row(ctx, ctx.active_feature)
        if row is not None and row.get("retry_step") is not None:
            step = row.get("retry_step")
        try:
            step_n = int(step) if step is not None else 1
        except (TypeError, ValueError):
            step_n = 1
        if "retry_build" in _enabled(program):
            program.send("retry_build")
        return _delegate(
            ctx,
            program,
            "build",
            ctx.active_feature,
            str(step_n),
            f"build:{ctx.active_feature}:{step_n}:reopen",
            telemetry,
        )

    if leaf == "live":
        _auto_advance(program)
        return _schedule(ctx, program, telemetry, depth=depth + 1)

    return _stop(ctx, program, "idle", message=f"unhandled state {state}")


def next_frame(
    memory: Path,
    brief_dir: Path | None = None,
    app_dir: Path | None = None,
    loop_budget: int | None = None,
    telemetry: LoopTelemetry | None = None,
    autonomous: bool = False,
) -> Action:
    memory = Path(memory).resolve()
    memory.mkdir(parents=True, exist_ok=True)
    ctx = ProgramContext(
        memory_dir=memory,
        brief_dir=brief_dir,
        app_dir=app_dir,
    )
    ctx.bind_loop_budget(loop_budget)
    if autonomous or ctx.now.get("autonomous"):
        ctx.now["autonomous"] = True
    tel = telemetry or NoOpTelemetry()
    listeners: list[Any] = []
    if hasattr(tel, "after_transition"):
        listeners.append(tel)
    program = Program(
        ctx,
        listeners=listeners or None,
        start_value=start_value_for(ctx.program_state),
    )
    tel_block = ctx.telemetry if isinstance(ctx.telemetry, dict) else {}
    ensure_program_id(tel_block)
    tel_block["frame_seq"] = int(tel_block.get("frame_seq") or 0) + 1
    ctx.telemetry = tel_block
    ctx.persist(ctx.program_state)
    parent_ctx = None
    resume = str(ctx.now.get("resume_point") or "")
    if resume.startswith("HANDOFF"):
        parent_ctx = tel.extract_context(carrier_from_telemetry(tel_block))
    tel.start_run(
        context=parent_ctx,
        **frame_attrs(
            program_id=str(tel_block.get("program_id") or ""),
            feature_id=ctx.active_feature,
            program_state=ctx.program_state,
            loop_remaining=ctx.loop_remaining,
            autonomous=bool(ctx.now.get("autonomous")),
            frame_seq=int(tel_block.get("frame_seq") or 0),
        ),
    )
    outcome = "ok"
    stop_reason = ""
    error = False
    try:
        action = _schedule(ctx, program, tel)
        action.resume_point = resume_point_for(action)
        tel.annotate_run(
            **frame_attrs(
                feature_id=action.feature_id or ctx.active_feature,
                skill=action.skill or "",
                substep=action.substep or "",
                transition_id=action.transition_id or "",
                kind=action.kind,
                program_state=ctx.program_state,
            )
        )
        if action.kind == "DELEGATE":
            outcome = "delegated"
        elif action.kind == "HANDOFF":
            outcome = "handoff"
        else:
            outcome = (
                "goal_not_met"
                if action.reason == "blocked_stagnation"
                else "stopped"
            )
            stop_reason = action.reason
        return action
    except Exception:
        error = True
        outcome = "operational_error"
        raise
    finally:
        tel.finish_run(outcome, stop_reason, error=error)
