---
name: init
description: >-
  Guided, resumable setup that makes this repository ready for agentic coding.
  Use when the user says "let's run the initialization flow", "/init", "set up
  this repo for agentic coding", "init status", or "init help". Orchestrates the
  four setup topics (instructions, tooling, skills, hooks) by delegating to the
  setup-* skills, persists progress, and writes a team guide on completion.
allowed-tools:
  - shell
---

# init — guided agentic setup (orchestrator)

Run the one-time Stage 1 setup. Mandatory topics: instructions, tooling, skills.
Optional: hooks. The flow is **resumable** and **non-destructive** — never
overwrite existing files without confirmation; create new files freely.

## Sub-commands

- `init status` — print the unified status (below) and stop.
- `init help` — explain the flow and the `/setup-*` commands and stop.
- otherwise — run/continue the guided flow.

## State

Single source of truth: `.agentic/setup/initialization-state.json`:

```json
{
  "version": 1,
  "profile": { "mandatory": ["instructions","tooling","skills"], "optional": ["hooks"] },
  "topics": {
    "instructions": {"status":"pending"}, "tooling": {"status":"pending"},
    "skills": {"status":"pending"}, "hooks": {"status":"pending","optional":true}
  },
  "currentStep": "instructions",
  "overall": "incomplete"
}
```

Topic status is one of `pending | partial | complete | blocked`. `blocked` means
a genuine environment/policy reason (recorded), and does **not** stop overall
completion for the mandatory topics.

## Procedure

1. **Load or create state.** Read `initialization-state.json`; create it with the
   profile above if absent.
2. **Handle sub-commands.** If invoked as `status` or `help`, do that and stop.
3. **Preflight (read-only).** Ensure `.agentic/setup/detected-repo.json` exists
   and is fresh; if not, detect and write: languages/frameworks, package
   managers, build/test/run/verify commands, CI, monorepo shape, candidate
   complex modules, existing customization files (`AGENTS.md`,
   `.github/copilot-instructions.md`, `.github/instructions/`, nested
   `AGENTS.md`, `.github/skills/`, `.github/hooks/`), and git state. These
   pre-fill the interviews so the user mostly confirms.
4. **Run topics in order**, resuming from `currentStep`. For each, run the
   matching skill and then refresh this state from its topic state file:
   - instructions → run `setup-instructions`
   - tooling → run `setup-tooling`
   - skills → run `setup-skills`
   - hooks (optional) → run `setup-hooks` (offer; user may decline)
   Pause for input as needed; the flow may span sessions. After installs that add
   skills/hooks/tools, ask the user to open a **new Copilot session**.
5. **Completion.** When `instructions`, `tooling`, and `skills` are each
   `complete` or `blocked` (with reason), set `overall = "complete"`, then:
   - **Generate/update `.github/AGENTIC.md`** — the committed team guide: list the
     installed skills and how to invoke them (`/teach`, `/doctor`, `/init`, …),
     which hooks are active, where instruction files live, and the run/verify
     commands. Regenerate it on every completed run.
   - Print the handoff.

## Unified status (for `init status`)

Aggregate the topic state files into one report; mark hooks optional; give the
single most important next step. Example:

```text
Setup status (mandatory: instructions, tooling, skills | optional: hooks)
Instruction files: complete
Tooling:           partial  (LSP ok; Graphifyy graph not generated)
Skills:            complete
Hooks:             optional — not installed
Overall: incomplete (tooling pending)
Next: finish Graphifyy in /setup-tooling
```

(`doctor` is the deeper active health check; `init status` reports progress from
state.)

## Handoff (on completion)

```text
Setup complete. Mandatory topics verified; hooks optional/installed.
Team guide written to .github/AGENTIC.md.
Next: start the feature flow with /feature (Stage 2).
```
