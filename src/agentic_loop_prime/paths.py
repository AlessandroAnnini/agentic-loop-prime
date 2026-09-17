"""Slim memory/ tree. No N/A stubs. Status is not stored here."""

from __future__ import annotations

from pathlib import Path

import yaml

SIGNED = "**Status:** signed"
STATUS_PASS = "**Status:** pass"
VERDICT_PASS = "**Verdict:** pass"


def run_state_path(memory: Path) -> Path:
    return memory / "run-state.yaml"


def charter_path(memory: Path) -> Path:
    return memory / "charter.md"


def backlog_path(memory: Path) -> Path:
    return memory / "backlog.yaml"


def decisions_path(memory: Path) -> Path:
    return memory / "decisions.yaml"


def landscape_path(memory: Path) -> Path:
    return memory / "research" / "LANDSCAPE.md"


def feature_dir(memory: Path, feature_id: str) -> Path:
    return memory / "features" / feature_id


def brief_path(memory: Path, feature_id: str) -> Path:
    return feature_dir(memory, feature_id) / "brief.md"


def plan_path(memory: Path, feature_id: str) -> Path:
    return feature_dir(memory, feature_id) / "plan.md"


def log_path(memory: Path, feature_id: str) -> Path:
    return feature_dir(memory, feature_id) / "log.jsonl"


def ux_path(memory: Path, feature_id: str) -> Path:
    return feature_dir(memory, feature_id) / "ux.md"


def ui_path(memory: Path, feature_id: str) -> Path:
    return feature_dir(memory, feature_id) / "ui.md"


def checks_dir(memory: Path, feature_id: str) -> Path:
    return feature_dir(memory, feature_id) / "checks"


def prove_path(memory: Path, feature_id: str) -> Path:
    return checks_dir(memory, feature_id) / "prove.yaml"


def security_path(memory: Path, feature_id: str) -> Path:
    return checks_dir(memory, feature_id) / "security.md"


def judge_path(memory: Path, feature_id: str) -> Path:
    return checks_dir(memory, feature_id) / "judge.md"


def fingerprint_path(memory: Path, feature_id: str) -> Path:
    return checks_dir(memory, feature_id) / "fingerprint.json"


def harness_path(memory: Path, feature_id: str) -> Path:
    return checks_dir(memory, feature_id) / "harness.json"


def tools_path(memory: Path, feature_id: str) -> Path:
    return checks_dir(memory, feature_id) / "tools.json"


def adr_path(memory: Path) -> Path:
    return memory / "adr" / "ADR-0005-technology-stack.md"


def load_yaml(path: Path) -> dict:
    if not path.is_file():
        return {}
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    return data if isinstance(data, dict) else {}


def dump_yaml(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        yaml.safe_dump(data, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )


def nonempty(path: Path) -> bool:
    return path.is_file() and bool(path.read_text(encoding="utf-8").strip())


def text_has(path: Path, marker: str) -> bool:
    return nonempty(path) and marker.lower() in path.read_text(encoding="utf-8").lower()
