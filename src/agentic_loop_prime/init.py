"""Create a slim Prime studio. Product git lives on app/ only."""

from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from agentic_loop_prime import __version__
from agentic_loop_prime.git_flow import default_git_block, init_git_flow, is_git_repo
from agentic_loop_prime.paths import adr_path, dump_yaml, run_state_path
from agentic_loop_prime.persist import (
    default_run_state,
    ensure_program_id,
    load_run_state,
    save_run_state,
)
from agentic_loop_prime.skill_roots import (
    SKILL_NAMES,
    SUPPORT_SKILLS,
    SkillSyncError,
    pin_skill_fields,
    sync_skills,
)

# Re-exported for studio and tests.
__all__ = [
    "InitError",
    "InitResult",
    "SKILL_NAMES",
    "SUPPORT_SKILLS",
    "init_studio",
    "kit_root",
]
from agentic_loop_prime.telemetry import LoopTelemetry, NoOpTelemetry


class InitError(Exception):
    """Studio already initialized or kit files missing."""


@dataclass
class InitResult:
    studio: Path
    memory: Path
    brief_dir: Path
    app_dir: Path
    skills: int

    def format_text(self) -> str:
        return (
            f"INIT studio={self.studio} memory={self.memory} "
            f"brief={self.brief_dir} app={self.app_dir} skills={self.skills}"
        )


def kit_root() -> Path:
    here = Path(__file__).resolve()
    checkout = here.parents[2]
    if (checkout / "templates").is_dir() and (checkout / "skills").is_dir():
        return checkout
    pkg = here.parent
    if (pkg / "templates").is_dir():
        return pkg
    return checkout


def _resolve(studio: Path, raw: str | Path) -> Path:
    path = Path(raw)
    if path.is_absolute():
        return path.resolve()
    return (studio / path).resolve()


def _kit_rel(studio: Path, kit: Path) -> str:
    try:
        return str(kit.resolve().relative_to(studio.resolve()))
    except ValueError:
        return str(kit.resolve())


def _copy_if_missing(src: Path, dest: Path) -> bool:
    if dest.exists():
        return False
    if src.resolve() == dest.resolve():
        return False
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dest)
    return True


def _write_if_missing(path: Path, text: str) -> bool:
    if path.exists():
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return True


def init_studio(
    studio: Path,
    *,
    memory: str | Path = "memory",
    brief_dir: str | Path = "brief",
    app_dir: str | Path = "app",
    force: bool = False,
    telemetry: LoopTelemetry | None = None,
) -> InitResult:
    studio = Path(studio).resolve()
    studio.mkdir(parents=True, exist_ok=True)
    mem = _resolve(studio, memory)
    brief = _resolve(studio, brief_dir)
    app = _resolve(studio, app_dir)
    state_path = run_state_path(mem)
    if state_path.is_file() and not force:
        raise InitError(f"already initialized ({state_path})")

    kit = kit_root()
    templates = kit / "templates"
    for required in (
        kit / "AGENTS.md",
        kit / "CLAUDE.md",
        templates / "ADR-0005-technology-stack.md",
        templates / "CORRECTIONS.md",
    ):
        if not required.is_file():
            raise InitError(f"missing kit file {required}")

    mem.mkdir(parents=True, exist_ok=True)
    brief.mkdir(parents=True, exist_ok=True)
    app.mkdir(parents=True, exist_ok=True)

    if not state_path.is_file():
        data: dict[str, Any] = default_run_state()
        ensure_program_id(data["telemetry"])
        data["brief_dir"] = str(brief)
        data["app_dir"] = str(app)
        data["git"] = default_git_block(app)
        save_run_state(mem, data)

    decisions = mem / "decisions.yaml"
    _write_if_missing(decisions, "version: 1\nitems: []\n")

    _copy_if_missing(templates / "ADR-0005-technology-stack.md", adr_path(mem))
    _copy_if_missing(kit / "AGENTS.md", studio / "AGENTS.md")
    _copy_if_missing(kit / "CLAUDE.md", studio / "CLAUDE.md")
    _copy_if_missing(templates / "CORRECTIONS.md", studio / "CORRECTIONS.md")

    gi = templates / "product.gitignore"
    ver = templates / "VERSION"
    log = templates / "CHANGELOG.md"
    tel = telemetry or NoOpTelemetry()
    if not is_git_repo(app):
        try:
            logs = init_git_flow(
                app,
                gitignore=gi.read_text(encoding="utf-8") if gi.is_file() else "",
                version_text=ver.read_text(encoding="utf-8") if ver.is_file() else "0.0.0\n",
                changelog_text=log.read_text(encoding="utf-8") if log.is_file() else "",
            )
            for line in logs:
                print(f"GIT {line}")
            tel.execute_tool("git.init", success=True, exit_code=0)
        except Exception as exc:  # noqa: BLE001
            print(f"GIT error {exc}")
            tel.execute_tool(
                "git.init",
                success=False,
                exit_code=1,
                stderr_tail=str(exc)[-200:],
            )
    else:
        if gi.is_file():
            _write_if_missing(app / ".gitignore", gi.read_text(encoding="utf-8"))
        if ver.is_file():
            _write_if_missing(app / "VERSION", ver.read_text(encoding="utf-8"))
        if log.is_file():
            _write_if_missing(app / "CHANGELOG.md", log.read_text(encoding="utf-8"))
        print("GIT skip repo already exists")
        tel.execute_tool("git.init", success=False, exit_code=0)
    state = load_run_state(mem)
    if not state.get("git"):
        state["git"] = default_git_block(app)
        save_run_state(mem, state)

    try:
        skills = sync_skills(studio, kit, overwrite=False)
    except SkillSyncError as exc:
        raise InitError(str(exc)) from exc

    pin = {
        "version": 1,
        "kit_version": __version__,
        "kit_path": _kit_rel(studio, kit),
        "memory": str(Path(memory)),
        "brief_dir": str(Path(brief_dir)),
        "app_dir": str(Path(app_dir)),
        "ide": "cursor",
        **pin_skill_fields(),
    }
    dump_yaml(studio / ".prime" / "manifest.yaml", pin)

    return InitResult(
        studio=studio,
        memory=mem,
        brief_dir=brief,
        app_dir=app,
        skills=skills,
    )
