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

Fresh context. Read `.agentic/STATE-PROTOCOL.md`; run `setup-status` and
`readiness-check`, offering confirmed local remediation when needed. Resolve the
feature with `feature-list` and `feature-show`, require phase `splitting`, and
note the revision. Then read `feature.md` and `understanding.md`. If phase is
still `framing`, send the user to `/feature-frame`. Never edit `state.json`.

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
- **Tag repos.** Mark which repos each story touches: this repo, a modifiable
  sibling repository, or both. A story spanning a modifiable sibling delivers
  the sibling-side contract (interface + its tests) before the consuming side. A
  change needed in a **read-only sibling repository** can never be a story —
  record it in `feature.md` as an external dependency/blocker for the owning team.
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

## Repos
- <this repo, and/or `../<modifiable-sibling>` — which repos this story changes>

<!-- Primer / Plan / Review / Learnings appended by Phase 3 -->
```

Do not put a status section in story Markdown. The controller-owned story `step`
is the only status source.

## Gate (hard stop)

Present the breakdown, each story's AC/dependencies, and the AC-to-story coverage
map; iterate until approved. Write all story files and update `feature.md` first.
Then call one `feature-add-stories --id <feature-id> --story <id-1> --story
<id-2> ...` command, repeating `--story` in approved order, with `--mode guided`
and the revision read at entry. Read the returned revision and call
`feature-advance --id <feature-id> --gate split
--expected-revision <new-revision>`.

The controller selects the first story, enters `story_loop`, and derives
`/story-prime`. Print that handoff and offer the normal fresh-session or
light-context continuation.

## Completion

Every story has a file with its own AC + explicit dependencies; `feature.md` lists
them in order; every feature AC traces to a story; the user approved; state records
the ordered stories and approved split gate. Stale state is reread and reconciled,
never overwritten.
