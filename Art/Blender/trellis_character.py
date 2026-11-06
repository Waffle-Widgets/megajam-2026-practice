# TRELLIS character -> game-ready rigged FBX. Runs headless:
#   blender -b --factory-startup --python trellis_character.py -- <in.glb> <Name> <kind: human|dog> <height_m> [tris]
# Writes Content/Game/Imported/<Name>/SK_<Name>.fbx + T_<Name>_BaseColor.png and preview renders in Art/Blender/cache/.
# Steps: import, weld, ground + scale to real height, find which way it faces, decimate a copy, give it clean UVs,
# bake the generator's colour onto them, build a skeleton from body landmarks, weight it on a voxel-remeshed proxy
# (TRELLIS meshes are not closed, so heat weighting on them directly fails), copy the weights over, export.
import bpy, bmesh, sys, os, math, time, json
import numpy as np
from mathutils import Vector, Matrix
t0 = time.time()
argv = sys.argv[sys.argv.index('--') + 1:]
GLB, NAME, KIND, HEIGHT = argv[0], argv[1], argv[2], float(argv[3])
TRIS = int(argv[4]) if len(argv) > 4 else 40000
REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
CACHE = os.path.join(REPO, 'Art', 'Blender', 'cache'); os.makedirs(CACHE, exist_ok=True)
OUTD = os.path.join(REPO, 'MegaJamPractice', 'Content', 'Game', 'Imported', NAME); os.makedirs(OUTD, exist_ok=True)
TEX = 2048
log = {}

bpy.ops.wm.read_factory_settings(use_empty=True)
prefs = bpy.context.preferences.addons['cycles'].preferences
for dt in ('OPTIX', 'CUDA'):
    try:
        prefs.compute_device_type = dt; prefs.get_devices()
        if any(d.type == dt for d in prefs.devices): break
    except TypeError: pass
for d in prefs.devices: d.use = d.type != 'CPU'

# ---------- 1. import, join, weld ----------
bpy.ops.import_scene.gltf(filepath=GLB)
meshes = [o for o in bpy.context.scene.objects if o.type == 'MESH']
for o in bpy.context.scene.objects: o.select_set(False)
for o in meshes: o.select_set(True)
bpy.context.view_layer.objects.active = meshes[0]
if len(meshes) > 1: bpy.ops.object.join()
src = bpy.context.view_layer.objects.active; src.name = 'SRC'
for o in list(bpy.context.scene.objects):
    if o is not src: bpy.data.objects.remove(o)
src.parent = None
bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
bm = bmesh.new(); bm.from_mesh(src.data)
bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-5)
bm.to_mesh(src.data); bm.free()
# drop loose specks (TRELLIS fur fuzz): they sit above the skin, catch the bake rays and confuse the weighting
def drop_small(o, frac, floor=0):
    """Delete connected pieces smaller than frac of the vertices (or floor). Returns (pieces removed, verts removed)."""
    me = o.data; nv = len(me.vertices); E = np.empty(len(me.edges) * 2, np.int64); me.edges.foreach_get('vertices', E); E = E.reshape(-1, 2)
    par = np.arange(nv)
    def find(i):
        while par[i] != i: par[i] = par[par[i]]; i = par[i]
        return i
    for a, b in E:
        ra, rb = find(a), find(b)
        if ra != rb: par[ra] = rb
    roots = np.array([find(i) for i in range(nv)]); _, inv, cnt = np.unique(roots, return_inverse=True, return_counts=True)
    lim = min(max(floor, int(frac * nv)), int(cnt.max())); small = cnt[inv] < lim   # always keep the biggest piece
    log.setdefault('pieces', []).append([o.name, len(cnt), int(cnt.max()), nv])
    bm = bmesh.new(); bm.from_mesh(me); bm.verts.ensure_lookup_table()
    bmesh.ops.delete(bm, geom=[bm.verts[i] for i in np.nonzero(small)[0]], context='VERTS')
    bm.to_mesh(me); bm.free(); me.update()
    return int((cnt < lim).sum()), int(small.sum())
