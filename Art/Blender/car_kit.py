"""Procedural car kit for Sundown Frogger: SM_CarHatch, SM_CarPickup, SM_CarTruck and SM_CarWheel.

Run inside Blender (Text Editor or the Blender MCP). Bodies are lofted from side/top profiles,
then get wheel wells, bumpers, light lenses, grille and mirrors.

Conventions (match BP_Car in Unreal):
- Front of the car is Blender -Y, which becomes Unreal +Y with our FBX settings.
- Body origin sits 30 cm above the ground (BP_Car places CarBody at z = 30).
- Wheel origin is the wheel centre; the wheel spins around X.
- Material slots: 0 Paint, 1 Glass, 2 Trim, 3 Chrome, 4 Headlight, 5 Taillight, 6 Cargo.
"""
import bpy, bmesh, math
from mathutils import Vector, Matrix

SLOTS = ['Paint', 'Glass', 'Trim', 'Chrome', 'Headlight', 'Taillight', 'Cargo']
PAINT, GLASS, TRIM, CHROME, HEAD, TAIL, CARGO = range(7)
BODY_Z = 0.30          # body origin height above ground
WHEEL_R = 0.15


def smooth_interp(keys, u):
    """keys: [(u, value)], smoothstep between neighbours."""
    if u <= keys[0][0]: return keys[0][1]
    for (u0, v0), (u1, v1) in zip(keys, keys[1:]):
        if u <= u1:
            t = (u - u0) / (u1 - u0)
            t = t * t * (3 - 2 * t)
            return v0 + (v1 - v0) * t
    return keys[-1][1]


def get_mats():
    mats = []
    cols = {'Paint': (0.6, 0.05, 0.03, 1), 'Glass': (0.01, 0.015, 0.02, 1), 'Trim': (0.02, 0.02, 0.022, 1),
            'Chrome': (0.8, 0.8, 0.8, 1), 'Headlight': (1, 0.95, 0.8, 1), 'Taillight': (0.8, 0.02, 0.01, 1),
            'Cargo': (0.75, 0.74, 0.7, 1)}
    for s in SLOTS:
        name = 'MC_' + s
        m = bpy.data.materials.get(name) or bpy.data.materials.new(name)
        m.use_nodes = True
        b = m.node_tree.nodes.get('Principled BSDF')
        if b:
            b.inputs['Base Color'].default_value = cols[s]
            b.inputs['Roughness'].default_value = {'Glass': 0.05, 'Chrome': 0.15, 'Paint': 0.3}.get(s, 0.6)
            b.inputs['Metallic'].default_value = 1.0 if s == 'Chrome' else 0.0
            if s in ('Headlight', 'Taillight'):
                b.inputs['Emission Color'].default_value = cols[s]; b.inputs['Emission Strength'].default_value = 2.0
        mats.append(m)
    return mats


def new_object(name, bm):
    old = bpy.data.objects.get(name)
    if old:
        me = old.data; bpy.data.objects.remove(old); bpy.data.meshes.remove(me)
    me = bpy.data.meshes.new(name)
    for m in get_mats():            # slots BEFORE writing faces, or indices clamp to 0
        me.materials.append(m)
    bm.to_mesh(me); bm.free()
    ob = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(ob)
    return ob


