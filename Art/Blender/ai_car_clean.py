"""Clean-up experiment for the AI BRZ: the same part outlines, two techniques.

Option A (paint_pixels): every texel gets its 3D position from a baked position map, then parts are painted with
smooth outlines (anti-aliased), so edges ignore the AI triangles.  One material: base colour, roughness and a mask
(R = clear-coat paint, G = metallic).
Option B (build_parts): the parts are real meshes (glass, headlights, grille, fog lights, tail lights, diffuser,
exhausts, arch liners, kit wheels) projected onto the AI body and smoothed; the body itself is one plain paint slot.

Coordinates are game-space metres on the AI coupe: front = -Y, origin 30 cm above the road.
Run inside Blender: exec this file into a dict and call the functions.
"""
import bpy, bmesh, math
import numpy as np
from mathutils import Vector, Matrix
from mathutils.bvhtree import BVHTree

WHEEL_YS = (-0.505, 0.512); WHEEL_Z = -0.178; TYRE_R = 0.127; RIM_R = 0.092
PAINT = ((0.012, 0.075, 0.55), 0.25, 1.0, 0.3)          # colour, roughness, clear-coat mask, metallic


def lerp_pts(pts):
    xs = np.array([p[0] for p in pts]); ys = np.array([p[1] for p in pts])
    return lambda a: np.interp(a, xs, ys)


# ------------------------------------------------------------------ outlines (shared by both options)
def ws_lo(x): return -0.372 + 0.035 * (np.asarray(x) / 0.30) ** 2           # windscreen bottom edge (plan view)
def ws_top(x): return -0.118 - 0.012 * (np.asarray(x) / 0.255) ** 2
def ws_hi(x):                                                               # top edge, then the A-pillar groove
    # the groove between windscreen and pillar runs |x| 0.278 (y -0.36) .. 0.232 (y -0.12), measured by ray cast;
    # stopping 4 mm inside it keeps the pillar body colour
    ax = np.abs(x)
    return np.minimum(ws_top(np.minimum(ax, 0.255)), -0.36 + (0.274 - ax) / 0.19)

def rg_hi(x): return 0.592 - 0.03 * (np.asarray(x) / 0.245) ** 2           # rear glass bottom (towards the boot)
def rg_lo(x):
    ax = np.abs(x); t = np.clip((ax - 0.215) / 0.03, 0, 1)
    return (0.290 + 0.02 * (np.minimum(ax, 0.215) / 0.245) ** 2) * (1 - t) + rg_hi(x) * t

# front part follows the pillar's outer edge (where the surface turns sideways), so the pillar stays body colour
side_hi = lerp_pts([(-0.335, 0.030), (-0.30, 0.055), (-0.27, 0.080), (-0.24, 0.100), (-0.21, 0.120), (-0.18, 0.137),
                    (-0.15, 0.155), (-0.12, 0.168), (-0.08, 0.185), (-0.04, 0.198), (0.0, 0.205), (0.24, 0.204), (0.28, 0.200), (0.32, 0.192),
                    (0.36, 0.183), (0.40, 0.174), (0.44, 0.163), (0.48, 0.148), (0.52, 0.133), (0.545, 0.118)])
def side_lo(y): return 0.040 + 0.46 * np.clip(np.asarray(y) - 0.24, 0, None) ** 1.5
def side_top(y): return np.maximum(side_lo(y), side_hi(y))

def hl_c(a): return -0.085 + (np.asarray(a) - 0.12) * 0.22                  # headlight centre line (front view)
HL_END = 0.335                                                                # nose corner: beyond this the surface faces sideways
def hl_h(a): return 0.028 * np.sqrt(np.clip((np.asarray(a) - 0.12) / 0.28, 0, 1))
def grille_half(z): return 0.21 + (np.asarray(z) + 0.215) * 0.4
tail_lo = lerp_pts([(0.215, 0.025), (0.24, 0.007), (0.26, -0.008), (0.28, -0.016), (0.30, -0.021), (0.32, -0.021),
                    (0.34, -0.012), (0.355, 0.0)])
tail_hi = lerp_pts([(0.215, 0.034), (0.24, 0.039), (0.26, 0.041), (0.28, 0.046), (0.30, 0.050), (0.32, 0.050),
                    (0.34, 0.045), (0.355, 0.035)])

def vent_lo(y): return 0.005 + (np.asarray(y) + 0.451) * 0.06
def vent_hi(y): return vent_lo(y) + 0.026 * np.sqrt(np.clip((np.asarray(y) + 0.451) / 0.10, 0, 1))
def vent_mid(y, f): return vent_lo(y) + (vent_hi(y) - vent_lo(y)) * f

GLASS = ((0.010, 0.013, 0.018), 0.04, 0, 0); TRIM = ((0.010, 0.010, 0.011), 0.25, 0, 0)
PLASTIC = ((0.016, 0.016, 0.017), 0.7, 0, 0); CHROME = ((0.62, 0.62, 0.64), 0.12, 0, 1)
LENS = ((0.030, 0.033, 0.040), 0.06, 0, 0); LED = ((0.75, 0.78, 0.80), 0.2, 0, 0)
RED = ((0.35, 0.008, 0.006), 0.08, 0, 0); SMOKE = ((0.06, 0.004, 0.004), 0.06, 0, 0)

C = lambda v: (lambda a: np.full(np.shape(a), v, float))


def tread_mask(P, N):
    """The AI tyre's tread at the front and back of each wheel (r up to 0.155, facing away from the hub,
    near hub height). classify_parts only catches the sidewall, so this tread stayed blue."""
    x, y, z = P[..., 0], P[..., 1], P[..., 2]; ax = np.abs(x); m = np.zeros(np.shape(x), bool)
    for yw in WHEEL_YS:
        dy, dz = y - yw, z - WHEEL_Z; r = np.hypot(dy, dz)
        rad = (dy * N[..., 1] + dz * N[..., 2]) / np.maximum(r, 1e-6)
        m |= (r < 0.155) & (ax > 0.19) & (ax < 0.35) & (rad > 0.4) & (np.abs(dz) < 0.09)
        side = (N[..., 0] * np.sign(x) > 0.55) & (ax > 0.342)    # fender skin (sideways, outboard of the tyre): only inside the tyre circle
        m |= (r < np.where(side, 0.138, 0.165)) & (ax > 0.19) & (ax < 0.375) & (dz < 0.03) & (dz > -0.13)   # 'flap' fused to the tyre
    return m
