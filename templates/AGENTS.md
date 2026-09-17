# Agent guide (Agentic Loop Prime)

Command-first rules for every session. Stack commands live in
`memory/adr/ADR-0005-technology-stack.md`. Schedule lives in
`memory/run-state.yaml`. Obey `al-prime next`.

Studio: `memory/` + `brief/` sit beside the product tree `app/`. Open the
studio folder in Cursor.

## Hard rules

1. Brief folder (`brief_dir` in run-state) is read-only.
2. No application code under `app/` until the feature brief is signed.
3. Do not invent schedule order. Run `al-prime next --prompt` and obey DELEGATE / HANDOFF / STOP.
4. Maker ≠ checker: build may edit `app/`; verify (prove / security / judge) must not.
5. Close a frame with `al-prime done --pass` or `--fail`. `--pass` on verify runs the harness.
6. Product git is `app/` only. Never commit `memory/`, the kit, or `.cursor/`.
7. `al-prime next --autonomous` skips human charter/brief sign-off and `open_questions`. It does not skip verify.
8. `al-prime doctor` checks studio health, including ADR-0005 commands. `al-prime update` refreshes `prime-*` and support skills from the kit.

## Boot

```bash
al-prime next --memory memory --brief-dir brief --app-dir app --prompt
# After the skill session:
al-prime done --memory memory --pass
# or
al-prime done --memory memory --fail
```

Fill ADR-0005 UNIT/E2E/SECURITY_* before prove.

## Corrections

Before build or verify, read `memory/decisions.yaml` then `CORRECTIONS.md`
for the active feature.
