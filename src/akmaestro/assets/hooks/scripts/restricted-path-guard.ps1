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
# SAFETY: always exit 0. Unknown payloads are allowed, but a parsed edit path is
# denied unless its canonical location is inside a declared writable root.
# Existing symlinks and junctions are resolved before boundary checks.

$ErrorActionPreference = 'SilentlyContinue'

function Allow { '{"permissionDecision":"allow"}'; exit 0 }
function Deny([string]$reason) {
  (@{ permissionDecision = 'deny'; permissionDecisionReason = $reason } | ConvertTo-Json -Compress)
  exit 0
}

function Canonicalize([string]$p) {
  $full = [System.IO.Path]::GetFullPath($(if ([System.IO.Path]::IsPathRooted($p)) {
    $p
  } else {
    Join-Path (Get-Location).Path $p
  }))
  $volume = [System.IO.Path]::GetPathRoot($full)
  $current = $volume.TrimEnd(
    [System.IO.Path]::DirectorySeparatorChar,
    [System.IO.Path]::AltDirectorySeparatorChar
  )
  if ([string]::IsNullOrEmpty($current)) { $current = $volume }
  $rest = $full.Substring($volume.Length)
  $segments = $rest.Split(
    @([System.IO.Path]::DirectorySeparatorChar, [System.IO.Path]::AltDirectorySeparatorChar),
    [System.StringSplitOptions]::RemoveEmptyEntries
  )
  foreach ($segment in $segments) {
    $candidate = Join-Path $current $segment
    $item = Get-Item -LiteralPath $candidate -Force -ErrorAction SilentlyContinue
    if ($item -and $item.LinkType) {
      $method = $item.GetType().GetMethod('ResolveLinkTarget', @([bool]))
      if (-not $method) { throw "Link resolution unavailable" }
      $target = $item.ResolveLinkTarget($true)
      if (-not $target) { throw "Link target unavailable" }
      $current = $target.FullName
    } else {
      $current = $candidate
    }
  }
  $trimmed = [System.IO.Path]::GetFullPath($current).TrimEnd('\', '/')
  if ([string]::IsNullOrEmpty($trimmed)) { return $volume }
  return $trimmed
}

function Is-Within([string]$path, [string]$root) {
  $comparison = if ($IsWindows -or $env:OS -eq 'Windows_NT') {
    [System.StringComparison]::OrdinalIgnoreCase
  } else {
    [System.StringComparison]::Ordinal
  }
  if ([string]::Equals($path, $root, $comparison)) { return $true }
  $prefix = $root.TrimEnd('\', '/') + [System.IO.Path]::DirectorySeparatorChar
  return $path.StartsWith($prefix, $comparison)
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
  if ($path.Contains("`n") -or $path.Contains("`r")) {
    Deny "Edit path contains unsupported control characters."
  }
  $path = $path -replace '^\./', ''

  $root = Canonicalize '.'
  try { $abs = Canonicalize $path } catch {
    Deny "Edit to '$path' is blocked because its canonical path could not be resolved safely."
  }

  # Inside the repository: restricted globs on the repo-relative path.
  if (Is-Within $abs $root) {
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
      try { $base = Canonicalize $e } catch { continue }
      if ($null -eq $base -or $base -eq '' -or $base -eq [System.IO.Path]::GetPathRoot($base)) { continue }
      if (Is-Within $abs $base) {
        Test-RestrictedGlobs (To-Rel $abs $base)
        Allow
      }
    }
  }

  Deny "Edit to '$path' is blocked: it resolves outside this repository and is not under a declared modifiable sibling repository. Modifiable sibling paths belong in .agentic/hooks/editable-paths.txt; read-only sibling repositories must not be edited."
} catch {
  Allow
}
