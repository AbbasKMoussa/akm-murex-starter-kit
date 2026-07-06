#!/usr/bin/env bash
# audit-log.sh — observational hook (userPromptSubmitted / postToolUse / sessionEnd)
#
# STATUS: DRAFT. Appends one JSON line per event to a local, gitignored trail.
#
# Never blocks and never influences the agent: emits no decision and ALWAYS
# exits 0, even on error.

set -u

dir=".agentic/audit"
mkdir -p "$dir" 2>/dev/null || exit 0
file="$dir/$(date +%Y-%m-%d 2>/dev/null).jsonl"
ts="$(date -u +%Y-%m-%dT%H:%M:%SZ 2>/dev/null)"

payload="$(cat 2>/dev/null)" || exit 0

if command -v jq >/dev/null 2>&1; then
  printf '%s' "$payload" | jq -c --arg ts "$ts" '
    {
      received_at: $ts,
      event:   (.hook_event_name // .hookEventName // null),
      session: (.sessionId // .session_id // null),
      tool:    (.toolName // .tool_name // null),
      raw: .
    }' >> "$file" 2>/dev/null \
  || printf '{"received_at":"%s","raw_unparsed":true}\n' "$ts" >> "$file" 2>/dev/null
else
  # No jq: escape the payload into a JSON string by hand (strip control chars,
  # escape backslash and quote) so every trail line is still valid JSON.
  escaped="$(printf '%s' "$payload" | tr -d '\000-\037' | sed -e 's/\\/\\\\/g' -e 's/"/\\"/g')"
  printf '{"received_at":"%s","raw_escaped":"%s"}\n' "$ts" "$escaped" >> "$file" 2>/dev/null
fi

exit 0
