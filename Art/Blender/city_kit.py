"""City kit: skyline buildings built like real ones, for a near-photoreal look.

Run inside Blender 5.2 after real_kit.py (helpers, flat-tile baking):
    exec(open(<real_kit.py>).read()); exec(open(<this file>).read())
    bake_city_tiles(<out>)          # real-scale tiling textures + the room sheet
    for name, fn in CITY: fn()      # the buildings
    preview_materials(<out>)        # Blender look-alike of the Unreal materials
    export(<out>, [names]); write_material_recipe(<out>)

How it looks real:
  * Curtain walls are real geometry: aluminium mullions every ~1.5 m, recessed glass, spandrel panels at the
    slab, sills and heads, louvre bands on plant floors. Punched-window walls for the low-rise blocks.
  * Textures repeat at real scale (UVs in metres), not one stretched bake per building.
  * Every glass pane has its own UV cell (u = module around the building, v = floor), so the material can give
    each pane a random room (lit or dark, blinds), a slightly different tilt and tint.
"""
import bpy, bmesh, math, random, os, json
from mathutils import Vector

FH, SP, MOD = 3.6, 0.9, 1.5        # floor height, spandrel height, window module (metres)

# material slot name -> (tile, tint, metallic, roughness multiplier). Glass and accent are special.
CITY_MATS = {
    'M_CityFrame_Silver':   ('Metal', (0.75, 0.77, 0.80), 1.0, 1.0),
    'M_CityFrame_Bronze':   ('Metal', (0.40, 0.29, 0.19), 1.0, 1.1),
    'M_CityFrame_Dark':     ('Metal', (0.10, 0.10, 0.11), 1.0, 1.2),
    'M_CityFrame_White':    ('Metal', (0.82, 0.82, 0.80), 0.0, 1.4),
    'M_CitySpandrel_Grey':  ('Metal', (0.20, 0.22, 0.25), 0.6, 0.9),
    'M_CitySpandrel_Black': ('Metal', (0.045, 0.045, 0.05), 0.5, 0.7),
    'M_CitySpandrel_White': ('Metal', (0.78, 0.78, 0.76), 0.0, 1.3),
    'M_CitySpandrel_Stone': ('Stone', (1.0, 1.0, 1.0), 0.0, 1.0),
    'M_CityWall_Brick':     ('Brick', (0.72, 0.62, 0.58), 0.0, 1.0),
    'M_CityWall_Stone':     ('Stone', (0.92, 0.9, 0.86), 0.0, 1.0),
    'M_CityConcrete':       ('Concrete', (0.78, 0.78, 0.78), 0.0, 1.0),
    'M_CityRoof':           ('Roof', (1.0, 1.0, 1.0), 0.0, 1.0),
}
GLASS_TINTS = {'Blue': (0.55, 0.70, 0.86), 'Green': (0.60, 0.80, 0.76), 'Bronze': (0.80, 0.66, 0.52), 'Neutral': (0.74, 0.77, 0.80)}
ACCENT = (0.85, 0.92, 1.0)
UV_SCALE = {'Metal': 2.0, 'Stone': 3.0, 'Concrete': 4.0, 'Roof': 6.0, 'Brick': 2.0}


def xform(plan, s=1.0, r=0.0, c=(0.0, 0.0)):
    cr, sr = math.cos(r), math.sin(r)
    return [(c[0] + s * (x * cr - y * sr), c[1] + s * (x * sr + y * cr)) for x, y in plan]


def rect(w, d, ch=0.0):
    hw, hd = w / 2, d / 2
    if ch <= 0: return [(hw, -hd), (hw, hd), (-hw, hd), (-hw, -hd)]
    return [(hw - ch, -hd), (hw, -hd + ch), (hw, hd - ch), (hw - ch, hd), (-hw + ch, hd), (-hw, hd - ch), (-hw, -hd + ch), (-hw + ch, -hd)]


def circ(r, n, rot=0.0):
    return [(r * math.cos(rot + TAU * i / n), r * math.sin(rot + TAU * i / n)) for i in range(n)]


def edge_n(a, b):
    d = Vector((b[0] - a[0], b[1] - a[1], 0)).normalized()
    return d, Vector((d.y, -d.x, 0))


def offset(P, o):
    """Mitred offset of a CCW polygon (o > 0 grows it)."""
    n = len(P); out = []
    for i in range(n):
        _, n1 = edge_n(P[i - 1], P[i]); _, n2 = edge_n(P[i], P[(i + 1) % n])
        m = (n1 + n2).normalized(); k = o / max(0.3, m.dot(n1))
        out.append((P[i][0] + m.x * k, P[i][1] + m.y * k))
    return out


def V(p, z): return Vector((p[0], p[1], z))


