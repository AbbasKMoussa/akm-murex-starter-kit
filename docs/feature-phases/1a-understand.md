# Feature Phase 1a: Understand

Skill: `/feature-understand` · Persona: **Analyst** (investigator).

The first step of the feature flow. Build a full, shared understanding of the
problem **before** any solutioning. The originating ticket is treated as
**incomplete by default** — the Analyst hunts for what's missing.

## Goal

A clear `understanding.md` that captures what the feature/problem actually is,
the current behavior, the areas of the codebase it touches, the edge cases and
ambiguities, and the open questions — agreed with the user. No solution yet.

## Entry and identity

Invoked via `/feature` or directly as `/feature-understand`, in a fresh context.
If starting a new feature, ask for a short **title** (and optional ticket id),
derive `feature-id`, and use controller `feature-create`. If resuming, use
`feature-list`/`feature-show`, require `understanding`, and note the revision.
Every entry checks committed initialization and local readiness first.

## Sources

Gather from whatever is available; record what was consulted.

- **Always:** the codebase and the Graphifyy graph (to find affected areas and
  related code), plus any links/files the user provides and online sources the
  agent can fetch.
- **Jira / wiki (optional, credential-gated):** if the user has configured access
  — a Personal Access Token + base URL via environment variables
  (e.g. `JIRA_TOKEN`/`JIRA_BASE_URL`, `WIKI_TOKEN`/`WIKI_BASE_URL`) — the Analyst
  pulls the ticket/pages directly. Otherwise it asks the user to paste the content
  or give a fetchable link, and notes the gap. **PATs are never committed**: read
  them from the environment (or a gitignored config); never write them into repo
  files. (Deeper integration could later be an MCP server.)

## The Analyst hunts for gaps

It does not just summarize the ticket. It actively:

- synthesizes all sources into a single problem statement and current-behavior
  description;
- maps affected areas/modules via Graphifyy and `AGENTS.md`;
- surfaces **unstated assumptions, ambiguities, and edge cases** the ticket
  didn't cover;
- lists what's still unknown and asks the user targeted clarifying questions to
  close those gaps.

## Output: `understanding.md`

```md
# Understanding: <title>  (<feature-id>)

## Problem (as understood)
<what the feature/problem actually is, who it's for>

## Current Behavior
<how things work today in the relevant area>

## Affected Areas
- `<path/module>`: <why it's involved>  (from Graphifyy / AGENTS.md)

## Edge Cases & Ambiguities
- <edge case / ambiguity the ticket didn't cover>

## Open Questions
- <unknown still needing an answer>

## Sources Consulted
- <ticket / wiki page / file / url, and whether fetched or pasted>
```

## Bundled resources

- `understanding.template.md` (above).
- `discovery-checklist.md` — the hunt checklist: assumptions, edge/negative cases,
  error/failure modes, affected areas + dependents, data/permissions, related
  repos, non-functional constraints, what the ticket omitted.

## Gate (hard stop — "understand first")

Present `understanding.md` and iterate until the user confirms it reflects reality
and the open questions are either answered or explicitly deferred. Nothing
proceeds to framing without this. On approval:

- write `understanding.md`, then call controller gate `understand` with the
  expected revision (which moves the phase to `framing`);
- tell the user: **open a new session and run `/feature-frame`**.

## State

Controller-owned `state.json`: phase `understanding` -> `framing`, approved
`understand` gate, revision/history. `/feature-frame` is derived, not stored.

## Completion criteria

Complete when `understanding.md` exists with problem, current behavior, affected
areas, edge cases/ambiguities, open questions, and sources consulted; the user has
confirmed it; and the controller records the approved gate.
