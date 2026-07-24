# Initialization Module Knowledge Design

## Summary

AKMaestro initialization will offer to generate path-scoped knowledge for the
complex modules confirmed by the team lead. Accepting the offer makes generation
and validation of every selected module a completion requirement for the
instructions topic. Declining preserves the modules as explicit, non-blocking
follow-up work.

The default artifact remains a Copilot path-scoped instruction file:

```text
.github/instructions/<module-id>.instructions.md
```

A nested `<module>/AGENTS.md` remains opt-in and is never generated solely
because a directory was detected as a complex module.

## Goals

- Detect candidate complex modules before asking the team lead for information.
- Let the lead add, remove, or correct candidates before generation.
- Obtain explicit consent before generating module-scoped knowledge.
- Make accepted generation resumable and controller-enforced.
- Produce concise module guidance scoped to the files where it applies.
- Preserve the existing non-destructive merge and project-boundary guarantees.
- Report deferred module knowledge clearly in status and final handoff output.

## Non-Goals

- Generating an instruction file for every directory or package.
- Treating filesystem structure alone as sufficient domain knowledge.
- Replacing the repository-wide `AGENTS.md`.
- Automatically generating nested module `AGENTS.md` files.
- Changing the Stage 2 feature lifecycle.
- Scanning sibling products during a subproject installation.

## User Experience

During `/akmaestro-init`, the `setup-instructions` topic presents complex-module
candidates as part of the sourced repository proposal. Each candidate includes:

- AKMaestro-root-relative path;
- proposed purpose;
- strongest source;
- confidence (`high`, `medium`, or `low`);
- any existing scoped instruction artifact.

The team lead may add, remove, or correct entries. The resulting list becomes
the confirmed `repositoryContext.complexModules` list. If a parent and child path
are both selected, the flow explains that both scoped files may apply and asks
the lead to confirm the overlap as part of the final selection.

When the confirmed list is non-empty, the flow asks:

```text
Generate scoped knowledge for all selected modules now?
```

The outcomes are:

- **Yes:** record `generate_now`, generate every selected module, and keep the
  instructions topic in progress until all module files pass validation.
- **No:** record `defer`, keep unresolved modules in `pendingModules`, complete
  the instructions topic, and report exact follow-up commands.
- **No confirmed modules:** record `not_applicable` without asking the question.

If the lead changes their mind after choosing `generate_now`, switching to
`defer` requires an explicit confirmation. Removing a module from the confirmed
list requires confirming that it was a false positive or is intentionally
outside the product's module-knowledge scope.

## State Contract

Instructions evidence gains this required object:

```json
{
  "moduleKnowledge": {
    "decision": "generate_now"
  }
}
```

`decision` accepts exactly:

- `generate_now`;
- `defer`;
- `not_applicable`.

The existing fields retain distinct responsibilities:

- `repositoryContext.complexModules` is the lead-confirmed module list.
- `pendingModules` is the subset that does not yet have validated scoped
  knowledge.
- `generatedFiles` contains only the root instruction artifacts, each validated
  controller-derived scoped module target, and any explicitly requested nested
  `<module>/AGENTS.md` listed alongside its completed scoped target.

The controller enforces these invariants:

1. Every pending module is present in `repositoryContext.complexModules`.
2. Every completed module has an existing generated artifact with valid scoped
   frontmatter.
3. `not_applicable` requires both `complexModules` and `pendingModules` to be
   empty.
4. `generate_now` may be written while modules remain pending, but instructions
   must remain `in_progress`: both terminal transitions and setup finalization
   are rejected until `pendingModules` is empty.
5. `defer` permits an instructions transition to `complete` with pending modules;
   those modules remain warnings in status and finalization output.
6. A nested `<module>/AGENTS.md` is valid only for a confirmed completed module,
   cannot replace its required scoped target, and enters the shared inventory
   when listed in `generatedFiles`.

The instructions evidence schema and bundled evidence example will be updated
with the new required object. Because AKMaestro has not shipped, the existing
pre-release state contract can be updated without a migration path.

## Generation Flow

After root instruction artifacts and initial instructions evidence are valid,
the flow handles selected modules in stable, normalized path order.

For each pending module:

1. Inspect code, manifests, documentation, existing instructions, and relevant
   confirmed root facts within the AKMaestro boundary.
2. Draft the module's purpose, boundaries, differing commands, important paths,
   established patterns, pitfalls, and restrictions.
