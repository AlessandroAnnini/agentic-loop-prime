from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import yaml

from agentic_loop_prime.cli import main
from agentic_loop_prime.done import close_frame
from agentic_loop_prime.paths import load_yaml
from agentic_loop_prime.schedule import next_frame
from agentic_loop_prime.unattended import run_unattended, write_continue_sh


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_unattended_agent_needed_intake(tmp_path: Path) -> None:
    brief = tmp_path / "brief"
    brief.mkdir()
    memory = tmp_path / "memory"
    code = run_unattended(memory, brief_dir=brief)
    assert code == 3
    prompt = memory / "now" / "next-prompt.md"
    assert prompt.is_file()
    text = prompt.read_text(encoding="utf-8")
    assert "DELEGATE" in text
    assert "intake" in text
    assert (memory / "now" / "continue.sh").is_file()
    assert (memory / "now" / "next-action.json").is_file()
    policy = json.loads((memory / "now" / "next-policy.json").read_text(encoding="utf-8"))
    assert policy["skill"] == "intake"
    assert policy["app_writable"] is False
    assert "memory/**" in policy["writable"]


def test_unattended_autonomous_skips_charter_review(tmp_path: Path) -> None:
    brief = tmp_path / "brief"
    brief.mkdir()
    memory = tmp_path / "memory"
    memory.mkdir()
    _write(memory / "charter.md", "# Charter\n\nShip a todo CLI.\n")
    _write(
        memory / "backlog.yaml",
        "version: 1\nfeatures:\n  - id: todo-cli\n    name: Todo\n    design_track: light\n",
    )
    _write(
        memory / "run-state.yaml",
        yaml.safe_dump(
            {
                "version": 1,
                "program_state": "idle",
                "charter_signed": False,
                "research_track": "none",
                "lock": None,
                "loop": {"initial": 20, "remaining": 20},
                "features": [],
            },
            sort_keys=False,
        ),
    )
    code = run_unattended(memory, brief_dir=brief, autonomous=True)
    assert code == 3
    state = load_yaml(memory / "run-state.yaml")
    assert state.get("charter_signed") is True
    payload = json.loads((memory / "now" / "next-action.json").read_text(encoding="utf-8"))
    assert payload["kind"] == "DELEGATE"
    assert payload["reason"] != "charter_review"
    assert payload["skill"] in ("design", "intake")


def test_unattended_done_exits_zero(tmp_path: Path) -> None:
    memory = tmp_path / "memory"
    memory.mkdir()
    _write(
        memory / "run-state.yaml",
        yaml.safe_dump(
            {
                "version": 1,
                "program_state": "done",
                "lock": None,
                "loop": {"initial": 20, "remaining": 0},
                "features": [],
            },
            sort_keys=False,
        ),
    )
    code = run_unattended(memory)
    assert code == 0


def test_cli_unattended_exit_3(tmp_path: Path) -> None:
    brief = tmp_path / "brief"
    brief.mkdir()
    memory = tmp_path / "memory"
    code = main(
        [
            "unattended",
            "--memory",
            str(memory),
            "--brief-dir",
            str(brief),
        ]
    )
    assert code == 3


def _log_lines(memory: Path, feature_id: str) -> list[dict]:
    path = memory / "features" / feature_id / "log.jsonl"
    if not path.is_file():
        return []
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line
    ]


def _agent_script(tmp_path: Path, body: str) -> str:
    path = tmp_path / "fake_agent.py"
    path.write_text(body, encoding="utf-8")
    return f"{sys.executable} {path}"


def _intake_charter_agent() -> str:
    return """
import json
import os
from pathlib import Path

action = json.loads(Path(os.environ["ALP_ACTION_JSON"]).read_text(encoding="utf-8"))
memory = Path(os.environ["ALP_PROMPT_FILE"]).resolve().parent.parent
skill = action.get("skill") or ""
sub = action.get("substep") or ""
if skill == "intake" and sub in ("", "charter"):
    (memory / "charter.md").write_text("# Charter\\n\\nShip a todo CLI.\\n", encoding="utf-8")
"""


def _mutate_app_agent(app: Path) -> str:
    return f"""
from pathlib import Path
root = Path({str(app)!r})
root.mkdir(parents=True, exist_ok=True)
(root / "mutated.py").write_text("x = 1\\n", encoding="utf-8")
"""


