"""Command-line entry point: ``akmaestro init`` / ``akmaestro update``."""

from __future__ import annotations

import argparse
import sys
from typing import List, Optional

from . import __version__, installer


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="akmaestro",
        description="AKMaestro — set up a repo for agentic coding with GitHub Copilot.",
    )
    parser.add_argument(
        "--version", action="version", version=f"%(prog)s {__version__}"
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_init = sub.add_parser(
        "init", help="Install the starter kit into the current repository"
    )
    p_init.add_argument(
        "--path",
        default=".",
        help="Target Git root, or product root with --subproject (default: cwd)",
    )
    p_init.add_argument(
        "--subproject",
        action="store_true",
        help="Explicitly treat a directory below the Git root as an independent product",
    )
    p_init.add_argument("--no-hooks", action="store_true", help="Do not install hooks")
    p_init.add_argument(
        "--dry-run", action="store_true", help="Preview without writing files"
    )

    p_update = sub.add_parser(
        "update",
        help="Refresh kit-owned files to this kit version (customized files are kept)",
    )
    p_update.add_argument(
        "--path",
        default=".",
        help="Target Git root, or product root with --subproject (default: cwd)",
    )
    p_update.add_argument(
        "--subproject",
        action="store_true",
        help="Update an installation rooted in an independent product below the Git root",
    )
    p_update.add_argument(
        "--force",
        action="store_true",
        help="Also overwrite customized files and files the kit cannot attribute to itself",
    )
    p_update.add_argument(
        "--dry-run", action="store_true", help="Preview without writing files"
    )

    args = parser.parse_args(argv)

    try:
        if args.command == "init":
            _report_init(
                installer.init(
                    target=args.path,
                    with_hooks=not args.no_hooks,
                    dry_run=args.dry_run,
                    subproject=args.subproject,
                ),
                dry_run=args.dry_run,
                subproject=args.subproject,
            )
        elif args.command == "update":
            _report_update(
                installer.update(
                    target=args.path,
                    force=args.force,
                    dry_run=args.dry_run,
                    subproject=args.subproject,
                ),
                dry_run=args.dry_run,
                subproject=args.subproject,
            )
    except installer.InstallerError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    except OSError as exc:
        print(f"error: filesystem operation failed: {exc}", file=sys.stderr)
        return 2
    return 0


def _report_init(results, dry_run=False, subproject=False) -> None:
    for f in results["created"]:
        print(f"  + {f}")
    for f in results["skipped"]:
        print(f"  = {f} (exists, left untouched)")
    print()
    verb = "Would install" if dry_run else "Installed"
    print(
        f"{verb} {len(results['created'])} file(s); "
        f"left {len(results['skipped'])} existing file(s) untouched."
    )
    if subproject:
        print(
            "Scope: explicit subproject root (the enclosing Git root was not modified)."
        )
    if dry_run:
        return
    print()
    print(
        "Next: the team lead opens Copilot (VS Code or CLI) at the "
        f"{'subproject' if subproject else 'repo'} root and runs:"
    )
    print("    /akmaestro-init")
    print('or say: "let\'s run the initialization flow".')
    print(
        "After /akmaestro-init, review and commit the shared setup so developers can start with /feature."
    )


def _report_update(results, dry_run=False, subproject=False) -> None:
    for f in results["updated"]:
        print(f"  ~ {f} (updated)")
    for f in results["created"]:
        print(f"  + {f} (new in this kit version)")
    for f in results["kept"]:
        print(
            f"  ! {f} (customized or unknown origin — kept; use --force or delete it and re-run)"
        )
    for f in results["removed"]:
        print(f"  - {f} (retired kit-owned file)")
    print()
    print(
        f"{'Would update' if dry_run else 'Updated'} {len(results['updated'])}, added {len(results['created'])}, "
        f"removed {len(results['removed'])}, "
        f"kept {len(results['kept'])} customized; "
        f"{len(results['up_to_date'])} already up to date."
    )
    if subproject:
        print("Scope: explicit subproject root.")
    if not dry_run and (results["updated"] or results["created"] or results["removed"]):
        print()
        print(
            "Review the diff, then open a fresh Copilot session to pick up the changes."
        )


if __name__ == "__main__":
    raise SystemExit(main())
