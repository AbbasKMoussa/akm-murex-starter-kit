# lint-on-edit.ps1 — postToolUse hook (PowerShell variant)
#
# STATUS: DRAFT, NOT YET FIRED AGAINST A LIVE COPILOT CLI.
# Context-injection field VERIFIED: {"additionalContext": "..."} is correct.
# NOTE: copilot-cli#2980 — additionalContext is not always forwarded into the
# context window (and not for MCP tool calls).
# TODO(verify): command execution below uses cmd.exe /c (Windows). Adjust for
# PowerShell Core on Linux/macOS after testing.
#
# SAFETY: always exit 0; emit nothing on any uncertainty. No-op when no lint
# command is configured for the file's extension.

$ErrorActionPreference = 'SilentlyContinue'

function NoOp { exit 0 }

try {
  $raw = [Console]::In.ReadToEnd()
  if ([string]::IsNullOrWhiteSpace($raw)) { NoOp }

  $o = $raw | ConvertFrom-Json
  $a = if ($o.toolArgs) { $o.toolArgs } elseif ($o.tool_input) { $o.tool_input } else { $null }
  if ($null -eq $a) { NoOp }

  $path = $a.path
  if (-not $path) { $path = $a.file_path }
  if (-not $path) { $path = $a.filePath }
  if (-not $path) { $path = $a.filename }
  if (-not $path) { $path = $a.file }
  if (-not $path -or -not (Test-Path $path)) { NoOp }

  $map = '.agentic/hooks/lint-commands.json'
  if (-not (Test-Path $map)) { NoOp }

  $m = Get-Content $map -Raw | ConvertFrom-Json
  $ext = [System.IO.Path]::GetExtension($path).TrimStart('.')
  $template = $m.$ext
  if (-not $template) { NoOp }

  $cmd = $template.Replace('{file}', '"' + $path + '"')
  $out = & cmd.exe /c $cmd 2>&1
  $status = $LASTEXITCODE
  if ($status -eq 0) { NoOp }

  $ctx = "Lint findings for $path (exit $status):`n$out"
  (@{ additionalContext = $ctx } | ConvertTo-Json -Compress)
} catch {
  exit 0
}
exit 0