# name, plane, a-key, b-key, a0, a1, lo(a), hi(a), look, B material, B offset (m)
PARTS = [
    ('cowl', 'top', 'x', 'y', -0.30, 0.30, lambda a: ws_lo(a) - 0.028, ws_lo, PLASTIC, 'MC_Plastic', 0.002),
    # window frames and pillars are body colour (the team's call), so they paint blue and B skips them
    ('ws_frame', 'top', 'x', 'y', -0.30, 0.30, ws_lo, ws_hi, PAINT, 'MC_PaintWR', 0.002),
    ('windscreen', 'top', 'x', 'y', -0.292, 0.292, lambda a: ws_lo(a) + 0.007, lambda a: ws_hi(a) - 0.006, GLASS, 'MC_Glass', 0.0035),
    ('side_frame', 'side', 'y', 'z', -0.335, 0.545, side_lo, side_top, PAINT, 'MC_PaintWR', 0.002),
    ('side_glass', 'side', 'y', 'z', -0.322, 0.535, lambda a: side_lo(a) + 0.005, lambda a: side_top(a) - 0.006, GLASS, 'MC_Glass', 0.0035),
    ('b_pillar', 'side', 'y', 'z', 0.316, 0.331, side_lo, side_top, PAINT, 'MC_PaintWR', 0.0045),
    ('rg_frame', 'top', 'x', 'y', -0.245, 0.245, rg_lo, rg_hi, PAINT, 'MC_PaintWR', 0.002),
    ('rear_glass', 'top', 'x', 'y', -0.238, 0.238, lambda a: rg_lo(a) + 0.006, lambda a: rg_hi(a) - 0.007, GLASS, 'MC_Glass', 0.0035),
    ('headlight', 'front', 'ax', 'z', 0.12, HL_END, lambda a: hl_c(a) - hl_h(a), lambda a: hl_c(a) + hl_h(a), LENS, 'MC_Glass', 0.003),
    ('hl_brow', 'front', 'ax', 'z', 0.15, HL_END, lambda a: hl_c(a) + hl_h(a) - 0.0045, lambda a: hl_c(a) + hl_h(a), CHROME, 'MC_Chrome', 0.0045),
    ('hl_led', 'front', 'ax', 'z', 0.18, HL_END - 0.012, lambda a: hl_c(a) - hl_h(a) + 0.002, lambda a: hl_c(a) - hl_h(a) + 0.0065, LED, 'MC_Headlight', 0.0045),
    ('grille', 'front', 'z', 'x', -0.215, -0.115, lambda a: -grille_half(a), grille_half, PLASTIC, 'MC_Plastic', 0.002),
    ('fog', 'front', 'z', 'ax', -0.205, -0.125, lambda a: grille_half(a) + 0.03, lambda a: 0.35 - (np.asarray(a) + 0.205) * 0.3, PLASTIC, 'MC_Plastic', 0.002),
    ('taillight', 'rear', 'ax', 'z', 0.215, 0.338,          # 0.338: rear corner (measured), beyond is the side
 tail_lo, tail_hi, RED, 'MC_Taillight', 0.003),
    ('tail_inner', 'rear', 'ax', 'z', 0.25, 0.285, lambda a: (tail_lo(a) + tail_hi(a)) / 2 - 0.007, lambda a: (tail_lo(a) + tail_hi(a)) / 2 + 0.007, SMOKE, 'MC_TailSmoke', 0.004),
    # fender vent behind the front wheel (owner's side photo): pointed at the front, two slats
    ('vent', 'flank', 'y', 'z', -0.451, -0.349, vent_lo, vent_hi, PLASTIC, 'MC_Plastic', 0.002),
    ('vent_slat0', 'flank', 'y', 'z', -0.44, -0.356, lambda a: vent_mid(a, 0.36) - 0.0015, lambda a: vent_mid(a, 0.36) + 0.0015, TRIM, 'MC_Trim', 0.0035),
    ('vent_slat1', 'flank', 'y', 'z', -0.44, -0.356, lambda a: vent_mid(a, 0.68) - 0.0015, lambda a: vent_mid(a, 0.68) + 0.0015, TRIM, 'MC_Trim', 0.0035),
    ('diffuser', 'rear', 'x', 'z', -0.33, 0.33, C(-0.296), C(-0.185), PLASTIC, 'MC_Plastic', 0.002),
]
# grille frame and slats (frame strips + 4 slats), drawn on top of the grille backing
for k, zc in enumerate((-0.195, -0.175, -0.155, -0.135)):
    PARTS.append(('slat%d' % k, 'front', 'z', 'x', zc - 0.0035, zc + 0.0035, lambda a: -grille_half(a) + 0.007,
                  lambda a: grille_half(a) - 0.007, TRIM, 'MC_Trim', 0.006))
PARTS += [('gframe_top', 'front', 'z', 'x', -0.122, -0.115, lambda a: -grille_half(a), grille_half, TRIM, 'MC_Trim', 0.005),
          ('gframe_bot', 'front', 'z', 'x', -0.215, -0.208, lambda a: -grille_half(a), grille_half, TRIM, 'MC_Trim', 0.005),
          ('gframe_l', 'front', 'z', 'x', -0.215, -0.115, lambda a: -grille_half(a), lambda a: -grille_half(a) + 0.007, TRIM, 'MC_Trim', 0.005),
          ('gframe_r', 'front', 'z', 'x', -0.215, -0.115, lambda a: grille_half(a) - 0.007, grille_half, TRIM, 'MC_Trim', 0.005)]
# circles: name, plane, a-key, b-key, centre a, centre b, radius, inner radius, look, B material, B offset, dome
CIRCLES = [
    ('projector', 'front', 'ax', 'z', 0.30, float(hl_c(0.30)), 0.0155, 0.0, CHROME, 'MC_Chrome', 0.004, 0.006),
    ('proj_lens', 'front', 'ax', 'z', 0.30, float(hl_c(0.30)), 0.0095, 0.0, LENS, 'MC_Glass', 0.0105, 0.0),
    ('fog_ring', 'front', 'ax', 'z', 0.315, -0.168, 0.0145, 0.0, CHROME, 'MC_Chrome', 0.004, 0.0),
    ('fog_lens', 'front', 'ax', 'z', 0.315, -0.168, 0.0105, 0.0, LED, 'MC_Headlight', 0.0055, 0.003),
    ('exhaust', 'rear', 'ax', 'z', 0.255, -0.243, 0.022, 0.0, CHROME, 'MC_Chrome', 0.028, 0.0),
    ('exhaust_in', 'rear', 'ax', 'z', 0.255, -0.243, 0.0165, 0.0, PLASTIC, 'MC_Plastic', 0.0285, 0.0),
    # reverse lamp inside the tail light, at the outer corner (rear photos): chrome ring around a clear lens
    ('tail_ring', 'rear', 'ax', 'z', 0.306, 0.0145, 0.018, 0.0, CHROME, 'MC_Chrome', 0.004, 0.0),
    ('tail_rev', 'rear', 'ax', 'z', 0.306, 0.0145, 0.0125, 0.0, LENS, 'MC_Glass', 0.0055, 0.002),
]

DIRS = {'top': Vector((0, 0, -1)), 'front': Vector((0, 1, 0)), 'rear': Vector((0, -1, 0))}


def to_xyz(plane, akey, bkey, a, b, s):
    """In-plane (a, b) -> the two known coordinates; returns dict axis->value (the ray axis is missing)."""
    d = {}
    for key, v in ((akey, a), (bkey, b)):
        if key == 'ax': d['x'] = s * v
        else: d[key] = v
    if plane in ('side', 'flank') and 'x' not in d: d['x'] = None
    return d


# ------------------------------------------------------------------ Option A: per-texel painting
def bake_maps(ob, size=2048, margin=8):
    """Bake object-space position ((p+1)/2) and normal maps into float images on ob's active UV map."""
    sc = bpy.context.scene; sc.render.engine = 'CYCLES'
    imgs = {}
    for nm in ('POS', 'NRM'):
        im = bpy.data.images.get('BAKE_' + nm)
        if im: bpy.data.images.remove(im)
        imgs[nm] = bpy.data.images.new('BAKE_' + nm, size, size, alpha=False, float_buffer=True)
    mat = bpy.data.materials.get('BAKE_MAT') or bpy.data.materials.new('BAKE_MAT'); mat.use_nodes = True
    nt = mat.node_tree; nt.nodes.clear()
    tc = nt.nodes.new('ShaderNodeTexCoord'); vm = nt.nodes.new('ShaderNodeVectorMath'); vm.operation = 'MULTIPLY_ADD'
    vm.inputs[1].default_value = (0.5, 0.5, 0.5); vm.inputs[2].default_value = (0.5, 0.5, 0.5)
    em = nt.nodes.new('ShaderNodeEmission'); out = nt.nodes.new('ShaderNodeOutputMaterial')
    nt.links.new(tc.outputs['Object'], vm.inputs[0]); nt.links.new(vm.outputs[0], em.inputs[0]); nt.links.new(em.outputs[0], out.inputs[0])
    tex = nt.nodes.new('ShaderNodeTexImage'); nt.nodes.active = tex
    keep = [s.material for s in ob.material_slots]
    for s in ob.material_slots: s.material = mat
    for o in bpy.context.view_layer.objects: o.select_set(False)
    ob.select_set(True); bpy.context.view_layer.objects.active = ob
    b = sc.render.bake; b.margin = margin; b.target = 'IMAGE_TEXTURES'; b.use_selected_to_active = False   # left on by real_kit
    sc.cycles.samples = 1
    tex.image = imgs['POS']; bpy.ops.object.bake(type='EMIT', margin=margin)
    tex.image = imgs['NRM']; bpy.ops.object.bake(type='NORMAL', normal_space='OBJECT', margin=margin)
    for s, m in zip(ob.material_slots, keep): s.material = m
    res = {}
    for nm, im in imgs.items():
        a = np.empty(size * size * 4, np.float32); im.pixels.foreach_get(a)
        res[nm] = a.reshape(size, size, 4)[..., :3] * 2 - 1
    return res['POS'], res['NRM']


def _alpha_region(A, B, a0, a1, lo, hi, aa=0.0012):
    d = np.minimum.reduce([A - a0, a1 - A, B - lo(A), hi(A) - B])
    return np.clip(d / aa + 0.5, 0, 1)


