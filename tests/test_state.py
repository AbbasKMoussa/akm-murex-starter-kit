"""Contract and transition tests for the bundled state controller."""

import copy
import hashlib
import json
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator, FormatChecker, ValidationError

from akmaestro import installer, state


SCHEMA_DIR = (
    Path(__file__).resolve().parent.parent / "src" / "akmaestro" / "assets" / "schemas"
)
INSTRUCTIONS_EXAMPLE = (
    SCHEMA_DIR.parent
    / "skills"
    / "setup-instructions"
    / "references"
    / "instructions-evidence.example.json"
)


def _requirements_body(artifact_path=".agentic/local/graphs/main/graph.json"):
    return {
        "tools": [
            {
                "id": tool_id,
                "label": tool_id,
                "required": True,
                "probe": {"command": [sys.executable, "--version"]},
            }
            for tool_id in ("uv", "graphify", "graphify-query", "lsp-test")
        ],
        "artifacts": [
            {
                "id": "graphify-graph",
                "path": artifact_path,
                "required": True,
                "remediation": {
                    "command": [
                        "graphify",
                        "extract",
                        ".",
                        "--out",
                        ".agentic/local/graphs/main",
                    ],
                    "cwd": ".",
                    "timeoutSeconds": 300,
                },
            }
        ],
    }


def _configured_command(label):
    return {
        "status": "configured",
        "actions": [
            {
                "label": label,
                "command": [sys.executable, "--version"],
                "cwd": ".",
                "timeoutSeconds": 30,
            }
        ],
        "sources": ["pyproject.toml", "team-lead confirmation"],
    }


def _not_applicable(reason):
    return {
        "status": "not_applicable",
        "reason": reason,
        "sources": ["team-lead confirmation"],
    }


def _undefined_policy(reason="No formal repository convention"):
    return {
        "status": "none",
        "reason": reason,
        "sources": ["team-lead confirmation"],
    }


def _action_check(root, action):
    return state.check_instruction_action(root, action)


def _passed_result(root, command):
    return {
        "status": "passed",
        "detail": "Every configured action exited 0",
        "checks": [_action_check(root, action) for action in command["actions"]],
    }


def _instructions_evidence(root, blocked_command=None):
    commands = {
        "bootstrap": _configured_command("Bootstrap dependencies"),
        "build": _configured_command("Build"),
        "test": _configured_command("Run tests"),
        "lint": _not_applicable("No linter is configured"),
        "typecheck": _not_applicable("No separate typecheck is configured"),
        "run": _not_applicable("This fixture is a library with no local server"),
        "verify": _configured_command("Run full verification"),
    }
    if blocked_command:
        commands[blocked_command]["actions"][0]["command"] = [
            "akmaestro-command-that-does-not-exist"
        ]
    results = {
        "bootstrap": {
            "status": "documented",
            "detail": "Confirmed; no install needed",
            "checks": [],
        },
        "build": _passed_result(root, commands["build"]),
        "test": _passed_result(root, commands["test"]),
        "lint": {
            "status": "not_applicable",
            "detail": "No linter is configured",
            "checks": [],
        },
        "typecheck": {
            "status": "not_applicable",
            "detail": "No separate typecheck is configured",
            "checks": [],
        },
        "run": {
            "status": "not_applicable",
            "detail": "This fixture is a library with no local server",
            "checks": [],
        },
        "verify": _passed_result(root, commands["verify"]),
    }
    if blocked_command:
        results[blocked_command] = {
            "status": "blocked",
            "detail": "Organization policy prevented the command",
            "checks": [_action_check(root, commands[blocked_command]["actions"][0])],
        }
    return {
        "product": {
            "summary": "A fixture repository used to verify AKMaestro workflow state.",
            "consumers": ["AKMaestro controller tests"],
            "primaryWorkflows": ["Exercise setup and feature transitions"],
            "sources": ["README.md", "team-lead confirmation"],
        },
        "commands": commands,
        "commandResults": results,
        "manualVerification": {
            "status": "configured",
            "steps": ["Inspect the generated state and expected test result"],
            "sources": ["team-lead confirmation"],
        },
        "gitWorkflow": {
            "baseBranch": "main",
            "policies": {
                policy: _undefined_policy() for policy in state.INSTRUCTION_GIT_POLICIES
            },
            "sources": ["git configuration", "team-lead confirmation"],
        },
        "repositoryContext": {
            "ciNotes": ["Run the test suite on supported Python versions"],
            "complexModules": [],
            "siblingRepositories": [],
            "restrictedPaths": [],
        },
        "moduleKnowledge": {"decision": "not_applicable"},
        "generatedFiles": list(state.INSTRUCTION_FILES),
        "pendingModules": [],
    }


def _write_instruction_artifacts(root):
    (root / ".github" / "instructions").mkdir(parents=True, exist_ok=True)
    headings = "\n\n".join(
        f"## {heading}\n\nConfigured for controller tests."
        for heading in state.INSTRUCTION_HEADINGS
    )
    (root / "AGENTS.md").write_text(f"# AGENTS.md\n\n{headings}\n", encoding="utf-8")
    (root / ".github" / "copilot-instructions.md").write_text(
        "# GitHub Copilot Instructions\n\nUse `AGENTS.md` as the source of truth.\n",
        encoding="utf-8",
    )
    (root / ".github" / "instructions" / "tests.instructions.md").write_text(
        '---\napplyTo: "**/tests/**"\n---\n\n# Test Instructions\n\nRun the configured test action.\n',
        encoding="utf-8",
    )


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


