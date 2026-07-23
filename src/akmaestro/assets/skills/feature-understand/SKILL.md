---
name: feature-understand
description: >-
  Phase 1a of the feature flow (Analyst). Build a full, shared understanding of a
  feature/problem BEFORE solutioning — treating the ticket as incomplete. Use for
  "/feature-understand", "let's understand this feature/ticket", or the
  understand step of /feature. Gathers from code, Graphifyy, online, and
  (optionally) Jira/wiki; produces understanding.md.
allowed-tools:
  - shell
---

# feature-understand — Phase 1a (Analyst)

Persona: an investigator. Build a clear, shared understanding of the problem
before any solution is proposed. **Treat the originating ticket as incomplete by
default** and hunt for what's missing. No solutioning here.

## Entry

Fresh context. Read `.agentic/STATE-PROTOCOL.md`, run `setup-status`, then run
`readiness-check`. If required local items are missing, follow the confirmed
remediation procedure in `/feature`; never send a developer through
`/akmaestro-init`.

Run `feature-list`. If starting a feature, ask for a short title and optional
ticket id, derive `feature-id`, and call `feature-create`. If resuming among
multiple features, use the valid local selection or ask and call
`feature-select`. Run `feature-show`, require phase `understanding`, and note its
revision. Never create or update `index.json` and never edit `state.json`.

## Sources

- **Always:** the codebase + Graphifyy graph (affected/related areas), `AGENTS.md`,
  any links/files the user gives, and online sources you can fetch.
- **Declared sibling repositories** (`AGENTS.md` → Workspace & Dependencies): use
  their Graphifyy graphs for a high-level map; open a read-only sibling's code
  only when a specific behavior matters. Findings in read-only sibling
  repositories are **fixed constraints** — adapt to them, do not change them —
  and record them as such.
- **Jira/wiki (optional, credential-gated):** if `JIRA_TOKEN`/`JIRA_BASE_URL` or
  `WIKI_TOKEN`/`WIKI_BASE_URL` are set in the environment, pull the ticket/pages
  directly. Otherwise ask the user to paste the content or give a fetchable link,
  and note the gap. **Never read or write secrets into repo files** — only from
  the environment.

## Hunt for gaps (don't just summarize)

- synthesize all sources into one problem statement + current-behavior description;
- map affected areas/modules via Graphifyy + `AGENTS.md` — across this repo and
  the declared sibling repositories, marking each area modifiable or read-only;
- surface unstated assumptions, ambiguities, and **edge cases the ticket omitted**;
- list unknowns and ask the user targeted questions to close them.

Discovery checklist: assumptions; edge/negative cases; error/failure modes;
affected areas + their dependents; data/permissions; related repos;
non-functional constraints; what the ticket left out.

This is a collaboration (HITL) — think out loud and iterate with the user.

## Output: `understanding.md`

```md
# Understanding: <title>  (<feature-id>)

## Problem (as understood)
<what it is, who it's for>

## Current Behavior
<how the relevant area works today>

## Affected Areas
- `<path/module>`: <why involved>   (Graphifyy / AGENTS.md)

## Edge Cases & Ambiguities
- <case the ticket didn't cover>

## Open Questions
- <unknown still needing an answer>

## Sources Consulted
- <ticket / page / file / url — fetched or pasted>
```

## Gate (hard stop — understand first)

Iterate until the user confirms it reflects reality and open questions are
answered or explicitly deferred. Write `understanding.md` first. On approval,
call `feature-advance --id <feature-id> --gate understand --expected-revision
<revision>`. The controller moves the phase to `framing`; report its derived
`/feature-frame` command. Tell the user to open a new session and run it, or, if
this session is still light, offer to continue here.

## Completion

`understanding.md` exists with problem, current behavior, affected areas, edge
cases/ambiguities, open questions, and sources; the user confirmed it; state
records the approved gate. A stale revision is a stop-and-reread condition, never
a reason to rewrite state manually.
