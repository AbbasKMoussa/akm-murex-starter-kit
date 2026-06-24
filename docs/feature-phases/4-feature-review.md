# Feature Phase 4: Feature Review

Skill: `/feature-review` · Persona: **QA / Integration reviewer**.

After all stories are `done`, step back and review the feature as a whole, and
produce guided manual-testing steps. Always gated/HITL (mode applies only to
Phase 3).

This is a **distinct persona** from the story-loop Reviewer. The story Reviewer is
a close-up code reviewer (did this slice follow its plan, is the code correct);
the QA / Integration reviewer works at feature altitude — do the stories integrate,
does the whole feature meet its acceptance criteria, and how does a human verify
it. Framing it as QA keeps it from drifting back into re-reviewing story internals.

## Goal

Confidence that the feature — not just each story in isolation — meets
`feature.md`'s acceptance criteria and hangs together, plus a clear manual-test
guide a human can follow to verify it.

## Entry

Invoked via `/feature` or directly as `/feature-review`, in a fresh context. Read
`state.json`, `feature.md`, `understanding.md`, and all story files. If any story
isn't `done`, point back to the per-story loop.

## What the Reviewer checks (high level)

- **Acceptance criteria**: every criterion in `feature.md` is satisfied across the
  combined stories (use the AC→story traceability from Split).
- **Coherence/integration**: the stories fit together — no seams, contradictions,
  or gaps between them; cross-cutting concerns (errors, edge cases from
  `understanding.md`) are handled end-to-end.
- **Tests/build**: the feature's tests pass and the build is green (run them);
  record `blocked` with a reason if the environment can't.
- **Conventions & safety**: consistent with `AGENTS.md`; no restricted-area or
  scope creep beyond the feature.

This is a high-level review, not a re-review of each story's internals (that
happened in Phase 3).

## Guided manual-testing steps

Produce concrete, ordered steps a human runs to verify the feature by hand — how
to run it (from `AGENTS.md`'s Run/Verify), the scenarios to exercise (happy path +
the key edge cases), and the expected result for each.

## Output: `review.md`

```md
# Feature Review: <title>  (<feature-id>)

## Acceptance Criteria — verdict
- [x] <criterion> — met (story 02)
- [ ] <criterion> — NOT met / partial — <why>

## Integration & Coherence
<findings across stories; seams/gaps>

## Tests & Build
<result, or blocked + reason>

## Manual Testing Guide
1. <setup / how to run>
2. <scenario → expected result>

## Issues / Follow-ups
- <anything to fix before done, or deferred with rationale>
```

Resource: `feature-review-checklist.md` + `review.template.md`.

## Gate (hard stop)

Present `review.md`. If issues block the feature, send back to the relevant
story's loop (reopen it). When the user approves:

- record `phase: "reviewed"` and the approval in `state.json`;
- tell the user: **open a new session and run `/feature-retro`**.

## Completion criteria

Complete when `review.md` exists with an AC verdict, integration findings, a
tests/build result, and a manual-testing guide; blocking issues are resolved or
explicitly deferred; the user has approved; and `state.json` records the approval
and next command.
