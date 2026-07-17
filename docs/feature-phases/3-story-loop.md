# Feature Phase 3: Per-story loop

Skills: `/story-prime` → `/story-plan` → `/story-implement` → `/story-review` →
`/story-learn`. Run once per story, in story order.

This is where the feature gets built, one story at a time. Each step is a curated
specialist. The loop runs in one of **two modes** (the only place mode applies):

- **Guided (HITL)** — each step is a separate gated step in its own fresh context.
- **Autonomous** — the five steps run back-to-back in one session, ungated,
  surfacing only genuine blockers. Hooks (guards/lint) apply in both modes.

Mode is chosen before Prime per story and shown in `feature status`.

## Entry

Invoked via `/feature` or directly as `/story-prime` for the current story, in a
fresh context. First check local readiness, then use `feature-show` to identify
the current story and step. Note the revision, then read `feature.md`,
`understanding.md`, and the current story artifact. If the
story has unmet dependencies, say so and point to the prerequisite story.

Confirm the **mode** for this story (default from the feature setting).

## The five steps

Each step appends its output to the story file, then advances the controller
step: `prime -> plan -> implement -> review -> learn -> complete`.

| Step | Skill | Persona | Does | Appends |
| --- | --- | --- | --- | --- |
| Prime | `/story-prime` | Researcher | Gather the context the story needs | Primer |
| Plan | `/story-plan` | Architect | Turn the primer into an implementation plan | Plan |
| Implement | `/story-implement` | Implementer | Build strictly to the approved plan | Change notes |
| Review | `/story-review` | Reviewer | Check the result vs plan + acceptance criteria | Review |
| Learn | `/story-learn` | Librarian | Capture durable lessons via `/teach` | Learnings |

### Prime (Researcher)

Gather and **persist** what the story needs so the next steps start oriented
without inheriting this context: relevant files/symbols (via Graphifyy + LSP), how
the area works today, constraints, what to touch, and the test approach. Write a
**Primer** into the story file. Resource: `primer.template.md` +
`priming-checklist.md` (affected files, dependents, tests to run, conventions in
the touched area). HITL gate: confirm the primer → new session → `/story-plan`.

### Plan (Architect)

From the primer, produce a concrete **implementation plan**: approach, files to
change, ordered steps, the test plan, and risks. Stays within the story's scope
and acceptance criteria. Resource: `plan.template.md` + `planning-checklist.md`.
HITL gate: approve the plan → new session → `/story-implement`.

### Implement (Implementer)

Implement **strictly to the approved plan**. The repo's hooks apply here
(restricted-path/dangerous-command guards, lint-on-edit). Run the story's tests
and the relevant build/test commands from `AGENTS.md`. Note what changed and any
deviations from the plan (with reasons). HITL gate: approve the change → new
session → `/story-review`.

### Review (Reviewer)

Review the implementation against the **plan and the story's acceptance
criteria**: correctness, AC met, tests present/passing, repo conventions
(`AGENTS.md`), and the edge cases from `understanding.md`. Resource:
`review-checklist.md`. Outcome is **pass** or **send back** (to plan or
implement) with specific findings. HITL gate: pass, or loop back.

### Learn (Librarian)

If the story surfaced a durable convention, pitfall, or gap, call **`/teach`** to
persist it in the right place, and flag any new skill/hook worth adding. This is
the feedback into Stage 1. Advance the story to `complete`. HITL gate: confirm what was
captured.

## Mode behavior

- **Guided:** each step ends at its gate; the user approves, opens a new session,
  and runs the next step. The Reviewer's "send back" returns to `/story-plan` or
  `/story-implement`.
- **Autonomous:** `/story-prime` (or `/feature`) runs all five steps in one
  session without inter-step gates. The Review→send-back loop is handled
  internally (re-plan/re-implement) up to a sensible limit; genuine blockers or
  hard decisions still stop and ask. The hooks still guard every tool call.

## Loop exit (always a gate)

When a story reaches `complete`, present the completed story (primer, plan, change
summary, review result, learnings) — this exit is a hard stop in **both** modes.
Then:

- if more stories remain, the controller selects the next at `prime` and derives
  `/story-prime`;
- if all stories are complete, it moves to `reviewing` and derives
  `/feature-review`.

Autonomous mode does **not** auto-advance to the next story.

## State

Controller-owned `state.json`: `currentStory`, ordered stories with `step`,
per-story `mode` and `reviewAttempts`, gate/history, and revision. Navigation and
display status are derived. Review can transition back to `plan` or `implement`.

## Completion criteria (per story)

A story is `complete` when it has a primer, an approved plan, an implementation that
follows the plan with the story's tests passing (or `blocked` with a reason), a
passing review against its acceptance criteria, and its learnings captured (or
explicitly "nothing to capture"). State reflects `complete`; the controller
derives what follows.
