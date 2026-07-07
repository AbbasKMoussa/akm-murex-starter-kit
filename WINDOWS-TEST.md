# AKMaestro — Windows Verification Prompt

> **For the agent:** You are verifying **AKMaestro** on Windows. Work through the
> phases below in order, run each command, compare against the **Expected**
> result, and record PASS/FAIL. At the end, write a results table to
> `windows-test-results.md` at the repo root and summarize what passed, what
> failed, and any surprises. Do not "fix" failures unless asked — your job here is
> to *observe and report*. These checks target two things that have never run on
> Windows: the **PowerShell hook scripts** and the **Windows installer path**.

AKMaestro is a kit that sets a repo up for agentic coding (Stage 1) and drives
features (Stage 2). Hooks are guard scripts Copilot runs around tool calls; each
guard reads a JSON event on **stdin** and prints a JSON decision on **stdout**.
The PowerShell variants (`*.ps1`) are unverified — that's the point of this run.

---

## Phase A — Installer on Windows

Goal: confirm `akmaestro init` works on Windows and lays files down correctly.

1. Ensure `uv` is installed (PowerShell):
   ```powershell
   powershell -c "irm https://astral.sh/uv/install.ps1 | iex"
   ```
2. Create a scratch folder and install into it:
   ```powershell
   mkdir akm-scratch; cd akm-scratch
   uvx --refresh --from git+https://github.com/AbbasKMoussa/akm-murex-starter-kit.git akmaestro init
   ```