def _pixel_ab(plane, akey, bkey, P, N):
    x, y, z = P[..., 0], P[..., 1], P[..., 2]
    get = {'x': x, 'ax': np.abs(x), 'y': y, 'z': z}
    A, B = get[akey], get[bkey]
    nx, ny, nz = N[..., 0], N[..., 1], N[..., 2]
    if plane == 'top': gate = (nz > 0.2) & (z > 0.03)
    elif plane == 'front': gate = (ny < -0.08) & (y < -0.55)
    elif plane == 'rear': gate = (ny > 0.08) & (y > 0.58)
    elif plane == 'flank': gate = (nx * np.sign(x) > 0.4) & (np.abs(x) > 0.3)
    else: gate = (nx * np.sign(x) > 0.25) & (np.abs(x) > 0.2) & (np.abs(x) < 0.335) & (z > 0.02)   # < 0.335 keeps the mirrors blue
    return A, B, gate


def paint_pixels(P, N, orig, skip=()):
    """Return base colour, roughness and mask (H, W, 3) arrays for option A.
    skip: part/circle names not to paint (e.g. the tail lights on a mesh that already has moulded ones)."""
    H, W = P.shape[:2]
    col = np.empty((H, W, 3), np.float32); col[:] = PAINT[0]
    rough = np.full((H, W), PAINT[1], np.float32); coat = np.full((H, W), PAINT[2], np.float32)
    metal = np.full((H, W), PAINT[3], np.float32)

    def put(alpha, look):
        c, r, m, mt = look; a = alpha[..., None]
        col[:] = col * (1 - a) + np.array(c, np.float32) * a
        rough[:] = rough * (1 - alpha) + r * alpha; coat[:] = coat * (1 - alpha) + m * alpha; metal[:] = metal * (1 - alpha) + mt * alpha

    x, y, z = P[..., 0], P[..., 1], P[..., 2]; ax = np.abs(x)
    # wheels first (radius from the wheel centre, crisp circles)
    for yw in WHEEL_YS:
        r = np.hypot(y - yw, z - WHEEL_Z)
        side = ax > 0.22
        bulge = (z < WHEEL_Z) & (np.abs(y - yw) < 0.125) & (r < TYRE_R + 0.035) & (ax > 0.20)
        liner = (r > TYRE_R) & (r < TYRE_R + 0.05) & (ax > 0.15) & (ax < 0.335) & (z > WHEEL_Z - 0.09) & \
                (((y - yw) * N[..., 1] + (z - WHEEL_Z) * N[..., 2]) / np.maximum(r, 1e-6) < -0.3)
        put(liner.astype(np.float32), PLASTIC)
        tyre = np.clip((TYRE_R - r) / 0.0012 + 0.5, 0, 1) * side
        put(np.maximum(tyre, bulge.astype(np.float32)), ((0.020, 0.020, 0.022), 0.85, 0, 0))
        if yw == WHEEL_YS[0]: put(tread_mask(P, N).astype(np.float32), ((0.020, 0.020, 0.022), 0.85, 0, 0))
        rim = np.clip((RIM_R - r) / 0.0012 + 0.5, 0, 1) * side
        lum = orig.mean(-1); red = (orig[..., 0] > orig[..., 2] * 1.6) & (orig[..., 0] > 0.12) & (r < 0.075)
        rimcol = np.where(red[..., None], np.array((0.40, 0.012, 0.01), np.float32), (lum * 0.35 + 0.006)[..., None].repeat(3, -1))
        a = rim[..., None]; col[:] = col * (1 - a) + rimcol * a
        rough[:] = rough * (1 - rim) + 0.18 * rim; coat[:] *= (1 - rim); metal[:] *= (1 - rim)
        stripe = np.clip(np.minimum(r - (RIM_R - 0.0055), (RIM_R - 0.0025) - r) / 0.0008 + 0.5, 0, 1) * side
        put(stripe, ((0.40, 0.012, 0.01), 0.3, 0, 0))
    for name, plane, ak, bk, a0, a1, lo, hi, look, _m, _o in PARTS:
        if name in skip: continue
        A, B, gate = _pixel_ab(plane, ak, bk, P, N)
        put(_alpha_region(A, B, a0, a1, lo, hi) * gate, look)
    for name, plane, ak, bk, ca, cb, rad, rin, look, _m, _o, _d in CIRCLES:
        if name in skip: continue
        A, B, gate = _pixel_ab(plane, ak, bk, P, N)
        d = rad - np.hypot(A - ca, B - cb)
        put(np.clip(d / 0.0010 + 0.5, 0, 1) * gate, look)
    # fuel door: a thin darker seam circle on the right rear quarter (Blender -X), measured off the side photo
    fd = (x < -0.3) & (-N[..., 0] > 0.5)
    ring = np.clip((0.0009 - np.abs(np.hypot(y - 0.614, z - 0.025) - 0.036)) / 0.0006 + 0.5, 0, 1) * fd
    a = ring[..., None]; col[:] = col * (1 - a * 0.7)
    mask = np.stack([coat, metal, np.zeros_like(coat)], -1)
    return col, rough, mask


def paint_faces(src, slot_name, col, rough, mask, look):
    """Paint every texel under the faces that use one of src's material slots (e.g. the wing in MC_Trim)."""
    fx = {}; exec(open(bpy.path.abspath('//ai_car_fix.py')).read(), fx)
    me = src.data; H, W = col.shape[:2]
    si = [m.name for m in me.materials].index(slot_name)
    m = fx['raster_faces'](me, [p for p in me.polygons if p.material_index == si], W, H)
    c, r, cc, mt = look
    col[m] = c; rough[m] = r; mask[m, 0] = cc; mask[m, 1] = mt
    return int(m.sum())


# ------------------------------------------------------------------ Option B: real parts on the body
def _smooth(D, it=4):
    for _ in range(it):
        p = np.pad(D, 1, mode='edge')
        D = (p[1:-1, 1:-1] * 4 + p[:-2, 1:-1] + p[2:, 1:-1] + p[1:-1, :-2] + p[1:-1, 2:]) / 8
    return D


def _cast(bvh, plane, pts2, s):
    """pts2: list of dicts with x/y/z known except the ray axis. Returns origins, direction, hit depths (nan = miss)."""
    if plane in ('side', 'flank'): d = Vector((-s, 0, 0))
    else: d = DIRS[plane]
    org, dep = [], []
    for p in pts2:
        o = Vector((p.get('x') if p.get('x') is not None else 0.0, p.get('y', 0.0), p.get('z', 0.0)))
        if plane == 'top': o.z = 1.0
        elif plane == 'front': o.y = -2.0
        elif plane == 'rear': o.y = 2.0
        else: o.x = s * 1.0
        hit = bvh.ray_cast(o, d, 4.0)
        org.append(o); dep.append(hit[3] if hit[0] is not None else np.nan)
    return org, d, np.array(dep, float)


def _grid_part(bm, bvh, mi, plane, ak, bk, a0, a1, lo, hi, s, off, step=0.004, depth_skirt=0.006):
    na = max(6, int(abs(a1 - a0) / step) + 1)
    A = np.linspace(a0, a1, na); LO = lo(A); HI = np.maximum(hi(A), LO)
    nb = max(3, int(np.max(HI - LO) / step) + 1)
    T = np.linspace(0, 1, nb)
    pts = [to_xyz(plane, ak, bk, A[i], LO[i] + (HI[i] - LO[i]) * T[j], s) for i in range(na) for j in range(nb)]
    org, d, dep = _cast(bvh, plane, pts, s)
    if np.all(np.isnan(dep)): return 0
    dep = dep.reshape(na, nb)
    med = np.nanmedian(dep)
    # rays that slipped past the body edge or hit a mirror: reject hits far from a smooth (quadratic) fit
    gi, gj = np.meshgrid(np.linspace(-1, 1, na), np.linspace(-1, 1, nb), indexing='ij')
    X = np.stack([np.ones_like(gi), gi, gj, gi * gi, gi * gj, gj * gj, gi ** 3, gj ** 3], -1).reshape(-1, 8)
    for _ in range(3):
        ok = ~np.isnan(dep.ravel())
        if ok.sum() < 10: break
        coef = np.linalg.lstsq(X[ok], dep.ravel()[ok], rcond=None)[0]
        res = np.abs(dep - (X @ coef).reshape(na, nb))
        dep[res > 0.06] = np.nan
    good = np.mean(~np.isnan(dep), axis=1) >= 0.6     # trim columns that mostly miss the body (part wider than the car)
    if good.sum() < 2: return 0
    i0, i1 = np.nonzero(good)[0][[0, -1]]
    dep = dep[i0:i1 + 1]; org = [org[i * nb + j] for i in range(i0, i1 + 1) for j in range(nb)]; na = i1 - i0 + 1
    for i in range(na):                              # fill holes from neighbours along each row, then each column
        ok = ~np.isnan(dep[i])
        if ok.sum() >= 2: dep[i] = np.interp(np.arange(nb), np.nonzero(ok)[0], dep[i][ok])
    for j in range(nb):
        ok = ~np.isnan(dep[:, j])
        if ok.sum() >= 2: dep[:, j] = np.interp(np.arange(na), np.nonzero(ok)[0], dep[:, j][ok])
    dep = np.where(np.isnan(dep), med, dep)
    dep = _smooth(dep)
    org = np.array([tuple(o) for o in org]).reshape(na, nb, 3); dv = np.array(d)
    top = org + dv * (dep - off)[..., None]; bot = org + dv * (dep + depth_skirt)[..., None]
    V = [[bm.verts.new(top[i, j]) for j in range(nb)] for i in range(na)]
    faces = []
    for i in range(na - 1):
        for j in range(nb - 1):
            q = (V[i][j], V[i + 1][j], V[i + 1][j + 1], V[i][j + 1])
            faces.append(bm.faces.new(q))
    ring = [(i, 0) for i in range(na)] + [(na - 1, j) for j in range(1, nb)] + \
           [(i, nb - 1) for i in range(na - 2, -1, -1)] + [(0, j) for j in range(nb - 2, 0, -1)]
    B = {ij: bm.verts.new(bot[ij]) for ij in ring}
    for k in range(len(ring)):
        p, q = ring[k], ring[(k + 1) % len(ring)]
        faces.append(bm.faces.new((V[p[0]][p[1]], V[q[0]][q[1]], B[q], B[p])))
    for f in faces: f.material_index = mi
    # outward facing: top faces must point back along the ray
    f0 = faces[0]; f0.normal_update()
    if f0.normal.dot(Vector(dv)) > 0:
        for f in faces: f.normal_flip()
    return len(faces)


