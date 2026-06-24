# Stage 1: Setup Flow (master spec)

This is the spine that ties the four setup topics together. The topic docs hold
the depth; this doc defines the orchestrator, bootstrap, detection, state,
merge policy, and the unified status/help. Decisions are recorded in
`docs/setup-flow-decisions.md`.

Stage 1 is run **once per repository**. The outcome: the repo has agent
instruction files, the kit skills, optional hooks, and verified tooling (LSP +
Graphifyy) — i.e. it is configured for agentic coding. Stage 2 (the feature
flow) is a separate, repeatable flow that builds on this.

## Delivery and bootstrap

- **Installer:** `uvx akmaestro init` (also `pipx`/`pip`). Source of
  truth is an internal git repo published to the internal Python registry. The
  installer is idempotent and re-runnable to upgrade.
- **Bootstrap = the installer.** It lays down the kit flow-skills
  (`.github/skills/init`, `.github/skills/doctor`, `.github/skills/teach`) plus a
  minimal `AGENTS.md`/`.github/copilot-instructions.md` pointer if none exists,
  so the agent understands the flow. After that, the developer runs `/init` (or
  says "let's run the initialization flow") on any Copilot surface.
- **Never overwrite without confirmation** (decision 6). New files are created
  directly; existing customization is protected by the merge policy below.

### The installer is a thin file-dropper

All dynamic logic — detection, interview, generation, and section-aware merge —
lives in the **skills** (run by the agent), not in the installer. `uvx
akmaestro init` only:

1. copies static assets from the package into the repo, and
2. prints the one line that starts the flow ("now run `/init`").

Asset mapping (package → repo):

| In the package | Copied to | Notes |
| --- | --- | --- |
| `assets/skills/{init,setup-instructions,setup-tooling,setup-skills,setup-hooks,teach,doctor}/` | `.github/skills/<name>/` | the flow-skills + catalog skill; skipped if a same-named skill the user customized exists |
| `assets/hooks/hooks.json`, `assets/hooks/scripts/*` | `.github/hooks/` | only when hooks are opted in; merged per decision 14 |
| `assets/hooks-data/*` | `.agentic/hooks/` | seed config data |
| `assets/AGENTS.bootstrap.md`, `assets/copilot-instructions.bootstrap.md` | repo root / `.github/` | minimal pointer files, **only if absent** |
| (generated) | `.agentic/setup/*` | created by the skills at runtime, not the installer |

The installer copies templates verbatim. Repo-specific generation (filling
`AGENTS.md` from detected facts + answers, section-merging into existing files)
is done by the skills, not by the installer. This keeps the Python package tiny
and puts ~all the build effort in skill authoring.

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
`init status`. Stage 1 therefore ships as five flow-skills (`init` +
four `setup-*`) alongside the catalog skill `teach` and the health-check `doctor`.

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
them via `init module <path>`.

## Flow phases

Each topic, whether guided or standalone, runs the same phases:

1. **Preflight / detection** — gather repo facts (see below). Cheap, read-only.
2. **Interview** — ask only the targeted questions the topic defines, pre-filled
   from detection so the user mostly confirms rather than types. Keep it short.
3. **Generate** — produce repo-specific files from detected facts + answers
   (never generic copies), applying the merge policy.
4. **Persist** — write detected facts, answers, and current step to `.agentic/`.
5. **Validate** — check the topic's completion criteria (files exist AND
   tools/guards verified). Per-topic criteria must pass (decision: validation
   gate). For instructions this includes **smoke-verify**: run the captured build
   and test commands once to confirm they actually work, so the agent's
   run/verify loop is trustworthy. Smoke-verify is blocked-not-failed (an
   environment that can't build is recorded as `blocked`, not failed).
6. **Handoff** — report what was done and the recommended next step.

## Preflight detection

Detected once and cached in `.agentic/setup/detected-repo.json`; refreshed on
re-run. Facts:

- languages and frameworks;
- package managers and lockfiles;
- build, test, and lint commands (from scripts/manifests/CI);
- CI system and key checks;
- monorepo shape and candidate **complex modules**;
- existing customization files: `AGENTS.md`, `.github/copilot-instructions.md`,
  `.github/instructions/`, nested `AGENTS.md`, `.github/skills/`,
  `.github/hooks/`, `.agentic/`;
- git state (branch, clean/dirty, remote).

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
  setup/
    initialization-state.json   # overall: profile, per-topic status, current step, session
    detected-repo.json          # cached preflight facts
    answers.json                # interview answers
    instructions-state.json     # per instruction-files topic
    tooling-state.json          # per tooling topic
    skills-state.json           # per skills topic
    hooks-state.json            # per hooks topic
    modules/<module-id>.json    # per complex module
    install-log.md              # human-readable log of changes
  hooks/                        # machine-readable hook config data
  audit/                        # local, gitignored audit trail
  features/                     # Stage 2
  stories/                      # Stage 2
  decisions/                    # Stage 2 / general
```

`initialization-state.json` (shape):

```json
{
  "version": 1,
  "profile": { "mandatory": ["instructions", "tooling", "skills"], "optional": ["hooks"] },
  "topics": {
    "instructions": { "status": "complete|partial|pending|blocked", "updatedAt": "…" },
    "tooling":      { "status": "…" },
    "skills":       { "status": "…" },
    "hooks":        { "status": "…", "optional": true }
  },
  "currentStep": "tooling",
  "overall": "incomplete|complete",
  "lastSession": "…"
}
```

Each topic's own state file holds the detail its topic doc specifies. State is
the single source of truth for resume and status.

## Resumability and multi-session

The flow may span sessions. `/init` reads `initialization-state.json`, reports
where it stopped, and continues from `currentStep`. Re-running any topic is safe
(idempotent) and updates the same state. A new Copilot session is requested after
tooling/skills/hooks installs so newly added tools, skills, and hooks are
discovered (see those topic docs).

## Unified status and help

`init status` aggregates the four topic fragments into one report, marks hooks as
optional, and gives the single most important next step. Example:

```text
Setup status (mandatory: instructions, tooling, skills | optional: hooks)

Instruction files: complete
Tooling:           partial  (LSP ok; Graphifyy graph not generated)
Skills:            complete
Hooks:             optional — not installed

Overall: incomplete (tooling pending)
Next: finish Graphifyy in `setup tooling` (graphify extract .)
```

`doctor` is the deeper, active health check (probes environment + integrity);
`init status` reports flow progress from state. They are complementary.

## Completion and handoff

Setup is complete when `instructions`, `tooling`, and `skills` each pass their
topic completion criteria. On completion, `init`:

1. generates/updates **`.github/AGENTIC.md`** — a short, committed
   discoverability guide so the *whole team* (not just the developer who ran
   setup) knows what is installed and how to use it: the available skills and how
   to invoke them (`/teach`, `/doctor`, …), which hooks are active, where the
   instruction files live, and how to run/verify the app. It is regenerated on
   re-run and linked from `AGENTS.md`/README;
2. prints a summary of everything installed/generated and hands off to Stage 2:

```text
Setup complete. Mandatory topics verified; hooks optional/installed.
Team guide written to .github/AGENTIC.md.
Next: start the feature flow with `/feature` (Stage 2).
```

(The feature flow is Stage 2 and is specified separately.)
