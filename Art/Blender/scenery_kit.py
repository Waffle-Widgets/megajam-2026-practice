"""Procedural scenery kit for Sundown Frogger.

Run inside Blender (Text Editor or the Blender MCP): build_all() makes every model below,
laid out in a row for previewing. export_all(folder) writes one FBX per model.

Every model sits on the ground at its origin (z = 0) and is sized to match the
basic-shape version it replaces in Unreal. Blender X stays Unreal X; Blender +Y becomes
Unreal -Y. Material slot names are listed per model; Unreal maps them to our MIs.
"""
import bpy, bmesh, math, random
from mathutils import Vector, Matrix, noise

TAU = 2 * math.pi


# ------------------------------------------------------------------ helpers
def slot_mats(names):
    mats = []
    for n in names:
        m = bpy.data.materials.get('MS_' + n) or bpy.data.materials.new('MS_' + n)
        m.use_nodes = True
        mats.append(m)
    return mats


def make_object(name, slots, bm, smooth_angle=40, flat=False):
    old = bpy.data.objects.get(name)
    if old:
        me = old.data; bpy.data.objects.remove(old); bpy.data.meshes.remove(me)
    me = bpy.data.meshes.new(name)
    for m in slot_mats(slots):          # slots before faces, or indices clamp to 0
        me.materials.append(m)
    bmesh.ops.recalc_face_normals(bm, faces=[f for f in bm.faces])
    bm.to_mesh(me); bm.free()
    ob = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(ob)
    bpy.context.view_layer.update()     # drop stale entries left by the object we just replaced
    for o in bpy.context.view_layer.objects:
        if o: o.select_set(False)
    ob.select_set(True); bpy.context.view_layer.objects.active = ob
    if flat:
        for p in me.polygons: p.use_smooth = False
    else:
        bpy.ops.object.shade_smooth_by_angle(angle=math.radians(smooth_angle))
        for mod in list(ob.modifiers): bpy.ops.object.modifier_apply(modifier=mod.name)
    bpy.ops.object.mode_set(mode='EDIT'); bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.uv.smart_project(angle_limit=math.radians(60), island_margin=0.01)
    bpy.ops.object.mode_set(mode='OBJECT')
    return ob


def tag(bm, before, mat):
    for f in set(bm.faces) - before:
        f.material_index = mat


def tube(bm, path, radii, seg=12, mat=0, cap_start=True, cap_end=True, ribs=0, rib_depth=0.0):
    """Sweep a circle along a list of points. radii: one radius per point."""
    before = set(bm.faces)
    rings = []
    for i, p in enumerate(path):
        p = Vector(p)
        d = (Vector(path[min(i + 1, len(path) - 1)]) - Vector(path[max(i - 1, 0)])).normalized()
        up = Vector((0, 0, 1)) if abs(d.z) < 0.95 else Vector((1, 0, 0))
        a = d.cross(up).normalized(); b = d.cross(a).normalized()
        ring = []
        for k in range(seg):
            t = TAU * k / seg
            r = radii[i] * (1 - rib_depth * (0.5 - 0.5 * math.cos(ribs * t))) if ribs else radii[i]
            ring.append(bm.verts.new(p + (a * math.cos(t) + b * math.sin(t)) * r))
        rings.append(ring)
    for r0, r1 in zip(rings, rings[1:]):
        for k in range(seg):
            j = (k + 1) % seg
            bm.faces.new((r0[k], r0[j], r1[j], r1[k]))
    if cap_start: bm.faces.new(list(reversed(rings[0])))
    if cap_end: bm.faces.new(rings[-1])
    tag(bm, before, mat)
    return rings


def lathe(bm, prof, seg=24, mat=0, centre=(0, 0, 0)):
    """Revolve [(radius, z)] around Z; closes the top/bottom when radius is 0."""
    before = set(bm.faces)
    c = Vector(centre)
    rows = [[bm.verts.new(c + Vector((r * math.cos(TAU * k / seg), r * math.sin(TAU * k / seg), z))) for k in range(seg)] for r, z in prof]
    for a, b in zip(rows, rows[1:]):
        for k in range(seg):
            j = (k + 1) % seg
            bm.faces.new((a[k], a[j], b[j], b[k]))
    bm.faces.new(list(reversed(rows[0])))
    bm.faces.new(rows[-1])
    bmesh.ops.remove_doubles(bm, verts=[v for row in rows for v in row], dist=1e-5)
    tag(bm, before, mat)


