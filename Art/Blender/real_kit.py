"""Realistic scenery test kit: SM_RockReal and SM_TreeReal.

Run inside Blender 5.2 (Text Editor or the Blender MCP), e.g. exec(open(<this file>).read()).
Each asset is a detailed high-poly sculpt with a procedural material, baked onto a lighter
game mesh as 2K textures (colour with baked shadowing, normal, roughness):
    build_rock(); bake_rock(<texture folder>)
    build_tree(); bake_tree_textures(<texture folder>)
    export(<fbx folder>)
"""
import bpy, bmesh, math, random, os
import numpy as np
from mathutils import Vector, noise

TAU = 2 * math.pi


# ---------------------------------------------------------------- helpers
def remove(name):
    o = bpy.data.objects.get(name)
    if o:
        me = o.data
        bpy.data.objects.remove(o)
        if me and me.users == 0:
            bpy.data.meshes.remove(me)


def link_new(name, me):
    remove(name)
    ob = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(ob)
    bpy.context.view_layer.update()
    return ob


def select_only(*obs):
    for o in bpy.context.view_layer.objects:
        if o: o.select_set(False)
    for o in obs: o.select_set(True)
    bpy.context.view_layer.objects.active = obs[-1]


def new_mat(name):
    m = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    m.use_nodes = True; nt = m.node_tree; nt.nodes.clear(); return m, nt


def L(nt, a, b): nt.links.new(a, b)


def mth(nt, op, a, b=None):
    n = nt.nodes.new('ShaderNodeMath'); n.operation = op
    for i, v in enumerate([a, b]):
        if v is None: continue
        if isinstance(v, (int, float)): n.inputs[i].default_value = v
        else: L(nt, v, n.inputs[i])
    return n.outputs[0]


def mix(nt, fac, a, b):
    n = nt.nodes.new('ShaderNodeMix'); n.data_type = 'RGBA'
    for s, v in [(n.inputs[0], fac), (n.inputs[6], a), (n.inputs[7], b)]:
        if isinstance(v, (tuple, int, float)): s.default_value = v
        else: L(nt, v, s)
    return n.outputs[2]


def smooth(nt, x, a, b):
    n = nt.nodes.new('ShaderNodeMapRange'); n.interpolation_type = 'SMOOTHSTEP'
    L(nt, x, n.inputs['Value']); n.inputs['From Min'].default_value = a; n.inputs['From Max'].default_value = b
    return n.outputs[0]


def tex(nt, kind, vec, scale, **kw):
    n = nt.nodes.new(kind)
    if vec is not None: L(nt, vec, n.inputs['Vector'])
    n.inputs['Scale'].default_value = scale
    for k, v in kw.items():
        if k in n.inputs: n.inputs[k].default_value = v
        else: setattr(n, k, v)
    return n


def principled(nt, col, rough, height=None, dist=0.002, strength=1.0):
    b = nt.nodes.new('ShaderNodeBsdfPrincipled')
    L(nt, col, b.inputs['Base Color'])
    if isinstance(rough, (int, float)): b.inputs['Roughness'].default_value = rough
    else: L(nt, rough, b.inputs['Roughness'])
    if height is not None:
        bp = nt.nodes.new('ShaderNodeBump'); bp.inputs['Strength'].default_value = strength; bp.inputs['Distance'].default_value = dist
        L(nt, height, bp.inputs['Height']); L(nt, bp.outputs['Normal'], b.inputs['Normal'])
    out = nt.nodes.new('ShaderNodeOutputMaterial'); L(nt, b.outputs[0], out.inputs[0])
    return b


def fbm(p, scale, octaves=5, seed=0):
    return noise.fractal(p * scale + Vector((seed * 7.1, seed * 3.3, seed * 1.7)), 0.5, 2.0, octaves, noise_basis='PERLIN_ORIGINAL')


# ---------------------------------------------------------------- rock
def rock_shape(p, planes, seed):
    """Ellipsoid cut by soft fracture planes, then weathered."""
    q = Vector((p.x * 0.62, p.y * 0.50, p.z * 0.40))
    q += q.normalized() * 0.06 * fbm(p, 1.3, 3, seed)
    for n, d in planes:
        s = q.dot(n) - d * (1 + 0.04 * fbm(p, 2.0, 2, seed + 3))
        if s > 0:
            q -= n * s * 0.93
    return q


