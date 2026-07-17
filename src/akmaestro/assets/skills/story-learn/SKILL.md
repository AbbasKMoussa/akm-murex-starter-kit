---
name: story-learn
description: >-
  Phase 3 step 5 (Librarian). Capture durable lessons from the finished story
  into the repo's AI infra via /teach, and close the story. Use for
  "/story-learn", "capture lessons", or the learn step of /feature.
allowed-tools:
  - shell
---

# story-learn — Phase 3 / Learn (Librarian)

Persona: a librarian who keeps the agent's knowledge sharp. If the story surfaced
something durable, persist it; then close the story. This is the per-story
feedback into Stage 1.

## Entry

Read `.agentic/STATE-PROTOCOL.md`; run `setup-status` and `readiness-check`.
Resolve the feature with `feature-list` and `feature-show`; require phase
`story_loop` and current story step `learn`, and note the revision. Read the
current story artifact and `feature.md`. In guided mode this is fresh context;
autonomous follows Review. Never edit controller state directly.

## Capture lessons

Look across the story for durable signal worth keeping:

- a convention, rule, or pitfall the work revealed → call **`/teach`** (it routes
  to the right `AGENTS.md` / instructions / module file and refines the wording);
- a recurring workflow worth a skill, or a guard worth a hook → flag it (note for
  `setup-skills` / `setup-hooks`); don't build it here;
- a stale or wrong instruction discovered → fix via `/teach`.

Be strict (like `/teach`): only persist durable, general lessons — not one-off
task detail. If nothing is worth capturing, record "nothing to capture".

## Output: append Learnings to the story file

```md
## Learnings
- taught: <rule> → <file>   (via /teach)
- flagged: skill/hook <name> — <why>
- (or) nothing durable to capture
```

## Loop exit (always a gate, both modes)

Closing a story is a hard stop in **both** modes. Present the completed story
(primer, plan, change, review, learnings). Write Learnings first, then call
`story-transition --feature <feature-id> --story <story-id> --to complete
--expected-revision <revision>`.

The controller either selects the next story at `prime` or moves the feature to
`reviewing`; use its derived `/story-prime` or `/feature-review` command. Offer
the normal fresh-session/light-context handoff. Autonomous mode never starts the
next story automatically.

## Completion

Learnings recorded (or "nothing to capture"); durable lessons applied via
`/teach`; controller state points to the next story or `/feature-review`.
