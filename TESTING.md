# Testing AKMaestro (v0.2.0)

Help us validate Stage 1 (the one-time setup flow). This is early — the installer
is tested, but the *skills running inside Copilot* are the unproven part, which
is exactly what we need eyes on.

## Prerequisites (once)

Install `uv`:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh   # macOS/Linux
```

(Windows / no `uv`? Use `pipx run --spec git+https://github.com/AbbasKMoussa/akm-murex-starter-kit.git akmaestro init`.)

## 1. Install into a repo

> Use a **scratch repo or a throwaway branch** — the installer writes
> `.github/skills/`, `.github/hooks/`, `.agentic/`, and a placeholder `AGENTS.md`
> (only if absent). It never overwrites existing files, but a branch keeps your
> diff clean.

From the root of that repo:

```bash
uvx --from git+https://github.com/AbbasKMoussa/akm-murex-starter-kit.git akmaestro init
```

Re-run with `--refresh` if you need the latest version:

```bash
uvx --refresh --from git+https://github.com/AbbasKMoussa/akm-murex-starter-kit.git akmaestro init
```

Options: `--no-hooks` to skip hooks, `--path <dir>` to target another directory.

## 2. Run Stage 1 (setup) in Copilot

1. Open Copilot at the repo root in a **fresh VS Code window or a new CLI
   session** — skills and hooks are only discovered in a new session.
2. Run `/init` (or say *"let's run the initialization flow"*) and walk the flow.
3. After setup, run `/doctor` to check the setup is healthy.

## 3. Run Stage 2 (feature flow)

In a fresh session, run `/feature` (or say *"start a feature"* / *"where are
we?"*). Take a small real feature through the phases. Between steps it will tell
you to open a new session and run the next command — that's expected. Try both a
**guided** story and an **autonomous** story.

## 4. What to report back

**Stage 1**
- Does `/init` drive the flow end to end? Does it **chain** to the `/setup-*`
  steps automatically, or do you invoke each (`/setup-instructions`,
  `/setup-tooling`, `/setup-skills`, `/setup-hooks`) yourself?
- Does `/teach` route a new instruction sensibly? Does `/doctor` give a sane report?
- **Hooks:** do they fire? (CLI has hooks GA; VS Code is preview/maybe
  policy-disabled.) Try editing a restricted path (e.g. `.env`) vs a normal file.

**Stage 2**
- Does `/feature` orient you correctly ("where are we?") from a cold session?
- Does the orchestrator **hand off** to the step skills, or do you run each
  `/feature-*` and `/story-*` yourself?
- Does the **gating** feel right, and does **autonomous** mode actually run the
  story loop end-to-end without stopping at each step?
- Are the generated artifacts (`understanding.md`, `feature.md`, stories,
  `review.md`, `retro.md`) useful?

- Anything confusing, broken, or that wrote a file you didn't expect.

## Known gaps (no need to report)

- Hook **PowerShell** variants and the **live Copilot CLI wiring** (real tool
  names / `toolArgs` fields) are not yet verified.
- Stage 2 skills are **unproven in a live session** — orchestrator→step handoff
  and the autonomous internal loop are exactly what we're testing.
