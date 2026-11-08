---
name: asset-import
description: Import a mesh, texture, character, animation or sound into Unreal through the MCP without freezing the editor or losing materials. Use whenever an FBX, PNG or WAV from Blender, TRELLIS or tools/make_sfx.py has to go into the Unreal project.
---

# Importing assets into Unreal

## Pick the route
| What | How |
|---|---|
| Static mesh, plain textures | Save under `Content/Game/Imported/<Name>/`, then `StaticMeshTools.import_file` / `TextureTools.import_file` (no window ever opens). |
| Mesh that relies on **vertex colours** (flowers, leaf shading) | Copy the `.fbx` into `Content/Game/Imported/<Name>/` and let Interchange auto-import it. The MCP importer drops vertex colours. |
| Character + skeleton + animation | Copy the FBX into its **own new folder** and let Interchange auto-import mesh, skeleton and animation together. Never `SkeletalMeshTools.import_file` onto an existing skeleton (it crushed the man). |
| `.wav` sounds | Drop into `Content/Game/Audio/`; they auto-import within seconds. Save the new asset. |

## Before importing
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
