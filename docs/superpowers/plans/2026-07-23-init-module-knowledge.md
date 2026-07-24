# Initialization Module Knowledge Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `/akmaestro-init` offer reviewed, resumable generation of scoped knowledge for confirmed complex modules and enforce completion when the lead accepts.

**Architecture:** Extend the strict instructions-evidence contract with a module-knowledge decision, then let the standard-library state controller derive collision-safe targets, validate scoped artifacts, gate completion, and report resume data. Keep repository inspection and knowledge drafting in the installed skills, with the controller as the sole state and safety authority.

**Tech Stack:** Python 3.9+ standard library controller, JSON Schema Draft 2020-12, pytest, jsonschema test dependency, Markdown agent skills, uv, Ruff, Hatchling.

**Execution correction:** Release audit expanded Task 4's `generate_now` gate
from a `complete`-only check to both terminal states (`complete` and `blocked`),
implemented in `d266fb5`.

## Global Constraints

- The bundled `.agentic/bin/akmaestro-state.py` controller must remain Python 3.9 compatible and standard-library only.
- Allowed decisions are exactly `generate_now`, `defer`, and `not_applicable`.
- Accepting `generate_now` must prevent instructions completion while any confirmed module remains pending.
- Declining with `defer` must permit finalization and retain actionable pending-module warnings.
- Module paths and generated artifacts must remain inside the AKMaestro root; subproject mode must not scan or write sibling products.
- Existing files must continue through `merge-plan`, exact diff review, and `merge-apply --approved`.
- Default module artifacts are `.github/instructions/*.instructions.md`; nested module-local `AGENTS.md` files remain explicitly opt-in.
- Module files contain only module-specific guidance and must not duplicate general repository instructions.
- Do not add runtime dependencies, change Stage 2 behavior, or bump the package version.

## File Structure

- `src/akmaestro/state.py`: evidence validation, target derivation, artifact validation, transition gate, inventory, and read-only controller command.
- `src/akmaestro/assets/schemas/setup-evidence.schema.json`: machine-readable module-decision contract.
- `src/akmaestro/assets/skills/setup-instructions/references/instructions-evidence.example.json`: complete evidence example.
- `src/akmaestro/assets/skills/setup-instructions/SKILL.md`: detection, selection, consent, generation loop, and resume procedure.
- `src/akmaestro/assets/skills/akmaestro-init/SKILL.md`: orchestration and final handoff behavior.
- `src/akmaestro/assets/skills/status/SKILL.md`: read-only decision and module-progress reporting.
- `src/akmaestro/assets/skills/doctor/SKILL.md`: decision-aware health checks.
- `.github/skills/doctor/SKILL.md`: synchronized dogfood copy of the canonical doctor skill.
- `src/akmaestro/assets/runtime/STATE-PROTOCOL.md`: installed state and resume contract.
- `tests/test_state.py`: controller, schema, target, artifact, transition, inventory, and CLI regression tests.
- `tests/test_installer.py`: bundled-skill wording and canonical/dogfood synchronization assertions.
- `README.md`, `docs/setup-flow.md`, `docs/setup-flow-decisions.md`, `docs/init-topics/instruction-files.md`: product and architecture documentation.
- `TESTING.md`, `WINDOWS-TEST.md`, `copilot-manual-test/PROMPT.md`: automated and live validation instructions.
- `AGENTS.md`, `CHANGELOG.md`: implementation status and unreleased change record.

---

### Task 1: Add The Module-Knowledge Evidence Contract

**Files:**
- Modify: `tests/test_state.py`
- Modify: `src/akmaestro/state.py`
- Modify: `src/akmaestro/assets/schemas/setup-evidence.schema.json`
- Modify: `src/akmaestro/assets/skills/setup-instructions/references/instructions-evidence.example.json`

**Interfaces:**
- Consumes: existing `validate_instructions_evidence(evidence: Dict[str, Any]) -> None`.
- Produces: required `evidence["moduleKnowledge"]["decision"]` with values `generate_now`, `defer`, or `not_applicable`; `_validate_module_path(value: str, label: str) -> None`.

- [ ] **Step 1: Write failing contract tests and update the shared fixture**

Add the required default to `_instructions_evidence`:

```python
"moduleKnowledge": {"decision": "not_applicable"},
```

Add focused semantic tests:

```python
@pytest.mark.parametrize("decision", ("generate_now", "defer"))
def test_module_knowledge_active_decisions_require_confirmed_modules(
    tmp_path, decision
):
    body = _instructions_evidence(tmp_path)
    body["moduleKnowledge"] = {"decision": decision}
    with pytest.raises(state.StateError, match="requires at least one complex module"):
        state.validate_instructions_evidence(body)


def test_module_knowledge_not_applicable_requires_empty_module_lists(tmp_path):
    body = _instructions_evidence(tmp_path)
    body["repositoryContext"]["complexModules"] = [
        {"path": "services/payments", "purpose": "Payment processing"}
    ]
    body["pendingModules"] = ["services/payments"]
    with pytest.raises(state.StateError, match="not_applicable requires no complex modules"):
        state.validate_instructions_evidence(body)


@pytest.mark.parametrize(
    "module_path",
    ("../outside", "services/../outside", "/absolute", "C:/absolute", r"services\payments"),
)
def test_complex_module_paths_must_be_normalized_product_relative_paths(
    tmp_path, module_path
):
    body = _instructions_evidence(tmp_path)
    body["moduleKnowledge"] = {"decision": "defer"}
    body["repositoryContext"]["complexModules"] = [
        {"path": module_path, "purpose": "Unsafe fixture"}
    ]
    body["pendingModules"] = [module_path]
    with pytest.raises(state.StateError, match="complex module path"):
        state.validate_instructions_evidence(body)
```

- [ ] **Step 2: Run the focused tests and verify the new field is rejected**

Run:

```bash
uv run pytest -q tests/test_state.py -k "module_knowledge or complex_module_paths"
```

Expected: failures report that `moduleKnowledge` is an unknown instructions-evidence key or that the new invariants are not enforced.

- [ ] **Step 3: Implement strict Python validation**

Add the key to both `_require_keys` and `_only_keys`, then validate it after the
confirmed module list is available:

```python
MODULE_KNOWLEDGE_DECISIONS = {"generate_now", "defer", "not_applicable"}


def _validate_module_path(value: str, label: str) -> None:
    _validate_workspace_path(value, label)
    normalized = PurePosixPath(value)
    if (
        value == "."
        or normalized.as_posix() != value
        or any(part in {".", ".."} for part in normalized.parts)
    ):
        raise StateError(
            f"{label} must be a normalized complex module path inside the product"
        )
```

Use `_validate_module_path` for every `repositoryContext.complexModules[*].path`
and every `pendingModules[*]` entry. After validating the pending list and its
membership in the confirmed module set, validate the decision object exactly:

```python
module_knowledge = evidence["moduleKnowledge"]
if not isinstance(module_knowledge, dict):
    raise StateError("instructions evidence.moduleKnowledge must be an object")
_require_keys(module_knowledge, ("decision",), "moduleKnowledge")
_only_keys(module_knowledge, ("decision",), "moduleKnowledge")
decision = module_knowledge["decision"]
if decision not in MODULE_KNOWLEDGE_DECISIONS:
    raise StateError(
        "moduleKnowledge.decision must be 'generate_now', 'defer', or 'not_applicable'"
    )
if decision == "not_applicable" and (module_paths or pending):
    raise StateError(
        "moduleKnowledge not_applicable requires no complex modules or pending modules"
    )
if decision in {"generate_now", "defer"} and not module_paths:
    raise StateError(
        f"moduleKnowledge {decision} requires at least one complex module"
    )
```

Retain the existing invariant that every pending path belongs to the confirmed
module set.

- [ ] **Step 4: Update the JSON Schema and evidence example**

Add `moduleKnowledge` to `instructionsEvidence.required` and properties:

```json
"moduleKnowledge": {
  "type": "object",
  "additionalProperties": false,
  "required": ["decision"],
  "properties": {
    "decision": {
      "enum": ["generate_now", "defer", "not_applicable"]
    }
  }
}
```

Add this to the bundled example because its complex-module list is empty:

```json
"moduleKnowledge": {
  "decision": "not_applicable"
}
```

- [ ] **Step 5: Run contract and schema tests**

Run:

```bash
uv run pytest -q tests/test_state.py -k "instructions_evidence or module_knowledge or complex_module_paths or bundled_instruction"
```

Expected: all selected tests pass.

- [ ] **Step 6: Commit the contract**

```bash
git add tests/test_state.py src/akmaestro/state.py src/akmaestro/assets/schemas/setup-evidence.schema.json src/akmaestro/assets/skills/setup-instructions/references/instructions-evidence.example.json
git commit -m "Add module knowledge evidence contract"
```

---

### Task 2: Derive Deterministic Module Instruction Targets

**Files:**
- Modify: `tests/test_state.py`
- Modify: `src/akmaestro/state.py`

**Interfaces:**
- Consumes: `_validate_module_path(value, label)` from Task 1 and existing scoped instruction files under `.github/instructions/`.
- Produces: `module_instruction_targets(root: Path, module_paths: Sequence[str]) -> Dict[str, str]`; read-only `module-targets --input module-paths.json` controller command accepting `{"modules": ["services/payments"]}`.

- [ ] **Step 1: Write failing target-derivation tests**

Add:

