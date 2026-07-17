---
name: init
description: >-
  One-time, team-lead-owned repository initialization for agentic coding. Use
  when the user says "let's run the initialization flow", "/init", "set up this
  repo for agentic coding", "init status", or "init help". Orchestrates the
  four setup topics, persists shared repository state, and writes the team guide.
allowed-tools:
  - shell
---

# init - repository initialization orchestrator

Run Stage 1 once for the repository. The **team lead** owns this flow and commits
its output. Other developers pull that committed initialization and start with
`/feature`; they do not rerun `/init` for their workstation.

Mandatory topics: instructions, tooling, and skills. Hooks are optional.
Mandatory topics may finish `blocked` only for a recorded environment or policy
reason. Existing files remain non-destructive: show and confirm every merge or
replacement; create absent files directly.

## Controller

Read `.agentic/STATE-PROTOCOL.md`, then use only:

```text
uv run --no-project python .agentic/bin/akmaestro-state.py <command>
```

Never edit `.agentic/setup/initialization-state.json` directly. Its version,
revision, completion, next topic, and legal transitions are controller-owned.

## Subcommands

- `init status`: run `setup-status`, present the four topics, blocker reasons,
  derived overall result, and next command; then stop.
- `init help`: explain the one-time lead-owned flow and `/setup-*` topics; stop.
- Otherwise: initialize or resume the repository flow.

If `setup-status` already reports `complete`, do not restart setup. Explain that
the repository is initialized, recommend `/doctor` for local health, and direct
feature work to `/feature`.

## Procedure

1. Run `setup-init`. If an incompatible pre-release state file exists, stop and
   ask before archiving/removing it; there is no migration because state v1 was
   never shipped.
2. Run `setup-status` and note its revision and derived next topic.
3. Refresh committed `.agentic/setup/detected-repo.json` with **stable repository
   facts only**: languages/frameworks, package managers, build/test/lint/run
   commands, CI, monorepo shape, complex modules, instruction/skill/hook files,
   and declared sibling repositories. Put branch, dirty status, PATH/tool
   availability, and other workstation facts under `.agentic/local/`, never in
   committed detection state.
4. Run topics in controller order. Before delegation, transition the topic from
   `pending`, `complete`, `blocked`, or `skipped` to `in_progress` using the
   revision just read. Delegate to the matching skill:
   - `instructions` -> `/setup-instructions`
   - `tooling` -> `/setup-tooling`
   - `skills` -> `/setup-skills`
   - `hooks` -> `/setup-hooks`, or transition it to `skipped` if declined
5. Each topic writes its evidence first and makes the terminal controller
   transition last. After it returns, rerun `setup-status`; never calculate or
   write the next topic yourself.
6. When the derived overall result is `complete`, generate or update
   `.github/AGENTIC.md` with installed skills, invocation examples, active hooks,
   instruction locations, required developer tools, local-readiness behavior,
   and run/verify commands. Confirm before merging an existing customized file.
7. Run controller `validate`. Resolve errors; report warnings explicitly.
8. Print the handoff and remind the lead to review and commit all shared setup
   assets. Do not commit automatically.

## Status example

```text
Repository initialization
Instructions  complete
Tooling       blocked   Graphifyy registry denied by organization policy
Skills        complete
Hooks         skipped   optional
Overall       complete

Local workstation readiness is separate; /feature checks it for every developer.
```

## Handoff

```text
Repository initialization complete. Mandatory topics are verified or have
documented blockers. Review and commit the shared AKMaestro files.

Developers: pull the commit and run /feature. Do not rerun /init; /feature checks
your local tools and offers confirmed remediation when required.
```
