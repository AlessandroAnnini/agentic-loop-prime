# UX Brief — [Project / Feature name]

> This brief is the interaction-architecture contract for the implementation pass.
> Task model, decision budgets, defaults, and the disclosure plan are **requirements**.
> Visual style, typography, color, motion, and component choices are **delegated** to the
> implementing agent (e.g. with Taste Skill / design-taste-frontend loaded).
> Fill every section; write "none" instead of deleting a section.

## 0. Assumptions
[Anything inferred rather than asked. The user can correct these before implementation.]

## 1. Primary user & primary task
- **User:** [who, expertise level, context of use]
- **Primary task:** [the ONE thing that must succeed on first contact, in the user's words]
- **Secondary tasks:** [ordered by frequency]
- **Explicit non-goals (v1 omissions):** [features considered and cut, so they don't creep back in]

## 2. Task model
[The user's intentions as an ordered sequence — not screens. Screens derive from this.]

1. ...
2. ...

## 3. Screen inventory & flow
[One entry per screen/state. Each screen must map to task-model steps.]

### Screen: [name]
- **Serves task-model steps:** [#]
- **Primary action:** [exactly one; must be visually dominant — hierarchy requirement, not a style directive]
- **Decision budget:** [N] — decisions on primary path: [list them; justify any over 3]
- **Memory items:** 0 — [what the UI re-displays to guarantee this]
- **Uncertainty points:** 0 — [labels/feedback that make every outcome predictable]
- **Empty / loading / error behavior:** [what happens, at the behavior level]

## 4. Defaults & options ledger
[Every configurable that survived the defaults pipeline: default-only → inferred → exposed.]

| Setting | Default | Why it exists as an option at all | Where exposed |
|---|---|---|---|
| ... | ... | ... | immediate / staged |

## 5. Disclosure plan
| Feature | Tier | Trigger label (information scent) | How the user who needs it finds it |
|---|---|---|---|
| ... | immediate / staged / omitted | ... | ... |

Constraints: no core action staged; max 2 layers; sets of ≤ 5 items are not staged.

## 6. Guardrails
- **Banned:** urgency banners, fake scarcity, confirm-shaming, pre-checked consent, nagging modals, and all other dark patterns.
- **Friction kept:** [destructive/irreversible actions that retain confirmation]
- **Friction removed:** [confirmations/steps eliminated as extraneous]

## 7. Iteration invariants
[Controls, layouts, and interaction patterns that future regenerations must NOT move or rename. On redesigns: everything users have already learned goes here unless a fix explicitly justifies the move.]

## 8. Handoff note to the implementing agent
Implement this brief. Sections 1–7 are fixed requirements. All visual and stylistic
decisions are yours, except the per-screen hierarchy requirements in section 3.
If a visual decision would force a violation of a budget or the disclosure plan,
stop and flag it instead of violating it.

## 9. Pre-flight (checked honestly before handoff)
- [ ] First-time user completes the primary task with zero menus/disclosures
- [ ] All screens within decision budget, overruns justified in writing
- [ ] Zero memory items across the flow
- [ ] Every option has a default and a written reason to exist
- [ ] Every staged feature: labeled trigger + answered discoverability question; ≤ 2 layers
- [ ] No core action behind a disclosure
- [ ] No dark patterns
- [ ] Destructive actions keep friction; nothing else has it
- [ ] Iteration invariants listed (mandatory on redesigns)
- [ ] No visual/style directives beyond hierarchy requirements