**Expected:**
- Command exits 0 and prints a list of created files ending with "Next: … run /init".
- `.github\skills\` contains **18** skill folders (each with `SKILL.md`).
- `.github\hooks\scripts\` contains the four `*.ps1` files.
- `.agentic\hooks\` contains `restricted-paths.txt`, `dangerous-commands.txt`,
  `editable-paths.txt`, `lint-commands.json`.
- `.gitignore` exists and contains `.agentic/audit/`.
- `AGENTS.md` was created (placeholder).

Record the skill count and whether each expected path exists.

---

## Phase B — PowerShell hook unit tests

> Note: since v0.4.0 these script-logic checks (plus the workspace-boundary
> cases) also run automatically in CI via `pwsh` on Linux and Windows
> (`tests/test_installer.py`). Phase B remains useful as a manual smoke check;
> Phase C (live Copilot) is what CI cannot cover.

Run from **inside `akm-scratch`**. Each test pipes a JSON event to a guard script
and checks the printed decision. Use `-ExecutionPolicy Bypass` so local scripts
run regardless of policy.

> Note: every script **always exits 0** by design (fail-open), so judge by
> **stdout**, not exit code. For `allow`, stdout is exactly
> `{"permissionDecision":"allow"}`. For `deny`, stdout is a JSON object whose
> `permissionDecision` is `deny` (key order may vary — match the value, not the
> whole string).
>
> If inline single-quote piping misbehaves, write the JSON to a temp file and use
> `Get-Content -Raw tmp.json | pwsh -ExecutionPolicy Bypass -File <script>`.

### restricted-path-guard.ps1

> **Real payload shape (verified 2026-07-06):** the GA Copilot CLI sends
> `toolArgs` as a **JSON-encoded string**, not a nested object. The tests below
> use that string form (`"toolArgs":"{\"path\":\"…\"}"`). Object-form is still
> accepted for back-compat, but string is what the live CLI actually sends —
> testing the object form is what previously hid a fail-open bug.

```powershell
$g = ".github\hooks\scripts\restricted-path-guard.ps1"
'{"toolName":"edit","toolArgs":"{\"path\":\".env\"}"}'               | pwsh -ExecutionPolicy Bypass -File $g   # B1
'{"toolName":"edit","toolArgs":"{\"path\":\"README.md\"}"}'          | pwsh -ExecutionPolicy Bypass -File $g   # B2
'{"tool_name":"create","tool_input":"{\"path\":\"secrets/x.txt\"}"}' | pwsh -ExecutionPolicy Bypass -File $g   # B3
'{"toolName":"edit","toolArgs":"{\"path\":\"src/app.py\"}"}'         | pwsh -ExecutionPolicy Bypass -File $g   # B4
'garbage not json'                                                   | pwsh -ExecutionPolicy Bypass -File $g   # B5
```

**Expected:** B1 **deny** · B2 **allow** · B3 **deny** (snake_case payload +
directory match on `secrets/**`) · B4 **allow** · B5 **allow** (fail-open on
unparseable input). B1 passing proves the string-encoded `toolArgs` is decoded;
B3 proves it reads both camelCase and snake_case payloads.

### dangerous-command-guard.ps1

```powershell
$g = ".github\hooks\scripts\dangerous-command-guard.ps1"
'{"toolName":"powershell","toolArgs":"{\"command\":\"rm -rf /\"}"}'                  | pwsh -ExecutionPolicy Bypass -File $g  # B6
'{"toolName":"powershell","toolArgs":"{\"command\":\"ls -la\"}"}'                    | pwsh -ExecutionPolicy Bypass -File $g  # B7
'{"toolName":"powershell","toolArgs":"{\"command\":\"git push --force origin main\"}"}' | pwsh -ExecutionPolicy Bypass -File $g  # B8
'{"toolName":"edit","toolArgs":"{\"path\":\"a.md\",\"file_text\":\"rm -rf /\"}"}'    | pwsh -ExecutionPolicy Bypass -File $g  # B9
```

**Expected:** B6 **deny** · B7 **allow** · B8 **deny** · B9 **allow**. B9 is the
key one: the dangerous text is in file *content*, not a shell command, and the
guard only reads the `command` field — so it must **allow**. (If B9 denies, the
guard is wrongly scanning the whole payload — report it.)

### audit-log.ps1

```powershell
$a = ".github\hooks\scripts\audit-log.ps1"
'{"sessionId":"abc","timestamp":1,"cwd":"C:\\x","prompt":"hi"}' | pwsh -ExecutionPolicy Bypass -File $a  # B10
Get-ChildItem .agentic\audit\*.jsonl | ForEach-Object { Get-Content $_ -Tail 1 }
```

**Expected:** B10 prints nothing (observational hook) and exits 0; a
`.agentic\audit\<date>.jsonl` file now exists with one JSON line containing
`"event":"userPromptSubmitted"` and `"session":"abc"`. This uses the **real**
CLI shape (no `hook_event_name` field), so it verifies the event kind is
inferred structurally from the presence of `prompt`.

### lint-on-edit.ps1

```powershell
$l = ".github\hooks\scripts\lint-on-edit.ps1"
'{"toolName":"edit","toolArgs":"{\"path\":\"AGENTS.md\"}"}' | pwsh -ExecutionPolicy Bypass -File $l  # B11
```

**Expected:** B11 prints nothing and exits 0 — no lint command is configured for
`.md` in `lint-commands.json`, so it's a correct no-op.

---

## Phase C — Live Copilot (only if Copilot is available on this machine)

Skip if GitHub Copilot (VS Code or CLI) isn't installed here; note it as skipped.

1. Open Copilot **in a fresh session** at the `akm-scratch` root (skills are only
   discovered in a new session).
2. Ask: **"where are we / what can you do?"** and check the AKMaestro skills are
   discoverable (e.g. `/doctor`, `/teach`, `/init`, `/feature`).
3. Run **`/doctor`** and capture its health report.
4. If hooks are enabled on this surface, try an edit to `.env` and to a normal
   file, and note whether the **restricted-path guard** actually fires (deny vs
   allow) in a real session — this verifies the live tool-name/`toolArgs` wiring.

Report: which skills were discoverable, what `/doctor` said, and whether hooks
fired live (and on which surface: VS Code or CLI).

---

## Report

Write `windows-test-results.md` with a table like:

| Test | Expected | Actual | Pass? |
|------|----------|--------|-------|
| A: skills installed | 18 | … | |
| B1 .env edit | deny | … | |
| … | | | |

Then summarize: PowerShell guards correct? Installer correct on Windows? Live
Copilot behavior (or skipped)? List any failures verbatim (exact stdout) so they
can be fixed.
