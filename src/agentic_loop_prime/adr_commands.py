"""Parse ADR-0005 test and security commands (stack-agnostic exports)."""

from __future__ import annotations

import hashlib
import json
import os
import re
from pathlib import Path

from agentic_loop_prime.paths import adr_path

EXPORT_RE = re.compile(
    r"""export\s+(?P<key>UNIT_TEST_CMD|E2E_TEST_CMD|SECURITY_SECRETS_CMD|SECURITY_SCA_CMD|SECURITY_SAST_CMD)=(?P<q>['"])(?P<val>.*?)(?P=q)""",
    re.MULTILINE,
)

TEST_KEYS = ("UNIT_TEST_CMD", "E2E_TEST_CMD")
SECURITY_KEYS = (
    "SECURITY_SECRETS_CMD",
    "SECURITY_SCA_CMD",
    "SECURITY_SAST_CMD",
)
_ENV_PREFIX_RE = re.compile(
    r"""^[A-Za-z_][A-Za-z0-9_]*=(?:"[^"]*"|'[^']*'|\S+)\s+"""
)
_NOOP_FIRST = frozenset({"true", "/bin/true", "/usr/bin/true", ":", "echo"})


def _strip_env_prefixes(cmd: str) -> str:
    body = cmd.strip()
    while True:
        match = _ENV_PREFIX_RE.match(body)
        if not match:
            return body.strip()
        body = body[match.end() :]


def is_noop_cmd(cmd: str) -> bool:
    """True for true, /bin/true, :, bare echo, including after KEY=val prefixes."""
    body = _strip_env_prefixes(cmd or "")
    if not body:
        return True
    first = re.split(r"\s+", body, maxsplit=1)[0].strip("'\"")
    return first in _NOOP_FIRST


def _parse_exports(memory: Path, keys: tuple[str, ...]) -> dict[str, str]:
    cmds: dict[str, str] = {}
    for key in keys:
        val = (os.environ.get(key) or "").strip()
        if val:
            cmds[key] = val

    path = adr_path(memory)
    if path.is_file():
        text = path.read_text(encoding="utf-8")
        for match in EXPORT_RE.finditer(text):
            key = match.group("key")
            if key in keys and key not in cmds:
                cmds[key] = match.group("val").strip()
    return cmds


def parse_adr_commands(memory: Path) -> dict[str, str]:
    return _parse_exports(memory, TEST_KEYS)


def parse_security_commands(memory: Path) -> dict[str, str]:
    return _parse_exports(memory, SECURITY_KEYS)


def require_commands(memory: Path) -> list[tuple[str, str]]:
    """UNIT and E2E required; E2E must not be a no-op and must differ from UNIT."""
    cmds = parse_adr_commands(memory)
    missing = [key for key in TEST_KEYS if not (cmds.get(key) or "").strip()]
    if missing:
        raise ValueError(
            "missing test commands in environment or ADR-0005: "
            + ", ".join(missing)
            + f" (see {adr_path(memory)})"
        )
    unit = cmds["UNIT_TEST_CMD"].strip()
    e2e = cmds["E2E_TEST_CMD"].strip()
    if is_noop_cmd(e2e):
        raise ValueError(
            "E2E_TEST_CMD is a no-op (true, :, echo). Use a user-journey "
            f"command (see {adr_path(memory)})"
        )
    if unit == e2e:
        raise ValueError(
            "E2E_TEST_CMD must differ from UNIT_TEST_CMD "
            "(unit suite is not a user journey)"
        )
    return [("UNIT_TEST_CMD", unit), ("E2E_TEST_CMD", e2e)]


def require_security_commands(memory: Path) -> list[tuple[str, str]]:
    """All three SECURITY_* required; secrets command must not be a no-op."""
    cmds = parse_security_commands(memory)
    ordered: list[tuple[str, str]] = []
    missing: list[str] = []
    for key in SECURITY_KEYS:
        val = (cmds.get(key) or "").strip()
        if not val:
            missing.append(key)
        else:
            ordered.append((key, val))
    if missing:
        raise ValueError(
            "missing security commands in environment or ADR-0005: "
            + ", ".join(missing)
            + f" (see {adr_path(memory)})"
        )
    secrets = cmds.get("SECURITY_SECRETS_CMD", "").strip()
    if is_noop_cmd(secrets):
        raise ValueError(
            "SECURITY_SECRETS_CMD is a no-op (true, :, echo). Fail closed "
            f"if the scanner is missing (see {adr_path(memory)})"
        )
    return ordered


def commands_fingerprint(commands: list[tuple[str, str]]) -> str:
    payload = json.dumps(list(commands), separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def result_cache_fresh(
    result_path: Path,
    *,
    app_digest: str,
    cmd_fingerprint: str,
) -> bool:
    if not result_path.is_file():
        return False
    try:
        data = json.loads(result_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return False
    if "exit_code" not in data or int(data["exit_code"]) != 0:
        return False
    if str(data.get("app_fingerprint") or "") != app_digest:
        return False
    if str(data.get("commands_fingerprint") or "") != cmd_fingerprint:
        return False
    return True
