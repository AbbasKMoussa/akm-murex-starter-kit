"""Tests for the asset installer: fresh install, idempotency, no-overwrite,
--no-hooks, gitignore handling, and dogfood-copy sync."""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from akmaestro import cli, installer, state

REPO_ROOT = Path(__file__).resolve().parent.parent
ASSETS = REPO_ROOT / "src" / "akmaestro" / "assets"

EXPECTED_SKILLS = {
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
}


@pytest.fixture(autouse=True)
def _git_repository(tmp_path):
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)


FEATURE_FLOW_SKILLS = {
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
    assert (
        tmp_path
        / ".github"
        / "skills"
        / "setup-instructions"
        / "references"
        / "instructions-evidence.example.json"
    ).is_file()

    assert (tmp_path / ".github" / "hooks" / "hooks.json").is_file()
    hooks = json.loads((tmp_path / ".github" / "hooks" / "hooks.json").read_text())
    assert hooks["disableAllHooks"] is True
    for data in (
        "restricted-paths.txt",
        "dangerous-commands.txt",
        "lint-commands.json",
    ):
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


def test_status_skill_is_read_only_universal_orientation():
    text = (ASSETS / "skills" / "status" / "SKILL.md").read_text(encoding="utf-8")

    commands = (
        "setup-status",
        "readiness-check --no-write",
        "feature-list",
        "feature-show",
    )
    for command in commands:
        assert f"`{command}`" in text or command in text
    for destination in ("/akmaestro-init", "/feature", "/doctor"):
        assert destination in text
    assert "Do not execute or delegate" in text


def test_subproject_scope_guidance_is_bundled():
    protocol = (ASSETS / "runtime" / "STATE-PROTOCOL.md").read_text(encoding="utf-8")
    init_skill = (ASSETS / "skills" / "akmaestro-init" / "SKILL.md").read_text(
        encoding="utf-8"
    )
    feature_skill = (ASSETS / "skills" / "feature" / "SKILL.md").read_text(
        encoding="utf-8"
    )
    status_skill = (ASSETS / "skills" / "status" / "SKILL.md").read_text(
        encoding="utf-8"
    )
    doctor_skill = (ASSETS / "skills" / "doctor" / "SKILL.md").read_text(
        encoding="utf-8"
    )

    for text in (protocol, init_skill, feature_skill, status_skill, doctor_skill):
        assert "installation_mode" in text
        assert "subproject" in text
    assert "Do not scan sibling products" in " ".join(protocol.split())
    assert "enclosing Git root" in init_skill
    assert "outside the subproject" in feature_skill


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
    marker = tmp_path / ".github" / "skills" / "teach" / "SKILL.md"
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
    assert (tmp_path / ".github" / "skills" / "akmaestro-init" / "SKILL.md").is_file()


def test_init_no_hooks_does_not_forget_previously_installed_hooks(tmp_path):
    installer.init(str(tmp_path))

    installer.init(str(tmp_path), with_hooks=False)

    assert _manifest(tmp_path)["hooks_installed"] is True
    assert (tmp_path / ".github" / "hooks" / "hooks.json").is_file()


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
    assert "/akmaestro-init" in out
    assert (tmp_path / ".github" / "skills" / "doctor" / "SKILL.md").is_file()


def test_init_dry_run_writes_nothing(tmp_path):
    before = {path.relative_to(tmp_path) for path in tmp_path.rglob("*")}
    results = installer.init(str(tmp_path), dry_run=True)
    after = {path.relative_to(tmp_path) for path in tmp_path.rglob("*")}

    assert results["created"]
    assert after == before


def test_init_requires_exact_git_root(tmp_path):
    nested = tmp_path / "nested"
    nested.mkdir()
    with pytest.raises(installer.InstallerError, match="--subproject"):
        installer.init(str(nested))


def test_subproject_install_is_explicit_and_isolated(tmp_path):
    product = tmp_path / "products" / "pricing"
    product.mkdir(parents=True)

    installer.init(str(product), subproject=True)

    assert (product / ".github" / "skills" / "akmaestro-init" / "SKILL.md").is_file()
    assert (product / ".agentic" / "bin" / "akmaestro-state.py").is_file()
    assert (product / "AGENTS.md").is_file()
    assert (product / ".gitignore").is_file()
    assert not (tmp_path / ".github").exists()
    assert not (tmp_path / ".agentic").exists()
    assert not (tmp_path / "AGENTS.md").exists()
    assert not (tmp_path / ".gitignore").exists()

    manifest = _manifest(product)
    assert manifest["installation_mode"] == "subproject"
    assert manifest["project_root"] == "."
    assert manifest["git_root"] == "../.."


def test_subproject_mode_rejects_the_git_root(tmp_path):
    with pytest.raises(installer.InstallerError, match="omit --subproject"):
        installer.init(str(tmp_path), subproject=True)

    assert not (tmp_path / ".agentic").exists()


def test_subproject_dry_run_writes_nothing(tmp_path):
    product = tmp_path / "products" / "pricing"
    product.mkdir(parents=True)
    before = {path.relative_to(tmp_path) for path in tmp_path.rglob("*")}

    results = installer.init(str(product), subproject=True, dry_run=True)

    assert results["created"]
    assert {path.relative_to(tmp_path) for path in tmp_path.rglob("*")} == before


def test_subproject_update_requires_an_existing_installation(tmp_path):
    product = tmp_path / "products" / "pricing"
    product.mkdir(parents=True)

    with pytest.raises(installer.InstallerError, match="existing subproject"):
        installer.update(str(product), subproject=True)

    assert not (product / ".agentic").exists()
    assert not (product / ".github").exists()


def test_subproject_update_requires_explicit_mode_and_preserves_boundary(tmp_path):
    product = tmp_path / "products" / "pricing"
    product.mkdir(parents=True)
    installer.init(str(product), subproject=True)
    kit_owned = product / ".github" / "skills" / "doctor" / "SKILL.md"
    original = kit_owned.read_bytes()
    kit_owned.write_bytes(b"pretend this is an OLD kit version\n")
    manifest_path = product / ".agentic" / "setup" / "kit-manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["files"][".github/skills/doctor/SKILL.md"] = installer._sha256(
        kit_owned.read_bytes()
    )
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(installer.InstallerError, match="--subproject"):
        installer.update(str(product))
    results = installer.update(str(product), subproject=True)

    assert kit_owned.read_bytes() == original
    assert ".github/skills/doctor/SKILL.md" in results["updated"]
    assert _manifest(product)["installation_mode"] == "subproject"
    assert not (tmp_path / ".github").exists()


