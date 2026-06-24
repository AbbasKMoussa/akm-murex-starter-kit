---
name: story-plan
description: >-
  Phase 3 step 2 (Architect). Turn the story primer into a concrete
  implementation plan. Use for "/story-plan", "plan this story", or the plan step
  of /feature.
allowed-tools:
  - shell
---

# story-plan — Phase 3 / Plan (Architect)

Persona: an architect who designs the smallest sound change. From the primer,
produce a concrete plan that stays within the story's scope and acceptance
criteria.

## Entry

Read `state.json`, the current story file (incl. its Primer), `feature.md`. In
guided mode this is a fresh context; in autonomous mode it follows Prime in the
same session. If there's no approved primer (guided), send back to `/story-prime`.

## Produce the plan

- **Approach** — how the change will be made, grounded in the primer.
- **Files to change** — each with what changes.
- **Ordered steps** — the implementation sequence.
- **Test plan** — what tests to add/update and how to verify the AC.
- **Risks** — and how to mitigate.

Planning checklist: within story scope; satisfies the story AC; reuses existing
patterns in the touched area; tests cover happy + edge cases; no restricted areas;
no unplanned scope creep.

## Output: append a Plan to the story file

```md
## Plan
Approach: <…>
Files:
- `<path>`: <change>
Steps:
1. <…>
Test plan: <…>
Risks: <…>
```

Set the story `status: planned`.

## Gate / continue

- **guided** — present the plan; iterate until the user approves; set
  `currentStep: "implement"`, `nextCommand: "/story-implement"`; tell them to open
  a new session and run it.
- **autonomous** — proceed to Implement in this session.

## Completion

The story file has an approved Plan (approach, files, steps, test plan, risks)
within scope; `status: planned`; state updated.