def blob(bm, centre, radius, squash=(1, 1, 1), lump=0.25, seed=0, subdiv=2, mat=0, flat_bottom=None):
    """Lumpy icosphere: the building block for leaves, bushes and rocks."""
    before = set(bm.faces)
    res = bmesh.ops.create_icosphere(bm, subdivisions=subdiv, radius=1.0)
    off = Vector((seed * 7.31, seed * 3.17, seed * 1.93))
    for v in res['verts']:
        n = v.co.normalized()
        d = 1 + lump * noise.noise(n * 1.8 + off) + lump * 0.4 * noise.noise(n * 4.5 + off)
        v.co = Vector(centre) + Vector((n.x * squash[0], n.y * squash[1], n.z * squash[2])) * radius * d
        if flat_bottom is not None and v.co.z < flat_bottom:
            v.co.z = flat_bottom + (v.co.z - flat_bottom) * 0.15
    tag(bm, before, mat)


def mul(a, b):
    return Vector((a[0] * b[0], a[1] * b[1], a[2] * b[2]))


def box(bm, centre, size, mat=0, bevel=0.0):
    before = set(bm.faces)
    res = bmesh.ops.create_cube(bm, size=1.0)
    for v in res['verts']:
        v.co = Vector((v.co.x * size[0], v.co.y * size[1], v.co.z * size[2])) + Vector(centre)
    if bevel > 0:
        bmesh.ops.bevel(bm, geom=list({e for v in res['verts'] for e in v.link_edges}), offset=bevel, segments=2, affect='EDGES')
    tag(bm, before, mat)


# ------------------------------------------------------------------ trees
def trunk_with_branches(bm, rnd, height, r0, r1, branches, mat=0):
    bend = Vector((rnd.uniform(-0.08, 0.08), rnd.uniform(-0.08, 0.08), 0))
    path = [Vector((0, 0, -0.05)) + bend * (i / 6) ** 2 + Vector((0, 0, height * i / 6)) for i in range(7)]
    tube(bm, path, [r0 * 1.35] + [r0 + (r1 - r0) * i / 6 for i in range(1, 7)], seg=12, mat=mat, cap_start=False)
    tips = []
    for k in range(branches):
        a = TAU * k / branches + rnd.uniform(-0.4, 0.4)
        h = height * rnd.uniform(0.55, 0.9)
        base = Vector((0, 0, h)) + bend * (h / height) ** 2
        out = Vector((math.cos(a), math.sin(a), 0))
        L = rnd.uniform(0.45, 0.7)
        p = [base, base + out * L * 0.5 + Vector((0, 0, L * 0.45)), base + out * L + Vector((0, 0, L * 0.75))]
        tube(bm, p, [r1 * 0.9, r1 * 0.6, r1 * 0.35], seg=8, mat=mat, cap_start=False)
        tips.append(p[-1])
    return tips


def build_tree(name='SM_Tree', seed=3):
    """Broadleaf tree ~2.9 m: bark trunk with branches, lumpy leaf clusters. Slots: Bark, Leaves."""
    rnd = random.Random(seed); bm = bmesh.new()
    tips = trunk_with_branches(bm, rnd, 1.75, 0.13, 0.08, 4)
    centres = [Vector((0, 0, 2.05))] + [t + Vector((0, 0, 0.12)) for t in tips]
    centres += [Vector((rnd.uniform(-0.5, 0.5), rnd.uniform(-0.5, 0.5), rnd.uniform(1.75, 2.55))) for _ in range(5)]
    for i, c in enumerate(centres):
        r = 0.62 if i == 0 else rnd.uniform(0.36, 0.52)
        blob(bm, c, r, (1, 1, 0.82), 0.28, seed * 10 + i, 2, mat=1)
    return make_object(name, ['Bark', 'Leaves'], bm, 50)