```python
def test_module_instruction_targets_are_readable_stable_and_collision_safe(tmp_path):
    modules = ["services/payments", "services_payments"]
    first = state.module_instruction_targets(tmp_path, modules)
    second = state.module_instruction_targets(tmp_path, list(reversed(modules)))

    assert first == second
    assert set(first) == set(modules)
    assert len(set(first.values())) == 2
    for module_path, target in first.items():
        digest = hashlib.sha256(module_path.encode("utf-8")).hexdigest()[:8]
        assert target == (
            f".github/instructions/services-payments-{digest}.instructions.md"
        )


def test_module_instruction_targets_reuse_existing_exact_scope(tmp_path):
    target = tmp_path / ".github" / "instructions" / "payments.instructions.md"
    target.parent.mkdir(parents=True)
    target.write_text(
        '---\napplyTo: "services/payments/**"\n---\n\n# Payments\n',
        encoding="utf-8",
    )

    result = state.module_instruction_targets(tmp_path, ["services/payments"])

    assert result == {
        "services/payments": ".github/instructions/payments.instructions.md"
    }


def test_module_instruction_targets_hash_an_occupied_mismatched_target(tmp_path):
    target = (
        tmp_path
        / ".github"
        / "instructions"
        / "services-payments.instructions.md"
    )
    target.parent.mkdir(parents=True)
    target.write_text(
        '---\napplyTo: "legacy/payments/**"\n---\n\n# Legacy\n',
        encoding="utf-8",
    )
    digest = hashlib.sha256(b"services/payments").hexdigest()[:8]

    result = state.module_instruction_targets(tmp_path, ["services/payments"])

    assert result["services/payments"].endswith(
        f"services-payments-{digest}.instructions.md"
    )


def test_module_instruction_targets_support_confirmed_parent_child_overlap(tmp_path):
    result = state.module_instruction_targets(
        tmp_path, ["services", "services/payments"]
    )

    assert result == {
        "services": ".github/instructions/services.instructions.md",
        "services/payments": (
            ".github/instructions/services-payments.instructions.md"
        ),
    }


def test_module_instruction_targets_reject_instruction_directory_escape(tmp_path):
    outside = tmp_path.parent / f"{tmp_path.name}-outside"
    outside.mkdir()
    instruction_dir = tmp_path / ".github" / "instructions"
    instruction_dir.parent.mkdir(parents=True)
    try:
        instruction_dir.symlink_to(outside, target_is_directory=True)
    except OSError:
        pytest.skip("directory symlinks are unavailable")

    with pytest.raises(state.StateError, match="instructions directory resolves outside"):
        state.module_instruction_targets(tmp_path, ["services/payments"])
```

Add a CLI test that writes `{"modules": ["services/payments"]}` to a JSON file,
runs `state.main(["--root", str(tmp_path), "module-targets", "--input", path])`,
and asserts exit code `0` plus a `targets` object in captured JSON.

- [ ] **Step 2: Run the target tests and verify the helper is missing**

Run:

```bash
uv run pytest -q tests/test_state.py -k "module_instruction_targets or module_targets_cli"
```

Expected: failures report that `module_instruction_targets` and the
`module-targets` parser command do not exist.

- [ ] **Step 3: Add frontmatter extraction and deterministic mapping**

Replace the boolean-only frontmatter scan with a scalar extractor while keeping
`_has_apply_to_frontmatter` as a compatibility wrapper:

```python
def _frontmatter_apply_to(text: str) -> Optional[str]:
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return None
    try:
        end = next(
            index
            for index, line in enumerate(lines[1:], start=1)
            if line.strip() == "---"
        )
    except StopIteration:
        return None
    matches = [
        match.group(1) or match.group(2) or match.group(3)
        for line in lines[1:end]
        if (
            match := re.fullmatch(
                r"""applyTo:\s*(?:"([^"]+)"|'([^']+)'|(\S+))\s*""",
                line,
            )
        )
    ]
    return matches[0] if len(matches) == 1 else None


def _has_apply_to_frontmatter(text: str) -> bool:
    return _frontmatter_apply_to(text) is not None
```

Implement:

```python
def _module_slug(module_path: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", module_path.lower()).strip("-")
    if slug:
        return slug
    digest = hashlib.sha256(module_path.encode("utf-8")).hexdigest()[:8]
    return f"module-{digest}"


def module_instruction_targets(
    root: Path, module_paths: Sequence[str]
) -> Dict[str, str]:
    ordered = sorted(set(module_paths))
    if len(ordered) != len(module_paths):
        raise StateError("module target input contains duplicate paths")
    for index, module_path in enumerate(ordered):
        _validate_module_path(module_path, f"modules[{index}]")

    instruction_dir = root / ".github" / "instructions"
    if instruction_dir.exists() and not _is_within(
        instruction_dir.resolve(), root.resolve()
    ):
        raise StateError("instructions directory resolves outside repository")
    existing_by_scope: Dict[str, str] = {}
    occupied: Dict[str, Optional[str]] = {}
    if instruction_dir.is_dir():
        for path in sorted(instruction_dir.glob("*.instructions.md")):
            relative = str(path.relative_to(root)).replace(os.sep, "/")
            resolved = path.resolve()
            if not _is_within(resolved, root.resolve()):
                raise StateError(
                    f"scoped instruction resolves outside repository: {relative}"
                )
            scope = _frontmatter_apply_to(
                _read_text_artifact(resolved, f"scoped instruction {relative}")
            )
            occupied[relative] = scope
            if scope in {f"{module_path}/**" for module_path in ordered}:
                if scope in existing_by_scope:
                    raise StateError(
                        f"multiple scoped instruction files use applyTo {scope!r}"
                    )
                existing_by_scope[scope] = relative

    slugs: Dict[str, List[str]] = {}
    for module_path in ordered:
        if f"{module_path}/**" not in existing_by_scope:
            slugs.setdefault(_module_slug(module_path), []).append(module_path)

    targets: Dict[str, str] = {}
    for module_path in ordered:
        scope = f"{module_path}/**"
        if scope in existing_by_scope:
            targets[module_path] = existing_by_scope[scope]
            continue
        slug = _module_slug(module_path)
        base = f".github/instructions/{slug}.instructions.md"
        needs_hash = len(slugs[slug]) > 1 or (
            base in occupied and occupied[base] != scope
        )
        if needs_hash:
            digest = hashlib.sha256(module_path.encode("utf-8")).hexdigest()[:8]
            base = f".github/instructions/{slug}-{digest}.instructions.md"
        if base in targets.values() or (
            base in occupied and occupied[base] != scope
        ):
            raise StateError(f"cannot derive a unique module instruction target: {base}")
        targets[module_path] = base
    return targets
```

- [ ] **Step 4: Add the read-only controller command**

Register:

```python
module_targets = sub.add_parser(
    "module-targets", help="Derive scoped instruction targets for confirmed modules"
)
module_targets.add_argument(
    "--input", required=True, help="JSON object containing a modules array"
)
```

Validate the input with exact keys and print:

```python
value = _load_object_argument(args.input)
_require_keys(value, ("modules",), "module target input")
_only_keys(value, ("modules",), "module target input")
if not isinstance(value["modules"], list):
    raise StateError("module target input.modules must be an array")
_print_json({"targets": module_instruction_targets(root, value["modules"])})
```

- [ ] **Step 5: Run target and parser tests**

Run:

```bash
uv run pytest -q tests/test_state.py -k "module_instruction_targets or module_targets_cli or apply_to"
```

Expected: all selected tests pass.

- [ ] **Step 6: Commit deterministic target derivation**

```bash
git add tests/test_state.py src/akmaestro/state.py
git commit -m "Derive scoped module instruction targets"
```

---

### Task 3: Validate Completed Module Artifacts

**Files:**
- Modify: `tests/test_state.py`
- Modify: `src/akmaestro/state.py`

**Interfaces:**
- Consumes: `module_instruction_targets(root, module_paths)` from Task 2 and instructions evidence from Task 1.
- Produces: `MODULE_INSTRUCTION_HEADINGS`; exact completed/pending artifact correlation inside `_validate_instruction_artifacts`.

- [ ] **Step 1: Add a valid module-artifact test helper**

Add:

```python
def _write_module_instruction(root, relative, module_path):
    headings = "\n\n".join(
        f"## {heading}\n\nConfirmed module-specific guidance."
        for heading in state.MODULE_INSTRUCTION_HEADINGS
    )
    target = root / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        f'---\napplyTo: "{module_path}/**"\n---\n\n# Module Knowledge\n\n{headings}\n',
        encoding="utf-8",
    )
```

- [ ] **Step 2: Write failing artifact contract tests**

Add tests that:

1. Create `services/payments`, record it as `generate_now`, write the target from
   `module_instruction_targets`, append the target to `generatedFiles`, clear
   `pendingModules`, and assert `write_topic_evidence` succeeds.
2. Change `applyTo` to `"services/orders/**"` and expect
   `StateError("must use applyTo")`.
3. Remove `## Pitfalls` and expect `StateError("missing required section: Pitfalls")`.
4. Insert an AKMaestro placeholder and expect `StateError("placeholder")`.
5. Mark a module completed without adding its target to `generatedFiles` and
   expect `StateError("completed module instruction is missing")`.
6. Leave a module pending while its target is listed in `generatedFiles` and
   expect `StateError("pending module cannot be listed as generated")`.
7. Use a module-directory symlink resolving outside the root and expect
   `StateError("complex module resolves outside")`; skip only when the platform
   cannot create symlinks.

- [ ] **Step 3: Run the artifact tests and verify current validation is too weak**

Run:

```bash
uv run pytest -q tests/test_state.py -k "module_artifact or completed_module or pending_module_cannot"
```

Expected: tests fail because current validation checks only for the presence of
an arbitrary `applyTo` line.

- [ ] **Step 4: Implement the module artifact contract**

Add:

```python
MODULE_INSTRUCTION_HEADINGS = (
    "Purpose",
    "Boundaries",
    "Commands",
    "Important Paths",
    "Patterns",
    "Pitfalls",
    "Restrictions",
)
```

