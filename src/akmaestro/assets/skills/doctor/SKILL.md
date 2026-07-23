---
name: doctor
description: >-
  Diagnose the health of this repository's agentic setup — instruction files,
  tooling, skills, hooks, and setup state — and report each check as ok / warn /
  fail with a concrete fix. Use when the user wants to check, verify, or
  troubleshoot the agentic setup: "is setup healthy?", "run doctor", "diagnose",
  "why isn't X working", or right after install. Read-only by default; applies
  safe fixes only when the user explicitly asks (e.g. "doctor fix" / "--fix").
---

# doctor — diagnose the agentic setup

Run a health check across the whole agentic setup and produce an actionable
report. This is distinct from `/akmaestro-init status` (which reports setup
*progress*):
doctor actively *probes* the environment and files for problems.

## Modes

- **Diagnose (default):** read-only. Inspect, report, suggest fixes. Change
  nothing.
- **Fix (opt-in):** only when the user explicitly asks ("doctor fix", "--fix",
  "fix it"). Apply **safe** remediations from the catalog below, show what you
  will change first, then confirm. Never modify user-authored content
  (instruction prose, code) and never install binaries automatically — recommend
  the command instead.

## How to run the checks

Use `shell` for probes (`command -v`, `--version`, `jq .`, dry-running scripts)
and read files directly. For any check you cannot run, report it as `warn` with
the reason — never fail the whole run because one probe is unavailable.

Group results by area. For each check emit: a status, a one-line finding, and a
fix when not `ok`.

### 1. Environment

- `bash`, `jq`, `git` on PATH; `pwsh` if Windows/PowerShell is in play; `uv`;
  `graphify`. Report versions. Python is supplied through `uv` for the bundled
  state controller and need not be a separately managed workstation command.
- `jq` missing → **warn**: the bash hook guards fall through to allow without it.
- Note the detected surface (Copilot CLI vs VS Code) if determinable; otherwise
  say it is unknown.
- `.agentic/setup/kit-manifest.json` has `installation_mode` of `repository` or
  `subproject` (`repository` when absent for a legacy install), `project_root`
  of `.`, and a portable relative `git_root`. Resolve it and compare it with
  `git rev-parse --show-toplevel`. A mismatch or running outside the recorded
  AKMaestro root is **fail**. In subproject mode, do not diagnose sibling
  products or write outside the subproject.

### 2. Instruction files

- `AGENTS.md` exists and contains the controller-required sections (Product,
  Repository Context, Workspace & Dependencies, Stack, Setup, Build, Tests,
  Run, Verify a Change, CI, Complex Modules, Git Workflow, Agent Rules).
  Missing file → **fail**; missing sections → **warn**.
- No known AKMaestro bootstrap placeholder remains in `AGENTS.md` or test
  instructions. A remaining placeholder → **fail**.
- `instructions-state.json` passes the controller's topic-specific contract:
  product summary/consumers/workflows, all seven command definitions and
  results, at least one verification path, all six Git policies, repository
  context, and generated-file claims. Invalid or legacy loose evidence →
  **fail** (`/setup-instructions` rewrites it after confirmation).
- Configured build/test/lint/typecheck/verify actions are `passed` or genuinely
  `blocked`; passing results contain one matching hashed check per action;
  bootstrap/run may be `documented`. A blocked result paired with a complete
  instructions topic, an omitted/substituted action check, or an ordinary
  failed/skipped result → **fail**.
- `.github/AGENTIC.md` (team-discoverability guide) exists. Missing → **warn**
  (regenerate via `/akmaestro-init`).
- `.github/copilot-instructions.md` exists and is short/pointer-only. If it is
  large or duplicates `AGENTS.md` content → **warn** (it should only point to the
  canonical sources).
- `.github/instructions/tests.instructions.md` exists with an `applyTo`
  frontmatter line.
- Read `.agentic/setup/instructions-state.json`; any complex modules still marked
  pending → **warn** with `/setup-instructions module <path>`.

### 3. Tooling

- `.agentic/setup/environment-requirements.json` exists and passes controller
  validation. Missing/invalid requirements -> **fail** because feature work
  cannot establish developer readiness.
- Run controller `readiness-check --no-write` in diagnose mode. Report each
  required local tool/artifact. A missing local requirement is **fail** with its
  recorded structured install/remediation action; do not send the developer through
  `/akmaestro-init`.
