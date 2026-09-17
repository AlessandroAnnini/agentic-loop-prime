# Agent guide (Agentic Loop Prime)

Command-first rules. Schedule lives in `memory/run-state.yaml`. Stack commands
live in `memory/adr/ADR-0005-technology-stack.md`. Diagrams:
[docs/how-it-works.md](docs/how-it-works.md). If this file and the code
disagree, the code wins.

Studio: `memory/` + `brief/` sit beside the product tree `app/`. Open the
studio folder (Cursor, Claude Code, or VS Code Agent). Resume names
`.agents/skills/`. The same files are also under `.claude/skills/`.

## Running a studio

### Hard rules

1. Brief folder (`brief_dir` in run-state) is read-only.
2. No application code under `app/` until the feature brief is signed.
3. Do not invent schedule order. Run `al-prime next --prompt` and obey DELEGATE / HANDOFF / STOP.
4. Maker ≠ checker: build may edit `app/`; verify (prove / security / judge) must not.
5. Close a frame with `al-prime done --pass` or `--fail`. `--pass` on verify runs the harness. Isolation is a fingerprint fail: if verify changes `app/`, that is `DONE fail`, not a stuck lock.
6. Product git is `app/` only. Never commit `memory/`, the kit, `.agents/`, or `.claude/`.
7. `al-prime next --autonomous` skips human charter/brief sign-off and `open_questions`. It does not skip verify.
8. `al-prime doctor` checks studio health, including ADR-0005 commands. `al-prime update` refreshes `prime-*` and support skills from the kit.

### Boot

```bash
al-prime next --memory memory --brief-dir brief --app-dir app --prompt
# After the skill session:
al-prime done --memory memory --pass
# or
al-prime done --memory memory --fail
```

Obey the printed line:

- `DELEGATE <skill>`: load `.agents/skills/prime-<skill>/SKILL.md`. Follow Write and Close. On design `ux` / `ui`, also load the support skill in the Resume block. On build with `surface: ui`, load `design-taste-frontend`.
- `HANDOFF verify`: switch to `prime-verify`. Do not keep building.
- `STOP`: stop. Do not invent work. Sign or fix the named gate, then `next` again.

Fill ADR-0005 `UNIT_TEST_CMD`, `E2E_TEST_CMD`, and `SECURITY_*` before prove. Env exports override the ADR. Do not plant `tests_passed: true`. Do not stamp `**Status:** pass` on a draft security report.

`--agent-cmd` is the write. Prime closes. Empty `--agent-cmd` still exits 3 (`AGENT_NEEDED`).

```bash
al-prime unattended --memory memory --brief-dir brief --app-dir app \
  --autonomous --agent-cmd 'bash scripts/agent-claude.sh'
```

`--autonomous` skips sign-off. It does not replace `--agent-cmd`. Traces are optional: [docs/opentelemetry.md](docs/opentelemetry.md).

Before build or verify, read `memory/decisions.yaml` then `CORRECTIONS.md` for the active feature.

After ship:

```bash
al-prime request-change --memory memory --intent "Add export to CSV" --surface cli --bump patch
```

## Changing this harness

From the kit checkout:

```bash
uv sync --extra dev
uv run pytest -q
```

Skills live in `skills/`. `init` copies them to `.agents/skills/` and `.claude/skills/`. Do not invent a second scheduler. Humans start at [README.md](README.md).
