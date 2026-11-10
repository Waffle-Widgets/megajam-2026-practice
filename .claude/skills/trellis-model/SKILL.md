---
name: trellis-model
description: Make a game-ready 3D model (vehicle, prop, character or animal) from a picture with the local TRELLIS.2 generator, then clean it up in Blender and export FBX + textures for Unreal. Use when the user wants an AI-generated model, or a reference picture made locally (tools/gen_images.py).
---

# Picture -> TRELLIS.2 -> cleaned FBX

TRELLIS.2 lives in `D:\AI\TRELLIS2` (main PC / M Station) or `C:\AI\TRELLIS2` (GameStation). Its Windows port is
patched: never `git pull` it. The owner's Hugging Face login must be on the PC (gated image encoder).

## 1. The picture decides the model
- The generator only knows what the photo shows. Whole object in frame, 3/4 angle, a little height, plain background.
- **Fix the photo, not the mesh.** Flatten paint reflections first (`tools/deflect.py`) or use a studio shot;
  reflections become raised plates on the model.
- Cut the background out: `venv\Scripts\python.exe tools\cutout.py <photo> <cutout.png> [boxes to paint over, e.g. plates]`.
- Characters/animals: ask Gemini (in the user's Chrome) for the full body on plain white; people in an A-pose with
  gaps between arms and body. Take the **newest** file in `~/Downloads`, never one picked by filename pattern.
- **Or make the picture locally** (M Station, no copy-paste): `python tools/gen_images.py --text "<prompt>" --name
  <Name> --takes 4`. It starts ComfyUI (`C:\Users\thecl\ComfyUI`, Qwen-Image, Apache 2.0) and saves takes to
  `Art/Refs/gen/`. Prompts: short, plain and positive; say the style once; describe shapes, because it reads words
  literally ("tower shield" drew a tower). Put unwanted things in `--neg`. `--ref <picture>` (up to 3) draws from a
  style reference. Close it before a TRELLIS run: both want the GPU. Credit it as AI-generated (ours, scored).
- **Start new designs from pictures, not words** (Coreatures): designs drawn from words alone took rounds of "looks
  pretty bad"; ones from the owner's pictures landed fast. Ask for a picture first, and when asked to improve a
  design, keep it and raise the detail instead of redesigning.
- Several views of one object can be blended: pass `front.png,rear.png` (comma-separated) in one run.
- Note where the picture came from for `CREDITS.md`.

## 2. Generate
Close Chrome and other GPU users (peaks near 17 GB VRAM). From the TRELLIS folder:
```
venv\Scripts\python.exe run_image_to_3d.py <cutout.png>[,<view2.png>] out\<name> 1024_cascade
```
About 5 minutes on the 3090. Env: `DEC=30000 TEX=2048` for characters (cleaner than decimating later),
`SEED`. Furry animals: use `512` instead of `1024_cascade`.

## 3. Clean up (headless Blender)
- **Vehicles:** `blender -b --factory-startup --python Art/Blender/trellis_vehicle.py -- "<json>"` (settings in the
  file header: GLB, OUT, REAL size in metres, BACK, GLASS_Z, paint options). Look up the real length/width/height first.
- **Characters/animals:** `blender -b --factory-startup --python Art/Blender/trellis_character.py -- <glb> <Name> human|dog <height_m>`,
  then `Art/Blender/walk_cycle.py <Name> human|dog` for a walk.
- Other props: borrow from `Art/Blender/ai_car_clean.py` (`import_trellis`, `bake_maps`, `fill_gaps`, `smooth_body`).

Rules that apply to any AI mesh:
- Weld (`remove_doubles(dist=1e-5)`) before decimating; smooth, then decimate, then transfer smooth normals.
- Move points only along their normals when smoothing a textured mesh. Never `recalc_face_normals` on the whole mesh.
- Throw away the generator's UV atlas: `smart_project`, bake its texture selected-to-active with margin 8, mipmaps on.
- Tag bmesh faces in an int layer; indices are reused after a delete.

## 4. Check before handing over
- Compare the measured size with the real object (the BRZ was 15% too wide).
- Render each wheel from a low side angle; render the four-view sheet the script writes to `Art/Blender/cache/`.
- Show the user the renders, then hand over with the `asset-import` skill. Judge the final look from the game camera.

## Jam rule
Before Nov 12, generated models are practice only. During the jam they count as our own (scored) art.
