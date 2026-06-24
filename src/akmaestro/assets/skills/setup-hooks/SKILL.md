---
name: setup-hooks
description: >-
  Install and verify the kit's optional Copilot hooks for this repo — guard
  rails, auditing, and lint-on-edit, configured in .github/hooks/. Use for
  "/setup-hooks", "set up hooks/guard rails", or the hooks step of /init. Hooks
  are optional and install-by-default (opt-out).
allowed-tools:
  - shell
---

# setup-hooks — guard rails, audit, lint (optional)

Hooks are a portable standard in `.github/hooks/*.json` (Copilot CLI GA, VS Code
preview, cloud agent). They are **optional**: install the recommended set by
default, let the user decline per hook or entirely, and degrade gracefully where
org policy disables them. Hooks never block overall setup completion.

## Recommended set

| Hook | Event | Behavior |
| --- | --- | --- |
| Restricted-path guard | `preToolUse` | deny edits to restricted paths |
| Dangerous-command guard | `preToolUse` | deny destructive shell commands |
| Audit log | `userPromptSubmitted`/`postToolUse`/`sessionEnd` | local JSONL trail |
| Lint-on-edit | `postToolUse` | run configured linter on changed file |

## Install

The installer drops `.github/hooks/hooks.json`, `.github/hooks/scripts/*`, and
seed data in `.agentic/hooks/`. This step:

- confirms the files are present and the `.sh` scripts are executable;
- **seeds repo-specific data**: add the restricted areas from `AGENTS.md` to
  `.agentic/hooks/restricted-paths.txt`; add detected lint commands (per
  extension, `{file}` placeholder) to `.agentic/hooks/lint-commands.json`;
- never overwrites an existing hook config or a script the user customized —
  merge handler arrays per event; show changes and confirm.

## Safety reminder

`preToolUse` is fail-closed (a crashing guard denies the tool call). The shipped
guards always exit 0 and default to **allow** on any uncertainty, denying only on
a positive match. Do not "harden" them into failing closed on error.

## Validate (allow AND deny)

- `jq . .github/hooks/hooks.json` parses; events/handlers are valid.
- Scripts exist and `.sh` are executable; `jq` present (bash guards need it).
- Dry-run the bash guards — both paths:
  - `printf '{"toolName":"edit","toolArgs":{"path":".env"}}' | bash .github/hooks/scripts/restricted-path-guard.sh` → deny
  - same with `"path":"README.md"` → allow
  - `printf '{"toolName":"bash","toolArgs":{"command":"rm -rf /"}}' | bash .github/hooks/scripts/dangerous-command-guard.sh` → deny
  - same with `"command":"ls -la"` → allow

This validates script logic only; the live Copilot CLI wiring (real tool
names/`toolArgs` fields) and the PowerShell variants must be confirmed in an
actual session.

## New session

After installing hooks, ask the user to open a new Copilot session and trigger a
guard's deny path (e.g. attempt an edit to a restricted path) to confirm.

## State

`.agentic/setup/hooks-state.json`: installed vs declined hooks; config-data paths
+ whether populated; per-hook validation (schema, scripts, allow+deny fired);
surface(s) verified; whether policy disabled hooks; new-session requested; status.

## Completion

Hooks are optional, so they never block setup. The topic is "done" when the
chosen hooks are installed, valid, and their guards fired both allow and deny on
at least the GA CLI; or recorded as `blocked` if policy disables them.
