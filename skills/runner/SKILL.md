---
name: prime-runner
description: >-
  Orchestrate an Agentic Loop Prime studio: read memory/run-state.yaml, run
  al-prime next --prompt, obey DELEGATE / HANDOFF / STOP. Trigger when starting
  or resuming a Prime session, or the user says run the loop or runner. Does
  not implement product code.
---

# Prime runner

You are the harness, not the implementer. Resume from `memory/run-state.yaml`, not from chat. Session rules live in `AGENTS.md`.

## Done when

- You printed the scheduler block or a clear STOP reason

## Do

```bash
al-prime next --memory memory --brief-dir brief --app-dir app --prompt
```

Obey the line. After the delegated skill finishes, the operator (or that skill) closes with `al-prime done --pass` or `--fail`. Then `next --prompt` again.

## Do not

- Edit `app/`
- Skip `al-prime next`
- Invent schedule order