def test_subproject_update_rejects_manifest_boundary_tampering(tmp_path):
    product = tmp_path / "products" / "pricing"
    product.mkdir(parents=True)
    installer.init(str(product), subproject=True)
    manifest_path = product / ".agentic" / "setup" / "kit-manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["git_root"] = ".."
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(installer.InstallerError, match="does not match"):
        installer.update(str(product), subproject=True)


def test_cli_subproject_init_and_update(tmp_path, capsys):
    product = tmp_path / "products" / "pricing"
    product.mkdir(parents=True)

    rc = cli.main(["init", "--subproject", "--path", str(product)])

    assert rc == 0
    assert "subproject root" in capsys.readouterr().out

    rc = cli.main(["update", "--subproject", "--path", str(product)])

    assert rc == 0
    assert "subproject" in capsys.readouterr().out


def test_invalid_manifest_is_rejected_without_replacement(tmp_path):
    manifest = tmp_path / ".agentic" / "setup" / "kit-manifest.json"
    manifest.parent.mkdir(parents=True)
    manifest.write_text("{not-json", encoding="utf-8")

    with pytest.raises(installer.InstallerError, match="valid kit manifest"):
        installer.update(str(tmp_path))
    assert manifest.read_text(encoding="utf-8") == "{not-json"


def test_reserved_skill_collision_fails_before_writing(tmp_path):
    collision = tmp_path / ".github" / "skills" / "status" / "SKILL.md"
    collision.parent.mkdir(parents=True)
    collision.write_text("---\nname: status\n---\ncustom\n", encoding="utf-8")

    with pytest.raises(installer.InstallerError, match="reserved skill collision"):
        installer.init(str(tmp_path))
    assert not (tmp_path / ".agentic").exists()


