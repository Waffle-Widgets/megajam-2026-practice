# Meshy-rigged character -> Unreal-ready FBX with Walk and Idle. Headless:
#   blender -b --factory-startup --python Art/Blender/meshy_character.py -- <rigged.glb> <Name> dog|smart <height_cm> [tris] [original.glb]
# dog   = Meshy's Quadruped Dog rig (bones Hips, chest, head, frontleg*, backleg*, tail*); keeps Meshy's own walk
#         (the GLB's action) as "Walk" and adds a procedural "Idle".
# smart = Meshy's Smart Rig (bones Bone_000...); legs, arms, head and tail are found by where the bones sit, then a
#         procedural waddle "Walk" and "Idle" are keyed.
# Writes Art/Blender/export/Characters/<Name>/SK_<Name>.fbx + T_<Name>_BaseColor.png (outside Content/: copy the
# folder into Content/Game/Imported/ with Unreal open so Interchange imports mesh, skeleton and both animations),
# and check sheets in Art/Blender/cache/<Name>_*.png.
# The scene is in centimetres (1 unit = 1 cm, scale applied) so the FBX holds plain cm numbers for the bind pose and
# the animation (see walk_cycle.py for why).
import bpy, sys, os, math, json
import numpy as np
from mathutils import Vector, Quaternion, Matrix

a = sys.argv[sys.argv.index('--') + 1:]
GLB, NAME, KIND, HEIGHT = a[0], a[1], a[2], float(a[3])
TRIS = int(a[4]) if len(a) > 4 else 30000
REPO = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..'))
CACHE = os.path.join(REPO, 'Art', 'Blender', 'cache'); os.makedirs(CACHE, exist_ok=True)
OUTD = os.path.join(REPO, 'Art', 'Blender', 'export', 'Characters', NAME); os.makedirs(OUTD, exist_ok=True)
log = {}

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=GLB)
sc = bpy.context.scene
for o in list(sc.objects):
    if o.type == 'MESH' and o.parent is None: bpy.data.objects.remove(o)      # Meshy's stray Icosphere
rig = [o for o in sc.objects if o.type == 'ARMATURE'][0]
mesh = [o for o in sc.objects if o.type == 'MESH'][0]
log['bones'] = len(rig.data.bones)


def action_fcurves(act):
    """All F-curves of an action (Blender 5 keeps them in layers / strips / channel bags)."""
    if hasattr(act, 'fcurves'): return list(act.fcurves)
    out = []
    for ly in act.layers:
        for st in ly.strips:
            for cb in st.channelbags: out.extend(cb.fcurves)
    return out


def world_verts(o):
    dg = bpy.context.evaluated_depsgraph_get(); e = o.evaluated_get(dg); me = e.to_mesh()
    V = np.array([e.matrix_world @ v.co for v in me.vertices]); e.to_mesh_clear(); return V


# ---------- 1. centimetre scene, real height, transforms applied ----------
meshy_act = rig.animation_data.action if rig.animation_data else None
if rig.animation_data: rig.animation_data.action = None          # measure and apply in the rest pose
for b in rig.pose.bones:                                          # (the bones keep the action's last pose otherwise)
    b.location = (0, 0, 0); b.rotation_quaternion = (1, 0, 0, 0); b.rotation_euler = (0, 0, 0); b.scale = (1, 1, 1)