# ---------------------------------------------------------------- body loft
def loft(bm, P, n_st=64, n_ar=56, expo=5.0):
    """Closed lofted shell. P holds profile keys over u = 0 (front) .. 1 (rear)."""
    L = P['length']
    rings = []
    for i in range(n_st + 1):
        u = i / n_st
        # bunch stations near the ends for rounder noses
        u = 0.5 - 0.5 * math.cos(math.pi * u) if P.get('cosine', True) else u
        y = -L / 2 + u * L
        zt = smooth_interp(P['top'], u); zb = smooth_interp(P['bottom'], u)
        hw = smooth_interp(P['half_width'], u); belt = smooth_interp(P['belt'], u)
        tk = P.get('tumblehome', 0.22)
        zm, hz = (zt + zb) / 2, (zt - zb) / 2
        ring = []
        for k in range(n_ar):
            a = 2 * math.pi * k / n_ar
            c, s = math.cos(a), math.sin(a)
            x = hw * math.copysign(abs(c) ** (2 / expo), c)
            z = zm + hz * math.copysign(abs(s) ** (2 / expo), s)
            if z > belt and zt > belt + 0.01:
                x *= 1 - tk * (z - belt) / (zt - belt)
            ring.append(bm.verts.new((x, y, z - BODY_Z)))
        rings.append(ring)
    ang = bm.faces.layers.float.new('ang')     # loft angle of each face: pi/2 = top centre
    stu = bm.faces.layers.float.new('stu')     # position along the car, 0 front .. 1 rear
    us = [0.5 - 0.5 * math.cos(math.pi * i / n_st) if P.get('cosine', True) else i / n_st for i in range(n_st + 1)]
    for i, (r0, r1) in enumerate(zip(rings, rings[1:])):
        for k in range(n_ar):
            j = (k + 1) % n_ar
            f = bm.faces.new((r0[k], r0[j], r1[j], r1[k]))
            f[ang] = 2 * math.pi * (k + 0.5) / n_ar
            f[stu] = (us[i] + us[i + 1]) / 2
    for ring, rev in ((rings[0], True), (rings[-1], False)):
        c = bm.verts.new((sum(v.co.x for v in ring) / n_ar, ring[0].co.y, sum(v.co.z for v in ring) / n_ar))
        for k in range(n_ar):
            j = (k + 1) % n_ar
            bm.faces.new((ring[j], ring[k], c) if rev else (ring[k], ring[j], c))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)


def paint_regions(bm, P):
    """Assign glass / trim / paint by where each face sits on the body."""
    """Uses the loft's own angle/station per face, so every border follows a loft line (no jaggies)."""
    ang = bm.faces.layers.float['ang']; stu = bm.faces.layers.float['stu']
    top_band = P.get('top_band', 0.95)          # half-angle of the 'roof / windscreen' band around the top
    for f in bm.faces:
        a = f[ang]; u = f[stu]
        z = f.calc_center_median().z + BODY_Z
        zt = smooth_interp(P['top'], u); belt = smooth_interp(P['belt'], u)
        f.material_index = PAINT
        if u <= 0.0:            # end caps
            continue
        if z < P.get('sill', 0.22):
            f.material_index = TRIM; continue
        if 'chassis_from' in P and u > P['chassis_from']:
            f.material_index = TRIM; continue
        if 'bed' in P and P['bed'][0] <= u <= P['bed'][1]:
            continue
        if not (0.0 < a < math.pi) or z < belt + 0.01 or zt < belt + 0.06:
            continue
        top = abs(a - math.pi / 2) < top_band
        in_roof = P['roof'][0] <= u <= P['roof'][1]
        if in_roof:
            if top: continue                                            # roof panel
            if any(abs(u - b) < 0.02 for b in P.get('b_pillars', [])):
                f.material_index = TRIM                                 # B pillar
            else:
                f.material_index = GLASS                                # side windows
        else:
            f.material_index = GLASS if top else PAINT                  # windscreen / rear glass, A & C pillars


def wheel_wells(ob, P):
    """Cut a wheel well into each corner with an exact boolean (keeps the shell closed)."""
    L = P['length']
    cutters = []
    for u in P['axles']:
        y = -L / 2 + u * L
        for side in (-1, 1):
            bpy.ops.mesh.primitive_cylinder_add(vertices=40, radius=WHEEL_R + 0.035, depth=0.30,
                                                location=(side * (P['wheel_x'] + 0.12), y, WHEEL_R - BODY_Z),
                                                rotation=(0, math.pi / 2, 0))
            cutters.append(bpy.context.active_object)
    for cu in cutters:
        mod = ob.modifiers.new('well', 'BOOLEAN'); mod.operation = 'DIFFERENCE'; mod.solver = 'EXACT'; mod.object = cu
        bpy.context.view_layer.objects.active = ob
        bpy.ops.object.modifier_apply(modifier=mod.name)
        bpy.data.objects.remove(cu)
    # faces inside the wells -> trim
    me = ob.data
    for p in me.polygons:
        c = p.center
        for u in P['axles']:
            y = -L / 2 + u * L
            # only the well's inner walls: near the wheel AND set back from the outer body side
            if math.hypot(c.y - y, c.z - (WHEEL_R - BODY_Z)) < WHEEL_R + 0.04 and \
                    abs(c.x) < smooth_interp(P['half_width'], (c.y + L / 2) / L) - 0.012 and abs(p.normal.x) < 0.7:
                p.material_index = TRIM


