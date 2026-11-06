"""World kit: scenery for new biomes (greenery, futuristic city, desolate lands).

Run inside Blender 5.2 after real_kit.py (it reuses its helpers, bark tube and bake code):
    exec(open(<real_kit.py>).read()); exec(open(<this file>).read())
Desolate:  build_dead_tree(), build_dead_bush()       (bark tiles: M_TreeBark / T_TreeBark, already in Unreal)
           build_rock_spire(); bake_set(SM_RockSpire_High, SM_RockSpire, <out>, 'T_RockSpire', 2048, 0.08, 0.6)
Greenery:  build_fern()                               (M_TreeBark + M_TreeLeaf / T_LeafTile, already in Unreal)
           build_flowers(); bake_flat(build_petal_tile(), <out>, 'T_PetalTile', 1024)
City:      build_neon_lamp();  bake_prop('SM_NeonLamp', <out>, 1024)   (slot 2 = glow, emissive in Unreal)
Then export(<out>, [names]). <out> is Art/Blender/export/World (committed for the Unreal PC).
Skyline buildings live in city_kit.py.
"""
import bpy, bmesh, math, random, os
import numpy as np
from mathutils import Vector, noise


# ---------------------------------------------------------------- desolate: dead tree
def cap(bm, uv, col, centre, ring_pts, shade):
    """Close a broken branch end with a small cone so it isn't a hole."""
    tip = bm.verts.new(centre)
    for j in range(len(ring_pts) - 1):
        f = bm.faces.new([ring_pts[j], ring_pts[j + 1], tip]); f.material_index = 0; f.smooth = True
        for lp in f.loops:
            lp[uv].uv = (j * 0.1, 0.0); lp[col] = (shade, shade, shade, 1)


def build_dead_tree(name='SM_DeadTree', seed=21, height=4.6):
    """A leafless, weathered tree: crooked trunk, a few gnarled limbs, snapped stubs, bare twigs."""
    rnd = random.Random(seed)
    bm = bmesh.new(); uv = bm.loops.layers.uv.new('UVMap'); col = bm.loops.layers.color.new('Col')

    def ao(p):                          # darker at the foot and in the crotch of the limbs
        return 0.5 + 0.5 * min(1, max(0.0, p.z) / 1.4)

    trunk = bend_path(Vector((0, 0, -0.15)), Vector((0.12, -0.05, 1)), height * 0.78, 14, rnd, 0.0, 0.09)
    tr = [0.19 * (1 - 0.72 * i / 14) for i in range(15)]
    bark_tube(bm, uv, col, trunk[:11], tr[:11], 12, ao, flare=True)

    def limb(pts, radii, level, broken):
        seg = [12, 8, 6, 4][level]
        bark_tube(bm, uv, col, pts, radii, seg, ao)
        if broken:                      # blunt snapped end
            end = pts[-1]; d = (pts[-1] - pts[-2]).normalized()
            ends = [v for v in bm.verts if (v.co - end).length <= radii[-1] * 1.01 + 1e-5][-(seg + 1):]
            cap(bm, uv, col, end + d * radii[-1] * 0.6, ends, 0.45)
        if level == 3 or broken: return
        seglen = sum((pts[i + 1] - pts[i]).length for i in range(len(pts) - 1))
        n_kids = [0, 4, 4, 3][level + 1]
        phase = rnd.uniform(0, 2 * math.pi)
        for k in range(n_kids):
            t = 0.3 + 0.65 * (k + rnd.uniform(0, 0.7)) / n_kids
            idx = min(len(pts) - 2, int(t * (len(pts) - 1)))
            p = pts[idx]; d = (pts[idx + 1] - p).normalized()
            n, b = frame(d); a = phase + k * math.radians(137.5)
            out = n * math.cos(a) + b * math.sin(a)
            ang = math.radians(rnd.uniform(30, 60))
            nd = (d * math.cos(ang) + out * math.sin(ang) + Vector((0, 0, 0.35))).normalized()
            length = seglen * rnd.uniform(0.4, 0.62) * (1.05 - 0.4 * t)
            r0 = radii[idx] * rnd.uniform(0.5, 0.65)
            nseg = [0, 6, 5, 4][level + 1]
            snap = level + 1 < 3 and rnd.random() < 0.18
            if snap: length *= 0.35
            pp = bend_path(p, nd, length, nseg, rnd, -0.05, [0, 0.22, 0.28, 0.3][level + 1])   # crooked, reaching up
            end_r = r0 * 0.55 if snap else 0.003
            limb(pp, [r0 + (end_r - r0) * i / nseg for i in range(nseg + 1)], level + 1, snap)

    nb = 6
    for k in range(nb):
        t = 0.4 + 0.55 * k / (nb - 1) + rnd.uniform(-0.04, 0.04)
        idx = min(13, int(t * 14)); p = trunk[idx]
        a = k * math.radians(137.5) + rnd.uniform(-0.4, 0.4)
        out = Vector((math.cos(a), math.sin(a), 0))
        length = height * rnd.uniform(0.32, 0.5) * (1.1 - 0.5 * t)
        el = math.radians(rnd.uniform(35, 60))
        nd = (out * math.sin(el) + Vector((0, 0, math.cos(el)))).normalized()
        snap = k in (1, 4)
        if snap: length *= 0.3
        pp = bend_path(p, nd, length, 7, rnd, -0.04, 0.2)
        r0 = tr[idx] * rnd.uniform(0.55, 0.7)
        end_r = r0 * 0.6 if snap else 0.004
        limb(pp, [r0 + (end_r - r0) * i / 7 for i in range(8)], 1, snap)
    limb(trunk[10:], tr[10:], 0, True)   # the leader snapped off: blunt top

    me = bpy.data.meshes.new(name)
    me.materials.append(bpy.data.materials.get('M_TreeBark') or bpy.data.materials.new('M_TreeBark'))   # slot before faces
    bm.normal_update(); bm.to_mesh(me); bm.free()
    ob = link_new(name, me)
    return {'tris': sum(len(p.vertices) - 2 for p in me.polygons), 'dims': tuple(round(x, 2) for x in ob.dimensions)}


