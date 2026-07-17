---
name: feature-frame
description: >-
  Phase 1b of the feature flow (Framer/PM). With the problem understood, decide
  the high-level solution approach and pin down acceptance criteria, producing
  feature.md. Use for "/feature-frame", "let's frame this feature", "what's our
  approach", or the frame step of /feature. Adapts to whether the dev already has
  an idea.
allowed-tools:
  - shell
---

# feature-frame — Phase 1b (Framer)

Persona: a pragmatic PM. With understanding done, agree the high-level approach
and the acceptance criteria. Detailed design happens later, per story (Phase 3) —
stay high-level here.

## Entry

Fresh context. Read `.agentic/STATE-PROTOCOL.md`; run `setup-status` and
`readiness-check`, remediating missing local requirements only after confirmation.
Resolve the feature through `feature-list` and `feature-show`. Require phase
`framing`, note the revision, then read `understanding.md`. If the controller is
still in `understanding`, send the user to `/feature-understand`. Never edit
`state.json` directly.

## Meet the dev where they are (HITL)

First ask: **do you already have a fix/approach/idea?**

- **Yes** → capture it, then pressure-test against `understanding.md`: does it
  cover the edge cases? risks/tradeoffs? anything simpler? Shape into a high-level
  implementable direction.
- **Partial** → take it and fill the gaps.
- **No** → brainstorm 1–2 options with tradeoffs and recommend one.

Ground everything in `AGENTS.md` + Graphifyy. Collaborate; don't monologue.

## Acceptance criteria

Draft testable, behavior-focused criteria covering the happy path **and** the
edge cases from `understanding.md`. Checklist: each is testable, unambiguous,
user-observable; covers happy + edge/negative; maps to the problem; no
implementation detail.

## Output: `feature.md`

```md
# Feature: <title>  (<feature-id>)

## Problem & Context
<short summary; see understanding.md for the full picture>

## Out of Scope
- <excluded>

## Solution Approach
<recommended high-level approach + rationale>
Origin: <user's idea / brainstormed / hybrid>
Alternatives considered: <1-line each, why not>

## Acceptance Criteria
- [ ] <testable, behavior-focused, incl. edge cases>

## Risks & Open Questions
- <risk / unknown / decision needed>

## Stories
<filled in Phase 2 by /feature-split>
```

## Gate (hard stop)

Iterate until the user approves `feature.md`. Write the artifact first. On
approval call `feature-advance --id <feature-id> --gate frame
--expected-revision <revision>`. Report the controller-derived `/feature-split`
command; offer the normal fresh-session handoff or the light-context exception.

## Completion

`feature.md` exists with problem & context, out-of-scope, a high-level approach
(noting its origin) with alternatives, testable AC covering the understood edge
cases, and risks; the user approved it; state records the gate. On a stale
revision, reread and reconcile instead of forcing the transition.
