"""Fix-ups for an AI-generated (Hunyuan3D) car before it goes into the game.

Run inside Blender on the imported, painted mesh. Works in the mesh's local space as Hunyuan
exports it (OBJ, Y up): x = width, y = height, z = length with the front at -z.

- recolour(): push the body paint towards a target colour (WR Blue Pearl for our coupe),
  leaving black trim, glass and red lights alone.
- fill_regions(): repaint areas the photos never showed (the bonnet) with the body colour,
  and paint out badges, lettering and the number plate (the jam bans logos; no real plates).
- shrink_wing(): pull an over-sized rear wing down towards the boot lid and in to body width.
"""
import bpy, numpy as np


def texture_of(mat):
    for n in mat.node_tree.nodes:
        if n.type == 'TEX_IMAGE' and n.image and 'metallic' not in n.image.filepath and 'roughness' not in n.image.filepath:
            return n.image


def recolour(px, target=(0.013, 0.085, 0.56)):
    """px: HxWx4 linear. Scale blue-dominant pixels so their median matches the target."""
    rgb = px[..., :3]
    blue = np.clip((rgb[..., 2] - np.maximum(rgb[..., 0], rgb[..., 1]) - 0.04) / 0.10, 0, 1)   # 0 = not paint, 1 = paint
    blue *= np.clip((rgb[..., 2] - 0.10) / 0.10, 0, 1)            # dark tinted glass is not paint
    sel = blue > 0.9
    med = np.median(rgb[sel], axis=0) if sel.any() else np.array([0.01, 0.09, 0.36])
    gain = np.array(target) / np.maximum(med, 1e-3)
    gain = np.clip(gain, 0.4, 3.0)
    gain[0] = min(gain[0], 1.0)                                    # never add red: it turns purple reflections pink
    rgb[:] = rgb * (1 - blue[..., None]) + np.clip(rgb * gain, 0, 1) * blue[..., None]
    return np.array(target)


def raster_faces(me, faces, W, H):
    """Boolean HxW mask covering the UV triangles of the given faces."""
    uvl = me.uv_layers.active.data
    mask = np.zeros((H, W), bool)
    for p in faces:
        uvs = [uvl[li].uv[:] for li in p.loop_indices]
        for k in range(1, len(uvs) - 1):
            tri = np.array([uvs[0], uvs[k], uvs[k + 1]]) * [W, H]
            x0, y0 = np.floor(tri.min(0)).astype(int) - 1; x1, y1 = np.ceil(tri.max(0)).astype(int) + 1
            x0, y0 = max(x0, 0), max(y0, 0); x1, y1 = min(x1, W - 1), min(y1, H - 1)
            if x1 < x0 or y1 < y0: continue
            gx, gy = np.meshgrid(np.arange(x0, x1 + 1) + 0.5, np.arange(y0, y1 + 1) + 0.5)
            (ax, ay), (bx, by), (cx, cy) = tri
            d = (by - cy) * (ax - cx) + (cx - bx) * (ay - cy)
            if abs(d) < 1e-9: continue
            l1 = ((by - cy) * (gx - cx) + (cx - bx) * (gy - cy)) / d
            l2 = ((cy - ay) * (gx - cx) + (ax - cx) * (gy - cy)) / d
            inside = (l1 >= -0.02) & (l2 >= -0.02) & (1 - l1 - l2 >= -0.02)
            mask[y0:y1 + 1, x0:x1 + 1] |= inside
    return mask


