---
name: asset-import
description: Import a mesh, texture, character, animation or sound into Unreal through the MCP without freezing the editor or losing materials. Use whenever an FBX, PNG or WAV from Blender, TRELLIS, Meshy or tools/make_sfx.py has to go into the Unreal project, including rigging a Meshy character or baking a Meshy prop.
---

# Importing assets into Unreal

## Pick the route
| What | How |
|---|---|
| Static mesh, plain textures | Save under `Content/Game/Imported/<Name>/`, then `StaticMeshTools.import_file` / `TextureTools.import_file` (no window ever opens). |
| Mesh that relies on **vertex colours** (flowers, leaf shading) | Copy the `.fbx` into `Content/Game/Imported/<Name>/` and let Interchange auto-import it. The MCP importer drops vertex colours. |
| Character + skeleton + animation | Copy the FBX into its **own new folder** and let Interchange auto-import mesh, skeleton and animation together. Never `SkeletalMeshTools.import_file` onto an existing skeleton (it crushed the man). |
| `.wav` sounds | Drop into `Content/Game/Audio/`; they auto-import within seconds. Save the new asset. |

## Meshy models (from the Deep Archive HD-2D test)
- **Rig and animate on Meshy's website, free on our plan** (Animate tab): Humanoid, Quadruped Dog (comes with a dog
  walk) or Smart Rig (beta, any shape, no animation library). Place the markers **by hand with Symmetry off** (the
  automatic ones sat off-centre). Humanoid failed twice on a chibi with a big tail; Smart Rig worked. Upload (top
  right) takes our own GLB.
- **Then:** `blender -b --factory-startup --python Art/Blender/meshy_character.py -- <rigged.glb> <Name> dog|smart
  <height_cm> [tris] [original.glb]` makes `Art/Blender/export/Characters/<Name>/SK_<Name>.fbx` with Walk and Idle,
  30k triangles, fresh UVs and the colour baked from the full-detail model. Copy that folder into
  `Content/Game/Imported/` (the Character route below).
  - Meshy's dog walk **shrinks the Hips bone to 0.681**, so the walking dog came out at 68% size; the script undoes it.
  - Before measuring a rig, reset the pose bones: taking the action off leaves them in its last pose.
- **Props:** `blender -b --factory-startup --python Art/Blender/meshy_prop_bake.py -- <in.glb> <Name> <size_m>
  height|width <tris> [voxel_m] [pole_height_m]` gives real size, few triangles and a clean baked texture
  (`PROP_PIXEL=1` for a chunky pixel texture). Pass a voxel size (e.g. 0.04) for leafy models made of thin shells,
  which otherwise decimate into spikes and bake black.
- **Never decimate a Meshy model and keep its UVs:** its atlas is hundreds of tiny islands that show as pale scratches.
  Smart-project new UVs and bake from the original (the scripts do this, in REST pose with the deform on).

## Before importing
- **An FBX that brings its texture's PNG along** pops a modal "convert this import to a re-import?" box that freezes
  the MCP (the game thread stops, so Slate tools can't reach it). Find it with Win32 `EnumWindows` (title "Message"),
  look at it with `PrintWindow`, and press Enter for Yes. Copying a changed FBX over the old one later re-imports by
  itself with no prompt, but the material slots reset.
- **Free the memory.** Import 4096 textures one per call (three at once crashed the editor). If Blender has run a long
  session, save and restart it first: its undo history can hold 100 GB of committed memory.
- **Check the file really is what its name says.** A `.png` that "produced no assets" may be WebP (`RIFF....WEBP` in
  the first bytes; TRELLIS packs WebP). Re-save as a real PNG.
- **Replacing an asset:** the import never overwrites. Run `AssetTools.get_referencers` first, delete the old asset
  (`attrib -r` the file first if it was unlocked), import, then re-point every referencer.
  Material parameter defaults count: `M_CarMasked`'s three `TextureSampleParameter2D` nodes need `Texture` set again,
  then `MaterialTools.recompile`, or the cars go grey.

## After importing
1. **Never delete the source file** in `Imported/`: Unreal opens a modal "Delete Assets" dialog that freezes the MCP.
   Sources there are gitignored. (If the dialog appears anyway: Escape keeps the assets.)
2. Interchange auto-imports: re-point the slots at our materials, delete the empty placeholder `M_*` materials it made,
   and **switch Nanite off** (`set_nanite_enabled false`), then check `get_triangle_count` matches the source.
   Nanite dropped every petal.
3. Check the bounds: Blender +Y becomes Unreal **-Y** with our FBX settings. Rotate in the Blueprint only after checking.
4. Don't re-import a mesh once it's set up (it resets the materials).
5. Judge it from the game camera (`playtest-capture` skill), not in a close-up.
6. Save, and if it isn't our own work, remind the user to add it to `CREDITS.md` with source and licence.
   Jam rule: sourced assets aren't scored; ours and AI-generated ones are.

## Who imports
Whoever owns that area in `docs/TEAM.md` imports it and commits the `.uasset` (lock first). Someone making art outside
Unreal commits the FBX/PNG and hands over the asset names, folders and slot-to-material notes. On the Team Owner's two
PCs, GameStation imports and M Station never commits `.uasset`.