def _light_build_studio(tmp_path: Path) -> tuple[Path, Path, Path]:
    brief = tmp_path / "brief"
    brief.mkdir()
    memory = tmp_path / "memory"
    memory.mkdir()
    app = tmp_path / "app"
    app.mkdir()
    _write(app / "main.py", "print('hi')\n")
    _write(
        memory / "run-state.yaml",
        yaml.safe_dump(
            {
                "version": 1,
                "program_state": "idle",
                "active_feature": "todo-cli",
                "charter_signed": True,
                "research_track": "none",
                "lock": None,
                "loop": {"initial": 20, "remaining": 20},
                "features": [
                    {
                        "feature_id": "todo-cli",
                        "status": "pending",
                        "design_track": "light",
                    }
                ],
            },
            sort_keys=False,
        ),
    )
    _write(memory / "charter.md", "# Charter\n\nTodo.\n")
    _write(
        memory / "backlog.yaml",
        "version: 1\nfeatures:\n  - id: todo-cli\n    design_track: light\n",
    )
    feat = memory / "features" / "todo-cli"
    _write(feat / "brief.md", "# Brief\n\n**Status:** signed\n")
    _write(feat / "plan.md", "### Step 1 — Scaffold\n\n- [ ] todo\n")
    return brief, memory, app


def _adr(memory: Path, *, unit: str = 'python3 -c "print(1)"') -> None:
    _write(
        memory / "adr" / "ADR-0005-technology-stack.md",
        "\n".join(
            [
                "```bash",
                f"export UNIT_TEST_CMD='{unit}'",
                'export E2E_TEST_CMD=\'python3 -c "print(2)"\'',
                'export SECURITY_SECRETS_CMD=\'python3 -c "print(3)"\'',
                'export SECURITY_SCA_CMD="true"',
                'export SECURITY_SAST_CMD="true"',
                "```",
                "",
            ]
        ),
    )


def test_unattended_intake_write_closes_and_frames_next(tmp_path: Path) -> None:
    brief = tmp_path / "brief"
    brief.mkdir()
    memory = tmp_path / "memory"
    cmd = _agent_script(tmp_path, _intake_charter_agent())
    code = run_unattended(
        memory,
        brief_dir=brief,
        autonomous=True,
        agent_cmd=cmd,
        max_turns=2,
    )
    assert code != 3
    state = load_yaml(memory / "run-state.yaml")
    assert state.get("lock") is None
    logs = _log_lines(memory, "program")
    assert logs
    assert logs[0]["verification_pass"] is True
    payload = json.loads((memory / "now" / "next-action.json").read_text(encoding="utf-8"))
    assert payload["reason"] != "transition_open"
    assert payload["kind"] == "DELEGATE"
    assert payload["skill"] == "intake"
    assert payload["substep"] == "backlog"


def test_unattended_intake_empty_write_is_done_fail(tmp_path: Path) -> None:
    brief = tmp_path / "brief"
    brief.mkdir()
    memory = tmp_path / "memory"
    code = run_unattended(
        memory,
        brief_dir=brief,
        agent_cmd="true",
        max_turns=1,
    )
    assert code != 3
    state = load_yaml(memory / "run-state.yaml")
    assert state.get("lock") is None
    logs = _log_lines(memory, "program")
    assert logs
    assert logs[-1]["verification_pass"] is False


def test_unattended_build_no_digest_change_fails(tmp_path: Path) -> None:
    brief, memory, app = _light_build_studio(tmp_path)
    code = run_unattended(
        memory,
        brief_dir=brief,
        app_dir=app,
        agent_cmd="true",
        max_turns=1,
    )
    assert code != 3
    state = load_yaml(memory / "run-state.yaml")
    assert state.get("lock") is None
    logs = _log_lines(memory, "todo-cli")
    assert logs
    assert logs[-1]["verification_pass"] is False
    assert logs[-1]["skill"] == "build"


