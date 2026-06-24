---
name: teach
description: >-
  Decide where a lesson, rule, convention, or fact the developer wants to teach
  the AI should be persisted, and refine its wording before adding it. Use
  whenever the developer wants to teach, remember, or capture a durable
  instruction — e.g. "remember that…", "from now on…", "going forward…",
  "teach the AI that…", "always/never do X", "don't do X again", "stop doing X",
  "make a rule that…", "as a convention…", "note that…", "the AI keeps doing X",
  or "add this to the instructions" — especially when they are unsure which file
  or scope it belongs in.
allowed-tools:
  - shell
---

# teach — route and refine agent instructions

This skill takes something the developer wants to teach the AI and (1) checks it
is worth persisting, (2) refines the wording, (3) decides the correct file and
scope, and (4) places it there following this repository's instruction
best-practices. Its goal is that every lesson lands in the right place, written
well, without duplicating or contradicting what already exists.

## When to use

Use this whenever the developer is trying to make the AI *remember* something
durable: a convention, a rule, a recurring pitfall, a build/test caveat, a
safety boundary, or a personal preference. Do **not** use it for one-off task
context — see the gate below.

## Input

The lesson to capture. If the developer only invoked the skill without stating
it (e.g. just `/teach`), ask: "What do you want the AI to remember, and roughly
where does it apply?"

## Step 1 — Gate: is this worth persisting?

Persist it only if it is a **durable, general** statement that should influence
future work. Be strict here — default to *not* persisting and recommend the
best-practice alternative when it looks like:

- a one-off task detail ("use port 4500 for this debugging session");
- transient context that will be stale tomorrow;
- something already obvious from the code or existing instructions;
- a vague aspiration that won't change concrete behavior.

State your recommendation clearly (e.g. "I'd keep this out of the instructions
because…"), but the **developer makes the final call**: if they still want it
persisted after your pushback, proceed. Never silently drop a lesson.

## Step 2 — Refine the statement

Rewrite the lesson into a clear instruction before placing it:

- **Imperative and specific** — "Run `pnpm test:unit` before pushing", not "tests
  matter".
- **Behavior-focused, not implementation trivia** — describe what to do/avoid.
- **Include the "why" when it changes behavior** — a short reason makes the rule
  stick and helps the agent generalize.
- **Strip vagueness** — remove "should probably", "try to", "etc." unless they are
  load-bearing.

Show the refined version and the original if you changed it materially.

## Step 3 — Route: choose file and scope

Pick the **most specific** scope that fully covers where the lesson applies. When
a lesson is both module- and pattern-scoped (e.g. "in `payments`, tests mock the
ledger"), most-specific-wins: prefer the narrower file, or place a path-scoped
instructions file under the module.

| The lesson… | Goes to |
| --- | --- |
| is a **personal preference** about how *you* like the AI to behave (not a team norm) | user-level config — see Step 5b |
| applies only to **files matching a pattern** (tests, `*.tsx`, migrations, `**/api/**`) | `.github/instructions/<topic>.instructions.md` with an `applyTo` glob |
| applies only **inside one module/directory** | `<module>/AGENTS.md` |
| applies **repo-wide / cross-cutting** | root `AGENTS.md`, under the right section |

Within root `AGENTS.md`, place by section: build caveats → **Build › Notes**;
test guidance → **Tests › Notes** (or `tests.instructions.md` if pattern-scoped);
safety boundaries → **Agent Rules**; branch/commit norms → **Git Workflow**;
product/stack facts → their sections.

`.github/copilot-instructions.md` is **almost never** the destination — it stays
short and only points to `AGENTS.md`, `.github/instructions/`, and nested
`AGENTS.md` files. Do not add lessons there; adding them duplicates the source of
truth and causes conflicts.

Use `shell` to discover targets, e.g. find nested module files
(`find . -name AGENTS.md`) and existing path-scoped files
(`ls .github/instructions`).

## Step 4 — Conflict and duplicate check

Before writing, read the chosen target (and the root `AGENTS.md`) and check
whether the lesson is already present or contradicted:

- **Duplicate** — already stated: tell the developer; do not add a second copy.
- **Conflict** — an existing line says the opposite: surface it
  ("this conflicts with `<existing line>` — replace it, or is this a scoped
  exception?") and let them decide. Replacing existing text needs confirmation
  (see Step 5).
- **Refinement** — the existing line is vaguer: offer to tighten it in place.

## Step 5 — Place it

1. Show the developer: the exact text, the target file, and the section/insertion
   point.
2. If the **target file does not exist** (a new module `AGENTS.md`, a new
   `<topic>.instructions.md`), create it — new files may be created directly. For
   a new `.instructions.md`, add the `applyTo` frontmatter. For a missing module
   `AGENTS.md`, prefer suggesting `init module <path>` if the module warrants full
   setup; otherwise create a minimal one.
3. If the file **exists**, never overwrite or weaken existing content without
   confirmation. Appending a new line under the right heading is fine after you
   have shown it; replacing or rewording existing lines requires an explicit OK.
4. Apply the change and confirm what landed where in one line.

### Step 5b — Personal preferences (surface-aware)

Personal preferences must not be committed to the shared repo. Their home differs
by surface, so handle each:

- **Copilot CLI** — append to `~/.copilot/copilot-instructions.md` (create it if
  missing). This is a real, portable path.
- **VS Code Copilot** — user instructions live in the VS Code *profile*, not at a
  fixed filesystem path. Do not try to write it by path. Instead give the
  developer the refined text and the steps: run **Chat: New Instructions File**,
  choose **User** scope, and paste it.

If you do not know which surface the developer uses, ask. If they use both, do
both.

## Best-practices this skill enforces

- One source of truth: root `AGENTS.md`. `copilot-instructions.md` only points to
  it.
- Module `AGENTS.md` files describe only what *differs* in that module.
- Path-scoped rules belong in `.github/instructions/*.instructions.md` via
  `applyTo`, not pasted into every file's neighbourhood.
- Never duplicate a rule across files; never overwrite existing instructions
  without confirmation.
