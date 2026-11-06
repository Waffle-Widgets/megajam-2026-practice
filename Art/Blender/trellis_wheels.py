"""Cut the wheels out of a TRELLIS car so the game can spin them.

Run inside Blender (exec with globals): SRC = joined car object (e.g. 'TR_BRZ'), OUT_BODY / OUT_WHEEL = FBX names,
SP = folder for preview renders, PICK = (sign of x, 'front'|'rear') of the wheel to keep as the shared wheel mesh.
The generator makes each wheel a nearly closed drum fused flush into the fender, so a cylinder cut around the axle
(tyre radius + 4 mm) frees it as one piece.  The body gets a dark liner drum built from each hole's own edge loop, so
the arch does not look straight into the empty shell.  The wheel is mirrored to face +X (Unreal's right side; the car
Blueprint yaws the left wheels 180) with its origin on the axle at |x| = X_ORG, where the Blueprint places WheelFR.
The defaults are the BRZ coupe's; another car passes its own (all in game metres, see the RAV4 call in the devlog):
TYRE_R tyre radius, X_IN inner end of the cut, X_CAP liner depth, X_ORG wheel origin, PFX object-name prefix,
MAT / IMG the car's material and base-colour image, CAND_X / CAND_R the outer tyre-sidewall band for the liner colour,
EXPORT_DIR where the FBXs go, SAVE_AS a .blend to save the result to (for headless runs).
"""
import bpy, bmesh, numpy as np, math, os, time
from mathutils import Vector

t0 = time.time()
G = globals().get
TYRE_R = G('TYRE_R', 0.127); R_CUT = TYRE_R + G('CUT_PAD', 0.004); X_IN = G('X_IN', 0.19); X_CAP = G('X_CAP', 0.17); X_ORG = G('X_ORG', 0.30)
PFX = G('PFX', 'TR_BRZ'); MAT = G('MAT', 'M_CarT'); IMG = G('IMG', 'T_CarCoupeT_BaseColor'); CAND_X = G('CAND_X', 0.345); CAND_R = G('CAND_R', (0.105, 0.12))
SRC = globals().get('SRC', 'TR_BRZ'); OUT_BODY = globals().get('OUT_BODY', 'SM_CarCoupeT26'); OUT_WHEEL = globals().get('OUT_WHEEL', 'SM_CarCoupeTWheel')
PICK = globals().get('PICK', (-1, 'rear')); DO_EXPORT = globals().get('DO_EXPORT', True); SPIN_DEG = globals().get('SPIN_DEG', 37.0)
D = os.path.dirname(bpy.data.filepath); SP = globals().get('SP', D + '\\cache')
out = {}
src = bpy.data.objects[SRC]; col = src.users_collection[0]
for nm in (PFX + '_Body', PFX + '_WheelsCut', PFX + '_Wheel') + tuple(PFX + '_W%d' % i for i in range(4)):
    o = bpy.data.objects.get(nm)
    if o:
        m = o.data; bpy.data.objects.remove(o)
        if m.users == 0: bpy.data.meshes.remove(m)

def verts(me):
    V = np.empty(len(me.vertices) * 3, np.float32); me.vertices.foreach_get('co', V); return V.reshape(-1, 3)

# ---- wheel centres: lowest points split into two y groups, axle at tyre radius above the ground
body = src.copy(); body.data = src.data.copy(); body.name = body.data.name = PFX + '_Body'; col.objects.link(body)
body.location = (0, 0, 0); body.hide_render = False; body.hide_set(False); body.hide_viewport = False
me = body.data; V = verts(me); n = len(V)
zmin = float(V[:, 2].min()); wz = zmin + TYRE_R
low = V[V[:, 2] < zmin + 0.02]; ys = np.sort(low[:, 1]); g = np.argmax(np.diff(ys))
wy = {'front': float(np.median(ys[:g + 1])), 'rear': float(np.median(ys[g + 1:]))}   # nose is -Y in the mesh frame
out['axles'] = {'wz': round(wz, 4), 'wy': {k: round(v, 4) for k, v in wy.items()}}
wheels = [(sgn, k) for k in ('front', 'rear') for sgn in (1, -1)]

# ---- tag faces inside each wheel cylinder; keep only the biggest connected piece per wheel
wid = np.zeros(n, np.int32)
for i, (sgn, k) in enumerate(wheels):
    wid[(np.hypot(V[:, 1] - wy[k], V[:, 2] - wz) < R_CUT) & (sgn * V[:, 0] > X_IN)] = i + 1
bm = bmesh.new(); bm.from_mesh(me); bm.verts.ensure_lookup_table(); bm.faces.ensure_lookup_table()
lay = bm.faces.layers.int.new('wid')
for f in bm.faces:
    ids = {wid[v.index] for v in f.verts}
    f[lay] = ids.pop() if len(ids) == 1 and 0 not in ids else 0