Within `_validate_instruction_artifacts`, resolve and boundary-check every
confirmed module path. Derive targets for the full confirmed list, then correlate
pending and completed modules:

```python
modules = {
    item["path"] for item in evidence["repositoryContext"]["complexModules"]
}
pending = set(evidence["pendingModules"])
targets = module_instruction_targets(root, sorted(modules))
generated = set(evidence["generatedFiles"])

for module_path in sorted(modules):
    module_root = (root / module_path).resolve()
    if not _is_within(module_root, root.resolve()):
        raise StateError(
            f"complex module resolves outside repository: {module_path}"
        )
    target = targets[module_path]
    if module_path in pending:
        if target in generated:
            raise StateError(
                f"pending module cannot be listed as generated: {module_path}"
            )
        continue
    if target not in generated:
        raise StateError(
            f"completed module instruction is missing from generatedFiles: {module_path}"
        )
```

For each completed target, require exact scope and headings:

```python
text = _read_text_artifact(root / target, f"module instruction {target}")
expected_scope = f"{module_path}/**"
if _frontmatter_apply_to(text) != expected_scope:
    raise StateError(
        f"module instruction {target} must use applyTo {expected_scope!r}"
    )
for heading in MODULE_INSTRUCTION_HEADINGS:
    if not re.search(rf"^##\s+{re.escape(heading)}\s*$", text, re.MULTILINE):
        raise StateError(
            f"module instruction {target} is missing required section: {heading}"
        )
lowered = text.lower()
for marker in INSTRUCTION_PLACEHOLDERS:
    if marker in lowered:
        raise StateError(
            f"module instruction {target} still contains an AKMaestro placeholder"
        )
```

- [ ] **Step 5: Run artifact and evidence regression tests**

Run:

```bash
uv run pytest -q tests/test_state.py -k "instruction_artifact or module_artifact or completed_module or pending_module"
```

Expected: all selected tests pass, including the existing test-instruction
frontmatter checks.

- [ ] **Step 6: Commit artifact validation**

```bash
git add tests/test_state.py src/akmaestro/state.py
git commit -m "Validate scoped module knowledge artifacts"
```

---

### Task 4: Gate Completion And Expose Resume State

**Files:**
- Modify: `tests/test_state.py`
- Modify: `src/akmaestro/state.py`

**Interfaces:**
- Consumes: validated module-decision evidence and completed/pending correlation.
- Produces: `_validate_instruction_completion(evidence: Dict[str, Any]) -> None`; controller-enforced `generate_now` completion and integrity gate; derived `moduleKnowledge` inventory with `decision`, `completedModules`, and `pendingModules`; pending items with exact `command`.

- [ ] **Step 1: Write failing transition and inventory tests**

Add:

```python
def test_generate_now_cannot_complete_with_pending_modules(tmp_path):
    state.setup_init(tmp_path)
    state.setup_transition(tmp_path, "instructions", "in_progress", expected_revision=0)
    _write_instruction_artifacts(tmp_path)
    body = _instructions_evidence(tmp_path)
    body["moduleKnowledge"] = {"decision": "generate_now"}
    body["repositoryContext"]["complexModules"] = [
        {"path": "services/payments", "purpose": "Payment processing"}
    ]
    body["pendingModules"] = ["services/payments"]
    state.write_topic_evidence(tmp_path, "instructions", body)

    with pytest.raises(state.StateError, match="accepted module generation"):
        state.setup_transition(
            tmp_path, "instructions", "complete", expected_revision=1
        )


def test_deferred_modules_complete_with_actionable_inventory(tmp_path):
    state.setup_init(tmp_path)
    state.setup_transition(tmp_path, "instructions", "in_progress", expected_revision=0)
    _write_instruction_artifacts(tmp_path)
    body = _instructions_evidence(tmp_path)
    body["moduleKnowledge"] = {"decision": "defer"}
    body["repositoryContext"]["complexModules"] = [
        {"path": "services/payments", "purpose": "Payment processing"}
    ]
    body["pendingModules"] = ["services/payments"]
    state.write_topic_evidence(tmp_path, "instructions", body)
    state.setup_transition(tmp_path, "instructions", "complete", expected_revision=1)

    report = state.setup_status(tmp_path)
    assert report["moduleKnowledge"] == {
        "decision": "defer",
        "completedModules": [],
        "pendingModules": ["services/payments"],
    }
    assert report["pendingItems"] == [
        {
            "type": "module",
            "path": "services/payments",
            "command": "/setup-instructions module services/payments",
        }
    ]
```

Add a partial-resume test with two modules: generate and validate the first,
revise evidence with only the second pending, then assert `setup-status` returns
the first in `completedModules`, the second in `pendingModules`, and
`nextCommand == "/akmaestro-init"`.