def build_rock(name='SM_RockReal', seed=7):
    rnd = random.Random(seed)
    bm = bmesh.new()
    bmesh.ops.create_icosphere(bm, subdivisions=8, radius=1.0)
    planes = []
    for k in range(10):
        a = rnd.uniform(0, TAU); el = rnd.uniform(-0.15, 1.0)
        n = Vector((math.cos(a) * math.cos(el), math.sin(a) * math.cos(el), math.sin(el))).normalized()
        sup = math.sqrt((n.x * 0.62) ** 2 + (n.y * 0.50) ** 2 + (n.z * 0.40) ** 2)
        planes.append((n, sup * rnd.uniform(0.74, 0.9)))
    for v in bm.verts:
        v.co = rock_shape(v.co.copy(), planes, seed)
    bm.normal_update()
    # soften the fracture edges, like weathering does
    for _ in range(4):
        bmesh.ops.smooth_vert(bm, verts=bm.verts, factor=0.5, use_axis_x=True, use_axis_y=True, use_axis_z=True)
    bm.normal_update()
    for v in bm.verts:
        p = v.co
        d = 0.010 * fbm(p, 2.0, 6, seed + 11)                          # gentle undulation
        cell = noise.voronoi(p * 2.6 + Vector((seed, 0, 0)), distance_metric='DISTANCE')[0]
        crack = min(1.0, (cell[1] - cell[0]) / 0.035)                  # 0 on a crack line
        keep = max(0.0, min(1.0, (noise.noise(p * 1.7 + Vector((0, seed, 0))) + 0.05) * 3))
        d -= 0.016 * (1 - crack) ** 3 * keep                           # a few deep fractures
        d += 0.0012 * noise.noise(p * 60.0)                             # grain
        v.co = p + v.normal * d
    zmin = -0.13
    for v in bm.verts:                                                  # sits in the ground
        if v.co.z < zmin: v.co.z = zmin + (v.co.z - zmin) * 0.15
    me = bpy.data.meshes.new(name + '_High'); bm.to_mesh(me); bm.free()
    hi = link_new(name + '_High', me)
    for p in me.polygons: p.use_smooth = True
    hi.location = (0, 0, 0)
    # game mesh: decimated copy, unwrapped
    lo_me = me.copy(); lo_me.name = name
    lo = link_new(name, lo_me)
    select_only(lo)
    mod = lo.modifiers.new('dec', 'DECIMATE'); mod.ratio = 0.035
    bpy.ops.object.modifier_apply(modifier='dec')
    bpy.ops.object.mode_set(mode='EDIT'); bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.uv.smart_project(angle_limit=math.radians(55), island_margin=0.004)
    bpy.ops.object.mode_set(mode='OBJECT')
    build_rock_material()
    hi.data.materials.append(bpy.data.materials['M_RockReal'])
    lo.data.materials.append(bpy.data.materials['M_RockReal'])
    return {'high_tris': sum(len(p.vertices) - 2 for p in hi.data.polygons),
            'low_tris': sum(len(p.vertices) - 2 for p in lo.data.polygons)}