bpy.context.view_layer.update()
V = world_verts(mesh); h = V[:, 2].max() - V[:, 2].min()
k = HEIGHT / h
sc.unit_settings.scale_length = 0.01
s_obj = rig.matrix_world.to_scale()[0] * k                       # bone-local units grow by this much
c = (V.min(0) + V.max(0)) / 2
rig.matrix_world = Matrix.Translation(Vector((-c[0] * k, -c[1] * k, -V[:, 2].min() * k))) @ Matrix.Scale(k, 4) @ rig.matrix_world
bpy.context.view_layer.update()
for o in sc.objects: o.select_set(o in (rig, mesh))
bpy.context.view_layer.objects.active = rig
bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
if meshy_act:                                                   # pose-bone locations are in bone units: rescale them
    for fc in action_fcurves(meshy_act):
        # Meshy's dog walk shrinks Hips to 0.681 and shifts it to keep the feet down, so the walking dog was 68% of
        # the standing one. Drop the scale and the constant shift; keep the bob.
        if fc.data_path.startswith('pose.bones["Hips"]') and fc.data_path.endswith('.scale'):
            for kp in fc.keyframe_points: kp.co[1] = 1.0; kp.handle_left[1] = 1.0; kp.handle_right[1] = 1.0
        if fc.data_path.startswith('pose.bones["Hips"]') and fc.data_path.endswith('.location'):
            mean = sum(kp.co[1] for kp in fc.keyframe_points) / max(1, len(fc.keyframe_points))
            for kp in fc.keyframe_points: kp.co[1] -= mean; kp.handle_left[1] -= mean; kp.handle_right[1] -= mean
        if fc.data_path.endswith('.location'):
            for kp in fc.keyframe_points:
                kp.co[1] *= s_obj; kp.handle_left[1] *= s_obj; kp.handle_right[1] *= s_obj
bpy.context.view_layer.update()
V = world_verts(mesh); log['size_cm'] = [round(float(x), 1) for x in (V.max(0) - V.min(0))]

# ---------- 2. game mesh: fewer triangles, one base-colour texture ----------
bpy.context.view_layer.objects.active = mesh
for o in sc.objects: o.select_set(o is mesh)
n0 = len(mesh.data.polygons)
if n0 > TRIS * 1.1:
    d = mesh.modifiers.new('dec', 'DECIMATE'); d.ratio = TRIS / n0
    bpy.ops.object.modifier_move_to_index(modifier='dec', index=0)
    bpy.ops.object.modifier_apply(modifier='dec')
log['tris'] = [n0, len(mesh.data.polygons)]
# Meshy's UV atlas is hundreds of small islands; decimating drags triangles across island edges and the
# neighbouring colours show as pale scratches. So: fresh smart-project UVs on the game mesh, and the colour baked
# onto them from Meshy's ORIGINAL full-detail model (SRC_GLB, uncut UVs), lined up by its bounding box.
SRC_GLB = a[5] if len(a) > 5 else GLB
before = set(sc.objects)
bpy.ops.import_scene.gltf(filepath=SRC_GLB)
new = [o for o in sc.objects if o not in before]
for o in new:
    if o.type == 'MESH' and len(o.data.polygons) < 500: bpy.data.objects.remove(o)   # the stray Icosphere
new = [o for o in sc.objects if o not in before]
srcm = [o for o in new if o.type == 'MESH']
for o in sc.objects: o.select_set(o in srcm)
bpy.context.view_layer.objects.active = srcm[0]
if len(srcm) > 1: bpy.ops.object.join()
src = bpy.context.view_layer.objects.active
mw = src.matrix_world.copy()                       # a rigged GLB parents the mesh to a scaled, turned armature
src.parent = None; src.matrix_world = mw
for o in new:
    if o is not src and o.name in bpy.data.objects: bpy.data.objects.remove(o)
