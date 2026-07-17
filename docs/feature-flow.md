# Stage 2: Feature Flow (master spec)

A repeatable, per-feature flow — BMAD-style but leaner. It assumes Stage 1 is
complete and committed by the team lead. It reuses the installed skills,
schemas, and repo-local state controller.

The flow is implemented as 11 bundled skills. This document remains the product
specification for improving their behavior.

## Working model (BMAD-style)

Four principles drive the whole flow:

1. **Fresh context per step.** Each step runs in its own Copilot session. When a
   step finishes it does **not** roll straight into the next — it tells the user
   to open a new session/context and run the next command. Continuity is carried
   by on-disk **state + artifacts**, never by conversation history. This keeps
   each step focused and avoids context bloat.

   *Light-context exception:* the rule guards context quality, not ceremony. At a
   gate, if the current session is still light (short history, few files read),
   the step may offer to continue with the next command in the same session. The
   one boundary where this never applies is implement → review, where a fresh
   session is the point: the reviewer must not inherit the implementer's context.
2. **Status/help always available.** `feature status` tells you exactly where you
   are — current feature, phase, story, what's done, and the precise next command
   to run in the new context. `feature help` explains the flow. (This is the
   "where are we" command, BMAD-style.)
3. **Gate every boundary.** Every phase boundary is a hard stop: the step ends by
   asking for explicit approval, records it in state, and only then prints the
   next command. Nothing auto-proceeds across a phase. (The **one exception** is
   the internal steps of the Phase 3 per-story loop, which can run ungated in
   autonomous mode — see Two modes.)
4. **Human-in-the-loop throughout.** A step is a *collaboration*, not an agent
   monologue that ends at the gate. Specialists think out loud, ask, and iterate
   *during* the step. And they **meet the user where they are**: if the user
   already has something (an approach, a story split, a fix), the specialist
   takes and accepts it, takes and enhances it, or — with a clearly stated reason
   — pushes back and proposes an alternative. Only when the user has nothing does
   the specialist propose from scratch.

## Two modes (Phase 3 per-story loop only)

The mode choice applies **only to the Phase 3 per-story loop** (Prime → Plan →
Implement → Review → Learn). Phases 1 (Understand, Frame), 2 (Split), 4 (Feature
review), and 5 (Retro) are **always gated/HITL** regardless of mode.

For a given story, the loop runs in one of two modes:

- **Guided (HITL)** — each of the five steps is a separate gated step in its own
  fresh context: approve, open a new session, run the next. Maximum oversight.
- **Autonomous** — the five steps run **back-to-back in one session**, no stops
  between them, producing a primed → planned → implemented → reviewed → learned
  story in one shot. It still surfaces genuine blockers/hard decisions, and the
  hooks (guards/lint) still apply. Faster, less oversight.

Mode is chosen before priming each story, defaults to guided, and can be set
**per story** until Prime begins. `feature status` shows the current
mode. The loop's *entry* and *exit* are still phase-level gates — autonomous only
removes the *inside-the-loop* stops for that story; it does not auto-advance to
the next story.

## Each step is a curated specialist

Like BMAD, every step is run by a **specialist**, not a generic agent — but we do
**not** map 1:1 to BMAD's full roster (Analyst/PM/Architect/PO/SM/Dev/QA/UX/…).
We use a leaner set, merging roles where it adds no value, to get the most value
for the least complexity.

