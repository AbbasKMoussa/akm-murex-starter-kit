# Initialization Topic: Skills

`/setup-skills` is the third mandatory topic. The installer already places the
fixed 19-skill catalog; this topic verifies integrity and live discovery. It is
also reached through `/akmaestro-init`.

## Bundled catalog

- Shared: `status`.
- Stage 1/helpers: `akmaestro-init`, `setup-instructions`, `setup-tooling`,
  `setup-skills`, `setup-hooks`, `teach`, `doctor`.
- Stage 2: `feature`, `feature-understand`, `feature-frame`, `feature-split`,
  `story-prime`, `story-plan`, `story-implement`, `story-review`, `story-learn`,
  `feature-review`, `feature-retro`.

There is no deferred or optional catalog. Additional team-owned skills are
preserved and reported; they are never overwritten or removed by this topic.

## Validation

For each bundled skill:

1. require `.github/skills/<name>/SKILL.md`;
2. validate lowercase-hyphen `name` frontmatter and non-empty `description`;
3. verify bundled relative resources;
4. detect reserved-name collisions;
5. record discovery as `verified`, `blocked`, or `not_tested` independently for
   Copilot CLI and VS Code.

Missing kit assets are repaired with `akmaestro update`. An existing customized
or same-named file requires a reviewed diff and confirmation.

## Strict evidence

`evidence-write skills` accepts exactly:

- `kitVersion`;
- `expectedSkills`, containing the complete bundled catalog;
- `verifiedSkills`;
- `collisions`;
- `discovery.copilotCli` and `discovery.vsCode`;
- `newSessionRequired`;
- `blockers`.

The topic completes only when every bundled skill is verified, collisions are
empty, and at least one Copilot surface has live discovery marked `verified`.
A repairable missing/invalid asset remains `in_progress`; use `blocked` only for
a real policy or environment restriction.

Request a new session only if an update changed skills and the current surface
cannot observe them. Persist evidence first and resume with `/akmaestro-init`.
