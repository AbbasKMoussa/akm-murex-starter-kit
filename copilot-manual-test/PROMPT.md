# AKMaestro Live Copilot Verification

You are verifying AKMaestro in a live GitHub Copilot session. Work through the
checks with the human in order. Record PASS, FAIL, or SKIPPED with the actual
result. Observe and report; do not repair failures unless asked. Stay inside the
scratch repository and its explicitly declared modifiable siblings.

Write `copilot-test-results.md` at the end. Record the OS, Copilot surface and
version, AKMaestro version, and whether `jq`, `pwsh`, and `uv` are available.
Never put raw prompts, tool arguments/results, credentials, or session IDs in
the report.

AKMaestro has two stages: a team lead runs `/akmaestro-init` once and commits the
shared result; developers start directly with `/feature`, which checks and
offers to remediate local prerequisites.

## Phase 0: Installed layout

1. Confirm `.github/skills/` contains exactly 19 skill folders with `SKILL.md`.
   The setup entry is `akmaestro-init`; there must be no bundled `init` skill.
2. Confirm `.agentic/bin/akmaestro-state.py`, `.agentic/STATE-PROTOCOL.md`, and
   seven schemas exist, including `action-checks.schema.json`.
3. Confirm hook scripts/data exist when installed, `.agentic/local/` and
   `.agentic/audit/` are ignored, and `hooks.json` has `disableAllHooks: true`.
4. Run `akmaestro update --dry-run` from the installed source. Confirm it writes
   nothing and reports the proposed result.

Expected: all assets are present; hooks are disabled before consent.

## Phase 1: Discovery and read-only orientation

5. Confirm these entry skills are discoverable: `status`, `akmaestro-init`,
   `setup-instructions`, `setup-tooling`, `setup-skills`, `setup-hooks`, `teach`,
   `doctor`, `feature`, and the eleven feature-step skills.
6. Run `/status` before setup. It must name the team lead as owner, give
   `/akmaestro-init` as the one next action, and create no setup state.
7. Ask “is the agentic setup healthy?” Confirm natural-language routing invokes
   `/doctor` and produces a grouped diagnosis without crashing.

## Phase 2: Team-lead initialization

8. Run `/akmaestro-init`. Confirm it reads and follows each installed topic skill
   in controller order without requiring manual topic invocation.
9. During instructions setup, confirm the agent presents one sourced matrix for:
   product purpose/consumers/workflows; bootstrap, build, test, lint, typecheck,
   run, and verify; branch and commit conventions; restricted paths; complex
   modules; and sibling repository roles. It should ask only about gaps,
   conflicts, and low-confidence proposals.
10. Confirm finite configured actions are represented as argument arrays, shown
    before execution, run through `action-check`, and written with the exact
    controller `checkId`. Machine-changing bootstrap requires confirmation.
11. Confirm existing instruction files use `merge-plan`, show the exact unified
    diff, and require confirmation before `merge-apply --approved`. Change a
    target after reviewing one test plan and confirm application is rejected.
12. Confirm Graphifyy writes every graph under
    `.agentic/local/graphs/<repository-id>/graph.json`, including sibling-source
    graphs. It must not write output into a read-only sibling.
13. Confirm skill evidence lists all 19 skills and discovery results for the
    surfaces actually tested.
14. In hooks setup, confirm assets remain disabled during explanation and dry
    tests. Declining must leave them disabled and skip the topic. If enabling,
    explicit consent must precede `hooks-enable`.
15. Interrupt once after an artifact/evidence write but before its aggregate
    transition. Start a fresh session, run `/akmaestro-init`, and confirm it
    resumes without corruption or duplicate advancement.
16. Confirm setup state is version 3, has revisions and finalization, and does
    not persist derived `overall`, `currentStep`, or `nextCommand` fields.
17. On completion, confirm `setup-finalize` writes `.github/AGENTIC.md`, returns
    exact shared/local/blocked/pending inventories, and rerunning is idempotent.
    If an existing test guide must be replaced, confirm `setup-finalize
    --preview` returns the exact diff without changing the guide or state, and
    replacement occurs only after explicit approval.
    No generated guide or root instruction file may retain a placeholder.

Expected: setup is controller-driven, resumable, non-destructive, and ends with
a review-and-commit handoff. A genuine policy/environment block may be recorded;
an ordinary failed command must remain unfinished.

### Module-knowledge decision paths

Run M1-M4 in separate scratch repositories or disposable branches so each
begins before instructions evidence exists:

- **M1 — accept two modules:** Confirm two complex modules, including their
  purpose, source, confidence, and product-relative POSIX paths. Accept the
  single generate-now question. Verify both controller-derived files stay under
  `.github/instructions/`, use exact `<module-path>/**` scopes, contain all seven
  required sections, and are added to evidence only after validation.
  Instructions must remain `in_progress`, and setup must not finalize, until
  both are complete.
