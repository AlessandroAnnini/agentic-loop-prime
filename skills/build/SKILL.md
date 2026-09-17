---
name: prime-build
description: >-
  Implement one plan step in app/ after the feature brief is signed. Trigger
  when al-prime next DELEGATEs build. Close with al-prime done --pass
  (fingerprints app/) or --fail.
---

# Prime build

Maker. One `### Step N` only. Brief must already be signed.

1. Read `memory/features/<id>/brief.md` and `plan.md`
2. If the backlog `surface` is `ui`, load `.cursor/skills/design-taste-frontend/SKILL.md` and follow `ux.md` / `ui.md`
3. Implement that step under `app/`
4. Close the frame:

```bash
al-prime done --memory memory --pass
```

`--pass` ticks the step checkboxes, writes `checks/fingerprint.json` when
`app_dir` is set, and commits that step on the product repo in `app/`.
`--fail` if the step did not land. Never commits.

## Do not

- Implement more than one step
- Run prove/security yourself (that is verify)
- Edit the brief folder
