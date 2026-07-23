---
name: setup-tooling
description: >-
  Set up and verify the tooling needed for agentic coding in this repo — a
  language server (LSP) for the chosen language(s) and Graphifyy code indexing.
  Use for "/setup-tooling", "set up tooling/LSP/Graphifyy", or the tooling step
  of /akmaestro-init. Not complete until the tools are installed AND tested.
---

# setup-tooling — LSP + Graphifyy

Mandatory topic. LSP is the floor; Graphifyy is required but blocked-not-failed
if the environment genuinely cannot install/run it.

## State protocol

Read `.agentic/STATE-PROTOCOL.md`. Run `setup-init` and `setup-status` through
the bundled controller. If this topic is not already `in_progress`, transition
`tooling` to `in_progress` with the revision just read. Never edit aggregate
setup state or local readiness directly.

## Input

Ask: **what language(s) should I set up LSP for?** (Pre-fill from detected
languages; the user confirms.)

## Graphifyy

The required actions are:

```bash
uv tool install graphifyy
graphify vscode install     # for VS Code Copilot Chat
graphify extract . --out .agentic/local/graphs/main
```

Do not run machine-changing snippets directly. First record confirmed install
and extraction argument arrays in environment requirements as described below,
run `readiness-check`, show each missing item and exact action, and ask for
confirmation. After confirmation, write that exact action object to a local file
and pass it to `remediation-run --input <file> --approved`. The controller
rejects actions not present in the committed requirements and never invokes a
shell. Rerun readiness after each action. The optional VS Code integration
command may instead use confirmed shell-free `action-check` because it is not a
cross-surface developer requirement.

Graphs are developer-local generated artifacts. Keep every graph under
`.agentic/local/graphs/`; never create `graphify-out/` in the main or a sibling
repository, and never commit graph output. Expected main output includes
`.agentic/local/graphs/main/graph.json`. Test:

```bash
graphify --version
graphify query "what is this repository about?" --graph .agentic/local/graphs/main/graph.json
```

Use the same `--graph <path>/graph.json` argument for each cached graph. Do not
fall back to moving or copying generated output into a source repository.

### Sibling repositories

If `AGENTS.md` declares modifiable or read-only sibling repositories, index their
source into the main repository's local graph cache:

```bash
graphify extract ../lib-b --out .agentic/local/graphs/lib-b
graphify extract ../vendor-c --out .agentic/local/graphs/vendor-c
```

Verify each produces `.agentic/local/graphs/<repo-id>/graph.json` and answers a
query using `--graph` with that exact path. The
source repository is read only during extraction. **Never write any file or
generated directory inside a read-only sibling repository.**

## LSP

Install/verify the language server for each chosen language and test its version.
Cover the languages of declared sibling repositories too, and make sure the LSP
can see them (in VS Code, add them to the workspace/folder set; in the CLI,
confirm the server resolves cross-repo references):

```
TypeScript/JS -> typescript-language-server (VS Code's built-in TS support may
                 supplement it but does not satisfy the CLI readiness probe)
Python        -> pyright --version
Java          -> jdtls with a non-interactive probe
Go            -> gopls version
Rust          -> rust-analyzer --version
C/C++         -> clangd --version
C#            -> OmniSharp / C# language server with a non-interactive probe
```

## Blocked-not-failed

If a step cannot be done for a real environment/policy reason (no registry
access, air-gapped, blocked install), record it as `blocked` with manual steps —
not failed/partial. LSP verified + Graphifyy blocked → tooling `blocked`, and
overall setup may still complete.

## New session

Restart only when the current process cannot observe a newly installed command or
the current Copilot surface requires it. Persist evidence and requirements first,
leave tooling `in_progress`, and use exactly this handoff:

```text
Next: open a new Copilot session at the repository root and run /akmaestro-init
```

Do not request a second restart merely because a graph was regenerated or VS
Code automatically reloaded configuration.

## State

Create local JSON evidence containing selected languages; Graphifyy install
command, version, graph paths, and query results; selected LSPs and probe results;
and whether a new session was requested. Write it with `evidence-write tooling`.
The resulting committed `.agentic/setup/tooling-state.json` has no independent
topic status.

Use exactly this evidence shape, replacing every value with actual results:

```json
{
  "languages": ["Python"],
  "graphify": {
    "status": "verified",
    "version": "<observed version>",
    "queryStatus": "passed",
    "graphPaths": [".agentic/local/graphs/main/graph.json"],
    "detail": "Version, extraction, and targeted query passed"
  },
  "lsps": [
    {"language": "Python", "toolId": "lsp-python", "status": "verified", "detail": "pyright --version passed"}
  ],
  "requirementsRevision": 0,
  "newSessionRequired": false,
  "blockers": []
}
```

For a blocked Graphifyy or LSP, use `blocked` in the matching result, keep the
expected local graph path, add the concise blocker string, and ensure the
requirements file carries the exact remediation action.

Also create a local JSON input containing `tools` and `artifacts`, then run
`requirements-write`. The committed
`.agentic/setup/environment-requirements.json` must require:

- `uv`, probed with `uv --version`;
- `graphify`, probed with `graphify --version`, with its confirmed install action;
- `graphify-query`, probed with a real `graphify query` in the main repo;
- one `lsp-<language>` tool per selected language, each with a non-interactive
  probe and confirmed install command;
- artifact id `graphify-graph` at
  `.agentic/local/graphs/main/graph.json`, with remediation action
  `graphify extract . --out .agentic/local/graphs/main`;
- required graph artifacts for declared sibling repositories, using their
  `.agentic/local/graphs/<repo-id>/graph.json` paths in the main repository, plus
  a required query probe that explicitly targets the cached graph. Extraction
  takes the sibling as a source argument and writes only under `.agentic/local/`.

Represent probe and remediation commands as argument arrays with an optional
repository-relative `cwd`, never as shell strings. This prevents command
separator injection. Never include credentials. Example input fragment:

```json
{
  "tools": [
    {"id":"uv","label":"uv","required":true,"probe":{"command":["uv","--version"]}},
    {"id":"graphify","label":"Graphifyy","required":true,"probe":{"command":["graphify","--version"]},"install":{"command":["uv","tool","install","graphifyy"]}},
    {"id":"graphify-query","label":"Graphifyy query","required":true,"probe":{"command":["graphify","query","what is this repository about?","--graph",".agentic/local/graphs/main/graph.json"],"cwd":".","timeoutSeconds":60}},
    {"id":"lsp-python","label":"Pyright","required":true,"probe":{"command":["pyright","--version"]},"install":{"command":["npm","install","--global","pyright"]}}
  ],
  "artifacts": [
    {"id":"graphify-graph","path":".agentic/local/graphs/main/graph.json","required":true,"remediation":{"command":["graphify","extract",".","--out",".agentic/local/graphs/main"],"cwd":"."}}
  ]
}
```

After writing requirements, run `readiness-check`. Exit `3` means the probes ran
but mandatory local items are missing; use its exact findings rather than
guessing.

## Completion

Complete only when Graphifyy is installed, has generated the required local graphs,
and a query passed; the selected LSP is installed and tested; and evidence plus
environment requirements are recorded. A genuine environment block counts as
`blocked`, not incomplete.

Write evidence and requirements first. Then transition `tooling` from
`in_progress` to `complete`, or to `blocked --reason <reason>` for a genuine
environment/policy blocker. Pass the latest aggregate `--expected-revision`.
Unfinished or failed-but-retryable work remains `in_progress`. Rerun
`setup-status` and return to the orchestrator. The only cross-session resume
command is `/akmaestro-init`.
