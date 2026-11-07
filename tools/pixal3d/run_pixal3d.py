"""Pixal3D (Tencent ARC, MIT) image -> 3D on Windows, set up like our TRELLIS.2 runner so the two compare like with like.
    venv\\Scripts\\python.exe run_pixal3d.py <cutout.png> <out_prefix> [1024|1536]
Writes <out_prefix>.glb. Env: SEED (42), DEC = triangle target of the GLB (500000), TEX = texture size (4096),
LOW_VRAM=1 loads one model at a time (~10-12 GB instead of ~18 GB).
Windows port: natten (used by the NAF feature upsampler) is replaced by the pure-PyTorch shim in shims/natten,
torch.segment_reduce is patched in pixal3d/modules/sparse/basic.py (same patch as TRELLIS.2), xformers attention
(FlashAttention-3 off outside Hopper). A cut-out with real alpha skips the background remover (BiRefNet)."""
import os, sys, time
ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(ROOT, 'shims'))
sys.path.insert(0, ROOT)
os.environ.setdefault('HF_HOME', os.path.join(os.path.dirname(ROOT), 'hf_cache')); os.environ['HF_HUB_DISABLE_SYMLINKS'] = '1'
os.environ.setdefault('TORCH_HOME', os.path.join(os.path.dirname(ROOT), 'torch_hub'))
_tok = os.path.expanduser('~/.cache/huggingface/token')
if 'HF_TOKEN' not in os.environ and os.path.exists(_tok):
    os.environ['HF_TOKEN'] = open(_tok).read().strip()
os.environ.setdefault('ATTN_BACKEND', 'xformers'); os.environ.setdefault('SPARSE_ATTN_BACKEND', 'xformers')
import numpy as np, torch
if torch.cuda.get_device_capability(0)[0] != 9:     # xformers' FlashAttention-3 kernel is Hopper-only
    from xformers.ops.fmha import dispatch
    dispatch._set_use_fa3(False)
from PIL import Image
image_path, out_prefix = sys.argv[1], sys.argv[2]
res = int(sys.argv[3]) if len(sys.argv) > 3 else -1
im = Image.open(image_path)
if im.mode == 'RGBA' and (np.array(im)[:, :, 3] != 255).any():
    import pixal3d.pipelines.rembg as rembg_mod
    rembg_mod.BiRefNet = lambda **kw: None              # alpha present: the pipeline never calls the remover
import o_voxel
_to_glb = o_voxel.postprocess.to_glb
DEC, TEX = int(os.environ.get('DEC', '500000')), int(os.environ.get('TEX', '4096'))
def to_glb(*a, **kw):                                   # inference.py hard-codes 1M triangles / 4096 textures
    kw['decimation_target'] = DEC; kw['texture_size'] = TEX
    return _to_glb(*a, **kw)
o_voxel.postprocess.to_glb = to_glb
import inference
t0 = time.time()
inference.run_inference(image_path=image_path, output_path=out_prefix + '.glb', seed=int(os.environ.get('SEED', '42')),
                        low_vram=os.environ.get('LOW_VRAM') == '1', resolution=res)
print('PIXAL3D total', round(time.time() - t0, 1), 's; peak VRAM', round(torch.cuda.max_memory_allocated() / 2**30, 1), 'GB', flush=True)
