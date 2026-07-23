---
name: akmaestro-init
description: >-
  One-time, team-lead-owned AKMaestro repository initialization. Use when the
  user says "let's run the initialization flow", "/akmaestro-init", "set up
  this repo for agentic coding", "AKMaestro setup status", or "AKMaestro setup
  help". Orchestrates four setup topics, persists shared state, and finalizes
  the committed team guide. This is distinct from the `akmaestro init` CLI
  command that only installs the bootstrap assets.
---

# akmaestro-init - repository initialization orchestrator

Run Stage 1 once for the repository. The **team lead** owns this flow and commits
its shared output. Other developers pull that commit and start with `/feature`;
they do not rerun repository initialization for their workstation.

The shell command `akmaestro init` installs AKMaestro files. This skill command,
`/akmaestro-init`, detects and configures this repository after installation.

Mandatory topics: instructions, tooling, and skills. Hooks are optional.
Mandatory topics may finish `blocked` only for a recorded environment or policy
reason. Existing files remain non-destructive: show and confirm every merge or
replacement; create absent files directly.

## Controller

Read `.agentic/STATE-PROTOCOL.md`, then use only:

```text
uv run --no-project python .agentic/bin/akmaestro-state.py <command>
```

Never edit controller-owned state or evidence directly. Its version, revision,
completion, finalization, next topic, and legal transitions are controller-owned.

## Subcommands

- `/akmaestro-init status`: run `setup-status`, present finalization, the four
  topics, blocker and pending-item reasons, the derived result, and the exact
  next command; then stop.
- `/akmaestro-init help`: explain the installer-versus-skill distinction, the
  one-time lead-owned flow, its `/setup-*` topics, resumability, and the developer
  handoff; do not inspect state.
- Otherwise: initialize, resume, or safely rerun repository finalization.

If the topics are complete but setup is not finalized, run the finalization
procedure below. If setup is already finalized, report durable blocked/pending
follow-ups, recommend `/doctor` for health, and direct feature work to `/feature`.
Do not restart completed topics automatically.

## Procedure

1. Run `setup-init`. If an incompatible pre-release state file exists, stop and
   ask before archiving/removing it; there is no migration because no earlier
   state contract shipped to users.
2. Run `setup-status` and retain its revision and controller-derived next action.
3. Refresh committed `.agentic/setup/detected-repo.json` with **stable repository
   facts only**: product purpose/consumers/workflows, languages/frameworks,
   package managers, bootstrap/build/test/lint/typecheck/run/verify commands,
   CI, documented Git policies, monorepo shape, complex modules,
   instruction/skill/hook files, and declared sibling repositories. Retain each
   proposal's source and confidence. Put current branch, dirty status, PATH/tool
   availability, and other workstation facts under `.agentic/local/`, never in
   committed detection state or team policy.
4. For the controller's derived next topic, transition it to `in_progress` with
   the revision just read when required. Then **open and follow the installed
   topic skill file directly**; do not rely on implicit skill-to-skill routing:
   - `instructions` -> `.github/skills/setup-instructions/SKILL.md`
   - `tooling` -> `.github/skills/setup-tooling/SKILL.md`
   - `skills` -> `.github/skills/setup-skills/SKILL.md`
   - `hooks` -> `.github/skills/setup-hooks/SKILL.md`, or transition it to
     `skipped` if the lead declines hooks
5. Each topic writes its evidence before its terminal transition. After it
   returns, rerun `setup-status`; never calculate the next topic yourself. Keep
   following installed topic skills in controller order in the same session.
6. Restart only when an installed tool cannot be observed by the current process
   or the current Copilot surface requires a reload. Before stopping, persist all
   evidence and leave the current topic resumable. Print exactly:

   ```text
   Next: open a new Copilot session at the repository root and run /akmaestro-init
   ```

   Do not tell the user to resume with a topic skill, status, or help command.
   Aim for no more than one mid-setup restart.
7. When `setup-status` reports all topics terminal but finalization pending, run:

   ```text
   uv run --no-project python .agentic/bin/akmaestro-state.py setup-finalize --expected-revision <revision>
   ```

   This controller-owned operation is idempotent. It validates topic integrity,
   atomically writes or refreshes `.github/AGENTIC.md` from validated evidence,
   verifies final shared artifacts, and returns the shared/local/blocked/pending
   inventory. If interrupted, rerunning `/akmaestro-init` repeats finalization
   safely. Resolve errors and report warnings explicitly.
   If an existing `.github/AGENTIC.md` is not controller-owned, run
   `setup-finalize --preview --expected-revision <revision>`, show its exact
   returned diff, ask for explicit confirmation, and only then rerun without
   `--preview` and with `--approved-guide-replace`. Never pass that approval flag
   without confirmation of the previewed diff.
8. Print the exact returned inventory and handoff. Do not commit automatically.

## Final report

Use the controller result rather than reconstructing lists by hand:

```text
Repository initialization finalized
Instructions  complete
Tooling       blocked   Graphifyy registry denied by organization policy
Skills        complete
Hooks         skipped   optional

Shared files to review and commit
- <controller-returned paths>

Local/generated (do not commit)
- <controller-returned paths>

Blocked follow-ups
- <item, owner, and remediation; or none>

Pending recommendations
- <module-scoped instructions or other non-blocking work; or none>

Validation: passed
Next: review the shared diff and commit the initialization.

Developers: pull that commit and run /feature. Do not run /akmaestro-init;
/feature checks local tools and offers confirmed remediation when required.
```

Never describe a topic-only state as finalized. Never tell developers to commit
`.agentic/local/`, generated graphs, audit logs, credentials, or temporary files.
