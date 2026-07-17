#!/usr/bin/env bash
# dangerous-command-guard.sh — preToolUse guard
#
# PAYLOAD SHAPE (captured from GA Copilot CLI 1.0.68, 2026-07-06): toolArgs is a
# JSON-ENCODED STRING (e.g. "{\"command\":\"...\"}"), not a nested object, so we
# parse it a second time (fromjson) before reading `command`. Object-form is
# still accepted. STATUS: both variants pass captured-payload tests; live
# post-fix denial remains pending, including a Bash-surface run.
#
# Denies shell commands matching a pattern in
# .agentic/hooks/dangerous-commands.txt.
#
# SAFETY: fail-closed event. ALWAYS exit 0; default allow; deny only on a
# positive match. Reads ONLY the command field — never greps the whole payload —
# so a file write whose content mentions a dangerous command is not blocked.

set -u

allow() { printf '{"permissionDecision":"allow"}\n'; exit 0; }
deny()  { printf '%s' "$1" | jq -Rsc '{permissionDecision:"deny",permissionDecisionReason:.}'; exit 0; }

command -v jq >/dev/null 2>&1 || allow

payload="$(cat 2>/dev/null)" || allow
[ -n "$payload" ] || allow

cmd="$(printf '%s' "$payload" | jq -r '
  (.toolArgs // .tool_input) as $a
  | (if ($a | type) == "string" then ($a | fromjson? // {}) else ($a // {}) end) as $args
  | ($args.command // empty)
' 2>/dev/null)" || allow
[ -n "$cmd" ] && [ "$cmd" != "null" ] || allow

patterns_file=".agentic/hooks/dangerous-commands.txt"
[ -f "$patterns_file" ] || allow

while IFS= read -r pat || [ -n "$pat" ]; do
  case "$pat" in ''|\#*) continue;; esac
  pat="${pat%$'\r'}"
  if printf '%s' "$cmd" | grep -Eq -- "$pat" 2>/dev/null; then
    deny "Command blocked by the dangerous-command guard (matched /$pat/). If this is intentional, run it yourself or get approval."
  fi
done < "$patterns_file"

allow