def test_unclaimed_custom_init_skill_is_preserved(tmp_path):
    custom = tmp_path / ".github" / "skills" / "init" / "SKILL.md"
    custom.parent.mkdir(parents=True)
    custom.write_text(
        "---\nname: init\ndescription: Team-owned\n---\n", encoding="utf-8"
    )

    installer.init(str(tmp_path))

    assert "Team-owned" in custom.read_text(encoding="utf-8")
    assert (tmp_path / ".github" / "skills" / "akmaestro-init" / "SKILL.md").is_file()


def test_init_refuses_symlinked_destination_parent(tmp_path):
    outside = tmp_path.parent / f"{tmp_path.name}-outside"
    outside.mkdir()
    (tmp_path / ".github").symlink_to(outside, target_is_directory=True)

    with pytest.raises(installer.InstallerError, match="symlinked installation path"):
        installer.init(str(tmp_path))


def _manifest(tmp_path):
    return json.loads(
        (tmp_path / ".agentic" / "setup" / "kit-manifest.json").read_text()
    )


def test_init_writes_manifest(tmp_path):
    installer.init(str(tmp_path))
    manifest = _manifest(tmp_path)
    assert manifest["files"][".github/skills/akmaestro-init/SKILL.md"]
    assert manifest["hooks_enabled"] is False
    assert manifest["hooks_config_structure_hash"]
    assert manifest["installation_mode"] == "repository"
    assert manifest["project_root"] == "."
    assert manifest["git_root"] == "."
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
    customized = [
        tmp_path / ".github" / "skills" / "teach" / "SKILL.md",
        tmp_path / ".github" / "skills" / "status" / "SKILL.md",
    ]
    for path in customized:
        path.write_text("custom\n", encoding="utf-8")

    results = installer.update(str(tmp_path), force=True)

    for path in customized:
        assert path.read_text(encoding="utf-8") != "custom\n"
        assert path.relative_to(tmp_path).as_posix() in results["updated"]


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
    assert ".github/skills/akmaestro-init/SKILL.md" in results["up_to_date"]


def test_update_respects_no_hooks_install(tmp_path):
    installer.init(str(tmp_path), with_hooks=False)

    results = installer.update(str(tmp_path))

    assert not (tmp_path / ".github" / "hooks").exists()
    assert not any("hooks" in f for f in results["created"])


def test_update_preserves_enabled_hook_consent(tmp_path):
    installer.init(str(tmp_path))
    config_path = tmp_path / ".github" / "hooks" / "hooks.json"
    config = json.loads(config_path.read_text())
    config["disableAllHooks"] = False
    config_path.write_text(json.dumps(config), encoding="utf-8")

    installer.update(str(tmp_path))

    assert json.loads(config_path.read_text())["disableAllHooks"] is False
    assert _manifest(tmp_path)["hooks_enabled"] is True


def test_hook_consent_does_not_make_custom_handlers_kit_owned(tmp_path):
    installer.init(str(tmp_path))
    config_path = tmp_path / ".github" / "hooks" / "hooks.json"
    config = json.loads(config_path.read_text(encoding="utf-8"))
    config["hooks"]["postToolUse"].append(
        {"type": "command", "bash": "team-owned-hook", "timeoutSec": 5}
    )
    config_path.write_text(json.dumps(config), encoding="utf-8")

    state.set_hooks_enabled(tmp_path, True)
    results = installer.update(str(tmp_path))

    updated = json.loads(config_path.read_text(encoding="utf-8"))
    assert updated["disableAllHooks"] is False
    assert any(
        handler.get("bash") == "team-owned-hook"
        for handler in updated["hooks"]["postToolUse"]
    )
    assert ".github/hooks/hooks.json" in results["kept"]


def test_update_removes_only_untouched_retired_files(tmp_path):
    installer.init(str(tmp_path))
    retired = tmp_path / ".github" / "skills" / "retired" / "SKILL.md"
    retired.parent.mkdir(parents=True)
    retired.write_text("retired\n", encoding="utf-8")
    manifest_path = tmp_path / ".agentic" / "setup" / "kit-manifest.json"
    manifest = json.loads(manifest_path.read_text())
    manifest["files"][".github/skills/retired/SKILL.md"] = installer._sha256(
        retired.read_bytes()
    )
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    results = installer.update(str(tmp_path))

    assert ".github/skills/retired/SKILL.md" in results["removed"]
    assert not retired.exists()


