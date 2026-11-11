---
name: niagara-fluids
description: Realistic fire, smoke and explosions with Unreal's Niagara Fluids (real-time simulation), tuned through the Niagara editor with the Slate inspector, and baked into flipbook textures so fast particles carry real fire. Use when the owner wants an effect to look real (not cartoon), when tuning a Grid3D gas/fire system, or when making a flipbook from a simulation.
---

# Realistic fire with Niagara Fluids (learned on the Deep Archive Fire Blast, Nov 11 2026)

Worked example: the Deep Archive HD-2D repo (`C:/Users/thecl/code/deep-archive-hd2d`, branch `gamestation/realistic-fire-blast`), `Game/FX/NS_FireBoomFluid3D` (explosion), `NS_FireBlastFluid3D` (flying fire),
`NS_FireBlastReal3D` (particle fireball whose Trail plays the baked fire), `Materials/MI_FireFluid3D`,
`Materials/M_FireFlipbook3D` (Deep Archive `tools/unreal_make_fire_flipbook_mat.py`: copy it into this repo's `tools/` to use it), the story with pictures in
`docs/realistic-3d-test.md` (`docs/captures/31_*`-`52_*`). Load `niagara-fx` too: captures, toolset calls and traps live there.

## What worked, what didn't
- **Explosion (stays in one place): Niagara Fluids is great.** Start from the plugin's `Grid3D_Gas_Explosion` template.
- **Fast projectile: a live fluid sim fails.** The grid moving with the ball either smears the fire into a streak/box
  (Compensate For Actor Motion on: the fire stays behind in the world, cut off at the grid edge) or, with it off, gives
  only a soft round puff. Ten rounds of source/swirl/wind tuning didn't fix it.
- **Procedural noise on round sprites always reads as puffs** from the game camera (size, count, ribbons all tried).
- **What finally looked real:** bake the explosion into a flipbook and play it on many small, long-lived trail
  particles (`M_FireFlipbook3D`): real billowing fire, burning from orange to dark red embers and smoke.
- A big, short-lived sprite (0.22 s) with the same flipbook flashes through the smoke frames: dark boxes. Only part of
  the bake (FrameStart/FrameEnd) doesn't help when those frames sit off-centre (the explosion starts at the ground).
  A head flame needs its own centred bake.

## Setting it up
- Enable the plugin in the `.uproject` (`"NiagaraFluids"`); restart the editor.
- Make the system from the plugin's template, then set its User parameters with the toolset (`GetUserVariables`,
  then `AddUserVariables` with changed defaults): `DrawBounds` (1 shows the grid as a red box: great for debugging),
  `ResolutionMaxAxis` (96 is plenty at game size), `WorldSpaceSize` (cm).
- The renderer material is reachable (`SetRendererData` index 1 `Material`); use a copy of `MI_3DGas_Base`
  (`MI_FireFluid3D`). Its **Use Colored Fire** switch split our explosion into quarters with hard seams: keep it off.
- **Everything inside the fluid emitter (simulation stages, Emitter Summary) is not reachable by the toolset**
  ("EmitterSpawnScript not found"). Edit it in the Niagara editor through the Slate inspector (below).

## Tuning in the Niagara editor through Slate
- Open the system yourself or ask the owner; it may be on another monitor (negative window positions are fine).
- Click the arrow at the top-left of the emitter node in the graph to show its full stack; select the emitter. The
  Details panel shows the Emitter Summary with group filters (Simulation / Source / Forces / Render / All).
- **Edit a number:** `Type` on the row's slider with empty text and submit opens its box; in the **next** call find the
  `textbox [focused]` (search the whole snapshot, `ref:''`, not one window), `PressKey Ctrl+A`, `Type` value with submit.
  Chain the next slider's open in the same call. If no focused box is found, **stop**: typing into whatever has focus
  set our camera width to 150 once.
- The panel is virtualised: rows below the visible area don't exist in the snapshot. Collapse groups above them
  (the arrow button next to a group name: Emitter, Particle Source) to bring them into view.
