# Stage 1: Repository Setup

Stage 1 initializes one repository once. The team lead runs it, reviews the
result, and commits the shared files. Developers pull that commit and start with
`/feature`; they do not repeat repository initialization for their workstation.

The topic specifications are in `docs/init-topics/`. Decisions and rationale
are in `docs/setup-flow-decisions.md`.

## Delivery model

The bootstrap is a thin Python CLI:

```text
uvx akmaestro init
```

Before registry publication, `uvx --from git+<internal-url> akmaestro init` runs
the same command without cloning this repository. By default, the target must
be an existing exact Git root. `--dry-run` previews destinations, `--no-hooks`
omits hook assets, and `--path <root>` selects another repository.

`--subproject` is an explicit exception for an independently operated product
below an enclosing Git root when the product has no `.git` of its own. The
selected product becomes the AKMaestro root and receives its own `.github/`,
`.agentic/`, `.gitignore`, and `AGENTS.md`; the enclosing Git root is not
modified. The manifest records `installation_mode`, `project_root: "."`, and a
portable relative `git_root`. `init` and `update` both require the explicit
flag. A Git-root target rejects the flag so the exceptional mode cannot silently
replace normal behavior.

Subproject users open that product as the VS Code workspace or start Copilot CLI
there. Every workflow path, command, state record, generated file, and ordinary
edit is scoped to the product. The enclosing root is consulted only for shared
Git and CI policy or requested Git operations. Other products are not scanned
or modified unless one is separately declared as a modifiable dependency.

The installer creates absent files and never overwrites an existing file.
Reserved AKMaestro entry-point collisions fail before installation. It refuses
symlinked destination parents, writes files atomically, and records kit-owned
hashes in `.agentic/setup/kit-manifest.json`.

`akmaestro update` refreshes files that still match their recorded hash, adds
new assets, and removes only untouched retired assets. Customized files are
kept. `--force` is an explicit reset, and `--dry-run` previews the update. Hook
activation consent survives updates.

## Installed assets

| Package asset | AKMaestro-root destination | Ownership |
| --- | --- | --- |
| `assets/skills/*` | `.github/skills/<name>/` | 19 bundled skills |
| `state.py` | `.agentic/bin/akmaestro-state.py` | kit-owned controller |
| `assets/schemas/*` | `.agentic/schemas/` | seven v3 JSON Schemas |
| `assets/runtime/*` | `.agentic/` | shared state protocol |
| `assets/hooks/*` | `.github/hooks/` | optional, installed disabled |
| `assets/hooks-data/*` | `.agentic/hooks/` | committed hook configuration |
| bootstrap pointers | `AGENTS.md`, `.github/copilot-instructions.md` | only when absent |

The installer is intentionally not the setup interview. Dynamic inspection,
questions, generation, and verification happen through the installed skills.

## Entry points

| Skill | Responsibility |
| --- | --- |
| `/akmaestro-init` | Team-lead setup orchestrator; initialize, resume, finalize, status, or help. |
| `/status` | Read-only orientation across setup and feature work. |
| `/setup-instructions` | Product, commands, Git policies, repository context, and instruction files. |
| `/setup-tooling` | Graphifyy, language servers, graphs, and developer requirements. |
| `/setup-skills` | Full bundled-skill and discovery verification. |
| `/setup-hooks` | Optional hook review, explicit activation, and verification. |
| `/doctor` | Read-only health diagnosis; limited confirmed fixes in fix mode. |
| `/teach` | Route durable rules to the correct instruction file. |

Natural language remains supported. The distinct name `/akmaestro-init` avoids
conflicting with VS Code's built-in `/init` command.

## Orchestration

The mandatory order is:

1. instructions;
2. tooling;
3. skills;
4. hooks, optional.

`/akmaestro-init` runs `setup-status`, reads the installed `SKILL.md` for the
derived next topic, and follows it directly. It never relies on implicit
skill-to-skill routing. After each topic it rereads controller state instead of
calculating progress from chat history.

Mandatory topics may end `blocked` only for a real environment or organization
policy restriction with evidence and remediation. An ordinary command failure
is unfinished work and remains `in_progress`. Hooks may be `skipped`.

