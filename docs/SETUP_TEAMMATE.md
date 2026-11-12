# Joining the team: setting up your PC

New here? Read [`HOW_WE_WORK.md`](HOW_WE_WORK.md) first (five minutes).

About 1-2 hours, most of it downloads. You need Windows with a decent NVIDIA GPU, or a Mac with Apple silicon
(see "On a Mac" below), and about 150 GB free.
Do this **before the jam** (Nov 12), and open the project once so the first long shader compile is behind you.

## 1. Accounts (the Team Owner helps)
1. A **GitHub** account. Send your username to the Team Owner, who adds you to the `Waffle-Widgets` organisation
   (each member uses a paid seat on its Team plan). Accept the email invite.
2. An **Epic Games** account (18+). Register for the jam with the email on it, and give the Team Owner your full name
   and that email for the entry and `docs/TEAM.md`.
3. A **Claude** account with Claude Code (Pro or higher), signed in to the Claude desktop app.

## 2. Install
1. **Unreal Engine 5.8** from the Epic Games Launcher, in the default folder (`C:\Program Files\Epic Games\UE_5.8`).
2. **Git** (git-scm.com) and **Git LFS** (`git lfs install` once).
3. **GitHub CLI** (`winget install GitHub.cli`), then `gh auth login` with *your* account.
4. Optional, if you'll make art: **Blender 5.2** and its MCP (see CLAUDE.md, "Blender"), and **uv**:
   `irm https://astral.sh/uv/install.ps1 | iex` (open a new terminal and check `uv --version`).

## 3. Clone and identify yourself
```
git clone https://github.com/Waffle-Widgets/<repo>.git
cd <repo>
git lfs pull
git config user.name "Your Name"
git config user.email "you@example.com"
git config lfs.locksverify true
```
Use the email on your GitHub account: Epic may check our Git history, and it should show who built what.
`lfs.locksverify` makes Git refuse a push that would overwrite a file a teammate has locked.

## 4. Claude Code MCP servers (run once on this computer)
From the repo folder:
```
.\tools\setup_mcp.ps1 -Clone      # Windows   (drop -Clone if you already have blender_mcp)
./tools/setup_mcp.sh --clone      # Mac
```
That writes `.claude\settings.local.json` (per PC, not committed) so the shared `.mcp.json` loads without an approval
prompt, and registers `unreal` and `blender` at **user scope** on this computer.

Only `unreal` is in the shared `.mcp.json`, because `http://127.0.0.1:8000/mcp` means "this machine's editor"
everywhere. `blender` needs a real folder path and that path is different on every computer, so it is never committed
to the repo — the script points it at your own clone. Check with `claude mcp list`.

Start a new Claude Code chat in the repo folder. Type `/` and check our skills are listed (`unreal-blueprint`,
`asset-import`, ...).

## 5. Open the project
1. Open the `.uproject` by double-clicking it (or from the Launcher). Never let a chat start Unreal as its own child process.
2. The first open compiles shaders: 5-15 minutes. If a window asks to **rebuild modules**, say Yes. If it fails because
   Visual Studio is missing, tell the Team Owner (we want the project to open without it).
3. When the editor is up, ask Claude: "Is the Unreal MCP answering?" It should list the level's actors.

## On a Mac
The project is Blueprint-only (no C++ of our own), so Unreal opens it on a Mac without Xcode. Not tested on a Mac
yet: tell the Team Owner what happens at each step. Do sections 1-7 with these changes:
- **Install (section 2):**
  - Unreal Engine 5.8 from the Epic Games Launcher for Mac (it installs to `/Users/Shared/Epic Games/UE_5.8`).
  - Git: `xcode-select --install` (Apple's command line tools; not the full Xcode).
  - [Homebrew](https://brew.sh), then `brew install git-lfs gh`, `git lfs install`, `gh auth login`.
  - uv, if you'll use Blender: `curl -LsSf https://astral.sh/uv/install.sh | sh`.
- **Settings and MCP (section 4):** run `./tools/setup_mcp.sh --clone`. It clones blender_mcp into `~/blender_mcp`,
  runs `uv sync`, writes `.claude/settings.local.json`, and registers `blender` at user scope pointing at your own
  path. No Mac path ever goes into the shared `.mcp.json`.
- **What stays on the Windows PCs:**
  - Packaging the game (`tools/package_build.ps1`): the jam wants a Windows build, and a Mac can't make one.
  - TRELLIS.2 (needs an NVIDIA GPU). Meshy works in any browser.
  - Making the jam repo (`tools/bootstrap/`).
- **Your role:** a Mac is a **tester** (and can be a **maker**), never the builder. To playtest, Claude switches
  the repo to the `playtest` branch; you press Play and never save.
- **First test:** open the project, press Play, and ask Claude "Is the Unreal MCP answering?" If the Model Context
  Protocol plugin doesn't load on Mac, tell the Team Owner; you can still design, test and make art.

## 6. Tell Claude what this computer does
Ask Claude in the repo: **"Add this computer to the Computers table as a tester"** (or maker, or whatever the team
agreed). It reads the computer's name with `hostname`, adds the row to `docs/TEAM.md`, commits and pushes. From then
on, every chat on this computer checks that row and only does what the role allows. To playtest, see `docs/PLAYTEST.md`.

## 7. How we work together
- Read `CLAUDE.md` ("Working as a team") and `docs/TEAM.md` (who owns what).
- Before work and before every commit: `git pull --rebase`.
- Before changing an Unreal file: `git lfs lock <file>`. If someone else has it, don't edit it.
- After pushing: unlock what you're done with.
- Commit small, tested changes with plain messages, and add a devlog entry (`devlog-entry` skill).