Add a decision-revision test that writes `generate_now`, rewrites the same
in-progress topic to `defer` with the latest evidence revision, and then
completes instructions successfully. The skill-level confirmation is tested in
Task 5; this controller test proves the state revision is legal and resumable.

Add an integrity test that creates a valid completed instructions topic, tampers
its evidence to `generate_now` with a pending module, and asserts both
`setup-status` and `validate` reject the inconsistent terminal state.

- [ ] **Step 2: Run focused tests and verify completion currently succeeds**

Run:

```bash
uv run pytest -q tests/test_state.py -k "generate_now_cannot or deferred_modules or partial_module_resume"
```

Expected: the generate-now transition incorrectly succeeds or the new inventory
fields are absent.

- [ ] **Step 3: Enforce the completion and integrity gate**

Add one reusable validator:

```python
def _validate_instruction_completion(evidence: Dict[str, Any]) -> None:
    if (
        evidence["moduleKnowledge"]["decision"] == "generate_now"
        and evidence["pendingModules"]
    ):
        raise StateError(
            "instructions cannot complete because accepted module generation "
            "still has pending modules"
        )
```

Call it from `setup_transition` whenever `topic == "instructions"` and
`status == "complete"`. Also call it from `validate_setup_integrity` for a
completed instructions topic and from `_setup_inventory` when the aggregate
state claims instructions is complete. This makes `setup-status`, `validate`,
and finalization reject stale or tampered terminal state.

Do not add pending modules to `_instructions_have_blockers`; an unfinished
generation is `in_progress`, not an environmental `blocked` topic.

- [ ] **Step 4: Return derived module progress and actionable pending items**

Extend `_setup_inventory` after validating instructions evidence:

```python
module_knowledge = None
if instructions_path.is_file():
    instructions = _read_json(instructions_path)
    validate_topic_evidence(instructions)
    body = instructions["evidence"]
    confirmed = sorted(
        module["path"] for module in body["repositoryContext"]["complexModules"]
    )
    pending_modules = sorted(body["pendingModules"])
    pending_set = set(pending_modules)
    module_knowledge = {
        "decision": body["moduleKnowledge"]["decision"],
        "completedModules": [
            module_path
            for module_path in confirmed
            if module_path not in pending_set
        ],
        "pendingModules": pending_modules,
    }
    pending.extend(
        {
            "type": "module",
            "path": module_path,
            "command": f"/setup-instructions module {module_path}",
        }
        for module_path in pending_modules
    )
```

Include `"moduleKnowledge": module_knowledge` in the returned inventory. Keep
`setup_summary` free of persisted or duplicated derived module state.

- [ ] **Step 5: Run setup transition, finalization, and inventory tests**

Run:

```bash
uv run pytest -q tests/test_state.py -k "setup or module or finalization"
```

Expected: all selected tests pass; `defer` finalizes and `generate_now` remains
resumable until pending modules are exhausted.

- [ ] **Step 6: Commit the gate and reporting contract**

```bash
git add tests/test_state.py src/akmaestro/state.py
git commit -m "Gate init on accepted module knowledge"
```

---

### Task 5: Update Installed Workflow Skills

**Files:**
- Modify: `src/akmaestro/assets/skills/setup-instructions/SKILL.md`
- Modify: `src/akmaestro/assets/skills/akmaestro-init/SKILL.md`
- Modify: `src/akmaestro/assets/skills/status/SKILL.md`
- Modify: `src/akmaestro/assets/skills/doctor/SKILL.md`
- Modify: `.github/skills/doctor/SKILL.md`
- Modify: `src/akmaestro/assets/runtime/STATE-PROTOCOL.md`
- Modify: `tests/test_installer.py`

**Interfaces:**
- Consumes: `module-targets`, `moduleKnowledge`, module progress inventory, merge protocol, and evidence revisions.
- Produces: one reviewed detection/selection prompt, explicit generate/defer consent, an ordered resumable generation loop, decision-aware status, and decision-aware health reporting.

- [ ] **Step 1: Add failing asset-contract tests**

Add a test that reads the four canonical skills and protocol:

```python
def test_init_skills_define_controller_bound_module_knowledge_flow():
    setup = (ASSETS / "skills" / "setup-instructions" / "SKILL.md").read_text(
        encoding="utf-8"
    )
    init = (ASSETS / "skills" / "akmaestro-init" / "SKILL.md").read_text(
        encoding="utf-8"
    )
    status = (ASSETS / "skills" / "status" / "SKILL.md").read_text(
        encoding="utf-8"
    )
    doctor = (ASSETS / "skills" / "doctor" / "SKILL.md").read_text(
        encoding="utf-8"
    )
    protocol = (ASSETS / "runtime" / "STATE-PROTOCOL.md").read_text(
        encoding="utf-8"
    )

    assert "Generate scoped knowledge for all selected modules now?" in setup
    assert "module-targets" in setup
    assert "generate_now" in setup and "defer" in setup
    assert "source" in setup and "confidence" in setup
    assert "parent/child" in setup
    assert "declining" in setup and "pending" in setup
    assert "accepted module generation" in init
    assert "moduleKnowledge" in status
    assert "generate_now" in doctor
    assert "moduleKnowledge" in protocol
```

