"""Tests for the asset installer: fresh install, idempotency, no-overwrite,
--no-hooks, gitignore handling, and dogfood-copy sync."""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from akmaestro import cli, installer

REPO_ROOT = Path(__file__).resolve().parent.parent
ASSETS = REPO_ROOT / "src" / "akmaestro" / "assets"

EXPECTED_SKILLS = {
    "init", "setup-instructions", "setup-tooling", "setup-skills", "setup-hooks",
    "teach", "doctor",
    "feature", "feature-understand", "feature-frame", "feature-split",
    "story-prime", "story-plan", "story-implement", "story-review", "story-learn",
    "feature-review", "feature-retro",
}

FEATURE_FLOW_SKILLS = {
    "feature", "feature-understand", "feature-frame", "feature-split",
    "story-prime", "story-plan", "story-implement", "story-review", "story-learn",
    "feature-review", "feature-retro",
}

DEPRECATED_ROLE_TERMS = {
    "editable satellite",
    "editable dependency",
    "read-only reference",
}


def test_fresh_install_lays_down_everything(tmp_path):
    results = installer.init(str(tmp_path))

    skills = {p.name for p in (tmp_path / ".github" / "skills").iterdir()}
    assert skills == EXPECTED_SKILLS
    for name in skills:
        assert (tmp_path / ".github" / "skills" / name / "SKILL.md").is_file()

    assert (tmp_path / ".github" / "hooks" / "hooks.json").is_file()
    for data in ("restricted-paths.txt", "dangerous-commands.txt", "lint-commands.json"):
        assert (tmp_path / ".agentic" / "hooks" / data).is_file()

    assert (tmp_path / "AGENTS.md").is_file()
    assert (tmp_path / ".github" / "copilot-instructions.md").is_file()
    assert (tmp_path / ".agentic" / "setup").is_dir()
    assert (tmp_path / ".agentic" / "local").is_dir()
    assert (tmp_path / ".agentic" / "bin" / "akmaestro-state.py").is_file()
    assert (tmp_path / ".agentic" / "schemas" / "feature-state.schema.json").is_file()
    assert (tmp_path / ".agentic" / "audit").is_dir()
    assert ".agentic/local/" in (tmp_path / ".gitignore").read_text().splitlines()
    assert ".agentic/audit/" in (tmp_path / ".gitignore").read_text().splitlines()

    assert results["skipped"] == []
    assert len(results["created"]) > 20


def test_skill_health_checks_cover_full_bundled_set():
    for validator in ("setup-skills", "doctor"):
        text = (ASSETS / "skills" / validator / "SKILL.md").read_text(encoding="utf-8")
        for skill in EXPECTED_SKILLS:
            assert f"`{skill}`" in text, f"{validator} does not validate {skill}"


def test_feature_skills_enforce_shared_init_and_local_readiness():
    for name in FEATURE_FLOW_SKILLS:
        text = (ASSETS / "skills" / name / "SKILL.md").read_text(encoding="utf-8")
        assert ".agentic/STATE-PROTOCOL.md" in text, name
        assert "readiness-check" in text, name
        assert "index.json" not in text or "never" in text, name


def test_setup_skills_use_controller_evidence_and_single_status_source():
    for name in ("setup-instructions", "setup-tooling", "setup-skills", "setup-hooks"):
        text = (ASSETS / "skills" / name / "SKILL.md").read_text(encoding="utf-8")
        assert "evidence-write" in text, name
        assert "setup-status" in text, name
        assert "Never edit" in text or "never edit" in text, name


def test_shipped_assets_use_current_sibling_repo_roles():
    for path in ASSETS.rglob("*"):
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8").lower()
        for term in DEPRECATED_ROLE_TERMS:
            assert term not in text, f"deprecated role term {term!r} in {path}"


@pytest.mark.skipif(sys.platform == "win32", reason="exec bits are POSIX-only")
def test_shell_scripts_are_executable(tmp_path):
    installer.init(str(tmp_path))
    scripts = list((tmp_path / ".github" / "hooks" / "scripts").glob("*.sh"))
    assert scripts
    for sh in scripts:
        assert os.access(sh, os.X_OK), f"{sh.name} is not executable"


