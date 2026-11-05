# Second half after trellis_build.py: bakes the generator texture onto the clean UVs. Set GLB, OUT, TAG (REAR=True paints an unseen rear by position).
# Second half for a de-reflected photo model: fill the window holes, bake the generator's own texture onto
# the clean UVs of TR_BRZ, derive roughness/mask from colour, keep our wheels, export. Needs trellis_build.py's
# TR_BRZ (clean UVs, P_tr/N_tr saved) and the same GLB.
import bpy, bmesh, numpy as np, math, time
REPO = globals().get('REPO', r"C:\Users\thecl\code\megajam-2026-practice")   # pass REPO=... on another PC
D = REPO + r"\Art\Blender"; SP = D + r"\cache"                                   # cache: baked maps, lamp points (gitignored)
import os; os.makedirs(SP, exist_ok=True)
from mathutils import Vector
t0 = time.time()
GLB = globals()['GLB']; OUT = globals()['OUT']; TAG = globals()['TAG']
_b = open(SP + r"\trellis_build.py").read()
exec(_b[_b.index('cl = {}'):_b.index('for o in list(bpy.data.objects)')])          # cl, out, HEIGHT, fix_strips_and_orient (stops before the object clean-up)
ob = bpy.data.objects['TR_BRZ']; me = ob.data; ob.location = (0, 0, 0)      # previews park it aside; the source is at the origin
for o in list(bpy.data.objects):
    if o.name == 'TR_SRC': bpy.data.objects.remove(o)

# 1. fill the side-window holes (photo had the windows down)
bm = bmesh.new(); bm.from_mesh(me); uvl = bm.loops.layers.uv.active
win = lambda v: abs(v.co.x) > 0.25 and -0.25 < v.co.y < 0.36 and 0.07 < v.co.z < 0.24
bnd = [e for e in bm.edges if e.is_boundary and win(e.verts[0]) and win(e.verts[1])]
new = bmesh.ops.holes_fill(bm, edges=bnd, sides=0)['faces']; ns = set(new)
new = bmesh.ops.triangulate(bm, faces=new)['faces']
for f in new:
    for l in f.loops:
        src = [ll for ll in l.vert.link_loops if ll.face not in ns]
        if src: l[uvl].uv = src[0][uvl].uv.copy()
out['window_fill'] = len(new)
bm.to_mesh(me); bm.free(); me.update()
for p in me.polygons: p.use_smooth = True
# the fill faces share border UVs only; give the whole mesh fresh UVs and re-bake positions
bpy.ops.object.mode_set(mode='EDIT'); bpy.ops.mesh.select_all(action='SELECT')
bpy.ops.uv.smart_project(angle_limit=math.radians(80), island_margin=0.001, correct_aspect=True, scale_to_bounds=False)
bpy.ops.object.mode_set(mode='OBJECT')
me.materials.clear(); me.materials.append(bpy.data.materials['MC_PaintWR'])
P, N = cl['bake_maps'](ob, size=4096, margin=8)
np.save(SP + r"\P_tr.npy", P); np.save(SP + r"\N_tr.npy", N)

# 2. source copy with the generator's UVs + texture, same transform
src_cut = cl['cut_roof_junk']; cl['cut_roof_junk'] = lambda o_, **k: (0, 0)
_imgs = set(bpy.data.images)
src = cl['import_trellis'](GLB, name='TR_SRC', decimate=None)
cl['cut_roof_junk'] = src_cut; fix_strips_and_orient(src)
img = [i for i in bpy.data.images if i not in _imgs][0]; out['src_image'] = (img.name, tuple(img.size))
msrc = bpy.data.materials.new('M_SrcBake'); msrc.use_nodes = True; nt = msrc.node_tree
for n in list(nt.nodes): nt.nodes.remove(n)
tex = nt.nodes.new('ShaderNodeTexImage'); tex.image = img
em = nt.nodes.new('ShaderNodeEmission'); outn = nt.nodes.new('ShaderNodeOutputMaterial')
nt.links.new(tex.outputs['Color'], em.inputs['Color']); nt.links.new(em.outputs['Emission'], outn.inputs['Surface'])
src.data.materials.clear(); src.data.materials.append(msrc)
# bake target
tgt = bpy.data.images.get('T_SrcBake') or bpy.data.images.new('T_SrcBake', 4096, 4096, float_buffer=True)
tgt.colorspace_settings.name = 'Non-Color'
mt = bpy.data.materials.new('M_TgtBake'); mt.use_nodes = True; nt2 = mt.node_tree
tn = nt2.nodes.new('ShaderNodeTexImage'); tn.image = tgt; nt2.nodes.active = tn
me.materials.clear(); me.materials.append(mt)
sc = bpy.context.scene; sc.render.engine = 'CYCLES'; sc.cycles.device = 'GPU'; sc.cycles.samples = 1
sc.render.bake.use_selected_to_active = True; sc.render.bake.cage_extrusion = 0.012; sc.render.bake.max_ray_distance = 0.03; sc.render.bake.margin = 8
for o in bpy.context.view_layer.objects: o.select_set(False)
src.select_set(True); ob.select_set(True); bpy.context.view_layer.objects.active = ob
src.hide_render = False; src.hide_viewport = False; ob.hide_render = False
bpy.ops.object.bake(type='EMIT')
S = 4096; px = np.empty(S * S * 4, np.float32); tgt.pixels.foreach_get(px); baked = px.reshape(S, S, 4)[..., :3].copy(); out['baked_mean'] = float(baked.mean())
bpy.data.objects.remove(src)