class Bld:
    def __init__(s, name, frame, glass, spandrel, seed=1):
        s.name = name; s.bm = bmesh.new(); s.uv = s.bm.loops.layers.uv.new('UVMap'); s.slots = []
        s.rnd = random.Random(seed)
        s.FRAME = s.m('M_CityFrame_' + frame); s.GLASS = s.m('M_CityGlass_' + glass)
        s.SPAN = s.m(spandrel if spandrel.startswith('M_') else 'M_CitySpandrel_' + spandrel)
        s.CONC = s.m('M_CityConcrete'); s.ROOF = s.m('M_CityRoof')

    def m(s, name):
        if name not in s.slots: s.slots.append(name)
        return s.slots.index(name)

    def tile_of(s, mat):
        nm = s.slots[mat]
        return CITY_MATS[nm][0] if nm in CITY_MATS else 'Metal'

    def face(s, pts, mat, uvs=None):
        vs = [s.bm.verts.new(p) for p in pts]
        f = s.bm.faces.new(vs); f.material_index = mat
        if uvs is None:
            sc = UV_SCALE.get(s.tile_of(mat), 2.0)
            n = (vs[1].co - vs[0].co).cross(vs[-1].co - vs[0].co)
            if n.length < 1e-12: n = Vector((0, 0, 1))
            n.normalize()
            if abs(n.z) > 0.7: uvs = [(p[0] / sc, p[1] / sc) for p in pts]
            else:
                t = Vector((-n.y, n.x, 0)).normalized()
                uvs = [(Vector(p).dot(t) / sc, p[2] / sc) for p in pts]
        for lp, u in zip(f.loops, uvs): lp[s.uv].uv = u
        return f

    def ring_prism(s, Pb, Pt, zb, zt, mat, top=True, bottom=False):
        n = len(Pb)
        for i in range(n):
            j = (i + 1) % n
            s.face([V(Pb[i], zb), V(Pb[j], zb), V(Pt[j], zt), V(Pt[i], zt)], mat)
        if top: s.face([V(p, zt) for p in Pt], mat)
        if bottom: s.face([V(p, zb) for p in reversed(Pb)], mat)

    def box(s, pb, pt, t, n, w, d0, d1, mat, caps=True):
        """Bar from pb to pt; cross-section spans -w..w along t and d0..d1 along n."""
        ring = [(d0, -w), (d1, -w), (d1, w), (d0, w)]          # CCW in the (n, t) frame
        B = [pb + n * a + t * b for a, b in ring]; T = [pt + n * a + t * b for a, b in ring]
        for i in range(4):
            j = (i + 1) % 4
            s.face([B[i], B[j], T[j], T[i]], mat)
        if caps:
            s.face(T, mat); s.face(list(reversed(B)), mat)

    def finish(s):
        bmesh.ops.remove_doubles(s.bm, verts=s.bm.verts, dist=1e-4)
        me = bpy.data.meshes.new(s.name)
        for nm in s.slots:                                       # slots before faces
            me.materials.append(bpy.data.materials.get(nm) or bpy.data.materials.new(nm))
        s.bm.normal_update(); s.bm.to_mesh(me); s.bm.free()
        ob = link_new(s.name, me); select_only(ob)
        bpy.ops.object.shade_flat()
        return {'tris': sum(len(p.vertices) - 2 for p in me.polygons), 'dims': tuple(round(x, 1) for x in ob.dimensions),
                'slots': list(s.slots)}


# ---------------------------------------------------------------- facades
def curtain(B, plan, z0, nfl, fh=FH, sp=SP, mod=MOD, xf=lambda z: (1.0, 0.0), c=(0.0, 0.0), band_every=0,
            recess=0.14, mull=(0.04, -0.1, 0.16), fin_every=0, fin_depth=0.55, v0=0, mull_mat=None):
    """Glass curtain wall, one floor at a time (so it can taper and twist)."""
    mull_mat = B.FRAME if mull_mat is None else mull_mat
    P0 = xform(plan, *xf(z0), c); n = len(plan)
    counts = [max(1, round((Vector(P0[(k + 1) % n]) - Vector(P0[k])).length / mod)) for k in range(n)]
    for i in range(nfl):
        za, zb = z0 + i * fh, z0 + (i + 1) * fh
        Pa, Pb = xform(plan, *xf(za), c), xform(plan, *xf(zb), c)
        Ia, Ib = offset(Pa, -recess), offset(Pb, -recess)
        band = band_every and i % band_every == band_every - 1
        f = sp / fh; cum = 0
        for k in range(n):
            q = (k + 1) % n
            a0, a1, b0, b1 = V(Pa[k], za), V(Pa[q], za), V(Pb[k], zb), V(Pb[q], zb)
            g0, g1, h0, h1 = V(Ia[k], za), V(Ia[q], za), V(Ib[k], zb), V(Ib[q], zb)
            t, nrm = edge_n(Pa[k], Pa[q])
            if band:
                B.face([a0, a1, b1, b0], B.SPAN)
            else:
                s0, s1 = a0.lerp(b0, f), a1.lerp(b1, f)
                gs0, gs1 = g0.lerp(h0, f), g1.lerp(h1, f)
                if sp > 0: B.face([a0, a1, s1, s0], B.SPAN)
                B.face([s0, s1, gs1, gs0], B.FRAME)                       # sill
                cu = counts[k]
                B.face([gs0, gs1, h1, h0], B.GLASS, [(cum, v0 + i), (cum + cu, v0 + i), (cum + cu, v0 + i + 1), (cum, v0 + i + 1)])
                B.face([h0, h1, b1, b0], B.FRAME)                         # head
            for j in range(counts[k]):
                u = j / counts[k]
                deep = fin_every and j % fin_every == 0
                B.box(a0.lerp(a1, u), b0.lerp(b1, u), t, nrm, mull[0] * (1.6 if deep else 1), mull[1],
                      fin_depth if deep else mull[2], mull_mat, caps=False)
            cum += counts[k]
    return z0 + nfl * fh


def punched(B, plan, z0, nfl, wall, fh=3.3, mod=1.7, ww=0.95, wh=1.7, sill=0.85, depth=0.2, v0=0):
    """Masonry wall with punched windows (no taper)."""
    n = len(plan); cum = 0
    counts = [max(1, round((Vector(plan[(k + 1) % n]) - Vector(plan[k])).length / mod)) for k in range(n)]
    for i in range(nfl):
        za, zb = z0 + i * fh, z0 + (i + 1) * fh; zs, zh = za + sill, za + sill + wh; cum = 0
        for k in range(n):
            q = (k + 1) % n; t, nrm = edge_n(plan[k], plan[q]); r = -nrm * depth
            for j in range(counts[k]):
                p = V(plan[k], 0).lerp(V(plan[q], 0), j / counts[k])
                e = V(plan[k], 0).lerp(V(plan[q], 0), (j + 1) / counts[k])
                mid = (p + e) / 2; wl = mid - t * (ww / 2); wr = mid + t * (ww / 2)
                Z = lambda v, z: Vector((v.x, v.y, z))
                B.face([Z(p, za), Z(e, za), Z(e, zs), Z(p, zs)], wall)
                B.face([Z(p, zh), Z(e, zh), Z(e, zb), Z(p, zb)], wall)
                B.face([Z(p, zs), Z(wl, zs), Z(wl, zh), Z(p, zh)], wall)
                B.face([Z(wr, zs), Z(e, zs), Z(e, zh), Z(wr, zh)], wall)
                B.face([Z(wl, zs), Z(wr, zs), Z(wr, zs) + r, Z(wl, zs) + r], B.CONC)          # stone sill
                B.face([Z(wl, zh) + r, Z(wr, zh) + r, Z(wr, zh), Z(wl, zh)], wall)            # head
                B.face([Z(wl, zs), Z(wl, zs) + r, Z(wl, zh) + r, Z(wl, zh)], wall)            # jambs
                B.face([Z(wr, zh), Z(wr, zh) + r, Z(wr, zs) + r, Z(wr, zs)], wall)
                B.face([Z(wl, zs) + r, Z(wr, zs) + r, Z(wr, zh) + r, Z(wl, zh) + r], B.GLASS,
                       [(cum + j, v0 + i), (cum + j + 1, v0 + i), (cum + j + 1, v0 + i + 1), (cum + j, v0 + i + 1)])
                mz = (zs + zh) / 2                                                             # window frame
                B.box(Z(mid, zs) + r * 0.9, Z(mid, zh) + r * 0.9, t, nrm, 0.03, -0.03, 0.03, B.FRAME, False)
                B.box(Z(wl, mz) + r * 0.9, Z(wr, mz) + r * 0.9, Vector((0, 0, 1)), nrm, 0.025, -0.03, 0.03, B.FRAME, False)
            cum += counts[k]
    return z0 + nfl * fh


