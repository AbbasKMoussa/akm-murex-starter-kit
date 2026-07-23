# Initialization Topic: Instruction Files

This topic defines what it means to initialize agent instruction files for a target repository.

## Goal

Create properly scoped instruction files so agents understand:

- what the product does;
- how to bootstrap, build, test, run, and verify the repo;
- CI expectations;
- complex modules that need their own local guidance;
- related repositories;
- Git workflow conventions and explicit absences;
- repo-specific safety boundaries.

The setup should detect facts with provenance, present one compact confirmation
summary, and ask only targeted follow-ups. Avoid long interviews that busy
developers will not complete.

## Agreed File Model

Generate or update these files:

```text
AGENTS.md
.github/copilot-instructions.md
.github/instructions/tests.instructions.md
.github/instructions/<module-id>.instructions.md
```

`AGENTS.md` is the main source of truth.

`.github/copilot-instructions.md` should stay short and direct Copilot to
`AGENTS.md` and `.github/instructions/`. Avoid duplicating the full root
instructions because duplicated instruction sources can conflict.

`.github/instructions/tests.instructions.md` contains test-specific guidance using path-scoped instructions.

Path-scoped module files are generated later for complex modules and describe
only what differs from root guidance. A nested module `AGENTS.md` is generated
only when the lead explicitly requests cross-agent portability.

## Phase 1: Root Instruction Setup

Command:

```text
/setup-instructions
```

(Also reachable through the guided `/akmaestro-init`. See `docs/setup-flow.md`.)

Creates or updates:

```text
AGENTS.md
.github/copilot-instructions.md
.github/instructions/tests.instructions.md
.agentic/setup/instructions-state.json   # controller-written evidence
```

### Detect, Then Confirm

Inspect README/package/product documentation for purpose; CI, manifests,
task runners, lockfiles, and contribution docs for commands; and contribution
docs, repository configuration, pull-request templates, plus recent history for
Git conventions. Record sources and confidence. The current branch and one
developer's local environment are not team policy.

Present one confirmation summary covering:

1. product summary, consumers, and primary workflows;
2. bootstrap, build, test, lint, typecheck, run, and automated verification;
3. manual verification steps, ensuring at least one verification path exists;
4. base branch, branch naming, commit style, direct-push, pull-request, signing,
   and ticket-reference policies;
5. CI, complex modules, sibling repositories, and restricted areas.

Only follow up where the proposed answer is incomplete or ambiguous. Never
invent a command or Git policy. Commands must be explicitly `configured` or
`not_applicable`; policies must be `defined`, `none`, or `unspecified`. Every
negative disposition requires a reason.

Before a bootstrap or other machine-changing action, show the structured action
and obtain confirmation. Check finite actions through controller `action-check`,
which uses an argument array, no shell, a relative working directory, and a
timeout. Preserve its controller-issued check ID, action hash, and timestamp in
evidence; every passing
command result needs a matching passing check for each configured action.
Build, test, lint, typecheck, and automated verification must pass or have a
genuine environmental blocker. A long-running server may be documented or
verified through a bounded startup and health check.

### Root AGENTS.md Template

````md
# AGENTS.md

## Product

<product description>

## Repository Context

- This repository is: <main repo / part of multi-repo system>.

## Workspace & Dependencies

- `<../sibling-path>` — **modifiable sibling repository** (we own it;
  functionally part of this application). May be changed as part of work here;
  follow its own `AGENTS.md`; changes reach this repo via <link / version bump /
  rebuild>. Also listed in the compatibility file
  `.agentic/hooks/editable-paths.txt` so the boundary guard permits edits.
- `<../other-sibling>` — **read-only sibling repository** (another team's code).
  Consult it to understand behavior (its Graphifyy graph first, code when
  needed); never edit it. A needed change there is an external dependency to
  raise with its owners, not a story.

## Stack

<auto-detected stack summary, with user corrections if needed>

## Setup

Run the confirmed dependency/bootstrap actions, or state why setup is not
applicable.

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

Each complex module should get a scoped `.instructions.md` file through
`/setup-instructions module <path>`.

## Git Workflow

- Base branch: `<base branch>`
- Branch naming: `<branch style>`
- Commit style: `<commit style>`
- Direct pushes: `<allowed / prohibited / unspecified with reason>`
- Pull requests: `<requirements or none>`
- Commit signing: `<requirements or none>`
- Ticket references: `<requirements or none>`

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

Also apply path-specific instructions in `.github/instructions/`.

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

- root `AGENTS.md` exists without bootstrap placeholders and contains product,
  setup, build, test, run, verify, CI, module, workspace, Git, and safety guidance;
- `.github/copilot-instructions.md` exists and points to the canonical instructions;
- `.github/instructions/tests.instructions.md` exists and includes the test command;
- every canonical command is configured or explicitly not applicable;
- configured finite checks passed or have a genuine `blocked` result, while
  bootstrap/run may be documented when execution is inappropriate;
- at least one automated or manual verification path exists;
- all six Git policies are defined, absent, or unspecified explicitly;
- `.agentic/setup/instructions-state.json` records controller-written evidence
  for product, commands/results, verification, Git workflow, repository context,
  generated files, and pending modules;
- after evidence is written, the controller makes the authoritative topic
  transition to `complete` or documented `blocked`;
- existing instruction files were merged per the section-aware policy, not overwritten.

## Phase 2: Complex Module Instruction Setup

Commands (sub-actions of the `setup-instructions` skill):

```text
/setup-instructions module <path>
/setup-instructions module all
```

Creates or updates:

```text
.github/instructions/<module-id>.instructions.md
```

The file requires YAML frontmatter with an `applyTo` glob scoped to the module.
Its body covers purpose, boundaries, differing commands, important paths,
patterns, pitfalls, and restrictions. Detect these first and present one compact
draft; ask only about missing or conflicting facts.

If the lead explicitly requests a cross-agent instruction file, create
`<module>/AGENTS.md` instead of or alongside the scoped GitHub instruction file.
Existing files still use the reviewed merge protocol.

### Module Completion Criteria

A module is complete when:

- the confirmed scoped instruction artifact exists with valid `applyTo`;
- the file documents purpose, boundaries, commands, patterns, risks, and restrictions;
- a new instructions evidence revision removes the module from `pendingModules`.

There is no second module-status file.

## Status And Help Behavior

`/akmaestro-init help` and `/akmaestro-init status` should report instruction setup like this:

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
- run /setup-instructions module backend/payment
```

If root instructions are missing, the recommended next step is
`/setup-instructions`.

If root instructions are complete but at least one complex module is pending,
recommend the next `/setup-instructions module <path>` command.

If all instruction files are complete, mark the instruction-files topic as complete and recommend the next initialization topic.