def fill_regions(ob, px, body, front_z=None):
    me = ob.data; H, W = px.shape[:2]
    zs = np.array([v.co.z for v in me.vertices]); zmin, zmax = zs.min(), zs.max(); L = zmax - zmin
    hs = np.array([v.co.y for v in me.vertices]); hmin, hmax = hs.min(), hs.max(); Hh = hmax - hmin
    def rel_z(c): return (c.z - zmin) / L          # 0 front .. 1 rear
    def rel_h(c): return (c.y - hmin) / Hh         # 0 ground .. 1 roof
    bonnet, badges = [], []
    for p in me.polygons:
        c, n = p.center, p.normal; u = rel_z(c); h = rel_h(c)
        if n.y > 0.45 and 0.04 < u < 0.33 and abs(c.x) < 0.36 and not (u < 0.12 and abs(c.x) > 0.25):
            bonnet.append(p)                       # top of the bonnet: the photos never showed it clearly
        elif n.z < -0.5 and u < 0.06 and abs(c.x) < 0.09 and 0.25 < h < 0.6:
            badges.append(p)                       # front badge
        elif n.z > 0.5 and u > 0.9 and abs(c.x) < 0.22 and 0.25 < h < 0.75:
            badges.append(p)                       # boot lettering, badge and number plate
    rng = np.random.default_rng(3)
    m = raster_faces(me, bonnet, W, H)
    noise = rng.normal(1.0, 0.03, (m.sum(), 1))
    px[m, :3] = np.clip(body * noise, 0, 1)
    m2 = raster_faces(me, badges, W, H)
    rgb = px[..., :3]
    lum = rgb.mean(-1); bright = (lum > body.mean() * 1.6) | (rgb[..., 0] > rgb[..., 2])   # silver, white or red-ish marks
    paint = m2 & bright
    px[paint, :3] = np.clip(body * rng.normal(1.0, 0.03, (paint.sum(), 1)), 0, 1)
    return len(bonnet), len(badges), int(m.sum()), int(paint.sum())


def shrink_wing(ob, deck, deck_u=0.845, keep=0.30, narrow=0.84):
    """Pull everything above the boot lid (local height `deck`) at the back down towards it and in towards the centre."""
    me = ob.data
    zs = np.array([v.co.z for v in me.vertices]); zmin, zmax = zs.min(), zs.max(); L = zmax - zmin
    rear = (zs - zmin) / L > deck_u
    n = 0
    for v, r in zip(me.vertices, rear):
        if r and v.co.y > deck + 0.01:
            v.co.y = deck + (v.co.y - deck) * keep
            v.co.x *= narrow
            n += 1
    me.update()
    return n, float(deck)


def darken_glass(ob, px, zones, glass=(0.012, 0.016, 0.022)):
    """Turn blue-tinted pixels on window faces back into dark glass (e.g. a car-wash hose reflected in the photo).
    zones: list of functions face -> bool, in the object's local space."""
    me = ob.data; H, W = px.shape[:2]
    faces = [p for p in me.polygons if any(z(p) for z in zones)]
    m = raster_faces(me, faces, W, H)
    rgb = px[..., :3]
    tinted = (rgb[..., 2] > rgb[..., 0] + 0.03) & (rgb[..., 2] > 0.04)
    sel = m & tinted
    rng = np.random.default_rng(5)
    px[sel, :3] = np.clip(np.array(glass) * rng.normal(1.0, 0.08, (sel.sum(), 1)), 0, 1)
    return len(faces), int(sel.sum())


# ---------------------------------------------------------------- one-shot pipeline, in game space (front -Y, up Z, origin 30 cm above the road)
def face_mean_rgb(me, px, faces):
    """Mean texture colour under each face's first-loop UV region (cheap: samples the UV centroid)."""
    uvl = me.uv_layers.active.data; H, W = px.shape[:2]; out = {}
    for p in faces:
        u = sum(uvl[li].uv[0] for li in p.loop_indices) / p.loop_total
        v = sum(uvl[li].uv[1] for li in p.loop_indices) / p.loop_total
        out[p.index] = px[min(H - 1, int(v * H)), min(W - 1, int(u * W)), :3]
    return out


