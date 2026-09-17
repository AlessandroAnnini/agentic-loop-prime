# Getting started (for the agent)

You are operating **Agentic Loop Prime**. You do not invent schedule order. You start traces, init the studio if needed, run `al-prime next --prompt`, obey DELEGATE / HANDOFF / STOP, then close with `done`.

This page is the boot protocol. Lesson and diagrams: [docs/how-it-works.md](docs/how-it-works.md). If this file and the code disagree, the code wins.

**CLI:** `al-prime` (run as `uv run al-prime` from this kit). **Memory:** `memory/`. **Product git:** `app/` only.

---

## Hard rules

1. `brief/` is read-only.
2. Do not write `app/` until the feature brief is signed.
3. Do not invent the next step. Run `next --prompt` and obey the Resume block (Load / Write / Close).
4. Build may edit `app/`. Prove, security, and judge must not.
5. Close every open lock with `done --pass` or `done --fail`. A second `next` while locked is `STOP transition_open`.
6. Never commit `memory/`, this kit, or `.cursor/`.
7. `--autonomous` skips charter/brief sign-off. It does not skip verify.
8. Keep `OTEL_EXPORTER_OTLP_ENDPOINT` set in every shell that runs `al-prime` so `next` and `done` share one `trace_id`.

---

## Layout (studio)

Open the studio folder in Cursor.

```text
my-studio/                 ← open this folder
├── memory/                run-state, charter, backlog, ADR-0005, checks
├── brief/                 operator notes (read-only)
├── app/                   PRODUCT git (source, VERSION, CHANGELOG)
├── AGENTS.md
├── CORRECTIONS.md
├── .prime/manifest.yaml
└── .cursor/skills/        prime-* plus UX/UI support
```

The kit (`agentic-loop-prime/`) can be the studio (`init .` from this directory) or sit beside it. Product history is `app/` only.

---

## Step 1. Start the OpenTelemetry endpoint

Prime exports OTLP HTTP only when an endpoint is set. Start a collector **before** `init` / `next` / `done` so every frame is recorded. There are no `chat` or token spans. This process does not call a model.

```bash
bash scripts/start-jaeger.sh
```

That starts Jaeger all-in-one with Prime's UI config so the UI is **light** (the theme toggle is off; OS dark mode is ignored). UI: `http://localhost:16686` (service `agentic-loop-prime`).

If a collector is already listening on `4318`, skip the container. If `4318` is busy, stop the old one or point the env at the collector you already have.

Keep this export in the same shell (and every later shell) that runs `al-prime`:

```bash
export OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4318
```

`OTEL_EXPORTER_OTLP_TRACES_ENDPOINT` also works. `OTEL_SDK_DISABLED=1` turns export off. Span names and how to read them: [docs/opentelemetry.md](docs/opentelemetry.md).

---

## Step 2. Install the kit

From this directory (`agentic-loop-prime/`):

```bash
uv sync --extra dev
uv run al-prime --version
```

Python 3.12.

---

## Step 3. `al-prime init`

Studio in this directory:

```bash
uv run al-prime init .
```

Or a folder you will open as the studio:

```bash
uv run al-prime init /path/to/my-studio
cd /path/to/my-studio
```

Init seeds `memory/`, `brief/`, `app/` (git-flow `main` + `develop` when `app/` is not already a repo), `AGENTS.md`, `CORRECTIONS.md`, `.prime/manifest.yaml`, and eight Cursor skills.

Reload the Cursor window if new skills do not appear.

```bash
uv run al-prime doctor --studio .
uv run al-prime update --studio .
```

Fill `memory/adr/ADR-0005-technology-stack.md` with `UNIT_TEST_CMD`, `E2E_TEST_CMD`, and `SECURITY_*` before prove. Env exports override the ADR. Do not pre-seed `memory/research/LANDSCAPE.md`.

`doctor` fails closed on a missing pin, run-state, skill, `commit_paths` that include `memory`, or missing/invalid ADR commands. Last line is the next command to run.

---

## Step 4. Brief + one frame

Put operator notes in `brief/`. Then take one frame:

```bash
uv run al-prime next --memory memory --brief-dir brief --app-dir app --prompt
```

Obey the printed line:

- `DELEGATE <skill>`: load `.cursor/skills/prime-<skill>/SKILL.md`. Follow Write and Close. On design `ux` / `ui`, also load the support skill in the Resume block. On build with `surface: ui`, load `design-taste-frontend`.
- `HANDOFF verify`: switch to `prime-verify`. Do not keep building.
- `STOP`: stop. Do not invent work. Sign or fix the named gate, then `next` again.

After the skill session:

```bash
uv run al-prime done --memory memory --pass
# or
uv run al-prime done --memory memory --fail
```

Then `next --prompt` again. `--pass` on verify runs the harness. Do not plant `tests_passed: true` or stamp `**Status:** pass` on a draft security report.

Autonomous (skips sign-off and `open_questions`, not verify):

```bash
uv run al-prime next --memory memory --brief-dir brief --app-dir app --prompt --autonomous
```

Multi-turn until STOP or AGENT_NEEDED:

```bash
uv run al-prime unattended --memory memory --brief-dir brief --app-dir app --loop-budget 20
```

Exit `3` means run one skill, `done`, then `memory/now/continue.sh`.

When `STOP charter_review` or `STOP brief_review` (non-autonomous): the human signs the charter or `memory/features/<id>/brief.md` (`**Status:** signed`). Then `next` again. There is no separate resume verb.

### After the program is done

```bash
uv run al-prime request-change --memory memory --intent "Add export to CSV" --surface cli --bump patch
```

That queues a new slice at design. `--feature-id` reopens an existing feature (deletes brief/ux/ui, unchecks plan).

---

## Confirm traces

After at least one `next` (and `done` if you closed a frame), open `http://localhost:16686`, search service `agentic-loop-prime`. You should see `invoke_agent`. A prove `--pass` adds `execute_tool` children for `UNIT_TEST_CMD` and `E2E_TEST_CMD`. `next` and `done` share one `trace_id` when the endpoint was set in both processes.

If the UI is empty: the collector is down, the export was missing in that shell, or `OTEL_SDK_DISABLED` is set. The loop still ran; you just have no export.

---

## Verify the harness

```bash
uv run pytest -q
```
