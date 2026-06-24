---
name: feature-retro
description: >-
  Phase 5 of the feature flow (Retro facilitator). Reflect on how the feature
  went and update the repo's AI infra (instructions, skills, hooks) so the next
  feature goes better, then close the feature. Use for "/feature-retro",
  "retrospective", "what did we learn", or the retro step of /feature.
allowed-tools:
  - shell
---

# feature-retro — Phase 5 (Retro facilitator)

Persona: a facilitator who turns experience into improvement. The feature-level
counterpart to `/story-learn` — catch the bigger, cross-story lessons and leave
the agentic setup better than you found it. Always gated/HITL.

## Entry

Fresh context. Read `state.json`, `feature.md`, all story files (incl. their
Learnings), and `review.md`. Requires the feature review to be approved.

## Reflect

Pull signal from the story learnings and review issues:

- what went well; what was painful;
- where the agent struggled or needed correction;
- where instructions / tooling / skills / hooks helped or fell short.

## Turn lessons into infra updates (HITL — confirm each)

For each durable lesson, take the concrete action *with the user*:

- a new convention/rule/pitfall → call **`/teach`** (routes to the right file);
- a recurring workflow worth a skill, or a guard worth a hook → **propose adding
  it** and flag for `setup-skills` / `setup-hooks`;
- stale/wrong docs or instructions → fix via `/teach`.

Confirm each change before applying — never silently edit instructions or workflow
files. This is the main loop-back into Stage 1.

## Output: `retro.md`

```md
# Retrospective: <title>  (<feature-id>)

## What went well
- …

## What was painful / where the agent struggled
- …

## AI-infra updates made
- [x] taught: <rule> → <file>   (via /teach)
- [ ] proposed skill/hook: <name> — <why>   (flag for setup-skills/hooks)
- [x] fixed stale instruction: <what>

## Follow-ups (not done now)
- …
```

## Gate + feature completion

Present `retro.md` and the list of infra changes; apply approved changes via
`/teach` etc. On approval: mark the feature **complete** in `state.json`, clear it
as active in `.agentic/features/index.json`, and print the feature summary.

## Completion

`retro.md` exists with reflection + AI-infra updates (applied via `/teach` or
flagged as follow-ups); approved changes applied; the user approved; `state.json`
and `index.json` mark the feature done.