def pine_tiers(bm, rnd, mat_needles=1, snow=False):
    """Stacked drooping needle skirts with jagged edges."""
    tiers = [(0.55, 0.78, 0.55), (0.95, 0.66, 0.5), (1.35, 0.54, 0.45), (1.72, 0.42, 0.42), (2.06, 0.30, 0.38), (2.36, 0.18, 0.34)]
    n = 18
    for ti, (z, R, h) in enumerate(tiers):
        before = set(bm.faces)
        top = bm.verts.new((0, 0, z + h))
        rows = []
        for ring, (fr, dz) in enumerate([(0.55, 0.42), (1.0, 0.0)]):
            row = []
            for k in range(n):
                a = TAU * k / n + ti * 0.37
                jag = 1.0 if k % 2 == 0 else 0.78
                rr = R * fr * (jag if ring == 1 else 1.0) * rnd.uniform(0.94, 1.06)
                droop = -0.06 if (ring == 1 and k % 2 == 0) else 0.0
                row.append(bm.verts.new((rr * math.cos(a), rr * math.sin(a), z + h * dz + droop)))
            rows.append(row)
        for k in range(n):
            j = (k + 1) % n
            bm.faces.new((top, rows[0][k], rows[0][j]))
            bm.faces.new((rows[0][k], rows[1][k], rows[1][j], rows[0][j]))
        # underside, slightly hollow so tiers look like skirts from below
        inner = bm.verts.new((0, 0, z + 0.05))
        for k in range(n):
            j = (k + 1) % n
            bm.faces.new((rows[1][j], rows[1][k], inner))
        tag(bm, before, mat_needles)
        if snow:
            for f in set(bm.faces) - before:
                c = f.calc_center_median()
                f.normal_update()
                if f.normal.z > 0.55 and c.z > z + h * 0.3 and noise.noise(c * 5) > 0.05:
                    f.material_index = 2


def build_pine(name='SM_Pine', seed=5, snow=False):
    """Pine ~2.7 m. Slots: Bark, Needles (+ Snow)."""
    rnd = random.Random(seed); bm = bmesh.new()
    tube(bm, [(0, 0, -0.05), (0, 0, 0.6), (0, 0, 2.3)], [0.12, 0.09, 0.04], seg=10, mat=0, cap_start=False)
    pine_tiers(bm, rnd, 1, snow)
    return make_object(name, ['Bark', 'Needles'] + (['Snow'] if snow else []), bm, 35)


def build_bush(name='SM_Bush', seed=11):
    """Low leafy clump ~1.4 m wide, 0.6 m tall. Slot: Leaves."""
    rnd = random.Random(seed); bm = bmesh.new()
    spots = [(0, 0, 0.22, 0.42), (0.32, 0.22, 0.16, 0.30), (-0.30, 0.18, 0.15, 0.30), (0.1, -0.3, 0.14, 0.28),
             (-0.2, -0.22, 0.12, 0.26), (0.05, 0.05, 0.42, 0.26), (0.42, -0.1, 0.1, 0.22)]
    for i, (x, y, z, r) in enumerate(spots):
        blob(bm, (x, y, z), r, (1, 1, 0.85), 0.3, seed + i, 2, 0, flat_bottom=0.0)
    return make_object(name, ['Leaves'], bm, 55)


def build_rock(name='SM_Rock', seed=21):
    """Weathered boulder plus a pebble. Slot: Rock."""
    bm = bmesh.new()
    blob(bm, (0, 0, 0.12), 0.5, (1.0, 0.8, 0.55), 0.22, seed, 3, 0, flat_bottom=0.0)
    blob(bm, (0.42, -0.22, 0.02), 0.13, (1, 0.8, 0.5), 0.25, seed + 5, 2, 0, flat_bottom=0.0)
    blob(bm, (-0.38, 0.30, 0.0), 0.08, (1, 0.9, 0.5), 0.25, seed + 9, 1, 0, flat_bottom=0.0)
    # chisel facets: quantise the surface a little
    for v in bm.verts:
        n = noise.noise(v.co * 3.0 + Vector((seed, 0, 0)))
        v.co += v.normal * 0.025 * round(n * 3) / 3
    return make_object(name, ['Rock'], bm, 28)


