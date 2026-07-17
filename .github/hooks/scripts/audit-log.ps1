# audit-log.ps1 — observational hook (PowerShell variant)
#
# STATUS: live audit output and structural event inference were verified on
# Copilot CLI 1.0.68 for Windows. Never blocks; always exits 0.

$ErrorActionPreference = 'SilentlyContinue'

try {
  $raw = [Console]::In.ReadToEnd()

  $dir = '.agentic/audit'
  New-Item -ItemType Directory -Force -Path $dir | Out-Null
  $file = Join-Path $dir ((Get-Date -Format 'yyyy-MM-dd') + '.jsonl')
  $ts = (Get-Date).ToUniversalTime().ToString('yyyy-MM-ddTHH:mm:ssZ')

  $line = $null
  try {
    $o = $raw | ConvertFrom-Json
    # The GA CLI sends no explicit event-name field — infer it structurally:
    # a tool call has toolName (+ toolResult once run); a prompt event has
    # `prompt`; a session-end has `reason`.
    $event = if ($o.hook_event_name) { $o.hook_event_name }
      elseif ($o.hookEventName) { $o.hookEventName }
      elseif ($o.PSObject.Properties.Name -contains 'toolName') {
        if ($o.PSObject.Properties.Name -contains 'toolResult') { 'postToolUse' } else { 'preToolUse' }
      }
      elseif ($o.PSObject.Properties.Name -contains 'prompt') { 'userPromptSubmitted' }
      elseif ($o.PSObject.Properties.Name -contains 'reason') { 'sessionEnd' }
      else { 'unknown' }
    $rec = [ordered]@{
      received_at = $ts
      event   = $event
      session = $(if ($o.sessionId) { $o.sessionId } else { $o.session_id })
      tool    = $(if ($o.toolName) { $o.toolName } else { $o.tool_name })
      raw     = $o
    }
    $line = $rec | ConvertTo-Json -Compress -Depth 20
  } catch {
    $line = (@{ received_at = $ts; raw_unparsed = $true } | ConvertTo-Json -Compress)
  }

  Add-Content -Path $file -Value $line
} catch { }

exit 0