def test_update_never_touches_a_filled_in_agents_md(tmp_path):
    installer.init(str(tmp_path))
    agents = tmp_path / "AGENTS.md"
    agents.write_text(
        "# Real instructions written by /akmaestro-init\n", encoding="utf-8"
    )

    installer.update(str(tmp_path))

    assert (
        agents.read_text(encoding="utf-8")
        == "# Real instructions written by /akmaestro-init\n"
    )


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
        pairs.append(
            (REPO_ROOT / ".github" / "skills" / name, ASSETS / "skills" / name)
        )
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
    (
        "restricted-path-guard.sh",
        '{"toolName":"edit","toolArgs":{"path":".env"}}',
        "deny",
    ),
    (
        "restricted-path-guard.sh",
        '{"toolName":"edit","toolArgs":{"path":"README.md"}}',
        "allow",
    ),
    (
        "restricted-path-guard.sh",
        '{"tool_name":"create","tool_input":{"path":"secrets/x.txt"}}',
        "deny",
    ),
    ("restricted-path-guard.sh", "garbage not json", "allow"),
    # Workspace boundary: outside the repo and not a declared modifiable sibling.
    (
        "restricted-path-guard.sh",
        '{"toolName":"edit","toolArgs":{"path":"../vendor-c/core.py"}}',
        "deny",
    ),
    (
        "restricted-path-guard.sh",
        '{"toolName":"edit","toolArgs":{"path":"/etc/hosts"}}',
        "deny",
    ),
    (
        "dangerous-command-guard.sh",
        '{"toolName":"bash","toolArgs":{"command":"rm -rf /"}}',
        "deny",
    ),
    (
        "dangerous-command-guard.sh",
        '{"toolName":"bash","toolArgs":{"command":"ls -la"}}',
        "allow",
    ),
    (
        "dangerous-command-guard.sh",
        '{"toolName":"edit","toolArgs":{"path":"a.md","content":"rm -rf /"}}',
        "allow",
    ),
]


