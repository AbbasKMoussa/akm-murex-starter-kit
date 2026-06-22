# restricted-path-guard.ps1 — preToolUse guard (PowerShell variant)
#
# STATUS: DRAFT, NOT YET FIRED AGAINST A LIVE COPILOT CLI. See the .sh variant.
#
# SAFETY: always exit 0; default to allow on any uncertainty; deny only on a
# positive match against a glob in .agentic/hooks/restricted-paths.txt.

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

  $path = $a.path
  if (-not $path) { $path = $a.file_path }
  if (-not $path) { $path = $a.filePath }
  if (-not $path) { $path = $a.filename }
  if (-not $path) { $path = $a.file }
  if (-not $path) { Allow }
  $path = $path -replace '^\./', ''

  $globsFile = '.agentic/hooks/restricted-paths.txt'
  if (-not (Test-Path $globsFile)) { Allow }

  foreach ($glob in Get-Content $globsFile) {
    $g = $glob.Trim()
    if ($g -eq '' -or $g.StartsWith('#')) { continue }
    $g = $g -replace '^\./', ''
    $base = ($g -replace '/\*\*$', '') -replace '/$', ''
    $bn = Split-Path $path -Leaf

    if (($path -like $g) -or ($bn -like $g)) {
      Deny "Edit to '$path' is blocked by the restricted-path guard (matched '$g'). Get approval before changing this path."
    }
    if ($base -ne '' -and ($path -eq $base -or $path -like "$base/*")) {
      Deny "Edit to '$path' is blocked by the restricted-path guard (inside restricted dir '$base'). Get approval before changing this path."
    }
  }
  Allow
} catch {
  Allow
}
