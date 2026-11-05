"""GLB bake in its own process, so the generator's weights are gone from the GPU.  python export_glb.py <out_prefix>"""
import os, sys
os.environ['PYTORCH_CUDA_ALLOC_CONF'] = 'expandable_segments:True'
sys.path.insert(0, r'D:\AI\TRELLIS2\TRELLIS.2')
import torch, o_voxel
out = sys.argv[1]; TEX = int(sys.argv[2]) if len(sys.argv) > 2 else 4096; DEC = int(sys.argv[3]) if len(sys.argv) > 3 else 500000
d = torch.load(out + '_mesh.pt', weights_only=False)
glb = o_voxel.postprocess.to_glb(vertices=d['vertices'].cuda(), faces=d['faces'].cuda(), attr_volume=d['attrs'].cuda(), coords=d['coords'].cuda(),
                                 attr_layout=d['layout'], voxel_size=d['voxel_size'], aabb=[[-0.5, -0.5, -0.5], [0.5, 0.5, 0.5]],
                                 decimation_target=DEC, texture_size=TEX, remesh=True, remesh_band=1, remesh_project=0, verbose=True)
glb.export(out + '.glb', extension_webp=True); print('wrote', out + '.glb', flush=True)
