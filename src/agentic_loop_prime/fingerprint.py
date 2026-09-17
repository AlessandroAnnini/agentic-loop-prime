"""App-tree fingerprints for maker≠checker enforcement."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

from agentic_loop_prime.paths import (
    dump_yaml,
    fingerprint_path,
    harness_path,
    judge_path,
    prove_path,
    security_path,
    tools_path,
)

SKIP_DIR_NAMES = {
    ".git",
    ".venv",
    "venv",
    "__pycache__",
    ".pytest_cache",
    "node_modules",
    ".mypy_cache",
    ".ruff_cache",
    "dist",
    "build",
    ".coverage",
    "htmlcov",
    ".tox",
    "target",
}

STATUS_LINE = re.compile(r"^(\*\*Status:\*\*\s*)\S+", re.IGNORECASE | re.MULTILINE)
VERDICT_LINE = re.compile(r"^(\*\*Verdict:\*\*\s*)\S+", re.IGNORECASE | re.MULTILINE)


def _iter_files(app_dir: Path) -> list[Path]:
    if not app_dir.is_dir():
        return []
    out: list[Path] = []
    for path in sorted(app_dir.rglob("*")):
        if not path.is_file():
            continue
        if any(part in SKIP_DIR_NAMES for part in path.parts):
            continue
        if path.name in {".coverage", "coverage.xml", "junit.xml"}:
            continue
        out.append(path)
    return out


def fingerprint_app(app_dir: Path) -> dict[str, str]:
    """Map relative path to sha256 hex digest."""
    root = app_dir.resolve()
    result: dict[str, str] = {}
    for path in _iter_files(root):
        rel = str(path.relative_to(root)).replace("\\", "/")
        result[rel] = hashlib.sha256(path.read_bytes()).hexdigest()
    return result


def fingerprint_digest(files: dict[str, str] | None) -> str:
    payload = json.dumps(files or {}, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def load_fingerprint(memory: Path, feature_id: str) -> dict[str, Any] | None:
    path = fingerprint_path(memory, feature_id)
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    return data if isinstance(data, dict) else None


def baseline_digest(memory: Path, feature_id: str) -> str | None:
    data = load_fingerprint(memory, feature_id)
    if not data:
        return None
    if data.get("digest"):
        return str(data["digest"])
    return fingerprint_digest(data.get("files") or {})


def write_fingerprint(memory: Path, feature_id: str, app_dir: Path) -> Path:
    path = fingerprint_path(memory, feature_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    files = fingerprint_app(app_dir)
    payload: dict[str, Any] = {
        "feature_id": feature_id,
        "app_dir": str(app_dir.resolve()),
        "files": files,
        "digest": fingerprint_digest(files),
    }
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return path


def app_matches_fingerprint(
    memory: Path, feature_id: str, app_dir: Path
) -> tuple[bool, str]:
    baseline = load_fingerprint(memory, feature_id)
    current = fingerprint_app(app_dir)
    if baseline is None:
        if not current:
            return True, "no baseline and empty app"
        return (
            False,
            "missing app fingerprint baseline — complete a passing build step first",
        )
    expected = baseline.get("files") or {}
    if expected != current:
        added = sorted(set(current) - set(expected))
        removed = sorted(set(expected) - set(current))
        changed = sorted(
            p for p in set(expected) & set(current) if expected[p] != current[p]
        )
        bits = []
        if changed:
            bits.append(f"changed={changed[:5]}")
        if added:
            bits.append(f"added={added[:5]}")
        if removed:
            bits.append(f"removed={removed[:5]}")
        return False, "app tree drifted from build fingerprint (" + ", ".join(bits) + ")"
    return True, "app fingerprint unchanged"


def invalidate_checker_artifacts(memory: Path, feature_id: str) -> None:
    dump_yaml(
        prove_path(memory, feature_id),
        {
            "feature_id": feature_id,
            "tests_passed": False,
            "app_fingerprint": None,
            "stale": True,
        },
    )
    for path in (
        harness_path(memory, feature_id),
        tools_path(memory, feature_id),
    ):
        if path.is_file():
            path.unlink()

    sec = security_path(memory, feature_id)
    if sec.is_file():
        text = sec.read_text(encoding="utf-8")
        text = STATUS_LINE.sub(r"\1stale", text, count=1)
        if "**Status:**" not in text:
            text = f"**Status:** stale\n\n{text}"
        sec.write_text(text, encoding="utf-8")

    jud = judge_path(memory, feature_id)
    if jud.is_file():
        text = jud.read_text(encoding="utf-8")
        text = VERDICT_LINE.sub(r"\1stale", text, count=1)
        if "**Verdict:**" not in text and "Verdict:" not in text:
            text = f"**Verdict:** stale\n\n{text}"
        jud.write_text(text, encoding="utf-8")