# ---------------------------------------------------------------- desolate: dead bush (dry, twiggy, tumbleweed-like)
def build_dead_bush(name='SM_DeadBush', seed=14):
    rnd = random.Random(seed)
    bm = bmesh.new(); uv = bm.loops.layers.uv.new('UVMap'); col = bm.loops.layers.color.new('Col')
    cc = Vector((0, 0, 0.35)); cr = Vector((0.6, 0.55, 0.4))

    def ao(p):
        q = p - cc
        d = min(1.3, math.sqrt((q.x / cr.x) ** 2 + (q.y / cr.y) ** 2 + (q.z / cr.z) ** 2))
        return max(0.4, min(1.0, 0.4 + 0.6 * d))

    def grow(pts, radii, level):
        bark_tube(bm, uv, col, pts, radii, [5, 4, 3][level], ao)
        if level == 2: return
        seglen = sum((pts[i + 1] - pts[i]).length for i in range(len(pts) - 1))
        n = [5, 5][level]
        for k in range(n):
            t = 0.25 + 0.7 * (k + rnd.uniform(0, 0.8)) / n
            idx = min(len(pts) - 2, int(t * (len(pts) - 1)))
            p = pts[idx]; d = (pts[idx + 1] - p).normalized(); fn, fb = frame(d)
            a = k * 2.4 + rnd.uniform(0, 1); out = fn * math.cos(a) + fb * math.sin(a)
            nd = (d * 0.6 + out * 0.8 + Vector((0, 0, 0.3))).normalized()
            ln = seglen * rnd.uniform(0.45, 0.65) * (1.1 - 0.5 * t)
            pp = bend_path(p, nd, ln, 4, rnd, -0.05, 0.3)             # zig-zag twigs
            r0 = radii[idx] * 0.6
            grow(pp, [r0 + (0.0015 - r0) * i / 4 for i in range(5)], level + 1)

    for s in range(11):
        a = s * 2.4 + rnd.uniform(-0.3, 0.3); out = Vector((math.cos(a), math.sin(a), 0))
        el = math.radians(rnd.uniform(15, 55))
        pp = bend_path(out * rnd.uniform(0.0, 0.06) + Vector((0, 0, -0.04)), out * math.sin(el) + Vector((0, 0, math.cos(el))),
                       rnd.uniform(0.5, 0.8), 5, rnd, -0.05, 0.22)
        grow(pp, [0.02 + (0.003 - 0.02) * i / 5 for i in range(6)], 0)
    return finish_mesh(name, bm, ['M_TreeBark'])


