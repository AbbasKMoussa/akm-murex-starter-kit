---
name: setup-instructions
description: >-
  Set up agent instruction files for this repository — root AGENTS.md,
  .github/copilot-instructions.md, .github/instructions/tests.instructions.md,
  and nested module AGENTS.md files. Use for "/setup-instructions", "set up the
  agent instructions", or the instructions step of /init. Supports
  "module <path>" / "module all" sub-actions for complex modules.
allowed-tools:
  - shell
---

# setup-instructions — agent instruction files

Generate properly scoped, repo-specific instruction files from detected facts +
a short interview. `AGENTS.md` is the source of truth;
`.github/copilot-instructions.md` stays a short pointer; path-scoped rules go in
`.github/instructions/*.instructions.md`; module files describe only what differs.

## Inputs (ask, pre-filled from detection — confirm, don't re-type)

1. Product: what it is and does. 2. Test command. 3. Build command. 4. Run/serve
command (if any). 5. How to verify a change. 6. CI notes. 7. Complex modules.
8. Related repositories (and when to consider each). 9. Branch naming.
10. Commit style. 11. Restricted files/areas (no edit without approval).

Keep it short; only follow up where an answer is incomplete or has setup
consequences.

## Generate

Create/merge:

- `AGENTS.md` with sections: Product, Repository Context, Stack, Build, Tests,
  **Run**, **Verify a Change**, CI, Complex Modules, Git Workflow, Agent Rules.
- `.github/copilot-instructions.md` — short; points to `AGENTS.md`,
  `.github/instructions/`, nested `AGENTS.md`. Never duplicate the full
  instructions there.
- `.github/instructions/tests.instructions.md` — `applyTo` frontmatter for test
  globs + the test command + behavior-focused guidance.

**Section-aware merge + confirm:** when a target exists, parse it into sections,
merge new content into the right section, show the diff, and apply only after
confirmation. Never delete/weaken existing content; surface genuine conflicts.
Create absent files directly.

## Smoke-verify (required)

Run the captured **build** and **test** commands once to prove they work. Record
the result in state. If they cannot run for a real environment reason
(air-gapped, missing deps, long-running), record `blocked` with the reason —
never silently skip. This is what makes the agent's run/verify loop trustworthy.

## Module sub-actions

`module <path>` / `module all`: generate `<module>/AGENTS.md` describing only what
differs (purpose, boundaries, local commands, patterns, pitfalls, restricted
areas). Record each in `.agentic/setup/modules/<id>.json`.

## State

`.agentic/setup/instructions-state.json`: answers, generated/merged files, smoke
-verify result, pending complex modules.

## Completion

Complete when root `AGENTS.md` (with build/test/run/verify), `copilot-instructions.md`
(pointer), and `tests.instructions.md` exist; smoke-verify passed or is `blocked`
with a reason; state is recorded; nothing was overwritten without confirmation.
Pending complex modules are warnings, not blockers (root files satisfy the gate).
