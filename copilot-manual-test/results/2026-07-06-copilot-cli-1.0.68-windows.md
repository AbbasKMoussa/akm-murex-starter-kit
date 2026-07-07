# AKMaestro — Live Copilot Verification Results

**Date:** 2026-07-06
**OS:** Windows_NT (Windows, PowerShell 7.6.0 / `pwsh`)
**Copilot surface:** GitHub Copilot CLI, version **1.0.68**
**`jq` on PATH:** No (not installed; `bash` also not on PATH — PowerShell hook
variants used throughout, which is the expected path on a native Windows box)
**Other tool versions seen:** git 2.54.0, python 3.12.5, uv 0.11.13, uvx 0.11.13

**Method note:** the verifying session's own working directory was the scratch
repo (`D:\Projects\akm-live-test`), so its own tool calls fired the installed
hooks (visible in the audit log). Several phases were additionally cross-checked
by spawning nested `copilot -p ... --allow-all-tools` sessions rooted in the same
repo, to simulate a fully independent live session. Both sources agree.

---

## Results

| # | Check | Expected | Actual | Result |
|---|-------|----------|--------|--------|
| 0.1 | 18 skill folders w/ SKILL.md | 18 | 18 present, each with `SKILL.md` | PASS |
| 0.2 | hooks.json + 4 .sh + 4 .ps1 scripts | present | `hooks.json` present; `scripts/` has exactly 4 `.sh` + 4 `.ps1` (audit-log, dangerous-command-guard, lint-on-edit, restricted-path-guard) | PASS |
| 0.3 | `.agentic/hooks/*` + kit-manifest.json | present | `restricted-paths.txt`, `dangerous-commands.txt`, `lint-commands.json`, `.agentic/setup/kit-manifest.json` all present | PASS |
| 0.4 | AGENTS.md placeholder + `.gitignore` has `.agentic/audit/` | present | Both present at install time | PASS |
| 1.5 | All 18 skills visible/invocable | all 18 | `copilot skill list` shows all 18 kit "Project skills" plus personal/builtin skills, correct descriptions | PASS |
| 1.6 | NL "is the agentic setup healthy?" routes to doctor | routes to doctor | Routed correctly both times it was tried (nested session and later a fresh one) | PASS |
| 2.7 | `/doctor` reaches a verdict, no crash | grouped ok/warn/fail | Ran 3 times across the session (see verbatim reports below); always reached a clean verdict, never crashed | PASS |
| 3.8 | Restricted path deny — create `.env` | blocked | **NOT blocked** — `.env` was created with content `FOO=bar` with no denial | **FAIL** |
| 3.9 | Restricted path allow — `notes.md` | succeeds | Succeeded, no interference (expected either way, given #8) | PASS |
| 3.10 | Dangerous command deny via sentinel `^echo AKM_GUARD_TEST$` | blocked | **NOT blocked** — command echoed normally | **FAIL** |
| 3.11 | Lint hook silence on `.md` edit | no-op | No lint content injected (no `.md` entry in `lint-commands.json`) | PASS |
| 4.12 | `.agentic/audit/<date>.jsonl` exists, grows | exists & grows | `2026-07-06.jsonl` exists, grew to 279 lines across the session | PASS |
| 4.13 | Extract real payload shape | field names identified | See "Real payload shape" section below — **critical mismatch found** | DONE (see below) |
| 5.14 | `/init` chains all 4 topics, persists/resumes state, `init status` sensible, writes both files | full flow | Chained instructions→tooling→skills→hooks automatically; wrote `initialization-state.json`; `init status` in a fresh nested session reported correctly; `AGENTS.md` filled with real facts; `.github/AGENTIC.md` written | PASS |
| 6.15 | `/teach` gates, refines, shows placement, writes | gated + written | Routed to root `AGENTS.md` → Tests section; refined wording to the `_spec` convention; wrote it | PASS (see caveat) |
| 7.16 | `/feature` creates state, hands to understand | handoff | Created `hello-script` feature, `.agentic/features/hello-script/state.json` + `index.json`, `nextCommand: /feature-understand` | PASS |
| 7.17 | Understand→Frame→Split: same-session offer + artifacts | offered + written | Each gate offered "continue here since light"; `understanding.md`, `feature.md`, `stories/01-*.md`, `stories/02-*.md` all written under `.agentic/features/hello-script/` | PASS |
| 7.18 | Guided story + autonomous story; review always fresh session in guided | as designed | Story 01 run guided (5 gated steps); story 02 run autonomous (Prime→Plan→Implement→Review→Learn back-to-back, still hard-stopped at story-close/Learn gate, matching spec). Guided mode's `/story-implement` skill text explicitly states review always needs a new session (no light-context exception) — confirmed via skill instructions; actual execution used the same continuous session as a pragmatic stand-in (see retro.md) | PASS (caveat noted) |
| 7.19 | Cold session `/feature "where are we?"` | correct state from disk | Nested cold session correctly reported phase `reviewed`, both stories done, next command `/feature-retro`, purely from disk state | PASS |

**Skill count:** 18/18.

---

## `/doctor` reports (verbatim)

### Run 1 — before `/init` (natural-language trigger, "is the agentic setup healthy?")

```
Environment   warn  git 2.54.0, pwsh 7.6.0, python 3.12.5, uv 0.11.13, graphify installed — ok
                    bash NOT FOUND, jq NOT FOUND (fine here since Windows/pwsh hook variants are used instead)

Instructions  fail  AGENTS.md is still the raw /init placeholder (no Product/Build/Tests/Run content);
                    missing CI & Git Workflow sections entirely
              warn  .agentic/setup/instructions-state.json missing (smoke-verify never recorded)
              warn  .github/AGENTIC.md (team guide) missing
              warn  .github/instructions/tests.instructions.md missing
              ok    .github/copilot-instructions.md is a short pointer file, as intended

Tooling       fail  graphify installed but no graphify-out/graph.json — code graph never built
              warn  .agentic/setup/tooling-state.json missing — no LSP setup recorded

Skills        ok    all 18 skills present incl. required kit set (init, setup-instructions,
                    setup-tooling, setup-skills, setup-hooks, doctor, teach) — valid frontmatter

Hooks         ok    hooks.json parses, all 4 events wired, all .sh/.ps1 scripts present
              ok    restricted-paths.txt / dangerous-commands.txt / lint-commands.json present
              ok    .agentic/audit/ is gitignored
              ok    dry-ran PowerShell guard logic: restricted-path deny(.env)/allow(README.md) and
                    dangerous-command deny(rm -rf /)/allow(ls -la) all returned correctly
                    (validates script logic only — live CLI wiring not exercised)

State         warn  .agentic/setup/ only has kit-manifest.json — instructions/tooling/skills/hooks
                    state files absent, meaning /init's substantive steps never ran (only the kit
                    scaffold was installed); files listed in kit-manifest.json do exist (no drift)
```
**Verdict: 2 failures, 5 warnings — setup is scaffolded but not initialized.**

*(Note: an earlier, separately-spawned `/doctor` run against identical on-disk
state reported "healthy with warnings, 0 failures" instead of 2 failures — the
skill's severity classification was not perfectly deterministic run-to-run
against the same state. Flagged as a minor consistency finding, not re-run
further per the "observe, don't fix" charter.)*

### Run 2 — after `/init` + Stage 2 feature flow completed

```
Environment   warn  git 2.54.0, pwsh 7.6.0, python 3.12.5, uv 0.11.13 all ok.
                     bash absent (expected, Windows-only session; PS1 hook
                     variants used instead). jq missing → bash guard variants
                     can't be dry-run (N/A here since PS1 used). graphify
                     resolves to D:\devTools\Python\Python312\Scripts\graphify.exe
                     (v0.7.5) instead of the uv-installed v0.9.7 — PATH shadowing.
Instructions  ok    AGENTS.md has all 8 required sections; smokeVerify recorded
                     as "blocked" (valid, not skipped); AGENTIC.md and
                     copilot-instructions.md (short/pointer-only) present;
                     tests.instructions.md has applyTo frontmatter; no pending
                     complex modules.
Tooling       warn  LSP correctly "blocked" (no app language — N/A repo).
                     graphify-out/graph.json missing, but documented as blocked
                     on missing LLM API key (genuine limitation). Real issue:
                     tooling-state.json claims graphify v0.9.7 active, but this
                     session actually runs a stale v0.7.5 from Python's Scripts
                     dir — ~\.local\bin (uv's install target) isn't on PATH.
Skills        ok    All 18 skills present incl. required kit-flow set + teach;
                     every SKILL.md has valid name/description frontmatter, no
                     duplicate names.
Hooks         FAIL  hooks.json valid; all 8 scripts present; seed data
                     (restricted-paths.txt, dangerous-commands.txt,
                     lint-commands.json) present; .agentic/audit/ gitignored.
                     CONFIRMED via direct dry-run: when toolArgs is passed as a
                     JSON-encoded STRING (the real shape the live Copilot CLI
                     sends, per .agentic/audit/2026-07-06.jsonl), restricted-
                     path-guard.ps1 returns "allow" for editing ".env" instead
                     of "deny". The script only handles toolArgs as an already-
                     parsed object, so it fails open on real CLI calls.
State         warn  kit-manifest.json's generated files all exist on disk — no
                     drift there. graphify version/PATH drift noted above.
```
**Verdict: 1 failure, 2 warnings.**

---

## Phase 4 — Real audit payload shape (redacted samples)

**Event names:** the audit-log hook's own derived `event` field (populated from
`hook_event_name`/`hookEventName`) was **null on every single line** captured —
neither guessed field name matches what the live CLI actually sends (or the CLI
doesn't send an explicit event-type field at all; the script must infer the
event kind from which other fields are present — see shapes below).