# ---------------------------------------------------------------- desolate: sandstone rock spire (hoodoo)
def mat_sandstone(name='MB_Sandstone'):
    m, nt = new_mat(name); P, (px, py, pz), (nx, ny, nz) = obj_coords(nt)
    wob = tex(nt, 'ShaderNodeTexNoise', P, 0.8, Detail=3.0)
    zz = mth(nt, 'ADD', pz, mth(nt, 'MULTIPLY', wob.outputs['Fac'], 0.6))
    band = mth(nt, 'MULTIPLY', mth(nt, 'ADD', mth(nt, 'SINE', mth(nt, 'MULTIPLY', zz, 7.0)), 1.0), 0.5)
    band2 = mth(nt, 'MULTIPLY', mth(nt, 'ADD', mth(nt, 'SINE', mth(nt, 'MULTIPLY', zz, 2.3)), 1.0), 0.5)
    col = mix(nt, band, (0.26, 0.085, 0.03, 1), (0.40, 0.17, 0.07, 1))
    col = mix(nt, smooth(nt, band2, 0.88, 0.97), col, (0.50, 0.33, 0.19, 1))      # pale cream layers
    fine = tex(nt, 'ShaderNodeTexNoise', P, 30.0, Detail=8.0, Roughness=0.7)
    col = mix(nt, mth(nt, 'MULTIPLY', fine.outputs['Fac'], 0.35), col, (0.25, 0.10, 0.05, 1))
    pits = tex(nt, 'ShaderNodeTexVoronoi', P, 18.0)
    pit = smooth(nt, pits.outputs['Distance'], 0.12, 0.03)
    col = mix(nt, mth(nt, 'MULTIPLY', pit, 0.5), col, (0.18, 0.07, 0.03, 1))
    col, low = grime(nt, P, pz, col, 0.4, 0.5, (0.30, 0.17, 0.09, 1), 0.5)       # desert varnish streaks, dust at the foot
    top = smooth(nt, nz, 0.6, 0.9)
    col = mix(nt, mth(nt, 'MULTIPLY', top, 0.3), col, (0.48, 0.30, 0.17, 1))      # sun-bleached tops
    h = mth(nt, 'ADD', mth(nt, 'MULTIPLY', band, 0.6), mth(nt, 'SUBTRACT', fine.outputs['Fac'], mth(nt, 'MULTIPLY', pit, 0.8)))
    principled(nt, col, 0.92, h, 0.006)
    return m


def build_rock_spire(name='SM_RockSpire', seed=3, height=6.0):
    """Eroded sandstone column: wide foot, narrow banded neck, a harder cap rock on top."""
    rnd = random.Random(seed)
    nr, na = 150, 128
    def radius(t, a):
        prof = 1.25 * (1 - t) ** 1.6 + 0.55                                   # wide foot, slim upper column
        prof += 0.28 * math.exp(-((t - 0.93) / 0.05) ** 2)                    # cap rock ledge
        prof -= 0.12 * math.exp(-((t - 0.86) / 0.04) ** 2)                    # neck under the cap
        layer = 0.06 * math.sin(t * height * 7.0 + 0.6 * math.sin(a * 2 + seed)) # soft and hard layers
        p = Vector((math.cos(a), math.sin(a), t * 2.5))
        n = 0.22 * fbm(p, 1.1, 5, seed) + 0.05 * fbm(p, 4.0, 4, seed + 5)
        return max(0.15, prof * (1 + n) + layer)
    bm = bmesh.new()
    rings = []
    for i in range(nr + 1):
        t = i / nr; ring = []
        for j in range(na):
            a = TAU * j / na; r = radius(t, a)
            z = -0.25 + t * (height + 0.25)
            if t > 0.95: r *= max(0.0, 1 - ((t - 0.95) / 0.05) ** 2) ** 0.5    # rounded top
            ring.append(bm.verts.new((r * math.cos(a) * 1.0, r * math.sin(a) * 0.85, z)))
        rings.append(ring)
    for i in range(nr):
        for j in range(na):
            bm.faces.new([rings[i][j], rings[i][(j + 1) % na], rings[i + 1][(j + 1) % na], rings[i + 1][j]])
    tip = bm.verts.new((0, 0, height))
    for j in range(na): bm.faces.new([rings[-1][j], rings[-1][(j + 1) % na], tip])
    bm.faces.new(list(reversed(rings[0])))
    bm.normal_update()
    for v in bm.verts:                                     # grain and a few vertical cracks
        p = v.co
        cell = noise.voronoi(Vector((p.x * 1.5, p.y * 1.5, p.z * 0.3 + seed)), distance_metric='DISTANCE')[0]
        crack = min(1.0, (cell[1] - cell[0]) / 0.05)
        v.co = p + v.normal * (-0.05 * (1 - crack) ** 3 + 0.01 * noise.noise(p * 12.0))
    me = bpy.data.meshes.new(name + '_High'); bm.to_mesh(me); bm.free()
    for pl in me.polygons: pl.use_smooth = True
    hi = link_new(name + '_High', me)
    lo_me = me.copy(); lo_me.name = name
    lo = link_new(name, lo_me); select_only(lo)
    mod = lo.modifiers.new('dec', 'DECIMATE'); mod.ratio = 0.16
    bpy.ops.object.modifier_apply(modifier='dec')
    bpy.ops.object.mode_set(mode='EDIT'); bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.uv.smart_project(angle_limit=math.radians(55), island_margin=0.004)
    bpy.ops.object.mode_set(mode='OBJECT')
    mt = mat_sandstone()
    hi.data.materials.append(mt); lo.data.materials.append(mt)
    return {'high_tris': sum(len(p.vertices) - 2 for p in hi.data.polygons),
            'low_tris': sum(len(p.vertices) - 2 for p in lo.data.polygons), 'dims': tuple(round(x, 2) for x in lo.dimensions)}


