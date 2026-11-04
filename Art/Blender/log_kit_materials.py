"""Procedural materials for the river log kit (SM_LogTrunk, SM_LogCapA, SM_LogCapB).

Run inside Blender (Text Editor or the Blender MCP). Builds M_Bark, M_Wood and M_Fungus
and assigns them. The bark repeats every 1 m along the log's Y axis and all the way
around it, so the baked trunk texture tiles seamlessly in Unreal.
"""
import bpy, math
from mathutils import Vector

R = 0.34
def rad(th):
    return R * (1 + 0.030 * math.sin(3 * th + 1.0) + 0.018 * math.sin(5 * th + 2.3) + 0.010 * math.sin(9 * th + 0.4))

# ---- tag fungus vertices: x = distance out from the log (0 base .. 1 rim), y = 1 on the top side ----
def tag_fungus():
    o = bpy.data.objects['SM_LogCapB']; me = o.data
    F = [(math.radians(14), 0.13, 1.0), (math.radians(2), 0.21, 0.75), (math.radians(24), 0.25, 0.6), (math.radians(-10), 0.09, 0.55)]
    fv = set()
    for p in me.polygons:
        if p.material_index == 2:
            fv.update(p.vertices)
    att = me.attributes.get('fungus') or me.attributes.new('fungus', 'FLOAT_VECTOR', 'POINT')
    for vi in range(len(me.vertices)):
        att.data[vi].vector = (0, 0, 0)
    for vi in fv:
        co = me.vertices[vi].co
        best = None
        for th, y, sz in F:
            out = Vector((math.cos(th), 0, math.sin(th))); side = Vector((0, 1, 0)); up = out.cross(side).normalized()
            d = co - (out * rad(th) * 0.97 + Vector((0, y, 0)))
            lx = d.dot(out) / (0.075 * sz); ly = d.dot(side) / (0.10 * sz); lz = d.dot(up) / (0.10 * sz)
            err = abs(lx * lx + ly * ly + (lz / 0.30 if lz > 0 else lz / 0.12) ** 2 - 1)
            if best is None or err < best[0]:
                best = (err, lx, lz)
        _, lx, lz = best
        att.data[vi].vector = (max(0, lx), 1.0 if lz > 0.02 else 0.0, 0.0)

# ---- node helpers ----
def new_mat(name):
    m = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    m.use_nodes = True; nt = m.node_tree; nt.nodes.clear(); return m, nt

def link(nt, a, b): nt.links.new(a, b)

def mth(nt, op, a, b=None):
    n = nt.nodes.new('ShaderNodeMath'); n.operation = op
    for i, v in enumerate([a, b]):
        if v is None: continue
        if isinstance(v, (int, float)): n.inputs[i].default_value = v
        else: nt.links.new(v, n.inputs[i])
    return n.outputs[0]

def mix(nt, fac, a, b):
    n = nt.nodes.new('ShaderNodeMix'); n.data_type = 'RGBA'
    for sock, v in [(n.inputs[0], fac), (n.inputs[6], a), (n.inputs[7], b)]:
        if isinstance(v, (tuple, int, float)): sock.default_value = v
        else: nt.links.new(v, sock)
    return n.outputs[2]

def smooth(nt, x, a, b):
    n = nt.nodes.new('ShaderNodeMapRange'); n.interpolation_type = 'SMOOTHSTEP'
    nt.links.new(x, n.inputs['Value']); n.inputs['From Min'].default_value = a; n.inputs['From Max'].default_value = b
    return n.outputs[0]

def comb(nt, x, y, z):
    n = nt.nodes.new('ShaderNodeCombineXYZ')
    for i, v in enumerate([x, y, z]):
        if isinstance(v, (int, float)): n.inputs[i].default_value = v
        else: nt.links.new(v, n.inputs[i])
    return n.outputs[0]

def coords(nt):
    tc = nt.nodes.new('ShaderNodeTexCoord'); sx = nt.nodes.new('ShaderNodeSeparateXYZ'); link(nt, tc.outputs['Object'], sx.inputs[0])
    x, y, z = sx.outputs
    th = mth(nt, 'ARCTAN2', z, x)
    tw = mth(nt, 'MULTIPLY', y, 2 * math.pi)
    r = mth(nt, 'SQRT', mth(nt, 'ADD', mth(nt, 'MULTIPLY', x, x), mth(nt, 'MULTIPLY', z, z)))
    return dict(tc=tc, x=x, y=y, z=z, th=th, ct=mth(nt, 'COSINE', th), st=mth(nt, 'SINE', th),
                cy=mth(nt, 'COSINE', tw), sy=mth(nt, 'SINE', tw), r=r,
                up=mth(nt, 'DIVIDE', z, mth(nt, 'MAXIMUM', r, 0.001)))