**Tool names observed** (top-level `toolName`, camelCase — matches one of the
two guesses): `create`, `edit`, `view`, `powershell`, `skill`, `glob`,
`fetch_copilot_cli_documentation`.

**Arguments field:** `toolArgs` (camelCase — matches one guess) — but **arrives
as a JSON-encoded string, not a nested JSON object.** This is the critical,
previously-unverified finding: guard scripts do `$a = $o.toolArgs; $a.path`,
which assumes `toolArgs` is already a deserialized object. Since it's actually a
string, `$a.path` silently resolves to `$null` in PowerShell, so the guard
**always allows** — confirmed independently both by direct observation (the
`.env` and dangerous-command probes below were not blocked) and by `/doctor`'s
own dry-run in Run 2 above.

**File-path field:** inside the string-encoded `toolArgs`, the key is `path`
(for `create`/`edit`). **Shell-command field:** inside the string-encoded
`toolArgs` for `powershell` tool calls, the key is `command`.

Representative redacted lines (file contents/prompts stripped, structure and
field names preserved):

```json
{"sessionId":"<redacted>","timestamp":1783342079735,"cwd":"D:\\Projects\\akm-live-test","toolName":"create","toolArgs":"{\"path\":\"D:\\\\Projects\\\\akm-live-test\\\\.env\",\"file_text\":\"<redacted>\"}","toolResult":{"resultType":"success","textResultForLlm":"Created file D:\\Projects\\akm-live-test\\.env with 9 characters"}}
```
```json
{"sessionId":"<redacted>","timestamp":1783342505781,"cwd":"D:\\Projects\\akm-live-test","toolName":"edit","toolArgs":"{\"path\":\"D:\\\\Projects\\\\akm-live-test\\\\AGENTS.md\",\"old_str\":\"<redacted>\",\"new_str\":\"<redacted>\"}","toolResult":{"resultType":"success","textResultForLlm":"File D:\\Projects\\akm-live-test\\AGENTS.md updated with changes."}}
```
```json
{"sessionId":"<redacted>","timestamp":1783341802768,"cwd":"D:\\Projects\\akm-live-test","prompt":"<redacted>"}
```
```json
{"sessionId":"<redacted>","timestamp":1783341812338,"cwd":"D:\\Projects\\akm-live-test","reason":"complete"}
```

