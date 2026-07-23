# AKMaestro — Manual Walkthrough (setup + multi-repo)

A hands-on guide to test the whole kit yourself: install it, run Stage 1
(`/akmaestro-init`), and drive a Stage 2 feature that spans **three repos** — your main
app plus a sibling repository you own (modifiable) and one you only read.

This is the human counterpart to `PROMPT.md` (which hands the checks to the
agent). Here *you* drive and watch. Budget ~45–60 min.

> **Surface:** the Copilot **CLI** is the most complete path — hooks are GA and
> were verified live there. VS Code Copilot works too, but its agent hooks are
> preview and may be disabled by org policy (the boundary/guard checks in Part 5
> and 6 will then be no-ops — note it and move on).
>
> **Fresh sessions matter:** skills and hooks are only discovered in a **new**
> Copilot session. After every install step, start a new CLI session (or new VS
> Code window) at the repo root before continuing.

---

## The model in one picture

```
akm-workspace/
├── app-a/      ← MAIN repo. Kit installed here. All /feature state lives here.  (flow home)
├── lib-b/      ← MODIFIABLE sibling. You own it; the agent may change it.      (../lib-b)
└── vendor-c/   ← READ-ONLY sibling. Consult it; the agent must never edit it.  (../vendor-c)
```

- **app-a** is the *flow home*: one feature = one spine of state, even when a
  story also changes `lib-b`.
- **lib-b** is functionally part of the app, just in its own git repo. Stories
  can change it; its path is listed in the compatibility file
  `.agentic/hooks/editable-paths.txt`.
- **vendor-c** is another team's code. The agent reads it to understand behavior
  (via its Graphifyy graph, and its source when needed) but is **blocked** from
  editing it. A change it *seems* to need becomes an external dependency to
  raise, never a story.

---

## Part 0 — Prerequisites

- **GitHub Copilot** — CLI (`copilot`) or VS Code.
- **`uv`**:
  ```bash
  curl -LsSf https://astral.sh/uv/install.sh | sh                 # macOS/Linux
  ```
  ```powershell
  powershell -c "irm https://astral.sh/uv/install.ps1 | iex"      # Windows
  ```
- **`jq`** — only needed for the *bash* hook guards (macOS/Linux). On Windows the
  PowerShell guards are used and don't need it.
- **Graphifyy** may need an LLM API key to build its graph; if it can't, the
  tooling step records `blocked` and setup still completes. That's expected.

---

## Part 1 — Scaffold the scratch workspace

Copy-paste this to create three tiny, coherent repos. The toy feature will be
"apply tier discounts at checkout" — it needs a change in **app-a** and in
**lib-b**, and must match a legacy rule that lives (unchangeable) in **vendor-c**.

```bash
mkdir akm-workspace && cd akm-workspace

# vendor-c — READ-ONLY sibling (the legacy rule app-a must match, can't change)
mkdir vendor-c && cd vendor-c && git init -q
cat > discount.py <<'EOF'
def legacy_discount_rate(tier):
    """The canonical rate table. app-a must match this exactly."""
    return {"gold": 0.20, "silver": 0.10}.get(tier, 0.0)
EOF
git add -A && git commit -qm "vendor-c: legacy pricing rule" && cd ..

# lib-b — MODIFIABLE sibling repository (you own it)
mkdir lib-b && cd lib-b && git init -q
cat > pricing.py <<'EOF'
def apply_discount(price, tier):
    # TODO(feature): apply the tier discount
    return price
EOF
cat > test_pricing.py <<'EOF'
from pricing import apply_discount
def test_no_discount_by_default():
    assert apply_discount(100.0, "none") == 100.0
EOF
git add -A && git commit -qm "lib-b: pricing stub + test" && cd ..

# app-a — MAIN app (flow home); calls lib-b's pricing
mkdir app-a && cd app-a && git init -q
cat > checkout.py <<'EOF'
# In the real app this imports from lib-b. For the walkthrough, keep it simple.
def checkout_total(price, tier):
    # TODO(feature): use lib-b's apply_discount so tiers get their discount
    return price
EOF
git add -A && git commit -qm "app-a: checkout stub"
# stay in app-a for the next part
```

You're now in `app-a/`, with `../lib-b` and `../vendor-c` as siblings.

> Prefer to test on **real** repos? Skip Part 1, `cd` into your real main repo,
> and use its real sibling checkouts as B and C in Part 4. Everything else is
> identical.

---

## Part 2 — Install the kit into the main repo

From inside `app-a/`:

```bash
uvx --from git+https://github.com/AbbasKMoussa/akm-murex-starter-kit.git akmaestro init
```

Expect a list of created files ending with "Next: … run /akmaestro-init". Confirm:

```bash
ls .github/skills            # 19 skill folders
ls .agentic/hooks            # restricted-paths.txt, dangerous-commands.txt, editable-paths.txt, lint-commands.json
cat .agentic/hooks/editable-paths.txt   # only comments so far — nothing outside the repo is writable yet
```

---

## Part 3 — Team lead opens a fresh Copilot session

Start a **new** session at the `app-a` root:

```bash
copilot          # or open a fresh VS Code window at app-a/
```

Sanity check that the kit is discoverable — ask:

> what agentic skills are available here?

You should see `/akmaestro-init`, `/doctor`, `/teach`, `/feature`, and the `setup-*` /
`feature-*` / `story-*` skills.

---

## Part 4 — Team lead runs `/akmaestro-init` and commits it

Run:

```text
/akmaestro-init
```

Walk the four topics. The **instructions** topic should first present one sourced
summary of product, commands, verification, Git workflow, and repository
context. Correct only what is wrong or missing. For *Workspace & Dependencies*,
use:

| Prompt | Your answer |
|---|---|
| Does this repo depend on other locally checked-out repos? | Yes |
| `../lib-b` — role? | **Modifiable sibling repository** — we own it; part of the app. Changes reach app-a by import/rebuild. |
| `../vendor-c` — role? | **Read-only sibling repository** — consult only, never edit. |

- **Tooling** topic: it will try to build a Graphifyy graph for app-a **and for
  each declared dependency** (lib-b and vendor-c). If graphify needs an API key
  and can't run, let it mark `blocked` and continue.
- **Skills / Hooks**: verify the full catalog. Review hooks while they remain
  disabled, then explicitly consent if you want the live hook checks.

When `/akmaestro-init` finishes it writes `.github/AGENTIC.md` (the team guide) and a
real `AGENTS.md`. **Verify the workspace was recorded correctly:**

```bash
grep -A8 "Workspace & Dependencies" AGENTS.md      # both deps, with roles
cat .agentic/hooks/editable-paths.txt              # MUST contain ../lib-b, MUST NOT contain ../vendor-c
uv run --no-project python .agentic/bin/akmaestro-state.py setup-status
git check-ignore .agentic/local/readiness.json     # MUST be ignored
```

Also inspect `.agentic/setup/environment-requirements.json`: it should require
`uv`, Graphifyy, the selected `lsp-*`, and graph artifacts for all three repos.
Every graph path must be under app-a's
`.agentic/local/graphs/<repository-id>/graph.json`; neither sibling may receive
generated graph output.
Inspect `.agentic/setup/instructions-state.json` too: it should contain strict
product, all seven command definitions/results, verification, Git-policy,
repository-context, and generated-file evidence. Confirm finite commands were
checked through controller `action-check` and no placeholder remains in
`AGENTS.md`.
Review the shared diff and commit it. Do not add anything under `.agentic/local/`.

> ✅ **Check 1 (the crux of the model):** `../lib-b` is in `editable-paths.txt`;
> `../vendor-c` is **not**. If vendor-c ended up in there, the boundary isn't
> protecting it — that's a bug to report.

---

## Part 5 — Verify setup health + the boundary guard

Open a **fresh session** (hooks/skills just changed), then:

### 5a. Doctor

```text
/doctor
```

Expect a grouped ok/warn/fail report that reaches a verdict. Warnings are fine
(e.g. Graphifyy blocked on an API key, no LSP language). It should specifically
check that `editable-paths.txt` matches the declared roles and that each
dependency has a graph.

### 5b. The boundary guard, by hand (the new, important bit)

These dry-runs feed the guard the **real CLI payload shape** (`toolArgs` as a
JSON-encoded string). Use `pwsh` on Windows, `bash` on macOS/Linux:

```powershell
# Windows
$g = ".github\hooks\scripts\restricted-path-guard.ps1"
'{"toolName":"edit","toolArgs":"{\"path\":\"../vendor-c/discount.py\"}"}' | pwsh -ExecutionPolicy Bypass -File $g   # expect DENY (read-only, outside repo)
'{"toolName":"edit","toolArgs":"{\"path\":\"../lib-b/pricing.py\"}"}'     | pwsh -ExecutionPolicy Bypass -File $g   # expect ALLOW (modifiable sibling)
'{"toolName":"edit","toolArgs":"{\"path\":\".env\"}"}'                    | pwsh -ExecutionPolicy Bypass -File $g   # expect DENY (restricted glob)
'{"toolName":"edit","toolArgs":"{\"path\":\"checkout.py\"}"}'             | pwsh -ExecutionPolicy Bypass -File $g   # expect ALLOW (in-repo)
```

