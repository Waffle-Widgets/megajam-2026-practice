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
and to lock files). Members on their own only get read access. When the jam repo is made, give Jam Team write on it
too (repo Settings > Collaborators and teams). Each new person needs a paid seat on the org first.

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
