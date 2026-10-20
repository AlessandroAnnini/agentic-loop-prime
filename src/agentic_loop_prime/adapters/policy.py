"""Shared frame inputs. No editor flags."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

from agentic_loop_prime.turn import app_digest


@dataclass
class Frame:
    prompt: str
    helper: str
    helper_output: Path | None
    app_dir: Path | None
    app_writable: bool


def load_frame() -> Frame:
    prompt_path = os.environ.get("ALP_PROMPT_FILE") or ""
    if not prompt_path or not Path(prompt_path).is_file():
        raise FileNotFoundError("ALP_PROMPT_FILE is required")
    prompt = Path(prompt_path).read_text(encoding="utf-8")
    helper = "none"
    helper_output: Path | None = None
    app_dir: Path | None = None
    app_writable = True
    policy_path = os.environ.get("ALP_POLICY_FILE") or ""
    if policy_path and Path(policy_path).is_file():
        try:
            data = json.loads(Path(policy_path).read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise ValueError(f"ALP_POLICY_FILE is not JSON: {exc}") from exc
        if isinstance(data, dict):
            helper = str(data.get("helper") or "none")
            raw_out = str(data.get("helper_output") or "").strip()
            if raw_out:
                helper_output = Path(raw_out)
            raw_app = str(data.get("app_dir") or "").strip()
            if raw_app:
                app_dir = Path(raw_app)
            app_writable = bool(data.get("app_writable", True))
    return Frame(
        prompt=prompt,
        helper=helper,
        helper_output=helper_output,
        app_dir=app_dir,
        app_writable=app_writable,
    )


def helper_instructions(frame: Frame) -> str:
    target = frame.helper_output or Path("memory/now/explore.md")
    return (
        f"Write a short map of the product tree.\n"
        f"The only file you may create is {target}.\n"
        "Do not edit app/.\n"
        "Do not implement the plan step.\n"
        "Read-only.\n\n"
        + frame.prompt
    )


def run_frame(
    *,
    helper_cmd: list[str] | None,
    writer_cmd: list[str],
    frame: Frame,
) -> int:
    """Run the helper when Prime asked for one, then the writer."""
    if frame.helper == "explore":
        if not helper_cmd or frame.helper_output is None:
            print("ERROR: explore helper has no command or output path", file=sys.stderr)
            return 1
        before = app_digest(frame.app_dir)
        proc = subprocess.run(helper_cmd, capture_output=True, text=True)
        if proc.returncode != 0:
            if proc.stderr:
                sys.stderr.write(proc.stderr)
            if proc.stdout:
                sys.stdout.write(proc.stdout)
            return proc.returncode
        note = (proc.stdout or "").strip()
        out = frame.helper_output
        if note and (not out.is_file() or not out.read_text(encoding="utf-8").strip()):
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(note + "\n", encoding="utf-8")
        if not out.is_file() or not out.read_text(encoding="utf-8").strip():
            print(f"ERROR: helper did not write {out}", file=sys.stderr)
            return 1
        if app_digest(frame.app_dir) != before:
            print("ERROR: helper changed app/", file=sys.stderr)
            return 1
    writer = subprocess.run(writer_cmd)
    return int(writer.returncode)