def build_rock_material():
    m, nt = new_mat('M_RockReal')
    tc = nt.nodes.new('ShaderNodeTexCoord'); P = tc.outputs['Object']
    sep = nt.nodes.new('ShaderNodeSeparateXYZ'); L(nt, tc.outputs['Normal'], sep.inputs[0]); nz = sep.outputs[2]
    sp = nt.nodes.new('ShaderNodeSeparateXYZ'); L(nt, P, sp.inputs[0]); pz = sp.outputs[2]
    big = tex(nt, 'ShaderNodeTexNoise', P, 2.2, Detail=6.0, Roughness=0.6)
    mid = tex(nt, 'ShaderNodeTexNoise', P, 9.0, Detail=8.0, Roughness=0.65)
    # granite: grey base with mineral speckle
    base = mix(nt, smooth(nt, big.outputs['Fac'], 0.35, 0.65), (0.13, 0.125, 0.115, 1), (0.30, 0.29, 0.27, 1))
    base = mix(nt, smooth(nt, mid.outputs['Fac'], 0.4, 0.7), base, (0.26, 0.225, 0.19, 1))
    sp1 = tex(nt, 'ShaderNodeTexVoronoi', P, 260.0)
    dark = smooth(nt, sp1.outputs['Distance'], 0.22, 0.12)
    bw = nt.nodes.new('ShaderNodeSeparateColor'); L(nt, sp1.outputs['Color'], bw.inputs[0])
    base = mix(nt, mth(nt, 'MULTIPLY', dark, smooth(nt, bw.outputs[0], 0.55, 0.75)), base, (0.05, 0.048, 0.045, 1))
    base = mix(nt, mth(nt, 'MULTIPLY', dark, smooth(nt, bw.outputs[1], 0.85, 0.95)), base, (0.55, 0.53, 0.50, 1))
    # crustose lichen: pale patches with a few orange spots
    ln = tex(nt, 'ShaderNodeTexNoise', P, 6.0, Detail=10.0, Roughness=0.7)
    lv = tex(nt, 'ShaderNodeTexVoronoi', P, 40.0)
    lich = mth(nt, 'MULTIPLY', smooth(nt, ln.outputs['Fac'], 0.56, 0.6), smooth(nt, lv.outputs['Distance'], 0.5, 0.2))
    lich = mth(nt, 'MULTIPLY', lich, smooth(nt, nz, -0.3, 0.3))
    col = mix(nt, mth(nt, 'MULTIPLY', lich, 0.85), base, mix(nt, mid.outputs['Fac'], (0.40, 0.42, 0.34, 1), (0.52, 0.53, 0.46, 1)))
    on = tex(nt, 'ShaderNodeTexNoise', P, 14.0, Detail=4.0)
    orange = mth(nt, 'MULTIPLY', smooth(nt, on.outputs['Fac'], 0.66, 0.70), smooth(nt, nz, 0.0, 0.5))
    col = mix(nt, orange, col, (0.50, 0.30, 0.07, 1))
    # moss on the top, creeping down in patches
    mn = tex(nt, 'ShaderNodeTexNoise', P, 3.2, Detail=8.0, Roughness=0.62)
    mf = tex(nt, 'ShaderNodeTexNoise', P, 120.0, Detail=3.0)
    mi = mth(nt, 'ADD', nz, mth(nt, 'MULTIPLY', mth(nt, 'SUBTRACT', mn.outputs['Fac'], 0.5), 1.8))
    mi = mth(nt, 'ADD', mi, mth(nt, 'MULTIPLY', mth(nt, 'SUBTRACT', mf.outputs['Fac'], 0.5), 0.5))
    moss = smooth(nt, mi, 0.80, 0.95)
    mcol = mix(nt, mf.outputs['Fac'], (0.018, 0.03, 0.006, 1), (0.07, 0.10, 0.022, 1))
    mcol = mix(nt, smooth(nt, mn.outputs['Fac'], 0.5, 0.7), mcol, (0.09, 0.09, 0.035, 1))
    col = mix(nt, moss, col, mcol)
    # rain streaks: long vertical darkening
    mp = nt.nodes.new('ShaderNodeMapping'); L(nt, P, mp.inputs['Vector']); mp.inputs['Scale'].default_value = (16, 16, 1.2)
    st = tex(nt, 'ShaderNodeTexNoise', mp.outputs[0], 1.0, Detail=4.0)
    col = mix(nt, mth(nt, 'MULTIPLY', smooth(nt, st.outputs['Fac'], 0.5, 0.75), 0.45), col, (0.06, 0.058, 0.052, 1))
    # earth stains near the ground
    dn = tex(nt, 'ShaderNodeTexNoise', P, 5.0, Detail=5.0)
    dirt = smooth(nt, mth(nt, 'ADD', pz, mth(nt, 'MULTIPLY', dn.outputs['Fac'], 0.12)), 0.03, -0.09)
    col = mix(nt, mth(nt, 'MULTIPLY', dirt, 0.85), col, (0.11, 0.085, 0.06, 1))
    rough = mth(nt, 'ADD', 0.78, mth(nt, 'ADD', mth(nt, 'MULTIPLY', moss, 0.17), mth(nt, 'MULTIPLY', dirt, 0.08)))
    h = mth(nt, 'ADD', mth(nt, 'MULTIPLY', mf.outputs['Fac'], mth(nt, 'MULTIPLY', moss, 0.8)), mth(nt, 'MULTIPLY', dark, -0.25))
    h = mth(nt, 'ADD', h, mth(nt, 'MULTIPLY', lich, 0.3))
    principled(nt, col, rough, h, 0.0015)
    return m


# ---------------------------------------------------------------- baking
def bake_image(name, size, non_color=False):
    img = bpy.data.images.get(name)
    if img: bpy.data.images.remove(img)
    img = bpy.data.images.new(name, size, size, alpha=False, float_buffer=False)
    if non_color: img.colorspace_settings.name = 'Non-Color'
    return img


def set_bake_target(lo, img):
    """The low mesh's own material gets an image node selected as the bake target."""
    for slot in lo.material_slots:
        nt = slot.material.node_tree
        n = nt.nodes.get('BAKE_TARGET') or nt.nodes.new('ShaderNodeTexImage')
        n.name = 'BAKE_TARGET'; n.image = img
        nt.nodes.active = n


def bake(kind, hi, lo, img, extrusion, samples=4, pass_filter=None):
    sc = bpy.context.scene
    sc.cycles.samples = samples
    set_bake_target(lo, img)
    hi.hide_render = False; lo.hide_render = False
    select_only(hi, lo)
    b = sc.render.bake
    b.use_selected_to_active = True; b.cage_extrusion = extrusion; b.max_ray_distance = extrusion * 2
    b.margin = 8; b.target = 'IMAGE_TEXTURES'
    kw = {}
    if pass_filter is not None: kw['pass_filter'] = pass_filter
    bpy.ops.object.bake(type=kind, **kw)


