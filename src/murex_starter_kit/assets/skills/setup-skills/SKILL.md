---
name: setup-skills
description: >-
  Install the kit's agent skills into this repository's .github/skills/ and
  verify they are valid and discoverable. Use for "/setup-skills", "install the
  skills", or the skills step of /init.
allowed-tools:
  - shell
---

# setup-skills — install agent skills

Install the curated skills into `.github/skills/` so the team gets reusable
workflows, invokable as `/<name>` on every Copilot surface.

## Verify kit flow-skills

Confirm the flow-skills and helpers are present and valid:
`init`, `setup-instructions`, `setup-tooling`, `setup-skills`, `setup-hooks`,
`doctor`. Missing/invalid → report and re-run the installer.

## Catalog

Present the catalog with one line each and let the user accept the recommended
set or pick a subset. Current catalog:

- `teach` — routes and refines agent instructions: decides where a lesson belongs
  (root `AGENTS.md`, a module `AGENTS.md`, a path-scoped instructions file, or
  personal user-level config) and refines the wording before adding it.

(Feature-implementation skills are added later by Stage 2, not here.)

## Install

For each selected skill, ensure `.github/skills/<name>/` exists with its
`SKILL.md` and bundled files (the installer copies them; this step verifies and,
if missing, restores from the kit). If a skill of the same name already exists
and the user customized it, do **not** overwrite — show the difference and let
the user decide.

## Validate

Each `SKILL.md` has valid frontmatter: `name` (lowercase letters/numbers/hyphens)
and a non-empty `description` (what it does and when to use it). Bundled files
referenced by relative path exist. Discovery is automatic from the description;
a newly added skill is only visible in a **new** session.

## New session

After adding skills, ask the user to open a new Copilot session so `/<name>`
invocation is available, then confirm with `init status` or `init help`.

## State

`.agentic/setup/skills-state.json`: catalog version; selected skills + installed
paths; per-skill validation (frontmatter, resources); kit flow-skills present;
new-session requested; overall status.

## Completion

Complete when the kit flow-skills are present/valid, every selected catalog skill
is installed with valid `SKILL.md` and intact resources, nothing was overwritten
without confirmation, a new session was requested if skills were added in an
existing session, and state records the results.
