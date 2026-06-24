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

## Input

Ask: **what language(s) should I set up LSP for?** (Pre-fill from detected
languages; the user confirms.)

## Graphifyy

Install (prefer `uv`, fall back to `pipx`/`pip`):

```bash
uv tool install graphifyy   # or: pipx install graphifyy / pip install graphifyy
graphify vscode install     # for VS Code Copilot Chat
graphify extract .          # build the graph from the repo root
```

Expected output under `graphify-out/` (`graph.json`, `graph.html`,
`GRAPH_REPORT.md`). Test:

```bash
graphify --version
graphify query "what is this repository about?"
```

## LSP

Install/verify the language server for each chosen language and test its version:

```
TypeScript/JS -> typescript-language-server (or built-in VS Code TS)
Python        -> pyright --version
Java          -> jdtls (or IDE extension check)
Go            -> gopls version
Rust          -> rust-analyzer --version
C/C++         -> clangd --version
C#            -> OmniSharp / C# language server (extension check)
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

`.agentic/setup/tooling-state.json`: selected languages; Graphifyy install command
+ version + graph path + query test result; selected LSP(s) + test command(s) +
result(s); new-session requested; overall status.

## Completion

Complete only when Graphifyy is installed, has generated `graphify-out/graph.json`,
and a query passed; the selected LSP is installed and tested; and state records
the results. A genuine environment block counts as `blocked`, not incomplete.