def to_game_space(ob, length=1.74, origin_height=0.30):
    """Hunyuan OBJ (Y up, front -Z) -> Z up, front -Y, scaled to `length`, origin `origin_height` above the road."""
    import math
    ob.location = (0, 0, 0); ob.rotation_euler = (math.pi / 2, 0, math.pi)
    for x in bpy.context.view_layer.objects: x.select_set(False)
    ob.select_set(True); bpy.context.view_layer.objects.active = ob
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    co = np.empty(len(ob.data.vertices) * 3); ob.data.vertices.foreach_get('co', co); co = co.reshape(-1, 3)
    co *= length / (co[:, 1].max() - co[:, 1].min())
    co[:, 0] -= (co[:, 0].max() + co[:, 0].min()) / 2; co[:, 1] -= (co[:, 1].max() + co[:, 1].min()) / 2
    co[:, 2] -= co[:, 2].min() + origin_height
    ob.data.vertices.foreach_set('co', co.ravel()); ob.data.update()


def game_space_regions(ob, px, body):
    """Bonnet fill, badge/plate paint-out and dark-glass clean-up, in game space."""
    me = ob.data; H, W = px.shape[:2]
    co = np.array([v.co[:] for v in me.vertices])
    ymin, ymax = co[:, 1].min(), co[:, 1].max(); zmin, zmax = co[:, 2].min(), co[:, 2].max()
    hw = (co[:, 0].max() - co[:, 0].min()) / 2
    U = lambda c: (c.y - ymin) / (ymax - ymin)          # 0 front .. 1 rear
    Hh = lambda c: (c.z - zmin) / (zmax - zmin)         # 0 road .. 1 roof
    means = face_mean_rgb(me, px, me.polygons)
    bonnet, badges, glass = [], [], []
    for p in me.polygons:
        c, n = p.center, p.normal; u = U(c); h = Hh(c); m = means[p.index]
        if n.z > 0.45 and 0.04 < u < 0.33 and abs(c.x) < 0.86 * hw and not (u < 0.12 and abs(c.x) > 0.6 * hw):
            bonnet.append(p)
        elif n.y < -0.5 and u < 0.06 and abs(c.x) < 0.2 * hw and 0.25 < h < 0.6:
            badges.append(p)
        elif n.y > 0.5 and u > 0.9 and abs(c.x) < 0.5 * hw and 0.25 < h < 0.75:
            badges.append(p)
        if h > 0.55 and abs(n.z) > 0.3 and m.mean() < 0.07:   # mostly dark: window glass
            glass.append(p)
    rng = np.random.default_rng(3)
    mb = raster_faces(me, bonnet, W, H)
    px[mb, :3] = np.clip(body * rng.normal(1.0, 0.03, (mb.sum(), 1)), 0, 1)
    m2 = raster_faces(me, badges, W, H); rgb = px[..., :3]
    paint = m2 & ((rgb.mean(-1) > body.mean() * 1.6) | (rgb[..., 0] > rgb[..., 2]))
    px[paint, :3] = np.clip(body * rng.normal(1.0, 0.03, (paint.sum(), 1)), 0, 1)
    mg = raster_faces(me, glass, W, H) & ~mb
    tinted = mg & (rgb[..., 2] > rgb[..., 0] + 0.03) & (rgb[..., 2] > 0.04)
    px[tinted, :3] = np.clip(np.array([0.012, 0.016, 0.022]) * rng.normal(1.0, 0.08, (tinted.sum(), 1)), 0, 1)
    return dict(bonnet=len(bonnet), badges=len(badges), glass=len(glass), glass_px=int(tinted.sum()))


def cut_wing(ob, lid_u=0.80, margin=0.012):
    """Delete the AI's rear wing: everything at the back standing clear above the boot lid, plus end plates past the body sides."""
    import bmesh
    me = ob.data; co = np.array([v.co[:] for v in me.vertices])
    ymin, ymax = co[:, 1].min(), co[:, 1].max(); U = (co[:, 1] - ymin) / (ymax - ymin)
    band = (U > lid_u - 0.03) & (U < lid_u) & (np.abs(co[:, 0]) < 0.12)
    lid = float(np.percentile(co[band, 2], 95))
    body_hw = float(np.percentile(np.abs(co[(U > 0.6) & (co[:, 2] < lid - 0.08), 0]), 99.5))
    bm = bmesh.new(); bm.from_mesh(me)
    def w(v):
        u = (v.co.y - ymin) / (ymax - ymin)
        return u > lid_u and (v.co.z > lid + margin or (abs(v.co.x) > body_hw + 0.004 and v.co.z > lid - 0.10))
    dead = [f for f in bm.faces if all(w(v) for v in f.verts)]
    bmesh.ops.delete(bm, geom=dead, context='FACES')
    bmesh.ops.delete(bm, geom=[v for v in bm.verts if not v.link_faces], context='VERTS')
    bm.to_mesh(me); bm.free(); me.update()
    return dict(lid=lid, body_hw=body_hw, faces=len(dead))


