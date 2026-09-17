---
name: prime-runner
description: >-
  Orchestrate an Agentic Loop Prime studio: read memory/run-state.yaml, run
  al-prime next --prompt, obey DELEGATE / HANDOFF / STOP. Trigger when starting
  or resuming a Prime session, or the user says run the loop or runner. Does
  not implement product code.
---

# Prime runner

You are the harness, not the implementer. Resume from `memory/run-state.yaml`, not from chat.

## Done when

- You printed the scheduler block or a clear STOP reason

## Do

```bash
al-prime next --memory memory --brief-dir brief --app-dir app --prompt
```

Obey the line:

- `DELEGATE <skill>`: load that Prime skill; do not write product code yourself. Follow Load / Write / Close in the Resume block. On design `ux` / `ui`, also load the support skill named there (`ux-architect` or `ui-direction`). On build with `surface: ui`, load `design-taste-frontend`.
- `HANDOFF verify`: switch to prime-verify; do not keep building
- `STOP`: stop. Do not invent the next step

After the delegated skill finishes, the operator (or that skill) runs:

```bash
al-prime done --memory memory --pass
# or
al-prime done --memory memory --fail
```

Then run `al-prime next --prompt` again.

`--autonomous` on `next` or `unattended` auto-signs charter and brief (sticky `now.autonomous`). After ship, `al-prime request-change --intent "..."` queues a new slice at design. `al-prime unattended` exit 3 means run one skill, `al-prime done`, then re-invoke `memory/now/continue.sh`.

A failed prove / security / judge check reopens a build step (`DELEGATE build` at `retry_step`). Two fails of the same action STOP `blocked_stagnation`. Refresh the studio with `al-prime update`; check health with `al-prime doctor`.

Optional traces: `OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4318` (Jaeger or Tempo OTLP HTTP). `next` and `done` share one `trace_id`. No `chat` or token spans.

## Do not

- Edit `app/`
- Sign the charter or brief unless the operator asked (or `--autonomous` is on)
- Skip `al-prime next`
