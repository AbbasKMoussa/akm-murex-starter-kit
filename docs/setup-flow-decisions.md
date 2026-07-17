# Setup Flow Decisions

Date: 2026-06-19
Last updated: 2026-07-14

## Context

AKMaestro is a Murex-internal kit that lets teams add agentic coding support to
existing repositories. Stage 1 configures the repository; Stage 2 guides feature
development from understanding through implementation, review, and learning.

## Desired Setup Outcome

The target experience is:

```text
Team lead installs AKMaestro and opens Copilot at the repository root.
> Let's run the initialization flow.

The lead completes the guided flow and commits the result.
Developers pull it and run /feature directly.
/feature verifies and offers to remediate each developer's local tools.
```

The flow may span multiple sessions, so setup state must be persisted on disk.

## Decisions So Far

1. The setup flow must be dynamic.

   It should inspect the repository and ask the user questions before deciding what to install or generate.

2. The bootstrap is a one-time installer (decided).

   An uninitialized repository cannot know what "initialization flow" means, so something must lay down the flow first. That "something" is a single, versioned, idempotent installer rather than a magic global understanding. After it runs once, everything else is conversational.

   - Distribution: a Python CLI run via `uvx akmaestro init`. The package may be
     installed by other Python mechanisms, but `uv` remains a workflow runtime
     prerequisite on every developer machine.
   - Source of truth: an internal git repo, intended for publication to the
     internal Python registry (PyPI / Artifactory).
   - `akmaestro init` is a non-destructive asset installer: it installs all 18
     skills, optional hooks, schemas, the state protocol/controller, and
     bootstrap pointers. Detection and interview logic runs later in the skills.
   - `akmaestro update` upgrades kit-owned files using the SHA-256 manifest while
     preserving customized files.

3. The model is "installer + repo-local assets" (BMAD-style).

   The installer starts the flow. The initialized repository receives its own
   instructions, skills, optional hooks, templates, and state files so future
   sessions are self-contained and resumable. This mirrors the BMAD method's
   installed-assets approach.

4. The flow should persist shared setup state and separate local state.

   State location:

   ```text
   .agentic/
     setup/
       initialization-state.json
       answers.json
       detected-repo.json
       environment-requirements.json
       install-log.md
     local/                    # gitignored active feature, readiness, locks
   ```

5. Generated files should be repo-specific.

   Agent instruction files should be generated from both detected facts and user answers, not copied unchanged from generic templates.

6. Never overwrite without confirmation.

   No separate `install-plan.md` artifact is required. The agent may install
   directly, but it must never overwrite or weaken an existing instruction,
   skill, or hook file without showing what it would change and getting
   confirmation. New files can be created freely; existing customization is
   protected.

7. Hooks are optional but installed by default (opt-out).

   Hooks are a portable standard configured in `.github/hooks/*.json` (same format across Copilot CLI, the cloud agent, and VS Code, and Claude-compatible). They are GA on Copilot CLI (Feb 2026) and preview on VS Code, so the kit must never depend on them and must degrade gracefully where org policy disables them. The kit installs a recommended set — restricted-path guard, dangerous-command guard, audit log, lint-on-edit — which the user can decline per hook or entirely. `preToolUse` is fail-closed, so guard scripts must default to `allow` on any uncertainty and only deny on a positive match. The fourth initialization topic; see `docs/init-topics/hooks.md`.

8. The first agreed initialization topic is instruction files.

   The topic has two phases:

   - root instruction setup through `/setup-instructions`;
   - complex module setup through `/setup-instructions module <path>` or
     `/setup-instructions module all`.

   See `docs/init-topics/instruction-files.md`.

9. The second agreed initialization topic is tooling.

   The user runs `/setup-tooling`. The flow asks which language(s) to set up LSP
   for, then installs/configures and tests both LSP and Graphifyy. This topic is
   complete when both work, or `blocked` with a genuine environmental reason and
   recorded manual steps.

   See `docs/init-topics/tooling.md`.

10. Target surfaces are GitHub Copilot only: VS Code and Copilot CLI (decided).

    Both surfaces read the same `.github/` asset set, so the kit generates one set of files, not two dialects. No other agentic tools are targeted for now.

