"""Refresh a Prime studio pin/skills and report health."""

from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from agentic_loop_prime import __version__
from agentic_loop_prime.init import (
    SKILL_NAMES,
    SUPPORT_SKILLS,
    InitError,
    _copy_if_missing,
    _kit_rel,
    _resolve,
    _sync_support_skill,
    _write_if_missing,
    kit_root,
)
from agentic_loop_prime.adr_commands import require_commands, require_security_commands
from agentic_loop_prime.paths import adr_path, dump_yaml, load_yaml, run_state_path
from agentic_loop_prime.persist import load_run_state
from agentic_loop_prime.telemetry import LoopTelemetry, NoOpTelemetry


class StudioError(Exception):
    """Studio is missing a pin or kit files."""


@dataclass
class UpdateResult:
    studio: Path
    skills: int

    def format_text(self) -> str:
        return f"UPDATE studio={self.studio} skills={self.skills}"


@dataclass
class DoctorResult:
    ok: bool
    lines: list[str]

    def format_text(self) -> str:
        return "\n".join(self.lines)


def resolve_studio(studio: Path | str | None) -> Path:
    root = Path(studio or ".").resolve()
    if (root / ".prime" / "manifest.yaml").is_file():
        return root
    cwd = Path.cwd()
    if (cwd / ".prime" / "manifest.yaml").is_file() and studio in (None, ".", ""):
        return cwd
    return root


def _pin_path(studio: Path) -> Path:
    return studio / ".prime" / "manifest.yaml"


def _overwrite_skills(studio: Path, kit: Path) -> int:
    src_root = kit / "skills"
    dest_root = studio / ".cursor" / "skills"
    count = 0
    for name in SKILL_NAMES:
        src = src_root / name / "SKILL.md"
        if not src.is_file():
            raise StudioError(f"missing kit skill {src}")
        dest = dest_root / f"prime-{name}" / "SKILL.md"
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dest)
        count += 1
    for name in SUPPORT_SKILLS:
        try:
            if _sync_support_skill(studio, kit, name, overwrite=True):
                count += 1
        except (InitError, OSError) as exc:
            raise StudioError(str(exc)) from exc
    return count


def _seed_missing_templates(studio: Path, kit: Path, pin: dict[str, Any]) -> None:
    templates = kit / "templates"
    memory = _resolve(studio, pin.get("memory") or "memory")
    app = _resolve(studio, pin.get("app_dir") or "app")
    if (templates / "ADR-0005-technology-stack.md").is_file():
        _copy_if_missing(templates / "ADR-0005-technology-stack.md", adr_path(memory))
    if (templates / "AGENTS.md").is_file():
        _copy_if_missing(templates / "AGENTS.md", studio / "AGENTS.md")
    if (templates / "CORRECTIONS.md").is_file():
        _copy_if_missing(templates / "CORRECTIONS.md", studio / "CORRECTIONS.md")
    gi = templates / "product.gitignore"
    if gi.is_file():
        _write_if_missing(app / ".gitignore", gi.read_text(encoding="utf-8"))
    ver = templates / "VERSION"
    if ver.is_file():
        _write_if_missing(app / "VERSION", ver.read_text(encoding="utf-8"))
    log = templates / "CHANGELOG.md"
    if log.is_file():
        _write_if_missing(app / "CHANGELOG.md", log.read_text(encoding="utf-8"))


def update_studio(
    studio: Path,
    *,
    kit: Path | None = None,
    telemetry: LoopTelemetry | None = None,
) -> UpdateResult:
    studio = resolve_studio(studio)
    pin_file = _pin_path(studio)
    if not pin_file.is_file():
        raise StudioError("no .prime/manifest.yaml — run al-prime init first")
    kit = (kit or kit_root()).resolve()
    pin = load_yaml(pin_file)
    if not pin:
        pin = {"version": 1}
    skills = _overwrite_skills(studio, kit)
    _seed_missing_templates(studio, kit, pin)
    pin["kit_version"] = __version__
    pin["kit_path"] = _kit_rel(studio, kit)
    dump_yaml(pin_file, pin)
    tel = telemetry or NoOpTelemetry()
    tel.execute_tool("kit.update", success=True, exit_code=0)
    return UpdateResult(studio=studio, skills=skills)


