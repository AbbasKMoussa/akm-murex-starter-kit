# Stage 1: Setup Flow (master spec)

This is the spine that ties the four setup topics together. The topic docs hold
the depth; this doc defines the orchestrator, bootstrap, detection, state,
merge policy, and the unified status/help. Decisions are recorded in
`docs/setup-flow-decisions.md`.

Stage 1 is run **once per repository by the team lead**. The outcome: the repo has agent
instruction files, the kit skills, optional hooks, and verified tooling (LSP +
Graphifyy) — i.e. it is configured for agentic coding. Stage 2 (the feature
flow) is a separate, repeatable flow that every developer starts directly.

## Delivery and bootstrap

- **Installer:** `uvx akmaestro init`. `uv` remains a developer prerequisite
  because it also runs the repo-local state controller. Source of
  truth is an internal git repo intended for publication to the internal Python
  registry. The installer is idempotent and never overwrites existing files.
  Upgrades use `uvx akmaestro update`, which refreshes only files still
  attributable to the kit and preserves customized files.
- **Bootstrap = the installer.** It lays down all 18 Stage 1 and Stage 2 skills,
  schemas/controller, optional hooks, and minimal instruction pointers. After
  that, the team lead runs `/init`, reviews the output, and commits it. Other
  developers pull the commit and start with `/feature`.
- **Never overwrite without confirmation** (decision 6). New files are created
  directly; existing customization is protected by the merge policy below.

### Installer versus runtime responsibilities

All dynamic logic — detection, interview, generation, and section-aware merge —
lives in the **skills**. State validation and transitions live in a bundled
standard-library controller. `uvx akmaestro init`:

1. copies versioned assets and the state controller into the repo, and
2. prints the one line that starts the flow ("now run `/init`").

Asset mapping (package → repo):

| In the package | Copied to | Notes |
| --- | --- | --- |
| `assets/skills/*` | `.github/skills/<name>/` | all 18 Stage 1 + Stage 2 skills; existing same-named files are skipped |
| `state.py` | `.agentic/bin/akmaestro-state.py` | deterministic standard-library controller, run through `uv` |
| `assets/schemas/*` | `.agentic/schemas/` | Draft 2020-12 contracts for setup, requirements, readiness, features, and local selection |
| `assets/runtime/STATE-PROTOCOL.md` | `.agentic/STATE-PROTOCOL.md` | shared mutation/readiness protocol used by every flow skill |
| `assets/hooks/hooks.json`, `assets/hooks/scripts/*` | `.github/hooks/` | only when hooks are opted in; existing files are skipped by the installer and merged later by `/setup-hooks` when needed |
| `assets/hooks-data/*` | `.agentic/hooks/` | seed config data |
| `assets/bootstrap/AGENTS.bootstrap.md`, `assets/bootstrap/copilot-instructions.bootstrap.md` | repo root / `.github/` | minimal pointer files, **only if absent** |
| (generated) | `.agentic/setup/*`, `.agentic/features/*` | committed state/evidence created at runtime |
| (generated) | `.agentic/local/*` | gitignored worktree readiness, selection, locks, and temporary inputs |

The installer copies templates verbatim. Repo-specific generation (filling
`AGENTS.md` from detected facts + answers, section-merging into existing files)
is done by the skills. Skills never hand-edit controller-owned state.

## Commands and skill decomposition (hybrid: guided + à la carte)

Stage 1 is **per-topic skills + an `init` orchestrator**, mirroring how `teach`
and `doctor` are built (standalone, auto-discoverable skills). The command verb
is standardized to `setup-<topic>`.

| Command (skill) | Behavior |
| --- | --- |
| `/init` (orchestrator) | Guided, resumable: runs the topics in mandatory order, pausing for input; resumes from saved state. Delegates to the per-topic skills. Also handles `init status` and `init help`. |
| `/setup-instructions` | Instruction-files topic. Handles root setup and the `module <path>` / `module all` sub-actions. |
| `/setup-tooling` | Tooling topic (LSP + Graphifyy). |
| `/setup-skills` | Skills topic. |
| `/setup-hooks` | Hooks topic (optional). |

The `init` orchestrator and the standalone skills share the same per-topic logic
and the same `.agentic/` state, so running a topic standalone advances the same
`init status`. Stage 1 therefore uses five flow-skills (`init` + four
`setup-*`) alongside `teach` and `doctor`; all 11 Stage 2 skills are already
present from the same bootstrap.

