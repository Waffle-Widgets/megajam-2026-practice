# Run inside Blender via the MCP: set GLB, OUT, TAG (and STRIPS=True) then exec this file. Needs ai_car_clean.py next to it.
# Build the game coupe from a TRELLIS.2 GLB: import, smooth, lamps from the generator's own red texels,
# paint by position, normals, FBX export, preview renders. Runs inside Blender (exec'd by the MCP).
import bpy, bmesh, numpy as np, math, time
import os
REPO = globals().get('REPO', (os.environ.get('MEGAJAM_REPO') or os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(globals().get('__file__', os.path.join(os.getcwd(), 'Art', 'Blender', '_')))), '..', '..'))))   # repo = two folders up from this script; pass REPO=... or set MEGAJAM_REPO to override
D = REPO + r"\Art\Blender"; SP = D + r"\cache"                                   # cache: baked maps, lamp points (gitignored)
import os; os.makedirs(SP, exist_ok=True)
from mathutils import Vector
t0 = time.time()
GLB = globals().get('GLB', r"D:\AI\TRELLIS2\out\brz_r34flat.glb")
OUT = globals().get('OUT', 'SM_CarCoupeT19')
TAG = globals().get('TAG', 'v')
cl = {}; exec(open(D + r"\ai_car_clean.py").read(), cl)
out = {}
HEIGHT = 1.320 / 4.240 * 1.717          # BRZ roof-to-ground in game units

def fix_strips_and_orient(ob):
    """Some runs hang thin vertical strips under the floor. Split the mesh at sill height, drop every loose
    piece below it that is thinner than a tyre, then re-orient (wing at +Y) and re-centre."""
    me = ob.data
    nv = len(me.vertices); V = np.empty(nv * 3); me.vertices.foreach_get('co', V); V = V.reshape(nv, 3)
    zg = V[:, 2].max() - HEIGHT; zs = zg + 0.09
    # wheel axes (the lowest points are the two tyre bottoms): nothing inside a tyre circle is a strip. Below sill
    # height the generator's hub and spokes are thousands of loose slivers, and the thin-piece test ate them,
    # so every coupe up to T23 had its wheels cut flat 4 cm under the hub.
    low = V[V[:, 2] < V[:, 2].min() + 0.02]; ys = np.sort(low[:, 1]); g = np.argmax(np.diff(ys))
    wy = (float(np.median(ys[:g + 1])), float(np.median(ys[g + 1:]))); wz = float(V[:, 2].min()) + cl['TYRE_R']
    in_wheel = lambda c: abs(c[0]) > 0.15 and min(math.hypot(c[1] - wy[0], c[2] - wz), math.hypot(c[1] - wy[1], c[2] - wz)) < cl['TYRE_R'] + 0.02
    bm = bmesh.new(); bm.from_mesh(me)
    cut = bmesh.ops.bisect_plane(bm, geom=bm.verts[:] + bm.edges[:] + bm.faces[:], plane_co=(0, 0, zs), plane_no=(0, 0, 1), dist=1e-5)
    bmesh.ops.split_edges(bm, edges=[g for g in cut['geom_cut'] if isinstance(g, bmesh.types.BMEdge)])
    seen = set(); dead = []; kept = 0
    for f in bm.faces:
        if f in seen: continue
        comp = [f]; seen.add(f); st = [f]
        while st:
            g = st.pop()
            for e in g.edges:
                for h in e.link_faces:
                    if h not in seen: seen.add(h); comp.append(h); st.append(h)
        C = np.array([g.calc_center_median()[:] for g in comp])
        if C[:, 2].max() > zs + 0.002: continue                   # part of the body
        if in_wheel(C.mean(0)): kept += 1; continue               # hub, spokes, inner sidewall
        ext = C.max(0) - C.min(0)
        if ext[0] > 0.06 and ext[1] > 0.06 and C[:, 2].min() > zg - 0.03: kept += 1; continue   # tyre bottoms, diffuser
        dead += comp
    bmesh.ops.delete(bm, geom=dead, context='FACES'); bmesh.ops.delete(bm, geom=[v for v in bm.verts if not v.link_faces], context='VERTS')
    bm.to_mesh(me); bm.free(); me.update()
    nv = len(me.vertices); V = np.empty(nv * 3); me.vertices.foreach_get('co', V); V = V.reshape(nv, 3)
    x, y, z = V.T
    wing = (np.abs(x) > 0.22) & (np.abs(x) < 0.36) & (z > z.max() - 0.15) & (np.abs(y) > 0.5)
    flipped = bool(wing.any() and y[wing].mean() < 0)
    if flipped: V[:, 0] *= -1; V[:, 1] *= -1
    V[:, 0] -= (V[:, 0].max() + V[:, 0].min()) / 2; V[:, 1] -= (V[:, 1].max() + V[:, 1].min()) / 2
    V[:, 2] -= V[:, 2].min() + 0.30
    me.vertices.foreach_set('co', V.ravel()); me.update()
    return {'strip_faces': len(dead), 'kept_low': kept, 'flipped': flipped, 'bounds': [V.min(0).round(3).tolist(), V.max(0).round(3).tolist()]}
