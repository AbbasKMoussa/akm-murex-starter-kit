"""Contract and transition tests for the bundled state controller."""

import json
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator, FormatChecker

from akmaestro import installer, state


SCHEMA_DIR = Path(__file__).resolve().parent.parent / "src" / "akmaestro" / "assets" / "schemas"


def _requirements_body(artifact_path="graphify-out/graph.json"):
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
                "remediation": {"command": ["graphify", "extract", "."], "cwd": "."},
            }
        ],
    }


def _advance_setup(root: Path, topic: str, terminal: str = "complete"):
    current = state._read_json(state._setup_path(root))
    state.setup_transition(root, topic, "in_progress", expected_revision=current["revision"])
    if terminal in {"complete", "blocked"}:
        evidence_path = root / ".agentic" / "setup" / f"{topic}-state.json"
        if not evidence_path.exists():
            state.write_topic_evidence(root, topic, {"verified": terminal == "complete"})
        if topic == "tooling" and not state._requirements_path(root).exists():
            state.write_requirements(root, _requirements_body())
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
    graph = root / "graphify-out" / "graph.json"
    graph.parent.mkdir(parents=True)
    graph.write_text("{}", encoding="utf-8")
    state.write_requirements(root, _requirements_body())
    readiness, ready = state.check_readiness(root)
    assert ready


def _write_feature_artifact(root: Path, feature_id: str, relative: str):
    path = root / ".agentic" / "features" / feature_id / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"# {relative}\n", encoding="utf-8")


def test_setup_state_is_derived_and_blocked_mandatory_topics_can_complete(tmp_path):
    created = state.setup_init(tmp_path)
    assert created["version"] == 2
    assert "overall" not in created
    assert "currentStep" not in created

    _advance_setup(tmp_path, "instructions")
    _advance_setup(tmp_path, "tooling", "blocked")
    _advance_setup(tmp_path, "skills")
    _advance_setup(tmp_path, "hooks", "skipped")

    current = state._read_json(state._setup_path(tmp_path))
    summary = state.setup_summary(current)
    assert summary["overall"] == "complete"
    assert summary["nextCommand"] is None
    assert current["topics"]["tooling"]["blocker"] == "organization policy"
    assert current["completedAt"]


def test_setup_rejects_illegal_and_stale_transitions_but_replay_is_idempotent(tmp_path):
    state.setup_init(tmp_path)
    with pytest.raises(state.StateError, match="illegal setup transition"):
        state.setup_transition(tmp_path, "instructions", "complete", expected_revision=0)

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
    assert any(isinstance(result, str) and "stale state" in result for result in results)


def test_topic_evidence_and_requirements_writes_are_idempotent(tmp_path):
    evidence = state.write_topic_evidence(tmp_path, "instructions", {"smokeTest": "passed"})
    replay = state.write_topic_evidence(
        tmp_path,
        "instructions",
        {"smokeTest": "passed"},
        expected_revision=99,
    )
    assert evidence == replay

    body = _requirements_body()
    requirements = state.write_requirements(tmp_path, body)
    assert requirements["revision"] == 0
    assert state.write_requirements(tmp_path, body, expected_revision=50) == requirements


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
        _write_feature_artifact(tmp_path, "abc-search-filters", f"stories/{story_id}.md")
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
    with pytest.raises(state.StateError, match="team lead must finish /init"):
        state.feature_create(tmp_path, "blocked-feature", "Blocked feature")

    state.setup_init(tmp_path)
    for topic in ("instructions", "tooling", "skills"):
        _advance_setup(tmp_path, topic)
    _advance_setup(tmp_path, "hooks", "skipped")
    state.write_requirements(tmp_path, _requirements_body())

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
    sent_back = state.story_transition(tmp_path, "review-loop", "01-change", "implement", 7)
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
    graph = tmp_path / "graphify-out" / "graph.json"
    graph.parent.mkdir(parents=True)
    graph.write_text("{}", encoding="utf-8")
    state.write_requirements(tmp_path, _requirements_body())
    state.check_readiness(tmp_path)
    for topic in ("instructions", "tooling", "skills"):
        _advance_setup(tmp_path, topic)
    _advance_setup(tmp_path, "hooks", "skipped")
    state.feature_create(tmp_path, "missing-artifact", "Missing artifact")
    _write_feature_artifact(tmp_path, "missing-artifact", "understanding.md")
    state.feature_advance_gate(tmp_path, "missing-artifact", "understand", 0)
    (tmp_path / ".agentic" / "features" / "missing-artifact" / "understanding.md").unlink()

    updated = _requirements_body()
    updated["artifacts"].append({"id": "x", "path": "x", "required": False})
    state.write_requirements(tmp_path, updated, expected_revision=0)
    report = state.validate_all(tmp_path)
    assert report["valid"]
    assert any("readiness is stale" in warning for warning in report["warnings"])
    assert any("understanding.md is missing" in warning for warning in report["warnings"])


def test_gate_refuses_to_advance_before_its_artifact_exists(tmp_path):
    _ready_repo(tmp_path)
    state.feature_create(tmp_path, "state-last", "State last")
    with pytest.raises(state.StateError, match="must be written before advancing"):
        state.feature_advance_gate(tmp_path, "state-last", "understand", 0)
    current = state._read_json(state._feature_path(tmp_path, "state-last"))
    assert current["revision"] == 0
    assert current["phase"] == "understanding"


def test_installed_controller_runs_without_importing_the_package(tmp_path):
    installer.init(str(tmp_path), with_hooks=False)
    controller = tmp_path / ".agentic" / "bin" / "akmaestro-state.py"
    namespace = {"__name__": "installed_controller"}
    exec(compile(controller.read_text(encoding="utf-8"), str(controller), "exec"), namespace)
    assert namespace["STATE_VERSION"] == 2
    for schema in (
        "setup-state.schema.json",
        "setup-evidence.schema.json",
        "environment-requirements.schema.json",
        "local-readiness.schema.json",
        "feature-state.schema.json",
        "active-feature.schema.json",
    ):
        json.loads((tmp_path / ".agentic" / "schemas" / schema).read_text(encoding="utf-8"))


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


def test_malformed_state_is_reported_as_a_controlled_error(tmp_path):
    malformed = state.new_setup_state()
    malformed["topics"]["instructions"]["status"] = ["complete"]
    with pytest.raises(state.StateError, match="invalid status"):
        state.validate_setup_state(malformed)

    malformed_feature = state.new_feature_state("safe-id", "Safe title")
    malformed_feature["unexpected"] = True
    with pytest.raises(state.StateError, match="unknown fields"):
        state.validate_feature_state(malformed_feature)
