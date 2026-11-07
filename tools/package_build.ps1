<#
.SYNOPSIS
  Packages the game as a Windows Shipping build and zips it for itch.io as <Team>_<Game>.zip in Builds\.

.EXAMPLE
  powershell -ExecutionPolicy Bypass -File tools\package_build.ps1
  powershell -ExecutionPolicy Bypass -File tools\package_build.ps1 -Run
  powershell -ExecutionPolicy Bypass -File tools\package_build.ps1 -Game CityFrog -CopyTo \\GAMINGPC2\Builds

.NOTES
  - Works with the editor open (about 4-5 minutes), but don't save assets while it cooks.
  - Cooks the start map (GameDefaultMap) plus every map under Content/Game/, so a new level can't be left out.
  - The first package on a PC compiles the game program (Binaries/ is not in Git); later ones reuse it. Pass -Build to
    force a compile (after C++ or plugin changes). Compiling needs this project's editor closed.
  - -Run starts the packaged game for 20 seconds to check that it launches and stays up, then closes it.
#>
param(
    [string]$Project,                       # path to the .uproject (default: the only one one folder below the repo root)
    [string]$Team = 'WaffleWidgets',
    [string]$Game,                          # default: the project's name
    [string]$Engine = 'C:\Program Files\Epic Games\UE_5.8',
    [switch]$Build,
    [switch]$Run,
    [string]$CopyTo
)
$ErrorActionPreference = 'Stop'
$Repo = (Resolve-Path (Join-Path (Split-Path -Parent $MyInvocation.MyCommand.Path) '..')).Path
function Step($m) { Write-Host "`n== $m" -ForegroundColor Cyan }
function Ok($m) { Write-Host "   ok  $m" -ForegroundColor Green }
function Warn($m) { Write-Host "   !!  $m" -ForegroundColor Yellow }

# ---------------------------------------------------------------- checks
Step 'Checking'
if (-not $Project) {
    $found = @(Get-ChildItem $Repo -Directory | ForEach-Object { Get-ChildItem $_.FullName -Filter *.uproject -File })
    if ($found.Count -ne 1) { throw "Found $($found.Count) .uproject files one folder below $Repo. Pass -Project." }
    $Project = $found[0].FullName
}
$ProjDir = Split-Path -Parent $Project
$ProjName = [IO.Path]::GetFileNameWithoutExtension($Project)
if (-not $Game) { $Game = $ProjName }
if ("$Team$Game" -notmatch '^[A-Za-z0-9]+$') { throw 'Team and Game must be letters and digits only (itch.io wants TeamName_GameName).' }
$UAT = Join-Path $Engine 'Engine\Build\BatchFiles\RunUAT.bat'
$Cmd = Join-Path $Engine 'Engine\Binaries\Win64\UnrealEditor-Cmd.exe'
foreach ($f in $UAT, $Cmd) { if (-not (Test-Path $f)) { throw "$f not found. Is UE 5.8 installed there? Pass -Engine." } }

# the start map must be set and must exist
$engIni = Join-Path $ProjDir 'Config\DefaultEngine.ini'
$m = Select-String -Path $engIni -Pattern '^GameDefaultMap=(.+)$' | Select-Object -First 1
if (-not $m) { throw "GameDefaultMap is not set in $engIni. Set it to the level the game should start in." }
$startMap = ($m.Matches[0].Groups[1].Value.Trim() -split '\.')[0]          # /Game/Game/Maps/Lvl_Frogger
$startFile = Join-Path $ProjDir ('Content' + ($startMap -replace '^/Game', '') + '.umap')
if (-not (Test-Path $startFile)) { throw "The start map $startMap doesn't exist ($startFile)." }
Ok "start map: $startMap"

# every map under Content/Game/ gets cooked too (a level the game opens by name but nobody listed would be missing)
$maps = @($startMap)
$gameContent = Join-Path $ProjDir 'Content\Game'
if (Test-Path $gameContent) {
    Get-ChildItem $gameContent -Recurse -Filter *.umap | ForEach-Object {
        $rel = $_.FullName.Substring((Join-Path $ProjDir 'Content').Length) -replace '\\', '/' -replace '\.umap$', ''
        if ("/Game$rel" -notin $maps) { $maps += "/Game$rel" }
    }
}
Ok ("maps to cook: " + (($maps | ForEach-Object { ($_ -split '/')[-1] }) -join ', '))

# Our editor plugins (MCP, toolsets) make Unreal build a game program of the project's own, even without C++.
# Binaries/ isn't in Git, so the first package on each PC compiles it (a few minutes); after that it's reused.
$receipt = Join-Path $ProjDir "Binaries\Win64\$ProjName-Win64-Shipping.target"
$hasSource = Test-Path (Join-Path $ProjDir 'Source')
if (-not $Build -and -not (Test-Path $receipt)) { Warn 'No compiled game program on this PC yet: compiling it this time (first package only).'; $Build = $true }
if ($hasSource -and -not $Build) { Warn 'This project has C++ code. Without -Build the last compiled game code is used.' }
# the editor only gets in the way of a compile when it has THIS project open
$sameEditor = @(Get-CimInstance Win32_Process -Filter "Name='UnrealEditor.exe'" | Where-Object { $_.CommandLine -like "*$ProjName.uproject*" })
if ($Build -and $sameEditor.Count) { throw "Compiling needs this project's editor closed (it tries to rebuild the editor). Close $ProjName in Unreal, or package again later with the game program already built." }
if ($sameEditor.Count) { Warn "The editor is open: that's fine, but don't save assets until this finishes." }