def _advance_setup(root: Path, topic: str, terminal: str = "complete"):
    current = state._read_json(state._setup_path(root))
    state.setup_transition(
        root, topic, "in_progress", expected_revision=current["revision"]
    )
    if terminal in {"complete", "blocked"}:
        evidence_path = root / ".agentic" / "setup" / f"{topic}-state.json"
        if not evidence_path.exists():
            if topic == "instructions":
                _write_instruction_artifacts(root)
                blocked = "build" if terminal == "blocked" else None
                state.write_topic_evidence(
                    root, topic, _instructions_evidence(root, blocked_command=blocked)
                )
            elif topic == "tooling":
                if not state._requirements_path(root).exists():
                    state.write_requirements(root, _requirements_body())
                graph = root / ".agentic" / "local" / "graphs" / "main" / "graph.json"
                if terminal == "complete":
                    graph.parent.mkdir(parents=True, exist_ok=True)
                    graph.write_text("{}", encoding="utf-8")
                state.write_topic_evidence(
                    root,
                    topic,
                    {
                        "languages": ["test"],
                        "graphify": {
                            "status": "verified"
                            if terminal == "complete"
                            else "blocked",
                            "version": "test-version",
                            "queryStatus": "passed"
                            if terminal == "complete"
                            else "blocked",
                            "graphPaths": [".agentic/local/graphs/main/graph.json"],
                            "detail": "Fixture Graphifyy check",
                        },
                        "lsps": [
                            {
                                "language": "test",
                                "toolId": "lsp-test",
                                "status": "verified",
                                "detail": "Fixture LSP check",
                            }
                        ],
                        "requirementsRevision": 0,
                        "newSessionRequired": False,
                        "blockers": []
                        if terminal == "complete"
                        else ["Graph unavailable"],
                    },
                )
            elif topic == "skills":
                for skill in state.REQUIRED_SKILLS:
                    path = root / ".github" / "skills" / skill / "SKILL.md"
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_text(
                        f"---\nname: {skill}\ndescription: Fixture\n---\n",
                        encoding="utf-8",
                    )
                state.write_topic_evidence(
                    root,
                    topic,
                    {
                        "kitVersion": "test",
                        "expectedSkills": list(state.REQUIRED_SKILLS),
                        "verifiedSkills": list(state.REQUIRED_SKILLS),
                        "collisions": [],
                        "discovery": {"copilotCli": "verified", "vsCode": "not_tested"},
                        "newSessionRequired": False,
                        "blockers": [],
                    },
                )
            elif topic == "hooks":
                config = root / ".github" / "hooks" / "hooks.json"
                config.parent.mkdir(parents=True, exist_ok=True)
                config.write_text('{"version":1,"disableAllHooks":false,"hooks":{}}\n')
                state.write_topic_evidence(
                    root,
                    topic,
                    {
                        "enabled": True,
                        "selectedHooks": ["restricted-path"],
                        "configPath": ".github/hooks/hooks.json",
                        "checks": [
                            {
                                "id": "restricted-path",
                                "status": "passed",
                                "detail": "allow and deny",
                            }
                        ],
                        "verifiedSurfaces": ["copilot-cli"],
                        "blockers": [],
                    },
                )
    current = state._read_json(state._setup_path(root))
    reason = "organization policy" if terminal == "blocked" else None
    return state.setup_transition(
        root,
        topic,
        terminal,
        reason=reason,
        expected_revision=current["revision"],
    )


def _ready_repo(root: Path):
    state.setup_init(root)
    for topic in ("instructions", "tooling", "skills"):
        _advance_setup(root, topic)
    _advance_setup(root, "hooks", "skipped")
    current = state._read_json(state._setup_path(root))
    state.finalize_setup(root, expected_revision=current["revision"])
    readiness, ready = state.check_readiness(root)
    assert ready


def _write_feature_artifact(root: Path, feature_id: str, relative: str):
    path = root / ".agentic" / "features" / feature_id / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"# {relative}\n", encoding="utf-8")


def test_setup_state_is_derived_and_blocked_mandatory_topics_can_complete(tmp_path):
    created = state.setup_init(tmp_path)
    assert created["version"] == 3
    assert "overall" not in created
    assert "currentStep" not in created
    initial = state.setup_summary(created)
    assert initial["nextTopic"] == "instructions"
    assert initial["nextCommand"] == "/akmaestro-init"

    _advance_setup(tmp_path, "instructions")
    _advance_setup(tmp_path, "tooling", "blocked")
    _advance_setup(tmp_path, "skills")
    _advance_setup(tmp_path, "hooks", "skipped")

    current = state._read_json(state._setup_path(tmp_path))
    summary = state.setup_summary(current)
    assert summary["topicsComplete"]
    assert summary["overall"] == "incomplete"
    assert summary["nextCommand"] == "/akmaestro-init"
    assert current["topics"]["tooling"]["blocker"] == "organization policy"
    finalized = state.finalize_setup(tmp_path, expected_revision=current["revision"])
    assert finalized["overall"] == "complete"
    assert finalized["blockedItems"]


def test_finalization_is_idempotent_and_requires_consent_for_unowned_guide(tmp_path):
    state.setup_init(tmp_path)
    for topic in ("instructions", "tooling", "skills"):
        _advance_setup(tmp_path, topic)
    _advance_setup(tmp_path, "hooks", "skipped")
    current = state._read_json(state._setup_path(tmp_path))
    guide = tmp_path / ".github" / "AGENTIC.md"
    guide.write_text("# Existing team-authored guide\n", encoding="utf-8")

    preview = state.finalize_setup(
        tmp_path, expected_revision=current["revision"], preview=True
    )
    assert preview["preview"] is True
    assert preview["wouldWrite"] is True
    assert "-# Existing team-authored guide" in preview["diff"]
    assert guide.read_text(encoding="utf-8") == "# Existing team-authored guide\n"
    assert state._read_json(state._setup_path(tmp_path)) == current

    with pytest.raises(state.StateError, match="not owned by this setup state"):
        state.finalize_setup(tmp_path, expected_revision=current["revision"])
    assert guide.read_text(encoding="utf-8") == "# Existing team-authored guide\n"

    first = state.finalize_setup(
        tmp_path,
        expected_revision=current["revision"],
        approved_guide_replace=True,
    )
    second = state.finalize_setup(tmp_path, expected_revision=999)
    assert first == second
    assert first["overall"] == "complete"


def test_reopened_setup_preserves_controller_guide_ownership(tmp_path):
    _ready_repo(tmp_path)
    before = state._read_json(state._setup_path(tmp_path))
    old_hash = before["finalization"]["guideHash"]
    state.setup_transition(
        tmp_path, "skills", "in_progress", expected_revision=before["revision"]
    )
    pending = state._read_json(state._setup_path(tmp_path))
    assert pending["finalization"]["previousGuideHash"] == old_hash
    state.setup_transition(
        tmp_path, "skills", "complete", expected_revision=pending["revision"]
    )
    pending = state._read_json(state._setup_path(tmp_path))
    finalized = state.finalize_setup(tmp_path, expected_revision=pending["revision"])
    assert finalized["overall"] == "complete"


def test_merge_plan_requires_approval_and_rejects_changed_preimage(tmp_path):
    target = tmp_path / "AGENTS.md"
    target.write_text("before\n", encoding="utf-8")
    proposed = tmp_path / "proposed.md"
    proposed.write_text("after\n", encoding="utf-8")
    plan = state.create_merge_plan(tmp_path, "AGENTS.md", str(proposed))
    assert "-before" in plan["diff"] and "+after" in plan["diff"]

    with pytest.raises(state.StateError, match="explicit --approved"):
        state.apply_merge_plan(tmp_path, plan["planId"], approved=False)
    target.write_text("changed after review\n", encoding="utf-8")
    with pytest.raises(state.StateError, match="changed after review"):
        state.apply_merge_plan(tmp_path, plan["planId"], approved=True)

    replacement = state.create_merge_plan(tmp_path, "AGENTS.md", str(proposed))
    result = state.apply_merge_plan(tmp_path, replacement["planId"], approved=True)
    assert result["applied"] is True
    assert target.read_text(encoding="utf-8") == "after\n"