log['specks_removed'], log['speck_verts'] = drop_small(src, 0.002, 500)
img = None
for m in src.data.materials:
    for n in m.node_tree.nodes:
        if n.type == 'TEX_IMAGE' and n.image and any(l.to_socket.name == 'Base Color' for l in n.outputs['Color'].links):
            img = n.image
log['src_faces'] = len(src.data.polygons); log['src_image'] = img.name if img else None

def verts(o):
    me = o.data; V = np.empty(len(me.vertices) * 3); me.vertices.foreach_get('co', V); return V.reshape(-1, 3)

# ---------- 2. upright, height, ground, facing ----------
V = verts(src); ext = V.max(0) - V.min(0)
if KIND == 'human':
    up = int(np.argmax(ext))                         # a standing person is tallest along "up"
else:
    up = 2                                           # glTF import already makes +Z up
if up != 2:
    rot = Matrix.Rotation(math.radians(90), 4, 'X') if up == 1 else Matrix.Rotation(math.radians(-90), 4, 'Y')
    src.data.transform(rot); V = verts(src)
lo, hi = V.min(0), V.max(0)
s = HEIGHT / (hi[2] - lo[2]) if KIND == 'human' else 1.0
if KIND == 'dog':                                    # HEIGHT for a dog = shoulder height; use 0.9 of the max height (ears stick up)
    s = HEIGHT / ((hi[2] - lo[2]) * 0.80)
c = (lo + hi) / 2
src.data.transform(Matrix.Scale(s, 4) @ Matrix.Translation(Vector((-c[0], -c[1], -lo[2]))))
V = verts(src); H = V[:, 2].max()

def facing_human(V):
    feet = V[V[:, 2] < 0.03 * H]; shins = V[(V[:, 2] > 0.10 * H) & (V[:, 2] < 0.18 * H)]
    d = feet[:, :2].mean(0) - shins[:, :2].mean(0)   # toes stick out in front of the shins
    return d / (np.linalg.norm(d) + 1e-9)

def facing_dog(V):
    xy = V[:, :2] - V[:, :2].mean(0); w, vec = np.linalg.eigh(np.cov(xy.T)); ax = vec[:, -1]  # body length axis
    t = xy @ ax; head = V[t > np.percentile(t, 85)]; tail = V[t < np.percentile(t, 15)]
    return ax if head[:, 2].max() > tail[:, 2].max() else -ax   # the head end is the taller end (ears)

f = facing_human(V) if KIND == 'human' else facing_dog(V)
ang = math.atan2(f[0], -f[1])                        # rotate so the character faces -Y (Blender front view)
src.data.transform(Matrix.Rotation(ang, 4, 'Z'))
V = verts(src); lo, hi = V.min(0), V.max(0); c = (lo + hi) / 2
src.data.transform(Matrix.Translation(Vector((-c[0], -c[1], 0))))
V = verts(src); log['size_m'] = [round(float(v), 3) for v in (V.max(0) - V.min(0))]

# ---------- 3. game mesh: decimated copy with clean UVs, bake the generator colour ----------
sc = bpy.context.scene
DIRECT = len(src.data.polygons) < TRIS * 1.5     # TRELLIS exported a game-size mesh itself (run with DEC=30000): use it as is
if DIRECT:
    SIZE = float((V.max(0) - V.min(0)).max())
    lowo = src; lowo.name = NAME; log['direct'] = True
    log['game_tris'] = sum(len(p.vertices) - 2 for p in lowo.data.polygons)
    for p in lowo.data.polygons: p.use_smooth = True
    # the GLB packs its texture as WebP and img.save() writes those bytes unchanged under a .png name, which
    # Unreal refuses ("produced no assets"): copy the pixels into a fresh image and save that as a real PNG
    w, h = img.size; png = bpy.data.images.new('T_%s_BaseColor' % NAME, w, h, alpha=True)
    px = np.empty(w * h * 4, dtype=np.float32); img.pixels.foreach_get(px); png.pixels.foreach_set(px)
    png.filepath_raw = os.path.join(OUTD, 'T_%s_BaseColor.png' % NAME); png.file_format = 'PNG'; png.save()
    m = lowo.data.materials[0]; m.name = 'M_%s' % NAME