def save_png(img, folder, fname):
    img.filepath_raw = os.path.join(folder, fname); img.file_format = 'PNG'; img.save()


def bake_set(hi, lo, folder, prefix, size=2048, extrusion=0.03, ao_strength=0.65, rough_from=None):
    """Bake colour (with ambient-occlusion shadowing multiplied in), normal and roughness."""
    os.makedirs(folder, exist_ok=True)
    col = bake_image(prefix + '_BaseColor', size)
    bake('DIFFUSE', hi, lo, col, extrusion, 1, {'COLOR'})
    ao = bake_image(prefix + '_AO', size, True)
    bake('AO', hi, lo, ao, extrusion, 64)
    c = np.array(col.pixels[:]).reshape(-1, 4); a = np.array(ao.pixels[:]).reshape(-1, 4)[:, :1]
    c[:, :3] *= (1 - ao_strength) + ao_strength * a
    col.pixels[:] = c.ravel()
    save_png(col, folder, prefix + '_BaseColor.png')
    nrm = bake_image(prefix + '_Normal', size, True)
    bake('NORMAL', hi, lo, nrm, extrusion, 1)
    save_png(nrm, folder, prefix + '_Normal.png')
    rgh = bake_image(prefix + '_Roughness', size, True)
    bake('ROUGHNESS', hi, lo, rgh, extrusion, 1)
    save_png(rgh, folder, prefix + '_Roughness.png')
    return [prefix + s for s in ('_BaseColor.png', '_Normal.png', '_Roughness.png')]


def bake_rock(folder, size=2048):
    hi = bpy.data.objects['SM_RockReal_High']; lo = bpy.data.objects['SM_RockReal']
    return bake_set(hi, lo, folder, 'T_RockReal', size, 0.04)


def game_material(name, folder, prefix, two_sided=False):
    """Preview material built only from the baked textures: what Unreal will show."""
    m, nt = new_mat(name)
    def img(suffix, non_color):
        n = nt.nodes.new('ShaderNodeTexImage')
        n.image = bpy.data.images.load(os.path.join(folder, prefix + suffix), check_existing=True)
        n.image.reload()
        if non_color: n.image.colorspace_settings.name = 'Non-Color'
        return n
    b = nt.nodes.new('ShaderNodeBsdfPrincipled')
    L(nt, img('_BaseColor.png', False).outputs[0], b.inputs['Base Color'])
    L(nt, img('_Roughness.png', True).outputs[0], b.inputs['Roughness'])
    nm = nt.nodes.new('ShaderNodeNormalMap'); L(nt, img('_Normal.png', True).outputs[0], nm.inputs['Color'])
    L(nt, nm.outputs[0], b.inputs['Normal'])
    out = nt.nodes.new('ShaderNodeOutputMaterial'); L(nt, b.outputs[0], out.inputs[0])
    return m


def use_game_material(ob, mat):
    ob.data.materials[0] = mat


# ---------------------------------------------------------------- flat tiling textures (bark, leaf)
def flat_plane(name):
    remove(name)
    bm = bmesh.new()
    vs = [bm.verts.new(c) for c in [(0, 0, 0), (1, 0, 0), (1, 1, 0), (0, 1, 0)]]
    f = bm.faces.new(vs); uv = bm.loops.layers.uv.new('UVMap')
    for lp, c in zip(f.loops, [(0, 0), (1, 0), (1, 1), (0, 1)]): lp[uv].uv = c
    me = bpy.data.meshes.new(name); bm.to_mesh(me); bm.free()
    return link_new(name, me)


def bake_flat(mat, folder, prefix, size):
    """Bake a material onto a unit plane: tangent-space normal from its bump, colour, roughness."""
    os.makedirs(folder, exist_ok=True)
    pl = flat_plane('BAKE_Plane'); pl.data.materials.append(mat); pl.location = (0, 0, -50)
    sc = bpy.context.scene; b = sc.render.bake
    b.use_selected_to_active = False; b.margin = 0; b.target = 'IMAGE_TEXTURES'
    select_only(pl)
    out = []
    for kind, suffix, nc, kw in [('DIFFUSE', '_BaseColor', False, {'pass_filter': {'COLOR'}}), ('NORMAL', '_Normal', True, {}),
                                 ('ROUGHNESS', '_Roughness', True, {})]:
        img = bake_image(prefix + suffix, size, nc)
        set_bake_target(pl, img); sc.cycles.samples = 1
        bpy.ops.object.bake(type=kind, **kw)
        save_png(img, folder, prefix + suffix + '.png'); out.append(prefix + suffix + '.png')
    remove('BAKE_Plane')
    return out


