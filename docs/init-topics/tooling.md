# Initialization Topic: Tooling

`/setup-tooling` is the second mandatory setup topic. It verifies Graphifyy and
one language server per confirmed project language, then writes the shared
developer-readiness contract used by `/feature`.

It is also reached through `/akmaestro-init`.

## Input

Detect project and sibling-repository languages, then ask the lead to confirm
the language set. Do not ask for tools already implied by that confirmation.

## Graphifyy

The package is `graphifyy`; the executable is `graphify`:

```text
uv tool install graphifyy
graphify vscode install
graphify extract . --out .agentic/local/graphs/main
graphify query "what is this repository about?" --graph .agentic/local/graphs/main/graph.json
```

Every graph is developer-local and gitignored:

```text
.agentic/local/graphs/<repository-id>/graph.json
```

For a sibling, pass its path as the extraction source and a path under the main
repository as `--out`:

```text
graphify extract ../lib-b --out .agentic/local/graphs/lib-b
graphify extract ../vendor-c --out .agentic/local/graphs/vendor-c
```

This applies equally to modifiable and read-only siblings. Never create
`graphify-out/` or any generated artifact inside a sibling repository.

## Language servers

Verify one non-interactive command per confirmed language. Typical choices are
`typescript-language-server`, `pyright`, `jdtls`, `gopls`, `rust-analyzer`,
`clangd`, and an appropriate C# language server. An IDE-only extension does not
satisfy Copilot CLI readiness unless it exposes a reliable command probe.

## Requirements contract

Write `.agentic/setup/environment-requirements.json` through
`requirements-write`. It contains structured argument-array probes and confirmed
install/remediation actions for:

- `uv`;
- Graphifyy version;
- a Graphifyy query against the main graph;
- `lsp-<language>` for every selected language;
- the main and declared-sibling graph artifacts.

Paths and working directories are AKMaestro-root-relative POSIX paths. Commands
are argument arrays, never shell strings. Credentials and local command output
are not committed. Run `readiness-check` after writing requirements.

## Strict evidence

`evidence-write tooling` accepts exactly:

- `languages`;
- `graphify`: `status`, `version`, `queryStatus`, `graphPaths`, and `detail`;
- `lsps`: exactly one `language`, `toolId`, `status`, and `detail` per language;
- `requirementsRevision`;
- `newSessionRequired`;
- `blockers`.

Graph paths must match `.agentic/local/graphs/<id>/graph.json`. Evidence must
reference the current requirements revision.

## Completion

Complete only when required local probes and artifacts are ready. A normal
install/query/LSP failure leaves the topic `in_progress`. A real air-gap,
registry, or organization-policy restriction is recorded as `blocked` with the
exact remediation in requirements; overall repository setup may still finalize
with that durable follow-up.

Request a restart only when the current process cannot observe an installed
command or Copilot must reload. Persist evidence and requirements first. The
sole resume instruction is:

```text
Next: open a new Copilot session at the AKMaestro root and run /akmaestro-init
```
