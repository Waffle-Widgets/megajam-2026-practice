# Any vehicle (car, SUV, van, truck) from a TRELLIS GLB to a game-ready FBX + textures. General version of
# trellis_truck.py (which stays as the exact Tacoma recipe). Headless:
#   blender -b --factory-startup --python Art/Blender/trellis_vehicle.py -- "<json settings>"
# Settings (JSON keys; all but GLB/OUT/REAL have defaults):
#   GLB    path to the generator GLB            OUT   asset name, e.g. "SM_CarRav4"
#   REAL   [length, width, height] in real metres, without mirrors (look them up: measured, not eyeballed)
#   BACK   how to find the rear: "tall" (SUV/van/hatch: the rear is roof-high, the hood is low),
#          "flat" (pickup: the bed rails are a flat low top), "keep" (trust the GLB), "flip" (reverse "keep")
#   GLASS_Z [lo, hi]  window band as a fraction of the height above the ground (default [0.52, 0.95])
#   PAINT_SAT   keep this much of the paint's colour saturation (1 = as generated, 0 = grey)
#   PAINT_LUM   lift the paint's median brightness to this (sRGB 0-1); null keeps the generator's brightness
#   PAINT_CONTRAST  how much of the photo's baked light and shade to keep on the paint (1 = all)
#   METALLIC, ROUGH  the paint's metallic and roughness       FACES  triangle target (160000, plus 4 LODs in Unreal)
#   PAINT_BOXES list of {"min":[x,y,z], "max":[x,y,z], "rgb":[r,g,b]} in game metres (front -Y, ground -0.30):
#               texels inside get that flat colour (badges the photo fix missed)
#   STAGE  "mesh", "bake" or "all"
# Output: <DEST>/<OUT>.fbx, T_<name>_BaseColor/_Roughness/_Mask.png (DEST defaults to Art/Blender/export/Vehicles/<name>),
# and Art/Blender/cache/<OUT>_work.blend + <OUT>_sheet.png (four views, for checking before Unreal).
import bpy, bmesh, numpy as np, math, time, os, sys, json
from mathutils import Vector
t0 = time.time()
if '--' in sys.argv: globals().update(json.loads(sys.argv[sys.argv.index('--') + 1]))
REPO = globals().get('REPO', (os.environ.get('MEGAJAM_REPO') or os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(globals().get('__file__', os.path.join(os.getcwd(), 'Art', 'Blender', '_')))), '..', '..'))))
D = REPO + r"\Art\Blender"; SP = D + r"\cache"; os.makedirs(SP, exist_ok=True)
GLB = globals()['GLB']; OUT = globals()['OUT']; NAME = OUT[3:] if OUT.startswith('SM_') else OUT
# Outside Content/ on purpose: files written into Content/ auto-import into an open Unreal (extra material, Nanite on)
DEST = globals().get('DEST', REPO + r"\Art\Blender\export\Vehicles" + '\\' + NAME)
REAL = dict(zip(('length', 'width', 'height'), globals()['REAL']))
BACK = globals().get('BACK', 'tall'); STAGE = globals().get('STAGE', 'all')
FACES = globals().get('FACES', 160000); TEX = globals().get('TEX', 4096)
cl = {}; exec(open(D + r"\ai_car_clean.py").read(), cl)
out = {}

# The car kit is in "game metres": the BRZ (4.24 m) is 1.717 long. Every vehicle uses the same ratio, so they
# sit next to each other at the right size. Tyre bottoms 30 cm (game) below the origin, like the coupe.
K = 1.717 / 4.240
GROUND = -0.30


def _verts(me):
    n = len(me.vertices); V = np.empty(n * 3); me.vertices.foreach_get('co', V); return V.reshape(n, 3)


def weld(ob, dist=1e-5):
    """The glTF import splits vertices along every UV seam; weld before anything else."""
    me = ob.data; bm = bmesh.new(); bm.from_mesh(me); n0 = len(bm.verts)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=dist)
    n1 = len(bm.verts); bm.to_mesh(me); bm.free(); me.update(); return n0 - n1


def end_tops(V):
    """Height profile near each end: 95th-percentile height of the front and back fifths of the length."""
    x, y, z = V.T; span = np.ptp(y); lo, hi = y.min(), y.max()
    a = z[y < lo + 0.2 * span]; b = z[y > hi - 0.2 * span]
    return float(np.percentile(a, 95)), float(np.percentile(b, 95))