def torus_coords(nt, ka, kb):
    """4D coordinates from UV that wrap in both U and V, so the baked texture tiles seamlessly."""
    uvn = nt.nodes.new('ShaderNodeUVMap'); sx = nt.nodes.new('ShaderNodeSeparateXYZ'); L(nt, uvn.outputs[0], sx.inputs[0])
    a = mth(nt, 'MULTIPLY', sx.outputs[0], TAU); b = mth(nt, 'MULTIPLY', sx.outputs[1], TAU)
    c = nt.nodes.new('ShaderNodeCombineXYZ')
    L(nt, mth(nt, 'MULTIPLY', mth(nt, 'COSINE', a), ka), c.inputs[0])
    L(nt, mth(nt, 'MULTIPLY', mth(nt, 'SINE', a), ka), c.inputs[1])
    L(nt, mth(nt, 'MULTIPLY', mth(nt, 'COSINE', b), kb), c.inputs[2])
    return c.outputs[0], mth(nt, 'MULTIPLY', mth(nt, 'SINE', b), kb), sx.outputs[0], sx.outputs[1]


def n4(nt, v, w, scale, detail=4.0, rough=0.55, kind='ShaderNodeTexNoise', feature=None):
    n = nt.nodes.new(kind)
    if kind == 'ShaderNodeTexNoise':
        n.noise_dimensions = '4D'; n.inputs['Detail'].default_value = detail; n.inputs['Roughness'].default_value = rough
    else:
        n.voronoi_dimensions = '4D'
        if feature: n.feature = feature
    L(nt, v, n.inputs['Vector']); L(nt, w, n.inputs['W']); n.inputs['Scale'].default_value = scale
    return n


def build_bark_tile():
    """Furrowed broadleaf bark (ash/oak-like): long interlacing ridges, grey-brown, lichen flecks."""
    m, nt = new_mat('M_BarkTile')
    v0, w0, _, _ = torus_coords(nt, 1.0, 1.0)
    v1, w1, _, _ = torus_coords(nt, 1.0, 0.22)                  # ridges ~4.5x longer than wide
    warp = n4(nt, v0, w0, 1.5, 3, 0.5)
    wv = nt.nodes.new('ShaderNodeVectorMath'); wv.operation = 'MULTIPLY_ADD'
    L(nt, warp.outputs['Color'], wv.inputs[0]); wv.inputs[1].default_value = (0.35, 0.35, 0.08); L(nt, v1, wv.inputs[2])
    plates = n4(nt, wv.outputs[0], w1, 2.6, kind='ShaderNodeTexVoronoi', feature='DISTANCE_TO_EDGE')
    ridge = smooth(nt, plates.outputs['Distance'], 0.0, 0.16)   # 0 in a furrow
    cell = n4(nt, wv.outputs[0], w1, 2.6, kind='ShaderNodeTexVoronoi', feature='F1')
    v2, w2, _, _ = torus_coords(nt, 1.0, 0.12)
    fib = n4(nt, v2, w2, 12.0, 6, 0.65)                         # vertical fibres on the ridges
    grain = n4(nt, v0, w0, 6.0, 8, 0.65)
    rc = mix(nt, cell.outputs['Color'], (0.075, 0.07, 0.062, 1), (0.14, 0.13, 0.115, 1))
    rc = mix(nt, mth(nt, 'MULTIPLY', fib.outputs['Fac'], 0.6), rc, (0.19, 0.18, 0.165, 1))
    furrow = mix(nt, grain.outputs['Fac'], (0.025, 0.018, 0.012, 1), (0.07, 0.045, 0.028, 1))
    col = mix(nt, ridge, furrow, rc)
    lic = n4(nt, v0, w0, 9.0, kind='ShaderNodeTexVoronoi', feature='F1')
    lm = mth(nt, 'MULTIPLY', smooth(nt, lic.outputs['Distance'], 0.22, 0.12), smooth(nt, grain.outputs['Fac'], 0.5, 0.6))
    col = mix(nt, mth(nt, 'MULTIPLY', lm, ridge), col, (0.26, 0.29, 0.23, 1))
    green = n4(nt, v0, w0, 2.0, 5, 0.6)                         # faint algae in the furrows
    col = mix(nt, mth(nt, 'MULTIPLY', smooth(nt, green.outputs['Fac'], 0.5, 0.65), mth(nt, 'SUBTRACT', 1.0, ridge)), col, (0.05, 0.07, 0.025, 1))
    h = mth(nt, 'ADD', mth(nt, 'POWER', ridge, 0.6), mth(nt, 'MULTIPLY', fib.outputs['Fac'], 0.25))
    h = mth(nt, 'ADD', h, mth(nt, 'MULTIPLY', grain.outputs['Fac'], 0.12))
    principled(nt, col, mth(nt, 'ADD', 0.80, mth(nt, 'MULTIPLY', ridge, -0.1)), h, 0.02, 1.0)
    return m


