---
name: pc-handoff
description: Leave or take over a computer safely - save, commit, push, release Git LFS locks, close or open Unreal, and message the other PC's chat. Use when the user says "I'm leaving this computer", "let's work on this computer", or work moves between GameStation and the main PC (M Station).
---

# Moving work between PCs

This is for **one person moving between their own PCs**, and for handing an area to a **teammate**.
- Teammates each have their own GitHub account, so LFS locks show who holds a file (`git lfs locks`).
- Which computer does what is the **Computers** table in `docs/TEAM.md` (run `hostname` to find this one). The Team
  Owner's PCs share one account, so locks can't tell them apart: only the `builder` row changes Unreal files.

## "Make <computer> the builder"
1. On the old builder: do "I'm leaving this computer" below (saved, pushed, locks released, Unreal closed).
   If you're not on the old builder, ask the user to confirm it's done there first.
2. Edit the table: the new computer gets `builder`, the old one its new role. Only one plain `builder` at a time.
3. Commit and push the table, then do "Let's work on this computer" on the new builder.

## "I'm leaving this computer"
1. Every asset under `/Game/Game` is saved (`is_dirty` false).
2. Tested work is committed and pushed (`git pull --rebase` first). Ask the user about anything untested; don't commit it.
3. Release our LFS locks: `git lfs locks --json`, unlock by **ID** (strip `\r` from IDs on Windows).
   `git lfs unlock` makes the file read-only again.
4. Close Unreal. If it stalls on a save prompt for a template asset we never meant to change, force-close it, but only
   after confirming our own assets are clean and pushed. A forced close can leave a "Restore Packages" dialog next
   time; close it with a window message from PowerShell.
5. Message the other PC's chat: what was pushed (commit), which assets, anything half done.

## "Let's work on this computer"
1. `git pull` (LFS brings the assets).
2. Open Unreal or Blender **yourself** with `explorer.exe <path>` (or the user opens it), never as a child of the chat:
   an app a chat starts closes when that chat is deleted, and its MCP tools vanish everywhere.
   Unreal: `MegaJamPractice/MegaJamPractice.uproject` in UE 5.8.
3. Wait until the Unreal MCP at `http://127.0.0.1:8000/mcp` answers (Blender: port 9876), then tell the user it's ready.
4. If MCP tools are missing in the chat: check the apps are running and listening, relaunch, then start a new chat.

## Switching branches on the Unreal PC (learned Nov 11, M Station)
- **Close Unreal before `git checkout`.** If it must be force-closed, first list unsaved packages
  (`tools/unreal_find_new_assets.py`): only force-close when none of ours hold real changes. The next start then waits
  behind a hidden **"Restore Packages"** window (the log stops at frame 0): find it with `EnumWindows` on the
  UnrealEditor process and send it `WM_CLOSE` (0x0010), which skips the restore.
- After switching to a branch that doesn't have an asset, the editor can still list that asset as unsaved (ours was
  `NS_FireBlastReal3D` on a branch from main). **Never save it**: it would write a file the branch shouldn't have.
- A script that rebuilds assets it doesn't own a lock on leaves them unsaved (read-only). If they didn't really change,
  that's harmless: close without saving.
- **Text-only commits (skills, docs, notes) to another branch while Unreal is open:** use a second checkout instead of
  switching: `GIT_LFS_SKIP_SMUDGE=1 git worktree add <scratch folder> origin/main -b <temp>`, commit there,
  `git push origin HEAD:main`, then `git worktree remove --force <folder>` and delete the temp branch. Bring a file from
  another branch with `git checkout origin/<branch> -- <path>`, or apply a commit with `git cherry-pick <sha>` (no `-q`).
- Always `git fetch` and look at every branch tip first: another chat (or the other PC) may have pushed.

## After every push that someone else must pick up
- Your own other PC: message its chat (same Claude account) with the asset names, folders and import notes.
- A teammate: their chat is on another Claude account and can't receive messages from yours. Write the hand-off where
  they'll see it: the commit message, plus a line in `docs/TEAM.md` if ownership changed. Tell the user to ping them.

## Handing an area to a teammate
Push, unlock every file in that area, update the owner in `docs/TEAM.md`, commit and push that, then tell the user
what to pass on (which files, what's half done).