def test_merge_target_rejects_lexical_traversal(tmp_path):
    proposed = tmp_path / "proposed.md"
    proposed.write_text("# Proposed\n", encoding="utf-8")

    with pytest.raises(state.StateError, match="traversal segments"):
        state.create_merge_plan(
            tmp_path,
            ".github/instructions/../../pyproject.toml",
            str(proposed),
        )


def test_merge_plan_identifier_binds_reviewed_content(tmp_path):
    target = tmp_path / "AGENTS.md"
    target.write_text("before\n", encoding="utf-8")
    proposed = tmp_path / "proposed.md"
    proposed.write_text("after\n", encoding="utf-8")
    plan = state.create_merge_plan(tmp_path, "AGENTS.md", str(proposed))
    plan_path = state._merge_plans_dir(tmp_path) / f"{plan['planId']}.json"
    tampered = json.loads(plan_path.read_text(encoding="utf-8"))
    tampered["proposedContent"] = "tampered\n"
    tampered["proposedHash"] = hashlib.sha256(b"tampered\n").hexdigest()
    plan_path.write_text(json.dumps(tampered), encoding="utf-8")

    with pytest.raises(state.StateError, match="identifier does not match"):
        state.apply_merge_plan(tmp_path, plan["planId"], approved=True)
    assert target.read_text(encoding="utf-8") == "before\n"


def test_hook_controller_preserves_explicit_consent_in_manifest(tmp_path):
    config = tmp_path / ".github" / "hooks" / "hooks.json"
    config.parent.mkdir(parents=True)
    config.write_text(
        json.dumps({"version": 1, "disableAllHooks": True, "hooks": {}}),
        encoding="utf-8",
    )
    manifest = tmp_path / ".agentic" / "setup" / "kit-manifest.json"
    manifest.parent.mkdir(parents=True)
    manifest.write_text(
        json.dumps({"version": 1, "files": {}, "hooks_enabled": False}),
        encoding="utf-8",
    )

    assert state.set_hooks_enabled(tmp_path, True)["enabled"] is True
    stored = json.loads(manifest.read_text(encoding="utf-8"))
    assert stored["hooks_enabled"] is True
    assert stored["files"] == {}
    assert state.set_hooks_enabled(tmp_path, False)["enabled"] is False


def test_setup_rejects_illegal_and_stale_transitions_but_replay_is_idempotent(tmp_path):
    state.setup_init(tmp_path)
    with pytest.raises(state.StateError, match="illegal setup transition"):
        state.setup_transition(
            tmp_path, "instructions", "complete", expected_revision=0
        )

    first = state.setup_transition(
        tmp_path, "instructions", "in_progress", expected_revision=0
    )
    replay = state.setup_transition(
        tmp_path, "instructions", "in_progress", expected_revision=0
    )
    assert replay["revision"] == first["revision"]

    with pytest.raises(state.StateError, match="stale state"):
        state.setup_transition(tmp_path, "tooling", "in_progress", expected_revision=0)
    with pytest.raises(state.StateError, match="requires --reason"):
        state.setup_transition(tmp_path, "instructions", "blocked")


def test_state_lock_serializes_competing_expected_revisions(tmp_path):
    state.setup_init(tmp_path)

    def transition(topic):
        try:
            return state.setup_transition(
                tmp_path, topic, "in_progress", expected_revision=0
            )["revision"]
        except state.StateError as exc:
            return str(exc)

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(transition, ("instructions", "tooling")))

    assert 1 in results
    assert any(
        isinstance(result, str) and "stale state" in result for result in results
    )


def test_topic_evidence_and_requirements_writes_are_idempotent(tmp_path):
    _write_instruction_artifacts(tmp_path)
    body = _instructions_evidence(tmp_path)
    evidence = state.write_topic_evidence(tmp_path, "instructions", body)
    replay = state.write_topic_evidence(
        tmp_path,
        "instructions",
        body,
        expected_revision=99,
    )
    assert evidence == replay

    requirements_body = _requirements_body()
    requirements = state.write_requirements(tmp_path, requirements_body)
    assert requirements["revision"] == 0
    assert (
        state.write_requirements(tmp_path, requirements_body, expected_revision=50)
        == requirements
    )


def test_instruction_evidence_rejects_incomplete_or_unsafe_answers(tmp_path):
    _write_instruction_artifacts(tmp_path)

    invalid = copy.deepcopy(_instructions_evidence(tmp_path))
    del invalid["product"]["summary"]
    with pytest.raises(
        state.StateError, match="product is missing required fields: summary"
    ):
        state.write_topic_evidence(tmp_path, "instructions", invalid)

    invalid = copy.deepcopy(_instructions_evidence(tmp_path))
    invalid["commands"]["build"]["actions"][0]["command"] = "python -m build"
    with pytest.raises(state.StateError, match="non-empty argument array"):
        state.write_topic_evidence(tmp_path, "instructions", invalid)

    invalid = copy.deepcopy(_instructions_evidence(tmp_path))
    del invalid["commands"]["lint"]["reason"]
    with pytest.raises(
        state.StateError, match="commands.lint is missing required fields: reason"
    ):
        state.write_topic_evidence(tmp_path, "instructions", invalid)

    invalid = copy.deepcopy(_instructions_evidence(tmp_path))
    del invalid["gitWorkflow"]["policies"]["directPush"]
    with pytest.raises(state.StateError, match="every canonical Git policy"):
        state.write_topic_evidence(tmp_path, "instructions", invalid)

    invalid = copy.deepcopy(_instructions_evidence(tmp_path))
    invalid["commandResults"]["build"]["checks"] = []
    with pytest.raises(state.StateError, match="passing check for every action"):
        state.write_topic_evidence(tmp_path, "instructions", invalid)

    invalid = copy.deepcopy(_instructions_evidence(tmp_path))
    invalid["commandResults"]["test"]["checks"][0]["actionHash"] = "0" * 64
    with pytest.raises(state.StateError, match="substituted action hash"):
        state.write_topic_evidence(tmp_path, "instructions", invalid)

    invalid = copy.deepcopy(_instructions_evidence(tmp_path))
    invalid["commandResults"]["build"]["status"] = "blocked"
    invalid["commandResults"]["build"]["checks"] = []
    with pytest.raises(state.StateError, match="requires a failed controller check"):
        state.write_topic_evidence(tmp_path, "instructions", invalid)