def periodic(nt, c, ka, kb):
    """4D coordinates that wrap around the log (angle) and repeat every 1 m along it."""
    v = comb(nt, mth(nt, 'MULTIPLY', c['ct'], ka), mth(nt, 'MULTIPLY', c['st'], ka), mth(nt, 'MULTIPLY', c['cy'], kb))
    return v, mth(nt, 'MULTIPLY', c['sy'], kb)

def noise4(nt, v, w, scale, detail=4, rough=0.55):
    n = nt.nodes.new('ShaderNodeTexNoise'); n.noise_dimensions = '4D'
    link(nt, v, n.inputs['Vector']); link(nt, w, n.inputs['W'])
    n.inputs['Scale'].default_value = scale; n.inputs['Detail'].default_value = detail; n.inputs['Roughness'].default_value = rough
    return n

def voro4(nt, v, w, scale, feature='F1'):
    n = nt.nodes.new('ShaderNodeTexVoronoi'); n.voronoi_dimensions = '4D'; n.feature = feature
    link(nt, v, n.inputs['Vector']); link(nt, w, n.inputs['W']); n.inputs['Scale'].default_value = scale
    return n

def finish(nt, col, rough, height, dist, strength=1.0):
    b = nt.nodes.new('ShaderNodeBsdfPrincipled')
    link(nt, col, b.inputs['Base Color'])
    if isinstance(rough, (int, float)): b.inputs['Roughness'].default_value = rough
    else: link(nt, rough, b.inputs['Roughness'])
    bump = nt.nodes.new('ShaderNodeBump'); bump.inputs['Strength'].default_value = strength; bump.inputs['Distance'].default_value = dist
    link(nt, height, bump.inputs['Height']); link(nt, bump.outputs['Normal'], b.inputs['Normal'])
    out = nt.nodes.new('ShaderNodeOutputMaterial'); link(nt, b.outputs[0], out.inputs[0])

def build_bark():
    m, nt = new_mat('M_Bark'); c = coords(nt)
    v0, w0 = periodic(nt, c, 1.0, 0.16)          # for moss / lichen / colour noise
    v1, w1 = periodic(nt, c, 1.0, 0.05)          # bark ridges: ~8x longer than wide
    warp = noise4(nt, v0, w0, 2.0, 3, 0.5)
    wv = nt.nodes.new('ShaderNodeVectorMath'); wv.operation = 'MULTIPLY_ADD'
    link(nt, warp.outputs['Color'], wv.inputs[0]); wv.inputs[1].default_value = (0.18, 0.18, 0.04); link(nt, v1, wv.inputs[2])
    ww = mth(nt, 'ADD', w1, mth(nt, 'MULTIPLY', warp.outputs['Fac'], 0.02))
    plates = voro4(nt, wv.outputs[0], ww, 7.0, 'DISTANCE_TO_EDGE')
    fiss = smooth(nt, plates.outputs['Distance'], 0.0, 0.13)       # 0 in a crack, 1 on a ridge
    cell = voro4(nt, wv.outputs[0], ww, 7.0, 'F1')
    vf, wf = periodic(nt, c, 1.0, 0.02)
    fib = noise4(nt, vf, wf, 30.0, 6, 0.6)                        # fibrous streaks along the log
    grain = noise4(nt, v0, w0, 14.0, 8, 0.65)
    plate_col = mix(nt, cell.outputs['Color'], (0.070, 0.050, 0.034, 1), (0.130, 0.098, 0.070, 1))
    plate_col = mix(nt, mth(nt, 'MULTIPLY', grain.outputs['Fac'], 0.7), plate_col, (0.17, 0.15, 0.13, 1))
    inner = mix(nt, fib.outputs['Fac'], (0.020, 0.013, 0.009, 1), (0.075, 0.032, 0.016, 1))
    col = mix(nt, fiss, inner, plate_col)
    lic = voro4(nt, v0, w0, 26.0, 'F1')                            # lichen spots
    licm = mth(nt, 'MULTIPLY', smooth(nt, lic.outputs['Distance'], 0.20, 0.10), smooth(nt, grain.outputs['Fac'], 0.52, 0.62))
    col = mix(nt, mth(nt, 'MULTIPLY', licm, 0.8), col, (0.24, 0.26, 0.20, 1))
    mn = noise4(nt, v0, w0, 3.5, 6, 0.62)                          # patchy moss on top, creeping into cracks
    mi = mth(nt, 'ADD', c['up'], mth(nt, 'MULTIPLY', mth(nt, 'SUBTRACT', mn.outputs['Fac'], 0.5), 1.6))
    mi = mth(nt, 'ADD', mi, mth(nt, 'MULTIPLY', mth(nt, 'SUBTRACT', 1.0, fiss), 0.3))
    moss = smooth(nt, mi, 0.74, 0.98)
    col = mix(nt, moss, col, mix(nt, grain.outputs['Fac'], (0.030, 0.055, 0.010, 1), (0.085, 0.125, 0.025, 1)))
    h = mth(nt, 'ADD', fiss, mth(nt, 'MULTIPLY', fib.outputs['Fac'], 0.25))
    h = mth(nt, 'ADD', h, mth(nt, 'MULTIPLY', grain.outputs['Fac'], 0.2))
    h = mth(nt, 'ADD', h, mth(nt, 'MULTIPLY', moss, 0.6))
    finish(nt, col, mth(nt, 'ADD', 0.82, mth(nt, 'MULTIPLY', moss, 0.13)), h, 0.012)

