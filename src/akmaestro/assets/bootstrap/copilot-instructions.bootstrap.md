# GitHub Copilot Instructions

Use the repository-wide instructions in `AGENTS.md` as the source of truth.

Also apply path-specific instructions in `.github/instructions/` and any nested
`AGENTS.md` files in the area being modified.

Available skills live in `.github/skills/` (team lead: `/akmaestro-init` once; developers:
`/feature`; anyone: `/status` for orientation, `/doctor` for health, and `/teach`
to capture an instruction).
See `.github/AGENTIC.md` for the team guide once setup has run.

When instructions conflict, prefer the most specific instruction for the files
being changed.
