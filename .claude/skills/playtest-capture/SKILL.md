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
