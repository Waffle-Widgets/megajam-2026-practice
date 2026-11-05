# Pickup-truck version of trellis_build.py + trellis_bake_texture.py (those stay BRZ-only).
# Run inside Blender via the MCP: set GLB, OUT, REPO (and optionally STAGE) in globals, then exec this file.
#   STAGE 'mesh'  : import, orient, scale to the real truck, weld, cut floaters, smooth, decimate, clean UVs
#   STAGE 'bake'  : bake the generator's own texture onto the clean UVs, derive roughness/mask, paint out
#                   badges (grille, tailgate), neutralise the paint, export FBX + PNG textures
#   STAGE 'all'   : both (default)
# Needs ai_car_clean.py next to it (smooth_body is shared with the BRZ path).
import bpy, bmesh, numpy as np, math, time, os
from mathutils import Vector
t0 = time.time()
REPO = globals().get('REPO', r"C:\Users\thecl\Projects\megajam-2026-practice")
D = REPO + r"\Art\Blender"; SP = D + r"\cache"; os.makedirs(SP, exist_ok=True)
GLB = globals().get('GLB', r"C:\AI\TRELLIS2\out\tacoma_front.glb")
OUT = globals().get('OUT', 'SM_CarTacoma')
DEST = globals().get('DEST', REPO + r"\MegaJamPractice\Content\Game\Imported\CarTacoma")
STAGE = globals().get('STAGE', 'all')
FACES = globals().get('FACES', 160000)
TEX = globals().get('TEX', 4096)
cl = {}; exec(open(D + r"\ai_car_clean.py").read(), cl)
out = {}

# ------------------------------------------------------------------ real size, in the game's car scale
# The car kit is in "game metres": the BRZ (4.24 m) is 1.717 long. Same ratio here, so the truck sits
# next to the coupe at the right size. 3rd-gen Tacoma double cab long bed: 5.69 x 1.91 (no mirrors) x 1.79 m.
K = 1.717 / 4.240
REAL = dict(length=5.69, width=1.91, height=1.79)
GROUND = -0.30                                   # tyre bottoms: origin 30 cm (game) above the road, like the coupe


def _verts(me):
    n = len(me.vertices); V = np.empty(n * 3); me.vertices.foreach_get('co', V); return V.reshape(n, 3)


def weld(ob, dist=1e-5):
    me = ob.data; bm = bmesh.new(); bm.from_mesh(me); n0 = len(bm.verts)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=dist)
    n1 = len(bm.verts); bm.to_mesh(me); bm.free(); me.update(); return n0 - n1


def orient_and_scale(ob):
    """Front at -Y, centred, tyre bottoms on GROUND, each axis scaled to the real truck (the generator makes
    trucks too wide and too tall, as it did the BRZ). Front/back: the bed rails make a flat top, the hood
    climbs towards the windscreen, so the flatter end goes to +Y."""
    me = ob.data; V = _verts(me)
    L = np.argmax(np.ptp(V[:, :2], 0))
    if L == 0: V = V[:, [1, 0, 2]] * np.array([-1, 1, 1])       # long axis -> Y
    x, y, z = V.T
    yc = (y.max() + y.min()) / 2
    def flat(sel): return np.std([np.percentile(z[sel & (np.abs(y - t) < 0.02 * np.ptp(y))], 99) for t in
                                  np.linspace(*np.percentile(y[sel], [10, 90]), 6)])
    span = np.ptp(y); front_half = y < yc - 0.18 * span; rear_half = y > yc + 0.18 * span
    flip = flat(front_half) < flat(rear_half)                      # flatter end = bed; must be at +Y
    if flip: V[:, 0] *= -1; V[:, 1] *= -1
    x, y, z = V.T
    s = REAL['length'] * K / np.ptp(y)
    V *= s; x, y, z = V.T
    mid = np.abs(y - y.mean()) < 0.35 * np.ptp(y)                 # cab band: mirrors stick out here
    body_half = np.percentile(np.abs(x[~mid]), 99.5)              # fender flares at the nose and bed
    sx = REAL['width'] * K / 2 / body_half
    top = np.percentile(z[mid], 99.95)                              # roof, not the antenna
    sz = REAL['height'] * K / (top - z.min())
    V[:, 0] *= sx; V[:, 2] *= sz
    V[:, 0] -= (V[:, 0].max() + V[:, 0].min()) / 2; V[:, 1] -= (V[:, 1].max() + V[:, 1].min()) / 2
    V[:, 2] -= V[:, 2].min() - GROUND
    me.vertices.foreach_set('co', V.ravel()); me.update()
    return {'flip': bool(flip), 'scale': round(float(s), 4), 'x_fix': round(float(sx), 3), 'z_fix': round(float(sz), 3),
            'bounds': [V.min(0).round(3).tolist(), V.max(0).round(3).tolist()]}


def components(me):
    nv = len(me.vertices); ed = np.empty(len(me.edges) * 2, np.int64); me.edges.foreach_get('vertices', ed); ed = ed.reshape(-1, 2)
    par = np.arange(nv)
    def find(a):
        while True:
            p = par[a]; pp = par[p]
            if np.all(p == pp): return p
            par[a] = pp; a = pp
    for _ in range(200):
        ra = find(ed[:, 0]); rb = find(ed[:, 1]); lo = np.minimum(ra, rb); hi = np.maximum(ra, rb); m = lo != hi
        if not m.any(): break
        np.minimum.at(par, hi[m], lo[m])
    return find(np.arange(nv))