def _disc_part(bm, bvh, mi, plane, ak, bk, ca, cb, rad, s, off, dome, depth_skirt=0.006, seg=40, rings=6):
    pts = [to_xyz(plane, ak, bk, ca, cb, s)]
    for r in range(1, rings + 1):
        rr = rad * r / rings
        for k in range(seg):
            t = 2 * math.pi * k / seg
            pts.append(to_xyz(plane, ak, bk, ca + rr * math.cos(t), cb + rr * math.sin(t), s))
    org, d, dep = _cast(bvh, plane, pts, s)
    if np.all(np.isnan(dep)): return 0
    base = np.nanmedian(dep)                                   # a flat disc: lamps and exhausts are not bent
    dv = np.array(d); org = np.array([tuple(o) for o in org])
    rho = np.array([0.0] + [r / rings for r in range(1, rings + 1) for _ in range(seg)])
    top = org + dv * (base - off - dome * (1 - rho ** 2))[:, None]
    V = [bm.verts.new(p) for p in top]
    faces = []
    for k in range(seg):
        faces.append(bm.faces.new((V[0], V[1 + k], V[1 + (k + 1) % seg])))
    for r in range(1, rings):
        for k in range(seg):
            a0 = 1 + (r - 1) * seg; a1 = 1 + r * seg
            faces.append(bm.faces.new((V[a0 + k], V[a1 + k], V[a1 + (k + 1) % seg], V[a0 + (k + 1) % seg])))
    outer = [1 + (rings - 1) * seg + k for k in range(seg)]
    Bv = [bm.verts.new(org[i] + dv * (base + depth_skirt)) for i in outer]
    for k in range(seg):
        faces.append(bm.faces.new((V[outer[k]], V[outer[(k + 1) % seg]], Bv[(k + 1) % seg], Bv[k])))
    for f in faces: f.material_index = mi
    f0 = faces[0]; f0.normal_update()
    if f0.normal.dot(Vector(dv)) > 0:
        for f in faces: f.normal_flip()
    return len(faces)


def _liners(bm, mi, R=TYRE_R + 0.016, seg=36, narrow=1.0):
    n = 0
    for yw in WHEEL_YS:
        for s in (1, -1):
            xs = (s * 0.16 * narrow, s * 0.356 * narrow)
            th = np.linspace(math.radians(-12), math.radians(192), seg)
            V = [[bm.verts.new((x, yw + R * math.cos(t), WHEEL_Z + R * math.sin(t))) for t in th] for x in xs]
            for k in range(seg - 1):
                f = bm.faces.new((V[0][k], V[0][k + 1], V[1][k + 1], V[1][k])); f.material_index = mi
                f.normal_update()
                c = f.calc_center_median()
                if f.normal.dot(Vector((0, c.y - yw, c.z - WHEEL_Z))) > 0: f.normal_flip()   # face the wheel
                n += 1
    return n


def fill_gaps(ob, box, merge=0.0004, sides=60):
    """Close small gaps in an AI mesh inside box ((x0,y0,z0),(x1,y1,z1)), where the dark inside shows through.
    Seam-split duplicates are merged first; each new face copies its UVs from the neighbouring paint, so
    the patch takes the surrounding colour. Keep the box tight: openings on purpose (wheel arches,
    exhausts) are holes too. Returns the number of faces added."""
    (x0, y0, z0), (x1, y1, z1) = box
    me = ob.data; bm = bmesh.new(); bm.from_mesh(me); uvl = bm.loops.layers.uv.active
    inside = lambda v: x0 < v.co.x < x1 and y0 < v.co.y < y1 and z0 < v.co.z < z1
    bv = [v for v in bm.verts if inside(v) and any(e.is_boundary for e in v.link_edges)]
    bmesh.ops.remove_doubles(bm, verts=bv, dist=merge)
    bnd = [e for e in bm.edges if e.is_boundary and inside(e.verts[0]) and inside(e.verts[1])]
    new = bmesh.ops.holes_fill(bm, edges=bnd, sides=sides)['faces']; ns = set(new)
    for f in new:
        f.material_index = 0
        for l in f.loops:
            src = [ll for ll in l.vert.link_loops if ll.face not in ns]
            if src: l[uvl].uv = src[0][uvl].uv.copy()
    bmesh.ops.recalc_face_normals(bm, faces=new)
    bm.to_mesh(me); bm.free()
    for p in me.polygons: p.use_smooth = True
    return len(new)


# gaps found on the BRZ: right rear quarter beside the fuel door
GAPS = [((-0.40, 0.50, -0.09), (-0.24, 0.80, 0.13))]


# ------------------------------------------------------------------ body repair (trunk and lumpy panels)
# The AI fused a second, broken wing into the trunk lid: floating blades, an overhanging lip, end blocks and
# torn sheets. fix_trunk irons all of it down onto a smooth deck measured from the clean parts of the lid,
# and we model our own wing instead (build_wing).
DECK_X = np.array([0, 0.10, 0.15, 0.20, 0.25, 0.27, 0.29, 0.31, 0.33, 0.35, 0.40])     # crown + shoulders, measured
DECK_Z = np.array([0.130, 0.124, 0.118, 0.112, 0.108, 0.104, 0.089, 0.072, 0.058, 0.045, 0.01])  # just behind the glass
REAR_X = np.array([0, 0.04, 0.10, 0.14, 0.18, 0.20, 0.22, 0.24, 0.26, 0.28, 0.30, 0.32, 0.34, 0.40])  # rear face line
REAR_Y = np.array([0.816, 0.811, 0.809, 0.808, 0.798, 0.793, 0.790, 0.778, 0.767, 0.747, 0.733, 0.722, 0.718, 0.70])


def rear_y(x): return np.interp(np.abs(x), REAR_X, REAR_Y)


def deck_z(x, y):
    """Height of the clean trunk lid: crown/shoulder profile + the centre-line slope, rounded over at the back."""
    y = np.asarray(y, float); t = np.clip(y - 0.74, 0, None)
    slope = np.where(y < 0.74, -0.155 * (y - 0.63), -0.155 * 0.11 - 0.2 * t - 1.5 * t * t)
    e = np.clip((y - (rear_y(x) - 0.015)) / 0.015, 0, 1.2)      # capped: past the rear face it stays level
    return np.interp(np.abs(x), DECK_X, DECK_Z) + slope - 0.004 - 0.012 * e * e