def test_rerun_is_idempotent_and_never_overwrites(tmp_path):
    installer.init(str(tmp_path))
    marker = tmp_path / ".github" / "skills" / "init" / "SKILL.md"
    marker.write_text("user-customized\n", encoding="utf-8")
    gitignore_before = (tmp_path / ".gitignore").read_text()

    results = installer.init(str(tmp_path))

    assert results["created"] == []
    assert marker.read_text(encoding="utf-8") == "user-customized\n"
    assert (tmp_path / ".gitignore").read_text() == gitignore_before


def test_no_hooks_skips_hooks_and_audit_but_keeps_local_state_ignore(tmp_path):
    installer.init(str(tmp_path), with_hooks=False)

    assert not (tmp_path / ".github" / "hooks").exists()
    assert not (tmp_path / ".agentic" / "hooks").exists()
    assert not (tmp_path / ".agentic" / "audit").exists()
    assert (tmp_path / ".agentic" / "local").is_dir()
    assert ".agentic/local/" in (tmp_path / ".gitignore").read_text().splitlines()
    assert ".agentic/audit/" not in (tmp_path / ".gitignore").read_text().splitlines()
    assert (tmp_path / ".github" / "skills" / "init" / "SKILL.md").is_file()


def test_bootstrap_files_respect_existing(tmp_path):
    (tmp_path / "AGENTS.md").write_text("real instructions\n", encoding="utf-8")

    results = installer.init(str(tmp_path))

    assert (tmp_path / "AGENTS.md").read_text(encoding="utf-8") == "real instructions\n"
    assert "AGENTS.md" in results["skipped"]


def test_gitignore_append_preserves_content_without_trailing_newline(tmp_path):
    (tmp_path / ".gitignore").write_text("node_modules/", encoding="utf-8")

    installer.init(str(tmp_path))

    lines = (tmp_path / ".gitignore").read_text(encoding="utf-8").splitlines()
    assert lines[0] == "node_modules/"
    assert ".agentic/audit/" in lines


def test_cli_init_reports_and_exits_zero(tmp_path, capsys):
    rc = cli.main(["init", "--path", str(tmp_path)])

    assert rc == 0
    out = capsys.readouterr().out
    assert "/init" in out
    assert (tmp_path / ".github" / "skills" / "doctor" / "SKILL.md").is_file()


def _manifest(tmp_path):
    return json.loads((tmp_path / ".agentic" / "setup" / "kit-manifest.json").read_text())


def test_init_writes_manifest(tmp_path):
    installer.init(str(tmp_path))
    manifest = _manifest(tmp_path)
    assert manifest["files"][".github/skills/init/SKILL.md"]
    assert all("\\" not in key for key in manifest["files"])  # posix keys on all OSes


def test_update_refreshes_kit_owned_but_keeps_customized(tmp_path):
    installer.init(str(tmp_path))
    kit_owned = tmp_path / ".github" / "skills" / "doctor" / "SKILL.md"
    customized = tmp_path / ".github" / "skills" / "teach" / "SKILL.md"
    original = kit_owned.read_bytes()
    kit_owned.write_bytes(b"pretend this is an OLD kit version\n")
    # Simulate: the old version is what the kit installed (manifest matches it).
    mpath = tmp_path / ".agentic" / "setup" / "kit-manifest.json"
    manifest = json.loads(mpath.read_text())
    manifest["files"][".github/skills/doctor/SKILL.md"] = installer._sha256(
        kit_owned.read_bytes()
    )
    mpath.write_text(json.dumps(manifest))
    customized.write_text("my team's custom teach skill\n", encoding="utf-8")

    results = installer.update(str(tmp_path))

    assert kit_owned.read_bytes() == original
    assert ".github/skills/doctor/SKILL.md" in results["updated"]
    assert customized.read_text(encoding="utf-8") == "my team's custom teach skill\n"
    assert ".github/skills/teach/SKILL.md" in results["kept"]


def test_update_force_overwrites_customized(tmp_path):
    installer.init(str(tmp_path))
    customized = tmp_path / ".github" / "skills" / "teach" / "SKILL.md"
    customized.write_text("custom\n", encoding="utf-8")

    results = installer.update(str(tmp_path), force=True)

    assert customized.read_text(encoding="utf-8") != "custom\n"
    assert ".github/skills/teach/SKILL.md" in results["updated"]


