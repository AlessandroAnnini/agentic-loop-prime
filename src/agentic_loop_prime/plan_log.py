"""Plan step headers and build-pass logs. Shared by schedule, done, and guards."""

from __future__ import annotations

import json
import re
from pathlib import Path

from agentic_loop_prime.paths import log_path, nonempty, plan_path

PLAN_STEP_HEADER = re.compile(r"^###\s+Step\s+(\d+)\b", re.MULTILINE)
CHECKBOX = re.compile(r"^-\s*\[([ xX])\]", re.MULTILINE)


def plan_steps_complete(memory: Path, feature_id: str) -> dict[int, bool]:
    path = plan_path(memory, feature_id)
    if not nonempty(path):
        return {}
    text = path.read_text(encoding="utf-8")
    found = sorted({int(m) for m in PLAN_STEP_HEADER.findall(text)})
    if not found:
        return {}
    complete: dict[int, bool] = {n: False for n in found}
    parts = PLAN_STEP_HEADER.split(text)
    for i in range(1, len(parts), 2):
        num = int(parts[i])
        body = parts[i + 1] if i + 1 < len(parts) else ""
        boxes = CHECKBOX.findall(body)
        complete[num] = bool(boxes) and all(m.lower() == "x" for m in boxes)
    return complete


def next_incomplete_step(memory: Path, feature_id: str) -> int | None:
    complete = plan_steps_complete(memory, feature_id)
    if not complete:
        return 1
    for n in sorted(complete):
        if not complete[n]:
            return n
    return None


def plan_steps_logged(memory: Path, feature_id: str) -> set[int]:
    """Steps whose latest build log entry is a pass (last-wins)."""
    path = log_path(memory, feature_id)
    latest: dict[int, bool] = {}
    if not path.is_file():
        return set()
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(entry, dict):
            continue
        skill = str(entry.get("skill") or "").lower()
        if skill and skill != "build":
            continue
        raw = entry.get("validated_step")
        if raw is None:
            raw = entry.get("substep")
        if raw is None:
            raw = entry.get("step")
        if raw is None:
            continue
        try:
            step = int(raw)
        except (TypeError, ValueError):
            continue
        latest[step] = bool(entry.get("verification_pass"))
    return {n for n, ok in latest.items() if ok}


def missing_build_log_steps(memory: Path, feature_id: str) -> list[int]:
    complete = plan_steps_complete(memory, feature_id)
    logged = plan_steps_logged(memory, feature_id)
    return sorted(n for n, done in complete.items() if done and n not in logged)


def build_log_matches_plan(memory: Path, feature_id: str) -> bool:
    return not missing_build_log_steps(memory, feature_id)


def last_completed_plan_step(memory: Path, feature_id: str) -> int | None:
    done = [n for n, ok in plan_steps_complete(memory, feature_id).items() if ok]
    return max(done) if done else None


def parse_reopen_step_from_security(memory: Path, feature_id: str) -> int | None:
    from agentic_loop_prime.paths import security_path

    path = security_path(memory, feature_id)
    if not path.is_file():
        return None
    for line in path.read_text(encoding="utf-8").splitlines():
        low = line.lower().strip()
        if low.startswith("**reopen_step:**") or low.startswith("reopen_step:"):
            raw = line.split(":", 1)[-1].strip().strip("*").strip()
            try:
                return int(raw)
            except ValueError:
                return None
    return None


def resolve_reopen_step(
    memory: Path,
    feature_id: str,
    hint: int | None = None,
    *,
    phase: str | None = None,
) -> int:
    from agentic_loop_prime.phase_outcomes import last_fail_retry_hint

    if phase == "security":
        sec = parse_reopen_step_from_security(memory, feature_id)
        if sec is not None:
            return sec
    if hint is None and phase:
        hint = last_fail_retry_hint(memory, feature_id, "verify", phase)
    complete = plan_steps_complete(memory, feature_id)
    declared = sorted(complete)
    if hint is not None and (not declared or hint in declared or hint >= 1):
        return int(hint)
    last = last_completed_plan_step(memory, feature_id)
    if last is not None:
        return last
    return 1


def reopen_plan_step(memory: Path, feature_id: str, step: int) -> None:
    from datetime import datetime, timezone

    from agentic_loop_prime.fingerprint import invalidate_checker_artifacts
    from agentic_loop_prime.persist import load_run_state, save_run_state

    path = plan_path(memory, feature_id)
    if path.is_file():
        text = path.read_text(encoding="utf-8")
        matches = list(PLAN_STEP_HEADER.finditer(text))
        done = re.compile(r"^(\s*-\s*)\[[xX]\]", re.MULTILINE)
        for i, match in enumerate(matches):
            if int(match.group(1)) != step:
                continue
            start = match.start()
            end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
            section = done.sub(r"\1[ ]", text[start:end])
            path.write_text(text[:start] + section + text[end:], encoding="utf-8")
            break

    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "skill": "build",
        "feature_id": feature_id,
        "substep": str(step),
        "verification_pass": False,
        "notes": "reopened",
    }
    lp = log_path(memory, feature_id)
    lp.parent.mkdir(parents=True, exist_ok=True)
    with lp.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry, ensure_ascii=False) + "\n")

    invalidate_checker_artifacts(memory, feature_id)
    state = load_run_state(memory)
    now = state.setdefault("now", {})
    now["retry_step"] = step
    for row in state.get("features") or []:
        if isinstance(row, dict) and str(row.get("feature_id")) == feature_id:
            row["retry_step"] = step
            break
    save_run_state(memory, state)
