# Initialization Topic: Instruction Files

This topic defines what it means to initialize agent instruction files for a target repository.

## Goal

Create properly scoped instruction files so agents understand:

- what the product does;
- how to build and test the repo;
- CI expectations;
- complex modules that need their own local guidance;
- related repositories;
- branch and commit conventions;
- repo-specific safety boundaries.

The setup should ask a small number of practical questions and generate useful files from the answers. Avoid long interviews that busy developers will not complete.

## Agreed File Model

Generate or update these files:

```text
AGENTS.md
.github/copilot-instructions.md
.github/instructions/tests.instructions.md
<complex-module>/AGENTS.md
```

`AGENTS.md` is the main source of truth.

`.github/copilot-instructions.md` should stay short and direct Copilot to `AGENTS.md`, `.github/instructions/`, and nested `AGENTS.md` files. Avoid duplicating the full root instructions because duplicated instruction sources can conflict.

`.github/instructions/tests.instructions.md` contains test-specific guidance using path-scoped instructions.

Nested module `AGENTS.md` files are generated later for complex modules and should only describe what differs inside that module.

## Phase 1: Root Instruction Setup

Command:

```text
/setup-instructions
```

(Also reachable through the guided `/init`. See `docs/setup-flow.md`.)

Creates or updates:

```text
AGENTS.md
.github/copilot-instructions.md
.github/instructions/tests.instructions.md
.agentic/setup/instructions-state.json
```

### Inputs To Collect

Ask these questions:

1. What is the product and what does it do?
2. How are tests run?
3. How is the project built?
4. How is the app run or served locally, if applicable?
5. How does a developer verify a change works (manual smoke check or steps)?
6. What should agents know about CI?
7. What complex modules exist?
8. Are there other repositories related to this product? If yes, briefly explain each repo and when agents should consider it.
9. What branch naming style should agents follow?
10. What commit message style should agents follow?
11. Are there files, directories, or changes agents must not touch without approval?

Questions 2–5 (build / test / run / verify) feed the smoke-verify in the
completion criteria — the flow runs build and test once to confirm the captured
commands actually work.

Only ask follow-up questions when the answer is incomplete or has direct setup consequences. Related repositories and product purpose are the most likely answers to need follow-up.

### Root AGENTS.md Template

````md
# AGENTS.md

## Product

<product description>

## Repository Context

- This repository is: <main repo / part of multi-repo system>.

## Workspace & Dependencies

- `<../dep-path>` — **editable** (we own it; functionally part of this
  application). May be changed as part of work here; follow its own `AGENTS.md`;
  changes reach this repo via <link / version bump / rebuild>. Also listed in
  `.agentic/hooks/editable-paths.txt` so the boundary guard permits edits.
