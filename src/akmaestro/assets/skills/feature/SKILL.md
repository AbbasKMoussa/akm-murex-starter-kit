---
name: feature
description: >-
  Orchestrate the feature flow, verify developer readiness, and report where
  work stands. Use to start, select, resume, or inspect a feature: "start a
  feature", "where are we on this feature?", "resume the feature", "/feature",
  "feature status", or "feature help". Reads deterministic on-disk state. Use
  the status skill for an unqualified "where are we?" across all workflows.
allowed-tools:
  - shell
---

# feature - feature-flow orchestrator

Stage 2 carries work through gated specialist phases. Shared continuity lives in
committed feature state and artifacts; the developer's selected feature and
readiness live only under `.agentic/local/`.

## Installation scope

Read `.agentic/setup/kit-manifest.json`. `installation_mode: subproject` means
the directory containing the manifest is the product boundary. Run all
controller commands, requirements, feature artifacts, verification, and normal
edits from that directory. The enclosing Git root is only for requested Git
operations. Do not inspect or edit outside the subproject unless setup records
the target as a modifiable dependency and this feature explicitly requires it.
If Copilot is not running from the recorded AKMaestro root, stop and direct the
developer to reopen that product before running `/feature`.

## Controller and entry gate

Read `.agentic/STATE-PROTOCOL.md`. Use:

```text
uv run --no-project python .agentic/bin/akmaestro-state.py <command>
```

Before the first controller call, verify `uv` is on PATH. If it is missing,
explain that uv is the controller bootstrap and show the platform's official
installer (`powershell -ExecutionPolicy ByPass -c "irm
https://astral.sh/uv/install.ps1 | iex"` on Windows, or `curl -LsSf
https://astral.sh/uv/install.sh | sh` on macOS/Linux). Explain that it downloads
and executes the uv installer and may update PATH; run it only after explicit
confirmation. Then stop and ask for a new terminal/Copilot session before
rerunning `/feature`. This is the only pre-controller bootstrap exception; do
not mutate workflow state or install any other prerequisite this way.

Run `setup-status`. If repository initialization is not complete, stop: the team
lead must finish and commit `/akmaestro-init`. A developer must never rerun
`/akmaestro-init` merely
because their workstation is missing a tool.

Run `readiness-check`. When it exits `3`:

1. Show every missing required tool/artifact and its controller-reported action.
2. Explain what each command changes and ask for confirmation before running it.
3. Write the exact recorded action object to a local input file and run it
   without a shell through `remediation-run --input <file> --approved`. Never
   reconstruct, interpolate, or add untrusted text. Pass `--approved` only after
   the confirmation in step 2.
4. Rerun `readiness-check`.
5. If requirements remain missing or the user declines, stop feature mutation
   with the exact remediation. Do not bypass the mandatory gate.

## Subcommands

- `status`, "where are we?", or "what's next?": orient and stop.
- `help`: explain phases, gates, modes, shared state, and local readiness; stop.
- `start` or `new`: begin a new feature after the entry gate.
- `select <feature-id>`: set this worktree's local active feature.
- Otherwise: orient and route to the derived next command.

## Orient

Run `feature-list`; never read or create an `index.json`.

- No open features: say so and offer `feature start`.
- One open feature: use it. If there is no local selection, call
  `feature-select --id <id>` before resuming.
- Multiple open features and no valid local selection: list each feature's phase
  and derived next command, ask which one this developer wants, then call
  `feature-select --id <id>`.
- Valid local selection: call `feature-show --id <id>` and report the phase,
  current story/step/mode, story progress, revision, and derived next command.

Status remains useful when readiness is missing: report both workflow position
and the local readiness problem, but do not mutate feature state.

## Start

Ask for a short title and optional ticket id. Derive a lowercase kebab-case id
matching `[a-z0-9][a-z0-9-]*`, then call:

```text
uv run --no-project python .agentic/bin/akmaestro-state.py feature-create --id <feature-id> --title <title>
```

The controller creates `.agentic/features/<feature-id>/state.json` and writes the
worktree-local selection. It does not create a shared mutable index. Print the
derived `/feature-understand` handoff.

## Phases and modes

Understand -> Frame -> Split -> per-story loop (Prime -> Plan -> Implement ->
Review -> Learn) -> Feature review -> Retro.

Feature and story boundaries use controller-enforced gates. Modes apply only to
the story loop:

- **guided**: each step is gated and normally starts in fresh context;
- **autonomous**: one story's five steps run in one session, stopping for real
  blockers or non-converging review. It never auto-starts another story.

The light-context exception may continue across a gate when the session is still
small. Implement-to-review always uses fresh context. Every skill writes its
artifact first, advances state last with the revision it read, and reports the
controller-derived next command.

## Routing

Do not implement specialist phases here. Route only to the `nextCommand` returned
by `feature-show`. If a state command reports a stale revision, reread state and
artifacts; never force or manually rewrite the JSON.
