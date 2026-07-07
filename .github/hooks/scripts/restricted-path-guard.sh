#!/usr/bin/env bash
# restricted-path-guard.sh — preToolUse guard
#
# PAYLOAD SHAPE (captured from GA Copilot CLI 1.0.68, 2026-07-06): the event is
#   { toolName, toolArgs, cwd, ... } where toolArgs is a JSON-ENCODED STRING,
#   e.g. "{\"path\":\"/abs/path/.env\",...}", NOT a nested object, and `path`
#   is ABSOLUTE. We therefore parse toolArgs a second time (fromjson) and match
#   on the repo-relative path. Object-form toolArgs is still accepted (VS Code /
#   dry-runs). STATUS: the PowerShell twin is live-verified on the Windows CLI;
#   this bash variant is fixed by analogy and confirmed against the captured
#   payload + CI, pending a live bash-surface (macOS/Linux CLI) re-confirmation.
#
# Two rules, in order:
#   1. Workspace boundary — create/edit resolving OUTSIDE the repository root is
#      denied unless the target is under a path declared in
#      .agentic/hooks/editable-paths.txt (owned sibling repos, "editable
#      satellites"). Read-only reference repos must not be listed there.
#   2. Restricted globs — create/edit matching a glob in
#      .agentic/hooks/restricted-paths.txt is denied. Applied to in-repo paths
#      AND inside editable satellites (so .env, *.pem etc. stay protected there).
#
# SAFETY: preToolUse command hooks are fail-closed (a non-zero exit denies ALL
# tool calls). Therefore this script ALWAYS exits 0 and defaults to "allow" on
# ANY parsing uncertainty. It denies only on a positive match: a restricted glob,
# or a path that positively resolves outside the declared workspace.

set -u
set -f  # no pathname expansion; [[ == pattern ]] matching is unaffected

allow() { printf '{"permissionDecision":"allow"}\n'; exit 0; }
deny()  { printf '%s' "$1" | jq -Rsc '{permissionDecision:"deny",permissionDecisionReason:.}'; exit 0; }

# jq is required for safe field parsing. If absent, allow (never error out).
command -v jq >/dev/null 2>&1 || allow

payload="$(cat 2>/dev/null)" || allow
[ -n "$payload" ] || allow

# Normalize both payload casings (toolArgs / tool_input), decode toolArgs when it
# is a JSON-encoded string (the real GA CLI shape), and check likely path field
# names defensively. Parse the specific field — never grep the whole blob.
path="$(printf '%s' "$payload" | jq -r '
  (.toolArgs // .tool_input) as $a
  | (if ($a | type) == "string" then ($a | fromjson? // {}) else ($a // {}) end) as $args
  | ($args.path // $args.file_path // $args.filePath // $args.filename // $args.file // empty)
' 2>/dev/null)" || allow
[ -n "$path" ] && [ "$path" != "null" ] || allow

path="${path#./}"

# Textually normalize to an absolute path, resolving '.' and '..' (bash 3.2
# compatible; no realpath dependency). Symlinks are not resolved — acceptable,
# since a wrong denial is recoverable and this guard must never hard-fail.
normalize() {
  local p="$1" out='' seg
  case "$p" in /*) ;; *) p="$PWD/$p" ;; esac
  local IFS='/'
  for seg in $p; do
    case "$seg" in
      ''|'.') ;;
      '..') out="${out%/*}" ;;
      *) out="$out/$seg" ;;
    esac
  done
  printf '%s' "${out:-/}"
}

# Deny if $1 (a path relative to its repo/satellite root) matches a restricted
# glob: shell-pattern on the full relative path, on the basename, and as a
# directory-prefix (a trailing /** means "anything under this directory").
check_restricted_globs() {
  local rel="$1" glob base
  local globs_file=".agentic/hooks/restricted-paths.txt"
  [ -f "$globs_file" ] || return 0
  while IFS= read -r glob || [ -n "$glob" ]; do
    case "$glob" in ''|\#*) continue;; esac
    glob="${glob%$'\r'}"   # tolerate CRLF line endings
    glob="${glob#./}"
    base="${glob%/**}"; base="${base%/}"
    if [[ "$rel" == $glob ]] || [[ "${rel##*/}" == $glob ]]; then
      deny "Edit to '$rel' is blocked by the restricted-path guard (matched '$glob'). Get approval before changing this path."
    fi
    if [ -n "$base" ] && { [ "$rel" = "$base" ] || [[ "$rel" == "$base"/* ]]; }; then
      deny "Edit to '$rel' is blocked by the restricted-path guard (inside restricted dir '$base'). Get approval before changing this path."
    fi
  done < "$globs_file"
}

root="$(normalize "$PWD")" || allow
abs="$(normalize "$path")" || allow

# Inside the repository: apply the restricted globs to the repo-relative path.
if [ "$abs" = "$root" ] || [[ "$abs" == "$root"/* ]]; then
  rel="${abs#"$root"/}"
  check_restricted_globs "$rel"
  allow
fi

# Outside the repository: allowed only under a declared editable dependency,
# and the restricted globs still apply inside it.
edits_file=".agentic/hooks/editable-paths.txt"
if [ -f "$edits_file" ]; then
  while IFS= read -r entry || [ -n "$entry" ]; do
    case "$entry" in ''|\#*) continue;; esac
    entry="${entry%$'\r'}"
    base="$(normalize "$entry")"
    [ "$base" = "/" ] && continue   # never treat the filesystem root as editable
    if [ "$abs" = "$base" ] || [[ "$abs" == "$base"/* ]]; then
      rel="${abs#"$base"/}"
      check_restricted_globs "$rel"
      allow
    fi
  done < "$edits_file"
fi

deny "Edit to '$path' is blocked: it resolves outside this repository and is not under a declared editable dependency. Owned sibling repos belong in .agentic/hooks/editable-paths.txt; read-only reference repos must not be edited."