- `graphify --version` works; the configured local graph exists under
  `.agentic/local/graphs/<repository-id>/graph.json`. Missing →
  **fail**/**warn** with the install/extract commands from the tooling topic.
- Each sibling repository declared in `AGENTS.md` (Workspace & Dependencies) has
  its own graph under the main repository's `.agentic/local/graphs/` tree and
  exists on disk. Missing → **warn** with the exact configured extraction
  command. Never write generated graphs into a read-only sibling.
- Each LSP listed in `.agentic/setup/tooling-state.json` responds to its version
  command.

### 4. Skills

- `.github/skills/` exists.
- All 19 bundled skills are present: shared helper (`status`), Stage 1/helpers
  (`akmaestro-init`, `setup-instructions`, `setup-tooling`, `setup-skills`, `setup-hooks`,
  `teach`, `doctor`) and Stage 2 (`feature`, `feature-understand`, `feature-frame`,
  `feature-split`, `story-prime`, `story-plan`, `story-implement`,
  `story-review`, `story-learn`, `feature-review`, `feature-retro`). Missing
  bundled skill → **fail**.
- For every `*/SKILL.md`: valid frontmatter — `name` (lowercase letters,
  numbers, hyphens) and a non-empty `description`. Invalid/missing → **fail** for
  that skill. Duplicate `name` across skills → **warn**.

### 5. Hooks

- `.github/hooks/hooks.json` parses (`jq . hooks.json`) and has `version` and a
  `hooks` object with known event names. Parse error → **fail**.
- Report `disableAllHooks` and compare it with hooks evidence. Disabled before
  consent or after a skipped topic is healthy; an enabled/evidence mismatch is
  **fail**.
- Every script referenced by the config exists; `.sh` files are executable.
  Non-executable → **warn** (fixable).
- `.agentic/hooks/restricted-paths.txt`, `dangerous-commands.txt`,
  `editable-paths.txt`, and `lint-commands.json` exist. Missing → **warn**
  (fixable).
- Cross-check the compatibility file `editable-paths.txt` against the Workspace
  & Dependencies section of `AGENTS.md`: a modifiable sibling repository missing
  from the file → **warn** (its edits will be denied); a read-only sibling
  repository listed in the file → **fail** (the boundary is not protecting it).
  Each listed path should exist on disk → **warn** if not.
- `.agentic/audit/` is gitignored. Not ignored → **warn** (fixable).
- **Dry-run the guards with the REAL CLI payload shape.** The GA Copilot CLI
  sends `toolArgs` as a **JSON-encoded string**, not a nested object (verified
  2026-07-06). Dry-run with that shape — an object-form probe passes even when
  the guards are dead (this is exactly how a broken build once looked healthy).
  On Windows/pwsh, pipe the same JSON to `pwsh -File …guard.ps1` instead.
  - restricted-path deny: `printf '%s' '{"toolName":"edit","toolArgs":"{\"path\":\".env\"}"}' | bash .github/hooks/scripts/restricted-path-guard.sh` → expect `deny`.
  - restricted-path allow: same with the inner `"path":"README.md"` → expect `allow`.
  - workspace boundary: inner `"path":"../akm-doctor-probe/x.txt"` (a nonexistent
    sibling) → expect `deny`; if a modifiable sibling repository is declared, a
    path under it → `allow`.
  - dangerous-command deny: `printf '%s' '{"toolName":"powershell","toolArgs":"{\"command\":\"rm -rf /\"}"}' | bash .github/hooks/scripts/dangerous-command-guard.sh` → expect `deny`.
  - dangerous-command allow: same with inner `"command":"ls -la"` → expect `allow`.

  Also test a symlink/junction escape for the restricted guard, a filename with
  spaces and shell metacharacters for structured lint execution, and a unique
  secret in prompt/argument/result/session fields for the audit hook. An escape
  that allows, command substitution that runs, or audit content that retains the
  secret is **fail**.

  Wrong result → **fail**. This validates script *logic* against the real
  payload shape; the definitive live-session wiring is still best confirmed in an
  actual Copilot session (see `copilot-manual-test/`).

### 6. Setup state drift

- `.agentic/bin/akmaestro-state.py`, `.agentic/STATE-PROTOCOL.md`, and all seven
  schemas exist. Missing controller/schema -> **fail** (`akmaestro update`).
- Run `uv run --no-project python .agentic/bin/akmaestro-state.py validate`.
  Every controller error is **fail**; warnings remain **warn**.
- `setup-status` is derived and agrees with the topic evidence on disk. Never
  repair `overall`, `currentStep`, `nextCommand`, or story status fields; v3 does
  not store those duplicates.
- Cross-check files claimed by setup evidence. Mismatch -> **warn**.
- `.agentic/local/` is gitignored. Tracked readiness, active-feature, lock, or
  temporary files -> **fail** because developer state must not be shared.
- No `.agentic/features/index.json` exists. If present -> **warn** as obsolete;
  feature discovery comes from feature directories and selection is local.

## Safe-fix catalog (fix mode only)

May auto-apply, after showing and confirming:

- `chmod +x .github/hooks/scripts/*.sh`;
- recreate missing `.agentic/hooks/*` config-data from kit defaults;
- recreate missing `.agentic/` state directories;
- add `.agentic/local/` and `.agentic/audit/` to `.gitignore` as applicable;
- clear a stale local active-feature pointer or readiness cache, then rerun the
  controller check.

Must NOT auto-do (recommend instead): edit `AGENTS.md`/instruction prose, install
binaries (graphify, LSPs, jq), overwrite an existing user-authored file, or
rewrite a skill/hook the user customized. Never hand-edit or synthesize
controller-owned state to silence a validation failure.

## Report format

```text
doctor — agentic setup health

Environment   ok    bash, jq, git, uv present; graphify 1.x
Instructions  warn  backend/auth module still pending (/setup-instructions module backend/auth)
Tooling       ok    graphify graph present; pyright 1.x
Skills        ok    all 19 bundled skills valid
Hooks         fail  restricted-path-guard allow-path returned deny (logic bug)
State         ok    v3 schemas and transitions valid; local state ignored

Verdict: 1 failure, 1 warning.
Most important next step: fix restricted-path-guard.sh allow path.
```

End with an overall verdict (healthy / warnings / failures) and the single most
important next action. In fix mode, also list what was changed.

## Limitation

As a skill, doctor cannot diagnose a setup where skills fail to load entirely —
if `/doctor` runs at all, skill loading is at least partly working. For a setup
that will not load skills, fall back to inspecting `.github/skills/` and
`hooks.json` by hand.
