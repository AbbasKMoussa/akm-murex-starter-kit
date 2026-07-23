#!/usr/bin/env bash
# restricted-path-guard.sh — preToolUse guard
#
# PAYLOAD SHAPE (captured from GA Copilot CLI 1.0.68, 2026-07-06): the event is
#   { toolName, toolArgs, cwd, ... } where toolArgs is a JSON-ENCODED STRING,
#   e.g. "{\"path\":\"/abs/path/.env\",...}", NOT a nested object, and `path`
#   is ABSOLUTE. We therefore parse toolArgs a second time (fromjson) and match
#   on the repo-relative path. Object-form toolArgs is still accepted (VS Code /
#   dry-runs). STATUS: both variants pass captured-payload tests; live post-fix
#   denial remains pending, including a Bash-surface (macOS/Linux CLI) run.
#
# Two rules, in order:
#   1. Workspace boundary — create/edit resolving OUTSIDE the repository root is
#      denied unless the target is under a path declared in
#      .agentic/hooks/editable-paths.txt (the compatibility file for modifiable
#      sibling repositories). Read-only sibling repositories must not be listed.
#   2. Restricted globs — create/edit matching a glob in
#      .agentic/hooks/restricted-paths.txt is denied. Applied to in-repo paths
#      AND inside modifiable siblings (so .env, *.pem etc. stay protected there).
#
# SAFETY: preToolUse command hooks are fail-closed (a non-zero exit denies all
# tool calls). This script always exits 0. It allows malformed/unknown payloads,
# but once an edit path is parsed it must be canonically resolvable and inside a
# declared writable root. Existing symlinks are resolved before boundary checks.

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

# Resolve symlinks in the existing portion of a path and preserve a potentially
# non-existent suffix for create operations. realpath is used when available;
# the fallback resolves physical parent directories and rejects a final symlink
# it cannot safely resolve.
canonicalize() {
  local full probe suffix='' name parent resolved
  full="$(normalize "$1")" || return 1
  probe="$full"
  while [ ! -e "$probe" ] && [ ! -L "$probe" ]; do
    [ "$probe" = "/" ] && break
    name="${probe##*/}"
    suffix="/$name$suffix"
    probe="${probe%/*}"; [ -n "$probe" ] || probe="/"
  done
  if command -v realpath >/dev/null 2>&1; then
    resolved="$(realpath "$probe" 2>/dev/null)" || return 1
  elif [ -L "$probe" ]; then
    return 1
  elif [ -d "$probe" ]; then
    resolved="$(cd -P -- "$probe" 2>/dev/null && pwd -P)" || return 1
  else
    parent="$(cd -P -- "${probe%/*}" 2>/dev/null && pwd -P)" || return 1
    resolved="$parent/${probe##*/}"
  fi
  printf '%s%s' "${resolved%/}" "$suffix"
}

# Deny if $1 (a path relative to its repository root) matches a restricted
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

case "$path" in *$'\n'*|*$'\r'*) deny "Edit path contains unsupported control characters.";; esac
root="$(canonicalize "$PWD")" || allow
abs="$(canonicalize "$path")" || deny "Edit to '$path' is blocked because its canonical path could not be resolved safely."

# Inside the repository: apply the restricted globs to the repo-relative path.
if [ "$abs" = "$root" ] || [[ "$abs" == "$root"/* ]]; then
  rel="${abs#"$root"/}"
  check_restricted_globs "$rel"
  allow
fi

# Outside the repository: allowed only under a declared modifiable sibling
# repository, and the restricted globs still apply inside it.
edits_file=".agentic/hooks/editable-paths.txt"
if [ -f "$edits_file" ]; then
  while IFS= read -r entry || [ -n "$entry" ]; do
    case "$entry" in ''|\#*) continue;; esac
    entry="${entry%$'\r'}"
    base="$(canonicalize "$entry")" || continue
    [ "$base" = "/" ] && continue   # never treat the filesystem root as modifiable
    if [ "$abs" = "$base" ] || [[ "$abs" == "$base"/* ]]; then
      rel="${abs#"$base"/}"
      check_restricted_globs "$rel"
      allow
    fi
  done < "$edits_file"
fi

deny "Edit to '$path' is blocked: it resolves outside this repository and is not under a declared modifiable sibling repository. Modifiable sibling paths belong in .agentic/hooks/editable-paths.txt; read-only sibling repositories must not be edited."
