"""Command-line entry point: ``akmaestro init`` / ``akmaestro update``."""

from __future__ import annotations

import argparse
from typing import List, Optional

from . import __version__, installer


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="akmaestro",
        description="AKMaestro — set up a repo for agentic coding with GitHub Copilot.",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    p_init = sub.add_parser("init", help="Install the starter kit into the current repository")
    p_init.add_argument("--path", default=".", help="Target repository root (default: cwd)")
    p_init.add_argument("--no-hooks", action="store_true", help="Do not install hooks")

    p_update = sub.add_parser(
        "update",
        help="Refresh kit-owned files to this kit version (customized files are kept)",
    )
    p_update.add_argument("--path", default=".", help="Target repository root (default: cwd)")
    p_update.add_argument(
        "--force",
        action="store_true",
        help="Also overwrite customized files and files the kit cannot attribute to itself",
    )

    args = parser.parse_args(argv)

    if args.command == "init":
        _report_init(installer.init(target=args.path, with_hooks=not args.no_hooks))
    elif args.command == "update":
        _report_update(installer.update(target=args.path, force=args.force))
    return 0


def _report_init(results) -> None:
    for f in results["created"]:
        print(f"  + {f}")
    for f in results["skipped"]:
        print(f"  = {f} (exists, left untouched)")
    print()
    print(
        f"Installed {len(results['created'])} file(s); "
        f"left {len(results['skipped'])} existing file(s) untouched."
    )
    print()
    print("Next: the team lead opens Copilot (VS Code or CLI) at the repo root and runs:")
    print("    /init")
    print('or say: "let\'s run the initialization flow".')
    print("After /init, review and commit the shared setup so developers can start with /feature.")


def _report_update(results) -> None:
    for f in results["updated"]:
        print(f"  ~ {f} (updated)")
    for f in results["created"]:
        print(f"  + {f} (new in this kit version)")
    for f in results["kept"]:
        print(f"  ! {f} (customized or unknown origin — kept; use --force or delete it and re-run)")
    print()
    print(
        f"Updated {len(results['updated'])}, added {len(results['created'])}, "
        f"kept {len(results['kept'])} customized; "
        f"{len(results['up_to_date'])} already up to date."
    )
    if results["updated"] or results["created"]:
        print()
        print("Review the diff, then open a fresh Copilot session to pick up the changes.")


if __name__ == "__main__":
    raise SystemExit(main())
