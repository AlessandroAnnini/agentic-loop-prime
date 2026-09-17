# Third-party skills

Vendored skill files shipped with this kit. Operators do not need to install them separately.

| Skill folder | Upstream | License | Notes |
|--------------|----------|---------|-------|
| `ux-architect/` | Local pack (`ux-architect.skill`) | Project / author license as shipped in the pack | Interaction architecture; writes `memory/features/<id>/ux.md` |
| `design-taste-frontend/` | [Leonxlnx/taste-skill](https://github.com/Leonxlnx/taste-skill) (`skills/taste-skill/`, install name `design-taste-frontend`) | MIT (see `design-taste-frontend/LICENSE`) | Anti-slop frontend skill; direction in design, implementation in build |
| `ui-direction/` | Prime wrapper | Project | Thin design-phase wrapper over taste skill |

Refresh taste-skill by re-copying `SKILL.md` from upstream when you intentionally upgrade the snapshot.
