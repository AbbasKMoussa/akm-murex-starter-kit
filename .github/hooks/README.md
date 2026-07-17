# Copilot Hooks

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

## Verification status

1. Copilot CLI 1.0.68 on Windows sends `toolArgs` as a JSON-encoded string;
   `create`/`edit` use `path`, and the shell tool uses `command`. Scripts also
   accept object-form arguments and defensive alternate field names.
2. The `postToolUse` context-injection field is verified as `additionalContext`.
   Caveat: copilot-cli#2980 — the CLI does not always forward it into the context
   window (never for MCP tool calls), so lint findings may not always reach the
   agent.
3. `lint-on-edit.ps1` command execution uses `cmd.exe /c` (Windows); adjust for
   PowerShell Core on Linux/macOS.
4. Automated tests exercise allow and deny paths. A post-fix live denial check,
   live Bash run, and VS Code run remain required before broad rollout.

## Dependencies

- bash variants need `jq` (absent → scripts fall through to allow / no-op).
- PowerShell variants use the built-in `ConvertFrom-Json`.
