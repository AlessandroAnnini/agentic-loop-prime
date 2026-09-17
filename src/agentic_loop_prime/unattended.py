"""Outer goal-loop: call next_frame until human STOP or AGENT_NEEDED."""

from __future__ import annotations

import json
import os
import shlex
import subprocess
import sys
from pathlib import Path

from agentic_loop_prime.context import ProgramContext
from agentic_loop_prime.done import CloseError, close_frame
from agentic_loop_prime.persist import load_run_state
from agentic_loop_prime.schedule import Action, next_frame, prompt_block
from agentic_loop_prime.telemetry import LoopTelemetry, OpenTelemetryListener
from agentic_loop_prime.turn import (
    app_digest,
    should_pass_after_agent,
    turn_policy,
)

HUMAN_PAUSE = {
    "charter_review",
    "brief_review",
    "open_questions",
    "blocked_stagnation",
    "path_mismatch",
    "brief_dir_missing",
    "build_log_gap",
    "session_budget",
    "transition_open",
}


def _now_dir(memory: Path) -> Path:
    path = memory / "now"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _al_prime_cmd() -> list[str]:
    return [sys.executable, "-m", "agentic_loop_prime"]


def write_continue_sh(
    memory: Path,
    *,
    brief_dir: Path | None,
    app_dir: Path | None,
    autonomous: bool,
    agent_cmd: str = "",
) -> Path:
    path = _now_dir(memory) / "continue.sh"
    parts = [
        *_al_prime_cmd(),
        "unattended",
        "--memory",
        str(memory),
    ]
    if brief_dir is not None:
        parts.extend(["--brief-dir", str(brief_dir)])
    if app_dir is not None:
        parts.extend(["--app-dir", str(app_dir)])
    if autonomous:
        parts.append("--autonomous")
    if agent_cmd:
        parts.extend(["--agent-cmd", agent_cmd])
    path.write_text(
        "#!/usr/bin/env bash\n" + " ".join(shlex.quote(p) for p in parts) + "\n",
        encoding="utf-8",
    )
    path.chmod(path.stat().st_mode | 0o111)
    return path


def _write_action_files(
    memory: Path,
    action: Action,
    brief_dir: Path | None,
    app_dir: Path | None,
) -> tuple[Path, Path, Path]:
    now = _now_dir(memory)
    ctx = ProgramContext(memory_dir=memory, brief_dir=brief_dir, app_dir=app_dir)
    prompt_path = now / "next-prompt.md"
    prompt_path.write_text(prompt_block(action, ctx, ctx.program_state), encoding="utf-8")
    action_path = now / "next-action.json"
    action_path.write_text(
        json.dumps(action.to_dict(), indent=2) + "\n", encoding="utf-8"
    )
    policy_path = now / "next-policy.json"
    policy_path.write_text(
        json.dumps(turn_policy(action.skill, action.substep), indent=2) + "\n",
        encoding="utf-8",
    )
    return prompt_path, action_path, policy_path


def _lock_open(memory: Path) -> bool:
    state = load_run_state(memory)
    return bool(state.get("lock"))


def _close_turn(
    memory: Path,
    *,
    passed: bool,
    telemetry: LoopTelemetry,
) -> None:
    try:
        result = close_frame(memory, passed=passed, telemetry=telemetry)
        print(result.format_text())
        return
    except CloseError as exc:
        print(f"ERROR {exc}", file=sys.stderr)
        if not _lock_open(memory):
            raise
        result = close_frame(memory, passed=False, telemetry=telemetry)
        print(result.format_text())


def run_unattended(
    memory: Path,
    *,
    brief_dir: Path | None = None,
    app_dir: Path | None = None,
    loop_budget: int | None = None,
    autonomous: bool = False,
    max_turns: int = 50,
    agent_cmd: str = "",
    telemetry: LoopTelemetry | None = None,
) -> int:
    memory = Path(memory).resolve()
    brief = Path(brief_dir).resolve() if brief_dir else None
    app = Path(app_dir).resolve() if app_dir else None
    budget_once = loop_budget
    sticky = autonomous
    turns = 0
    while turns < max_turns:
        turns += 1
        budget = budget_once
        budget_once = None
        tel = telemetry or OpenTelemetryListener()
        try:
            action = next_frame(
                memory,
                brief_dir=brief,
                app_dir=app,
                loop_budget=budget,
                autonomous=sticky,
                telemetry=tel,
            )
        except Exception as exc:  # noqa: BLE001
            print(f"ERROR {exc}", file=sys.stderr)
            return 1

        state = load_run_state(memory)
        if state.get("now", {}).get("autonomous"):
            sticky = True

        print(action.format_text())

        if action.kind == "STOP":
            reason = action.reason or "stop"
            if reason == "idle":
                if str(state.get("program_state") or "") == "done":
                    print("OK: program done")
                    return 0
                print(f"STOP idle — not done yet ({state.get('program_state')})")
                return 2
            if reason in HUMAN_PAUSE or reason:
                print(f"PAUSE: {reason}", file=sys.stderr)
                return 2
            return 2

        if action.kind in ("DELEGATE", "HANDOFF"):
            prompt_path, action_path, policy_path = _write_action_files(
                memory, action, brief, app
            )
            write_continue_sh(
                memory,
                brief_dir=brief,
                app_dir=app,
                autonomous=sticky,
                agent_cmd=agent_cmd,
            )
            if action.kind == "HANDOFF":
                continue
            if not agent_cmd:
                continue_path = memory / "now" / "continue.sh"
                print(
                    "AGENT_NEEDED: run one skill session using "
                    f"{prompt_path} then re-invoke via {continue_path}."
                )
                return 3
            before = app_digest(app)
            env = {
                **os.environ,
                "ALP_PROMPT_FILE": str(prompt_path),
                "ALP_ACTION_JSON": str(action_path),
                "ALP_POLICY_FILE": str(policy_path),
            }
            proc = subprocess.run(agent_cmd, shell=True, env=env)
            if proc.returncode != 0:
                print(
                    f"FAIL: agent-cmd exited {proc.returncode}",
                    file=sys.stderr,
                )
                try:
                    _close_turn(memory, passed=False, telemetry=tel)
                except CloseError:
                    return 1
                continue
            passed = should_pass_after_agent(
                skill=action.skill,
                sub=action.substep,
                feature_id=action.feature_id or "program",
                memory=memory,
                app_dir=app,
                before_digest=before,
            )
            try:
                _close_turn(memory, passed=passed, telemetry=tel)
            except CloseError:
                return 1
            continue

        print(f"ERROR: unexpected action {action.kind}", file=sys.stderr)
        return 1

    print("ERROR: max-turns exceeded", file=sys.stderr)
    return 1