The specialist is carried by the **skill** (decision: curated skills as
specialists). Each step's `SKILL.md` embeds a named role persona — its identity,
expertise, and what "good" looks like — plus its templates and checklists (the
equivalent of BMAD's agent "dependencies"). Combined with fresh context per
step, each step therefore runs as a focused specialist loaded only with its own
role and resources. This keeps the cross-surface uniformity of Stage 1 (skills
work the same in VS Code + CLI) with no loss of quality: the quality comes from
the curation and the clean context, not from any agent primitive.

## Prerequisite

`/feature` first checks the committed Stage 1 state. If repository initialization
is incomplete, only the team lead resumes `/init`. It then runs the local
readiness probes from committed environment requirements. Missing `uv`,
Graphifyy, selected LSPs, or graphs block mutation; `/feature` presents the
structured remediation action and asks before running it. Developers never run
`/init` for workstation setup.

## Multi-repo workspaces

The main repo is always the **flow home**: state, artifacts, and every session
live here, even when work spans repos. Locally checked-out sibling repositories
are declared in `AGENTS.md` (Workspace & Dependencies) with one of two roles:

- **Modifiable sibling repository** — a repo the team owns; functionally part of
  the application, just in its own git repo. Stories may change it as part of
  normal work here: Split tags each story with the repos it touches, the
  sibling-side contract (interface + its tests, per that repo's own `AGENTS.md`)
  is delivered before the consuming side, and changes are committed in the
  sibling repo referencing the feature id. The restricted-path guard permits
  these paths via the compatibility file `.agentic/hooks/editable-paths.txt`.
- **Read-only sibling repository** — another team's code, consulted to
  understand behavior: use its Graphifyy graph for the high-level map and open
  code only when a specific behavior matters. Findings there are fixed
  constraints. It is never edited; a needed change is recorded in `feature.md`
  as an external dependency for the owning team, never a story.

## Phases and skills

The feature flow ships as an orchestrator plus per-step skills (so each step can
run in its own context), mirroring `/init` + `/setup-*`.

| Phase | Skill | Specialist persona | Output |
| --- | --- | --- | --- |
| — | `/feature` | Orchestrator | Start/resume a feature; `feature status`, `feature help`. |
| 1a. Understand | `/feature-understand` | Analyst | `understanding.md`: problem, current behavior, affected areas, edge cases, open questions, sources. |
| 1b. Frame | `/feature-frame` | Framer (PM) | `feature.md`: high-level solution approach (adaptive to the dev's idea) + acceptance criteria. |
| 2. Split | `/feature-split` | Planner (scrum-master) | `stories/` — high-level stories with their own acceptance criteria. |
| 3. Per-story loop | `/story-prime` → `/story-plan` → `/story-implement` → `/story-review` → `/story-learn` | Researcher → Architect → Implementer → Reviewer → Librarian | One story primed, planned, built, reviewed, and its lessons captured. Repeats per story. |
| 4. Feature review | `/feature-review` | QA / Integration reviewer | `review.md`: high-level review + guided manual-testing steps. |
| 5. Retrospective | `/feature-retro` | Retro facilitator | `retro.md` + AI-infra updates (via `/teach`). |

Each skill embeds the templates/checklists its persona uses (e.g.
`/feature-frame` ships a feature-doc template + an acceptance-criteria checklist;
`/story-review` ships a review checklist). This roster is leaner than BMAD's —
story-level review and feature-level review are distinct personas (a close-up
code Reviewer in Phase 3; a QA / Integration reviewer in Phase 4, at feature
altitude), and roles like UX/PO/Orchestrator-as-separate are dropped or folded
into `/feature`. Roster: Analyst, Framer, Planner, Researcher, Architect,
Implementer, Reviewer (story), QA / Integration reviewer (feature), Librarian,
Retro facilitator.

## Sources (Phase 1)

The specialists gather from the codebase + Graphifyy + online sources they can
fetch, always. **Jira/wiki are optional and credential-gated**: if the user
configures a Personal Access Token + base URL via environment variables, the
Analyst pulls tickets/pages directly; otherwise it asks the user to paste them.
PATs are never committed (read from env / a gitignored config). Deeper
integration could later be an MCP server.

## Phase details

- Phase 1a — `docs/feature-phases/1a-understand.md`
- Phase 1b — `docs/feature-phases/1b-frame.md`
- Phase 2 — `docs/feature-phases/2-split.md`
- Phase 3 — `docs/feature-phases/3-story-loop.md`
- Phase 4 — `docs/feature-phases/4-feature-review.md`
- Phase 5 — `docs/feature-phases/5-retro.md`

### Phase 3 — the per-story loop (fresh context each step)

For each story, run these in order, **each in a new session**, gating between:

- **`/story-prime`** — gather and persist the context the story needs: relevant
  files (via Graphifyy + LSP), the story's acceptance criteria, the slice of
  `feature.md` that applies. Writes a **primer** into the story file so the next
  step starts well-oriented without inheriting this session's context.
- **`/story-plan`** — from the primer, produce a concrete implementation plan in
  the story file. Gate: user approves the plan.
- **`/story-implement`** — implement strictly to the approved plan. Hooks (guards,
  lint) apply here. Gate: user approves the change.
- **`/story-review`** — review the implementation against the plan + acceptance
  criteria (reuses the `doctor`/review mindset). Gate: pass or send back.
- **`/story-learn`** — if the story surfaced a durable convention, pitfall, or
  gap, call **`/teach`** to persist it (and flag any new skill/hook worth adding).
  Closes the story. Gate: user confirms what was captured.

This is where Stage 2 **feeds back into Stage 1**: `/story-learn` (and the retro)
use `/teach` to keep the agent files and instructions improving as the codebase
evolves.

## State and artifacts

```text
.agentic/features/
  <feature-id>/
    understanding.md      # Phase 1a: problem, current behavior, edge cases, sources
    feature.md            # Phase 1b: solution approach + acceptance criteria
    state.json            # canonical phase, ordered story steps, gates, history
    stories/
      01-<slug>.md        # description, acceptance, primer, plan, review, learnings
      02-<slug>.md
    review.md             # Phase 4 output
    retro.md              # Phase 5 output

.agentic/local/
  active-feature.json     # this worktree's selected feature; gitignored
  readiness.json          # this developer's requirement probes; gitignored
  locks/                  # cross-platform mutation locks; gitignored
```

`state.json` (shape):

```json
{
  "$schema": "../../schemas/feature-state.schema.json",
  "version": 2,
  "revision": 8,
  "featureId": "<id>",
  "title": "…",
  "phase": "story_loop",
  "currentStory": "01-<slug>",
  "stories": [
    { "id": "01-<slug>", "step": "implement", "mode": "guided", "reviewAttempts": 0 }
  ],
  "gates": [
    { "name": "understand", "approvedAt": "…" },
    { "name": "frame", "approvedAt": "…" },
    { "name": "split", "approvedAt": "…" }
  ],
  "history": [],
  "createdAt": "…",
  "updatedAt": "…"
}
```

The controller enforces phases `understanding -> framing -> splitting ->
story_loop -> reviewing -> retrospective -> complete` and story steps `prime ->
plan -> implement -> review -> learn -> complete`, including review send-backs.
`nextCommand`, completion, and display status are derived rather than persisted.
Story Markdown never duplicates status.

Each step runs `feature-show`, notes the revision, writes its human artifact
first, then makes the controller transition last with `--expected-revision`.
Writes are atomic and serialized by local locks. Replays are idempotent; stale
revisions force a reread instead of an overwrite.

## Status / help behavior

Orientation works from **any point, in a fresh/cold session** — it reads state
from disk, not conversation history. This is the "where am I?" command, always
available:

- **`/feature`** with no argument, or **`/feature status`** — report where you
  are and the suggested next command.
- **`/feature help`** — explain the phases, the fresh-context rule, and the gates.

Because it's a skill, this is **auto-discovered from natural language** too — no
slash command needed. The `/feature` skill's `description` must include trigger
phrases like "where are we?", "what's the status?", "what's left?", "what should
I do next?", "resume the feature" so Copilot routes those to it (same mechanism as
`/teach`). The slash form is just the explicit path.

`/feature status` runs `feature-list` and `feature-show`, then prints, e.g.:

```text
Feature: search-filters  (phase: story loop)
Stories: 01-query-parser ✓  02-facet-ui ▶ (plan approved)  03-results-cache ·
Now: story 02, step implement.
Next: open a new session and run /story-implement
```

It handles every situation so the user is never stuck:

- **No feature in progress** → say so and suggest `/feature-understand` to start.
- **One feature in progress** → orient as above and select it locally if needed.
- **Multiple features in progress** → list them with their phase/next-step and ask
  which to resume in this worktree.

Feature directories themselves are the shared registry. There is no mutable
shared index. The selected feature is stored in gitignored
`.agentic/local/active-feature.json`, so developers and worktrees do not conflict.
Every step prints the controller-derived "Next" line.

## Completion

A feature is complete when every story has passed `/story-review` and been closed
by `/story-learn`, the feature review + manual-test guide (`review.md`) is done,
and the retrospective (`retro.md`) is recorded. `/feature` then prints a summary.

## Implementation status

All five phases are now detailed (see Phase details above). Resolved along the
way: feature-id scheme (1a), story sizing + ordering + dependencies (Phase 2,
S10), what story/feature review checks (Phases 3–4), manual-testing-guide format
(Phase 4), and primer location — appended to the story file (Phase 3).

All 11 Stage 2 skills and the v2 controller/schemas are bundled by the installer.
Automated tests cover legal/illegal transitions, stale revisions, idempotent
replay, review loops, local readiness, and feature completion. The revised flow
still needs end-to-end Copilot CLI and VS Code validation, including
interruption/recovery, autonomous delegation, remediation, hooks, and the
multi-repo boundary.
