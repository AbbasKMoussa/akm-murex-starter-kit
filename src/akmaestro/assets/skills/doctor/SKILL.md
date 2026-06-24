---
name: doctor
description: >-
  Diagnose the health of this repository's agentic setup — instruction files,
  tooling, skills, hooks, and setup state — and report each check as ok / warn /
  fail with a concrete fix. Use when the user wants to check, verify, or
  troubleshoot the agentic setup: "is setup healthy?", "run doctor", "diagnose",
  "why isn't X working", or right after install. Read-only by default; applies
  safe fixes only when the user explicitly asks (e.g. "doctor fix" / "--fix").
allowed-tools:
  - shell
---

# doctor — diagnose the agentic setup

Run a health check across the whole agentic setup and produce an actionable
report. This is distinct from `init status` (which reports setup *progress*):
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

- `bash`, `jq`, `git` on PATH; `pwsh` if Windows/PowerShell is in play; `python`
  + `uv`; `graphify`. Report versions.
- `jq` missing → **warn**: the bash hook guards fall through to allow without it.
- Note the detected surface (Copilot CLI vs VS Code) if determinable; otherwise
  say it is unknown.

### 2. Instruction files

- `AGENTS.md` exists and contains the core sections (Product, Build, Tests, Run,
  Verify a Change, CI, Git Workflow, Agent Rules). Missing file → **fail**;
  missing sections → **warn**.
- Smoke-verify result is recorded in `instructions-state.json` as passed or
  `blocked` (not skipped). Missing/skipped → **warn**.
- `.github/AGENTIC.md` (team-discoverability guide) exists. Missing → **warn**
  (regenerate via `/init`).
- `.github/copilot-instructions.md` exists and is short/pointer-only. If it is
  large or duplicates `AGENTS.md` content → **warn** (it should only point to the
  canonical sources).
- `.github/instructions/tests.instructions.md` exists with an `applyTo`
  frontmatter line.
- Read `.agentic/setup/instructions-state.json`; any complex modules still marked
  pending → **warn** with `init module <path>`.

### 3. Tooling

- `graphify --version` works; `graphify-out/graph.json` exists. Missing →
  **fail**/**warn** with the install/extract commands from the tooling topic.
- Each LSP listed in `.agentic/setup/tooling-state.json` responds to its version
  command.

### 4. Skills

- `.github/skills/` exists.
- Kit flow-skills present (`init`, `setup-instructions`, `setup-tooling`,
  `setup-skills`, `setup-hooks`, `doctor`) and the `teach` catalog skill. Missing
  → **fail**.
- For every `*/SKILL.md`: valid frontmatter — `name` (lowercase letters,
  numbers, hyphens) and a non-empty `description`. Invalid/missing → **fail** for
  that skill. Duplicate `name` across skills → **warn**.

### 5. Hooks

- `.github/hooks/hooks.json` parses (`jq . hooks.json`) and has `version` and a
  `hooks` object with known event names. Parse error → **fail**.
- Every script referenced by the config exists; `.sh` files are executable.
  Non-executable → **warn** (fixable).
- `.agentic/hooks/restricted-paths.txt`, `dangerous-commands.txt`, and
  `lint-commands.json` exist. Missing → **warn** (fixable).
- `.agentic/audit/` is gitignored. Not ignored → **warn** (fixable).
- **Dry-run the bash guards (logic check):**
  - restricted-path deny: `printf '{"toolName":"edit","toolArgs":{"path":".env"}}' | bash .github/hooks/scripts/restricted-path-guard.sh` → expect `deny`.
  - restricted-path allow: same with `"path":"README.md"` → expect `allow`.
  - dangerous-command deny: `printf '{"toolName":"bash","toolArgs":{"command":"rm -rf /"}}' | bash .github/hooks/scripts/dangerous-command-guard.sh` → expect `deny`.
  - dangerous-command allow: same with `"command":"ls -la"` → expect `allow`.

  Wrong result → **fail**. State clearly that this validates script *logic* only;
  the live Copilot CLI wiring (real tool names / `toolArgs` fields, PowerShell
  variants) must still be verified in an actual session.

### 6. Setup state drift

- For each `.agentic/setup/*.json`, cross-check that files it claims to have
  generated actually exist on disk. Mismatch → **warn** (stale state).

## Safe-fix catalog (fix mode only)

May auto-apply, after showing and confirming:

- `chmod +x .github/hooks/scripts/*.sh`;
- recreate missing `.agentic/hooks/*` config-data from kit defaults;
- recreate missing `.agentic/` state directories;
- add `.agentic/audit/` to `.gitignore`;
- regenerate a drifted `.agentic/setup/*.json` from what is actually on disk.

Must NOT auto-do (recommend instead): edit `AGENTS.md`/instruction prose, install
binaries (graphify, LSPs, jq), overwrite an existing user-authored file, or
rewrite a skill/hook the user customized.

## Report format

```text
doctor — agentic setup health

Environment   ok    bash, jq, git, uv present; graphify 1.x
Instructions  warn  backend/auth module still pending (init module backend/auth)
Tooling       ok    graphify graph present; pyright 1.x
Skills        ok    init, doctor, teach valid
Hooks         fail  restricted-path-guard allow-path returned deny (logic bug)
State         ok    no drift

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