if not DIRECT:
  lowo = src.copy(); lowo.data = src.data.copy(); lowo.name = NAME; bpy.context.scene.collection.objects.link(lowo)
  bpy.context.view_layer.objects.active = lowo
  for o in bpy.context.scene.objects: o.select_set(o is lowo)
  SIZE = float((V.max(0) - V.min(0)).max())
  if os.environ.get('CHAR_REMESH') == '1':      # experiment, off: both remesh modes broke the TRELLIS Shiba into scraps
      # fur comes out as fins (3+ faces on one edge) that the decimator will not collapse: rebuild one closed skin
      # (6 mm voxels close the fur's pinholes; 4 mm left it in 2,000 pieces), keep the main piece, smooth, then decimate
      # voxel remesh needs a closed surface (on this fur it left 622 blobs); the octree remesh wraps open surfaces
      rm0 = lowo.modifiers.new('rm0', 'REMESH'); rm0.mode = 'SMOOTH'; rm0.octree_depth = int(os.environ.get('CHAR_OCTREE', '8'))
      rm0.scale = 0.9; rm0.use_remove_disconnected = True; rm0.threshold = 0.5
      bpy.ops.object.modifier_apply(modifier='rm0')
      log['skin_pieces_removed'] = drop_small(lowo, 0.2)[0]
      sm0 = lowo.modifiers.new('sm0', 'CORRECTIVE_SMOOTH'); sm0.iterations = 6; sm0.use_only_smooth = True
      bpy.ops.object.modifier_apply(modifier='sm0')
  while lowo.data.uv_layers: lowo.data.uv_layers.remove(lowo.data.uv_layers[0])   # generator UV seams stop the decimator
  ntri = lambda: sum(len(p.vertices) - 2 for p in lowo.data.polygons)
  for _ in range(3):                                   # open fur edges make one pass stop early
      if ntri() < TRIS * 1.15: break
      dec = lowo.modifiers.new('dec', 'DECIMATE'); dec.ratio = min(1.0, TRIS / max(1, ntri()))
      r = bpy.ops.object.modifier_apply(modifier='dec')
      log.setdefault('tri_steps', []).append((round(dec.ratio, 4) if False else None, str(r), ntri(), bpy.context.view_layer.objects.active.name))
  log['low_pieces_removed'] = drop_small(lowo, 0.01)[0]
  wn = lowo.modifiers.new('wn', 'WEIGHTED_NORMAL'); wn.keep_sharp = False
  bpy.ops.object.modifier_apply(modifier='wn')
  for p in lowo.data.polygons: p.use_smooth = True
  while lowo.data.uv_layers: lowo.data.uv_layers.remove(lowo.data.uv_layers[0])
  lowo.data.uv_layers.new(name='UV')
  bpy.ops.object.mode_set(mode='EDIT'); bpy.ops.mesh.select_all(action='SELECT')
  bpy.ops.uv.smart_project(angle_limit=math.radians(66 if KIND == 'human' else 80), island_margin=0.003, correct_aspect=True)
  bpy.ops.uv.select_all(action='SELECT'); bpy.ops.uv.pack_islands(margin=0.002, rotate=True)
  bpy.ops.object.mode_set(mode='OBJECT')
  uvd = lowo.data.uv_layers.active.data; UVa = np.empty(len(uvd) * 2); uvd.foreach_get('uv', UVa)
  log['uv_extent'] = [round(float(v), 3) for v in UVa.reshape(-1, 2).max(0)]
  log['game_tris'] = sum(len(p.vertices) - 2 for p in lowo.data.polygons)

  ms = bpy.data.materials.new('M_Src'); ms.use_nodes = True; nt = ms.node_tree
  for n in list(nt.nodes): nt.nodes.remove(n)
  tx = nt.nodes.new('ShaderNodeTexImage'); tx.image = img
  em = nt.nodes.new('ShaderNodeEmission'); on = nt.nodes.new('ShaderNodeOutputMaterial')
  nt.links.new(tx.outputs['Color'], em.inputs['Color']); nt.links.new(em.outputs['Emission'], on.inputs['Surface'])
  src.data.materials.clear(); src.data.materials.append(ms)
  bake = bpy.data.images.new('T_%s_BaseColor' % NAME, TEX, TEX)
  mt = bpy.data.materials.new('M_%s' % NAME); mt.use_nodes = True; nt2 = mt.node_tree
  bsdf = nt2.nodes['Principled BSDF']; tn = nt2.nodes.new('ShaderNodeTexImage'); tn.image = bake
  nt2.links.new(tn.outputs['Color'], bsdf.inputs['Base Color']); bsdf.inputs['Roughness'].default_value = 0.8
  nt2.nodes.active = tn
  lowo.data.materials.clear(); lowo.data.materials.append(mt)
  sc = bpy.context.scene; sc.render.engine = 'CYCLES'; sc.cycles.device = 'GPU'; sc.cycles.samples = 1
  bk = sc.render.bake; bk.use_selected_to_active = True; bk.cage_extrusion = 0.006 * SIZE; bk.max_ray_distance = 0.02 * SIZE; bk.margin = 8
  for o in sc.objects: o.select_set(False)
  src.select_set(True); lowo.select_set(True); bpy.context.view_layer.objects.active = lowo
  bpy.ops.object.bake(type='EMIT')
  bake.filepath_raw = os.path.join(OUTD, 'T_%s_BaseColor.png' % NAME); bake.file_format = 'PNG'; bake.save()
  src.hide_render = True; src.hide_viewport = True

