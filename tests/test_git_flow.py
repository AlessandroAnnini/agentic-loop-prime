from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from opentelemetry.trace import StatusCode

from agentic_loop_prime.done import close_frame
from agentic_loop_prime.git_flow import (
    current_branch,
    init_git_flow,
    is_git_repo,
    run_git,
)
from agentic_loop_prime.init import InitError, init_studio
from agentic_loop_prime.paths import load_yaml
from agentic_loop_prime.schedule import next_frame
from agentic_loop_prime.telemetry import OpenTelemetryListener
from test_tools import _adr, _light_studio, _to_prove, _write_passing_security


@pytest.fixture(autouse=True)
def _git_identity(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GIT_AUTHOR_NAME", "Prime")
    monkeypatch.setenv("GIT_AUTHOR_EMAIL", "agentic-loop-prime@local")
    monkeypatch.setenv("GIT_COMMITTER_NAME", "Prime")
    monkeypatch.setenv("GIT_COMMITTER_EMAIL", "agentic-loop-prime@local")


def _branches(repo: Path) -> set[str]:
    code, out = run_git(repo, "branch", "--list", "--format=%(refname:short)")
    assert code == 0
    return {line.strip() for line in out.splitlines() if line.strip()}


def _head_message(repo: Path) -> str:
    code, out = run_git(repo, "log", "-1", "--format=%s")
    assert code == 0
    return out


def _commit_files(repo: Path, rev: str = "HEAD") -> list[str]:
    code, out = run_git(repo, "show", "--name-only", "--pretty=format:", rev)
    assert code == 0
    return [line.strip() for line in out.splitlines() if line.strip()]


def _studio_with_git(tmp_path: Path) -> tuple[Path, Path, Path]:
    brief, memory, app = _light_studio(tmp_path)
    init_git_flow(app, gitignore=".venv/\n.env\n", version_text="0.0.0\n")
    data = load_yaml(memory / "run-state.yaml")
    data["app_dir"] = str(app.resolve())
    data["git"] = {
        "root": str(app.resolve()),
        "main_branch": "main",
        "develop_branch": "develop",
        "remote": "origin",
        "push": True,
        "auto_commit_steps": True,
        "auto_ship": True,
        "commit_paths": [".", "VERSION", "CHANGELOG.md"],
    }
    (memory / "run-state.yaml").write_text(
        yaml.safe_dump(data, sort_keys=False), encoding="utf-8"
    )
    return brief, memory, app


def test_init_makes_product_repo_outside_memory(tmp_path: Path) -> None:
    studio = tmp_path / "studio"
    init_studio(studio)
    app = studio / "app"
    assert is_git_repo(app)
    assert (app / "VERSION").read_text(encoding="utf-8").strip() == "0.0.0"
    assert (app / ".gitignore").is_file()
    assert (app / "CHANGELOG.md").is_file()
    assert _branches(app) >= {"main", "develop"}
    assert current_branch(app) == "develop"
    code, toplevel = run_git(app, "rev-parse", "--show-toplevel")
    assert code == 0
    assert Path(toplevel).resolve() == app.resolve()
    assert not (app / "memory").exists()
    tracked = _commit_files(app)
    assert all("memory" not in name for name in tracked)
    assert (studio / "memory").is_dir()
    assert (studio / "memory").resolve() != app.resolve()


def test_second_init_refuses_force_does_not_reinit_repo(tmp_path: Path) -> None:
    studio = tmp_path / "studio"
    init_studio(studio)
    app = studio / "app"
    code, first = run_git(app, "rev-parse", "HEAD")
    assert code == 0
    try:
        init_studio(studio)
        raise AssertionError("expected InitError")
    except InitError:
        pass
    init_studio(studio, force=True)
    code, again = run_git(app, "rev-parse", "HEAD")
    assert code == 0
    assert again == first
    assert current_branch(app) == "develop"


def test_delegate_build_opens_feature_branch(tmp_path: Path) -> None:
    brief, memory, app = _studio_with_git(tmp_path)
    framed = next_frame(memory, brief_dir=brief, app_dir=app)
    assert framed.kind == "DELEGATE"
    assert framed.skill == "build"
    assert current_branch(app) == "feature/todo-cli"
    assert "feature/todo-cli" in _branches(app)


def test_build_pass_commits_step_not_memory(tmp_path: Path) -> None:
    brief, memory, app = _studio_with_git(tmp_path)
    next_frame(memory, brief_dir=brief, app_dir=app)
    (app / "main.py").write_text("print('step 1')\n", encoding="utf-8")
    result = close_frame(memory, passed=True)
    assert result.passed is True
    assert "feat(todo-cli)" in _head_message(app)
    assert "step" in _head_message(app).lower() or "scaffolding" in _head_message(app)
    names = _commit_files(app)
    assert "main.py" in names
    assert all("memory" not in name for name in names)
    code, out = run_git(app, "log", "--oneline", "develop..HEAD")
    assert code == 0
    commits = [line for line in out.splitlines() if line.strip()]
    assert len(commits) == 1


def test_build_pass_without_repo_still_done(tmp_path: Path) -> None:
    brief, memory, app = _light_studio(tmp_path)
    assert not is_git_repo(app)
    next_frame(memory, brief_dir=brief, app_dir=app)
    result = close_frame(memory, passed=True)
    assert result.passed is True
    assert not is_git_repo(app)


def test_judge_pass_ships_to_develop(tmp_path: Path) -> None:
    brief, memory, app = _studio_with_git(tmp_path)
    _adr(memory)
    next_frame(memory, brief_dir=brief, app_dir=app)
    close_frame(memory, passed=True)
    prove = _to_prove(memory, brief, app)
    assert prove.substep == "prove"
    assert close_frame(memory, passed=True).passed is True
    sec = next_frame(memory, brief_dir=brief, app_dir=app)
    assert sec.substep == "security"
    _write_passing_security(memory)
    assert close_frame(memory, passed=True).passed is True
    judge = next_frame(memory, brief_dir=brief, app_dir=app)
    assert judge.substep == "judge"
    result = close_frame(memory, passed=True)
    assert result.passed is True
    assert current_branch(app) == "develop"
    assert (app / "VERSION").read_text(encoding="utf-8").strip() == "0.1.0"
    assert "feature/todo-cli" not in _branches(app)
    log = (app / "CHANGELOG.md").read_text(encoding="utf-8")
    assert "0.1.0" in log
    assert "todo-cli" in log


def test_build_pass_otel_git_commit_not_error(tmp_path: Path) -> None:
    brief, memory, app = _studio_with_git(tmp_path)
    next_frame(memory, brief_dir=brief, app_dir=app)
    (app / "main.py").write_text("print('otel')\n", encoding="utf-8")
    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    listener = OpenTelemetryListener(tracer=provider.get_tracer("test"))
    result = close_frame(memory, passed=True, telemetry=listener)
    assert result.passed is True
    spans = exporter.get_finished_spans()
    tools = [s for s in spans if s.name == "execute_tool"]
    names = [s.attributes["gen_ai.tool.name"] for s in tools]
    assert "git.commit" in names
    git_span = next(s for s in tools if s.attributes["gen_ai.tool.name"] == "git.commit")
    assert git_span.status.status_code != StatusCode.ERROR
    assert git_span.attributes["app.tool.success"] is True
    keys = set(git_span.attributes.keys())
    assert "git.command" not in keys
    assert "commit.message" not in keys
