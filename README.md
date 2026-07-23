# AKMaestro

*Conduct your agentic coding.*

A Murex-internal kit that bootstraps an existing repository for agentic coding
with GitHub Copilot (VS Code + CLI), then drives features with a guided,
BMAD-style flow with an orchestrator cueing focused, repo-local skills.

- **Stage 1 — Setup (once per repo):** generate agent instructions, configure
  optional hooks, validate the bootstrapped skills, and verify tooling (LSP +
  Graphifyy). The team lead runs this and commits the result.
- **Stage 2 — Feature flow (per feature):** take a feature from idea to done
  through gated phases. Developers start here; local prerequisites are checked
  and remediated without rerunning setup.

## Prerequisites

- **GitHub Copilot** in VS Code or the Copilot CLI.
- **`uv`** on the team lead and every developer machine (installer + bundled
  workflow state controller):
  ```bash
  curl -LsSf https://astral.sh/uv/install.sh | sh                  # macOS/Linux
  ```
  ```powershell
  powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex" # Windows
  ```
  See the [official uv installation guide](https://docs.astral.sh/uv/getting-started/installation/)
  for package-manager alternatives.

## Install into a repo

> Run from the **Git root of the repository you want to set up** — ideally a scratch
> repo or a throwaway branch the first time. The installer is non-destructive
> (never overwrites existing files), but a branch keeps your diff clean.

Until the kit is on the internal registry, install straight from git:

```bash
uvx --from git+https://github.com/AbbasKMoussa/akm-murex-starter-kit.git akmaestro init
```

You do not need to clone AKMaestro. `uvx` builds and runs it directly from the
Git URL. Use `--dry-run` first to preview every destination without writing.

Use `--refresh` to pick up the latest version, `--no-hooks` to skip hooks,
`--path <dir>` to target another directory. Once published to the registry this
becomes simply `uvx akmaestro init`.

The installer lays down all 19 skills, the optional hook files in a disabled
state, minimal instruction
pointers, schemas, and the repo-local deterministic state controller. Dynamic
detection and configuration happen later inside Copilot.

### Upgrading an already-set-up repo

`init` never overwrites existing files, so re-running it does not pick up new
kit versions. Use `update` instead:

```bash
uvx --refresh --from git+https://github.com/AbbasKMoussa/akm-murex-starter-kit.git akmaestro update
```

`update` refreshes **kit-owned** files only: a file is overwritten only when it
is still byte-identical to what the kit installed (tracked via
`.agentic/setup/kit-manifest.json`). Anything you customized — a tweaked skill,
your `restricted-paths.txt`, your filled-in `AGENTS.md` — is kept and listed, so
nothing you wrote is ever lost. `--force` overrides that for a file you want
reset to the kit version. Untouched retired kit files are removed, customized
retired files are kept, and explicit hook enablement is preserved. Preview with
`akmaestro update --dry-run`; then review the diff, commit, and open a fresh
Copilot session.

## Important: open a fresh Copilot session

Skills and hooks are only discovered in a **new** Copilot session. After
installing (and after any step that adds skills/hooks/tooling), open a fresh
VS Code window or start a new CLI session at the repo root before continuing.

## Stage 1 — team lead initializes the repository

The team lead opens a fresh Copilot session at the repo root:

```text
/akmaestro-init
```

(or say "let's run the initialization flow"; `/status` and
`/akmaestro-init status` both show where you are). `/akmaestro-init` walks four
topics — **instructions, tooling, skills, hooks** —
detecting product, command, and Git facts with provenance, presenting one short
confirmation summary, generating repo-specific files, and verifying finite
commands without a shell. It can span multiple sessions and resumes from where
you left off. On
completion it writes **`.github/AGENTIC.md`**, a committed guide so every teammate
knows what's installed and how to use it. Review and commit the resulting shared
AKMaestro files. `/akmaestro-init` is repository initialization, not a
per-developer step. Hook files remain disabled until the lead reviews their
behavior and explicitly consents during the optional hooks topic.

Everyday helper skills included by the bootstrap (usable any time, not just in a
flow):

- **`/status`** — read-only orientation across initialization and feature work;
  reports the active flow and one exact next action.
- **`/teach`** — "remember that…" / "from now on…": routes a new rule to the right
  instruction file and refines the wording.
- **`/doctor`** — health-check the agentic setup; `--fix` applies safe fixes.

## Stage 2 — build a feature

Once the lead's initialization commit is available, each developer opens a fresh
session and starts directly with:

```text
/feature        # start a feature, resume, or ask "where are we?"
```

Because it's a skill, natural language works too: *"start a feature"*, *"what's
the feature status?"*, *"what should I do next on this feature?"*, *"resume the
feature"*.

Use `/status` for an unqualified "where are we?". It automatically reports
initialization until setup is complete, then local readiness and active feature
progress. It does not change state or install anything.

`/feature` checks the committed initialization and probes the current developer's
`uv`, Graphifyy, selected LSPs, and graph artifacts. When something is missing it
shows the structured remediation action and asks before changing the machine.
Developers do not rerun `/akmaestro-init`.

It runs gated, BMAD-style phases, each a curated specialist:

```
Understand → Frame → Split → per-story loop → Feature review → Retrospective
                              (Prime → Plan → Implement → Review → Learn)
```

How it behaves:

- **Fresh context per step.** Each step finishes by saving state and telling you
  the next command to run **in a new session** — shared continuity lives on disk
  (`.agentic/features/<id>/`), not in chat history. Ask `/feature` "where are we?"
  any time to re-orient. When the current session is still light, a step may
  offer to continue right there instead (never between implement and review —
  review gets fresh eyes).
- **Gated boundaries.** Every phase boundary is a hard stop for your approval.
- **Two modes for the per-story loop only:** *guided* (each of the five steps
  gated, in its own session) or *autonomous* (the five steps run back-to-back in
  one session, stopping only for real blockers). You pick per story.
- **It improves the repo as it goes** — the Learn/Retro steps feed lessons back
  into your instructions via `/teach`.
- **Developer context stays local.** Readiness and the selected feature live in
  gitignored `.agentic/local/`; feature decisions and transitions are committed.

### Multi-repo workspaces

If your app spans repos, declare local sibling-repository checkouts during
`/akmaestro-init`
(they land in `AGENTS.md` → Workspace & Dependencies), each with a role:

- **Modifiable sibling repository** — a repo your team owns (e.g. `../lib-b`):
  functionally part of the application, so stories can change it as part of
  normal work here. Its path is recorded in the compatibility file
  `.agentic/hooks/editable-paths.txt`, and its own build/test commands are honored.
- **Read-only sibling repository** — another team's code (e.g. `../vendor-c`):
  indexed by Graphifyy/LSP so the agent understands it and read when needed, but
  **never edited**. Graphifyy reads it as a source but writes its index only
  under the main repo's gitignored `.agentic/local/graphs/` tree. When hooks are
  enabled, the restricted-path guard denies edits outside the main repo
  unless the target is a declared modifiable sibling repository.

### Optional: pull from Jira / wiki

The Understand phase can read a ticket/page directly if you provide credentials
via environment variables (otherwise it asks you to paste the content):

```bash
export JIRA_TOKEN=…  JIRA_BASE_URL=https://…
export WIKI_TOKEN=…  WIKI_BASE_URL=https://…
```

Tokens are read only from the environment and are **never** written into the repo.

## Testing this kit

See [`TESTING.md`](TESTING.md) for a focused walkthrough and what feedback is most
useful.

## Design docs

- `docs/setup-flow.md` — Stage 1 spec; `docs/init-topics/` — per-topic depth.
- `docs/feature-flow.md` — Stage 2 spec; `docs/feature-phases/` — per-phase depth.
- `docs/setup-flow-decisions.md` — the full decision log (Stage 1 + Stage 2).
