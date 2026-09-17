---
name: ui-direction
description: >-
  Design-phase UI direction: write memory/features/<id>/ui.md (dials, locks,
  system map) using design-taste-frontend. Trigger when al-prime next
  DELEGATEs design with substep ui. Does not edit app/ or implement UI.
---

# UI direction (design phase)

Thin wrapper around **design-taste-frontend** for the Prime design phase.

## Load

1. This skill (constraints)
2. `.cursor/skills/design-taste-frontend/SKILL.md` (taste vocabulary)

## Done when

- `memory/features/<id>/ui.md` exists and is non-empty
- Captures brief inference, dials, locks, and a system map, not screenshots, frames, or running UI
- No edits under `app/`

Then:

```bash
al-prime done --memory memory --pass
```

## Hard constraints (design phase)

| Allowed | Forbidden |
|---------|-----------|
| Direction contract markdown | Pixel mocks, Figma-like frames, screenshots |
| Type/color/motion dials + locks | Implementing components in `app/` |
| System map / composition notes | Shipping a taste-complete UI |

Implementation happens later in **build** with `design-taste-frontend` against the signed `ux.md` and this `ui.md`.

## Workflow

1. Read `memory/features/<id>/ux.md` and the backlog `surface`. Inherit those locks; do not invent a second aesthetic from chat.
2. Apply taste skill inference → dials → locks
3. Write only `memory/features/<id>/ui.md`
4. Do not sign the feature brief
