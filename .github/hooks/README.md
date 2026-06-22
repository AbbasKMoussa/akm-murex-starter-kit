# Copilot Hooks (DRAFT — untested against a live Copilot CLI)

This directory holds the kit's recommended hook set. Config is `hooks.json`;
logic lives in `scripts/` as `.sh` + `.ps1` pairs. Repo-specific data lives in
`.agentic/hooks/`. See `docs/init-topics/hooks.md` for the full spec.

| Hook | Event(s) | Script |
| --- | --- | --- |
| Restricted-path guard | `preToolUse` (create\|edit) | `restricted-path-guard.{sh,ps1}` |
| Dangerous-command guard | `preToolUse` (bash\|powershell) | `dangerous-command-guard.{sh,ps1}` |
| Lint-on-edit | `postToolUse` (create\|edit) | `lint-on-edit.{sh,ps1}` |
| Audit log | `userPromptSubmitted`, `postToolUse`, `sessionEnd` | `audit-log.{sh,ps1}` |

## Safety model

`preToolUse` is **fail-closed** — a crash or non-zero exit denies the tool call.
The guards therefore **always exit 0** and **default to `allow`** on any
uncertainty (unparseable payload, missing field, missing `jq`, unknown tool).
They emit a `deny` only on a positive match against a glob/pattern. A bug should
never be able to block every action.

## Before trusting these (must verify on the GA Copilot CLI)

1. The exact `toolArgs` field carrying the file path for `create`/`edit`
   (scripts check `path`/`file_path`/`filePath`/`filename`/`file`).
2. That the shell command lives in `toolArgs.command`.
3. The `postToolUse` context-injection field is VERIFIED as `additionalContext`.
   Caveat: copilot-cli#2980 — the CLI does not always forward it into the context
   window (never for MCP tool calls), so lint findings may not always reach the
   agent.
4. `lint-on-edit.ps1` command execution uses `cmd.exe /c` (Windows); adjust for
   PowerShell Core on Linux/macOS.
5. Each guard fires **both** its `allow` and `deny` paths (e.g. attempt an edit
   to `.env` → expect deny; edit an ordinary file → expect allow).

## Dependencies

- bash variants need `jq` (absent → scripts fall through to allow / no-op).
- PowerShell variants use the built-in `ConvertFrom-Json`.
