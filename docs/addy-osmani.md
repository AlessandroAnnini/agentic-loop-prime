# What we took from Addy Osmani

Source: [Practical Loop Engineering](https://addyosmani.com/blog/practical-loop-engineering/) (June 2026), also republished as [Loop Engineering](https://www.oreilly.com/radar/loop-engineering/) on O'Reilly Radar. The July follow-up, *Own the Outer Loop*, is the second half of the same argument.

Osmani did not invent the practice. He named it and gave it a parts list. Steinberger: you should be designing loops that prompt your agents. Cherny: the job is to write loops. Osmani’s definition is the one we built against:

> Loop engineering is replacing yourself as the person who prompts the agent. You design the system that does it instead.

A loop is a recursive goal: define a purpose, iterate until a condition holds. Prime is that system for **new** software. `al-prime next` finds the work. A skill session does the work. `al-prime done --pass` checks it. `memory/` writes down what is done. The next `next` decides what is next.

## The five pieces, plus memory

Osmani’s bill of materials is five product primitives and one place to remember stuff. We took some of those as kit surface. We took others as discipline and implemented them in a different shape, because this process does not call a model.

| Osmani | What it is | What Prime did | Why |
|---|---|---|---|
| Automations | Discovery on a cadence so the loop is not a one-off | `next` / `unattended` / `--autonomous`. Not a morning cron. | We wanted a **goal** loop (`/goal`: keep going until a condition is true), not a heartbeat (`/loop`: re-run on a timer). Osmani treats both as automations. We picked the goal form. |
| Worktrees | Isolated checkouts so parallel agents do not collide | One `feature/<id>` branch on `app/`. Studio `memory/` sits outside that repo. | Isolation still matters. Our collision problem is kit files leaking into product git, not two agents editing the same tree at once. Parallel worktrees are out of scope. |
| Skills | `SKILL.md` so the agent does not re-guess the project | Eight skills: `prime-runner`, `prime-intake`, `prime-design`, `prime-build`, `prime-verify`, plus `ux-architect`, `ui-direction`, `design-taste-frontend` | This is how we repay **intent debt**. Conventions live in skills and ADR-0005, not in chat. |
| Plugins and connectors | MCP so the loop touches real tools | None as first-class kit surface. No Linear, Slack, or required remotes. | A loop that only sees the filesystem is smaller. We kept the harness local and honest rather than inventing connectors we do not run. |
| Subagents | Maker and checker are different agents | HANDOFF to `prime-verify`. Prove / security / judge must not edit `app/`. The harness, not the builder, stamps pass. | Osmani’s strongest structural claim. The model that wrote the code is too nice grading its own homework. |
| State (the sixth) | Markdown or a board outside the conversation | `memory/`: `run-state.yaml`, charter, backlog, feature logs, `checks/` | “The agent forgets; the repo doesn’t.” Without disk state, every session starts cold. |

## Discipline we kept, even when the primitive changed

The rest of this page is that reading, not a recap of Codex tabs.

**Goal and bounds.** Iterate until every backlog row is `live`, with `--loop-budget`. A scheduled “check CI every morning” loop is a different product.

**Act is one framed skill.** `next` prints one DELEGATE. The operator does not invent schedule order.

**Evaluate is not “I think I’m done.”** `done --pass` on verify runs UNIT/E2E, `SECURITY_*`, and the findings gate. A planted `tests_passed: true` does not advance. Osmani’s `/goal` uses a separate small model to decide done. We use files and process exits instead, because we do not own a model client.

**Independent verify.** Fingerprint on build `--pass`, then prove, security, judge. Each close also emits `goal.verify` with `app.verification.independent=true`.

**Stop on no progress.** Two fails of the same action is `STOP blocked_stagnation`. Unattended mistakes must not loop forever. Fail is an outcome (`goal_not_met`), not `StatusCode.ERROR`.

**Taste stays human.** Charter and brief sign-off are the default. `--autonomous` auto-signs those gates and may reopen design once. It does not skip verify. That is Osmani’s closing line in kit form: stay the engineer, not only the person who presses go.

## What we left on the table

Osmani’s essay is written for Codex and Claude Code as the runtime. Prime sits one floor **above** that runtime.

We did not take scheduled automations as the primary trigger. `unattended` can close after `--agent-cmd`. Without that flag it still writes `continue.sh` for one skill. It is not a Triage inbox on a timer.

We did not take parallel worktrees or agent teams. One feature, one branch, one open lock.

We did not take MCP connectors or PR creation. They are out of scope for this kit.

We did not take inner-loop spans (`chat`, tokens, DECIDING/ACTING). Inventing them would fake a model this process does not call. See [OpenTelemetry](opentelemetry.md).

We did take the warning half. Intent debt is why skills and ADR-0005 exist. Comprehension debt is why verify is a different session and why the brief is signed before `app/` changes. Cognitive surrender is why autonomous still cannot stamp `**Status:** pass` on a security report.

## How to read the two essays against this kit

*Loop Engineering* is the parts list: find work, hand it out, check it, write it down, decide next.

*Own the Outer Loop* splits the job. The inner loop (investigate, implement, verify inside a session) belongs to the agent. The outer loop (quality evidence, ship-or-block verdict, answerability) belongs to the human. Prime is the outer loop made mechanical. Cursor still owns the inner one.

If this page and the code disagree, the code wins.
