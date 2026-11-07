# Pixal3D on Windows (GameStation, RTX 5090)

Pixal3D (Tencent ARC, MIT, May 2026) is an image-to-3D model built on TRELLIS.2. We tried it in the Nov 7 bake-off;
TRELLIS.2 stayed our main tool (see docs/DEVLOG.md). These files let it be set up again.

Setup (`C:\AI\Pixal3D`):
1. `git clone https://github.com/TencentARC/Pixal3D.git C:\AI\Pixal3D`
2. Copy the TRELLIS.2 venv, which already has torch cu129 and o_voxel, flex_gemm, cumesh and nvdiffrast built for Windows:
   `robocopy C:\AI\TRELLIS2\venv C:\AI\Pixal3D\venv /E /MT:16` (robocopy's exit code 1 means "copied").
3. `venv\Scripts\python.exe -m pip install -r requirements.txt` without its `gradio` and `trimesh` lines (the trimesh
   pin clashes with MoGe; the venv's newer trimesh works), then `pip install einops` (needed by NAF).
4. `git apply pixal3d-segment_reduce.patch`: the same Windows fix as TRELLIS.2 (no CUDA `segment_reduce` on Windows).
5. Copy `run_pixal3d.py` and `shims\` into `C:\AI\Pixal3D`. `shims\natten` is a pure-PyTorch stand-in for the one
   NATTEN call (`na2d`) that the NAF feature upsampler makes; NATTEN doesn't build on Windows. It matches a
   brute-force reference to about 5e-7.

Run (cmd): `set LOW_VRAM=1 && set DEC=30000 && set TEX=2048 && venv\Scripts\python.exe run_pixal3d.py <cutout.png> <out_prefix>`

- Always use `LOW_VRAM=1`. The default mode keeps every model on the GPU, goes past 32 GB into shared system memory,
  and the texture stage crawls: 25 minutes for one man instead of 2.
- Big objects are still slow: the RAV4 took 16 minutes (TRELLIS.2: 2).
- First run downloads Pixal3D's weights, DINOv3 from an ungated mirror (`camenduru/dinov3-vitl16-pretrain-lvd1689m`;
  Meta's DINOv3 licence still applies), MoGe-2 (Microsoft) and NAF (valeoai, through torch.hub).
- Its metallic channel can come out far too high on organic things: the Shiba looked like gold.
- Its models come out turned the way the photo saw them (the 3/4 RAV4 and Shiba were turned 43 and 53 degrees), so
  straighten them before use; TRELLIS.2's come out facing forward. In the game the RAV4 looked melted and grainy.
