"""TRELLIS.2 image -> 3D on Windows.  python run_image_to_3d.py <image.png>[,<view2.png>,...] <out_prefix> [512|1024|1024_cascade|1536_cascade]
Several comma-separated pictures of the same object are blended into one model (each step averages the model's answer per picture).
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
imgs = [Image.open(p) for p in sys.argv[1].split(',')]   # several views of ONE object: "front.png,rear.png"
if all(im.mode == 'RGBA' and (np.array(im)[:, :, 3] != 255).any() for im in imgs):
    rembg_mod.BiRefNet = lambda **kw: None            # alpha present: the pipeline never calls the remover
from trellis2.pipelines import Trellis2ImageTo3DPipeline
pipe = Trellis2ImageTo3DPipeline.from_pretrained('microsoft/TRELLIS.2-4B'); pipe.cuda()
ptype = sys.argv[3] if len(sys.argv) > 3 else '1024_cascade'
if len(imgs) > 1:
    # Multi-view ("multidiffusion", as TRELLIS v1 did it): every generation step asks the model once per picture
    # and averages the answers, so all views shape ONE object. TRELLIS.2 itself only takes one picture.
    imgs = [pipe.preprocess_image(im) for im in imgs]
    _get_cond = pipe.get_cond
    pipe.get_cond = lambda image, res, include_neg_cond=True: _get_cond(imgs, res, include_neg_cond)
    def _multi(orig):
        def run_views(model, x_t, t, cond=None, **kw):
            n = cond.shape[0] if torch.is_tensor(cond) else 1
            if n == 1: return orig(model, x_t, t, cond, **kw)
            preds = []
            for i in range(n):
                kw_i = dict(kw)
                if torch.is_tensor(kw.get('neg_cond')) and kw['neg_cond'].shape[0] == n: kw_i['neg_cond'] = kw['neg_cond'][i:i + 1]
                preds.append(orig(model, x_t, t, cond[i:i + 1], **kw_i))
            return sum(preds[1:], preds[0]) * (1.0 / n)
        return run_views
    for s in (pipe.sparse_structure_sampler, pipe.shape_slat_sampler, pipe.tex_slat_sampler):
        s._inference_model = _multi(s._inference_model)
    print('multi-view:', len(imgs), 'pictures', flush=True)
t0 = time.time()
mesh = pipe.run(imgs[0], seed=int(os.environ.get('SEED', '42')), pipeline_type=ptype, preprocess_image=len(imgs) == 1)[0]
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
