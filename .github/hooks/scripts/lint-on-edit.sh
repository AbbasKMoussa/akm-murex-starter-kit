#!/usr/bin/env bash
# lint-on-edit.sh — postToolUse hook
#
# STATUS: the PowerShell twin fired live on the GA CLI (Windows); this bash
# variant is fixed by analogy (toolArgs decoded as a JSON string) and unverified
# on a live bash surface.
# Context-injection field VERIFIED: postToolUse output is
#   { modifiedResult?: {...}, additionalContext?: string }
# so {"additionalContext": "..."} below is correct. NOTE: copilot-cli#2980 — the
# CLI does not always forward additionalContext into the context window (and not
# at all for MCP tool calls), so findings may not always reach the agent.
#
# Runs a structured linter command directly (never through a shell) on the
# changed file and injects bounded findings as context. postToolUse cannot block,
# only inform. No-op when no linter is configured for the file's extension.
#
# SAFETY: always exit 0; emit nothing (no context) on any uncertainty.

set -u

noop() { exit 0; }

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

# Resolve symlinks in the existing portion of a path, then append any
# not-yet-created suffix. This also protects create events below symlinked dirs.
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

is_allowed_path() {
  local abs="$1" root entry base
  root="$(canonicalize "$PWD")" || return 1
  if [ "$abs" = "$root" ] || [[ "$abs" == "$root"/* ]]; then
    return 0
  fi
  [ -f ".agentic/hooks/editable-paths.txt" ] || return 1
  while IFS= read -r entry || [ -n "$entry" ]; do
    case "$entry" in ''|\#*) continue;; esac
    entry="${entry%$'\r'}"
    base="$(canonicalize "$entry")" || continue
    [ "$base" = "/" ] && continue
    if [ "$abs" = "$base" ] || [[ "$abs" == "$base"/* ]]; then
      return 0
    fi
  done < ".agentic/hooks/editable-paths.txt"
  return 1
}

command -v jq >/dev/null 2>&1 || noop

payload="$(cat 2>/dev/null)" || noop
[ -n "$payload" ] || noop

# toolArgs is a JSON-encoded string on the GA CLI; decode it before reading path.
path="$(printf '%s' "$payload" | jq -r '
  (.toolArgs // .tool_input) as $a
  | (if ($a | type) == "string" then ($a | fromjson? // {}) else ($a // {}) end) as $args
  | ($args.path // $args.file_path // $args.filePath // $args.filename // $args.file // empty)
' 2>/dev/null)" || noop
[ -n "$path" ] && [ "$path" != "null" ] || noop
case "$path" in *$'\n'*|*$'\r'*) noop;; esac
abs="$(canonicalize "$path")" || noop
is_allowed_path "$abs" || noop
[ -f "$abs" ] || noop

map=".agentic/hooks/lint-commands.json"
[ -f "$map" ] || noop

ext="${abs##*.}"
entry="$(jq -c --arg e "$ext" '
  .[$e]
  | select(type == "object")
  | select(.command | type == "string")
  | select(.args | type == "array" and all(.[]; type == "string"))
  | select(any(.args[]; contains("{file}")))
' "$map" 2>/dev/null)" || noop
[ -n "$entry" ] && [ "$entry" != "null" ] || noop

executable="$(printf '%s' "$entry" | jq -r '.command' 2>/dev/null)" || noop
case "$executable" in
  ''|*/*|*\\*|sh|bash|dash|zsh|fish|cmd|cmd.exe|powershell|powershell.exe|pwsh|pwsh.exe) noop;;
  *[!A-Za-z0-9._+-]*) noop;;
esac
command -v "$executable" >/dev/null 2>&1 || noop

args=()
while IFS= read -r encoded; do
  arg="$(printf '%s' "$encoded" | jq -r '.' 2>/dev/null)" || noop
  args+=("${arg//\{file\}/$abs}")
done < <(printf '%s' "$entry" | jq -c '.args[]' 2>/dev/null)

out="$("$executable" "${args[@]}" 2>&1)"; status=$?
[ "$status" -eq 0 ] && noop   # clean: nothing to inject
out="${out:0:20000}"

printf '%s' "Lint findings for $abs (exit $status):
$out" | jq -Rsc '{additionalContext: .}'
exit 0