### Out of scope

**MCP servers** are a separate Copilot extension surface and are intentionally
**not** part of Stage 1. Skills, instructions, hooks, and tooling are the
delivery mechanisms; MCP may be revisited later.

## Topic sequence and mandatory profile

Guided order, with completion requirements:

1. **Instruction files** — **mandatory**
2. **Tooling** (LSP + Graphifyy) — **mandatory**
3. **Skills** — **mandatory**
4. **Hooks** — **optional** (recommended; install-by-default but the user may
   decline, and enterprise policy may disable them)

Setup is **complete** when the three mandatory topics each meet their documented
completion criteria. Hooks never block completion; their state is reported as
optional.

### Blocked-not-failed escape (tooling)

Tooling is mandatory, but a topic can legitimately be impossible to finish in a
given environment (air-gapped repo, no registry access, org policy blocking an
install). When a mandatory step is blocked by the environment rather than by
incomplete work, it is recorded as **`blocked`** (not `failed`), and overall
setup may still complete with a documented manual-completion path. This applies
especially to Graphifyy: if LSP is verified but Graphifyy genuinely cannot install
or run, tooling is `blocked`, the manual steps are recorded in
`tooling-state.json`, and `init` reports setup complete-with-blocked-items rather
than refusing to finish. `blocked` requires a real environment reason — not just
a skipped or failed step.

### What "instructions complete" means

The instruction-files gate is satisfied by the **root** files (root `AGENTS.md`,
`copilot-instructions.md`, `tests.instructions.md`). Complex-module `AGENTS.md`
files are tracked in state and **recommended**, but pending modules are reported
as warnings and do **not** block the mandatory gate. A repo with complex modules
can complete setup with module files still pending; `init status` keeps surfacing
them via `/setup-instructions module <path>`.

## Flow phases

Each topic, whether guided or standalone, runs the same phases:

1. **Preflight / detection** — gather repo facts (see below). Cheap, read-only.
2. **Interview** — ask only the targeted questions the topic defines, pre-filled
   from detection so the user mostly confirms rather than types. Keep it short.
3. **Generate** — produce repo-specific files from detected facts + answers
   (never generic copies), applying the merge policy.
