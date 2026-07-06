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
2. From then on, a developer opens Copilot (VS Code or CLI) and says "Let's run the initialization flow" (or uses `/init` in VS Code, the `init` agent in the CLI).
3. The agent runs a guided setup flow, possibly across multiple sessions.
4. The repository ends with agentic coding support installed and configured.

## Current Direction

The setup flow should be dynamic, not a blind file copy. It should:

- inspect the target repository;
- ask the user targeted questions;
- persist answers and setup state on disk;
- install relevant skills, prompts, agents, hooks, and instruction files;
- generate repo-specific agent instructions from detected facts and user answers;
- validate the result;
- produce a clear final setup summary.

The architecture is a one-time installer plus repo-local installed assets (BMAD-style):

- the installer is a Python CLI run via `uvx akmaestro init` (source of truth in an internal git repo, published to the internal Python registry); it is the bootstrap and lays down the in-agent flow;
- repo-local files such as `.github/copilot-instructions.md`, `AGENTS.md`, `.github/instructions/`, `.github/skills/` (agent skills, including the kit's own flows like `init`), optional `.github/hooks/`, and `.agentic/` state files.

The kit's universal mechanism is **agent skills** (`.github/skills/<name>/SKILL.md`), an open standard that works identically in VS Code Copilot, Copilot CLI, and the cloud agent. The kit's flows ship as skills (so `/init` and natural language both work on every surface), and setup also installs a curated catalog of reusable skills for daily team use. See decisions 11–12 in `docs/setup-flow-decisions.md`.

## Important Notes

- Hooks are useful but should be treated carefully because VS Code agent hooks are still preview functionality and may be disabled by organization policy.
- The setup flow should never overwrite existing instructions, prompts, hooks, or agent files without confirmation. New files may be created directly.

See `docs/setup-flow.md` for the integrated Stage 1 spec (orchestrator, bootstrap, detection, state, merge policy, status/help) and `docs/setup-flow-decisions.md` for the decision log and open questions.

Agreed initialization topics:

- `docs/init-topics/instruction-files.md`
- `docs/init-topics/tooling.md`
- `docs/init-topics/skills.md`
- `docs/init-topics/hooks.md`

## Implementation status

Stage 1 is implemented in `src/akmaestro/`: a thin Python installer
(`cli.py` + `installer.py`, commands `init` and `update` — `update` refreshes
kit-owned files via the sha256 manifest in `.agentic/setup/kit-manifest.json`
and never touches customized files) plus the installable assets under `assets/` — the
seven skills (`init`, `setup-instructions`, `setup-tooling`, `setup-skills`,
`setup-hooks`, `teach`, `doctor`), the hooks, and bootstrap templates. The
installer is tested (`tests/test_installer.py`, run by CI on Linux + Windows via
`.github/workflows/ci.yml`; `uv run pytest` locally) and the wheel bundles the
assets (CI verifies all 18 skills + hooks land in it). Note:
`.github/skills/{teach,doctor}`, `.github/hooks/`, and `.agentic/hooks/` at the
repo root are the original dogfood copies and duplicate `assets/`; the canonical
source is `assets/`, and a test fails if the copies drift — change `assets/`
first, then sync the root copies. Not yet done: end-to-end run of `/init` in a real
Copilot session, hook live-CLI/PowerShell verification, and registry publish.

Stage 2 (feature flow) is implemented as 11 skills under `assets/skills/`:
`feature` (orchestrator), `feature-understand`, `feature-frame`, `feature-split`,
the five `story-*` loop steps, `feature-review`, and `feature-retro`. They install
via the same thin installer (verified: all 18 skills bundle and install). Design
lives in `docs/feature-flow.md` + `docs/feature-phases/`. Not yet done: end-to-end
run in a real Copilot session (the skill procedures are unproven live, including
orchestrator→step delegation and the autonomous-mode internal loop). These Stage 2
skills exist only in `assets/` (no root dogfood copies, avoiding the Stage 1
duplication).
