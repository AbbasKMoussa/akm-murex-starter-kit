---
name: setup-instructions
description: >-
  Set up and verify repository-specific agent instructions: root AGENTS.md,
  .github/copilot-instructions.md, path-scoped test instructions, and optional
  module-scoped instructions. Use for "/setup-instructions", instruction setup,
  or the instructions step of /akmaestro-init. Supports "module <path>" and
  "module all".
---

# setup-instructions - repository operating context

Mandatory topic. Produce concise instructions that tell an agent what the
product does, how to work and verify changes, which Git policies exist, and how
this repository relates to the rest of the workspace. Detect first; ask the team
lead to confirm rather than making them retype repository facts.

`AGENTS.md` is the cross-agent source of truth. Keep
`.github/copilot-instructions.md` as a short pointer. Put test-specific rules in
`.github/instructions/tests.instructions.md`; module-scoped instruction files
describe only what differs for their `applyTo` paths. Create a nested
`<module>/AGENTS.md` only when the lead explicitly requests a cross-agent file.

## State protocol

Read `.agentic/STATE-PROTOCOL.md`. Run `setup-init` and `setup-status` through:

```text
uv run --no-project python .agentic/bin/akmaestro-state.py <command>
```

For the main instructions topic, transition it to `in_progress` with the
revision just read when required. Never edit aggregate state or committed
evidence directly. A deferred `module <path>` follow-up may revise instructions
evidence after the topic is complete; it does not reopen or hand-edit the setup
topic.

## 1. Detect with provenance

Inspect before asking:

- product: README, package metadata, architecture/product docs, service manifests;
- commands: CI workflows, package scripts, Makefiles/task runners, lockfiles,
  contribution docs, and existing instructions;
- Git workflow: contribution docs, repository configuration, pull-request
  templates, and recent commit messages;
- CI, complex modules, restricted areas, existing instruction files, and locally
  checked-out sibling repositories.

Record the source of every proposed product, command, and Git answer. Do not
treat the current branch, dirty status, or one developer's PATH as team policy.

## 2. Confirm one sourced summary

Present one compact matrix. Every proposal shows its strongest source and a
confidence of `high`, `medium`, or `low`, so the lead can validate rather than
retype it. Keep observed patterns distinct from documented policy. For example:

```text
Repository initialization proposal

Product
| Field | Proposed value | Source | Confidence |
| Summary | Internal pricing service used by checkout. | README.md | high |
| Consumers | checkout; pricing operations | docs/architecture.md | medium |
| Workflows | calculate quote; publish rules | README.md | high |

Commands
| Action | Proposed value | Source | Confidence |
| Bootstrap | uv sync | CONTRIBUTING.md | high |
| Build | uv build | pyproject.toml | high |
| Tests | uv run pytest | .github/workflows/ci.yml | high |
| Lint | not applicable - no linter configured | manifests + CI | medium |
| Typecheck | not applicable - no typechecker configured | manifests + CI | medium |
| Run | uv run pricing-api | README.md | high |
| Verify | uv run pytest; manual GET /health | CI + runbook.md | high |

Git workflow
| Policy | Proposed value | Source | Confidence |
| Base branch | main | origin/HEAD | high |
| Branch naming | feature/<ticket>-<description> | CONTRIBUTING.md | high |
| Commit style | observed Conventional Commits; policy unconfirmed | history | low |
| Direct push | prohibited | repository rules | high |

Repository context
| Item | Proposed value | Source | Confidence |
| Restricted paths | .env; secrets/** | existing instructions | high |
| Siblings | ../pricing-lib (modifiable) | workspace + lead | medium |

Module candidates
| Path | Purpose | Source | Confidence | Existing scope |
| services/pricing | Pricing rules and quote calculation. | docs/architecture.md | medium | none |

Confirm the proposal or correct only the rows that are wrong or uncertain.
```

Ask targeted follow-ups only for missing, low-confidence, or conflicting rows.
Do not turn the checklist below into a question-by-question interview. Establish:

1. a specific product summary, its consumers, and primary workflows;
2. bootstrap, build, test, lint, typecheck, run, and automated verification;
3. at least one automated or manual verification path;
4. base branch plus branch naming, commit style, direct-push, pull-request,
   signing, and ticket-reference policies;
5. CI notes, complex modules, restricted paths, and sibling repositories;
6. whether an agent may create branches, commit, push, and open pull requests.