3. Present the draft with sources and confidence; ask only about missing,
   conflicting, or low-confidence facts.
4. Derive a readable module ID from the full relative path. If normalization
   would collide with another selected or existing module target, add a stable
   short path hash to every colliding target.
5. Create or merge
   `.github/instructions/<module-id>.instructions.md`.
6. Validate the artifact.
7. Atomically revise instructions evidence by adding the artifact to
   `generatedFiles` and removing the module from `pendingModules`.

Evidence is written before the first module and after each successful module.
An interruption therefore preserves the selection, consent decision, completed
modules, and exact remaining set. A resumed `/akmaestro-init` continues with the
first pending module; topic skills are not used as cross-session resume commands.

## Module Artifact Contract

The default scoped artifact uses AKMaestro-root-relative POSIX paths:

```md
---
applyTo: "services/payments/**"
---

# Payments Module

## Purpose

Own payment authorization and settlement behavior used by checkout.
```

Each artifact must:

- use an `applyTo` glob confined to the confirmed module path;
- contain no AKMaestro placeholders;
- cover Purpose, Boundaries, Commands, Important Paths, Patterns, Pitfalls, and
  Restrictions;
- state explicitly when a section has no module-specific difference from root
  guidance;
- avoid duplicating general repository instructions;
- contain only confirmed or source-supported claims.

The controller validates the file's existence, boundary, frontmatter scope,
required headings, and placeholder absence before accepting it as generated.
Content quality, provenance, and lead confirmation remain skill-level gates.

## Existing Files And Safety

New scoped files may be created directly. Existing scoped files use the current
controller-bound merge protocol:

1. create the complete proposal locally;
2. run `merge-plan`;
3. show the exact diff;
4. obtain approval;
5. run `merge-apply --approved`.

Declining a proposed merge leaves the module pending. The flow does not weaken,
replace, or delete existing guidance without approval.

Module paths must be relative, normalized, and contained by the AKMaestro root.
Absolute paths, traversal, symlink escapes, and output paths outside the root are
rejected. In subproject mode, the enclosing Git root and sibling products are
not module candidates. A separately declared modifiable dependency remains a
dependency, not a module of the current product.

## Status, Finalization, And Errors

`/akmaestro-init status` and `/status` report:

- the module-knowledge decision;
- completed module artifacts;
- pending modules;
- the exact next action.

For `generate_now` with pending modules, the next cross-session command remains
`/akmaestro-init`, and setup cannot finalize. A normal generation or validation
failure keeps the instructions topic `in_progress`; it is not converted into an
environmental blocker.

For `defer`, setup may finalize. The final handoff lists each pending module and
the corresponding command:

```text
/setup-instructions module <path>
```

Unsafe paths, invalid state, and stale evidence revisions stop without mutation.
An unapproved existing-file merge also stops without marking the module
complete.

## Testing

Automated tests will cover:

- all three decision values and rejection of unknown or missing values;
- `not_applicable` list invariants;
- pending-module subset validation;
- rejection of `complete`, `blocked`, and finalization for `generate_now` with
  pending modules;
- successful completion when accepted module generation is exhausted;
- permitted completion and warnings for `defer`;
- atomic evidence revision after each completed module;
- resumption from a partially completed module list;
- deterministic module ordering and filename derivation;
- filename collision handling;
- exact `applyTo` scope validation;
- required headings and placeholder rejection;
- existing-file merge approval and declined-merge behavior;
- confirmed parent/child overlaps;
- path traversal, absolute path, and symlink escape rejection;
- Windows path normalization;
- normal repository and explicit subproject isolation;
- bundled schema/example consistency;
- wheel contents and installed-wheel smoke behavior.

The manual Copilot test guide will cover accepting, declining, interrupting, and
resuming module generation on both VS Code and Copilot CLI. Documentation will
also update the setup flow, decision log, instruction topic, README, testing
guides, changelog, and repository context where the current pending-only
behavior is described.

## Acceptance Criteria

The change is complete when:

1. The lead reviews and confirms the complex-module list.
2. A non-empty list produces the explicit generate-now question.
3. Accepting generation prevents instructions completion until every selected
   module artifact validates.
4. Declining records an explicit deferred decision and preserves actionable
   warnings.
5. Interrupted generation resumes through `/akmaestro-init` without repeating
   completed modules.
6. Generated files are path-scoped, concise, safe, and non-destructive.
7. Automated and manual-test documentation covers both repository installation
   modes and supported Copilot surfaces.
