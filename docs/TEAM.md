# Team

Up to 5 people (jam rule §2). Every member must be 18+, have an Epic account, and be listed on the entry.
Claude reads this file to know who owns what. Update it whenever ownership changes, and commit it.

## Members

| Name | GitHub | Epic account email registered? | PC(s) | Role |
|---|---|---|---|---|
| _(Team Owner: submits the entry)_ | mendezm87 | | GameStation (Unreal), M Station (Blender, TRELLIS) | |
| Justin | allbarkdev (joined Waffle-Widgets and Jam Team Nov 8) | | | |
| | | | | |
| | | | | |
| | | | | |

**GitHub access:** every teammate joins the Waffle-Widgets team **Jam Team**, which has write access (needed to push
and to lock files). The org's base permission is "No permission" (since Nov 8), so members see only the repos their
team is given; the owner's other projects stay private to the owner. When the jam repo is made, give Jam Team write
on it (repo Settings > Collaborators and teams), or teammates won't even see it.
**Teammates get the MegaJam repos only.** Add new people to Jam Team, never to a repo directly, and give Jam Team
only MegaJam repos. The org's other repos aren't part of this work. Members may create repos of their own. Each new person needs a paid seat on the org first.

## Computers: who does what
Claude reads this table at the start of every chat. It runs `hostname` and finds its row (case doesn't matter, and a
Mac's `.local` ending is ignored). If no row matches, it asks which computer it is on and fixes the name here.
**Change a role by asking any chat** ("make GameStation the builder", "add this Mac as a tester"): Claude edits this
table, commits and pushes. A computer can have more than one role (`tester, maker`).

| Computer (`hostname`) | Person | OS | Role | Notes |
|---|---|---|---|---|
| GameStation | Team Owner | Windows | builder | Unreal edits, packaging, fixes playtest issues |
| M_Station | Team Owner | Windows | maker | TRELLIS, Blender, Meshy, sounds |
| _(Owner's Mac: hostname to add)_ | Team Owner | macOS | tester | |
| Justins-Mac-mini | Justin | macOS | tester, maker | Mac mini, Apple silicon. git-lfs, gh, uv and the Blender MCP set up Nov 9; Blender is 5.1.2 (team uses 5.2) |

**Roles**
- **builder:** the only computer that changes Unreal files (`.uasset`, `.umap`) and commits them. It packages and publishes
  test builds and works through the playtest issues (`playtest-issues` skill). Exactly **one** at a time, on Windows
  (the jam wants a Windows build). It works on the `playtest` branch and merges into `main` once testers confirm.
- **builder (area):** e.g. `builder (UI)`. A second person may change Unreal files in that one area only (its folder
  in "Who owns what" below), with LFS locks. Use it when one builder can't keep up; never two in the same Blueprint.
- **maker:** makes things outside Unreal (Blender, Meshy, TRELLIS, `tools/make_sfx.py`) and commits FBX, textures,
  sounds and scripts. It never saves in Unreal; the builder imports what it makes.
- **tester:** plays test builds and files GitHub issues (`docs/PLAYTEST.md`). Windows: downloads the build from the
  repo's Releases. Mac: pulls the `playtest` branch and presses Play in Unreal, never saving.
- Everyone may edit docs and scripts (text files merge normally).

## Who owns what this jam
Own a system, a folder, or a set of Blueprints. Others ask before changing it, and only the owner (or whoever holds
the lock) edits its `.uasset` files.

| Area | Owner | Files / folders |
|---|---|---|
| Level layout | | `Content/Game/Maps/` (One File Per Actor: lock the actors you move) |
| Player character | | `Content/Game/Blueprints/BP_<Player>*` |
| Obstacles / enemies | | |
| UI (title, HUD, end screen) | | `Content/Game/UI/` |
| Audio | | `Content/Game/Audio/`, `tools/make_sfx.py` |
| Art made outside Unreal | | `Art/Blender/`, imported by the level owner |
| Devlog, video, submission | Team Owner | `docs/DEVLOG.md`, the zip |
