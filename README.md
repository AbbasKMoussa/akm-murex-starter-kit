# Murex Starter Kit

Bootstrap an existing repository for agentic coding with GitHub Copilot
(VS Code + CLI). The kit installs agent instruction files, skills, optional
hooks, and tooling guidance, then a guided flow finishes repo-specific setup.

## Install into a repo

From the root of the target repository:

```bash
uvx murex-starter-kit init
```

(or `pipx run murex-starter-kit init`). This is a thin file-dropper: it copies
the kit's skills and hooks in, then tells you to run the guided flow.

## Then run the flow

Open Copilot (VS Code or CLI) at the repo root and run:

```text
/init
```

or say "let's run the initialization flow". The `init` skill walks the four
setup topics — instructions, tooling, skills, hooks — and writes a team guide to
`.github/AGENTIC.md`.

## Design

- `docs/setup-flow.md` — the integrated Stage 1 spec.
- `docs/setup-flow-decisions.md` — the decision log.
- `docs/init-topics/` — per-topic depth (instructions, tooling, skills, hooks).

Stage 2 (the BMAD-style feature flow) is planned separately.
