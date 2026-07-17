"""Deterministic, repo-local state controller for AKMaestro workflows.

This module is copied into installed repositories as
``.agentic/bin/akmaestro-state.py``. It intentionally uses only the Python
standard library so every developer can run the repository's pinned controller
through ``uv`` without installing AKMaestro as a persistent tool.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, Iterator, List, Optional, Sequence, Tuple


STATE_VERSION = 2
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
    fd, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
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


@contextmanager
def _state_lock(root: Path, state_path: Path, timeout: float = 10.0) -> Iterator[None]:
    """Serialize a state update using an atomic directory lock.

    Directory creation is atomic on the supported filesystems and works on both
    Windows and POSIX. Locks are local-only and stale locks are reclaimed.
    """

    lock_root = root / ".agentic" / "local" / "locks"
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
        "createdAt": now,
        "updatedAt": now,
    }


def validate_setup_state(state: Dict[str, Any]) -> None:
    _require_schema(state, "../schemas/setup-state.schema.json", "setup state")
    _require_version(state, "setup state")
    _require_revision(state, "setup state")
    _require_keys(state, ("profile", "topics", "createdAt", "updatedAt"), "setup state")
    _only_keys(
        state,
        (
            "$schema",
            "version",
            "revision",
            "profile",
            "topics",
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
        _only_keys(item, ("status", "optional", "updatedAt", "blocker"), f"setup topic {topic}")
        if not isinstance(item["status"], str) or item["status"] not in TOPIC_STATUSES:
            raise StateError(f"invalid status for setup topic {topic}: {item['status']!r}")
        expected_optional = topic in OPTIONAL_TOPICS
        if item["optional"] is not expected_optional:
            raise StateError(f"setup topic {topic} has an invalid optional flag")
        if item["status"] == "blocked" and not item.get("blocker"):
            raise StateError(f"blocked setup topic {topic} requires a blocker")
        if item["status"] == "skipped" and not expected_optional:
            raise StateError(f"mandatory setup topic {topic} cannot be skipped")
        _require_timestamp(item["updatedAt"], f"setup topic {topic}.updatedAt")


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
    return {
        "overall": "complete" if mandatory_done and optional_done else "incomplete",
        "nextTopic": next_topic,
        "nextCommand": f"/setup-{next_topic}" if next_topic else None,
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
    if state["topics"]["tooling"]["status"] in {"complete", "blocked"}:
        validate_requirements(_read_json(_requirements_path(root)))


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
            if topic == "tooling":
                requirements = _read_json(_requirements_path(root))
                validate_requirements(requirements)

        now = _now()
        current["status"] = status
        current["updatedAt"] = now
        if reason:
            current["blocker"] = reason
        else:
            current.pop("blocker", None)
        state["revision"] += 1
        state["updatedAt"] = now
        summary = setup_summary(state)
        if summary["overall"] == "complete":
            state.setdefault("completedAt", now)
        else:
            state.pop("completedAt", None)
        validate_setup_state(state)
        _atomic_write_json(path, state)
        return state


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
            if existing["evidence"] == evidence:
                return existing
            _expect_revision(existing, expected_revision)
            revision = existing["revision"] + 1
            created_at = existing["createdAt"]
        elif expected_revision not in (None, 0):
            raise StateError(f"stale evidence state: expected revision {expected_revision}, found none")
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
    _only_keys(
        state,
        ("$schema", "version", "revision", "topic", "evidence", "createdAt", "updatedAt"),
        "setup evidence",
    )
    _require_timestamp(state["createdAt"], "setup evidence.createdAt")
    _require_timestamp(state["updatedAt"], "setup evidence.updatedAt")


def _validate_workspace_path(value: str, label: str) -> None:
    if not isinstance(value, str) or not value or "\x00" in value:
        raise StateError(f"{label} must be a non-empty path")
    path = Path(value)
    if path.is_absolute():
        raise StateError(f"{label} must be relative to the repository: {value!r}")


def _validate_action(value: Dict[str, Any], label: str) -> None:
    if not isinstance(value, dict):
        raise StateError(f"{label} must be an object")
    command = value.get("command")
    if not isinstance(command, list) or not command or not all(
        isinstance(part, str) and part for part in command
    ):
        raise StateError(f"{label}.command must be a non-empty argument array")
    cwd = value.get("cwd", ".")
    _validate_workspace_path(cwd, f"{label}.cwd")
    _only_keys(value, ("command", "cwd"), label)


def validate_requirements(state: Dict[str, Any]) -> None:
    _require_schema(
        state,
        "../schemas/environment-requirements.schema.json",
        "environment requirements",
    )
    _require_version(state, "environment requirements")
    _require_revision(state, "environment requirements")
    _require_keys(state, ("tools", "artifacts", "createdAt", "updatedAt"), "environment requirements")
    if not isinstance(state["tools"], list) or not isinstance(state["artifacts"], list):
        raise StateError("environment requirements tools and artifacts must be arrays")
    _only_keys(
        state,
        ("$schema", "version", "revision", "tools", "artifacts", "createdAt", "updatedAt"),
        "environment requirements",
    )
    _require_timestamp(state["createdAt"], "environment requirements.createdAt")
    _require_timestamp(state["updatedAt"], "environment requirements.updatedAt")
    seen = set()
    for tool in state["tools"]:
        if not isinstance(tool, dict):
            raise StateError("each tool requirement must be an object")
        _require_keys(tool, ("id", "label", "required", "probe"), "tool requirement")
        _only_keys(tool, ("id", "label", "required", "probe", "install"), "tool requirement")
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
        if not probe["command"] or not all(isinstance(part, str) and part for part in probe["command"]):
            raise StateError(f"tool requirement {tool['id']} probe.command is invalid")
        timeout = probe.get("timeoutSeconds", 30)
        if not isinstance(timeout, int) or isinstance(timeout, bool) or not 1 <= timeout <= 120:
            raise StateError(f"tool requirement {tool['id']} probe timeout must be 1..120")
        contains = probe.get("contains")
        if contains is not None and (not isinstance(contains, str) or not contains):
            raise StateError(f"tool requirement {tool['id']} probe.contains must be text")
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
        _only_keys(artifact, ("id", "path", "required", "remediation"), "artifact requirement")
        _validate_id(artifact["id"], "artifact requirement id", ID_RE)
        if artifact["id"] in seen:
            raise StateError(f"duplicate requirement id: {artifact['id']}")
        seen.add(artifact["id"])
        if not isinstance(artifact["required"], bool):
            raise StateError(f"artifact requirement {artifact['id']}.required must be boolean")
        _validate_workspace_path(artifact["path"], f"artifact requirement {artifact['id']}.path")
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
        raise StateError("environment requirements must require at least one lsp-* tool")
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
            raise StateError(f"stale requirements: expected revision {expected_revision}, found none")
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
        probe_cwd = root / tool["probe"].get("cwd", ".")
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
            full_output = "\n".join(part for part in (proc.stdout, proc.stderr) if part).strip()
            combined = full_output.splitlines()
            detail = combined[0][:500] if combined else f"exit {proc.returncode}"
            contains = tool["probe"].get("contains")
            status = "ok" if proc.returncode == 0 and (not contains or contains in full_output) else "missing"
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
        exists = (root / artifact["path"]).exists()
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
    _require_keys(state, ("requirementsHash", "status", "checks", "checkedAt"), "local readiness")
    _only_keys(
        state,
        ("$schema", "version", "requirementsHash", "status", "checks", "checkedAt"),
        "local readiness",
    )
    if not isinstance(state["requirementsHash"], str) or not re.fullmatch(
        r"[0-9a-f]{64}", state["requirementsHash"]
    ):
        raise StateError("local readiness requirementsHash must be sha256")
    if not isinstance(state["status"], str) or state["status"] not in {"ready", "not_ready"}:
        raise StateError("local readiness status must be ready or not_ready")
    if not isinstance(state["checks"], list):
        raise StateError("local readiness checks must be an array")
    seen = set()
    for check in state["checks"]:
        if not isinstance(check, dict):
            raise StateError("each local readiness check must be an object")
        _require_keys(check, ("id", "type", "required", "status", "detail"), "readiness check")
        _only_keys(check, ("id", "type", "required", "status", "detail", "remediation"), "readiness check")
        _validate_id(check["id"], "readiness check id", ID_RE)
        if check["id"] in seen:
            raise StateError(f"duplicate readiness check: {check['id']}")
        seen.add(check["id"])
        if not isinstance(check["type"], str) or check["type"] not in {"tool", "artifact"}:
            raise StateError(f"invalid readiness check type: {check['type']!r}")
        if not isinstance(check["required"], bool):
            raise StateError(f"readiness check {check['id']}.required must be boolean")
        if not isinstance(check["status"], str) or check["status"] not in {"ok", "missing"}:
            raise StateError(f"invalid readiness check status: {check['status']!r}")
        if not isinstance(check["detail"], str):
            raise StateError(f"readiness check {check['id']}.detail must be text")
        if "remediation" in check:
            _validate_action(check["remediation"], f"readiness check {check['id']}.remediation")
    expected_ready = all(
        check["status"] == "ok" for check in state["checks"] if check["required"]
    )
    if (state["status"] == "ready") is not expected_ready:
        raise StateError("local readiness status disagrees with its required checks")
    _require_timestamp(state["checkedAt"], "local readiness.checkedAt")


def require_workflow_ready(root: Path) -> None:
    """Require shared initialization and current worktree readiness."""

    if not _setup_path(root).is_file():
        raise StateError("repository initialization is incomplete; the team lead must finish /init")
    setup = _read_json(_setup_path(root))
    if setup_summary(setup)["overall"] != "complete":
        raise StateError("repository initialization is incomplete; the team lead must finish /init")
    validate_setup_integrity(root, setup)
    _read_json(_requirements_path(root))
    _readiness, ready = check_readiness(root, write=True)
    if not ready:
        raise StateError("developer environment is not ready; run readiness-check and remediate")


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
            raise StateError(f"feature phase {state['phase']} requires every story to be complete")
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
        _require_timestamp(gate["approvedAt"], f"feature gate {gate['name']}.approvedAt")
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
        current_story = next(story for story in state["stories"] if story["id"] == state["currentStory"])
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
                raise StateError(f"feature {feature_id} already exists with a different title")
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
        if existing_ids == list(story_ids) and all(story["mode"] == mode for story in state["stories"]):
            return state
        _expect_revision(state, expected_revision)
        if state["phase"] != "splitting":
            raise StateError("stories can only be added during the splitting phase")
        if state["stories"]:
            raise StateError("stories are already registered; do not replace them implicitly")
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
        _require_artifact(path.parent / "stories" / f"{story_id}.md", f"story artifact {story_id}")
        if current_step == to_step:
            return state
        _expect_revision(state, expected_revision)

        reopening = state["phase"] == "reviewing" and current_step == "complete"
        if reopening:
            if to_step not in {"plan", "implement"}:
                raise StateError("feature review can reopen a story only to plan or implement")
        else:
            if state["phase"] != "story_loop":
                raise StateError("story transitions require the story_loop phase")
            if state["currentStory"] != story_id:
                raise StateError(f"story {story_id} is not the current story")
            if to_step not in STORY_TRANSITIONS[current_step]:
                raise StateError(f"illegal story transition: {current_step} -> {to_step}")

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
            next_story = next((item for item in state["stories"] if item["step"] != "complete"), None)
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
            raise StateError("story mode can only change before the current story is primed")
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
        if not any(item["featureId"] == active_id and item["phase"] != "complete" for item in summaries):
            active_id = None
    open_features = [item for item in summaries if item["phase"] != "complete"]
    return {"activeFeature": active_id, "open": open_features, "all": summaries}


def validate_active_feature(state: Dict[str, Any]) -> None:
    _require_schema(state, "../schemas/active-feature.schema.json", "active feature")
    _require_version(state, "active feature")
    _require_keys(state, ("featureId", "selectedAt"), "active feature")
    _only_keys(state, ("$schema", "version", "featureId", "selectedAt"), "active feature")
    _validate_id(state["featureId"], "feature id", ID_RE)
    _require_timestamp(state["selectedAt"], "active feature.selectedAt")


def validate_all(root: Path) -> Dict[str, Any]:
    checked: List[str] = []
    errors: List[str] = []
    warnings: List[str] = []

    validators = [
        (_setup_path(root), validate_setup_state),
        (_requirements_path(root), validate_requirements),
        (_readiness_path(root), validate_readiness),
        (_active_path(root), validate_active_feature),
    ]
    for topic in TOPICS:
        validators.append(
            (root / ".agentic" / "setup" / f"{topic}-state.json", validate_topic_evidence)
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
            if state["phase"] != "understanding" and not (feature_dir / "understanding.md").is_file():
                warnings.append(f"{state['featureId']}: understanding.md is missing")
            if state["phase"] not in {"understanding", "framing"} and not (feature_dir / "feature.md").is_file():
                warnings.append(f"{state['featureId']}: feature.md is missing")
            for story in state["stories"]:
                if not (feature_dir / "stories" / f"{story['id']}.md").is_file():
                    warnings.append(f"{state['featureId']}: story artifact {story['id']}.md is missing")
        except StateError as exc:
            errors.append(str(exc))

    if list((root / ".agentic" / "features").glob("*/state.json")):
        if setup_state is None or setup_summary(setup_state)["overall"] != "complete":
            errors.append("feature state exists but repository initialization is incomplete")

    if (root / ".agentic" / "features" / "index.json").exists():
        warnings.append("obsolete shared feature index exists: .agentic/features/index.json")

    readiness_path = _readiness_path(root)
    requirements_path = _requirements_path(root)
    if readiness_path.exists() and requirements_path.exists():
        try:
            readiness = _read_json(readiness_path)
            requirements = _read_json(requirements_path)
            if readiness.get("requirementsHash") != requirements_hash(requirements):
                warnings.append("local readiness is stale because environment requirements changed")
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
                warnings.append(f"active feature is already complete: {active['featureId']}")
        except (KeyError, StateError):
            pass

    return {"valid": not errors, "checked": checked, "errors": errors, "warnings": warnings}


def _load_object_argument(path: str) -> Dict[str, Any]:
    value = _read_json(Path(path))
    return value


def _print_json(value: Any) -> None:
    print(json.dumps(value, indent=2, sort_keys=True))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="AKMaestro deterministic state controller")
    parser.add_argument("--root", default=".", help="Repository root (default: current directory)")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("setup-init", help="Create setup state v2 if absent")
    sub.add_parser("setup-status", help="Print derived setup status")
    setup_transition_parser = sub.add_parser("setup-transition", help="Advance a setup topic")
    setup_transition_parser.add_argument("topic", choices=TOPICS)
    setup_transition_parser.add_argument("status", choices=sorted(TOPIC_STATUSES))
    setup_transition_parser.add_argument("--reason")
    setup_transition_parser.add_argument("--expected-revision", type=int)

    evidence = sub.add_parser("evidence-write", help="Atomically write setup topic evidence")
    evidence.add_argument("topic", choices=TOPICS)
    evidence.add_argument("--input", required=True, help="JSON object containing topic evidence")
    evidence.add_argument("--expected-revision", type=int)

    requirements = sub.add_parser("requirements-write", help="Atomically write environment requirements")
    requirements.add_argument("--input", required=True, help="JSON object with tools and artifacts")
    requirements.add_argument("--expected-revision", type=int)

    readiness = sub.add_parser("readiness-check", help="Probe this developer environment")
    readiness.add_argument("--no-write", action="store_true")

    create = sub.add_parser("feature-create", help="Create and locally select a feature")
    create.add_argument("--id", required=True)
    create.add_argument("--title", required=True)

    select = sub.add_parser("feature-select", help="Select a feature in this worktree")
    select.add_argument("--id", required=True)

    clear = sub.add_parser("feature-clear-active", help="Clear this worktree's active feature")
    clear.add_argument("--id")

    sub.add_parser("feature-list", help="List features and the local selection")
    show = sub.add_parser("feature-show", help="Show a feature with derived navigation")
    show.add_argument("--id", required=True)

    stories = sub.add_parser("feature-add-stories", help="Register the approved ordered stories")
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

    story_mode = sub.add_parser("story-mode", help="Set mode before priming the current story")
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
            _print_json(setup_summary(_read_json(_setup_path(root))))
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
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