11. Agent skills are the kit's universal delivery and trigger mechanism (decided, supersedes the earlier prompt/agent split).

    GitHub agent skills are an open standard that works identically across VS Code Copilot, Copilot CLI, and the cloud agent, so there is no longer a trigger asymmetry to work around. A skill is a folder under `.github/skills/<name>/` containing `SKILL.md` (YAML frontmatter + Markdown) plus optional bundled scripts/templates/resources.

    - Frontmatter: `name` (required, lowercase + hyphens), `description` (required — what it does and when to use it), optional `license`, optional `allowed-tools` (e.g. `shell`).
    - Invocation: auto-discovered from the description, or `/<name>` in the slash menu — in both surfaces.
    - The kit's own flows ship as skills (e.g. `init`), so `/init` and natural language both work everywhere. This replaces the previously proposed `.github/prompts/init.prompt.md` + `.github/agents/init.agent.md` pair.

    Skill format and locations are verified in "GitHub Copilot Agent Skills" below.

12. Skills are the third initialization topic (decided).

    The CLI bootstrap installs the complete 18-skill set up front: seven Stage 1
    skills/helpers and eleven Stage 2 skills. `/setup-skills` validates that fixed
    bundled set and preserves any additional team-owned skills; it does not defer
    Stage 2 installation or ask the user to choose a subset.

13. The setup flow is hybrid: guided + à la carte (decided).

    `/init` drives the topics in mandatory order and is resumable; each topic also
    runs standalone (`/setup-instructions`, `/setup-tooling`, `/setup-skills`,
    `/setup-hooks`). Both share the same per-topic logic and state. See
    `docs/setup-flow.md`.

14. Existing files use section-aware merge + confirm (decided).

    When a customization file already exists, the flow parses it into sections,
    merges new content into the matching section, shows the diff, and applies only
    after confirmation. It never deletes or weakens existing content; genuine
    conflicts are surfaced for the user. New files are created directly.

15. Mandatory profile: instructions + tooling + skills; hooks optional (decided).

    Setup counts as complete when the instruction-files, tooling, and skills
    topics are complete or carry a genuine documented `blocked` outcome. Hooks
    are recommended but never block completion and may be skipped or disabled.

16. Completion gate: per-topic criteria must pass (decided).

    Each mandatory topic must meet its documented completion criteria — required
    files exist AND tools/guards are verified — before `init` reports complete.

17. Stage 1 = per-topic skills + an `init` orchestrator; verb is `setup-<topic>`
    (decided).

    Stage 1 ships as five flow-skills — `init` (guided orchestrator, also handles
    `init status`/`init help`) plus `setup-instructions`, `setup-tooling`,
    `setup-skills`, `setup-hooks` — alongside `teach` and `doctor`. Mirrors how
    `teach`/`doctor` are built as standalone auto-discoverable skills. This
    replaces the earlier mixed `init X` / `setup X` phrasing in the topic docs.

18. Mandatory topics get a blocked-not-failed escape (decided).

    A mandatory step that genuinely cannot be done in the environment (air-gapped,
    no registry, policy) is recorded as `blocked`, with manual-completion steps,
    and overall setup may still complete. Applies especially to Graphifyy; LSP is
    the tooling floor. `blocked` needs a real environment reason — not a skipped
    or failed step.

19. The instructions gate is satisfied by root files only (decided).

    Root `AGENTS.md` + `copilot-instructions.md` + `tests.instructions.md` satisfy
    the mandatory gate. Complex-module `AGENTS.md` files are tracked and
    recommended but pending modules are warnings, not blockers.

20. Detection/interview/generation live in skills; state logic is deterministic
    code (revised decision).

    `uvx akmaestro init` copies assets and prints the line that starts the flow.
    Detection, interview, generation, and section merge are done by skills.
    Legal transitions, validation, locking, revision checks, and atomic writes
    are handled by the bundled standard-library controller. MCP servers remain
    out of scope for Stage 1.

21. Execution readiness is part of "ready for agentic coding" (decided).

    Instructions capture not just build/test but also how to **run/serve** the app
    and how to **verify a change**. Setup runs a **smoke-verify** (build + test
    once) so the agent operates on commands proven to work; smoke-verify is
    blocked-not-failed. This serves both Stage 2 and ad-hoc dev+agent use.

22. Setup generates a committed team-discoverability guide (decided).

    On completion, `init` writes `.github/AGENTIC.md` listing installed skills
    (and how to invoke them), active hooks, instruction-file locations, and
    run/verify commands — so every teammate who clones the repo understands the
    initialized workflow. Regenerated on re-run; linked from `AGENTS.md`.

23. `/init` is team-lead-owned repository initialization (decided).

    The lead runs the installer and `/init`, then commits the shared output.
    Other developers never rerun `/init` for workstation setup; they begin with
    `/feature` after pulling the initialization commit.

