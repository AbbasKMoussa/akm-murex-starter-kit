# Initialization Topic: Skills

This topic defines the third setup step for a target repository: installing the
agent skills the team will use.

## Goal

Install a curated catalog of GitHub agent skills into the repository so the team
gets reusable, best-practice workflows out of the box, invokable on every Copilot
surface (VS Code, CLI, cloud agent).

Skills are the kit's universal delivery and trigger mechanism. The format and
locations are fixed by decisions 11–12 and the "GitHub Copilot Agent Skills"
section in `docs/setup-flow-decisions.md`; in short: a skill is a folder under
`.github/skills/<name>/` containing `SKILL.md` (YAML frontmatter with `name` and
`description`, optional `allowed-tools`) plus any bundled resources, discovered
automatically or invoked as `/<name>`.

## Two Kinds of Skill

1. **Kit flow-skills** — the kit's own flows delivered as skills so the guided
   flow works the same on every surface. Current flow-skills: `init` (the guided
   orchestrator), the four per-topic skills `setup-instructions`, `setup-tooling`,
   `setup-skills`, `setup-hooks`, and `doctor`
   (`.github/skills/doctor/SKILL.md`, a read-only health check with an opt-in
   `--fix` mode). These are laid down by the installer
   (`uvx akmaestro init`) as part of the bootstrap,
   *before* this topic runs, because the flow must exist for the flow to run.
   This topic only verifies they are present and valid.

2. **Catalog skills** — reusable, daily-use skills installed for the team. This
   topic installs the ones the team selects.

### Current Catalog

- `teach` — routes and refines agent instructions: decides where a lesson, rule,
  convention, or fact belongs (root `AGENTS.md`, a module `AGENTS.md`, a
  path-scoped `.github/instructions/*.instructions.md`, or personal user-level
  config) and refines its wording before adding it. Source:
  `.github/skills/teach/SKILL.md`.

Feature-implementation skills (a BMAD-like idea → spec → stories → implement →
review flow) are **out of scope here** and are added by the later feature flow
("part 2"), not by setup.

## Command

```text
/setup-skills
```

(Also reachable through the guided `/init`. See `docs/setup-flow.md`.)

## Inputs To Collect

Keep this short. Ask one question:

```text
Which catalog skills should I install? (default: all recommended)
```

Present the current catalog with a one-line description each and let the user
accept the recommended set or pick a subset. Do not run a long interview.

## Install Behavior

For each selected skill:

- Copy the skill folder to `.github/skills/<name>/` (create `.github/skills/` if
  missing). New skill folders are created directly.
- If a skill of the same name already exists, do not overwrite or downgrade it
  without confirmation. Show what differs and let the user decide (per decision
  6).
- Preserve bundled resources and relative-path references inside the skill.

## Validation

A skill is only "installed" when it is valid and discoverable:

- `SKILL.md` exists with required frontmatter — `name` (lowercase letters,
  numbers, hyphens) and a `description` that states what it does and when to use
  it.
- Bundled files referenced by the skill exist at their relative paths.
- The skill is discoverable by Copilot. Discovery is automatic from the
  description, but a session that was already open will not see newly added
  skills, so a new session is usually required to confirm (see below).

## New Session Requirement

After installing skills, ask the user to open a new Copilot session at the
repository root so newly added skills are discovered and `/<name>` invocation is
available. The new session can run:

```text
setup skills
```

or:

```text
init help
```

to confirm the skills are loaded.

## State File

Record status in:

```text
.agentic/setup/skills-state.json
```

The state should include:

- the catalog version installed from;
- selected skills and their installed paths;
- per-skill validation result (frontmatter valid, resources present);
- kit flow-skills present (yes/no);
- whether a new session was requested;
- overall status.

## Completion Criteria

`setup skills` is complete only when:

- the kit flow-skills are present and valid;
- every selected catalog skill is installed under `.github/skills/<name>/` with
  valid `SKILL.md` frontmatter and intact bundled resources;
- no existing skill was overwritten without confirmation;
- a new session has been requested if skills were added in an existing session;
- `.agentic/setup/skills-state.json` records the successful results.

If a selected skill is missing, invalid, or unverified, the topic is partial or
blocked, not complete.

## Status And Help Behavior

`init help` and `init status` should report skills setup like this:

```text
Skills:
- Kit flow-skills: present
- Catalog:
  - teach: installed

Recommended next step:
- open a new Copilot session at the repo root and run init help
```

If the kit flow-skills are missing, recommend re-running the installer.

If catalog skills are selected but not yet installed or validated, recommend
completing `setup skills`.

If all three initialization topics (instruction files, tooling, skills) are
complete, mark setup as complete and recommend starting the feature flow once it
exists.
