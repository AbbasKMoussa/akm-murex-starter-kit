# AKMaestro State Protocol

AKMaestro separates committed repository workflow state from worktree-local
developer context. Skills must use the bundled controller for every state
mutation:

```text
uv run --no-project python .agentic/bin/akmaestro-state.py <command>
```

## Persistence boundary

Committed:

- `.agentic/setup/initialization-state.json` and setup evidence;
- `.agentic/setup/environment-requirements.json`;
- `.agentic/features/<feature-id>/state.json` and feature artifacts;
- `.agentic/hooks/` configuration.

Gitignored and local to one developer/worktree:

- `.agentic/local/active-feature.json`;
- `.agentic/local/readiness.json`;
- `.agentic/local/locks/` and temporary input files;
- `.agentic/audit/` when the audit hook is installed.

## Mutation protocol

1. Read state through `setup-status`, `feature-list`, or `feature-show` and note
   its `revision`.
2. Produce and validate the human-readable artifact or setup evidence first.
3. Invoke the matching controller transition with `--expected-revision` last.
4. Re-read state and print the controller-derived `nextCommand`.

Feature gates and story transitions refuse to advance until their corresponding
artifact file exists. Content quality remains the skill's gated responsibility.

Never edit controller-owned JSON directly. Never infer progress from chat
history. If a command reports stale state, re-read the artifacts and state,
reconcile with the user when necessary, and retry from the new revision. A
repeated command that already reached the requested state is idempotent.

Instructions evidence is topic-specific and strict. It records product purpose,
all canonical command definitions/results, automated or manual verification,
Git policies, repository context, and generated files. Commands use argument
arrays, relative working directories, and bounded timeouts. After user
confirmation, run one finite instruction action without shell interpretation:

```text
uv run --no-project python .agentic/bin/akmaestro-state.py action-check --input <local-action-json>
```

The controller revalidates instruction artifacts even on an idempotent evidence
write, so deleted files or reintroduced bootstrap placeholders cannot be hidden
by replaying old evidence. `action-check` returns a controller check ID, sha256
of the canonical action, exit status, and timestamp. Command output is never
persisted in committed evidence. Passing command evidence must contain one matching
passing check for every configured action. Omitted or substituted hashes fail
validation.

The controller uses atomic file replacement and worktree-local locks. An
interruption before the transition leaves the prior state resumable; an
interruption after it leaves the new state complete.

Existing instruction and hook files use `merge-plan` followed by
`merge-apply --approved`; the plan identifier binds the target, preimage, and
proposed content reviewed by the user. `setup-finalize --preview` provides the
same read-only diff before an unowned `.github/AGENTIC.md` may be replaced.

## Repository and developer readiness

`/akmaestro-init` is run once by the team lead. Its committed completion state is the
repository-level gate. Tooling setup also writes committed environment
requirements for `uv`, Graphifyy, the selected LSPs, and required generated
artifacts.

`uv` bootstraps this controller. If it is absent, `/feature` may offer the
official platform installer after explaining the downloaded-script behavior and
obtaining explicit confirmation, then must stop for a PATH/session refresh. No
workflow state changes before the controller is available, and every other
remediation remains controller-bound.

Every feature-flow entry runs `readiness-check`. The result is written only to
`.agentic/local/readiness.json` and is tied to a hash of the committed
requirements. Missing required tools or artifacts block feature mutations. The
skill shows the recorded structured install/remediation action, obtains
confirmation before changing the developer machine, then passes its exact action
object to `remediation-run --approved`. The controller executes the argument
array only when it exactly matches a committed install/remediation action,
confines it to a declared writable root, and never invokes a shell. The skill
then reruns the readiness check.

## Canonical lifecycle

Feature phases:

```text
understanding -> framing -> splitting -> story_loop -> reviewing
              -> retrospective -> complete
```

Story steps:

```text
prime -> plan -> implement -> review -> learn -> complete
```

Review may send a story back to `plan` or `implement`. Feature review may reopen
a completed story to either of those steps. `nextCommand`, setup completion,
current story status, and feature lists are derived and are never stored as a
second source of truth.

## Exit codes

- `0`: command succeeded; readiness is satisfied when applicable.
- `1`: validation found invalid state.
- `2`: command or transition error, including stale revisions.
- `3`: readiness probes completed but required items are missing.
- `4`: an instruction action check ran but did not pass.
