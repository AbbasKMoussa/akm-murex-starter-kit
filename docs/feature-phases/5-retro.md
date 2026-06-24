# Feature Phase 5: Retrospective

Skill: `/feature-retro` · Persona: **Retro facilitator**.

The closing phase. Reflect on how the feature went and **update the AI infra** so
the next feature goes better. Always gated/HITL.

## Goal

A short retrospective plus concrete improvements to the agentic setup — captured,
not just discussed. This is the deliberate, feature-level counterpart to the
per-story `/story-learn`: it catches the bigger, cross-story lessons.

## Entry

Invoked via `/feature` or directly as `/feature-retro`, in a fresh context. Read
`state.json`, `feature.md`, all story files (incl. their learnings), and
`review.md`. Requires the feature review to be approved.

## What the facilitator does

1. **Reflect** — what went well, what was painful, where the agent struggled or
   needed correction, where instructions/tooling/skills/hooks helped or fell
   short. Pull signal from the story learnings and review issues.
2. **Turn lessons into infra updates** — for each durable lesson, take the
   concrete action (with the user, HITL):
   - a new convention/rule/pitfall → call **`/teach`** (it routes to the right
     `AGENTS.md` / instructions / module file);
   - a recurring workflow worth a skill, or a guard worth a hook → propose adding
     it (and flag for `setup-skills` / `setup-hooks`);
   - stale or wrong docs/instructions → fix via `/teach`.
3. **Confirm** each change with the user before applying (never silently edit
   instructions or workflow files).

This is the main loop-back into Stage 1: the feature flow leaves the repo's
agentic setup better than it found it.

## Output: `retro.md`

```md
# Retrospective: <title>  (<feature-id>)

## What went well
- …

## What was painful / where the agent struggled
- …

## AI-infra updates made
- [x] taught: <rule> → <file>  (via /teach)
- [ ] proposed skill/hook: <name> — <why>  (flag for setup-skills/hooks)
- [x] fixed stale instruction: <what>

## Follow-ups (not done now)
- …
```

Resource: `retro-checklist.md` + `retro.template.md`.

## Gate (hard stop) and feature completion

Present `retro.md` and the list of infra changes; apply approved changes via
`/teach` etc. On approval:

- mark the feature **complete** in `state.json` and update
  `.agentic/features/index.json` (no longer the active feature);
- `/feature` prints the feature summary.

## Completion criteria

The feature is complete when `retro.md` exists with reflection and the AI-infra
updates (applied via `/teach` or explicitly flagged as follow-ups), approved
changes are applied, the user has approved, and `state.json` + `index.json` mark
the feature done.