def build_reeds(name='SM_Reeds', seed=31):
    """Cluster of curved reed blades and cattails ~1.1 m. Slots: Reed, Cattail."""
    rnd = random.Random(seed); bm = bmesh.new()
    for k in range(14):
        a = rnd.uniform(0, TAU); r = rnd.uniform(0.0, 0.22)
        base = Vector((r * math.cos(a), r * math.sin(a), -0.02))
        lean = Vector((math.cos(a), math.sin(a), 0)) * rnd.uniform(0.05, 0.3)
        H = rnd.uniform(0.7, 1.15)
        path = [base + lean * (i / 5) ** 2 + Vector((0, 0, H * i / 5)) for i in range(6)]
        tube(bm, path, [0.012, 0.011, 0.009, 0.007, 0.004, 0.001], seg=4, mat=0, cap_start=False, cap_end=False)
    for k in range(5):
        a = TAU * k / 5 + rnd.uniform(-0.3, 0.3); r = rnd.uniform(0.05, 0.16)
        base = Vector((r * math.cos(a), r * math.sin(a), -0.02)); H = rnd.uniform(0.9, 1.2)
        tube(bm, [base, base + Vector((0, 0, H))], [0.008, 0.006], seg=6, mat=0, cap_start=False)
        top = base + Vector((0, 0, H - 0.22))
        tube(bm, [top, top + Vector((0, 0, 0.05)), top + Vector((0, 0, 0.14)), top + Vector((0, 0, 0.18))],
             [0.012, 0.024, 0.024, 0.012], seg=10, mat=1)
    return make_object(name, ['Reed', 'Cattail'], bm, 60)


def build_cactus(name='SM_Cactus', seed=41):
    """Ribbed saguaro ~2 m with two arms and a flower. Slots: Cactus, Flower."""
    bm = bmesh.new()
    def capsule(path, r):
        n = len(path)
        radii = [r] * n
        radii[-1] = r * 0.55
        tube(bm, path + [Vector(path[-1]) + Vector((0, 0, r * 0.45))], radii + [r * 0.12], seg=24, mat=0,
             cap_start=False, ribs=12, rib_depth=0.18)
    capsule([Vector((0, 0, -0.05)), Vector((0, 0, 0.9)), Vector((0, 0, 1.75))], 0.2)
    for side, h, out, up in [(-1, 0.85, 0.30, 0.55), (1, 0.62, 0.26, 0.42)]:
        y = side
        p = [Vector((0, 0, h)), Vector((0, y * out * 0.6, h + 0.02)), Vector((0, y * out, h + 0.12)),
             Vector((0, y * out, h + 0.3)), Vector((0, y * out, h + up))]
        capsule(p, 0.1)
    before = set(bm.faces)
    for k in range(6):
        a = TAU * k / 6
        box(bm, (0.05 * math.cos(a), 0.05 * math.sin(a), 1.92), (0.06, 0.06, 0.02), 1, 0.008)
    blob(bm, (0, 0, 1.94), 0.035, (1, 1, 0.7), 0.1, seed, 1, 1)
    return make_object(name, ['Cactus', 'Flower'], bm, 30)


# ------------------------------------------------------------------ street furniture
def build_hydrant(name='SM_Hydrant'):
    """Fire hydrant ~0.75 m. Slots: Paint, Metal."""
    bm = bmesh.new()
    lathe(bm, [(0.0, 0.0), (0.16, 0.0), (0.16, 0.04), (0.12, 0.05), (0.11, 0.08), (0.11, 0.48), (0.13, 0.50),
               (0.13, 0.54), (0.11, 0.56), (0.10, 0.64), (0.06, 0.70), (0.0, 0.71)], 24, 0)
    lathe(bm, [(0.0, 0.70), (0.035, 0.70), (0.035, 0.76), (0.0, 0.77)], 6, 1)   # top nut
    for a in (0, math.pi):
        d = Vector((math.cos(a), math.sin(a), 0))
        tube(bm, [d * 0.08 + Vector((0, 0, 0.36)), d * 0.17 + Vector((0, 0, 0.36))], [0.045, 0.045], 14, 0)
        tube(bm, [d * 0.17 + Vector((0, 0, 0.36)), d * 0.2 + Vector((0, 0, 0.36))], [0.05, 0.05], 6, 1)
    tube(bm, [Vector((0, 0.08, 0.32)), Vector((0, 0.2, 0.32))], [0.065, 0.065], 16, 0)
    tube(bm, [Vector((0, 0.2, 0.32)), Vector((0, 0.235, 0.32))], [0.07, 0.07], 6, 1)
    return make_object(name, ['Paint', 'Metal'], bm, 35)


