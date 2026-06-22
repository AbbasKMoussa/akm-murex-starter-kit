# Testing the Murex Starter Kit (v0.1.0)

Help us validate Stage 1 (the one-time setup flow). This is early — the installer
is tested, but the *skills running inside Copilot* are the unproven part, which
is exactly what we need eyes on.

## Prerequisites (once)

Install `uv`:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh   # macOS/Linux
```

(Windows / no `uv`? Use `pipx run --spec git+https://github.com/AbbasKMoussa/akm-murex-starter-kit.git murex-starter-kit init`.)

## 1. Install into a repo

> Use a **scratch repo or a throwaway branch** — the installer writes
> `.github/skills/`, `.github/hooks/`, `.agentic/`, and a placeholder `AGENTS.md`
> (only if absent). It never overwrites existing files, but a branch keeps your
> diff clean.

From the root of that repo:

```bash
uvx --from git+https://github.com/AbbasKMoussa/akm-murex-starter-kit.git murex-starter-kit init
```

Re-run with `--refresh` if you need the latest version:

```bash
uvx --refresh --from git+https://github.com/AbbasKMoussa/akm-murex-starter-kit.git murex-starter-kit init
```

Options: `--no-hooks` to skip hooks, `--path <dir>` to target another directory.

## 2. Run the flow in Copilot

1. Open Copilot at the repo root in a **fresh VS Code window or a new CLI
   session** — skills and hooks are only discovered in a new session.
2. Run `/init` (or say *"let's run the initialization flow"*) and walk the flow.
3. After setup, run `/doctor` to check the setup is healthy.

## 3. What to report back

- Does `/init` actually drive the flow end to end?
- Do the `/setup-*` steps work — and does `/init` **chain** to them automatically,
  or do you have to invoke each (`/setup-instructions`, `/setup-tooling`,
  `/setup-skills`, `/setup-hooks`) yourself?
- Does `/teach` route a new instruction to a sensible place?
- Does `/doctor` produce a sane health report?
- **Hooks:** do they fire? (Copilot CLI has hooks GA; VS Code is preview and may
  be disabled by org policy.) Try editing a restricted path (e.g. `.env`) and a
  normal file to see the guard allow/deny.
- Anything confusing, broken, or that wrote a file you didn't expect.

## Known gaps (no need to report)

- Hook **PowerShell** variants and the **live Copilot CLI wiring** (real tool
  names / `toolArgs` fields) are not yet verified.
- The feature flow (Stage 2) does not exist yet.
