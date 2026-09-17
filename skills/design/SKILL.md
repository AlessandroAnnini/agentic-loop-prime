---
name: prime-design
description: >-
  Write track-aware design artifacts under memory/features/<id>/. Light:
  brief.md. Standard: ux.md, then ui.md, then brief.md. Trigger when
  al-prime next DELEGATEs design. Does not write app/ or sign the brief.
---

# Prime design

One feature. Track comes from the backlog row / run-state.

| Track | Order |
|-------|--------|
| light | `brief` |
| standard | `ux` → `ui` → `brief` |

Write:

- `memory/features/<id>/brief.md` (sign-ready; human sets `**Status:** signed`)
- `memory/features/<id>/ux.md` and `ui.md` only on standard

On standard:

- `ux` — load `.agents/skills/ux-architect/SKILL.md`
- `ui` — load `.agents/skills/ui-direction/SKILL.md`

## Done when

The Resume substep file exists and is non-empty. Then:

```bash
al-prime done --memory memory --pass
```

## Do not

- Edit `app/`
- Sign the brief yourself
- Write ux/ui on a light track