# ---------------------------------------------------------------- building parts
def plaza(B, plan, c=(0.0, 0.0), grow=5.0):
    P = xform(offset(plan, grow), 1, 0, c)
    B.ring_prism(P, P, -0.2, 0.15, B.CONC)


def lobby(B, plan, c=(0.0, 0.0), h=5.6, inset=1.4, xf0=(1.0, 0.0)):
    """Recessed double-height glass lobby under the tower, with columns and a concrete soffit."""
    outer = xform(plan, *xf0, c); inner = offset(outer, -inset)
    curtain(B, offset(plan, -inset), 0.15, 1, fh=h - 0.75, sp=0, mod=3.0, c=c, xf=lambda z: xf0, recess=0.1,
            mull=(0.06, -0.12, 0.2), v0=900)
    B.face([V(p, h - 0.6) for p in reversed(outer)], B.CONC)                # soffit (faces down)
    n = len(outer)
    for k in range(n):
        q = (k + 1) % n; t, nrm = edge_n(outer[k], outer[q])
        L = (Vector(outer[q]) - Vector(outer[k])).length; cnt = max(1, round(L / 7.0))
        for j in range(cnt):
            p = V(outer[k], 0).lerp(V(outer[q], 0), (j + 0.5) / cnt) - nrm * 0.45
            B.box(Vector((p.x, p.y, 0.15)), Vector((p.x, p.y, h - 0.6)), t, nrm, 0.35, -0.35, 0.35, B.SPAN, False)
    for k in range(n):
        q = (k + 1) % n
        B.face([V(outer[k], h - 0.6), V(outer[q], h - 0.6), V(outer[q], h), V(outer[k], h)], B.SPAN)
    return h


def roof(B, P, z, parapet=1.1, clutter=4, c=(0.0, 0.0)):
    """Roof deck, parapet with metal coping, and rooftop plant."""
    I = offset(P, -0.3); n = len(P)
    for k in range(n):
        q = (k + 1) % n
        B.face([V(P[k], z), V(P[q], z), V(P[q], z + parapet), V(P[k], z + parapet)], B.SPAN)
        B.face([V(I[q], z), V(I[k], z), V(I[k], z + parapet), V(I[q], z + parapet)], B.CONC)
        B.face([V(P[k], z + parapet), V(P[q], z + parapet), V(I[q], z + parapet), V(I[k], z + parapet)], B.FRAME)
    B.face([V(p, z + 0.05) for p in I], B.ROOF)
    cx = sum(p[0] for p in P) / n; cy = sum(p[1] for p in P) / n
    for _ in range(clutter):
        w = [B.rnd.random() for _ in range(n)]; sw = sum(w)
        x = cx + 0.45 * sum((P[i][0] - cx) * w[i] for i in range(n)) / sw * 1.6
        y = cy + 0.45 * sum((P[i][1] - cy) * w[i] for i in range(n)) / sw * 1.6
        kind = B.rnd.random()
        if kind < 0.6:
            a, b, h = B.rnd.uniform(1.5, 4), B.rnd.uniform(1.2, 3), B.rnd.uniform(1.2, 2.8)
            Pr = xform(rect(a, b), 1, B.rnd.uniform(0, 0.3), (x, y))
            B.ring_prism(Pr, Pr, z, z + h, B.FRAME)
        else:
            r = B.rnd.uniform(0.8, 1.5)
            Pc = circ(r, 12, 0); Pc = xform(Pc, 1, 0, (x, y))
            B.ring_prism(Pc, Pc, z, z + B.rnd.uniform(1.5, 2.5), B.CONC)
    return z + parapet


def spire(B, z, h, r0=0.6, c=(0.0, 0.0), accent=True):
    Pb = xform(circ(r0, 8), 1, 0, c); Pt = xform(circ(r0 * 0.15, 8), 1, 0, c)
    B.ring_prism(Pb, Pt, z, z + h, B.FRAME)
    if accent:
        A = B.m('M_CityAccent')
        for zz, rr in [(z + h * 0.35, r0 * 1.25), (z + h * 0.7, r0 * 0.8)]:
            P = xform(circ(rr, 12), 1, 0, c)
            B.ring_prism(P, P, zz, zz + 0.12, A)


# ---------------------------------------------------------------- the buildings
def build_city_needle(name='SM_CityNeedle'):
    B = Bld(name, 'Silver', 'Blue', 'Grey', 11)
    plan = circ(11.0, 8, math.pi / 8); nfl = 20
    plaza(B, plan); z0 = lobby(B, plan)
    top = z0 + nfl * FH
    xf = lambda zz: (1 - 0.42 * (zz - z0) / (top - z0), 0.0)
    z = curtain(B, plan, z0, nfl, xf=xf, band_every=8)
    z = roof(B, xform(plan, *xf(z)), z, 1.4, 3)
    spire(B, z - 1.0, 18.0, 0.7)
    return B.finish()


