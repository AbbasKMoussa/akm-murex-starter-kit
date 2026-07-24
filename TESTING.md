# Testing AKMaestro (v0.6.0)

> For a structured, agent-driven live verification session (recommended), see
> [`copilot-manual-test/README.md`](copilot-manual-test/README.md) — it walks
> Copilot itself through the checks and produces a results file to send back.

The installer, v3 state contracts/transitions, readiness gate, hook scripts, and
skill assets have automated coverage. The v0.6 workflow still needs live Copilot CLI and VS
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

Options: `--dry-run` to preview, `--no-hooks` to skip hook assets, and
`--path <dir>` to target another Git root. Installed hook assets start disabled.

### Subproject exception

To exercise an independent product below a shared Git root:

```bash
mkdir -p products/pricing
cd products/pricing
uvx --refresh --from git+https://github.com/AbbasKMoussa/akm-murex-starter-kit.git \
  akmaestro init --subproject
```

Confirm `.github/`, `.agentic/`, `.gitignore`, and `AGENTS.md` exist under
`products/pricing`, none were created at the enclosing Git root, and the
manifest contains `installation_mode: "subproject"`, `project_root: "."`, and
the correct relative `git_root`. Confirm both commands reject the nested target
without `--subproject`, then run:

```bash
akmaestro update --subproject
```

Open `products/pricing` itself in a fresh VS Code window or start Copilot CLI
there. Run `/status`, `/akmaestro-init`, and a small `/feature`; verify discovery
and that no inspection, state, or edits leak into sibling products.

## 2. Team lead runs Stage 1 in Copilot

1. Open Copilot at the repo root in a **fresh VS Code window or a new CLI
   session** — skills and hooks are only discovered in a new session.
2. Run `/akmaestro-init` (or say *"let's run the initialization flow"*) and walk the flow.
   Before starting, run `/status` and confirm it reports setup as not started
   without creating state. Run it again mid-flow and confirm the next setup
   command remains `/akmaestro-init` while the controller reports the internal
   next topic separately.
3. Confirm instructions setup proposes one sourced product/command/Git summary,
   including complex-module candidates with provenance. Confirm the lead can
   correct the module list, finite commands run through `action-check`, and
   strict evidence has `moduleKnowledge` with no placeholders.
4. After setup, run `/doctor` to check the setup is healthy.
5. Confirm `.agentic/local/` is ignored, review the shared diff, and commit it.

### Module-knowledge decision paths

Use isolated scratch repositories or fresh disposable branches so each path
starts before instructions evidence is committed:

1. Confirm two modules, accept generation, and verify both controller-derived
   files under `.github/instructions/` have exact product-relative `applyTo`
   scopes and all seven required sections. Instructions must remain
   `in_progress`, and setup must not finalize, until both artifacts validate.
2. Confirm at least one module, decline generation, and verify initialization
   finalizes with `moduleKnowledge.decision: "defer"` plus the exact
   `/setup-instructions module <path>` follow-up for every pending module.
3. Confirm two modules and accept generation, then interrupt after the first
   artifact and evidence revision. In a fresh session run `/akmaestro-init`;
   verify the first module stays complete and generation resumes at the second.
4. Remove or correct a false-positive candidate before accepting the summary.
   Verify it is absent from committed `repositoryContext.complexModules`,
   `pendingModules`, generated targets, and status output.

For an explicit subproject installation, repeat a two-module path and confirm
every detected candidate is below the selected product root. All
`module-targets` results, scoped instruction files, evidence, and setup state
must remain below that root; the enclosing Git root and sibling products must
receive none of them.

## 3. Run Stage 2 (feature flow)

From a developer checkout of that initialization commit, do **not** run
`/akmaestro-init`.
In a fresh session, run `/feature`. Confirm it probes local readiness and offers
each missing structured remediation action for approval, and rejects any action
that differs from committed requirements. Take a small real
feature through the phases. Between steps it will tell
you to open a new session and run the next command — that's expected. Try both a
**guided** story and an **autonomous** story.

## 4. What to report back

**Stage 1**
- Does instructions setup detect and confirm product purpose, all canonical
  commands, verification, and explicit Git policies without inventing values?
- Does invalid/unsafe instructions evidence fail before the topic transition?
- Does accepted module generation remain mandatory-to-finish, while deferred
  modules finalize with exact follow-up commands?
- Does interrupted module generation resume through `/akmaestro-init` without
  repeating a validated module?
- Does `/akmaestro-init` drive the flow end to end? Does it follow the installed `/setup-*`
  steps automatically, or do you invoke each (`/setup-instructions`,
  `/setup-tooling`, `/setup-skills`, `/setup-hooks`) yourself?
- Does `/teach` route a new instruction sensibly? Does `/doctor` give a sane report?
- Is repository completion committed while readiness and active feature remain
  under ignored `.agentic/local/`?
- **Hooks:** do they remain disabled before consent, preserve consent across
  `akmaestro update`, and fire after explicit enablement? (CLI has hooks GA; VS
  Code may be preview or policy-disabled.) Try a restricted path, normal file,
  and symlink/junction escape.

**Stage 2**
- Does a developer start directly with `/feature`, receive confirmed local-tool
  remediation, and remain blocked if mandatory readiness is declined?
- Does `/feature` orient you correctly ("where are we?") from a cold session?
- Does `/status` distinguish incomplete setup from feature work, report local
  readiness, and leave setup, readiness, selection, and feature state unchanged?
- Does the orchestrator **hand off** to the step skills, or do you run each
  `/feature-*` and `/story-*` yourself?
- Does the **gating** feel right, and does **autonomous** mode actually run the
  story loop end-to-end without stopping at each step?
- Are the generated artifacts (`understanding.md`, `feature.md`, stories,
  `review.md`, `retro.md`) useful?

- Anything confusing, broken, or that wrote a file you didn't expect.

## Status

- **Previously verified on v0.4.1:** skill discovery, `/doctor`, the legacy
  `/init` skill, `/teach`, and the previous Stage 2 flow on Copilot CLI
  1.0.68/Windows. That run does not validate the v0.6 controller or
  lead/developer readiness split.
- **Fixed after the run (v0.4.1):** the guard hooks were failing *open* — the GA
  CLI sends `toolArgs` as a JSON-encoded string, not an object, so the guards read
  a null path/command and allowed everything. All guards now decode it; the
  PowerShell and Bash variants pass regression tests against the captured shape.
  A live **re-confirmation** that the guards now deny (`copilot-manual-test/`
  Phase 3) is still open.
- Still unverified for v0.6: state-last handoffs, interruption recovery, local
  readiness/remediation, autonomous controller transitions, live Bash guards,
  and the VS Code surface.
- The cross-repo walkthrough in `copilot-manual-test/MULTI-REPO-WALKTHROUGH.md`
  is the source of truth for validating modifiable vs. read-only sibling repos.
