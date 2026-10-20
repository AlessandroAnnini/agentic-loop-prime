# Changelog

All notable changes to Agentic Loop Prime are documented in this file.

The format is based on Keep a Changelog.

## [Unreleased]

- Prime detects Cursor, VS Code, or Claude Code and runs that editor's adapter. A build frame with 30 or more files in `app/` runs a read-only helper first (`helper: explore`). The VS Code extension is not a runner; `scripts/agent-vscode.sh` uses the standalone `claude` CLI.
- CI runs `uv run pytest -q` on Python 3.12 via GitHub Actions.
- Agent boot is `AGENTS.md`. `CLAUDE.md` points at it. `GETTING_STARTED.md` is a stub for old links. Humans start at the README.
- Unattended `--agent-cmd` does the write; Prime closes the frame. `continue.sh` keeps `--agent-cmd`. `ALP_POLICY_FILE` is `memory/now/next-policy.json` (`app_writable` is true only for build).
- Verify `--pass` treats `app/` hash mismatch as `DONE fail` (lock cleared, reopen build). Missing fingerprint on prove stays `ERROR` (lock held).
- `scripts/agent-claude.sh` does not call `done`. With no `--agent-cmd`, exit 3 only when the editor is unknown.
- Skills install to `.agents/skills/` and `.claude/skills/`. Resume names the `.agents/` path. `init` seeds `CLAUDE.md`.
- Jaeger via `scripts/start-jaeger.sh` ships a light UI (`devtools/jaeger-ui.json`).

## [0.1.0] - 2026-09-01
