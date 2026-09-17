"""Queue a post-ship change or reopen a live feature into design."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from agentic_loop_prime.fingerprint import invalidate_checker_artifacts
from agentic_loop_prime.paths import (
    backlog_path,
    brief_path,
    dump_yaml,
    feature_dir,
    load_yaml,
    plan_path,
    ui_path,
    ux_path,
)
from agentic_loop_prime.persist import load_run_state, save_run_state

_SLUG = re.compile(r"[^a-z0-9]+")
CHECKBOX_DONE = re.compile(r"^(\s*-\s*)\[[xX]\]", re.MULTILINE)


class RequestChangeError(Exception):
    """Missing args or unknown feature."""


@dataclass
class RequestChangeResult:
    feature_id: str
    mode: str
    program_state: str

    def format_text(self) -> str:
        if self.mode == "reopen":
            return f"OK: reopened {self.feature_id}"
        return f"OK: queued change {self.feature_id}"


def _slug(text: str) -> str:
    s = _SLUG.sub("-", text.strip().lower()).strip("-")
    return s[:48] or "change"


def default_design_track(surface: str) -> str:
    return "standard" if str(surface).strip().lower() == "ui" else "light"


def uncheck_all_plan_steps(memory: Path, feature_id: str) -> None:
    path = plan_path(memory, feature_id)
    if not path.is_file():
        return
    text = CHECKBOX_DONE.sub(r"\1[ ]", path.read_text(encoding="utf-8"))
    path.write_text(text, encoding="utf-8")


def _feature_known(memory: Path, feature_id: str) -> bool:
    backlog = load_yaml(backlog_path(memory))
    for item in backlog.get("features") or []:
        if isinstance(item, dict) and str(item.get("id")) == feature_id:
            return True
    state = load_run_state(memory)
    for row in state.get("features") or []:
        if isinstance(row, dict) and str(row.get("feature_id")) == feature_id:
            return True
    return feature_dir(memory, feature_id).is_dir()


def apply_reopen_design(
    memory: Path, feature_id: str, *, source: str = "human"
) -> dict[str, Any]:
    """Reset design gate. ``source=autonomous`` burns the one-shot escalate budget."""
    if not _feature_known(memory, feature_id):
        raise RequestChangeError(f"unknown feature {feature_id}")
    for path in (
        brief_path(memory, feature_id),
        ux_path(memory, feature_id),
        ui_path(memory, feature_id),
    ):
        if path.is_file():
            path.unlink()
    invalidate_checker_artifacts(memory, feature_id)
    uncheck_all_plan_steps(memory, feature_id)

    state = load_run_state(memory)
    state["active_feature"] = feature_id
    state["program_state"] = "feature_pipeline/designing"
    state["lock"] = None
    now = state.setdefault("now", {})
    now["doing"] = f"design:{feature_id}"
    now["waiting_on_human"] = None
    now["resume_point"] = None
    now["stagnation"] = None
    now["blocked_action"] = None
    now["fail_streak"] = 0
    now["retry_step"] = None
    loop = state.setdefault("loop", {"initial": 1, "remaining": 0})
    loop["remaining"] = max(int(loop.get("remaining") or 0), 1)
    found = False
    count = 0
    auto_count = 0
    for row in state.get("features") or []:
        if not isinstance(row, dict):
            continue
        if str(row.get("feature_id")) == feature_id:
            count = int(row.get("design_reopen_count") or 0) + 1
            row["design_reopen_count"] = count
            if source == "autonomous":
                auto_count = int(row.get("autonomous_escalate_count") or 0) + 1
                row["autonomous_escalate_count"] = auto_count
            else:
                auto_count = int(row.get("autonomous_escalate_count") or 0)
            row["status"] = "designing"
            row["blocked_action"] = ""
            row["fail_streak"] = 0
            row["retry_step"] = None
            found = True
            break
    if not found:
        rows = list(state.get("features") or [])
        row = {"feature_id": feature_id, "status": "designing"}
        if source == "autonomous":
            row["autonomous_escalate_count"] = 1
            auto_count = 1
        rows.append(row)
        state["features"] = rows
        count = 1
    save_run_state(memory, state)
    return {
        "feature_id": feature_id,
        "design_reopen_count": count,
        "autonomous_escalate_count": auto_count,
        "source": source,
    }


def request_change(
    memory: Path,
    *,
    intent: str = "",
    feature_id: str = "",
    name: str = "",
    surface: str = "cli",
    bump: str = "patch",
) -> RequestChangeResult:
    memory = Path(memory).resolve()
    fid = (feature_id or "").strip()
    if fid:
        apply_reopen_design(memory, fid)
        state = load_run_state(memory)
        return RequestChangeResult(
            feature_id=fid,
            mode="reopen",
            program_state=str(state.get("program_state") or ""),
        )

    text = (intent or "").strip()
    if not text:
        raise RequestChangeError("pass --intent or --feature-id")

    kind = (bump or "patch").lower()
    if kind not in ("patch", "minor", "major"):
        raise RequestChangeError(f"invalid bump {bump}")
    surf = (surface or "cli").lower()
    if surf not in ("ui", "cli", "api", "library"):
        raise RequestChangeError(f"invalid surface {surface}")

    fid = _slug(name or text)
    backlog = load_yaml(backlog_path(memory))
    if not backlog:
        backlog = {"version": 1, "features": []}
    feats = backlog.setdefault("features", [])
    existing = {str(f.get("id")) for f in feats if isinstance(f, dict)}
    base = fid
    n = 2
    while fid in existing:
        fid = f"{base}-{n}"
        n += 1
    track = default_design_track(surf)
    feats.append(
        {
            "id": fid,
            "name": name or text[:80],
            "intent": text,
            "depends_on": [],
            "status": "pending",
            "surface": surf,
            "needs_ui": surf == "ui",
            "design_track": track,
            "bump": kind,
        }
    )
    dump_yaml(backlog_path(memory), backlog)

    state = load_run_state(memory)
    rows = list(state.get("features") or [])
    rows.append(
        {
            "feature_id": fid,
            "status": "pending",
            "name": name or text[:80],
            "surface": surf,
            "needs_ui": surf == "ui",
            "design_track": track,
            "bump": kind,
        }
    )
    state["features"] = rows
    prog_state = str(state.get("program_state") or "idle")
    if prog_state in ("done", "idle") or prog_state.endswith("/live"):
        state["program_state"] = "feature_pipeline/pending"
        state["active_feature"] = fid
    elif not state.get("active_feature"):
        state["active_feature"] = fid
    loop = state.setdefault("loop", {"initial": 1, "remaining": 0})
    loop["remaining"] = max(int(loop.get("remaining") or 0), 1)
    save_run_state(memory, state)
    return RequestChangeResult(
        feature_id=fid,
        mode="queue",
        program_state=str(state.get("program_state") or ""),
    )