4. **Persist evidence** — write stable facts, answers, and topic evidence first.
5. **Validate** — check the topic's completion criteria (files exist AND
   tools/guards verified). Per-topic criteria must pass (decision: validation
   gate). For instructions this includes **smoke-verify**: run the captured build
   and test commands once to confirm they actually work, so the agent's
   run/verify loop is trustworthy. Smoke-verify is blocked-not-failed (an
   environment that can't build is recorded as `blocked`, not failed).
6. **Commit transition** — use the controller with the expected revision as the
   final operation; report its derived next step.

## Preflight detection

Stable facts are cached in committed `.agentic/setup/detected-repo.json` and
refreshed on re-run:

- languages and frameworks;
- package managers and lockfiles;
- build, test, and lint commands (from scripts/manifests/CI);
- CI system and key checks;
- monorepo shape and candidate **complex modules**;
- existing customization files: `AGENTS.md`, `.github/copilot-instructions.md`,
  `.github/instructions/`, nested `AGENTS.md`, `.github/skills/`,
  `.github/hooks/`, `.agentic/`;
- declared sibling repository paths and roles.

Branch, clean/dirty status, PATH contents, installed tools, and other
workstation facts go under `.agentic/local/` and are never committed.

Detection feeds both the interview (pre-filled answers) and generation
(e.g. build/test commands flow into `AGENTS.md` and `tests.instructions.md`;
detected lint commands seed `.agentic/hooks/lint-commands.json`; restricted areas
seed `.agentic/hooks/restricted-paths.txt`).

## Existing-file merge policy (section-aware merge + confirm)

When a target file already exists:

1. Parse it into sections (Markdown headings for `AGENTS.md` and instruction
   files; the JSON object for `hooks.json`; etc.).
2. Compute the additions/changes the topic would make, mapped to sections.
3. Merge new content into the matching section; if a section is absent, add it.
4. **Show the diff and get confirmation before applying.** Never delete or weaken
   existing content; on a genuine conflict, surface it and let the user choose.
5. New files (no existing target) are created directly without a diff prompt.

Special cases:
- `hooks.json`: merge handler arrays per event; never drop existing handlers.
- Scripts and skills the user customized: do not overwrite; report and skip.

## State and artifacts

```text
.agentic/
  bin/akmaestro-state.py        # kit-owned deterministic controller
  schemas/*.schema.json         # versioned state contracts
  STATE-PROTOCOL.md             # mutation and readiness rules
  setup/
    initialization-state.json   # committed authoritative topic state
    detected-repo.json          # stable repository facts only
    answers.json                # interview answers
    environment-requirements.json # committed developer prerequisites/probes
    instructions-state.json     # topic evidence, no duplicate status
    tooling-state.json          # topic evidence, no duplicate status
    skills-state.json           # topic evidence, no duplicate status
    hooks-state.json            # topic evidence, no duplicate status
    modules/<module-id>.json    # per complex module
    install-log.md              # human-readable log of changes
  hooks/                        # machine-readable hook config data
  local/                        # readiness, selected feature, locks; gitignored
  audit/                        # local, gitignored audit trail
  features/                     # Stage 2
  decisions/                    # Stage 2 / general
```

`initialization-state.json` (shape):

```json
{
  "$schema": "../schemas/setup-state.schema.json",
  "version": 2,
  "revision": 7,
  "profile": { "mandatory": ["instructions", "tooling", "skills"], "optional": ["hooks"] },
  "topics": {
    "instructions": { "status": "complete", "optional": false, "updatedAt": "…" },
    "tooling":      { "status": "blocked", "optional": false, "blocker": "…", "updatedAt": "…" },
    "skills":       { "status": "complete", "optional": false, "updatedAt": "…" },
    "hooks":        { "status": "skipped", "optional": true, "updatedAt": "…" }
  },
  "createdAt": "…",
  "updatedAt": "…",
  "completedAt": "…"
}
```

Legal statuses are `pending`, `in_progress`, `complete`, `blocked`, and optional
`skipped`. `overall`, next topic, and next command are derived by `setup-status`
and never persisted. Each topic file is versioned evidence only. Mutations are
serialized by local directory locks, use optimistic revisions, and replace JSON
atomically. The human-readable artifact/evidence is written before the state
transition, so interruption always leaves a resumable boundary.

`environment-requirements.json` contains structured probe and remediation
argument arrays for mandatory `uv`, Graphifyy version/query checks, selected
`lsp-*` tools, and graph artifacts. Probes may set a repository-relative `cwd`
for sibling repositories. `/feature` writes results to gitignored
`.agentic/local/readiness.json`, keyed by a hash of those requirements.

## Resumability and multi-session

The flow may span sessions. `/init` runs `setup-status` and continues from its
derived next topic. Re-running a completed transition is idempotent; a stale
revision forces a reread rather than an overwrite. A new session is requested after
tooling/skills/hooks changes so newly added tools, skills, and hooks are
discovered (see those topic docs).

## Unified status and help

`init status` aggregates the four topic fragments into one report, marks hooks as
optional, and gives the single most important next step. Example:

```text
Setup status (mandatory: instructions, tooling, skills | optional: hooks)

Instruction files: complete
Tooling:           in_progress  (LSP ok; Graphifyy graph not generated)
Skills:            complete
Hooks:             optional — not installed

Overall: incomplete (tooling in progress)
Next: finish Graphifyy in `/setup-tooling` (`graphify extract .`)
```

`doctor` is the deeper, active health check (probes environment + integrity);
`init status` reports flow progress from state. They are complementary.

## Completion and handoff

Setup is complete when `instructions`, `tooling`, and `skills` each pass their
topic completion criteria or are `blocked` for a recorded environmental reason.
Blocked mandatory items remain visible as manual follow-ups. On completion,
`init`:

1. generates/updates **`.github/AGENTIC.md`** — a short, committed
   discoverability guide so the whole team knows what is installed and how
   to use it: the available skills and how
   to invoke them (`/teach`, `/doctor`, …), which hooks are active, where the
   instruction files live, and how to run/verify the app. It is regenerated on
   re-run and linked from `AGENTS.md`/README;
2. validates v2 state and prints a summary;
3. asks the lead to review and commit the shared output, then hands developers
   directly to Stage 2:

```text
Setup complete. Mandatory topics verified or documented as blocked; hooks optional/installed.
Team guide written to .github/AGENTIC.md. Review and commit the shared files.
Developers: pull the commit and run `/feature`; do not rerun `/init`.
```

(The feature flow is Stage 2 and is specified separately.)