def build_lamp(name='SM_Lamp'):
    """Street lamp: plinth, tapered post, curved arm to x = 0.74, head with glowing lens. Slots: Metal, Glow."""
    bm = bmesh.new()
    lathe(bm, [(0.0, 0.0), (0.16, 0.0), (0.16, 0.10), (0.12, 0.14), (0.08, 0.18), (0.0, 0.19)], 8, 0)
    tube(bm, [(0, 0, 0.15), (0, 0, 1.4), (0, 0, 2.62)], [0.06, 0.05, 0.04], 12, 0)
    arc = [Vector((0.42 * (1 - math.cos(t)), 0, 2.62 + 0.2 * math.sin(t))) for t in [i * math.pi / 2 / 6 for i in range(7)]]
    arc += [Vector((0.42 + 0.32 * i / 3, 0, 2.82 - 0.06 * i / 3)) for i in range(1, 4)]
    tube(bm, [Vector((0, 0, 2.58))] + arc, [0.035] * (len(arc) + 1), 10, 0)
    lathe(bm, [(0.0, 2.80), (0.05, 2.80), (0.20, 2.70), (0.22, 2.66), (0.0, 2.66)], 16, 0, centre=(0.74, 0, 0))
    lathe(bm, [(0.0, 2.58), (0.10, 2.60), (0.17, 2.66), (0.0, 2.665)], 16, 1, centre=(0.74, 0, 0))
    return make_object(name, ['Metal', 'Glow'], bm, 40)


def build_building(name='SM_Building', seed=51):
    """Small two-storey brick building, 1.8 m footprint. Slots: Brick, Concrete, Windows, Dark, Metal."""
    bm = bmesh.new()
    box(bm, (0, 0, 1.6), (1.8, 1.8, 3.2), 0)
    box(bm, (0, 0, 0.08), (1.86, 1.86, 0.16), 1)          # plinth
    box(bm, (0, 0, 1.68), (1.84, 1.84, 0.08), 1)           # floor band
    box(bm, (0, 0, 3.28), (1.92, 1.92, 0.16), 1, 0.01)     # cornice
    box(bm, (0, 0, 3.38), (1.86, 1.86, 0.06), 1)           # roof slab
    for sx, sy in ((1, 1), (1, -1), (-1, 1), (-1, -1)):
        box(bm, (sx * 0.88, sy * 0.88, 1.6), (0.1, 0.1, 3.2), 1)   # corner quoins
    for face in range(4):
        R = Matrix.Rotation(face * math.pi / 2, 3, 'Z')
        for fz in (1.05, 2.35):
            for wx in (-0.45, 0.45):
                if face in (0, 2) and fz < 1.5 and wx < 0:
                    continue                                  # door goes here
                c = R @ Vector((wx, -0.9, fz))
                s = R @ Vector((0.42, 0.05, 0.62)); s = Vector((abs(s.x), abs(s.y), abs(s.z)))
                box(bm, c, mul(s, (1.12, 1.6, 1.12)), 1)     # frame
                box(bm, c + R @ Vector((0, -0.02, 0)), s, 2)        # glass (glows at night)
                box(bm, c + R @ Vector((0, -0.03, -0.36)), Vector((abs((R @ Vector((0.5, 0.08, 0.05))).x), abs((R @ Vector((0.5, 0.08, 0.05))).y), 0.05)), 1)
        if face in (0, 2):
            c = R @ Vector((-0.45, -0.9, 0.55))
            s = R @ Vector((0.5, 0.06, 1.05)); s = Vector((abs(s.x), abs(s.y), abs(s.z)))
            box(bm, c, mul(s, (1.15, 1.2, 1.06)), 1)
            box(bm, c + R @ Vector((0, -0.02, 0)), s, 3)
            box(bm, c + R @ Vector((0, -0.2, -0.5)), Vector((abs((R @ Vector((0.7, 0.4, 0.06))).x), abs((R @ Vector((0.7, 0.4, 0.06))).y), 0.06)), 1)
    box(bm, (0.4, -0.3, 3.55), (0.4, 0.4, 0.3), 4, 0.02)    # roof AC unit
    box(bm, (-0.5, 0.45, 3.5), (0.12, 0.12, 0.2), 4)        # vent stack
    return make_object(name, ['Brick', 'Concrete', 'Windows', 'Dark', 'Metal'], bm, 30, flat=True)