- **M2 — defer:** Confirm one or more modules and decline generation. Verify
  `moduleKnowledge.decision` is `defer`, setup finalizes, and status plus the
  final handoff print the controller-returned
  `/setup-instructions module <path>` command for every pending module.
- **M3 — interrupt and resume:** Confirm two modules and accept generation.
  Stop after the first module artifact and atomic evidence revision. Open a new
  Copilot session, run `/akmaestro-init`, and verify it preserves the first
  completion and resumes at the second module without asking for the topic
  skill as the cross-session command.
- **M4 — correct a false positive:** Remove or correct one detected candidate
  before confirming the sourced summary. Verify the false-positive path is
  absent from committed `repositoryContext.complexModules`, `pendingModules`,
  generated targets, and all status/finalization output.

For every path, confirm the default artifact is a scoped instruction file and
that a nested module `AGENTS.md` appears only after a separate explicit request.

## Phase 3: Hook scripts while disabled

Skip hook checks when assets were omitted. Directly invoke the platform scripts
with the GA CLI shape, where `toolArgs` is a JSON-encoded string:

18. Restricted guard: `.env` -> deny; `README.md` -> allow; undeclared sibling
    -> deny; declared modifiable sibling -> allow; `.env` inside that sibling ->
    deny; a symlink or junction escape -> deny.
19. Dangerous-command guard: a harmless sentinel pattern -> deny when matched;
    a normal listing command -> allow; dangerous text in file content -> allow.
20. Lint hook: configure a temporary structured linter and use a filename with
    spaces and shell metacharacters. Confirm direct execution treats the path as
    one argument and performs no command substitution.
21. Audit hook: send unique secret strings in prompt, arguments, result, and
    session fields. Confirm the JSONL file stores only bounded event/tool/time
    metadata and none of the secret strings. Confirm local ignore and 14-day
    retention behavior.

Every hook script must exit zero. Malformed unknown payloads may allow; a parsed
edit path that cannot be resolved inside a writable root must deny.

## Phase 4: Live hook wiring after consent

Run only if the lead consented and the surface permits hooks.

22. Open a fresh session and confirm `hooks-status` reports enabled.
23. Attempt a harmless edit to `.env`; expect a live deny. Edit `notes.md`;
    expect success. Attempt an edit through a symlink/junction that resolves
    outside declared writable roots; expect a deny.
24. Confirm the audit line remains metadata-only. Do not attempt to recover or
    report raw hook payloads from the audit log.
25. Run `akmaestro update`, then confirm hook activation remains enabled. Run
    `hooks-disable` and confirm live hooks can be revoked.

Record the exact surface and any organization-policy restriction.

## Phase 5: Developer handoff and feature flow

26. From the committed setup in a fresh developer session, do not run
    `/akmaestro-init`; run `/feature`.
27. Confirm `/feature` validates shared finalization and probes local `uv`,
    Graphifyy version/query, LSPs, and graph artifacts. Decline one remediation
    and confirm feature mutation remains blocked; alter a recorded action and
    confirm the controller rejects it; approve the exact action and rerun. If uv
    itself is absent in a separate scratch environment, confirm `/feature`
    offers the official platform installer and makes no workflow mutation.
28. Start a small feature. Confirm shared state is under
    `.agentic/features/<id>/`, local selection is
    `.agentic/local/active-feature.json`, and no shared `index.json` exists.
29. Walk Understand -> Frame -> Split. Confirm each approval gate is real and
    artifacts are useful and persisted before transitions.
30. Run one guided story. If possible, run another autonomous story and confirm
    Prime -> Plan -> Implement -> Review -> Learn loops internally until a real
    blocker. Guided implement-to-review must use fresh context.
31. From a cold session, compare `/status` with `/feature` orientation. Both must
    derive the same phase/story/next command; `/status` must mutate nothing.

## Phase 6: Multi-repository boundary

When modifiable and read-only siblings are declared:

32. Confirm only modifiable sibling paths are in
    `.agentic/hooks/editable-paths.txt`.
33. Confirm a feature story may read both siblings, may edit and run commands in
    the modifiable sibling, and never edits the read-only sibling.
34. Confirm all sibling graphs remain under the main repository's local cache.

## Phase 7: Explicit subproject module boundary

Install into an independent product with `--subproject`, open that product as
the workspace/root, and repeat M1 with two modules inside it.

35. Confirm every detected module candidate is below the selected product root;
    the enclosing Git root and sibling products are not candidates.
36. Confirm every `module-targets` result, generated scoped file, evidence
    revision, and setup-state write stays below the selected product root.
37. Confirm neither `.github/` nor `.agentic/` module artifacts are created at
    the enclosing Git root or in sibling products.

## Report

Use this table:

| # | Check | Expected | Actual | Result |
|---|---|---|---|---|
| 1 | Installed skills | 19, including `akmaestro-init` | | |

Include the `/doctor` verdict, setup final inventory, hook surface/policy, and a
short list of failures with exact non-sensitive errors. Do not include secrets
or raw prompt/tool/session content.