def build_city_twist(name='SM_CityTwist'):
    B = Bld(name, 'Dark', 'Neutral', 'Black', 12)
    plan = rect(18, 14, 2.5); nfl = 19
    plaza(B, plan, grow=4.5)
    z0 = lobby(B, plan, xf0=(1.0, math.radians(0)))
    top = z0 + nfl * FH
    xf = lambda zz: (1.0, math.radians(75) * (zz - z0) / (top - z0))
    z = curtain(B, plan, z0, nfl, xf=xf, fin_every=0)
    roof(B, xform(plan, *xf(z)), z, 2.2, 4)
    return B.finish()


def build_city_stepped(name='SM_CityStepped'):
    B = Bld(name, 'Bronze', 'Bronze', 'Stone', 13)
    tiers = [(26, 6), (20, 5), (15, 4), (10.5, 3)]
    plaza(B, rect(26, 26, 3)); z = lobby(B, rect(26, 26, 3))
    for i, (w, n) in enumerate(tiers):
        plan = rect(w, w, w * 0.12)
        z = curtain(B, plan, z, n, v0=i * 20, band_every=0 if i else 6)
        roof(B, plan, z, 1.0, 3 if i < 3 else 1)
    for x, y, h in [(0, 0, 16), (2.2, 1.4, 8), (-2.0, -1.6, 10)]:
        spire(B, z + 1.0, h, 0.35, (x, y), accent=(h == 16))
    return B.finish()


def build_city_cylinder(name='SM_CityCylinder'):
    B = Bld(name, 'White', 'Green', 'White', 14)
    plan = circ(9.5, 32); nfl = 16
    plaza(B, plan, grow=6); z = lobby(B, plan)
    z = curtain(B, plan, z, nfl, mod=1.6, band_every=6)
    zt = roof(B, plan, z, 1.2, 4)
    # crown: tall open frame of fins carrying a slim ring
    n = len(plan)
    for k in range(0, n, 2):
        t, nrm = edge_n(plan[k], plan[(k + 1) % n])
        p = V(plan[k], z)
        B.box(p, p + Vector((0, 0, 7.0)), t, nrm, 0.12, -0.3, 0.25, B.FRAME)
    P = offset(plan, 0.1)
    B.ring_prism(P, P, z + 7.0, z + 7.6, B.FRAME)
    A = B.m('M_CityAccent'); P2 = offset(plan, 0.12)
    B.ring_prism(P2, P2, z + 7.0, z + 7.1, A, top=False)
    return B.finish()


def build_city_twins(name='SM_CityTwins'):
    B = Bld(name, 'Silver', 'Blue', 'Grey', 15)
    plan = rect(13, 13, 1.8); nfl = 14
    plaza(B, rect(36, 18, 2), grow=4)
    for cx in (-10.0, 10.0):
        z = lobby(B, plan, (cx, 0))
        z = curtain(B, plan, z, nfl, c=(cx, 0), v0=int(cx), band_every=7)
        roof(B, xform(plan, 1, 0, (cx, 0)), z, 1.2, 3, (cx, 0))
    for fl in (5, 11):                                     # skybridges: two floors of glass between the towers
        zb = 5.6 + fl * FH
        bp = rect(7.6, 6.0)
        curtain(B, bp, zb, 2, sp=0.6, mod=1.9, v0=500 + fl)
        B.face([V(p, zb) for p in reversed(bp)], B.SPAN)
        B.face([V(p, zb + 2 * FH) for p in bp], B.ROOF)
    spire(B, 5.6 + nfl * FH + 1.2, 9.0, 0.4, (10.0, 0), accent=False)
    return B.finish()


def build_city_slab(name='SM_CitySlab'):
    B = Bld(name, 'Dark', 'Neutral', 'Grey', 16)
    plan = rect(34, 14); nfl = 10
    plaza(B, plan, grow=4); z = lobby(B, plan, inset=1.0)
    z = curtain(B, plan, z, nfl, fin_every=2, fin_depth=0.7)
    roof(B, plan, z, 1.3, 7)
    return B.finish()


def build_city_tiers(name='SM_CityTiers'):
    B = Bld(name, 'White', 'Blue', 'Stone', 17)
    tiers = [(22, 7), (17, 5), (12.5, 3)]
    plaza(B, rect(22, 22, 3)); z = lobby(B, rect(22, 22, 3))
    for i, (w, n) in enumerate(tiers):
        plan = rect(w, w, w * 0.18)
        z = curtain(B, plan, z, n, v0=i * 30)
        roof(B, plan, z, 1.1, 3)
    spire(B, z + 1.0, 11.0, 0.45)
    return B.finish()


def low_rise(name, w, d, nfl, wall, seed):
    B = Bld(name, 'Dark', 'Neutral', 'Black', seed)
    W = B.m(wall); plan = rect(w, d)
    B.ring_prism(xform(offset(plan, 3.0)), xform(offset(plan, 3.0)), -0.2, 0.15, B.CONC)    # pavement
    z = curtain(B, offset(plan, -0.3), 0.15, 1, fh=4.4, sp=0, mod=2.4, recess=0.1, mull=(0.05, -0.1, 0.12), v0=700)
    sign = offset(plan, 0.05)
    B.ring_prism(sign, sign, z, z + 0.9, B.SPAN, top=False)                 # blank fascia (no logos)
    aw = offset(plan, 1.2)
    B.ring_prism(aw, aw, z - 0.1, z + 0.05, B.FRAME)                        # awning
    B.face([V(p, z - 0.1) for p in reversed(aw)], B.FRAME)
    z = punched(B, plan, z + 0.9, nfl, W)
    corn = offset(plan, 0.35)
    B.ring_prism(corn, corn, z, z + 0.5, B.CONC, top=False)                 # cornice
    B.face([V(p, z) for p in reversed(corn)], B.CONC)
    roof(B, plan, z + 0.5, 0.6, 5)
    return B.finish()


def build_city_low_a(name='SM_CityLowA'): return low_rise(name, 17, 12, 5, 'M_CityWall_Brick', 21)
def build_city_low_b(name='SM_CityLowB'): return low_rise(name, 13, 13, 7, 'M_CityWall_Stone', 22)


