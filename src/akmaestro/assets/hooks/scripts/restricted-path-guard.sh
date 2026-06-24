#!/usr/bin/env bash
# restricted-path-guard.sh — preToolUse guard
#
# STATUS: DRAFT, NOT YET FIRED AGAINST A LIVE COPILOT CLI.
# Verify the toolArgs path field name and the create/edit tool names on the GA
# CLI, then exercise both the allow and deny paths before trusting this.
#
# Denies create/edit on files matching a restricted glob in
# .agentic/hooks/restricted-paths.txt.
#
# SAFETY: preToolUse command hooks are fail-closed (a non-zero exit denies ALL
# tool calls). Therefore this script ALWAYS exits 0 and defaults to "allow" on
# ANY uncertainty. It only emits a deny on a positive match against a glob.

set -u

allow() { printf '{"permissionDecision":"allow"}\n'; exit 0; }
deny()  { printf '%s' "$1" | jq -Rs '{permissionDecision:"deny",permissionDecisionReason:.}'; exit 0; }

# jq is required for safe field parsing. If absent, allow (never error out).
command -v jq >/dev/null 2>&1 || allow

payload="$(cat 2>/dev/null)" || allow
[ -n "$payload" ] || allow

# Normalize both payload casings (toolArgs / tool_input) and check likely path
# field names defensively. Parse the specific field — never grep the whole blob.
path="$(printf '%s' "$payload" | jq -r '
  ((.toolArgs // .tool_input) // {}) as $a
  | ($a.path // $a.file_path // $a.filePath // $a.filename // $a.file // empty)
' 2>/dev/null)" || allow
[ -n "$path" ] && [ "$path" != "null" ] || allow

path="${path#./}"

globs_file=".agentic/hooks/restricted-paths.txt"
[ -f "$globs_file" ] || allow

while IFS= read -r glob || [ -n "$glob" ]; do
  case "$glob" in ''|\#*) continue;; esac
  glob="${glob%$'\r'}"   # tolerate CRLF line endings
  glob="${glob#./}"
  base="${glob%/**}"; base="${base%/}"

  # shell-pattern match on full path, basename match, and directory-prefix match
  if [[ "$path" == $glob ]] || [[ "${path##*/}" == $glob ]]; then
    deny "Edit to '$path' is blocked by the restricted-path guard (matched '$glob'). Get approval before changing this path."
  fi
  if [ -n "$base" ] && { [ "$path" = "$base" ] || [[ "$path" == "$base"/* ]]; }; then
    deny "Edit to '$path' is blocked by the restricted-path guard (inside restricted dir '$base'). Get approval before changing this path."
  fi
done < "$globs_file"

allow
