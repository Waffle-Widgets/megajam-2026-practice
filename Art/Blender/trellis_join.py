# Two models, one car: GLB_B (rear photo) is the body, its nose is shrink-wrapped onto GLB_A (front photo). Set GLB_A, GLB_B, OUT, TAG, Y_FULL=-0.50, Y_NONE=-0.35.
# One car from two generator models without a seam: the rear-photo model B is the whole body; its invented front end
# is shrink-wrapped onto the front-photo model A. Textures bake from A on the front, B on the rear. Runs in Blender.
import bpy, bmesh, numpy as np, math, time
import os
REPO = globals().get('REPO', (os.environ.get('MEGAJAM_REPO') or os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(globals().get('__file__', os.path.join(os.getcwd(), 'Art', 'Blender', '_')))), '..', '..'))))   # repo = two folders up from this script; pass REPO=... or set MEGAJAM_REPO to override
D = REPO + r"\Art\Blender"; SP = D + r"\cache"                                   # cache: baked maps, lamp points (gitignored)
import os; os.makedirs(SP, exist_ok=True)
from mathutils import Vector
t0 = time.time()
GLB_A = globals()['GLB_A']; GLB_B = globals()['GLB_B']; OUT = globals()['OUT']; TAG = globals()['TAG']
Y_FULL, Y_NONE = globals().get('Y_FULL', -0.30), globals().get('Y_NONE', -0.10)     # wrap weight 1 ahead of Y_FULL, 0 behind Y_NONE
Y_SPLIT = (Y_FULL + Y_NONE) / 2                                                       # bake sources meet here
_b = open(D + r"\trellis_build.py").read()
exec(_b[_b.index('cl = {}'):_b.index('for o in list(bpy.data.objects)')])
for o in list(bpy.data.objects):
    if o.name in ('SRC_A', 'SRC_B', 'TR_BRZ', 'TR_SRC'): bpy.data.objects.remove(o)
src_cut = cl['cut_roof_junk']; cl['cut_roof_junk'] = lambda o_, **k: (0, 0)
def load(glb, name):
    imgs = set(bpy.data.images)
    o = cl['import_trellis'](glb, name=name, decimate=None); fix_strips_and_orient(o)
    img = [i for i in bpy.data.images if i not in imgs][0]
    m = bpy.data.materials.new('M_Src_' + name); m.use_nodes = True; nt = m.node_tree
    for n in list(nt.nodes): nt.nodes.remove(n)
    tex = nt.nodes.new('ShaderNodeTexImage'); tex.image = img; em = nt.nodes.new('ShaderNodeEmission'); on = nt.nodes.new('ShaderNodeOutputMaterial')
    nt.links.new(tex.outputs['Color'], em.inputs['Color']); nt.links.new(em.outputs['Emission'], on.inputs['Surface'])
    o.data.materials.clear(); o.data.materials.append(m); o.location = (0, 0, 0)
    return o, img
srcA, imgA = load(GLB_A, 'SRC_A'); srcB, imgB = load(GLB_B, 'SRC_B'); cl['cut_roof_junk'] = src_cut
def verts(o):
    n = len(o.data.vertices); V = np.empty(n * 3); o.data.vertices.foreach_get('co', V); return V.reshape(n, 3)
def section(V, y0, w=0.02):
    m = np.abs(V[:, 1] - y0) < w; return float(np.abs(V[m, 0]).max()), float(V[m, 2].max())
VA = verts(srcA); VB = verts(srcB); ax, az = section(VA, Y_NONE); bx, bz = section(VB, Y_NONE)
sx = ax / bx; sz = (az + 0.3) / (bz + 0.3)
VB[:, 0] *= sx; VB[:, 2] = -0.3 + (VB[:, 2] + 0.3) * sz; srcB.data.vertices.foreach_set('co', VB.ravel()); srcB.data.update()
out['align'] = {'sx': round(sx, 3), 'sz': round(sz, 3)}
def fill_atlas_gaps(img, passes=10):
    W, H = img.size; px = np.empty(W * H * 4, np.float32); img.pixels.foreach_get(px); a = px.reshape(H, W, 4)
    rgb = a[..., :3]; good = rgb.max(-1) > 0.02
    for _ in range(passes):
        if good.all(): break
        for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            sh = np.roll(rgb, (dy, dx), (0, 1)); shg = np.roll(good, (dy, dx), (0, 1))
            fill = ~good & shg; rgb[fill] = sh[fill]; good |= fill
    a[..., :3] = rgb; img.pixels.foreach_set(a.ravel()); img.update()
