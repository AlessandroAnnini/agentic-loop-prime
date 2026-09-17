from __future__ import annotations

from pathlib import Path

from agentic_loop_prime.cli import main
from agentic_loop_prime.init import InitError, init_studio
from agentic_loop_prime.paths import load_yaml
from agentic_loop_prime.schedule import next_frame


def test_init_creates_slim_layout(tmp_path: Path) -> None:
    studio = tmp_path / "studio"
    result = init_studio(studio)
    assert result.skills == 8
    assert (studio / "memory" / "run-state.yaml").is_file()
    assert (studio / "memory" / "decisions.yaml").is_file()
    assert (studio / "memory" / "adr" / "ADR-0005-technology-stack.md").is_file()
    assert (studio / "brief").is_dir()
    assert (studio / "app").is_dir()
    assert (studio / "app" / ".git").exists()
    assert (studio / "app" / "VERSION").is_file()
    assert (studio / "app" / ".gitignore").is_file()
    assert (studio / "AGENTS.md").is_file()
    assert (studio / "CLAUDE.md").is_file()
    assert "AGENTS.md" in (studio / "CLAUDE.md").read_text(encoding="utf-8")
    assert (studio / "CORRECTIONS.md").is_file()
    assert (studio / ".prime" / "manifest.yaml").is_file()
    assert not (studio / "gf-program").exists()
    assert not (studio / "memory" / "locks").exists()
    state = load_yaml(studio / "memory" / "run-state.yaml")
    assert Path(state["brief_dir"]) == (studio / "brief").resolve()
    assert Path(state["app_dir"]) == (studio / "app").resolve()
    assert state["research_track"] == "none"
    assert state["git"]["root"] == str((studio / "app").resolve())
    assert state["git"]["auto_commit_steps"] is True
    assert state["git"]["auto_ship"] is True
    pin = load_yaml(studio / ".prime" / "manifest.yaml")
    assert pin["ide"] == "cursor"
    assert pin["skill_root"] == ".agents/skills"
    assert pin["skill_roots"] == [".agents/skills", ".claude/skills"]


def test_init_refuses_without_force(tmp_path: Path) -> None:
    studio = tmp_path / "studio"
    init_studio(studio)
    agents = (studio / "AGENTS.md").read_text(encoding="utf-8")
    try:
        init_studio(studio)
        raise AssertionError("expected InitError")
    except InitError:
        pass
    assert (studio / "AGENTS.md").read_text(encoding="utf-8") == agents


def test_init_force_fills_missing_only(tmp_path: Path) -> None:
    studio = tmp_path / "studio"
    init_studio(studio)
    adr = studio / "memory" / "adr" / "ADR-0005-technology-stack.md"
    adr.unlink()
    custom = "custom agents\n"
    (studio / "AGENTS.md").write_text(custom, encoding="utf-8")
    init_studio(studio, force=True)
    assert adr.is_file()
    assert (studio / "AGENTS.md").read_text(encoding="utf-8") == custom


def test_next_after_init_delegates_intake(tmp_path: Path) -> None:
    studio = tmp_path / "studio"
    init_studio(studio)
    action = next_frame(
        studio / "memory",
        brief_dir=studio / "brief",
        app_dir=studio / "app",
    )
    assert action.kind == "DELEGATE"
    assert action.skill == "intake"
    assert action.substep in ("charter", "research")


def test_skills_copied_with_al_prime_next(tmp_path: Path) -> None:
    studio = tmp_path / "studio"
    init_studio(studio)
    for root_name in (".agents/skills", ".claude/skills"):
        root = studio / Path(root_name)
        for name in ("runner", "intake", "design", "build", "verify"):
            path = root / f"prime-{name}" / "SKILL.md"
            assert path.is_file()
            text = path.read_text(encoding="utf-8")
            assert "al-prime next" in text
            assert f"name: prime-{name}" in text
        for name in ("ux-architect", "ui-direction", "design-taste-frontend"):
            path = root / name / "SKILL.md"
            assert path.is_file()
        assert (root / "ux-architect" / "assets" / "UX-BRIEF-template.md").is_file()
        assert (root / "design-taste-frontend" / "LICENSE").is_file()
    assert not (studio / ".cursor" / "skills").exists()


def test_cli_init(tmp_path: Path, capsys) -> None:
    studio = tmp_path / "studio"
    code = main(["init", str(studio)])
    assert code == 0
    out = capsys.readouterr().out
    assert "INIT studio=" in out
    assert "skills=8" in out
    code = main(["init", str(studio)])
    assert code == 1
