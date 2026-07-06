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

Read `state.json`, the current story file (incl. its Plan), `feature.md`. In
guided mode this is a fresh context; in autonomous mode it follows Plan. If there's
no approved plan (guided), send back to `/story-plan`.

## Implement

- Follow the **approved plan** step by step; if reality forces a deviation, note
  it and the reason (in autonomous mode, only stop for a *material* deviation or a
  genuine blocker).
- The repo's **hooks apply** here (restricted-path / dangerous-command guards,
  lint-on-edit) — respect their feedback.
- Run the story's tests and the relevant build/test commands from `AGENTS.md`.
  Record results; if the environment can't run them, record `blocked` + reason
  (don't silently skip).
- **Cross-repo stories:** changes in an editable dependency follow *that* repo's
  `AGENTS.md` (build and test there too, dependency-side contract first) and are
  committed in the dependency repo referencing this feature id. Never modify a
  read-only dependency — the boundary guard denies it; if a change there turns
  out to be required, stop: that's a genuine blocker to surface.
- Keep changes scoped to this story; reuse existing patterns in the area.

## Output: append Change notes to the story file

```md
## Implementation
Changed:
- `<path>`: <what>
Deviations from plan: <none / what + why>
Tests: <command → result, or blocked + reason>
```

Set the story `status: implemented`.

## Gate / continue

- **guided** — present the change + test results; iterate until the user approves;
  set `currentStep: "review"`, `nextCommand: "/story-review"`; tell them to open a
  new session and run it. No light-context exception at this gate: review deserves
  fresh, unbiased eyes, so always hand off to a new session.
- **autonomous** — proceed to Review in this session.

## Completion

The change follows the plan (deviations noted with reasons), the story's tests
pass (or `blocked` + reason), change notes are recorded; `status: implemented`;
state updated.
