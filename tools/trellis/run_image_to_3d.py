"""TRELLIS.2 image -> 3D on Windows.  python run_image_to_3d.py <image.png> <out_prefix> [512|1024|1024_cascade|1536_cascade]
Writes <out_prefix>_raw.ply (shape only, always) and <out_prefix>.glb (textured PBR, needs nvdiffrast).
Env: SEED (default 42). A cut-out with real alpha skips the gated RMBG-2.0 background remover."""
import os, sys, time
os.environ.setdefault('ATTN_BACKEND', 'xformers'); os.environ.setdefault('SPARSE_ATTN_BACKEND', 'xformers')
os.environ.setdefault('HF_HOME', r'D:\AI\hf_cache'); os.environ['HF_HUB_DISABLE_SYMLINKS'] = '1'
_tok = os.path.expanduser('~/.cache/huggingface/token')         # where `huggingface-cli login` stores it
if 'HF_TOKEN' not in os.environ and os.path.exists(_tok):
    os.environ['HF_TOKEN'] = open(_tok).read().strip()
os.environ['PYTORCH_CUDA_ALLOC_CONF'] = 'expandable_segments:True'
sys.path.insert(0, r'D:\AI\TRELLIS2\TRELLIS.2')
import numpy as np, torch, trimesh
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
r = subprocess.run([sys.executable, r'D:\AI\TRELLIS2\export_glb.py', out])
print('GLB export exit', r.returncode, flush=True)
if r.returncode == 0: os.remove(out + '_mesh.pt')
