"""Makes a Meshy prop game-ready: real size, few triangles, clean UVs and its colour baked from the full-detail model
(from the Deep Archive HD-2D test). Default: a fine texture (about 4 mm per texel, at most 2048).
PROP_PIXEL=1: a chunky pixel texture instead (one texel = 3 cm, to sit next to pixel-art sprites).
    blender -b --factory-startup --python Art/Blender/meshy_prop_bake.py -- <in.glb> <Name> <size_m> <height|width> <tris>
Writes Art/Meshy/<Name>/SM_<Name>.fbx and T_<Name>.png, and a check render in Art/Blender/cache/meshy_<Name>.png.
Steps: import the GLB, size it (height, or its widest side for `width`), stand it on the ground, centred; copy it,
weld and decimate the copy, give it clean big UV islands, bake the Meshy colour texture onto it (Cycles,
selected-to-active, emission), and export with our FBX settings (forward -Z, up Y: Blender +Y becomes Unreal -Y, so a
model facing Blender -Y faces the game camera)."""
import bpy, bmesh, math, os, sys
import numpy as np

argv = sys.argv[sys.argv.index('--') + 1:]
GLB, NAME, SIZE, MODE, TRIS = argv[0], argv[1], float(argv[2]), argv[3], int(argv[4])
REPO = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..'))
OUT = os.path.join(REPO, 'Art', 'Meshy', NAME)
CACHE = os.path.join(REPO, 'Art', 'Blender', 'cache')
os.makedirs(OUT, exist_ok=True); os.makedirs(CACHE, exist_ok=True)
TEXEL = 0.03          # metres per texel: a sprite pixel is 1.5 game units = 3 cm
# PROP_SMOOTH=1: the stylized-3D room's version (pass a <Name>3D name): a fine, smoothly filtered texture
# (about 4 mm per texel, at most 2048) instead of the 3 cm pixel one, and a wider bake margin
SMOOTH = os.environ.get('PROP_PIXEL') != '1'   # practice repo: fine texture by default
if SMOOTH:
    TEXEL = 0.004
# optional 6th argument: voxel size in metres. Wraps the low copy in one closed skin before decimating, for models
# made of many thin overlapping shells (the berry bush's leaves), which otherwise decimate into spikes and bake black
VOXEL = float(argv[5]) if len(argv) > 5 else 0.0
# optional 7th argument: total height in metres for a pole-like prop (the torch post). The model is sized by its
# widest part (the bowl, with `width`), then only the part below that wide top is stretched until the whole is this
# tall, so a taller post doesn't also get a giant bowl (scaling the whole model evenly gave an 85 cm bowl).
POLE = float(argv[6]) if len(argv) > 6 else 0.0
report = {'name': NAME}

for o in list(bpy.data.objects):
    bpy.data.objects.remove(o)
bpy.ops.import_scene.gltf(filepath=GLB)
meshes = [o for o in bpy.context.scene.objects if o.type == 'MESH']
for o in bpy.context.scene.objects:
    o.select_set(o in meshes)
bpy.context.view_layer.objects.active = meshes[0]
if len(meshes) > 1:
    bpy.ops.object.join()
src = bpy.context.view_layer.objects.active
src.name = 'SRC'
src.parent = None
bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
for o in list(bpy.context.scene.objects):
    if o is not src:
        bpy.data.objects.remove(o)

# size and place: base on the ground, centred
V = np.empty(len(src.data.vertices) * 3); src.data.vertices.foreach_get('co', V); V = V.reshape(-1, 3)
lo, hi = V.min(0), V.max(0); dims = hi - lo
s = SIZE / (dims[2] if MODE == 'height' else max(dims[0], dims[1]))
V = (V - [(lo[0] + hi[0]) / 2, (lo[1] + hi[1]) / 2, lo[2]]) * s
if POLE > 0:
    # the wide top starts at the lowest height where the model is at least half as wide as its widest part
    z, r = V[:, 2], np.abs(V[:, :2]).max(1)
    bins = np.linspace(0, z.max(), 61)
    width = np.array([r[(z >= a) & (z < b)].max() if ((z >= a) & (z < b)).any() else 0 for a, b in zip(bins[:-1], bins[1:])])
    zb = float(bins[np.argmax(width >= 0.5 * width.max())])
    k = (POLE - (z.max() - zb)) / zb
    below = z < zb
    V[below, 2] *= k
    V[~below, 2] += zb * (k - 1)
    report['pole'] = {'bowl_from_m': round(zb, 3), 'stretch': round(float(k), 2)}
src.data.vertices.foreach_set('co', V.ravel()); src.data.update()
report['size_m'] = [round(float(x), 3) for x in (V.max(0) - V.min(0))]
report['src_tris'] = sum(len(p.vertices) - 2 for p in src.data.polygons)

# the low copy: weld (the glTF import splits vertices along UV seams), then decimate
low = src.copy(); low.data = src.data.copy(); low.name = 'LOW'
bpy.context.scene.collection.objects.link(low)
bm = bmesh.new(); bm.from_mesh(low.data)
bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-5 * SIZE)
bm.to_mesh(low.data); bm.free()
while low.data.uv_layers:
    low.data.uv_layers.remove(low.data.uv_layers[0])
low.data.materials.clear()
for o in bpy.context.scene.objects:
    o.select_set(o is low)
