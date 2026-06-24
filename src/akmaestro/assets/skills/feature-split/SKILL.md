---
name: feature-split
description: >-
  Phase 2 of the feature flow (Planner/Scrum-Master). Break the approved
  feature.md into a small set of high-level, right-sized stories with their own
  acceptance criteria, order, and dependencies. Use for "/feature-split", "split
  this into stories", "break down the feature", or the split step of /feature.
allowed-tools:
  - shell
---

# feature-split — Phase 2 (Planner)

Persona: a crisp planner. Turn `feature.md` into a small set of coherent stories,
each takeable through one Phase 3 loop.

## Entry

Fresh context. Read `state.json`, `feature.md`, `understanding.md`. If the feature
isn't framed/approved, send the user back to `/feature-frame`.

## Meet the user where they are (HITL)

First ask: **do you already have a split in mind?**

- **Yes** → take it and either **accept** as-is if sound, **enhance** it (gaps,
  ordering, coverage), or — with a clearly stated reason — push back and propose a
  different split. The user decides.
- **No** → propose a split and walk through it *with* the user, iterating.

## How to split

- **Vertical slices**, not horizontal layers (no "DB story / API story / UI
  story").
- **Right-sized — not too small.** Each story delivers meaningful, user-visible
  value. Bias to **fewer, larger** stories; split only when one is genuinely too
  big for a single Phase 3 loop. Story-level, never a task list.
- **Order** them; make **dependencies explicit**.
- **Trace coverage:** every acceptance criterion in `feature.md` maps to ≥1 story;
  flag any uncovered AC and any story not tracing back to the feature.
- Each story gets its own testable, behavior-focused acceptance criteria.

## Output

One file per story + update `feature.md`'s Stories section.

`stories/<NN>-<slug>.md`:

```md
# Story <NN>: <title>  (<feature-id>)

## Description
<the slice this delivers>

## Acceptance Criteria
- [ ] <testable, behavior-focused>

## Dependencies
- <other story, or "none">

## Status
not-started   # not-started → primed → planned → implemented → reviewed → done

<!-- Primer / Plan / Review / Learnings appended by Phase 3 -->
```

## Gate (hard stop)

Present the breakdown — ordered list, each story's AC, dependencies, and the
AC→story coverage map — and iterate until approved. On approval: write the story
files, update `feature.md`, set `phase: "split"`, the ordered `stories` list with
`status`, `currentStory: "01-<slug>"`, `lastApprovedGate: "split"`,
`nextCommand: "/story-prime"`; tell the user to open a new session and run
**`/story-prime`**.

## Completion

Every story has a file with its own AC + explicit dependencies; `feature.md` lists
them in order; every feature AC traces to a story; the user approved; state records
the story list, current story, and next command.
