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

## State protocol

Read `.agentic/STATE-PROTOCOL.md`. Run `setup-init` and `setup-status` through
the bundled controller. If this topic is not already `in_progress`, transition
`instructions` to `in_progress` with the revision just read. Never edit the
aggregate setup state directly.

## Inputs (ask, pre-filled from detection — confirm, don't re-type)

1. Product: what it is and does. 2. Test command. 3. Build command. 4. Run/serve
command (if any). 5. How to verify a change. 6. CI notes. 7. Complex modules.
8. **Workspace & dependencies:** does this repo depend on other locally
checked-out sibling repositories? For each: where it is checked out (e.g.
`../lib-b`), its role — **modifiable** (we own it; functionally part of this
application, just in its own git repo) or **read-only** (another team's code we
consult but never modify) — and, for modifiable ones, how a change there reaches
this repo (relative link, version bump + publish, rebuild). 9. Branch naming.
10. Commit style. 11. Restricted files/areas (no edit without approval).

Keep it short; only follow up where an answer is incomplete or has setup
consequences.

## Generate

Create/merge:

- `AGENTS.md` with sections: Product, Repository Context, Stack, Build, Tests,
  **Run**, **Verify a Change**, CI, Complex Modules, **Workspace & Dependencies**,
  Git Workflow, Agent Rules.
- **Workspace & Dependencies** lists each declared sibling repository with its
  checkout path, role, and rules: *modifiable sibling repositories* may be
  changed as part of normal work here (follow their own `AGENTS.md`; state how
  changes flow back); *read-only sibling repositories* are consulted for
  understanding only — a needed change there is an external dependency to
  surface, never an edit. For each modifiable sibling repository, also append
  its path to `.agentic/hooks/editable-paths.txt` (the compatibility file read by
  the boundary guard) and recommend running `akmaestro init` inside that repo so
  it has its own `AGENTS.md`.
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
the result as evidence. If they cannot run for a real environment reason
(air-gapped, missing deps, long-running), record `blocked` with the reason —
never silently skip. This is what makes the agent's run/verify loop trustworthy.

## Module sub-actions

`module <path>` / `module all`: generate `<module>/AGENTS.md` describing only what
differs (purpose, boundaries, local commands, patterns, pitfalls, restricted
areas). Record each in `.agentic/setup/modules/<id>.json`.

## State

Create a JSON object containing the confirmed answers, generated/merged files,
smoke-verification commands/results, and pending complex modules under
`.agentic/local/`. Write it atomically as committed evidence with:

```text
uv run --no-project python .agentic/bin/akmaestro-state.py evidence-write instructions --input <local-json> --expected-revision <evidence-revision-or-0>
```

This produces `.agentic/setup/instructions-state.json`. It intentionally has no
independent topic status.

## Completion

Complete when root `AGENTS.md` (with build/test/run/verify), `copilot-instructions.md`
(pointer), and `tests.instructions.md` exist; smoke-verify passed or is `blocked`
with a reason; evidence is recorded; nothing was overwritten without
confirmation. Pending complex modules are warnings, not blockers.

Write evidence first. Then, as the final operation, transition `instructions`
from `in_progress` to `complete`, or to `blocked --reason <reason>` when the
required smoke verification has a genuine environment blocker. Pass the latest
aggregate `--expected-revision`. If work is merely unfinished, leave it
`in_progress`. Rerun `setup-status` and report its derived next command.