def _cli_path(studio: Path, raw: Any, default: str) -> str:
    if raw is None or str(raw).strip() == "":
        return default
    path = Path(str(raw))
    if not path.is_absolute():
        return str(path)
    try:
        return str(path.resolve().relative_to(studio.resolve()))
    except ValueError:
        return str(path.resolve())


def _commit_paths_include_memory(paths: list[Any]) -> bool:
    for raw in paths:
        parts = Path(str(raw).replace("\\", "/")).parts
        if "memory" in parts:
            return True
    return False


def _skill_named(studio: Path, name: str) -> bool:
    path = studio / ".cursor" / "skills" / f"prime-{name}" / "SKILL.md"
    if not path.is_file():
        return False
    return f"name: prime-{name}" in path.read_text(encoding="utf-8")


def doctor_next_command(
    studio: Path,
    pin: dict[str, Any] | None,
    state: dict[str, Any] | None,
    *,
    ok: bool,
) -> str:
    if not ok:
        return "al-prime update && al-prime doctor"
    pin = pin or {}
    state = state or {}
    now = state.get("now") or {}
    memory = _cli_path(studio, state.get("memory") or pin.get("memory"), "memory")
    brief = _cli_path(
        studio,
        state.get("brief_dir") or pin.get("brief_dir"),
        "brief",
    )
    app = _cli_path(studio, state.get("app_dir") or pin.get("app_dir"), "app")
    cmd = (
        f"al-prime next --memory {memory} --brief-dir {brief} --app-dir {app}"
    )
    if now.get("autonomous"):
        cmd += " --autonomous"
    return cmd


def doctor_studio(
    studio: Path,
    *,
    kit: Path | None = None,
    telemetry: LoopTelemetry | None = None,
) -> DoctorResult:
    studio = resolve_studio(studio)
    _ = kit  # accepted for CLI symmetry; health does not hash kit files
    lines: list[str] = []
    ok = True
    pin = load_yaml(_pin_path(studio)) if _pin_path(studio).is_file() else {}
    state: dict[str, Any] | None = None

    if not _pin_path(studio).is_file():
        lines.append("FAIL: missing .prime/manifest.yaml")
        ok = False
    else:
        pin_ver = str(pin.get("kit_version") or "")
        if pin_ver != __version__:
            lines.append(
                f"WARN: pin kit_version {pin_ver!r} != package {__version__!r}"
            )

    memory = _resolve(studio, (pin or {}).get("memory") or "memory")
    if not run_state_path(memory).is_file():
        lines.append("FAIL: missing memory/run-state.yaml")
        ok = False
    else:
        state = load_run_state(memory)
        git = state.get("git")
        if isinstance(git, dict) and git:
            paths = git.get("commit_paths") or []
            if _commit_paths_include_memory(list(paths) if isinstance(paths, list) else []):
                lines.append("FAIL: commit_paths include memory")
                ok = False
            app = _resolve(studio, (pin or {}).get("app_dir") or state.get("app_dir") or "app")
            root = git.get("root")
            if root and Path(str(root)).resolve() != app.resolve():
                lines.append(f"WARN: git.root {root} != studio app {app}")
        try:
            require_commands(memory)
        except ValueError as exc:
            lines.append(f"FAIL: {exc}")
            ok = False
        try:
            require_security_commands(memory)
        except ValueError as exc:
            lines.append(f"FAIL: {exc}")
            ok = False

    for name in SKILL_NAMES:
        if not _skill_named(studio, name):
            lines.append(f"FAIL: skill prime-{name} missing")
            ok = False
    for name in SUPPORT_SKILLS:
        if not (studio / ".cursor" / "skills" / name / "SKILL.md").is_file():
            lines.append(f"FAIL: skill {name} missing")
            ok = False

    next_cmd = doctor_next_command(studio, pin, state, ok=ok)
    lines.append(f"next: {next_cmd}")
    tel = telemetry or NoOpTelemetry()
    tel.execute_tool("kit.doctor", success=ok, exit_code=0 if ok else 1)
    tel.trace_evaluation("doctor", ok)
    return DoctorResult(ok=ok, lines=lines)