def fix_trunk(ob):
    """Remove the AI's fused wing from the trunk lid of ob (in place). Returns counts."""
    me = ob.data; bm = bmesh.new(); bm.from_mesh(me); uvl = bm.loops.layers.uv.active
    trim = [m.name for m in me.materials].index('MC_Trim') if 'MC_Trim' in me.materials else -1
    def junk(f):                                   # the flat AI blade, and the thin blades floating at its front edge
        if f.material_index == trim: return True
        c = f.calc_center_median(); ax = abs(c.x); yr = float(rear_y(c.x))
        if 0.27 < ax < 0.39 and c.y > yr - 0.02 and c.z > float(deck_z(c.x, yr - 0.015)) - 0.005:
            return True                            # the AI's wing risers sitting on the tail-light corners
        return (0.595 < c.y < 0.70 and ax < 0.37 and c.z - deck_z(c.x, c.y) > 0.007
                and (f.normal.z < 0 or f.normal.y < 0.12))
    dead = [f for f in bm.faces if junk(f)]
    bmesh.ops.delete(bm, geom=dead, context='FACES')
    bmesh.ops.delete(bm, geom=[v for v in bm.verts if not v.link_faces], context='VERTS')
    pressed = 0
    for v in bm.verts:                             # iron everything above the deck down onto it
        x, y, z = v.co
        if not (abs(x) < 0.37 and y > 0.600 and z > -0.01): continue
        yr = float(rear_y(x))
        if abs(x) < 0.27 and y > yr and z > float(deck_z(x, yr)) - 0.025: y = yr     # the lip hanging past the rear face
        if abs(x) >= 0.27 and y > yr - 0.015:     # tail-light corners: only the AI end blocks above the shoulder
            h = float(deck_z(x, yr - 0.015))
        else:
            h = float(deck_z(x, y))
        if z > h or y != v.co.y: v.co.y = y; v.co.z = min(z, h); pressed += 1
    box = lambda v: abs(v.co.x) < 0.38 and 0.58 < v.co.y < 0.90 and v.co.z > -0.02
    bv = [v for v in bm.verts if box(v) and any(e.is_boundary for e in v.link_edges)]
    bmesh.ops.remove_doubles(bm, verts=bv, dist=0.0006)
    bnd = [e for e in bm.edges if e.is_boundary and box(e.verts[0]) and box(e.verts[1])]
    new = bmesh.ops.holes_fill(bm, edges=bnd, sides=400)['faces']; ns = set(new)
    for f in new:
        f.material_index = 0
        for l in f.loops:
            src = [ll for ll in l.vert.link_loops if ll.face not in ns]
            if src: l[uvl].uv = src[0][uvl].uv.copy()
    new = bmesh.ops.triangulate(bm, faces=new)['faces']
    for f in new:                                  # patches face up/out (never recalc the whole AI mesh:
        c = f.calc_center_median()                 # it is not closed, and that flipped big areas inside out)
        if f.normal.dot(Vector((0, 0.3 if c.y > 0.8 else 0, 1))) < 0: f.normal_flip()
    skin = _deck_skin(bm, uvl)
    bm.to_mesh(me); bm.free()
    for p in me.polygons: p.use_smooth = True
    return {'deleted': len(dead), 'pressed': pressed, 'filled': len(new), 'skin': skin}


def _deck_skin(bm, uvl, half=0.31, nx=53, ny=28, lift=0.0006):
    """A clean grid laid over the ironed lid, a hair above it, so slits left between ironed layers can't
    show. Its front row and outer columns tuck a few mm under the body so no edge stands proud; the rear
    corners beyond `half` are left to the wing's end plates. UVs all point at one plain-paint texel (roof)."""
    roof = min((f for f in bm.faces if f.material_index == 0 and f.normal.z > 0.9),
               key=lambda f: (f.calc_center_median() - Vector((0, 0.05, 0.24))).length)
    uv = roof.loops[0][uvl].uv.copy()
    xs = np.linspace(-half, half, nx); rows = []
    for j in range(ny):
        row = []
        for x in xs:
            y = 0.600 + (float(rear_y(x)) - 0.002 - 0.600) * j / (ny - 1)
            tuck = -0.004 if (j == 0 or abs(x) > half - 0.015) else lift
            row.append(bm.verts.new((x, y, float(deck_z(x, y)) + tuck)))
        rows.append(row)
    n = 0
    for a, b in zip(rows, rows[1:]):
        for i in range(nx - 1):
            f = bm.faces.new((a[i], a[i + 1], b[i + 1], b[i])); f.material_index = 0; n += 1
            if f.normal.z < 0: f.normal_flip()
            for l in f.loops: l[uvl].uv = uv
    return n


def fix_fenders(ob, amp=0.018, cx=0.31, wx=0.09, cy=-0.50, wy=0.26):
    """The real BRZ's front fender tops rise above the hood edge; the AI left them flat. Push the fender
    skin outward along its normals in a soft bump centred on (|x|=cx, y=cy). In place; returns verts moved."""
    me = ob.data; n = len(me.vertices)
    co = np.empty(n * 3); me.vertices.foreach_get('co', co); co = co.reshape(n, 3)
    vn = np.empty(n * 3); me.vertices.foreach_get('normal', vn); vn = vn.reshape(n, 3)
    bx = np.clip(1 - np.abs(np.abs(co[:, 0]) - cx) / wx, 0, 1); by = np.clip(1 - np.abs(co[:, 1] - cy) / wy, 0, 1)
    w = amp * (0.5 - 0.5 * np.cos(np.pi * bx)) * (0.5 - 0.5 * np.cos(np.pi * by)) * (co[:, 2] > -0.12)
    co += w[:, None] * vn
    me.vertices.foreach_set('co', co.ravel()); me.update()
    return int((w > 1e-4).sum())


# the AI body is 15% too wide for a BRZ (4240 x 1775 mm: length/width 2.39; ours was 2.07). build_parts
# narrows everything except the wheels, which already sit at the real track width.
NARROW = 0.867


