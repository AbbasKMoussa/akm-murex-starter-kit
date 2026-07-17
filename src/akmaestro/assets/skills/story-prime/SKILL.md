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

Fresh context. Read `.agentic/STATE-PROTOCOL.md`; run `setup-status` and
`readiness-check`, offering confirmed local remediation when required. Resolve
the feature with `feature-list` and `feature-show`. Require phase `story_loop`
and current story step `prime`; note the revision. Read `feature.md`,
`understanding.md`, and the current story artifact. If dependencies are unmet,
stop and point to the prerequisite story. Never edit `state.json`.

Confirm the **mode** for this story (default from the feature setting):

- **guided** — five steps, each gated and in its own fresh context;
- **autonomous** — run Prime → Plan → Implement → Review → Learn back-to-back in
  this session, no inter-step gates, surfacing only genuine blockers. Hooks still
  apply.

If the selected mode differs from `feature-show`, call `story-mode --feature
<feature-id> --story <story-id> --mode <mode> --expected-revision <revision>` and
use the returned revision for the later transition.

## Prime the story

Gather and persist (via Graphifyy + LSP + reading code):

- relevant files/symbols and how the area works today;
- constraints and conventions in the touched area (from `AGENTS.md`);
- for a story touching a **modifiable sibling repository** (see the story's
  Repos tag): that repo's own `AGENTS.md` (its build/test commands) and the
  touched area there; for a **read-only sibling repository**: the exact behavior
  being depended on — a fixed constraint to record, never something to change;
- what to change and what *not* to touch;
- the test approach (how this slice will be tested).

Priming checklist: affected files; their dependents; tests to run; conventions in
the area; the story's acceptance criteria; edge cases from `understanding.md`.

## Output: append a Primer to the story file

```md
## Primer
- Relevant files: `<path>` — <why>   (may span declared sibling repositories)
- How it works today: <short>
- Touch / don't touch: <scope; read-only sibling repositories are always "don't touch">
- Test approach: <how this slice is verified — per repo if cross-repo>
- Notes/constraints: <… incl. behaviors pinned by read-only sibling repositories>
```

## Gate / continue

- **guided** - confirm the primer with the user. Write the artifact first, then
  call `story-transition --feature <feature-id> --story <story-id> --to plan
  --expected-revision <revision>`. Report the derived `/story-plan` command and
  offer a fresh session or light-context continuation.
- **autonomous** — proceed directly to the Plan step in this session.

Autonomous mode still performs the same `story-transition` before starting Plan.

## Completion

The story file has a Primer covering relevant files, current behavior, scope, and
test approach; controller state advances to `plan`. Stale state is reread and
reconciled, never overwritten.