for o in list(bpy.data.objects):
    if o.name in ('TR_BRZ', 'TR_SRC', 'TR_NEW'): bpy.data.objects.remove(o)

# 1. lamp points: a copy with the generator's own UVs, bake positions, read its red texels
src_cut = cl['cut_roof_junk']
if globals().get('STRIPS'): cl['cut_roof_junk'] = lambda ob, **k: (0, 0)
_imgs = set(bpy.data.images)
src = cl['import_trellis'](GLB, name='TR_SRC', decimate=None)
if globals().get('STRIPS'): out['src_fix'] = fix_strips_and_orient(src)
me = src.data; me.materials.clear(); me.materials.append(bpy.data.materials['MC_PaintWR'])
P, N = cl['bake_maps'](src, size=2048, margin=0)
img = [i for i in bpy.data.images if i not in _imgs][0]; W, H = img.size
px = np.empty(W * H * 4, np.float32); img.pixels.foreach_get(px); px = px.reshape(H, W, 4)[..., :3]
idx = (np.arange(2048) * W // 2048); px = px[idx][:, idx]
r, g, b = px[..., 0], px[..., 1], px[..., 2]; red = (r > 0.22) & (r > 1.7 * g) & (r > 1.7 * b)
valid = np.abs(P).sum(-1) > 0.01
pts = P[red & valid & (P[..., 1] > 0.55)]
np.save(SP + r"\lamp_pts.npy", pts); out['lamp_pts'] = int(len(pts))
bpy.data.objects.remove(src)

# 2. the game mesh
if globals().get('STRIPS'):
    ob = cl['import_trellis'](GLB, name='TR_BRZ', decimate=None)
    out['fix'] = fix_strips_and_orient(ob)          # no roof cut: de-reflected photos give a clean roof, and the cut nicked the hood
    me = ob.data
    for o in bpy.context.view_layer.objects: o.select_set(False)
    ob.select_set(True); bpy.context.view_layer.objects.active = ob
    cl['smooth_body'](ob, iters=6, normal_iters=30, snap_dot=-2)
    hi_ = ob.copy(); hi_.data = me.copy(); bpy.context.scene.collection.objects.link(hi_)
    mod = ob.modifiers.new('dec', 'DECIMATE'); mod.ratio = 180000 / len(me.polygons); mod.use_collapse_triangulate = True
    bpy.ops.object.modifier_apply(modifier=mod.name)
    mod = ob.modifiers.new('nrm', 'DATA_TRANSFER'); mod.object = hi_; mod.use_loop_data = True; mod.data_types_loops = {'CUSTOM_NORMAL'}; mod.loop_mapping = 'POLYINTERP_NEAREST'
    bpy.ops.object.modifier_apply(modifier=mod.name); bpy.data.objects.remove(hi_)
    cl['cut_roof_junk'] = src_cut
else:
    ob = cl['import_trellis'](GLB, name='TR_BRZ', decimate=180000)
me = ob.data
for o in bpy.context.view_layer.objects: o.select_set(False)
ob.select_set(True); bpy.context.view_layer.objects.active = ob; ob.location = (0, 0, 0)
cl['smooth_body'](ob, iters=10, normal_iters=40, snap_dot=-2, only=((-0.30, -0.46, 0.12), (0.30, 0.22, 0.30)), skip=((-0.37, 0.60, -0.01), (0.37, 0.90, 0.25)))
bm = bmesh.new(); bm.from_mesh(me); bm.faces.ensure_lookup_table()
seen = set(); small = []
for f in bm.faces:
    if f.index in seen: continue
    st = [f]; seen.add(f.index); g = []
    while st:
        a = st.pop(); g.append(a)
        for e in a.edges:
            for b_ in e.link_faces:
                if b_.index not in seen: seen.add(b_.index); st.append(b_)
    if len(g) < 60: small += g
bmesh.ops.delete(bm, geom=small, context='FACES'); bmesh.ops.delete(bm, geom=[v for v in bm.verts if not v.link_faces], context='VERTS')
bm.to_mesh(me); bm.free(); me.update(); out['small_shells_faces'] = len(small)
for p in me.polygons: p.use_smooth = True
nv = len(me.vertices); V = np.empty(nv * 3); me.vertices.foreach_get('co', V); V = V.reshape(nv, 3)
out['bounds'] = [V.min(0).round(3).tolist(), V.max(0).round(3).tolist()]; out['faces'] = len(me.polygons)

# 3. UVs, position bake, paint by position
bpy.ops.object.mode_set(mode='EDIT'); bpy.ops.mesh.select_all(action='SELECT')
bpy.ops.uv.smart_project(angle_limit=math.radians(80), island_margin=0.001, correct_aspect=True, scale_to_bounds=False)
bpy.ops.object.mode_set(mode='OBJECT')
me.materials.clear(); me.materials.append(bpy.data.materials['MC_PaintWR'])
P, N = cl['bake_maps'](ob, size=4096, margin=8)
np.save(SP + r"\P_tr.npy", P); np.save(SP + r"\N_tr.npy", N)
col, rough, mask = cl['paint_pixels'](P, N, np.zeros_like(P), skip=cl['TRELLIS_SKIP'])

# 4. tail lamps: hull of the generator's lamp points, split by facing (rear-facing vs side-facing texels)
pts = pts[(pts[:, 1] > 0.69) & (pts[:, 2] > -0.03) & (np.abs(pts[:, 0]) > 0.19)]
def hull(Q):
    Q = np.unique(Q, axis=0); Q = Q[np.lexsort((Q[:, 1], Q[:, 0]))]
    def half(Q):
        h = []
        for q in Q:
            while len(h) >= 2 and np.cross(h[-1] - h[-2], q - h[-2]) <= 0: h.pop()
            h.append(q)
        return h
    return np.array(half(Q)[:-1] + half(Q[::-1])[:-1])
def inside(Hh, X, grow=0.006):
    ok = np.ones(len(X), bool)
    for i in range(len(Hh)):
        a = Hh[i]; b = Hh[(i + 1) % len(Hh)]; L = np.hypot(*(b - a)) + 1e-9
        ok &= ((b[0] - a[0]) * (X[:, 1] - a[1]) - (b[1] - a[1]) * (X[:, 0] - a[0])) / L >= -grow
    return ok
flat = P.reshape(-1, 3); fn = N.reshape(-1, 3); hit = np.zeros(len(flat), bool)
for s_ in (1, -1):
    Q = pts[np.sign(pts[:, 0]) == s_]
    if len(Q) < 20: continue
    Hr = hull(np.c_[np.abs(Q[Q[:, 1] > 0.72, 0]), Q[Q[:, 1] > 0.72, 2]]); Hs = hull(np.c_[Q[np.abs(Q[:, 0]) > 0.29, 1], Q[np.abs(Q[:, 0]) > 0.29, 2]])
    side = (np.sign(flat[:, 0]) == s_) & (flat[:, 1] > 0.66) & (flat[:, 2] > -0.05) & (np.abs(flat[:, 0]) > 0.17)
    idx = np.nonzero(side)[0]; X = flat[idx]; n_ = fn[idx]
    rearish = (n_[:, 1] > 0.3); sideish = (np.abs(n_[:, 0]) > 0.45); ok = np.zeros(len(idx), bool)
    ok[rearish] = inside(Hr, np.c_[np.abs(X[rearish, 0]), X[rearish, 2]]); ok[sideish] |= inside(Hs, np.c_[X[sideish, 1], X[sideish, 2]])
    hit[idx[ok]] = True
al = hit.reshape(P.shape[:2]).astype(np.float32)
from numpy.lib.stride_tricks import sliding_window_view
k = np.pad(al, 1, mode='edge'); al = sliding_window_view(k, (3, 3)).mean((-1, -2))
RED = cl['RED']; aa = al[..., None]
col = col * (1 - aa) + np.array(RED[0], np.float32) * aa; rough = rough * (1 - al) + RED[1] * al; mask[..., 0] *= (1 - al); mask[..., 1] *= (1 - al)
out['lamp_texels'] = int((al > 0.5).sum())
def put(name, rgb):
    im = bpy.data.images[name]; arr = np.ones((4096, 4096, 4), np.float32); arr[..., :3] = rgb; im.pixels.foreach_set(arr.ravel()); im.save()
lin = np.clip(col, 0, 1); srgb = np.where(lin <= 0.0031308, lin * 12.92, 1.055 * np.power(lin, 1 / 2.4) - 0.055)
put('T_CarCoupeT_BaseColor', srgb); put('T_CarCoupeT_Roughness', np.repeat(rough[..., None], 3, -1)); put('T_CarCoupeT_Mask', mask)

# 5. export + previews
me.materials.clear(); me.materials.append(bpy.data.materials['M_CarT'])
bpy.ops.export_scene.fbx(filepath=D + '\\export\\%s.fbx' % OUT, use_selection=True, axis_forward='-Z', axis_up='Y', global_scale=1.0, apply_unit_scale=True, mesh_smooth_type='FACE', use_mesh_modifiers=True, path_mode='STRIP', embed_textures=False, bake_anim=False)
sc = bpy.context.scene; cam = bpy.data.objects['PV_Cam']
eng = sc.render.engine; vt = sc.view_settings.view_transform; ex = sc.view_settings.exposure; res = (sc.render.resolution_x, sc.render.resolution_y)
others = [o for o in bpy.data.objects if o.type == 'MESH' and o is not ob and not o.hide_render]
for o in others: o.hide_render = True
ob.location = (0, 0, 0.3); ob.hide_render = False
sc.render.resolution_x = 1000; sc.render.resolution_y = 650
sc.render.engine = 'BLENDER_WORKBENCH'; sc.view_settings.view_transform = 'Standard'; sc.view_settings.exposure = 0.0
sh = sc.display.shading; sh.light = 'STUDIO'; sh.color_type = 'SINGLE'; sh.single_color = (0.8, 0.8, 0.8)
for k_, (l, t) in {'clay_roof': ((0.9, -0.6, 1.3), (0, 0.05, 0.5)), 'clay_rq': ((-1.6, 1.8, 0.9), (0.0, 0.2, 0.45)), 'clay_fq': ((1.6, -1.8, 0.9), (0.0, -0.2, 0.45))}.items():
    cam.location = l; cam.rotation_euler = (Vector(t) - Vector(l)).to_track_quat('-Z', 'Y').to_euler()
    sc.render.filepath = SP + '\\%s_%s.png' % (TAG, k_); bpy.ops.render.render(write_still=True)
sc.render.engine = 'CYCLES'; sc.cycles.samples = 40; sc.view_settings.view_transform = vt; sc.view_settings.exposure = ex
for k_, (l, t) in {'top': ((0.0, 0.0, 2.6), (0, 0, 0.25)), 'rq': ((-1.4, 1.6, 0.75), (0.0, 0.3, 0.25)), 'fq': ((1.6, -1.6, 0.75), (0.0, -0.3, 0.25))}.items():
    cam.location = l; cam.rotation_euler = (Vector(t) - Vector(l)).to_track_quat('-Z', 'Y').to_euler()
    sc.render.filepath = SP + '\\%s_%s.png' % (TAG, k_); bpy.ops.render.render(write_still=True)
ob.location = (3, 1.5, 0)
for o in others: o.hide_render = False
sc.render.engine = eng; sc.render.resolution_x, sc.render.resolution_y = res
bpy.ops.wm.save_mainfile()
out['s'] = round(time.time() - t0, 1)
result = out