# ---------------------------------------------------------------- shape-based parts (game space; numbers measured on the BRZ coupe)
def classify_parts(ob, wheel_y=(-0.505, 0.512), wheel_z=-0.178, tyre_r=0.127, rim_r=0.092):
    """Per-face part labels from the car's shape: 'glass', 'tyre', 'rim', 'liner' or ''.
    Wheel centres/radius measured from the dark rubber in the AI texture (tyre top sits at z -0.065)."""
    me = ob.data; n = len(me.polygons)
    cen = np.empty(n * 3); me.polygons.foreach_get('center', cen); cen = cen.reshape(-1, 3)
    nrm = np.empty(n * 3); me.polygons.foreach_get('normal', nrm); nrm = nrm.reshape(-1, 3)
    x, y, z = cen.T; nx, ny, nz = nrm.T; ax = np.abs(x)
    lab = np.array([''] * n, dtype=object)
    belt = np.where(y < 0.25, 0.04, 0.04 + (y - 0.25) / 0.30 * 0.08)          # side window sill rises towards the C pillar
    windscreen = (y > -0.39) & (y < -0.10) & (z > 0.06) & (ax < 0.30) & (nz > 0.3) & (ny < -0.1)
    rear = (y > 0.28) & (y < 0.64) & (z > 0.12) & (ax < 0.30) & (nz > 0.3) & (ny > 0.1)
    side = (y > -0.32) & (y < 0.58) & (z > belt) & (z < 0.205) & (ax < 0.36) & (ax > 0.18) & (nz < 0.75)
    lab[windscreen | rear | side] = 'glass'
    for yw in wheel_y:
        r = np.hypot(y - yw, z - wheel_z)
        wheel = (r < tyre_r) & (ax > 0.22)
        wheel |= (z < wheel_z) & (r < tyre_r + 0.035) & (np.abs(y - yw) < 0.125) & (ax > 0.20)   # tyre bulge at the bottom
        lab[wheel & (r > rim_r)] = 'tyre'
        lab[wheel & (r <= rim_r)] = 'rim'
        liner = (r >= tyre_r) & (r < tyre_r + 0.05) & (ax > 0.15) & (ax < 0.335) & (z > wheel_z)
        lab[liner & (lab == '')] = 'liner'
    return lab


def paint_parts(ob, lab, px, rough):
    """Write glass / rubber / gloss-black rim / black liner into the base-colour and roughness textures."""
    me = ob.data; H, W = px.shape[:2]; rng = np.random.default_rng(11)
    polys = me.polygons
    def mask(name): return raster_faces(me, [polys[i] for i in np.nonzero(lab == name)[0]], W, H)
    g = mask('glass'); t = mask('tyre'); r = mask('rim'); l = mask('liner')
    px[g, :3] = np.clip(np.array([0.010, 0.013, 0.018]) * rng.normal(1, 0.06, (g.sum(), 1)), 0, 1); rough[g] = 0.04
    px[t, :3] = np.clip(np.array([0.020, 0.020, 0.022]) * rng.normal(1, 0.08, (t.sum(), 1)), 0, 1); rough[t] = 0.85
    rgb = px[..., :3]; red = (rgb[..., 0] > rgb[..., 2] * 1.6) & (rgb[..., 0] > 0.12)
    rr = r & ~red
    lum = rgb[rr].mean(-1, keepdims=True)
    px[rr, :3] = np.clip(lum * 0.35 + 0.006, 0, 0.08); rough[rr] = 0.18                          # gloss black, keeps the spoke shading
    px[l, :3] = np.clip(np.array([0.012, 0.012, 0.013]) * rng.normal(1, 0.08, (l.sum(), 1)), 0, 1); rough[l] = 0.9
    return dict(glass=int(g.sum()), tyre=int(t.sum()), rim=int(r.sum()), liner=int(l.sum()))


