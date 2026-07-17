---
name: story-review
description: >-
  Phase 3 step 4 (Reviewer). Review the current story's implementation against
  its plan and acceptance criteria; pass or send back with findings. Use for
  "/story-review", "review this story", or the review step of /feature.
allowed-tools:
  - shell
---

# story-review — Phase 3 / Review (Reviewer)

Persona: a close-up code reviewer (distinct from the feature-level QA reviewer in
Phase 4). Check this story's implementation only.

## Entry

Read `.agentic/STATE-PROTOCOL.md`; run `setup-status` and `readiness-check`.
Resolve the feature with `feature-list` and `feature-show`; require phase
`story_loop` and current story step `review`, and note the revision. Read the
current story artifact, `feature.md`, and `understanding.md`. In guided mode this
is fresh context; autonomous follows Implement. Never edit controller state.

## Review against plan + acceptance criteria

- **Correctness** — does it work; logic sound.
- **AC met** — the story's acceptance criteria are satisfied.
- **Plan adherence** — matches the approved plan (deviations justified).
- **Tests** — present and passing; cover happy + the edge cases from
  `understanding.md`.
- **Conventions & safety** — consistent with `AGENTS.md`; no restricted-area edits;
  no scope creep.

Review checklist: correctness; AC; tests; conventions; edge cases; scope.

## Output: append a Review to the story file

```md
## Review
Verdict: pass | send-back
Findings:
- <issue → where → severity>
Sends back to: <plan | implement>   # if send-back
```

## Outcome

- **pass** - write the Review, then transition the story `--to learn` with the
  revision read at entry.
- **send back** - write the Review, then transition `--to plan` or `--to
  implement` with specific findings. The controller records the review attempt.
  In autonomous mode, re-plan/re-implement and re-review through the same
  transitions, up to a sensible limit; if it cannot converge, stop and ask.

## Gate / continue

- **guided** - present the review and report the controller-derived command. On
  pass, offer `/story-learn` in a fresh or still-light session. On send-back,
  point to the derived redo step.
- **autonomous** — on pass, proceed to Learn in this session.

## Completion

A Review with a verdict; controller state points to Learn or the exact send-back
step. A stale transition requires rereading the current implementation and state.
