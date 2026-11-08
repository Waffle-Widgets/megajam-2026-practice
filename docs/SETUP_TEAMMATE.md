# Joining the team: setting up your PC

About 1-2 hours, most of it downloads. You need Windows, a decent NVIDIA GPU, and about 150 GB free.
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
   `irm https://astral.sh/uv/install.ps1 | iex`. The repo's `.mcp.json` runs plain `uv`, so it must be on your PATH
   (open a new terminal and check `uv --version`).

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

## 4. Claude Code settings for this repo
Create `.claude\settings.local.json` (it's per PC and not committed):
```
{
  "enableAllProjectMcpServers": true
}
```
Start a new Claude Code chat in the repo folder. Type `/` and check our skills are listed (`unreal-blueprint`,
`asset-import`, ...).

## 5. Open the project
1. Open the `.uproject` by double-clicking it (or from the Launcher). Never let a chat start Unreal as its own child process.
2. The first open compiles shaders: 5-15 minutes. If a window asks to **rebuild modules**, say Yes. If it fails because
   Visual Studio is missing, tell the Team Owner (we want the project to open without it).
3. When the editor is up, ask Claude: "Is the Unreal MCP answering?" It should list the level's actors.

## 6. How we work together
- Read `CLAUDE.md` ("Working as a team") and `docs/TEAM.md` (who owns what).
- Before work and before every commit: `git pull --rebase`.
- Before changing an Unreal file: `git lfs lock <file>`. If someone else has it, don't edit it.
- After pushing: unlock what you're done with.
- Commit small, tested changes with plain messages, and add a devlog entry (`devlog-entry` skill).
