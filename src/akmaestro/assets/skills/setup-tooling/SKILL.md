---
name: setup-tooling
description: >-
  Set up and verify the tooling needed for agentic coding in this repo — a
  language server (LSP) for the chosen language(s) and Graphifyy code indexing.
  Use for "/setup-tooling", "set up tooling/LSP/Graphifyy", or the tooling step
  of /init. Not complete until the tools are installed AND tested.
allowed-tools:
  - shell
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

Install with the repository-standard `uv` runtime:

```bash
uv tool install graphifyy
graphify vscode install     # for VS Code Copilot Chat
graphify extract .          # build the graph from the repo root
```

Expected output under `graphify-out/` (`graph.json`, `graph.html`,
`GRAPH_REPORT.md`). Test:

```bash
graphify --version
graphify query "what is this repository about?"
```

### Sibling repositories

If `AGENTS.md` declares modifiable or read-only sibling repositories, index them
too — reading across the workspace is the whole point of declaring them:

```bash
(cd ../lib-b && graphify extract .)      # modifiable sibling repository
(cd ../vendor-c && graphify extract .)   # read-only sibling repository
```

Verify each produces its own `graphify-out/graph.json` and answers a query.
Read-only sibling repositories are indexed exactly like modifiable ones — the
boundary guard, not the tooling, is what prevents edits there.

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

After installing tooling, ask the user to open a new Copilot session at the repo
root so new PATH entries / VS Code config are picked up, then re-run
`/setup-tooling` or `init status` to confirm.

## State

Create local JSON evidence containing selected languages; Graphifyy install
command, version, graph paths, and query results; selected LSPs and probe results;
and whether a new session was requested. Write it with `evidence-write tooling`.
The resulting committed `.agentic/setup/tooling-state.json` has no independent
topic status.

Also create a local JSON input containing `tools` and `artifacts`, then run
`requirements-write`. The committed
`.agentic/setup/environment-requirements.json` must require:

- `uv`, probed with `uv --version`;
- `graphify`, probed with `graphify --version`, with its confirmed install action;
- `graphify-query`, probed with a real `graphify query` in the main repo;
- one `lsp-<language>` tool per selected language, each with a non-interactive
  probe and confirmed install command;
- artifact id `graphify-graph` at `graphify-out/graph.json`, with remediation
  action `graphify extract .`;
- required graph artifacts for declared sibling repositories, using their
  repository-relative `../<sibling>/graphify-out/graph.json` paths, plus a
  required query probe whose `cwd` is that sibling path.

Represent probe and remediation commands as argument arrays with an optional
repository-relative `cwd`, never as shell strings. This prevents command
separator injection. Never include credentials. Example input fragment:

```json
{
  "tools": [
    {"id":"uv","label":"uv","required":true,"probe":{"command":["uv","--version"]}},
    {"id":"graphify","label":"Graphifyy","required":true,"probe":{"command":["graphify","--version"]},"install":{"command":["uv","tool","install","graphifyy"]}},
    {"id":"graphify-query","label":"Graphifyy query","required":true,"probe":{"command":["graphify","query","what is this repository about?"],"cwd":".","timeoutSeconds":60}},
    {"id":"lsp-python","label":"Pyright","required":true,"probe":{"command":["pyright","--version"]},"install":{"command":["npm","install","--global","pyright"]}}
  ],
  "artifacts": [
    {"id":"graphify-graph","path":"graphify-out/graph.json","required":true,"remediation":{"command":["graphify","extract","."],"cwd":"."}}
  ]
}
```

After writing requirements, run `readiness-check`. Exit `3` means the probes ran
but mandatory local items are missing; use its exact findings rather than
guessing.

## Completion

Complete only when Graphifyy is installed, has generated `graphify-out/graph.json`,
and a query passed; the selected LSP is installed and tested; and evidence plus
environment requirements are recorded. A genuine environment block counts as
`blocked`, not incomplete.

Write evidence and requirements first. Then transition `tooling` from
`in_progress` to `complete`, or to `blocked --reason <reason>` for a genuine
environment/policy blocker. Pass the latest aggregate `--expected-revision`.
Unfinished or failed-but-retryable work remains `in_progress`. Rerun
`setup-status` and report its derived next command.