# ---------- 4. skeleton from landmarks ----------
V = verts(lowo); H = V[:, 2].max()
arm = bpy.data.armatures.new('Armature'); rig = bpy.data.objects.new('Armature', arm); sc.collection.objects.link(rig)
bpy.context.view_layer.objects.active = rig
for o in sc.objects: o.select_set(o is rig)
bpy.ops.object.mode_set(mode='EDIT')
eb = arm.edit_bones
def bone(name, head, tail, parent=None, connect=False, roll=0.0):
    b = eb.new(name); b.head = Vector(head); b.tail = Vector(tail); b.roll = roll
    if parent: b.parent = eb[parent]; b.use_connect = connect
    return b
def slab(z0, z1):                                  # vertices in a horizontal slab
    return V[(V[:, 2] >= z0) & (V[:, 2] < z1)]

if KIND == 'human':
    bone('root', (0, 0, 0), (0, 0.2 * H, 0))   # UE convention: root at the feet, pointing forward-ish
    pz = 0.53 * H; cz = 0.47 * H
    bone('pelvis', (0, 0, cz + 0.02 * H), (0, 0, pz + 0.03 * H), 'root')
    bone('spine_01', (0, 0, pz + 0.03 * H), (0, 0, 0.64 * H), 'pelvis', True)
    bone('spine_02', (0, 0, 0.64 * H), (0, 0, 0.72 * H), 'spine_01', True)
    bone('spine_03', (0, 0, 0.72 * H), (0, 0, 0.80 * H), 'spine_02', True)
    bone('neck_01', (0, 0, 0.83 * H), (0, 0, 0.88 * H), 'spine_03')
    bone('head', (0, 0, 0.88 * H), (0, 0, H), 'neck_01', True)
    torso = slab(0.68 * H, 0.74 * H); half = np.percentile(np.abs(torso[:, 0]), 97)   # chest half-width
    for sgn, sd in ((1, 'l'), (-1, 'r')):
        side = V[V[:, 0] * sgn > half * 1.15]                     # arms: everything wider than the chest
        side = side[(side[:, 2] > 0.30 * H) & (side[:, 2] < 0.85 * H)]
        tip = side[np.argmax(side[:, 0] * sgn - 0.3 * side[:, 2])]  # fingertips: far out and low
        sh = np.array([sgn * (half * 0.95), 0.0, 0.81 * H])
        d = tip - sh; L = np.linalg.norm(d); dn = d / L
        wr = sh + dn * (L - 0.105 * H)
        el = (sh + wr) / 2 + np.array([0, 0.015 * H, 0])            # elbows bend backwards slightly
        bone('clavicle_' + sd, (sgn * 0.02 * H, 0, 0.80 * H), tuple(sh), 'spine_03')
        bone('upperarm_' + sd, tuple(sh), tuple(el), 'clavicle_' + sd, True)
        bone('lowerarm_' + sd, tuple(el), tuple(wr), 'upperarm_' + sd, True)
        bone('hand_' + sd, tuple(wr), tuple(tip), 'lowerarm_' + sd, True)
        legs = slab(0.04 * H, 0.10 * H); legs = legs[legs[:, 0] * sgn > 0]
        ax, ay = np.median(legs[:, 0]), np.median(legs[:, 1])
        hip = (ax * 0.85, 0, cz + 0.04 * H); knee = (ax * 0.95, -0.01 * H, 0.285 * H); ank = (ax, ay + 0.01 * H, 0.05 * H)
        foot = V[(V[:, 2] < 0.04 * H) & (V[:, 0] * sgn > 0)]; toe_y = np.percentile(foot[:, 1], 2)   # front is -Y
        bone('thigh_' + sd, hip, knee, 'pelvis')
        bone('calf_' + sd, knee, ank, 'thigh_' + sd, True)
        bone('foot_' + sd, ank, (ax, ay + 0.6 * (toe_y - ay), 0.015 * H), 'calf_' + sd, True)
        bone('ball_' + sd, (ax, ay + 0.6 * (toe_y - ay), 0.015 * H), (ax, toe_y, 0.015 * H), 'foot_' + sd, True)
