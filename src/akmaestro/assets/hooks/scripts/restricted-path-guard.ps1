# restricted-path-guard.ps1 — preToolUse guard (PowerShell variant)
#
# PAYLOAD SHAPE captured from GA Copilot CLI 1.0.68 on Windows (2026-07-06). The
# event is { toolName, toolArgs, cwd, ... } where toolArgs is a JSON-ENCODED STRING
# (e.g. "{\"path\":\"D:\\...\\.env\",...}"), not a nested object, and `path` is
# ABSOLUTE. We decode toolArgs a second time and match on the repo-relative
# path. Object-form toolArgs is still accepted (VS Code / dry-runs). Logic passes
# captured-payload tests; live post-fix denial is pending.
#
# Two rules, in order:
#   1. Workspace boundary — edits resolving OUTSIDE the repository root are
#      denied unless under a path declared in .agentic/hooks/editable-paths.txt.
#   2. Restricted globs — edits matching .agentic/hooks/restricted-paths.txt are
#      denied, in-repo and inside modifiable sibling repositories alike.
#
# SAFETY: always exit 0; default to allow on any parsing uncertainty; deny only
# on a positive match (a restricted glob, or a path positively outside the
# declared workspace).

$ErrorActionPreference = 'SilentlyContinue'

function Allow { '{"permissionDecision":"allow"}'; exit 0 }
function Deny([string]$reason) {
  (@{ permissionDecision = 'deny'; permissionDecisionReason = $reason } | ConvertTo-Json -Compress)
  exit 0
}

function Normalize([string]$p) {
  if (-not [System.IO.Path]::IsPathRooted($p)) {
    $p = Join-Path (Get-Location).Path $p
  }
  # GetFullPath resolves '.' and '..' textually; it does not require the path
  # to exist and does not resolve symlinks.
  return [System.IO.Path]::GetFullPath($p).TrimEnd([System.IO.Path]::DirectorySeparatorChar)
}

# Deny if $rel (forward-slash path relative to its repository root) matches
# a restricted glob: full-path match, basename match, directory-prefix match.
function Test-RestrictedGlobs([string]$rel) {
  $globsFile = '.agentic/hooks/restricted-paths.txt'
  if (-not (Test-Path $globsFile)) { return }
  $bn = Split-Path $rel -Leaf
  foreach ($glob in Get-Content $globsFile) {
    $g = $glob.Trim()
    if ($g -eq '' -or $g.StartsWith('#')) { continue }
    $g = $g -replace '^\./', ''
    $base = ($g -replace '/\*\*$', '') -replace '/$', ''

    if (($rel -like $g) -or ($bn -like $g)) {
      Deny "Edit to '$rel' is blocked by the restricted-path guard (matched '$g'). Get approval before changing this path."
    }
    if ($base -ne '' -and ($rel -eq $base -or $rel -like "$base/*")) {
      Deny "Edit to '$rel' is blocked by the restricted-path guard (inside restricted dir '$base'). Get approval before changing this path."
    }
  }
}

function To-Rel([string]$abs, [string]$root) {
  $rel = $abs.Substring($root.Length).TrimStart('\', '/')
  return $rel -replace '\\', '/'
}

try {
  $raw = [Console]::In.ReadToEnd()
  if ([string]::IsNullOrWhiteSpace($raw)) { Allow }

  $o = $raw | ConvertFrom-Json
  $a = if ($o.toolArgs) { $o.toolArgs } elseif ($o.tool_input) { $o.tool_input } else { $null }
  if ($null -eq $a) { Allow }
  # The GA CLI sends toolArgs as a JSON-encoded string — decode it. (Object-form
  # from other surfaces / dry-runs is used as-is.)
  if ($a -is [string]) {
    try { $a = $a | ConvertFrom-Json } catch { Allow }
  }

  $path = $a.path
  if (-not $path) { $path = $a.file_path }
  if (-not $path) { $path = $a.filePath }
  if (-not $path) { $path = $a.filename }
  if (-not $path) { $path = $a.file }
  if (-not $path) { Allow }
  $path = $path -replace '^\./', ''

  $root = Normalize '.'
  $abs = Normalize $path
  if ($null -eq $abs -or $abs -eq '') { Allow }

  # Inside the repository: restricted globs on the repo-relative path.
  if ($abs -eq $root -or $abs.StartsWith($root + [System.IO.Path]::DirectorySeparatorChar) -or $abs.StartsWith($root + '/')) {
    Test-RestrictedGlobs (To-Rel $abs $root)
    Allow
  }

  # Outside the repository: allowed only under a declared modifiable sibling
  # repository, with the restricted globs still applied inside it.
  $editsFile = '.agentic/hooks/editable-paths.txt'
  if (Test-Path $editsFile) {
    foreach ($entry in Get-Content $editsFile) {
      $e = $entry.Trim()
      if ($e -eq '' -or $e.StartsWith('#')) { continue }
      $base = Normalize $e
      if ($null -eq $base -or $base -eq '' -or $base -eq [System.IO.Path]::GetPathRoot($base)) { continue }
      if ($abs -eq $base -or $abs.StartsWith($base + [System.IO.Path]::DirectorySeparatorChar) -or $abs.StartsWith($base + '/')) {
        Test-RestrictedGlobs (To-Rel $abs $base)
        Allow
      }
    }
  }

  Deny "Edit to '$path' is blocked: it resolves outside this repository and is not under a declared modifiable sibling repository. Modifiable sibling paths belong in .agentic/hooks/editable-paths.txt; read-only sibling repositories must not be edited."
} catch {
  Allow
}