CITY = [('SM_CityNeedle', build_city_needle), ('SM_CityTwist', build_city_twist), ('SM_CityStepped', build_city_stepped),
        ('SM_CityCylinder', build_city_cylinder), ('SM_CityTwins', build_city_twins), ('SM_CitySlab', build_city_slab),
        ('SM_CityTiers', build_city_tiers), ('SM_CityLowA', build_city_low_a), ('SM_CityLowB', build_city_low_b)]


# ---------------------------------------------------------------- real-scale tiling textures (seamless, neutral; tinted per material)
def tile_metal():
    """Anodised aluminium, brushed vertically. One tile = 2 m."""
    m, nt = new_mat('MT_CityMetal')
    v, w, _, _ = torus_coords(nt, 7.0, 0.3)
    br = n4(nt, v, w, 3.0, 6.0, 0.65)
    v2, w2, _, _ = torus_coords(nt, 1.0, 1.0)
    big = n4(nt, v2, w2, 2.5, 3.0, 0.5)
    col = mix(nt, br.outputs['Fac'], (0.52, 0.52, 0.52, 1), (0.64, 0.64, 0.64, 1))
    col = mix(nt, mth(nt, 'MULTIPLY', smooth(nt, big.outputs['Fac'], 0.5, 0.75), 0.45), col, (0.40, 0.40, 0.40, 1))
    principled(nt, col, mth(nt, 'ADD', 0.22, mth(nt, 'MULTIPLY', big.outputs['Fac'], 0.2)), br.outputs['Fac'], 0.0004, 0.3)
    return m


def tile_stone():
    """Honed limestone cladding. One tile = 3 m."""
    m, nt = new_mat('MT_CityStone')
    v, w, _, _ = torus_coords(nt, 1.0, 1.0)
    a = n4(nt, v, w, 3.0, 5.0, 0.55); b = n4(nt, v, w, 28.0, 8.0, 0.7)
    sp = n4(nt, v, w, 160.0, kind='ShaderNodeTexVoronoi', feature='F1')
    col = mix(nt, a.outputs['Fac'], (0.53, 0.50, 0.44, 1), (0.66, 0.63, 0.56, 1))
    col = mix(nt, mth(nt, 'MULTIPLY', b.outputs['Fac'], 0.35), col, (0.44, 0.41, 0.36, 1))
    col = mix(nt, mth(nt, 'MULTIPLY', smooth(nt, sp.outputs['Distance'], 0.10, 0.04), 0.6), col, (0.30, 0.28, 0.25, 1))
    principled(nt, col, mth(nt, 'ADD', 0.62, mth(nt, 'MULTIPLY', b.outputs['Fac'], 0.15)), b.outputs['Fac'], 0.0006, 0.5)
    return m


def tile_concrete():
    """Smooth architectural concrete with pores and soft rain streaks. One tile = 4 m."""
    m, nt = new_mat('MT_CityConcrete')
    v, w, _, _ = torus_coords(nt, 1.0, 1.0)
    a = n4(nt, v, w, 2.5, 5.0, 0.55); f = n4(nt, v, w, 40.0, 8.0, 0.7)
    po = n4(nt, v, w, 220.0, kind='ShaderNodeTexVoronoi', feature='F1')
    vs, ws, _, _ = torus_coords(nt, 9.0, 0.4)
    st = n4(nt, vs, ws, 2.0, 4.0, 0.5)
    col = mix(nt, a.outputs['Fac'], (0.36, 0.355, 0.34, 1), (0.47, 0.46, 0.44, 1))
    col = mix(nt, mth(nt, 'MULTIPLY', smooth(nt, st.outputs['Fac'], 0.55, 0.75), 0.4), col, (0.28, 0.275, 0.26, 1))
    pore = smooth(nt, po.outputs['Distance'], 0.09, 0.03)
    col = mix(nt, mth(nt, 'MULTIPLY', pore, 0.6), col, (0.18, 0.18, 0.17, 1))
    principled(nt, col, mth(nt, 'ADD', 0.78, mth(nt, 'MULTIPLY', f.outputs['Fac'], 0.12)), mth(nt, 'SUBTRACT', f.outputs['Fac'], pore), 0.0008, 0.5)
    return m


def tile_roof():
    """Roof gravel over membrane. One tile = 6 m."""
    m, nt = new_mat('MT_CityRoof')
    v, w, _, _ = torus_coords(nt, 1.0, 1.0)
    g = n4(nt, v, w, 90.0, kind='ShaderNodeTexVoronoi', feature='F1')
    a = n4(nt, v, w, 3.0, 4.0, 0.5)
    sep = nt.nodes.new('ShaderNodeSeparateColor'); L(nt, g.outputs['Color'], sep.inputs[0])
    col = mix(nt, sep.outputs[0], (0.13, 0.13, 0.13, 1), (0.30, 0.29, 0.27, 1))
    col = mix(nt, mth(nt, 'MULTIPLY', a.outputs['Fac'], 0.4), col, (0.10, 0.10, 0.10, 1))
    principled(nt, col, 0.92, smooth(nt, g.outputs['Distance'], 0.45, 0.0), 0.002, 0.7)
    return m


