---
name: feature
description: >-
  Orchestrate the feature flow and report where you are. Use to start a feature,
  resume one, or check status: "start a feature", "let's build a feature",
  "where are we?", "what's the status?", "what's left?", "what should I do
  next?", "resume the feature", "/feature", "feature status", "feature help".
  Reads on-disk state so it works from any fresh session.
allowed-tools:
  - shell
---

# feature — feature-flow orchestrator

Stage 2 builds a feature through gated phases, BMAD-style: each step is a curated
specialist run in a fresh context, continuity is carried by on-disk state (not
chat history), and every phase boundary is a hard approval gate. This skill
starts/resumes features and tells you exactly where you are and what to run next.

## Prerequisite

The repo must be set up for agentic coding (Stage 1). If `AGENTS.md` or the
agentic setup is missing, run `init status` / `/doctor` first.

## Sub-commands

- **status / "where are we?" / "what's next?"** — orient (below) and stop.
- **help** — explain the phases, fresh-context rule, gates, and modes; stop.
- **start / new** — begin a new feature.
- otherwise — resume the active feature (route to its `nextCommand`).

## State

```text
.agentic/features/
  index.json              # { "active": "<feature-id>", "features": [{id,title,phase,nextCommand}] }
  <feature-id>/
    understanding.md feature.md state.json stories/ review.md retro.md
```

`state.json` carries `phase`, `currentStory`, `currentStep`, per-story `status`,
per-story `mode`, `lastApprovedGate`, `nextCommand`.

## Orient (status)

Read `index.json` and the active `state.json`, then report and stop:

- **No feature in progress** → say so; suggest **`/feature-understand`** to start.
- **One in progress** → print feature, phase, story progress, current step, mode,
  and the exact next command, e.g.:

  ```text
  Feature: search-filters  (phase: story loop, mode: guided)
  Stories: 01-query-parser ✓  02-facet-ui ▶ (plan approved)  03-cache ·
  Now: story 02, step implement.
  Next: open a new session and run /story-implement
  ```
- **Multiple in progress** → list each with phase + next step; ask which to resume,
  then set it active in `index.json`.

## Start a new feature

Ask for a short title (+ optional ticket id). Derive `feature-id` = optional
ticket + kebab-title. Create `.agentic/features/<feature-id>/`, seed `state.json`
(`phase: "understanding"`, `nextCommand: "/feature-understand"`), add it to
`index.json` and mark active. Then tell the user: open a new session and run
**`/feature-understand`**.

## The phases (for help)

1a Understand → 1b Frame → 2 Split → 3 per-story loop (Prime → Plan → Implement →
Review → Learn) → 4 Feature review → 5 Retro.

- Every phase boundary is a hard gate. **Modes apply only to the Phase 3 loop**:
  *guided* (each step gated, fresh context) or *autonomous* (the 5 steps run
  back-to-back in one session, ungated, surfacing only real blockers). Hooks apply
  in both modes. Autonomous never auto-advances to the next story.
- **Light-context exception:** the fresh-session rule guards context quality, not
  ceremony. At a gate, if the current session is still light (short history, few
  files read), the step may offer to continue with the next command right here.
  The one boundary where it never applies is implement → review: review deserves
  fresh, unbiased eyes.
- Each step skill ends by writing state + printing the next command, so `feature
  status` and the step output always agree.

## Routing

This skill does not implement the phases — it points to the right skill for the
current step (`nextCommand`). Tell the user to open a fresh session and run that
command. Always keep `index.json` and `state.json` as the source of truth.