# ---------------------------------------------------------------- greenery: fern
def build_fern(name='SM_Fern', seed=9):
    """A clump of arching fronds: brown-green stems with paired leaflets shrinking towards the tip."""
    rnd = random.Random(seed)
    bm = bmesh.new(); uv = bm.loops.layers.uv.new('UVMap'); col = bm.loops.layers.color.new('Col')
    def ao(p): return 0.45 + 0.55 * min(1.0, max(0.0, p.z) / 0.5)
    nf = 11
    for k in range(nf):
        a = TAU * k / nf + rnd.uniform(-0.25, 0.25); out = Vector((math.cos(a), math.sin(a), 0))
        L_ = rnd.uniform(0.75, 1.05); el = math.radians(rnd.uniform(20, 45))
        pts = bend_path(Vector((0, 0, -0.02)) + out * 0.03, out * math.sin(el) + Vector((0, 0, math.cos(el))), L_, 12, rnd, 0.55, 0.03)
        bark_tube(bm, uv, col, pts, [0.006 * (1 - 0.7 * i / 12) for i in range(13)], 4, ao)
        side = out.cross(Vector((0, 0, 1))).normalized()
        npair = 24
        for j in range(npair):
            t = 0.18 + 0.8 * j / npair
            f = t * 12; i = min(11, int(f)); p = pts[i].lerp(pts[i + 1], f - i)
            d = (pts[i + 1] - pts[i]).normalized()
            sz = 0.13 * math.sin(math.pi * min(1.0, (t - 0.1) / 0.95)) ** 0.7 + 0.015
            sh = ao(p) * rnd.uniform(0.85, 1.05)
            hue = rnd.uniform(-1, 1)
            shade = (sh * (0.95 + 0.08 * hue), sh * 1.05, sh * (0.8 - 0.1 * hue), 1)
            for sgn in (-1, 1):
                ld = (side * sgn + d * 0.55 + Vector((0, 0, -0.1))).normalized()
                upv = d.cross(ld).normalized() * sgn
                if upv.z < 0: upv = -upv
                petal(bm, uv, col, p, ld, upv, sz, sz * 0.26, shade, -0.15, 1)   # long, narrow leaflets
    return finish_mesh(name, bm, ['M_TreeBark', 'M_TreeLeaf'])


