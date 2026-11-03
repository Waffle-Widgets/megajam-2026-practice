# Project notes for Claude Code

## Read these first
- `docs/PLAN.md` — the team plan, schedule, and rules of thumb
- `docs/PITCH.md` — the game we're making (filled in after the theme reveal)
- `docs/RULES.md` — the official jam rules we must follow
- `CREDITS.md` — every asset we didn't make ourselves

## Who we are
- A two-person team entering the 2026 Epic AI MegaJam (Nov 12-15).
- **This repo is our practice/setup sandbox, not the jam entry.** We're learning the tools and running practice jams here.
  When we discover a better way to work, suggest updating this CLAUDE.md so the improvement carries into the real jam repo.
- We are beginners: we play a lot of games but have little coding or Unreal experience.
- We act as game designers and testers. You do the implementation.

## Engine and project
- Unreal Engine 5.8, connected to you through Epic's Unreal MCP plugin.
- C++ project, but build gameplay in **Blueprints** unless C++ is truly required. Ask before writing C++.
- Target platform: Windows.

## How to work with us
- Make **one small change at a time**, then stop and tell us exactly what to test in Play mode.
- Explain every change in plain language: what you made, where it lives in the Content Browser, and why.
- Before a big or risky change, tell us the plan and wait for "go".
- If something fails, tell us the actual error and your best guess at the cause. Don't silently retry many times.
- Once we confirm a feature works in Play mode, save all assets in the editor, then commit and push to GitHub yourself
  with a short plain-language message. Tell us what you committed. Don't commit work we haven't tested.
- We often prompt you remotely from another machine, so send screenshots of the editor or results when they help us follow along.
- Keep the project tidy: put our content under `Content/Game/` in folders by type (Blueprints, Maps, Materials, Audio, UI).
- Use clear names: `BP_` for Blueprints, `M_` for materials, `MI_` for material instances, `WBP_` for widgets, `SFX_` for sounds.

## Lessons from practice (Unreal + MCP)
- **Lock before you edit.** Git LFS marks committed `.uasset`/`.umap` files read-only. Run `git lfs lock <file>` before changing
  an asset that's already committed, or the editor's save silently does nothing. After pushing, `git lfs unlock <file>`.
  Check `git status` after saving to confirm the file really changed.
- `Content/Game/` on disk is `/Game/Game/...` inside Unreal (and in MCP tool paths).
- A child Blueprint's input event does **not** replace the parent's. To stop the template character walking, override the
  parent's `Move` event with an empty one in the child.
- Claude can't send keyboard input into Play mode, so it can check that things compile and spawn, but **we** test movement and feel.
- The Blueprint graph tool (`write_graph_dsl`) can't attach code to Enhanced Input events or create Timelines. Put logic in a
  function, then wire the input event to it by hand; use Event Tick instead of a Timeline.
- **Never edit while Play mode is running.** Stop PIE first. Creating or editing Blueprints during PIE froze the editor
  for good and lost all unsaved work. Also **save after every batch** of changes, not at the end.
- Reset the input mode to "game only" when a level starts; "UI only" from an end screen survives a level reload.
- After deleting a Blueprint function, compile before re-adding one with the same name, or it becomes `Name_0`.
- Changing a Blueprint's components doesn't always update copies **already placed in the level**. After a component
  change, check one placed copy; if it's stale, re-place the actors (keep their transforms and settings).
- Blueprint "pure" nodes re-run every time they're read. Don't `bind` a value, then set the variable it came from and read
  the bind again (the goal count got +1 twice). Read the variable after setting it instead.
- Batch many MCP calls into one `execute_tool_script` (sandboxed Python) to save round trips. Don't `time.sleep` inside
  it; that freezes the game thread. Wait outside instead.
- With "prompt before auto-importing" off (Editor Preferences > Loading & Saving), `.wav` files dropped into or changed in
  `Content/` import by themselves within seconds, even while the editor is open. Save the new asset afterwards.
  `tools/make_sfx.py` generates our sounds and music from code: no downloads, no credits needed.
