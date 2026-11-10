# How we work (read this first)

A five-minute overview for anyone joining the team. You don't need to know Git or Unreal well: **almost everything
here is done by asking Claude** in a chat opened on the repo folder. The sentences in quotes are things you can say.

## 1. Each computer has one job
Unreal files (`.uasset`, `.umap`) are binary: if two people change the same one, one person's work is lost. So we
split the work by **computer**, in the **Computers** table in [`TEAM.md`](TEAM.md):

| Role | What it does | Typical computer |
|---|---|---|
| **builder** | The only one that changes the game in Unreal. Fixes playtest issues, publishes test builds. Exactly one. | A Windows PC with Unreal open |
| **maker** | Makes things outside Unreal: 3D models (Blender, Meshy, TRELLIS), sounds, scripts. The builder imports them. | Any PC or Mac |
| **tester** | Plays test builds and reports what's wrong as GitHub issues. | Any PC or Mac |

Claude checks the table at the start of every chat and only does what that computer's role allows.
- "Add this computer to the Computers table as a tester."
- "Make GameStation the builder." (Claude makes sure the old builder saved and pushed first.)
- "What's this computer's role?"

A Mac can be a tester or a maker, not the builder (the jam wants a Windows build, and a Mac can't make one).

## 2. The playtest loop
```
 testers play Build N  ->  file issues  ->  builder's Claude fixes them
        ^                                           |
        |                                           v
 reply "works"  <-  Build N+1 published, issues marked "ready-to-check"
```
- **Get the game:** "Get me the latest build." Windows downloads it from the repo's Releases (the link
  `.../releases/latest` always opens the newest build: bookmark it); a Mac pulls the
  `playtest` branch and you press Play in Unreal (never save).
- **Report:** "File an issue: on Build 14 the frog fell through the road, it breaks the game." Or use the
  **Playtest report** form on GitHub (Issues > New issue), also in the GitHub phone app. One problem per issue.
- **Check a fix:** issues labelled **ready-to-check** name the build with the fix. Play it, then reply `works` or
  say what's still wrong ("Issue 12 works").
- **On the builder:** "Work through the playtest issues." Confirmed fixes go into `main`, which closes the issues.

Full guide: [`PLAYTEST.md`](PLAYTEST.md).

## 3. Areas, so makers don't collide
"Who owns what" in [`TEAM.md`](TEAM.md) gives each person an area (UI, audio, art...). Stay in yours and ask before
touching someone else's. If one builder can't keep up, a second person can get `builder (UI)` and change Unreal files
in that area only.

Talking between Claudes on different accounts: the plan is a sync tool a friend made (to be set up). The backup,
GitHub issues as a mailbox and how to split the work, is in [`TEAM_SYNC_BACKUP.md`](TEAM_SYNC_BACKUP.md).

## 4. Git, the short version (Claude does this for you)
- Before working and before every commit: get the latest (`git pull --rebase`).
- Before changing an Unreal file: lock it (`git lfs lock`). If a teammate holds the lock, wait or make a new file.
- Commit small, tested changes under **your own name**; Epic may read our Git history. Untested work goes on a branch.
- Every change gets a devlog entry in [`DEVLOG.md`](DEVLOG.md): we're aiming for the Glass Box prize.

## 5. Rules that matter
- Before Nov 12 we may only prepare tools, scripts, prompts and settings. Gameplay, levels and art are made Nov 12-15.
- English only, suitable for ages 13+, no trademarks or logos (except Unreal's).
- Anything we didn't make goes in [`../CREDITS.md`](../CREDITS.md). Full rules: [`RULES.md`](RULES.md).

## Where to go next
1. Set up your computer: [`SETUP_TEAMMATE.md`](SETUP_TEAMMATE.md) (Windows or Mac).
2. Add your computer to the Computers table (step 6 there).
3. Read [`PLAYTEST.md`](PLAYTEST.md), then the game we're making: [`PITCH.md`](PITCH.md).
