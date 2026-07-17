# Feature Phase 2: Split

Skill: `/feature-split` · Persona: **Planner** (scrum-master).

The second phase. Break the approved `feature.md` into a small set of high-level
**stories** that can each be taken through the Phase 3 loop independently.

## Goal

An ordered set of stories under `stories/`, each a coherent, independently
testable slice with its own acceptance criteria, with dependencies made explicit
— and full traceability back to the feature's acceptance criteria (no orphan AC).

## Entry

Invoked via `/feature` or directly as `/feature-split`, in fresh context. Check
local readiness, run `feature-show`, require `splitting`, note its revision, and
read `feature.md` plus `understanding.md`. If framing is not approved, return to
`/feature-frame`.

## Meet the user where they are (HITL)

Splitting is a **collaboration**, not a proposal dropped at the end. First ask:
**do you already have a split in mind?**

- **Yes** → take it and: **accept** it as-is if it's sound; **enhance** it (fix
  gaps, ordering, coverage); or, with a **clearly stated reason**, push back and
  propose a different split. The user decides.
- **No** → propose a split, and walk through it *with* the user — think out loud,
  explain the slicing, and iterate on their feedback rather than presenting a
  finished list to rubber-stamp.

Either way, work through the breakdown interactively before the gate.

## How the Planner splits

- Prefer **vertical slices** (a thin end-to-end capability), not horizontal layers
  (don't make "the DB story", "the API story", "the UI story").
- **Right-size — and don't make stories too small.** Each story should deliver
  meaningful, user-visible value and be a substantial chunk of work, not a
  micro-task. Bias toward **fewer, larger** stories; only split when a story is
  genuinely too big to take through one Phase 3 loop. This is story-level, never a
  task list.
- **Order** the stories and make **dependencies explicit** (which must come
  first). Default execution is sequential in this order; note where a story
  depends on another.
- **Trace coverage**: every acceptance criterion in `feature.md` maps to at least
  one story. Flag any criterion not covered, and any story that doesn't trace back
  to the feature.
- Each story gets its own acceptance criteria (derived from / a subset of the
  feature's), testable and behavior-focused.

## Output

Create one file per story and update the feature's Stories section.

`stories/<NN>-<slug>.md`:

```md
# Story <NN>: <title>  (<feature-id>)

## Description
<the slice this story delivers>

## Acceptance Criteria
- [ ] <testable, behavior-focused>

## Dependencies
- <other story this needs, or "none">

<!-- Primer, Plan, and Review notes are appended by the Phase 3 steps. -->
```

Story Markdown has no Status section. The controller-owned story `step` is the
single status source.

In `feature.md`, fill the **Stories** section with the ordered list and links.

## Bundled resources

- `story.template.md` (above).
- `story-splitting-checklist.md` — vertical slices not layers; **substantial, not
  too small** (fewer, larger stories; each delivers meaningful value); ordered with
  explicit dependencies; every feature AC covered; no orphan stories; each story
  independently testable.

## Gate (hard stop)

Present the proposed breakdown — the ordered list, each story's acceptance
criteria, dependencies, and the AC-coverage map — and iterate until the user
approves. On approval:

- write the story files and update `feature.md`;
- call `feature-add-stories` once with the ordered ids and expected revision,
  then call controller gate `split` with the returned revision;
- tell the user: **open a new session and run `/story-prime`** to start the first
  story.

## State

Controller-owned `state.json`: phase `splitting` -> `story_loop`, ordered stories
with initial step `prime`, selected first story, gate/history/revision.
`/story-prime` is derived.

## Completion criteria

Complete when every story has a file with its own testable acceptance criteria
and explicit dependencies; `feature.md`'s Stories section lists them in order;
every feature acceptance criterion traces to a story; the user has approved the
breakdown; and controller state records the ordered stories and approved gate.
