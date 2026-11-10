<#
.SYNOPSIS
  Packages a test build and publishes it as a numbered GitHub Release ("Build 14") for the testers, then tells the
  issues it fixes to get checked. Builder computer only (the Computers table in docs/TEAM.md).

.EXAMPLE
  powershell -ExecutionPolicy Bypass -File tools\publish_build.ps1 -Issues 12,15
  powershell -ExecutionPolicy Bypass -File tools\publish_build.ps1 -SkipPackage -Notes "Faster cars on lane 3"
  powershell -ExecutionPolicy Bypass -File tools\publish_build.ps1 -DryRun

.NOTES
  - Everything in the build must be committed and pushed first, so Mac testers can play the same commit in Unreal.
  - Runs tools\package_build.ps1 (4-5 minutes; don't save assets while it cooks). -SkipPackage reuses the newest zip
    in Builds\ (only if nothing changed since it was made).
  - Each issue in -Issues gets a comment ("Fixed in Build N, please check") and the ready-to-check label.
  - Builds are normal releases, so the fixed link <repo>/releases/latest always opens the newest one.
#>
param(
    [int[]]$Issues = @(),
    [string]$Notes = '',
    [string]$Game,
    [string]$Engine = 'C:\Program Files\Epic Games\UE_5.8',
    [switch]$SkipPackage,
    [switch]$DryRun
)
$ErrorActionPreference = 'Stop'
$Repo = (Resolve-Path (Join-Path (Split-Path -Parent $MyInvocation.MyCommand.Path) '..')).Path
function Step($m) { Write-Host "`n== $m" -ForegroundColor Cyan }
function Ok($m) { Write-Host "   ok  $m" -ForegroundColor Green }
# git prints progress on stderr, which Windows PowerShell turns into errors under 'Stop': relax it inside
function RunGit { $ErrorActionPreference = 'Continue'; $out = & git -C $Repo @args 2>$null; if ($LASTEXITCODE) { throw "git $args failed" }; $out }

# ---------------------------------------------------------------- is this the builder?
Step 'Checking this computer is the builder'
$me = ((hostname) -split '\.')[0].Trim()
$rows = Get-Content (Join-Path $Repo 'docs\TEAM.md') -Encoding UTF8 | Where-Object { $_ -match '^\|' } |
    ForEach-Object { , @(($_.Trim('|') -split '\|') | ForEach-Object { $_.Trim() }) }
$row = $rows | Where-Object { $_.Count -ge 4 -and $_[0] -ieq $me } | Select-Object -First 1
if (-not $row) { throw "This computer ($me) isn't in the Computers table in docs/TEAM.md. Ask Claude to add it." }
$roles = @($row[3] -split ',' | ForEach-Object { $_.Trim().ToLower() })
if ($roles -notcontains 'builder') {
    $b = ($rows | Where-Object { $_.Count -ge 4 -and (@($_[3] -split ',' | ForEach-Object { $_.Trim().ToLower() }) -contains 'builder') } |
        ForEach-Object { $_[0] }) -join ', '
    throw "This computer ($me) is '$($row[3])', not the builder. Only the builder publishes builds (builder: $b)."
}
Ok "$me is the builder"

# ---------------------------------------------------------------- is everything committed and pushed?
Step 'Checking everything is committed and pushed'
$dirty = RunGit status --porcelain --untracked-files=no
if ($dirty) { throw "Uncommitted changes (commit and push them first, so testers on a Mac get the same game):`n$($dirty -join "`n")" }
RunGit fetch -q | Out-Null
$branch = (RunGit rev-parse --abbrev-ref HEAD).Trim()
$sha = (RunGit rev-parse HEAD).Trim()
$remote = (& git -C $Repo rev-parse '@{u}' 2>$null)
if (-not $remote -or $remote.Trim() -ne $sha) { throw "Branch $branch isn't pushed (or is behind GitHub). git pull --rebase, then git push." }
Ok "$branch at $($sha.Substring(0,7)), pushed"

# ---------------------------------------------------------------- next build number
$tags = @(gh release list --limit 500 --json tagName --jq '.[].tagName' 2>$null)
$n = 1 + (@($tags | Where-Object { $_ -match '^build-(\d+)$' } | ForEach-Object { [int]$Matches[1] }) + 0 | Measure-Object -Maximum).Maximum
$tag = "build-$n"
Ok "this will be Build $n"

$issueLines = foreach ($i in $Issues) {
    $t = gh issue view $i --json title --jq .title
    if ($LASTEXITCODE) { throw "Issue #$i not found." }
    "- #$i $t"
}
$body = @"
Test build from ``$branch`` at commit $($sha.Substring(0,7)), $(Get-Date -Format 'yyyy-MM-dd HH:mm').

**Windows:** download the zip below, unzip it, run the .exe.
**Mac:** in the repo, ``git fetch``, ``git switch $branch``, ``git pull``, open the project in Unreal and press Play (never save).
"@
if ($Notes) { $body += "`n`n**What changed:** $Notes" }
if ($issueLines) { $body += "`n`n**Please check these and reply on each issue with ``works`` or what's still wrong:**`n" + ($issueLines -join "`n") }

if ($DryRun) {
    Step 'Dry run: would package, then publish'
    Write-Host "Release $tag (becomes releases/latest), target $sha`n$body"
    exit 0
}

# ---------------------------------------------------------------- package
if (-not $SkipPackage) {
    Step 'Packaging (tools\package_build.ps1, about 4-5 minutes)'
    $pkg = @{ Engine = $Engine }
    if ($Game) { $pkg.Game = $Game }
    & (Join-Path $Repo 'tools\package_build.ps1') @pkg
    if (-not $?) { throw 'Packaging failed: see the log in Builds\.' }
}
$zip = Get-ChildItem (Join-Path $Repo 'Builds') -Filter *.zip | Sort-Object LastWriteTime -Descending | Select-Object -First 1
if (-not $zip) { throw 'No zip in Builds\. Run without -SkipPackage.' }
Ok "$($zip.Name), $([math]::Round($zip.Length / 1MB)) MB"

# ---------------------------------------------------------------- publish
Step "Publishing Build $n"
$notesFile = Join-Path $env:TEMP "release-$tag.md"
[IO.File]::WriteAllText($notesFile, $body, (New-Object Text.UTF8Encoding $false))
gh release create $tag "$($zip.FullName)#$($zip.BaseName) Build $n.zip" --latest --target $sha --title "Build $n" --notes-file $notesFile
if ($LASTEXITCODE) { throw 'gh release create failed (signed in? gh auth status).' }
$url = gh release view $tag --json url --jq .url
Ok $url

foreach ($i in $Issues) {
    gh issue comment $i --body "Fixed in **Build $n** ($url). Please play it and reply ``works``, or say what's still wrong." | Out-Null
    gh issue edit $i --add-label ready-to-check --remove-label in-progress | Out-Null
    Ok "#$i marked ready-to-check"
}
Write-Host "`nDone: Build $n is at $url" -ForegroundColor Cyan