def smooth_body(ob, iters=10, lam=0.5, keep_sharp=(-2, -1), skip=None, normal_iters=60, deck_box=None,
                snap_dot=0.5, snap_rings=4):
    """Iron out the AI's lumpy panels (in place), in two layers:
    - shape: each vertex moves towards the average of its neighbours for `iters` rounds, but only along its
      normal (in/out). Sliding sideways moves the texture with it and zigzags painted outlines. (Gently, so the
      overlapping skin layers the AI leaves at panel seams don't pull apart into holes);
    - light: the normals come from a much smoother copy (`normal_iters` rounds), so the remaining lumps and
      creases stop catching the light. This is most of the visible improvement.
    UV-split seams are welded first (UVs are kept per corner). keep_sharp (cosines) can freeze sharp corners,
    but by default nothing is frozen: the AI's jagged panel lines all count as sharp, and freezing them kept
    the jaggies as ridges.
    skip: box ((x0,y0,z0),(x1,y1,z1)) whose shape is left alone (the ironed trunk: folded layers).
    deck_box: box whose top-facing normals come straight from deck_z (the trunk lid)."""
    me = ob.data; bm = bmesh.new(); bm.from_mesh(me)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-5)
    bm.to_mesh(me); bm.free()
    nv = len(me.vertices); ne = len(me.edges); nf = len(me.polygons)
    co = np.empty(nv * 3); me.vertices.foreach_get('co', co); co = co.reshape(nv, 3)
    ed = np.empty(ne * 2, np.int64); me.edges.foreach_get('vertices', ed); ed = ed.reshape(ne, 2)
    fn = np.empty(nf * 3); me.polygons.foreach_get('normal', fn); fn = fn.reshape(nf, 3)
    vn = np.empty(nv * 3); me.vertices.foreach_get('normal', vn); vn = vn.reshape(nv, 3)
    lt = np.empty(nf, np.int64); me.polygons.foreach_get('loop_total', lt)
    lv = np.empty(len(me.loops), np.int64); me.loops.foreach_get('vertex_index', lv)
    lf = np.repeat(np.arange(nf), lt)
    cmin = np.ones(nv); np.minimum.at(cmin, lv, np.einsum('ij,ij->i', fn[lf], vn[lv]))
    w = np.clip((cmin - keep_sharp[0]) / (keep_sharp[1] - keep_sharp[0]), 0, 1)
    inbox = lambda P, box: np.all((P > np.array(box[0])) & (P < np.array(box[1])), 1)
    deg = np.zeros(nv); np.add.at(deg, ed[:, 0], 1); np.add.at(deg, ed[:, 1], 1); deg = np.maximum(deg, 1)
    def step(P, wv):
        s = np.zeros_like(P); np.add.at(s, ed[:, 0], P[ed[:, 1]]); np.add.at(s, ed[:, 1], P[ed[:, 0]])
        d = s / deg[:, None] - P
        d = np.einsum('ij,ij->i', d, vn)[:, None] * vn     # in/out only: sliding along the surface drags
        P += (lam * wv)[:, None] * d                      # the painted outlines into zigzags
    keep = ~inbox(co, skip) if skip else np.ones(nv, bool)
    ws = w * keep
    for _ in range(iters): step(co, ws)
    me.calc_loop_triangles(); tri = np.empty(len(me.loop_triangles) * 3, np.int64)
    me.loop_triangles.foreach_get('vertices', tri); tri = tri.reshape(-1, 3)
    def vnormals(Q):
        fnn = np.cross(Q[tri[:, 1]] - Q[tri[:, 0]], Q[tri[:, 2]] - Q[tri[:, 0]])
        out = np.zeros_like(Q)
        for k in range(3): np.add.at(out, tri[:, k], fnn)
        return fnn, out / np.maximum(np.linalg.norm(out, axis=1, keepdims=True), 1e-12)
    # steps and folds: the AI's panel seams are jagged ledges a few mm high, or skin folded back on itself
    # (dark jagged lines). Any triangle tilted more than ~60 degrees from the smooth surface marks one; its
    # vertices and a few rings around blend onto the smooth surface.
    P = co.copy()
    for _ in range(normal_iters): step(P, np.ones(nv))     # unweighted: frozen ledges would survive in P
    folds = 0
    for _ in range(2):
        fco, _n = vnormals(co); _f, Ns = vnormals(P)
        fco /= np.maximum(np.linalg.norm(fco, axis=1, keepdims=True), 1e-12)
        bad_t = np.einsum('ij,ij->i', fco, Ns[tri].mean(1)) < snap_dot
        fv = np.zeros(nv, bool); fv[tri[bad_t].ravel()] = True
        wt = fv.astype(float); cur = fv.copy()
        for k in range(snap_rings):
            nxt = cur.copy(); nxt[ed[cur[ed[:, 0]], 1]] = True; nxt[ed[cur[ed[:, 1]], 0]] = True
            wt = np.maximum(wt, (nxt & ~cur) * (1 - (k + 1) / (snap_rings + 1))); cur = nxt
        wt *= keep
        folds += int((wt > 0).sum()); co += wt[:, None] * (P - co)
    me.vertices.foreach_set('co', co.ravel()); me.update()
    # normals from the smoother copy, area-weighted
    _f, N = vnormals(P); _f, Nc = vnormals(co)
    bad = np.einsum('ij,ij->i', N, Nc) < 0.3                    # never tilt a normal far from its real faces
    N[bad] = Nc[bad]
    if deck_box:                                               # the ironed lid: normals straight from deck_z
        m = inbox(co, deck_box) & (vn[:, 2] > 0.3)
        x, y = co[m, 0], co[m, 1]; e = 1e-3
        gx = (deck_z(x + e, y) - deck_z(x - e, y)) / (2 * e); gy = (deck_z(x, y + e) - deck_z(x, y - e)) / (2 * e)
        g = np.stack([-gx, -gy, np.ones_like(gx)], 1); N[m] = g / np.linalg.norm(g, axis=1, keepdims=True)
    for p in me.polygons: p.use_smooth = True
    me.normals_split_custom_set_from_vertices([tuple(n) for n in N])
    # also keep them per point: custom normals get scrambled when faces are added or deleted later
    # (build_parts), so it re-applies these as its last step
    a = me.attributes.get('smooth_n') or me.attributes.new('smooth_n', 'FLOAT_VECTOR', 'POINT')
    a.data.foreach_set('vector', N.astype(np.float32).ravel())
    return {'verts': nv, 'frozen': int((w == 0).sum()), 'fold_verts': folds,
            'deck_normals': int(m.sum()) if deck_box else 0}


# our rear wing (the user's car): a flat black blade swept along the trunk's back edge, on two body-colour
# risers, with body-colour end plates. Sizes follow the AI blade (span +-0.335, chord y 0.705..0.78).
WING_SPAN = 0.335; WING_Y = (0.705, 0.782); WING_TOP = 0.130    # blade top: ~1 cm clear of the lid (photo)


def wing_sweep(x):
    """The blade is flat but curves in plan view: it follows the trunk's back edge (user's photo), so the
    tips sit further forward than the middle. Returns the blade's trailing-edge y at x."""
    return float(rear_y(x)) + 0.004


# end plate outline traced from the user's photo: (along the car 0 = front .. 1 = back, down 0 = top .. 1)
# a long top edge, a rounded top-back corner, a near-vertical back edge and a long sloped cut at the front
PLATE_UV = [(0.0, 0.03), (0.02, 0.0), (0.40, 0.08), (0.80, 0.18), (0.86, 0.22), (0.90, 0.29), (0.95, 0.62),
            (1.0, 0.94), (0.985, 1.0), (0.70, 0.97), (0.40, 0.91), (0.28, 0.85), (0.16, 0.71), (0.07, 0.50),
            (0.02, 0.27)]
PLATE_LEN, PLATE_H, PLATE_T = 0.105, 0.055, 0.007


def _end_plate(bm, x, ztip, mat, uvl, uv):
    """One flat end plate centred on x, its top a little above the blade tip (ztip)."""
    y0 = wing_sweep(x) - (WING_Y[1] - WING_Y[0]) - 0.012; zt = ztip + 0.016
    pts = [(y0 + u * PLATE_LEN, zt - v * PLATE_H) for u, v in PLATE_UV]
    sides = []
    for dx in (-PLATE_T / 2, PLATE_T / 2):
        sides.append([bm.verts.new((x + dx, y, z)) for y, z in pts])
    a, b = sides; fs = [bm.faces.new(a[::-1]), bm.faces.new(b)]
    for i in range(len(pts)):
        j = (i + 1) % len(pts); fs.append(bm.faces.new((a[i], a[j], b[j], b[i])))
    bmesh.ops.recalc_face_normals(bm, faces=fs)
    for f in fs:
        f.material_index = mat
        for l in f.loops: l[uvl].uv = uv
    return len(fs)


def _box(bm, lo, hi, mat, uvl=None, uv=None):
    res = bmesh.ops.create_cube(bm, size=1.0)
    c = [(l + h) / 2 for l, h in zip(lo, hi)]; s = [h - l for l, h in zip(lo, hi)]
    for v in res['verts']: v.co = Vector((c[0] + v.co.x * s[0], c[1] + v.co.y * s[1], c[2] + v.co.z * s[2]))
    fs = {f for v in res['verts'] for f in v.link_faces}
    for f in fs:
        f.material_index = mat
        if uvl is not None:
            for l in f.loops: l[uvl].uv = uv
    return len(fs)


def build_wing(bm, trim, paint, seg=24):
    """Add the wing to bm. trim/paint: material slots for the black parts and the body colour.
    Its faces are tagged in the 'flat' face layer so build_parts can give them hard edges."""
    uvl = bm.loops.layers.uv.active
    old = bm.faces.layers.int.new('old_face')      # mark what exists now (freed slots get reused, so
    for f in bm.faces: f[old] = 1                  # neither face sets nor indices find the new faces)
    roof = min((f for f in bm.faces if f.material_index == paint and f.normal.z > 0.9),
               key=lambda f: (f.calc_center_median() - Vector((0, 0.05, 0.24))).length)
    uv = roof.loops[0][uvl].uv.copy()
    y0, y1 = WING_Y; n = 0
    # blade: a thin aerofoil (round nose, flat-ish top, thin tail with a small kick-up). Flat, but swept in
    # plan view along the trunk's back edge (wing_sweep).
    chord = WING_Y[1] - WING_Y[0]; prof = []
    for i in range(seg + 1):                      # upper surface, nose -> tail, as (0..1 along chord, z)
        t = i / seg; prof.append((t, 0.0012 + 0.0078 * math.sqrt(t) * (1 - t) ** 0.8 + 0.004 * t ** 6))
    low = [(t, -0.0035 * math.sin(math.pi * t) ** 0.7) for t, _ in prof]
    ring = prof + low[::-1][1:-1]
    xs = np.linspace(-WING_SPAN, WING_SPAN, 25)
    rows = [[bm.verts.new((x, wing_sweep(x) - chord * (1 - t), WING_TOP - 0.010 + z)) for t, z in ring] for x in xs]
    for a, b in zip(rows, rows[1:]):
        for i in range(len(ring)):
            j = (i + 1) % len(ring); f = bm.faces.new((a[i], a[j], b[j], b[i])); f.material_index = trim; n += 1
    for r, s in ((rows[0], -1), (rows[-1], 1)):
        f = bm.faces.new(r if s < 0 else r[::-1]); f.material_index = trim; n += 1
    # two body-colour risers near the ends of the lid, under the middle of the blade
    for sx in (-1, 1):
        x = sx * 0.27; yc = wing_sweep(x) - chord * 0.5
        n += _box(bm, (x - 0.005, yc - 0.018, float(deck_z(x, yc)) - 0.006), (x + 0.005, yc + 0.018, WING_TOP - 0.011),
                  paint, uvl, uv)
    # end plates (body colour), the shape from the user's photo, at each blade tip
    for sx in (-1, 1):
        n += _end_plate(bm, sx * (WING_SPAN + 0.002), WING_TOP, paint, uvl, uv)
    flat = bm.faces.layers.int.get('flat') or bm.faces.layers.int.new('flat')
    old = bm.faces.layers.int['old_face']
    for f in bm.faces:
        if not f[old]: f[flat] = 1
    bm.faces.layers.int.remove(old)
    return n



