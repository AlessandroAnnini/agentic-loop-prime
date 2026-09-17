# Agentic Loop Prime

[![License: AGPL-3.0](https://img.shields.io/badge/license-AGPL--3.0-blue.svg)](LICENSE)
[![Python 3.12](https://img.shields.io/badge/python-3.12-3776AB.svg)](https://www.python.org/)

An outer loop that will not let the builder grade its own homework.

You put notes in a brief. Prime names **one** skill. Cursor does that skill. A file or a process exit decides whether the work counts. Then the next real step, or a stop. `al-prime` never calls a model.

```mermaid
flowchart LR
  notes["brief/"] --> nextCmd["al-prime next"]
  nextCmd --> skill["one Cursor skill"]
  skill --> doneCmd["al-prime done"]
  doneCmd --> gate{"gate"}
  gate -->|pass or fail| nextCmd
  gate -->|stuck| stop["STOP"]
```

## What it is

Prime is a **goal-loop harness** for building **new** software from a brief. The folder you open in Cursor is a *studio*: operator notes, run state, and the product tree sit side by side.

`al-prime` owns the outer schedule. It prints a Resume block (which skill to load, what to write, how to close) and records the outcome. Cursor owns the inner loop: plan, act, observe. The model forgets between sessions. `memory/` does not.

The pipeline is intake, design, build, then an independent verify. Build may edit `app/`. Prove, security, and judge must not. Product git is `app/` only. `memory/` stays beside that repo, never inside it.

A planted `tests_passed: true` does not advance the program. Two fails of the same action stop as `blocked_stagnation`.

## What it is not

Prime is not an agent and not a model wrapper. It does not write your product, talk to an API, or invent the next step. Something that can load a `SKILL.md` and run a CLI does that work. Today that something is Cursor.

It is not a tool for reshaping a large existing codebase. You start from notes and an empty `app/`.

It is not a hosted product and not a timer that pokes CI every morning. One program, one feature at a time, until every backlog row is `live` or the loop stops.

## Five-minute try

You need Python 3.12 and [uv](https://docs.astral.sh/uv/). Cursor is the runtime the skills are written for.

```bash
git clone https://github.com/AlessandroAnnini/agentic-loop-prime.git
cd agentic-loop-prime
uv sync --extra dev
uv run al-prime --version
```

Seed a studio in this directory (or pass another path to `init`):

```bash
uv run al-prime init .
printf '%s\n' \
  'Build a tiny todo CLI in Python.' \
  'Add a task, list tasks, and mark one done.' \
  > brief/notes.md
uv run al-prime next --memory memory --brief-dir brief --app-dir app --prompt
```

You will not finish a product in five minutes. You will see the first frame.

## What you will see

`next --prompt` prints a line such as `DELEGATE intake program substep=charter`, then a Resume block: Load, Write, Close. Open that skill under `.cursor/skills/`, do only that write, and close the frame:

```bash
uv run al-prime done --memory memory --pass
```

The next `next` is the next real step, not a guess. A second `next` while a lock is open is `STOP transition_open`.

When the charter or a feature brief needs a human, you get `STOP` with a named gate. Sign the file (`**Status:** signed` on the brief, or `charter_signed` in run-state), then `next` again. `--autonomous` auto-signs those gates. It does not skip verify.

Before prove, fill `memory/adr/ADR-0005-technology-stack.md` with `UNIT_TEST_CMD`, `E2E_TEST_CMD`, and `SECURITY_*`. Env exports override the ADR.

`done --pass` on verify runs those commands. Prove stamps `prove.yaml` only on exit 0 with a matching `app/` fingerprint. Security runs `SECURITY_*` and gates the findings report. The harness never writes `**Status:** pass` for you. A failed check reopens a build step.

## Studio

```text
my-studio/
├── memory/          run-state, charter, backlog, ADR-0005, feature logs
├── brief/           your notes (read-only to the agent)
├── app/             product tree and git root
├── AGENTS.md
├── CORRECTIONS.md
├── .prime/manifest.yaml
└── .cursor/skills/  prime-* skills plus UX/UI support
```

`al-prime init` creates that layout. `al-prime doctor` checks the pin, run-state, skills, commit paths, and ADR commands. `al-prime update` refreshes skills from the kit without wiping `memory/` or `app/` source.

After a feature ships, `al-prime request-change --intent "..."` queues a new slice at design.

## Commands

| Command | Role |
|---|---|
| `init` | Create a studio |
| `next` | Frame the next DELEGATE, HANDOFF, or STOP |
| `done` | Close the open frame |
| `request-change` | Queue a new slice after ship |
| `unattended` | Run one frame and print the continue path |
| `update` | Refresh skills and the kit pin |
| `doctor` | Report studio health |

If you are the agent in the session, the boot protocol is [GETTING_STARTED.md](GETTING_STARTED.md). How the states and gates fit together, with diagrams: [docs/how-it-works.md](docs/how-it-works.md).

## Tests

```bash
uv run pytest -q
```

## Observability

Traces are optional. The loop runs without a collector.

When `OTEL_EXPORTER_OTLP_ENDPOINT` is set (for example `http://localhost:4318`), Prime exports the spans it already records over OTLP HTTP. `next` and `done` share one W3C `trace_id`. There are no `chat` or token spans. This process does not call a model.

```bash
export OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4318
uv run al-prime next --memory memory --brief-dir brief --app-dir app
```

A local Jaeger all-in-one is `bash scripts/start-jaeger.sh`. What we emit and how to read it: [docs/opentelemetry.md](docs/opentelemetry.md).

## Design notes

The control plane is a `python-statemachine` StateChart. The shape of the loop (one framed skill, independent verify, stop on no progress, state on disk) follows the parts list in Addy Osmani's *Loop Engineering*. What we took, and what we left: [docs/addy-osmani.md](docs/addy-osmani.md).

If a page and the code disagree, the code wins.

## License

Copyright Alessandro Annini. Licensed under [AGPL-3.0](LICENSE). If you run a modified version as a network service, you must offer the source. Changes are listed in [CHANGELOG.md](CHANGELOG.md).
