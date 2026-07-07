# AKMaestro — Live Copilot Verification Prompt

> **For the agent:** You are verifying **AKMaestro** in a live GitHub Copilot
> session — the one environment its automated tests cannot reach. Work through
> the phases in order with the human. For each numbered check, compare against
> the **Expected** result and record PASS / FAIL / SKIPPED. At the end, write
> `copilot-test-results.md` at the repo root with the results table, the
> captured audit-payload samples, and a summary. **Observe and report — do not
> fix failures**, and stay inside this scratch repository at all times.

AKMaestro sets a repo up for agentic coding (Stage 1: `/init`) and drives
features through gated phases (Stage 2: `/feature`). It was installed into this
scratch repo with `akmaestro init`. Its guard hooks read a JSON event on stdin
and print a decision on stdout — but the tool names and payload field names they
match on (`toolName`/`tool_name`, `toolArgs.path`, …) are **defensive guesses
that have never been checked against a real Copilot session**. Capturing the
real values is the single most valuable output of this run.

Record up front: OS, Copilot surface (VS Code or CLI) and its version, and
whether `jq` is on PATH (`jq --version`).

---

## Phase 0 — Installed layout (shell checks)

1. `.github/skills/` contains **18** skill folders, each with a `SKILL.md`.
2. `.github/hooks/hooks.json` exists; `.github/hooks/scripts/` has 4 `.sh` + 4
   `.ps1` files; on macOS/Linux the `.sh` files are executable.
3. `.agentic/hooks/` has `restricted-paths.txt`, `dangerous-commands.txt`,
   `editable-paths.txt`, `lint-commands.json`; `.agentic/setup/kit-manifest.json`
   exists.
4. `AGENTS.md` exists (placeholder) and `.gitignore` contains `.agentic/audit/`.

**Expected:** all present. Record the actual skill count.

## Phase 1 — Skill discovery

In *this* session, check which kit skills are discoverable/invocable: `init`,
`setup-instructions`, `setup-tooling`, `setup-skills`, `setup-hooks`, `teach`,
`doctor`, `feature`, `feature-understand`, `feature-frame`, `feature-split`,
`story-prime`, `story-plan`, `story-implement`, `story-review`, `story-learn`,
`feature-review`, `feature-retro`.

5. Are they visible as slash commands (or listed as available skills)?
6. Does plain natural language route correctly — say nothing but
   *"is the agentic setup healthy?"* and see whether the **doctor** skill is
   picked up.

**Expected:** all 18 discoverable; natural language triggers doctor. Record any
missing names and how discovery presents them on this surface.

## Phase 2 — /doctor

7. Run `/doctor` and capture its report verbatim.

**Expected:** a grouped ok/warn/fail report that reaches a verdict without
crashing. Warns are fine (e.g. Graphifyy not installed); note anything that
looks wrong, especially in the Hooks section.

## Phase 3 — Live hooks (the main event)

> Re-verification note: a prior live run found the guards fail-open because the
> GA CLI sends `toolArgs` as a JSON-encoded string (not an object); the guards
> were fixed to decode it. This phase confirms the fix fires live. If a probe is
> NOT blocked, capture the exact audit payload for that call — the shape may have
> shifted again.

First ask the human whether hooks are enabled on this surface (VS Code agent
hooks are preview and may be disabled by org policy; the CLI has them GA). If
they cannot be enabled, mark 8–13 SKIPPED with the reason and go to Phase 4.

> Safety by design: every probe below is harmless even if **no** hook fires.
> Do not use real destructive commands to test the guard.

8. **Restricted path — deny.** Try to create/edit `.env` in this scratch repo
   (any content). **Expected:** the edit is blocked and the deny reason mentions
   the restricted-path guard. (If no hook fires, a `.env` appears in a scratch
   repo — harmless; record FAIL.)
9. **Restricted path — allow.** Create `notes.md` with one line.
   **Expected:** succeeds, no interference.
10. **Dangerous command — deny, via a benign sentinel.** Append this line to
    `.agentic/hooks/dangerous-commands.txt`:
    ```
    ^echo AKM_GUARD_TEST$
    ```
    Then run the shell command `echo AKM_GUARD_TEST`. **Expected:** blocked by
    the dangerous-command guard. (If no hook fires it just echoes — harmless;
    record FAIL.) Remove the sentinel line afterwards.
