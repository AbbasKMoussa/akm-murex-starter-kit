# AKMaestro State Protocol

AKMaestro separates committed repository workflow state from worktree-local
developer context. Skills must use the bundled controller for every state
mutation:

```text
uv run --no-project python .agentic/bin/akmaestro-state.py <command>
```

## Installation boundary

Read `.agentic/setup/kit-manifest.json` before inspecting or changing project
files. `installation_mode` defines the AKMaestro root:

- `repository` (or an absent field from a legacy installation): the AKMaestro
  root and Git root are the same directory;
- `subproject`: the current directory is an explicitly isolated product below
  the Git root. `project_root` is `.` and `git_root` is a portable relative path
  to the enclosing Git root.

All workflow paths, commands, state, generated files, and ordinary edits are
relative to the AKMaestro root. In subproject mode, use the enclosing Git root
only to read shared Git policy and perform requested Git operations. Do not
scan sibling products or treat the enclosing repository as the product. Do not
edit outside the subproject unless the path is a separately declared modifiable
dependency and the task explicitly requires it.

Run Copilot with the AKMaestro root as its working directory: the repository
root for normal installations or the selected product root for subproject
installations. Stop with `/doctor` if the manifest boundary does not match the
current directory or Git reports a different enclosing root.

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

## Module knowledge

Instructions evidence records a required `moduleKnowledge.decision`:

- `generate_now`: the lead accepted generation for every confirmed complex
  module. All begin in `pendingModules`, and the controller refuses either
  terminal instructions state (`complete` or `blocked`) until none remain.
- `defer`: confirmed modules may remain pending while instructions completes.
  The controller retains a follow-up command for each.
- `not_applicable`: both confirmed complex modules and `pendingModules` must be
  empty.

Pass the full confirmed module list to `module-targets`; its returned mapping is
the only filename authority. Every completed module needs the exact
`applyTo: "<module-path>/**"` scope and the seven required sections: Purpose,
Boundaries, Commands, Important Paths, Patterns, Pitfalls, and Restrictions.
Existing targets still use the reviewed merge protocol.

Process pending modules in normalized path order. For each artifact, submit the
prepared `generatedFiles` and `pendingModules` revision through `evidence-write
instructions --input <local-evidence-json> --expected-revision
<latest-evidence-revision>`. A successful write validates the artifact and is
atomic, so an invalid artifact leaves the prior revision resumable.
`setup-status` returns `moduleKnowledge` with completed and pending module lists
plus a controller-derived pending-item command for each remaining module.

When `generate_now` remains pending, instructions stays `in_progress`,
`setup-status.nextCommand` remains `/akmaestro-init`, and that is the only
cross-session resume command. Accepted generation may change to `defer` only
after explicit lead confirmation and a new evidence revision. A blocked command
result may transition instructions to `blocked` only after accepted module
generation has no pending modules. Deferred post-setup work uses each returned
`/setup-instructions module <path>` command and does not reopen the completed
setup topic.

## Repository and developer readiness

`/akmaestro-init` is run once by the team lead. Its committed completion state is the
AKMaestro-root gate. Tooling setup also writes committed environment
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
