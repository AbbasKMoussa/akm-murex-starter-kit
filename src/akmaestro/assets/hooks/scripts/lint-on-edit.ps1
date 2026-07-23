# lint-on-edit.ps1 — postToolUse hook (PowerShell variant)
#
# STATUS: fired live on the GA Copilot CLI (Windows, 2026-07-06); the no-lint
# no-op path was confirmed. toolArgs is a JSON-encoded string there (decoded
# below); the actual lint-injection path is unverified live (no linter was
# configured for the edited extension during the run).
# Context-injection field VERIFIED: {"additionalContext": "..."} is correct.
# NOTE: copilot-cli#2980 — additionalContext is not always forwarded into the
# context window (and not for MCP tool calls).
# Commands use a structured command/argument configuration and are invoked
# directly, never through cmd.exe, PowerShell parsing, or another shell.
# SAFETY: always exit 0; emit nothing on any uncertainty.

$ErrorActionPreference = 'SilentlyContinue'

function NoOp { exit 0 }

function Get-CanonicalPath([string]$path) {
  $full = [System.IO.Path]::GetFullPath($(if ([System.IO.Path]::IsPathRooted($path)) { $path } else { Join-Path (Get-Location).Path $path }))
  $root = [System.IO.Path]::GetPathRoot($full)
  $current = $root.TrimEnd([System.IO.Path]::DirectorySeparatorChar, [System.IO.Path]::AltDirectorySeparatorChar)
  if ([string]::IsNullOrEmpty($current)) { $current = $root }
  $rest = $full.Substring($root.Length)
  $segments = $rest.Split(@([System.IO.Path]::DirectorySeparatorChar, [System.IO.Path]::AltDirectorySeparatorChar), [System.StringSplitOptions]::RemoveEmptyEntries)
  foreach ($segment in $segments) {
    $candidate = Join-Path $current $segment
    $item = Get-Item -LiteralPath $candidate -Force -ErrorAction SilentlyContinue
    if ($item -and $item.LinkType) {
      $method = $item.GetType().GetMethod('ResolveLinkTarget', @([bool]))
      if (-not $method) { return $null }
      $target = $item.ResolveLinkTarget($true)
      if (-not $target) { return $null }
      $current = $target.FullName
    } else {
      $current = $candidate
    }
  }
  return [System.IO.Path]::GetFullPath($current).TrimEnd([System.IO.Path]::DirectorySeparatorChar, [System.IO.Path]::AltDirectorySeparatorChar)
}

function Test-IsWithin([string]$path, [string]$root) {
  $comparison = if ([System.Runtime.InteropServices.RuntimeInformation]::IsOSPlatform([System.Runtime.InteropServices.OSPlatform]::Windows)) {
    [System.StringComparison]::OrdinalIgnoreCase
  } else {
    [System.StringComparison]::Ordinal
  }
  $base = $root.TrimEnd([System.IO.Path]::DirectorySeparatorChar, [System.IO.Path]::AltDirectorySeparatorChar)
  return $path.Equals($base, $comparison) -or
    $path.StartsWith($base + [System.IO.Path]::DirectorySeparatorChar, $comparison) -or
    $path.StartsWith($base + [System.IO.Path]::AltDirectorySeparatorChar, $comparison)
}

function Test-IsAllowedPath([string]$path) {
  $root = Get-CanonicalPath '.'
  if (-not $root) { return $false }
  if (Test-IsWithin $path $root) { return $true }
  $editsFile = '.agentic/hooks/editable-paths.txt'
  if (-not (Test-Path -LiteralPath $editsFile)) { return $false }
  foreach ($line in Get-Content -LiteralPath $editsFile) {
    $entry = $line.Trim()
    if ($entry -eq '' -or $entry.StartsWith('#')) { continue }
    $base = Get-CanonicalPath $entry
    if (-not $base -or $base -eq [System.IO.Path]::GetPathRoot($base)) { continue }
    if (Test-IsWithin $path $base) { return $true }
  }
  return $false
}

try {
  $raw = [Console]::In.ReadToEnd()
  if ([string]::IsNullOrWhiteSpace($raw)) { NoOp }

  $o = $raw | ConvertFrom-Json
  $a = if ($o.toolArgs) { $o.toolArgs } elseif ($o.tool_input) { $o.tool_input } else { $null }
  if ($null -eq $a) { NoOp }
  # The GA CLI sends toolArgs as a JSON-encoded string — decode it.
  if ($a -is [string]) {
    try { $a = $a | ConvertFrom-Json } catch { NoOp }
  }

  $path = $a.path
  if (-not $path) { $path = $a.file_path }
  if (-not $path) { $path = $a.filePath }
  if (-not $path) { $path = $a.filename }
  if (-not $path) { $path = $a.file }
  if (-not $path -or $path.Contains("`n") -or $path.Contains("`r")) { NoOp }
  $path = Get-CanonicalPath $path
  if (-not $path -or -not (Test-IsAllowedPath $path) -or -not (Test-Path -LiteralPath $path -PathType Leaf)) { NoOp }

  $map = '.agentic/hooks/lint-commands.json'
  if (-not (Test-Path -LiteralPath $map -PathType Leaf)) { NoOp }

  $m = Get-Content -LiteralPath $map -Raw | ConvertFrom-Json
  $ext = [System.IO.Path]::GetExtension($path).TrimStart('.')
  $property = $m.PSObject.Properties[$ext]
  if (-not $property) { NoOp }
  $entry = $property.Value
  $command = [string]$entry.command
  $configuredArgs = @($entry.args)
  if (-not $command -or $command -notmatch '^[A-Za-z0-9._+-]+$') { NoOp }
  if ($command -match '^(?i:sh|bash|dash|zsh|fish|cmd(?:\.exe)?|powershell(?:\.exe)?|pwsh(?:\.exe)?)$') { NoOp }
  if ($configuredArgs.Count -eq 0 -or @($configuredArgs | Where-Object { $_ -isnot [string] }).Count -gt 0) { NoOp }
  if (-not ($configuredArgs | Where-Object { $_.Contains('{file}') })) { NoOp }
  $resolved = Get-Command $command -CommandType Application -ErrorAction SilentlyContinue | Select-Object -First 1
  if (-not $resolved) { NoOp }

  $arguments = @($configuredArgs | ForEach-Object { $_.Replace('{file}', $path) })
  $out = & $resolved.Source @arguments 2>&1
  $status = $LASTEXITCODE
  if ($status -eq 0) { NoOp }

  $rendered = ($out | Out-String)
  if ($rendered.Length -gt 20000) { $rendered = $rendered.Substring(0, 20000) }
  $ctx = "Lint findings for $path (exit $status):`n$rendered"
  (@{ additionalContext = $ctx } | ConvertTo-Json -Compress)
} catch {
  exit 0
}
exit 0
