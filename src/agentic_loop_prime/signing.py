"""Auto-sign charter and brief when --autonomous is on."""

from __future__ import annotations

from pathlib import Path

from agentic_loop_prime.paths import SIGNED, brief_path, charter_path
from agentic_loop_prime.persist import load_run_state, save_run_state

STATUS_DRAFT = "**Status:** draft"


def mark_document_signed(text: str) -> str:
    if SIGNED.lower() in text.lower():
        return text
    if STATUS_DRAFT.lower() in text.lower():
        return text.replace("**Status:** draft", SIGNED, 1)
    if text.startswith("#"):
        lines = text.splitlines(keepends=True)
        insert = f"\n{SIGNED}\n"
        if len(lines) == 1:
            return lines[0].rstrip("\n") + "\n" + insert
        return lines[0] + insert + "".join(lines[1:])
    return SIGNED + "\n\n" + text


def auto_sign_charter(memory: Path) -> None:
    state = load_run_state(memory)
    state["charter_signed"] = True
    save_run_state(memory, state)
    path = charter_path(memory)
    if path.is_file():
        path.write_text(
            mark_document_signed(path.read_text(encoding="utf-8")),
            encoding="utf-8",
        )


def auto_sign_brief(memory: Path, feature_id: str) -> None:
    path = brief_path(memory, feature_id)
    if not path.is_file():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"# Feature Brief: {feature_id}\n\n{SIGNED}\n", encoding="utf-8")
        return
    path.write_text(
        mark_document_signed(path.read_text(encoding="utf-8")),
        encoding="utf-8",
    )
