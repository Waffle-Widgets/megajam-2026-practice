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

## Calling the MCP
- `mcp__unreal__call_tool` needs `toolset_name` **and** `tool_name`.
- Batch many calls into one `execute_tool_script`. Never `time.sleep` inside it (it freezes the game thread).
- `ObjectTools.get_properties` takes exact names. Never build names by splitting `list_properties` text (a 2,000-char
  "name" crashed the editor).

## Hand over to the humans
Claude can't press keys in Play mode. Tell the user exactly what to test (which key, what should happen), and wait
for "it works" before committing. Then use the `devlog-entry` skill.