fill_atlas_gaps(imgA); fill_atlas_gaps(imgB)
def strip_inner_shell(o):
    """The generator makes a hollow shell about 2 mm thick. After smoothing and decimation the inner wall pokes
    through the paint as dark flecks, so drop it here, at full resolution, where the two walls are still apart.
    Inner wall = a face with another face just behind it that also looks at something inside the car."""
    from mathutils.bvhtree import BVHTree
    bmh = bmesh.new(); bmh.from_mesh(o.data); bvh = BVHTree.FromBMesh(bmh)
    V = np.array([v.co[:] for v in bmh.verts]); low = V[V[:, 2] < V[:, 2].min() + 0.02]
    ys = np.sort(low[:, 1]); g = np.argmax(np.diff(ys)); wy = (float(np.median(ys[:g + 1])), float(np.median(ys[g + 1:]))); wz = float(V[:, 2].min() + cl['TYRE_R'])
    dead = []
    for f in bmh.faces:
        c = f.calc_center_median(); n = f.normal
        if n.length < 0.5: continue
        if min(math.hypot(c.y - wy[0], c.z - wz), math.hypot(c.y - wy[1], c.z - wz)) < cl['TYRE_R'] + 0.06: continue   # wheels and arches stay
        if bvh.ray_cast(c - n * 0.0005, -n, 0.004)[0] is None: continue
        if bvh.ray_cast(c + n * 0.0005, n, 1.0)[0] is not None: dead.append(f)
    bmesh.ops.delete(bmh, geom=dead, context='FACES'); bmesh.ops.delete(bmh, geom=[v for v in bmh.verts if not v.link_faces], context='VERTS')
    n0 = len(o.data.polygons); bmh.to_mesh(o.data); bmh.free(); o.data.update()
    return (n0, len(dead))
out['inner_shell_A'] = strip_inner_shell(srcA)        # the wrap target must be the outer skin only

# the body: B welded, with its front end wrapped onto A
me = srcB.data.copy(); me.name = 'TR_BRZ'
bm = bmesh.new(); bm.from_mesh(me); bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-5); bm.to_mesh(me); bm.free(); me.update()
ob = bpy.data.objects.new('TR_BRZ', me); bpy.context.scene.collection.objects.link(ob)
for o in bpy.context.view_layer.objects: o.select_set(False)
ob.select_set(True); bpy.context.view_layer.objects.active = ob
V = verts(ob); w = np.clip((Y_NONE - V[:, 1]) / (Y_NONE - Y_FULL), 0, 1)
# the front wheels keep B's own hub and spokes: wrapped onto A's (different) wheel they crumple into a ball
lowB = V[V[:, 2] < V[:, 2].min() + 0.02]; ysB = np.sort(lowB[:, 1]); wyB = float(np.median(ysB[:np.argmax(np.diff(ysB)) + 1]))
w[(np.hypot(V[:, 1] - wyB, V[:, 2] - (V[:, 2].min() + cl['TYRE_R'])) < cl['TYRE_R'] + 0.03) & (np.abs(V[:, 0]) > 0.18)] = 0
vg = ob.vertex_groups.new(name='front')
for i in np.nonzero(w > 0)[0]: vg.add([int(i)], float(w[i]), 'REPLACE')
mod = ob.modifiers.new('wrap', 'SHRINKWRAP'); mod.target = srcA; mod.wrap_method = 'NEAREST_SURFACEPOINT'
mod.vertex_group = 'front'; mod.wrap_mode = 'ON_SURFACE'
bpy.ops.object.modifier_apply(modifier=mod.name)
V2 = verts(ob); out['wrapped_mm'] = {'mean': round(float(np.linalg.norm(V2 - V, axis=1)[w > 0.5].mean()) * 1000, 1), 'max': round(float(np.linalg.norm(V2 - V, axis=1).max()) * 1000, 1)}