def test_update_adds_files_new_in_this_version(tmp_path):
    installer.init(str(tmp_path))
    removed = tmp_path / ".github" / "skills" / "feature" / "SKILL.md"
    removed.unlink()  # as if installed by an older kit without this skill

    results = installer.update(str(tmp_path))

    assert removed.is_file()
    assert ".github/skills/feature/SKILL.md" in results["created"]


def test_update_keeps_files_with_unknown_provenance(tmp_path):
    """A repo installed before the manifest existed: differing files are kept."""
    installer.init(str(tmp_path))
    (tmp_path / ".agentic" / "setup" / "kit-manifest.json").unlink()
    target = tmp_path / ".github" / "skills" / "doctor" / "SKILL.md"
    target.write_text("edited before manifests existed\n", encoding="utf-8")

    results = installer.update(str(tmp_path))

    assert target.read_text(encoding="utf-8") == "edited before manifests existed\n"
    assert ".github/skills/doctor/SKILL.md" in results["kept"]
    # Untouched files are adopted into the fresh manifest as up-to-date.
    assert ".github/skills/init/SKILL.md" in results["up_to_date"]


def test_update_respects_no_hooks_install(tmp_path):
    installer.init(str(tmp_path), with_hooks=False)

    results = installer.update(str(tmp_path))

    assert not (tmp_path / ".github" / "hooks").exists()
    assert not any("hooks" in f for f in results["created"])


def test_update_never_touches_a_filled_in_agents_md(tmp_path):
    installer.init(str(tmp_path))
    agents = tmp_path / "AGENTS.md"
    agents.write_text("# Real instructions written by /init\n", encoding="utf-8")

    installer.update(str(tmp_path))

    assert agents.read_text(encoding="utf-8") == "# Real instructions written by /init\n"


def test_cli_update_reports_and_exits_zero(tmp_path, capsys):
    installer.init(str(tmp_path))
    (tmp_path / ".github" / "skills" / "teach" / "SKILL.md").write_text("custom\n")

    rc = cli.main(["update", "--path", str(tmp_path)])

    assert rc == 0
    out = capsys.readouterr().out
    assert "kept 1 customized" in out


def test_dogfood_copies_match_assets():
    """The repo-root .github/skills/{teach,doctor} and .github/hooks are dogfood
    copies of assets/ (the canonical source, per AGENTS.md). Guard against drift."""
    pairs = []
    for name in ("teach", "doctor"):
        pairs.append((REPO_ROOT / ".github" / "skills" / name, ASSETS / "skills" / name))
    pairs.append((REPO_ROOT / ".github" / "hooks", ASSETS / "hooks"))
    pairs.append((REPO_ROOT / ".agentic" / "hooks", ASSETS / "hooks-data"))

    for dogfood, canonical in pairs:
        for cur, _dirs, files in os.walk(dogfood):
            for fname in files:
                if fname == "README.md":  # root-only explainer, not an asset
                    continue
                dst = Path(cur) / fname
                src = canonical / dst.relative_to(dogfood)
                assert src.is_file(), f"{dst} has no canonical counterpart in assets/"
                assert dst.read_bytes() == src.read_bytes(), (
                    f"{dst} drifted from {src} — canonical source is assets/"
                )


HOOK_CASES = [
    ("restricted-path-guard.sh", '{"toolName":"edit","toolArgs":{"path":".env"}}', "deny"),
    ("restricted-path-guard.sh", '{"toolName":"edit","toolArgs":{"path":"README.md"}}', "allow"),
    ("restricted-path-guard.sh", '{"tool_name":"create","tool_input":{"path":"secrets/x.txt"}}', "deny"),
    ("restricted-path-guard.sh", "garbage not json", "allow"),
    # Workspace boundary: outside the repo and not a declared modifiable sibling.
    ("restricted-path-guard.sh", '{"toolName":"edit","toolArgs":{"path":"../vendor-c/core.py"}}', "deny"),
    ("restricted-path-guard.sh", '{"toolName":"edit","toolArgs":{"path":"/etc/hosts"}}', "deny"),
    ("dangerous-command-guard.sh", '{"toolName":"bash","toolArgs":{"command":"rm -rf /"}}', "deny"),
    ("dangerous-command-guard.sh", '{"toolName":"bash","toolArgs":{"command":"ls -la"}}', "allow"),
    ("dangerous-command-guard.sh",
     '{"toolName":"edit","toolArgs":{"path":"a.md","content":"rm -rf /"}}', "allow"),
]