# ---------------------------------------------------------------- greenery: wildflower clump
def build_petal_tile():
    """One petal filling the UV square (U base -> tip): white with fine veins and a warm base; vertex colour tints it."""
    m, nt = new_mat('M_PetalTile')
    u, v = uv_sep(nt)
    dv = mth(nt, 'ABSOLUTE', mth(nt, 'SUBTRACT', v, 0.5))
    vein = smooth(nt, mth(nt, 'ABSOLUTE', mth(nt, 'SINE', mth(nt, 'MULTIPLY', mth(nt, 'DIVIDE', dv, mth(nt, 'ADD', u, 0.3)), 40.0))), 0.25, 0.0)
    uvn = nt.nodes.new('ShaderNodeUVMap')
    tn = nt.nodes.new('ShaderNodeTexNoise'); L(nt, uvn.outputs[0], tn.inputs['Vector']); tn.inputs['Scale'].default_value = 12; tn.inputs['Detail'].default_value = 5
    col = mix(nt, tn.outputs['Fac'], (0.72, 0.72, 0.70, 1), (0.85, 0.85, 0.83, 1))
    col = mix(nt, mth(nt, 'MULTIPLY', vein, 0.35), col, (0.55, 0.55, 0.55, 1))
    col = mix(nt, smooth(nt, u, 0.18, 0.0), col, (0.75, 0.55, 0.12, 1))        # warm base near the centre
    principled(nt, col, 0.45, mth(nt, 'SUBTRACT', 1.0, vein), 0.001, 0.4)
    return m


def petal(bm, uv, col, base, d, up, length, width, shade, cup=0.25, mat=2):
    side = d.cross(up).normalized(); nrm = side.cross(d).normalized()
    prof = [(0.0, 0.15), (0.35, 0.9), (0.75, 1.0), (1.0, 0.0)]
    rows = []
    for u_, w in prof:
        c = base + d * (u_ * length) + nrm * (cup * u_ * u_ * length)
        rows.append([(bm.verts.new(c + side * (s * w * width * 0.5) - nrm * (abs(s) * cup * 0.3 * w * width)), u_, 0.5 + s * w * 0.5)
                     for s in (-1, 0, 1)])
    for i in range(len(rows) - 1):
        for j in range(2):
            q = [rows[i][j], rows[i][j + 1], rows[i + 1][j + 1], rows[i + 1][j]]
            if i == len(rows) - 2: q = [rows[i][j], rows[i][j + 1], rows[i + 1][1]]
            f = bm.faces.new([x[0] for x in q]); f.material_index = mat; f.smooth = True
            for lp, x in zip(f.loops, q): lp[uv].uv = (x[1], x[2]); lp[col] = shade


FLOWER_TINTS = [(1.0, 0.82, 0.12), (0.62, 0.32, 0.95), (1.0, 1.0, 1.0), (1.0, 0.35, 0.25)]


