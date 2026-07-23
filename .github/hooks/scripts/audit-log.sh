#!/usr/bin/env bash
# audit-log.sh — observational hook (userPromptSubmitted / postToolUse / sessionEnd)
#
# STATUS: event inference is regression-tested against captured CLI payloads;
# live Bash-surface verification remains pending.
#
# Records metadata only: event kind, tool name, and timestamp. Prompt text,
# tool arguments, tool results, and session identifiers are never persisted.
# Never blocks or influences the agent and always exits 0, even on error.

set -u
umask 077

dir=".agentic/audit"
mkdir -p "$dir" 2>/dev/null || exit 0
chmod 700 "$dir" 2>/dev/null || true
# Daily files are sufficient for local diagnostics. Keep at most 14 days.
find "$dir" -type f -name '*.jsonl' -mtime +14 -exec rm -f -- {} + 2>/dev/null || true
file="$dir/$(date +%Y-%m-%d 2>/dev/null).jsonl"
ts="$(date -u +%Y-%m-%dT%H:%M:%SZ 2>/dev/null)"

payload="$(cat 2>/dev/null)" || exit 0

if command -v jq >/dev/null 2>&1; then
  # The GA CLI sends no explicit event-name field, so infer the event kind
  # structurally. Only bounded, non-content metadata is retained.
  printf '%s' "$payload" | jq -c --arg ts "$ts" '
    def safe_event:
      if . == "preToolUse" or . == "postToolUse" or
         . == "userPromptSubmitted" or . == "sessionEnd"
      then . else "unknown" end;
    def safe_tool:
      if type == "string" and test("^[A-Za-z0-9._:-]{1,128}$") then . else null end;
    {
      received_at: $ts,
      event: (
        .hook_event_name // .hookEventName //
        (if      has("toolName") then (if has("toolResult") then "postToolUse" else "preToolUse" end)
         elif    has("prompt")   then "userPromptSubmitted"
         elif    has("reason")   then "sessionEnd"
         else    "unknown" end)
        | safe_event
      ),
      tool: ((.toolName // .tool_name // null) | safe_tool)
    }' >> "$file" 2>/dev/null \
  || printf '{"received_at":"%s","event":"unknown","parse_error":true}\n' "$ts" >> "$file" 2>/dev/null
else
  printf '{"received_at":"%s","event":"unknown","parser_unavailable":true}\n' "$ts" >> "$file" 2>/dev/null
fi

chmod 600 "$file" 2>/dev/null || true

exit 0