def wheel_axle(V, y0, wz, sgn):
    """Axle direction of one wheel: the thinnest axis of its tyre/rim points (inside the tyre circle, one side)."""
    r = np.hypot(V[:, 1] - y0, V[:, 2] - wz); m = (r < cl['TYRE_R'] - 0.01) & (r > 0.06) & (sgn * V[:, 0] > 0.18) & (sgn * V[:, 0] < 0.40)
    P = V[m]; c = P.mean(0); _, E = np.linalg.eigh(np.cov((P - c).T)); ax = E[:, 0]
    if ax[0] < 0: ax = -ax
    return math.atan2(ax[1], ax[0]), float(c[0]), int(m.sum())
def straighten_front_wheels(ob, min_deg=5.0):
    """The yellow photo was shot with the front wheels turned (38 deg here), and the generator copied that. The wheels
    are part of the body mesh, so the game can't steer them: turn each front wheel back about the vertical axis
    through its centre. The wheel is picked out in its own turned frame (a turned tyre pokes out of the straight
    cylinder) with a 2.5 cm soft edge so the arch skin around it isn't torn."""
    V = verts(ob); wz = float(V[:, 2].min()) + cl['TYRE_R']
    low = V[V[:, 2] < V[:, 2].min() + 0.02]; ys = np.sort(low[:, 1]); y0 = float(np.median(ys[:np.argmax(np.diff(ys)) + 1]))
    rep = {}
    for sgn in (1, -1):
        th, xc, n = wheel_axle(V, y0, wz, sgn); k = 'R' if sgn > 0 else 'L'
        rep[k] = {'steer_deg': round(math.degrees(th), 1), 'n': n}
        if abs(math.degrees(th)) < min_deg: continue
        c = np.array([xc, y0, wz]); cs, sn = math.cos(-th), math.sin(-th)
        D = V - c; Vr = D.copy(); Vr[:, 0] = cs * D[:, 0] - sn * D[:, 1]; Vr[:, 1] = sn * D[:, 0] + cs * D[:, 1]   # un-steered frame
        r = np.hypot(Vr[:, 1], Vr[:, 2]); inx = (np.abs(Vr[:, 0]) < 0.085) & (sgn * V[:, 0] > 0.17)
        wt = np.clip((cl['TYRE_R'] + 0.015 - r) / 0.025, 0, 1) * inx
        V = V + (Vr - D) * wt[:, None]; rep[k]['moved'] = int((wt > 0).sum())
    ob.data.vertices.foreach_set('co', V.ravel()); ob.data.update()
    V = verts(ob); rep['after_deg'] = [round(math.degrees(wheel_axle(V, y0, wz, s)[0]), 1) for s in (1, -1)]
    return rep
out['steer'] = straighten_front_wheels(ob)
for p in me.polygons: p.use_smooth = True
cl['smooth_body'](ob, iters=6, normal_iters=30, snap_dot=-2)
cl['smooth_body'](ob, iters=10, normal_iters=30, snap_dot=-2, only=((-0.5, -0.9, -0.3), (0.5, Y_FULL + 0.02, 0.35)))   # the wrapped nose, a little more