def tile_brick():
    """Running-bond brick, 250 x 62 mm with mortar. One tile = 2 m."""
    m, nt = new_mat('MT_CityBrick')
    uvn = nt.nodes.new('ShaderNodeUVMap')
    br = nt.nodes.new('ShaderNodeTexBrick'); L(nt, uvn.outputs[0], br.inputs['Vector'])
    br.inputs['Scale'].default_value = 1.0; br.inputs['Brick Width'].default_value = 0.125; br.inputs['Row Height'].default_value = 0.03125
    br.inputs['Mortar Size'].default_value = 0.0035; br.inputs['Mortar Smooth'].default_value = 0.4; br.offset = 0.5
    br.inputs['Color1'].default_value = (0.26, 0.09, 0.05, 1); br.inputs['Color2'].default_value = (0.38, 0.16, 0.09, 1)
    br.inputs['Mortar'].default_value = (0.42, 0.40, 0.36, 1)
    v, w, _, _ = torus_coords(nt, 1.0, 1.0)
    f = n4(nt, v, w, 70.0, 6.0, 0.7); s = n4(nt, v, w, 3.0, 4.0, 0.5)
    col = mix(nt, mth(nt, 'MULTIPLY', f.outputs['Fac'], 0.35), br.outputs['Color'], (0.17, 0.07, 0.04, 1))
    col = mix(nt, mth(nt, 'MULTIPLY', smooth(nt, s.outputs['Fac'], 0.5, 0.7), 0.35), col, (0.12, 0.10, 0.09, 1))
    h = mth(nt, 'ADD', mth(nt, 'SUBTRACT', 1.0, br.outputs['Fac']), mth(nt, 'MULTIPLY', f.outputs['Fac'], 0.15))
    principled(nt, col, mth(nt, 'ADD', 0.8, mth(nt, 'MULTIPLY', br.outputs['Fac'], 0.1)), h, 0.004, 1.0)
    return m


def tile_rooms(emissive=False):
    """4 x 4 sheet of office rooms seen through a window: walls, ceiling lights, desks, blinds.
    About 60% are lit. The emissive version is the glow mask (white = lit)."""
    m, nt = new_mat('MT_CityRooms' + ('E' if emissive else ''))
    uvn = nt.nodes.new('ShaderNodeUVMap')
    mp = nt.nodes.new('ShaderNodeMapping'); L(nt, uvn.outputs[0], mp.inputs['Vector']); mp.inputs['Scale'].default_value = (4, 4, 1)
    sx = nt.nodes.new('ShaderNodeSeparateXYZ'); L(nt, mp.outputs[0], sx.inputs[0])
    x, y = sx.outputs[0], sx.outputs[1]
    fx, fy = mth(nt, 'FLOOR', x), mth(nt, 'FLOOR', y)
    lx, ly = mth(nt, 'SUBTRACT', x, fx), mth(nt, 'SUBTRACT', y, fy)
    cv = nt.nodes.new('ShaderNodeCombineXYZ'); L(nt, fx, cv.inputs[0]); L(nt, fy, cv.inputs[1])
    wn = nt.nodes.new('ShaderNodeTexWhiteNoise'); wn.noise_dimensions = '3D'; L(nt, cv.outputs[0], wn.inputs['Vector'])
    rc = nt.nodes.new('ShaderNodeSeparateColor'); L(nt, wn.outputs['Color'], rc.inputs[0])
    r1, r2, r3 = rc.outputs[0], rc.outputs[1], wn.outputs['Value']
    lit = mth(nt, 'GREATER_THAN', r3, 0.4)
    wall = mix(nt, r1, (0.58, 0.50, 0.40, 1), (0.46, 0.50, 0.55, 1))
    ceil_ = smooth(nt, ly, 0.84, 0.86)
    col = mix(nt, ceil_, wall, (0.72, 0.72, 0.70, 1))
    sx2 = mth(nt, 'ABSOLUTE', mth(nt, 'SUBTRACT', mth(nt, 'FRACT', mth(nt, 'MULTIPLY', lx, 2.0)), 0.5))
    strip = mth(nt, 'MULTIPLY', mth(nt, 'MULTIPLY', smooth(nt, ly, 0.895, 0.9), smooth(nt, ly, 0.935, 0.93)), smooth(nt, sx2, 0.36, 0.33))
    col = mix(nt, strip, col, (1.0, 0.97, 0.9, 1))
    fl = smooth(nt, ly, 0.24, 0.2)
    col = mix(nt, fl, col, (0.16, 0.13, 0.11, 1))
    nz = nt.nodes.new('ShaderNodeTexNoise'); L(nt, mp.outputs[0], nz.inputs['Vector']); nz.inputs['Scale'].default_value = 3.0
    furn = mth(nt, 'MULTIPLY', mth(nt, 'MULTIPLY', smooth(nt, ly, 0.42, 0.38), smooth(nt, ly, 0.18, 0.22)), smooth(nt, nz.outputs['Fac'], 0.45, 0.55))
    col = mix(nt, furn, col, (0.08, 0.07, 0.07, 1))                                   # desks, chairs, screens
    dx = mth(nt, 'ABSOLUTE', mth(nt, 'SUBTRACT', lx, 0.5))
    depth = mth(nt, 'SUBTRACT', 1.0, mth(nt, 'MULTIPLY', mth(nt, 'POWER', mth(nt, 'MULTIPLY', dx, 2.0), 3.0), 0.5))
    col = mix(nt, mth(nt, 'SUBTRACT', 1.0, depth), col, (0.0, 0.0, 0.0, 1))          # darker towards the side walls
    blind_lv = mth(nt, 'SUBTRACT', 1.0, mth(nt, 'MULTIPLY', mth(nt, 'MULTIPLY', r2, r2), 0.75))
    blind = mth(nt, 'GREATER_THAN', ly, blind_lv)
    slat = mth(nt, 'ADD', 0.85, mth(nt, 'MULTIPLY', mth(nt, 'SINE', mth(nt, 'MULTIPLY', ly, 260.0)), 0.12))
    bm_ = nt.nodes.new('ShaderNodeMix'); bm_.data_type = 'RGBA'; bm_.blend_type = 'MULTIPLY'; bm_.inputs[0].default_value = 1.0
    bm_.inputs[6].default_value = (0.70, 0.68, 0.62, 1); L(nt, slat, bm_.inputs[7])
    col = mix(nt, blind, col, bm_.outputs[2])
    if emissive:
        e = mth(nt, 'MULTIPLY', lit, mth(nt, 'ADD', 0.55, mth(nt, 'MULTIPLY', strip, 0.45)))
        e = mth(nt, 'MULTIPLY', e, mth(nt, 'SUBTRACT', 1.0, mth(nt, 'MULTIPLY', blind, 0.35)))
        out = mix(nt, e, (0, 0, 0, 1), (1, 1, 1, 1))
    else:
        dim = mth(nt, 'ADD', 0.12, mth(nt, 'MULTIPLY', lit, 0.88))
        dim = mth(nt, 'MAXIMUM', dim, mth(nt, 'MULTIPLY', blind, 0.45))            # unlit rooms: blinds still catch daylight
        out = mix(nt, dim, (0, 0, 0, 1), col)
    principled(nt, out, 0.5)
    return m


