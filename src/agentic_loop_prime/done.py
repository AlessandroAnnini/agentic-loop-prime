"""Close an open frame: log, optional stamp, clear lock."""

from __future__ import annotations

import json
import re
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from agentic_loop_prime.context import ProgramContext
from agentic_loop_prime.fingerprint import (
    invalidate_checker_artifacts,
    write_fingerprint,
)
from agentic_loop_prime.turn import verify_tree_drifted
from agentic_loop_prime.paths import log_path, plan_path
from agentic_loop_prime.plan_log import PLAN_STEP_HEADER
from agentic_loop_prime.telemetry import (
    LoopTelemetry,
    NoOpTelemetry,
    apply_carrier_to_telemetry,
    carrier_from_lock,
    frame_attrs,
)
from agentic_loop_prime.tools import (
    ToolPrepError,
    run_adr_tests,
    run_judge,
    run_security_tools,
)


class CloseError(Exception):
    """Lock missing, id mismatch, or checker not runnable. Lock is unchanged."""


@dataclass
class DoneResult:
    passed: bool
    transition_id: str
    skill: str
    feature_id: str
    substep: str

    def format_text(self) -> str:
        flag = "pass" if self.passed else "fail"
        return f"DONE {flag} transition_id={self.transition_id}"


def _tick_plan_step(path: Path, step: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.is_file() or not path.read_text(encoding="utf-8").strip():
        path.write_text(f"### Step {step}\n\n- [x] done\n", encoding="utf-8")
        return
    text = path.read_text(encoding="utf-8")
    header = re.compile(rf"^###\s+Step\s+{step}\b[^\n]*\n", re.MULTILINE)
    match = header.search(text)
    if not match:
        path.write_text(
            text.rstrip() + f"\n\n### Step {step}\n\n- [x] done\n",
            encoding="utf-8",
        )
        return
    start = match.end()
    nxt = PLAN_STEP_HEADER.search(text, start)
    end = nxt.start() if nxt else len(text)
    section = text[start:end]
    section = re.sub(r"^(\s*-\s*)\[[ xX]\]", r"\1[x]", section, flags=re.MULTILINE)
    if not re.search(r"^-\s*\[[xX]\]", section, re.MULTILINE):
        section = "- [x] done\n" + section
    path.write_text(text[:start] + section + text[end:], encoding="utf-8")


def _run_pass(
    memory: Path,
    ctx: ProgramContext,
    lock: dict[str, Any],
    telemetry: LoopTelemetry,
) -> bool:
    skill = str(lock.get("skill") or "")
    sub = str(lock.get("substep") or "")
    fid = str(lock.get("feature_id") or "program")
    if skill == "build":
        try:
            step = int(sub)
        except ValueError:
            step = 1
        _tick_plan_step(plan_path(memory, fid), step)
        if ctx.app_dir is not None:
            write_fingerprint(memory, fid, Path(ctx.app_dir))
            invalidate_checker_artifacts(memory, fid)
            telemetry.execute_tool("fingerprint", success=True, exit_code=0)
        _git_commit_step(ctx, fid, step, telemetry)
        return True
    if skill in ("intake", "design"):
        return True
    if skill == "verify" and ctx.app_dir is not None:
        drifted, msg = verify_tree_drifted(memory, fid, Path(ctx.app_dir))
        if drifted:
            print(f"FAIL: {msg}", file=sys.stderr)
            return False
    if skill == "verify" and sub == "prove":
        return run_adr_tests(memory, fid, ctx.app_dir, telemetry).passed
    if skill == "verify" and sub == "security":
        if not run_security_tools(memory, fid, ctx.app_dir, telemetry).passed:
            return False
        from agentic_loop_prime.security_report import security_report_failure_reason

        reason = security_report_failure_reason(memory, fid)
        if reason:
            print(f"FAIL: {reason}", file=sys.stderr)
            raise ToolPrepError(reason)
        return True
    if skill == "verify" and sub == "judge":
        agreed = run_judge(
            memory,
            fid,
            ctx.app_dir,
            brief_signed=ctx.brief_is_signed(),
            plan_complete=ctx.plan_complete(),
            telemetry=telemetry,
        ).passed
        if agreed:
            _git_ship(ctx, fid, telemetry)
        return agreed
    raise CloseError(f"unknown skill/substep for --pass: {skill}/{sub}")


def _git_commit_step(
    ctx: ProgramContext,
    feature_id: str,
    step: int,
    telemetry: LoopTelemetry,
) -> None:
    from agentic_loop_prime.git_flow import (
        commit_step,
        git_config,
        is_git_repo,
        resolve_git_root,
    )

    if ctx.memory_dir is None:
        return
    cfg = git_config(ctx.memory_dir)
    if not cfg["auto_commit_steps"]:
        print("GIT skip auto_commit_steps=false")
        return
    root = resolve_git_root(ctx.memory_dir, ctx.app_dir)
    if root is None or not is_git_repo(root):
        print("GIT skip no repo")
        telemetry.execute_tool("git.commit", success=False, exit_code=0)
        return
    try:
        ok, msg = commit_step(
            root, feature_id, step, pathspecs=list(cfg["commit_paths"])
        )
        telemetry.execute_tool("git.commit", success=ok, exit_code=0 if ok else 1)
        print(("GIT " if ok else "GIT skip ") + msg)
    except Exception as exc:  # noqa: BLE001
        telemetry.execute_tool(
            "git.commit",
            success=False,
            exit_code=1,
            stderr_tail=str(exc)[-200:],
        )
        print(f"GIT error {exc}")


def _git_ship(
    ctx: ProgramContext, feature_id: str, telemetry: LoopTelemetry
) -> None:
    from agentic_loop_prime.git_flow import (
        finish_feature,
        git_config,
        is_git_repo,
        push_ref,
        resolve_git_root,
    )
    from agentic_loop_prime.release import apply_release, commit_release

    if ctx.memory_dir is None:
        return
    cfg = git_config(ctx.memory_dir)
    if not cfg["auto_ship"]:
        print("GIT skip auto_ship=false")
        return
    root = resolve_git_root(ctx.memory_dir, ctx.app_dir)
    if root is None or not is_git_repo(root):
        print("GIT skip no repo")
        telemetry.execute_tool("git.merge", success=False, exit_code=0)
        return
    try:
        for line in finish_feature(
            root,
            feature_id,
            cfg["develop_branch"],
            pathspecs=list(cfg["commit_paths"]),
        ):
            print(f"GIT {line}")
        old, new = apply_release(root, ctx.memory_dir, feature_id)
        msg = commit_release(root, version=new, feature_id=feature_id)
        print(f"GIT release {old} → {new}; {msg}")
        telemetry.execute_tool("git.merge", success=True, exit_code=0)
        if cfg["push"]:
            ok, pmsg = push_ref(root, cfg["remote"], cfg["develop_branch"])
            print(("GIT " if ok else "GIT skip ") + pmsg)
    except Exception as exc:  # noqa: BLE001
        telemetry.execute_tool(
            "git.merge",
            success=False,
            exit_code=1,
            stderr_tail=str(exc)[-200:],
        )
        print(f"GIT error {exc}")


def _record_blocked(
    ctx: ProgramContext, lock: dict[str, Any], passed: bool
) -> None:
    fid = str(lock.get("feature_id") or ctx.active_feature or "program")
    skill = str(lock.get("skill") or "work")
    sub = str(lock.get("substep") or "work")
    action = f"{skill}:{sub}"
    row = None
    for item in ctx.features:
        if str(item.get("feature_id")) == fid:
            row = item
            break
    if passed:
        ctx.now["stagnation"] = None
        ctx.now["blocked_action"] = None
        ctx.now["fail_streak"] = 0
        if row is not None:
            row["blocked_action"] = ""
            row["fail_streak"] = 0
        return
    prev = ""
    streak = 0
    if row is not None:
        prev = str(row.get("blocked_action") or "")
        streak = int(row.get("fail_streak") or 0)
    if not prev:
        prev = str(ctx.now.get("blocked_action") or "")
        streak = int(ctx.now.get("fail_streak") or 0)
    streak = streak + 1 if prev == action else 1
    ctx.now["blocked_action"] = action
    ctx.now["fail_streak"] = streak
    if streak >= 2:
        ctx.now["stagnation"] = action
    if row is not None:
        row["blocked_action"] = action
        row["fail_streak"] = streak


def _append_log(memory: Path, lock: dict[str, Any], *, passed: bool, status_after: str) -> None:
    fid = str(lock.get("feature_id") or "program")
    path = log_path(memory, fid)
    path.parent.mkdir(parents=True, exist_ok=True)
    rec = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "transition_id": lock.get("transition_id"),
        "skill": lock.get("skill"),
        "feature_id": fid,
        "substep": lock.get("substep"),
        "verification_pass": passed,
        "status_after": status_after,
    }
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(rec, ensure_ascii=False) + "\n")


