"""Product git-flow on app/ only. memory/ stays outside the repo."""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

from agentic_loop_prime.paths import load_yaml, run_state_path

STEP_MESSAGES: dict[int, str] = {
    1: "🗃️ feat({scope}): scaffolding / schema",
    2: "✅ test({scope}): acceptance tests",
    3: "✨ feat({scope}): backend / core",
    4: "💄 feat({scope}): UI or CLI surface",
    5: "✅ test({scope}): regression tests / polish",
}

FINISH_MESSAGE = "🚀 chore({scope}): finish feature into develop"
INIT_MESSAGE = "🎉 chore: initialize git-flow (main + develop)"
PRODUCT_COMMIT_PATHS = [".", "VERSION", "CHANGELOG.md"]


def run_git(cwd: Path, *args: str) -> tuple[int, str]:
    proc = subprocess.run(
        ["git", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        check=False,
    )
    out = ((proc.stdout or "") + (proc.stderr or "")).strip()
    return proc.returncode, out


def is_git_repo(git_root: Path) -> bool:
    return (git_root / ".git").exists()


def current_branch(git_root: Path) -> str:
    code, out = run_git(git_root, "rev-parse", "--abbrev-ref", "HEAD")
    return out if code == 0 else ""


def remote_exists(git_root: Path, remote: str) -> bool:
    code, out = run_git(git_root, "remote")
    if code != 0:
        return False
    return remote in out.splitlines()


def feature_branch_name(feature_id: str) -> str:
    return f"feature/{feature_id}"


def git_config(memory: Path) -> dict[str, Any]:
    state = load_yaml(run_state_path(memory))
    cfg = state.get("git") or {}
    paths = cfg.get("commit_paths")
    if not isinstance(paths, list) or not paths:
        paths = list(PRODUCT_COMMIT_PATHS)
    else:
        paths = [str(p) for p in paths]
    root = cfg.get("root") or state.get("app_dir") or "."
    return {
        "root": str(root),
        "main_branch": str(cfg.get("main_branch") or "main"),
        "develop_branch": str(cfg.get("develop_branch") or "develop"),
        "remote": str(cfg.get("remote") or "origin"),
        "push": bool(cfg.get("push", True)),
        "auto_commit_steps": bool(cfg.get("auto_commit_steps", True)),
        "auto_ship": bool(cfg.get("auto_ship", True)),
        "commit_paths": paths,
    }


def default_git_block(app_dir: Path) -> dict[str, Any]:
    return {
        "root": str(app_dir.resolve()),
        "main_branch": "main",
        "develop_branch": "develop",
        "remote": "origin",
        "push": True,
        "auto_commit_steps": True,
        "auto_ship": True,
        "commit_paths": list(PRODUCT_COMMIT_PATHS),
    }


def resolve_git_root(memory: Path, app_dir: Path | None) -> Path | None:
    cfg = git_config(memory)
    raw = Path(str(cfg["root"]))
    if raw.is_absolute() and raw.is_dir():
        return raw
    if app_dir is not None:
        return Path(app_dir).resolve()
    return None


def ensure_identity(git_root: Path) -> None:
    code, name = run_git(git_root, "config", "--local", "user.name")
    if code != 0 or not name:
        run_git(git_root, "config", "--local", "user.name", "Prime")
    code, email = run_git(git_root, "config", "--local", "user.email")
    if code != 0 or not email:
        run_git(git_root, "config", "--local", "user.email", "agentic-loop-prime@local")


def seed_gitignore(git_root: Path, seed: str) -> bool:
    dest = git_root / ".gitignore"
    if dest.exists():
        return False
    dest.write_text(seed, encoding="utf-8")
    return True


def init_git_flow(
    git_root: Path,
    *,
    main: str = "main",
    develop: str = "develop",
    gitignore: str = "",
    version_text: str = "0.0.0\n",
    changelog_text: str = "# Changelog\n\nAll notable changes to this project are documented here.\n",
) -> list[str]:
    logs: list[str] = []
    git_root.mkdir(parents=True, exist_ok=True)
    if is_git_repo(git_root):
        ensure_identity(git_root)
        logs.append(f"repo already exists at {git_root}")
        return logs

    code, out = run_git(git_root, "init", "-b", main)
    if code != 0:
        code, out = run_git(git_root, "init")
        if code != 0:
            raise RuntimeError(f"git init failed: {out}")
        run_git(git_root, "checkout", "-b", main)
    logs.append(f"initialized repo at {git_root} on {main}")
    ensure_identity(git_root)
    if gitignore:
        seed_gitignore(git_root, gitignore)
    if not (git_root / "VERSION").exists():
        (git_root / "VERSION").write_text(version_text, encoding="utf-8")
    if not (git_root / "CHANGELOG.md").exists():
        (git_root / "CHANGELOG.md").write_text(changelog_text, encoding="utf-8")
    readme = git_root / "README.md"
    if not readme.exists():
        readme.write_text("# Project\n\nBootstrapped by Agentic Loop Prime.\n", encoding="utf-8")
    run_git(git_root, "add", "--", "README.md", ".gitignore", "VERSION", "CHANGELOG.md")
    code, out = run_git(git_root, "commit", "-m", INIT_MESSAGE)
    if code != 0 and "nothing to commit" not in out.lower():
        raise RuntimeError(f"initial commit failed: {out}")
    logs.append("initial commit on main")

    code, branches = run_git(git_root, "branch", "--list", develop)
    if develop not in (branches or ""):
        run_git(git_root, "checkout", "-b", develop)
        logs.append(f"created {develop} from {main}")
    else:
        run_git(git_root, "checkout", develop)
    return logs


def start_feature(git_root: Path, feature_id: str, develop: str) -> list[str]:
    logs: list[str] = []
    ensure_identity(git_root)
    branch = feature_branch_name(feature_id)
    code, branches = run_git(git_root, "branch", "--list", branch)
    if branch in (branches or ""):
        code, out = run_git(git_root, "checkout", branch)
        if code != 0:
            raise RuntimeError(f"checkout {branch} failed: {out}")
        logs.append(f"checked out existing {branch}")
        return logs
    code, out = run_git(git_root, "checkout", develop)
    if code != 0:
        raise RuntimeError(f"checkout {develop} failed: {out}")
    code, out = run_git(git_root, "checkout", "-b", branch)
    if code != 0:
        raise RuntimeError(f"create {branch} failed: {out}")
    logs.append(f"created {branch} from {develop}")
    return logs


def _stage(git_root: Path, pathspecs: list[str]) -> None:
    specs = pathspecs or list(PRODUCT_COMMIT_PATHS)
    run_git(git_root, "add", "--", *specs)


def commit_step(
    git_root: Path,
    feature_id: str,
    step: int,
    *,
    pathspecs: list[str] | None = None,
) -> tuple[bool, str]:
    ensure_identity(git_root)
    branch = feature_branch_name(feature_id)
    if current_branch(git_root) != branch:
        code, out = run_git(git_root, "checkout", branch)
        if code != 0:
            return False, f"not on {branch}: {out}"
    msg = STEP_MESSAGES.get(step, "✨ feat({scope}): step {step}").format(
        scope=feature_id, step=step
    )
    _stage(git_root, pathspecs or list(PRODUCT_COMMIT_PATHS))
    code, staged = run_git(git_root, "diff", "--cached", "--name-only")
    if code != 0:
        return False, staged
    if not staged.strip():
        return False, "clean working tree — nothing to commit"
    code, out = run_git(git_root, "commit", "-m", msg)
    if code != 0:
        return False, out
    return True, msg


def finish_feature(
    git_root: Path,
    feature_id: str,
    develop: str,
    *,
    pathspecs: list[str] | None = None,
    delete_branch: bool = True,
) -> list[str]:
    logs: list[str] = []
    ensure_identity(git_root)
    branch = feature_branch_name(feature_id)
    if current_branch(git_root) != branch:
        code, out = run_git(git_root, "checkout", branch)
        if code != 0:
            raise RuntimeError(f"checkout {branch} failed: {out}")
    _stage(git_root, pathspecs or list(PRODUCT_COMMIT_PATHS))
    code, staged = run_git(git_root, "diff", "--cached", "--name-only")
    if staged.strip():
        msg = FINISH_MESSAGE.format(scope=feature_id)
        code, out = run_git(git_root, "commit", "-m", msg)
        if code != 0:
            raise RuntimeError(f"pre-finish commit failed: {out}")
        logs.append(f"committed leftover changes: {msg}")
    code, out = run_git(git_root, "checkout", develop)
    if code != 0:
        raise RuntimeError(f"checkout {develop} failed: {out}")
    merge_msg = FINISH_MESSAGE.format(scope=feature_id)
    code, out = run_git(git_root, "merge", "--no-ff", branch, "-m", merge_msg)
    if code != 0:
        raise RuntimeError(f"merge {branch} → {develop} failed: {out}")
    logs.append(f"merged {branch} → {develop}")
    if delete_branch:
        code, out = run_git(git_root, "branch", "-d", branch)
        if code == 0:
            logs.append(f"deleted local {branch}")
        else:
            logs.append(f"warn: could not delete {branch}: {out}")
    return logs


def push_ref(git_root: Path, remote: str, ref: str) -> tuple[bool, str]:
    if not remote_exists(git_root, remote):
        return False, f"no remote '{remote}' — skip push"
    code, out = run_git(git_root, "push", "-u", remote, ref)
    if code != 0:
        return False, out
    return True, f"pushed {ref} → {remote}"