The existing dogfood synchronization test must continue comparing canonical and
root doctor directories byte-for-byte.

- [ ] **Step 2: Run the asset test and verify wording is absent**

Run:

```bash
uv run pytest -q tests/test_installer.py -k "module_knowledge_flow or dogfood"
```

Expected: the new asset-contract test fails.

- [ ] **Step 3: Rewrite the setup-instructions module flow**

Update the skill so it explicitly performs this sequence:

```text
1. Detect candidates with path, purpose, source, confidence, and existing scope.
2. Present the candidate table and obtain one corrected, confirmed selection.
3. Flag parent/child overlaps and include explicit overlap confirmation.
4. Record not_applicable when the confirmed list is empty.
5. Otherwise ask exactly:
   Generate scoped knowledge for all selected modules now?
6. Persist generate_now or defer in initial instructions evidence.
7. For generate_now, call module-targets with the full confirmed list.
8. Process pending modules in normalized path order.
9. After each validated artifact, revise generatedFiles and pendingModules
   through evidence-write with the latest evidence revision.
10. Transition instructions to complete only after the controller accepts it.
```

Define the exact seven required module sections, exact `applyTo` scope, sourced
draft behavior, collision mapping from `module-targets`, merge approval protocol,
explicit `generate_now` to `defer` confirmation, and `/akmaestro-init` as the sole
cross-session resume command.

- [ ] **Step 4: Update orchestration, status, doctor, and protocol**

In `akmaestro-init/SKILL.md`, require the orchestrator to:

```text
- inspect moduleKnowledge whenever instructions is in_progress;
- resume the first controller-returned pending module after generate_now;
- never finalize while accepted module generation is pending;
- list deferred module commands in the final handoff.
```

In `status/SKILL.md`, report the decision plus completed/pending counts and keep
one `Next: /akmaestro-init` line during accepted generation.

In `doctor/SKILL.md`, use:

```text
- generate_now + pending + instructions in_progress: warn as unfinished setup;
- generate_now + pending + instructions complete: fail as invalid controller state;
- defer + pending: warn with each controller-returned follow-up command;
- not_applicable + non-empty modules: fail contract validation.
```

Document the same state/resume distinction in `STATE-PROTOCOL.md`.

- [ ] **Step 5: Synchronize the dogfood doctor copy**

Copy the canonical content without editing it independently:

```bash
cp src/akmaestro/assets/skills/doctor/SKILL.md .github/skills/doctor/SKILL.md
```

- [ ] **Step 6: Run asset and installer tests**

Run:

```bash
uv run pytest -q tests/test_installer.py
```

Expected: all installer, asset, subproject, and dogfood tests pass.

- [ ] **Step 7: Commit installed workflow behavior**

```bash
git add src/akmaestro/assets/skills/setup-instructions/SKILL.md src/akmaestro/assets/skills/akmaestro-init/SKILL.md src/akmaestro/assets/skills/status/SKILL.md src/akmaestro/assets/skills/doctor/SKILL.md .github/skills/doctor/SKILL.md src/akmaestro/assets/runtime/STATE-PROTOCOL.md tests/test_installer.py
git commit -m "Guide init through module knowledge generation"
```

---

### Task 6: Update Product Documentation And Run Release Validation

**Files:**
- Modify: `README.md`
- Modify: `docs/setup-flow.md`
- Modify: `docs/setup-flow-decisions.md`
- Modify: `docs/init-topics/instruction-files.md`
- Modify: `TESTING.md`
- Modify: `WINDOWS-TEST.md`
- Modify: `copilot-manual-test/PROMPT.md`
- Modify: `AGENTS.md`
- Modify: `CHANGELOG.md`

**Interfaces:**
- Consumes: the completed controller and skill behavior from Tasks 1-5.
- Produces: consistent user guidance, decision record, live verification cases, and an audited release-ready artifact set.

- [ ] **Step 1: Update user-facing and architecture documentation**

Document this exact behavior in `README.md`, `docs/setup-flow.md`, and
`docs/init-topics/instruction-files.md`:

```text
- complex modules are detected with provenance and confirmed by the lead;
- a non-empty confirmed list produces one generate-now question;
- generate_now is mandatory-to-finish once accepted;
- defer is non-blocking and produces exact follow-up commands;
- module files default to .github/instructions/ and nested AGENTS.md is opt-in;
- interruption resumes through /akmaestro-init.
```

Update the setup-evidence JSON excerpt in `docs/setup-flow.md` to include:

```json
"moduleKnowledge": {"decision": "generate_now"}
```

Add decision 31 to `docs/setup-flow-decisions.md` recording the integrated,
controller-enforced approach and why post-finalization or unconditional
generation was rejected.