# ------------------------------------------------------------------ train
def train_car(bm, y0, y1, nose0=False, nose1=False):
    """One carriage from y0 to y1 (Blender Y). Rounded body, window band, stripe, roof units, bogies."""
    BODY, STRIPE, WIN, DARK, HEAD, METAL = range(6)
    hw = 0.40
    # explicit cross-section (right half, bottom to top) so there are rows exactly at the stripe and windows
    half = [(0.34, 0.30), (0.38, 0.32), (0.40, 0.36), (0.40, 0.50), (0.40, 0.66), (0.40, 0.76), (0.40, 0.86),
            (0.40, 0.99), (0.40, 1.12), (0.395, 1.19), (0.37, 1.25), (0.32, 1.29), (0.2, 1.315), (0.0, 1.325)]
    sec = half + [(-x, z) for x, z in reversed(half[:-1])] + [(-x, 0.30) for x, z in half[:1]]
    sec = sec[:-1] + [(0.0, 0.29)]
    n_ar = len(sec)
    n_st = 40
    rings = []
    for i in range(n_st + 1):
        u = i / n_st; y = y0 + (y1 - y0) * u
        shrink_top = 0.0
        if nose0 and u < 0.12: shrink_top = (0.12 - u) / 0.12
        if nose1 and u > 0.88: shrink_top = (u - 0.88) / 0.12
        ring = []
        for x, z in sec:
            if z > 0.85:   # sloped cab nose
                z = 0.85 + (z - 0.85) * (1 - 0.55 * shrink_top ** 1.5)
            ring.append(bm.verts.new((x, y, z)))
        rings.append(ring)
    before = set(bm.faces)
    for i, (r0, r1) in enumerate(zip(rings, rings[1:])):
        u = (i + 0.5) / n_st
        for k in range(n_ar):
            j = (k + 1) % n_ar
            f = bm.faces.new((r0[k], r0[j], r1[j], r1[k]))
            z = (r0[k].co.z + r0[j].co.z) / 2
            side = abs(r0[k].co.x) > hw * 0.97 and abs(r0[j].co.x) > hw * 0.97
            nose = (nose0 and u < 0.13) or (nose1 and u > 0.87)
            if nose and z > 0.86 and not side:
                f.material_index = DARK           # windscreen
            elif side and 0.86 < z < 1.12 and 0.04 < u < 0.96 and not nose:
                f.material_index = WIN if i % 4 != 0 else BODY      # windows with pillars between
            elif side and 0.66 < z < 0.76:
                f.material_index = STRIPE
            elif z < 0.34:
                f.material_index = DARK
            else:
                f.material_index = BODY
    for ring, rev in ((rings[0], True), (rings[-1], False)):
        c = bm.verts.new((0, ring[0].co.y, 0.8))
        for k in range(n_ar):
            j = (k + 1) % n_ar
            f = bm.faces.new((ring[j], ring[k], c) if rev else (ring[k], ring[j], c)); f.material_index = BODY
    # headlights on the nose ends
    for yy, isnose in ((y0, nose0), (y1, nose1)):
        if isnose:
            for sx in (-0.24, 0.24):
                box(bm, (sx, yy + (0.01 if yy == y0 else -0.01), 0.55), (0.14, 0.04, 0.08), HEAD, 0.01)
    # bogies and wheels
    L = y1 - y0
    for by in (y0 + L * 0.18, y1 - L * 0.18):
        box(bm, (0, by, 0.22), (0.7, 1.0, 0.12), DARK, 0.02)
        for wy in (by - 0.3, by + 0.3):
            for sx in (-0.33, 0.33):
                tube(bm, [Vector((sx - 0.03, wy, 0.15)), Vector((sx + 0.03, wy, 0.15))], [0.15, 0.15], 16, METAL)
    # roof units
    for ry in (y0 + L * 0.3, y1 - L * 0.3):
        box(bm, (0, ry, 1.34), (0.45, 0.8, 0.1), METAL, 0.02)


def build_train(name='SM_Train'):
    """Three-car commuter train, 16 m long, cabs at both ends. Slots: Body, Stripe, Windows, Dark, Headlight, Metal."""
    bm = bmesh.new()
    cars = [(-8.0, -2.72, True, False), (-2.6, 2.6, False, False), (2.72, 8.0, False, True)]
    for y0, y1, n0, n1 in cars:
        train_car(bm, y0, y1, n0, n1)
    for gy in (-2.66, 2.66):   # gangways
        box(bm, (0, gy, 0.8), (0.6, 0.2, 0.9), 3)
    return make_object(name, ['Body', 'Stripe', 'Windows', 'Dark', 'Headlight', 'Metal'], bm, 30)