- The readouts lag behind what you typed. Read back after saving before retrying.
- Settings we used: explosion Render > Smoke Color (0.05, 0.04, 0.035), Density Albedo 0.1, Temperature Color Gain 3;
  Heterogeneous Volume Quality: Lighting Downsample 1, Shadow Step 1, Shadow Bias 0.1 (full detail). Gravity is world
  space: a "wind" from gravity only works for one flight direction.

## Baking a simulation into a flipbook (the Niagara Baker)
- Niagara editor toolbar > **Baker**. It opens a Baker tab: Live Sim, Baked Sim and Settings. Its settings are not
  readable from Python or `ObjectTools` (editor-only); drive it through Slate.
- Source Binding: open the list, type into its Search box (`Inv Opacity`) and submit: clicking list items didn't select.
  We used "SceneColor (HDR) in RGB, Inv Opacity in A". **The saved texture's A is opacity**, despite the name.
- Camera: the view dropdown > **Front** (orthographic); the eye dropdown has Camera Location, Rotation and
  **Orthographic Width**. Leave a margin: width 300 cut the explosion at the frame edges (square edges in game); 420 with
  Location Z 150 fit our 260 x 320 cm explosion.
- Time Range 0-1.6 s, Frames Per Dimension 8 x 8, Frame Size 256, Atlas 2048 (tick its box). Bake = the first toolbar
  button of the Baker tab. The result is `<System>_BakedAtlas_<OutputName>` next to the system (sRGB 8-bit, unsaved:
  save it with `AssetTools.save_assets`; `tools/unreal_find_new_assets.py` lists dirty packages).
- Play it with `tools/unreal_make_fire_flipbook_mat.py` (Translucent Unlit; frame = particle age x 64; colour = bake x
  particle colour x Glow; opacity = (A - 0.06) x particle alpha; FrameStart/FrameEnd params; makes `MI_FireFlipbookHead`).
- Saving the system also stores its Baker settings, so the next bake starts from them.

## A centred head bake (the fireball head, Nov 11, M Station)
- Bake a fire that burns **in place** (source at the centre, Velocity 0) and let its heat lift the flames: a teardrop
  with the ball at the bottom. On the projectile, turn the sprite so the frame's top points backward (renderer
  Alignment Custom + Face Camera, `Particles.SpriteAlignment = -normalize(Engine.Owner.Velocity)` at spawn) and put the
  pivot on the ball (`PivotInUVSpace` y about 0.72). It reads as a comet head from every angle.
- Make the grid tall enough for the flames (`User.WorldSpaceSize` z 440 for a 50 cm source): a short grid flattens them
  against its ceiling into a hard line. `AddUserVariables` works while the system's editor is open.
- Fill the frame: a wide ortho camera wasted most of each 256 px frame. Ortho 260, Location Z 60 put the ball low and the
  flames up to the top; fade the cut tips in the material (`EdgeFade`) and drop dark smoke (`DarkCut`).
- See the bake without opening the texture editor: `RenderingLibrary.export_texture2d` writes a Radiance HDR (no alpha)
  whatever the extension; decode RGBE with numpy. `AssetExportTask` has no PNG exporter for these textures.
- The Baker's number boxes appear in the Slate snapshot only on the next call after opening them; check the focused box's
  position before typing, or the value lands in the previous box.

- **A trail playing the whole explosion bake turns into a dark lumpy cloud** (its last frames are smoke). Give the trail
  its own instance that plays only the burning frames (FrameStart 0.05, FrameEnd 0.6, DarkCut 2.5: `MI_FireTrail3D`), a
  short life (0.5 s) and a taper: hot flames that cool to red and fade, like a comet (Nov 11, `docs/captures/56_*`).

## Traps
- `/NiagaraFluids/Materials/Grid3D/M_3DGas_Base` shows as unsaved after tuning: it's the plugin's, never save it.
- Lock new assets after their first commit (bake texture, materials), or the next save silently does nothing.
- Judge from the game camera **and** the side (`unreal_capture_megabeam.py <sec> side FireFireBlast`).
