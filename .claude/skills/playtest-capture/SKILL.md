---
name: playtest-capture
description: Take screenshots of the game as the player sees it (real lighting, game camera) and measure frame rate, so the remote user can follow along. Use to show results, judge art, check a change in Play mode, or debug the camera.
---

# Seeing the game the way the player does

The user often prompts from another machine, so send pictures (SendUserFile) whenever they help.

## Real game look
1. Save everything first (an exploratory call during PIE once crashed the editor).
2. `EditorToolset.EditorAppToolset` / `StartPIE` in **Simulate** mode.
3. Click the editor's **Pause** button with the Slate inspector.
4. `CaptureViewport` with a camera transform at the game camera's height and angle. Judge art only this way: the
   TRELLIS coupe looked great close up and like a dark blob from the game camera.
5. `CaptureEditorImage` during PIE shows exactly what the player's camera sees. Use it to debug camera problems
   (variables can look right while the picture shows the camera never moved).

## Full-size game-camera pictures (best for the devlog)
In one `execute_tool_script`: `StartPIE` (not Simulate), then `Type` `HighResShot 1920x1080` into the console box
(`SlateInspectorToolset.Type` works from inside the script). Wait **outside** the script for
`Saved/Screenshots/WindowsEditor/HighresScreenshot*.png`, then `StopPIE`. It shows the real camera, lens and
post-process at 1920 wide, without the editor around it.
- **After an editor restart, wait about 40 s for shaders** before capturing: a material still compiling shows as a
  grey smear.
- **To catch an effect at an exact moment,** freeze time (`set_global_time_dilation(world, 0.0001)`) and jump the
  effect to that moment with a small Blueprint function (`unreal-blueprint` skill, "Testing a live actor").

## Aim at a specific actor
In Play mode, `SceneTools.find_actors` with `actor_type` = the generated class (`BP_Car.BP_Car_C`) lists live actors.

## Frame rate
- Type `startfpschart`, play a while, then `stopfpschart` into the console box (Slate inspector); read the log.
- The `stat unit` overlay never shows in captures.
- 3 fps means the editor is throttling in the background: "Use Less CPU when in Background" must be off
  (`bThrottleCPUWhenNotForeground=False` in `Config/DefaultEditorSettings.ini`).

## Saving pictures
Save keepers to `docs/media/<short-name>.png` and link them from the devlog entry. Stop PIE when done, and never
edit Blueprints while it's running.

## What Claude can't test
Claude can't press keys in Play mode. Movement, feel and timing are the humans' job: say exactly what to try.
