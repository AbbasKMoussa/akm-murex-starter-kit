"""Deterministic, repo-local state controller for AKMaestro workflows.

This module is copied into installed repositories as
``.agentic/bin/akmaestro-state.py``. It intentionally uses only the Python
standard library so every developer can run the repository's pinned controller
through ``uv`` without installing AKMaestro as a persistent tool.
"""

from __future__ import annotations

import argparse
import difflib
import hashlib
import json
import os
import re
import secrets
import shutil
import subprocess
import sys
import tempfile
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any, Dict, Iterable, Iterator, List, Optional, Sequence, Tuple


STATE_VERSION = 3
TOPICS = ("instructions", "tooling", "skills", "hooks")
MANDATORY_TOPICS = ("instructions", "tooling", "skills")
OPTIONAL_TOPICS = ("hooks",)
TOPIC_STATUSES = {"pending", "in_progress", "complete", "blocked", "skipped"}
TERMINAL_TOPIC_STATUSES = {"complete", "blocked", "skipped"}

FEATURE_PHASES = (
    "understanding",
    "framing",
    "splitting",
    "story_loop",
    "reviewing",
    "retrospective",
    "complete",
)
STORY_STEPS = ("prime", "plan", "implement", "review", "learn", "complete")
STORY_MODES = ("guided", "autonomous")
GATE_TRANSITIONS = {
    "understand": ("understanding", "framing"),
    "frame": ("framing", "splitting"),
    "split": ("splitting", "story_loop"),
    "feature-review": ("reviewing", "retrospective"),
    "retro": ("retrospective", "complete"),
}
STORY_TRANSITIONS = {
    "prime": {"plan"},
    "plan": {"implement"},
    "implement": {"review"},
    "review": {"learn", "plan", "implement"},
    "learn": {"complete"},
    "complete": set(),
}
NEXT_COMMANDS = {
    "understanding": "/feature-understand",
    "framing": "/feature-frame",
    "splitting": "/feature-split",
    "reviewing": "/feature-review",
    "retrospective": "/feature-retro",
    "complete": None,
}
STORY_COMMANDS = {
    "prime": "/story-prime",
    "plan": "/story-plan",
    "implement": "/story-implement",
    "review": "/story-review",
    "learn": "/story-learn",
    "complete": None,
}

INSTRUCTION_COMMANDS = (
    "bootstrap",
    "build",
    "test",
    "lint",
    "typecheck",
    "run",
    "verify",
)
INSTRUCTION_GIT_POLICIES = (
    "branchNaming",
    "commitStyle",
    "directPush",
    "pullRequests",
    "commitSigning",
    "ticketReferences",
)
INSTRUCTION_FILES = (
    "AGENTS.md",
    ".github/copilot-instructions.md",
    ".github/instructions/tests.instructions.md",
)
INSTRUCTION_HEADINGS = (
    "Product",
    "Repository Context",
    "Workspace & Dependencies",
    "Stack",
    "Setup",
    "Build",
    "Tests",
    "Run",
    "Verify a Change",
    "CI",
    "Complex Modules",
    "Git Workflow",
    "Agent Rules",
)
INSTRUCTION_PLACEHOLDERS = (
    "<team lead: run `/akmaestro-init`",
    "<product description>",
    "<main repository or role",
    "<dependency/bootstrap actions",
    "<build command>",
    "<test command>",
    "<run command",
    "<how to run/serve",
    "<how a developer confirms",
    "<ci system and required checks>",
    "<module paths needing scoped instructions",
    "<base branch and explicit branch",
    "<branch style>",
    "<commit style>",
    "<restricted areas",
)

REQUIRED_SKILLS = (
    "status",
    "akmaestro-init",
    "setup-instructions",
    "setup-tooling",
    "setup-skills",
    "setup-hooks",
    "teach",
    "doctor",
    "feature",
    "feature-understand",
    "feature-frame",
    "feature-split",
    "story-prime",
    "story-plan",
    "story-implement",
    "story-review",
    "story-learn",
    "feature-review",
    "feature-retro",
)

MERGE_TARGETS = (
    "AGENTS.md",
    ".github/copilot-instructions.md",
    ".github/instructions/",
    ".github/hooks/",
    ".agentic/hooks/",
)

ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,99}$")
STORY_ID_RE = re.compile(r"^[0-9]{2,}-[a-z0-9][a-z0-9-]{0,99}$")