def rounded_box(bm, centre, size, mat, bevel=0.012):
    res = bmesh.ops.create_cube(bm, size=1.0)
    vs = res['verts']
    for v in vs:
        v.co = Vector((v.co.x * size[0], v.co.y * size[1], v.co.z * size[2])) + Vector(centre)
    edges = list({e for v in vs for e in v.link_edges})
    if bevel > 0:
        bmesh.ops.bevel(bm, geom=edges, offset=bevel, segments=2, affect='EDGES', profile=0.5)


def add_part(bm, centre, size, mat, bevel=0.012):
    before = set(bm.faces)
    rounded_box(bm, centre, size, mat, bevel)
    for f in set(bm.faces) - before:
        f.material_index = mat


def surface_y(ob, x, z, front=True):
    """Where the body surface is at (x, z), shooting a ray along Y from in front of / behind the car."""
    o = Vector((x, -5.0 if front else 5.0, z - BODY_Z))
    d = Vector((0, 1 if front else -1, 0))
    hit, loc, nrm, idx = ob.ray_cast(o, d)
    return loc.y if hit else None


def details(ob, P):
    """Bumpers, light lenses, grille, mirrors, door handles."""
    bm = bmesh.new(); bm.from_mesh(ob.data)
    L = P['length']
    hw = smooth_interp(P['half_width'], 0.5)
    yf = surface_y(ob, 0.0, 0.26) or -L / 2
    yr = surface_y(ob, 0.0, 0.26, front=False) or L / 2
    add_part(bm, (0, yf - 0.005, 0.25 - BODY_Z), (hw * 2 + 0.01, 0.07, 0.09), TRIM, 0.02)
    add_part(bm, (0, yr + 0.005, 0.25 - BODY_Z), (hw * 2 + 0.01, 0.07, 0.09), TRIM, 0.02)
    for side in (-1, 1):
        hx, hz = P['head']
        y = surface_y(ob, side * hx, hz)
        if y is not None:
            add_part(bm, (side * hx, y + 0.004, hz - BODY_Z), (0.13, 0.03, 0.055), HEAD, 0.01)
        tx, tz = P['tail']
        y = surface_y(ob, side * tx, tz, front=False)
        if y is not None:
            add_part(bm, (side * tx, y - 0.004, tz - BODY_Z), (0.10, 0.03, 0.07), TAIL, 0.01)
        # mirror on the A pillar
        mu = P['mirror_u']; my = -L / 2 + mu * L; mz = smooth_interp(P['belt'], mu) + 0.04
        mhw = smooth_interp(P['half_width'], mu)
        add_part(bm, (side * (mhw + 0.035), my, mz - BODY_Z), (0.07, 0.035, 0.045), PAINT, 0.012)
        # door handles
        for hu in P.get('handles', []):
            hy = -L / 2 + hu * L; hz2 = smooth_interp(P['belt'], hu) - 0.05
            add_part(bm, (side * (smooth_interp(P['half_width'], hu) + 0.002), hy, hz2 - BODY_Z), (0.012, 0.06, 0.014), CHROME, 0.004)
    gy = surface_y(ob, 0.0, P['grille'][1])
    if gy is not None:
        add_part(bm, (0, gy + 0.004, P['grille'][1] - BODY_Z), (P['grille'][0], 0.03, P['grille'][2]), TRIM, 0.01)
    bm.to_mesh(ob.data); bm.free()


def finish(ob):
    bpy.context.view_layer.objects.active = ob
    ob.select_set(True)
    # smooth, but keep hard edges where parts meet (wheel wells, bumpers, lenses)
    bpy.ops.object.shade_smooth_by_angle(angle=math.radians(38), keep_sharp_edges=True)
    for m in list(ob.modifiers):
        bpy.ops.object.modifier_apply(modifier=m.name)
    mod = ob.modifiers.new('wn', 'WEIGHTED_NORMAL'); mod.keep_sharp = True
    bpy.ops.object.modifier_apply(modifier=mod.name)
    # UVs: one smart projection so Unreal has lightmap-friendly coordinates
    bpy.ops.object.mode_set(mode='EDIT'); bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.uv.smart_project(angle_limit=math.radians(60), island_margin=0.01)
    bpy.ops.object.mode_set(mode='OBJECT')