# ---------------------------------------------------------------- package
$Builds = Join-Path $Repo 'Builds'
$Stage = Join-Path $Builds 'Stage'
New-Item -ItemType Directory -Force $Builds | Out-Null
if (Test-Path $Stage) { Remove-Item -Recurse -Force $Stage }
$stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$log = Join-Path $Builds "package-$stamp.log"
Step "Packaging $Game (Shipping, Win64). Log: $log"
$uatArgs = @('BuildCookRun', "-project=`"$Project`"", '-platform=Win64', '-clientconfig=Shipping',
    $(if ($Build) { '-build' } else { '-skipbuild' }), '-nocompileeditor', '-cook', "-map=$($maps -join '+')", '-stage', '-pak', '-prereqs',
    '-archive', "-archivedirectory=`"$Stage`"", "-unrealexe=`"$Cmd`"", '-utf8output', '-nop4', '-unattended')
$t0 = Get-Date
& cmd.exe /c "`"$UAT`" $($uatArgs -join ' ') > `"$log`" 2>&1"
$code = $LASTEXITCODE
$mins = ((Get-Date) - $t0).TotalMinutes
if ($code -ne 0) {
    Warn ("Packaging failed (exit code $code) after {0:N1} min. The lines that mention errors:" -f $mins)
    Select-String -Path $log -Pattern 'Error:|error |ERROR:|failed' | Select-Object -Last 25 | ForEach-Object { Write-Host "      $($_.Line.Trim())" }
    throw "See the full log: $log"
}
Ok ("packaged in {0:N1} min" -f $mins)

# ---------------------------------------------------------------- zip for itch.io
$win = Join-Path $Stage 'Windows'
$exe = Get-ChildItem $win -Filter *.exe -File | Select-Object -First 1
if (-not $exe) { throw "No .exe in $win. Something went wrong in staging; see $log" }
$zipName = "${Team}_${Game}"
$zip = Join-Path $Builds "$zipName.zip"
$folder = Join-Path $Builds $zipName                     # the zip opens to one folder named like the zip
if (Test-Path $folder) { Remove-Item -Recurse -Force $folder }
Move-Item $win $folder
if (Test-Path $zip) { Remove-Item -Force $zip }
# debug symbols (.pdb, ~180 MB) are no use to players; keep them outside the zip for reading crash reports
$sym = Join-Path $Builds 'Symbols'
New-Item -ItemType Directory -Force $sym | Out-Null
Get-ChildItem $folder -Recurse -Filter *.pdb | ForEach-Object { Move-Item $_.FullName (Join-Path $sym $_.Name) -Force }
Step "Zipping $zipName.zip"
Add-Type -AssemblyName System.IO.Compression.FileSystem
[IO.Compression.ZipFile]::CreateFromDirectory($folder, $zip, [IO.Compression.CompressionLevel]::Optimal, $true)
$mb = (Get-Item $zip).Length / 1MB
if ($mb -ge 1024) { Warn ("{0:N0} MB: over itch.io's 1 GB limit! Remove unused content or lower texture sizes." -f $mb) }
else { Ok ("{0:N0} MB (itch.io limit 1024 MB)" -f $mb) }
Remove-Item -Recurse -Force $Stage

# ---------------------------------------------------------------- optional: smoke test and copy
if ($Run) {
    Step 'Starting the packaged game for 20 seconds'
    $gameExe = Join-Path $folder $exe.Name
    $p = Start-Process $gameExe -PassThru
    Start-Sleep -Seconds 20
    $alive = Get-Process -Id $p.Id -ErrorAction SilentlyContinue
    $kids = Get-Process | Where-Object { $_.ProcessName -like "$ProjName*Shipping*" -or $_.ProcessName -like "$ProjName-Win64*" }
    if ($alive -or $kids) {
        Ok 'the game started and is still running after 20 seconds'
        $kids | Stop-Process -Force -ErrorAction SilentlyContinue
        if ($alive) { Stop-Process -Id $p.Id -Force -ErrorAction SilentlyContinue }
    } else { Warn "The game closed within 20 seconds (exit code $($p.ExitCode)). Run it by hand to see why: $gameExe" }
}
if ($CopyTo) {
    Step "Copying the zip to $CopyTo"
    Copy-Item $zip $CopyTo -Force
    Ok "copied to $CopyTo"
}
Write-Host "`nDone: $zip`nThe unzipped game is in $folder (run $($exe.Name))." -ForegroundColor Cyan