@pytest.mark.skipif(sys.platform == "win32", reason="bash guards are POSIX-only")
@pytest.mark.parametrize("script,payload,expected", HOOK_CASES)
def test_bash_guard_logic(tmp_path, script, payload, expected):
    if not _have("bash") or not _have("jq"):
        pytest.skip("bash and jq required")
    installer.init(str(tmp_path))

    proc = subprocess.run(
        ["bash", f".github/hooks/scripts/{script}"],
        input=payload, capture_output=True, text=True, cwd=tmp_path,
    )

    assert proc.returncode == 0, proc.stderr  # guards must always exit 0
    decision = json.loads(proc.stdout)
    assert decision["permissionDecision"] == expected


@pytest.mark.parametrize("script,payload,expected", HOOK_CASES)
def test_powershell_guard_logic(tmp_path, script, payload, expected):
    if not _have("pwsh"):
        pytest.skip("pwsh required")
    installer.init(str(tmp_path))

    proc = _run_pwsh(script.replace(".sh", ".ps1"), payload, tmp_path)

    assert proc.returncode == 0, proc.stderr
    assert json.loads(proc.stdout)["permissionDecision"] == expected


def _live_event(tool_name, inner):
    """Build an event the way the GA Copilot CLI 1.0.68 actually sends it:
    toolArgs is a JSON-ENCODED STRING (not a nested object). Mirrors the bytes
    captured in .agentic/audit during the 2026-07-06 live run."""
    return json.dumps({
        "sessionId": "x", "timestamp": 1, "cwd": "/r",
        "toolName": tool_name, "toolArgs": json.dumps(inner),
    })


def _live_cases(repo):
    """Real-shape payloads with string toolArgs and ABSOLUTE paths — the exact
    class the object-form dry-runs failed to catch (guards fell through to allow
    because .path resolved to null on a string). Regression lock for that bug."""
    return [
        ("restricted-path-guard.sh",
         _live_event("create", {"path": str(repo / ".env"), "file_text": "FOO=bar"}), "deny"),
        ("restricted-path-guard.sh",
         _live_event("edit", {"path": str(repo / "README.md")}), "allow"),
        ("restricted-path-guard.sh",
         _live_event("edit", {"path": str(repo / "secrets" / "s.txt")}), "deny"),
        # A prompt-shape event (no toolName/toolArgs at all) must fall through.
        ("restricted-path-guard.sh",
         json.dumps({"sessionId": "x", "timestamp": 1, "cwd": str(repo), "prompt": "hi"}), "allow"),
        ("dangerous-command-guard.sh",
         _live_event("powershell", {"command": "rm -rf /"}), "deny"),
        ("dangerous-command-guard.sh",
         _live_event("powershell", {"command": "ls -la"}), "allow"),
    ]


@pytest.mark.skipif(sys.platform == "win32", reason="bash guards are POSIX-only")
def test_bash_guards_real_cli_payload_shape(tmp_path):
    if not _have("bash") or not _have("jq"):
        pytest.skip("bash and jq required")
    installer.init(str(tmp_path))
    for script, payload, expected in _live_cases(tmp_path):
        proc = subprocess.run(
            ["bash", f".github/hooks/scripts/{script}"],
            input=payload, capture_output=True, text=True, cwd=tmp_path,
        )
        assert proc.returncode == 0, proc.stderr
        assert json.loads(proc.stdout)["permissionDecision"] == expected, (script, payload)


def test_powershell_guards_real_cli_payload_shape(tmp_path):
    if not _have("pwsh"):
        pytest.skip("pwsh required")
    installer.init(str(tmp_path))
    for script, payload, expected in _live_cases(tmp_path):
        proc = _run_pwsh(script.replace(".sh", ".ps1"), payload, tmp_path)
        assert proc.returncode == 0, proc.stderr
        assert json.loads(proc.stdout)["permissionDecision"] == expected, (script, payload)


