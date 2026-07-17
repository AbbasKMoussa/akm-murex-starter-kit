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

Fresh context. Read `.agentic/STATE-PROTOCOL.md`; run `setup-status` and
`readiness-check`, offering confirmed local remediation when required. Resolve
the feature with `feature-list` and `feature-show`, require phase `reviewing`,
and note the revision. Then read `feature.md`, `understanding.md`, and all story
artifacts. The controller already guarantees every story step is `complete`.
Never edit `state.json` directly.

## Review (high level)

- **Acceptance criteria** — every criterion in `feature.md` is satisfied across the
  combined stories (use the AC→story traceability from Split).
- **Integration & coherence** — stories fit together; no seams, contradictions, or
  gaps; cross-cutting concerns and the edge cases from `understanding.md` are
  handled end-to-end.
- **Tests & build** — run the feature's tests and the build; green? Record
  `blocked` + reason if the environment can't.
- **Cross-repo integration** — if stories touched a modifiable sibling
  repository: its own tests/build pass, its changes are committed there
  (referencing the feature id), and this repo consumes them through the declared
  mechanism (link/version/rebuild) — not through uncommitted local state. No
  read-only sibling repository was modified; any external dependencies recorded
  in `feature.md` are resolved or explicitly still open.
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
Write the findings first, then call `story-transition --feature <feature-id>
--story <story-id> --to plan|implement --expected-revision <revision>`. The
controller reopens `story_loop` and records the review attempt.

On approval, write `review.md` first, then call `feature-advance --id
<feature-id> --gate feature-review --expected-revision <revision>`. Report the
derived `/feature-retro` command and offer the normal fresh-session or
light-context continuation.

## Completion

`review.md` exists with an AC verdict, integration findings, a tests/build result,
and a manual-testing guide; blocking issues resolved or explicitly deferred; the
user approved; state records the approved gate. Stale state is reread and
reconciled rather than overwritten.