src.modifiers.clear(); src.vertex_groups.clear()
bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
S = np.array([src.matrix_world @ v.co for v in src.data.vertices]); L = world_verts(mesh)
ks = (L[:, 2].max() - L[:, 2].min()) / (S[:, 2].max() - S[:, 2].min())
sc_ = Vector(((S.min(0) + S.max(0)) / 2).tolist()); lc_ = Vector(((L.min(0) + L.max(0)) / 2).tolist())
src.data.transform(Matrix.Translation(lc_) @ Matrix.Scale(ks, 4) @ Matrix.Translation(-sc_))
S = np.array([v.co for v in src.data.vertices])
# the bounding box can line up while the body is turned (Meshy's rigged GLB faces the other way): try the four
# turns/mirrors about the vertical axis and keep the one whose surface lies closest to the game mesh
from mathutils.kdtree import KDTree
pick = L[np.random.default_rng(0).choice(len(L), min(3000, len(L)), replace=False)]
best = None
for nm, T in (('as is', Matrix.Identity(4)), ('turn 180', Matrix.Rotation(math.pi, 4, 'Z')),
              ('mirror x', Matrix.Scale(-1, 4, (1, 0, 0))), ('mirror y', Matrix.Scale(-1, 4, (0, 1, 0)))):
    M_ = Matrix.Translation(lc_) @ T @ Matrix.Translation(-lc_)
    kd = KDTree(len(S))
    for i, p in enumerate(S): kd.insert(M_ @ Vector(p.tolist()), i)
    kd.balance()
    dist = float(np.mean([kd.find(Vector(p.tolist()))[2] for p in pick]))
    log.setdefault('bake_fit_mean_cm', {})[nm] = round(dist, 3)
    if best is None or dist < best[0]: best = (dist, nm, M_)
if best[1] != 'as is':
    src.data.transform(best[2])
    if best[1].startswith('mirror'): src.data.flip_normals()
log['bake_fit'] = best[1]
S = np.array([v.co for v in src.data.vertices])
log['bake_src_fit_cm'] = [round(float(x), 2) for x in (S.min(0) - L.min(0))] + [round(float(x), 2) for x in (S.max(0) - L.max(0))]
img = None
for m in src.data.materials:
    for n in m.node_tree.nodes:
        if n.type == 'TEX_IMAGE' and n.image and any(l.to_socket.name == 'Base Color' for l in n.outputs['Color'].links):
            img = n.image
ms = bpy.data.materials.new('M_Src'); ms.use_nodes = True; nts = ms.node_tree
for n in list(nts.nodes): nts.nodes.remove(n)
tx = nts.nodes.new('ShaderNodeTexImage'); tx.image = img
emn = nts.nodes.new('ShaderNodeEmission'); on = nts.nodes.new('ShaderNodeOutputMaterial')
nts.links.new(tx.outputs['Color'], emn.inputs['Color']); nts.links.new(emn.outputs['Emission'], on.inputs['Surface'])
src.data.materials.clear(); src.data.materials.append(ms)
# fresh UVs on the game mesh
bpy.context.view_layer.objects.active = mesh
for o in sc.objects: o.select_set(o is mesh)
while mesh.data.uv_layers: mesh.data.uv_layers.remove(mesh.data.uv_layers[0])
mesh.data.uv_layers.new(name='UV')
bpy.ops.object.mode_set(mode='EDIT'); bpy.ops.mesh.select_all(action='SELECT')
bpy.ops.uv.smart_project(angle_limit=math.radians(66), island_margin=0.004, correct_aspect=True)
bpy.ops.uv.select_all(action='SELECT'); bpy.ops.uv.pack_islands(margin=0.003, rotate=True)
bpy.ops.object.mode_set(mode='OBJECT')
TEX = 2048
png = bpy.data.images.new('T_%s_BaseColor' % NAME, TEX, TEX)
mt = bpy.data.materials.new('M_%s' % NAME); mt.use_nodes = True; nt = mt.node_tree
tn = nt.nodes.new('ShaderNodeTexImage'); tn.image = png; nt.nodes.active = tn
nt.links.new(tn.outputs['Color'], nt.nodes['Principled BSDF'].inputs['Base Color'])
nt.nodes['Principled BSDF'].inputs['Roughness'].default_value = 0.8
mesh.data.materials.clear(); mesh.data.materials.append(mt)
prefs = bpy.context.preferences.addons['cycles'].preferences
for dt in ('OPTIX', 'CUDA'):
    try:
        prefs.compute_device_type = dt; prefs.get_devices()
        if any(d_.type == dt for d_ in prefs.devices): break
    except TypeError: pass