# nose transplant
def nose_transplant(ob, srcA, y_cut=-0.65, lap=0.02, dip=0.002):
    """The wrap puts B's invented nose onto A's surface, but a nearest-point wrap cannot carry recesses: the grille
    opening, fog-lamp pockets and lamp housings come out as a crumpled lump. So ahead of y_cut (just in front of the
    front arches, where both skins agree to a millimetre) the body's faces are swapped for A's own. It is an overlap
    joint, not a butt joint: A's edge is torn into dozens of pieces, so bridging the two cut loops pairs them wrongly
    and leaves a row of holes. Instead A keeps a flange `lap` past the cut, and the body's leading band is dipped
    `dip` toward the car's centre line (a smooth ramp over lap + 1 cm) so it tucks under that flange. The dip
    direction is geometric, not the vertex normal, because the AI shell's normals are not consistently outward.
    A's flange edge (y_cut + lap) must stay ahead of the front arch hole (its front edge is at about -0.617, and
    trellis_wheels.py cuts the wheels out there): at -0.62 A's ragged edge hung over the arch and showed in the game."""
    def cut(bm, y0, keep_front):
        bmesh.ops.bisect_plane(bm, geom=bm.verts[:] + bm.edges[:] + bm.faces[:], dist=1e-5, plane_co=(0, y0, 0), plane_no=(0, 1, 0), clear_inner=not keep_front, clear_outer=keep_front)
        bmesh.ops.delete(bm, geom=[v for v in bm.verts if not v.link_faces], context='VERTS')
    bm = bmesh.new(); bm.from_mesh(ob.data); cut(bm, y_cut, keep_front=False); n_body = len(bm.faces)
    zc = -0.08; dipped = 0
    for v in bm.verts:
        t = (v.co.y - y_cut) / (lap + 0.01)
        if 0 <= t < 1:
            d = Vector((-v.co.x, 0, zc - v.co.z)); d.normalize(); v.co += d * dip * (1 - t); dipped += 1
    ba = bmesh.new(); ba.from_mesh(srcA.data); cut(ba, y_cut + lap, keep_front=True); n_nose = len(ba.faces)
    tmp = bpy.data.meshes.new('_nose'); ba.to_mesh(tmp); ba.free(); bm.from_mesh(tmp); bpy.data.meshes.remove(tmp)
    for f in bm.faces: f.smooth = True
    bm.to_mesh(ob.data); bm.free(); ob.data.update()
    return {'body_faces': n_body, 'nose_faces': n_nose, 'dipped': dipped}
out['nose'] = nose_transplant(ob, srcA)
# end nose transplant
mod = ob.modifiers.new('dec', 'DECIMATE'); mod.ratio = 180000 / len(me.polygons); mod.use_collapse_triangulate = True
bpy.ops.object.modifier_apply(modifier=mod.name)
nv = len(me.vertices); vn = np.empty(nv * 3); me.vertices.foreach_get('normal', vn); vn = vn.reshape(nv, 3)
ne = len(me.edges); ed = np.empty(ne * 2, np.int64); me.edges.foreach_get('vertices', ed); ed = ed.reshape(ne, 2)
S_ = vn.copy()
for _ in range(4):
    acc = S_.copy(); np.add.at(acc, ed[:, 0], S_[ed[:, 1]]); np.add.at(acc, ed[:, 1], S_[ed[:, 0]])
    S_ = acc / np.maximum(np.linalg.norm(acc, axis=1, keepdims=True), 1e-9)
nl = len(me.loops); lv = np.empty(nl, np.int64); me.loops.foreach_get('vertex_index', lv)
nf = len(me.polygons); fn = np.empty(nf * 3); me.polygons.foreach_get('normal', fn); fn = fn.reshape(nf, 3)
ls = np.empty(nf, np.int64); me.polygons.foreach_get('loop_total', ls); fidx = np.repeat(np.arange(nf), ls)
cn = S_[lv]; bad = (cn * fn[fidx]).sum(1) < 0.2; cn[bad] = fn[fidx][bad]
me.normals_split_custom_set([tuple(v) for v in cn])
out['faces'] = nf

# each source only covers its own end for the bake
def keep_side(o, front):
    bmh = bmesh.new(); bmh.from_mesh(o.data)
    dead = [f for f in bmh.faces if (f.calc_center_median().y > Y_SPLIT) == front]
    bmesh.ops.delete(bmh, geom=dead, context='FACES'); bmesh.ops.delete(bmh, geom=[v for v in bmh.verts if not v.link_faces], context='VERTS')
    bmh.to_mesh(o.data); bmh.free(); o.data.update()
keep_side(srcA, True); keep_side(srcB, False)