def build_leaf_tile():
    """One leaf filling the UV square (U along the midrib): veins, colour shading, slightly paler edge."""
    m, nt = new_mat('M_LeafTile')
    uvn = nt.nodes.new('ShaderNodeUVMap'); sx = nt.nodes.new('ShaderNodeSeparateXYZ'); L(nt, uvn.outputs[0], sx.inputs[0])
    u, v = sx.outputs[0], sx.outputs[1]
    dv = mth(nt, 'ABSOLUTE', mth(nt, 'SUBTRACT', v, 0.5))       # distance from the midrib
    mid = smooth(nt, dv, 0.012, 0.0)
    # secondary veins run from the midrib towards the tip at an angle
    ph = mth(nt, 'SUBTRACT', mth(nt, 'MULTIPLY', u, 9.0), mth(nt, 'MULTIPLY', dv, 7.0))
    vein = smooth(nt, mth(nt, 'ABSOLUTE', mth(nt, 'SINE', mth(nt, 'MULTIPLY', ph, math.pi))), 0.10, 0.0)
    vein = mth(nt, 'MULTIPLY', vein, smooth(nt, dv, 0.46, 0.2))
    tn = nt.nodes.new('ShaderNodeTexNoise'); L(nt, uvn.outputs[0], tn.inputs['Vector']); tn.inputs['Scale'].default_value = 40; tn.inputs['Detail'].default_value = 6
    cell = nt.nodes.new('ShaderNodeTexVoronoi'); L(nt, uvn.outputs[0], cell.inputs['Vector']); cell.inputs['Scale'].default_value = 60
    cell.feature = 'DISTANCE_TO_EDGE'
    tert = smooth(nt, cell.outputs['Distance'], 0.05, 0.0)    # fine vein network
    base = mix(nt, tn.outputs['Fac'], (0.08, 0.16, 0.025, 1), (0.15, 0.25, 0.05, 1))
    base = mix(nt, smooth(nt, dv, 0.25, 0.5), base, (0.18, 0.26, 0.06, 1))
    col = mix(nt, mth(nt, 'MULTIPLY', tert, 0.25), base, (0.13, 0.22, 0.05, 1))
    col = mix(nt, mth(nt, 'MAXIMUM', mid, mth(nt, 'MULTIPLY', vein, 0.7)), col, (0.22, 0.30, 0.10, 1))
    h = mth(nt, 'SUBTRACT', 1.0, mth(nt, 'MAXIMUM', mid, mth(nt, 'MAXIMUM', vein, mth(nt, 'MULTIPLY', tert, 0.4))))
    principled(nt, col, mth(nt, 'ADD', 0.45, mth(nt, 'MULTIPLY', tn.outputs['Fac'], 0.15)), h, 0.002, 0.6)
    return m


# ---------------------------------------------------------------- tree
BARK_W = 0.6        # metres of bark one texture tile covers


def frame(t):
    up = Vector((0, 0, 1)) if abs(t.z) < 0.95 else Vector((1, 0, 0))
    n = t.cross(up).normalized(); return n, t.cross(n).normalized()


def bark_tube(bm, uv, col, path, radii, seg, ao, flare=False):
    """Bark tube with UVs that tile the bark texture; ao(point) gives a vertex shade."""
    circ = TAU * radii[0]
    k = max(1, round(circ / BARK_W))
    vs_per_m = k / circ
    rings = []; s = 0.0; n_prev = None
    for i, p in enumerate(path):
        t = (path[min(i + 1, len(path) - 1)] - path[max(i - 1, 0)]).normalized()
        if n_prev is None: n, b = frame(t)
        else:
            n = (n_prev - t * n_prev.dot(t)).normalized(); b = t.cross(n)
        n_prev = n
        if i: s += (p - path[i - 1]).length
        ring = []
        for j in range(seg + 1):
            a = TAU * j / seg; r = radii[i]
            if flare:
                r *= 1 + 0.9 * math.exp(-max(p.z, 0) * 9) * (0.75 + 0.25 * math.sin(5 * a + 0.7))
            ring.append((bm.verts.new(p + (n * math.cos(a) + b * math.sin(a)) * r), j / seg * k, s * vs_per_m))
        rings.append(ring)
    for i in range(len(rings) - 1):
        for j in range(seg):
            q = [rings[i][j], rings[i][j + 1], rings[i + 1][j + 1], rings[i + 1][j]]
            f = bm.faces.new([x[0] for x in q]); f.material_index = 0; f.smooth = True
            for lp, x in zip(f.loops, q):
                lp[uv].uv = (x[1], x[2]); sh = ao(lp.vert.co); lp[col] = (sh, sh, sh, 1)


