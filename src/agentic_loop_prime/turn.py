"""One unattended turn: artifact check, app snapshot, verify drift."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from agentic_loop_prime.fingerprint import (
    app_matches_fingerprint,
    fingerprint_app,
    fingerprint_digest,
    load_fingerprint,
)


def artifact_path(
    memory: Path, skill: str, sub: str, feature_id: str
) -> Path | None:
    fid = feature_id or "program"
    if skill == "intake":
        if sub == "research":
            return memory / "research" / "LANDSCAPE.md"
        if sub == "backlog":
            return memory / "backlog.yaml"
        return memory / "charter.md"
    if skill == "design":
        feat = memory / "features" / fid
        if sub == "ux":
            return feat / "ux.md"
        if sub == "ui":
            return feat / "ui.md"
        return feat / "brief.md"
    return None


def artifact_ready(
    memory: Path, skill: str, sub: str, feature_id: str
) -> bool:
    path = artifact_path(memory, skill, sub, feature_id)
    if path is None or not path.is_file():
        return False
    return bool(path.read_text(encoding="utf-8").strip())


def app_digest(app_dir: Path | None) -> str:
    if app_dir is None:
        return fingerprint_digest({})
    root = Path(app_dir)
    if not root.is_dir():
        return fingerprint_digest({})
    return fingerprint_digest(fingerprint_app(root))


def verify_tree_drifted(
    memory: Path, feature_id: str, app_dir: Path
) -> tuple[bool, str]:
    """True only when an existing baseline no longer matches the tree."""
    if load_fingerprint(memory, feature_id) is None:
        return False, "no baseline"
    ok, msg = app_matches_fingerprint(memory, feature_id, app_dir)
    if ok:
        return False, msg
    return True, msg


def turn_policy(skill: str, substep: str = "") -> dict[str, Any]:
    app_writable = skill == "build"
    writable = ["memory/**"]
    if app_writable:
        writable.append("app/**")
    return {
        "skill": skill,
        "substep": substep,
        "app_writable": app_writable,
        "writable": writable,
    }


def should_pass_after_agent(
    *,
    skill: str,
    sub: str,
    feature_id: str,
    memory: Path,
    app_dir: Path | None,
    before_digest: str,
) -> bool:
    if skill in ("intake", "design"):
        return artifact_ready(memory, skill, sub, feature_id)
    if skill == "build":
        return app_digest(app_dir) != before_digest
    if skill == "verify":
        if app_dir is None:
            return True
        drifted, _ = verify_tree_drifted(memory, feature_id, app_dir)
        return not drifted
    return False