else:  # dog: the body runs along Y, head at -Y
    L = V[:, 1].max() - V[:, 1].min(); y0 = V[:, 1].min(); y1 = V[:, 1].max()
    def at(fy): return y0 + fy * L
    bodyz = np.median(slab(0.45 * H, 0.75 * H)[:, 2]) if len(slab(0.45 * H, 0.75 * H)) else 0.6 * H
    bone('root', (0, 0, 0), (0, -0.2 * L, 0))
    bone('pelvis', (0, at(0.72), bodyz), (0, at(0.62), bodyz), 'root')
    bone('spine_01', (0, at(0.62), bodyz), (0, at(0.50), bodyz), 'pelvis', True)
    bone('spine_02', (0, at(0.50), bodyz), (0, at(0.38), bodyz + 0.03 * H), 'spine_01', True)
    hd = V[V[:, 1] < at(0.22)]; hz = np.median(hd[:, 2])
    bone('neck_01', (0, at(0.38), bodyz + 0.03 * H), (0, at(0.25), hz), 'spine_02', True)
    bone('head', (0, at(0.25), hz), (0, y0, hz - 0.05 * H), 'neck_01', True)
    tl = V[V[:, 1] > at(0.80)]; tz = np.percentile(tl[:, 2], 90)
    bone('tail_01', (0, at(0.74), bodyz + 0.05 * H), (0, at(0.84), tz), 'pelvis')
    bone('tail_02', (0, at(0.84), tz), (0, at(0.70), tz + 0.02 * H), 'tail_01', True)
    leg = slab(0.0, 0.25 * H)
    for fy0, fy1, nm in ((0.0, 0.5, 'front'), (0.5, 1.0, 'back')):
        part = leg[(leg[:, 1] >= at(fy0)) & (leg[:, 1] < at(fy1))]
        for sgn, sd in ((1, 'l'), (-1, 'r')):
            p = part[part[:, 0] * sgn > 0]; lx, ly = np.median(p[:, 0]), np.median(p[:, 1])
            top = (lx, ly, bodyz); mid = (lx, ly + (0.02 if nm == 'front' else -0.04) * L, 0.45 * H)
            low = (lx, ly, 0.12 * H); paw = (lx, ly - 0.05 * L, 0.01 * H)
            par = 'spine_02' if nm == 'front' else 'pelvis'
            bone('%s_upper_%s' % (nm, sd), top, mid, par)
            bone('%s_lower_%s' % (nm, sd), mid, low, '%s_upper_%s' % (nm, sd), True)
            bone('%s_paw_%s' % (nm, sd), low, paw, '%s_lower_%s' % (nm, sd), True)