def bend_path(start, d, length, n, rnd, droop, wobble):
    pts = [start.copy()]; p = start.copy(); d = d.normalized()
    for i in range(n):
        d = (d + Vector((rnd.uniform(-1, 1), rnd.uniform(-1, 1), rnd.uniform(-1, 1))) * wobble
             + Vector((0, 0, -droop * (i + 1) / n))).normalized()
        p = p + d * (length / n); pts.append(p.copy())
    return pts


def leaf(bm, uv, col, base, d, up, size, shade):
    """A leaf: pointed oval with a folded midrib, curving down towards the tip."""
    side = d.cross(up).normalized(); nrm = side.cross(d).normalized()
    prof = [(0.0, 0.0), (0.3, 0.58), (0.66, 0.48), (1.0, 0.0)]
    pts = {}
    for i, (u, w) in enumerate(prof):
        c = base + d * (u * size) + nrm * (-0.18 * u * u * size)
        pts[(i, 0)] = (bm.verts.new(c), u, 0.5)
        if 0 < i < len(prof) - 1:
            for sgn in (-1, 1):
                off = side * (sgn * w * 0.5 * size) - nrm * (0.06 * w * size)   # folded along the midrib
                pts[(i, sgn)] = (bm.verts.new(c + off), u, 0.5 + sgn * w * 0.5)
    last = len(prof) - 1
    polys = []
    for sgn in (-1, 1):
        polys.append([pts[(0, 0)], pts[(1, sgn)], pts[(1, 0)]])
        for i in range(1, last - 1):
            polys.append([pts[(i, 0)], pts[(i, sgn)], pts[(i + 1, sgn)], pts[(i + 1, 0)]])
        polys.append([pts[(last - 1, 0)], pts[(last - 1, sgn)], pts[(last, 0)]])
    for q in polys:
        f = bm.faces.new([x[0] for x in q]); f.material_index = 1; f.smooth = True
        for lp, x in zip(f.loops, q):
            lp[uv].uv = (x[1], x[2]); lp[col] = shade