At most one mid-setup restart should be requested, and only when the current
process cannot observe a newly installed tool or the Copilot surface must reload.
The sole cross-session resume command is `/akmaestro-init`.

## Detection and interview

Stable repository facts are written to
`.agentic/setup/detected-repo.json`; transient workstation facts belong under
gitignored `.agentic/local/`. Detection covers:

- product purpose, consumers, and workflows;
- languages, frameworks, manifests, lockfiles, and repository layout;
- bootstrap, build, test, lint, typecheck, run, and verification actions;
- CI configuration and documented Git policies;
- complex modules, restricted paths, and existing agent customization;
- sibling repositories, each confirmed as `modifiable` or `read-only`.

In subproject mode, "repository facts" means facts about the selected product.
Detection does not traverse sibling products. It may read the enclosing Git
root only for policies and CI facts that apply to the product.

The agent presents one sourced matrix and asks only about missing, conflicting,
or low-confidence rows. History can suggest a pattern but does not establish
team policy without lead confirmation.

### Complex-module knowledge

Complex-module candidates include their normalized product-relative path,
purpose, strongest source, confidence, and any existing scoped instruction.
The lead corrects and confirms the candidate list, including any intentional
parent/child overlap. A non-empty confirmed list produces one question:

```text
Generate scoped knowledge for all selected modules now?
```

An accepted answer records `generate_now`. Every selected module starts
pending, and the controller keeps the instructions topic `in_progress` and
prevents setup finalization until each module artifact validates. A declined
answer records `defer`; setup may complete, but status and finalization retain an exact
`/setup-instructions module <path>` command for every pending module. An empty
confirmed list records `not_applicable` without asking the question.

The default artifact is
`.github/instructions/<module-id>.instructions.md`, with a product-relative
POSIX `applyTo: "<module-path>/**"` scope. The controller's `module-targets`
command is the filename authority. Nested `<module>/AGENTS.md` files are
generated only after a separate explicit request. Evidence is revised after
each validated module, so an interrupted `generate_now` run resumes at the
first pending module through `/akmaestro-init`.

## Existing-file changes

New files may be created directly. Existing instruction and hook files use the
controller's deterministic merge protocol:

1. write the complete proposed content to a local temporary file;
2. run `merge-plan --target <path> --input <file>`;
3. show the returned unified diff;
4. obtain explicit confirmation;
5. run `merge-apply --plan-id <id> --approved`.

The plan stores the target preimage hash. If the target changes after review,
application fails and a new plan is required. The controller accepts only known
instruction and hook destinations and refuses paths that resolve outside the
repository.

## Strict evidence

Every topic writes its evidence before its terminal aggregate transition.
Topic contracts are exact and reject unknown or missing fields:

- instructions: product, all seven command definitions/results, verification,
  six Git policies, repository context, the module-knowledge decision,
  generated files, and pending modules;
- tooling: selected languages, Graphifyy version/query/graph paths, one LSP per
  language, requirements revision, restart requirement, and blockers;
- skills: kit version, complete expected and verified catalog, collisions,
  discovery by surface, restart requirement, and blockers;
- hooks: enabled state, selected hooks, config, checks, live-verified surfaces,
  and blockers.

Instruction actions are argument arrays with a relative working directory and
timeout. After user confirmation, `action-check` executes without a shell and
records the result in `.agentic/setup/action-checks.json`. Instructions evidence
must reference the exact controller-issued `checkId` and action hash. A fabricated,
omitted, substituted, or empty blocked check is rejected.

An instructions-evidence excerpt for accepted module generation is:

```json
{
  "repositoryContext": {
    "complexModules": [
      {"path": "services/payments", "purpose": "Payment processing"}
    ]
  },
  "moduleKnowledge": {"decision": "generate_now"},
  "generatedFiles": [
    "AGENTS.md",
    ".github/copilot-instructions.md",
    ".github/instructions/tests.instructions.md"
  ],
  "pendingModules": ["services/payments"]
}
```

