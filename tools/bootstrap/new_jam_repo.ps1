<#
.SYNOPSIS
  Creates a fresh jam repo: an Unreal 5.8 project from Epic's Third Person Blueprint template, with our
  settings, agent instructions, scripts and docs. Copies NO gameplay, levels or art from the practice repo.

.EXAMPLE
  powershell -ExecutionPolicy Bypass -File tools\bootstrap\new_jam_repo.ps1 -Repo C:\Projects\megajam-2026 -Name OurGame
  powershell -ExecutionPolicy Bypass -File tools\bootstrap\new_jam_repo.ps1 -Repo C:\Projects\megajam-2026 -Name OurGame -Verify

.NOTES
  -Verify opens the new project in Unreal (as its own app, not a child of this shell), waits for the Unreal MCP
  on port 8000 and lists the level's actors through it. Close any other Unreal first: they share that port.
  The script never commits and never creates a GitHub repo; do both yourselves when you're ready.
#>
param(
    [Parameter(Mandatory = $true)][string]$Repo,
    [Parameter(Mandatory = $true)][string]$Name,
    [string]$Engine = 'C:\Program Files\Epic Games\UE_5.8',
    [switch]$Verify,
    [switch]$VerifyOnly
)
$ErrorActionPreference = 'Stop'
$Here = Split-Path -Parent $MyInvocation.MyCommand.Path
$Src = (Resolve-Path (Join-Path $Here '..\..')).Path          # the repo this script lives in (the practice repo)
$Tpl = Join-Path $Here 'templates'
$Today = Get-Date -Format 'yyyy-MM-dd'
$Utf8 = New-Object System.Text.UTF8Encoding($false)             # no BOM: a BOM breaks the first line of .gitignore

function Step($msg) { Write-Host "`n== $msg" -ForegroundColor Cyan }
function Ok($msg) { Write-Host "   ok  $msg" -ForegroundColor Green }
function Warn($msg) { Write-Host "   !!  $msg" -ForegroundColor Yellow }
function Write-Text($path, $text) {
    $dir = Split-Path -Parent $path
    if ($dir -and -not (Test-Path $dir)) { New-Item -ItemType Directory -Force $dir | Out-Null }
    [IO.File]::WriteAllText($path, $text, $Utf8)
}
function From-Template($file) {
    $t = [IO.File]::ReadAllText((Join-Path $Tpl $file))
    return $t.Replace('{{NAME}}', $Name).Replace('{{DATE}}', $Today)
}
function Copy-Tree($from, $to, [string[]]$excludeFiles = @(), [string[]]$excludeDirs = @()) {
    # robocopy exit codes below 8 mean success
    $a = @($from, $to, '/E', '/NFL', '/NDL', '/NJH', '/NJS', '/NP', '/R:1', '/W:1')
    if ($excludeFiles.Count) { $a += '/XF'; $a += $excludeFiles }
    if ($excludeDirs.Count) { $a += '/XD'; $a += $excludeDirs }
    & robocopy @a | Out-Null
    if ($LASTEXITCODE -ge 8) { throw "robocopy failed ($LASTEXITCODE): $from -> $to" }
}

# ---------------------------------------------------------------- checks
if ($Name -notmatch '^[A-Za-z][A-Za-z0-9]{0,19}$') { throw "Name must be letters and digits only, starting with a letter, at most 20 characters (got '$Name')." }
$Proj = Join-Path $Repo $Name
$UProject = Join-Path $Proj "$Name.uproject"
$TemplateDir = Join-Path $Engine 'Templates\TP_ThirdPersonBP'
$Packs = Join-Path $Engine 'Templates\TemplateResources\High'

