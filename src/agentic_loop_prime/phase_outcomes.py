"""Session-log phase matching for prove/security/judge reopen decisions."""

from __future__ import annotations

import json
from pathlib import Path

from agentic_loop_prime.paths import log_path


def load_log_entries(memory: Path, feature_id: str) -> list[dict]:
    path = log_path(memory, feature_id)
    if not path.is_file():
        return []
    entries: list[dict] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(rec, dict):
            entries.append(rec)
    return entries


def is_latest_checker_entry(entries: list[dict], index: int) -> bool:
    for later in entries[index + 1 :]:
        if str(later.get("skill") or "").lower() in ("verify", "security"):
            return False
    return True


def entry_matches_phase(
    entry: dict,
    skill: str,
    substep: str | None = None,
    *,
    latest_checker: bool = False,
) -> bool:
    entry_skill = str(entry.get("skill") or "").lower()
    step_blob = " ".join(
        str(entry.get(k) or "") for k in ("substep", "step", "phase")
    ).lower()
    if skill == "verify" and substep in ("prove", None):
        if entry_skill != "verify":
            return False
        if substep is None:
            return True
        if any(tok in step_blob for tok in ("security", "gate", "judge")):
            return False
        return True
    if skill == "verify" and substep == "security":
        if entry_skill == "security":
            return True
        if entry_skill != "verify":
            return False
        if any(tok in step_blob for tok in ("prove", "judge")):
            return False
        if any(tok in step_blob for tok in ("security", "gate")):
            return True
        if not step_blob.strip() or step_blob.strip() == "work":
            return latest_checker
        return False
    if skill == "verify" and substep == "judge":
        if entry_skill != "verify":
            return False
        return "judge" in step_blob
    return entry_skill == skill.lower()


def is_build_pass_entry(entry: dict) -> bool:
    return (
        str(entry.get("skill") or "").lower() == "build"
        and bool(entry.get("verification_pass"))
    )


def should_reopen_for_phase_fail(
    memory: Path,
    feature_id: str,
    skill: str,
    substep: str | None = None,
) -> bool:
    entries = load_log_entries(memory, feature_id)
    last_build_pass_idx = -1
    last_phase_fail_idx = -1
    last_phase_pass_idx = -1
    for i, entry in enumerate(entries):
        if is_build_pass_entry(entry):
            last_build_pass_idx = i
        if not entry_matches_phase(
            entry,
            skill,
            substep,
            latest_checker=is_latest_checker_entry(entries, i),
        ):
            continue
        if entry.get("verification_pass"):
            last_phase_pass_idx = i
        else:
            last_phase_fail_idx = i
    if last_phase_fail_idx < 0:
        return False
    if last_phase_pass_idx > last_phase_fail_idx:
        return False
    if last_phase_fail_idx <= last_build_pass_idx:
        return False
    return True


def last_fail_retry_hint(
    memory: Path,
    feature_id: str,
    skill: str,
    substep: str | None = None,
) -> int | None:
    entries = load_log_entries(memory, feature_id)
    hint: int | None = None
    for i, entry in enumerate(entries):
        if not entry_matches_phase(
            entry,
            skill,
            substep,
            latest_checker=is_latest_checker_entry(entries, i),
        ):
            continue
        if entry.get("verification_pass"):
            continue
        raw = entry.get("retry_step")
        if raw is None:
            continue
        try:
            hint = int(raw)
        except (TypeError, ValueError):
            continue
    return hint
