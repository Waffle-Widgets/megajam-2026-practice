"""Car kit v2 for Sundown Frogger: SM_CarCoupeV2, SM_CarHatchV2, SM_CarPickupV2, SM_CarTruckV2, SM_CarWheelV2.

Run inside Blender (Text Editor or the Blender MCP). Built the way car designers describe a body:
each station along the car is a cross-section with named lines (sill, shoulder crease, beltline,
window line, roof edge). Glass, lights and seams follow those lines, then a subdivision pass
smooths the panels while creases keep the character lines crisp.

Proportions come from real cars scaled to the game's lane width (about 0.72 m wide):
the coupe follows a first-generation BRZ (4.24 x 1.78 x 1.29 m, 2.57 m wheelbase); no badges or names.

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
BODY_Z = 0.30
WHEEL_R = 0.135
NROW = 10            # rows per half section: 0 bottom centre .. 9 roof centre


def interp(keys, u):
    if u <= keys[0][0]: return keys[0][1]
    for (u0, v0), (u1, v1) in zip(keys, keys[1:]):
        if u <= u1:
            t = (u - u0) / (u1 - u0); t = t * t * (3 - 2 * t)
            return v0 + (v1 - v0) * t
    return keys[-1][1]


def get_mats():
    cols = {'Paint': (0.6, 0.05, 0.03, 1), 'Glass': (0.01, 0.015, 0.02, 1), 'Trim': (0.02, 0.02, 0.022, 1),
            'Chrome': (0.8, 0.8, 0.8, 1), 'Headlight': (1, 0.95, 0.8, 1), 'Taillight': (0.8, 0.02, 0.01, 1),
            'Cargo': (0.75, 0.74, 0.7, 1)}
    mats = []
    for s in SLOTS:
        m = bpy.data.materials.get('MC_' + s) or bpy.data.materials.new('MC_' + s)
        m.use_nodes = True
        b = m.node_tree.nodes.get('Principled BSDF')
        if b:
            b.inputs['Base Color'].default_value = cols[s]
            b.inputs['Roughness'].default_value = {'Glass': 0.05, 'Chrome': 0.15, 'Paint': 0.3}.get(s, 0.6)
            b.inputs['Metallic'].default_value = 1.0 if s == 'Chrome' else 0.0
        mats.append(m)
    return mats


# ---------------------------------------------------------------- sections
def in_bed(P, u):
    return 'bed' in P and P['bed'][0] <= u <= P['bed'][1]


def section(P, u):
    """Half cross-section at station u as NROW (x, z) points, x >= 0, z relative to the ground."""
    zt = interp(P['top'], u); zb = interp(P['bottom'], u); zbelt = interp(P['belt'], u)
    w = interp(P['half_width'], u); zsh = min(interp(P['shoulder'], u), zbelt - 0.02)
    wroof = interp(P['roof_half'], u)
    h = zt - zbelt; k = max(0.0, min(1.0, h / P.get('gh', 0.10)))
    tuck = P.get('tuck', 0.10)          # how far the sill tucks under the body side
    pts = [(0.0, zb), (w * (0.80 - tuck * 0.3), zb), (w * (1 - tuck), zb + 0.03), (w * (1 - tuck * 0.25), zb + 0.55 * (zsh - zb)),
           (w, zsh), (w * 0.95, zbelt), (w * 0.925, zbelt + 0.004)]
    if in_bed(P, u):                     # open load bed: rail, inner wall, floor
        fl = P['bed_floor']
        pts += [(w * 0.86, zbelt), (w * 0.84, fl), (0.0, fl)]
    elif h > 0:                          # greenhouse: window line rises to the roof edge, then over the roof
        wr = w * 0.80 * (1 - k) + wroof * k
        pts += [(wr, zbelt + 0.004 + 0.80 * h), (wr * 0.55, zbelt + 0.004 + 0.97 * h), (0.0, zt)]
    else:                                # bonnet / boot: fender crest at the belt, centre dips to the top line
        pts += [(w * 0.80, zbelt + 0.5 * h), (w * 0.42, zt + 0.003), (0.0, zt)]
    # round the ends of the car in plan and elevation
    d = min(u, 1 - u); r = P.get('end_round', 0.10); zone = P.get('end_zone', 0.06)
    f = 1 - r * (1 - min(1.0, d / zone)) ** 2
    zc = (zb + max(zbelt, zt)) / 2
    return [(x * f, zc + (z - zc) * (1 - 0.35 * (1 - f))) for x, z in pts]


def stations(P, n=96):
    us = {0.5 - 0.5 * math.cos(math.pi * i / n) for i in range(n + 1)}
    for g in P.get('gaps', []):
        us |= {g, g + 0.003}
    for a, b in [P.get('bed', (None, None))]:
        if a is not None: us |= {a - 0.004, a, b, b + 0.004}
    for key in ('ws', 'side_win', 'bl'):
        if key in P: us |= set(P[key])
    for bp in P.get('b_pillars', []): us |= {bp - 0.008, bp + 0.008}
    return sorted(u for u in us if 0 <= u <= 1)


def face_material(P, u, band, x_frac):
    """band = lower row of the face (0..8); x_frac = |x| / half width at that station."""
    if band <= 1: return TRIM                                     # underbody and sill
    if 'chassis_from' in P and u > P['chassis_from']: return TRIM
    if any(g <= u <= g + 0.003 for g in P.get('gaps', [])) and 2 <= band <= 5:
        return TRIM                                               # door shut line
    if in_bed(P, u) and band >= 6: return TRIM                    # bed liner
    lo, hi = P.get('head_u', 0.06), P.get('tail_u', 0.95)
    if u < lo and band in P.get('head_bands', (4, 5)) and x_frac > P.get('head_x', 0.42): return HEAD
    if u > hi and band in P.get('tail_bands', (4, 5)) and x_frac > P.get('tail_x', 0.40): return TAIL
    if band == 6 and 'side_win' in P and P['side_win'][0] <= u <= P['side_win'][1]:
        if any(abs(u - bp) <= 0.008 for bp in P.get('b_pillars', [])): return TRIM
        return GLASS
    if band >= 7:
        if 'ws' in P and P['ws'][0] <= u <= P['ws'][1]: return GLASS
        if 'bl' in P and P['bl'][0] <= u <= P['bl'][1]: return GLASS
    return PAINT


def build_shell(name, P):
    L = P['length']; us = stations(P)
    bm = bmesh.new()
    rings = []
    for u in us:
        y = -L / 2 + u * L
        half = section(P, u)
        right = [bm.verts.new((x, y, z - BODY_Z)) for x, z in half]
        left = [bm.verts.new((-x, y, z - BODY_Z)) for x, z in half[1:-1]]
        rings.append((u, right, left, interp(P['half_width'], u)))
    crease = bm.edges.layers.float.get('crease_edge') or bm.edges.layers.float.new('crease_edge')
    for (u0, r0, l0, w0), (u1, r1, l1, w1) in zip(rings, rings[1:]):
        um = (u0 + u1) / 2
        for side, a, b in (('R', r0, r1), ('L', l0, l1)):
            if side == 'R':
                rowsA, rowsB = a, b
            else:   # left side rows 1..8, joined to the shared centre verts of the right side
                rowsA = [r0[0]] + a + [r0[-1]]; rowsB = [r1[0]] + b + [r1[-1]]
            for band in range(NROW - 1):
                q = [rowsA[band], rowsA[band + 1], rowsB[band + 1], rowsB[band]]
                if side == 'L': q = q[::-1]
                f = bm.faces.new(q)
                xf = abs((q[0].co.x + q[2].co.x) / 2) / max(w0, 1e-4)
                f.material_index = face_material(P, um, band, xf)
    # end caps
    for (u, r, l, w), rev in ((rings[0], True), (rings[-1], False)):
        loop = r + l[::-1]
        c = bm.verts.new((0.0, r[0].co.y, sum(v.co.z for v in loop) / len(loop)))
        for i in range(len(loop)):
            tri = (loop[i], loop[(i + 1) % len(loop)], c)
            f = bm.faces.new(tri[::-1] if rev else tri); f.material_index = PAINT
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-6)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    # crisp lines: material borders fully, the shoulder crease partly
    for e in bm.edges:
        fs = e.link_faces
        if len(fs) == 2 and fs[0].material_index != fs[1].material_index:
            e[crease] = 0.9
    for (u0, r0, l0, w0), (u1, r1, l1, w1) in zip(rings, rings[1:]):   # shoulder crease line, both sides
        for va, vb in ((r0[4], r1[4]), (l0[3], l1[3])):
            if va.is_valid and vb.is_valid:
                e = bm.edges.get((va, vb))
                if e: e[crease] = max(e[crease], 0.6)
    me = bpy.data.meshes.new(name)
    for m in get_mats(): me.materials.append(m)          # slots before faces
    bm.to_mesh(me); bm.free()
    old = bpy.data.objects.get(name)
    if old: bpy.data.objects.remove(old)
    ob = bpy.data.objects.new(name, me); bpy.context.scene.collection.objects.link(ob)
    return ob


def select_only(ob):
    for o in bpy.context.view_layer.objects:
        if o: o.select_set(False)
    ob.select_set(True); bpy.context.view_layer.objects.active = ob


def subdivide(ob, levels=2):
    select_only(ob)
    m = ob.modifiers.new('sub', 'SUBSURF'); m.levels = levels; m.render_levels = levels
    bpy.ops.object.modifier_apply(modifier='sub')


def wheel_wells(ob, P):
    L = P['length']; cutters = []
    for u in P['axles']:
        y = -L / 2 + u * L
        for side in (-1, 1):
            bpy.ops.mesh.primitive_cylinder_add(vertices=48, radius=WHEEL_R + P.get('arch_gap', 0.018), depth=0.32,
                                                location=(side * (P['wheel_x'] + 0.13), y, WHEEL_R - BODY_Z),
                                                rotation=(0, math.pi / 2, 0))
            cutters.append(bpy.context.active_object)
    for cu in cutters:
        mod = ob.modifiers.new('well', 'BOOLEAN'); mod.operation = 'DIFFERENCE'; mod.solver = 'EXACT'; mod.object = cu
        select_only(ob); bpy.ops.object.modifier_apply(modifier=mod.name)
        bpy.data.objects.remove(cu)
    for p in ob.data.polygons:                               # inner arch walls -> black
        c = p.center
        for u in P['axles']:
            y = -L / 2 + u * L
            if math.hypot(c.y - y, c.z - (WHEEL_R - BODY_Z)) < WHEEL_R + 0.03 and abs(p.normal.x) < 0.75 \
                    and abs(c.x) < interp(P['half_width'], (c.y + L / 2) / L) - 0.008:
                p.material_index = TRIM


# ---------------------------------------------------------------- detail parts
def part(bm, centre, size, mat, bevel=0.01, segs=3):
    before = set(bm.faces)
    res = bmesh.ops.create_cube(bm, size=1.0); vs = res['verts']
    for v in vs:
        v.co = Vector((v.co.x * size[0], v.co.y * size[1], v.co.z * size[2])) + Vector(centre)
    if bevel > 0:
        bmesh.ops.bevel(bm, geom=list({e for v in vs for e in v.link_edges}), offset=bevel, segments=segs, affect='EDGES', profile=0.5)
    for f in set(bm.faces) - before: f.material_index = mat     # bevel replaces the cube's faces, so diff the face set


def trapezoid(bm, cx, y, cz, w_top, w_bot, h, depth, mat):
    """A flat trapezoid plate facing -Y (grille / intake)."""
    pts = [(-w_bot / 2, cz - h / 2), (w_bot / 2, cz - h / 2), (w_top / 2, cz + h / 2), (-w_top / 2, cz + h / 2)]
    front = [bm.verts.new((cx + x, y, z)) for x, z in pts]; back = [bm.verts.new((cx + x, y + depth, z)) for x, z in pts]
    fs = [bm.faces.new(front[::-1]), bm.faces.new(back)]
    for i in range(4):
        j = (i + 1) % 4; fs.append(bm.faces.new((front[i], front[j], back[j], back[i])))
    for f in fs: f.material_index = mat


def cylinder(bm, c, axis, r, length, mat, seg=16):
    axis = Vector(axis).normalized(); n = axis.orthogonal().normalized(); b = axis.cross(n)
    a0 = [bm.verts.new(Vector(c) + (n * math.cos(TA * i / seg) + b * math.sin(TA * i / seg)) * r) for i in range(seg)]
    a1 = [bm.verts.new(v.co + axis * length) for v in a0]
    fs = [bm.faces.new(a0[::-1]), bm.faces.new(a1)]
    for i in range(seg):
        j = (i + 1) % seg; fs.append(bm.faces.new((a0[i], a0[j], a1[j], a1[i])))
    for f in fs: f.material_index = mat


TA = 2 * math.pi


def ray_y(ob, x, z, front=True):
    o = Vector((x, -5.0 if front else 5.0, z - BODY_Z)); d = Vector((0, 1 if front else -1, 0))
    hit, loc, nrm, idx = ob.ray_cast(o, d)
    return loc.y if hit else None


def ray_x(ob, y, z):
    hit, loc, nrm, idx = ob.ray_cast(Vector((5.0, y, z - BODY_Z)), Vector((-1, 0, 0)))
    return loc.x if hit else None


def details(ob, P):
    L = P['length']
    bm = bmesh.new(); bm.from_mesh(ob.data)
    yf = ray_y(ob, 0, P['grille'][1]) or -L / 2; yr = ray_y(ob, 0, P.get('plate_r', 0.3), front=False) or L / 2
    gw_t, gz, gh, gw_b = P['grille'][0], P['grille'][1], P['grille'][2], P['grille'][3]
    yf = ray_y(ob, 0, gz) or yf
    trapezoid(bm, 0, yf - 0.004, gz - BODY_Z, gw_t, gw_b, gh, 0.03, TRIM)
    if 'plate' in P:
        part(bm, (0, yf - 0.007, P['plate'] - BODY_Z), (0.13, 0.006, 0.034), CARGO, 0.003, 1)
        part(bm, (0, yr + 0.007, P['plate_r'] - BODY_Z), (0.13, 0.006, 0.034), CARGO, 0.003, 1)
    for side in (-1, 1):
        for (fx, fz, fr) in P.get('fogs', []):                  # fog lights in the bumper corners
            y = ray_y(ob, side * fx, fz)
            if y is not None: cylinder(bm, (side * fx, y + 0.004, fz - BODY_Z), (0, -1, 0), fr, 0.008, HEAD, 12)
        mu = P['mirror_u']; my = -L / 2 + mu * L; mz = interp(P['belt'], mu) + 0.02
        mx = ray_x(ob, my, mz) or interp(P['half_width'], mu)
        part(bm, (side * (mx + 0.022), my, mz - BODY_Z), (0.045, 0.03, 0.028), P.get('mirror_mat', PAINT), 0.011, 3)
        part(bm, (side * (mx + 0.006), my + 0.004, mz - 0.006 - BODY_Z), (0.02, 0.012, 0.01), TRIM, 0.003, 1)
        for hu in P.get('handles', []):
            hy = -L / 2 + hu * L; hz = interp(P['belt'], hu) - 0.035
            hx = ray_x(ob, hy, hz)
            if hx is not None: part(bm, (side * (hx + 0.002), hy, hz - BODY_Z), (0.006, 0.045, 0.01), P.get('handle_mat', PAINT), 0.003, 1)
        if 'vent_u' in P:                                        # fender vent behind the front wheel
            vy = -L / 2 + P['vent_u'] * L; vz = P['vent_z']; vx = ray_x(ob, vy, vz)
            if vx is not None:
                part(bm, (side * (vx + 0.001), vy, vz - BODY_Z), (0.006, 0.05, 0.016), TRIM, 0.004, 2)
                part(bm, (side * (vx + 0.003), vy - 0.004, vz - BODY_Z), (0.004, 0.035, 0.004), CHROME, 0.0015, 1)
        for (ex, ez) in P.get('exhaust', []):
            y = ray_y(ob, side * ex, ez, front=False)
            if y is not None: cylinder(bm, (side * ex, y - 0.012, ez - BODY_Z), (0, 1, 0), 0.016, 0.03, CHROME, 14)
    if P.get('wing'):                                            # rear wing on two posts
        wu = P['wing'][0]; wy = -L / 2 + wu * L; wz = interp(P['top'], wu) + P['wing'][1]
        part(bm, (0, wy, wz - BODY_Z), (P['wing'][2], 0.07, 0.009), P.get('wing_mat', PAINT), 0.004, 2)
        for side in (-1, 1):
            part(bm, (side * P['wing'][2] * 0.36, wy + 0.01, wz - P['wing'][1] / 2 - BODY_Z), (0.008, 0.035, P['wing'][1]), TRIM, 0.002, 1)
    if 'fin_u' in P:                                             # shark-fin antenna at the back of the roof
        fy = -L / 2 + P['fin_u'] * L; fz = interp(P['top'], P['fin_u'])
        fin = bmesh.ops.create_cone(bm, cap_ends=True, segments=10, radius1=0.016, radius2=0.002, depth=0.03,
                                    matrix=Matrix.Translation((0, fy, fz + 0.012 - BODY_Z)))
        for v in fin['verts']:
            v.co.y += (v.co.z - (fz - BODY_Z)) * 0.8                    # sweep it back
            for f in v.link_faces: f.material_index = PAINT
        for v in fin['verts']: v.co.x *= 0.45
    if 'box' in P:                                               # truck cargo box with roll-up door ribs
        y0 = -L / 2 + P['box'][0] * L; y1 = L / 2 - 0.02
        part(bm, (0, (y0 + y1) / 2, P['box'][1] - BODY_Z), (0.80, y1 - y0, P['box'][2]), CARGO, 0.02, 3)
        for k in range(6):
            part(bm, (0, y1 + 0.004, P['box'][1] - P['box'][2] / 2 + 0.06 + k * 0.1 - BODY_Z), (0.72, 0.01, 0.01), TRIM, 0.003, 1)
    bm.to_mesh(ob.data); bm.free()


def finish(ob):
    select_only(ob)
    for p in ob.data.polygons: p.use_smooth = True
    bpy.ops.object.shade_smooth_by_angle(angle=math.radians(35), keep_sharp_edges=True)
    for m in list(ob.modifiers): bpy.ops.object.modifier_apply(modifier=m.name)
    mod = ob.modifiers.new('wn', 'WEIGHTED_NORMAL'); mod.keep_sharp = True
    bpy.ops.object.modifier_apply(modifier=mod.name)
    bpy.ops.object.mode_set(mode='EDIT'); bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.uv.smart_project(angle_limit=math.radians(60), island_margin=0.01)
    bpy.ops.object.mode_set(mode='OBJECT')


def build_body(name, P):
    ob = build_shell(name, P)
    subdivide(ob, 2)
    wheel_wells(ob, P)
    details(ob, P)
    finish(ob)
    return ob


# ---------------------------------------------------------------- the bodies (lengths kept close to the old hit boxes)
COUPE = dict(   # first-generation BRZ (2017 facelift) silhouette, scaled to 0.41: no badges or names
    length=1.72, axles=[0.198, 0.804], wheel_x=0.30, gh=0.12, end_round=0.24, arch_gap=0.012,
    top=[(0.0, 0.215), (0.015, 0.255), (0.05, 0.283), (0.20, 0.328), (0.38, 0.372), (0.425, 0.392), (0.50, 0.492),
         (0.56, 0.521), (0.62, 0.512), (0.70, 0.480), (0.80, 0.432), (0.875, 0.403), (0.95, 0.393), (0.985, 0.38), (1.0, 0.33)],
    belt=[(0.0, 0.235), (0.05, 0.298), (0.20, 0.345), (0.38, 0.378), (0.425, 0.382), (0.60, 0.386), (0.80, 0.392), (0.90, 0.39), (1.0, 0.36)],
    bottom=[(0.0, 0.12), (0.03, 0.075), (0.97, 0.075), (1.0, 0.13)],
    half_width=[(0.0, 0.29), (0.06, 0.335), (0.19, 0.358), (0.33, 0.345), (0.48, 0.33), (0.64, 0.345), (0.80, 0.362), (0.92, 0.352), (0.98, 0.33), (1.0, 0.31)],
    shoulder=[(0.0, 0.21), (0.08, 0.27), (0.20, 0.33), (0.34, 0.30), (0.50, 0.29), (0.66, 0.31), (0.80, 0.345), (0.93, 0.335), (1.0, 0.31)], tuck=0.13, end_zone=0.085,
    roof_half=[(0.0, 0.20), (0.45, 0.245), (0.56, 0.265), (0.75, 0.245), (1.0, 0.20)],
    ws=(0.428, 0.505), side_win=(0.432, 0.705), bl=(0.632, 0.862), gaps=[0.365, 0.625],
    head_u=0.075, head_bands=(4, 5, 6), head_x=0.58, tail_u=0.95, tail_bands=(4, 5), tail_x=0.5,
    grille=(0.40, 0.165, 0.075, 0.30), plate=0.215, plate_r=0.30, fogs=[(0.24, 0.155, 0.014)],
    mirror_u=0.445, handles=[0.585], vent_u=0.335, vent_z=0.29, exhaust=[(0.22, 0.13)], wing=(0.965, 0.045, 0.60), wing_mat=TRIM,
    fin_u=0.66)

HATCH = dict(   # compact five-door hatchback (Golf-class), scaled to 0.39
    length=1.62, axles=[0.17, 0.83], wheel_x=0.29, gh=0.16, end_round=0.10,
    top=[(0.0, 0.25), (0.02, 0.30), (0.08, 0.335), (0.30, 0.372), (0.34, 0.385), (0.47, 0.545), (0.52, 0.565),
         (0.78, 0.558), (0.86, 0.535), (0.94, 0.47), (0.985, 0.42), (1.0, 0.36)],
    belt=[(0.0, 0.27), (0.08, 0.33), (0.30, 0.375), (0.34, 0.385), (0.60, 0.395), (0.90, 0.415), (1.0, 0.40)],
    bottom=[(0.0, 0.13), (0.03, 0.085), (0.97, 0.085), (1.0, 0.14)],
    half_width=[(0.0, 0.30), (0.06, 0.34), (0.20, 0.35), (0.50, 0.35), (0.85, 0.352), (0.97, 0.34), (1.0, 0.31)],
    shoulder=[(0.0, 0.23), (0.20, 0.30), (0.60, 0.32), (1.0, 0.33)],
    roof_half=[(0.0, 0.22), (0.50, 0.285), (0.85, 0.285), (1.0, 0.25)],
    ws=(0.345, 0.47), side_win=(0.352, 0.855), bl=(0.868, 0.965), b_pillars=[0.62], gaps=[0.335, 0.612, 0.628, 0.84], end_zone=0.07,
    head_u=0.055, head_bands=(4,), head_x=0.5, tail_u=0.955, tail_bands=(5, 6),
    grille=(0.36, 0.215, 0.05, 0.30), plate=0.24, plate_r=0.30, mirror_u=0.355, mirror_mat=TRIM, handles=[0.55, 0.78], handle_mat=CHROME)

PICKUP = dict(  # mid-size crew-cab pickup, scaled to 0.38
    length=1.95, axles=[0.16, 0.80], wheel_x=0.30, gh=0.17, end_round=0.07,
    top=[(0.0, 0.37), (0.02, 0.43), (0.06, 0.465), (0.22, 0.485), (0.25, 0.495), (0.33, 0.655), (0.37, 0.672),
         (0.615, 0.668), (0.622, 0.64), (0.626, 0.50), (1.0, 0.50)],
    belt=[(0.0, 0.42), (0.06, 0.465), (0.22, 0.485), (0.25, 0.495), (0.62, 0.50), (1.0, 0.50)],
    bottom=[(0.0, 0.17), (0.04, 0.12), (0.96, 0.12), (1.0, 0.17)],
    half_width=[(0.0, 0.32), (0.05, 0.355), (0.20, 0.36), (1.0, 0.36)],
    shoulder=[(0.0, 0.30), (0.20, 0.38), (1.0, 0.40)],
    roof_half=[(0.0, 0.25), (0.45, 0.295), (0.60, 0.295), (1.0, 0.29)],
    ws=(0.255, 0.335), side_win=(0.262, 0.61), bl=(0.612, 0.621), b_pillars=[0.44], gaps=[0.245, 0.436, 0.444, 0.615],
    bed=(0.63, 0.985), bed_floor=0.36,
    head_u=0.045, head_bands=(4,), head_x=0.45, tail_u=0.982, tail_bands=(3, 4, 5),
    grille=(0.50, 0.37, 0.10, 0.46), plate=0.24, plate_r=0.26, mirror_u=0.265, mirror_mat=TRIM, handles=[0.40, 0.56], handle_mat=TRIM)

TRUCK = dict(   # cab-over box truck
    length=2.66, axles=[0.13, 0.62, 0.80], wheel_x=0.33, gh=0.30, end_round=0.05, chassis_from=0.31,
    top=[(0.0, 0.62), (0.02, 0.80), (0.04, 0.98), (0.06, 1.06), (0.10, 1.10), (0.29, 1.10), (0.30, 1.08), (0.305, 0.40), (1.0, 0.40)],
    belt=[(0.0, 0.62), (0.03, 0.75), (0.06, 0.78), (0.30, 0.80), (0.305, 0.40), (1.0, 0.40)],
    bottom=[(0.0, 0.26), (0.02, 0.22), (0.30, 0.22), (0.305, 0.30), (1.0, 0.30)],
    half_width=[(0.0, 0.36), (0.03, 0.39), (0.30, 0.39), (0.305, 0.30), (1.0, 0.30)],
    shoulder=[(0.0, 0.50), (0.30, 0.55), (0.305, 0.36), (1.0, 0.36)],
    roof_half=[(0.0, 0.33), (0.10, 0.36), (1.0, 0.36)],
    ws=(0.035, 0.092), side_win=(0.10, 0.29), gaps=[0.20],
    head_u=0.03, head_bands=(4,), head_x=0.5, tail_u=0.99,
    grille=(0.42, 0.50, 0.12, 0.40), plate=0.36, plate_r=0.40, mirror_u=0.06, mirror_mat=TRIM, handles=[0.18], handle_mat=TRIM,
    box=(0.33, 0.86, 0.86))


# ---------------------------------------------------------------- wheel: low-profile tyre, ten-spoke alloy, brake disc
def build_wheel(name='SM_CarWheelV3'):
    bm = bmesh.new(); k = WHEEL_R / 0.15; seg = 56
    def revolve(pts, mat):
        rows = [[bm.verts.new((x, r * math.cos(TA * i / seg), r * math.sin(TA * i / seg))) for i in range(seg)] for r, x in pts]
        for a, b in zip(rows, rows[1:]):
            for i in range(seg):
                j = (i + 1) % seg; bm.faces.new((a[i], a[j], b[j], b[i])).material_index = mat
    tyre = [(0.106, 0.050), (0.124, 0.054), (0.140, 0.050), (0.148, 0.040), (0.150, 0.030), (0.146, 0.025), (0.150, 0.020),
            (0.150, 0.006), (0.146, 0.001), (0.146, -0.003), (0.150, -0.008), (0.150, -0.022), (0.146, -0.026), (0.150, -0.031),
            (0.148, -0.041), (0.140, -0.050), (0.124, -0.054), (0.106, -0.050)]
    revolve([(r * k, x) for r, x in tyre], 0)
    revolve([(r * k, x) for r, x in [(0.106, -0.050), (0.102, -0.040), (0.100, -0.030), (0.040, -0.025), (0.0, -0.025)]], 1)
    revolve([(r * k, x) for r, x in [(0.106, 0.050), (0.104, 0.046), (0.098, 0.044), (0.094, 0.030), (0.090, 0.020)]], 1)
    revolve([(r * k, x) for r, x in [(0.070, 0.004), (0.070, 0.0), (0.0, 0.0)]], 1)        # brake disc face
    revolve([(r * k, x) for r, x in [(0.1045, 0.0475), (0.1015, 0.0465)]], 2)               # pinstripe on the rim lip
    cal = bmesh.ops.create_cube(bm, size=1.0)                                                # brake caliper at the front
    for v in cal['verts']:
        a = math.atan2(v.co.z, 1.0) * 0 + (v.co.y + 0.5) * 0.9 - 0.45
        rr = (0.074 + (v.co.z + 0.5) * 0.016) * k
        v.co = Vector((0.012 + v.co.x * 0.026, rr * math.sin(a), rr * math.cos(a)))
    for f in {f for v in cal['verts'] for f in v.link_faces}: f.material_index = 2
    for s in range(5):                                       # five split spokes = ten arms
        for off in (-0.13, 0.13):
            a = TA * s / 5 + off
            R = Matrix.Rotation(a, 3, 'X')
            res = bmesh.ops.create_cube(bm, size=1.0)
            for v in res['verts']:
                t = (v.co.y + 0.5)                           # 0 at the hub .. 1 at the rim
                v.co = R @ Vector((0.040 + v.co.x * 0.010, (0.022 + t * 0.074) * k, v.co.z * (0.012 - 0.004 * t) * k * (1.0)))
            for f in {f for v in res['verts'] for f in v.link_faces}: f.material_index = 1
    hub = bmesh.ops.create_cone(bm, cap_ends=True, segments=20, radius1=0.022 * k, radius2=0.018 * k, depth=0.012,
                                matrix=Matrix.Translation((0.044, 0, 0)) @ Matrix.Rotation(math.pi / 2, 4, 'Y'))
    for v in hub['verts']:
        for f in v.link_faces: f.material_index = 1
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    me = bpy.data.meshes.new(name)
    for n, col, rough, met in (('Tyre', (0.015, 0.015, 0.016, 1), 0.85, 0.0), ('Rim', (0.12, 0.12, 0.13, 1), 0.3, 1.0), ('Accent', (0.5, 0.01, 0.01, 1), 0.3, 0.0)):
        m = bpy.data.materials.get('MC_' + n) or bpy.data.materials.new('MC_' + n); m.use_nodes = True
        b = m.node_tree.nodes['Principled BSDF']; b.inputs['Base Color'].default_value = col
        b.inputs['Roughness'].default_value = rough; b.inputs['Metallic'].default_value = met
        me.materials.append(m)
    bm.to_mesh(me); bm.free()
    old = bpy.data.objects.get(name)
    if old: bpy.data.objects.remove(old)
    ob = bpy.data.objects.new(name, me); bpy.context.scene.collection.objects.link(ob)
    select_only(ob)
    bpy.ops.object.shade_smooth_by_angle(angle=math.radians(40))
    for m in list(ob.modifiers): bpy.ops.object.modifier_apply(modifier=m.name)
    bpy.ops.object.mode_set(mode='EDIT'); bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.uv.smart_project(angle_limit=math.radians(60), island_margin=0.01)
    bpy.ops.object.mode_set(mode='OBJECT')
    return ob


def build_all():
    out = []
    for name, P, x in (('SM_CarCoupeV2', COUPE, -2.2), ('SM_CarHatchV2', HATCH, -1.1), ('SM_CarPickupV2', PICKUP, 0.0), ('SM_CarTruckV2', TRUCK, 1.2)):
        ob = build_body(name, P); ob.location = (x, 0, BODY_Z); out.append(ob)
    w = build_wheel(); w.location = (0, 2.5, WHEEL_R); out.append(w)
    return out
