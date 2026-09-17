"""Security report parser: Medium disposition, open High, harness, no clobber."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from agentic_loop_prime.done import CloseError, close_frame
from agentic_loop_prime.paths import security_path, tools_path
from agentic_loop_prime.schedule import next_frame
from agentic_loop_prime.security_report import (
    passing_security_markdown,
    security_report_failure_reason,
    security_report_passed,
)
from agentic_loop_prime.tools import run_security_tools, security_gate

from test_tools import _adr, _light_studio, _to_prove, _write


def _digest(memory: Path, feature_id: str = "todo-cli") -> str:
    fp = memory / "features" / feature_id / "checks" / "fingerprint.json"
    return json.loads(fp.read_text(encoding="utf-8"))["digest"]


def _reach_security(tmp_path: Path) -> tuple[Path, Path, Path]:
    brief, memory, app = _light_studio(tmp_path)
    _adr(memory)
    next_frame(memory, brief_dir=brief, app_dir=app)
    close_frame(memory, passed=True)
    _to_prove(memory, brief, app)
    close_frame(memory, passed=True)
    sec = next_frame(memory, brief_dir=brief, app_dir=app)
    assert sec.substep == "security"
    return brief, memory, app


def test_security_pass_with_medium_disposition(tmp_path: Path) -> None:
    brief, memory, app = _reach_security(tmp_path)
    result = run_security_tools(memory, "todo-cli", app)
    assert result.passed is True
    digest = _digest(memory)
    _write(
        security_path(memory, "todo-cli"),
        f"""# Security

**Status:** pass
**App fingerprint:** {digest}

**Secrets clean:** yes

## SCA

| Finding | Severity | Package | Disposition |
|---------|----------|---------|-------------|
| overflow | Medium | hound | accepted |

## Notes

accepted with rationale: bounded by caller
""",
    )
    assert security_report_passed(memory, "todo-cli")
    assert security_gate(memory, "todo-cli")
    done = close_frame(memory, passed=True)
    assert done.passed is True


def test_security_fails_without_tools_harness(tmp_path: Path) -> None:
    brief, memory, app = _reach_security(tmp_path)
    digest = _digest(memory)
    _write(
        security_path(memory, "todo-cli"),
        passing_security_markdown(digest, "todo-cli"),
    )
    tools = tools_path(memory, "todo-cli")
    if tools.is_file():
        tools.unlink()
    reason = security_report_failure_reason(memory, "todo-cli")
    assert reason is not None
    assert "tools harness" in reason.lower()
    assert not security_report_passed(memory, "todo-cli")


def test_security_report_passed_requires_tools_harness(tmp_path: Path) -> None:
    brief, memory, app = _reach_security(tmp_path)
    digest = _digest(memory)
    _write(
        security_path(memory, "todo-cli"),
        passing_security_markdown(digest, "todo-cli"),
    )
    tools = tools_path(memory, "todo-cli")
    if tools.is_file():
        tools.unlink()
    assert not security_report_passed(memory, "todo-cli")
    run_security_tools(memory, "todo-cli", app)
    assert security_report_passed(memory, "todo-cli")


def test_security_fails_open_high(tmp_path: Path) -> None:
    brief, memory, app = _reach_security(tmp_path)
    run_security_tools(memory, "todo-cli", app)
    digest = _digest(memory)
    _write(
        security_path(memory, "todo-cli"),
        f"""# Security
**Status:** pass
**App fingerprint:** {digest}
**Secrets clean:** yes

| Finding | Severity | Path | Disposition |
|---------|----------|------|-------------|
| rce | High | x.rs | open |
""",
    )
    reason = security_report_failure_reason(memory, "todo-cli")
    assert reason is not None
    assert "high" in reason.lower()
    with pytest.raises(CloseError, match="fixed/false_positive"):
        close_frame(memory, passed=True)


def test_tools_pass_without_filled_report_fails_gate(tmp_path: Path) -> None:
    brief, memory, app = _reach_security(tmp_path)
    with pytest.raises(CloseError, match="status is not pass"):
        close_frame(memory, passed=True)
    assert tools_path(memory, "todo-cli").is_file()
    assert not security_gate(memory, "todo-cli")
    seeded = security_path(memory, "todo-cli").read_text(encoding="utf-8")
    assert "**Status:** draft" in seeded
    assert "**Secrets clean:** pending" in seeded
    assert "**Secrets clean:** yes" not in seeded


def test_tools_do_not_clobber_edited_report(tmp_path: Path) -> None:
    brief, memory, app = _reach_security(tmp_path)
    digest = _digest(memory)
    marker = "agent-triage-marker"
    _write(
        security_path(memory, "todo-cli"),
        passing_security_markdown(digest, "todo-cli") + f"\n\n{marker}\n",
    )
    first = run_security_tools(memory, "todo-cli", app)
    assert first.passed is True
    text = security_path(memory, "todo-cli").read_text(encoding="utf-8")
    assert marker in text
    second = run_security_tools(memory, "todo-cli", app)
    assert second.passed is True
    again = security_path(memory, "todo-cli").read_text(encoding="utf-8")
    assert marker in again
    assert close_frame(memory, passed=True).passed is True


def test_yaml_only_status_does_not_pass(tmp_path: Path) -> None:
    brief, memory, app = _reach_security(tmp_path)
    run_security_tools(memory, "todo-cli", app)
    digest = _digest(memory)
    _write(security_path(memory, "todo-cli"), f"status: pass\napp: {digest}\n")
    reason = security_report_failure_reason(memory, "todo-cli")
    assert reason == "status is not pass"


def test_medium_empty_disposition_with_path(tmp_path: Path) -> None:
    brief, memory, app = _reach_security(tmp_path)
    run_security_tools(memory, "todo-cli", app)
    digest = _digest(memory)
    _write(
        security_path(memory, "todo-cli"),
        f"""# Security
**Status:** pass
**App fingerprint:** {digest}
**Secrets clean:** yes

| Finding | Severity | Path | Disposition |
|---------|----------|------|-------------|
| overflow | Medium | src/foo.py | |
""",
    )
    reason = security_report_failure_reason(memory, "todo-cli")
    assert reason is not None
    assert "missing Disposition" in reason
    assert "src/foo.py" not in reason
