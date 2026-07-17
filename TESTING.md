# Testing AKMaestro (v0.5.0)

> For a structured, agent-driven live verification session (recommended), see
> [`copilot-manual-test/README.md`](copilot-manual-test/README.md) — it walks
> Copilot itself through the checks and produces a results file to send back.

The installer, v2 state contracts/transitions, readiness gate, and skill assets
have automated coverage. The v0.5 workflow still needs live Copilot CLI and VS
Code validation.

## Prerequisites (once)

Install `uv`:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh   # macOS/Linux
```

`uv` is required on the lead and developer machines because it also runs the
repo-local controller after installation.

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

## 2. Team lead runs Stage 1 in Copilot

1. Open Copilot at the repo root in a **fresh VS Code window or a new CLI
   session** — skills and hooks are only discovered in a new session.
2. Run `/init` (or say *"let's run the initialization flow"*) and walk the flow.
3. After setup, run `/doctor` to check the setup is healthy.
4. Confirm `.agentic/local/` is ignored, review the shared diff, and commit it.

## 3. Run Stage 2 (feature flow)

From a developer checkout of that initialization commit, do **not** run `/init`.
In a fresh session, run `/feature`. Confirm it probes local readiness and offers
each missing structured remediation action for approval. Take a small real
feature through the phases. Between steps it will tell
you to open a new session and run the next command — that's expected. Try both a
**guided** story and an **autonomous** story.

## 4. What to report back

**Stage 1**
- Does `/init` drive the flow end to end? Does it **chain** to the `/setup-*`
  steps automatically, or do you invoke each (`/setup-instructions`,
  `/setup-tooling`, `/setup-skills`, `/setup-hooks`) yourself?
- Does `/teach` route a new instruction sensibly? Does `/doctor` give a sane report?
- Is repository completion committed while readiness and active feature remain
  under ignored `.agentic/local/`?
- **Hooks:** do they fire? (CLI has hooks GA; VS Code is preview/maybe
  policy-disabled.) Try editing a restricted path (e.g. `.env`) vs a normal file.

**Stage 2**
- Does a developer start directly with `/feature`, receive confirmed local-tool
  remediation, and remain blocked if mandatory readiness is declined?
- Does `/feature` orient you correctly ("where are we?") from a cold session?
- Does the orchestrator **hand off** to the step skills, or do you run each
  `/feature-*` and `/story-*` yourself?
- Does the **gating** feel right, and does **autonomous** mode actually run the
  story loop end-to-end without stopping at each step?
- Are the generated artifacts (`understanding.md`, `feature.md`, stories,
  `review.md`, `retro.md`) useful?

- Anything confusing, broken, or that wrote a file you didn't expect.

## Status

- **Previously verified on v0.4.1:** skill discovery, `/doctor`, `/init`,
  `/teach`, and the previous Stage 2 flow on Copilot CLI 1.0.68/Windows. That run
  does not validate the new v0.5 controller or lead/developer readiness split.
- **Fixed after the run (v0.4.1):** the guard hooks were failing *open* — the GA
  CLI sends `toolArgs` as a JSON-encoded string, not an object, so the guards read
  a null path/command and allowed everything. All guards now decode it; the
  PowerShell and Bash variants pass regression tests against the captured shape.
  A live **re-confirmation** that the guards now deny (`copilot-manual-test/`
  Phase 3) is still open.
- Still unverified for v0.5: state-last handoffs, interruption recovery, local
  readiness/remediation, autonomous controller transitions, live Bash guards,
  and the VS Code surface.
- The cross-repo walkthrough in `copilot-manual-test/MULTI-REPO-WALKTHROUGH.md`
  is the source of truth for validating modifiable vs. read-only sibling repos.
