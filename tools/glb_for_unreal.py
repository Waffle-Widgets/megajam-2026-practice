"""Makes an AI generator's GLB ready for Unreal's own importer (Interchange), without touching the geometry.
    C:\AI\TRELLIS2\venv\Scripts\python.exe tools/glb_for_unreal.py <in.glb> <out.glb> <size_m> [height|length]
- textures are written as PNG: TRELLIS.2 and Pixal3D pack WebP, which Unreal can't import ("produced no assets")
- scaled so its height (or, with `length`, its longest side) is <size_m> metres, standing on the ground and centred;
  glTF metres become Unreal centimetres on import, so it arrives at real size
Uses trimesh, the library the generators write their GLBs with, so the PBR textures pass through unchanged.
Then import the result with tools/unreal_import_glb.py (Unreal's auto-import doesn't take .glb)."""
import sys
import numpy as np, trimesh

src, dst, size = sys.argv[1], sys.argv[2], float(sys.argv[3])
mode = sys.argv[4] if len(sys.argv) > 4 else 'height'
scene = trimesh.load(src, force='scene')
lo, hi = scene.bounds                       # glTF is Y-up
dims = hi - lo
s = size / (dims[1] if mode == 'height' else dims.max())
T = np.eye(4)
T[:3, :3] *= s
T[:3, 3] = [-(lo[0] + hi[0]) / 2 * s, -lo[1] * s, -(lo[2] + hi[2]) / 2 * s]
scene.apply_transform(T)
scene.export(dst)                           # trimesh's GLB export writes PNG textures by default
lo2, hi2 = scene.bounds
print('GLB_FOR_UNREAL', dst, 'scaled by', round(s, 4), 'size m', np.round(hi2 - lo2, 3).tolist())
