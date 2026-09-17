"""Read/write memory/run-state.yaml. Lock lives in this file, not locks/."""

from __future__ import annotations

import uuid
from pathlib import Path
from typing import Any

from agentic_loop_prime.paths import dump_yaml, load_yaml, run_state_path

DEFAULT_LOOP = 20


def default_telemetry() -> dict[str, Any]:
    return {
        "program_id": "",
        "last_traceparent": None,
        "last_tracestate": None,
        "frame_seq": 0,
    }


def ensure_program_id(block: dict[str, Any]) -> str:
    pid = str(block.get("program_id") or "").strip()
    if not pid:
        pid = str(uuid.uuid4())
        block["program_id"] = pid
    return pid


def default_run_state() -> dict[str, Any]:
    return {
        "version": 1,
        "program_state": "idle",
        "active_feature": None,
        "brief_dir": None,
        "app_dir": None,
        "charter_signed": False,
        "research_track": "none",
        "lock": None,
        "intent": None,
        "loop": {"initial": DEFAULT_LOOP, "remaining": DEFAULT_LOOP},
        "now": {
            "doing": None,
            "waiting_on_human": None,
            "resume_point": None,
            "autonomous": False,
            "fail_streak": 0,
            "blocked_action": None,
            "stagnation": None,
            "retry_step": None,
        },
        "features": [],
        "telemetry": default_telemetry(),
    }


def load_run_state(memory: Path) -> dict[str, Any]:
    path = run_state_path(memory)
    if not path.is_file():
        data = default_run_state()
        ensure_program_id(data["telemetry"])
        return data
    data = load_yaml(path)
    base = default_run_state()
    base.update(data)
    loop = base.get("loop") if isinstance(base.get("loop"), dict) else {}
    base["loop"] = {
        "initial": int(loop.get("initial", DEFAULT_LOOP)),
        "remaining": int(loop.get("remaining", DEFAULT_LOOP)),
    }
    if not isinstance(base.get("now"), dict):
        base["now"] = default_run_state()["now"]
    else:
        base["now"] = {**default_run_state()["now"], **base["now"]}
    if not isinstance(base.get("features"), list):
        base["features"] = []
    stored_tel = base.get("telemetry")
    merged_tel = {**default_telemetry(), **(stored_tel if isinstance(stored_tel, dict) else {})}
    ensure_program_id(merged_tel)
    base["telemetry"] = merged_tel
    return base


def save_run_state(memory: Path, data: dict[str, Any]) -> None:
    memory.mkdir(parents=True, exist_ok=True)
    dump_yaml(run_state_path(memory), data)


def start_value_for(program_state: str | None) -> str | None:
    """Map stored program_state to StateChart start_value."""
    raw = str(program_state or "idle")
    if raw in ("", "idle"):
        return None
    if raw.startswith("feature_pipeline/"):
        return raw.split("/", 1)[1]
    if raw == "feature_pipeline":
        return "pending"
    return raw
