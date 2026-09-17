from __future__ import annotations

import shutil
from pathlib import Path

import yaml
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from opentelemetry.trace import StatusCode

from agentic_loop_prime.cli import main
from agentic_loop_prime.init import InitError, init_studio
from agentic_loop_prime.paths import load_yaml
from agentic_loop_prime.studio import StudioError, doctor_studio, update_studio
from agentic_loop_prime.telemetry import OpenTelemetryListener


def _provider() -> tuple[TracerProvider, InMemorySpanExporter]:
    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    return provider, exporter


def test_update_overwrites_skill_keeps_operator_edits(tmp_path: Path) -> None:
    studio = tmp_path / "studio"
    init_studio(studio)
    skill = studio / ".agents" / "skills" / "prime-runner" / "SKILL.md"
    skill.write_text("edited runner\n", encoding="utf-8")
    state_text = (studio / "memory" / "run-state.yaml").read_text(encoding="utf-8")
    app_file = studio / "app" / "VERSION"
    app_text = app_file.read_text(encoding="utf-8")
    (studio / "app" / "notes.txt").write_text("operator\n", encoding="utf-8")

    result = update_studio(studio)
    assert result.skills == 8
    restored = skill.read_text(encoding="utf-8")
    assert restored != "edited runner\n"
    assert "name: prime-runner" in restored
    support = studio / ".agents" / "skills" / "ui-direction" / "SKILL.md"
    support.write_text("edited ui-direction\n", encoding="utf-8")
    update_studio(studio)
    assert "edited ui-direction" not in support.read_text(encoding="utf-8")
    assert "name: ui-direction" in support.read_text(encoding="utf-8")
    assert (studio / "memory" / "run-state.yaml").read_text(encoding="utf-8") == state_text
    assert app_file.read_text(encoding="utf-8") == app_text
    assert (studio / "app" / "notes.txt").read_text(encoding="utf-8") == "operator\n"


def test_update_migrates_old_pin(tmp_path: Path) -> None:
    studio = tmp_path / "studio"
    init_studio(studio)
    leftover = studio / ".cursor" / "skills" / "prime-runner" / "SKILL.md"
    leftover.parent.mkdir(parents=True)
    leftover.write_text("old cursor copy\n", encoding="utf-8")
    pin_path = studio / ".prime" / "manifest.yaml"
    pin = load_yaml(pin_path)
    pin.pop("skill_root", None)
    pin.pop("skill_roots", None)
    pin_path.write_text(yaml.safe_dump(pin, sort_keys=False), encoding="utf-8")
    shutil.rmtree(studio / ".agents")
    shutil.rmtree(studio / ".claude")
    (studio / "CLAUDE.md").unlink()
    result = update_studio(studio)
    assert result.skills == 8
    migrated = load_yaml(pin_path)
    assert migrated["skill_root"] == ".agents/skills"
    assert migrated["skill_roots"] == [".agents/skills", ".claude/skills"]
    assert (studio / ".agents" / "skills" / "prime-runner" / "SKILL.md").is_file()
    assert (studio / ".claude" / "skills" / "prime-runner" / "SKILL.md").is_file()
    assert leftover.read_text(encoding="utf-8") == "old cursor copy\n"
    assert (studio / "CLAUDE.md").is_file()


def test_update_does_not_require_force(tmp_path: Path) -> None:
    studio = tmp_path / "studio"
    init_studio(studio)
    try:
        init_studio(studio)
        raise AssertionError("expected InitError")
    except InitError:
        pass
    result = update_studio(studio)
    assert result.skills == 8


def test_update_without_pin_exits_error(tmp_path: Path) -> None:
    empty = tmp_path / "empty"
    empty.mkdir()
    try:
        update_studio(empty)
        raise AssertionError("expected StudioError")
    except StudioError:
        pass
    assert main(["update", "--studio", str(empty)]) == 1


def test_doctor_fresh_init(tmp_path: Path, capsys) -> None:
    studio = tmp_path / "studio"
    init_studio(studio)
    result = doctor_studio(studio)
    assert result.ok is True
    text = result.format_text()
    assert "next: al-prime next" in text
    code = main(["doctor", "--studio", str(studio)])
    assert code == 0
    out = capsys.readouterr().out
    assert "next: al-prime next" in out


def test_doctor_missing_adr_commands(tmp_path: Path) -> None:
    studio = tmp_path / "studio"
    init_studio(studio)
    adr = studio / "memory" / "adr" / "ADR-0005-technology-stack.md"
    adr.write_text("# ADR-0005\n\nNo exports.\n", encoding="utf-8")
    result = doctor_studio(studio)
    assert result.ok is False
    joined = "\n".join(result.lines)
    assert "FAIL:" in joined
    assert "UNIT_TEST_CMD" in joined
    assert "SECURITY_" in joined
    assert joined.count("FAIL:") >= 2


def test_doctor_missing_skill(tmp_path: Path) -> None:
    studio = tmp_path / "studio"
    init_studio(studio)
    (studio / ".agents" / "skills" / "prime-verify" / "SKILL.md").unlink()
    result = doctor_studio(studio)
    assert result.ok is False
    assert any("prime-verify" in line for line in result.lines)
    assert main(["doctor", "--studio", str(studio)]) == 1


def test_doctor_missing_support_skill(tmp_path: Path) -> None:
    studio = tmp_path / "studio"
    init_studio(studio)
    skill = studio / ".claude" / "skills" / "ux-architect" / "SKILL.md"
    skill.unlink()
    result = doctor_studio(studio)
    assert result.ok is False
    assert any("ux-architect" in line for line in result.lines)


def test_doctor_commit_paths_memory(tmp_path: Path) -> None:
    studio = tmp_path / "studio"
    init_studio(studio)
    state = load_yaml(studio / "memory" / "run-state.yaml")
    state["git"]["commit_paths"] = [".", "memory"]
    (studio / "memory" / "run-state.yaml").write_text(
        yaml.safe_dump(state, sort_keys=False),
        encoding="utf-8",
    )
    result = doctor_studio(studio)
    assert result.ok is False
    assert any("commit_paths include memory" in line for line in result.lines)
    assert result.lines[-1] == "next: al-prime update && al-prime doctor"


def test_doctor_otel_not_error(tmp_path: Path) -> None:
    studio = tmp_path / "studio"
    init_studio(studio)
    provider, exporter = _provider()
    listener = OpenTelemetryListener(tracer=provider.get_tracer("test"))
    listener.start_run()
    result = doctor_studio(studio, telemetry=listener)
    listener.finish_run("ok", error=False)
    assert result.ok is True
    spans = exporter.get_finished_spans()
    tools = [
        s
        for s in spans
        if s.name == "execute_tool" and s.attributes.get("gen_ai.tool.name") == "kit.doctor"
    ]
    assert tools
    assert tools[0].attributes["app.tool.success"] is True
    assert tools[0].status.status_code != StatusCode.ERROR
    evaluate = [
        s
        for s in spans
        if s.name == "goal.evaluate" and s.attributes.get("app.eval.name") == "doctor"
    ]
    assert evaluate
    assert evaluate[0].attributes["app.eval.passed"] is True
    assert evaluate[0].status.status_code != StatusCode.ERROR


def test_cli_update(tmp_path: Path, capsys) -> None:
    studio = tmp_path / "studio"
    init_studio(studio)
    code = main(["update", "--studio", str(studio)])
    assert code == 0
    out = capsys.readouterr().out
    assert "UPDATE studio=" in out
    assert "skills=8" in out
