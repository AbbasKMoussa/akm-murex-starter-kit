# AKMaestro — Live Copilot Verification Prompt

> **For the agent:** You are verifying **AKMaestro** in a live GitHub Copilot
> session — the one environment its automated tests cannot reach. Work through
> the phases in order with the human. For each numbered check, compare against
> the **Expected** result and record PASS / FAIL / SKIPPED. At the end, write
> `copilot-test-results.md` at the repo root with the results table, the
> captured audit-payload samples, and a summary. **Observe and report — do not
> fix failures**, and stay inside this scratch repository at all times.

AKMaestro lets a team lead initialize a repo once (`/init`), then lets every
developer start directly with `/feature`. `/feature` checks developer-local
readiness and offers confirmed remediation. The kit was installed into this
scratch repo with `akmaestro init`. Its guard hooks read a JSON event on stdin
and print a decision on stdout. Copilot CLI 1.0.68 on Windows sent `toolArgs` as
a JSON-encoded string; the scripts now decode that shape and retain defensive
fallbacks. This run must confirm the fixed deny paths fire live and capture the
payload again in case the surface contract moved.

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
4. `.agentic/bin/akmaestro-state.py`, `.agentic/STATE-PROTOCOL.md`, and six
   schemas exist.
5. `AGENTS.md` exists (placeholder) and `.gitignore` contains both
   `.agentic/local/` and `.agentic/audit/`.

**Expected:** all present. Record the actual skill count.

## Phase 1 — Skill discovery

In *this* session, check which kit skills are discoverable/invocable: `init`,
`setup-instructions`, `setup-tooling`, `setup-skills`, `setup-hooks`, `teach`,
`doctor`, `feature`, `feature-understand`, `feature-frame`, `feature-split`,
`story-prime`, `story-plan`, `story-implement`, `story-review`, `story-learn`,
`feature-review`, `feature-retro`.

6. Are they visible as slash commands (or listed as available skills)?
7. Does plain natural language route correctly — say nothing but
   *"is the agentic setup healthy?"* and see whether the **doctor** skill is
   picked up.

**Expected:** all 18 discoverable; natural language triggers doctor. Record any
missing names and how discovery presents them on this surface.

## Phase 2 — /doctor

8. Run `/doctor` and capture its report verbatim.

**Expected:** a grouped ok/warn/fail report that reaches a verdict without
crashing. Before `/init`, missing initialization/environment requirements are
expected failures; note anything else that looks wrong.

## Phase 3 — Live hooks (the main event)

> Re-verification note: a prior live run found the guards fail-open because the
> GA CLI sends `toolArgs` as a JSON-encoded string (not an object); the guards
> were fixed to decode it. This phase confirms the fix fires live. If a probe is
> NOT blocked, capture the exact audit payload for that call — the shape may have
> shifted again.

First ask the human whether hooks are enabled on this surface (VS Code agent
hooks are preview and may be disabled by org policy; the CLI has them GA). If
they cannot be enabled, mark the hook checks SKIPPED with the reason and continue.

> Safety by design: every probe below is harmless even if **no** hook fires.
> Do not use real destructive commands to test the guard.

9. **Restricted path — deny.** Try to create/edit `.env` in this scratch repo
   (any content). **Expected:** the edit is blocked and the deny reason mentions
   the restricted-path guard. (If no hook fires, a `.env` appears in a scratch
   repo — harmless; record FAIL.)
10. **Restricted path — allow.** Create `notes.md` with one line.
   **Expected:** succeeds, no interference.
11. **Dangerous command — deny, via a benign sentinel.** Append this line to
    `.agentic/hooks/dangerous-commands.txt`:
    ```
    ^echo AKM_GUARD_TEST$
    ```
    Then run the shell command `echo AKM_GUARD_TEST`. **Expected:** blocked by
    the dangerous-command guard. (If no hook fires it just echoes — harmless;
    record FAIL.) Remove the sentinel line afterwards.
12. **Workspace boundary — deny.** Try to create `../akm-boundary-probe/x.txt`
    (a sibling of this repo). **Expected:** blocked — the path resolves outside
    the repository and no modifiable sibling repository is declared. (If no hook
    fires, a stray sibling folder appears — delete it and record FAIL.)
13. **Workspace boundary — modifiable sibling allow.** Create a sibling repo
    `../akm-lib-b/` (plain `mkdir`), append the line `../akm-lib-b` to
    `.agentic/hooks/editable-paths.txt`, then try to create
    `../akm-lib-b/mod.py`. **Expected:** allowed. Also try
    `../akm-lib-b/.env` — **Expected:** denied (restricted globs apply inside
    sibling repositories). Clean up `../akm-lib-b/` and the added line afterwards.
14. **Lint hook silence.** After the `notes.md` edit, confirm nothing lint-ish
    was injected (no lint command is configured for `.md`). **Expected:** no-op.

## Phase 4 — Audit trail: capture the real payloads

15. Check `.agentic/audit/` for a `<date>.jsonl` file. **Expected:** if hooks
    are enabled, it exists and grew during Phase 3.
16. From the `.jsonl` lines, extract and report the **real payload shape** —
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

17. Run `/init` **as the team lead** and walk the flow with the human. Record:
    - does it **chain** to `setup-instructions` → `setup-tooling` →
      `setup-skills` → `setup-hooks` by itself, or must each be invoked by hand?
    - does it write `.agentic/setup/initialization-state.json` and resume
      correctly if you stop and run `/init` again in a **new** session?
    - is state version 2, with a revision, no persisted `overall`/`currentStep`,
      and controller-derived status?
    - does tooling write `.agentic/setup/environment-requirements.json` with
      required `uv`, Graphifyy, selected `lsp-*`, and graph entries?
    - does `init status` report sensibly mid-flow?
    - on completion: is `AGENTS.md` filled in with real repo facts, and is
      `.github/AGENTIC.md` written?

**Expected:** the flow drives itself, persists state, resumes, and completes
with both files written. `.agentic/local/` remains ignored. Time-box it; a
genuine setup blocker may be documented, but `/feature` will still require local
readiness before mutation.

## Phase 6 — /teach

18. Say: *"remember that in this repo, test files always end in `_spec`"*.
    **Expected:** the teach skill gates/refines it, proposes root `AGENTS.md`
    (or a scoped instructions file), shows the exact text and placement, and
    asks before writing. Record where it landed.

## Phase 7 — Stage 2 mini-feature (optional, ~30+ min)

19. In a fresh **developer** session, skip `/init` and run `/feature`. Record:
    does it verify the shared initialization, probe local readiness, and offer
    missing remediation actions for confirmation? Decline one once and confirm
    feature mutation remains blocked; then approve/remediate and rerun.
20. Start a tiny toy feature. Confirm state is created without a shared
    `index.json`, the selection is in `.agentic/local/active-feature.json`, and
    the derived handoff is `/feature-understand`.
21. Walk Understand → Frame → Split with the human. At each gate, record whether
    it offers to **continue in the same session while context is light** (it
    should) and whether artifacts (`understanding.md`, `feature.md`, story
    files) are written under `.agentic/features/<id>/`.
22. Run one story in **guided** mode and, if a second story exists, one in
    **autonomous** mode. Record: does autonomous run Prime→…→Learn in one
    session without stopping? Does implement → review insist on a fresh session
    in guided mode (it must — no same-session offer there)?
23. From a cold session, ask `/feature` *"where are we?"*. **Expected:** correct
    phase/story/next command derived from disk state. Interrupt once after an
    artifact write and before transition; rerun and confirm the old state resumes
    without corruption or duplicate advancement.

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
