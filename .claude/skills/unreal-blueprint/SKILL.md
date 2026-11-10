---
name: unreal-blueprint
description: Safe procedure for creating or editing Unreal Blueprints, functions, components and placed actors through the Unreal MCP (write_graph_dsl, execute_tool_script). Use before any Blueprint or level change in the editor.
---

# Editing Blueprints through the Unreal MCP

Follow these steps in order. Every one of them comes from a bug we actually hit.

## Before you touch anything
1. **Play mode must be stopped.** Editing or creating Blueprints during PIE froze the editor for good and lost all
   unsaved work. Check, and stop PIE first.
2. **Pull, then lock.** `git pull --rebase`, then `git lfs lock <file>`. Committed `.uasset`/`.umap` files are
   read-only until locked, and the editor's save silently does nothing. If `git lfs locks` shows a teammate has it,
   stop: tell the user who has it and offer a new asset instead. Check `docs/TEAM.md` for who owns the area.
   A brand-new asset needs a lock right after its first commit. (M Station spare runs: no locks, `attrib -r` instead.)
3. **Paths:** `Content/Game/X` on disk is `/Game/Game/X` in MCP calls. Put new content under `Content/Game/<Type>/`
   with `BP_`, `M_`, `MI_`, `WBP_`, `SFX_` prefixes.
4. **Find every place the thing is built.** One Blueprint can be set up in more than one place (`BP_Log`: its
   construction script for placed logs *and* `LogSetup` for Endless spawns). Search for callers first.
5. **Back up the graph:** `read_graph_dsl` the function you're about to replace. `write_graph_dsl` replaces the whole graph.

## Writing the graph (write_graph_dsl)
- **Unique function names**, across the engine and our project (never `Clear`, `SetTime`, or a second `SpeedUp`).
  Otherwise the tool quietly calls the wrong function and it still compiles.
- Never `(return (OurFunction ...))`: the call never runs and you get the default value. `bind` the call, then `(return x)`.
- Pure nodes re-run on every read. Don't `bind` a value, set its source variable, then read the bind again. Read the variable.
- Actor calls need named pins: `SetActorLocation :NewLocation v`, `SetActorRotation :NewRotation r`. A positional
  argument lands in `self`.
- The reader prints literals as `(bind _x 1.0)`, and the writer rejects that: fold literals back into the expressions.
  A `b`-bool prints as `(|GetbIsHopping)`, but you write `Variables|Default|GetIsHopping` / `SetIsHopping`.
- The tool can't attach code to Enhanced Input events or make Timelines. Put logic in a function, ask the user to wire
  the input event to it by hand, and animate with Event Tick.
- When two classes share a node name (Set Volume Multiplier on Audio vs Synth), check the node's class and fix it with
  `retarget_node_class`, then reconnect its pins.
- `IsValid` has two versions; make sure you got the one you meant (one silently deleted the honk).
- After deleting a function, **compile before** re-adding one with the same name, or it becomes `Name_0`.

## After writing
1. **Compile, then `read_graph_dsl` and compare** with what you meant. "It compiled" isn't "it works".
2. **Save now**, after every batch, not at the end. Then `git status` to confirm the file really changed.
3. After a component change, look at one copy **already placed in the level**. If it's stale, re-place the actors with
   their full transforms (`set_actor_transform` resets any part you leave out).
4. Test both maps if the Blueprint is used in both (story and `Lvl_Endless`).

## Patterns that work (from the Deep Archive HD-2D test, Nov 8-9)
- **Keys and gamepad without hand-wiring:** in Event Tick (or a function it calls), poll
  `Game|Player|IsInputKeyDown` (`:Key "W"`) and `Game|Player|GetInputAnalogKeyState` (`:Key "Gamepad_LeftX"`) on
  player controller 0. No Enhanced Input event to wire by hand, so Claude can build the controls completely.
- **The player pawn:** setting a Blueprint game mode's `DefaultPawnClass` from Python reads back right, but Play mode
  still spawned Unreal's grey sphere. Place the pawn in the level with `auto_possess_player = PLAYER0` instead.