# ---------------------------------------------------------------- front details from the owner's front photos
def front_parts(ob, lab):
    """Add front labels in place: lower grille, fog-light openings, headlights (lens / chrome projector / silver rim),
    black cowl under the windscreen and the small fender vent. Numbers are game-space metres (front = -Y)."""
    me = ob.data; n = len(me.polygons)
    cen = np.empty(n * 3); me.polygons.foreach_get('center', cen); x, y, z = cen.reshape(-1, 3).T
    nrm = np.empty(n * 3); me.polygons.foreach_get('normal', nrm); nx, ny, nz = nrm.reshape(-1, 3).T
    ax = np.abs(x); free = lab == ''
    front = (y < -0.68) & (ny < -0.3)
    # trapezoid grille: wide at the top (just under the nose), narrower at the bottom, above the blue lip
    half = 0.21 + (z + 0.215) / 0.10 * 0.04
    grille = front & (z > -0.215) & (z < -0.115) & (ax < half)
    fog = front & (ax > half + 0.025) & (ax < 0.355) & (z > -0.205) & (z < -0.125)
    # headlights: swept band at the upper corners, wrapping back along the fender
    zl = -0.10 + (ax - 0.12) * 0.10                    # measured on the head-on photo: inner tip low by the badge,
    zh = -0.07 + (ax - 0.12) * 0.25                   # outer end higher, up to the bonnet shut line
    head = (y < -0.62) & (ax > 0.12) & (ax < 0.40) & (z > zl) & (z < zh) & ((ny < -0.45) | ((ax > 0.33) & (ny < -0.1)))
    chrome = head & (np.hypot(ax - 0.27, z - (zl + zh) / 2) < 0.019)
    rim = head & ~chrome & (z > zh - 0.008)
    cowl = (y > -0.41) & (y < -0.355) & (z > 0.035) & (ax < 0.33) & (nz > 0.3)
    vent = (ax > 0.34) & (y > -0.33) & (y < -0.27) & (z > -0.05) & (z < 0.035) & (np.abs(nx) > 0.6)
    for name, m in (('grille', grille), ('fog', fog), ('head', head & ~chrome & ~rim), ('head_chrome', chrome),
                    ('head_rim', rim), ('cowl', cowl), ('vent', vent)):
        lab[m & free] = name
    return lab


FRONT_COLOURS = {            # base colour, roughness, noise
    'grille': ((0.014, 0.014, 0.015), 0.55, 0.15),
    'fog': ((0.012, 0.012, 0.013), 0.6, 0.10),
    'head': ((0.035, 0.037, 0.042), 0.08, 0.10),
    'head_chrome': ((0.35, 0.36, 0.38), 0.12, 0.05),
    'head_rim': ((0.22, 0.23, 0.25), 0.15, 0.05),
    'cowl': ((0.013, 0.013, 0.014), 0.7, 0.08),
    'vent': ((0.012, 0.012, 0.013), 0.6, 0.08),
}


def paint_front(ob, lab, px, rough):
    me = ob.data; H, W = px.shape[:2]; rng = np.random.default_rng(5); out = {}
    for name, (c, ro, noise) in FRONT_COLOURS.items():
        idx = np.nonzero(lab == name)[0]
        if not len(idx): out[name] = 0; continue
        m = raster_faces(me, [me.polygons[i] for i in idx], W, H)
        px[m, :3] = np.clip(np.array(c) * rng.normal(1, noise, (m.sum(), 1)), 0, 1); rough[m] = ro
        out[name] = int(len(idx))
    return out