def test_all_topic_evidence_contracts_reject_empty_objects():
    validators = (
        state.validate_instructions_evidence,
        state.validate_tooling_evidence,
        state.validate_skills_evidence,
        state.validate_hooks_evidence,
    )
    for validator in validators:
        with pytest.raises(state.StateError, match="missing required fields"):
            validator({})


def test_instruction_evidence_must_match_controller_action_ledger(tmp_path):
    _write_instruction_artifacts(tmp_path)
    invalid = _instructions_evidence(tmp_path)
    invalid["commandResults"]["build"]["checks"][0]["checkId"] = "0" * 32

    with pytest.raises(state.StateError, match="does not match the controller ledger"):
        state.write_topic_evidence(tmp_path, "instructions", invalid)


def test_bundled_instruction_evidence_example_matches_controller_and_schema():
    evidence = json.loads(INSTRUCTIONS_EXAMPLE.read_text(encoding="utf-8"))
    state.validate_instructions_evidence(evidence)
    envelope = {
        "$schema": "../schemas/setup-evidence.schema.json",
        "version": 3,
        "revision": 0,
        "topic": "instructions",
        "evidence": evidence,
        "createdAt": "2026-07-17T00:00:00Z",
        "updatedAt": "2026-07-17T00:00:00Z",
    }
    schema = json.loads(
        (SCHEMA_DIR / "setup-evidence.schema.json").read_text(encoding="utf-8")
    )
    Draft202012Validator(schema, format_checker=FormatChecker()).validate(envelope)


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
    with pytest.raises(
        state.StateError, match="not_applicable requires no complex modules"
    ):
        state.validate_instructions_evidence(body)


