# Setup Flow Decisions

Date: 2026-06-19

## Context

We are designing a Murex starter kit that lets teams add agentic coding support to existing repositories. The first major flow is the setup/initialization flow. A later flow will guide feature development from idea to feature spec to stories to write/implement/review cycles.

## Desired Setup Outcome

The target experience is:

```text
Open Copilot at the root of a repo.
> Let's run the initialization flow.

The flow runs through guided questions and setup steps.
Initialization completes.
The repo now supports agentic coding.
```

The flow may span multiple sessions, so setup state must be persisted on disk.

## Decisions So Far

1. The setup flow must be dynamic.

   It should inspect the repository and ask the user questions before deciding what to install or generate.

2. The bootstrap is a one-time installer (decided).

   An uninitialized repository cannot know what "initialization flow" means, so something must lay down the flow first. That "something" is a single, versioned, idempotent installer rather than a magic global understanding. After it runs once, everything else is conversational.

   - Distribution: a Python CLI run via `uvx murex-starter-kit init` (also installable with `pipx`/`pip`). This matches the existing `uv tool install graphifyy` idiom in the tooling topic.
   - Source of truth: an internal git repo, published to the internal Python registry (PyPI / Artifactory).
   - The installer runs preflight detection, drives the interview, and lays down the repo-local Layer-1 assets. It is idempotent and re-runnable to upgrade.

3. The model is "installer + repo-local assets" (BMAD-style).

   The installer starts the flow. The initialized repository receives its own instructions, prompts, agents, templates, and state files so future sessions are self-contained and resumable. This mirrors the BMAD method's installed-assets approach.

4. The flow should persist setup state.

   State location:

   ```text
   .agentic/
     setup/
       initialization-state.json
       answers.json
       detected-repo.json
       install-log.md
   ```

5. Generated files should be repo-specific.

   Agent instruction files should be generated from both detected facts and user answers, not copied unchanged from generic templates.

6. Never overwrite without confirmation.

   No separate `install-plan.md` artifact is required. The agent may install directly, but it must never overwrite or weaken an existing instruction, prompt, agent, or hook file without showing what it would change and getting confirmation. New files can be created freely; existing customization is protected.

7. Hooks are optional but installed by default (opt-out).

   Hooks are a portable standard configured in `.github/hooks/*.json` (same format across Copilot CLI, the cloud agent, and VS Code, and Claude-compatible). They are GA on Copilot CLI (Feb 2026) and preview on VS Code, so the kit must never depend on them and must degrade gracefully where org policy disables them. The kit installs a recommended set — restricted-path guard, dangerous-command guard, audit log, lint-on-edit — which the user can decline per hook or entirely. `preToolUse` is fail-closed, so guard scripts must default to `allow` on any uncertainty and only deny on a positive match. The fourth initialization topic; see `docs/init-topics/hooks.md`.

8. The first agreed initialization topic is instruction files.

   The topic has two phases:

   - root instruction setup through `init instructions`;
   - complex module instruction setup through `init module <path>` or `init module all`.

   See `docs/init-topics/instruction-files.md`.

9. The second agreed initialization topic is tooling.

   The user runs `setup tooling`. The flow asks which language(s) to set up LSP for, then installs/configures and tests both LSP and Graphifyy. This topic is not complete unless both are tested and working.

   See `docs/init-topics/tooling.md`.

10. Target surfaces are GitHub Copilot only: VS Code and Copilot CLI (decided).

    Both surfaces read the same `.github/` asset set, so the kit generates one set of files, not two dialects. No other agentic tools are targeted for now.

11. Agent skills are the kit's universal delivery and trigger mechanism (decided, supersedes the earlier prompt/agent split).

    GitHub agent skills are an open standard that works identically across VS Code Copilot, Copilot CLI, and the cloud agent, so there is no longer a trigger asymmetry to work around. A skill is a folder under `.github/skills/<name>/` containing `SKILL.md` (YAML frontmatter + Markdown) plus optional bundled scripts/templates/resources.

    - Frontmatter: `name` (required, lowercase + hyphens), `description` (required — what it does and when to use it), optional `license`, optional `allowed-tools` (e.g. `shell`).
    - Invocation: auto-discovered from the description, or `/<name>` in the slash menu — in both surfaces.
    - The kit's own flows ship as skills (e.g. `init`), so `/init` and natural language both work everywhere. This replaces the previously proposed `.github/prompts/init.prompt.md` + `.github/agents/init.agent.md` pair.

    Skill format and locations are verified in "GitHub Copilot Agent Skills" below.

