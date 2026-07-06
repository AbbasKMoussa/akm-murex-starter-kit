"""The installer: a thin file-dropper.

All dynamic logic (detection, interview, generation, section-aware merge) lives
in the skills and runs inside the agent. This module only copies static assets
into the target repository:

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
import stat
from pathlib import Path
from typing import Dict, List, Tuple

from . import __version__

ASSETS = Path(__file__).resolve().parent / "assets"

# Bootstrap pointer files: (asset relative path, destination relative path).
# Dropped only if the destination is absent, so they never clobber real ones.
BOOTSTRAP = [
    ("bootstrap/AGENTS.bootstrap.md", "AGENTS.md"),
    ("bootstrap/copilot-instructions.bootstrap.md", ".github/copilot-instructions.md"),
]

AUDIT_IGNORE = ".agentic/audit/"
MANIFEST_REL = ".agentic/setup/kit-manifest.json"


def init(target: str = ".", with_hooks: bool = True) -> Dict[str, List[str]]:
    """Install the kit into ``target``. Idempotent and non-destructive."""
    root = Path(target).resolve()
    results: Dict[str, List[str]] = {"created": [], "skipped": []}
    manifest = _load_manifest(root)

    for src, dst_rel in _mappings(with_hooks):
        dst = root / dst_rel
        data = src.read_bytes()
        if dst.exists():
            results["skipped"].append(dst_rel)
            # Adopt into the manifest only if it is exactly the kit's file, so
            # a later `update` can refresh it.
            if dst.read_bytes() == data:
                manifest["files"][dst_rel] = _sha256(data)
        else:
            dst.parent.mkdir(parents=True, exist_ok=True)
            dst.write_bytes(data)
            results["created"].append(dst_rel)
            manifest["files"][dst_rel] = _sha256(data)

    # The audit dir and its gitignore entry only exist for the audit-log hook,
    # so they are installed together with the hooks.
    if with_hooks:
        _make_executable(root / ".github" / "hooks" / "scripts")
        (root / ".agentic" / "audit").mkdir(parents=True, exist_ok=True)
        _ensure_gitignore(root, results)

    # Runtime state dir (the setup skills write into this).
    (root / ".agentic" / "setup").mkdir(parents=True, exist_ok=True)

    _save_manifest(root, manifest)
    return results


def update(target: str = ".", force: bool = False) -> Dict[str, List[str]]:
    """Refresh kit-owned files in ``target`` to this kit version.

    A file is overwritten only when it is missing, or byte-identical to what
    the kit last installed (per the manifest) — i.e. the user never touched it.
    Customized files and files with unknown provenance (installed before the
    manifest existed) are kept, unless ``force`` is passed.
    """
    root = Path(target).resolve()
    results: Dict[str, List[str]] = {
        "created": [], "updated": [], "up_to_date": [], "kept": [],
    }
    manifest = _load_manifest(root)
    # Respect the original --no-hooks choice: only manage hook files if the
    # hooks are actually installed.
    hooks_installed = (root / ".github" / "hooks" / "hooks.json").is_file()

    for src, dst_rel in _mappings(hooks_installed):
        dst = root / dst_rel
        new = src.read_bytes()
        if not dst.exists():
            dst.parent.mkdir(parents=True, exist_ok=True)
            dst.write_bytes(new)
            results["created"].append(dst_rel)
        elif dst.read_bytes() == new:
            results["up_to_date"].append(dst_rel)
        elif force or manifest["files"].get(dst_rel) == _sha256(dst.read_bytes()):
            dst.write_bytes(new)
            results["updated"].append(dst_rel)
        else:
            results["kept"].append(dst_rel)
            continue
        manifest["files"][dst_rel] = _sha256(new)

    if hooks_installed:
        _make_executable(root / ".github" / "hooks" / "scripts")

    _save_manifest(root, manifest)
    return results


def _mappings(with_hooks: bool) -> List[Tuple[Path, str]]:
    """All (asset file, posix destination relative path) pairs."""
    pairs = _tree_pairs(ASSETS / "skills", ".github/skills")
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


def _load_manifest(root: Path) -> Dict:
    path = root / MANIFEST_REL
    if path.is_file():
        try:
            manifest = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(manifest.get("files"), dict):
                manifest["kit_version"] = __version__
                return manifest
        except (json.JSONDecodeError, OSError):
            pass
    return {"version": 1, "kit_version": __version__, "files": {}}


def _save_manifest(root: Path, manifest: Dict) -> None:
    path = root / MANIFEST_REL
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _make_executable(scripts_dir: Path) -> None:
    if not scripts_dir.is_dir():
        return
    for sh in scripts_dir.glob("*.sh"):
        mode = sh.stat().st_mode
        sh.chmod(mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


def _ensure_gitignore(root: Path, results: Dict[str, List[str]]) -> None:
    gi = root / ".gitignore"
    line = AUDIT_IGNORE
    existing = gi.read_text(encoding="utf-8").splitlines() if gi.exists() else []
    if any(l.strip() == line for l in existing):
        return
    with gi.open("a", encoding="utf-8") as fh:
        if existing and existing[-1].strip():
            fh.write("\n")
        fh.write("# Local agent audit trail written by the audit-log hook — never commit.\n")
        fh.write(line + "\n")
    results["created"].append(".gitignore (+audit ignore)")