bpy.ops.object.mode_set(mode='OBJECT')
log['bones'] = len(arm.bones)

# ---------- 5. weights: heat weighting on the mesh itself; if that leaves skin behind (open or fragmented
# meshes), heat-weight a closed voxel proxy instead and copy its weights over ----------
def count_unweighted():
    return sum(1 for v in lowo.data.vertices if not any(g.weight > 0.01 for g in v.groups))
def rescale(k):                                     # bone heat fails on small meshes: weight a small character at 10x
    for o in (lowo, rig):
        for x in sc.objects: x.select_set(x is o)
        bpy.context.view_layer.objects.active = o; o.scale = (k, k, k)
        bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
UP = 10.0 if SIZE < 1.2 else 1.0
if UP != 1: rescale(UP)
for o in sc.objects: o.select_set(False)
lowo.select_set(True); rig.select_set(True); bpy.context.view_layer.objects.active = rig
bpy.ops.object.parent_set(type='ARMATURE_AUTO')
if UP != 1:
    lowo.parent = None; lowo.modifiers.clear(); rescale(1 / UP)
    for o in sc.objects: o.select_set(False)
    lowo.select_set(True); rig.select_set(True); bpy.context.view_layer.objects.active = rig
    bpy.ops.object.parent_set(type='ARMATURE')
log['weights'] = 'direct'; un = count_unweighted()
if un > 0.02 * len(lowo.data.vertices):
    log['direct_unweighted'] = un; log['weights'] = 'proxy'
    lowo.vertex_groups.clear()
    proxy = lowo.copy(); proxy.data = lowo.data.copy(); proxy.name = 'PROXY'; sc.collection.objects.link(proxy)
    for m_ in list(proxy.modifiers): proxy.modifiers.remove(m_)
    proxy.parent = None; proxy.matrix_world = lowo.matrix_world.copy()
    rm = proxy.modifiers.new('rm', 'REMESH'); rm.mode = 'VOXEL'; rm.voxel_size = 0.008 * HEIGHT / 1.8 if KIND == 'human' else 0.02 * SIZE
    bpy.context.view_layer.objects.active = proxy
    for o in sc.objects: o.select_set(o is proxy)
    bpy.ops.object.modifier_apply(modifier='rm')
    log['proxy_pieces_removed'] = drop_small(proxy, 0.2)[0]   # keep the main solid only; bubbles break heat weighting
    for o in sc.objects: o.select_set(False)
    proxy.select_set(True); rig.select_set(True); bpy.context.view_layer.objects.active = rig
    bpy.ops.object.parent_set(type='ARMATURE_AUTO')
    dt = lowo.modifiers.new('dt', 'DATA_TRANSFER'); dt.object = proxy; dt.use_vert_data = True
    dt.data_types_verts = {'VGROUP_WEIGHTS'}; dt.vert_mapping = 'POLYINTERP_NEAREST'
    dt.layers_vgroup_select_src = 'ALL'; dt.layers_vgroup_select_dst = 'NAME'
    for b in arm.bones: lowo.vertex_groups.new(name=b.name)
    bpy.context.view_layer.objects.active = lowo
    for o in sc.objects: o.select_set(o is lowo)
    bpy.ops.object.modifier_move_to_index(modifier='dt', index=0)
    bpy.ops.object.modifier_apply(modifier='dt')
    bpy.data.objects.remove(proxy)
    un = count_unweighted()
log['unweighted_verts'] = un