```bash
# macOS/Linux
g=.github/hooks/scripts/restricted-path-guard.sh
printf '%s' '{"toolName":"edit","toolArgs":"{\"path\":\"../vendor-c/discount.py\"}"}' | bash $g   # DENY
printf '%s' '{"toolName":"edit","toolArgs":"{\"path\":\"../lib-b/pricing.py\"}"}'     | bash $g   # ALLOW
printf '%s' '{"toolName":"edit","toolArgs":"{\"path\":\".env\"}"}'                    | bash $g   # DENY
printf '%s' '{"toolName":"edit","toolArgs":"{\"path\":\"checkout.py\"}"}'             | bash $g   # ALLOW
```

> ✅ **Check 2:** vendor-c → deny, lib-b → allow, `.env` → deny, in-repo → allow.
> This proves the boundary distinguishes modifiable from read-only siblings.

### 5c. Live guard fire (CLI, hooks enabled)

In the live session, ask the agent to do something it should be blocked from:

> create a file `../vendor-c/scratch.txt` with the text "hello"

Expect it to be **denied** by the restricted-path guard (you'll see the deny
reason). Then:

> create a file `notes.md` here with one line

Expect that to **succeed**.

> ✅ **Check 3:** the guard actually fires live — vendor-c edit blocked, in-repo
> edit allowed. (If nothing is blocked, capture the audit line from
> `.agentic/audit/<date>.jsonl` for that call — the payload shape may have moved.)

---

## Part 6 — Stage 2: a cross-repo feature

Open a fresh **developer** session from the initialized commit. Do not rerun
`/akmaestro-init`; run:

```text
/feature
```

It must probe this developer's local requirements. If something is missing, it
shows the structured remediation action and asks before running it. Decline once
to confirm feature creation remains blocked, then approve/remediate and rerun.
If Graphifyy was documented as blocked during `/akmaestro-init`, it must be made available
now; Stage 2 does not bypass mandatory developer readiness.

Start a feature — title it **"tier discounts at checkout"**. Then walk the phases
(`/feature-understand` → `/feature-frame` → `/feature-split` → the per-story
loop). Watch for these multi-repo behaviors:

Confirm there is no `.agentic/features/index.json`; this worktree's selection is
`.agentic/local/active-feature.json` and remains ignored.

**Understand** — it should pull context from app-a, lib-b, **and** vendor-c
(reading the legacy rate table in `vendor-c/discount.py`), and record vendor-c's
rule as a *fixed constraint* it must match, not change.

**Split** — stories should be **tagged with the repos they touch**. Expect
something like: one story implementing `apply_discount` in **lib-b** (with its
test), and one wiring `checkout_total` in **app-a** to call it. The story files
under `.agentic/features/<id>/stories/` should have a **Repos** line.

> ✅ **Check 4:** a story touching lib-b is tagged for it; nothing proposes
> *editing* vendor-c. If matching the legacy rate needs a vendor-c change, it's
> recorded in `feature.md` as an external dependency — not a story.

**Per-story loop** — run the lib-b story. During **Implement**:

- the agent edits `../lib-b/pricing.py` and runs **lib-b's own** test
  (`test_pricing.py`) — following lib-b's build/test, not app-a's;
- the guard permits the lib-b edit (it's modifiable) but would block a vendor-c
  edit.

> ✅ **Check 5 (the genuinely unproven bit):** can the CLI session rooted at
> app-a actually **read and write files in `../lib-b`** at all? This depends on
> the surface's workspace/trust settings, not just our guard. Note whether the
> agent can edit lib-b, or whether the surface itself refuses paths outside the
> session root. **This is the single most valuable thing to report.**

Then run the app-a story (wire `checkout_total` to use lib-b). Finish with
**Feature review** — it should check cross-repo integration: lib-b's tests pass,
its change is committed there, and app-a consumes it.

---

## Part 7 — Everyday helpers (quick)

- `/teach` — say *"remember: in lib-b, every public function needs a test in
  `test_*.py`"*. Watch it gate, refine, and propose where it lands.
- `akmaestro update` — from app-a, re-run to see it refresh only kit-owned
  (unmodified) files and keep anything you customized:
  ```bash
  uvx --refresh --from git+https://github.com/AbbasKMoussa/akm-murex-starter-kit.git akmaestro update
  ```

---

## Part 8 — What to report back

The checks above (✅ 1–5) are the spine. For each: pass/fail + what you saw.
The three highest-value findings:

1. **Check 1** — did the roles route correctly (lib-b modifiable, vendor-c read-only)?
2. **Check 3** — did the guard actually fire live to block the vendor-c edit?
3. **Check 5** — could the app-a session read/write lib-b across the repo
   boundary at all, or did the surface refuse it? (If refused, the multi-repo
   flow needs the deps opened as a multi-root workspace / the session started a
   level up — tell me what you observed.)

Plus anything confusing, any file written you didn't expect, and (if a guard
failed to fire) the raw audit line for that call from
`.agentic/audit/<date>.jsonl`.