# ------------------------------------------------------------------ TRELLIS.2 output (D:/AI/TRELLIS2/run_image_to_3d.py)
TRELLIS_SKIP = ('taillight', 'tail_inner', 'tail_ring', 'tail_rev')   # moulded on the mesh; painted from its own texture instead


def texture_lamps(ob, image, col, rough, mask, P, look=None, y_min=0.55):
    """Paint the generator's red lamp pixels (its texture shares our baked UVs) with the tail-light look,
    so the lamps land exactly on the moulded lights. Edits col/rough/mask in place; returns pixel count."""
    look = look or RED; W, H = image.size; S = col.shape[0]
    px = np.empty(W * H * 4, np.float32); image.pixels.foreach_get(px); px = px.reshape(H, W, 4)[..., :3]
    if W != S: idx = np.arange(S) * W // S; px = px[idx][:, idx]
    r, g, b = px[..., 0], px[..., 1], px[..., 2]
    lamp = ((r > 0.22) & (r > 1.7 * g) & (r > 1.7 * b) & (P[..., 1] > y_min)).astype(np.float32)
    k = np.pad(lamp, 2, mode='edge')
    from numpy.lib.stride_tricks import sliding_window_view
    a = np.clip(sliding_window_view(k, (5, 5)).mean((-1, -2)) * 1.4, 0, 1)
    col[:] = col * (1 - a[..., None]) + np.array(look[0], np.float32) * a[..., None]
    rough[:] = rough * (1 - a) + look[1] * a; mask[..., 0] *= (1 - a); mask[..., 1] *= (1 - a)
    return int((a > 0.5).sum())
def import_trellis(glb, name='TR_BRZ', length=1.717, decimate=None):
    """Import a TRELLIS.2 GLB into game space (front -Y, up Z, `length` long, origin 30 cm above the road),
    cut the reflections the generator turns into solids on the roof, and optionally decimate to a face
    count. The GLB's own texture is dropped (we paint by position). Returns the object."""
    import math
    for o in list(bpy.data.objects):
        if o.name == name or o.name.startswith('geometry_'): bpy.data.objects.remove(o)
    before = set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=glb)
    new = [o for o in bpy.data.objects if o not in before]
    ob = [o for o in new if o.type == 'MESH'][0]; ob.name = name
    for o in new:
        if o.type != 'MESH': bpy.data.objects.remove(o)
    for o in bpy.context.view_layer.objects: o.select_set(False)
    ob.select_set(True); bpy.context.view_layer.objects.active = ob
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    me = ob.data; n = len(me.vertices)
    co = np.empty(n * 3); me.vertices.foreach_get('co', co); co = co.reshape(n, 3)
    co *= length / (co[:, 1].max() - co[:, 1].min())
    x, y, z = co.T
    wing = (np.abs(x) > 0.22) & (np.abs(x) < 0.36) & (z > z.min() + 0.39) & (np.abs(y) > 0.5)   # end plates: high, outboard, at one end
    if wing.any() and y[wing].mean() < 0: co[:, 0] *= -1; co[:, 1] *= -1             # wing must be at +Y (rear)
    co[:, 0] -= (co[:, 0].max() + co[:, 0].min()) / 2; co[:, 1] -= (co[:, 1].max() + co[:, 1].min()) / 2
    co[:, 2] -= co[:, 2].min() + 0.30
    me.vertices.foreach_set('co', co.ravel()); me.update()
    cut_roof_junk(ob)
    for p in me.polygons: p.use_smooth = True
    if decimate:
        # the remeshed skin carries micro-noise that decimation folds into creases: smooth it first (normal-
        # direction only, so nothing slides), decimate, then shade the low-poly mesh with the smooth normals
        smooth_body(ob, iters=6, normal_iters=30, snap_dot=-2)
        hi = ob.copy(); hi.data = me.copy(); bpy.context.scene.collection.objects.link(hi)
        mod = ob.modifiers.new('dec', 'DECIMATE'); mod.ratio = decimate / len(me.polygons); mod.use_collapse_triangulate = True
        bpy.ops.object.modifier_apply(modifier=mod.name)
        mod = ob.modifiers.new('nrm', 'DATA_TRANSFER'); mod.object = hi; mod.use_loop_data = True
        mod.data_types_loops = {'CUSTOM_NORMAL'}; mod.loop_mapping = 'POLYINTERP_NEAREST'
        bpy.ops.object.modifier_apply(modifier=mod.name)
        bpy.data.objects.remove(hi)
    return ob