def close_frame(
    memory: Path,
    *,
    passed: bool,
    transition_id: str | None = None,
    telemetry: LoopTelemetry | None = None,
) -> DoneResult:
    memory = Path(memory).resolve()
    if not (memory / "run-state.yaml").is_file():
        raise CloseError("memory/run-state.yaml missing")
    ctx = ProgramContext(memory_dir=memory)
    lock = ctx.lock
    if not lock:
        raise CloseError("no open lock")
    open_id = str(lock.get("transition_id") or "")
    tid = (transition_id or open_id).strip()
    if not tid or tid != open_id:
        raise CloseError(f"transition_id mismatch (open={open_id})")

    tel = telemetry or NoOpTelemetry()
    tel.start_run(
        context=tel.extract_context(carrier_from_lock(lock)),
        **frame_attrs(
            program_id=str(ctx.telemetry.get("program_id") or ""),
            feature_id=str(lock.get("feature_id") or ctx.active_feature or ""),
            skill=str(lock.get("skill") or ""),
            substep=str(lock.get("substep") or ""),
            transition_id=open_id,
            program_state=ctx.program_state,
            loop_remaining=ctx.loop_remaining,
            autonomous=bool(ctx.now.get("autonomous")),
            frame_seq=int(ctx.telemetry.get("frame_seq") or 0),
        ),
    )
    try:
        agreed = passed
        if passed:
            used = ctx.loop_initial - ctx.loop_remaining
            tel.start_iteration(
                max(used, 1),
                **frame_attrs(
                    feature_id=str(lock.get("feature_id") or ctx.active_feature or ""),
                    skill=str(lock.get("skill") or ""),
                    substep=str(lock.get("substep") or ""),
                ),
            )
            try:
                agreed = _run_pass(memory, ctx, lock, tel)
            finally:
                tel.finish_iteration()
        _append_log(
            memory,
            lock,
            passed=agreed,
            status_after=ctx.program_state,
        )
        _record_blocked(ctx, lock, agreed)
        apply_carrier_to_telemetry(ctx.telemetry, tel.inject_carrier())
        ctx.lock = None
        ctx.now["doing"] = None
        ctx.now["waiting_on_human"] = None
        ctx.persist(ctx.program_state)
        tel.trace_evaluation(f"done.{lock.get('skill') or 'frame'}", agreed)
        tel.finish_run(
            "closed" if agreed else "goal_not_met",
            "" if agreed else "done_fail",
            error=False,
        )
        return DoneResult(
            passed=agreed,
            transition_id=open_id,
            skill=str(lock.get("skill") or ""),
            feature_id=str(lock.get("feature_id") or "program"),
            substep=str(lock.get("substep") or ""),
        )
    except ToolPrepError as exc:
        tel.finish_run("operational_error", error=True)
        raise CloseError(str(exc)) from exc
    except CloseError:
        tel.finish_run("operational_error", error=True)
        raise
    except Exception:
        tel.finish_run("operational_error", error=True)
        raise