24. State uses a hybrid v2 model with a bundled controller (decided).

    Committed state contains setup decisions/evidence, environment requirements,
    and feature/story progress. `.agentic/local/` contains readiness, active
    feature selection, locks, and temporary files and is always gitignored.
    Draft 2020-12 JSON Schemas document the contracts. Controller-owned JSON is
    updated atomically, guarded by revisions and cross-platform directory locks.
    Derived navigation and completion fields are not persisted.

25. `/feature` owns per-developer readiness (decided).

    Every feature entry verifies the committed `/init` result and probes local
    `uv`, Graphifyy version/query probes, selected LSPs, and graph artifacts. Missing requirements
    block feature mutations. `/feature` shows structured argument-array
    remediation actions and executes only after user confirmation. The readiness
    result and active feature selection stay local. There is no v1 migration
    because the state model was not shipped before v2.

The integrated Stage 1 spec (orchestrator, bootstrap, detection, state schema,
merge policy, unified status/help) lives in `docs/setup-flow.md`. The four topic
docs hold the per-topic depth.

## GitHub Copilot CLI Constraints

Verified from GitHub docs (2026-06):

- Copilot CLI reads `AGENTS.md` and `.github/copilot-instructions.md` (both used if present); also `CLAUDE.md` / `GEMINI.md` at repo root, and a user-level `~/.copilot/copilot-instructions.md`.
- Custom agents are `*.agent.md` Markdown files in `.github/agents/` (repo) or `~/.copilot/agents/` (user); invoked via the `/agent` slash command, the `--agent <name>` CLI flag, or natural-language inference from the agent description.
- **Copilot CLI has no support for user-defined slash commands or reusable prompt files** (e.g. `.github/prompts/*.prompt.md`). This is an open feature request. Therefore the CLI trigger must be a custom agent or plain natural language, not a prompt file.

Sources:

- https://docs.github.com/en/copilot/how-tos/copilot-cli/customize-copilot/add-custom-instructions
- https://docs.github.com/en/copilot/how-tos/copilot-cli/customize-copilot/create-custom-agents-for-cli
- https://github.com/github/copilot-cli/issues/618

## GitHub Copilot Agent Skills

Verified from GitHub and VS Code docs (2026-06):

- A skill is a folder containing a `SKILL.md` file (YAML frontmatter + Markdown instructions) plus any bundled scripts/templates/resources, referenced by relative path.
- Required frontmatter: `name` (unique, lowercase letters/numbers/hyphens only) and `description` (what the skill does and when to use it). Optional: `license`, `allowed-tools` (e.g. `shell` to pre-approve tool use).
- Repo-level locations: `.github/skills/`, `.claude/skills/`, `.agents/skills/`. User-level: `~/.copilot/skills/`, `~/.claude/skills/`, `~/.agents/skills/`. The kit uses `.github/skills/` (repo) and may use `~/.copilot/skills/` (user-level bootstrap).
- Discovery/invocation: auto-discovered from the description when relevant, or invoked explicitly as `/<name>`. This works in VS Code Copilot, Copilot CLI, and the cloud agent — it is an open, portable standard.

Sources:

- https://docs.github.com/en/copilot/how-tos/copilot-cli/customize-copilot/add-skills
- https://code.visualstudio.com/docs/agent-customization/agent-skills

## Candidate Installed Assets

The initialized target repository may contain:

```text
.github/
  copilot-instructions.md   # short pointer to AGENTS.md
  AGENTIC.md                # committed team-discoverability guide (decision 22)
  instructions/             # path-scoped *.instructions.md
  skills/                   # all 18 Stage 1 + Stage 2 skills
  hooks/                    # hooks.json + scripts (optional topic)

AGENTS.md                   # main source of truth

<complex-module>/AGENTS.md  # nested, for complex modules

.agentic/
  bin/                      # bundled deterministic state controller
  schemas/                  # versioned Draft 2020-12 state contracts
  setup/                    # committed repository setup state/evidence
  hooks/                    # machine-readable hook config data
  local/                    # developer/worktree state, gitignored
  audit/                    # local, gitignored audit trail
  features/                 # Stage 2
  stories/                  # Stage 2
  decisions/                # general / Stage 2
```

The exact set depends on repository needs, team preference, and tool support;
the full Stage 1 layout and asset mapping are in `docs/setup-flow.md`.

## Setup Flow Shape

> Superseded by the integrated spec in `docs/setup-flow.md`. Kept here as the
> original outline.

1. Preflight

   Detect stable repo facts, customization files, language/frameworks, package
   managers, test/build commands, CI, and monorepo shape. Keep branch, dirty
   status, PATH, and tool availability local.

2. Interview

   Ask targeted questions about team, repo type, strictness, testing expectations, review expectations, allowed tools, hooks, and instruction-file preferences.

