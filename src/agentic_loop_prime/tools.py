"""Independent checkers: ADR tests, security tools, mechanical judge."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

from agentic_loop_prime.adr_commands import (
    commands_fingerprint,
    require_commands,
    require_security_commands,
    result_cache_fresh,
)
from agentic_loop_prime.fingerprint import (
    app_matches_fingerprint,
    baseline_digest,
)
from agentic_loop_prime.paths import (
    VERDICT_PASS,
    dump_yaml,
    harness_path,
    judge_path,
    load_yaml,
    prove_path,
    security_path,
    text_has,
    tools_path,
)
from agentic_loop_prime.telemetry import LoopTelemetry, NoOpTelemetry


class ToolPrepError(Exception):
    """Missing ADR, fingerprint, or app_dir. Lock should stay open."""


@dataclass
class ToolResult:
    passed: bool


def _load_json(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    return data if isinstance(data, dict) else None


def harness_ok(memory: Path, feature_id: str) -> bool:
    path = harness_path(memory, feature_id)
    data = _load_json(path)
    if not data:
        return False
    if "exit_code" not in data or int(data["exit_code"]) != 0:
        return False
    digest = baseline_digest(memory, feature_id)
    stored = str(data.get("app_fingerprint") or "")
    if not digest or stored != digest:
        return False
    try:
        expected = commands_fingerprint(require_commands(memory))
    except ValueError:
        return False
    return str(data.get("commands_fingerprint") or "") == expected


def security_tools_ok(memory: Path, feature_id: str) -> bool:
    path = tools_path(memory, feature_id)
    data = _load_json(path)
    if not data:
        return False
    if "exit_code" not in data or int(data["exit_code"]) != 0:
        return False
    digest = baseline_digest(memory, feature_id)
    stored = str(data.get("app_fingerprint") or "")
    if not digest or stored != digest:
        return False
    try:
        expected = commands_fingerprint(require_security_commands(memory))
    except ValueError:
        return False
    return str(data.get("commands_fingerprint") or "") == expected


def prove_gate(memory: Path, feature_id: str) -> bool:
    data = load_yaml(prove_path(memory, feature_id))
    if data.get("tests_passed") is not True:
        return False
    digest = baseline_digest(memory, feature_id)
    stored = str(data.get("app_fingerprint") or "")
    if digest and stored and stored != digest:
        return False
    return harness_ok(memory, feature_id)


def security_gate(memory: Path, feature_id: str) -> bool:
    from agentic_loop_prime.security_report import security_report_passed

    return security_report_passed(memory, feature_id)


def judge_gate(memory: Path, feature_id: str) -> bool:
    return text_has(judge_path(memory, feature_id), VERDICT_PASS)


def _require_app(ctx_app: Path | None) -> Path:
    if ctx_app is None:
        raise ToolPrepError("app_dir missing in run-state — pass --app-dir to next")
    return Path(ctx_app).resolve()


def _require_fingerprint(memory: Path, feature_id: str) -> str:
    digest = baseline_digest(memory, feature_id)
    if not digest:
        raise ToolPrepError(
            "missing app fingerprint — complete a passing build step first"
        )
    return digest


def _require_fresh_tree(memory: Path, feature_id: str, app_dir: Path) -> None:
    ok, msg = app_matches_fingerprint(memory, feature_id, app_dir)
    if not ok:
        raise ToolPrepError(msg)


def _run_commands(
    commands: list[tuple[str, str]],
    *,
    cwd: Path,
    telemetry: LoopTelemetry,
) -> tuple[int, list[dict[str, Any]]]:
    tmp_base = Path(tempfile.gettempdir()) / "al-prime-tools"
    tmp_base.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    env["TMPDIR"] = str(tmp_base)
    env["TMP"] = str(tmp_base)
    env["TEMP"] = str(tmp_base)
    env["BASETEMP"] = str(tmp_base)
    results: list[dict[str, Any]] = []
    overall = 0
    for name, cmd in commands:
        try:
            proc = subprocess.run(
                cmd,
                shell=True,
                cwd=str(cwd),
                env=env,
                capture_output=True,
                text=True,
            )
        except OSError as exc:
            telemetry.execute_tool(
                name,
                success=False,
                exit_code=127,
                operational_error=True,
                stderr_tail=str(exc)[-200:],
            )
            raise
        sys.stdout.write(proc.stdout or "")
        if proc.stderr:
            sys.stderr.write(proc.stderr)
        exit_code = proc.returncode
        tail = ""
        if exit_code != 0:
            tail = (proc.stderr or "")[-200:]
        telemetry.execute_tool(
            name,
            success=exit_code == 0,
            exit_code=exit_code,
            stderr_tail=tail,
        )
        results.append({"name": name, "command": cmd, "exit_code": exit_code})
        if exit_code != 0:
            overall = exit_code
    return overall, results


def _write_result(
    path: Path,
    *,
    feature_id: str,
    overall: int,
    results: list[dict[str, Any]],
    digest: str,
    cmd_fp: str,
) -> None:
    payload = {
        "feature_id": feature_id,
        "exit_code": overall,
        "commands": results,
        "app_fingerprint": digest,
        "commands_fingerprint": cmd_fp,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def run_adr_tests(
    memory: Path,
    feature_id: str,
    app_dir: Path | None,
    telemetry: LoopTelemetry | None = None,
) -> ToolResult:
    tel = telemetry or NoOpTelemetry()
    app = _require_app(app_dir)
    digest = _require_fingerprint(memory, feature_id)
    _require_fresh_tree(memory, feature_id, app)
    try:
        commands = require_commands(memory)
    except ValueError as exc:
        raise ToolPrepError(str(exc)) from exc
    cmd_fp = commands_fingerprint(commands)
    out = harness_path(memory, feature_id)
    if result_cache_fresh(out, app_digest=digest, cmd_fingerprint=cmd_fp):
        dump_yaml(
            prove_path(memory, feature_id),
            {"tests_passed": True, "app_fingerprint": digest},
        )
        tel.record_verification(True)
        return ToolResult(passed=True)
    overall, results = _run_commands(
        commands, cwd=app.parent, telemetry=tel
    )
    _write_result(
        out,
        feature_id=feature_id,
        overall=overall,
        results=results,
        digest=digest,
        cmd_fp=cmd_fp,
    )
    passed = overall == 0
    if passed:
        dump_yaml(
            prove_path(memory, feature_id),
            {"tests_passed": True, "app_fingerprint": digest},
        )
    tel.record_verification(passed)
    return ToolResult(passed=passed)


def run_security_tools(
    memory: Path,
    feature_id: str,
    app_dir: Path | None,
    telemetry: LoopTelemetry | None = None,
) -> ToolResult:
    tel = telemetry or NoOpTelemetry()
    app = _require_app(app_dir)
    digest = _require_fingerprint(memory, feature_id)
    _require_fresh_tree(memory, feature_id, app)
    try:
        commands = require_security_commands(memory)
    except ValueError as exc:
        raise ToolPrepError(str(exc)) from exc
    cmd_fp = commands_fingerprint(commands)
    out = tools_path(memory, feature_id)
    if result_cache_fresh(out, app_digest=digest, cmd_fingerprint=cmd_fp):
        _seed_security_md_if_missing(memory, feature_id, digest)
        tel.record_verification(True)
        return ToolResult(passed=True)
    overall, results = _run_commands(
        commands, cwd=app.parent, telemetry=tel
    )
    _write_result(
        out,
        feature_id=feature_id,
        overall=overall,
        results=results,
        digest=digest,
        cmd_fp=cmd_fp,
    )
    passed = overall == 0
    if passed:
        _seed_security_md_if_missing(memory, feature_id, digest)
    tel.record_verification(passed)
    return ToolResult(passed=passed)


def _seed_security_md_if_missing(
    memory: Path, feature_id: str, digest: str
) -> None:
    path = security_path(memory, feature_id)
    if path.is_file():
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    text = _security_report_template()
    text = text.replace("<feature-id>", feature_id)
    text = text.replace("<digest>", digest)
    text = text.replace("<date>", date.today().isoformat())
    path.write_text(text, encoding="utf-8")


def _security_report_template() -> str:
    from agentic_loop_prime.init import kit_root

    src = kit_root() / "templates" / "security-report.md"
    if src.is_file():
        return src.read_text(encoding="utf-8")
    return (
        "# Security Report: <feature-id>\n\n"
        "**Status:** draft\n"
        "**Feature id:** <feature-id>\n"
        "**Date:** <date>\n"
        "**App fingerprint:** <digest>\n"
        "\n"
        "**Secrets clean:** pending\n"
    )


def run_judge(
    memory: Path,
    feature_id: str,
    app_dir: Path | None,
    *,
    brief_signed: bool,
    plan_complete: bool,
    telemetry: LoopTelemetry | None = None,
) -> ToolResult:
    tel = telemetry or NoOpTelemetry()
    app = _require_app(app_dir)
    digest = baseline_digest(memory, feature_id)
    app_ok, app_msg = app_matches_fingerprint(memory, feature_id, app)
    checks = [
        ("1", "Feature brief signed", brief_signed),
        ("2", "All declared plan steps complete", plan_complete),
        (
            "3",
            "Harness ADR tests passed (bound to fingerprint)",
            prove_gate(memory, feature_id),
        ),
        (
            "4",
            "Security tools fingerprint-bound",
            security_gate(memory, feature_id),
        ),
        ("5", f"App fingerprint unchanged ({app_msg})", app_ok),
        ("6", "Fingerprint baseline present", bool(digest)),
    ]
    passed = all(ok for _, _, ok in checks)
    lines = [
        f"# Judge Report: {feature_id}",
        "",
        f"**Verdict:** {'pass' if passed else 'fail'}",
        f"**Feature id:** {feature_id}",
        f"**Date:** {date.today()}",
        f"**App fingerprint:** {digest or 'missing'}",
        "",
        "| # | Check | yes/no |",
        "|---|-------|--------|",
    ]
    for num, label, ok in checks:
        lines.append(f"| {num} | {label} | {'yes' if ok else 'no'} |")
    lines.append("")
    path = judge_path(memory, feature_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    tel.execute_tool("judge", success=passed, exit_code=0 if passed else 1)
    tel.record_verification(passed)
    return ToolResult(passed=passed)