# 3. our wheels + derived materials
nv = len(me.vertices); V = np.empty(nv * 3); me.vertices.foreach_get('co', V); V = V.reshape(nv, 3)
low = V[V[:, 2] < V[:, 2].min() + 0.02]; ys = np.sort(low[:, 1]); gap = np.argmax(np.diff(ys))
cl['WHEEL_YS'] = (float(np.median(ys[:gap + 1])), float(np.median(ys[gap + 1:]))); cl['WHEEL_Z'] = float(V[:, 2].min() + cl['TYRE_R'])
out['wheels'] = [cl['WHEEL_YS'], cl['WHEEL_Z']]
col, rough, mask = cl['paint_pixels'](P, N, np.zeros_like(P), skip=cl['TRELLIS_SKIP'])
x, y, z = P[..., 0], P[..., 1], P[..., 2]
wheel = np.zeros(P.shape[:2], bool)
for yw in cl['WHEEL_YS']: wheel |= (np.hypot(y - yw, z - cl['WHEEL_Z']) < cl['TYRE_R'] + 0.002) & (np.abs(x) > 0.20)
b = np.clip(baked, 0, 1); lum = b.mean(-1); mx = b.max(-1); mn = b.min(-1); sat = (mx - mn) / (mx + 1e-6)
red = (b[..., 0] > 1.7 * b[..., 1]) & (b[..., 0] > 1.7 * b[..., 2]) & (b[..., 0] > 0.10) & (y > 0.6) & (z > -0.05) & (np.abs(x) > 0.17)   # tail lamps only
dark = (lum < 0.025) & (sat < 0.5)
glassbox = (np.abs(x) > 0.25) & (np.abs(x) < 0.37) & (y > -0.25) & (y < 0.36) & (z > 0.085) & (z < 0.24) & (np.abs(N[..., 0]) > 0.5)
PAINT = cl['PAINT']; GLASS = cl['GLASS']; RED = cl['RED']
bc = b.copy(); br = np.full(lum.shape, PAINT[1], np.float32); bm0 = np.full(lum.shape, PAINT[2], np.float32); bm1 = np.full(lum.shape, PAINT[3], np.float32)
br[dark] = GLASS[1]; bm0[dark] = 0; bm1[dark] = 0
br[red] = RED[1]; bm0[red] = 0; bm1[red] = 0; bc[red] = np.array(RED[0], np.float32)
bc[glassbox] = np.array(GLASS[0], np.float32); br[glassbox] = GLASS[1]; bm0[glassbox] = 0; bm1[glassbox] = 0
if globals().get('REAR'):
    # the photo did not show the rear: paint it by position (lid/bumper body colour, rear glass, tail lamps from
    # the lamp hull, diffuser, wing black with body-colour end plates)
    top = np.load(SP + r"\deck_top.npy"); ax = np.load(SP + r"\deck_axes.npy")
    ii = np.clip(np.round((x - ax[0]) / ax[2]).astype(int), 0, top.shape[1] - 1); jj = np.clip(np.round((y - ax[1]) / ax[2]).astype(int), 0, top.shape[0] - 1)
    deckz = top[jj, ii]
    rear = ((y > 0.50) | ((y > 0.30) & (z > 0.12))) & ~wheel          # the photo showed none of this: lid, bumper, rear glass, back of the roof
    bc[rear] = np.array(PAINT[0], np.float32); br[rear] = PAINT[1]; bm0[rear] = PAINT[2]; bm1[rear] = PAINT[3]
    rglass = rear & (N[..., 1] > 0.35) & (N[..., 2] > 0.2) & (z > 0.10) & (y > 0.30) & (y < 0.68) & (np.abs(x) < 0.30)
    bc[rglass] = np.array(GLASS[0], np.float32); br[rglass] = GLASS[1]; bm0[rglass] = 0; bm1[rglass] = 0
    PLASTIC = cl['PLASTIC']; TRIM = cl['TRIM']
    diff = rear & (y > 0.74) & (z < -0.13)
    bc[diff] = np.array(PLASTIC[0], np.float32); br[diff] = PLASTIC[1]; bm0[diff] = 0; bm1[diff] = 0
    wingt = rear & (y > 0.58) & ~np.isnan(deckz) & (z > deckz + 0.010) & (np.abs(x) < 0.31)
    bc[wingt] = np.array(TRIM[0], np.float32); br[wingt] = TRIM[1]; bm0[wingt] = 0; bm1[wingt] = 0
    pts = np.load(SP + r"\lamp_pts_r34.npy"); pts = pts[(pts[:, 1] > 0.69) & (pts[:, 2] > -0.03) & (np.abs(pts[:, 0]) > 0.19)]
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
            a = Hh[i]; b_ = Hh[(i + 1) % len(Hh)]; L = np.hypot(*(b_ - a)) + 1e-9
            ok &= ((b_[0] - a[0]) * (X[:, 1] - a[1]) - (b_[1] - a[1]) * (X[:, 0] - a[0])) / L >= -grow
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
    lamp = hit.reshape(P.shape[:2])
    bc[lamp] = np.array(RED[0], np.float32); br[lamp] = RED[1]; bm0[lamp] = 0; bm1[lamp] = 0
    out['rear_texels'] = {'rear': int(rear.sum()), 'glass': int(rglass.sum()), 'wing': int(wingt.sum()), 'lamp': int(lamp.sum())}
