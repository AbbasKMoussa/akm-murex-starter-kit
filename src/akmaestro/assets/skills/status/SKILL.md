---
name: status
description: >-
  Report the repository's current AKMaestro workflow position and exact next
  action without changing anything. Use for "/status", "where are we?", "what
  should I do next?", "are we still initializing?", "is a feature active?", or
  general AKMaestro help. Automatically distinguishes repository setup from
  feature work and reads deterministic on-disk state.
allowed-tools:
  - shell
---

# status - universal workflow orientation

Give a concise, read-only answer from a fresh session. Setup takes precedence:
feature work is actionable only after the team lead has completed and committed
repository initialization.

## Controller

Read `.agentic/STATE-PROTOCOL.md`, then use:

```text
uv run --no-project python .agentic/bin/akmaestro-state.py <command>
```

Do not create, select, install, remediate, or advance anything. Never call
`setup-init`, `setup-transition`, `feature-select`, or any other mutating state
command. Readiness probes must use `readiness-check --no-write`.

Read `.agentic/setup/kit-manifest.json` first. Report its `installation_mode` as
`repository` or `subproject`; a missing field means a legacy `repository`
installation. In subproject mode, verify that `project_root` is `.` and the
relative `git_root` resolves to Git's enclosing root. A mismatch is invalid
installation state: stop with `/doctor` and do not search the parent repository.

## Help

For `/status help` or a general request for AKMaestro help, explain and stop:

- `/status` reports the active flow and one next action without changing state;
- `/akmaestro-init help` explains the one-time, team-lead-owned setup flow;
- `/feature help` explains the developer feature flow, phases, gates, and modes;
- `/doctor` diagnoses installation, configuration, or environment health.

Do not inspect workflow state when the user asks only for help.

## Orient

1. If `.agentic/setup/initialization-state.json` does not exist, report setup as
   not started. The owner is the team lead and the exact next action is
   `/akmaestro-init`.
   Do not inspect feature state.
2. Otherwise run `setup-status` and retain its topics, blocker reasons, derived
   result, and revision. If the command fails or returns invalid output, stop
   with `/doctor` as the next action; never infer setup progress from files by
   hand.
3. If setup is incomplete, report the active flow as **setup**, show all four
   topics and blocker reasons, and report the controller-returned
   `moduleKnowledge` decision plus completed and pending module counts when it
   is present. During `generate_now` with pending modules, print exactly one
   `Next: /akmaestro-init` line. Otherwise print the controller's `nextCommand`,
   point to `/akmaestro-init help`, and stop. Do not inspect readiness or
   features.
4. If setup is complete, summarize it on one line, report any blocked topics as
   durable follow-ups, and report `moduleKnowledge` with completed/pending
   counts. For `defer`, list each pending module and its controller-returned
   follow-up command without making it the active `Next:` action. Then run
   `readiness-check --no-write`:
   - Exit `0` means ready.
   - Exit `3` means local prerequisites are missing: summarize every missing
     requirement and its recorded remediation action, but do not run it.
   - Another exit or invalid output means status could not verify readiness;
     report that and point to `/doctor`.
5. Run `feature-list`; never read or create an `index.json`.
   - Valid local selection: run `feature-show --id <active-id>`.
   - One open feature with no selection: run `feature-show --id <id>`, but do
     not select it.
   - Multiple open features with no selection: list every feature's id, title,
     phase, and derived next command. Do not choose one.
   - No open features: report the number of completed features, if any.
   If `feature-list` or `feature-show` fails or returns invalid output, stop with
   `/doctor` as the next action; never guess feature progress.

## Next-action priority

Print exactly one `Next:` line:

1. Incomplete setup: use the `setup-status` `nextCommand` and identify the team
   lead as owner. Accepted `generate_now` work always has
   `Next: /akmaestro-init`.
2. Unreadable or invalid workflow state: `/doctor`.
3. Missing local readiness: `/feature` to review and confirm remediation. If
   the readiness probe itself failed or was unverifiable, use `/doctor`.
4. Valid active feature: use the exact `nextCommand` from `feature-show`.
5. One unselected open feature: `/feature` to select it locally and resume.
6. Multiple unselected open features: `/feature select <feature-id>`.
7. No open feature: `/feature start`.

Do not execute or delegate to the next command. Status only orients.

## Report

Keep the output scannable and omit empty feature fields:

```text
AKMaestro status
Scope       repository
Flow        feature
Setup       complete (revision 8)
Readiness   ready
Feature     search-filters - story loop
Now         story 02-facet-ui, implement (guided); 1/3 stories complete
Next: /story-implement

Help: /feature help | Health: /doctor
```

When setup is active, replace the feature fields with the four setup-topic
statuses, include `Module knowledge  <decision> (<completed>/<total> complete)`,
and end with `Help: /akmaestro-init help | Health: /doctor`.
