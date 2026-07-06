# Initialization Topic: Hooks

This topic defines the fourth setup step for a target repository: installing
agent hooks that add guard rails, auditing, and quality automation to Copilot
sessions.

## Goal

Install a recommended set of Copilot hooks so the team gets safety and quality
automation out of the box, working across every surface that supports hooks.

Hooks remain **optional and opt-out** (decision 7): the kit installs the
recommended set by default but the user can decline, and everything must degrade
gracefully where hooks are disabled by enterprise policy.

## Surface Support (verified 2026-06)

Hooks are a shared, portable standard. The same `.github/hooks/*.json` config
works in:

- **Copilot CLI** — GA (February 2026). Primary target.
- **Cloud agent** — supported.
- **VS Code** — preview (8 events); may be disabled by organization policy.

Because VS Code is still preview, the topic must not depend on it. The CLI being
GA is what makes hooks genuinely usable for Murex today.

## Command

```text
/setup-hooks
```

(Also reachable through the guided `/init`. See `docs/setup-flow.md`.)

## Hook Config Format

Config files live in `.github/hooks/*.json`:

```json
{
  "version": 1,
  "disableAllHooks": false,
  "hooks": {
    "preToolUse": [
      {
        "type": "command",
        "matcher": "create|edit",
        "bash": "bash .github/hooks/scripts/restricted-path-guard.sh",
        "powershell": "pwsh -File .github/hooks/scripts/restricted-path-guard.ps1",
        "timeoutSec": 10
      }
    ]
  }
}
```

Verified facts that shape the design:

- **Tool names**: shell = `bash` (Unix) / `powershell` (Windows); file ops =
  `create`, `edit`, `view`. `matcher` is a regex compiled as `^(?:PATTERN)$` and
  matched against the tool name.
- **Payload casing is chosen by the event-name convention**, not the surface:
  camelCase event keys (`preToolUse`) → camelCase fields (`toolName`,
  `toolArgs`); PascalCase keys (`PreToolUse`) → snake_case (`tool_name`,
  `tool_input`). The kit uses **camelCase** event keys. Scripts normalize both
  casings anyway as cheap insurance.
- **`preToolUse` command hooks are fail-closed**: a crash or non-zero exit
  **denies** the tool call. This drives the safety principles below.
- **Decision output** (preToolUse, to stdout):
  `{"permissionDecision":"allow|deny|ask","permissionDecisionReason":"…"}`.

## Script Implementation Rules (non-negotiable)

Because `preToolUse` is fail-closed and runs on tool calls, a buggy guard can
deny *every* action and look like model misbehavior. Every guard script must:

1. **Default to `allow` on any uncertainty.** Can't parse the payload, can't find
   the relevant field, parser missing, unknown tool → print
   `{"permissionDecision":"allow"}` and exit 0. Only ever deny on a *positive*
   match against a restricted glob or denylist pattern. Never exit non-zero
   except as a deliberate deny.
2. **Parse the specific field, never grep the whole payload blob.** The
   dangerous-command guard reads the shell tool's `command`/`tool_input.command`
   field only — not the entire `toolArgs` — so a legitimate file write whose
   *content* contains `rm -rf` is not falsely denied.
3. **Normalize both payload casings** (`toolName`/`tool_name`,
   `toolArgs`/`tool_input`).
4. **Handle missing parser:** PowerShell has `ConvertFrom-Json` built in; the
   bash variant needs `jq`. If `jq` is absent, fall through to `allow` (rule 1),
   never error.
5. Keep scripts small and dependency-light to minimize crash surface.

Scripts are shipped as files under `.github/hooks/scripts/` (`.sh` + `.ps1`
pairs); the JSON config references them so logic is not inlined in JSON.

## Recommended Hook Set

All four are config-driven: the installer writes machine-readable data into
`.agentic/hooks/` and the generic scripts read it. No prose parsing of
`AGENTS.md`.

| Hook | Event | Matcher | Behavior | Config data |
| --- | --- | --- | --- | --- |
| Restricted-path guard | `preToolUse` | `create\|edit` | Deny when the target resolves outside the workspace (repo + declared editable deps), or matches a restricted glob. | `.agentic/hooks/restricted-paths.txt`, `.agentic/hooks/editable-paths.txt` |
| Dangerous-command guard | `preToolUse` | `bash\|powershell` | Deny when the shell `command` matches a destructive pattern (`rm -rf`, force-push to a protected branch, `curl … \| sh`, `chmod -R 777`, …). | `.agentic/hooks/dangerous-commands.txt` |
| Audit log | `userPromptSubmitted`, `postToolUse`, `sessionEnd` | — | Append one JSON line per event to a local audit trail. Never blocks. | — |
| Lint-on-edit | `postToolUse` | `create\|edit` | Run the configured linter on the changed file and inject results as context (postToolUse can inform, not block). No-op if no lint command is configured. | `.agentic/hooks/lint-commands.json` |

