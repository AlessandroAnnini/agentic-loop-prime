from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from agentic_loop_prime.adr_commands import SECURITY_KEYS, TEST_KEYS
from agentic_loop_prime.context import ProgramContext


@pytest.fixture(autouse=True)
def _clear_adr_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for key in TEST_KEYS + SECURITY_KEYS:
        monkeypatch.delenv(key, raising=False)


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def write_run_state(memory: Path, data: dict) -> None:
    _write(memory / "run-state.yaml", yaml.safe_dump(data, sort_keys=False))


@pytest.fixture
def slim_light_memory(tmp_path: Path) -> Path:
    """One light CLI feature. No ux.md / ui.md. Charter signed in run-state only."""
    memory = tmp_path / "memory"
    memory.mkdir()
    write_run_state(
        memory,
        {
            "version": 1,
            "program_state": "idle",
            "active_feature": "todo-cli",
            "charter_signed": True,
            "research_track": "none",
            "lock": None,
            "intent": None,
            "features": [
                {
                    "feature_id": "todo-cli",
                    "status": "pending",
                    "design_track": "light",
                    "surface": "cli",
                }
            ],
        },
    )
    _write(memory / "charter.md", "# Charter\n\nBuild a todo CLI.\n")
    _write(
        memory / "backlog.yaml",
        yaml.safe_dump(
            {
                "version": 1,
                "features": [
                    {
                        "id": "todo-cli",
                        "name": "Todo CLI",
                        "intent": "Track tasks from a terminal",
                        "surface": "cli",
                        "design_track": "light",
                    }
                ],
            },
            sort_keys=False,
        ),
    )
    _write(memory / "decisions.yaml", "version: 1\nitems: []\n")
    feat = memory / "features" / "todo-cli"
    _write(
        feat / "brief.md",
        "# Feature Brief: todo-cli\n\n**Status:** signed\n\nAcceptance: add and list tasks.\n",
    )
    _write(
        feat / "plan.md",
        "# Plan\n\n### Step 1 — Scaffold\n\n- [x] done\n",
    )
    _write(feat / "log.jsonl", '{"step": 1, "verification_pass": true}\n')
    _write(
        memory / "adr" / "ADR-0005-technology-stack.md",
        "\n".join(
            [
                "```bash",
                "export UNIT_TEST_CMD='python3 -c \"print(1)\"'",
                "export E2E_TEST_CMD='python3 -c \"print(2)\"'",
                "export SECURITY_SECRETS_CMD='python3 -c \"print(3)\"'",
                "export SECURITY_SCA_CMD=\"true\"",
                "export SECURITY_SAST_CMD=\"true\"",
                "```",
                "",
            ]
        ),
    )
    from agentic_loop_prime.adr_commands import (
        commands_fingerprint,
        require_commands,
        require_security_commands,
    )

    digest = "0123456789abcdef"
    harness_fp = commands_fingerprint(require_commands(memory))
    tools_fp = commands_fingerprint(require_security_commands(memory))
    checks = feat / "checks"
    _write(
        checks / "prove.yaml",
        f"tests_passed: true\napp_fingerprint: {digest}\n",
    )
    from agentic_loop_prime.security_report import passing_security_markdown

    _write(checks / "security.md", passing_security_markdown(digest, "todo-cli"))
    _write(checks / "judge.md", "**Verdict:** pass\n")
    _write(checks / "fingerprint.json", f'{{"digest": "{digest}"}}\n')
    _write(
        checks / "harness.json",
        (
            '{"exit_code": 0, "app_fingerprint": "%s", '
            '"commands_fingerprint": "%s"}\n' % (digest, harness_fp)
        ),
    )
    _write(
        checks / "tools.json",
        (
            '{"exit_code": 0, "app_fingerprint": "%s", '
            '"commands_fingerprint": "%s"}\n' % (digest, tools_fp)
        ),
    )
    return memory


@pytest.fixture
def light_context(slim_light_memory: Path) -> ProgramContext:
    return ProgramContext(memory_dir=slim_light_memory)
