---
name: story-prime
description: >-
  Phase 3 step 1 (Researcher). Gather and persist the context the current story
  needs so later steps start oriented. Use for "/story-prime", "prime the story",
  or the prime step of /feature. Also the entry point for the per-story loop,
  where the mode (guided vs autonomous) is chosen.
allowed-tools:
  - shell
---

# story-prime — Phase 3 / Prime (Researcher)

Persona: a researcher who orients the work. Gather what the current story needs
and write it down so the next steps start well without inheriting this context.

## Entry & mode

Fresh context. Read `state.json` (which story is current), `feature.md`,
`understanding.md`, and the current `stories/<NN>-<slug>.md`. If the story has
unmet dependencies, say so and point to the prerequisite story.

Confirm the **mode** for this story (default from the feature setting):

- **guided** — five steps, each gated and in its own fresh context;
- **autonomous** — run Prime → Plan → Implement → Review → Learn back-to-back in
  this session, no inter-step gates, surfacing only genuine blockers. Hooks still
  apply. Record the chosen mode in `state.json`.

## Prime the story

Gather and persist (via Graphifyy + LSP + reading code):

- relevant files/symbols and how the area works today;
- constraints and conventions in the touched area (from `AGENTS.md`);
- what to change and what *not* to touch;
- the test approach (how this slice will be tested).

Priming checklist: affected files; their dependents; tests to run; conventions in
the area; the story's acceptance criteria; edge cases from `understanding.md`.

## Output: append a Primer to the story file

```md
## Primer
- Relevant files: `<path>` — <why>
- How it works today: <short>
- Touch / don't touch: <scope>
- Test approach: <how this slice is verified>
- Notes/constraints: <…>
```

Set the story `status: primed`.

## Gate / continue

- **guided** — confirm the primer with the user, set `currentStep: "plan"`,
  `nextCommand: "/story-plan"`; tell them to open a new session and run it.
- **autonomous** — proceed directly to the Plan step in this session.

## Completion

The story file has a Primer covering relevant files, current behavior, scope, and
test approach; `status: primed`; state updated.
