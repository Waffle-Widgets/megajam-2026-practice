<#
.SYNOPSIS
  Sets up this PC's MCP servers for the jam repo. Run once per computer.

.DESCRIPTION
  The shared .mcp.json only holds `unreal`, because http://127.0.0.1:8000/mcp means
  "this machine's editor" on every OS. Blender's server needs a real folder path, and
  that path differs on every computer, so it is registered at USER scope here instead.
  See CLAUDE.md, "Blender", and docs/SETUP_TEAMMATE.md.

.PARAMETER BlenderMcpDir
  Where blender_mcp is cloned. Defaults to C:\blender_mcp (the repo's Windows convention).

.PARAMETER Clone
  Clone blender_mcp if it isn't there yet, and run `uv sync`.

.EXAMPLE
  .\tools\setup_mcp.ps1
  .\tools\setup_mcp.ps1 -Clone
  .\tools\setup_mcp.ps1 -BlenderMcpDir D:\tools\blender_mcp
#>
param(
    [string]$BlenderMcpDir = $(if ($env:BLENDER_MCP_DIR) { $env:BLENDER_MCP_DIR } else { 'C:\blender_mcp' }),
    [switch]$Clone
)

$ErrorActionPreference = 'Stop'
$repo = Split-Path -Parent $PSScriptRoot

function Say($msg) { Write-Host "  $msg" }

Write-Host "`nMCP setup for this PC" -ForegroundColor Cyan
Write-Host "repo: $repo"

# --- 1. Approve the shared servers on this PC (per-PC file, gitignored) -------
$settingsDir = Join-Path $repo '.claude'
$settingsPath = Join-Path $settingsDir 'settings.local.json'
if (-not (Test-Path $settingsDir)) { New-Item -ItemType Directory -Path $settingsDir | Out-Null }

$settings = if (Test-Path $settingsPath) {
    Get-Content $settingsPath -Raw | ConvertFrom-Json
} else {
    [pscustomobject]@{}
}
$settings | Add-Member -NotePropertyName 'enableAllProjectMcpServers' -NotePropertyValue $true -Force
$settings | ConvertTo-Json -Depth 10 | Set-Content $settingsPath -Encoding utf8
Say "approved shared .mcp.json servers -> .claude/settings.local.json"

# --- 2. uv must be on PATH ----------------------------------------------------
$uv = Get-Command uv -ErrorAction SilentlyContinue
if (-not $uv) {
    Write-Host "  uv is not on PATH. Install it, then re-run:" -ForegroundColor Yellow
    Write-Host "    irm https://astral.sh/uv/install.ps1 | iex"
    Write-Host "  (Unreal still works without uv; only Blender needs it.)"
    exit 1
}
Say "uv: $($uv.Source)"

# --- 3. Find (or clone) blender_mcp ------------------------------------------
$mcpDir = Join-Path $BlenderMcpDir 'mcp'
if (-not (Test-Path $mcpDir)) {
    if ($Clone) {
        Say "cloning blender_mcp -> $BlenderMcpDir"
        git clone https://projects.blender.org/lab/blender_mcp.git $BlenderMcpDir
        & uv --directory $mcpDir sync
    } else {
        Write-Host "  No blender_mcp at $mcpDir." -ForegroundColor Yellow
        Write-Host "  Re-run with -Clone, or pass -BlenderMcpDir <path> if it lives elsewhere."
        Write-Host "  Unreal is set up regardless; stopping before the Blender step."
        exit 1
    }
}
$mcpDir = (Resolve-Path $mcpDir).Path
Say "blender_mcp: $mcpDir"

# --- 4. Register the servers at USER scope (this PC, any folder) --------------
# User scope means chats pick them up wherever the session starts, not just in the repo.
# `mcp remove` writes to stderr when the server isn't there yet, and under
# $ErrorActionPreference='Stop' PowerShell treats a native command's stderr as fatal.
# So drop to 'Continue' for these calls and judge success by the exit code instead.
$prev = $ErrorActionPreference
$ErrorActionPreference = 'Continue'
try {
    foreach ($name in @('blender', 'unreal')) {
        & claude mcp remove $name -s user *>$null   # not there yet on a fresh PC: fine
    }

    # NOTE: '--' must be QUOTED. PowerShell 5.1 swallows a bare -- as its own
    # end-of-parameters marker, so claude then sees --directory as its own flag
    # and fails with "unknown option '--directory'".
    & claude mcp add blender -s user '--' uv --directory $mcpDir run blender-mcp *>$null
    if ($LASTEXITCODE -ne 0) { throw "claude mcp add blender failed (exit $LASTEXITCODE)" }

    & claude mcp add --transport http unreal -s user http://127.0.0.1:8000/mcp *>$null
    if ($LASTEXITCODE -ne 0) { throw "claude mcp add unreal failed (exit $LASTEXITCODE)" }
}
finally {
    $ErrorActionPreference = $prev
}
Say "registered 'blender' and 'unreal' at user scope"

Write-Host "`nDone. Check with:  claude mcp list" -ForegroundColor Green
Write-Host "Blender's own add-on still has to be running (port 9876) before Blender tools answer."
Write-Host "Servers are read when a session starts, so open a NEW session to pick them up.`n"
