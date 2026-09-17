# Cognitive principles behind the rules

This file is the "why" layer. Read it when a rule in SKILL.md needs defending, when auditing an existing UI, or when a situation falls between the rules.

## Contents
1. Choice overload is conditional, not a law
2. Defaults are the strongest lever
3. Complexity is conserved (Tesler's law)
4. Progressive disclosure: the failure modes
5. The three loads (Sweller) and useful friction
6. Recognition over recall, and muscle memory as user capital
7. Dark patterns vs. complexity — different diseases, different cures
8. LLM-specific pathologies
9. Audit rubric

## 1. Choice overload is conditional, not a law

Schwartz's *Paradox of Choice* (2004) popularized "more options = worse." The evidence is messier: Scheibehenne, Greifeneder & Todd's 2010 meta-analysis (50 experiments, 5,000+ participants) found a mean effect of assortment size on satisfaction near zero — some studies show overload, some the opposite, most nothing. Chernev et al. (2015) identified when overload actually bites: options are hard to compare, the decision feels consequential, the user lacks expertise, the set is poorly organized, and there's time pressure.

**Design consequence:** the enemy is not the count of options but *comparison difficulty*. Before cutting options, structure them: mutually exclusive, distinctly labeled, ordered by frequency, grouped by user goal (not by internal system architecture). Cut only what structure can't save. Never justify a decision with "the jam study proved fewer is better" — it didn't.

## 2. Defaults are the strongest lever

Across the choice-architecture literature, no intervention moves behavior like a default (opt-out organ donation: ~99% consent vs. ~12% opt-in — same freedom, different default; every 10 extra funds in a 401(k) menu drops participation ~2 points). A smart default removes the decision for the majority without removing capability for anyone.

**Design consequence:** "defaults first, options second" is a pipeline, not a preference: ship-only-the-default → infer-it → expose-it, stopping at the earliest stage that works. An option without a default is a design task pushed onto the user. Also: defaults are read as recommendations — set them to what genuinely serves the user, not what serves engagement metrics.

## 3. Complexity is conserved (Tesler's law)

Every application has irreducible complexity; the only question is who absorbs it — the user, or the designer/system. "Simplification" that merely relocates complexity (into hidden menus, into modes, into documentation, into support tickets) hasn't reduced anything.

The Microsoft ribbon is the honest version of this story: Word 2003's 30+ toolbars were genuinely bad; the 2007 ribbon helped novices discover features — *and* it consumed screen space, broke expert muscle memory, drew years of backlash, and by 2018 Microsoft itself shipped a "simplified ribbon," conceding the ribbon had become the new complexity. Redesigns are trades, not victories.

**Design consequence:** when the brief simplifies something, state where the complexity went (absorbed by a default, by inference, by an omission) — if you can't say, it was relocated onto the user. Prefer designs where the *system* pays: computation, inference, and sensible assumptions are cheap; user attention is not.

## 4. Progressive disclosure: the failure modes

Disclosure done right stages the long tail; done wrong it creates *discoverability debt*. Documented failure modes:

- **The wrong split** — hiding something users need frequently. Nielsen's own formulation: disclose everything frequently needed up front; otherwise you've relocated complexity, not reduced it.
- **Invisible reveals** — a reveal users can't find isn't disclosure, it's a hidden feature. The trigger needs a label with information scent ("Show 4 more", "Advanced export options"), not a mystery chevron. Discoverability is the entire contract.
- **Discovery deficit** — users who never find a feature they'd value conclude the product lacks it and leave. The product is perceived as worth less than it is.
- **Layer sprawl** — beyond two layers users lose the map. A needed third layer is an information-architecture bug, not a disclosure decision.
- **Pointless staging** — with ≤ 5 total items, the disclosure click costs more than the reduction saves. Just show them.
- **Aesthetic hiding** — hiding driven by a taste for empty margins rather than usage data. The test: does the disclosure serve the user's ability to find what they'll want, or the team's desire for a simpler-looking screenshot? When they conflict, the user wins.
- **Accessibility traps** — hover-only reveals, content removed from the DOM, color-only state. Hidden content must stay reachable by keyboard and screen reader, with a persistent trigger.

## 5. The three loads (Sweller) and useful friction

Cognitive load theory distinguishes: **intrinsic** load (inherent to the task — a mixing console is complex because mixing is), **extraneous** load (caused by presentation — clutter, ambiguous labels, redundant confirmations, decorative noise), and **germane** load (effort that builds understanding).

"Eliminate mental effort" is therefore the wrong north star. The correct triage:

- Extraneous → eliminate ruthlessly.
- Intrinsic → flatten the *presentation* (staging, sensible grouping, plain language), never amputate the capability. Photoshop, DAWs, CAD, ERPs cannot become three buttons without dying.
- Germane / useful friction → preserve deliberately: confirmations before destructive or irreversible actions, onboarding steps that build a durable mental model, moments where slowing the user down prevents a worse cost later. A tool used for years may charge a learning fee; a tool used once may not.

## 6. Recognition over recall, and muscle memory as user capital

Humans recognize far better than they recall. Anything the system already knows (previous inputs, current context, what step the user is on) it must re-display rather than make the user remember — the "memory items = 0" budget in SKILL.md operationalizes this.

Learned spatial layout is the same asset over time: users invest in where things are, and that investment compounds into speed. Microsoft's floating Copilot button (2025) is the cautionary tale — moved out of the ribbon to boost engagement, it broke two decades of ribbon muscle memory and covered users' work; the backlash forced a reversal. The lesson generalizes brutally to LLM workflows, where regeneration is free and every regeneration can silently reshuffle the interface. Novelty that costs learned layout is usually a net loss even when the feature is good — hence the "iteration invariants" section in every brief.

## 7. Dark patterns vs. complexity — different diseases, different cures

Complexity is *accidental* cognitive load; dark patterns are *deliberate* cognitive load engineered to bias decisions: urgency banners ("Only 1 left!"), fake scarcity, confirm-shaming, pre-checked boxes, nagging modals, roach-motel flows (easy in, hard out). They often coexist with clean visuals — Booking.com's urgency messaging is a decluttered interface with weaponized load on top, and EU consumer authorities have acted against exactly those patterns.

**Design consequence:** the categorical ban in every brief. Also a generation-time hazard: models trained on the e-commerce web reproduce these patterns spontaneously when asked for "conversion-optimized" anything. The ban must be explicit because the default is contaminated.

## 8. LLM-specific pathologies

Empirical work comparing human-designed, raw AI-generated, and prompt-optimized AI-generated interfaces finds raw generations look polished while carrying inconsistent grouping, weak task hierarchy, unclear affordances, and excessive decoration — visual plausibility is not usability. Known biases to design against:

- **Option maximalism** — features are cheap to generate, so every imagined need becomes a toggle. Counter: the defaults pipeline and the decision budget.
- **Screenshot optimization** — models optimize for looking like good design in a static frame, not for task completion over time. Counter: task model before screens; audit by walking the flow, not by looking at it.
- **Regeneration churn** — each pass may re-layout everything. Counter: iteration invariants.
- **Critique beats restraint** — LLMs are much better at auditing against explicit criteria than at spontaneous restraint. Counter: this skill's generate → audit → cut loop; the pre-flight checklist exists to be *failed* honestly and then fixed.

## 9. Audit rubric

Score each screen of an existing UI:

| Metric | How to measure | Severity if over |
|---|---|---|
| Decisions on primary path | Walk the primary task; count real choices (a pre-filled field with a good default = 0) | > 3 without justification: major |
| Memory items | Anything the user must carry between steps that the UI knows | Any: major |
| Uncertainty points | Actions whose outcome the user can't predict from the label | Any: major |
| Core action behind disclosure | Is the #1 task reachable with zero reveals? | Yes hidden: critical |
| Unlabeled reveals | Disclosure triggers without information scent | Each: minor |
| Disclosure depth | Count layers | > 2: major |
| Options without defaults | Configurables the user must decide | Each: minor; on primary path: major |
| Dark patterns | Urgency/scarcity/confirm-shaming/pre-checked/nagging | Any: critical |
| Missing friction | Destructive actions without confirmation | Any: major |
| Extraneous confirmations | Non-destructive actions with confirmation | Each: minor |

Report as: finding → severity → which principle above → concrete fix → what it preserves. Then emit the corrective brief with the preservation list (section 6) given equal weight to the fixes.