if (-not $VerifyOnly) {
    Step 'Checking'
    if (-not (Test-Path $TemplateDir)) { throw "Unreal's Third Person BP template not found at $TemplateDir. Is UE 5.8 installed there? Pass -Engine." }
    if ((Test-Path $Repo) -and (Get-ChildItem -Force $Repo | Select-Object -First 1)) { throw "$Repo already exists and isn't empty. Pick a new folder." }
    foreach ($tool in 'git', 'git-lfs') { if (-not (Get-Command $tool -ErrorAction SilentlyContinue)) { throw "$tool is not installed." } }
    Ok "template, git and git-lfs found; $Repo is free"

    # ------------------------------------------------------------ 1. the Unreal project
    Step "Creating the Unreal project $Name from the Third Person Blueprint template"
    New-Item -ItemType Directory -Force $Proj | Out-Null
    # what the New Project window copies: the template minus its own description files (TemplateDefs.ini FilesToIgnore/FoldersToIgnore)
    Copy-Tree (Join-Path $TemplateDir 'Config') (Join-Path $Proj 'Config') @('TemplateDefs.ini', 'config.ini')
    Copy-Tree (Join-Path $TemplateDir 'Content') (Join-Path $Proj 'Content')
    # ...plus the shared content packs the template lists (SharedContentPacks in TP_ThirdPerson's TemplateDefs.ini)
    foreach ($pack in 'LevelPrototyping', 'Characters', 'Input') {
        Copy-Tree (Join-Path $Packs "$pack\Content") (Join-Path $Proj "Content\$pack")
    }
    # the template's name is replaced in every config file, as the New Project window does
    Get-ChildItem (Join-Path $Proj 'Config') -Filter *.ini | ForEach-Object {
        $t = [IO.File]::ReadAllText($_.FullName)
        Write-Text $_.FullName ($t -replace 'TP_ThirdPersonBP', $Name)
    }
    Ok 'template content and the LevelPrototyping, Characters and Input packs copied'

    # ------------------------------------------------------------ 2. our settings
    Step 'Applying our settings (plugins, MCP auto-start, imports without pop-ups, full speed in background)'
    $uprojData = [ordered]@{
        FileVersion = 3; EngineAssociation = '5.8'; Category = ''; Description = ''
        Plugins = @(
            [ordered]@{ Name = 'ModelingToolsEditorMode'; Enabled = $true; TargetAllowList = @('Editor') },
            [ordered]@{ Name = 'GameplayStateTree'; Enabled = $true },
            [ordered]@{ Name = 'ModelContextProtocol'; Enabled = $true },
            [ordered]@{ Name = 'AllToolsets'; Enabled = $true },
            [ordered]@{ Name = 'Terminal'; Enabled = $true },
            # an AI denoiser for offline movie renders, on by default; it adds ~130 MB to every packaged game
            [ordered]@{ Name = 'NNEDenoiser'; Enabled = $false }
        )
    }
    Write-Text $UProject ($uprojData | ConvertTo-Json -Depth 5)

    $cfg = Join-Path $Proj 'Config'
    $game = Join-Path $cfg 'DefaultGame.ini'
    $t = [IO.File]::ReadAllText($game)
    $t = $t -replace '(?m)^ProjectName=.*$', "ProjectName=$Name"
    $t = $t -replace '(?m)^ProjectID=.*$', ('ProjectID=' + [guid]::NewGuid().ToString('N').ToUpper())
    Write-Text $game ($t.TrimEnd() + "`r`n`r`n" + (From-Template 'DefaultGame.add.ini'))
    $eng = Join-Path $cfg 'DefaultEngine.ini'
    Write-Text $eng (([IO.File]::ReadAllText($eng)).TrimEnd() + "`r`n`r`n" + (From-Template 'DefaultEngine.add.ini'))
    $epp = Join-Path $cfg 'DefaultEditorPerProjectUserSettings.ini'
    Write-Text $epp (([IO.File]::ReadAllText($epp)).TrimEnd() + "`r`n" + (From-Template 'DefaultEditorPerProjectUserSettings.add.ini'))
    Write-Text (Join-Path $cfg 'DefaultEditorSettings.ini') (From-Template 'DefaultEditorSettings.ini')
    Ok "$Name.uproject (UE 5.8, MCP + toolsets + Terminal plugins), project name and a new project ID"
    Ok 'MCP auto-start on port 8000, Interchange without import windows, background throttling off, auto-import on'

    # ------------------------------------------------------------ 3. repo files
    Step 'Repo files (.gitignore, .gitattributes, .mcp.json, per-PC Claude settings)'
    Write-Text (Join-Path $Repo '.gitignore') (From-Template 'gitignore.txt')
    Copy-Item (Join-Path $Src '.gitattributes') (Join-Path $Repo '.gitattributes')
    # .mcp.json is committed and shared by every teammate, so it names plain 'uv' (found on each PC's PATH),
    # never one person's C:\Users\<name>\... path.
    if (-not (Get-Command uv -ErrorAction SilentlyContinue)) { Warn "uv isn't on this PC's PATH: the Blender MCP won't start until it's installed (docs/SETUP_TEAMMATE.md)" }
    if (-not (Test-Path 'C:\blender_mcp\mcp')) { Warn 'C:\blender_mcp\mcp not found: clone the Blender MCP there (see CLAUDE.md, Blender setup)' }
    $mcp = [ordered]@{ mcpServers = [ordered]@{
            unreal  = [ordered]@{ type = 'http'; url = 'http://127.0.0.1:8000/mcp' }
            blender = [ordered]@{ type = 'stdio'; command = 'uv'; args = @('--directory', 'C:\blender_mcp\mcp', 'run', 'blender-mcp') }
        } }
    Write-Text (Join-Path $Repo '.mcp.json') ($mcp | ConvertTo-Json -Depth 5)
    Write-Text (Join-Path $Repo '.claude\settings.local.json') "{`r`n  `"enableAllProjectMcpServers`": true`r`n}`r`n"
    Ok '.gitignore, .gitattributes (LFS + locking), .mcp.json, .claude/settings.local.json'

    # ------------------------------------------------------------ 4. tools and scripts (never art)
    Step 'Copying tools and scripts (no .blend kits, models, textures or practice content)'
    Copy-Tree (Join-Path $Src 'tools') (Join-Path $Repo 'tools') @('*.wav', '*.png', '*.jpg', '*.glb', '*.fbx', '*.ply', '*.pt') @('__pycache__', 'out')
    New-Item -ItemType Directory -Force (Join-Path $Repo 'Art\Blender') | Out-Null
    Get-ChildItem (Join-Path $Src 'Art\Blender') -Filter *.py | Copy-Item -Destination (Join-Path $Repo 'Art\Blender')
    $n = (Get-ChildItem (Join-Path $Repo 'Art\Blender') -Filter *.py).Count
    Ok "tools/ and $n Blender scripts"

    # ------------------------------------------------------------ 5. agent instructions and docs
    Step 'Agent instructions and docs'
    foreach ($f in 'CLAUDE.md', 'GEMINI.md') {
        $t = [IO.File]::ReadAllText((Join-Path $Src $f))
        Write-Text (Join-Path $Repo $f) ($t.Replace('MegaJamPractice', $Name))
    }
    # Claude Code skills (.claude/skills/<name>/SKILL.md): how-to instructions only, allowed before the jam (§7h)
    foreach ($sk in Get-ChildItem (Join-Path $Src '.claude\skills') -Recurse -File -ErrorAction SilentlyContinue) {
        $rel = $sk.FullName.Substring($Src.TrimEnd('\').Length + 1)
        Write-Text (Join-Path $Repo $rel) ([IO.File]::ReadAllText($sk.FullName).Replace('MegaJamPractice', $Name))
    }
    New-Item -ItemType Directory -Force (Join-Path $Repo 'docs') | Out-Null
    # GitHub issue form for playtest reports (labels: see the playtest-issues skill)
    Copy-Tree (Join-Path $Src '.github') (Join-Path $Repo '.github')
    foreach ($f in 'PLAN.md', 'RULES.md', 'SETUP_TEAMMATE.md', 'TEAM.md', 'PLAYTEST.md', 'HOW_WE_WORK.md') { Copy-Item (Join-Path $Src "docs\$f") (Join-Path $Repo "docs\$f") }
    Write-Text (Join-Path $Repo 'docs\PITCH.md') (From-Template 'PITCH.md')
    Write-Text (Join-Path $Repo 'docs\DEVLOG.md') (From-Template 'DEVLOG.md')
    Write-Text (Join-Path $Repo 'docs\media\.gitkeep') ''
    Write-Text (Join-Path $Repo 'CREDITS.md') (From-Template 'CREDITS.md')
    Write-Text (Join-Path $Repo 'README.md') (From-Template 'README.md')
    Ok 'CLAUDE.md, GEMINI.md, .claude/skills, README, CREDITS, docs/ (PLAN, RULES, SETUP_TEAMMATE, TEAM, PLAYTEST, HOW_WE_WORK, empty PITCH, fresh DEVLOG), .github issue form'

    # ------------------------------------------------------------ 6. git
    Step 'Git'
    Push-Location $Repo
    try {
        git init -q -b main
        git lfs install --local | Out-Null
        git config lfs.locksverify true      # refuse a push that changes a file someone else has locked
        Ok 'git repo (branch main) with LFS hooks and lock checks; nothing committed yet'
    } finally { Pop-Location }
}

# ---------------------------------------------------------------- 7. verify: open it in Unreal and talk to the MCP
function Test-Port8000 { try { $c = New-Object Net.Sockets.TcpClient; $c.Connect('127.0.0.1', 8000); $c.Close(); return $true } catch { return $false } }
function Invoke-Mcp($body, $session) {
    $h = @{ 'Accept' = 'application/json, text/event-stream' }
    if ($session) { $h['Mcp-Session-Id'] = $session }
    $r = Invoke-WebRequest -UseBasicParsing -Method Post -Uri 'http://127.0.0.1:8000/mcp' -ContentType 'application/json' -Headers $h -Body ($body | ConvertTo-Json -Depth 10 -Compress)
    $text = $r.Content
    if ($text -match '(?m)^data:\s*(.+)$') { $text = $Matches[1] }   # streamable HTTP may answer as an event stream
    return @{ session = $r.Headers['Mcp-Session-Id']; json = ($text | ConvertFrom-Json) }
}

if ($Verify -or $VerifyOnly) {
    Step 'Verify: opening the project in Unreal and asking the MCP for the level'
    if (-not (Test-Path $UProject)) { throw "$UProject not found." }
    if (Test-Port8000) { throw 'Something is already listening on port 8000 (another Unreal?). Close it first, then run again with -VerifyOnly.' }
    # explorer.exe opens it as its own app: an editor started as a child of a chat closes when that chat is deleted
    Start-Process explorer.exe $UProject
    Write-Host '   waiting for the editor (the first open compiles shaders: 5-15 minutes)...'
    $t0 = Get-Date
    while (-not (Test-Port8000)) {
        if (((Get-Date) - $t0).TotalMinutes -gt 30) { throw 'The MCP did not answer within 30 minutes. Look at the editor: a dialog may be waiting.' }
        Start-Sleep -Seconds 10
    }
    Ok ("MCP answered after {0:N0} s" -f ((Get-Date) - $t0).TotalSeconds)
    Start-Sleep -Seconds 5
    $init = Invoke-Mcp @{ jsonrpc = '2.0'; id = 1; method = 'initialize'; params = @{ protocolVersion = '2025-03-26'; capabilities = @{}; clientInfo = @{ name = 'bootstrap'; version = '1' } } } $null
    $s = $init.session
    Invoke-WebRequest -UseBasicParsing -Method Post -Uri 'http://127.0.0.1:8000/mcp' -ContentType 'application/json' -Headers @{ 'Accept' = 'application/json, text/event-stream'; 'Mcp-Session-Id' = $s } -Body '{"jsonrpc":"2.0","method":"notifications/initialized"}' | Out-Null
    $callArgs = @{ toolset_name = 'editor_toolset.toolsets.scene.SceneTools'; tool_name = 'find_actors'; arguments = @{ name = ''; tag = ''; collision_channels = @() } }
    $res = Invoke-Mcp @{ jsonrpc = '2.0'; id = 2; method = 'tools/call'; params = @{ name = 'call_tool'; arguments = $callArgs } } $s
    $out = ($res.json.result.content | ForEach-Object { $_.text }) -join "`n"
    $count = ([regex]::Matches($out, 'refPath')).Count
    if ($out -notmatch "/Game/ThirdPerson/Lvl_ThirdPerson") { Warn "Unexpected answer: $($out.Substring(0, [Math]::Min(400, $out.Length)))" }
    else { Ok "the MCP lists $count actors in Lvl_ThirdPerson: Claude can drive this project" }
    # load errors open a Message Log window on start; list them
    $log = Join-Path $Proj "Saved\Logs\$Name.log"
    $le = @(Select-String -Path $log -Pattern 'LoadErrors: Error' -ErrorAction SilentlyContinue)
    if ($le.Count) { $le | ForEach-Object { Warn ("load error: " + ($_.Line -replace '^.*LoadErrors: Error: ', '')) } } else { Ok 'no load errors' }
    # the settings we rely on, read back from the running editor
    $checks = @(
        @('/Script/UnrealEd.Default__EditorPerformanceSettings', 'bThrottleCPUWhenNotForeground', 'false', 'Use Less CPU when in Background is off'),
        @('/Script/UnrealEd.Default__EditorLoadingSavingSettings', 'bPromptBeforeAutoImporting', 'false', 'dropped files import without asking'),
        @('/Script/UnrealEd.Default__EditorLoadingSavingSettings', 'bMonitorContentDirectories', 'true', 'Content folder is watched for new files'),
        @('/Script/EngineSettings.Default__GeneralProjectSettings', 'ProjectName', $Name, "project name is $Name"))
    $id = 3
    foreach ($c in $checks) {
        $q = @{ toolset_name = 'editor_toolset.toolsets.object.ObjectTools'; tool_name = 'get_properties'; arguments = @{ instance = @{ refPath = $c[0] }; properties = @($c[1]) } }
        $a = Invoke-Mcp @{ jsonrpc = '2.0'; id = $id; method = 'tools/call'; params = @{ name = 'call_tool'; arguments = $q } } $s
        $id++
        $txt = ($a.json.result.content | ForEach-Object { $_.text }) -join ' '
        $flat = ($txt -replace '[\\" ]', '')              # {"returnValue":"{\"ProjectName\":\"X\"}"} -> {returnValue:{ProjectName:X}}
        if ($flat -match ([regex]::Escape($c[1] + ':' + $c[2]) + '(\W|$)')) { Ok $c[3] } else { Warn "$($c[1]) is not $($c[2]): $txt" }
    }
}

Write-Host "`nDone. Next: open $Repo in a new Claude Code session, create the GitHub repo, and make the first commit when you're ready." -ForegroundColor Cyan
