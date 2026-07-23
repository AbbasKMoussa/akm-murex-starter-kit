# audit-log.ps1 — observational hook (PowerShell variant)
#
# Records metadata only: event kind, tool name, and timestamp. Prompt text,
# tool arguments, tool results, and session identifiers are never persisted.
# Never blocks; always exits 0.

$ErrorActionPreference = 'SilentlyContinue'

try {
  $raw = [Console]::In.ReadToEnd()

  $dir = '.agentic/audit'
  New-Item -ItemType Directory -Force -Path $dir | Out-Null
  Get-ChildItem -LiteralPath $dir -Filter '*.jsonl' -File |
    Where-Object { $_.LastWriteTimeUtc -lt (Get-Date).ToUniversalTime().AddDays(-14) } |
    Remove-Item -Force
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
    if ($event -notin @('preToolUse', 'postToolUse', 'userPromptSubmitted', 'sessionEnd')) {
      $event = 'unknown'
    }
    $tool = if ($o.toolName) { [string]$o.toolName } elseif ($o.tool_name) { [string]$o.tool_name } else { $null }
    if ($tool -and $tool -notmatch '^[A-Za-z0-9._:-]{1,128}$') { $tool = $null }
    $rec = [ordered]@{
      received_at = $ts
      event   = $event
      tool    = $tool
    }
    $line = $rec | ConvertTo-Json -Compress
  } catch {
    $line = ([ordered]@{ received_at = $ts; event = 'unknown'; parse_error = $true } | ConvertTo-Json -Compress)
  }

  Add-Content -Path $file -Value $line
  if (Get-Command chmod -ErrorAction SilentlyContinue) {
    & chmod 700 -- $dir 2>$null
    & chmod 600 -- $file 2>$null
  }
} catch { }

exit 0
