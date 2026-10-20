---
name: prime-build
description: >-
  Implement one plan step in app/ after the feature brief is signed. Trigger
  when al-prime next DELEGATEs build. Close with al-prime done --pass
  (fingerprints app/) or --fail. Substep plan writes the plan and does not
  touch app/.
---

# Prime build

Maker. Brief must already be signed.

## Plan frame

When `next` delegates substep `plan`, write `memory/features/<id>/plan.md`.
Each `### Step N` has a checkbox whose text is the work, and a "Done when"
line for the implementer. The close accepts the step when that checkbox
text is more than the word `done`. Then:

```bash
al-prime done --memory memory --pass
```

That close does not edit `app/` and does not commit. A checkbox that says
only `done` is not a step.

## Step frame

When `next` delegates substep `N`:

1. Read `memory/features/<id>/brief.md` and `plan.md`
2. If the backlog `surface` is `ui`, load `.agents/skills/design-taste-frontend/SKILL.md` and follow `ux.md` / `ui.md`
3. Implement that step under `app/`
4. Close the frame:

```bash
al-prime done --memory memory --pass
```

`--pass` ticks that step's existing checkbox, writes `checks/fingerprint.json`
when `app_dir` is set, and commits that step on the product repo in `app/`.
It does not invent a step. `--fail` if the step did not land. Never commits
on fail.

## Do not

- Implement more than one step
- Run prove/security yourself (that is verify)
- Edit the brief folder