def build_crossing(name='SM_CrossingSign'):
    """Level-crossing post with a crossbuck and a lamp housing. Slots: Metal, White, Red, Dark."""
    bm = bmesh.new()
    tube(bm, [(0, 0, 0), (0, 0, 1.95)], [0.04, 0.035], 10, 0)
    lathe(bm, [(0.0, 0.0), (0.12, 0.0), (0.1, 0.08), (0.0, 0.09)], 8, 0)
    for ang in (math.radians(35), math.radians(-35)):
        R = Matrix.Rotation(ang, 3, 'X')
        for v_size, mat, off in (((0.02, 0.9, 0.16), 2, 0.0), ((0.022, 0.84, 0.11), 1, -0.004)):
            before = set(bm.faces)
            res = bmesh.ops.create_cube(bm, size=1.0)
            for v in res['verts']:
                v.co = R @ Vector((v.co.x * v_size[0], v.co.y * v_size[1], v.co.z * v_size[2])) + Vector((off - 0.05, 0, 1.55))
            tag(bm, before, mat)
    box(bm, (-0.1, 0, 2.0), (0.1, 0.42, 0.12), 3, 0.01)    # lamp bar under the flashing lamp
    return make_object(name, ['Metal', 'White', 'Red', 'Dark'], bm, 35)


# ------------------------------------------------------------------ river
def build_lilypad(name='SM_LilyPad', seed=61):
    """Lily pad ~0.86 m across with a notch, raised rim and radial veins. Slot: Pad."""
    bm = bmesh.new()
    rnd = random.Random(seed)
    n, rings = 48, [0.0, 0.12, 0.25, 0.36, 0.42, 0.43]
    notch = math.radians(14)
    verts = []
    for ri, r in enumerate(rings):
        row = []
        for k in range(n + 1):
            a = notch + (TAU - 2 * notch) * k / n
            vein = 0.003 * (1 if k % 4 == 0 else 0) * (ri > 0)
            z = 0.015 + (0.012 if ri == len(rings) - 1 else 0) + vein - 0.004 * (1 - r / 0.43)
            rr = r * (1 + 0.02 * math.sin(a * 5 + 1))
            row.append(bm.verts.new((rr * math.cos(a), rr * math.sin(a), z)))
        verts.append(row)
    for r0, r1 in zip(verts, verts[1:]):
        for k in range(n):
            bm.faces.new((r0[k], r0[k + 1], r1[k + 1], r1[k]))
    # thickness: copy the outline down and close the sides
    bot = [bm.verts.new((v.co.x, v.co.y, 0.0)) for v in verts[-1]]
    for k in range(n):
        bm.faces.new((verts[-1][k + 1], verts[-1][k], bot[k], bot[k + 1]))
    return make_object(name, ['Pad'], bm, 50)


BUILDERS = [build_tree, build_pine, lambda: build_pine('SM_PineSnow', 5, True), build_bush, build_rock, build_reeds,
            build_cactus, build_hydrant, build_lamp, build_building, build_train, build_crossing, build_lilypad]


def build_all():
    if getattr(bpy.context, 'object', None) and bpy.context.object.mode != 'OBJECT':
        bpy.ops.object.mode_set(mode='OBJECT')
    obs = [b() for b in BUILDERS]
    x = 0.0
    for o in obs:
        if o.name == 'SM_Train':
            o.location = (x + 1.5, 0, 0); x += 3.0
        else:
            o.location = (x, 0, 0); x += max(o.dimensions.x, 0.6) + 0.6
    return obs


def export_all(folder):
    import os
    os.makedirs(folder, exist_ok=True)
    for o in [o for o in bpy.data.objects if o.type == 'MESH' and o.name.startswith('SM_') and o.name in
              ('SM_Tree', 'SM_Pine', 'SM_PineSnow', 'SM_Bush', 'SM_Rock', 'SM_Reeds', 'SM_Cactus', 'SM_Hydrant',
               'SM_Lamp', 'SM_Building', 'SM_Train', 'SM_CrossingSign', 'SM_LilyPad')]:
        loc = tuple(o.location); o.location = (0, 0, 0)
        for s in bpy.context.view_layer.objects: s.select_set(False)
        o.select_set(True); bpy.context.view_layer.objects.active = o
        bpy.ops.export_scene.fbx(filepath=os.path.join(folder, o.name + '.fbx'), use_selection=True, object_types={'MESH'},
                                 apply_unit_scale=True, apply_scale_options='FBX_SCALE_NONE', axis_forward='-Z', axis_up='Y',
                                 mesh_smooth_type='FACE', add_leaf_bones=False, bake_anim=False, embed_textures=False)
        o.location = loc