def build_body(name, P, extra=None):
    bm = bmesh.new(); loft(bm, P, expo=P.get('expo', 5.0))
    if 'bed' in P:   # sink the pickup bed: top-middle verts in the bed range drop to make a tub
        L = P['length']
        for v in bm.verts:
            u = (v.co.y + L / 2) / L
            if P['bed'][0] + 0.02 <= u <= P['bed'][1] - 0.02 and v.co.z + BODY_Z > smooth_interp(P['top'], u) - 0.03 \
                    and abs(v.co.x) < smooth_interp(P['half_width'], u) - 0.05:
                v.co.z -= 0.16
    paint_regions(bm, P)
    if 'bed' in P:
        L = P['length']; bm.normal_update()
        for f in bm.faces:
            c = f.calc_center_median(); u = (c.y + L / 2) / L
            if P['bed'][0] < u < P['bed'][1] and abs(c.x) < smooth_interp(P['half_width'], u) - 0.03 \
                    and c.z + BODY_Z > smooth_interp(P['top'], u) - 0.22:
                f.material_index = TRIM
    ob = new_object(name, bm)
    for o in bpy.context.selected_objects: o.select_set(False)
    ob.select_set(True); bpy.context.view_layer.objects.active = ob
    wheel_wells(ob, P)
    details(ob, P)
    if extra: extra(ob, P)
    finish(ob)
    return ob


# ---------------------------------------------------------------- the three bodies
HATCH = dict(
    length=1.46, axles=[0.20, 0.79], wheel_x=0.30, expo=7.0, tumblehome=0.26,
    top=[(0.0, 0.42), (0.04, 0.52), (0.12, 0.58), (0.30, 0.62), (0.47, 0.90), (0.55, 0.93), (0.80, 0.92), (0.90, 0.84), (0.97, 0.66), (1.0, 0.50)],
    bottom=[(0.0, 0.20), (0.06, 0.15), (0.94, 0.15), (1.0, 0.20)],
    half_width=[(0.0, 0.30), (0.08, 0.355), (0.5, 0.37), (0.92, 0.36), (1.0, 0.32)],
    belt=[(0.0, 0.60), (0.32, 0.62), (0.9, 0.66), (1.0, 0.66)],
    roof=(0.52, 0.84), b_pillars=[0.64], sill=0.19,
    head=(0.23, 0.50), tail=(0.25, 0.62), grille=(0.26, 0.40, 0.07), mirror_u=0.36, handles=[0.55, 0.74])

PICKUP = dict(
    length=1.58, axles=[0.19, 0.78], wheel_x=0.31, expo=8.0, tumblehome=0.20, sill=0.21,
    top=[(0.0, 0.50), (0.04, 0.62), (0.10, 0.68), (0.30, 0.70), (0.42, 0.95), (0.48, 1.00), (0.60, 1.00), (0.63, 0.80), (0.65, 0.76), (0.98, 0.76), (1.0, 0.62)],
    bottom=[(0.0, 0.24), (0.05, 0.19), (0.95, 0.19), (1.0, 0.24)],
    half_width=[(0.0, 0.33), (0.06, 0.37), (0.5, 0.38), (1.0, 0.37)],
    belt=[(0.0, 0.68), (0.35, 0.70), (0.62, 0.72), (1.0, 0.76)],
    roof=(0.46, 0.61), b_pillars=[], bed=(0.645, 0.985),
    head=(0.25, 0.58), tail=(0.30, 0.62), grille=(0.34, 0.50, 0.11), mirror_u=0.34, handles=[0.50])

TRUCK = dict(
    length=2.66, axles=[0.13, 0.62, 0.80], wheel_x=0.33, expo=9.0, tumblehome=0.15, sill=0.24, chassis_from=0.31,
    top=[(0.0, 0.62), (0.03, 0.80), (0.06, 1.02), (0.10, 1.10), (0.29, 1.10), (0.31, 0.62), (1.0, 0.60)],
    bottom=[(0.0, 0.26), (0.03, 0.22), (1.0, 0.22)],
    half_width=[(0.0, 0.36), (0.04, 0.39), (1.0, 0.39)],
    belt=[(0.0, 0.70), (0.30, 0.72), (1.0, 0.70)],
    roof=(0.08, 0.30), b_pillars=[], cosine=False,
    head=(0.27, 0.52), tail=(0.30, 0.45), grille=(0.40, 0.44, 0.16), mirror_u=0.07, handles=[0.18])


