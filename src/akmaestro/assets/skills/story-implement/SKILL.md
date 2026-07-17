---
name: story-implement
description: >-
  Phase 3 step 3 (Implementer). Implement the current story strictly to its
  approved plan, run its tests, and note what changed. Use for
  "/story-implement", "implement this story", "build it", or the implement step
  of /feature.
allowed-tools:
  - shell
---

# story-implement — Phase 3 / Implement (Implementer)

Persona: a disciplined implementer. Build exactly what the approved plan
specifies — no more.

## Entry

Read `.agentic/STATE-PROTOCOL.md`; run `setup-status` and `readiness-check`.
Resolve the feature with `feature-list` and `feature-show`; require phase
`story_loop` and current story step `implement`, and note the revision. Read the
current story artifact including its Plan and `feature.md`. In guided mode this
is fresh context; autonomous mode follows Plan. If the Plan is absent, stop and
send back to `/story-plan`. Never edit controller state directly.

## Implement

- Follow the **approved plan** step by step; if reality forces a deviation, note
  it and the reason (in autonomous mode, only stop for a *material* deviation or a
  genuine blocker).
- The repo's **hooks apply** here (restricted-path / dangerous-command guards,
  lint-on-edit) — respect their feedback.
- Run the story's tests and the relevant build/test commands from `AGENTS.md`.
  Record results; if the environment can't run them, record `blocked` + reason
  (don't silently skip).
- **Cross-repo stories:** changes in a modifiable sibling repository follow
  *that* repo's `AGENTS.md` (build and test there too, sibling-side contract
  first) and are committed in the sibling repo referencing this feature id.
  Never modify a read-only sibling repository — the boundary guard denies it;
  if a change there turns out to be required, stop and surface the blocker.
- Keep changes scoped to this story; reuse existing patterns in the area.

## Output: append Change notes to the story file

```md
## Implementation
Changed:
- `<path>`: <what>
Deviations from plan: <none / what + why>
Tests: <command → result, or blocked + reason>
```

## Gate / continue

- **guided** — present the change + test results; iterate until the user approves;
  write Implementation notes first, then call `story-transition --feature
  <feature-id> --story <story-id> --to review --expected-revision <revision>`.
  Report `/story-review` and always hand off to a fresh session for unbiased
  review; there is no light-context exception at this gate.
- **autonomous** — proceed to Review in this session.

Autonomous mode performs the same transition before review.

## Completion

The change follows the plan (deviations noted with reasons), the story's tests
pass (or `blocked` + reason), change notes are recorded, and controller state
advances to `review`.
