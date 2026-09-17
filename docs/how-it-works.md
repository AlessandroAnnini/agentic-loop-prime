# How Prime works

Prime is an **outer** goal loop. It names one skill, waits for that session to close, then advances only if a mechanical gate agrees. Cursor (or another agent) runs the **inner** loop: plan, act, observe. `al-prime` never calls a model.

The goal is every backlog feature `live`, or a STOP. Not a heartbeat. Not a cron.

## Two loops

```mermaid
flowchart LR
  subgraph outer ["Outer loop: al-prime"]
    N["next"] --> D["DELEGATE / HANDOFF / STOP"]
    D --> S["skill session"]
    S --> C["done --pass or --fail"]
    C --> G{"gate"}
    G -->|pass| N
    G -->|fail| N
  end

  subgraph inner ["Inner loop: agent"]
    P["plan"] --> A["act"]
    A --> O["observe"]
    O --> P
  end

  D -.->|Resume block| P
  O -.->|operator closes| C
```

`next --prompt` prints a Resume block: which `prime-*` skill to load, what to write, and the close command. The operator (or that skill) runs `done`. A second `next` while a lock is open is `STOP transition_open`.

## Studio

The folder you open (Cursor, Claude Code, or VS Code Agent) is the studio. Three trees sit side by side.

```mermaid
flowchart TB
  subgraph studio ["Studio"]
    brief["brief/  operator notes, read-only"]
    memory["memory/  run-state, charter, backlog, checks"]
    app["app/  product source and git"]
    skills[".agents/skills/  prime-* plus UX/UI"]
  end

  brief --> memory
  memory --> skills
  skills --> app
```

`memory/` is the spine. The model forgets between sessions. The files do not. Product history is `app/` only. Never commit `memory/`, the kit, `.agents/`, or `.claude/`. The same skills are also copied to `.claude/skills/` for Claude Code. Resume names `.agents/skills/`.

## Pipeline

Intake runs once. Each feature then walks design, sign-off, build, an independent verify, and ship. The next feature starts at design, not at the brief folder.

```mermaid
flowchart TD
  briefFolder["brief/"] --> intake

  subgraph intake ["Intake, once"]
    research["research  if light or deep"]
    charter["charter"]
    backlog["backlog"]
    research --> charter --> backlog
  end

  backlog --> charterSign["charter sign-off"]
  charterSign --> track{"design_track"}

  subgraph design ["Design"]
    ux["ux"]
    ui["ui"]
    fbrief["feature brief"]
    ux --> ui --> fbrief
  end

  track -->|standard| ux
  track -->|light| fbrief
  fbrief --> briefSign["brief sign-off"]
  briefSign --> branch["feature/id from develop"]
  branch --> build["build: one plan step"]
  build --> handoff["HANDOFF verify"]

  subgraph verify ["Verify, checker"]
    prove["prove"]
    security["security"]
    judge["judge"]
    prove --> security --> judge
  end

  handoff --> prove
  judge --> ok{"checks pass?"}
  ok -->|no| reopen["reopen that plan step"]
  reopen --> build
  ok -->|yes| ship["merge, VERSION, CHANGELOG"]
  ship --> more{"more features?"}
  more -->|yes| design
  more -->|no| done["program done"]
```

Light track writes `brief.md` only. Standard track writes `ux.md`, then `ui.md`, then the brief. Prime has no functional or technical design files.

Build may edit `app/`. Prove, security, and judge must not.

## Frame and close

One `next` is one frame. The StateChart picks the coarse state. Substeps stay out of the machine.

```mermaid
stateDiagram-v2
  [*] --> idle
  idle --> intake
  intake --> charter_review
  charter_review --> scoping
  scoping --> feature_pipeline
  feature_pipeline --> done

  state feature_pipeline {
    [*] --> pending
    pending --> designing
    designing --> brief_review
    brief_review --> building
    building --> verifying
    verifying --> security
    security --> live
    verifying --> blocked_retry
    security --> blocked_retry
    blocked_retry --> building
    live --> pending
  }
```

`done --pass` on build hashes `app/` into `checks/fingerprint.json`. On prove it runs ADR `UNIT_TEST_CMD` and `E2E_TEST_CMD`. On security it runs `SECURITY_*` and then the findings-table gate. On judge it writes a checklist, merges to `develop`, and bumps `VERSION`. `--fail` logs only. Neither outcome is a telemetry error by itself.

Two fails of the same `{skill}:{substep}` become `STOP blocked_stagnation`. `--autonomous` may reopen design once. It still does not skip verify.

## Commands in the loop

```mermaid
flowchart LR
  init["init"] --> next1["next --prompt"]
  next1 --> skill["load skill, write artifact"]
  skill --> doneCmd["done --pass"]
  doneCmd --> next2["next"]
  next2 --> next1
  next2 --> stop["STOP"]
  stop --> human["sign, fill ADR, or fix"]
  human --> next1
```

`doctor` checks the studio. `update` refreshes skills from the kit. `request-change` queues a new slice after ship. `unattended` without `--agent-cmd` writes `memory/now/` and exits 3 so you can run one skill, `done`, and `continue.sh`. With `--agent-cmd`, the command writes and Prime closes. Verify drift versus the build fingerprint is `DONE fail`, not a stuck lock.

## Where to go next

- [Addy Osmani](addy-osmani.md): why the loop is shaped this way
- [OpenTelemetry](opentelemetry.md): what a frame looks like as traces