- **Overriding a parent function that has no outputs:** it's an event. `add_event(bp, 'Name')`, then write it in the
  EventGraph as `(event EventName ...)`. `(|Parent:Tick ...)` can't be written: leave Tick/BeginPlay out of the
  child's DSL and the parent's still run.
- **Defaults that stick:** `ObjectTools.set_properties` on `/Game/.../BP_X.Default__BP_X_C` (class defaults) and
  `/Game/.../BP_X.BP_X_C:Comp_GEN_VARIABLE` (an added component).
- **A level actor's component:** `(Actor|GetComponentbyClass :self actor :ComponentClass "/Script/Engine.SkyLightComponent")`.
  Class-specific getters like `Class|SkyLight|GetLightComponent` quietly became other classes' nodes. Every Character
  already has an empty `Mesh` component, so look components up by **name**, not by class.
- **Spawning from a graph:** `(Game|SpawnActorfromClass "<class path>_C" transform "AlwaysSpawn" "MultiplyWithRoot")`,
  4 inputs. The reader prints `SpawnActorBPName ... 0 0`, which the writer rejects.
- **Testing a live actor:** Python and `set_properties` can't set a Blueprint variable on an actor in Play mode
  ("cannot be edited on instances"). Give the Blueprint a small function (`JumpTo`) and call it with
  `actor.call_method('Name', (value,))`. Freeze time with `set_global_time_dilation(world, 0.0001)` to capture an
  effect at an exact moment; slowed time and waits kept missing it.
- **Long graph texts:** save them to `Saved/*.json` and read them inside `execute_tool_script` with
  `AssetTools.read_file` (`file_path`) instead of pasting them into the call.
- **Rebuild a material in place** with `MaterialEditingLibrary.delete_all_material_expressions(m)` and new nodes, not
  by deleting the asset: post-process volumes and Blueprints keep pointing at it.
- **Effects without Niagara:** `Art/Blender/fx3d_kit.py` (shapes) + `tools/unreal_make_fx3d.py` (fire, sparks, smoke,
  beam materials). Masked + Unlit materials with the noise in Custom HLSL nodes (Custom-node code can't declare
  functions: put them in a local `struct`). Pass age or burn through custom primitive data. Keep emissive at
  1.5-2.5 (3-4 with default bloom hazed the whole screen) and colours saturated (the tonemapper washes orange to cream).
- **Light levels:** with a 6-lux sun, effect lights must be tiny (12 cd per beam light, 5 cd for a glow). 140 cd
  turned the screen white.
- **A closer camera:** zoom the lens (raise focal length and aperture together) instead of shortening the boom, when the
  cine camera's focus is set by hand. A shorter boom blurred the whole picture.
- **Paper2D sprites and flipbooks** can't be made through the MCP: write an Unreal Python script under `tools/`, run it
  with `py <path>` in the console box, and have it write its result to `Saved/`.
- **Characters fall forever** when the floor is only a picture: give it an invisible collision box.
- **Ground cover:** never hundreds of separate grass tufts. Bake blades into 3 m carpet tiles in Blender and turn or
  mirror them: far fewer actors, much denser grass.
- **Never `duplicate_asset` a map and then open the copy:** the editor crashed ("Old world ... not cleaned up").
  Copy a level with `EditorLoadingAndSavingUtils.save_map(world, path)` (Save As) from the open level.
- Saving dirty packages after making child Blueprints also re-saved the parents: `git restore` the ones that didn't change.
- **On the builder only:** a fresh clone makes every committed asset read-only until it's locked. Instead of locking
  everything, the builder may clear the flag on its own content folder
  (`Get-ChildItem -Recurse -File <Project>\Content\Game | % { $_.IsReadOnly = $false }`); teammates still lock.

## Calling the MCP
- `mcp__unreal__call_tool` needs `toolset_name` **and** `tool_name`.
- Batch many calls into one `execute_tool_script`. Never `time.sleep` inside it (it freezes the game thread).
- `ObjectTools.get_properties` takes exact names. Never build names by splitting `list_properties` text (a 2,000-char
  "name" crashed the editor).

## Hand over to the humans
Claude can't press keys in Play mode. Tell the user exactly what to test (which key, what should happen), and wait
for "it works" before committing. Then use the `devlog-entry` skill.
