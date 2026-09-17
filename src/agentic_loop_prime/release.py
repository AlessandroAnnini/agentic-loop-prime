"""Semver VERSION + CHANGELOG on the product git root."""

from __future__ import annotations

import re
from datetime import date
from pathlib import Path

from agentic_loop_prime.git_flow import run_git
from agentic_loop_prime.paths import backlog_path, load_yaml

SEMVER_RE = re.compile(r"^(\d+)\.(\d+)\.(\d+)$")


def read_version(repo_root: Path) -> str:
    path = repo_root / "VERSION"
    if path.is_file():
        text = path.read_text(encoding="utf-8").strip().splitlines()[0].strip()
        if SEMVER_RE.match(text):
            return text
    return "0.0.0"


def bump_semver(version: str, bump: str) -> str:
    match = SEMVER_RE.match(version.strip())
    if not match:
        major, minor, patch = 0, 0, 0
    else:
        major, minor, patch = (int(match.group(1)), int(match.group(2)), int(match.group(3)))
    kind = (bump or "minor").lower()
    if kind == "major":
        return f"{major + 1}.0.0"
    if kind == "patch":
        return f"{major}.{minor}.{patch + 1}"
    return f"{major}.{minor + 1}.0"


def feature_bump(memory: Path, feature_id: str, default: str = "minor") -> str:
    backlog = load_yaml(backlog_path(memory))
    for item in backlog.get("features") or []:
        if isinstance(item, dict) and str(item.get("id")) == feature_id:
            raw = str(item.get("bump") or default).lower()
            if raw in ("major", "minor", "patch"):
                return raw
    return default


def append_changelog_entry(repo_root: Path, *, version: str, feature_id: str) -> Path:
    path = repo_root / "CHANGELOG.md"
    if not path.is_file():
        path.write_text(
            "# Changelog\n\nAll notable changes to this project are documented here.\n",
            encoding="utf-8",
        )
    entry = (
        f"\n## [{version}] - {date.today().isoformat()}\n\n"
        f"### Added\n\n- Feature `{feature_id}` shipped to develop.\n"
    )
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines(keepends=True)
    if lines and lines[0].startswith("#"):
        insert_at = len(lines)
        for i, line in enumerate(lines):
            if i > 0 and line.strip() == "":
                insert_at = i + 1
                break
        new_text = "".join(lines[:insert_at]) + entry + "".join(lines[insert_at:])
    else:
        new_text = "# Changelog\n" + entry + text
    path.write_text(new_text, encoding="utf-8")
    return path


def apply_release(repo_root: Path, memory: Path, feature_id: str) -> tuple[str, str]:
    old = read_version(repo_root)
    new = bump_semver(old, feature_bump(memory, feature_id))
    (repo_root / "VERSION").write_text(new + "\n", encoding="utf-8")
    append_changelog_entry(repo_root, version=new, feature_id=feature_id)
    return old, new


def commit_release(git_root: Path, *, version: str, feature_id: str) -> str:
    msg = f"📝 docs: release v{version} ({feature_id})"
    run_git(git_root, "add", "--", "VERSION", "CHANGELOG.md")
    code, out = run_git(git_root, "commit", "-m", msg)
    if code != 0:
        if "nothing to commit" in out.lower():
            return f"skip release commit ({out})"
        raise RuntimeError(f"release commit failed: {out}")
    return msg
