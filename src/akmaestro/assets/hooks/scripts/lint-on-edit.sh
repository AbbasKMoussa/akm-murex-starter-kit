#!/usr/bin/env bash
# lint-on-edit.sh — postToolUse hook
#
# STATUS: DRAFT, NOT YET FIRED AGAINST A LIVE COPILOT CLI.
# Context-injection field VERIFIED: postToolUse output is
#   { modifiedResult?: {...}, additionalContext?: string }
# so {"additionalContext": "..."} below is correct. NOTE: copilot-cli#2980 — the
# CLI does not always forward additionalContext into the context window (and not
# at all for MCP tool calls), so findings may not always reach the agent.
#
# Runs the configured linter on the changed file and injects findings as context
# so the agent can fix them. postToolUse cannot block, only inform. No-op when no
# lint command is configured for the file's extension.
#
# SAFETY: always exit 0; emit nothing (no context) on any uncertainty.

set -u

noop() { exit 0; }

command -v jq >/dev/null 2>&1 || noop

payload="$(cat 2>/dev/null)" || noop
[ -n "$payload" ] || noop

path="$(printf '%s' "$payload" | jq -r '
  ((.toolArgs // .tool_input) // {}) as $a
  | ($a.path // $a.file_path // $a.filePath // $a.filename // $a.file // empty)
' 2>/dev/null)" || noop
[ -n "$path" ] && [ "$path" != "null" ] || noop
[ -f "$path" ] || noop

map=".agentic/hooks/lint-commands.json"
[ -f "$map" ] || noop

ext="${path##*.}"
template="$(jq -r --arg e "$ext" '.[$e] // empty' "$map" 2>/dev/null)" || noop
[ -n "$template" ] && [ "$template" != "null" ] || noop

# Substitute the {file} placeholder with the shell-quoted path.
qpath="$(printf '%q' "$path")"
cmd="${template//\{file\}/$qpath}"

out="$(eval "$cmd" 2>&1)"; status=$?
[ "$status" -eq 0 ] && noop   # clean: nothing to inject

printf '%s' "Lint findings for $path (exit $status):
$out" | jq -Rs '{additionalContext: .}'
exit 0