def build_wood(name='M_Wood', broken=False):
    m, nt = new_mat(name); c = coords(nt)
    dn = nt.nodes.new('ShaderNodeTexNoise'); link(nt, c['tc'].outputs['Object'], dn.inputs['Vector']); dn.inputs['Scale'].default_value = 3.0
    rr = mth(nt, 'ADD', c['r'], mth(nt, 'MULTIPLY', mth(nt, 'SUBTRACT', dn.outputs['Fac'], 0.5), 0.03))
    ringl = smooth(nt, mth(nt, 'SINE', mth(nt, 'MULTIPLY', rr, 2 * math.pi * 65)), 0.35, 1.0)
    heart = smooth(nt, c['r'], 0.24, 0.17)
    base = mix(nt, heart, (0.40, 0.29, 0.17, 1), (0.27, 0.15, 0.075, 1))
    base = mix(nt, mth(nt, 'MULTIPLY', ringl, 0.55), base, (0.15, 0.085, 0.04, 1))
    # radial checks: 1D Voronoi edges around the angle give straight cracks from the rim inwards
    ck = nt.nodes.new('ShaderNodeTexVoronoi'); ck.voronoi_dimensions = '1D'; ck.feature = 'DISTANCE_TO_EDGE'
    wob = nt.nodes.new('ShaderNodeTexNoise'); link(nt, c['tc'].outputs['Object'], wob.inputs['Vector']); wob.inputs['Scale'].default_value = 12.0
    link(nt, mth(nt, 'ADD', c['th'], mth(nt, 'MULTIPLY', mth(nt, 'SUBTRACT', wob.outputs['Fac'], 0.5), 0.08)), ck.inputs['W']); ck.inputs['Scale'].default_value = 2.2
    cl = nt.nodes.new('ShaderNodeTexNoise'); cl.noise_dimensions = '1D'; link(nt, c['th'], cl.inputs['W']); cl.inputs['Scale'].default_value = 3.0
    reach = mth(nt, 'ADD', 0.12, mth(nt, 'MULTIPLY', cl.outputs['Fac'], 0.25))
    width = mth(nt, 'MULTIPLY', mth(nt, 'SUBTRACT', c['r'], reach), 0.12)
    crack = mth(nt, 'MULTIPLY', smooth(nt, mth(nt, 'SUBTRACT', ck.outputs['Distance'], width), 0.012, 0.0), smooth(nt, mth(nt, 'SUBTRACT', c['r'], reach), 0.0, 0.03))
    mp = nt.nodes.new('ShaderNodeMapping'); link(nt, c['tc'].outputs['Object'], mp.inputs['Vector']); mp.inputs['Scale'].default_value = (70, 3, 70)
    fn = nt.nodes.new('ShaderNodeTexNoise'); link(nt, mp.outputs[0], fn.inputs['Vector']); fn.inputs['Scale'].default_value = 1.0; fn.inputs['Detail'].default_value = 6
    splint = mix(nt, fn.outputs['Fac'], (0.17, 0.11, 0.06, 1), (0.40, 0.30, 0.18, 1))
    sn = nt.nodes.new('ShaderNodeSeparateXYZ'); link(nt, c['tc'].outputs['Normal'], sn.inputs[0])
    endf = smooth(nt, mth(nt, 'ABSOLUTE', sn.outputs[1]), 0.55, 0.9)   # 1 on the end face, 0 on splinter sides
    if broken:
        # torn, weathered wood: fibres everywhere, rings barely showing, damp dark centre
        wet = smooth(nt, c['r'], 0.16, 0.05)
        torn = mix(nt, mth(nt, 'MULTIPLY', ringl, 0.2), splint, (0.12, 0.075, 0.04, 1))
        torn = mix(nt, 0.35, torn, (0.16, 0.14, 0.12, 1))
        col = mix(nt, wet, torn, (0.035, 0.03, 0.02, 1))
        mn = nt.nodes.new('ShaderNodeTexNoise'); link(nt, c['tc'].outputs['Object'], mn.inputs['Vector']); mn.inputs['Scale'].default_value = 9
        mc = mth(nt, 'MULTIPLY', smooth(nt, c['r'], 0.13, 0.07), smooth(nt, mn.outputs['Fac'], 0.45, 0.6))
        col = mix(nt, mc, col, (0.05, 0.09, 0.015, 1))
        h = mth(nt, 'ADD', mth(nt, 'MULTIPLY', fn.outputs['Fac'], 1.0), mth(nt, 'MULTIPLY', ringl, 0.05))
        finish(nt, col, 0.85, h, 0.006)
        return
    col = mix(nt, endf, splint, base)
    col = mix(nt, crack, col, (0.06, 0.04, 0.025, 1))
    wn = nt.nodes.new('ShaderNodeTexNoise'); link(nt, c['tc'].outputs['Object'], wn.inputs['Vector']); wn.inputs['Scale'].default_value = 6
    col = mix(nt, mth(nt, 'MULTIPLY', smooth(nt, c['r'], 0.22, 0.34), 0.45), col, (0.20, 0.18, 0.15, 1))
    mossw = mth(nt, 'MULTIPLY', smooth(nt, mth(nt, 'ADD', c['up'], mth(nt, 'MULTIPLY', wn.outputs['Fac'], 0.6)), 0.95, 1.25), mth(nt, 'SUBTRACT', 1.0, endf))
    col = mix(nt, mossw, col, (0.05, 0.09, 0.02, 1))
    h = mth(nt, 'ADD', mth(nt, 'MULTIPLY', ringl, 0.15), mth(nt, 'MULTIPLY', fn.outputs['Fac'], 0.6))
    h = mth(nt, 'SUBTRACT', h, mth(nt, 'MULTIPLY', crack, 0.8))
    finish(nt, col, 0.75, h, 0.004)