- `<../other-dep>` — **read-only reference** (another team's code). Consult it
  to understand behavior (its Graphifyy graph first, code when needed); never
  edit; a needed change there is an external dependency to raise with its
  owners, not a story.

## Stack

<auto-detected stack summary, with user corrections if needed>

## Build

Run:

```bash
<build command>
```

Notes:

- <build caveats, if any>

## Tests

Run:

```bash
<test command>
```

Notes:

- <test caveats, if any>

## Run

How to run or serve the app locally:

```bash
<run command, or "not applicable (library/service with no local run)">
```

## Verify a Change

How to confirm a change works before declaring done:

- <manual smoke steps, or the command/flow a developer uses to verify>

## CI

- CI system: <CI info>
- Important checks: <checks>
- If CI fails: <where/how to inspect failures, if known>

## Complex Modules

The following modules need scoped setup:

- `<path>`: <short purpose/status>

Each complex module should get a nested `AGENTS.md` through `init module <path>`.

## Git Workflow

- Branch naming: `<branch style>`
- Commit style: `<commit style>`

## Agent Rules

- Keep changes scoped to the requested task.
- Prefer existing patterns in the touched area.
- Run the relevant build or test command before reporting done when feasible.
- If validation cannot be run, explain why.
- Do not overwrite existing instructions or workflow files without user approval.
- Do not edit restricted areas without approval: <restricted areas or "none declared">
````

### Copilot Instructions Template

````md
# GitHub Copilot Instructions

Use the repository-wide instructions in `AGENTS.md` as the source of truth.

Also apply path-specific instructions in `.github/instructions/` and any nested `AGENTS.md` files in the area being modified.

When instructions conflict, prefer the most specific instruction for the files being changed.
````

### Test Instructions Template

````md
---
applyTo: "**/*test*,**/*spec*,**/tests/**,**/test/**"
---

# Test Instructions

- Use the existing test framework and patterns in the nearest test folder.
- Run the relevant test command before reporting test-related work done:

```bash
<test command>
```

- Add or update regression tests for bug fixes when practical.
- Prefer behavior-focused tests over implementation-detail tests.
- Do not delete or weaken tests without explicit approval.
````

### Root Completion Criteria

`setup-instructions` is complete when:

- root `AGENTS.md` exists and contains product, build, test, run, verify, CI, module, repo, branch, commit, and safety guidance;
- `.github/copilot-instructions.md` exists and points to the canonical instructions;
- `.github/instructions/tests.instructions.md` exists and includes the test command;
- **smoke-verify has run**: the captured build and test commands were executed once and passed (or were recorded as `blocked` with a reason — air-gapped, missing deps, long-running — never silently skipped). This is what makes the agent's run/verify loop trustworthy;
- `.agentic/setup/instructions-state.json` records answers, generated files, pending complex modules, and the smoke-verify result;
- existing instruction files were merged per the section-aware policy, not overwritten.

## Phase 2: Complex Module Instruction Setup

Commands (sub-actions of the `setup-instructions` skill):

```text
/setup-instructions module <path>
/setup-instructions module all
```

Creates or updates:

```text
<complex-module>/AGENTS.md
.agentic/setup/modules/<module-id>.json
```

### Inputs To Collect Per Module

Ask these questions:

1. What is this module responsible for?
2. What should this module not be responsible for?
3. How do you test or build this module specifically, if different from the root commands?
4. What are the main entry points or important files?
5. What patterns should agents follow here?
6. What are common pitfalls or risky areas?
7. Are there module-specific restricted files or changes?

### Module AGENTS.md Template

````md
# AGENTS.md - <Module Name>

## Module Purpose

<what this module is responsible for>

## Boundaries

This module should not handle:

- <non-responsibility>

## Important Files

- `<path>`: <purpose>
- `<path>`: <purpose>

## Local Commands

Use root commands unless noted otherwise.

- Build/check: `<command or "same as root">`
- Test: `<command or "same as root">`

## Module Rules

- <pattern/rule>
- <pattern/rule>

## Risks and Pitfalls

- <pitfall>
- <risky area>

## Agent Guidance

- Prefer patterns already used in this module.
- Keep changes inside this module unless the task explicitly requires cross-module work.
- If a change affects public contracts used elsewhere, call that out before implementation.
- Do not edit restricted module areas without approval: <restricted areas or "none declared">
````

### Module Completion Criteria

A module is complete when:

- `<module>/AGENTS.md` exists;
- the file documents purpose, boundaries, commands, patterns, risks, and restrictions;
- `.agentic/setup/modules/<module-id>.json` records the module status as complete;
- the root instruction state no longer marks that module as pending.

## Status And Help Behavior

`init help` and `init status` should report instruction setup like this:

```text
Instruction files:
- Root AGENTS.md: complete
- Copilot instructions: complete
- Test instructions: complete
- Complex modules:
  - frontend: complete
  - backend/payment: pending
  - backend/auth: pending

Recommended next step:
- run init module backend/payment
```

If root instructions are missing, the recommended next step is `init instructions`.

If root instructions are complete but at least one complex module is pending, recommend the next pending `init module <path>` command.

If all instruction files are complete, mark the instruction-files topic as complete and recommend the next initialization topic.
