"""TRELLIS.2 image -> 3D on Windows.  python run_image_to_3d.py <image.png> <out_prefix> [512|1024|1024_cascade|1536_cascade]
Writes <out_prefix>_raw.ply (shape only, always) and <out_prefix>.glb (textured PBR, needs nvdiffrast).
Env: SEED (default 42); DEC = triangle target of the GLB (default 500000; ~30000 gives a clean game mesh, since the
export remeshes from the voxel volume, not from the generator's fur flaps); TEX = texture size (4096); KEEP_PT=1 keeps
<out_prefix>_mesh.pt so `export_glb.py <out_prefix> <TEX> <DEC>` can re-export without regenerating. A cut-out with real alpha skips the gated RMBG-2.0 background remover."""
import os, sys, time
os.environ.setdefault('ATTN_BACKEND', 'xformers'); os.environ.setdefault('SPARSE_ATTN_BACKEND', 'xformers')
ROOT = os.path.dirname(os.path.abspath(__file__))              # the TRELLIS2 folder (D:\AI\TRELLIS2 or C:\AI\TRELLIS2)
os.environ.setdefault('HF_HOME', os.path.join(os.path.dirname(ROOT), 'hf_cache')); os.environ['HF_HUB_DISABLE_SYMLINKS'] = '1'
_tok = os.path.expanduser('~/.cache/huggingface/token')         # where `huggingface-cli login` stores it
if 'HF_TOKEN' not in os.environ and os.path.exists(_tok):
    os.environ['HF_TOKEN'] = open(_tok).read().strip()
os.environ['PYTORCH_CUDA_ALLOC_CONF'] = 'expandable_segments:True'
sys.path.insert(0, os.path.join(ROOT, 'TRELLIS.2'))
import numpy as np, torch, trimesh
if torch.cuda.get_device_capability(0)[0] != 9:     # xformers' FlashAttention-3 kernel is Hopper-only; on an RTX 50
    from xformers.ops.fmha import dispatch            # it fails with "invalid argument", so use FlashAttention-2
    dispatch._set_use_fa3(False)
from PIL import Image
import trellis2.pipelines.rembg as rembg_mod
img = Image.open(sys.argv[1])
if img.mode == 'RGBA' and (np.array(img)[:, :, 3] != 255).any():
    rembg_mod.BiRefNet = lambda **kw: None            # alpha present: the pipeline never calls the remover
from trellis2.pipelines import Trellis2ImageTo3DPipeline
pipe = Trellis2ImageTo3DPipeline.from_pretrained('microsoft/TRELLIS.2-4B'); pipe.cuda()
ptype = sys.argv[3] if len(sys.argv) > 3 else '1024_cascade'
t0 = time.time()
mesh = pipe.run(img, seed=int(os.environ.get('SEED', '42')), pipeline_type=ptype)[0]
print('generated in', round(time.time() - t0, 1), 's; verts', tuple(mesh.vertices.shape), 'faces', tuple(mesh.faces.shape), flush=True)
out = sys.argv[2]
mesh.simplify(16777216)
v = mesh.vertices.detach().cpu().numpy(); f = mesh.faces.detach().cpu().numpy()
trimesh.Trimesh(v, f, process=False).export(out + '_raw.ply'); print('wrote', out + '_raw.ply', flush=True)
torch.save({'vertices': mesh.vertices.detach().cpu(), 'faces': mesh.faces.detach().cpu(), 'attrs': mesh.attrs.detach().cpu(),
            'coords': mesh.coords.detach().cpu(), 'layout': mesh.layout, 'voxel_size': mesh.voxel_size}, out + '_mesh.pt')
del mesh, pipe; import gc; gc.collect(); torch.cuda.empty_cache()
import subprocess                                   # the GLB bake runs in a fresh process with the whole GPU
r = subprocess.run([sys.executable, os.path.join(ROOT, 'export_glb.py'), out, os.environ.get('TEX', '4096'), os.environ.get('DEC', '500000')])
print('GLB export exit', r.returncode, flush=True)
if r.returncode == 0 and os.environ.get('KEEP_PT') != '1': os.remove(out + '_mesh.pt')   # KEEP_PT=1: re-export later with other TEX/DEC
