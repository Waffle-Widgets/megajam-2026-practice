# Setting up a second work PC (GameStation)

Everything below is tooling, so it may be prepared before the jam. Gameplay, levels and art wait for Nov 12.
The order matters: Unreal and Blender first (they are needed for every task), the AI generator last (only needed
for car/prop generation, and only one PC needs it at a time).

## 1. Repo, Unreal and Blender (about 30 minutes)

1. Install Git and Git LFS, then `git clone` this repo. `git lfs pull` brings the assets.
2. Install Unreal Engine 5.8 and the Unreal MCP plugin (the one that serves `http://127.0.0.1:8000/mcp`).
   Open `MegaJamPractice/MegaJamPractice.uproject`; it compiles the C++ project on first open (10-20 min).
3. Blender 5.2 LTS + Blender's MCP add-on, `uv`, and the `blender_mcp` clone. Steps and the `.mcp.json` path
   to fix are in `CLAUDE.md` under **Blender**.
4. Create `.claude/settings.local.json` with `{"enableAllProjectMcpServers": true}` so both MCP servers load.
5. Editor Preferences (see `CLAUDE.md` lessons): turn off "Use Less CPU when in Background", turn off
   "prompt before auto-importing", and `Config/DefaultEngine.ini` already disables the Interchange import dialog.
6. Open Unreal and Blender from the Start menu (not from a chat), click **Start** on Blender's MCP panel, then
   start a new Claude Code session so it finds both servers.

Only one PC should have the Unreal project open at a time (see **Switching computers** in `CLAUDE.md`).

## 2. Image-to-3D generator: TRELLIS.2 (about 1 hour if copied, about 3 hours if rebuilt)

TRELLIS.2 (Microsoft, MIT licence) is officially Linux-only; our Windows port lives in `D:\AI\TRELLIS2` on the
main PC. It needs an NVIDIA GPU with 24 GB (a 3090 is the minimum we have tested; generation peaks around
17 GB plus whatever else is open, so close Chrome, Unreal and anything else that holds VRAM before a run).

### Option A: copy the working folder (preferred)
The venv is tied to its absolute path, so keep the same drive letter and path.
1. Copy `D:\AI\TRELLIS2` (venv with PyTorch + the five compiled CUDA extensions, the patched `TRELLIS.2` clone,
   `run_image_to_3d.py`, `export_glb.py`, `build_ext.py`) to `D:\AI\TRELLIS2` on GameStation. About 20 GB.
2. Copy `D:\AI\hf_cache` (model weights, about 16 GB) to the same path, or let the first run download them.
3. The compiled extensions target compute capability 8.6 (RTX 30 series). An RTX 40 card runs them as they are.
   For anything else, rebuild each extension: `venv\Scripts\python.exe build_ext.py <ext>` after editing
   `TORCH_CUDA_ARCH_LIST` in `build_ext.py`. Rebuilding needs Visual Studio 2022 Build Tools (C++ workload) and
   the CUDA 12.9 toolkit installed.
4. Install the NVIDIA driver that matches CUDA 12.9 (any recent Game Ready driver works).
5. Hugging Face login on that PC: `venv\Scripts\hf.exe auth login` with the owner's token (the DINOv3 image encoder is
   gated; the owner has accepted its licence). Never paste the token into a chat.
6. Test: `venv\Scripts\python.exe run_image_to_3d.py in\<cutout>.png out\test 1024_cascade` (about 5 minutes).
   `out\test.glb` is the result. The GLB bake runs in its own process (`export_glb.py`); if it runs out of memory,
   `python export_glb.py out\test 2048 250000` retries it with a smaller texture and mesh.

### Option B: rebuild from scratch
Follow the notes in `docs/DEVLOG.md` ("The owner's real car, part 2"): clone TRELLIS.2, create the venv with
PyTorch for CUDA 12.9, `pip install triton-windows transformers==4.57.1 "huggingface_hub<1.0" xformers rembg
onnxruntime`, apply the three Windows patches (`segment_reduce` replacement in `trellis2/modules/sparse/basic.py`,
`.template data_ptr<T>()` in FlexGEMM, integer casts in o-voxel), then build the extensions with `build_ext.py`.
Budget three hours.

## 3. The car pipeline (scripts in this repo)

| Step | Script | Where it runs |
|---|---|---|
| Cut the photo out, hide plates/decals | `rembg` in the TRELLIS venv (`tools/cutout.py`) | PowerShell |
| Flatten paint reflections | `tools/deflect.py <cut.png> <out.png> <look.jpg> 0.25` | PowerShell |
| Generate the model | `D:\AI\TRELLIS2\run_image_to_3d.py` | PowerShell, 5 min, GPU |
| Build the game mesh from a GLB | `Art/Blender/trellis_build.py` (then `trellis_bake_texture.py`) | Blender MCP |
| Join two models (front photo + rear photo) | `Art/Blender/trellis_join.py` | Blender MCP |
| Import into Unreal, LODs, swap into `BP_Car` | the Unreal snippet in `docs/DEVLOG.md` part 3 | Unreal MCP |

Rules we learned the hard way (details in `CLAUDE.md`):
- The generator only knows what the photo shows. Use photos with the **whole car in frame**, from a 3/4 angle and
  a bit of height so the roof is visible. A photo that clips the roof gives a mesh with strips hanging under it.
- Paint reflections become raised plates on the model. Flatten them first (`deflect.py`); studio photos need no flattening.
- One photo gives one good end. A front-3/4 photo invents the rear and vice versa; join two models for both ends.
- Bake the generator's own texture onto clean UVs instead of painting outlines by hand.

## 4. Splitting work between the two PCs

- Unreal project: one PC at a time (LFS locks). Hand over with "I'm leaving this computer".
- Generation and Blender cleanup can run on the PC that does not have the project open; the result that crosses
  over is an FBX in `Art/Blender/export/` plus the three textures in `Content/Game/Imported/Cars/`
  (commit them, pull on the other side, import with the Unreal snippet).