Note the last two shapes have **no `toolName`/`toolArgs` at all** — a
`userPromptSubmitted`-style event is `{sessionId, timestamp, cwd, prompt}`; a
`sessionEnd`-style event is `{sessionId, timestamp, cwd, reason}`. Scripts must
distinguish event kind structurally (presence/absence of `toolName` vs `prompt`
vs `reason`), since no explicit event-name field is populated.

---

## Summary

**What worked:** Kit scaffolding (Phase 0), skill discovery incl. natural-language
routing (Phase 1), `/doctor`'s diagnostics (Phase 2 — reaches a verdict reliably,
though severity classification varied slightly run-to-run on identical state),
the full `/init` orchestration with state persistence/resume (Phase 5), `/teach`
routing and refinement (Phase 6), and the entire Stage 2 `/feature` flow
including guided vs. autonomous story modes and cold-session state recovery
(Phase 7) — all passed cleanly.

**What broke (the main event):** the live hooks do not actually block anything.
Both the restricted-path guard (`.env` creation) and the dangerous-command guard
(sentinel `echo` pattern) failed to fire in Phase 3, and this was traced to a
concrete, previously-unverified root cause: the real GitHub Copilot CLI sends
`toolArgs` as a **JSON-encoded string**, not a parsed object, while all four
guard/hook PowerShell (and presumably bash) scripts access it as
`$o.toolArgs.path` / `.command`, assuming it's already an object. This makes the
`preToolUse` guards **fail-open on the real CLI** — they never deny anything in
practice, despite passing their own internal dry-run tests (which fed them
pre-parsed objects instead of real payloads). The audit-log hook is unaffected
(it just re-serializes whatever it receives), which is why the `.jsonl` trail
itself was intact and is what allowed this bug to be caught at all.