def cut_floaters(ob, min_verts=200):
    """Drop every loose piece smaller than min_verts (the generator's crumbs inside and around the body).
    The mud flaps behind the front wheels are separate pieces of ~250 verts and stay."""
    me = ob.data; lab = components(me); u, c = np.unique(lab, return_counts=True)
    small = set(u[c < min_verts].tolist()); dead = np.isin(lab, list(small))
    bm = bmesh.new(); bm.from_mesh(me); bm.verts.ensure_lookup_table()
    bmesh.ops.delete(bm, geom=[bm.verts[i] for i in np.nonzero(dead)[0]], context='VERTS')
    bm.to_mesh(me); bm.free(); me.update()
    return {'pieces': int(len(u)), 'cut_pieces': len(small), 'cut_verts': int(dead.sum())}


def import_src(name):
    for o in list(bpy.data.objects):
        if o.name == name: bpy.data.objects.remove(o)
    before = set(bpy.data.objects); imgs = set(bpy.data.images)
    bpy.ops.import_scene.gltf(filepath=GLB)
    new = [o for o in bpy.data.objects if o not in before]
    ob = [o for o in new if o.type == 'MESH'][0]; ob.name = name
    for o in new:
        if o.type != 'MESH': bpy.data.objects.remove(o)
    for o in bpy.context.view_layer.objects: o.select_set(False)
    ob.select_set(True); bpy.context.view_layer.objects.active = ob
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    newimg = [i for i in bpy.data.images if i not in imgs]
    return ob, newimg


def select_only(ob):
    for o in bpy.context.view_layer.objects: o.select_set(False)
    ob.select_set(True); bpy.context.view_layer.objects.active = ob


def stage_mesh():
    for o in list(bpy.data.objects):
        if o.name in ('TR_TAC', 'TR_TAC_SRC'): bpy.data.objects.remove(o)
    src, imgs = import_src('TR_TAC_SRC')
    out['src_images'] = [(i.name, tuple(i.size)) for i in imgs]
    # the base-colour image is the one plugged into Base Color
    bc = None
    for n in src.data.materials[0].node_tree.nodes:
        if n.type == 'TEX_IMAGE' and any(l.to_socket.name == 'Base Color' for l in n.outputs['Color'].links): bc = n.image
    bc = bc or imgs[0]; bc.name = 'TAC_SRC_BaseColor'; out['src_base'] = bc.name
    out['weld_src'] = weld(src)
    out['orient'] = orient_and_scale(src)
    src.data.name = 'TAC_SRC'
    # game mesh: a copy without the crumbs, smoothed (along normals only), decimated with the smooth normals
    ob = src.copy(); ob.data = src.data.copy(); ob.name = 'TR_TAC'; ob.data.name = 'TAC_GAME'
    bpy.context.scene.collection.objects.link(ob)
    out['floaters'] = cut_floaters(ob)
    select_only(ob)
    out['smooth'] = cl['smooth_body'](ob, iters=6, normal_iters=30, snap_dot=-2)
    me = ob.data
    hi = ob.copy(); hi.data = me.copy(); bpy.context.scene.collection.objects.link(hi)
    mod = ob.modifiers.new('dec', 'DECIMATE'); mod.ratio = FACES / len(me.polygons); mod.use_collapse_triangulate = True
    bpy.ops.object.modifier_apply(modifier=mod.name)
    mod = ob.modifiers.new('nrm', 'DATA_TRANSFER'); mod.object = hi; mod.use_loop_data = True
    mod.data_types_loops = {'CUSTOM_NORMAL'}; mod.loop_mapping = 'POLYINTERP_NEAREST'
    bpy.ops.object.modifier_apply(modifier=mod.name); bpy.data.objects.remove(hi)
    for p in me.polygons: p.use_smooth = True
    # clean UVs: big islands (the generator's atlas has thousands of micro islands that bleed in mipmaps)
    while len(me.uv_layers) > 1: me.uv_layers.remove(me.uv_layers[-1])
    # Unwrapped as-is, the AI's noisy faces split into 15,000 islands (24% of the sheet used). Unwrap a heavily
    # smoothed copy of the shape instead, then put the real points back: the UVs stay, islands are big (47%).
    # (pack_islands afterwards made it worse: 32%.)
    nv = len(me.vertices); keep = _verts(me); Q = keep.copy()
    ed = np.empty(len(me.edges) * 2, np.int64); me.edges.foreach_get('vertices', ed); ed = ed.reshape(-1, 2)
    deg = np.zeros(nv); np.add.at(deg, ed[:, 0], 1); np.add.at(deg, ed[:, 1], 1); deg = np.maximum(deg, 1)
    for _ in range(40):
        s_ = np.zeros_like(Q); np.add.at(s_, ed[:, 0], Q[ed[:, 1]]); np.add.at(s_, ed[:, 1], Q[ed[:, 0]]); Q += 0.6 * (s_ / deg[:, None] - Q)
    me.vertices.foreach_set('co', Q.ravel()); me.update()
    bpy.ops.object.mode_set(mode='EDIT'); bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.uv.smart_project(angle_limit=math.radians(66), island_margin=0.001, correct_aspect=True, scale_to_bounds=False)
    bpy.ops.object.mode_set(mode='OBJECT')
    me.vertices.foreach_set('co', keep.ravel()); me.update()
    V = _verts(me); out['faces'] = len(me.polygons); out['bounds'] = [V.min(0).round(3).tolist(), V.max(0).round(3).tolist()]
    src.hide_viewport = True; src.hide_render = True
    bpy.ops.wm.save_as_mainfile(filepath=SP + r"\tacoma_work.blend")


if STAGE in ('mesh', 'all'): stage_mesh()
if STAGE in ('bake', 'all'):
    exec(open(D + r"\trellis_truck_bake.py").read())
out['s'] = round(time.time() - t0, 1)
result = out
