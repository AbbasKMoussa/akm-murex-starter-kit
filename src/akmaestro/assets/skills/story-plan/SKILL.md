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

Read `.agentic/STATE-PROTOCOL.md`; run `setup-status` and `readiness-check`.
Resolve the feature with `feature-list` and `feature-show`; require phase
`story_loop` and current story step `plan`, and note the revision. Read the
current story artifact including its Primer and `feature.md`. In guided mode this
is fresh context; autonomous mode follows Prime. If the Primer is absent, stop
and send back to `/story-prime`. Never edit controller state directly.

## Produce the plan

- **Approach** — how the change will be made, grounded in the primer.
- **Files to change** — each with what changes.
- **Ordered steps** — the implementation sequence.
- **Test plan** — what tests to add/update and how to verify the AC.
- **Risks** — and how to mitigate.

Planning checklist: within story scope; satisfies the story AC; reuses existing
patterns in the touched area; tests cover happy + edge cases; no restricted areas;
no unplanned scope creep; **cross-repo** — no read-only sibling repository is
touched, and changes in a modifiable sibling repository come first (contract +
its own tests, per that repo's `AGENTS.md`), then the consuming change here.

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

## Gate / continue

- **guided** - present the plan and iterate until approval. Write the artifact
  first, then call `story-transition --feature <feature-id> --story <story-id>
  --to implement --expected-revision <revision>`. Report the derived
  `/story-implement` command and offer a fresh session or light-context
  continuation.
- **autonomous** — proceed to Implement in this session.

Autonomous mode performs the same transition before implementation.

## Completion

The story file has an approved Plan (approach, files, steps, test plan, risks)
within scope; controller state advances to `implement`.
