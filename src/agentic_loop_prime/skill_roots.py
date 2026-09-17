"""Where kit skills are installed in a studio."""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

CANONICAL_SKILL_ROOT = ".agents/skills"
DEFAULT_SKILL_ROOTS = (".agents/skills", ".claude/skills")

SKILL_NAMES = ("runner", "intake", "design", "build", "verify")
SUPPORT_SKILLS = ("ux-architect", "ui-direction", "design-taste-frontend")


class SkillSyncError(Exception):
    """Kit skill missing or could not be copied."""


def skill_folder_name(name: str) -> str:
    if name in SKILL_NAMES:
        return f"prime-{name}"
    return name


def skill_load_path(name: str) -> str:
    """Canonical Load path for a Resume block (posix, relative to studio)."""
    return f"{CANONICAL_SKILL_ROOT}/{skill_folder_name(name)}/SKILL.md"


def skill_load_line(name: str) -> str:
    return f"Load skill: {skill_load_path(name)}"


def pin_skill_fields() -> dict[str, Any]:
    return {
        "skill_root": CANONICAL_SKILL_ROOT,
        "skill_roots": list(DEFAULT_SKILL_ROOTS),
    }


def skill_roots_from_pin(pin: dict[str, Any] | None) -> list[str]:
    pin = pin or {}
    raw = pin.get("skill_roots")
    if isinstance(raw, list) and raw:
        return [str(item).replace("\\", "/").rstrip("/") for item in raw if str(item).strip()]
    return list(DEFAULT_SKILL_ROOTS)


def apply_pin_skill_fields(pin: dict[str, Any]) -> dict[str, Any]:
    """Backfill skill_root / skill_roots on an old pin. Mutates pin."""
    fields = pin_skill_fields()
    if not str(pin.get("skill_root") or "").strip():
        pin["skill_root"] = fields["skill_root"]
    roots = pin.get("skill_roots")
    if not isinstance(roots, list) or not roots:
        pin["skill_roots"] = fields["skill_roots"]
    return pin


def _sync_prime_skill(dest_root: Path, src: Path, folder: str, *, overwrite: bool) -> None:
    dest = dest_root / folder / "SKILL.md"
    if dest.exists() and not overwrite:
        return
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dest)


def _sync_support_skill(dest_root: Path, src: Path, name: str, *, overwrite: bool) -> None:
    dest = dest_root / name
    if dest.exists() and not overwrite:
        return
    if dest.exists():
        shutil.rmtree(dest)
    shutil.copytree(src, dest)


def sync_skills(studio: Path, kit: Path, *, overwrite: bool = False) -> int:
    """Copy unique skills into every default root. Returns 8, not 16."""
    src_root = kit / "skills"
    unique = 0
    for name in SKILL_NAMES:
        src = src_root / name / "SKILL.md"
        if not src.is_file():
            raise SkillSyncError(f"missing kit skill {src}")
        folder = f"prime-{name}"
        for root in DEFAULT_SKILL_ROOTS:
            _sync_prime_skill(studio / Path(root), src, folder, overwrite=overwrite)
        unique += 1
    for name in SUPPORT_SKILLS:
        src = src_root / name
        if not src.is_dir() or not (src / "SKILL.md").is_file():
            raise SkillSyncError(f"missing kit skill {src}")
        for root in DEFAULT_SKILL_ROOTS:
            _sync_support_skill(studio / Path(root), src, name, overwrite=overwrite)
        unique += 1
    return unique


def skill_named(studio: Path, name: str, roots: list[str] | None = None) -> bool:
    roots = roots if roots is not None else list(DEFAULT_SKILL_ROOTS)
    needle = f"name: prime-{name}"
    folder = f"prime-{name}"
    for root in roots:
        path = studio / Path(root) / folder / "SKILL.md"
        if not path.is_file():
            return False
        if needle not in path.read_text(encoding="utf-8"):
            return False
    return True


def support_skill_present(studio: Path, name: str, roots: list[str] | None = None) -> bool:
    roots = roots if roots is not None else list(DEFAULT_SKILL_ROOTS)
    for root in roots:
        if not (studio / Path(root) / name / "SKILL.md").is_file():
            return False
    return True