11. **Workspace boundary — deny.** Try to create `../akm-boundary-probe/x.txt`
    (a sibling of this repo). **Expected:** blocked — the path resolves outside
    the repository and no editable dependency is declared. (If no hook fires, a
    stray sibling folder appears — delete it and record FAIL.)
12. **Workspace boundary — editable satellite allow.** Create a sibling repo
    `../akm-lib-b/` (plain `mkdir`), append the line `../akm-lib-b` to
    `.agentic/hooks/editable-paths.txt`, then try to create
    `../akm-lib-b/mod.py`. **Expected:** allowed. Also try
    `../akm-lib-b/.env` — **Expected:** denied (restricted globs apply inside
    satellites). Clean up `../akm-lib-b/` and the added line afterwards.
13. **Lint hook silence.** After the `notes.md` edit, confirm nothing lint-ish
    was injected (no lint command is configured for `.md`). **Expected:** no-op.

## Phase 4 — Audit trail: capture the real payloads

14. Check `.agentic/audit/` for a `<date>.jsonl` file. **Expected:** if hooks
    are enabled, it exists and grew during Phase 3.
15. From the `.jsonl` lines, extract and report the **real payload shape** —
    this is the data we need to validate the guards' field guesses:
    - the event names seen (`hook_event_name` / `hookEventName` values);
    - the tool names Copilot uses for file edits and shell commands;
    - whether arguments arrive as `toolArgs` or `tool_input`;
    - the exact field name that carries the file path, and the one that
      carries the shell command.

    Paste 2–3 representative raw lines into the results file, **redacting**
    any file contents, prompts, or anything internal — keep only structure and
    field names.

## Phase 5 — /init end-to-end (interactive; the human answers)

16. Run `/init` and walk the flow with the human. Record:
    - does it **chain** to `setup-instructions` → `setup-tooling` →
      `setup-skills` → `setup-hooks` by itself, or must each be invoked by hand?
    - does it write `.agentic/setup/initialization-state.json` and resume
      correctly if you stop and run `/init` again in a **new** session?
    - does `init status` report sensibly mid-flow?
    - on completion: is `AGENTS.md` filled in with real repo facts, and is
      `.github/AGENTIC.md` written?

**Expected:** the flow drives itself, persists state, resumes, and completes
with both files written. Time-box it; if a topic drags (e.g. Graphifyy install),
let it be marked `blocked` and continue — that path is part of the design.

## Phase 6 — /teach

17. Say: *"remember that in this repo, test files always end in `_spec`"*.
    **Expected:** the teach skill gates/refines it, proposes root `AGENTS.md`
    (or a scoped instructions file), shows the exact text and placement, and
    asks before writing. Record where it landed.

## Phase 7 — Stage 2 mini-feature (optional, ~30+ min)

18. In a fresh session run `/feature`, start a tiny toy feature (e.g. "add a
    `hello` script with a test"). Record: does `/feature` create the state and
    hand off to `/feature-understand`?
19. Walk Understand → Frame → Split with the human. At each gate, record whether
    it offers to **continue in the same session while context is light** (it
    should) and whether artifacts (`understanding.md`, `feature.md`, story
    files) are written under `.agentic/features/<id>/`.
20. Run one story in **guided** mode and, if a second story exists, one in
    **autonomous** mode. Record: does autonomous run Prime→…→Learn in one
    session without stopping? Does implement → review insist on a fresh session
    in guided mode (it must — no same-session offer there)?
21. From a cold session, ask `/feature` *"where are we?"*. **Expected:** correct
    phase/story/next command from disk state alone.

---

## Report

Write `copilot-test-results.md`:

| # | Check | Expected | Actual | Result |
|---|-------|----------|--------|--------|
| 0.1 | 18 skills installed | 18 | … | |
| … | | | | |

Then: the redacted audit payload samples (Phase 4), the `/doctor` report, and a
short summary — what worked, what broke (verbatim errors), and anything
surprising a teammate should know before rolling this out.