12. Skills are the third initialization topic (in progress).

    The topic covers two things: (a) delivering the kit's own flows as agent skills, and (b) installing a curated catalog of reusable skills into the team's `.github/skills/` for daily use. The specific catalog is being designed collaboratively with the user, not taken from a fixed list. Bootstrap option under consideration: a user-level skill in `~/.copilot/skills/` so "run the initialization flow" works in any repo with no per-repo command.

13. The setup flow is hybrid: guided + à la carte (decided).

    `/init` drives the topics in mandatory order and is resumable; each topic also
    runs standalone (`init instructions`, `setup tooling`, `setup skills`,
    `setup hooks`). Both share the same per-topic logic and state. See
    `docs/setup-flow.md`.

14. Existing files use section-aware merge + confirm (decided).

    When a customization file already exists, the flow parses it into sections,
    merges new content into the matching section, shows the diff, and applies only
    after confirmation. It never deletes or weakens existing content; genuine
    conflicts are surfaced for the user. New files are created directly.

15. Mandatory profile: instructions + tooling + skills; hooks optional (decided).

    Setup counts as complete when the instruction-files, tooling, and skills
    topics are complete. Hooks are recommended (install-by-default) but never block
    completion and may be disabled by policy.

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

20. The installer is a thin file-dropper; logic lives in skills (decided).

    `uvx murex-starter-kit init` only copies static assets and prints the line
    that starts the flow. Detection, interview, generation, and section-merge are
    done by the skills at runtime. See the asset mapping in `docs/setup-flow.md`.
    MCP servers are explicitly out of scope for Stage 1.

21. Execution readiness is part of "ready for agentic coding" (decided).

    Instructions capture not just build/test but also how to **run/serve** the app
    and how to **verify a change**. Setup runs a **smoke-verify** (build + test
    once) so the agent operates on commands proven to work; smoke-verify is
    blocked-not-failed. This serves both Stage 2 and ad-hoc dev+agent use.

22. Setup generates a committed team-discoverability guide (decided).

    On completion, `init` writes `.github/AGENTIC.md` listing installed skills
    (and how to invoke them), active hooks, instruction-file locations, and
    run/verify commands — so every teammate who clones the repo is ready, not just
    the developer who ran setup. Regenerated on re-run; linked from `AGENTS.md`.

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
  skills/                   # init, setup-*, teach, doctor, + catalog skills
  hooks/                    # hooks.json + scripts (optional topic)

AGENTS.md                   # main source of truth

<complex-module>/AGENTS.md  # nested, for complex modules

.agentic/
  setup/                    # state files (Stage 1)
  hooks/                    # machine-readable hook config data
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

   Detect repo facts, existing customization files, git state, language/frameworks, package managers, test/build commands, CI, and monorepo shape.

2. Interview

   Ask targeted questions about team, repo type, strictness, testing expectations, review expectations, allowed tools, hooks, and instruction-file preferences.

3. Persist

   Write detected facts, answers, and current step to `.agentic/setup/`.

4. Install

   Create or merge prompts, agents, hooks, instructions, templates, and state folders. New files are created directly. Before overwriting or weakening any existing customization file, show what would change and get confirmation (see decision 6).

5. Validate

   Check that required files exist, generated files are coherent, and configured commands are available or documented.

6. Handoff

   Produce a setup summary explaining what was installed and how to start the feature flow.

## Open Questions

Resolved: min profile (decision 15), merge policy (decision 14), validation gate
(decision 16), flow shape (decision 13).

- What should the Stage 2 feature flow look like in detail — phases, per-phase
  skills, state under `.agentic/features/` and `.agentic/stories/`, and how its
  "update AI infra" steps feed back into Stage 1 assets (the `teach` skill)?
