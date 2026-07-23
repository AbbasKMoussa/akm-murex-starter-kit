---
name: setup-skills
description: >-
  Verify the complete agent-skill set bootstrapped into this repository's
  .github/skills/. Use for "/setup-skills", "check the installed skills", or the
  skills step of /akmaestro-init.
---

# setup-skills — verify agent skills

The `akmaestro init` CLI bootstrap installs all 19 bundled skills into
`.github/skills/` before this flow starts. Verify that complete set so
`/status`, `/akmaestro-init`, and `/feature`
are available on every Copilot surface.

## State protocol

Read `.agentic/STATE-PROTOCOL.md`. Run `setup-init` and `setup-status` through
the bundled controller. If this topic is not already `in_progress`, transition
`skills` to `in_progress` with the revision just read. Never edit aggregate
setup state directly.

## Required bundled set

Confirm all bundled skills are present and valid:

- Shared helper: `status`.
- Stage 1: `akmaestro-init`, `setup-instructions`, `setup-tooling`, `setup-skills`,
  `setup-hooks`, `teach`, `doctor`.
- Stage 2: `feature`, `feature-understand`, `feature-frame`, `feature-split`,
  `story-prime`, `story-plan`, `story-implement`, `story-review`, `story-learn`,
  `feature-review`, `feature-retro`.

Missing bundled skill → report it and recommend `akmaestro update` (or
`akmaestro init` for a fresh bootstrap). A same-named customized skill is never
overwritten without confirmation.

## Additional team skills

Preserve and validate any non-bundled skills already present. They are
team-owned; do not overwrite or remove them. Report an invalid additional skill
as a warning, but do not let it block the required bundled set.

There is no separate optional catalog. The full AKMaestro capability set is part
of the bootstrap by design.

## Validate

Each `SKILL.md` has valid frontmatter: `name` (lowercase letters/numbers/hyphens)
and a non-empty `description` (what it does and when to use it). Bundled files
referenced by relative path exist. Discovery is automatic from the description;
a newly added skill is only visible in a **new** session.

## New session

The lead already opens a fresh session after the CLI bootstrap. Request another
session only if an update added or repaired a skill during this running session
and the current surface cannot observe it. Persist evidence first and resume only
with `/akmaestro-init`; otherwise return directly to the orchestrator.

## State

Create local JSON evidence containing the kit version, all 19 bundled skill
paths, additional team skills, per-skill validation, and new-session result.
Write it atomically with `evidence-write skills`; this produces committed
`.agentic/setup/skills-state.json` without a duplicate topic status.

Use exactly this evidence shape. `expectedSkills` and `verifiedSkills` must each
contain the full catalog listed above when complete:

```json
{
  "kitVersion": "<installed version>",
  "expectedSkills": ["status", "akmaestro-init", "setup-instructions", "setup-tooling", "setup-skills", "setup-hooks", "teach", "doctor", "feature", "feature-understand", "feature-frame", "feature-split", "story-prime", "story-plan", "story-implement", "story-review", "story-learn", "feature-review", "feature-retro"],
  "verifiedSkills": ["status", "akmaestro-init", "setup-instructions", "setup-tooling", "setup-skills", "setup-hooks", "teach", "doctor", "feature", "feature-understand", "feature-frame", "feature-split", "story-prime", "story-plan", "story-implement", "story-review", "story-learn", "feature-review", "feature-retro"],
  "collisions": [],
  "discovery": {"copilotCli": "verified", "vsCode": "not_tested"},
  "newSessionRequired": false,
  "blockers": []
}
```

## Completion

Complete when all 19 bundled skills are present with valid `SKILL.md` files and
intact resources, additional team skills were preserved, nothing was overwritten
without confirmation, a new session was requested if skills were added in an
existing session, and state records the results.

A missing or invalid bundled skill leaves this topic `in_progress`. Use
`blocked` only when a real environment or policy constraint prevents repair and
the manual steps are recorded.

Write evidence first. Then transition `skills` from `in_progress` to `complete`,
or to `blocked --reason <reason>` for a genuine blocker, using the latest
aggregate `--expected-revision`. Rerun `setup-status` and report its derived next
command. The only cross-session resume command is `/akmaestro-init`.
