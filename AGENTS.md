# AKMaestro Project Context

This repository builds **AKMaestro** ("conduct your agentic coding") — a Murex-internal kit for helping teams adopt agentic coding workflows in their existing repositories.

## Collaboration Rule

- Do not start implementation work without first discussing the plan with the user.
- Prefer short, explicit plans before creating, editing, deleting, or reorganizing files.
- Let the user guide the conversation step by step.

## Product Goal

Target surfaces are GitHub Copilot only: VS Code and the Copilot CLI. Both read the same `.github/` asset set.

The desired user experience is:

1. A team lead runs the one-time installer in an existing repository (`uvx akmaestro init`).
2. The team lead opens Copilot and runs `/init`, possibly across multiple sessions,
   then commits the initialized repository assets.
3. Every developer pulls those assets and starts directly with `/feature`.
4. `/feature` verifies that developer's local tools and offers confirmed
   remediation without rerunning repository initialization.

## Current Direction

The setup flow should be dynamic, not a blind file copy. It should:

- inspect the target repository;
- ask the user targeted questions;
- persist shared answers/setup state and separate developer-local readiness;
- configure the bootstrapped skills, hooks, and instruction files;
- generate repo-specific agent instructions from detected facts and user answers;
- validate the result;
- produce a clear final setup summary.

The architecture is a one-time installer plus repo-local installed assets (BMAD-style):

- the installer is a Python CLI run via `uvx akmaestro init` (source of truth in
  an internal git repo, intended for publication to the internal Python
  registry); it is the bootstrap and lays down the in-agent flow;
- repo-local files such as `.github/copilot-instructions.md`, `AGENTS.md`, `.github/instructions/`, `.github/skills/` (agent skills, including the kit's own flows like `init`), optional `.github/hooks/`, and `.agentic/` state files.
- a bundled, standard-library state controller under `.agentic/bin/`, invoked
  through `uv`, with versioned schemas and atomic legal transitions.

The kit's universal mechanism is **agent skills** (`.github/skills/<name>/SKILL.md`), an open standard that works identically in VS Code Copilot, Copilot CLI, and the cloud agent. The bootstrap installs all 18 Stage 1 and Stage 2 skills up front, so `/init`, `/feature`, and natural-language routing work on every surface. See decisions 11–12 in `docs/setup-flow-decisions.md`.

## Important Notes

- Hooks are useful but should be treated carefully because VS Code agent hooks are still preview functionality and may be disabled by organization policy.
- The setup flow should never overwrite existing instructions, skills, or hooks without confirmation. New files may be created directly.
- A local sibling repository is either **modifiable** (the team owns it and the agent may change it) or **read-only** (consult it, never edit it).

See `docs/setup-flow.md` for the integrated Stage 1 spec (orchestrator,
bootstrap, detection, state, merge policy, status/help) and
`docs/setup-flow-decisions.md` for the decision log.

Agreed initialization topics:

- `docs/init-topics/instruction-files.md`
- `docs/init-topics/tooling.md`
- `docs/init-topics/skills.md`
- `docs/init-topics/hooks.md`

## Implementation status

Stage 1 is implemented in `src/akmaestro/`: a Python installer
(`cli.py` + `installer.py`, commands `init` and `update` — `update` refreshes
kit-owned files via the sha256 manifest in `.agentic/setup/kit-manifest.json`
and never touches customized files), the repo-local deterministic state
controller (`state.py`), and installable assets under `assets/`: all 18 skills,
state schemas/protocol, hooks, and bootstrap templates. The installer/controller
are tested (`tests/test_installer.py`, `tests/test_state.py`, run by CI on Linux + Windows via
`.github/workflows/ci.yml`; `uv run pytest` locally) and the wheel bundles the
assets (CI verifies all 18 skills + hooks land in it). Note:
`.github/skills/{teach,doctor}`, `.github/hooks/`, and `.agentic/hooks/` at the
repo root are the original dogfood copies and duplicate `assets/`; the canonical
source is `assets/`, and a test fails if the copies drift — change `assets/`
first, then sync the root copies.

Stage 2 (feature flow) is implemented as 11 skills under `assets/skills/`:
`feature` (orchestrator), `feature-understand`, `feature-frame`, `feature-split`,
the five `story-*` loop steps, `feature-review`, and `feature-retro`. They install
via the same asset installer (verified: all 18 skills bundle and install). Design
uses controller-enforced v2 transitions and lives in `docs/feature-flow.md` plus
`docs/feature-phases/`. These Stage 2 skills exist only in `assets/` (no root
dogfood copies, avoiding the Stage 1 duplication).

Remaining release work: run the revised `/init` and `/feature` flows end to end
in real Copilot CLI and VS Code sessions, verify local remediation and
interruption recovery, re-confirm live hooks on each surface, exercise the
multi-repo boundary, and publish to the internal registry.
