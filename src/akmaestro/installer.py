"""The installer: a thin file-dropper.

All dynamic logic (detection, interview, generation, section-aware merge) lives
in the skills and runs inside the agent. This module only copies static assets
into the target repository and never overwrites existing files (decision 6).
"""

from __future__ import annotations

import os
import stat
from pathlib import Path
from typing import Dict, List

ASSETS = Path(__file__).resolve().parent / "assets"

# Bootstrap pointer files: (asset relative path, destination relative path).
# Dropped only if the destination is absent, so they never clobber real ones.
BOOTSTRAP = [
    ("bootstrap/AGENTS.bootstrap.md", "AGENTS.md"),
    ("bootstrap/copilot-instructions.bootstrap.md", ".github/copilot-instructions.md"),
]

AUDIT_IGNORE = ".agentic/audit/"


def init(target: str = ".", with_hooks: bool = True) -> Dict[str, List[str]]:
    """Install the kit into ``target``. Idempotent and non-destructive."""
    root = Path(target).resolve()
    results: Dict[str, List[str]] = {"created": [], "skipped": []}

    # Skills (always): init, setup-*, teach, doctor.
    _copy_tree(ASSETS / "skills", root / ".github" / "skills", root, results)

    # Hooks (optional topic; may be declined or disabled by policy). The audit
    # dir and its gitignore entry only exist for the audit-log hook, so they
    # are installed together.
    if with_hooks:
        _copy_tree(ASSETS / "hooks", root / ".github" / "hooks", root, results)
        _copy_tree(ASSETS / "hooks-data", root / ".agentic" / "hooks", root, results)
        _make_executable(root / ".github" / "hooks" / "scripts")
        (root / ".agentic" / "audit").mkdir(parents=True, exist_ok=True)
        _ensure_gitignore(root, results)

    # Bootstrap pointer files — only if absent.
    for src_rel, dst_rel in BOOTSTRAP:
        _copy_file(ASSETS / src_rel, root / dst_rel, root, results)

    # Runtime state dir (the setup skills write into this).
    (root / ".agentic" / "setup").mkdir(parents=True, exist_ok=True)

    return results


def _rel(path: Path, root: Path) -> str:
    try:
        return str(path.relative_to(root))
    except ValueError:
        return str(path)


def _copy_file(src: Path, dst: Path, root: Path, results: Dict[str, List[str]]) -> None:
    if dst.exists():
        results["skipped"].append(_rel(dst, root))
        return
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_bytes(src.read_bytes())
    results["created"].append(_rel(dst, root))


def _copy_tree(src: Path, dst: Path, root: Path, results: Dict[str, List[str]]) -> None:
    if not src.is_dir():
        return
    for cur, _dirs, files in os.walk(src):
        rel = Path(cur).relative_to(src)
        for name in sorted(files):
            _copy_file(Path(cur) / name, dst / rel / name, root, results)


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
    results["created"].append(_rel(gi, root) + " (+audit ignore)")