Never elevate recent history into policy without lead confirmation. Prefer
contribution docs and repository/ruleset configuration, then CI and manifests;
use history only as a low-confidence observed pattern. Never invent a command or
policy. Every command is either `configured` with one
or more structured actions, or `not_applicable` with a reason. Every Git policy
is `defined`, `none`, or `unspecified`, with provenance and an explanation when
it is not defined.

For each sibling repository, record its relative checkout path, purpose, and
role: **modifiable** (owned by this team and changeable here) or **read-only**
(consult only). A modifiable sibling also requires how its change reaches this
repository. Add only modifiable sibling paths to
`.agentic/hooks/editable-paths.txt`.

## 3. Confirm module knowledge

Detect complex-module candidates from architecture documents, manifests, code
entry points, tests, CI, and existing scoped instructions. Within the single
sourced summary, present one table with each candidate's normalized
product-relative path, purpose, strongest source, `high`/`medium`/`low`
confidence, and existing `applyTo` scope. Obtain one corrected, confirmed
selection rather than accepting detection silently.

Flag every parent/child overlap, explain that both scopes may apply, and require
explicit overlap confirmation. Confirm that any removed candidate is a false
positive or intentionally outside the product's module-knowledge scope. When
the confirmed selection is empty, record `moduleKnowledge.decision` as
`not_applicable` and keep `complexModules` and `pendingModules` empty.

For a non-empty confirmed selection, ask exactly:

```text
Generate scoped knowledge for all selected modules now?
```

An affirmative answer records `generate_now`; declining records `defer`.
Initially, every selected module is pending under either decision. Persist this
decision and the confirmed modules in the first instructions evidence revision.
Do not treat `defer` as `not_applicable`, and do not silently change an accepted
decision because generation later stops.

## 4. Generate root instructions non-destructively

Create or section-merge:

- `AGENTS.md`: Product, Repository Context, Workspace & Dependencies, Stack,
  Setup, Build, Tests, Run, Verify a Change, CI, Complex Modules, Git Workflow,
  and Agent Rules;
- `.github/copilot-instructions.md`: short pointer to `AGENTS.md` and scoped
  instructions;
- `.github/instructions/tests.instructions.md`: `applyTo` frontmatter, confirmed
  test actions, and behavior-focused test guidance.

For an existing file, parse sections, show the proposed diff, and obtain
confirmation before applying. Never delete or weaken existing content. Create a
missing file directly. No generated file may retain AKMaestro placeholders.

For every existing file, write the complete proposed UTF-8 content to a local
file, create a controller-bound plan, and show its returned diff:

```text
uv run --no-project python .agentic/bin/akmaestro-state.py merge-plan --target <repo-relative-target> --input <proposed-file>
```

Only after the lead approves that exact diff, apply its returned identifier:

```text
uv run --no-project python .agentic/bin/akmaestro-state.py merge-apply --plan-id <id> --approved
```

Never pass `--approved` before confirmation. If the target changes after review,
discard the plan, regenerate the proposal, and show a new diff.

## 5. Check commands safely

Represent every action as a JSON argument array with optional repository-relative
`cwd`, `label`, and `timeoutSeconds`; never store a shell command string. Before
running bootstrap or any other machine-changing action, show the exact action
and obtain explicit confirmation.

Run each confirmed finite action through the controller so it uses
`subprocess` without a shell and enforces the timeout:

```text
uv run --no-project python .agentic/bin/akmaestro-state.py action-check --input <local-action-json>
```

Preserve its `actionHash`, status, optional exit code, detail, and `checkedAt` in
the matching command result. A passing result requires one passing check for
every configured action; substituted or omitted action hashes are rejected.

Build, test, lint, typecheck, and automated verification actions that are
configured must pass or have a genuine environmental `blocked` result. A normal
failure is unfinished work: correct the command or repository and rerun it.

Bootstrap may be `documented` without execution when dependencies are already
satisfied. A long-running `run` action may be `documented`; prefer a bounded
startup plus health check when the repository provides one. Record manual
verification as explicit ordered steps. Never record credentials or full command
output in committed evidence.

## 6. Persist strict evidence

Use `references/instructions-evidence.example.json` as the structural example.
Replace every example value and check record with this repository's confirmed
facts and actual `action-check` output; never copy its claims as evidence.

Build the local JSON input for `evidence-write instructions` with exactly:

- `product`: `summary`, `consumers`, `primaryWorkflows`, `sources`;
- `commands`: all seven canonical command definitions;
- `commandResults`: matching `passed`, `blocked`, `documented`, or
  `not_applicable` results with concise detail and per-action check records;
- `manualVerification`;
- `gitWorkflow`: `baseBranch`, all six policies, and sources;
- `repositoryContext`: CI notes, complex modules, sibling repositories, and
  restricted paths;
- `moduleKnowledge`: the confirmed `generate_now`, `defer`, or `not_applicable`
  decision;
- `generatedFiles` and `pendingModules`.

Write it atomically:

```text
uv run --no-project python .agentic/bin/akmaestro-state.py evidence-write instructions --input <local-evidence-json> --expected-revision <evidence-revision-or-0>
```

The controller rejects incomplete answers, unsafe command strings, omitted or
substituted action checks, mismatched command results, missing verification,
missing/placeholder artifacts, and Git policies that were never answered.

## 7. Generate selected module knowledge

Whenever generating module knowledge, pass the full confirmed list to the
controller and use its returned mapping as the sole source of filenames:

```text
uv run --no-project python .agentic/bin/akmaestro-state.py module-targets --input <local-modules-json>
```

The input is exactly `{"modules": ["<normalized-path>", ...]}`. Process pending
modules in normalized path order. The mapping handles existing exact scopes and
filename collisions; never derive or substitute a target yourself. On a resumed
accepted run, use the first controller-returned pending module from
`setup-status`; the only cross-session resume command is `/akmaestro-init`.

For each pending module, inspect its documentation, manifests, entry points,
tests, CI, and existing instructions. Present one compact sourced draft and ask
only about missing, conflicting, or low-confidence facts. The controller target
must have this exact scope and these seven second-level sections:

```markdown
---
applyTo: "<module-path>/**"
---

# <Module name>

## Purpose
## Boundaries
## Commands
## Important Paths
## Patterns
## Pitfalls
## Restrictions
```

Every section must contain confirmed, module-specific guidance and no
placeholder. State explicitly when a section has no module-specific difference
from root guidance; do not duplicate that general guidance. A nested
`<module>/AGENTS.md` is a separate, explicitly requested cross-agent artifact;
it may accompany but never replace the controller-targeted scoped file. When
requested, append its exact path to `generatedFiles` only alongside the
completed module's controller target. This makes both artifacts part of the
shared inventory the lead reviews and commits.

Create a missing target directly. For an existing target, use `merge-plan`,
show the exact diff, and call `merge-apply --approved` only after approval.
Declining an existing-file merge leaves that module pending. It does not alter
`moduleKnowledge.decision`.

For each scoped artifact, prepare the next evidence input by appending its
returned target to `generatedFiles` and removing only that module from
`pendingModules`. When the lead requested the optional nested `AGENTS.md`,
append its exact `<module>/AGENTS.md` path in the same evidence only after both
it and the required scoped target are complete. Call `evidence-write
instructions` with the latest evidence revision; only a successful controller
write marks those artifacts validated and advances the evidence revision.
Never list a nested `AGENTS.md` for an unconfirmed or pending module, batch an
unvalidated artifact into evidence, or maintain another module-status file. If
the lead no longer accepts generation now, explicitly confirm changing
`generate_now` to `defer`, write that new evidence revision, and only then allow
the topic to complete. The controller-returned `/setup-instructions module
<path>` commands remain the deferred follow-ups for `module <path>` or `module
all`.

## Completion

Complete when strict evidence passes; the three root instruction files exist
without placeholders; existing content was merged with confirmation; every
canonical command has an explicit disposition; configured finite checks passed
or have documented environmental blockers; at least one verification path
exists; and every Git policy is defined or explicitly absent/unspecified.

With `generate_now`, pending modules are unfinished accepted work and the
controller rejects either terminal instructions state (`complete` or `blocked`).
With `defer`, pending modules are non-blocking follow-ups. With
`not_applicable`, both confirmed and pending module lists must be empty.

Write evidence first, then make the final aggregate transition using the latest
setup-state revision. A blocked command result may transition instructions to
`blocked` only after accepted module generation has no pending modules. Use
`blocked --reason <reason>`; otherwise transition to `complete` only after the
controller accepts it. Rerun `setup-status` and return to the orchestrator,
which loads the next installed topic skill in the same session. If a restart is
genuinely required, the only resume command is `/akmaestro-init`.
