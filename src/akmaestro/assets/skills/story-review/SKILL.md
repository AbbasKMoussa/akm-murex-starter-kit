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

Read `state.json`, the current story file (Primer, Plan, Implementation),
`feature.md`, `understanding.md`. In guided mode this is a fresh context;
autonomous follows Implement.

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

- **pass** → set `status: reviewed`.
- **send back** → return to `/story-plan` or `/story-implement` with specific
  findings. In autonomous mode, re-plan/re-implement internally and re-review,
  up to a sensible limit; if it can't converge, stop and ask the user.

## Gate / continue

- **guided** — present the review; on pass set `currentStep: "learn"`,
  `nextCommand: "/story-learn"`; tell them to open a new session and run it. On
  send-back, point to the step to redo.
- **autonomous** — on pass, proceed to Learn in this session.

## Completion

A Review with a verdict; if pass, `status: reviewed` and state updated; if
send-back, the target step is recorded.