- [ ] **Step 2: Expand automated and manual test guidance**

In `TESTING.md` and `copilot-manual-test/PROMPT.md`, add four concrete paths:

```text
1. Accept generation for two modules and verify both scoped files.
2. Decline generation and verify finalization plus exact follow-up commands.
3. Interrupt after the first of two modules and resume with /akmaestro-init.
4. Correct a false positive and confirm it is absent from committed evidence.
```

Add subproject assertions that all module candidates, target files, and state
stay below the selected product root. In `WINDOWS-TEST.md`, add a module path
test using `services/payments` in evidence and verify backslash-form
`services\payments` is rejected rather than silently normalized.

- [ ] **Step 3: Update repository status and changelog**

Update `AGENTS.md` implementation status to describe the new module-knowledge
decision and accepted-generation gate. Add an Unreleased changelog entry:

```md
- Reviewed complex-module knowledge generation during `/akmaestro-init`, with
  controller-enforced completion, deterministic scoped targets, and resumable
  per-module evidence.
```

Do not change `pyproject.toml` version `0.6.0`.

- [ ] **Step 4: Run focused tests**

Run:

```bash
uv run pytest -q tests/test_state.py tests/test_installer.py
```

Expected: all tests pass.

- [ ] **Step 5: Run formatting and static checks**

Run:

```bash
uv run ruff check src tests
uv run ruff format --check src tests
git diff --check
```

Expected: every command exits `0` with no formatting or whitespace errors.

- [ ] **Step 6: Run the full suite**

Run:

```bash
uv run pytest -q
```

Expected: all available-platform tests pass; hook tests may skip only when their
required shell is unavailable.

- [ ] **Step 7: Build and inspect the wheel**

Run:

```bash
rm -rf dist
uv build --wheel
python -m zipfile -l dist/akmaestro-0.6.0-py3-none-any.whl
```

Expected: the wheel contains the updated state controller, setup evidence
schema, instructions evidence example, four updated skills, and state protocol.

- [ ] **Step 8: Smoke-test the installed wheel in both installation modes**

Use a temporary Git root, install the built wheel into an isolated virtual
environment, and run:

```bash
smoke_root="$(mktemp -d)"
trap 'rm -rf "$smoke_root"' EXIT
git init -q "$smoke_root/repository"
git init -q "$smoke_root/monorepo"
mkdir -p "$smoke_root/repository/services/payments"
mkdir -p "$smoke_root/monorepo/products/payments/services/payments"
uv venv "$smoke_root/venv"
uv pip install \
  --python "$smoke_root/venv/bin/python" \
  dist/akmaestro-0.6.0-py3-none-any.whl
"$smoke_root/venv/bin/akmaestro" init --path "$smoke_root/repository"
"$smoke_root/venv/bin/akmaestro" init \
  --subproject \
  --path "$smoke_root/monorepo/products/payments"
python -c \
  'import json,sys; open(sys.argv[1], "w", encoding="utf-8").write(json.dumps({"modules": ["services/payments"]}))' \
  "$smoke_root/module-paths.json"
python "$smoke_root/repository/.agentic/bin/akmaestro-state.py" \
  --root "$smoke_root/repository" \
  module-targets \
  --input "$smoke_root/module-paths.json"
python "$smoke_root/monorepo/products/payments/.agentic/bin/akmaestro-state.py" \
  --root "$smoke_root/monorepo/products/payments" \
  module-targets \
  --input "$smoke_root/module-paths.json"
test ! -e "$smoke_root/monorepo/.agentic"
test ! -e "$smoke_root/monorepo/.github"
```

For each installation, invoke the copied controller's `module-targets` command
with `{"modules":["services/payments"]}` and expect a target below that
installation's `.github/instructions/`. Confirm the enclosing Git root receives
no subproject AKMaestro artifacts.

- [ ] **Step 9: Audit Markdown and artifact consistency**

Search for stale claims:

```bash
rg -n "pending module-scoped files are warnings|pendingModules|moduleKnowledge|module-targets" README.md AGENTS.md CHANGELOG.md docs TESTING.md WINDOWS-TEST.md copilot-manual-test src/akmaestro/assets
```

Expected: every pending-module statement distinguishes `generate_now` from
`defer`; all evidence examples include `moduleKnowledge`; all scoped-artifact
guidance uses product-relative POSIX paths.

- [ ] **Step 10: Commit documentation after all validation passes**

```bash
git add README.md docs/setup-flow.md docs/setup-flow-decisions.md docs/init-topics/instruction-files.md TESTING.md WINDOWS-TEST.md copilot-manual-test/PROMPT.md AGENTS.md CHANGELOG.md
git commit -m "Document init module knowledge workflow"
```

- [ ] **Step 11: Final repository review**

Run:

```bash
git status --short --branch
git log -7 --oneline --decorate
```

Expected: the worktree is clean and the branch contains one focused commit for
each implemented responsibility after the design and plan commits.