`pendingModules` must be a subset of the confirmed list. `generate_now` may be
persisted while work is in progress but cannot transition instructions to
either terminal state or finalize setup until the list is empty. `defer`
permits completion with pending modules as explicit warnings; `not_applicable`
requires both module lists to be empty.

## State contract

State version 3 is a clean contract because earlier versions were not shipped.
All mutations go through the bundled standard-library controller:

```text
uv run --no-project python .agentic/bin/akmaestro-state.py <command>
```

The controller uses optimistic revisions, worktree-local locks, validation, and
atomic replacement. Derived fields such as overall status, next topic, and next
command are never persisted as a second source of truth.

```json
{
  "$schema": "../schemas/setup-state.schema.json",
  "version": 3,
  "revision": 8,
  "profile": {
    "mandatory": ["instructions", "tooling", "skills"],
    "optional": ["hooks"]
  },
  "topics": {
    "instructions": {"status": "complete", "optional": false, "updatedAt": "..."},
    "tooling": {"status": "blocked", "optional": false, "blocker": "...", "updatedAt": "..."},
    "skills": {"status": "complete", "optional": false, "updatedAt": "..."},
    "hooks": {"status": "skipped", "optional": true, "updatedAt": "..."}
  },
  "finalization": {"status": "complete", "guideHash": "<sha256>", "updatedAt": "..."},
  "createdAt": "...",
  "updatedAt": "...",
  "completedAt": "..."
}
```

## Persistence boundary

Committed:

```text
.agentic/bin/akmaestro-state.py
.agentic/schemas/*.schema.json
.agentic/STATE-PROTOCOL.md
.agentic/setup/initialization-state.json
.agentic/setup/*-state.json
.agentic/setup/action-checks.json
.agentic/setup/environment-requirements.json
.agentic/setup/kit-manifest.json
.agentic/hooks/*
.agentic/features/*
```

Gitignored and worktree-local:

```text
.agentic/local/readiness.json
.agentic/local/active-feature.json
.agentic/local/graphs/<repository-id>/graph.json
.agentic/local/locks/
.agentic/local/merge-plans/
.agentic/audit/
```

Graphifyy always writes to the main repository's local graph cache, including
when a modifiable or read-only sibling is the extraction source. A read-only
sibling is never a generated-output destination.

## Hook consent

When hook assets are included, `hooks.json` starts with `disableAllHooks: true`.
`/setup-hooks` explains the selected guards, metadata-only audit trail, and
structured lint action; tests them while disabled; and asks for explicit
activation consent. `hooks-enable` and `hooks-disable` update both files under
one local lock; each write is atomic, ordinary failures roll the configuration
back, and installer reconciliation treats the actual `hooks.json` flag as
authoritative after an interruption.

Hooks are defense in depth. They must not be required for workflow correctness,
because VS Code support or organization policy may disable them. Guard scripts
always exit zero. Malformed unknown events allow, while a parsed edit path that
cannot be canonically resolved inside a declared writable root is denied.

## Finalization and handoff

After all topics are terminal, `setup-finalize` validates their artifacts,
renders `.github/AGENTIC.md` deterministically, records its hash, and returns
exact shared/local/blocked/pending inventories. It is idempotent and resumable.
An existing unowned team guide is never replaced without explicit confirmation
of the `setup-finalize --preview` diff and the `--approved-guide-replace` flag.

The shared inventory includes every validated instructions-evidence
`generatedFiles` path, including scoped module artifacts. The lead reviews and
commits that inventory. Developers then pull that commit and run `/feature`.
`/feature` validates committed initialization, probes the current developer's
`uv`, Graphifyy, LSPs, and local graphs, and offers each recorded remediation
action for confirmation. It executes only the confirmed argument array through
controller-owned `remediation-run --approved`, without a shell and only in a
declared writable repository. It never sends a developer back through repository
initialization.

`/status` is the read-only answer to “where are we?” Setup takes precedence until
finalization succeeds; afterward it reports readiness and feature progress.
`/akmaestro-init help` and `/feature help` explain their respective flows, and
`/doctor` provides deeper diagnostics.