seen = set(); comps = {i + 1: [] for i in range(4)}
for f in bm.faces:
    if f[lay] == 0 or f in seen: continue
    stack = [f]; seen.add(f); comp = []
    while stack:
        a = stack.pop(); comp.append(a)
        for e in a.edges:
            for b in e.link_faces:
                if b[lay] == a[lay] and b not in seen: seen.add(b); stack.append(b)
    comps[f[lay]].append(comp)
out['pieces'] = {}
for i, cs in comps.items():
    cs.sort(key=len, reverse=True); out['pieces'][str(wheels[i - 1])] = [len(c) for c in cs[:5]]
    for c in cs[1:]:
        for f in c: f[lay] = 0   # small slivers stay with the body
wm = bpy.data.meshes.new(PFX + '_WheelsCut'); wm.materials.append(bpy.data.materials[MAT])
bw = bm.copy(); lw = bw.faces.layers.int.get('wid')
bmesh.ops.delete(bw, geom=[f for f in bw.faces if f[lw] == 0], context='FACES')
bmesh.ops.delete(bw, geom=[v for v in bw.verts if not v.link_faces], context='VERTS')
bw.to_mesh(wm); bw.free()
wcut = bpy.data.objects.new(PFX + '_WheelsCut', wm); col.objects.link(wcut); wcut.hide_render = True
bmesh.ops.delete(bm, geom=[f for f in bm.faces if f[lay] != 0], context='FACES')
bmesh.ops.delete(bm, geom=[v for v in bm.verts if not v.link_faces], context='VERTS')   # loose points blow up the bounds

# ---- a dark texel for the liners: the darkest tyre-sidewall loop of the picked wheel (the tyre is painted, so black)
im = bpy.data.images[IMG]; S = im.size[0]
px = np.empty(S * S * 4, np.float32); im.pixels.foreach_get(px); px = px.reshape(S, S, 4)[..., :3]
uvl = wm.uv_layers.active.data; Vw = verts(wm); psgn, pk = PICK
r = np.hypot(Vw[:, 1] - wy[pk], Vw[:, 2] - wz)
cand = set(np.where((psgn * Vw[:, 0] > CAND_X) & (r > CAND_R[0]) & (r < CAND_R[1]))[0].tolist())
best = None
for p in wm.polygons:
    for li in p.loop_indices:
        if wm.loops[li].vertex_index in cand:
            u, v = uvl[li].uv; i_ = int(v * S) % S; j_ = int(u * S) % S
            m = float(px[max(0, i_ - 3):i_ + 4, max(0, j_ - 3):j_ + 4].max())
            if best is None or m < best[0]: best = (m, (float(u), float(v)))
del px
DUV = best[1]; out['liner_uv'] = best

# ---- arch liners: the boundary chains around each hole, extruded to a plane at |x| = X_CAP and fanned shut
uv = bm.loops.layers.uv.active; out['liners'] = {}
for sgn, k in wheels:
    yw = wy[k]
    def near(v): return math.hypot(v.co.y - yw, v.co.z - wz) < R_CUT + 0.05 and sgn * v.co.x > X_IN
    be = [e for e in bm.edges if len(e.link_faces) == 1 and near(e.verts[0]) and near(e.verts[1])]
    adj = {}
    for e in be:
        for v in e.verts: adj.setdefault(v, []).append(e)
    left = set(be); chains = []
    while left:
        e0 = left.pop(); stack = [e0]; chain = [e0]
        while stack:
            e = stack.pop()
            for v in e.verts:
                for e2 in adj[v]:
                    if e2 in left: left.discard(e2); stack.append(e2); chain.append(e2)
        chains.append(chain)
    chains.sort(key=len, reverse=True); be = [e for ch in chains if len(ch) >= 8 for e in ch]   # the hole's edge comes in broken chains
    res = bmesh.ops.extrude_edge_only(bm, edges=be)
    nv = [g_ for g_ in res['geom'] if isinstance(g_, bmesh.types.BMVert)]
    nf = [g_ for g_ in res['geom'] if isinstance(g_, bmesh.types.BMFace)]
    for v in nv: v.co.x = sgn * X_CAP
    ne = [g_ for g_ in res['geom'] if isinstance(g_, bmesh.types.BMEdge) and all(abs(abs(v.co.x) - X_CAP) < 1e-6 for v in g_.verts)]
    c = bm.verts.new(Vector((sgn * X_CAP, yw, wz))); caps = []
    for e in ne:
        try: caps.append(bm.faces.new((e.verts[0], e.verts[1], c)))
        except ValueError: pass
    for f in nf:
        f.normal_update(); ctr = f.calc_center_median()
        if f.normal.dot(Vector((0, yw - ctr.y, wz - ctr.z))) < 0: f.normal_flip()   # wall faces the axle
    for f in caps:
        f.normal_update()
        if f.normal.dot(Vector((sgn, 0, 0))) < 0: f.normal_flip()                   # cap faces the viewer
    for f in nf + caps:
        for l in f.loops: l[uv].uv = DUV
    out['liners'][str((sgn, k))] = {'chains': [len(ch) for ch in chains[:4]], 'wall': len(nf), 'cap': len(caps)}
bm.to_mesh(me); bm.free(); me.update()