for d_ in prefs.devices: d_.use = d_.type != 'CPU'
sc.render.engine = 'CYCLES'; sc.cycles.device = 'GPU'; sc.cycles.samples = 1
bk = sc.render.bake; bk.use_selected_to_active = True; bk.cage_extrusion = 0.008 * HEIGHT; bk.max_ray_distance = 0.03 * HEIGHT; bk.margin = 8
for o in sc.objects: o.select_set(o in (src, mesh))
bpy.context.view_layer.objects.active = mesh
rig.data.pose_position = 'REST'        # bake the mesh where it is drawn (its raw data can sit elsewhere), unposed
bpy.context.view_layer.update()
bpy.ops.object.bake(type='EMIT')
rig.data.pose_position = 'POSE'
png.filepath_raw = os.path.join(OUTD, 'T_%s_BaseColor.png' % NAME); png.file_format = 'PNG'; png.save()
bpy.data.objects.remove(src)
mesh.name = NAME; rig.name = 'Armature'

# ---------- 3. animations ----------
pb = rig.pose.bones
SIDE = Vector((1, 0, 0)); FWD = Vector((0, -1, 0)); UP = Vector((0, 0, 1))
H = HEIGHT
FPS = 30; sc.render.fps = FPS


def local_q(name, axis, deg):
    m = pb[name].bone.matrix_local.to_3x3()
    return Quaternion((m.inverted() @ axis).normalized(), math.radians(deg))


def reset():
    for b in pb:
        b.rotation_mode = 'QUATERNION'; b.rotation_quaternion = (1, 0, 0, 0); b.location = (0, 0, 0); b.scale = (1, 1, 1)
    bpy.context.view_layer.update()


def sign_for(name, axis, end, want):
    reset(); a0 = pb[end].tail.copy()
    pb[name].rotation_quaternion = local_q(name, axis, 20); bpy.context.view_layer.update()
    s = 1.0 if (pb[end].tail - a0).dot(want) > 0 else -1.0
    reset(); return s


def chain_from(root):
    out = [root]
    while True:
        kids = [b.name for b in rig.data.bones[out[-1]].children]
        if not kids: return out
        out.append(kids[0])


def new_action(name):
    act = bpy.data.actions.new(name); rig.animation_data_create(); rig.animation_data.action = act; return act


def key_all(f):
    for b in pb:
        b.keyframe_insert('rotation_quaternion', frame=f); b.keyframe_insert('location', frame=f)


bones = rig.data.bones
if KIND == 'dog':
    walk = meshy_act; walk.name = 'Walk'
    tail = [n for n in ('tailstart', 'tail1', 'tail2', 'tail3') if n in pb]
    spine, head = 'chest', 'head'
    legs = arms = []