3. Persist

   Write stable facts, answers, and controller-owned progress to
   `.agentic/setup/`; write workstation facts to `.agentic/local/`.

4. Install

   Create or merge skills, hooks, instructions, templates, and state folders.
   New files are created directly. Before overwriting or weakening any existing
   customization file, show what would change and get confirmation (decision 6).

5. Validate

   Check that required files exist, generated files are coherent, and configured commands are available or documented.

6. Handoff

   Produce a setup summary explaining what was installed and how to start the feature flow.

## Resolved Questions

The minimum profile, merge policy, validation gate, flow shape, bootstrap skill
set, and Stage 2 design are resolved in the decisions above and below. Remaining
work is workflow improvement and cross-surface validation, not architecture
selection.

## Stage 2: Feature Flow Decisions

S1. Stage 2 is a repeatable per-feature flow, BMAD-style but leaner, delivered as
    skills + `.agentic/features/<id>/` state in the same kit. Assumes Stage 1 is
    complete. See `docs/feature-flow.md`.

S2. Working model: fresh context per step. Each step runs in its own Copilot
    session; on finishing it tells the user to open a new context and run the next
    command. Continuity is carried by on-disk state + artifacts, not conversation
    history.

S3. A `feature status` / `feature help` command always reports where you are and
    the controller-derived next command. Feature directories are the registry;
    a worktree-local pointer selects among multiple open features.

S4. Gate every phase boundary and every guided story-step boundary. Autonomous
    mode removes only the internal Phase 3 story-step gates; story entry/exit and
    all other phase boundaries remain hard stops requiring explicit approval.

S5. Phases: Phase 1 is two gated steps — Understand → Frame — then Split →
    per-story loop (Prime → Plan → Implement → Review → Learn) → Feature review →
    Retrospective. Per-step skills so each runs in its own context. Understand
    comes first and treats the originating ticket as incomplete; Frame adapts to
    whether the dev already has an idea (capture+pressure-test) or needs
    brainstorming.

S6. The loop feeds Stage 1: `/story-learn` and `/feature-retro` call `/teach` to
    persist new conventions/pitfalls and flag new skills/hooks.

S7. Each step is a curated specialist, carried by the skill (not Copilot custom
    agents). Each step's `SKILL.md` embeds a named role persona plus
    templates/checklists (BMAD role + dependencies); fresh-context-per-step makes
    each step a focused specialist. We do NOT map 1:1 to BMAD's roster — a leaner
    set (Framer, Planner, Researcher, Architect, Implementer, Reviewer,
    Librarian, Retro facilitator) merges roles for max value at least complexity.
    Skills keep cross-surface uniformity (decision 11) with no quality loss —
    quality comes from curation + clean context, not the primitive.

S8. Sources for understanding: codebase + Graphifyy + fetchable online sources
    always; Jira/wiki are optional and credential-gated via a user-provided PAT +
    base URL (environment variables / gitignored config) — otherwise the user
    pastes the content. PATs are never committed. Deeper Jira/wiki integration may
    later be an MCP server (revisits the Stage-1 MCP-out-of-scope decision).

S9. Human-in-the-loop throughout (working-model principle 4). Steps are
    collaborations, not agent monologues — specialists think out loud, ask, and
    iterate during the step, and meet the user where they are: take+accept,
    take+enhance, or push back with a reason and propose an alternative; only
    propose from scratch when the user has nothing. Applies especially to Frame
    (the dev's idea) and Split (the dev's story breakdown).

S10. Stories are right-sized — not too small. Bias toward fewer, larger,
     user-meaningful vertical slices; split only when a story is too big for one
     Phase 3 loop. Story-level, never a task list.

S11. Story review and feature review are distinct personas (corrects an earlier
     "reuse the Reviewer" shortcut). Phase 3 = close-up code Reviewer (this slice
     vs its plan); Phase 4 = QA / Integration reviewer at feature altitude
     (cross-story integration, whole-feature AC, manual-verification guide).
     Distinct framing + checklists stop the feature review from drifting into
     re-reviewing story internals.

S12. Two modes, scoped to the Phase 3 per-story loop ONLY. The loop runs either
     autonomous (the five steps back-to-back in one session, ungated) or guided
     (each step gated + fresh context). Phases 1, 2, 4, 5 are always gated
     regardless of mode (S4 still holds for them). Mode is per-story, switchable,
     shown in `feature status`; autonomous removes only the inside-the-loop stops
     and does not auto-advance to the next story. Hooks still apply in both modes.

Implementation and remaining verification status are recorded at the end of
`docs/feature-flow.md`.