def test_unattended_verify_mutate_fails_without_harness(tmp_path: Path) -> None:
    brief, memory, app = _light_build_studio(tmp_path)
    marker = memory / "features" / "todo-cli" / "checks" / "HARNESS_RAN"
    _adr(memory, unit=f"touch {marker}")
    framed = next_frame(memory, brief_dir=brief, app_dir=app)
    assert framed.skill == "build"
    close_frame(memory, passed=True)
    cmd = _agent_script(tmp_path, _mutate_app_agent(app))
    code = run_unattended(
        memory,
        brief_dir=brief,
        app_dir=app,
        agent_cmd=cmd,
        max_turns=2,
    )
    assert code != 3
    state = load_yaml(memory / "run-state.yaml")
    assert state.get("lock") is None
    assert not marker.is_file()
    prove = memory / "features" / "todo-cli" / "checks" / "prove.yaml"
    if prove.is_file():
        assert load_yaml(prove).get("tests_passed") is not True
    logs = _log_lines(memory, "todo-cli")
    verify_logs = [row for row in logs if row.get("skill") == "verify"]
    assert verify_logs
    assert verify_logs[-1]["verification_pass"] is False


def test_continue_sh_keeps_agent_cmd(tmp_path: Path) -> None:
    memory = tmp_path / "memory"
    memory.mkdir()
    brief = tmp_path / "brief"
    brief.mkdir()
    app = tmp_path / "app"
    app.mkdir()
    path = write_continue_sh(
        memory,
        brief_dir=brief,
        app_dir=app,
        autonomous=True,
        agent_cmd="bash scripts/agent-claude.sh",
    )
    text = path.read_text(encoding="utf-8")
    assert "--agent-cmd" in text
    assert "agent-claude.sh" in text
    assert "--autonomous" in text


def test_unattended_continue_sh_includes_agent_cmd(tmp_path: Path) -> None:
    brief = tmp_path / "brief"
    brief.mkdir()
    memory = tmp_path / "memory"
    run_unattended(
        memory,
        brief_dir=brief,
        agent_cmd="true",
        max_turns=1,
    )
    text = (memory / "now" / "continue.sh").read_text(encoding="utf-8")
    assert "--agent-cmd" in text
    assert "true" in text


def test_agent_claude_requires_claude_and_prompt(tmp_path: Path) -> None:
    script = Path(__file__).resolve().parents[1] / "scripts" / "agent-claude.sh"
    empty = tmp_path / "empty-bin"
    empty.mkdir()
    prompt = tmp_path / "prompt.md"
    prompt.write_text("do the skill\n", encoding="utf-8")
    env = {**os.environ, "PATH": str(empty), "ALP_PROMPT_FILE": str(prompt)}
    missing_bin = subprocess.run(
        ["/bin/bash", str(script)],
        env=env,
        capture_output=True,
        text=True,
    )
    assert missing_bin.returncode != 0
    assert "claude" in missing_bin.stderr.lower()
    stub = empty / "claude"
    stub.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    stub.chmod(0o755)
    no_prompt = subprocess.run(
        ["/bin/bash", str(script)],
        env={**os.environ, "PATH": str(empty)},
        capture_output=True,
        text=True,
    )
    assert no_prompt.returncode != 0
    assert "ALP_PROMPT_FILE" in no_prompt.stderr


def test_agent_claude_denies_app_when_not_writable(tmp_path: Path) -> None:
    script = Path(__file__).resolve().parents[1] / "scripts" / "agent-claude.sh"
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    log = tmp_path / "claude-args.txt"
    stub = bin_dir / "claude"
    stub.write_text(
        f"#!/bin/sh\nprintf '%s\\n' \"$@\" > {log}\n",
        encoding="utf-8",
    )
    stub.chmod(0o755)
    prompt = tmp_path / "prompt.md"
    prompt.write_text("do the skill\n", encoding="utf-8")
    policy = tmp_path / "policy.json"
    policy.write_text('{"app_writable": false}\n', encoding="utf-8")
    env = {
        **os.environ,
        "PATH": f"{bin_dir}:/bin:/usr/bin",
        "ALP_PROMPT_FILE": str(prompt),
        "ALP_POLICY_FILE": str(policy),
    }
    proc = subprocess.run(
        ["/bin/bash", str(script)],
        env=env,
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0
    args = log.read_text(encoding="utf-8")
    assert "-p" in args
    assert "Edit(app/**)" in args