**Fix needed (not applied — observe & report only, per charter):** in
`restricted-path-guard.ps1/.sh`, `dangerous-command-guard.ps1/.sh`, and
`lint-on-edit.ps1/.sh`, parse `toolArgs` a second time
(`$a = $o.toolArgs | ConvertFrom-Json` in PowerShell; `echo "$toolArgs" | jq` in
bash) before accessing its fields. The audit-log hook's `hook_event_name` /
`hookEventName` field guesses are also unconfirmed — no event-type field was
ever observed populated; downstream consumers should key off field presence
(`toolName`+`toolArgs` vs `prompt` vs `reason`) instead.

**Secondary/minor findings:**
- `graphify` version drift: a stale v0.7.5 install on the Python `Scripts`
  PATH shadows the `uv`-installed v0.9.7, silently used by tooling checks.
- `/doctor`'s pass/fail severity classification was not perfectly stable across
  repeated runs against identical on-disk state (once reported "healthy,
  0 failures", another time "2 failures") before `/init` completed.
- Guided-mode's "review always needs a fresh session" rule is documented in the
  skill text but isn't tooling-enforced — nothing currently prevents running
  it in the same session, which this verification run itself had to do as a
  practical stand-in.

Nothing here is a crash or data-loss risk; the kit's scaffolding, skills, and
orchestration logic (`/init`, `/feature`, `/teach`) all behave exactly as
designed. The one real risk is that teams may believe the guard hooks are
protecting restricted paths/dangerous commands when, on the current GA CLI
payload shape, they are not.
