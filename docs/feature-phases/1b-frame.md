# Feature Phase 1b: Frame

Skill: `/feature-frame` · Persona: **Framer** (PM).

The second step of Phase 1. With the problem now understood (`understanding.md`),
decide the high-level approach and pin down acceptance criteria, producing the
agreed `feature.md`.

## Entry

Invoked via `/feature` or directly as `/feature-frame`, in fresh context. Check
local readiness, run `feature-show`, require `framing`, note its revision, and
read `understanding.md`. If understanding is not approved, return to
`/feature-understand`.

## Meet the dev where they are (adaptive approach)

The Framer first asks: **do you already have a fix/approach/idea?**

- **Yes, clear idea** → capture it, then pressure-test it against
  `understanding.md`: does it cover the edge cases? what are the risks/tradeoffs?
  is anything simpler? Shape it into a high-level, implementable direction.
- **Partial idea** → take what they have and fill the gaps; refine into a coherent
  approach.
- **No idea / wants help** → brainstorm 1–2 high-level options with tradeoffs and
  recommend one.

In all cases the approach stays **high-level** — detailed design happens per story
in Phase 3, not here. Ground the discussion in `AGENTS.md` + Graphifyy.

## Acceptance criteria

Draft testable, behavior-focused acceptance criteria that cover the happy path
**and** the edge cases identified in `understanding.md`. Apply the bundled
checklist.

## Output: `feature.md`

```md
# Feature: <title>  (<feature-id>)

## Problem & Context
<short summary; see understanding.md for the full picture>

## Out of Scope
- <explicitly excluded>

## Solution Approach
<recommended high-level approach + short rationale>
Origin: <user's idea / brainstormed / hybrid>
Alternatives considered: <1-line each, why not>

## Acceptance Criteria
- [ ] <testable, behavior-focused criterion, incl. edge cases>

## Risks & Open Questions
- <risk / unknown / decision still needed>

## Stories
<filled in Phase 2 by /feature-split>
```

## Bundled resources

- `feature.template.md` (above).
- `acceptance-criteria-checklist.md` — testable, unambiguous, user-observable;
  covers happy + edge/negative cases (cross-check `understanding.md`); maps to the
  problem; no implementation detail.

## Gate (hard stop)

Present `feature.md` and iterate until the user approves. On approval:

- write `feature.md`, then call controller gate `frame` with the expected
  revision (which moves the phase to `splitting`);
- tell the user: **open a new session and run `/feature-split`**.

## State

Controller-owned `state.json`: phase `framing` -> `splitting`, approved `frame`
gate, revision/history. `/feature-split` is derived.

## Completion criteria

Complete when `feature.md` exists with problem & context, out-of-scope, a
high-level solution approach (noting whether it came from the dev or brainstorming)
with alternatives, testable acceptance criteria covering the understood edge
cases, and risks/open questions; the user has approved it; and `state.json`
records the approved gate.