@pytest.mark.skipif(sys.platform == "win32", reason="bash guards are POSIX-only")
@pytest.mark.parametrize("script,payload,expected", HOOK_CASES)
def test_bash_guard_logic(tmp_path, script, payload, expected):
    if not _have("bash") or not _have("jq"):
        pytest.skip("bash and jq required")
    installer.init(str(tmp_path))

    proc = subprocess.run(
        ["bash", f".github/hooks/scripts/{script}"],
        input=payload,
        capture_output=True,
        text=True,
        cwd=tmp_path,
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
    return json.dumps(
        {
            "sessionId": "x",
            "timestamp": 1,
            "cwd": "/r",
            "toolName": tool_name,
            "toolArgs": json.dumps(inner),
        }
    )


def _live_cases(repo):
    """Real-shape payloads with string toolArgs and ABSOLUTE paths — the exact
    class the object-form dry-runs failed to catch (guards fell through to allow
    because .path resolved to null on a string). Regression lock for that bug."""
    return [
        (
            "restricted-path-guard.sh",
            _live_event("create", {"path": str(repo / ".env"), "file_text": "FOO=bar"}),
            "deny",
        ),
        (
            "restricted-path-guard.sh",
            _live_event("edit", {"path": str(repo / "README.md")}),
            "allow",
        ),
        (
            "restricted-path-guard.sh",
            _live_event("edit", {"path": str(repo / "secrets" / "s.txt")}),
            "deny",
        ),
        # A prompt-shape event (no toolName/toolArgs at all) must fall through.
        (
            "restricted-path-guard.sh",
            json.dumps(
                {"sessionId": "x", "timestamp": 1, "cwd": str(repo), "prompt": "hi"}
            ),
            "allow",
        ),
        (
            "dangerous-command-guard.sh",
            _live_event("powershell", {"command": "rm -rf /"}),
            "deny",
        ),
        (
            "dangerous-command-guard.sh",
            _live_event("powershell", {"command": "ls -la"}),
            "allow",
        ),
    ]


@pytest.mark.skipif(sys.platform == "win32", reason="bash guards are POSIX-only")
def test_bash_guards_real_cli_payload_shape(tmp_path):
    if not _have("bash") or not _have("jq"):
        pytest.skip("bash and jq required")
    installer.init(str(tmp_path))
    for script, payload, expected in _live_cases(tmp_path):
        proc = subprocess.run(
            ["bash", f".github/hooks/scripts/{script}"],
            input=payload,
            capture_output=True,
            text=True,
            cwd=tmp_path,
        )
        assert proc.returncode == 0, proc.stderr
        assert json.loads(proc.stdout)["permissionDecision"] == expected, (
            script,
            payload,
        )


def test_powershell_guards_real_cli_payload_shape(tmp_path):
    if not _have("pwsh"):
        pytest.skip("pwsh required")
    installer.init(str(tmp_path))
    for script, payload, expected in _live_cases(tmp_path):
        proc = _run_pwsh(script.replace(".sh", ".ps1"), payload, tmp_path)
        assert proc.returncode == 0, proc.stderr
        assert json.loads(proc.stdout)["permissionDecision"] == expected, (
            script,
            payload,
        )


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
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
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
        input=payload,
        capture_output=True,
        text=True,
        cwd=repo,
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


def _symlink_escape(tmp_path):
    outside = tmp_path.parent / f"{tmp_path.name}-hook-outside"
    outside.mkdir(exist_ok=True)
    link = tmp_path / "linked-outside"
    try:
        link.symlink_to(outside, target_is_directory=True)
    except OSError as exc:
        pytest.skip(f"symlink creation unavailable: {exc}")
    return json.dumps(
        {"toolName": "edit", "toolArgs": {"path": "linked-outside/new.txt"}}
    )


@pytest.mark.skipif(sys.platform == "win32", reason="bash guards are POSIX-only")
def test_bash_guard_denies_symlink_escape(tmp_path):
    if not _have("bash") or not _have("jq"):
        pytest.skip("bash and jq required")
    installer.init(str(tmp_path))
    proc = subprocess.run(
        ["bash", ".github/hooks/scripts/restricted-path-guard.sh"],
        input=_symlink_escape(tmp_path),
        capture_output=True,
        text=True,
        cwd=tmp_path,
    )
    assert proc.returncode == 0, proc.stderr
    assert json.loads(proc.stdout)["permissionDecision"] == "deny"


def test_powershell_guard_denies_symlink_or_junction_escape(tmp_path):
    if not _have("pwsh"):
        pytest.skip("pwsh required")
    installer.init(str(tmp_path))
    proc = _run_pwsh("restricted-path-guard.ps1", _symlink_escape(tmp_path), tmp_path)
    assert proc.returncode == 0, proc.stderr
    assert json.loads(proc.stdout)["permissionDecision"] == "deny"


@pytest.mark.skipif(sys.platform == "win32", reason="audit-log.sh is POSIX-only")
def test_audit_log_infers_event_kind_structurally(tmp_path):
    """The GA CLI sends no event-name field; audit-log must infer it from which
    fields are present (toolName+toolResult / prompt / reason)."""
    if not _have("bash") or not _have("jq"):
        pytest.skip("bash and jq required")
    installer.init(str(tmp_path))
    events = [
        (
            '{"sessionId":"s","toolName":"create","toolArgs":"{}","toolResult":{"resultType":"ok"}}',
            "postToolUse",
        ),
        ('{"sessionId":"s","prompt":"hi"}', "userPromptSubmitted"),
        ('{"sessionId":"s","reason":"complete"}', "sessionEnd"),
    ]
    for payload, _ in events:
        subprocess.run(
            ["bash", ".github/hooks/scripts/audit-log.sh"],
            input=payload,
            capture_output=True,
            text=True,
            cwd=tmp_path,
        )

    lines = list((tmp_path / ".agentic" / "audit").glob("*.jsonl"))
    assert lines, "no audit trail written"
    recorded = [json.loads(line)["event"] for line in lines[0].read_text().splitlines()]
    assert recorded == [e for _, e in events]


@pytest.mark.skipif(sys.platform == "win32", reason="audit-log.sh is POSIX-only")
def test_bash_audit_log_never_persists_sensitive_payload_content(tmp_path):
    if not _have("bash") or not _have("jq"):
        pytest.skip("bash and jq required")
    installer.init(str(tmp_path))
    secret = "AKMAESTRO-DO-NOT-PERSIST-SECRET"
    payload = json.dumps(
        {
            "sessionId": secret,
            "prompt": secret,
            "toolArgs": secret,
            "toolResult": secret,
        }
    )
    subprocess.run(
        ["bash", ".github/hooks/scripts/audit-log.sh"],
        input=payload,
        capture_output=True,
        text=True,
        cwd=tmp_path,
        check=True,
    )
    stored = "\n".join(
        path.read_text(encoding="utf-8")
        for path in (tmp_path / ".agentic" / "audit").glob("*.jsonl")
    )
    assert secret not in stored


def test_powershell_audit_log_never_persists_sensitive_payload_content(tmp_path):
    if not _have("pwsh"):
        pytest.skip("pwsh required")
    installer.init(str(tmp_path))
    secret = "AKMAESTRO-DO-NOT-PERSIST-SECRET"
    payload = json.dumps(
        {
            "sessionId": secret,
            "prompt": secret,
            "toolArgs": secret,
            "toolResult": secret,
        }
    )
    proc = _run_pwsh("audit-log.ps1", payload, tmp_path)
    assert proc.returncode == 0, proc.stderr
    stored = "\n".join(
        path.read_text(encoding="utf-8")
        for path in (tmp_path / ".agentic" / "audit").glob("*.jsonl")
    )
    assert secret not in stored


def _configure_lint_probe(tmp_path):
    probe = tmp_path / ".agentic" / "hooks" / "lint-probe.py"
    probe.write_text(
        "import sys\nprint(repr(sys.argv[1:]))\nraise SystemExit(7)\n",
        encoding="utf-8",
    )
    config = tmp_path / ".agentic" / "hooks" / "lint-commands.json"
    config.write_text(
        json.dumps(
            {
                "py": {
                    "command": "python",
                    "args": [".agentic/hooks/lint-probe.py", "{file}"],
                }
            }
        ),
        encoding="utf-8",
    )
    changed = tmp_path / "unsafe;touch SHOULD_NOT_EXIST.py"
    changed.write_text("pass\n", encoding="utf-8")
    payload = json.dumps({"toolName": "edit", "toolArgs": {"path": str(changed)}})
    return payload, changed


@pytest.mark.skipif(sys.platform == "win32", reason="lint-on-edit.sh is POSIX-only")
def test_bash_lint_hook_executes_structured_args_without_shell_injection(tmp_path):
    if not _have("bash") or not _have("jq") or not _have("python"):
        pytest.skip("bash, jq, and python required")
    installer.init(str(tmp_path))
    payload, changed = _configure_lint_probe(tmp_path)
    proc = subprocess.run(
        ["bash", ".github/hooks/scripts/lint-on-edit.sh"],
        input=payload,
        capture_output=True,
        text=True,
        cwd=tmp_path,
    )
    assert proc.returncode == 0, proc.stderr
    assert str(changed) in json.loads(proc.stdout)["additionalContext"]
    assert not (tmp_path / "SHOULD_NOT_EXIST.py").exists()


def test_powershell_lint_hook_executes_structured_args_without_shell_injection(
    tmp_path,
):
    if not _have("pwsh") or not _have("python"):
        pytest.skip("pwsh and python required")
    installer.init(str(tmp_path))
    payload, changed = _configure_lint_probe(tmp_path)
    proc = _run_pwsh("lint-on-edit.ps1", payload, tmp_path)
    assert proc.returncode == 0, proc.stderr
    assert str(changed) in json.loads(proc.stdout)["additionalContext"]
    assert not (tmp_path / "SHOULD_NOT_EXIST.py").exists()


def _run_pwsh(script, payload, cwd):
    return subprocess.run(
        [
            "pwsh",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(Path(".github/hooks/scripts") / script),
        ],
        input=payload,
        capture_output=True,
        text=True,
        cwd=cwd,
    )


def _have(tool):
    from shutil import which

    return which(tool) is not None