bpy.ops.object.mode_set(mode='EDIT'); bpy.ops.mesh.select_all(action='SELECT')
bpy.ops.uv.smart_project(angle_limit=math.radians(80), island_margin=0.001, correct_aspect=True, scale_to_bounds=False)
bpy.ops.object.mode_set(mode='OBJECT')
me.materials.clear(); me.materials.append(bpy.data.materials['MC_PaintWR'])
P, N = cl['bake_maps'](ob, size=4096, margin=8)
np.save(SP + r"\P_tr.npy", P); np.save(SP + r"\N_tr.npy", N)
tgt = bpy.data.images.get('T_SrcBake') or bpy.data.images.new('T_SrcBake', 4096, 4096, float_buffer=True)
tgt.colorspace_settings.name = 'Non-Color'
mt = bpy.data.materials.new('M_TgtBake'); mt.use_nodes = True; tn = mt.node_tree.nodes.new('ShaderNodeTexImage'); tn.image = tgt; mt.node_tree.nodes.active = tn
me.materials.clear(); me.materials.append(mt)
sc = bpy.context.scene; sc.render.engine = 'CYCLES'; sc.cycles.device = globals().get('DEVICE', 'GPU'); sc.cycles.samples = 1
b = sc.render.bake; b.use_selected_to_active = True; b.cage_extrusion = 0.012; b.max_ray_distance = 0.03; b.margin = 8
for o in bpy.context.view_layer.objects: o.select_set(False)
srcA.select_set(True); srcB.select_set(True); ob.select_set(True); bpy.context.view_layer.objects.active = ob
for o in (srcA, srcB, ob): o.hide_render = False; o.hide_viewport = False; o.hide_set(False)
ob.location = (0, 0, 0)
bpy.ops.object.bake(type='EMIT', use_selected_to_active=True, cage_extrusion=0.012, max_ray_distance=0.03)
S = 4096; px = np.empty(S * S * 4, np.float32); tgt.pixels.foreach_get(px); baked = px.reshape(S, S, 4)[..., :3].copy(); out['baked_mean'] = round(float(baked.mean()), 4)
for o in (srcA, srcB): o.hide_render = True; o.hide_viewport = True

# materials
V = verts(ob); low = V[V[:, 2] < V[:, 2].min() + 0.02]; ys = np.sort(low[:, 1]); gap = np.argmax(np.diff(ys))
cl['WHEEL_YS'] = (float(np.median(ys[:gap + 1])), float(np.median(ys[gap + 1:]))); cl['WHEEL_Z'] = float(V[:, 2].min() + cl['TYRE_R'])
out['wheels'] = [cl['WHEEL_YS'], cl['WHEEL_Z']]
# only the wheel painting is used from paint_pixels (the body comes from the bake), so skip every body part and
# circle: the straightened front tyre's face sits where the headlight projector rule looks and got a chrome disc
col, rough, mask = cl['paint_pixels'](P, N, np.zeros_like(P), skip=tuple(p[0] for p in cl['PARTS']) + tuple(c[0] for c in cl['CIRCLES']))
x, y, z = P[..., 0], P[..., 1], P[..., 2]
wheel = np.zeros(P.shape[:2], bool)
for yw in cl['WHEEL_YS']: wheel |= (np.hypot(y - yw, z - cl['WHEEL_Z']) < cl['TYRE_R'] + 0.002) & (np.abs(x) > 0.20)
bb = np.clip(baked, 0, 1); lum = bb.mean(-1); mx = bb.max(-1); mn = bb.min(-1); sat = (mx - mn) / (mx + 1e-6)
PAINT = cl['PAINT']; GLASS = cl['GLASS']; RED = cl['RED']
hue = np.where(mx == bb[..., 2], (4 + (bb[..., 0] - bb[..., 1]) / (mx - mn + 1e-6)) / 6, np.where(mx == bb[..., 1], (2 + (bb[..., 2] - bb[..., 0]) / (mx - mn + 1e-6)) / 6, ((bb[..., 1] - bb[..., 2]) / (mx - mn + 1e-6)) / 6 % 1))
paintpx = (sat > 0.35) & (mx > 0.05) & (((hue > 0.52) & (hue < 0.75)) | ((hue > 0.09) & (hue < 0.22)))
red = (bb[..., 0] > 1.7 * bb[..., 1]) & (bb[..., 0] > 1.7 * bb[..., 2]) & (bb[..., 0] > 0.10) & (y > 0.6) & (z > -0.05) & (np.abs(x) > 0.17)
dark = (lum < 0.025) & (sat < 0.5)
side = (np.abs(x) > 0.25) & (np.abs(x) < 0.37) & (z < 0.24) & (np.abs(N[..., 0]) > 0.5)
glassbox = side & (((y > -0.25) & (y < 0.36) & (z > 0.085)) | ((y >= 0.36) & (y < 0.40) & (z > 0.11)))   # door glass + quarter window
rglass = (N[..., 2] > 0.4) & (z > 0.10) & (y > 0.35) & (y < 0.625) & (np.abs(x) < 0.205 + 0.1 * (y - 0.35))   # rear window: laid back ~17 deg, so test height not tilt
plate = (N[..., 1] > 0.6) & (y > 0.72) & (np.abs(x) < 0.13) & (z > -0.06) & (z < 0.09)                           # plate recess: body colour, no plate
wglass = (N[..., 1] < -0.3) & (N[..., 2] > 0.3) & (z > 0.10) & (y > -0.52) & (y < -0.12) & (np.abs(x) < 0.30)   # windscreen
junk = ((sat < 0.3) & (lum > 0.25) & (z < -0.10)) | ((sat < 0.3) & (lum < 0.08) & (z < 0.06) & (np.abs(y) < 0.62) & (np.abs(N[..., 0]) > 0.5))
junk &= ~wheel
bc = bb.copy(); bc[paintpx | junk | plate] = np.array(PAINT[0], np.float32)
br = np.full(lum.shape, PAINT[1], np.float32); bm0 = np.full(lum.shape, PAINT[2], np.float32); bm1 = np.full(lum.shape, PAINT[3], np.float32)
br[dark] = GLASS[1]; bm0[dark] = 0; bm1[dark] = 0
for m_, look in ((glassbox | rglass | wglass, GLASS), (red, RED)):
    bc[m_] = np.array(look[0], np.float32); br[m_] = look[1]; bm0[m_] = 0; bm1[m_] = 0