@pytest.mark.parametrize(
    "module_path",
    (
        "../outside",
        "services/../outside",
        "/absolute",
        "C:/absolute",
        r"services\payments",
    ),
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
    target = tmp_path / ".github" / "instructions" / "services-payments.instructions.md"
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
        "services/payments": (".github/instructions/services-payments.instructions.md"),
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

    with pytest.raises(
        state.StateError, match="instructions directory resolves outside"
    ):
        state.module_instruction_targets(tmp_path, ["services/payments"])


def test_module_targets_cli_prints_derived_targets(tmp_path, capsys):
    module_path = tmp_path / "module-paths.json"
    module_path.write_text(
        json.dumps({"modules": ["services/payments"]}),
        encoding="utf-8",
    )

    assert (
        state.main(
            [
                "--root",
                str(tmp_path),
                "module-targets",
                "--input",
                str(module_path),
            ]
        )
        == 0
    )
    assert json.loads(capsys.readouterr().out) == {
        "targets": {
            "services/payments": (
                ".github/instructions/services-payments.instructions.md"
            )
        }
    }


def test_instruction_action_check_uses_argument_arrays_without_a_shell(tmp_path):
    action = {
        "command": [
            sys.executable,
            "-c",
            "import sys; assert sys.argv[1] == 'literal;not-a-shell-command'",
            "literal;not-a-shell-command",
        ],
        "cwd": ".",
        "timeoutSeconds": 30,
    }
    checked = state.check_instruction_action(tmp_path, action)
    assert checked["status"] == "passed"
    assert checked["actionHash"] == state.instruction_action_hash(action)
    assert checked["checkedAt"].endswith("Z")
    missing = state.check_instruction_action(
        tmp_path,
        {"command": ["akmaestro-command-that-does-not-exist"], "timeoutSeconds": 1},
    )
    assert missing["status"] == "failed"
    assert "command not found" in missing["detail"]


def test_instruction_action_ledger_does_not_persist_command_output(tmp_path):
    secret = "AKMAESTRO-COMMAND-OUTPUT-SECRET"
    checked = state.check_instruction_action(
        tmp_path,
        {"command": [sys.executable, "-c", f"print({secret!r})"]},
    )
    assert checked["status"] == "passed"
    assert secret not in checked["detail"]
    assert secret not in state._action_checks_path(tmp_path).read_text(encoding="utf-8")


def test_instruction_action_check_cli_returns_distinct_failure_code(tmp_path, capsys):
    action_path = tmp_path / "action.json"
    action_path.write_text(
        json.dumps({"command": ["akmaestro-command-that-does-not-exist"]}),
        encoding="utf-8",
    )
    assert (
        state.main(
            [
                "--root",
                str(tmp_path),
                "action-check",
                "--input",
                str(action_path),
            ]
        )
        == 4
    )
    assert json.loads(capsys.readouterr().out)["status"] == "failed"


def test_action_checks_and_readiness_reject_symlink_escapes(tmp_path):
    outside = tmp_path.parent / f"{tmp_path.name}-outside"
    outside.mkdir()
    (outside / "artifact.json").write_text("{}", encoding="utf-8")
    (tmp_path / "escape").symlink_to(outside, target_is_directory=True)

    with pytest.raises(state.StateError, match="outside declared"):
        state.check_instruction_action(
            tmp_path,
            {"command": [sys.executable, "--version"], "cwd": "escape"},
        )

    state.write_requirements(tmp_path, _requirements_body("escape/artifact.json"))
    with pytest.raises(state.StateError, match="outside declared"):
        state.check_readiness(tmp_path)


def test_sibling_declarations_cannot_expand_workspace_with_traversal(tmp_path):
    _write_instruction_artifacts(tmp_path)
    invalid = _instructions_evidence(tmp_path)
    invalid["repositoryContext"]["siblingRepositories"] = [
        {
            "path": "../../",
            "role": "modifiable",
            "purpose": "Invalid broad workspace",
            "integration": "Not applicable",
        }
    ]
    with pytest.raises(state.StateError, match="must identify a sibling"):
        state.write_topic_evidence(tmp_path, "instructions", invalid)


def test_instruction_evidence_requires_automated_or_manual_verification(tmp_path):
    _write_instruction_artifacts(tmp_path)
    invalid = copy.deepcopy(_instructions_evidence(tmp_path))
    invalid["commands"]["verify"] = _not_applicable("No automated verification")
    invalid["commandResults"]["verify"] = {
        "status": "not_applicable",
        "detail": "No automated verification",
        "checks": [],
    }
    invalid["manualVerification"] = {
        "status": "not_applicable",
        "reason": "No manual verification",
        "sources": ["team-lead confirmation"],
    }
    with pytest.raises(state.StateError, match="automated or manual verification path"):
        state.write_topic_evidence(tmp_path, "instructions", invalid)


def test_instruction_artifacts_must_exist_and_contain_no_placeholders(tmp_path):
    _write_instruction_artifacts(tmp_path)
    agents = tmp_path / "AGENTS.md"
    agents.write_text(agents.read_text() + "\n<build command>\n", encoding="utf-8")
    with pytest.raises(state.StateError, match="still contains AKMaestro placeholder"):
        state.write_topic_evidence(
            tmp_path, "instructions", _instructions_evidence(tmp_path)
        )

    _write_instruction_artifacts(tmp_path)
    (tmp_path / ".github" / "instructions" / "tests.instructions.md").unlink()
    with pytest.raises(
        state.StateError, match="must be written before advancing state"
    ):
        state.write_topic_evidence(
            tmp_path, "instructions", _instructions_evidence(tmp_path)
        )


def test_valid_module_artifact_is_accepted(tmp_path):
    _write_instruction_artifacts(tmp_path)
    (tmp_path / "services" / "payments").mkdir(parents=True)
    body = _instructions_evidence(tmp_path)
    body["repositoryContext"]["complexModules"] = [
        {"path": "services/payments", "purpose": "Payment processing"}
    ]
    body["moduleKnowledge"] = {"decision": "generate_now"}
    target = state.module_instruction_targets(tmp_path, ["services/payments"])[
        "services/payments"
    ]
    _write_module_instruction(tmp_path, target, "services/payments")
    body["generatedFiles"].append(target)
    body["pendingModules"] = []

    written = state.write_topic_evidence(tmp_path, "instructions", body)

    assert written["evidence"]["pendingModules"] == []


def test_module_artifact_claim_requires_existing_scoped_file(tmp_path):
    _write_instruction_artifacts(tmp_path)
    body = _instructions_evidence(tmp_path)
    body["repositoryContext"]["complexModules"] = [
        {"path": "services/payments", "purpose": "Payment processing"}
    ]
    body["moduleKnowledge"] = {"decision": "generate_now"}
    target = state.module_instruction_targets(tmp_path, ["services/payments"])[
        "services/payments"
    ]
    body["generatedFiles"].append(target)

    with pytest.raises(state.StateError, match="must be written before advancing"):
        state.write_topic_evidence(tmp_path, "instructions", body)

    artifact = tmp_path / target
    artifact.write_text("# Payments\n", encoding="utf-8")
    with pytest.raises(state.StateError, match="must contain applyTo"):
        state.write_topic_evidence(tmp_path, "instructions", body)


def test_module_artifact_requires_exact_apply_to(tmp_path):
    _write_instruction_artifacts(tmp_path)
    body = _instructions_evidence(tmp_path)
    body["repositoryContext"]["complexModules"] = [
        {"path": "services/payments", "purpose": "Payment processing"}
    ]
    body["moduleKnowledge"] = {"decision": "generate_now"}
    target = state.module_instruction_targets(tmp_path, ["services/payments"])[
        "services/payments"
    ]
    _write_module_instruction(tmp_path, target, "services/payments")
    artifact = tmp_path / target
    artifact.write_text(
        artifact.read_text(encoding="utf-8").replace(
            'applyTo: "services/payments/**"',
            'applyTo: "services/orders/**"',
        ),
        encoding="utf-8",
    )
    body["generatedFiles"].append(target)

    with pytest.raises(state.StateError, match="must use applyTo"):
        state.write_topic_evidence(tmp_path, "instructions", body)


def test_module_artifact_requires_all_sections(tmp_path):
    _write_instruction_artifacts(tmp_path)
    body = _instructions_evidence(tmp_path)
    body["repositoryContext"]["complexModules"] = [
        {"path": "services/payments", "purpose": "Payment processing"}
    ]
    body["moduleKnowledge"] = {"decision": "generate_now"}
    target = state.module_instruction_targets(tmp_path, ["services/payments"])[
        "services/payments"
    ]
    _write_module_instruction(tmp_path, target, "services/payments")
    artifact = tmp_path / target
    artifact.write_text(
        artifact.read_text(encoding="utf-8").replace(
            "## Pitfalls", "## Operational Traps"
        ),
        encoding="utf-8",
    )
    body["generatedFiles"].append(target)

    with pytest.raises(state.StateError, match="missing required section: Pitfalls"):
        state.write_topic_evidence(tmp_path, "instructions", body)


def test_module_artifact_rejects_akmaestro_placeholders(tmp_path):
    _write_instruction_artifacts(tmp_path)
    body = _instructions_evidence(tmp_path)
    body["repositoryContext"]["complexModules"] = [
        {"path": "services/payments", "purpose": "Payment processing"}
    ]
    body["moduleKnowledge"] = {"decision": "generate_now"}
    target = state.module_instruction_targets(tmp_path, ["services/payments"])[
        "services/payments"
    ]
    _write_module_instruction(tmp_path, target, "services/payments")
    artifact = tmp_path / target
    artifact.write_text(
        artifact.read_text(encoding="utf-8")
        + "\n<module paths needing scoped instructions>\n",
        encoding="utf-8",
    )
    body["generatedFiles"].append(target)

    with pytest.raises(state.StateError, match="placeholder"):
        state.write_topic_evidence(tmp_path, "instructions", body)


def test_completed_module_instruction_must_be_listed_as_generated(tmp_path):
    _write_instruction_artifacts(tmp_path)
    body = _instructions_evidence(tmp_path)
    body["repositoryContext"]["complexModules"] = [
        {"path": "services/payments", "purpose": "Payment processing"}
    ]
    body["moduleKnowledge"] = {"decision": "generate_now"}

    with pytest.raises(
        state.StateError, match="completed module instruction is missing"
    ):
        state.write_topic_evidence(tmp_path, "instructions", body)


def test_pending_module_cannot_be_listed_as_generated(tmp_path):
    _write_instruction_artifacts(tmp_path)
    body = _instructions_evidence(tmp_path)
    body["repositoryContext"]["complexModules"] = [
        {"path": "services/payments", "purpose": "Payment processing"}
    ]
    body["moduleKnowledge"] = {"decision": "generate_now"}
    body["pendingModules"] = ["services/payments"]
    target = state.module_instruction_targets(tmp_path, ["services/payments"])[
        "services/payments"
    ]
    _write_module_instruction(tmp_path, target, "services/payments")
    body["generatedFiles"].append(target)

    with pytest.raises(
        state.StateError, match="pending module cannot be listed as generated"
    ):
        state.write_topic_evidence(tmp_path, "instructions", body)


def test_complex_module_artifact_rejects_product_boundary_escape(tmp_path):
    _write_instruction_artifacts(tmp_path)
    outside = tmp_path.parent / f"{tmp_path.name}-outside-module"
    outside.mkdir()
    module = tmp_path / "services" / "payments"
    module.parent.mkdir()
    try:
        module.symlink_to(outside, target_is_directory=True)
    except OSError:
        pytest.skip("directory symlinks are unavailable")
    body = _instructions_evidence(tmp_path)
    body["repositoryContext"]["complexModules"] = [
        {"path": "services/payments", "purpose": "Payment processing"}
    ]
    body["moduleKnowledge"] = {"decision": "generate_now"}

    with pytest.raises(state.StateError, match="complex module resolves outside"):
        state.write_topic_evidence(tmp_path, "instructions", body)


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

    current = state._read_json(state._setup_path(tmp_path))
    assert current["revision"] == 1
    assert current["topics"]["instructions"]["status"] == "in_progress"


def test_generate_now_completes_after_all_modules_are_generated(tmp_path):
    state.setup_init(tmp_path)
    state.setup_transition(tmp_path, "instructions", "in_progress", expected_revision=0)
    _write_instruction_artifacts(tmp_path)
    body = _instructions_evidence(tmp_path)
    body["moduleKnowledge"] = {"decision": "generate_now"}
    body["repositoryContext"]["complexModules"] = [
        {"path": "services/payments", "purpose": "Payment processing"}
    ]
    target = state.module_instruction_targets(tmp_path, ["services/payments"])[
        "services/payments"
    ]
    _write_module_instruction(tmp_path, target, "services/payments")
    body["generatedFiles"].append(target)
    state.write_topic_evidence(tmp_path, "instructions", body)

    completed = state.setup_transition(
        tmp_path, "instructions", "complete", expected_revision=1
    )

    assert completed["topics"]["instructions"]["status"] == "complete"


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

    for topic in ("tooling", "skills"):
        _advance_setup(tmp_path, topic)
    _advance_setup(tmp_path, "hooks", "skipped")
    current = state._read_json(state._setup_path(tmp_path))
    finalized = state.finalize_setup(
        tmp_path,
        expected_revision=current["revision"],
    )
    assert finalized["overall"] == "complete"
    assert finalized["moduleKnowledge"] == report["moduleKnowledge"]
    assert finalized["pendingItems"] == report["pendingItems"]


def test_partial_module_resume_reports_completed_and_pending_modules(tmp_path):
    state.setup_init(tmp_path)
    state.setup_transition(tmp_path, "instructions", "in_progress", expected_revision=0)
    _write_instruction_artifacts(tmp_path)
    modules = [
        {"path": "services/payments", "purpose": "Payment processing"},
        {"path": "services/orders", "purpose": "Order processing"},
    ]
    body = _instructions_evidence(tmp_path)
    body["moduleKnowledge"] = {"decision": "generate_now"}
    body["repositoryContext"]["complexModules"] = modules
    body["pendingModules"] = [module["path"] for module in modules]
    first = state.write_topic_evidence(tmp_path, "instructions", body)

    target = state.module_instruction_targets(tmp_path, ["services/payments"])[
        "services/payments"
    ]
    _write_module_instruction(tmp_path, target, "services/payments")
    resumed = copy.deepcopy(body)
    resumed["generatedFiles"].append(target)
    resumed["pendingModules"] = ["services/orders"]
    second = state.write_topic_evidence(
        tmp_path,
        "instructions",
        resumed,
        expected_revision=first["revision"],
    )

    report = state.setup_status(tmp_path)
    assert second["revision"] == 1
    assert report["moduleKnowledge"] == {
        "decision": "generate_now",
        "completedModules": ["services/payments"],
        "pendingModules": ["services/orders"],
    }
    assert report["pendingItems"] == [
        {
            "type": "module",
            "path": "services/orders",
            "command": "/setup-instructions module services/orders",
        }
    ]
    assert report["nextCommand"] == "/akmaestro-init"


def test_module_knowledge_decision_can_be_revised_before_completion(tmp_path):
    state.setup_init(tmp_path)
    state.setup_transition(tmp_path, "instructions", "in_progress", expected_revision=0)
    _write_instruction_artifacts(tmp_path)
    body = _instructions_evidence(tmp_path)
    body["moduleKnowledge"] = {"decision": "generate_now"}
    body["repositoryContext"]["complexModules"] = [
        {"path": "services/payments", "purpose": "Payment processing"}
    ]
    body["pendingModules"] = ["services/payments"]
    first = state.write_topic_evidence(tmp_path, "instructions", body)

    deferred = copy.deepcopy(body)
    deferred["moduleKnowledge"] = {"decision": "defer"}
    revised = state.write_topic_evidence(
        tmp_path,
        "instructions",
        deferred,
        expected_revision=first["revision"],
    )
    completed = state.setup_transition(
        tmp_path, "instructions", "complete", expected_revision=1
    )

    assert revised["revision"] == 1
    assert completed["topics"]["instructions"]["status"] == "complete"
    assert state.setup_status(tmp_path)["moduleKnowledge"]["decision"] == "defer"


def test_tampered_terminal_module_generation_is_rejected_by_status_and_validate(
    tmp_path,
):
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
    completed = state.setup_transition(
        tmp_path, "instructions", "complete", expected_revision=1
    )

    evidence_path = tmp_path / ".agentic" / "setup" / "instructions-state.json"
    tampered = json.loads(evidence_path.read_text(encoding="utf-8"))
    tampered["evidence"]["moduleKnowledge"]["decision"] = "generate_now"
    evidence_path.write_text(json.dumps(tampered), encoding="utf-8")

    with pytest.raises(state.StateError, match="accepted module generation"):
        state.setup_transition(
            tmp_path,
            "instructions",
            "complete",
            expected_revision=completed["revision"],
        )
    with pytest.raises(state.StateError, match="accepted module generation"):
        state.setup_status(tmp_path)
    with pytest.raises(state.StateError, match="accepted module generation"):
        state.validate_setup_integrity(tmp_path, completed)
    report = state.validate_all(tmp_path)
    assert report["valid"] is False
    assert any("accepted module generation" in error for error in report["errors"])


def test_blocked_instruction_checks_require_a_blocked_topic_transition(tmp_path):
    state.setup_init(tmp_path)
    state.setup_transition(tmp_path, "instructions", "in_progress", expected_revision=0)
    _write_instruction_artifacts(tmp_path)
    state.write_topic_evidence(
        tmp_path,
        "instructions",
        _instructions_evidence(tmp_path, blocked_command="build"),
    )
    with pytest.raises(state.StateError, match="must transition to blocked"):
        state.setup_transition(
            tmp_path, "instructions", "complete", expected_revision=1
        )
    blocked = state.setup_transition(
        tmp_path,
        "instructions",
        "blocked",
        reason="Build unavailable under organization policy",
        expected_revision=1,
    )
    assert blocked["topics"]["instructions"]["status"] == "blocked"


def test_idempotent_instruction_replay_revalidates_artifacts(tmp_path):
    _write_instruction_artifacts(tmp_path)
    body = _instructions_evidence(tmp_path)
    state.write_topic_evidence(tmp_path, "instructions", body)
    (tmp_path / "AGENTS.md").unlink()
    with pytest.raises(
        state.StateError, match="must be written before advancing state"
    ):
        state.write_topic_evidence(tmp_path, "instructions", body, expected_revision=0)


def test_readiness_is_worktree_local_and_tracks_missing_requirements(tmp_path):
    body = _requirements_body("graph.json")
    body["tools"].append(
        {
            "id": "unavailable-tool",
            "label": "Unavailable tool",
            "required": False,
            "probe": {"command": ["akmaestro-command-that-does-not-exist"]},
            "install": {"command": ["install", "unavailable-tool"]},
        }
    )
    state.write_requirements(tmp_path, body)
    readiness, ready = state.check_readiness(tmp_path)
    assert not ready
    assert readiness["status"] == "not_ready"
    assert state._readiness_path(tmp_path).is_file()

    (tmp_path / "graph.json").write_text("{}", encoding="utf-8")
    readiness, ready = state.check_readiness(tmp_path)
    assert ready
    assert readiness["status"] == "ready"


def test_local_remediation_requires_approval_and_never_invokes_a_shell(tmp_path):
    secret = "AKMAESTRO-REMEDIATION-OUTPUT-SECRET"
    action = {
        "command": [
            sys.executable,
            "-c",
            f"import sys; assert sys.argv[1] == 'literal;not-shell'; print({secret!r})",
            "literal;not-shell",
        ],
        "cwd": ".",
        "timeoutSeconds": 30,
    }
    requirements = _requirements_body()
    requirements["tools"][0]["install"] = action
    state.write_requirements(tmp_path, requirements)
    with pytest.raises(state.StateError, match="explicit --approved"):
        state.run_remediation(tmp_path, action, approved=False)
    with pytest.raises(state.StateError, match="exactly match committed"):
        state.run_remediation(
            tmp_path,
            {**action, "command": [sys.executable, "--version"]},
            approved=True,
        )

    result = state.run_remediation(tmp_path, action, approved=True)
    assert result["status"] == "passed"
    assert secret not in result["detail"]
    assert not state._action_checks_path(tmp_path).exists()


def test_feature_lifecycle_derives_navigation_and_clears_local_selection(tmp_path):
    _ready_repo(tmp_path)
    feature = state.feature_create(tmp_path, "abc-search-filters", "Search filters")
    assert state._feature_summary(feature)["nextCommand"] == "/feature-understand"
    assert not (tmp_path / ".agentic" / "features" / "index.json").exists()

    _write_feature_artifact(tmp_path, "abc-search-filters", "understanding.md")
    feature = state.feature_advance_gate(
        tmp_path, "abc-search-filters", "understand", expected_revision=0
    )
    assert feature["phase"] == "framing"
    _write_feature_artifact(tmp_path, "abc-search-filters", "feature.md")
    feature = state.feature_advance_gate(
        tmp_path, "abc-search-filters", "frame", expected_revision=1
    )
    assert feature["phase"] == "splitting"
    for story_id in ("01-query-parser", "02-facet-ui"):
        _write_feature_artifact(
            tmp_path, "abc-search-filters", f"stories/{story_id}.md"
        )
    feature = state.feature_add_stories(
        tmp_path,
        "abc-search-filters",
        ["01-query-parser", "02-facet-ui"],
        "guided",
        expected_revision=2,
    )
    feature = state.feature_advance_gate(
        tmp_path, "abc-search-filters", "split", expected_revision=3
    )
    assert feature["phase"] == "story_loop"
    assert state._feature_summary(feature)["nextCommand"] == "/story-prime"

    revision = 4
    for story_id in ("01-query-parser", "02-facet-ui"):
        for step in ("plan", "implement", "review", "learn", "complete"):
            feature = state.story_transition(
                tmp_path,
                "abc-search-filters",
                story_id,
                step,
                expected_revision=revision,
            )
            revision += 1

    assert feature["phase"] == "reviewing"
    assert state._feature_summary(feature)["nextCommand"] == "/feature-review"
    _write_feature_artifact(tmp_path, "abc-search-filters", "review.md")
    feature = state.feature_advance_gate(
        tmp_path, "abc-search-filters", "feature-review", expected_revision=revision
    )
    revision += 1
    assert feature["phase"] == "retrospective"
    _write_feature_artifact(tmp_path, "abc-search-filters", "retro.md")
    feature = state.feature_advance_gate(
        tmp_path, "abc-search-filters", "retro", expected_revision=revision
    )
    assert feature["phase"] == "complete"
    assert not state._active_path(tmp_path).exists()


def test_feature_mutation_requires_initialized_repo_and_ready_workstation(tmp_path):
    with pytest.raises(state.StateError, match="team lead must finish /akmaestro-init"):
        state.feature_create(tmp_path, "blocked-feature", "Blocked feature")

    state.setup_init(tmp_path)
    for topic in ("instructions", "tooling", "skills"):
        _advance_setup(tmp_path, topic)
    _advance_setup(tmp_path, "hooks", "skipped")
    state.write_requirements(tmp_path, _requirements_body())
    current = state._read_json(state._setup_path(tmp_path))
    state.finalize_setup(tmp_path, expected_revision=current["revision"])
    (tmp_path / ".agentic" / "local" / "graphs" / "main" / "graph.json").unlink()

    with pytest.raises(state.StateError, match="developer environment is not ready"):
        state.feature_create(tmp_path, "blocked-feature", "Blocked feature")


def test_story_review_send_back_and_feature_review_reopen_are_legal(tmp_path):
    _ready_repo(tmp_path)
    state.feature_create(tmp_path, "review-loop", "Review loop")
    _write_feature_artifact(tmp_path, "review-loop", "understanding.md")
    state.feature_advance_gate(tmp_path, "review-loop", "understand", 0)
    _write_feature_artifact(tmp_path, "review-loop", "feature.md")
    state.feature_advance_gate(tmp_path, "review-loop", "frame", 1)
    _write_feature_artifact(tmp_path, "review-loop", "stories/01-change.md")
    state.feature_add_stories(tmp_path, "review-loop", ["01-change"], "guided", 2)
    state.feature_advance_gate(tmp_path, "review-loop", "split", 3)
    state.story_transition(tmp_path, "review-loop", "01-change", "plan", 4)
    state.story_transition(tmp_path, "review-loop", "01-change", "implement", 5)
    state.story_transition(tmp_path, "review-loop", "01-change", "review", 6)
    sent_back = state.story_transition(
        tmp_path, "review-loop", "01-change", "implement", 7
    )
    assert sent_back["stories"][0]["reviewAttempts"] == 1

    state.story_transition(tmp_path, "review-loop", "01-change", "review", 8)
    state.story_transition(tmp_path, "review-loop", "01-change", "learn", 9)
    state.story_transition(tmp_path, "review-loop", "01-change", "complete", 10)
    reopened = state.story_transition(tmp_path, "review-loop", "01-change", "plan", 11)
    assert reopened["phase"] == "story_loop"
    assert reopened["currentStory"] == "01-change"
    assert reopened["stories"][0]["reviewAttempts"] == 2


def test_story_mode_can_change_only_before_prime(tmp_path):
    _ready_repo(tmp_path)
    state.feature_create(tmp_path, "mode-choice", "Mode choice")
    _write_feature_artifact(tmp_path, "mode-choice", "understanding.md")
    state.feature_advance_gate(tmp_path, "mode-choice", "understand", 0)
    _write_feature_artifact(tmp_path, "mode-choice", "feature.md")
    state.feature_advance_gate(tmp_path, "mode-choice", "frame", 1)
    _write_feature_artifact(tmp_path, "mode-choice", "stories/01-change.md")
    state.feature_add_stories(tmp_path, "mode-choice", ["01-change"], "guided", 2)
    state.feature_advance_gate(tmp_path, "mode-choice", "split", 3)
    changed = state.story_set_mode(
        tmp_path, "mode-choice", "01-change", "autonomous", 4
    )
    assert changed["stories"][0]["mode"] == "autonomous"
    state.story_transition(tmp_path, "mode-choice", "01-change", "plan", 5)
    with pytest.raises(state.StateError, match="only change before"):
        state.story_set_mode(tmp_path, "mode-choice", "01-change", "guided", 6)


def test_validate_reports_stale_local_readiness_and_missing_artifacts(tmp_path):
    state.setup_init(tmp_path)
    graph = tmp_path / ".agentic" / "local" / "graphs" / "main" / "graph.json"
    graph.parent.mkdir(parents=True)
    graph.write_text("{}", encoding="utf-8")
    state.write_requirements(tmp_path, _requirements_body())
    state.check_readiness(tmp_path)
    for topic in ("instructions", "tooling", "skills"):
        _advance_setup(tmp_path, topic)
    _advance_setup(tmp_path, "hooks", "skipped")
    current = state._read_json(state._setup_path(tmp_path))
    state.finalize_setup(tmp_path, expected_revision=current["revision"])
    state.feature_create(tmp_path, "missing-artifact", "Missing artifact")
    _write_feature_artifact(tmp_path, "missing-artifact", "understanding.md")
    state.feature_advance_gate(tmp_path, "missing-artifact", "understand", 0)
    (
        tmp_path / ".agentic" / "features" / "missing-artifact" / "understanding.md"
    ).unlink()

    updated = _requirements_body()
    updated["artifacts"].append({"id": "x", "path": "x", "required": False})
    state.write_requirements(tmp_path, updated, expected_revision=0)
    report = state.validate_all(tmp_path)
    assert not report["valid"]
    assert any("stale requirements revision" in error for error in report["errors"])
    assert any("readiness is stale" in warning for warning in report["warnings"])
    assert any(
        "understanding.md is missing" in warning for warning in report["warnings"]
    )


def test_gate_refuses_to_advance_before_its_artifact_exists(tmp_path):
    _ready_repo(tmp_path)
    state.feature_create(tmp_path, "state-last", "State last")
    with pytest.raises(state.StateError, match="must be written before advancing"):
        state.feature_advance_gate(tmp_path, "state-last", "understand", 0)
    current = state._read_json(state._feature_path(tmp_path, "state-last"))
    assert current["revision"] == 0
    assert current["phase"] == "understanding"


def test_installed_controller_runs_without_importing_the_package(tmp_path):
    import subprocess

    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    installer.init(str(tmp_path), with_hooks=False)
    controller = tmp_path / ".agentic" / "bin" / "akmaestro-state.py"
    namespace = {"__name__": "installed_controller"}
    exec(
        compile(controller.read_text(encoding="utf-8"), str(controller), "exec"),
        namespace,
    )
    assert namespace["STATE_VERSION"] == 3
    for schema in (
        "setup-state.schema.json",
        "setup-evidence.schema.json",
        "action-checks.schema.json",
        "environment-requirements.schema.json",
        "local-readiness.schema.json",
        "feature-state.schema.json",
        "active-feature.schema.json",
    ):
        json.loads(
            (tmp_path / ".agentic" / "schemas" / schema).read_text(encoding="utf-8")
        )


def test_published_schemas_and_controller_instances_are_draft_2020_12(tmp_path):
    schemas = {}
    for path in SCHEMA_DIR.glob("*.json"):
        schema = json.loads(path.read_text(encoding="utf-8"))
        Draft202012Validator.check_schema(schema)
        schemas[path.name] = schema

    _ready_repo(tmp_path)
    state.feature_create(tmp_path, "schema-sample", "Schema sample")
    paths = [
        state._setup_path(tmp_path),
        state._requirements_path(tmp_path),
        state._action_checks_path(tmp_path),
        state._readiness_path(tmp_path),
        state._active_path(tmp_path),
        state._feature_path(tmp_path, "schema-sample"),
    ]
    paths.extend((tmp_path / ".agentic" / "setup").glob("*-state.json"))
    for path in paths:
        instance = json.loads(path.read_text(encoding="utf-8"))
        schema_name = Path(instance["$schema"]).name
        Draft202012Validator(
            schemas[schema_name], format_checker=FormatChecker()
        ).validate(instance)

    instructions = json.loads(
        (tmp_path / ".agentic" / "setup" / "instructions-state.json").read_text()
    )
    instructions["evidence"]["commands"]["build"]["actions"][0]["command"] = (
        "python -m build"
    )
    with pytest.raises(ValidationError):
        Draft202012Validator(schemas["setup-evidence.schema.json"]).validate(
            instructions
        )


def test_malformed_state_is_reported_as_a_controlled_error(tmp_path):
    malformed = state.new_setup_state()
    malformed["topics"]["instructions"]["status"] = ["complete"]
    with pytest.raises(state.StateError, match="invalid status"):
        state.validate_setup_state(malformed)

    malformed_feature = state.new_feature_state("safe-id", "Safe title")
    malformed_feature["unexpected"] = True
    with pytest.raises(state.StateError, match="unknown fields"):
        state.validate_feature_state(malformed_feature)