def build_fungus():
    m, nt = new_mat('M_Fungus')
    at = nt.nodes.new('ShaderNodeAttribute'); at.attribute_name = 'fungus'
    sx = nt.nodes.new('ShaderNodeSeparateXYZ'); link(nt, at.outputs['Vector'], sx.inputs[0])
    d, top = sx.outputs[0], sx.outputs[1]
    fz = nt.nodes.new('ShaderNodeTexNoise'); fz.inputs['Scale'].default_value = 60
    bands = mth(nt, 'SINE', mth(nt, 'MULTIPLY', mth(nt, 'ADD', d, mth(nt, 'MULTIPLY', fz.outputs['Fac'], 0.06)), 26))
    tcol = mix(nt, smooth(nt, bands, -0.3, 0.6), (0.10, 0.04, 0.015, 1), (0.30, 0.13, 0.04, 1))
    tcol = mix(nt, smooth(nt, d, 0.78, 0.95), tcol, (0.62, 0.50, 0.30, 1))
    finish(nt, mix(nt, top, (0.55, 0.48, 0.36, 1), tcol), 0.6, mth(nt, 'MULTIPLY', bands, top), 0.002, 0.6)

def assign():
    for oname, mats in [('SM_LogTrunk', ['M_Bark']), ('SM_LogCapA', ['M_Bark', 'M_Wood']), ('SM_LogCapB', ['M_Bark', 'M_WoodBroken', 'M_Fungus'])]:
        # never clear the slots: that resets every face's material index to 0
        ob = bpy.data.objects[oname]
        while len(ob.data.materials) < len(mats): ob.data.materials.append(None)
        for i, mm in enumerate(mats): ob.data.materials[i] = bpy.data.materials[mm]

tag_fungus(); build_bark(); build_wood(); build_wood('M_WoodBroken', True); build_fungus(); assign()