def flatness(V, sel):
    x, y, z = V.T
    return np.std([np.percentile(z[sel & (np.abs(y - t) < 0.02 * np.ptp(y))], 99) for t in
                   np.linspace(*np.percentile(y[sel], [10, 90]), 6)])


def orient_and_scale(ob):
    """Front at -Y, centred, tyre bottoms on GROUND, each axis scaled to the real vehicle (TRELLIS makes cars
    about 15% too wide and 10% too tall)."""
    me = ob.data; V = _verts(me)
    if np.argmax(np.ptp(V[:, :2], 0)) == 0: V = V[:, [1, 0, 2]] * np.array([-1, 1, 1])     # long axis -> Y
    x, y, z = V.T; yc = (y.max() + y.min()) / 2; span = np.ptp(y)
    if BACK == 'tall':
        f, b = end_tops(V); flip = f > b                     # the taller end is the back
        out['end_tops'] = [round(f, 3), round(b, 3)]
    elif BACK == 'flat':
        flip = flatness(V, y < yc - 0.18 * span) < flatness(V, y > yc + 0.18 * span)
    else:
        flip = BACK == 'flip'
    if flip: V[:, 0] *= -1; V[:, 1] *= -1
    x, y, z = V.T
    V *= REAL['length'] * K / np.ptp(y); x, y, z = V.T
    mid = np.abs(y - y.mean()) < 0.35 * np.ptp(y)            # the cabin band: mirrors stick out here
    sx = REAL['width'] * K / 2 / np.percentile(np.abs(x[~mid]), 99.5)
    sz = REAL['height'] * K / (np.percentile(z[mid], 99.95) - z.min())
    V[:, 0] *= sx; V[:, 2] *= sz
    V[:, 0] -= (V[:, 0].max() + V[:, 0].min()) / 2; V[:, 1] -= (V[:, 1].max() + V[:, 1].min()) / 2
    V[:, 2] -= V[:, 2].min() - GROUND
    me.vertices.foreach_set('co', V.ravel()); me.update()
    return {'flip': bool(flip), 'x_fix': round(float(sx), 3), 'z_fix': round(float(sz), 3),
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
    """Drop every loose piece smaller than min_verts (the generator's crumbs inside and around the body)."""
    me = ob.data; lab = components(me); u, c = np.unique(lab, return_counts=True)
    small = set(u[c < min_verts].tolist()); dead = np.isin(lab, list(small))
    bm = bmesh.new(); bm.from_mesh(me); bm.verts.ensure_lookup_table()
    bmesh.ops.delete(bm, geom=[bm.verts[i] for i in np.nonzero(dead)[0]], context='VERTS')
    bm.to_mesh(me); bm.free(); me.update()
    return {'pieces': int(len(u)), 'cut_pieces': len(small), 'cut_verts': int(dead.sum())}


def select_only(ob):
    for o in bpy.context.view_layer.objects: o.select_set(False)
    ob.select_set(True); bpy.context.view_layer.objects.active = ob


def stage_mesh():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    imgs0 = set(bpy.data.images)
    bpy.ops.import_scene.gltf(filepath=GLB)
    src = [o for o in bpy.data.objects if o.type == 'MESH'][0]; src.name = 'VEH_SRC'
    for o in list(bpy.data.objects):
        if o is not src: bpy.data.objects.remove(o)
    select_only(src); bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    bc = None
    for n in src.data.materials[0].node_tree.nodes:
        if n.type == 'TEX_IMAGE' and any(l.to_socket.name == 'Base Color' for l in n.outputs['Color'].links): bc = n.image
    bc = bc or [i for i in bpy.data.images if i not in imgs0][0]; bc.name = 'VEH_SRC_BaseColor'
    out['weld_src'] = weld(src)
    out['orient'] = orient_and_scale(src)
    # game mesh: a copy without the crumbs, smoothed along normals only, decimated with the smooth normals kept
    ob = src.copy(); ob.data = src.data.copy(); ob.name = 'VEH'
    bpy.context.scene.collection.objects.link(ob)
    out['floaters'] = cut_floaters(ob)
    select_only(ob)
    out['smooth'] = cl['smooth_body'](ob, iters=6, normal_iters=30, snap_dot=-2)
    me = ob.data
    hi = ob.copy(); hi.data = me.copy(); bpy.context.scene.collection.objects.link(hi)
    mod = ob.modifiers.new('dec', 'DECIMATE'); mod.ratio = min(1.0, FACES / len(me.polygons)); mod.use_collapse_triangulate = True
    bpy.ops.object.modifier_apply(modifier=mod.name)
    mod = ob.modifiers.new('nrm', 'DATA_TRANSFER'); mod.object = hi; mod.use_loop_data = True
    mod.data_types_loops = {'CUSTOM_NORMAL'}; mod.loop_mapping = 'POLYINTERP_NEAREST'
    bpy.ops.object.modifier_apply(modifier=mod.name); bpy.data.objects.remove(hi)
    for p in me.polygons: p.use_smooth = True
    # clean UVs: unwrap a heavily smoothed stand-in (big islands), then put the real points back
    while len(me.uv_layers) > 1: me.uv_layers.remove(me.uv_layers[-1])
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
    bpy.ops.wm.save_as_mainfile(filepath=SP + '\\%s_work.blend' % OUT)


def render_sheet(ob):
    """Four views of the finished vehicle (front-3/4, rear-3/4, side, low wheel view) for a check before Unreal."""
    sc = bpy.context.scene; eng = [e.identifier for e in bpy.types.RenderSettings.bl_rna.properties['engine'].enum_items]
    sc.render.engine = 'BLENDER_EEVEE_NEXT' if 'BLENDER_EEVEE_NEXT' in eng else 'BLENDER_EEVEE'
    sc.render.resolution_x = 900; sc.render.resolution_y = 560
    w = bpy.data.worlds.get('VW') or bpy.data.worlds.new('VW'); sc.world = w; w.use_nodes = True
    w.node_tree.nodes['Background'].inputs[0].default_value = (0.75, 0.78, 0.82, 1); w.node_tree.nodes['Background'].inputs[1].default_value = 0.9
    sun = bpy.data.objects.new('VSun', bpy.data.lights.new('VSun', 'SUN')); sun.data.energy = 3.5; sun.rotation_euler = (0.9, 0.2, 0.7)
    sc.collection.objects.link(sun)
    cam = bpy.data.objects.new('VCam', bpy.data.cameras.new('VCam')); sc.collection.objects.link(cam); sc.camera = cam
    cam.data.lens = 50
    files = []
    for i, (az, el, dist) in enumerate([(-35, 18, 5.5), (145, 18, 5.5), (90, 3, 6.0), (-60, 2, 3.2)]):
        a, e = math.radians(az), math.radians(el)
        tgt = Vector((0, 0, -0.1)) if i < 3 else Vector((0, -0.55, -0.2))
        cam.location = tgt + Vector((math.sin(a) * math.cos(e), -math.cos(a) * math.cos(e), math.sin(e))) * dist * K * 2.4
        cam.rotation_euler = (tgt - cam.location).to_track_quat('-Z', 'Y').to_euler()
        f = SP + '\\%s_view%d.png' % (OUT, i); sc.render.filepath = f; bpy.ops.render.render(write_still=True); files.append(f)
    ims = []
    for f in files:
        im = bpy.data.images.load(f); a = np.empty(im.size[0] * im.size[1] * 4, np.float32); im.pixels.foreach_get(a)
        ims.append(a.reshape(im.size[1], im.size[0], 4))
    h, w_ = ims[0].shape[:2]; S_ = np.ones((2 * h, 2 * w_, 4), np.float32)
    for k, a in enumerate(ims):
        r, c = divmod(k, 2); S_[(1 - r) * h:(2 - r) * h, c * w_:(c + 1) * w_] = a
    im = bpy.data.images.new('VSheet', 2 * w_, 2 * h); im.pixels.foreach_set(S_.ravel())
    im.filepath_raw = SP + '\\%s_sheet.png' % OUT; im.file_format = 'PNG'; im.save()
    for o in (sun, cam): bpy.data.objects.remove(o)
    return im.filepath_raw


if STAGE in ('mesh', 'all'): stage_mesh()
if STAGE in ('bake', 'all'):
    if STAGE == 'bake': bpy.ops.wm.open_mainfile(filepath=SP + '\\%s_work.blend' % OUT)
    exec(open(D + r"\trellis_vehicle_bake.py").read())
    out['sheet'] = render_sheet(bpy.data.objects['VEH'])
out['s'] = round(time.time() - t0, 1)
print('VEHICLE_RESULT', json.dumps(out))
result = out
