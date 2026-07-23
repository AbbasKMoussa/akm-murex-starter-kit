---
name: setup-hooks
description: >-
  Review, configure, explicitly enable, and verify AKMaestro's optional Copilot
  hooks. Use for "/setup-hooks", "set up hooks or guard rails", or the hooks
  step of /akmaestro-init. Installed hooks remain disabled until the team lead
  gives explicit consent.
---

# setup-hooks - optional guard rails, audit, and lint

Hooks are optional and are never a prerequisite for AKMaestro. The installer
places the recommended files in the repository with `disableAllHooks: true`.
Do not enable them implicitly. Copilot CLI support is GA; VS Code support may be
preview or disabled by organization policy, so report the verified surface and
degrade cleanly.

## State protocol

Read `.agentic/STATE-PROTOCOL.md`. Use the bundled controller for state, merge,
and hook activation commands. If the topic is not `in_progress`, transition it
using the revision from `setup-status`. Never edit controller-owned state by
hand.

Start with `hooks-status`. Explain the selected behavior before asking for one
explicit choice: enable all selected hooks, customize the selection, or decline.

- Decline: run `hooks-disable`, transition the optional topic to `skipped`, and
  return to `/akmaestro-init`.
- Organization policy prevents hooks: keep them disabled, write strict evidence
  with the policy blocker, and transition to `blocked`.
- Consent to enable: continue below. Consent to installation is not consent to
  activation.

## Recommended set

| Hook | Event | Behavior |
| --- | --- | --- |
| Restricted-path guard | `preToolUse` | Denies edits outside declared writable roots and to restricted paths. |
| Dangerous-command guard | `preToolUse` | Denies known destructive shell commands. |
| Audit log | `userPromptSubmitted`, `postToolUse`, `sessionEnd` | Records metadata only in a local, retained JSONL log. |
| Lint-on-edit | `postToolUse` | Runs a structured, shell-free linter command on the changed file. |

Hooks are defense in depth, not a general command sandbox. The workflow and
controller enforce read-only sibling boundaries for their own actions; the
dangerous-command denylist cannot prove an arbitrary shell command harmless.

## Configure without overwriting

Confirm these installed files exist:

- `.github/hooks/hooks.json` and every referenced script;
- `.agentic/hooks/restricted-paths.txt`;
- `.agentic/hooks/editable-paths.txt`;
- `.agentic/hooks/dangerous-commands.txt`;
- `.agentic/hooks/lint-commands.json`.

Add only confirmed modifiable sibling roots to `editable-paths.txt`; never add a
read-only sibling. Keep generated graphs under the main repository's
`.agentic/local/graphs/` tree. Configure lint commands as a bare executable plus
an argument array containing `{file}`; shell executables and command strings are
invalid.

For any existing instruction or hook file, write the complete proposed content
to a local temporary file, then use:

```text
uv run --no-project python .agentic/bin/akmaestro-state.py merge-plan --target <repo-relative-target> --input <proposed-file>
```

Show the returned unified diff. Apply only after explicit confirmation:

```text
uv run --no-project python .agentic/bin/akmaestro-state.py merge-apply --plan-id <id> --approved
```

If the target changes after review, the controller rejects the plan. Create a
new plan; never force or silently reconstruct the merge.

## Validate while disabled

Run deterministic dry checks before activation. Use the real Copilot CLI payload
shape, where `toolArgs` is a JSON-encoded string. Test the platform variant that
will be used, and both Bash and PowerShell when available:

1. Parse `hooks.json`; confirm `disableAllHooks` is still `true`, all referenced
   scripts exist, and Bash scripts are executable.
2. Restricted guard: `.env` -> deny, `README.md` -> allow, undeclared sibling ->
   deny, declared modifiable sibling -> allow, and a symlink/junction escape ->
   deny.
3. Dangerous-command guard: a known destructive command -> deny and a harmless
   command -> allow.
4. Lint hook: use a filename containing spaces and shell metacharacters; confirm
   the configured executable is invoked directly with the filename as one
   argument and no command substitution occurs.
5. Audit hook: confirm it stores event/tool/file/status metadata only, never raw
   prompt text, tool arguments/results, credentials, or session identifiers;
   confirm local ignore, restrictive permissions where supported, and retention.

The scripts must always exit zero because a crashing `preToolUse` hook denies the
tool call. Unknown payloads may allow, but a parsed edit path that cannot be
canonically resolved must be denied.

## Enable after consent

When all selected dry checks pass and consent is explicit, run:

```text
uv run --no-project python .agentic/bin/akmaestro-state.py hooks-enable
```

Run `hooks-status` and require `enabled: true`. To revoke consent or recover from
a hook problem, run `hooks-disable`; this state is preserved by `akmaestro
update`.

Ask for one fresh Copilot session only when needed to load the activation. A
live allow/deny probe is recommended but may be recorded as `not tested` in the
report; do not invent a verified surface.

## Strict evidence

Write `evidence-write hooks` with exactly this shape, replacing every value with
actual results:

```json
{
  "enabled": true,
  "selectedHooks": ["restricted-path", "dangerous-command", "audit-log", "lint-on-edit"],
  "configPath": ".github/hooks/hooks.json",
  "checks": [
    {"id": "config", "status": "passed", "detail": "Parsed; enabled only after consent"},
    {"id": "restricted-path", "status": "passed", "detail": "Allow, deny, boundary, and canonical-path probes passed"},
    {"id": "dangerous-command", "status": "passed", "detail": "Allow and deny probes passed"},
    {"id": "audit-privacy", "status": "passed", "detail": "Metadata-only output and retention verified"},
    {"id": "lint-direct-exec", "status": "passed", "detail": "Structured direct execution probe passed"}
  ],
  "verifiedSurfaces": ["copilot-cli-windows"],
  "blockers": []
}
```

Use `failed` for retryable failures and leave the topic `in_progress`. Use
`blocked` plus a concise string in `blockers` only for a real environment or
policy restriction. `verifiedSurfaces` contains only live sessions actually
tested; dry-run platforms belong in check details.

Write evidence before the terminal transition. Enabled hooks may complete only
when every selected check passed and `hooks-status` agrees. Transition to
`blocked --reason <reason>` for policy blocks. Rerun `setup-status` and return to
the orchestrator. The only cross-session resume command is `/akmaestro-init`.