w = wheel[..., None]
col = np.where(w, col, bc); rough = np.where(wheel, rough, br); mask[..., 0] = np.where(wheel, mask[..., 0], bm0); mask[..., 1] = np.where(wheel, mask[..., 1], bm1)
def put(name, rgb):
    im = bpy.data.images[name]; arr = np.ones((S, S, 4), np.float32); arr[..., :3] = rgb; im.pixels.foreach_set(arr.ravel()); im.save()
lin = np.clip(col, 0, 1); srgb = np.where(lin <= 0.0031308, lin * 12.92, 1.055 * np.power(lin, 1 / 2.4) - 0.055)
put('T_CarCoupeT_BaseColor', srgb); put('T_CarCoupeT_Roughness', np.repeat(rough[..., None], 3, -1)); put('T_CarCoupeT_Mask', mask)

# 4. export + previews
me.materials.clear(); me.materials.append(bpy.data.materials['M_CarT'])
for o in bpy.context.view_layer.objects: o.select_set(False)
ob.select_set(True); bpy.context.view_layer.objects.active = ob
bpy.ops.export_scene.fbx(filepath=D + '\\export\\%s.fbx' % OUT, use_selection=True, axis_forward='-Z', axis_up='Y', global_scale=1.0, apply_unit_scale=True, mesh_smooth_type='FACE', use_mesh_modifiers=True, path_mode='STRIP', embed_textures=False, bake_anim=False)
cam = bpy.data.objects['PV_Cam']
vt = sc.view_settings.view_transform; ex = sc.view_settings.exposure; res = (sc.render.resolution_x, sc.render.resolution_y)
others = [o for o in bpy.data.objects if o.type == 'MESH' and o is not ob and not o.hide_render]
for o in others: o.hide_render = True
ob.location = (0, 0, 0.3); sc.render.resolution_x = 1000; sc.render.resolution_y = 650; sc.cycles.samples = 40
for k_, (l, t) in {'top': ((0.0, 0.0, 2.6), (0, 0, 0.25)), 'rq': ((-1.4, 1.6, 0.75), (0.0, 0.3, 0.25)), 'fq': ((1.6, -1.6, 0.75), (0.0, -0.3, 0.25)), 'side': ((2.4, 0.2, 0.5), (0, 0, 0.2))}.items():
    cam.location = l; cam.rotation_euler = (Vector(t) - Vector(l)).to_track_quat('-Z', 'Y').to_euler()
    sc.render.filepath = SP + '\\%s_%s.png' % (TAG, k_); bpy.ops.render.render(write_still=True)
ob.location = (3, 1.5, 0)
for o in others: o.hide_render = False
sc.render.resolution_x, sc.render.resolution_y = res
bpy.ops.wm.save_mainfile()
out['s'] = round(time.time() - t0, 1)
result = out
