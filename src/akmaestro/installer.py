"""Install AKMaestro's repo-local workflow assets.

Detection, interviews, generation, and section-aware merge remain in the skills.
Deterministic workflow state transitions live in the bundled standard-library
controller copied to ``.agentic/bin``. This module installs those assets:

- ``init`` never overwrites existing files (decision 6);
- ``update`` refreshes kit-owned files, where "kit-owned" means the file on
  disk is byte-identical to what the kit last installed (tracked as a sha256
  in ``.agentic/setup/kit-manifest.json``). Customized files are never touched
  unless ``force`` is passed.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import stat
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Dict, List, Optional, Tuple

from . import __version__

ASSETS = Path(__file__).resolve().parent / "assets"
STATE_CONTROLLER = Path(__file__).resolve().parent / "state.py"

# Bootstrap pointer files: (asset relative path, destination relative path).
# Dropped only if the destination is absent, so they never clobber real ones.
BOOTSTRAP = [
    ("bootstrap/AGENTS.bootstrap.md", "AGENTS.md"),
    ("bootstrap/copilot-instructions.bootstrap.md", ".github/copilot-instructions.md"),
]

LOCAL_IGNORE = ".agentic/local/"
AUDIT_IGNORE = ".agentic/audit/"
MANIFEST_REL = ".agentic/setup/kit-manifest.json"
HOOKS_CONFIG_REL = ".github/hooks/hooks.json"
RESERVED_SKILLS = ("akmaestro-init", "status", "feature")
INSTALLATION_MODES = ("repository", "subproject")


class InstallerError(RuntimeError):
    """A target-repository condition that requires user action."""


@dataclass(frozen=True)
class InstallationContext:
    project_root: Path
    git_root: Path
    mode: str

    def manifest_fields(self) -> Dict[str, str]:
        return {
            "installation_mode": self.mode,
            "project_root": ".",
            "git_root": Path(
                os.path.relpath(self.git_root, self.project_root)
            ).as_posix(),
        }


def init(
    target: str = ".",
    with_hooks: bool = True,
    dry_run: bool = False,
    subproject: bool = False,
) -> Dict[str, List[str]]:
    """Install the kit into ``target``. Idempotent and non-destructive."""
    context = _installation_context(target, subproject)
    root = context.project_root
    results: Dict[str, List[str]] = {"created": [], "skipped": []}
    _preflight_runtime_paths(root, with_hooks)
    manifest = _load_manifest(root)
    _apply_installation_context(manifest, context)
    _check_reserved_skill_collisions(root)
    hooks_were_installed = bool(
        manifest.get("hooks_installed", _hooks_were_installed(root, manifest))
    )
    manifest["hooks_installed"] = hooks_were_installed or with_hooks
    manifest["hooks_enabled"] = (
        _hooks_are_enabled(root)
        if (root / HOOKS_CONFIG_REL).is_file()
        else bool(manifest.get("hooks_enabled", False))
    )

    mappings = _mappings(with_hooks)
    destinations = {
        dst_rel: _safe_destination(root, dst_rel) for _src, dst_rel in mappings
    }
    for src, dst_rel in mappings:
        dst = destinations[dst_rel]
        data = _asset_data(src, dst_rel, bool(manifest["hooks_enabled"]))
        if dst.exists():
            results["skipped"].append(dst_rel)
            # Adopt into the manifest only if it is exactly the kit's file, so
            # a later `update` can refresh it.
            if dst.read_bytes() == data:
                manifest["files"][dst_rel] = _sha256(data)
                if dst_rel == HOOKS_CONFIG_REL:
                    manifest["hooks_config_structure_hash"] = _hooks_structure_hash(
                        data
                    )
        else:
            results["created"].append(dst_rel)
            if dry_run:
                continue
            dst.parent.mkdir(parents=True, exist_ok=True)
            _write_atomic(dst, data)
            manifest["files"][dst_rel] = _sha256(data)
            if dst_rel == HOOKS_CONFIG_REL:
                manifest["hooks_config_structure_hash"] = _hooks_structure_hash(data)

    # The audit dir only exists for the audit-log hook. Worktree-local workflow
    # state exists for every installation and is never committed.
    if with_hooks and not dry_run:
        _make_executable(root / ".github" / "hooks" / "scripts")
        (root / ".agentic" / "audit").mkdir(parents=True, exist_ok=True)
    if not dry_run:
        (root / ".agentic" / "local").mkdir(parents=True, exist_ok=True)
    _ensure_gitignore(root, results, with_audit=with_hooks, dry_run=dry_run)

    # Runtime state dir (the setup skills write into this).
    if not dry_run:
        (root / ".agentic" / "setup").mkdir(parents=True, exist_ok=True)

    if not dry_run:
        manifest["kit_version"] = __version__
        _save_manifest(root, manifest)
    return results


def update(
    target: str = ".",
    force: bool = False,
    dry_run: bool = False,
    subproject: bool = False,
) -> Dict[str, List[str]]:
    """Refresh kit-owned files in ``target`` to this kit version.

    A file is overwritten only when it is missing, or byte-identical to what
    the kit last installed (per the manifest) — i.e. the user never touched it.
    Customized files and files with unknown provenance (installed before the
    manifest existed) are kept, unless ``force`` is passed.
    """
    context = _installation_context(target, subproject)
    root = context.project_root
    results: Dict[str, List[str]] = {
        "created": [],
        "updated": [],
        "up_to_date": [],
        "kept": [],
        "removed": [],
    }
    _safe_destination(root, MANIFEST_REL)
    manifest_existed = (root / MANIFEST_REL).exists()
    manifest = _load_manifest(root)
    if context.mode == "subproject" and not manifest_existed:
        raise InstallerError(
            "subproject update requires an existing subproject installation; "
            "run 'akmaestro init --subproject' first"
        )
    _apply_installation_context(manifest, context)
    from_version = manifest.get("kit_version")
    hooks_installed = bool(
        manifest.get("hooks_installed", _hooks_were_installed(root, manifest))
    )
    hooks_enabled = _hooks_are_enabled(root) if hooks_installed else False
    if not force:
        _check_reserved_skill_collisions(
            root, allow_manifest_owned=True, manifest=manifest
        )

    mappings = _mappings(hooks_installed)
    current_paths = {dst_rel for _src, dst_rel in mappings}
    retired = sorted(set(manifest["files"]) - current_paths)
    destinations = {
        dst_rel: _safe_destination(root, dst_rel)
        for dst_rel in current_paths.union(retired)
    }
    _preflight_runtime_paths(root, hooks_installed)
    for src, dst_rel in mappings:
        dst = destinations[dst_rel]
        new = _asset_data(src, dst_rel, hooks_enabled)
        if not dst.exists():
            results["created"].append(dst_rel)
            if dry_run:
                continue
            dst.parent.mkdir(parents=True, exist_ok=True)
            _write_atomic(dst, new)
        elif dst.read_bytes() == new:
            results["up_to_date"].append(dst_rel)
        elif (
            force
            or manifest["files"].get(dst_rel) == _sha256(dst.read_bytes())
            or (
                dst_rel == HOOKS_CONFIG_REL
                and manifest.get("hooks_config_structure_hash")
                == _try_hooks_structure_hash(dst.read_bytes())
            )
        ):
            results["updated"].append(dst_rel)
            if dry_run:
                continue
            _write_atomic(dst, new)
        else:
            results["kept"].append(dst_rel)
            continue
        manifest["files"][dst_rel] = _sha256(new)
        if dst_rel == HOOKS_CONFIG_REL:
            manifest["hooks_config_structure_hash"] = _hooks_structure_hash(new)

    for dst_rel in retired:
        dst = destinations[dst_rel]
        if not dst.exists():
            manifest["files"].pop(dst_rel, None)
            continue
        if dst.is_file() and _sha256(dst.read_bytes()) == manifest["files"][dst_rel]:
            results["removed"].append(dst_rel)
            if not dry_run:
                dst.unlink()
                _remove_empty_parents(dst.parent, root)
                manifest["files"].pop(dst_rel, None)
        else:
            results["kept"].append(dst_rel)

    if hooks_installed and not dry_run:
        _make_executable(root / ".github" / "hooks" / "scripts")

    if not dry_run:
        (root / ".agentic" / "local").mkdir(parents=True, exist_ok=True)
    _ensure_gitignore(root, results, with_audit=hooks_installed, dry_run=dry_run)

    if not dry_run:
        manifest["previous_kit_version"] = from_version
        manifest["kit_version"] = __version__
        manifest["hooks_installed"] = hooks_installed
        manifest["hooks_enabled"] = hooks_enabled
        _save_manifest(root, manifest)
    return results


def _mappings(with_hooks: bool) -> List[Tuple[Path, str]]:
    """All (asset file, posix destination relative path) pairs."""
    pairs = _tree_pairs(ASSETS / "skills", ".github/skills")
    pairs += _tree_pairs(ASSETS / "schemas", ".agentic/schemas")
    pairs += _tree_pairs(ASSETS / "runtime", ".agentic")
    pairs.append((STATE_CONTROLLER, ".agentic/bin/akmaestro-state.py"))
    if with_hooks:
        pairs += _tree_pairs(ASSETS / "hooks", ".github/hooks")
        pairs += _tree_pairs(ASSETS / "hooks-data", ".agentic/hooks")
    for src_rel, dst_rel in BOOTSTRAP:
        pairs.append((ASSETS / src_rel, dst_rel))
    return pairs


def _tree_pairs(src: Path, dst_prefix: str) -> List[Tuple[Path, str]]:
    pairs: List[Tuple[Path, str]] = []
    if not src.is_dir():
        return pairs
    for cur, _dirs, files in os.walk(src):
        rel = Path(cur).relative_to(src)
        for name in sorted(files):
            pairs.append((Path(cur) / name, (Path(dst_prefix) / rel / name).as_posix()))
    return pairs


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _installation_context(target: str, subproject: bool) -> InstallationContext:
    root = Path(target).resolve()
    if not root.is_dir():
        raise InstallerError(f"target is not a directory: {root}")
    git_root = _find_git_root(root)
    if git_root != root and git_root not in root.parents:
        raise InstallerError(
            f"Git reported a root that does not contain the target: {git_root}"
        )
    if subproject:
        if git_root == root:
            raise InstallerError(
                "target is already the Git root; omit --subproject for a normal "
                "repository installation"
            )
        relative = root.relative_to(git_root)
        if relative.parts and relative.parts[0] == ".git":
            raise InstallerError("a Git metadata directory cannot be a subproject root")
        return InstallationContext(root, git_root, "subproject")
    if git_root != root:
        raise InstallerError(
            f"target must be the Git root: {git_root}; pass --subproject only "
            "when this directory is intentionally an independent product"
        )
    return InstallationContext(root, git_root, "repository")


def _find_git_root(root: Path) -> Path:
    try:
        proc = subprocess.run(
            ["git", "-C", str(root), "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
    except (FileNotFoundError, OSError, subprocess.TimeoutExpired) as exc:
        raise InstallerError(f"cannot verify Git repository root: {exc}") from exc
    if proc.returncode != 0:
        raise InstallerError("target must be the root of an existing Git repository")
    return Path(proc.stdout.strip()).resolve()


def _apply_installation_context(manifest: Dict, context: InstallationContext) -> None:
    expected = context.manifest_fields()
    for field, value in expected.items():
        existing = manifest.get(field)
        if existing is not None and existing != value:
            raise InstallerError(
                "kit manifest installation boundary does not match the selected "
                f"target: {field} is {existing!r}, expected {value!r}"
            )
    manifest.update(expected)


def _safe_destination(root: Path, relative: str) -> Path:
    candidate = root / relative
    current = root
    for part in Path(relative).parts:
        current = current / part
        if current.is_symlink():
            raise InstallerError(f"refusing symlinked installation path: {current}")
    resolved_parent = candidate.parent.resolve()
    if root != resolved_parent and root not in resolved_parent.parents:
        raise InstallerError(f"installation path escapes the repository: {relative}")
    return candidate


def _preflight_runtime_paths(root: Path, with_hooks: bool) -> None:
    paths = [".gitignore", MANIFEST_REL, ".agentic/local"]
    if with_hooks:
        paths.append(".agentic/audit")
    for relative in paths:
        _safe_destination(root, relative)


def _write_atomic(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
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
    finally:
        try:
            temp.unlink()
        except FileNotFoundError:
            pass


def _check_reserved_skill_collisions(
    root: Path,
    *,
    allow_manifest_owned: bool = False,
    manifest: Optional[Dict] = None,
) -> None:
    owned = (manifest or {}).get("files", {})
    for skill in RESERVED_SKILLS:
        relative = f".github/skills/{skill}/SKILL.md"
        path = _safe_destination(root, relative)
        if not path.exists():
            continue
        asset = ASSETS / "skills" / skill / "SKILL.md"
        asset_hash = _sha256(asset.read_bytes()) if asset.is_file() else None
        current_hash = _sha256(path.read_bytes()) if path.is_file() else None
        if current_hash == asset_hash:
            continue
        if allow_manifest_owned and owned.get(relative) == current_hash:
            continue
        raise InstallerError(
            f"reserved skill collision: {relative} is not AKMaestro-owned"
        )


def _asset_data(src: Path, dst_rel: str, hooks_enabled: bool) -> bytes:
    data = src.read_bytes()
    if dst_rel != HOOKS_CONFIG_REL:
        return data
    try:
        config = json.loads(data.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise InstallerError(f"bundled hooks config is invalid: {exc}") from exc
    config["disableAllHooks"] = not hooks_enabled
    return (json.dumps(config, indent=2, sort_keys=True) + "\n").encode("utf-8")


def _hooks_structure_hash(data: bytes) -> str:
    try:
        config = json.loads(data.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise InstallerError(f"hooks config is invalid: {exc}") from exc
    config.pop("disableAllHooks", None)
    canonical = json.dumps(config, sort_keys=True, separators=(",", ":")).encode(
        "utf-8"
    )
    return _sha256(canonical)


def _try_hooks_structure_hash(data: bytes) -> Optional[str]:
    try:
        return _hooks_structure_hash(data)
    except InstallerError:
        return None


def _hooks_are_enabled(root: Path) -> bool:
    path = root / HOOKS_CONFIG_REL
    if not path.is_file():
        return False
    try:
        return (
            json.loads(path.read_text(encoding="utf-8")).get("disableAllHooks") is False
        )
    except (OSError, json.JSONDecodeError):
        return False


def _hooks_were_installed(root: Path, manifest: Dict) -> bool:
    return bool(
        (root / HOOKS_CONFIG_REL).is_file()
        or any(path.startswith(".github/hooks/") for path in manifest.get("files", {}))
    )


def _remove_empty_parents(path: Path, root: Path) -> None:
    while path != root:
        try:
            path.rmdir()
        except OSError:
            return
        path = path.parent


def _load_manifest(root: Path) -> Dict:
    path = root / MANIFEST_REL
    if path.exists() and not path.is_file():
        raise InstallerError(f"kit manifest is not a file: {path}")
    if path.is_file():
        try:
            manifest = json.loads(path.read_text(encoding="utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError, OSError) as exc:
            raise InstallerError(
                f"cannot read valid kit manifest {path}: {exc}"
            ) from exc
        if not isinstance(manifest, dict) or not isinstance(
            manifest.get("files"), dict
        ):
            raise InstallerError(f"kit manifest has an invalid structure: {path}")
        if manifest.get("version") != 1:
            raise InstallerError(
                f"kit manifest uses unsupported version {manifest.get('version')!r}"
            )
        for relative, digest in manifest["files"].items():
            if (
                not isinstance(relative, str)
                or not relative
                or "\\" in relative
                or PurePosixPath(relative).is_absolute()
                or any(part in {".", ".."} for part in PurePosixPath(relative).parts)
                or not isinstance(digest, str)
                or not re.fullmatch(r"[0-9a-f]{64}", digest)
            ):
                raise InstallerError(
                    f"kit manifest contains an invalid file record: {relative!r}"
                )
        for field in ("hooks_installed", "hooks_enabled"):
            if field in manifest and not isinstance(manifest[field], bool):
                raise InstallerError(f"kit manifest field {field} must be boolean")
        mode = manifest.get("installation_mode")
        if mode is not None and mode not in INSTALLATION_MODES:
            raise InstallerError(
                f"kit manifest field installation_mode is invalid: {mode!r}"
            )
        project_root = manifest.get("project_root")
        if project_root is not None and project_root != ".":
            raise InstallerError("kit manifest field project_root must be '.'")
        git_root = manifest.get("git_root")
        if git_root is not None and (
            not isinstance(git_root, str)
            or (
                git_root != "."
                and (
                    "\\" in git_root
                    or PurePosixPath(git_root).is_absolute()
                    or not PurePosixPath(git_root).parts
                    or any(part != ".." for part in PurePosixPath(git_root).parts)
                )
            )
        ):
            raise InstallerError(
                "kit manifest field git_root must be '.' or a normalized "
                "repository-relative ancestor path"
            )
        return manifest
    return {"version": 1, "kit_version": __version__, "files": {}}


def _save_manifest(root: Path, manifest: Dict) -> None:
    path = root / MANIFEST_REL
    data = (json.dumps(manifest, indent=2, sort_keys=True) + "\n").encode("utf-8")
    _write_atomic(path, data)


def _make_executable(scripts_dir: Path) -> None:
    if not scripts_dir.is_dir():
        return
    for sh in scripts_dir.glob("*.sh"):
        mode = sh.stat().st_mode
        sh.chmod(mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


def _ensure_gitignore(
    root: Path,
    results: Dict[str, List[str]],
    with_audit: bool,
    dry_run: bool = False,
) -> None:
    gi = _safe_destination(root, ".gitignore")
    try:
        original = gi.read_text(encoding="utf-8") if gi.exists() else ""
    except (OSError, UnicodeDecodeError) as exc:
        raise InstallerError(f"cannot read UTF-8 .gitignore: {exc}") from exc
    existing = original.splitlines()
    wanted = [LOCAL_IGNORE]
    if with_audit:
        wanted.append(AUDIT_IGNORE)
    missing = [
        line for line in wanted if not any(item.strip() == line for item in existing)
    ]
    if not missing:
        return
    results["created"].append(".gitignore (+local state ignores)")
    if dry_run:
        return
    addition = "\n" if existing and existing[-1].strip() else ""
    addition += "# Developer-local AKMaestro state — never commit.\n"
    addition += "".join(line + "\n" for line in missing)
    _write_atomic(gi, (original + addition).encode("utf-8"))
