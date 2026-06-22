# dangerous-command-guard.ps1 — preToolUse guard (PowerShell variant)
#
# STATUS: DRAFT, NOT YET FIRED AGAINST A LIVE COPILOT CLI. See the .sh variant.
#
# SAFETY: always exit 0; default allow; deny only on a positive regex match
# against .agentic/hooks/dangerous-commands.txt. Patterns are written to be
# compatible with both grep -E and .NET regex (use \s and \b, not POSIX classes).

$ErrorActionPreference = 'SilentlyContinue'

function Allow { '{"permissionDecision":"allow"}'; exit 0 }
function Deny([string]$reason) {
  (@{ permissionDecision = 'deny'; permissionDecisionReason = $reason } | ConvertTo-Json -Compress)
  exit 0
}

try {
  $raw = [Console]::In.ReadToEnd()
  if ([string]::IsNullOrWhiteSpace($raw)) { Allow }

  $o = $raw | ConvertFrom-Json
  $a = if ($o.toolArgs) { $o.toolArgs } elseif ($o.tool_input) { $o.tool_input } else { $null }
  if ($null -eq $a) { Allow }

  $cmd = $a.command
  if (-not $cmd) { Allow }

  $patternsFile = '.agentic/hooks/dangerous-commands.txt'
  if (-not (Test-Path $patternsFile)) { Allow }

  foreach ($pat in Get-Content $patternsFile) {
    $p = $pat.Trim()
    if ($p -eq '' -or $p.StartsWith('#')) { continue }
    if ($cmd -match $p) {
      Deny "Command blocked by the dangerous-command guard (matched /$p/). If this is intentional, run it yourself or get approval."
    }
  }
  Allow
} catch {
  Allow
}