def cut_roof_junk(ob, half=0.19, lift=0.012):
    """Reflections in the photo become plates and blobs standing on the roof. Fit a smooth surface through
    the highest point of each 2 cm cell of the flat roof centre (|x| < half) and delete faces more than
    `lift` above it, then close the slits left behind."""
    me = ob.data; nf = len(me.polygons)
    C = np.empty(nf * 3); me.polygons.foreach_get('center', C); C = C.reshape(nf, 3)
    N = np.empty(nf * 3); me.polygons.foreach_get('normal', N); N = N.reshape(nf, 3)
    x, y, z = C.T
    region = (np.abs(x) < 0.30) & (y > -0.50) & (y < 0.25) & (z > 0.0); up = region & (N[:, 2] > 0.5)
    key = ((x + 0.30) // 0.02).astype(int) * 1000 + ((y + 0.50) // 0.02).astype(int)
    top = {}
    for k, zz in zip(key[up], z[up]):
        if zz > top.get(k, -9): top[k] = zz
    ks = np.array(list(top)); zs = np.array([top[k] for k in ks]); xs = (ks // 1000) * 0.02 - 0.29; ys = (ks % 1000) * 0.02 - 0.49
    def basis(x, y):
        X = x / 0.3; Y = y / 0.4
        return np.stack([X ** i * Y ** j for i in range(6) for j in range(6) if i + j <= 5], -1)
    B = basis(xs, ys); w = np.ones(len(zs))
    for _ in range(15):
        c, *_ = np.linalg.lstsq(B * w[:, None], zs * w, rcond=None); r = zs - B @ c; s = 1.4826 * np.median(np.abs(r)) + 1e-4
        w = np.where(r > 0, 1 / (1 + (r / s) ** 4), 1 / (1 + (r / (3 * s)) ** 2))
    bad = region & (np.abs(x) < half) & (z > basis(x, y) @ c + lift)
    nv = len(me.vertices); V = np.empty(nv * 3); me.vertices.foreach_get('co', V); V = V.reshape(nv, 3)
    vr = (np.abs(V[:, 0]) < half) & (V[:, 1] > -0.48) & (V[:, 1] < 0.23) & (V[:, 2] > 0.05)   # only well inside the fit
    top = basis(V[vr, 0], V[vr, 1]) @ c + 0.002
    V[vr, 2] = np.minimum(V[vr, 2], top)                      # smaller bumps: iron them into the roof
    me.vertices.foreach_set('co', V.ravel()); me.update()
    bm = bmesh.new(); bm.from_mesh(me); bm.faces.ensure_lookup_table(); uvl = bm.loops.layers.uv.active
    bmesh.ops.delete(bm, geom=[bm.faces[i] for i in np.nonzero(bad)[0]], context='FACES')
    bmesh.ops.delete(bm, geom=[v for v in bm.verts if not v.link_faces], context='VERTS')
    rb = lambda v: abs(v.co.x) < half + 0.02 and -0.52 < v.co.y < 0.27 and v.co.z > 0.05
    bnd = [e for e in bm.edges if e.is_boundary and rb(e.verts[0]) and rb(e.verts[1])]
    new = bmesh.ops.holes_fill(bm, edges=bnd, sides=600)['faces']; ns = set(new)
    new = bmesh.ops.triangulate(bm, faces=new)['faces']
    for f in new:
        for l in f.loops:
            src = [ll for ll in l.vert.link_loops if ll.face not in ns]
            if src: l[uvl].uv = src[0][uvl].uv.copy()
    bm.to_mesh(me); bm.free(); me.update()
    return int(bad.sum()), len(new)


def mat_named(name, col, rough, met=0.0, emit=0.0):
    m = bpy.data.materials.get(name)
    if m: return m
    m = bpy.data.materials.new(name); m.use_nodes = True
    b = m.node_tree.nodes['Principled BSDF']; b.inputs['Base Color'].default_value = (*col, 1)
    b.inputs['Roughness'].default_value = rough; b.inputs['Metallic'].default_value = met
    if emit: b.inputs['Emission Color'].default_value = (*col, 1); b.inputs['Emission Strength'].default_value = emit
    return m


# parts that stick out: the combined method models only these and paints everything else
RAISED = {'headlight', 'hl_brow', 'hl_led', 'taillight', 'tail_inner', 'tail_ring', 'tail_rev',
          'projector', 'proj_lens', 'fog_ring', 'fog_lens', 'exhaust', 'exhaust_in'}


def build_parts(body, wheel, name='SM_CarCoupeB', body_mat=None, keep=None, wing=False, narrow=NARROW):
    """Copy the AI body, swap its wheels for kit wheels and add real parts. Returns (object, counts).
    Option 3: body_mat=None (one flat paint), keep=None (every part).
    Combined: body_mat = the painted-texture material (option 1's UVs are kept), keep = RAISED.
    wing: add our own rear wing (use it on a body cleaned by fix_trunk, which removes the AI's)."""
    fx = {}; exec(open(bpy.path.abspath('//ai_car_fix.py')).read(), fx)
    dg = bpy.context.evaluated_depsgraph_get()
    bvh = BVHTree.FromObject(body, dg)
    old = bpy.data.objects.get(name)
    if old: bpy.data.objects.remove(old)
    me = body.data.copy(); me.name = name
    ob = bpy.data.objects.new(name, me); bpy.context.scene.collection.objects.link(ob)
    # materials: slot order is fixed so Unreal can map them
    mats = [body_mat or bpy.data.materials['MC_PaintWR'], bpy.data.materials['MC_Glass'], bpy.data.materials['MC_Trim'],
            mat_named('MC_Plastic', (0.016, 0.016, 0.017), 0.7), bpy.data.materials['MC_Chrome'],
            bpy.data.materials['MC_Headlight'], bpy.data.materials['MC_Taillight'],
            bpy.data.materials['MC_Tyre'], bpy.data.materials['MC_Rim'], bpy.data.materials['MC_Accent'],
            mat_named('MC_TailSmoke', (0.09, 0.005, 0.005), 0.08), mat_named('MC_Disc', (0.55, 0.55, 0.56), 0.35, 1.0)]
    src_mi = np.empty(len(me.polygons), np.int32); me.polygons.foreach_get('material_index', src_mi)
    trim_i = [m.name for m in body.data.materials].index('MC_Trim')      # the wing
    me.materials.clear()                                                  # NB: this resets every face to slot 0
    for m in mats: me.materials.append(m)
    idx = {m.name: i for i, m in enumerate(mats)}
    # remove the AI wheels (shape rule from ai_car_fix), paint the rest
    lab = fx['classify_parts'](ob)
    bm = bmesh.new(); bm.from_mesh(me); bm.faces.ensure_lookup_table()
    n = len(me.polygons); Cf = np.empty(n * 3); Nf = np.empty(n * 3)
    me.polygons.foreach_get('center', Cf); me.polygons.foreach_get('normal', Nf)
    tread = tread_mask(Cf.reshape(n, 3), Nf.reshape(n, 3)) & (lab == '')
    for f in bm.faces:                                   # wing blade black; its end plates (facing sideways) body colour
        f.material_index = idx['MC_Trim'] if (src_mi[f.index] == trim_i and abs(f.normal.x) < 0.6) else 0
    dead = [bm.faces[i] for i in np.nonzero((lab == 'tyre') | (lab == 'rim'))[0]]
    rubber = [bm.faces[i] for i in np.nonzero(tread)[0]]          # kept (no holes), painted tyre black below
    bmesh.ops.delete(bm, geom=dead, context='FACES')
    loose = [v for v in bm.verts if not v.link_faces]
    bmesh.ops.delete(bm, geom=loose, context='VERTS')
    for f in rubber: f.material_index = idx['MC_Tyre']
    counts = {}
    for nm, plane, ak, bk, a0, a1, lo, hi, look, mname, off in PARTS:
        if nm in ('ws_frame', 'side_frame', 'rg_frame'): continue     # body colour already
        if keep is not None and nm not in keep: continue
        sides = (1, -1) if (ak == 'ax' or bk == 'ax' or plane in ('side', 'flank')) else (1,)
        counts[nm] = sum(_grid_part(bm, bvh, idx[mname], plane, ak, bk, a0, a1, lo, hi, s, off) for s in sides)
    for nm, plane, ak, bk, ca, cb, rad, rin, look, mname, off, dome in CIRCLES:
        if keep is not None and nm not in keep: continue
        sides = (1, -1) if (ak == 'ax' or bk == 'ax') else (1,)
        counts[nm] = sum(_disc_part(bm, bvh, idx[mname], plane, ak, bk, ca, cb, rad, s, off, dome) for s in sides)
    if wing: counts['wing'] = build_wing(bm, idx['MC_Trim'], 0)
    if narrow != 1.0:                                    # body + parts + wing; the wheels stay put
        bmesh.ops.scale(bm, vec=(narrow, 1.0, 1.0), verts=bm.verts[:])
    # arch edge per axle, measured on the body before the liners go in
    arches = {yw: max((abs(v.co.x) for v in bm.verts if abs(v.co.y - yw) < 0.12 and WHEEL_Z - 0.05 < v.co.z < WHEEL_Z + 0.10), default=0.36)
              for yw in WHEEL_YS}
    counts['liners'] = _liners(bm, idx['MC_Plastic'], narrow=narrow)
    # kit wheels, scaled to the AI tyre size, spokes facing out
    wb = bmesh.new(); wb.from_mesh(wheel.data)
    sc = TYRE_R / 0.135
    remap = {i: idx[m.name] for i, m in enumerate(wheel.data.materials)}
    half_w = 0.054 * sc                                  # kit wheel half-width at this scale
    for yw in WHEEL_YS:
        # sit each wheel's outer face 4 mm inside the arch edge (the real car's wheels are nearly flush)
        wx = min(0.305, arches[yw] - half_w - 0.004); counts['wheel_x_%.2f' % yw] = round(wx, 4)
        for s in (1, -1):
            # left side is a mirror image, so the caliper sits at the front on both sides
            sy = 1 if yw < 0 else -1                     # rear calipers sit behind the hub (rear photo)
            M = Matrix.Translation((s * wx, yw, WHEEL_Z)) @ Matrix.Diagonal((s * sc, sy * sc, sc, 1))
            cp = wb.copy(); bmesh.ops.transform(cp, matrix=M, verts=cp.verts)
            if s * sy < 0: bmesh.ops.reverse_faces(cp, faces=cp.faces[:])
            for f in cp.faces: f.material_index = remap[f.material_index]
            tmp = bpy.data.meshes.new('tmpw'); cp.to_mesh(tmp); cp.free()
            bm.from_mesh(tmp); bpy.data.meshes.remove(tmp)
    wb.free()
    bm.to_mesh(me); bm.free()
    for p in me.polygons: p.use_smooth = True
    fl = me.attributes.get('flat')
    if fl:                                               # wing: hard edges (boxes looked like blobs smoothed)
        for p, a in zip(me.polygons, fl.data):
            if a.value: p.use_smooth = False
        me.attributes.remove(fl)
    sn = me.attributes.get('smooth_n')
    if sn:                                               # smooth_body's shading normals, re-applied last
        V = np.empty(len(me.vertices) * 3, np.float32); sn.data.foreach_get('vector', V); V = V.reshape(-1, 3)
        lv = np.empty(len(me.loops), np.int64); me.loops.foreach_get('vertex_index', lv)
        L = V[lv]                                        # zero (new parts) = keep the automatic normal
        sm = np.empty(len(me.polygons), bool); me.polygons.foreach_get('use_smooth', sm)
        lt = np.empty(len(me.polygons), np.int64); me.polygons.foreach_get('loop_total', lt)
        L[~np.repeat(sm, lt)] = 0
        me.attributes.remove(sn)
        me.normals_split_custom_set([tuple(n) for n in L])
    return ob, counts
