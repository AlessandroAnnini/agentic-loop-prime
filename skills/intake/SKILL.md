---
name: prime-intake
description: >-
  Study a read-only brief folder and write memory/charter.md plus
  memory/backlog.yaml (and research/LANDSCAPE.md when research_track is
  light or deep). Trigger when al-prime next DELEGATEs intake. Does not
  sign the charter or write app/.
---

# Prime intake

Turn notes in `brief/` into a charter and ordered backlog.

## Substeps

| Substep | Write |
|---------|--------|
| `research` | `memory/research/LANDSCAPE.md` (only if track is light or deep) |
| `charter` | `memory/charter.md` |
| `backlog` | `memory/backlog.yaml` with `id`, `design_track`, `surface` |

`research_track: none` (default after init) skips research.

## Done when

The current Resume substep file exists and is non-empty. Then:

```bash
al-prime done --memory memory --pass
```

## Do not

- Sign the charter (`charter_signed` in run-state)
- Edit `app/` or the brief folder
- Invent features that are not in the brief
