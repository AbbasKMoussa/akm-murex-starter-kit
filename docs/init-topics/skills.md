# Initialization Topic: Skills

This topic defines the third setup step for a target repository: validating the
agent skills installed by the bootstrap.

## Goal

Verify the complete bundled GitHub agent-skill set so Stage 1, Stage 2, and the
daily helpers are available on every Copilot surface (VS Code, CLI, cloud agent).

Skills are the kit's universal delivery and trigger mechanism. The format and
locations are fixed by decisions 11–12 and the "GitHub Copilot Agent Skills"
section in `docs/setup-flow-decisions.md`; in short: a skill is a folder under
`.github/skills/<name>/` containing `SKILL.md` (YAML frontmatter with `name` and
`description`, optional `allowed-tools`) plus any bundled resources, discovered
automatically or invoked as `/<name>`.

## Bundled Skill Set

`uvx akmaestro init` lays down all 18 skills before the conversational `/init`
flow runs:

- **Stage 1 and helpers (7):** `init`, `setup-instructions`, `setup-tooling`,
  `setup-skills`, `setup-hooks`, `teach`, `doctor`.
- **Stage 2 (11):** `feature`, `feature-understand`, `feature-frame`,
  `feature-split`, `story-prime`, `story-plan`, `story-implement`,
  `story-review`, `story-learn`, `feature-review`, `feature-retro`.

This topic verifies them; it does not defer Stage 2 installation or ask the user
to choose a subset. Non-bundled skills already in the repository are team-owned
and must be preserved. Invalid additional skills are warnings; they do not block
the required bundled set.

## Command

```text
/setup-skills
```

(Also reachable through the guided `/init`. See `docs/setup-flow.md`.)

## Inputs To Collect

None. The bundled set is fixed by the installed kit version. Report additional
team-owned skills, but do not ask the user to select or remove them.

## Verification Behavior

For every bundled skill:

- Confirm `.github/skills/<name>/SKILL.md` exists. If a bundled skill is missing,
  recommend `akmaestro update` (or `akmaestro init` for a fresh bootstrap).
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

If the bootstrap or an update added skills during the current session, ask the
user to open a new Copilot session at the repository root so they are discovered.
The new session can run:

```text
/setup-skills
```

or:

```text
init help
```

to confirm the skills are loaded.

## Evidence

Write evidence through the controller to:

```text
.agentic/setup/skills-state.json
```

The evidence should include:

- the kit version installed from;
- the 18 required bundled skills and their installed paths;
- additional team-owned skills found;
- per-skill validation result (frontmatter valid, resources present);
- complete bundled set present (yes/no);
- whether a new session was requested;

The authoritative topic status exists only in
`initialization-state.json`. Write evidence first, then make the controller
transition last.

## Completion Criteria

`/setup-skills` is complete only when:

- all 18 bundled skills are installed under `.github/skills/<name>/` with valid
  `SKILL.md` frontmatter and intact bundled resources;
- additional team-owned skills were preserved;
- no existing skill was overwritten without confirmation;
- a new session has been requested if skills were added in an existing session;
- `.agentic/setup/skills-state.json` records the successful results.

If a bundled skill is missing, invalid, or unverified, the topic remains
`in_progress`.
Use `blocked` only when a real environment or policy constraint prevents repair
and the manual steps are recorded.

## Status And Help Behavior

`init help` and `init status` should report skills setup like this:

```text
Skills:
- Bundled skills: 18/18 valid
- Additional team skills: <count>

Recommended next step:
- open a new Copilot session at the repo root and run init help
```

If a bundled skill is missing, recommend `akmaestro update`.

If all three mandatory topics (instruction files, tooling, skills) are complete
or blocked with a recorded environmental reason, mark setup complete and
recommend starting `/feature`.