class StateError(RuntimeError):
    """A user-correctable state or transition error."""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _read_json(path: Path) -> Dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise StateError(f"state file does not exist: {path}") from exc
    except (OSError, json.JSONDecodeError) as exc:
        raise StateError(f"cannot read valid JSON from {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise StateError(f"state file must contain a JSON object: {path}")
    return value


def _atomic_write_json(path: Path, value: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    data = (json.dumps(value, indent=2, sort_keys=True) + "\n").encode("utf-8")
    fd, temp_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
    )
    temp = Path(temp_name)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        try:
            temp.chmod(0o644)
        except OSError:
            pass
        os.replace(str(temp), str(path))
        if os.name != "nt":
            dir_fd = os.open(str(path.parent), os.O_RDONLY)
            try:
                os.fsync(dir_fd)
            finally:
                os.close(dir_fd)
    finally:
        try:
            temp.unlink()
        except FileNotFoundError:
            pass


def _atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
    )
    temp = Path(temp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as stream:
            stream.write(text)
            stream.flush()
            os.fsync(stream.fileno())
        try:
            temp.chmod(0o644)
        except OSError:
            pass
        os.replace(str(temp), str(path))
    finally:
        try:
            temp.unlink()
        except FileNotFoundError:
            pass


@contextmanager
def _state_lock(root: Path, state_path: Path, timeout: float = 10.0) -> Iterator[None]:
    """Serialize a state update using an atomic directory lock.

    Directory creation is atomic on the supported filesystems and works on both
    Windows and POSIX. Locks are local-only and stale locks are reclaimed.
    """

    resolved_root = root.resolve()
    if not _is_within(state_path.parent.resolve(), resolved_root):
        raise StateError(f"state path resolves outside repository: {state_path}")
    lock_root = root / ".agentic" / "local" / "locks"
    if not _is_within(lock_root.resolve(), resolved_root):
        raise StateError("local lock path resolves outside repository")
    lock_root.mkdir(parents=True, exist_ok=True)
    key = hashlib.sha256(str(state_path.resolve()).encode("utf-8")).hexdigest()[:20]
    lock_dir = lock_root / f"{key}.lock"
    deadline = time.monotonic() + timeout

    while True:
        try:
            lock_dir.mkdir()
            _atomic_write_json(
                lock_dir / "owner.json",
                {"pid": os.getpid(), "createdAt": _now(), "state": str(state_path)},
            )
            break
        except FileExistsError:
            try:
                age = time.time() - lock_dir.stat().st_mtime
                if age > 60:
                    shutil.rmtree(lock_dir)
                    continue
            except FileNotFoundError:
                continue
            if time.monotonic() >= deadline:
                raise StateError(f"timed out waiting for state lock: {state_path}")
            time.sleep(0.05)

    try:
        yield
    finally:
        shutil.rmtree(lock_dir, ignore_errors=True)


def _expect_revision(state: Dict[str, Any], expected: Optional[int]) -> None:
    if expected is None:
        return
    actual = state.get("revision")
    if actual != expected:
        raise StateError(f"stale state: expected revision {expected}, found {actual}")


def _require_keys(value: Dict[str, Any], keys: Iterable[str], label: str) -> None:
    missing = [key for key in keys if key not in value]
    if missing:
        raise StateError(f"{label} is missing required fields: {', '.join(missing)}")


def _only_keys(value: Dict[str, Any], keys: Iterable[str], label: str) -> None:
    extra = sorted(set(value) - set(keys))
    if extra:
        raise StateError(f"{label} has unknown fields: {', '.join(extra)}")


def _require_schema(value: Dict[str, Any], expected: str, label: str) -> None:
    if value.get("$schema") != expected:
        raise StateError(f"{label} must reference schema {expected!r}")


def _require_timestamp(value: Any, label: str) -> None:
    if not isinstance(value, str):
        raise StateError(f"{label} must be an RFC 3339 timestamp")
    try:
        datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise StateError(f"{label} must be an RFC 3339 timestamp") from exc


def _require_version(value: Dict[str, Any], label: str) -> None:
    if value.get("version") != STATE_VERSION:
        raise StateError(f"{label} must use state version {STATE_VERSION}")


def _require_revision(value: Dict[str, Any], label: str) -> None:
    revision = value.get("revision")
    if not isinstance(revision, int) or isinstance(revision, bool) or revision < 0:
        raise StateError(f"{label}.revision must be a non-negative integer")


def _setup_path(root: Path) -> Path:
    return root / ".agentic" / "setup" / "initialization-state.json"


def _requirements_path(root: Path) -> Path:
    return root / ".agentic" / "setup" / "environment-requirements.json"


def _action_checks_path(root: Path) -> Path:
    return root / ".agentic" / "setup" / "action-checks.json"


def _merge_plans_dir(root: Path) -> Path:
    return root / ".agentic" / "local" / "merge-plans"


def _readiness_path(root: Path) -> Path:
    return root / ".agentic" / "local" / "readiness.json"


def _active_path(root: Path) -> Path:
    return root / ".agentic" / "local" / "active-feature.json"


def _feature_path(root: Path, feature_id: str) -> Path:
    _validate_id(feature_id, "feature id", ID_RE)
    return root / ".agentic" / "features" / feature_id / "state.json"


def _require_artifact(path: Path, label: str) -> None:
    if not path.is_file():
        raise StateError(f"{label} must be written before advancing state: {path}")


def _validate_id(value: str, label: str, pattern: re.Pattern[str]) -> None:
    if not isinstance(value, str) or not pattern.fullmatch(value):
        raise StateError(f"invalid {label}: {value!r}")


def _validate_workspace_path(value: str, label: str) -> None:
    if (
        not isinstance(value, str)
        or not value
        or "\x00" in value
        or "\\" in value
        or re.match(r"^[A-Za-z]:", value)
    ):
        raise StateError(f"{label} must be a non-empty path")
    path = PurePosixPath(value)
    if path.is_absolute():
        raise StateError(f"{label} must be relative to the repository: {value!r}")


def _declared_workspace_roots(root: Path, include_read_only: bool) -> List[Path]:
    roots = [root.resolve()]
    evidence_path = root / ".agentic" / "setup" / "instructions-state.json"
    if not evidence_path.is_file():
        return roots
    try:
        envelope = _read_json(evidence_path)
        validate_topic_evidence(envelope)
        siblings = envelope["evidence"]["repositoryContext"]["siblingRepositories"]
    except (KeyError, StateError):
        return roots
    for sibling in siblings:
        if sibling["role"] == "read-only" and not include_read_only:
            continue
        candidate = (root / sibling["path"]).resolve()
        if candidate not in roots:
            roots.append(candidate)
    return roots


def _is_within(path: Path, base: Path) -> bool:
    try:
        path.relative_to(base)
        return True
    except ValueError:
        return False


def _resolve_workspace_path(
    root: Path,
    value: str,
    label: str,
    *,
    include_read_only: bool = False,
) -> Path:
    """Resolve a repository-relative path inside an explicitly declared root."""

    _validate_workspace_path(value, label)
    resolved = (root / value).resolve()
    allowed = _declared_workspace_roots(root, include_read_only)
    if not any(_is_within(resolved, base) for base in allowed):
        roles = "main/modifiable/read-only" if include_read_only else "main/modifiable"
        raise StateError(
            f"{label} resolves outside declared {roles} repository roots: {value!r}"
        )
    return resolved


def new_setup_state() -> Dict[str, Any]:
    now = _now()
    return {
        "$schema": "../schemas/setup-state.schema.json",
        "version": STATE_VERSION,
        "revision": 0,
        "profile": {
            "mandatory": list(MANDATORY_TOPICS),
            "optional": list(OPTIONAL_TOPICS),
        },
        "topics": {
            topic: {
                "status": "pending",
                "optional": topic in OPTIONAL_TOPICS,
                "updatedAt": now,
            }
            for topic in TOPICS
        },
        "finalization": {"status": "pending", "updatedAt": now},
        "createdAt": now,
        "updatedAt": now,
    }


def validate_setup_state(state: Dict[str, Any]) -> None:
    _require_schema(state, "../schemas/setup-state.schema.json", "setup state")
    _require_version(state, "setup state")
    _require_revision(state, "setup state")
    _require_keys(
        state,
        ("profile", "topics", "finalization", "createdAt", "updatedAt"),
        "setup state",
    )
    _only_keys(
        state,
        (
            "$schema",
            "version",
            "revision",
            "profile",
            "topics",
            "finalization",
            "createdAt",
            "updatedAt",
            "completedAt",
        ),
        "setup state",
    )
    _require_timestamp(state["createdAt"], "setup state.createdAt")
    _require_timestamp(state["updatedAt"], "setup state.updatedAt")
    if "completedAt" in state:
        _require_timestamp(state["completedAt"], "setup state.completedAt")
    profile = state["profile"]
    if not isinstance(profile, dict):
        raise StateError("setup state.profile must be an object")
    if profile.get("mandatory") != list(MANDATORY_TOPICS):
        raise StateError("setup state mandatory topics do not match this controller")
    if profile.get("optional") != list(OPTIONAL_TOPICS):
        raise StateError("setup state optional topics do not match this controller")
    _only_keys(profile, ("mandatory", "optional"), "setup state.profile")
    topics = state["topics"]
    if not isinstance(topics, dict) or set(topics) != set(TOPICS):
        raise StateError("setup state must contain exactly the four setup topics")
    for topic, item in topics.items():
        if not isinstance(item, dict):
            raise StateError(f"setup topic {topic} must be an object")
        _require_keys(item, ("status", "optional", "updatedAt"), f"setup topic {topic}")
        _only_keys(
            item, ("status", "optional", "updatedAt", "blocker"), f"setup topic {topic}"
        )
        if not isinstance(item["status"], str) or item["status"] not in TOPIC_STATUSES:
            raise StateError(
                f"invalid status for setup topic {topic}: {item['status']!r}"
            )
        expected_optional = topic in OPTIONAL_TOPICS
        if item["optional"] is not expected_optional:
            raise StateError(f"setup topic {topic} has an invalid optional flag")
        if item["status"] == "blocked" and not item.get("blocker"):
            raise StateError(f"blocked setup topic {topic} requires a blocker")
        if item["status"] == "skipped" and not expected_optional:
            raise StateError(f"mandatory setup topic {topic} cannot be skipped")
        _require_timestamp(item["updatedAt"], f"setup topic {topic}.updatedAt")

    finalization = state["finalization"]
    if not isinstance(finalization, dict):
        raise StateError("setup state.finalization must be an object")
    _require_keys(finalization, ("status", "updatedAt"), "setup finalization")
    allowed = ("status", "updatedAt", "guideHash", "previousGuideHash")
    _only_keys(finalization, allowed, "setup finalization")
    if finalization["status"] not in {"pending", "complete"}:
        raise StateError("setup finalization status must be pending or complete")
    _require_timestamp(finalization["updatedAt"], "setup finalization.updatedAt")
    if finalization["status"] == "complete":
        guide_hash = finalization.get("guideHash")
        if not isinstance(guide_hash, str) or not re.fullmatch(
            r"[0-9a-f]{64}", guide_hash
        ):
            raise StateError("completed setup finalization requires guideHash")
        if "previousGuideHash" in finalization:
            raise StateError(
                "completed setup finalization cannot contain previousGuideHash"
            )
    else:
        if "guideHash" in finalization:
            raise StateError("pending setup finalization cannot contain guideHash")
        previous = finalization.get("previousGuideHash")
        if previous is not None and (
            not isinstance(previous, str) or not re.fullmatch(r"[0-9a-f]{64}", previous)
        ):
            raise StateError("pending setup finalization previousGuideHash is invalid")


def setup_summary(state: Dict[str, Any]) -> Dict[str, Any]:
    validate_setup_state(state)
    mandatory_done = all(
        state["topics"][topic]["status"] in {"complete", "blocked"}
        for topic in MANDATORY_TOPICS
    )
    optional_done = all(
        state["topics"][topic]["status"] in TERMINAL_TOPIC_STATUSES
        for topic in OPTIONAL_TOPICS
    )
    next_topic = next(
        (
            topic
            for topic in TOPICS
            if state["topics"][topic]["status"] not in TERMINAL_TOPIC_STATUSES
        ),
        None,
    )
    topics_complete = mandatory_done and optional_done
    finalized = state["finalization"]["status"] == "complete"
    return {
        "overall": "complete" if topics_complete and finalized else "incomplete",
        "topicsComplete": topics_complete,
        "finalized": finalized,
        "nextTopic": next_topic,
        # Topic skills are internal orchestrator steps. The lead always enters
        # and resumes the public setup flow through /akmaestro-init.
        "nextCommand": "/akmaestro-init" if not finalized else None,
        "revision": state["revision"],
        "topics": state["topics"],
    }


def validate_setup_integrity(root: Path, state: Dict[str, Any]) -> None:
    validate_setup_state(state)
    for topic in TOPICS:
        if state["topics"][topic]["status"] not in {"complete", "blocked"}:
            continue
        path = root / ".agentic" / "setup" / f"{topic}-state.json"
        _require_artifact(path, f"setup evidence for {topic}")
        evidence = _read_json(path)
        validate_topic_evidence(evidence)
        if evidence["topic"] != topic:
            raise StateError(f"setup evidence topic mismatch for {topic}")
        _validate_topic_artifacts(root, evidence)
    if state["topics"]["tooling"]["status"] in {"complete", "blocked"}:
        validate_requirements(_read_json(_requirements_path(root)))
    if _action_checks_path(root).is_file():
        validate_action_checks(_read_json(_action_checks_path(root)))
    _validate_finalization(root, state)


def setup_init(root: Path) -> Dict[str, Any]:
    path = _setup_path(root)
    with _state_lock(root, path):
        if path.exists():
            state = _read_json(path)
            validate_setup_state(state)
            return state
        state = new_setup_state()
        _atomic_write_json(path, state)
        return state


def setup_transition(
    root: Path,
    topic: str,
    status: str,
    reason: Optional[str] = None,
    expected_revision: Optional[int] = None,
) -> Dict[str, Any]:
    if topic not in TOPICS:
        raise StateError(f"unknown setup topic: {topic}")
    if status not in TOPIC_STATUSES:
        raise StateError(f"unknown setup status: {status}")
    if status == "blocked" and not reason:
        raise StateError("blocked status requires --reason")
    path = _setup_path(root)
    with _state_lock(root, path):
        state = _read_json(path)
        validate_setup_state(state)
        current = state["topics"][topic]
        if current["status"] == status and current.get("blocker") == reason:
            return state
        _expect_revision(state, expected_revision)

        allowed = {
            "pending": {"in_progress", "skipped"},
            "in_progress": {"complete", "blocked", "skipped"},
            "complete": {"in_progress"},
            "blocked": {"in_progress"},
            "skipped": {"in_progress"},
        }
        if status not in allowed[current["status"]]:
            raise StateError(
                f"illegal setup transition for {topic}: {current['status']} -> {status}"
            )
        if status == "skipped" and topic not in OPTIONAL_TOPICS:
            raise StateError(f"mandatory setup topic {topic} cannot be skipped")
        if status in {"complete", "blocked"}:
            evidence_path = root / ".agentic" / "setup" / f"{topic}-state.json"
            _require_artifact(evidence_path, f"setup evidence for {topic}")
            evidence = _read_json(evidence_path)
            validate_topic_evidence(evidence)
            if evidence["topic"] != topic:
                raise StateError(f"setup evidence topic mismatch for {topic}")
            _validate_topic_artifacts(root, evidence)
            has_blockers = _topic_has_blockers(topic, evidence["evidence"])
            if status == "complete" and has_blockers:
                raise StateError(
                    f"{topic} evidence has blockers and must transition to blocked"
                )
            if status == "blocked" and not has_blockers:
                raise StateError(f"blocked {topic} requires a blocker in evidence")
            if topic == "tooling":
                requirements = _read_json(_requirements_path(root))
                validate_requirements(requirements)
                _readiness, ready = check_readiness(root, write=False)
                if status == "complete" and not ready:
                    raise StateError(
                        "tooling cannot complete while required readiness checks fail"
                    )
                if status == "blocked" and ready:
                    raise StateError(
                        "tooling cannot be blocked when all readiness checks pass"
                    )
            if topic == "skills" and status == "complete":
                body = evidence["evidence"]
                if set(body["verifiedSkills"]) != set(REQUIRED_SKILLS):
                    raise StateError(
                        "skills cannot complete until the full catalog is verified"
                    )
                if body["collisions"]:
                    raise StateError(
                        "skills cannot complete with unresolved collisions"
                    )
                if "verified" not in body["discovery"].values():
                    raise StateError(
                        "skills cannot complete until one Copilot surface discovers them"
                    )
            if topic == "hooks" and status == "complete":
                body = evidence["evidence"]
                if body["enabled"] and any(
                    check["status"] != "passed" for check in body["checks"]
                ):
                    raise StateError(
                        "enabled hooks cannot complete until every selected check passes"
                    )

        now = _now()
        current["status"] = status
        current["updatedAt"] = now
        if reason:
            current["blocker"] = reason
        else:
            current.pop("blocker", None)
        state["revision"] += 1
        state["updatedAt"] = now
        previous_guide_hash = state["finalization"].get(
            "guideHash", state["finalization"].get("previousGuideHash")
        )
        state["finalization"] = {"status": "pending", "updatedAt": now}
        if previous_guide_hash:
            state["finalization"]["previousGuideHash"] = previous_guide_hash
        state.pop("completedAt", None)
        validate_setup_state(state)
        _atomic_write_json(path, state)
        return state


def _require_nonempty_text(value: Any, label: str) -> None:
    if not isinstance(value, str) or not value.strip() or "\x00" in value:
        raise StateError(f"{label} must be a non-empty string")


def _validate_text_list(value: Any, label: str, *, allow_empty: bool = False) -> None:
    if not isinstance(value, list) or (not value and not allow_empty):
        qualifier = "a" if allow_empty else "a non-empty"
        raise StateError(f"{label} must be {qualifier} string array")
    for index, item in enumerate(value):
        _require_nonempty_text(item, f"{label}[{index}]")


def _validate_instruction_action(value: Any, label: str) -> None:
    if not isinstance(value, dict):
        raise StateError(f"{label} must be an object")
    _require_keys(value, ("command",), label)
    _only_keys(value, ("label", "command", "cwd", "timeoutSeconds"), label)
    command = value["command"]
    if not isinstance(command, list) or not command:
        raise StateError(f"{label}.command must be a non-empty argument array")
    for index, part in enumerate(command):
        _require_nonempty_text(part, f"{label}.command[{index}]")
    if "label" in value:
        _require_nonempty_text(value["label"], f"{label}.label")
    _validate_workspace_path(value.get("cwd", "."), f"{label}.cwd")
    timeout = value.get("timeoutSeconds", 300)
    if (
        not isinstance(timeout, int)
        or isinstance(timeout, bool)
        or timeout < 1
        or timeout > 3600
    ):
        raise StateError(f"{label}.timeoutSeconds must be an integer from 1 to 3600")


def instruction_action_hash(action: Dict[str, Any]) -> str:
    _validate_instruction_action(action, "instruction action")
    canonical = json.dumps(action, sort_keys=True, separators=(",", ":")).encode(
        "utf-8"
    )
    return hashlib.sha256(canonical).hexdigest()


def check_instruction_action(root: Path, action: Dict[str, Any]) -> Dict[str, Any]:
    """Run one confirmed instruction command without invoking a shell."""

    _validate_instruction_action(action, "instruction action")
    command = action["command"]
    cwd = _resolve_workspace_path(
        root,
        action.get("cwd", "."),
        "instruction action.cwd",
        include_read_only=False,
    )
    if not cwd.is_dir():
        raise StateError(f"instruction action working directory does not exist: {cwd}")
    timeout = action.get("timeoutSeconds", 300)
    try:
        proc = subprocess.run(
            command,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
        result = {
            "actionHash": instruction_action_hash(action),
            "status": "passed" if proc.returncode == 0 else "failed",
            "exitCode": proc.returncode,
            # Evidence is committed. Never persist command output, which may
            # contain credentials or repository-sensitive content.
            "detail": f"command exited {proc.returncode}",
            "checkedAt": _now(),
        }
    except FileNotFoundError:
        result = {
            "actionHash": instruction_action_hash(action),
            "status": "failed",
            "detail": f"command not found: {command[0]}",
            "checkedAt": _now(),
        }
    except subprocess.TimeoutExpired:
        result = {
            "actionHash": instruction_action_hash(action),
            "status": "failed",
            "detail": f"command timed out after {timeout}s",
            "checkedAt": _now(),
        }
    except OSError as exc:
        result = {
            "actionHash": instruction_action_hash(action),
            "status": "failed",
            "detail": f"command could not run: {exc}",
            "checkedAt": _now(),
        }
    return _record_action_check(root, result)


def new_action_checks() -> Dict[str, Any]:
    now = _now()
    return {
        "$schema": "../schemas/action-checks.schema.json",
        "version": STATE_VERSION,
        "revision": 0,
        "checks": [],
        "createdAt": now,
        "updatedAt": now,
    }


def validate_action_checks(state: Dict[str, Any]) -> None:
    _require_schema(state, "../schemas/action-checks.schema.json", "action checks")
    _require_version(state, "action checks")
    _require_revision(state, "action checks")
    _require_keys(state, ("checks", "createdAt", "updatedAt"), "action checks")
    _only_keys(
        state,
        ("$schema", "version", "revision", "checks", "createdAt", "updatedAt"),
        "action checks",
    )
    _require_timestamp(state["createdAt"], "action checks.createdAt")
    _require_timestamp(state["updatedAt"], "action checks.updatedAt")
    if not isinstance(state["checks"], list):
        raise StateError("action checks.checks must be an array")
    seen = set()
    for index, check in enumerate(state["checks"]):
        _validate_action_check(check, f"action checks.checks[{index}]")
        if check["checkId"] in seen:
            raise StateError("action checks contains duplicate checkId values")
        seen.add(check["checkId"])


def _record_action_check(root: Path, result: Dict[str, Any]) -> Dict[str, Any]:
    path = _action_checks_path(root)
    with _state_lock(root, path):
        ledger = _read_json(path) if path.exists() else new_action_checks()
        validate_action_checks(ledger)
        recorded = {"checkId": secrets.token_hex(16), **result}
        _validate_action_check(recorded, "action check")
        ledger["checks"].append(recorded)
        ledger["revision"] += 1
        ledger["updatedAt"] = recorded["checkedAt"]
        _atomic_write_json(path, ledger)
        return recorded


def _validate_action_check(check: Any, label: str) -> None:
    if not isinstance(check, dict):
        raise StateError(f"{label} must be an object")
    _require_keys(
        check,
        ("checkId", "actionHash", "status", "detail", "checkedAt"),
        label,
    )
    _only_keys(
        check,
        ("checkId", "actionHash", "status", "exitCode", "detail", "checkedAt"),
        label,
    )
    if not isinstance(check["checkId"], str) or not re.fullmatch(
        r"[0-9a-f]{32}", check["checkId"]
    ):
        raise StateError(f"{label}.checkId must be a controller-generated identifier")
    if not isinstance(check["actionHash"], str) or not re.fullmatch(
        r"[0-9a-f]{64}", check["actionHash"]
    ):
        raise StateError(f"{label}.actionHash must be a sha256 hex digest")
    if check["status"] not in {"passed", "failed"}:
        raise StateError(f"{label}.status must be 'passed' or 'failed'")
    if "exitCode" in check and (
        not isinstance(check["exitCode"], int) or isinstance(check["exitCode"], bool)
    ):
        raise StateError(f"{label}.exitCode must be an integer")
    if check["status"] == "passed" and check.get("exitCode") != 0:
        raise StateError(f"{label} passed result must have exitCode 0")
    if check["status"] == "failed" and check.get("exitCode") == 0:
        raise StateError(f"{label} failed result cannot have exitCode 0")
    _require_nonempty_text(check["detail"], f"{label}.detail")
    _require_timestamp(check["checkedAt"], f"{label}.checkedAt")


def _validate_command_definition(value: Any, label: str) -> None:
    if not isinstance(value, dict):
        raise StateError(f"{label} must be an object")
    _require_keys(value, ("status", "sources"), label)
    _validate_text_list(value["sources"], f"{label}.sources")
    status = value["status"]
    if status == "configured":
        _require_keys(value, ("actions",), label)
        _only_keys(value, ("status", "actions", "sources"), label)
        actions = value["actions"]
        if not isinstance(actions, list) or not actions:
            raise StateError(f"{label}.actions must be a non-empty array")
        for index, action in enumerate(actions):
            _validate_instruction_action(action, f"{label}.actions[{index}]")
    elif status == "not_applicable":
        _require_keys(value, ("reason",), label)
        _only_keys(value, ("status", "reason", "sources"), label)
        _require_nonempty_text(value["reason"], f"{label}.reason")
    else:
        raise StateError(f"{label}.status must be 'configured' or 'not_applicable'")


def _validate_command_result(value: Any, label: str) -> None:
    if not isinstance(value, dict):
        raise StateError(f"{label} must be an object")
    _require_keys(value, ("status", "detail", "checks"), label)
    _only_keys(value, ("status", "detail", "checks"), label)
    if value["status"] not in {"passed", "blocked", "documented", "not_applicable"}:
        raise StateError(f"{label}.status is invalid: {value['status']!r}")
    _require_nonempty_text(value["detail"], f"{label}.detail")
    checks = value["checks"]
    if not isinstance(checks, list):
        raise StateError(f"{label}.checks must be an array")
    hashes = set()
    check_ids = set()
    for index, check in enumerate(checks):
        check_label = f"{label}.checks[{index}]"
        _validate_action_check(check, check_label)
        action_hash = check["actionHash"]
        if action_hash in hashes:
            raise StateError(f"{label}.checks contains duplicate action hashes")
        hashes.add(action_hash)
        if check["checkId"] in check_ids:
            raise StateError(f"{label}.checks contains duplicate check identifiers")
        check_ids.add(check["checkId"])


def _validate_policy(value: Any, label: str) -> None:
    if not isinstance(value, dict):
        raise StateError(f"{label} must be an object")
    _require_keys(value, ("status", "sources"), label)
    _validate_text_list(value["sources"], f"{label}.sources")
    status = value["status"]
    if status == "defined":
        _require_keys(value, ("value",), label)
        _only_keys(value, ("status", "value", "sources"), label)
        _require_nonempty_text(value["value"], f"{label}.value")
    elif status in {"none", "unspecified"}:
        _require_keys(value, ("reason",), label)
        _only_keys(value, ("status", "reason", "sources"), label)
        _require_nonempty_text(value["reason"], f"{label}.reason")
    else:
        raise StateError(f"{label}.status must be 'defined', 'none', or 'unspecified'")


def validate_instructions_evidence(evidence: Dict[str, Any]) -> None:
    if not isinstance(evidence, dict):
        raise StateError("instructions evidence must be an object")
    _require_keys(
        evidence,
        (
            "product",
            "commands",
            "commandResults",
            "manualVerification",
            "gitWorkflow",
            "repositoryContext",
            "generatedFiles",
            "pendingModules",
        ),
        "instructions evidence",
    )
    _only_keys(
        evidence,
        (
            "product",
            "commands",
            "commandResults",
            "manualVerification",
            "gitWorkflow",
            "repositoryContext",
            "generatedFiles",
            "pendingModules",
        ),
        "instructions evidence",
    )

    product = evidence["product"]
    if not isinstance(product, dict):
        raise StateError("instructions evidence.product must be an object")
    _require_keys(
        product, ("summary", "consumers", "primaryWorkflows", "sources"), "product"
    )
    _only_keys(
        product, ("summary", "consumers", "primaryWorkflows", "sources"), "product"
    )
    _require_nonempty_text(product["summary"], "product.summary")
    _validate_text_list(product["consumers"], "product.consumers")
    _validate_text_list(product["primaryWorkflows"], "product.primaryWorkflows")
    _validate_text_list(product["sources"], "product.sources")
    if any(marker in product["summary"].lower() for marker in INSTRUCTION_PLACEHOLDERS):
        raise StateError("product.summary still contains an AKMaestro placeholder")

    commands = evidence["commands"]
    if not isinstance(commands, dict) or set(commands) != set(INSTRUCTION_COMMANDS):
        raise StateError(
            "instructions evidence.commands must contain every canonical command"
        )
    results = evidence["commandResults"]
    if not isinstance(results, dict) or set(results) != set(INSTRUCTION_COMMANDS):
        raise StateError(
            "instructions evidence.commandResults must contain every canonical command"
        )
    for command_id in INSTRUCTION_COMMANDS:
        definition = commands[command_id]
        result = results[command_id]
        _validate_command_definition(definition, f"commands.{command_id}")
        _validate_command_result(result, f"commandResults.{command_id}")
        if definition["status"] == "not_applicable":
            if result["status"] != "not_applicable":
                raise StateError(
                    f"commandResults.{command_id} must be not_applicable when its command is"
                )
            if result["checks"]:
                raise StateError(
                    f"commandResults.{command_id}.checks must be empty when not applicable"
                )
            continue
        allowed_results = {"passed", "blocked"}
        if command_id in {"bootstrap", "run"}:
            allowed_results.add("documented")
        if result["status"] not in allowed_results:
            allowed = ", ".join(sorted(allowed_results))
            raise StateError(
                f"commandResults.{command_id}.status must be one of: {allowed}"
            )
        expected_hashes = {
            instruction_action_hash(action) for action in definition["actions"]
        }
        checked_hashes = {check["actionHash"] for check in result["checks"]}
        unknown_hashes = sorted(checked_hashes - expected_hashes)
        if unknown_hashes:
            raise StateError(
                f"commandResults.{command_id}.checks contains a substituted action hash"
            )
        if result["status"] == "passed":
            if checked_hashes != expected_hashes or any(
                check["status"] != "passed" for check in result["checks"]
            ):
                raise StateError(
                    f"commandResults.{command_id} must contain a passing check for every action"
                )
        elif result["status"] == "blocked":
            if not result["checks"] or all(
                check["status"] == "passed" for check in result["checks"]
            ):
                raise StateError(
                    f"commandResults.{command_id} blocked status requires a failed controller check"
                )
        elif result["status"] == "documented" and result["checks"]:
            raise StateError(
                f"commandResults.{command_id}.checks must be empty when only documented"
            )

    manual = evidence["manualVerification"]
    if not isinstance(manual, dict):
        raise StateError("instructions evidence.manualVerification must be an object")
    _require_keys(manual, ("status", "sources"), "manualVerification")
    _validate_text_list(manual["sources"], "manualVerification.sources")
    if manual["status"] == "configured":
        _require_keys(manual, ("steps",), "manualVerification")
        _only_keys(manual, ("status", "steps", "sources"), "manualVerification")
        _validate_text_list(manual["steps"], "manualVerification.steps")
    elif manual["status"] == "not_applicable":
        _require_keys(manual, ("reason",), "manualVerification")
        _only_keys(manual, ("status", "reason", "sources"), "manualVerification")
        _require_nonempty_text(manual["reason"], "manualVerification.reason")
    else:
        raise StateError(
            "manualVerification.status must be 'configured' or 'not_applicable'"
        )
    if (
        commands["verify"]["status"] != "configured"
        and manual["status"] != "configured"
    ):
        raise StateError(
            "instructions evidence requires an automated or manual verification path"
        )

    git_workflow = evidence["gitWorkflow"]
    if not isinstance(git_workflow, dict):
        raise StateError("instructions evidence.gitWorkflow must be an object")
    _require_keys(git_workflow, ("baseBranch", "policies", "sources"), "gitWorkflow")
    _only_keys(git_workflow, ("baseBranch", "policies", "sources"), "gitWorkflow")
    _require_nonempty_text(git_workflow["baseBranch"], "gitWorkflow.baseBranch")
    _validate_text_list(git_workflow["sources"], "gitWorkflow.sources")
    policies = git_workflow["policies"]
    if not isinstance(policies, dict) or set(policies) != set(INSTRUCTION_GIT_POLICIES):
        raise StateError("gitWorkflow.policies must contain every canonical Git policy")
    for policy_id in INSTRUCTION_GIT_POLICIES:
        _validate_policy(policies[policy_id], f"gitWorkflow.policies.{policy_id}")

    context = evidence["repositoryContext"]
    if not isinstance(context, dict):
        raise StateError("instructions evidence.repositoryContext must be an object")
    _require_keys(
        context,
        ("ciNotes", "complexModules", "siblingRepositories", "restrictedPaths"),
        "repositoryContext",
    )
    _only_keys(
        context,
        ("ciNotes", "complexModules", "siblingRepositories", "restrictedPaths"),
        "repositoryContext",
    )
    _validate_text_list(
        context["ciNotes"], "repositoryContext.ciNotes", allow_empty=True
    )
    _validate_text_list(
        context["restrictedPaths"],
        "repositoryContext.restrictedPaths",
        allow_empty=True,
    )
    modules = context["complexModules"]
    if not isinstance(modules, list):
        raise StateError("repositoryContext.complexModules must be an array")
    module_paths = set()
    for index, module in enumerate(modules):
        label = f"repositoryContext.complexModules[{index}]"
        if not isinstance(module, dict):
            raise StateError(f"{label} must be an object")
        _require_keys(module, ("path", "purpose"), label)
        _only_keys(module, ("path", "purpose"), label)
        _validate_workspace_path(module["path"], f"{label}.path")
        _require_nonempty_text(module["purpose"], f"{label}.purpose")
        if module["path"] in module_paths:
            raise StateError(f"duplicate complex module path: {module['path']}")
        module_paths.add(module["path"])
    siblings = context["siblingRepositories"]
    if not isinstance(siblings, list):
        raise StateError("repositoryContext.siblingRepositories must be an array")
    sibling_paths = set()
    for index, sibling in enumerate(siblings):
        label = f"repositoryContext.siblingRepositories[{index}]"
        if not isinstance(sibling, dict):
            raise StateError(f"{label} must be an object")
        _require_keys(sibling, ("path", "role", "purpose"), label)
        allowed_keys = ("path", "role", "purpose", "integration")
        _only_keys(sibling, allowed_keys, label)
        _validate_workspace_path(sibling["path"], f"{label}.path")
        sibling_parts = PurePosixPath(sibling["path"]).parts
        if (
            len(sibling_parts) < 2
            or sibling_parts[0] != ".."
            or any(part in {".", ".."} for part in sibling_parts[1:])
        ):
            raise StateError(
                f"{label}.path must identify a sibling below '..' without further traversal"
            )
        _require_nonempty_text(sibling["purpose"], f"{label}.purpose")
        if sibling["role"] not in {"modifiable", "read-only"}:
            raise StateError(f"{label}.role must be 'modifiable' or 'read-only'")
        if sibling["role"] == "modifiable":
            _require_keys(sibling, ("integration",), label)
            _require_nonempty_text(sibling["integration"], f"{label}.integration")
        elif "integration" in sibling:
            raise StateError(
                f"{label}.integration is only valid for modifiable siblings"
            )
        if sibling["path"] in sibling_paths:
            raise StateError(f"duplicate sibling repository path: {sibling['path']}")
        sibling_paths.add(sibling["path"])

    generated = evidence["generatedFiles"]
    _validate_text_list(generated, "instructions evidence.generatedFiles")
    if len(set(generated)) != len(generated):
        raise StateError("instructions evidence.generatedFiles contains duplicates")
    for index, path in enumerate(generated):
        _validate_workspace_path(path, f"instructions evidence.generatedFiles[{index}]")
    missing_files = sorted(set(INSTRUCTION_FILES) - set(generated))
    if missing_files:
        raise StateError(
            "instructions evidence.generatedFiles is missing required files: "
            + ", ".join(missing_files)
        )

    pending = evidence["pendingModules"]
    if not isinstance(pending, list):
        raise StateError("instructions evidence.pendingModules must be an array")
    if len(set(pending)) != len(pending):
        raise StateError("instructions evidence.pendingModules contains duplicates")
    for index, path in enumerate(pending):
        _validate_workspace_path(path, f"instructions evidence.pendingModules[{index}]")
        if path not in module_paths:
            raise StateError(
                f"pending module is not declared as a complex module: {path}"
            )


def _instructions_have_blockers(evidence: Dict[str, Any]) -> bool:
    return any(
        result["status"] == "blocked" for result in evidence["commandResults"].values()
    )


def _validate_blockers(value: Any, label: str) -> None:
    _validate_text_list(value, label, allow_empty=True)


def validate_tooling_evidence(evidence: Dict[str, Any]) -> None:
    if not isinstance(evidence, dict):
        raise StateError("tooling evidence must be an object")
    required = (
        "languages",
        "graphify",
        "lsps",
        "requirementsRevision",
        "newSessionRequired",
        "blockers",
    )
    _require_keys(evidence, required, "tooling evidence")
    _only_keys(evidence, required, "tooling evidence")
    _validate_text_list(evidence["languages"], "tooling evidence.languages")
    if len(set(evidence["languages"])) != len(evidence["languages"]):
        raise StateError("tooling evidence.languages contains duplicates")
    graphify = evidence["graphify"]
    if not isinstance(graphify, dict):
        raise StateError("tooling evidence.graphify must be an object")
    _require_keys(
        graphify,
        ("status", "version", "queryStatus", "graphPaths", "detail"),
        "tooling evidence.graphify",
    )
    _only_keys(
        graphify,
        ("status", "version", "queryStatus", "graphPaths", "detail"),
        "tooling evidence.graphify",
    )
    if graphify["status"] not in {"verified", "blocked"}:
        raise StateError("tooling evidence.graphify.status must be verified or blocked")
    if graphify["queryStatus"] not in {"passed", "blocked"}:
        raise StateError(
            "tooling evidence.graphify.queryStatus must be passed or blocked"
        )
    _require_nonempty_text(graphify["version"], "tooling evidence.graphify.version")
    _require_nonempty_text(graphify["detail"], "tooling evidence.graphify.detail")
    _validate_text_list(graphify["graphPaths"], "tooling evidence.graphify.graphPaths")
    for index, path in enumerate(graphify["graphPaths"]):
        _validate_workspace_path(path, f"tooling evidence.graphify.graphPaths[{index}]")
        if not path.startswith(".agentic/local/graphs/") or not path.endswith(
            "/graph.json"
        ):
            raise StateError(
                "Graphifyy graphs must use .agentic/local/graphs/<id>/graph.json"
            )
    lsps = evidence["lsps"]
    if not isinstance(lsps, list) or not lsps:
        raise StateError("tooling evidence.lsps must be a non-empty array")
    languages = set(evidence["languages"])
    lsp_languages = set()
    for index, lsp in enumerate(lsps):
        label = f"tooling evidence.lsps[{index}]"
        if not isinstance(lsp, dict):
            raise StateError(f"{label} must be an object")
        _require_keys(lsp, ("language", "toolId", "status", "detail"), label)
        _only_keys(lsp, ("language", "toolId", "status", "detail"), label)
        _require_nonempty_text(lsp["language"], f"{label}.language")
        _validate_id(lsp["toolId"], f"{label}.toolId", ID_RE)
        if not lsp["toolId"].startswith("lsp-"):
            raise StateError(f"{label}.toolId must start with lsp-")
        if lsp["status"] not in {"verified", "blocked"}:
            raise StateError(f"{label}.status must be verified or blocked")
        _require_nonempty_text(lsp["detail"], f"{label}.detail")
        lsp_languages.add(lsp["language"])
    if languages != lsp_languages:
        raise StateError(
            "tooling evidence needs exactly one LSP result per selected language"
        )
    revision = evidence["requirementsRevision"]
    if not isinstance(revision, int) or isinstance(revision, bool) or revision < 0:
        raise StateError("tooling evidence.requirementsRevision must be non-negative")
    if not isinstance(evidence["newSessionRequired"], bool):
        raise StateError("tooling evidence.newSessionRequired must be boolean")
    _validate_blockers(evidence["blockers"], "tooling evidence.blockers")


def validate_skills_evidence(evidence: Dict[str, Any]) -> None:
    if not isinstance(evidence, dict):
        raise StateError("skills evidence must be an object")
    required = (
        "kitVersion",
        "expectedSkills",
        "verifiedSkills",
        "collisions",
        "discovery",
        "newSessionRequired",
        "blockers",
    )
    _require_keys(evidence, required, "skills evidence")
    _only_keys(evidence, required, "skills evidence")
    _require_nonempty_text(evidence["kitVersion"], "skills evidence.kitVersion")
    _validate_text_list(evidence["expectedSkills"], "skills evidence.expectedSkills")
    _validate_text_list(evidence["verifiedSkills"], "skills evidence.verifiedSkills")
    if set(evidence["expectedSkills"]) != set(REQUIRED_SKILLS):
        raise StateError(
            "skills evidence.expectedSkills must contain the full bundled catalog"
        )
    if set(evidence["verifiedSkills"]) - set(evidence["expectedSkills"]):
        raise StateError("skills evidence.verifiedSkills contains unknown skills")
    _validate_text_list(
        evidence["collisions"], "skills evidence.collisions", allow_empty=True
    )
    discovery = evidence["discovery"]
    if not isinstance(discovery, dict) or set(discovery) != {"copilotCli", "vsCode"}:
        raise StateError("skills evidence.discovery must contain copilotCli and vsCode")
    for surface, status in discovery.items():
        if status not in {"verified", "blocked", "not_tested"}:
            raise StateError(f"skills evidence.discovery.{surface} has invalid status")
    if not isinstance(evidence["newSessionRequired"], bool):
        raise StateError("skills evidence.newSessionRequired must be boolean")
    _validate_blockers(evidence["blockers"], "skills evidence.blockers")


def validate_hooks_evidence(evidence: Dict[str, Any]) -> None:
    if not isinstance(evidence, dict):
        raise StateError("hooks evidence must be an object")
    required = (
        "enabled",
        "selectedHooks",
        "configPath",
        "checks",
        "verifiedSurfaces",
        "blockers",
    )
    _require_keys(evidence, required, "hooks evidence")
    _only_keys(evidence, required, "hooks evidence")
    if not isinstance(evidence["enabled"], bool):
        raise StateError("hooks evidence.enabled must be boolean")
    _validate_text_list(
        evidence["selectedHooks"], "hooks evidence.selectedHooks", allow_empty=True
    )
    _validate_workspace_path(evidence["configPath"], "hooks evidence.configPath")
    checks = evidence["checks"]
    if not isinstance(checks, list):
        raise StateError("hooks evidence.checks must be an array")
    seen = set()
    for index, check in enumerate(checks):
        label = f"hooks evidence.checks[{index}]"
        if not isinstance(check, dict):
            raise StateError(f"{label} must be an object")
        _require_keys(check, ("id", "status", "detail"), label)
        _only_keys(check, ("id", "status", "detail"), label)
        _validate_id(check["id"], f"{label}.id", ID_RE)
        if check["id"] in seen:
            raise StateError("hooks evidence.checks contains duplicate ids")
        seen.add(check["id"])
        if check["status"] not in {"passed", "failed", "blocked"}:
            raise StateError(f"{label}.status is invalid")
        _require_nonempty_text(check["detail"], f"{label}.detail")
    _validate_text_list(
        evidence["verifiedSurfaces"],
        "hooks evidence.verifiedSurfaces",
        allow_empty=True,
    )
    _validate_blockers(evidence["blockers"], "hooks evidence.blockers")
    if evidence["enabled"] and not evidence["selectedHooks"]:
        raise StateError("enabled hooks evidence requires selectedHooks")


def _topic_has_blockers(topic: str, evidence: Dict[str, Any]) -> bool:
    if topic == "instructions":
        return _instructions_have_blockers(evidence)
    return bool(evidence["blockers"])


def _read_text_artifact(path: Path, label: str) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        raise StateError(f"cannot read UTF-8 {label}: {path}: {exc}") from exc


def _has_apply_to_frontmatter(text: str) -> bool:
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return False
    try:
        end = next(
            index
            for index, line in enumerate(lines[1:], start=1)
            if line.strip() == "---"
        )
    except StopIteration:
        return False
    return any(re.fullmatch(r"applyTo:\s*\S.*", line) for line in lines[1:end])


def _validate_instruction_artifacts(root: Path, evidence: Dict[str, Any]) -> None:
    for relative in evidence["generatedFiles"]:
        artifact = (root / relative).resolve()
        if not _is_within(artifact, root.resolve()):
            raise StateError(
                f"instruction artifact resolves outside repository: {relative}"
            )
        _require_artifact(artifact, f"instruction artifact {relative}")
        if relative.startswith(".github/instructions/") and relative.endswith(
            ".instructions.md"
        ):
            scoped = _read_text_artifact(artifact, f"scoped instruction {relative}")
            if not _has_apply_to_frontmatter(scoped):
                raise StateError(
                    f"scoped instruction {relative} must contain applyTo frontmatter"
                )

    agents = _read_text_artifact(root / "AGENTS.md", "AGENTS.md")
    lowered = agents.lower()
    for marker in INSTRUCTION_PLACEHOLDERS:
        if marker in lowered:
            raise StateError(
                f"AGENTS.md still contains AKMaestro placeholder: {marker}"
            )
    for heading in INSTRUCTION_HEADINGS:
        if not re.search(rf"^##\s+{re.escape(heading)}\s*$", agents, re.MULTILINE):
            raise StateError(f"AGENTS.md is missing required section: {heading}")

    copilot = _read_text_artifact(
        root / ".github" / "copilot-instructions.md", "copilot instructions"
    )
    if "AGENTS.md" not in copilot:
        raise StateError(".github/copilot-instructions.md must point to AGENTS.md")

    tests = _read_text_artifact(
        root / ".github" / "instructions" / "tests.instructions.md",
        "test instructions",
    )
    if not _has_apply_to_frontmatter(tests):
        raise StateError("tests.instructions.md must contain applyTo frontmatter")
    if "<test command>" in tests.lower():
        raise StateError(
            "tests.instructions.md still contains the test command placeholder"
        )

    referenced = {
        check["checkId"]: check
        for result in evidence["commandResults"].values()
        for check in result["checks"]
    }
    if referenced:
        ledger_path = _action_checks_path(root)
        _require_artifact(ledger_path, "controller action-check ledger")
        ledger = _read_json(ledger_path)
        validate_action_checks(ledger)
        recorded = {check["checkId"]: check for check in ledger["checks"]}
        for check_id, check in referenced.items():
            if recorded.get(check_id) != check:
                raise StateError(
                    f"instructions evidence check {check_id} does not match the controller ledger"
                )


def _validate_topic_artifacts(root: Path, state: Dict[str, Any]) -> None:
    if state["topic"] == "instructions":
        _validate_instruction_artifacts(root, state["evidence"])
    elif state["topic"] == "tooling":
        evidence = state["evidence"]
        requirements = _read_json(_requirements_path(root))
        validate_requirements(requirements)
        if evidence["requirementsRevision"] != requirements["revision"]:
            raise StateError(
                "tooling evidence references a stale requirements revision"
            )
        for path in evidence["graphify"]["graphPaths"]:
            _resolve_workspace_path(root, path, "tooling graph path")
    elif state["topic"] == "skills":
        evidence = state["evidence"]
        missing = []
        for skill in evidence["verifiedSkills"]:
            skill_path = root / ".github" / "skills" / skill / "SKILL.md"
            if not _is_within(skill_path.resolve(), root.resolve()):
                raise StateError(f"skill {skill} resolves outside the repository")
            if not skill_path.is_file():
                missing.append(skill)
                continue
            text = _read_text_artifact(skill_path, f"skill {skill}")
            if not re.search(rf"^name:\s*{re.escape(skill)}\s*$", text, re.MULTILINE):
                raise StateError(
                    f"skill {skill} frontmatter name does not match its directory"
                )
        if missing:
            raise StateError(
                "verified skills are missing: " + ", ".join(sorted(missing))
            )
    elif state["topic"] == "hooks":
        evidence = state["evidence"]
        config = _resolve_workspace_path(
            root, evidence["configPath"], "hooks config path"
        )
        if evidence["enabled"]:
            _require_artifact(config, "enabled hooks config")
            hooks = _read_json(config)
            if hooks.get("disableAllHooks") is not False:
                raise StateError(
                    "hooks evidence says enabled but disableAllHooks is not false"
                )


def write_topic_evidence(
    root: Path,
    topic: str,
    evidence: Dict[str, Any],
    expected_revision: Optional[int] = None,
) -> Dict[str, Any]:
    if topic not in TOPICS:
        raise StateError(f"unknown setup topic: {topic}")
    path = root / ".agentic" / "setup" / f"{topic}-state.json"
    with _state_lock(root, path):
        revision = 0
        created_at = _now()
        if path.exists():
            existing = _read_json(path)
            validate_topic_evidence(existing)
            _validate_topic_artifacts(root, existing)
            if existing["evidence"] == evidence:
                return existing
            _expect_revision(existing, expected_revision)
            revision = existing["revision"] + 1
            created_at = existing["createdAt"]
        elif expected_revision not in (None, 0):
            raise StateError(
                f"stale evidence state: expected revision {expected_revision}, found none"
            )
        now = _now()
        state = {
            "$schema": "../schemas/setup-evidence.schema.json",
            "version": STATE_VERSION,
            "revision": revision,
            "topic": topic,
            "evidence": evidence,
            "createdAt": created_at,
            "updatedAt": now,
        }
        validate_topic_evidence(state)
        _validate_topic_artifacts(root, state)
        _atomic_write_json(path, state)
        return state


def validate_topic_evidence(state: Dict[str, Any]) -> None:
    _require_schema(state, "../schemas/setup-evidence.schema.json", "setup evidence")
    _require_version(state, "setup evidence")
    _require_revision(state, "setup evidence")
    _require_keys(
        state,
        ("topic", "evidence", "createdAt", "updatedAt"),
        "setup evidence",
    )
    if state["topic"] not in TOPICS:
        raise StateError(f"unknown setup evidence topic: {state['topic']!r}")
    if not isinstance(state["evidence"], dict):
        raise StateError("setup evidence.evidence must be an object")
    if state["topic"] == "instructions":
        validate_instructions_evidence(state["evidence"])
    elif state["topic"] == "tooling":
        validate_tooling_evidence(state["evidence"])
    elif state["topic"] == "skills":
        validate_skills_evidence(state["evidence"])
    elif state["topic"] == "hooks":
        validate_hooks_evidence(state["evidence"])
    _only_keys(
        state,
        (
            "$schema",
            "version",
            "revision",
            "topic",
            "evidence",
            "createdAt",
            "updatedAt",
        ),
        "setup evidence",
    )
    _require_timestamp(state["createdAt"], "setup evidence.createdAt")
    _require_timestamp(state["updatedAt"], "setup evidence.updatedAt")


def _validate_action(value: Dict[str, Any], label: str) -> None:
    if not isinstance(value, dict):
        raise StateError(f"{label} must be an object")
    command = value.get("command")
    if not isinstance(command, list) or not command:
        raise StateError(f"{label}.command must be a non-empty argument array")
    for index, part in enumerate(command):
        _require_nonempty_text(part, f"{label}.command[{index}]")
    cwd = value.get("cwd", ".")
    _validate_workspace_path(cwd, f"{label}.cwd")
    timeout = value.get("timeoutSeconds", 900)
    if (
        not isinstance(timeout, int)
        or isinstance(timeout, bool)
        or not 1 <= timeout <= 3600
    ):
        raise StateError(f"{label}.timeoutSeconds must be an integer from 1 to 3600")
    _only_keys(value, ("command", "cwd", "timeoutSeconds"), label)


def run_remediation(
    root: Path, action: Dict[str, Any], approved: bool
) -> Dict[str, Any]:
    """Run one explicitly approved local remediation without a shell."""

    if not approved:
        raise StateError("remediation requires explicit --approved")
    _validate_action(action, "remediation action")
    requirements = _read_json(_requirements_path(root))
    validate_requirements(requirements)
    recorded = [
        item[key]
        for collection, key in (
            (requirements["tools"], "install"),
            (requirements["artifacts"], "remediation"),
        )
        for item in collection
        if key in item
    ]
    if action not in recorded:
        raise StateError(
            "remediation action must exactly match committed environment requirements"
        )
    cwd = _resolve_workspace_path(
        root,
        action.get("cwd", "."),
        "remediation action.cwd",
        include_read_only=False,
    )
    if not cwd.is_dir():
        raise StateError(f"remediation working directory does not exist: {cwd}")
    timeout = action.get("timeoutSeconds", 900)
    try:
        proc = subprocess.run(
            action["command"],
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
        return {
            "status": "passed" if proc.returncode == 0 else "failed",
            "exitCode": proc.returncode,
            # Remediation output can contain machine-local secrets. The caller
            # only needs the exit status before rerunning readiness probes.
            "detail": f"command exited {proc.returncode}",
        }
    except FileNotFoundError:
        return {
            "status": "failed",
            "detail": f"command not found: {action['command'][0]}",
        }
    except subprocess.TimeoutExpired:
        return {
            "status": "failed",
            "detail": f"command timed out after {timeout}s",
        }
    except OSError as exc:
        return {"status": "failed", "detail": f"command could not run: {exc}"}


def validate_requirements(state: Dict[str, Any]) -> None:
    _require_schema(
        state,
        "../schemas/environment-requirements.schema.json",
        "environment requirements",
    )
    _require_version(state, "environment requirements")
    _require_revision(state, "environment requirements")
    _require_keys(
        state,
        ("tools", "artifacts", "createdAt", "updatedAt"),
        "environment requirements",
    )
    if not isinstance(state["tools"], list) or not isinstance(state["artifacts"], list):
        raise StateError("environment requirements tools and artifacts must be arrays")
    _only_keys(
        state,
        (
            "$schema",
            "version",
            "revision",
            "tools",
            "artifacts",
            "createdAt",
            "updatedAt",
        ),
        "environment requirements",
    )
    _require_timestamp(state["createdAt"], "environment requirements.createdAt")
    _require_timestamp(state["updatedAt"], "environment requirements.updatedAt")
    seen = set()
    for tool in state["tools"]:
        if not isinstance(tool, dict):
            raise StateError("each tool requirement must be an object")
        _require_keys(tool, ("id", "label", "required", "probe"), "tool requirement")
        _only_keys(
            tool, ("id", "label", "required", "probe", "install"), "tool requirement"
        )
        _validate_id(tool["id"], "tool requirement id", ID_RE)
        if tool["id"] in seen:
            raise StateError(f"duplicate requirement id: {tool['id']}")
        seen.add(tool["id"])
        if not isinstance(tool["label"], str) or not tool["label"].strip():
            raise StateError(f"tool requirement {tool['id']} needs a label")
        if not isinstance(tool["required"], bool):
            raise StateError(f"tool requirement {tool['id']}.required must be boolean")
        probe = tool["probe"]
        if not isinstance(probe, dict) or not isinstance(probe.get("command"), list):
            raise StateError(f"tool requirement {tool['id']} needs probe.command array")
        _only_keys(
            probe,
            ("command", "cwd", "timeoutSeconds", "contains"),
            f"tool requirement {tool['id']}.probe",
        )
        if not probe["command"] or not all(
            isinstance(part, str) and part for part in probe["command"]
        ):
            raise StateError(f"tool requirement {tool['id']} probe.command is invalid")
        timeout = probe.get("timeoutSeconds", 30)
        if (
            not isinstance(timeout, int)
            or isinstance(timeout, bool)
            or not 1 <= timeout <= 120
        ):
            raise StateError(
                f"tool requirement {tool['id']} probe timeout must be 1..120"
            )
        contains = probe.get("contains")
        if contains is not None and (not isinstance(contains, str) or not contains):
            raise StateError(
                f"tool requirement {tool['id']} probe.contains must be text"
            )
        _validate_workspace_path(
            probe.get("cwd", "."), f"tool requirement {tool['id']}.probe.cwd"
        )
        install = tool.get("install")
        if install is not None:
            _validate_action(install, f"tool requirement {tool['id']}.install")
    for artifact in state["artifacts"]:
        if not isinstance(artifact, dict):
            raise StateError("each artifact requirement must be an object")
        _require_keys(artifact, ("id", "path", "required"), "artifact requirement")
        _only_keys(
            artifact, ("id", "path", "required", "remediation"), "artifact requirement"
        )
        _validate_id(artifact["id"], "artifact requirement id", ID_RE)
        if artifact["id"] in seen:
            raise StateError(f"duplicate requirement id: {artifact['id']}")
        seen.add(artifact["id"])
        if not isinstance(artifact["required"], bool):
            raise StateError(
                f"artifact requirement {artifact['id']}.required must be boolean"
            )
        _validate_workspace_path(
            artifact["path"], f"artifact requirement {artifact['id']}.path"
        )
        remediation = artifact.get("remediation")
        if remediation is not None:
            _validate_action(
                remediation, f"artifact requirement {artifact['id']}.remediation"
            )

    required_tools = {tool["id"] for tool in state["tools"] if tool["required"]}
    required_artifacts = {
        artifact["id"] for artifact in state["artifacts"] if artifact["required"]
    }
    for required_id in ("uv", "graphify", "graphify-query"):
        if required_id not in required_tools:
            raise StateError(f"environment requirements must require {required_id}")
    if not any(tool_id.startswith("lsp-") for tool_id in required_tools):
        raise StateError(
            "environment requirements must require at least one lsp-* tool"
        )
    if "graphify-graph" not in required_artifacts:
        raise StateError("environment requirements must require graphify-graph")


def write_requirements(
    root: Path,
    body: Dict[str, Any],
    expected_revision: Optional[int] = None,
) -> Dict[str, Any]:
    path = _requirements_path(root)
    tools = body.get("tools")
    artifacts = body.get("artifacts")
    with _state_lock(root, path):
        revision = 0
        created_at = _now()
        if path.exists():
            existing = _read_json(path)
            validate_requirements(existing)
            if existing["tools"] == tools and existing["artifacts"] == artifacts:
                return existing
            _expect_revision(existing, expected_revision)
            revision = existing["revision"] + 1
            created_at = existing["createdAt"]
        elif expected_revision not in (None, 0):
            raise StateError(
                f"stale requirements: expected revision {expected_revision}, found none"
            )
        now = _now()
        state = {
            "$schema": "../schemas/environment-requirements.schema.json",
            "version": STATE_VERSION,
            "revision": revision,
            "tools": tools,
            "artifacts": artifacts,
            "createdAt": created_at,
            "updatedAt": now,
        }
        validate_requirements(state)
        _atomic_write_json(path, state)
        return state


def requirements_hash(requirements: Dict[str, Any]) -> str:
    validate_requirements(requirements)
    canonical = json.dumps(
        {"tools": requirements["tools"], "artifacts": requirements["artifacts"]},
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def check_readiness(root: Path, write: bool = True) -> Tuple[Dict[str, Any], bool]:
    requirements = _read_json(_requirements_path(root))
    validate_requirements(requirements)
    checks: List[Dict[str, Any]] = []

    for tool in requirements["tools"]:
        command = tool["probe"]["command"]
        timeout = tool["probe"].get("timeoutSeconds", 30)
        probe_cwd = _resolve_workspace_path(
            root,
            tool["probe"].get("cwd", "."),
            f"tool requirement {tool['id']}.probe.cwd",
            include_read_only=False,
        )
        if not probe_cwd.is_dir():
            checks.append(
                {
                    "id": tool["id"],
                    "type": "tool",
                    "required": tool["required"],
                    "status": "missing",
                    "detail": f"probe working directory does not exist: {probe_cwd}",
                    **({"remediation": tool["install"]} if tool.get("install") else {}),
                }
            )
            continue
        try:
            proc = subprocess.run(
                command,
                cwd=probe_cwd,
                capture_output=True,
                text=True,
                timeout=timeout,
                check=False,
            )
            full_output = "\n".join(
                part for part in (proc.stdout, proc.stderr) if part
            ).strip()
            combined = full_output.splitlines()
            detail = combined[0][:500] if combined else f"exit {proc.returncode}"
            contains = tool["probe"].get("contains")
            status = (
                "ok"
                if proc.returncode == 0 and (not contains or contains in full_output)
                else "missing"
            )
            if proc.returncode == 0 and contains and contains not in full_output:
                detail = f"probe output did not contain {contains!r}"
        except FileNotFoundError:
            status = "missing"
            detail = f"command not found: {command[0]}"
        except subprocess.TimeoutExpired:
            status = "missing"
            detail = f"probe timed out after {timeout}s"
        except OSError as exc:
            status = "missing"
            detail = f"probe could not run: {exc}"
        checks.append(
            {
                "id": tool["id"],
                "type": "tool",
                "required": tool["required"],
                "status": status,
                "detail": detail,
                **({"remediation": tool["install"]} if tool.get("install") else {}),
            }
        )

    for artifact in requirements["artifacts"]:
        artifact_path = _resolve_workspace_path(
            root,
            artifact["path"],
            f"artifact requirement {artifact['id']}.path",
            include_read_only=False,
        )
        exists = artifact_path.is_file()
        checks.append(
            {
                "id": artifact["id"],
                "type": "artifact",
                "required": artifact["required"],
                "status": "ok" if exists else "missing",
                "detail": artifact["path"],
                **(
                    {"remediation": artifact["remediation"]}
                    if artifact.get("remediation")
                    else {}
                ),
            }
        )

    ready = all(check["status"] == "ok" for check in checks if check["required"])
    readiness = {
        "$schema": "../schemas/local-readiness.schema.json",
        "version": STATE_VERSION,
        "requirementsHash": requirements_hash(requirements),
        "status": "ready" if ready else "not_ready",
        "checks": checks,
        "checkedAt": _now(),
    }
    validate_readiness(readiness)
    if write:
        path = _readiness_path(root)
        with _state_lock(root, path):
            _atomic_write_json(path, readiness)
    return readiness, ready


def validate_readiness(state: Dict[str, Any]) -> None:
    _require_schema(state, "../schemas/local-readiness.schema.json", "local readiness")
    _require_version(state, "local readiness")
    _require_keys(
        state, ("requirementsHash", "status", "checks", "checkedAt"), "local readiness"
    )
    _only_keys(
        state,
        ("$schema", "version", "requirementsHash", "status", "checks", "checkedAt"),
        "local readiness",
    )
    if not isinstance(state["requirementsHash"], str) or not re.fullmatch(
        r"[0-9a-f]{64}", state["requirementsHash"]
    ):
        raise StateError("local readiness requirementsHash must be sha256")
    if not isinstance(state["status"], str) or state["status"] not in {
        "ready",
        "not_ready",
    }:
        raise StateError("local readiness status must be ready or not_ready")
    if not isinstance(state["checks"], list):
        raise StateError("local readiness checks must be an array")
    seen = set()
    for check in state["checks"]:
        if not isinstance(check, dict):
            raise StateError("each local readiness check must be an object")
        _require_keys(
            check, ("id", "type", "required", "status", "detail"), "readiness check"
        )
        _only_keys(
            check,
            ("id", "type", "required", "status", "detail", "remediation"),
            "readiness check",
        )
        _validate_id(check["id"], "readiness check id", ID_RE)
        if check["id"] in seen:
            raise StateError(f"duplicate readiness check: {check['id']}")
        seen.add(check["id"])
        if not isinstance(check["type"], str) or check["type"] not in {
            "tool",
            "artifact",
        }:
            raise StateError(f"invalid readiness check type: {check['type']!r}")
        if not isinstance(check["required"], bool):
            raise StateError(f"readiness check {check['id']}.required must be boolean")
        if not isinstance(check["status"], str) or check["status"] not in {
            "ok",
            "missing",
        }:
            raise StateError(f"invalid readiness check status: {check['status']!r}")
        if not isinstance(check["detail"], str):
            raise StateError(f"readiness check {check['id']}.detail must be text")
        if "remediation" in check:
            _validate_action(
                check["remediation"], f"readiness check {check['id']}.remediation"
            )
    expected_ready = all(
        check["status"] == "ok" for check in state["checks"] if check["required"]
    )
    if (state["status"] == "ready") is not expected_ready:
        raise StateError("local readiness status disagrees with its required checks")
    _require_timestamp(state["checkedAt"], "local readiness.checkedAt")


def require_workflow_ready(root: Path) -> None:
    """Require shared initialization and current worktree readiness."""

    if not _setup_path(root).is_file():
        raise StateError(
            "repository initialization is incomplete; the team lead must finish /akmaestro-init"
        )
    setup = _read_json(_setup_path(root))
    if setup_summary(setup)["overall"] != "complete":
        raise StateError(
            "repository initialization is incomplete; the team lead must finish /akmaestro-init"
        )
    validate_setup_integrity(root, setup)
    _read_json(_requirements_path(root))
    _readiness, ready = check_readiness(root, write=True)
    if not ready:
        raise StateError(
            "developer environment is not ready; run readiness-check and remediate"
        )


def new_feature_state(feature_id: str, title: str) -> Dict[str, Any]:
    _validate_id(feature_id, "feature id", ID_RE)
    if not title.strip():
        raise StateError("feature title cannot be empty")
    now = _now()
    return {
        "$schema": "../../schemas/feature-state.schema.json",
        "version": STATE_VERSION,
        "revision": 0,
        "featureId": feature_id,
        "title": title.strip(),
        "phase": "understanding",
        "currentStory": None,
        "stories": [],
        "gates": [],
        "history": [],
        "createdAt": now,
        "updatedAt": now,
    }


def validate_feature_state(state: Dict[str, Any]) -> None:
    _require_schema(state, "../../schemas/feature-state.schema.json", "feature state")
    _require_version(state, "feature state")
    _require_revision(state, "feature state")
    _require_keys(
        state,
        (
            "featureId",
            "title",
            "phase",
            "currentStory",
            "stories",
            "gates",
            "history",
            "createdAt",
            "updatedAt",
        ),
        "feature state",
    )
    _only_keys(
        state,
        (
            "$schema",
            "version",
            "revision",
            "featureId",
            "title",
            "phase",
            "currentStory",
            "stories",
            "gates",
            "history",
            "createdAt",
            "updatedAt",
            "completedAt",
        ),
        "feature state",
    )
    _validate_id(state["featureId"], "feature id", ID_RE)
    if state["phase"] not in FEATURE_PHASES:
        raise StateError(f"invalid feature phase: {state['phase']!r}")
    if not isinstance(state["title"], str) or not state["title"].strip():
        raise StateError("feature title cannot be empty")
    if not isinstance(state["stories"], list):
        raise StateError("feature stories must be an array")
    story_ids = []
    for story in state["stories"]:
        if not isinstance(story, dict):
            raise StateError("each story state must be an object")
        _require_keys(story, ("id", "step", "mode", "reviewAttempts"), "story state")
        _only_keys(story, ("id", "step", "mode", "reviewAttempts"), "story state")
        _validate_id(story["id"], "story id", STORY_ID_RE)
        if story["step"] not in STORY_STEPS:
            raise StateError(f"invalid story step for {story['id']}: {story['step']!r}")
        if story["mode"] not in STORY_MODES:
            raise StateError(f"invalid story mode for {story['id']}: {story['mode']!r}")
        attempts = story["reviewAttempts"]
        if not isinstance(attempts, int) or isinstance(attempts, bool) or attempts < 0:
            raise StateError(f"story {story['id']} reviewAttempts must be non-negative")
        story_ids.append(story["id"])
    if len(story_ids) != len(set(story_ids)):
        raise StateError("feature story ids must be unique")
    current = state["currentStory"]
    if current is not None and current not in story_ids:
        raise StateError("currentStory must identify a story in the feature")
    if state["phase"] == "story_loop" and current is None:
        raise StateError("story_loop phase requires currentStory")
    if state["phase"] != "story_loop" and current is not None:
        raise StateError("currentStory is only valid during story_loop")
    if state["phase"] in {"reviewing", "retrospective", "complete"}:
        if any(story["step"] != "complete" for story in state["stories"]):
            raise StateError(
                f"feature phase {state['phase']} requires every story to be complete"
            )
    if not isinstance(state["gates"], list) or not isinstance(state["history"], list):
        raise StateError("feature gates and history must be arrays")
    if state["phase"] == "story_loop":
        first_incomplete = next(
            (story["id"] for story in state["stories"] if story["step"] != "complete"),
            None,
        )
        if first_incomplete is None:
            raise StateError("story_loop phase requires an incomplete story")
        if current != first_incomplete:
            raise StateError("currentStory must be the first incomplete story")
    expected_gates = {
        "understanding": [],
        "framing": ["understand"],
        "splitting": ["understand", "frame"],
        "story_loop": ["understand", "frame", "split"],
        "reviewing": ["understand", "frame", "split"],
        "retrospective": ["understand", "frame", "split", "feature-review"],
        "complete": ["understand", "frame", "split", "feature-review", "retro"],
    }
    gate_names = []
    for gate in state["gates"]:
        if not isinstance(gate, dict):
            raise StateError("each feature gate must be an object")
        _require_keys(gate, ("name", "approvedAt"), "feature gate")
        _only_keys(gate, ("name", "approvedAt"), "feature gate")
        if not isinstance(gate["name"], str) or gate["name"] not in GATE_TRANSITIONS:
            raise StateError(f"invalid feature gate: {gate['name']!r}")
        _require_timestamp(
            gate["approvedAt"], f"feature gate {gate['name']}.approvedAt"
        )
        gate_names.append(gate["name"])
    if gate_names != expected_gates[state["phase"]]:
        raise StateError(f"feature gates disagree with phase {state['phase']}")
    if state["revision"] != len(state["history"]):
        raise StateError("feature revision must equal the number of history events")
    for index, event in enumerate(state["history"], start=1):
        if not isinstance(event, dict):
            raise StateError("each feature history event must be an object")
        _require_keys(event, ("revision", "event", "from", "to", "at"), "history event")
        _only_keys(event, ("revision", "event", "from", "to", "at"), "history event")
        if event["revision"] != index:
            raise StateError("feature history revisions must be contiguous")
        if not all(isinstance(event[key], str) for key in ("event", "from", "to")):
            raise StateError("feature history event/from/to must be text")
        _require_timestamp(event["at"], f"feature history revision {index}.at")
    _require_timestamp(state["createdAt"], "feature state.createdAt")
    _require_timestamp(state["updatedAt"], "feature state.updatedAt")
    if state["phase"] == "complete":
        if "completedAt" not in state:
            raise StateError("complete feature requires completedAt")
        _require_timestamp(state["completedAt"], "feature state.completedAt")
    elif "completedAt" in state:
        raise StateError("only a complete feature may contain completedAt")


def _feature_summary(state: Dict[str, Any]) -> Dict[str, Any]:
    validate_feature_state(state)
    current_story = None
    next_command = NEXT_COMMANDS.get(state["phase"])
    if state["phase"] == "story_loop":
        current_story = next(
            story for story in state["stories"] if story["id"] == state["currentStory"]
        )
        next_command = STORY_COMMANDS[current_story["step"]]
    return {
        "featureId": state["featureId"],
        "title": state["title"],
        "phase": state["phase"],
        "revision": state["revision"],
        "currentStory": current_story,
        "nextCommand": next_command,
        "stories": state["stories"],
    }


def _append_history(
    state: Dict[str, Any], event: str, old: str, new: str, now: str
) -> None:
    state["history"].append(
        {
            "revision": state["revision"] + 1,
            "event": event,
            "from": old,
            "to": new,
            "at": now,
        }
    )


def feature_create(root: Path, feature_id: str, title: str) -> Dict[str, Any]:
    require_workflow_ready(root)
    path = _feature_path(root, feature_id)
    with _state_lock(root, path):
        if path.exists():
            state = _read_json(path)
            validate_feature_state(state)
            if state["title"] != title.strip():
                raise StateError(
                    f"feature {feature_id} already exists with a different title"
                )
        else:
            state = new_feature_state(feature_id, title)
            _atomic_write_json(path, state)
    feature_select(root, feature_id)
    return state


def feature_select(root: Path, feature_id: str) -> Dict[str, Any]:
    state = _read_json(_feature_path(root, feature_id))
    validate_feature_state(state)
    if state["phase"] == "complete":
        raise StateError(f"cannot select completed feature: {feature_id}")
    active = {
        "$schema": "../schemas/active-feature.schema.json",
        "version": STATE_VERSION,
        "featureId": feature_id,
        "selectedAt": _now(),
    }
    path = _active_path(root)
    with _state_lock(root, path):
        _atomic_write_json(path, active)
    return active


def feature_clear_active(root: Path, feature_id: Optional[str] = None) -> None:
    path = _active_path(root)
    with _state_lock(root, path):
        if not path.exists():
            return
        try:
            active = _read_json(path)
            validate_active_feature(active)
        except StateError:
            path.unlink()
            return
        if feature_id is None or active.get("featureId") == feature_id:
            path.unlink()


def feature_add_stories(
    root: Path,
    feature_id: str,
    story_ids: Sequence[str],
    mode: str,
    expected_revision: Optional[int] = None,
) -> Dict[str, Any]:
    require_workflow_ready(root)
    if not story_ids:
        raise StateError("at least one --story is required")
    if mode not in STORY_MODES:
        raise StateError(f"invalid story mode: {mode}")
    path = _feature_path(root, feature_id)
    for story_id in story_ids:
        _validate_id(story_id, "story id", STORY_ID_RE)
        _require_artifact(
            path.parent / "stories" / f"{story_id}.md",
            f"story artifact {story_id}",
        )
    if len(set(story_ids)) != len(story_ids):
        raise StateError("story ids must be unique")
    with _state_lock(root, path):
        state = _read_json(path)
        validate_feature_state(state)
        existing_ids = [story["id"] for story in state["stories"]]
        if existing_ids == list(story_ids) and all(
            story["mode"] == mode for story in state["stories"]
        ):
            return state
        _expect_revision(state, expected_revision)
        if state["phase"] != "splitting":
            raise StateError("stories can only be added during the splitting phase")
        if state["stories"]:
            raise StateError(
                "stories are already registered; do not replace them implicitly"
            )
        now = _now()
        state["stories"] = [
            {"id": story_id, "step": "prime", "mode": mode, "reviewAttempts": 0}
            for story_id in story_ids
        ]
        _append_history(state, "stories-added", "none", ",".join(story_ids), now)
        state["revision"] += 1
        state["updatedAt"] = now
        validate_feature_state(state)
        _atomic_write_json(path, state)
        return state


def feature_advance_gate(
    root: Path,
    feature_id: str,
    gate: str,
    expected_revision: Optional[int] = None,
) -> Dict[str, Any]:
    require_workflow_ready(root)
    if gate not in GATE_TRANSITIONS:
        raise StateError(f"unknown feature gate: {gate}")
    path = _feature_path(root, feature_id)
    with _state_lock(root, path):
        state = _read_json(path)
        validate_feature_state(state)
        if any(item.get("name") == gate for item in state["gates"]):
            return state
        _expect_revision(state, expected_revision)
        expected_phase, next_phase = GATE_TRANSITIONS[gate]
        if state["phase"] != expected_phase:
            raise StateError(
                f"gate {gate} requires phase {expected_phase}, found {state['phase']}"
            )
        if gate == "split" and not state["stories"]:
            raise StateError("split gate requires at least one registered story")
        required_artifacts = {
            "understand": ("understanding.md", "understanding artifact"),
            "frame": ("feature.md", "feature artifact"),
            "feature-review": ("review.md", "feature review artifact"),
            "retro": ("retro.md", "retrospective artifact"),
        }
        if gate in required_artifacts:
            name, label = required_artifacts[gate]
            _require_artifact(path.parent / name, label)
        now = _now()
        state["gates"].append({"name": gate, "approvedAt": now})
        _append_history(state, f"gate:{gate}", expected_phase, next_phase, now)
        state["phase"] = next_phase
        if gate == "split":
            state["currentStory"] = state["stories"][0]["id"]
        state["revision"] += 1
        state["updatedAt"] = now
        if next_phase == "complete":
            state["completedAt"] = now
        validate_feature_state(state)
        _atomic_write_json(path, state)
    if next_phase == "complete":
        feature_clear_active(root, feature_id)
    return state


def story_transition(
    root: Path,
    feature_id: str,
    story_id: str,
    to_step: str,
    expected_revision: Optional[int] = None,
) -> Dict[str, Any]:
    require_workflow_ready(root)
    if to_step not in STORY_STEPS:
        raise StateError(f"unknown story step: {to_step}")
    path = _feature_path(root, feature_id)
    with _state_lock(root, path):
        state = _read_json(path)
        validate_feature_state(state)
        try:
            story = next(item for item in state["stories"] if item["id"] == story_id)
        except StopIteration as exc:
            raise StateError(f"unknown story: {story_id}") from exc
        current_step = story["step"]
        _require_artifact(
            path.parent / "stories" / f"{story_id}.md", f"story artifact {story_id}"
        )
        if current_step == to_step:
            return state
        _expect_revision(state, expected_revision)

        reopening = state["phase"] == "reviewing" and current_step == "complete"
        if reopening:
            if to_step not in {"plan", "implement"}:
                raise StateError(
                    "feature review can reopen a story only to plan or implement"
                )
        else:
            if state["phase"] != "story_loop":
                raise StateError("story transitions require the story_loop phase")
            if state["currentStory"] != story_id:
                raise StateError(f"story {story_id} is not the current story")
            if to_step not in STORY_TRANSITIONS[current_step]:
                raise StateError(
                    f"illegal story transition: {current_step} -> {to_step}"
                )

        now = _now()
        if current_step == "review" and to_step in {"plan", "implement"}:
            story["reviewAttempts"] += 1
        if reopening:
            story["reviewAttempts"] += 1
            state["phase"] = "story_loop"
            state["currentStory"] = story_id
            old = f"reviewing:{current_step}"
        else:
            old = current_step
        story["step"] = to_step
        _append_history(state, f"story:{story_id}", old, to_step, now)

        if to_step == "complete":
            next_story = next(
                (item for item in state["stories"] if item["step"] != "complete"), None
            )
            if next_story:
                state["currentStory"] = next_story["id"]
            else:
                state["phase"] = "reviewing"
                state["currentStory"] = None

        state["revision"] += 1
        state["updatedAt"] = now
        validate_feature_state(state)
        _atomic_write_json(path, state)
        return state


def story_set_mode(
    root: Path,
    feature_id: str,
    story_id: str,
    mode: str,
    expected_revision: Optional[int] = None,
) -> Dict[str, Any]:
    require_workflow_ready(root)
    if mode not in STORY_MODES:
        raise StateError(f"invalid story mode: {mode}")
    path = _feature_path(root, feature_id)
    with _state_lock(root, path):
        state = _read_json(path)
        validate_feature_state(state)
        try:
            story = next(item for item in state["stories"] if item["id"] == story_id)
        except StopIteration as exc:
            raise StateError(f"unknown story: {story_id}") from exc
        if story["mode"] == mode:
            return state
        _expect_revision(state, expected_revision)
        if (
            state["phase"] != "story_loop"
            or state["currentStory"] != story_id
            or story["step"] != "prime"
        ):
            raise StateError(
                "story mode can only change before the current story is primed"
            )
        now = _now()
        old_mode = story["mode"]
        story["mode"] = mode
        _append_history(state, f"story-mode:{story_id}", old_mode, mode, now)
        state["revision"] += 1
        state["updatedAt"] = now
        validate_feature_state(state)
        _atomic_write_json(path, state)
        return state


def feature_states(root: Path) -> List[Dict[str, Any]]:
    directory = root / ".agentic" / "features"
    if not directory.is_dir():
        return []
    states = []
    for path in sorted(directory.glob("*/state.json")):
        state = _read_json(path)
        validate_feature_state(state)
        states.append(state)
    return states


def feature_list(root: Path) -> Dict[str, Any]:
    states = feature_states(root)
    summaries = [_feature_summary(state) for state in states]
    active_id = None
    active_path = _active_path(root)
    if active_path.exists():
        active = _read_json(active_path)
        validate_active_feature(active)
        active_id = active["featureId"]
        if not any(
            item["featureId"] == active_id and item["phase"] != "complete"
            for item in summaries
        ):
            active_id = None
    open_features = [item for item in summaries if item["phase"] != "complete"]
    return {"activeFeature": active_id, "open": open_features, "all": summaries}


def _setup_inventory(root: Path, state: Dict[str, Any]) -> Dict[str, Any]:
    blocked = [
        {"topic": topic, "reason": item["blocker"]}
        for topic, item in state["topics"].items()
        if item["status"] == "blocked"
    ]
    pending: List[Dict[str, str]] = []
    instructions_path = root / ".agentic" / "setup" / "instructions-state.json"
    if instructions_path.is_file():
        instructions = _read_json(instructions_path)
        validate_topic_evidence(instructions)
        pending.extend(
            {"type": "module", "path": path}
            for path in instructions["evidence"]["pendingModules"]
        )

    shared = {
        ".github/AGENTIC.md",
        ".agentic/setup/initialization-state.json",
    }
    manifest_path = root / ".agentic" / "setup" / "kit-manifest.json"
    if manifest_path.is_file():
        try:
            manifest = _read_json(manifest_path)
            shared.update(
                path
                for path in manifest.get("files", {})
                if not path.startswith(".agentic/local/")
                and not path.startswith(".agentic/audit/")
            )
        except StateError:
            pass
    for topic in TOPICS:
        evidence_path = root / ".agentic" / "setup" / f"{topic}-state.json"
        if evidence_path.is_file():
            shared.add(str(evidence_path.relative_to(root)).replace(os.sep, "/"))
    if _requirements_path(root).is_file():
        shared.add(".agentic/setup/environment-requirements.json")
    if _action_checks_path(root).is_file():
        shared.add(".agentic/setup/action-checks.json")
    return {
        "sharedFiles": sorted(shared),
        "localPaths": [".agentic/local/", ".agentic/audit/"],
        "blockedItems": blocked,
        "pendingItems": pending,
    }


def _render_agentic_guide(root: Path) -> str:
    instructions = _read_json(root / ".agentic" / "setup" / "instructions-state.json")
    tooling = _read_json(root / ".agentic" / "setup" / "tooling-state.json")
    validate_topic_evidence(instructions)
    validate_topic_evidence(tooling)
    body = instructions["evidence"]
    requirements = _read_json(_requirements_path(root))
    validate_requirements(requirements)
    skills = sorted(
        path.parent.name for path in (root / ".github" / "skills").glob("*/SKILL.md")
    )
    hooks = hooks_status(root)

    lines = [
        "# AKMaestro Team Guide",
        "",
        "This repository is initialized for the AKMaestro agentic workflow.",
        "The team lead owns `/akmaestro-init`; developers start and resume work with `/feature`.",
        "Use `/status` for orientation and `/doctor` for a full health check.",
        "",
        "## Product",
        "",
        body["product"]["summary"],
        "",
        "## Canonical Commands",
        "",
    ]
    for command_id in INSTRUCTION_COMMANDS:
        definition = body["commands"][command_id]
        if definition["status"] == "configured":
            rendered = "; ".join(
                json.dumps(action["command"]) for action in definition["actions"]
            )
        else:
            rendered = f"not applicable: {definition['reason']}"
        lines.append(f"- **{command_id}**: `{rendered}`")
    lines.extend(["", "## Installed Skills", ""])
    lines.extend(f"- `/{skill}`" for skill in skills)
    lines.extend(
        [
            "",
            "## Hooks",
            "",
            f"- Status: {'enabled' if hooks['enabled'] else 'disabled'}",
            f"- Configuration: `{hooks['configPath']}`",
            "",
            "## Developer Requirements",
            "",
        ]
    )
    lines.extend(
        f"- `{tool['id']}`: {tool['label']} ({'required' if tool['required'] else 'optional'})"
        for tool in requirements["tools"]
    )
    lines.extend(
        [
            "",
            "Generated Graphifyy indexes are developer-local under `.agentic/local/graphs/`.",
            "They are never written into read-only sibling repositories.",
            "",
            "## Instruction Sources",
            "",
            "- `AGENTS.md` is the repository-wide source of truth.",
            "- `.github/instructions/*.instructions.md` contains path-scoped guidance.",
            "- `.github/copilot-instructions.md` is a short pointer to those sources.",
            "",
        ]
    )
    return "\n".join(lines)


def _validate_finalization(root: Path, state: Dict[str, Any]) -> None:
    if state["finalization"]["status"] != "complete":
        return
    guide = root / ".github" / "AGENTIC.md"
    if guide.is_symlink() or not _is_within(guide.parent.resolve(), root.resolve()):
        raise StateError("finalized AKMaestro team guide uses an unsafe path")
    _require_artifact(guide, "finalized AKMaestro team guide")
    actual = hashlib.sha256(guide.read_bytes()).hexdigest()
    if actual != state["finalization"]["guideHash"]:
        raise StateError(
            ".github/AGENTIC.md changed after setup finalization; rerun /akmaestro-init"
        )


def setup_status(root: Path) -> Dict[str, Any]:
    state = _read_json(_setup_path(root))
    summary = setup_summary(state)
    summary.update(_setup_inventory(root, state))
    if summary["finalized"]:
        try:
            _validate_finalization(root, state)
        except StateError as exc:
            summary["overall"] = "incomplete"
            summary["finalized"] = False
            summary["nextCommand"] = "/akmaestro-init"
            summary["finalizationError"] = str(exc)
    return summary


def finalize_setup(
    root: Path,
    expected_revision: Optional[int] = None,
    approved_guide_replace: bool = False,
    preview: bool = False,
) -> Dict[str, Any]:
    if preview and approved_guide_replace:
        raise StateError("setup finalization preview cannot approve replacement")
    path = _setup_path(root)
    with _state_lock(root, path):
        state = _read_json(path)
        validate_setup_state(state)
        if not setup_summary(state)["topicsComplete"]:
            raise StateError("all setup topics must be terminal before finalization")
        validate_setup_integrity(root, state)
        guide_path = root / ".github" / "AGENTIC.md"
        if not _is_within(guide_path.parent.resolve(), root.resolve()):
            raise StateError(".github/AGENTIC.md resolves outside the repository")
        if guide_path.is_symlink():
            raise StateError(
                "refusing to finalize through symlinked .github/AGENTIC.md"
            )
        guide_text = _render_agentic_guide(root)
        guide_hash = hashlib.sha256(guide_text.encode("utf-8")).hexdigest()
        try:
            current_text = (
                guide_path.read_text(encoding="utf-8") if guide_path.is_file() else ""
            )
        except (OSError, UnicodeDecodeError) as exc:
            raise StateError(f"cannot read existing .github/AGENTIC.md: {exc}") from exc
        if preview:
            _expect_revision(state, expected_revision)
            result = setup_summary(state)
            result.update(_setup_inventory(root, state))
            result.update(
                {
                    "preview": True,
                    "wouldWrite": current_text != guide_text,
                    "guideHash": guide_hash,
                    "diff": "".join(
                        difflib.unified_diff(
                            current_text.splitlines(keepends=True),
                            guide_text.splitlines(keepends=True),
                            fromfile=(
                                ".github/AGENTIC.md"
                                if guide_path.is_file()
                                else "/dev/null"
                            ),
                            tofile=".github/AGENTIC.md",
                        )
                    ),
                }
            )
            return result
        if (
            state["finalization"]["status"] == "complete"
            and state["finalization"].get("guideHash") == guide_hash
            and guide_path.is_file()
            and hashlib.sha256(current_text.encode("utf-8")).hexdigest() == guide_hash
        ):
            result = setup_summary(state)
            result.update(_setup_inventory(root, state))
            return result
        _expect_revision(state, expected_revision)
        trusted_hash = state["finalization"].get(
            "guideHash", state["finalization"].get("previousGuideHash")
        )
        if guide_path.exists():
            current_hash = hashlib.sha256(current_text.encode("utf-8")).hexdigest()
            if (
                current_hash != guide_hash
                and current_hash != trusted_hash
                and not approved_guide_replace
            ):
                raise StateError(
                    ".github/AGENTIC.md contains content not owned by this setup state; "
                    "review the replacement and rerun setup-finalize with "
                    "--approved-guide-replace only after explicit confirmation"
                )
        _atomic_write_text(guide_path, guide_text)
        now = _now()
        state["revision"] += 1
        state["updatedAt"] = now
        state["completedAt"] = now
        state["finalization"] = {
            "status": "complete",
            "guideHash": guide_hash,
            "updatedAt": now,
        }
        validate_setup_state(state)
        _validate_finalization(root, state)
        _atomic_write_json(path, state)
        result = setup_summary(state)
        result.update(_setup_inventory(root, state))
        return result


def _hooks_config_path(root: Path) -> Path:
    return root / ".github" / "hooks" / "hooks.json"


def _validate_hooks_config_path(root: Path) -> Path:
    path = _hooks_config_path(root)
    if path.is_symlink() or not _is_within(path.parent.resolve(), root.resolve()):
        raise StateError("hooks config uses an unsafe path")
    return path


def hooks_status(root: Path) -> Dict[str, Any]:
    path = _validate_hooks_config_path(root)
    if not path.is_file():
        return {
            "installed": False,
            "enabled": False,
            "configPath": ".github/hooks/hooks.json",
        }
    config = _read_json(path)
    if not isinstance(config.get("disableAllHooks"), bool):
        raise StateError("hooks config must declare boolean disableAllHooks")
    return {
        "installed": True,
        "enabled": not config["disableAllHooks"],
        "configPath": ".github/hooks/hooks.json",
    }


def set_hooks_enabled(root: Path, enabled: bool) -> Dict[str, Any]:
    path = _validate_hooks_config_path(root)
    _require_artifact(path, "AKMaestro hooks config")
    with _state_lock(root, path):
        config = _read_json(path)
        if not isinstance(config.get("disableAllHooks"), bool):
            raise StateError("hooks config must declare boolean disableAllHooks")
        original_config = dict(config)
        config["disableAllHooks"] = not enabled
        _atomic_write_json(path, config)
        manifest_path = root / ".agentic" / "setup" / "kit-manifest.json"
        if manifest_path.is_symlink():
            _atomic_write_json(path, original_config)
            raise StateError("kit manifest resolves outside the repository")
        if manifest_path.is_file():
            if not _is_within(manifest_path.parent.resolve(), root.resolve()):
                _atomic_write_json(path, original_config)
                raise StateError("kit manifest resolves outside the repository")
            try:
                manifest = _read_json(manifest_path)
                manifest["hooks_enabled"] = enabled
                _atomic_write_json(manifest_path, manifest)
            except (OSError, StateError):
                _atomic_write_json(path, original_config)
                raise
    return hooks_status(root)


def _validate_merge_target(root: Path, relative: str) -> Path:
    _validate_workspace_path(relative, "merge target")
    target_path = PurePosixPath(relative)
    if any(part in {".", ".."} for part in target_path.parts):
        raise StateError("merge target cannot contain traversal segments")
    normalized = target_path.as_posix()
    exact_targets = MERGE_TARGETS[:2]
    directory_targets = MERGE_TARGETS[2:]
    if normalized not in exact_targets and not any(
        normalized.startswith(prefix) and normalized != prefix
        for prefix in directory_targets
    ):
        raise StateError("merge target is not an approved instruction or hook file")
    candidate = root / normalized
    current = root
    for part in target_path.parts:
        current = current / part
        if current.is_symlink():
            raise StateError(f"merge target cannot use a symlinked path: {relative}")
    resolved = candidate.resolve()
    if not _is_within(resolved, root.resolve()):
        raise StateError("merge target resolves outside the repository")
    if not resolved.is_file():
        raise StateError("merge target must be an existing file")
    return resolved


def _merge_plan_identifier(plan: Dict[str, Any]) -> str:
    payload = {key: value for key, value in plan.items() if key != "planId"}
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode(
        "utf-8"
    )
    return hashlib.sha256(canonical).hexdigest()[:32]


def _validate_merge_plan(plan: Dict[str, Any], expected_id: str) -> None:
    required = (
        "version",
        "planId",
        "target",
        "targetExisted",
        "preimageHash",
        "proposedHash",
        "proposedContent",
        "createdAt",
    )
    _require_keys(plan, required, "merge plan")
    _only_keys(plan, required, "merge plan")
    if plan["version"] != STATE_VERSION:
        raise StateError(f"merge plan must use state version {STATE_VERSION}")
    if plan["planId"] != expected_id or _merge_plan_identifier(plan) != expected_id:
        raise StateError("merge plan identifier does not match its reviewed content")
    if not isinstance(plan["target"], str):
        raise StateError("merge plan target must be text")
    if plan["targetExisted"] is not True:
        raise StateError("merge plans may update existing files only")
    for field in ("preimageHash", "proposedHash"):
        if not isinstance(plan[field], str) or not re.fullmatch(
            r"[0-9a-f]{64}", plan[field]
        ):
            raise StateError(f"merge plan {field} must be sha256")
    if not isinstance(plan["proposedContent"], str):
        raise StateError("merge plan proposedContent must be text")
    _require_timestamp(plan["createdAt"], "merge plan.createdAt")


def create_merge_plan(root: Path, target: str, proposed_path: str) -> Dict[str, Any]:
    destination = _validate_merge_target(root, target)
    try:
        proposed = Path(proposed_path).read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        raise StateError(f"cannot read proposed UTF-8 content: {exc}") from exc
    if target.endswith(".json"):
        try:
            json.loads(proposed)
        except json.JSONDecodeError as exc:
            raise StateError(f"proposed JSON is invalid: {exc}") from exc
    try:
        current = destination.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        raise StateError(f"cannot read merge target as UTF-8: {exc}") from exc
    plan = {
        "version": STATE_VERSION,
        "target": Path(target).as_posix(),
        "targetExisted": True,
        "preimageHash": hashlib.sha256(current.encode("utf-8")).hexdigest(),
        "proposedHash": hashlib.sha256(proposed.encode("utf-8")).hexdigest(),
        "proposedContent": proposed,
        "createdAt": _now(),
    }
    plan_id = _merge_plan_identifier(plan)
    plan["planId"] = plan_id
    plans = _merge_plans_dir(root)
    if not _is_within(plans.resolve(), root.resolve()):
        raise StateError("merge plan directory resolves outside the repository")
    plans.mkdir(parents=True, exist_ok=True)
    _atomic_write_json(plans / f"{plan_id}.json", plan)
    diff = "".join(
        difflib.unified_diff(
            current.splitlines(keepends=True),
            proposed.splitlines(keepends=True),
            fromfile=target,
            tofile=target,
        )
    )
    return {key: value for key, value in plan.items() if key != "proposedContent"} | {
        "diff": diff
    }


def apply_merge_plan(root: Path, plan_id: str, approved: bool) -> Dict[str, Any]:
    if not approved:
        raise StateError("merge application requires explicit --approved")
    if not re.fullmatch(r"[0-9a-f]{32}", plan_id):
        raise StateError("invalid merge plan identifier")
    plans = _merge_plans_dir(root)
    if not _is_within(plans.resolve(), root.resolve()):
        raise StateError("merge plan directory resolves outside the repository")
    plan_path = plans / f"{plan_id}.json"
    plan = _read_json(plan_path)
    _validate_merge_plan(plan, plan_id)
    destination = _validate_merge_target(root, plan["target"])
    with _state_lock(root, destination):
        plan = _read_json(plan_path)
        _validate_merge_plan(plan, plan_id)
        if _validate_merge_target(root, plan["target"]) != destination:
            raise StateError("merge plan target changed after review")
        try:
            current = destination.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            raise StateError(f"cannot read merge target as UTF-8: {exc}") from exc
        current_hash = hashlib.sha256(current.encode("utf-8")).hexdigest()
        if current_hash != plan["preimageHash"]:
            raise StateError("merge target changed after review; create a new plan")
        proposed = plan["proposedContent"]
        if hashlib.sha256(proposed.encode("utf-8")).hexdigest() != plan["proposedHash"]:
            raise StateError("merge plan content is invalid")
        _atomic_write_text(destination, proposed)
        plan_path.unlink()
    return {"applied": True, "target": plan["target"], "hash": plan["proposedHash"]}


def validate_active_feature(state: Dict[str, Any]) -> None:
    _require_schema(state, "../schemas/active-feature.schema.json", "active feature")
    _require_version(state, "active feature")
    _require_keys(state, ("featureId", "selectedAt"), "active feature")
    _only_keys(
        state, ("$schema", "version", "featureId", "selectedAt"), "active feature"
    )
    _validate_id(state["featureId"], "feature id", ID_RE)
    _require_timestamp(state["selectedAt"], "active feature.selectedAt")


def validate_all(root: Path) -> Dict[str, Any]:
    checked: List[str] = []
    errors: List[str] = []
    warnings: List[str] = []

    validators = [
        (_setup_path(root), validate_setup_state),
        (_requirements_path(root), validate_requirements),
        (_action_checks_path(root), validate_action_checks),
        (_readiness_path(root), validate_readiness),
        (_active_path(root), validate_active_feature),
    ]
    for topic in TOPICS:
        validators.append(
            (
                root / ".agentic" / "setup" / f"{topic}-state.json",
                validate_topic_evidence,
            )
        )
    for path, validator in validators:
        if not path.exists():
            continue
        try:
            validator(_read_json(path))
            checked.append(str(path.relative_to(root)))
        except StateError as exc:
            errors.append(str(exc))

    setup_state = None
    if _setup_path(root).exists():
        try:
            setup_state = _read_json(_setup_path(root))
            validate_setup_integrity(root, setup_state)
        except StateError as exc:
            errors.append(str(exc))
            setup_state = None

    for path in sorted((root / ".agentic" / "features").glob("*/state.json")):
        try:
            state = _read_json(path)
            validate_feature_state(state)
            checked.append(str(path.relative_to(root)))
            feature_dir = path.parent
            if (
                state["phase"] != "understanding"
                and not (feature_dir / "understanding.md").is_file()
            ):
                warnings.append(f"{state['featureId']}: understanding.md is missing")
            if (
                state["phase"] not in {"understanding", "framing"}
                and not (feature_dir / "feature.md").is_file()
            ):
                warnings.append(f"{state['featureId']}: feature.md is missing")
            for story in state["stories"]:
                if not (feature_dir / "stories" / f"{story['id']}.md").is_file():
                    warnings.append(
                        f"{state['featureId']}: story artifact {story['id']}.md is missing"
                    )
        except StateError as exc:
            errors.append(str(exc))

    if list((root / ".agentic" / "features").glob("*/state.json")):
        if setup_state is None or setup_summary(setup_state)["overall"] != "complete":
            errors.append(
                "feature state exists but repository initialization is incomplete"
            )

    if (root / ".agentic" / "features" / "index.json").exists():
        warnings.append(
            "obsolete shared feature index exists: .agentic/features/index.json"
        )

    readiness_path = _readiness_path(root)
    requirements_path = _requirements_path(root)
    if readiness_path.exists() and requirements_path.exists():
        try:
            readiness = _read_json(readiness_path)
            requirements = _read_json(requirements_path)
            if readiness.get("requirementsHash") != requirements_hash(requirements):
                warnings.append(
                    "local readiness is stale because environment requirements changed"
                )
        except StateError:
            pass

    active_path = _active_path(root)
    if active_path.exists():
        try:
            active = _read_json(active_path)
            target = _feature_path(root, active["featureId"])
            if not target.exists():
                warnings.append(f"active feature does not exist: {active['featureId']}")
            elif _read_json(target).get("phase") == "complete":
                warnings.append(
                    f"active feature is already complete: {active['featureId']}"
                )
        except (KeyError, StateError):
            pass

    return {
        "valid": not errors,
        "checked": checked,
        "errors": errors,
        "warnings": warnings,
    }


def _load_object_argument(path: str) -> Dict[str, Any]:
    value = _read_json(Path(path))
    return value


def _print_json(value: Any) -> None:
    print(json.dumps(value, indent=2, sort_keys=True))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="AKMaestro deterministic state controller"
    )
    parser.add_argument(
        "--root", default=".", help="Repository root (default: current directory)"
    )
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("setup-init", help="Create setup state v3 if absent")
    sub.add_parser("setup-status", help="Print derived setup status")
    finalize = sub.add_parser(
        "setup-finalize", help="Render and record final setup handoff"
    )
    finalize.add_argument("--expected-revision", type=int)
    finalize.add_argument(
        "--approved-guide-replace",
        action="store_true",
        help="Replace an existing unowned team guide after explicit confirmation",
    )
    finalize.add_argument(
        "--preview", action="store_true", help="Show the deterministic guide diff"
    )
    setup_transition_parser = sub.add_parser(
        "setup-transition", help="Advance a setup topic"
    )
    setup_transition_parser.add_argument("topic", choices=TOPICS)
    setup_transition_parser.add_argument("status", choices=sorted(TOPIC_STATUSES))
    setup_transition_parser.add_argument("--reason")
    setup_transition_parser.add_argument("--expected-revision", type=int)

    evidence = sub.add_parser(
        "evidence-write", help="Atomically write setup topic evidence"
    )
    evidence.add_argument("topic", choices=TOPICS)
    evidence.add_argument(
        "--input", required=True, help="JSON object containing topic evidence"
    )
    evidence.add_argument("--expected-revision", type=int)

    action = sub.add_parser(
        "action-check", help="Run one confirmed instruction action without a shell"
    )
    action.add_argument(
        "--input", required=True, help="JSON object containing one action"
    )

    merge_plan = sub.add_parser("merge-plan", help="Plan an exact existing-file update")
    merge_plan.add_argument(
        "--target", required=True, help="Approved repository-relative target"
    )
    merge_plan.add_argument(
        "--input", required=True, help="File containing proposed UTF-8 content"
    )
    merge_apply = sub.add_parser(
        "merge-apply", help="Apply a reviewed merge plan atomically"
    )
    merge_apply.add_argument("--plan-id", required=True)
    merge_apply.add_argument("--approved", action="store_true")

    sub.add_parser(
        "hooks-status", help="Report whether installed AKMaestro hooks are enabled"
    )
    sub.add_parser(
        "hooks-enable", help="Enable installed AKMaestro hooks after consent"
    )
    sub.add_parser("hooks-disable", help="Disable installed AKMaestro hooks")

    requirements = sub.add_parser(
        "requirements-write", help="Atomically write environment requirements"
    )
    requirements.add_argument(
        "--input", required=True, help="JSON object with tools and artifacts"
    )
    requirements.add_argument("--expected-revision", type=int)

    readiness = sub.add_parser(
        "readiness-check", help="Probe this developer environment"
    )
    readiness.add_argument("--no-write", action="store_true")
    remediation = sub.add_parser(
        "remediation-run", help="Run one explicitly approved local remediation"
    )
    remediation.add_argument(
        "--input", required=True, help="JSON object containing the recorded action"
    )
    remediation.add_argument("--approved", action="store_true")

    create = sub.add_parser(
        "feature-create", help="Create and locally select a feature"
    )
    create.add_argument("--id", required=True)
    create.add_argument("--title", required=True)

    select = sub.add_parser("feature-select", help="Select a feature in this worktree")
    select.add_argument("--id", required=True)

    clear = sub.add_parser(
        "feature-clear-active", help="Clear this worktree's active feature"
    )
    clear.add_argument("--id")

    sub.add_parser("feature-list", help="List features and the local selection")
    show = sub.add_parser("feature-show", help="Show a feature with derived navigation")
    show.add_argument("--id", required=True)

    stories = sub.add_parser(
        "feature-add-stories", help="Register the approved ordered stories"
    )
    stories.add_argument("--id", required=True)
    stories.add_argument("--story", action="append", required=True)
    stories.add_argument("--mode", choices=STORY_MODES, default="guided")
    stories.add_argument("--expected-revision", type=int)

    gate = sub.add_parser("feature-advance", help="Cross an approved feature gate")
    gate.add_argument("--id", required=True)
    gate.add_argument("--gate", choices=tuple(GATE_TRANSITIONS))
    gate.add_argument("--expected-revision", type=int)

    story = sub.add_parser("story-transition", help="Advance or send back a story")
    story.add_argument("--feature", required=True)
    story.add_argument("--story", required=True)
    story.add_argument("--to", choices=STORY_STEPS, required=True)
    story.add_argument("--expected-revision", type=int)

    story_mode = sub.add_parser(
        "story-mode", help="Set mode before priming the current story"
    )
    story_mode.add_argument("--feature", required=True)
    story_mode.add_argument("--story", required=True)
    story_mode.add_argument("--mode", choices=STORY_MODES, required=True)
    story_mode.add_argument("--expected-revision", type=int)

    sub.add_parser("validate", help="Validate all known workflow state and invariants")
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    root = Path(args.root).resolve()
    try:
        if args.command == "setup-init":
            _print_json(setup_init(root))
        elif args.command == "setup-status":
            _print_json(setup_status(root))
        elif args.command == "setup-finalize":
            _print_json(
                finalize_setup(
                    root,
                    args.expected_revision,
                    args.approved_guide_replace,
                    args.preview,
                )
            )
        elif args.command == "setup-transition":
            state = setup_transition(
                root, args.topic, args.status, args.reason, args.expected_revision
            )
            _print_json({"state": state, "derived": setup_summary(state)})
        elif args.command == "evidence-write":
            _print_json(
                write_topic_evidence(
                    root,
                    args.topic,
                    _load_object_argument(args.input),
                    args.expected_revision,
                )
            )
        elif args.command == "action-check":
            result = check_instruction_action(root, _load_object_argument(args.input))
            _print_json(result)
            return 0 if result["status"] == "passed" else 4
        elif args.command == "merge-plan":
            _print_json(create_merge_plan(root, args.target, args.input))
        elif args.command == "merge-apply":
            _print_json(apply_merge_plan(root, args.plan_id, args.approved))
        elif args.command == "hooks-status":
            _print_json(hooks_status(root))
        elif args.command == "hooks-enable":
            _print_json(set_hooks_enabled(root, True))
        elif args.command == "hooks-disable":
            _print_json(set_hooks_enabled(root, False))
        elif args.command == "requirements-write":
            _print_json(
                write_requirements(
                    root, _load_object_argument(args.input), args.expected_revision
                )
            )
        elif args.command == "readiness-check":
            readiness, ready = check_readiness(root, write=not args.no_write)
            _print_json(readiness)
            return 0 if ready else 3
        elif args.command == "remediation-run":
            result = run_remediation(
                root, _load_object_argument(args.input), args.approved
            )
            _print_json(result)
            return 0 if result["status"] == "passed" else 4
        elif args.command == "feature-create":
            state = feature_create(root, args.id, args.title)
            _print_json(_feature_summary(state))
        elif args.command == "feature-select":
            _print_json(feature_select(root, args.id))
        elif args.command == "feature-clear-active":
            feature_clear_active(root, args.id)
            _print_json({"activeFeature": None})
        elif args.command == "feature-list":
            _print_json(feature_list(root))
        elif args.command == "feature-show":
            _print_json(_feature_summary(_read_json(_feature_path(root, args.id))))
        elif args.command == "feature-add-stories":
            state = feature_add_stories(
                root, args.id, args.story, args.mode, args.expected_revision
            )
            _print_json(_feature_summary(state))
        elif args.command == "feature-advance":
            state = feature_advance_gate(
                root, args.id, args.gate, args.expected_revision
            )
            _print_json(_feature_summary(state))
        elif args.command == "story-transition":
            state = story_transition(
                root,
                args.feature,
                args.story,
                args.to,
                args.expected_revision,
            )
            _print_json(_feature_summary(state))
        elif args.command == "story-mode":
            state = story_set_mode(
                root,
                args.feature,
                args.story,
                args.mode,
                args.expected_revision,
            )
            _print_json(_feature_summary(state))
        elif args.command == "validate":
            report = validate_all(root)
            _print_json(report)
            return 0 if report["valid"] else 1
    except StateError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    except OSError as exc:
        print(f"error: filesystem operation failed: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