- Night scenes need fixed exposure (post-process Metering Mode = Manual), or auto-exposure brightens night back to day.
- **Lock new assets right after their first commit.** Committing makes them read-only, and the next save fails silently.
- `set_actor_transform` resets any part you leave out (location, rotation or scale). Always pass the full transform.
- When two engine classes share a node name (e.g. Set Volume Multiplier on Audio vs Synth components), the DSL may pick
  the wrong one. Write it, then use `retarget_node_class` and reconnect its pins.
- Give every Blueprint function a name that is unique across the engine **and** our project (not Clear, SetTime, or a
  second `SpeedUp`). Otherwise the graph tool quietly calls the wrong one and it still compiles. Always `read_graph_dsl`
  after writing to check what was really built.
- **Packaging a Windows build** (about 4-5 minutes, works with the editor open). First set `GameDefaultMap` in
  `Config/DefaultEngine.ini` to our level. Then run `RunUAT.bat BuildCookRun -project=<uproject> -platform=Win64
  -clientconfig=Shipping -build -cook -stage -pak -archive -archivedirectory=<repo>/Builds -unrealexe="<UE>/Engine/Binaries/Win64/UnrealEditor-Cmd.exe"`.
  Without `-unrealexe`, the cook step fails looking for `MegaJamPracticeEditor.target`. When only Blueprints/assets
  changed, use `-skipbuild` instead of `-build`. With the editor open, `-build` fails trying to recompile the editor. `Builds/` is gitignored. Don't
  save assets while it cooks.
- Turn off "Use Less CPU when in Background" (Editor Preferences) so Play mode runs at full speed while Claude tests it.

## Switching computers
We work on more than one PC. Only one machine should have the project open at a time. You can only act on the PC
this session runs on, so the session on each machine handles its own side.
- **"I'm leaving this computer":** check every asset under `/Game/Game` is saved (`is_dirty`), make sure tested work is
  committed and pushed (ask about anything untested), release our LFS locks (`git lfs locks`), then close Unreal. If it
  stalls on a save prompt for a template asset we never meant to change, force-close it, but only after confirming our
  own assets are clean and pushed.
- **"Let's work on this computer":** `git pull` (LFS brings the assets), open `MegaJamPractice/MegaJamPractice.uproject`
  in UE 5.8, wait until the Unreal MCP at `http://127.0.0.1:8000/mcp` answers, then tell us it's ready.

## Scope guardrails
- The game should be one level, one core mechanic, 3-5 minutes of play.
- Push back if we ask for multiplayer, story/dialogue systems, inventories, complex enemy AI, or open worlds during the jam. Suggest a simpler version instead.
- Prioritize game feel (responsive controls, feedback, sound, juice) over feature count.

## Devlog (Glass Box)
- We're aiming for the Glass Box prize (best devlog showing how we built the game), so keep `docs/DEVLOG.md` going without being asked.
- After each change we test and you commit, add an entry using the template in `DEVLOG.md`: what we asked for, the actual prompt,
  what happened (including failures, retries and dead ends), and what we learned. Commit it with the change.
- Log setup problems and things that broke too, not just successes. Those are the most useful parts.
- When the editor is open, save a screenshot to `docs/media/` and link it from the entry.

## Assets and credits
- When we import an asset we didn't make (Fab, AI-generated, sound libraries), remind us to add it to `CREDITS.md` with its source and license.

## Jam rules to enforce
Full summary in `docs/RULES.md`. Warn us if a request would break one of these:
- Only tools, agent configs, MCP settings, prompts and scripts may be prepared before the jam. Gameplay, levels and art must be
  made between Nov 12 and 15, and Epic may check our Git history.
- Sourced assets (Fab, sound libraries) are allowed but not scored. Assets we make or generate with AI are scored, so prefer those.
- Everything in English, suitable for ages 13+, and no trademarks or logos except the Unreal Engine logo.
- The game must use the theme and go well beyond the Third Person template.

## The current game
See `docs/PITCH.md` for the current practice game. If it's empty, ask us what we're building before starting.