### Restricted-path guard

The restricted globs are seeded from the "restricted areas" the instruction-files
topic collects, but stored machine-readably in
`.agentic/hooks/restricted-paths.txt` (one glob per line). This turns a written
rule into an enforced one. The script reads the edit target path from `toolArgs`
(checking the likely field names defensively), matches against the globs, and
denies with a clear reason on a positive match — otherwise allows.

It also enforces the **workspace boundary**: the target path is normalized to an
absolute path, and anything resolving *outside* the repository root is denied
unless it is under a path declared in `.agentic/hooks/editable-paths.txt` — the
owned sibling repos ("editable satellites") collected during the instruction
interview. Read-only reference repos are never listed, which is exactly what
keeps them read-only. The restricted globs are applied inside editable
satellites too (relative to the satellite root), so `.env`, `*.pem`, `secrets/`
etc. stay protected there. Both rules deny only on a positive match and the
scripts still always exit 0.

### Dangerous-command guard

Reads only the shell `command` field. Patterns live in
`.agentic/hooks/dangerous-commands.txt`. The denylist stays conservative to avoid
false positives that block legitimate work; borderline patterns may use `ask`
rather than `deny`.

### Audit log

Appends to `.agentic/audit/<date>.jsonl` on the developer's machine, one JSON
object per event (timestamp, sessionId, event, tool, summary). The installer adds
`.agentic/audit/` to `.gitignore` — the trail is local and private, never
committed. (A future `http` handler can additionally POST to a central
governance endpoint when Murex provides one.)

### Lint-on-edit

Reads the changed file path, looks up a lint command for that file's language in
`.agentic/hooks/lint-commands.json`, runs it, and injects the result as context
so the agent can fix issues. If no command is configured for the language, it is
a silent no-op. Lint commands are collected during instruction/tooling setup.

## Posture and Installation

- Install the recommended set **by default**; let the user opt out per hook or
  entirely.
- Write `.github/hooks/hooks.json`, the `.github/hooks/scripts/*` pairs, the
  `.agentic/hooks/*` config data, and the `.gitignore` entry for the audit dir.
- Never overwrite an existing hook config or script without confirmation
  (decision 6).
- If hooks are disabled by policy, installation still succeeds; the topic records
  that hooks could not be verified live.

## Validation

A hook is only "installed" when it is valid and has been exercised:

- `.github/hooks/hooks.json` is valid against the schema (`version`, `hooks`,
  known event names, valid handler fields).
- Referenced script files exist and are executable.
- The config-data files exist (restricted paths, dangerous patterns, lint
  commands) even if some are empty.
- **Each guard has fired on at least the GA Copilot CLI — both the `allow` path
  and the `deny` path** — because these scripts carry surface-dependent
  assumptions (tool names, `toolArgs` field shapes) that cannot be confirmed by
  reading alone. A guard that has never denied is not validated.

## New Session Requirement

After installing hooks, ask the user to open a new Copilot session at the
repository root so the hooks are loaded, then run a quick check that triggers a
guard's `deny` path (e.g. attempt an edit to a restricted path) and its `allow`
path.

## State File

Record status in:

```text
.agentic/setup/hooks-state.json
```

The state should include:

- which hooks were installed vs. declined;
- config-data file paths and whether they are populated;
- per-hook validation result (schema valid, scripts present, allow+deny fired);
- the surface(s) on which hooks were verified;
- whether hooks were disabled by policy;
- whether a new session was requested;
- overall status.

## Completion Criteria

`setup hooks` is complete only when:

- `.github/hooks/hooks.json` is valid and references existing, executable
  scripts;
- the `.agentic/hooks/*` config-data files exist;
- the audit directory is gitignored;
- every installed guard has fired both its `allow` and `deny` paths on at least
  the GA Copilot CLI;
- no existing hook config or script was overwritten without confirmation;
- `.agentic/setup/hooks-state.json` records the results.

If hooks are disabled by enterprise policy, the topic is **blocked, not failed**:
record that hooks are installed but unverifiable, and treat the rest of setup as
able to complete without them.

## Status And Help Behavior

`init help` and `init status` should report hooks setup like this:

```text
Hooks:
- Restricted-path guard: verified
- Dangerous-command guard: verified
- Audit log: installed
- Lint-on-edit: installed
- Verified on: Copilot CLI

Recommended next step:
- open a new Copilot session and trigger a guard's deny path to verify
```

If hooks are not yet installed, recommend `setup hooks`.

If hooks are installed but a guard has not fired its deny path, recommend the
verification step above.

If hooks are disabled by policy, report that and recommend proceeding without
them.

If all initialization topics (instruction files, tooling, skills, hooks) are
complete, mark setup as complete and recommend starting the feature flow once it
exists.