bpy.context.view_layer.objects.active = low
if VOXEL > 0:
    rm = low.modifiers.new('voxel', 'REMESH'); rm.mode = 'VOXEL'; rm.voxel_size = VOXEL
    bpy.ops.object.modifier_apply(modifier='voxel')
    bpy.ops.object.mode_set(mode='EDIT'); bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.mesh.quads_convert_to_tris(); bpy.ops.object.mode_set(mode='OBJECT')
cur = sum(len(p.vertices) - 2 for p in low.data.polygons)
if cur > TRIS:
    mod = low.modifiers.new('dec', 'DECIMATE'); mod.ratio = TRIS / cur
    bpy.ops.object.modifier_apply(modifier='dec')
bpy.ops.object.shade_smooth_by_angle(angle=math.radians(40))
report['low_tris'] = sum(len(p.vertices) - 2 for p in low.data.polygons)

# clean UVs, big islands
low.data.uv_layers.new(name='UV')
bpy.ops.object.mode_set(mode='EDIT'); bpy.ops.mesh.select_all(action='SELECT')
bpy.ops.uv.smart_project(angle_limit=math.radians(66), island_margin=0.03, scale_to_bounds=False)
bpy.ops.object.mode_set(mode='OBJECT')

# texture size from the surface area at 3 cm per texel (smart_project fills roughly half the square)
area = sum(p.area for p in low.data.polygons)
need = math.sqrt(area / (TEXEL * TEXEL) / 0.5)
TEX = int(2 ** math.ceil(math.log2(max(need, 32))))
if SMOOTH:
    TEX = min(TEX, 2048)
report['area_m2'] = round(area, 2); report['tex_px'] = TEX

# the source shows its own colour texture as emission, for the bake
for slot in src.material_slots:
    m = slot.material
    if not m or not m.use_nodes:
        continue
    nt = m.node_tree
    bsdf = next((n for n in nt.nodes if n.type == 'BSDF_PRINCIPLED'), None)
    outn = next((n for n in nt.nodes if n.type == 'OUTPUT_MATERIAL'), None)
    if not bsdf or not outn or not bsdf.inputs['Base Color'].links:
        continue
    em = nt.nodes.new('ShaderNodeEmission')
    nt.links.new(bsdf.inputs['Base Color'].links[0].from_socket, em.inputs['Color'])
    nt.links.new(em.outputs['Emission'], outn.inputs['Surface'])

img = bpy.data.images.new(f'T_{NAME}', TEX, TEX, alpha=False)
img.colorspace_settings.name = 'sRGB'
mat = bpy.data.materials.new(f'M_{NAME}'); mat.use_nodes = True; nt = mat.node_tree
tn = nt.nodes.new('ShaderNodeTexImage'); tn.image = img; tn.interpolation = 'Linear' if SMOOTH else 'Closest'
nt.links.new(tn.outputs['Color'], nt.nodes['Principled BSDF'].inputs['Base Color'])
nt.nodes.active = tn
low.data.materials.append(mat)

sc = bpy.context.scene
sc.render.engine = 'CYCLES'; sc.cycles.samples = 4
try:
    sc.cycles.device = 'GPU'
except Exception:
    pass
bk = sc.render.bake
bk.use_selected_to_active = True; bk.cage_extrusion = 0.05 * SIZE; bk.max_ray_distance = 0.0; bk.margin = 8 if SMOOTH else 2   # 0 = no limit
for o in sc.objects:
    o.select_set(False)
src.select_set(True); low.select_set(True); bpy.context.view_layer.objects.active = low
bpy.ops.object.bake(type='EMIT')
tex_path = os.path.join(OUT, f'T_{NAME}.png')
img.filepath_raw = tex_path; img.file_format = 'PNG'; img.save()
px = np.empty(TEX * TEX * 4, np.float32); img.pixels.foreach_get(px)
report['tex_mean'] = round(float(px.reshape(-1, 4)[:, :3].mean()), 3)

# export the low mesh only
bpy.data.objects.remove(src)
low.name = f'SM_{NAME}'
for o in sc.objects:
    o.select_set(o is low)
fbx = os.path.join(OUT, f'SM_{NAME}.fbx')
bpy.ops.export_scene.fbx(filepath=fbx, use_selection=True, axis_forward='-Z', axis_up='Y', global_scale=1.0,
                         apply_unit_scale=True, apply_scale_options='FBX_SCALE_UNITS', mesh_smooth_type='FACE',
                         path_mode='STRIP', embed_textures=False, bake_anim=False, add_leaf_bones=False)

# check render: about the game camera's angle (looking from -Y, 35 degrees down), texture shown with nearest pixels
FRAME = float((V.max(0) - V.min(0)).max())   # the prop's biggest size, so tall poles fit too
cam_d = FRAME * 3.2
cam = bpy.data.objects.new('cam', bpy.data.cameras.new('cam')); sc.collection.objects.link(cam)
cam.data.lens = 85
h = FRAME * 0.45
cam.location = (0, -cam_d * math.cos(math.radians(35)), h + cam_d * math.sin(math.radians(35)))
cam.rotation_euler = (math.radians(90 - 35), 0, 0)
sc.camera = cam
sc.render.engine = 'BLENDER_WORKBENCH'
sh = sc.display.shading; sh.light = 'STUDIO'; sh.color_type = 'TEXTURE'
sc.render.resolution_x = sc.render.resolution_y = 512
sc.render.film_transparent = True
sc.render.filepath = os.path.join(CACHE, f'meshy_{NAME}.png')
bpy.ops.render.render(write_still=True)
print('MESHY_BAKE', report)
