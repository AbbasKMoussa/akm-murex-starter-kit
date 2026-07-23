# Changelog

All notable AKMaestro changes are recorded here. This product has not yet been
released for team use, so `0.6.0` establishes the first release-candidate state
contract without migration support for earlier development formats.

## Unreleased

### Added

- Explicit `init --subproject` and `update --subproject` support for an
  independently operated product below a shared Git root.
- Portable installation-boundary metadata and workflow guidance that confines
  setup, features, generated state, and ordinary edits to the selected product.

### Fixed

- PowerShell restricted-path guard symlink/junction resolution on current .NET,
  preventing canonical paths from falling through to `allow`.
- Wheel-content CI verification for the top-level bundled state controller.

## 0.6.0 - 2026-07-18

### Added

- `/akmaestro-init` setup entry point and read-only `/status` orientation.
- Strict v3 setup evidence, action-check ledger, deterministic finalization, and
  exact merge-plan approval protocol with read-only finalization preview.
- Developer-local Graphifyy graphs and explicit modifiable/read-only sibling
  repository boundaries.
- Confirmed developer remediation bound to committed requirements, plus a
  documented uv bootstrap exception when the controller is unavailable.
- Installer and update dry runs, exact Git-root validation, collision checks,
  symlink-path rejection, atomic writes, and safe retired-file cleanup.
- Installed-wheel smoke tests, Ruff enforcement, and current immutable,
  least-privilege CI action pins on Linux/Windows.

### Changed

- Renamed the setup skill from `/init` to `/akmaestro-init` to avoid the VS Code
  built-in command collision.
- Hook assets install disabled and require explicit activation consent.
- Audit hooks retain metadata only; lint hooks execute structured commands
  without a shell; path guards canonicalize symlinks and junctions.
- State version is `3`; no migration is provided because previous contracts were
  not shipped.

### Removed

- Legacy `assets/skills/init` and committed `graphify-out` workflow guidance.
