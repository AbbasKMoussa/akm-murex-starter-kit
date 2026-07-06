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

Read `state.json` and the current story file (Primer, Plan, Implementation,
Review), `feature.md`. In guided mode this is a fresh context; autonomous follows
Review.

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

Set the story `status: done`.

## Loop exit (always a gate, both modes)

Closing a story is a hard stop in **both** modes. Present the completed story
(primer, plan, change, review, learnings). Then update `state.json`:

- more stories remain → `currentStory` = next, `currentStep: "prime"`,
  `nextCommand: "/story-prime"`; tell the user to open a new session and run it
  (or, if this session is still light, offer to start the next story's Prime
  right here). Autonomous does **not** auto-advance to the next story.
- all stories done → `phase: "story-loop-done"`, `nextCommand: "/feature-review"`.

## Completion

Learnings recorded (or "nothing to capture"); durable lessons applied via
`/teach`; `status: done`; state points to the next story or `/feature-review`.
