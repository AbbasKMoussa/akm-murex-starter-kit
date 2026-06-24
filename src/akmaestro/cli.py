"""Command-line entry point: ``akmaestro init``."""

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

    args = parser.parse_args(argv)

    if args.command == "init":
        results = installer.init(target=args.path, with_hooks=not args.no_hooks)
        _report(results)
    return 0


def _report(results) -> None:
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
    print("Next: open Copilot (VS Code or CLI) at the repo root and run:")
    print("    /init")
    print('or say: "let\'s run the initialization flow".')


if __name__ == "__main__":
    raise SystemExit(main())