TILES = [('Metal', tile_metal, 1024), ('Stone', tile_stone, 1024), ('Concrete', tile_concrete, 1024),
         ('Roof', tile_roof, 1024), ('Brick', tile_brick, 2048)]


def bake_color_only(mat, folder, fname, size):
    os.makedirs(folder, exist_ok=True)
    pl = flat_plane('BAKE_Plane'); pl.data.materials.append(mat); pl.location = (0, 0, -50)
    sc = bpy.context.scene; b = sc.render.bake
    b.use_selected_to_active = False; b.margin = 0; b.target = 'IMAGE_TEXTURES'
    select_only(pl)
    img = bake_image(fname, size)
    set_bake_target(pl, img); sc.cycles.samples = 1
    bpy.ops.object.bake(type='DIFFUSE', pass_filter={'COLOR'})
    save_png(img, folder, fname + '.png'); remove('BAKE_Plane')


def bake_city_tiles(folder):
    sc = bpy.context.scene; eng = sc.render.engine; sc.render.engine = 'CYCLES'
    out = []
    for nm, fn, size in TILES:
        out += bake_flat(fn(), folder, 'T_City' + nm, size)
    bake_color_only(tile_rooms(False), folder, 'T_CityRooms_BaseColor', 2048)
    bake_color_only(tile_rooms(True), folder, 'T_CityRooms_Emissive', 2048)
    sc.render.engine = eng
    return out + ['T_CityRooms_BaseColor.png', 'T_CityRooms_Emissive.png']


# ---------------------------------------------------------------- Blender look-alike of the Unreal materials
def _img(nt, folder, fname, non_color):
    n = nt.nodes.new('ShaderNodeTexImage')
    n.image = bpy.data.images.load(os.path.join(folder, fname), check_existing=True); n.image.reload()
    if non_color: n.image.colorspace_settings.name = 'Non-Color'
    return n


def city_tile_material(name, folder):
    tile, tint, metal, rmul = CITY_MATS[name]
    m, nt = new_mat(name)
    uvn = nt.nodes.new('ShaderNodeUVMap')
    c = _img(nt, folder, 'T_City%s_BaseColor.png' % tile, False); L(nt, uvn.outputs[0], c.inputs[0])
    r = _img(nt, folder, 'T_City%s_Roughness.png' % tile, True); L(nt, uvn.outputs[0], r.inputs[0])
    n = _img(nt, folder, 'T_City%s_Normal.png' % tile, True); L(nt, uvn.outputs[0], n.inputs[0])
    tm = nt.nodes.new('ShaderNodeMix'); tm.data_type = 'RGBA'; tm.blend_type = 'MULTIPLY'; tm.inputs[0].default_value = 1.0
    L(nt, c.outputs[0], tm.inputs[6]); tm.inputs[7].default_value = tint + (1,)
    b = nt.nodes.new('ShaderNodeBsdfPrincipled')
    L(nt, tm.outputs[2], b.inputs['Base Color']); b.inputs['Metallic'].default_value = metal
    L(nt, mth(nt, 'MINIMUM', mth(nt, 'MULTIPLY', r.outputs[0], rmul), 1.0), b.inputs['Roughness'])
    nm = nt.nodes.new('ShaderNodeNormalMap'); L(nt, n.outputs[0], nm.inputs['Color']); L(nt, nm.outputs[0], b.inputs['Normal'])
    o = nt.nodes.new('ShaderNodeOutputMaterial'); L(nt, b.outputs[0], o.inputs[0])
    return m