def build_tree(name='SM_TreeReal', seed=12, height=3.8):
    rnd = random.Random(seed)
    bm = bmesh.new(); uv = bm.loops.layers.uv.new('UVMap'); col = bm.loops.layers.color.new('Col')
    crown_c = Vector((0, 0, height * 0.66)); crown_r = Vector((1.25, 1.25, height * 0.36))
    def depth(p):                       # 0 at the crown centre .. 1 at its surface
        q = p - crown_c
        return min(1.4, math.sqrt((q.x / crown_r.x) ** 2 + (q.y / crown_r.y) ** 2 + (q.z / crown_r.z) ** 2))
    def ao(p):
        if p.z > 1.2: return max(0.4, min(1.0, 0.4 + 0.6 * depth(p) ** 1.3))
        return 0.55 + 0.45 * min(1, max(0.0, p.z) / 1.2)
    leaves = []
    trunk = bend_path(Vector((0, 0, -0.1)), Vector((0.05, 0.02, 1)), height * 0.9, 14, rnd, 0.0, 0.035)
    tr = [0.11 * (1 - 0.8 * i / 14) for i in range(15)]
    bark_tube(bm, uv, col, trunk, tr, 14, ao, flare=True)

    def branch(pts, radii, level):
        bark_tube(bm, uv, col, pts, radii, [10, 7, 5, 4][level], ao)
        if level == 3:
            for i in range(1, len(pts)):
                for k in range(6):
                    leaves.append((pts[i], (pts[i] - pts[i - 1]).normalized()))
            return
        n_kids = [0, 7, 7, 7][level + 1]
        seglen = sum((pts[i + 1] - pts[i]).length for i in range(len(pts) - 1))
        phase = rnd.uniform(0, TAU)
        for k in range(n_kids):
            t = 0.25 + 0.72 * (k + rnd.uniform(0, 0.8)) / n_kids
            idx = min(len(pts) - 2, int(t * (len(pts) - 1)))
            p = pts[idx]; d = (pts[idx + 1] - p).normalized()
            n, b = frame(d); a = phase + k * math.radians(137.5)
            out = n * math.cos(a) + b * math.sin(a)
            ang = math.radians(rnd.uniform(35, 55))
            nd = (d * math.cos(ang) + out * math.sin(ang) + Vector((0, 0, 0.25))).normalized()
            length = seglen * rnd.uniform(0.42, 0.6) * (1.05 - 0.45 * t)
            r0 = radii[idx] * rnd.uniform(0.55, 0.7)
            nseg = [0, 7, 5, 5][level + 1]
            pp = bend_path(p, nd, length, nseg, rnd, [0, 0.10, 0.18, 0.22][level + 1], [0, 0.10, 0.16, 0.2][level + 1])
            branch(pp, [r0 * (1 - 0.8 * i / nseg) + 0.002 for i in range(nseg + 1)], level + 1)

    nb = 9                              # main scaffold branches
    for k in range(nb):
        t = 0.36 + 0.6 * k / (nb - 1) + rnd.uniform(-0.03, 0.03)
        idx = min(13, int(t * 14)); p = trunk[idx]
        a = k * math.radians(137.5) + rnd.uniform(-0.3, 0.3)
        out = Vector((math.cos(a), math.sin(a), 0))
        shape = math.sin(math.pi * (0.15 + 0.85 * (1 - t) ** 0.8))
        length = height * 0.5 * (0.45 + 0.55 * shape) * rnd.uniform(0.85, 1.1)
        el = math.radians(rnd.uniform(48, 62))
        nd = (out * math.sin(el) + Vector((0, 0, math.cos(el)))).normalized()
        pp = bend_path(p, nd, length, 7, rnd, 0.12, 0.08)
        r0 = tr[idx] * rnd.uniform(0.55, 0.68)
        branch(pp, [r0 * (1 - 0.8 * i / 7) + 0.002 for i in range(8)], 1)
    branch(trunk[9:], tr[9:], 1)        # the leader's top forks too

    for p, d in leaves:
        out = Vector((p.x, p.y, 0)).normalized() if (abs(p.x) + abs(p.y)) > 1e-4 else Vector((1, 0, 0))
        a = rnd.uniform(0, TAU)
        ld = (d * 0.5 + out * 0.6 + Vector((math.cos(a), math.sin(a), rnd.uniform(-0.6, 0.2))) * 0.7).normalized()
        upv = (Vector((0, 0, 0.8)) + out * 0.4 + Vector((rnd.uniform(-.3, .3), rnd.uniform(-.3, .3), 0))).normalized()
        if abs(ld.dot(upv)) > 0.95: upv = Vector((1, 0, 0))
        sh = max(0.38, min(1.0, 0.38 + 0.62 * depth(p) ** 1.6)) * rnd.uniform(0.8, 1.1)
        hue = rnd.uniform(-1, 1)
        shade = (sh * (1 + 0.10 * hue), sh * (1 + 0.04 * hue), sh * (1 - 0.15 * hue), 1)
        leaf(bm, uv, col, p + ld * 0.012, ld, upv, rnd.uniform(0.11, 0.15), shade)
    me = bpy.data.meshes.new(name)
    for mn in ('M_TreeBark', 'M_TreeLeaf'):            # slots before faces
        me.materials.append(bpy.data.materials.get(mn) or bpy.data.materials.new(mn))
    bm.normal_update(); bm.to_mesh(me); bm.free()
    ob = link_new(name, me)
    return {'tris': sum(len(p.vertices) - 2 for p in me.polygons), 'leaves': len(leaves),
            'dims': tuple(round(x, 2) for x in ob.dimensions)}


def tree_game_materials(folder):
    """Bark and leaf materials from the baked tiles, times the per-vertex shade (as in Unreal)."""
    for mname, prefix, leafy in [('M_TreeBark', 'T_TreeBark', False), ('M_TreeLeaf', 'T_LeafTile', True)]:
        m = game_material(mname, folder, prefix)
        nt = m.node_tree; b = [n for n in nt.nodes if n.bl_idname == 'ShaderNodeBsdfPrincipled'][0]
        src = b.inputs['Base Color'].links[0].from_socket
        vc = nt.nodes.new('ShaderNodeVertexColor'); vc.layer_name = 'Col'
        mul_n = nt.nodes.new('ShaderNodeMix'); mul_n.data_type = 'RGBA'; mul_n.blend_type = 'MULTIPLY'
        mul_n.inputs[0].default_value = 1.0
        L(nt, src, mul_n.inputs[6]); L(nt, vc.outputs['Color'], mul_n.inputs[7]); L(nt, mul_n.outputs[2], b.inputs['Base Color'])
        if leafy:
            b.inputs['Transmission Weight'].default_value = 0.25
        m.use_backface_culling = False


def export(folder, names=('SM_RockReal', 'SM_TreeReal')):
    os.makedirs(folder, exist_ok=True)
    for nm in names:
        o = bpy.data.objects[nm]; select_only(o)
        bpy.ops.export_scene.fbx(filepath=os.path.join(folder, nm + '.fbx'), use_selection=True, object_types={'MESH'},
                                 apply_unit_scale=True, apply_scale_options='FBX_SCALE_NONE', axis_forward='-Z', axis_up='Y',
                                 mesh_smooth_type='FACE', add_leaf_bones=False, bake_anim=False, embed_textures=False,
                                 colors_type='LINEAR')