MODIFIABLE_SIBLING_CASES = [
    # A declared modifiable sibling is writable from the main repo's session…
    ('{"toolName":"edit","toolArgs":{"path":"../lib-b/src/mod.py"}}', "allow"),
    # …including via a sneaky in-repo-looking traversal…
    ('{"toolName":"edit","toolArgs":{"path":"src/../../lib-b/ok.py"}}', "allow"),
    # …but restricted globs still apply inside it…
    ('{"toolName":"edit","toolArgs":{"path":"../lib-b/.env"}}', "deny"),
    # …and undeclared siblings stay read-only.
    ('{"toolName":"edit","toolArgs":{"path":"../vendor-c/core.py"}}', "deny"),
]


def _repo_with_modifiable_sibling(tmp_path):
    repo = tmp_path / "repo-a"
    repo.mkdir()
    (tmp_path / "lib-b").mkdir()
    (tmp_path / "vendor-c").mkdir()
    installer.init(str(repo))
    with (repo / ".agentic" / "hooks" / "editable-paths.txt").open("a") as fh:
        fh.write("../lib-b\n")
    return repo


@pytest.mark.skipif(sys.platform == "win32", reason="bash guards are POSIX-only")
@pytest.mark.parametrize("payload,expected", MODIFIABLE_SIBLING_CASES)
def test_workspace_boundary_with_modifiable_sibling(tmp_path, payload, expected):
    if not _have("bash") or not _have("jq"):
        pytest.skip("bash and jq required")
    repo = _repo_with_modifiable_sibling(tmp_path)

    proc = subprocess.run(
        ["bash", ".github/hooks/scripts/restricted-path-guard.sh"],
        input=payload, capture_output=True, text=True, cwd=repo,
    )

    assert proc.returncode == 0, proc.stderr
    assert json.loads(proc.stdout)["permissionDecision"] == expected


@pytest.mark.parametrize("payload,expected", MODIFIABLE_SIBLING_CASES)
def test_workspace_boundary_powershell(tmp_path, payload, expected):
    if not _have("pwsh"):
        pytest.skip("pwsh required")
    repo = _repo_with_modifiable_sibling(tmp_path)

    proc = _run_pwsh("restricted-path-guard.ps1", payload, repo)

    assert proc.returncode == 0, proc.stderr
    assert json.loads(proc.stdout)["permissionDecision"] == expected


@pytest.mark.skipif(sys.platform == "win32", reason="audit-log.sh is POSIX-only")
def test_audit_log_infers_event_kind_structurally(tmp_path):
    """The GA CLI sends no event-name field; audit-log must infer it from which
    fields are present (toolName+toolResult / prompt / reason)."""
    if not _have("bash") or not _have("jq"):
        pytest.skip("bash and jq required")
    installer.init(str(tmp_path))
    events = [
        ('{"sessionId":"s","toolName":"create","toolArgs":"{}","toolResult":{"resultType":"ok"}}', "postToolUse"),
        ('{"sessionId":"s","prompt":"hi"}', "userPromptSubmitted"),
        ('{"sessionId":"s","reason":"complete"}', "sessionEnd"),
    ]
    for payload, _ in events:
        subprocess.run(["bash", ".github/hooks/scripts/audit-log.sh"],
                       input=payload, capture_output=True, text=True, cwd=tmp_path)

    lines = list((tmp_path / ".agentic" / "audit").glob("*.jsonl"))
    assert lines, "no audit trail written"
    recorded = [json.loads(line)["event"] for line in lines[0].read_text().splitlines()]
    assert recorded == [e for _, e in events]


def _run_pwsh(script, payload, cwd):
    return subprocess.run(
        ["pwsh", "-NoProfile", "-ExecutionPolicy", "Bypass",
         "-File", str(Path(".github/hooks/scripts") / script)],
        input=payload, capture_output=True, text=True, cwd=cwd,
    )


def _have(tool):
    from shutil import which
    return which(tool) is not None
