# Initialization Topic: Tooling

This topic defines the second setup step for a target repository.

## Goal

Set up and verify the repo tooling needed for agentic coding:

- LSP for the selected project language(s);
- code indexing through Graphifyy.

The step should stay simple. Ask the user only what language(s) they want LSP configured for.

## Command

```text
/setup-tooling
```

(Also reachable through the guided `/init`. See `docs/setup-flow.md` for the
command model.)

## User Input

Ask:

```text
What language(s) should I set up LSP for?
```

Then continue with setup.

## Graphifyy Setup

Graphifyy is installed from the official `graphifyy` package. The CLI command is `graphify`.

Preferred install:

```bash
uv tool install graphifyy
```

Fallbacks:

```bash
pipx install graphifyy
pip install graphifyy
```

For VS Code Copilot Chat:

```bash
graphify vscode install
```

Build the repo graph from the repository root:

```bash
graphify extract .
```

If `AGENTS.md` declares workspace dependencies (editable or read-only), build a
graph for each of them too — high-level understanding of a read-only dependency
is exactly what its graph provides, so the agent only opens its code when a
specific behavior matters:

```bash
(cd ../lib-b && graphify extract .)
(cd ../vendor-c && graphify extract .)
```

Expected output:

```text
graphify-out/
  graph.html
  GRAPH_REPORT.md
  graph.json
```

Test Graphifyy:

```bash
graphify --version
graphify query "what is this repository about?"
```

Graphifyy is complete only when the command exists, the graph is generated, and a query runs successfully.

## LSP Setup

Install or verify the language server for the language(s) chosen by the user.

Common mappings:

```text
TypeScript/JavaScript -> typescript-language-server or built-in VS Code TypeScript support
Python -> pyright
Java -> jdtls
Go -> gopls
Rust -> rust-analyzer
C/C++ -> clangd
C# -> C# language server or OmniSharp
```

Test the selected LSP with its version command when available:

```bash
pyright --version
gopls version
rust-analyzer --version
clangd --version
```

For Java and C#, use the appropriate installed language server or IDE extension check.

LSP is complete only when the selected language server is installed/configured and the agent can verify it is available.

## New Session Requirement

After installing Graphifyy or LSP tooling, ask the user to open a new Copilot session at the repository root.

The new session should run:

```text
setup tooling
```

or:

```text
init help
```

This lets the assistant detect newly installed tools, loaded skills, updated PATH values, and any VS Code/Copilot configuration changes.

## State File

Record status in:

```text
.agentic/setup/tooling-state.json
```

The state should include:

- selected language(s);
- Graphifyy install command used;
- Graphifyy version;
- graph output path;
- Graphifyy query test result;
- selected LSP(s);
- LSP test command(s);
- LSP test result(s);
- whether a new session was requested;
- overall status.

## Completion Criteria

`setup tooling` is complete only when:

- Graphifyy is installed;
- Graphifyy has generated `graphify-out/graph.json`;
- a Graphifyy query test has passed;
- the selected LSP is installed/configured;
- the selected LSP has been tested successfully;
- `.agentic/setup/tooling-state.json` records the successful results.

If either Graphifyy or LSP is missing, untested, or failing because work is
incomplete, the topic is partial, not complete.

**Blocked-not-failed escape.** Tooling is mandatory, but if a step genuinely
cannot be done in this environment (air-gapped repo, no registry access, org
policy blocking the install) it is recorded as `blocked` — not `failed` or
`partial` — with the manual-completion steps written to `tooling-state.json`.
LSP is the floor: when LSP is verified but Graphifyy is environmentally blocked,
tooling is `blocked` and overall setup may still complete (see
`docs/setup-flow.md`). `blocked` requires a real environment reason, not a
skipped or failed step.

## Status And Help Behavior

`init help` and `init status` should report tooling setup like this:

```text
Tooling:
- Graphifyy: complete
- LSP:
  - Java: complete

Recommended next step:
- open a new Copilot session at the repo root and run init help
```

If Graphifyy is incomplete, recommend fixing Graphifyy first.

If Graphifyy is complete but LSP is incomplete, recommend fixing the selected LSP.

If both are complete and a new session has not been requested yet, ask the user to open a new Copilot session at the repo root.
