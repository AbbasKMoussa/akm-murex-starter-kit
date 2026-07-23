# Initialization Topic: Hooks

`/setup-hooks` is the optional fourth topic. Hook assets may be installed by the
CLI, but `hooks.json` starts with `disableAllHooks: true`. Activation is opt-in:
the team lead reviews behavior and test results before explicit consent. The
workflow never depends on hooks because a surface or organization policy may
disable them.

This topic is also reached through `/akmaestro-init`.

## Recommended set

| Hook | Event | Behavior |
| --- | --- | --- |
| Restricted-path guard | `preToolUse` | Denies restricted paths, undeclared outside-workspace edits, and canonical symlink/junction escapes. |
| Dangerous-command guard | `preToolUse` | Denies conservative destructive-command patterns. |
| Audit log | prompt/tool/session events | Writes bounded event/tool/time metadata only to a local retained JSONL trail. |
| Lint-on-edit | `postToolUse` | Runs a structured linter directly and injects bounded findings. |

The restricted guard reads modifiable sibling roots from
`.agentic/hooks/editable-paths.txt`. Read-only siblings are never listed.
Restricted globs still apply inside modifiable siblings.

The dangerous-command guard is defense in depth, not an arbitrary shell-command
sandbox. It reads only the command field, so dangerous text in file content is
not a match.

The audit hook never stores prompt text, tool arguments/results, credentials, or
session identifiers. `.agentic/audit/` is gitignored, uses restrictive local
permissions where supported, and removes files older than 14 days.

Lint configuration is a bare executable plus an argument array containing
`{file}`. Shell executables and command strings are invalid; the file path is
passed as an argument, not evaluated.

## Script safety

Copilot CLI has been observed sending camelCase `toolArgs` as a JSON-encoded
string. Scripts decode that shape and accept object-form/snake_case variants for
other surfaces.

Every hook script exits zero. A non-zero `preToolUse` command hook can deny all
tool calls. Malformed or irrelevant events allow/no-op. Once an edit path is
parsed, canonical resolution must place it inside the main repository or a
declared modifiable sibling; otherwise it denies. Bash guards require `jq` and
allow if that parser is absent.

## Non-destructive configuration

Existing hook and config-data files use controller `merge-plan` and
`merge-apply --approved`. Plans contain an exact target preimage and are rejected
if the file changes after review. New files may be created directly. Customized
scripts are never overwritten silently.

## Validation before activation

With hooks still disabled:

1. parse `hooks.json` and verify referenced scripts and executable bits;
2. test restricted-path allow, deny, workspace boundary, modifiable sibling,
   restricted sibling path, and symlink/junction escape cases;
3. test dangerous-command allow and deny cases;
4. test lint with spaces and shell metacharacters in the filename;
5. test that audit output contains no unique secret sent in content fields.

Use the real JSON-encoded-string `toolArgs` shape. Test both Bash and PowerShell
when available. Record dry-run platforms in check details; only a real Copilot
session belongs in `verifiedSurfaces`.

After all selected dry checks pass and consent is explicit, run `hooks-enable`.
Run `hooks-status` and require `enabled: true`. `hooks-disable` revokes consent.
The manifest preserves this choice across `akmaestro update`.

## Strict evidence

`evidence-write hooks` accepts exactly:

- `enabled`;
- `selectedHooks`;
- `configPath`;
- `checks`, each with `id`, `status`, and `detail`;
- `verifiedSurfaces`;
- `blockers`.

An enabled topic completes only when all selected checks passed and the config
agrees. A retryable test failure remains `in_progress`. A policy restriction is
`blocked` while hooks remain disabled. If the lead declines, run
`hooks-disable`, transition the optional topic to `skipped`, and continue.