def truck_box(ob, P):
    """Cargo box on the truck's chassis, with a roll-up door line at the back."""
    bm = bmesh.new(); bm.from_mesh(ob.data)
    L = P['length']
    y0 = -L / 2 + 0.33 * L; y1 = L / 2 - 0.02
    add_part(bm, (0, (y0 + y1) / 2, 0.95 - BODY_Z), (0.80, y1 - y0, 0.68), CARGO, 0.025)
    for k in range(5):   # door ribs
        add_part(bm, (0, y1 + 0.004, 0.70 + k * 0.11 - BODY_Z), (0.70, 0.012, 0.012), TRIM, 0.003)
    bm.to_mesh(ob.data); bm.free()


# ---------------------------------------------------------------- wheel
def build_wheel():
    bm = bmesh.new()
    prof = [  # (radius, x) around the tyre, outside -> inside, then the rim
        (0.098, 0.050), (0.120, 0.052), (0.140, 0.048), (0.148, 0.038), (0.150, 0.0),
        (0.148, -0.038), (0.140, -0.048), (0.120, -0.052), (0.098, -0.050)]
    rim = [(0.098, -0.030), (0.090, -0.034), (0.030, -0.030), (0.025, -0.02), (0.0, -0.018)]
    rim_o = [(0.098, 0.030), (0.090, 0.040), (0.060, 0.036), (0.030, 0.042), (0.012, 0.046), (0.0, 0.046)]
    seg = 36
    def revolve(pts, mat, close_center=False):
        rows = []
        for r, x in pts:
            rows.append([bm.verts.new((x, r * math.cos(2 * math.pi * i / seg), r * math.sin(2 * math.pi * i / seg))) for i in range(seg)])
        for a, b in zip(rows, rows[1:]):
            for i in range(seg):
                j = (i + 1) % seg
                f = bm.faces.new((a[i], a[j], b[j], b[i])); f.material_index = mat
        return rows
    tyre = revolve(prof, 0)
    inner = revolve([(0.098, -0.050)] + rim, 1)
    outer = revolve([(0.098, 0.050)] + rim_o, 1)
    # spokes: five raised bars on the outer face
    for k in range(5):
        a = 2 * math.pi * k / 5
        c = Vector((0.050, 0.06 * math.cos(a), 0.06 * math.sin(a)))
        res = bmesh.ops.create_cube(bm, size=1.0)
        R = Matrix.Rotation(a, 3, 'X')
        for v in res['verts']:
            v.co = R @ Vector((v.co.x * 0.012, v.co.y * 0.075, v.co.z * 0.022)) + c
        for f in {f for v in res['verts'] for f in v.link_faces}: f.material_index = 1
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-5)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    old = bpy.data.objects.get('SM_CarWheel')
    if old:
        me = old.data; bpy.data.objects.remove(old); bpy.data.meshes.remove(me)
    me = bpy.data.meshes.new('SM_CarWheel')
    for n in ('Tyre', 'Rim'):
        m = bpy.data.materials.get('MC_' + n) or bpy.data.materials.new('MC_' + n); m.use_nodes = True
        bsdf = m.node_tree.nodes.get('Principled BSDF')
        bsdf.inputs['Base Color'].default_value = (0.015, 0.015, 0.016, 1) if n == 'Tyre' else (0.7, 0.7, 0.72, 1)
        bsdf.inputs['Roughness'].default_value = 0.85 if n == 'Tyre' else 0.25
        bsdf.inputs['Metallic'].default_value = 0.0 if n == 'Tyre' else 1.0
        me.materials.append(m)
    bm.to_mesh(me); bm.free()
    ob = bpy.data.objects.new('SM_CarWheel', me); bpy.context.scene.collection.objects.link(ob)
    for p in me.polygons: p.use_smooth = True
    for o in bpy.context.selected_objects: o.select_set(False)
    finish(ob)
    return ob


def build_all():
    if getattr(bpy.context, 'object', None) and bpy.context.object.mode != 'OBJECT':
        bpy.ops.object.mode_set(mode='OBJECT')
    a = build_body('SM_CarHatch', HATCH); a.location = (-1.0, 0, BODY_Z)
    b = build_body('SM_CarPickup', PICKUP); b.location = (0.0, 0, BODY_Z)
    c = build_body('SM_CarTruck', TRUCK, truck_box); c.location = (1.1, 0, BODY_Z)
    w = build_wheel(); w.location = (-1.0, 2.0, WHEEL_R)
    return [a, b, c, w]


if __name__ == '__main__':
    build_all()