def city_glass_material(name, folder, glow=1.0):
    """Reflective coated glass; each pane (one UV cell) shows a random room from the sheet, with its own tilt."""
    tint = GLASS_TINTS[name.split('_')[-1]]
    m, nt = new_mat(name)
    uvn = nt.nodes.new('ShaderNodeUVMap'); sx = nt.nodes.new('ShaderNodeSeparateXYZ'); L(nt, uvn.outputs[0], sx.inputs[0])
    u, v = sx.outputs[0], sx.outputs[1]
    fu, fv = mth(nt, 'FLOOR', u), mth(nt, 'FLOOR', v)
    lu, lv = mth(nt, 'SUBTRACT', u, fu), mth(nt, 'SUBTRACT', v, fv)
    cv = nt.nodes.new('ShaderNodeCombineXYZ'); L(nt, fu, cv.inputs[0]); L(nt, fv, cv.inputs[1])
    wn = nt.nodes.new('ShaderNodeTexWhiteNoise'); wn.noise_dimensions = '3D'; L(nt, cv.outputs[0], wn.inputs['Vector'])
    rc = nt.nodes.new('ShaderNodeSeparateColor'); L(nt, wn.outputs['Color'], rc.inputs[0])
    r1, r2, r3 = rc.outputs[0], rc.outputs[1], rc.outputs[2]
    cell = mth(nt, 'FLOOR', mth(nt, 'MULTIPLY', wn.outputs['Value'], 15.999))
    cx = mth(nt, 'MODULO', cell, 4.0); cy = mth(nt, 'FLOOR', mth(nt, 'DIVIDE', cell, 4.0))
    au = mth(nt, 'DIVIDE', mth(nt, 'ADD', cx, mth(nt, 'ADD', 0.01, mth(nt, 'MULTIPLY', lu, 0.98))), 4.0)
    av = mth(nt, 'DIVIDE', mth(nt, 'ADD', cy, mth(nt, 'ADD', 0.01, mth(nt, 'MULTIPLY', lv, 0.98))), 4.0)
    ac = nt.nodes.new('ShaderNodeCombineXYZ'); L(nt, au, ac.inputs[0]); L(nt, av, ac.inputs[1])
    room = _img(nt, folder, 'T_CityRooms_BaseColor.png', False); L(nt, ac.outputs[0], room.inputs[0])
    mask = _img(nt, folder, 'T_CityRooms_Emissive.png', True); L(nt, ac.outputs[0], mask.inputs[0])
    room.interpolation = mask.interpolation = 'Closest'
    # each pane tilts a little, so reflections break up pane by pane
    h = mth(nt, 'ADD', mth(nt, 'MULTIPLY', mth(nt, 'SUBTRACT', r1, 0.5), lu), mth(nt, 'MULTIPLY', mth(nt, 'SUBTRACT', r2, 0.5), lv))
    bp = nt.nodes.new('ShaderNodeBump'); bp.inputs['Strength'].default_value = 0.8; bp.inputs['Distance'].default_value = 0.04
    L(nt, h, bp.inputs['Height'])
    tv = mth(nt, 'ADD', 0.9, mth(nt, 'MULTIPLY', r3, 0.2))
    tn = nt.nodes.new('ShaderNodeMix'); tn.data_type = 'RGBA'; tn.blend_type = 'MULTIPLY'; tn.inputs[0].default_value = 1.0
    tn.inputs[6].default_value = tint + (1,); L(nt, tv, tn.inputs[7])
    inside = nt.nodes.new('ShaderNodeMix'); inside.data_type = 'RGBA'; inside.blend_type = 'MULTIPLY'; inside.inputs[0].default_value = 1.0
    L(nt, room.outputs[0], inside.inputs[6]); L(nt, tn.outputs[2], inside.inputs[7])
    a = nt.nodes.new('ShaderNodeBsdfPrincipled')                 # the room is behind glass: barely lit by the sun outside
    a.inputs['Base Color'].default_value = (0.01, 0.01, 0.012, 1); a.inputs['Roughness'].default_value = 0.35
    L(nt, inside.outputs[2], a.inputs['Emission Color']); a.inputs['Emission Strength'].default_value = 0.35
    L(nt, bp.outputs[0], a.inputs['Normal'])
    g = nt.nodes.new('ShaderNodeBsdfPrincipled'); g.inputs['Metallic'].default_value = 1.0
    gm = nt.nodes.new('ShaderNodeMix'); gm.data_type = 'RGBA'; gm.blend_type = 'MULTIPLY'; gm.inputs[0].default_value = 1.0
    L(nt, tn.outputs[2], gm.inputs[6]); gm.inputs[7].default_value = (0.75, 0.75, 0.75, 1)
    L(nt, gm.outputs[2], g.inputs['Base Color'])
    L(nt, mth(nt, 'ADD', 0.015, mth(nt, 'MULTIPLY', r2, 0.04)), g.inputs['Roughness']); L(nt, bp.outputs[0], g.inputs['Normal'])
    lw = nt.nodes.new('ShaderNodeLayerWeight'); lw.inputs['Blend'].default_value = 0.3; L(nt, bp.outputs[0], lw.inputs['Normal'])
    fac = mth(nt, 'ADD', 0.30, mth(nt, 'MULTIPLY', lw.outputs['Fresnel'], 0.6))
    ms = nt.nodes.new('ShaderNodeMixShader'); L(nt, fac, ms.inputs[0]); L(nt, a.outputs[0], ms.inputs[1]); L(nt, g.outputs[0], ms.inputs[2])
    em = nt.nodes.new('ShaderNodeEmission')
    ec = nt.nodes.new('ShaderNodeMix'); ec.data_type = 'RGBA'; ec.blend_type = 'MULTIPLY'; ec.inputs[0].default_value = 1.0
    L(nt, room.outputs[0], ec.inputs[6]); L(nt, mask.outputs[0], ec.inputs[7]); L(nt, ec.outputs[2], em.inputs['Color'])
    gv = nt.nodes.new('ShaderNodeValue'); gv.name = 'ROOM_GLOW'; gv.outputs[0].default_value = glow
    L(nt, mth(nt, 'MULTIPLY', gv.outputs[0], mth(nt, 'SUBTRACT', 1.0, fac)), em.inputs['Strength'])
    ad = nt.nodes.new('ShaderNodeAddShader'); L(nt, ms.outputs[0], ad.inputs[0]); L(nt, em.outputs[0], ad.inputs[1])
    o = nt.nodes.new('ShaderNodeOutputMaterial'); L(nt, ad.outputs[0], o.inputs[0])
    return m


def preview_materials(folder, glow=0.4):
    for nm in CITY_MATS: city_tile_material(nm, folder)
    for t in GLASS_TINTS: city_glass_material('M_CityGlass_' + t, folder, glow)
    m, nt = new_mat('M_CityAccent')
    e = nt.nodes.new('ShaderNodeEmission'); e.inputs['Color'].default_value = ACCENT + (1,); e.inputs['Strength'].default_value = 8
    o = nt.nodes.new('ShaderNodeOutputMaterial'); L(nt, e.outputs[0], o.inputs[0])


def set_room_glow(v):
    for t in GLASS_TINTS:
        m = bpy.data.materials.get('M_CityGlass_' + t)
        if m: m.node_tree.nodes['ROOM_GLOW'].outputs[0].default_value = v


def write_material_recipe(folder):
    """Everything GameStation needs to build the Unreal materials, as JSON."""
    d = {'tiles_metres_per_uv': UV_SCALE,
         'materials': {nm: {'tile': t, 'tint': tint, 'metallic': met, 'roughness_mult': rm} for nm, (t, tint, met, rm) in CITY_MATS.items()},
         'glass': {('M_CityGlass_' + k): {'tint': v} for k, v in GLASS_TINTS.items()},
         'accent': {'M_CityAccent': {'emissive_color': ACCENT, 'strength': 8}},
         'glass_notes': 'Each glass pane is one UV cell (u = window module around the building, v = floor). '
                        'Hash floor(UV) to pick a room 0..15 from T_CityRooms (4x4 sheet) and a per-pane tilt/tint. '
                        'frac(UV) samples inside that room. Blend reflective glass over it with Fresnel (0.3 + 0.6*F). '
                        'Emissive = room colour x T_CityRooms_Emissive x glow (0 by day, about 3-6 at dusk).'}
    with open(os.path.join(folder, 'city_materials.json'), 'w') as f: json.dump(d, f, indent=1)
