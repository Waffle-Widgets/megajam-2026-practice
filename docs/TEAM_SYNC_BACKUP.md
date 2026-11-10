# Backup plan: splitting work between two Claude plans, and syncing through GitHub

Saved 2026-11-09. **Not set up.** The Team Owner plans to use a sync tool a friend developed instead. Use this plan
if that tool doesn't work out. Ask Claude: "set up the backup team sync plan".

## Splitting the work (works with any sync tool)
Split by computer and role (Computers table in `docs/TEAM.md`), which also splits the Claude usage:
- **Team Owner, GameStation (builder):** everything in Unreal: gameplay Blueprints, the level, importing assets,
  fixing playtest issues, publishing builds. The heaviest Claude use (graph edits, captures).
- **Justin, Mac (maker + tester):** what can be made outside Unreal:
  - 3D characters and props on Meshy's website, including rigging there (Claude in his Chrome drives it).
  - Blender cleanup and bakes with our scripts (they run on a Mac).
  - Sounds and music with `tools/make_sfx.py` (plain Python).
  - UI text, the devlog, the trailer script and video, playtest reports.
- **Team Owner, M Station:** GPU-only work Justin's Mac can't do: TRELLIS.2 and `tools/gen_images.py`.

GameStation and M Station share the Owner's Claude plan, so they share one usage limit. Justin's plan is the
separate capacity: give it the long jobs that don't need Unreal, so both plans work at the same time.

## Syncing: GitHub issues as a shared mailbox
Chats on different Claude accounts can't message each other (the Owner's own PCs can). Both Claudes can reach GitHub
under their own accounts, so:
1. **A "Hand-off" issue form** (`.github/ISSUE_TEMPLATE/handoff.yml`) and a `handoff` label. Fields: who it's for,
   which computer (the Owner's PCs share one GitHub account), what's ready or needed, which files, what done looks like.
   Example: "SK_Toshi rigged, FBX in Art/Blender/export/Characters/Toshi: please import and use as the player."
2. **Assigned to the person who should act**, so it shows in their GitHub notifications and phone app.
3. **Inbox check at the start of every chat** (added to CLAUDE.md's "Which computer am I on?"):
   `gh issue list --label handoff --assignee @me --state open`. Claude says what's waiting and offers to start.
   After pushing something for the other side, Claude opens a hand-off.
4. **A `team-sync` skill:** "check my inbox", "send this to Justin", "what's Justin working on?"
   (open hand-offs and recent commits by him).
5. **Optional:** the builder's `/loop 10m /playtest-issues` also picks up hand-offs.
6. A short section in `docs/HOW_WE_WORK.md`, then a test with a fake hand-off.

## Needed first, whichever tool we use
- Justin accepts his GitHub invite to Waffle-Widgets (allbarkdev), or his Claude can't see the repo or its issues.
- Justin's Claude adds his Mac to the Computers table (`hostname`).