# ---------- 6. export ----------
for o in sc.objects: o.select_set(o in (lowo, rig))
bpy.context.view_layer.objects.active = rig
fbx = os.path.join(OUTD, 'SK_%s.fbx' % NAME)
bpy.ops.export_scene.fbx(filepath=fbx, use_selection=True, object_types={'ARMATURE', 'MESH'}, axis_forward='-Z', axis_up='Y',
                         global_scale=1.0, apply_unit_scale=True, apply_scale_options='FBX_SCALE_ALL', mesh_smooth_type='FACE',
                         add_leaf_bones=False, primary_bone_axis='Y', secondary_bone_axis='X', bake_anim=False, path_mode='STRIP', embed_textures=False)
log['fbx'] = fbx

# ---------- 7. previews: rest pose and a test pose ----------
w = bpy.data.worlds.new('W'); sc.world = w; w.use_nodes = True
w.node_tree.nodes['Background'].inputs[0].default_value = (0.8, 0.8, 0.8, 1)
sun = bpy.data.objects.new('Sun', bpy.data.lights.new('Sun', 'SUN')); sun.data.energy = 3; sun.rotation_euler = (0.7, 0.2, -0.5); sc.collection.objects.link(sun)
cam = bpy.data.objects.new('Cam', bpy.data.cameras.new('Cam')); sc.collection.objects.link(cam); sc.camera = cam
cam.data.type = 'ORTHO'; V = verts(lowo); size = float((V.max(0) - V.min(0)).max()); cam.data.ortho_scale = size * 1.15
ctr = Vector(((V.min(0) + V.max(0)) / 2).tolist())
sc.render.engine = 'BLENDER_EEVEE' if 'BLENDER_EEVEE' in [e.identifier for e in bpy.types.RenderSettings.bl_rna.properties['engine'].enum_items] else 'BLENDER_EEVEE_NEXT'
sc.render.resolution_x = sc.render.resolution_y = 600
rig.show_in_front = True
def shoot(tag):
    files = []
    for i, d in enumerate([(0, -1, 0.15), (1, -1, 0.3), (1, 0, 0.1), (-1, 1, 0.3)]):
        dv = Vector(d).normalized(); cam.location = ctr + dv * size * 3
        cam.rotation_euler = (ctr - cam.location).to_track_quat('-Z', 'Y').to_euler()
        fp = os.path.join(CACHE, '%s_%s_%d.png' % (NAME, tag, i)); sc.render.filepath = fp; bpy.ops.render.render(write_still=True); files.append(fp)
    ims = [bpy.data.images.load(fp) for fp in files]; W = 600
    sheet = bpy.data.images.new('sheet_' + tag, W * 4, W); px = np.zeros((W, W * 4, 4), np.float32)
    for k, im in enumerate(ims):
        a = np.empty(W * W * 4, np.float32); im.pixels.foreach_get(a); px[:, k * W:(k + 1) * W] = a.reshape(W, W, 4)
    sheet.pixels.foreach_set(px.ravel()); out = os.path.join(CACHE, '%s_%s_sheet.png' % (NAME, tag))
    sheet.filepath_raw = out; sheet.file_format = 'PNG'; sheet.save(); return out
log['sheet_rest'] = shoot('rest')
pb = rig.pose.bones
def rot(n, axis, deg):
    if n in pb: pb[n].rotation_mode = 'XYZ'; setattr(pb[n].rotation_euler, axis, math.radians(deg))
if KIND == 'human':
    rot('upperarm_l', 'x', 50); rot('lowerarm_l', 'x', 60); rot('thigh_r', 'x', 40); rot('calf_r', 'x', -60); rot('head', 'z', 30)
else:
    rot('front_upper_l', 'x', 35); rot('back_upper_r', 'x', -30); rot('head', 'x', 20); rot('tail_01', 'x', 30)
bpy.context.view_layer.update()
log['sheet_pose'] = shoot('pose')
for b in pb: b.rotation_euler = (0, 0, 0)
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(CACHE, '%s.blend' % NAME))
log['seconds'] = round(time.time() - t0, 1)
print('RESULT ' + json.dumps(log))