def build_flowers(name='SM_Wildflowers', seed=17):
    """Knee-high wildflower clump: green stems, a few leaves, daisy-like heads in mixed colours."""
    rnd = random.Random(seed)
    bm = bmesh.new(); uv = bm.loops.layers.uv.new('UVMap'); col = bm.loops.layers.color.new('Col')
    def ao(p): return 0.55 + 0.45 * min(1.0, max(0.0, p.z) / 0.4)
    for k in range(22):
        a = rnd.uniform(0, TAU); r = 0.24 * math.sqrt(rnd.random())
        base = Vector((r * math.cos(a), r * math.sin(a), -0.02)); out = Vector((math.cos(a), math.sin(a), 0))
        H = rnd.uniform(0.22, 0.45)
        stem = bend_path(base, out * 0.25 + Vector((0, 0, 1)), H, 6, rnd, -0.02, 0.06)
        bark_tube(bm, uv, col, stem, [0.0035 * (1 - 0.4 * i / 6) for i in range(7)], 4, ao)
        for j in range(2):                                   # a couple of stem leaves
            p = stem[1 + j * 2]; la = rnd.uniform(0, TAU)
            ld = (Vector((math.cos(la), math.sin(la), 0.5))).normalized()
            leaf(bm, uv, col, p, ld, Vector((0, 0, 1)) if abs(ld.z) < 0.9 else Vector((1, 0, 0)), rnd.uniform(0.06, 0.09), (0.9, 1.0, 0.85, 1))
        for j in range(3):                                   # basal leaves around the foot
            la = rnd.uniform(0, TAU); ld = Vector((math.cos(la), math.sin(la), 0.35)).normalized()
            leaf(bm, uv, col, base + Vector((0, 0, 0.02)), ld, Vector((0, 0, 1)), rnd.uniform(0.09, 0.13), (0.8, 0.9, 0.75, 1))
        tip = stem[-1]; d = (stem[-1] - stem[-2]).normalized()
        face = (d + Vector((0, 0, 0.6)) + out * 0.3).normalized()
        n_, b_ = frame(face)
        tint = FLOWER_TINTS[rnd.randrange(len(FLOWER_TINTS))]
        np_ = rnd.choice([8, 10, 12]); pl = rnd.uniform(0.035, 0.05)
        for q in range(np_):
            th = TAU * q / np_ + rnd.uniform(-0.1, 0.1)
            pd = (n_ * math.cos(th) + b_ * math.sin(th) + face * 0.15).normalized()
            s = rnd.uniform(0.85, 1.05)
            petal(bm, uv, col, tip + pd * 0.006, pd, face, pl, pl * 0.42, (tint[0] * s, tint[1] * s, tint[2] * s, 1))
        # the centre: a small dome using the warm base of the petal texture
        ring = [bm.verts.new(tip + (n_ * math.cos(TAU * q / 8) + b_ * math.sin(TAU * q / 8)) * 0.008 + face * 0.002) for q in range(8)]
        top = bm.verts.new(tip + face * 0.008)
        for q in range(8):
            f = bm.faces.new([ring[q], ring[(q + 1) % 8], top]); f.material_index = 2; f.smooth = True
            for lp in f.loops: lp[uv].uv = (0.03, 0.5); lp[col] = (0.9, 0.7, 0.3, 1)
    # stems take the green middle of the leaf texture, leaves move to slot 0 too, petals to slot 1
    for f in bm.faces:
        if f.material_index == 0:
            for lp in f.loops: lp[uv].uv = (0.35 + (lp[uv].uv.y % 1.0) * 0.1, 0.28 + (lp[uv].uv.x % 1.0) * 0.04)
        f.material_index = 1 if f.material_index == 2 else 0
    return finish_mesh(name, bm, ['M_TreeLeaf', 'M_Petal'])


# ---------------------------------------------------------------- futuristic city: shared parts
def prism(bm, cx, cy, z0, z1, w, d, ch, mat, taper=1.0):
    """Box with chamfered vertical corners (8 sides), capped; `taper` scales the top."""
    def ring(z, s):
        hw, hd, c = w * 0.5 * s, d * 0.5 * s, ch * s
        pts = [(hw - c, -hd), (hw, -hd + c), (hw, hd - c), (hw - c, hd), (-hw + c, hd), (-hw, hd - c), (-hw, -hd + c), (-hw + c, -hd)]
        return [bm.verts.new((cx + x, cy + y, z)) for x, y in pts]
    a, b = ring(z0, 1.0), ring(z1, taper)
    fs = [bm.faces.new([a[i], a[(i + 1) % 8], b[(i + 1) % 8], b[i]]) for i in range(8)]
    fs += [bm.faces.new(b), bm.faces.new(list(reversed(a)))]
    for f in fs: f.material_index = mat
    return fs


def beam(bm, p0, p1, w, h, mat, up=Vector((0, 0, 1))):
    """Rectangular bar from p0 to p1."""
    d = (p1 - p0).normalized(); s = d.cross(up).normalized() * (w * 0.5); u = s.cross(d).normalized() * (h * 0.5)
    c = [s + u, -s + u, -s - u, s - u]
    a = [bm.verts.new(p0 + x) for x in c]; b = [bm.verts.new(p1 + x) for x in c]
    fs = [bm.faces.new([a[i], a[(i + 1) % 4], b[(i + 1) % 4], b[i]]) for i in range(4)]
    fs += [bm.faces.new(list(reversed(a))), bm.faces.new(b)]
    for f in fs: f.material_index = mat
    return fs


def finish_hard(name, bm, mats):
    """Mesh with its material slots (before faces), merged doubles, normals outward, smart-project UVs."""
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    me = bpy.data.meshes.new(name)
    for m in mats: me.materials.append(m)
    bm.to_mesh(me); bm.free()
    ob = link_new(name, me); select_only(ob)
    bpy.ops.object.shade_smooth_by_angle(angle=math.radians(35))
    for mod in list(ob.modifiers): bpy.ops.object.modifier_apply(modifier=mod.name)
    bpy.ops.object.mode_set(mode='EDIT'); bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.uv.smart_project(angle_limit=math.radians(60), island_margin=0.004)
    bpy.ops.object.mode_set(mode='OBJECT')
    return {'tris': sum(len(p.vertices) - 2 for p in me.polygons), 'dims': tuple(round(x, 2) for x in ob.dimensions)}


