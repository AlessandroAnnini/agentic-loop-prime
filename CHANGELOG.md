# Changelog

All notable changes to Agentic Loop Prime are documented in this file.

The format is based on Keep a Changelog.

## [Unreleased]

- Agent boot is `AGENTS.md`. `CLAUDE.md` points at it. `GETTING_STARTED.md` is a stub for old links. Humans start at the README.
- Unattended `--agent-cmd` does the write; Prime closes the frame. `continue.sh` keeps `--agent-cmd`. `ALP_POLICY_FILE` is `memory/now/next-policy.json` (`app_writable` is true only for build).
- Verify `--pass` treats `app/` hash mismatch as `DONE fail` (lock cleared, reopen build). Missing fingerprint on prove stays `ERROR` (lock held).
- `scripts/agent-claude.sh` runs `claude -p` and does not call `done`. Empty `--agent-cmd` still exits `AGENT_NEEDED`.
- Skills install to `.agents/skills/` and `.claude/skills/`. Resume names the `.agents/` path. `init` seeds `CLAUDE.md`.
- Jaeger via `scripts/start-jaeger.sh` ships a light UI (`devtools/jaeger-ui.json`).

## [0.1.0] - 2026-09-01