else:
    # Smart Rig: root = the bone without a parent; its chain up = spine; branches = legs (low), arms (mid), head
    # (highest), tail (reaches far behind, +Y).
    root = [b for b in bones if b.parent is None][0].name
    def tipz(ch): return bones[ch[-1]].tail_local.z
    def far_y(ch): return max(bones[n].tail_local.y for n in ch)
    branches = {}
    def walk_tree(n, depth=0):
        for ch in bones[n].children: branches.setdefault(n, []).append(ch.name); walk_tree(ch.name, depth + 1)
    walk_tree(root)
    hip = bones[root].children[0].name if bones[root].children else root   # Bone_001: where legs and tail start
    hip_kids = [ch.name for ch in bones[hip].children]
    chains = {k_: chain_from(k_) for k_ in hip_kids}
    tail_root = max(hip_kids, key=lambda k_: far_y(chains[k_]))
    leg_roots = [k_ for k_ in hip_kids if k_ != tail_root and tipz(chains[k_]) < 0.25 * H]
    spine_root = [k_ for k_ in hip_kids if k_ not in leg_roots and k_ != tail_root][0]
    spine_chain = []; n = spine_root
    while True:                                        # follow the spine to the bone where arms branch off
        spine_chain.append(n); kids = [ch.name for ch in bones[n].children]
        if len(kids) != 1: break
        n = kids[0]
    chest = spine_chain[-1]
    ck = {ch.name: chain_from(ch.name) for ch in bones[chest].children}
    head_root = max(ck, key=lambda k_: tipz(ck[k_]))
    arm_roots = [k_ for k_ in ck if k_ != head_root]
    tail = chains[tail_root]
    legs = []
    for r in sorted(leg_roots, key=lambda r: bones[r].head_local.x):
        ch = chains[r]; legs.append((ch[0], ch[1], ch[-1], 0.0 if len(legs) == 0 else math.pi))
    arms = []
    for r in sorted(arm_roots, key=lambda r: bones[r].head_local.x):
        ch = ck[r]; arms.append((ch[0], ch[1], ch[-1], math.pi if len(arms) == 0 else 0.0))   # opposite to the leg
    spine, head = chest, head_root
    log['found'] = {'root': root, 'hip': hip, 'legs': legs, 'arms': arms, 'spine': spine_chain, 'head': ck[head_root], 'tail': tail}

    # Walk: a chibi waddle, 0.8 s a loop (two steps)
    s_sw = {u: sign_for(u, SIDE, e, FWD) for u, l, e, ph in legs}
    s_kn = {l: sign_for(l, SIDE, e, -FWD) for u, l, e, ph in legs}
    s_as = {u: sign_for(u, SIDE, e, FWD) for u, l, e, ph in arms}
    N = 24; walk = new_action('Walk'); hm = pb[hip].bone.matrix_local.to_3x3().inverted()
    for f in range(N + 1):
        p = 2 * math.pi * (f % N) / N; reset()
        for u, l, e, ph in legs:
            q = p + ph
            pb[u].rotation_quaternion = local_q(u, SIDE, s_sw[u] * 24 * math.sin(q))
            pb[l].rotation_quaternion = local_q(l, SIDE, s_kn[l] * (4 + 30 * max(0.0, math.cos(q))))
        for u, l, e, ph in arms:
            pb[u].rotation_quaternion = local_q(u, SIDE, s_as[u] * 14 * math.sin(p + ph))
        pb[hip].rotation_quaternion = local_q(hip, FWD, 5 * math.sin(p))            # side-to-side waddle
        pb[head].rotation_quaternion = local_q(head, FWD, -4 * math.sin(p))
        for i, t in enumerate(tail):
            pb[t].rotation_quaternion = local_q(t, UP, 5 * math.sin(p - 0.5 * i))
        pb[hip].location = hm @ Vector((0, 0, -0.025 * H * math.cos(2 * p) + 0.01 * H))
        key_all(f)

# Idle (both): breathing, a slow head turn and a lazy tail sway, 2 s a loop
N = 60; idle = new_action('Idle')
for f in range(N + 1):
    p = 2 * math.pi * (f % N) / N; reset()
    if spine in pb: pb[spine].rotation_quaternion = local_q(spine, SIDE, 2.5 * math.sin(p))
    if head in pb: pb[head].rotation_quaternion = local_q(head, UP, 6 * math.sin(p)) @ local_q(head, SIDE, -2 * math.sin(p))
    for i, t in enumerate(tail):
        pb[t].rotation_quaternion = local_q(t, UP, (7 if KIND == 'dog' else 4) * math.sin(p - 0.6 * i))
    for u, l, e, ph in arms:
        pb[u].rotation_quaternion = local_q(u, SIDE, 3 * math.sin(p))
    key_all(f)
log['actions'] = [ac.name for ac in bpy.data.actions]
for ac in bpy.data.actions:
    if ac not in (walk, idle): bpy.data.actions.remove(ac)