# the transplanted nose: the generator bakes the grille mesh and the fog-lamp pockets as dark blue (median
# luminance 0.03 and 0.06), which the paint rule above turns body colour. Boxes measured on the front view.
nose = (y < -0.70) & (N[..., 1] < -0.2)
grille = nose & (np.abs(x) < 0.22) & (z > -0.195) & (z < -0.10)                                 # the opening, plate bar included
pocket = nose & (np.abs(x) > 0.26) & (np.abs(x) < 0.37) & (z > -0.195) & (z < -0.095) & (lum < 0.12)   # the lamp itself stays
PLASTIC = cl['PLASTIC']
for m_ in (grille, pocket):
    bc[m_] = np.array(PLASTIC[0], np.float32); br[m_] = PLASTIC[1]; bm0[m_] = 0; bm1[m_] = 0
w_ = wheel[..., None]
col = np.where(w_, col, bc); rough = np.where(wheel, rough, br); mask[..., 0] = np.where(wheel, mask[..., 0], bm0); mask[..., 1] = np.where(wheel, mask[..., 1], bm1)
def put(name, rgb):
    im = bpy.data.images[name]; arr = np.ones((S, S, 4), np.float32); arr[..., :3] = rgb; im.pixels.foreach_set(arr.ravel()); im.save()
lin = np.clip(col, 0, 1); srgb = np.where(lin <= 0.0031308, lin * 12.92, 1.055 * np.power(lin, 1 / 2.4) - 0.055)
put('T_CarCoupeT_BaseColor', srgb); put('T_CarCoupeT_Roughness', np.repeat(rough[..., None], 3, -1)); put('T_CarCoupeT_Mask', mask)

# export + previews
me.materials.clear(); me.materials.append(bpy.data.materials['M_CarT'])
for o in bpy.context.view_layer.objects: o.select_set(False)
ob.select_set(True); bpy.context.view_layer.objects.active = ob
bpy.ops.export_scene.fbx(filepath=D + '\\export\\%s.fbx' % OUT, use_selection=True, axis_forward='-Z', axis_up='Y', global_scale=1.0, apply_unit_scale=True, mesh_smooth_type='FACE', use_mesh_modifiers=True, path_mode='STRIP', embed_textures=False, bake_anim=False)
cam = bpy.data.objects['PV_Cam']; res = (sc.render.resolution_x, sc.render.resolution_y)
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