def mat_scifi_panel(name, base=(0.10, 0.11, 0.125, 1), panel=(1.6, 0.8)):
    """Painted metal cladding: large panels with dark seams, slight tone change per panel, worn edges, grime."""
    m, nt = new_mat(name); P, (px, py, pz), (nx, ny, nz) = obj_coords(nt)
    v = box_uv(nt, P, nx, ny)
    br = nt.nodes.new('ShaderNodeTexBrick'); L(nt, v, br.inputs['Vector'])
    br.inputs['Scale'].default_value = 1.0; br.inputs['Brick Width'].default_value = panel[0]; br.inputs['Row Height'].default_value = panel[1]
    br.inputs['Mortar Size'].default_value = 0.012; br.inputs['Mortar Smooth'].default_value = 0.2; br.offset = 0.0
    br.inputs['Color1'].default_value = base
    br.inputs['Color2'].default_value = tuple(min(1, c * 1.3) for c in base[:3]) + (1,)
    br.inputs['Mortar'].default_value = (0.02, 0.02, 0.025, 1)
    e = edge_mask(nt, 0.03)
    col = mix(nt, mth(nt, 'MULTIPLY', e, 0.6), br.outputs['Color'], (0.45, 0.46, 0.48, 1))   # bare metal on edges
    col, low = grime(nt, P, pz, col, 0.4, 0.4, (0.05, 0.045, 0.04, 1), 0.6)
    h = mth(nt, 'SUBTRACT', 1.0, br.outputs['Fac'])
    principled(nt, col, mth(nt, 'ADD', 0.32, mth(nt, 'MULTIPLY', low, 0.3)), h, 0.01)
    b = [n for n in nt.nodes if n.bl_idname == 'ShaderNodeBsdfPrincipled'][0]
    L(nt, e, b.inputs['Metallic'])
    return m


# ---------------------------------------------------------------- futuristic city: neon street light
def build_neon_lamp(name='SM_NeonLamp', seed=4):
    """5.6 m street light: slim faceted pole, a swept arm with a glowing strip underneath, a glow ring on the pole."""
    bm = bmesh.new()
    PANEL, GLASS, GLOW, CONC = 0, 1, 2, 3
    prism(bm, 0, 0, -0.1, 0.35, 0.6, 0.6, 0.15, CONC)                       # footing
    prism(bm, 0, 0, 0.35, 0.6, 0.36, 0.36, 0.1, PANEL, 0.7)                 # base collar
    prism(bm, 0, 0, 0.6, 5.4, 0.2, 0.2, 0.06, PANEL, 0.6)                   # pole
    prism(bm, 0, 0, 2.4, 2.5, 0.26, 0.26, 0.08, GLOW)                       # glow ring
    prism(bm, 0, 0, 1.0, 1.6, 0.16, 0.24, 0.04, GLASS)                      # little screen panel
    p0 = Vector((0, 0, 5.3)); p1 = Vector((0.9, 0, 5.7)); p2 = Vector((2.2, 0, 5.75))
    beam(bm, p0, p1, 0.16, 0.12, PANEL); beam(bm, p1 - Vector((0.05, 0, 0)), p2, 0.3, 0.1, PANEL)
    beam(bm, p1 + Vector((0.1, 0, -0.065)), p2 + Vector((-0.05, 0, -0.065)), 0.16, 0.03, GLOW)   # strip light underneath
    mats = [bpy.data.materials.get('MB_SciFi_Panel') or mat_scifi_panel('MB_SciFi_Panel'),
            bpy.data.materials.get('MB_SciFi_Glass') or mat_plain('MB_SciFi_Glass', (0.012, 0.02, 0.035, 1), 0.06, 0.05),
            bpy.data.materials.get('MB_SciFi_Glow') or mat_emit('MB_SciFi_Glow', (0.3, 0.9, 1.0)),
            bpy.data.materials.get('MB_SciFi_Concrete') or mat_concrete('MB_SciFi_Concrete', (0.36, 0.36, 0.37, 1))]
    return finish_hard(name, bm, mats)