# ---- the shared wheel: the picked one, mirrored to face +X, axle through the origin, origin at |x| = X_ORG
bw = bmesh.new(); bw.from_mesh(wm); bw.verts.ensure_lookup_table()
ymid = (wy['front'] + wy['rear']) / 2
keep = {v for v in bw.verts if psgn * v.co.x > 0 and ((v.co.y > ymid) == (pk == 'rear'))}
bmesh.ops.delete(bw, geom=[v for v in bw.verts if v not in keep], context='VERTS')
for v in bw.verts: v.co = Vector((psgn * v.co.x - X_ORG, v.co.y - wy[pk], v.co.z - wz))
if psgn < 0:
    for f in bw.faces: f.normal_flip()
wmesh = bpy.data.meshes.new(PFX + '_Wheel'); wmesh.materials.append(bpy.data.materials[MAT]); bw.to_mesh(wmesh); bw.free()
wob = bpy.data.objects.new(PFX + '_Wheel', wmesh); col.objects.link(wob); wob.hide_render = True
Vq = verts(wmesh); out['wheel'] = {'verts': len(wmesh.vertices), 'faces': len(wmesh.polygons), 'min': Vq.min(0).round(3).tolist(), 'max': Vq.max(0).round(3).tolist()}
out['body'] = {'verts': len(me.vertices), 'faces': len(me.polygons)}
V = verts(me); out['body_bounds'] = [V.min(0).round(3).tolist(), V.max(0).round(3).tolist()]

# ---- put four copies back on the body (spun by SPIN_DEG so anything poking through the fender shows) and render
inst = []
for i, (sgn, k) in enumerate(wheels):
    o = bpy.data.objects.new(PFX + '_W%d' % i, wmesh); col.objects.link(o)
    o.location = (sgn * X_ORG, wy[k], wz); o.rotation_euler = (math.radians(SPIN_DEG), 0, 0 if sgn > 0 else math.pi); o.hide_render = False; inst.append(o)
sc = bpy.context.scene; cam = bpy.data.objects.get('PV_Cam')
if cam is None:
    cam = bpy.data.objects.new('PV_Cam', bpy.data.cameras.new('PV_Cam')); col.objects.link(cam)
sc.camera = cam
vis = {o.name: o.hide_render for o in bpy.data.objects if o.type == 'MESH'}
for o in bpy.data.objects:
    if o.type == 'MESH': o.hide_render = True
res_ = (sc.render.resolution_x, sc.render.resolution_y); smp = sc.cycles.samples
sc.render.resolution_x = 900; sc.render.resolution_y = 600; sc.cycles.samples = 32
cl0, cr0 = cam.location.copy(), cam.rotation_euler.copy()
def shot(name, loc, tgt):
    cam.location = loc; cam.rotation_euler = (Vector(tgt) - Vector(loc)).to_track_quat('-Z', 'Y').to_euler()
    sc.render.filepath = SP + '\\%s.png' % name; bpy.ops.render.render(write_still=True)
body.hide_render = False
shot('wh_body_side', (2.3, -0.2, -0.05), (0, 0, -0.05))
for o in inst: o.hide_render = False
shot('wh_full_side', (2.3, -0.2, -0.05), (0, 0, -0.05))
shot('wh_full_fq', (1.6, -1.6, 0.45), (0, -0.3, -0.05))
shot('wh_full_low', (1.3, -1.2, -0.5), (0, -0.2, -0.15))
body.hide_render = True
for o in inst: o.hide_render = True
wob.hide_render = False; wob.location = (0, 0, 0)
shot('wh_wheel_face', (0.9, 0.1, -0.1), (0, 0, 0))
shot('wh_wheel_back', (-0.9, 0.1, -0.1), (0, 0, 0))
wob.hide_render = True
for nm, h in vis.items(): bpy.data.objects[nm].hide_render = h
for o in inst: o.hide_render = True
sc.render.resolution_x, sc.render.resolution_y = res_; sc.cycles.samples = smp
cam.location = cl0; cam.rotation_euler = cr0

# ---- export
if DO_EXPORT:
    def export(ob, name):
        for o in bpy.context.view_layer.objects: o.select_set(False)
        ob.hide_set(False); ob.hide_viewport = False; ob.select_set(True); bpy.context.view_layer.objects.active = ob
        bpy.ops.export_scene.fbx(filepath=(G('EXPORT_DIR') + chr(92) + name + '.fbx') if G('EXPORT_DIR') else D + '\\export\\%s.fbx' % name, use_selection=True, axis_forward='-Z', axis_up='Y', global_scale=1.0, apply_unit_scale=True, mesh_smooth_type='FACE', use_mesh_modifiers=True, path_mode='STRIP', embed_textures=False, bake_anim=False)
    export(body, OUT_BODY); export(wob, OUT_WHEEL)
    out['exported'] = [OUT_BODY, OUT_WHEEL]
body.location = (3, 1.5, 0)
if G('SAVE_AS'): bpy.ops.wm.save_as_mainfile(filepath=G('SAVE_AS'), copy=True)
out['s'] = round(time.time() - t0, 1)
result = out
