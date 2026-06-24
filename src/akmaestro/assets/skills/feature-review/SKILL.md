---
name: feature-review
description: >-
  Phase 4 of the feature flow (QA / Integration reviewer). After all stories are
  done, review the feature as a whole against its acceptance criteria and produce
  a guided manual-testing guide. Use for "/feature-review", "review the whole
  feature", "does it all hang together", or the feature-review step of /feature.
allowed-tools:
  - shell
---

# feature-review — Phase 4 (QA / Integration reviewer)

Persona: QA at feature altitude — **distinct** from the story-level code reviewer.
Don't re-review story internals (that happened in Phase 3); check the feature as a
whole and how a human verifies it. Always gated/HITL (modes apply only to Phase 3).

## Entry

Fresh context. Read `state.json`, `feature.md`, `understanding.md`, and all story
files. If any story isn't `done`, point back to the per-story loop.

## Review (high level)

- **Acceptance criteria** — every criterion in `feature.md` is satisfied across the
  combined stories (use the AC→story traceability from Split).
- **Integration & coherence** — stories fit together; no seams, contradictions, or
  gaps; cross-cutting concerns and the edge cases from `understanding.md` are
  handled end-to-end.
- **Tests & build** — run the feature's tests and the build; green? Record
  `blocked` + reason if the environment can't.
- **Conventions & safety** — consistent with `AGENTS.md`; no scope creep beyond the
  feature; no restricted-area changes.

## Guided manual-testing steps

Produce concrete, ordered steps a human runs to verify by hand: how to run it
(from `AGENTS.md` Run/Verify), scenarios to exercise (happy path + key edge cases),
and the expected result for each.

## Output: `review.md`

```md
# Feature Review: <title>  (<feature-id>)

## Acceptance Criteria — verdict
- [x] <criterion> — met (story 02)
- [ ] <criterion> — not met / partial — <why>

## Integration & Coherence
<findings; seams/gaps>

## Tests & Build
<result, or blocked + reason>

## Manual Testing Guide
1. <setup / how to run>
2. <scenario → expected result>

## Issues / Follow-ups
- <fix before done, or deferred with rationale>
```

## Gate (hard stop)

Present `review.md`. If issues block the feature, reopen the relevant story's loop.
On approval: set `phase: "reviewed"`, `lastApprovedGate: "feature-review"`,
`nextCommand: "/feature-retro"`; tell the user to open a new session and run
**`/feature-retro`**.

## Completion

`review.md` exists with an AC verdict, integration findings, a tests/build result,
and a manual-testing guide; blocking issues resolved or explicitly deferred; the
user approved; state records approval and next command.