# ---------- 4. check sheets: walk from the side and front, idle from the front ----------
w_ = bpy.data.worlds.new('W'); sc.world = w_; w_.use_nodes = True; w_.node_tree.nodes['Background'].inputs[0].default_value = (0.85, 0.85, 0.85, 1)
sun = bpy.data.objects.new('Sun', bpy.data.lights.new('Sun', 'SUN')); sun.data.energy = 3; sun.rotation_euler = (0.7, 0.2, -0.5); sc.collection.objects.link(sun)
cam = bpy.data.objects.new('Cam', bpy.data.cameras.new('Cam')); sc.collection.objects.link(cam); sc.camera = cam
cam.data.type = 'ORTHO'; cam.data.ortho_scale = H * 1.6; cam.data.clip_end = 100000
sc.render.engine = 'BLENDER_EEVEE'; sc.render.resolution_x = 300; sc.render.resolution_y = 300
ctr = Vector((0, 0, H / 2))


def sheet(act, view, frames, tag):
    rig.animation_data.action = act
    cam.location = ctr + view * H * 4; cam.rotation_euler = (ctr - cam.location).to_track_quat('-Z', 'Y').to_euler()
    tiles = []
    for i, f in enumerate(frames):
        sc.frame_set(f); fp = os.path.join(CACHE, '%s_%s_%d.png' % (NAME, tag, i)); sc.render.filepath = fp
        bpy.ops.render.render(write_still=True); tiles.append(fp)
    ims = [bpy.data.images.load(fp) for fp in tiles]; W = 300; out = np.zeros((W, W * len(ims), 4), np.float32)
    for i, im in enumerate(ims):
        x = np.empty(W * W * 4, np.float32); im.pixels.foreach_get(x); out[:, i * W:(i + 1) * W] = x.reshape(W, W, 4)
    s = bpy.data.images.new('sheet_' + tag, W * len(ims), W); s.pixels.foreach_set(out.ravel())
    s.filepath_raw = os.path.join(CACHE, '%s_%s.png' % (NAME, tag)); s.file_format = 'PNG'; s.save(); return s.filepath_raw


wl = int(walk.frame_range[1])
log['walk_frames'] = [int(walk.frame_range[0]), wl]
log['sheet_walk_side'] = sheet(walk, Vector((1, 0, 0.15)).normalized(), [int(i * wl / 6) for i in range(6)], 'walk_side')
log['sheet_walk_front'] = sheet(walk, Vector((0.35, -1, 0.35)).normalized(), [int(i * wl / 4) for i in range(4)], 'walk_front')
log['sheet_idle'] = sheet(idle, Vector((0.5, -1, 0.5)).normalized(), [0, 15, 30, 45], 'idle')

# ---------- 5. export mesh + rig + Walk and Idle ----------
rig.animation_data.action = walk; sc.frame_set(0)
for o in sc.objects: o.select_set(o in (mesh, rig))
bpy.context.view_layer.objects.active = rig
fbx = os.path.join(OUTD, 'SK_%s.fbx' % NAME)
bpy.ops.export_scene.fbx(filepath=fbx, use_selection=True, object_types={'ARMATURE', 'MESH'}, axis_forward='-Z', axis_up='Y',
                         global_scale=1.0, apply_unit_scale=True, apply_scale_options='FBX_SCALE_ALL', mesh_smooth_type='FACE',
                         add_leaf_bones=False, primary_bone_axis='Y', secondary_bone_axis='X', bake_anim=True,
                         bake_anim_use_all_actions=True, bake_anim_use_nla_strips=False, bake_anim_force_startend_keying=True,
                         bake_anim_simplify_factor=0.0, path_mode='STRIP', embed_textures=False)
log['fbx'] = fbx
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(CACHE, '%s.blend' % NAME))
print('MESHYCHAR ' + json.dumps(log))
