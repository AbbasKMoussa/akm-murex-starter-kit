# audit-log.ps1 — observational hook (PowerShell variant)
#
# STATUS: DRAFT. Appends one JSON line per event. Never blocks; always exit 0.

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
    $rec = [ordered]@{
      received_at = $ts
      event   = $(if ($o.hook_event_name) { $o.hook_event_name } else { $o.hookEventName })
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
