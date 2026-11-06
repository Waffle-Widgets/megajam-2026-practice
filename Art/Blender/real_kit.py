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
    if isinstance(col, tuple): b.inputs['Base Color'].default_value = col
    else: L(nt, col, b.inputs['Base Color'])
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


def build_tree(name='SM_TreeReal', seed=12, height=3.8, tint=None, leaf_mat='M_TreeLeaf'):
    rnd = random.Random(seed); rt = random.Random(seed + 7)
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
        if tint: shade = tint(rt, sh)
        leaf(bm, uv, col, p + ld * 0.012, ld, upv, rnd.uniform(0.11, 0.15), shade)
    me = bpy.data.meshes.new(name)
    for mn in ('M_TreeBark', leaf_mat):                # slots before faces
        me.materials.append(bpy.data.materials.get(mn) or bpy.data.materials.new(mn))
    bm.normal_update(); bm.to_mesh(me); bm.free()
    ob = link_new(name, me)
    return {'tris': sum(len(p.vertices) - 2 for p in me.polygons), 'leaves': len(leaves),
            'dims': tuple(round(x, 2) for x in ob.dimensions)}


TILE_MATS = [('M_TreeBark', 'T_TreeBark', False), ('M_TreeLeaf', 'T_LeafTile', True), ('M_TreeLeafAutumn', 'T_LeafAutumn', True),
             ('M_Needles', 'T_Needles', True), ('M_Snow', 'T_SnowTile', False), ('M_Blade', 'T_ReedBlade', True),
             ('M_Cattail', 'T_Cattail', False), ('M_Cactus', 'T_CactusRib', False),
             ('M_Lawn', 'T_LawnBlade', True)]


def tree_game_materials(folder, table=TILE_MATS):
    """Preview materials from the baked tiles, times the per-vertex shade (as in Unreal)."""
    for mname, prefix, leafy in table:
        if not os.path.exists(os.path.join(folder, prefix + '_BaseColor.png')): continue
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


# ================================================================ round 2: the rest of the scenery
def periodic_noise(nt, scale, detail=4.0, rough=0.55):
    v, w, _, _ = torus_coords(nt, 1.0, 1.0)
    return n4(nt, v, w, scale, detail, rough)


def uv_sep(nt):
    uvn = nt.nodes.new('ShaderNodeUVMap'); sx = nt.nodes.new('ShaderNodeSeparateXYZ'); L(nt, uvn.outputs[0], sx.inputs[0])
    return sx.outputs[0], sx.outputs[1]


def build_needle_tile():
    """Spruce shoot seen from above: needles angled forward from a central twig. U runs along the twig (tiles)."""
    m, nt = new_mat('M_NeedleTile')
    u, v = uv_sep(nt)
    d = mth(nt, 'MULTIPLY', mth(nt, 'ABSOLUTE', mth(nt, 'SUBTRACT', v, 0.5)), 2.0)   # 0 at the twig, 1 at the tips
    ph = mth(nt, 'SUBTRACT', mth(nt, 'MULTIPLY', u, 16.0), mth(nt, 'MULTIPLY', d, 2.2))
    stripe = mth(nt, 'MULTIPLY', mth(nt, 'ADD', mth(nt, 'COSINE', mth(nt, 'MULTIPLY', ph, TAU)), 1.0), 0.5)
    needle = smooth(nt, stripe, 0.30, 0.80)
    var = periodic_noise(nt, 4.0, 4.0)
    ncol = mix(nt, var.outputs['Fac'], (0.035, 0.075, 0.030, 1), (0.065, 0.12, 0.045, 1))
    ncol = mix(nt, smooth(nt, d, 0.70, 0.95), ncol, (0.10, 0.16, 0.055, 1))        # paler new tips
    col = mix(nt, needle, (0.012, 0.026, 0.012, 1), ncol)
    twig = smooth(nt, d, 0.09, 0.04)
    col = mix(nt, twig, col, (0.09, 0.06, 0.035, 1))
    h = mth(nt, 'MAXIMUM', needle, twig)
    principled(nt, col, 0.55, h, 0.002, 0.8)
    return m


def build_blade_tile():
    """Reed / grass blade: U runs base to tip. Parallel veins, pale base, green middle, dry brown tip."""
    m, nt = new_mat('M_BladeTile')
    u, v = uv_sep(nt)
    vein = mth(nt, 'MULTIPLY', mth(nt, 'ADD', mth(nt, 'COSINE', mth(nt, 'MULTIPLY', v, TAU * 9)), 1.0), 0.5)
    tn = nt.nodes.new('ShaderNodeTexNoise'); mp = nt.nodes.new('ShaderNodeMapping')
    uvn = nt.nodes.new('ShaderNodeUVMap'); L(nt, uvn.outputs[0], mp.inputs['Vector']); mp.inputs['Scale'].default_value = (3, 40, 1)
    L(nt, mp.outputs[0], tn.inputs['Vector']); tn.inputs['Scale'].default_value = 3.0; tn.inputs['Detail'].default_value = 5
    col = mix(nt, smooth(nt, u, 0.0, 0.25), (0.20, 0.19, 0.11, 1), (0.07, 0.12, 0.03, 1))
    col = mix(nt, tn.outputs['Fac'], col, (0.10, 0.15, 0.04, 1))
    col = mix(nt, smooth(nt, mth(nt, 'ADD', u, mth(nt, 'MULTIPLY', tn.outputs['Fac'], 0.2)), 0.80, 1.0), col, (0.22, 0.17, 0.08, 1))
    col = mix(nt, mth(nt, 'MULTIPLY', vein, 0.25), col, (0.16, 0.20, 0.08, 1))
    principled(nt, col, 0.5, vein, 0.001, 0.5)
    return m


def build_cattail_tile():
    """Velvety brown cattail head (tiles both ways)."""
    m, nt = new_mat('M_CattailTile')
    fine = periodic_noise(nt, 60.0, 8.0, 0.7); coarse = periodic_noise(nt, 6.0, 3.0)
    col = mix(nt, fine.outputs['Fac'], (0.07, 0.035, 0.015, 1), (0.16, 0.085, 0.035, 1))
    col = mix(nt, smooth(nt, coarse.outputs['Fac'], 0.55, 0.7), col, (0.20, 0.15, 0.10, 1))
    principled(nt, col, 0.9, fine.outputs['Fac'], 0.002, 0.7)
    return m


def build_snow_tile():
    m, nt = new_mat('M_SnowTile')
    fine = periodic_noise(nt, 40.0, 6.0, 0.6); big = periodic_noise(nt, 3.0, 4.0)
    col = mix(nt, big.outputs['Fac'], (0.72, 0.76, 0.82, 1), (0.88, 0.90, 0.93, 1))
    h = mth(nt, 'ADD', fine.outputs['Fac'], mth(nt, 'MULTIPLY', big.outputs['Fac'], 1.5))
    principled(nt, col, mth(nt, 'ADD', 0.55, mth(nt, 'MULTIPLY', fine.outputs['Fac'], 0.2)), h, 0.004, 0.6)
    return m


def build_autumn_leaf_tile():
    """Same leaf as M_LeafTile, in autumn yellow-orange with darker blotches."""
    m, nt = new_mat('M_LeafAutumnTile')
    u, v = uv_sep(nt)
    dv = mth(nt, 'ABSOLUTE', mth(nt, 'SUBTRACT', v, 0.5))
    mid = smooth(nt, dv, 0.012, 0.0)
    ph = mth(nt, 'SUBTRACT', mth(nt, 'MULTIPLY', u, 9.0), mth(nt, 'MULTIPLY', dv, 7.0))
    vein = smooth(nt, mth(nt, 'ABSOLUTE', mth(nt, 'SINE', mth(nt, 'MULTIPLY', ph, math.pi))), 0.10, 0.0)
    vein = mth(nt, 'MULTIPLY', vein, smooth(nt, dv, 0.46, 0.2))
    uvn = nt.nodes.new('ShaderNodeUVMap')
    tn = nt.nodes.new('ShaderNodeTexNoise'); L(nt, uvn.outputs[0], tn.inputs['Vector']); tn.inputs['Scale'].default_value = 6; tn.inputs['Detail'].default_value = 6
    sp = nt.nodes.new('ShaderNodeTexVoronoi'); L(nt, uvn.outputs[0], sp.inputs['Vector']); sp.inputs['Scale'].default_value = 9
    base = mix(nt, tn.outputs['Fac'], (0.42, 0.16, 0.02, 1), (0.62, 0.38, 0.05, 1))
    col = mix(nt, mth(nt, 'MULTIPLY', smooth(nt, sp.outputs['Distance'], 0.16, 0.08), 0.8), base, (0.16, 0.07, 0.02, 1))
    col = mix(nt, smooth(nt, dv, 0.36, 0.5), col, (0.30, 0.13, 0.03, 1))
    col = mix(nt, mth(nt, 'MAXIMUM', mid, mth(nt, 'MULTIPLY', vein, 0.6)), col, (0.70, 0.50, 0.15, 1))
    h = mth(nt, 'SUBTRACT', 1.0, mth(nt, 'MAXIMUM', mid, vein))
    principled(nt, col, 0.55, h, 0.002, 0.6)
    return m


def autumn_tint(rnd, sh):
    r = rnd.random()
    if r < 0.30: c = (1.0, 0.55, 0.40)       # red-orange
    elif r < 0.62: c = (1.0, 0.85, 0.65)     # orange
    elif r < 0.90: c = (1.0, 1.0, 0.80)      # yellow
    else: c = (0.55, 0.42, 0.32)             # browned
    return (sh * c[0], sh * c[1], sh * c[2], 1)


def finish_mesh(name, bm, slots):
    me = bpy.data.meshes.new(name)
    for mn in slots:                                    # slots before faces
        me.materials.append(bpy.data.materials.get(mn) or bpy.data.materials.new(mn))
    bm.normal_update(); bm.to_mesh(me); bm.free()
    ob = link_new(name, me)
    return {'tris': sum(len(p.vertices) - 2 for p in me.polygons), 'dims': tuple(round(x, 2) for x in ob.dimensions)}


# ---------------------------------------------------------------- spruce
def spray(bm, uv, col, path, side_ref, width, shade, mat, tile=0.08, fold=0.25, drop=0.0):
    """Two crossed needle cards along a twig. Zig-zag edges give a needly silhouette."""
    s_total = sum((path[i + 1] - path[i]).length for i in range(len(path) - 1))
    if s_total < 0.02: return
    step = 0.012
    n = max(2, int(s_total / step))
    # resample the path evenly
    pts = []; seg_i = 0; acc = 0.0
    lens = [(path[i + 1] - path[i]).length for i in range(len(path) - 1)]
    for k in range(n + 1):
        target = s_total * k / n
        while seg_i < len(lens) - 1 and acc + lens[seg_i] < target:
            acc += lens[seg_i]; seg_i += 1
        f = (target - acc) / max(lens[seg_i], 1e-6)
        pts.append(path[seg_i].lerp(path[seg_i + 1], min(1.0, f)))
    for tilt in (0.0, 1.0):
        rows = []
        for k, p in enumerate(pts):
            d = (pts[min(k + 1, n)] - pts[max(k - 1, 0)]).normalized()
            side = (side_ref - d * side_ref.dot(d)).normalized()
            up = d.cross(side).normalized()
            if up.z < 0: up = -up
            if tilt: side = (side * 0.5 + up * 0.866).normalized(); up = d.cross(side).normalized()
            t = k / n
            w = width * (1 - 0.55 * t ** 1.5) * (1.0 if k % 2 == 0 else 0.62)
            sag = -up * (fold * w)
            row = [(bm.verts.new(p + side * w + sag + Vector((0, 0, -drop * w))), 0.0),
                   (bm.verts.new(p), 0.5),
                   (bm.verts.new(p - side * w + sag + Vector((0, 0, -drop * w))), 1.0)]
            rows.append((row, k * step / tile, w / width))
        for k in range(n):
            (ra, ua, wa), (rb, ub, wb) = rows[k], rows[k + 1]
            for j in range(2):
                q = [(ra[j], ua), (ra[j + 1], ua), (rb[j + 1], ub), (rb[j], ub)]
                f = bm.faces.new([x[0][0] for x in q]); f.material_index = mat; f.smooth = True
                for lp, (vv, uu) in zip(f.loops, q):
                    ww = wa if uu == ua else wb
                    lp[uv].uv = (uu, 0.5 + (vv[1] - 0.5) * ww); lp[col] = shade


def blob_snow(bm, uv, col, c, r, h, mat):
    tmp = bmesh.new(); bmesh.ops.create_icosphere(tmp, subdivisions=2, radius=1.0)
    m = {}
    for v in tmp.verts:
        p = v.co
        z = p.z * h if p.z > 0 else p.z * h * 0.25
        m[v] = bm.verts.new(c + Vector((p.x * r, p.y * r * 0.8, z)) + Vector((0, 0, noise.noise(p * 3 + c * 7) * h * 0.25)))
    for f in tmp.faces:
        nf = bm.faces.new([m[v] for v in f.verts]); nf.material_index = mat; nf.smooth = True
        for lp in nf.loops:
            co = lp.vert.co; lp[uv].uv = (co.x * 2.5, co.y * 2.5); lp[col] = (1, 1, 1, 1)
    tmp.free()


def build_spruce(name='SM_PineReal', seed=5, height=4.2, snow=False):
    rnd = random.Random(seed); rs = random.Random(seed + 99)
    bm = bmesh.new(); uv = bm.loops.layers.uv.new('UVMap'); col = bm.loops.layers.color.new('Col')
    base_r = 1.05
    def reach(z): return 0.12 + base_r * max(0.0, (height - z) / (height - 0.45)) ** 0.95
    def ao(p):
        r = math.hypot(p.x, p.y); rel = r / max(reach(p.z), 0.1)
        return max(0.3, min(1.0, 0.3 + 0.7 * rel ** 1.2)) * (0.8 + 0.2 * min(1.0, p.z / height * 1.5))
    trunk = bend_path(Vector((0, 0, -0.1)), Vector((0, 0, 1)), height + 0.1, 16, rnd, 0.0, 0.012)
    bark_tube(bm, uv, col, trunk, [0.095 * (1 - 0.92 * i / 16) for i in range(17)], 10, ao, flare=True)
    z = 0.45; wi = 0
    while z < height - 0.2:
        nbr = rnd.choice([5, 5, 6])
        phase = wi * 0.71 + rnd.uniform(0, 0.4)
        for k in range(nbr):
            a = phase + TAU * k / nbr + rnd.uniform(-0.2, 0.2)
            out = Vector((math.cos(a), math.sin(a), 0))
            length = reach(z) * rnd.uniform(0.85, 1.05)
            start = Vector((0, 0, z)) + out * 0.02
            pts = bend_path(start, out + Vector((0, 0, -0.30)), length, 6, rnd, -0.25, 0.05)
            r0 = 0.006 + 0.022 * (length / (base_r + 0.12))
            bark_tube(bm, uv, col, pts, [r0 * (1 - 0.8 * i / 6) + 0.002 for i in range(7)], 4, ao)
            side_ref = out.cross(Vector((0, 0, 1))).normalized()
            sh = ao(pts[-1]); shade = (sh, sh, sh, 1)
            spray(bm, uv, col, pts[1:], side_ref, 0.10, shade, 1, drop=0.35)
            # side shoots, alternating left and right
            nt_ = max(3, int(length / 0.065))
            for j in range(nt_):
                t = 0.15 + 0.8 * j / nt_
                idx = min(5, int(t * 6)); p = pts[idx].lerp(pts[idx + 1], t * 6 - idx)
                d = (pts[idx + 1] - pts[idx]).normalized()
                sgn = 1 if j % 2 == 0 else -1
                sd = d.cross(Vector((0, 0, 1))).normalized() * sgn
                tl = (length * (1 - t) * 0.6 + 0.10) * rnd.uniform(0.8, 1.15)
                hang = 0.25 + 0.45 * (1 - z / height)
                tp = bend_path(p, d * 0.5 + sd * 0.8 + Vector((0, 0, -hang)), tl, 3, rnd, 0.15, 0.1)
                sh = ao(tp[-1]) * rnd.uniform(0.85, 1.05); shade = (sh, sh, sh, 1)
                spray(bm, uv, col, tp, Vector((0, 0, 1)).cross(d).normalized(), 0.085, shade, 1, drop=0.35)
            if snow:
                for j in range(int(length / 0.055) + 1):
                    t = rs.uniform(0.1, 0.9)
                    idx = min(5, int(t * 6)); p = pts[idx].lerp(pts[idx + 1], t * 6 - idx)
                    blob_snow(bm, uv, col, p + Vector((0, 0, 0.035)), rs.uniform(0.07, 0.13) * (1 - 0.4 * t), rs.uniform(0.03, 0.05), 2)
        z += rnd.uniform(0.15, 0.21) * (1 - 0.3 * z / height); wi += 1
    # leader tip
    for k in range(5):                  # leader tip: a few short upward shoots
        a = TAU * k / 5
        tp = bend_path(Vector((0, 0, height - 0.3 + 0.05 * k)), Vector((math.cos(a) * 0.5, math.sin(a) * 0.5, 1)), 0.22, 2, rnd, 0.0, 0.05)
        spray(bm, uv, col, tp, Vector((-math.sin(a), math.cos(a), 0)), 0.06, (1, 1, 1, 1), 1)
    slots = ['M_TreeBark', 'M_Needles'] + (['M_Snow'] if snow else [])
    return finish_mesh(name, bm, slots)


# ---------------------------------------------------------------- bush
def build_bush(name='SM_BushReal', seed=8):
    rnd = random.Random(seed)
    bm = bmesh.new(); uv = bm.loops.layers.uv.new('UVMap'); col = bm.loops.layers.color.new('Col')
    cc = Vector((0, 0, 0.42)); cr = Vector((0.68, 0.62, 0.42))
    def depth(p):
        q = p - cc; return min(1.4, math.sqrt((q.x / cr.x) ** 2 + (q.y / cr.y) ** 2 + (q.z / cr.z) ** 2))
    def ao(p): return max(0.3, min(1.0, 0.3 + 0.7 * depth(p) ** 1.4))
    leaves = []
    def grow(pts, radii, level):
        bark_tube(bm, uv, col, pts, radii, [6, 5, 4][level], ao)
        if level == 2:
            for i in range(1, len(pts)):
                for k in range(7): leaves.append((pts[i], (pts[i] - pts[i - 1]).normalized()))
            return
        seglen = sum((pts[i + 1] - pts[i]).length for i in range(len(pts) - 1))
        for k in range([6, 6][level]):
            t = 0.25 + 0.7 * (k + rnd.uniform(0, 0.8)) / 6
            idx = min(len(pts) - 2, int(t * (len(pts) - 1)))
            p = pts[idx]; d = (pts[idx + 1] - p).normalized(); n, b = frame(d)
            a = k * 2.4 + rnd.uniform(0, 1); out = n * math.cos(a) + b * math.sin(a)
            nd = (d * 0.6 + out * 0.8 + Vector((0, 0, 0.2))).normalized()
            ln = seglen * rnd.uniform(0.4, 0.6) * (1.1 - 0.5 * t)
            pp = bend_path(p, nd, ln, 4, rnd, 0.1, 0.18)
            r0 = radii[idx] * 0.6
            grow(pp, [r0 * (1 - 0.8 * i / 4) + 0.0015 for i in range(5)], level + 1)
    for s in range(8):
        a = s * 2.4 + rnd.uniform(-0.3, 0.3); out = Vector((math.cos(a), math.sin(a), 0))
        el = math.radians(rnd.uniform(25, 55))
        pp = bend_path(out * rnd.uniform(0.02, 0.12) + Vector((0, 0, -0.05)), out * math.sin(el) + Vector((0, 0, math.cos(el))),
                       rnd.uniform(0.55, 0.8), 5, rnd, 0.12, 0.12)
        grow(pp, [0.016 * (1 - 0.8 * i / 5) + 0.002 for i in range(6)], 0)
    for p, d in leaves:
        out = Vector((p.x, p.y, 0)).normalized() if (abs(p.x) + abs(p.y)) > 1e-4 else Vector((1, 0, 0))
        a = rnd.uniform(0, TAU)
        ld = (d * 0.4 + out * 0.5 + Vector((math.cos(a), math.sin(a), rnd.uniform(-0.5, 0.4))) * 0.8).normalized()
        upv = (Vector((0, 0, 0.8)) + out * 0.5).normalized()
        if abs(ld.dot(upv)) > 0.95: upv = Vector((1, 0, 0))
        sh = max(0.32, min(1.0, 0.32 + 0.68 * depth(p) ** 1.6)) * rnd.uniform(0.8, 1.1)
        hue = rnd.uniform(-1, 1)
        leaf(bm, uv, col, p + ld * 0.008, ld, upv, rnd.uniform(0.05, 0.075), (sh * (1 + 0.08 * hue), sh, sh * (1 - 0.12 * hue), 1))
    r = finish_mesh(name, bm, ['M_TreeBark', 'M_TreeLeaf']); r['leaves'] = len(leaves); return r


# ---------------------------------------------------------------- reeds
def build_reeds(name='SM_ReedsReal', seed=31):
    rnd = random.Random(seed)
    bm = bmesh.new(); uv = bm.loops.layers.uv.new('UVMap'); col = bm.loops.layers.color.new('Col')
    for k in range(75):
        a = rnd.uniform(0, TAU); r = 0.28 * math.sqrt(rnd.random())
        base = Vector((r * math.cos(a), r * math.sin(a), -0.03))
        out = Vector((math.cos(a), math.sin(a), 0))
        H = rnd.uniform(0.6, 1.3); bend = rnd.uniform(0.05, 0.45) * (0.4 + r * 2)
        n = 7; w0 = rnd.uniform(0.010, 0.017)
        tw = rnd.uniform(0, TAU)
        side0 = Vector((math.cos(tw), math.sin(tw), 0))
        rows = []
        for i in range(n + 1):
            t = i / n
            p = base + out * bend * t * t * H + Vector((0, 0, H * (t - 0.35 * bend * t * t * t)))
            w = w0 * (1 - t ** 1.3) + 0.0008
            side = (side0 + out * 0.3 * t).normalized()
            rows.append((p, side, w, t))
        sh = rnd.uniform(0.75, 1.0)
        for i in range(n):
            (pa, sa, wa, ta), (pb, sb, wb, tb) = rows[i], rows[i + 1]
            ups = [Vector((0, 0, 0)), Vector((0, 0, 0.004))]
            va = [bm.verts.new(pa + sa * wa), bm.verts.new(pa + ups[1] * (wa / w0)), bm.verts.new(pa - sa * wa)]
            vb = [bm.verts.new(pb + sb * wb), bm.verts.new(pb + ups[1] * (wb / w0)), bm.verts.new(pb - sb * wb)]
            for j in range(2):
                f = bm.faces.new([va[j], va[j + 1], vb[j + 1], vb[j]]); f.material_index = 0; f.smooth = True
                vv = [j * 0.5, (j + 1) * 0.5, (j + 1) * 0.5, j * 0.5]; uu = [ta, ta, tb, tb]
                for lp, u_, v_ in zip(f.loops, uu, vv):
                    s_ = sh * (0.55 + 0.45 * u_); lp[uv].uv = (u_, v_); lp[col] = (s_, s_, s_, 1)
    def ao_stem(p): return 0.6 + 0.4 * min(1.0, max(0.0, p.z))
    for k in range(7):
        a = TAU * k / 7 + rnd.uniform(-0.3, 0.3); r = rnd.uniform(0.04, 0.18)
        base = Vector((r * math.cos(a), r * math.sin(a), -0.03)); H = rnd.uniform(1.0, 1.35)
        lean = Vector((math.cos(a), math.sin(a), 0)) * rnd.uniform(0.02, 0.1)
        stem = [base + lean * (i / 5) ** 2 + Vector((0, 0, H * i / 5)) for i in range(6)]
        bark_tube(bm, uv, col, stem, [0.005, 0.0048, 0.0045, 0.004, 0.0035, 0.003], 5, ao_stem)
        head = H - 0.32
        hp = [base + lean * ((head / H) ** 2) + Vector((0, 0, head + 0.17 * i / 3)) for i in range(4)]
        before = set(bm.faces)
        bark_tube(bm, uv, col, hp, [0.016, 0.021, 0.021, 0.017], 10, lambda p: 1.0)
        for f in set(bm.faces) - before: f.material_index = 1
    # stems: squeeze their UVs into the green middle of the blade texture
    for f in bm.faces:
        if f.material_index == 0:
            for lp in f.loops:
                if lp[uv].uv.y > 1.001 or lp[uv].uv.x > 1.001:
                    lp[uv].uv = (0.45 + (lp[uv].uv.y % 1.0) * 0.1, 0.45 + (lp[uv].uv.x % 1.0) * 0.1)
    return finish_mesh(name, bm, ['M_Blade', 'M_Cattail'])


# ---------------------------------------------------------------- saguaro cactus
def rib_tube(bm, uv, col, path, radii, ribs, shade, cap=True, tile_v=0.15):
    """Ribbed cactus limb along a path, with spines on every rib crest. U = rib count around."""
    seg = ribs * 4
    rings = []; s = 0.0; n_prev = None
    for i, p in enumerate(path):
        t = (path[min(i + 1, len(path) - 1)] - path[max(i - 1, 0)]).normalized()
        if n_prev is None: n, b = frame(t)
        else: n = (n_prev - t * n_prev.dot(t)).normalized(); b = t.cross(n)
        n_prev = n
        if i: s += (p - path[i - 1]).length
        ring = []
        for j in range(seg + 1):
            a = TAU * j / seg
            prof = 0.86 + 0.16 * (0.5 + 0.5 * math.cos(ribs * a)) ** 1.6
            ring.append((bm.verts.new(p + (n * math.cos(a) + b * math.sin(a)) * radii[i] * prof), j / seg * ribs, s / tile_v, a, n, b))
        rings.append(ring)
    for i in range(len(rings) - 1):
        for j in range(seg):
            q = [rings[i][j], rings[i][j + 1], rings[i + 1][j + 1], rings[i + 1][j]]
            f = bm.faces.new([x[0] for x in q]); f.material_index = 0; f.smooth = True
            for lp, x in zip(f.loops, q):
                lp[uv].uv = (x[1], x[2]); sh = shade(lp.vert.co); lp[col] = (sh, sh * 0.97, sh * 0.92, 1)
    # spines: little thin triangles in clusters along each crest
    total = s; nA = int(total / (tile_v / 3))
    for k in range(nA):
        ss = (k + 0.5) * tile_v / 3
        acc = 0.0
        for i in range(len(path) - 1):
            sl = (path[i + 1] - path[i]).length
            if acc + sl >= ss: break
            acc += sl
        f_ = (ss - acc) / max(sl, 1e-6)
        p = path[i].lerp(path[i + 1], f_); r = radii[i] + (radii[i + 1] - radii[i]) * f_
        t = (path[i + 1] - path[i]).normalized(); n, b = rings[i][0][4], rings[i][0][5]
        for rib in range(ribs):
            a = TAU * rib / ribs
            out = (n * math.cos(a) + b * math.sin(a)); c = p + out * r * 1.02
            for sp in range(4):
                th = sp * 1.7 + k
                dirv = (out * 0.8 + t * math.cos(th) * 0.6 + out.cross(t) * math.sin(th) * 0.6).normalized()
                L_ = 0.012 + 0.012 * ((sp * 7 + k * 3) % 5) / 4
                side = dirv.cross(out).normalized() * 0.0012
                tri = [bm.verts.new(c + side), bm.verts.new(c - side), bm.verts.new(c + dirv * L_)]
                fs = bm.faces.new(tri); fs.material_index = 0
                for lp in fs.loops: lp[uv].uv = (0.5, 0.165); lp[col] = (1, 1, 1, 1)
    if cap:
        top = path[-1]; tdir = (path[-1] - path[-2]).normalized(); last = rings[-1]
        prev = last
        for k in range(1, 5):
            f_ = math.cos(k / 5 * math.pi / 2); dz = math.sin(k / 5 * math.pi / 2) * radii[-1] * 0.8
            ring = []
            for j, x in enumerate(last):
                co = top + (x[0].co - top) * f_ + tdir * dz
                ring.append((bm.verts.new(co), x[1], x[2] + k * 0.15))
            for j in range(seg):
                q = [prev[j], prev[j + 1], ring[j + 1], ring[j]]
                fq = bm.faces.new([y[0] for y in q]); fq.material_index = 0; fq.smooth = True
                for lp, y in zip(fq.loops, q): lp[uv].uv = (y[1], y[2]); lp[col] = (1, 0.97, 0.92, 1)
            prev = ring
        apex = bm.verts.new(top + tdir * radii[-1] * 0.82)
        for j in range(seg):
            fq = bm.faces.new([prev[j][0], prev[j + 1][0], apex]); fq.material_index = 0; fq.smooth = True
            for lp in fq.loops: lp[uv].uv = (prev[j][1], prev[j][2] + 0.1); lp[col] = (1, 0.97, 0.92, 1)


def build_cactus(name='SM_CactusReal', seed=4, height=2.3):
    rnd = random.Random(seed)
    bm = bmesh.new(); uv = bm.loops.layers.uv.new('UVMap'); col = bm.loops.layers.color.new('Col')
    def shade(p): return 0.62 + 0.38 * min(1.0, max(0.0, (p.z + 0.05) / 0.45))     # corky, dusty base
    trunk = bend_path(Vector((0, 0, -0.08)), Vector((0, 0, 1)), height, 18, rnd, 0.0, 0.01)
    rib_tube(bm, uv, col, trunk, [0.17 + 0.015 * math.sin(i / 18 * math.pi) for i in range(19)], 14, shade)
    for side, zb, up_h in [(1, 0.95, 0.75), (-1, 1.25, 0.55)]:
        a = rnd.uniform(-0.4, 0.4); out = Vector((math.cos(a) * 0, side * 1, 0)).normalized()
        start = Vector((0, 0, zb)) + out * 0.05
        pts = [start]
        for i in range(1, 13):                          # out, then an elbow, then up
            t = i / 12; ang = min(1.0, t * 1.8) * math.pi / 2
            pts.append(pts[-1] + (out * math.cos(ang) + Vector((0, 0, 1)) * math.sin(ang)) * ((0.28 + up_h) / 12))
        rib_tube(bm, uv, col, pts, [0.11] * len(pts), 11, shade)
    return finish_mesh(name, bm, ['M_Cactus'])


def build_cactus_tile():
    """One rib per U unit: dark groove at the edges, waxy crest in the middle with areoles every 1/3 V."""
    m, nt = new_mat('M_CactusTile')
    u, v = uv_sep(nt)
    crest = mth(nt, 'MULTIPLY', mth(nt, 'ADD', mth(nt, 'COSINE', mth(nt, 'MULTIPLY', mth(nt, 'SUBTRACT', u, 0.5), TAU)), 1.0), 0.5)
    groove = smooth(nt, crest, 0.12, 0.0)
    av = mth(nt, 'MULTIPLY', mth(nt, 'FRACT', mth(nt, 'MULTIPLY', v, 3.0)), 1.0)
    du = mth(nt, 'SUBTRACT', u, 0.5); dvv = mth(nt, 'MULTIPLY', mth(nt, 'SUBTRACT', av, 0.5), 0.33 * 1.0)
    dist = mth(nt, 'SQRT', mth(nt, 'ADD', mth(nt, 'MULTIPLY', du, du), mth(nt, 'MULTIPLY', dvv, dvv)))
    areole = smooth(nt, dist, 0.075, 0.045)
    var = periodic_noise(nt, 3.0, 5.0); streak = periodic_noise(nt, 20.0, 3.0)
    base = mix(nt, var.outputs['Fac'], (0.075, 0.12, 0.065, 1), (0.12, 0.17, 0.085, 1))
    base = mix(nt, mth(nt, 'MULTIPLY', streak.outputs['Fac'], 0.4), base, (0.15, 0.17, 0.11, 1))
    col = mix(nt, groove, base, (0.03, 0.055, 0.03, 1))
    col = mix(nt, areole, col, (0.55, 0.52, 0.44, 1))
    h = mth(nt, 'ADD', mth(nt, 'MULTIPLY', crest, 0.4), mth(nt, 'MULTIPLY', areole, 0.6))
    principled(nt, col, mth(nt, 'ADD', 0.45, mth(nt, 'MULTIPLY', areole, 0.4)), h, 0.004, 0.7)
    return m


# ---------------------------------------------------------------- hard-surface props: realistic materials baked onto the earlier shapes
def obj_coords(nt):
    tc = nt.nodes.new('ShaderNodeTexCoord')
    sp = nt.nodes.new('ShaderNodeSeparateXYZ'); L(nt, tc.outputs['Object'], sp.inputs[0])
    sn = nt.nodes.new('ShaderNodeSeparateXYZ'); L(nt, tc.outputs['Normal'], sn.inputs[0])
    return tc.outputs['Object'], sp.outputs, sn.outputs


def edge_mask(nt, radius=0.012, lo=0.07, hi=0.3):
    """1 on worn edges: where a bevelled normal leans away from the true normal."""
    bv = nt.nodes.new('ShaderNodeBevel'); bv.samples = 16; bv.inputs['Radius'].default_value = radius
    geo = nt.nodes.new('ShaderNodeNewGeometry')
    dp = nt.nodes.new('ShaderNodeVectorMath'); dp.operation = 'DOT_PRODUCT'
    L(nt, bv.outputs[0], dp.inputs[0]); L(nt, geo.outputs['Normal'], dp.inputs[1])
    return smooth(nt, mth(nt, 'SUBTRACT', 1.0, dp.outputs['Value']), lo, hi)


def grime(nt, P, pz, col, zlow=0.25, streak=0.35, dirt=(0.09, 0.075, 0.06, 1), strength=0.7):
    """Rain streaks running down and dirt splashed up from the ground."""
    mp = nt.nodes.new('ShaderNodeMapping'); L(nt, P, mp.inputs['Vector']); mp.inputs['Scale'].default_value = (14, 14, 1.0)
    st = tex(nt, 'ShaderNodeTexNoise', mp.outputs[0], 1.6, Detail=5.0)
    col = mix(nt, mth(nt, 'MULTIPLY', smooth(nt, st.outputs['Fac'], 0.52, 0.75), streak), col, (0.05, 0.045, 0.04, 1))
    dn = tex(nt, 'ShaderNodeTexNoise', P, 7.0, Detail=6.0)
    low = smooth(nt, mth(nt, 'ADD', pz, mth(nt, 'MULTIPLY', dn.outputs['Fac'], zlow * 0.6)), zlow, 0.0)
    return mix(nt, mth(nt, 'MULTIPLY', low, strength), col, dirt), low


def mat_paint(name, color, wear=0.5, rough=0.42, metal_under=(0.10, 0.095, 0.09, 1), rust=0.6):
    m, nt = new_mat(name); P, (px, py, pz), (nx, ny, nz) = obj_coords(nt)
    fade = tex(nt, 'ShaderNodeTexNoise', P, 3.0, Detail=4.0)
    c2 = tuple(min(1.0, c * 1.25) for c in color[:3]) + (1,)
    col = mix(nt, smooth(nt, fade.outputs['Fac'], 0.35, 0.7), color, c2)         # sun-faded patches
    e = edge_mask(nt)
    cn = tex(nt, 'ShaderNodeTexNoise', P, 28.0, Detail=8.0, Roughness=0.7)
    chips = smooth(nt, mth(nt, 'ADD', mth(nt, 'MULTIPLY', e, wear * 1.4), mth(nt, 'MULTIPLY', mth(nt, 'SUBTRACT', cn.outputs['Fac'], 0.5), 1.2)), 0.55, 0.65)
    rn = tex(nt, 'ShaderNodeTexNoise', P, 12.0, Detail=6.0)
    under = mix(nt, mth(nt, 'MULTIPLY', rn.outputs['Fac'], rust), metal_under, (0.20, 0.075, 0.025, 1))
    col = mix(nt, chips, col, under)
    col, low = grime(nt, P, pz, col)
    rough_s = mth(nt, 'ADD', rough, mth(nt, 'ADD', mth(nt, 'MULTIPLY', chips, 0.35), mth(nt, 'MULTIPLY', low, 0.3)))
    h = mth(nt, 'SUBTRACT', 1.0, mth(nt, 'MULTIPLY', chips, 0.6))
    principled(nt, col, rough_s, h, 0.0008)
    return m


def mat_galv(name, base=(0.33, 0.34, 0.34, 1)):
    m, nt = new_mat(name); P, (px, py, pz), _ = obj_coords(nt)
    sp = tex(nt, 'ShaderNodeTexVoronoi', P, 30.0)
    bw = nt.nodes.new('ShaderNodeSeparateColor'); L(nt, sp.outputs['Color'], bw.inputs[0])
    col = mix(nt, mth(nt, 'MULTIPLY', bw.outputs[0], 0.2), base, (0.45, 0.46, 0.46, 1))     # zinc spangle
    wn = tex(nt, 'ShaderNodeTexNoise', P, 4.0, Detail=5.0)
    col = mix(nt, mth(nt, 'MULTIPLY', smooth(nt, wn.outputs['Fac'], 0.5, 0.7), 0.6), col, (0.22, 0.22, 0.21, 1))
    col, low = grime(nt, P, pz, col, 0.3)
    principled(nt, col, mth(nt, 'ADD', 0.38, mth(nt, 'MULTIPLY', wn.outputs['Fac'], 0.25)), bw.outputs[1], 0.0004)
    return m


def box_uv(nt, P, nx, ny):
    """2D wall coordinates: (y, z) on walls facing X, (x, z) on walls facing Y."""
    ax = nt.nodes.new('ShaderNodeMath'); ax.operation = 'GREATER_THAN'
    L(nt, mth(nt, 'ABSOLUTE', nx), ax.inputs[0]); L(nt, mth(nt, 'ABSOLUTE', ny), ax.inputs[1])
    sp = nt.nodes.new('ShaderNodeSeparateXYZ'); L(nt, P, sp.inputs[0])
    a = nt.nodes.new('ShaderNodeCombineXYZ'); L(nt, sp.outputs[0], a.inputs[0]); L(nt, sp.outputs[2], a.inputs[1])
    b = nt.nodes.new('ShaderNodeCombineXYZ'); L(nt, sp.outputs[1], b.inputs[0]); L(nt, sp.outputs[2], b.inputs[1])
    mv = nt.nodes.new('ShaderNodeMix'); mv.data_type = 'VECTOR'
    L(nt, ax.outputs[0], mv.inputs[0]); L(nt, a.outputs[0], mv.inputs[4]); L(nt, b.outputs[0], mv.inputs[5])
    return mv.outputs[1]


def mat_brick(name):
    m, nt = new_mat(name); P, (px, py, pz), (nx, ny, nz) = obj_coords(nt)
    v = box_uv(nt, P, nx, ny)
    br = nt.nodes.new('ShaderNodeTexBrick'); L(nt, v, br.inputs['Vector'])
    br.inputs['Scale'].default_value = 1.0; br.inputs['Brick Width'].default_value = 0.215; br.inputs['Row Height'].default_value = 0.068
    br.inputs['Mortar Size'].default_value = 0.009; br.inputs['Mortar Smooth'].default_value = 0.3; br.inputs['Bias'].default_value = 0.0
    br.inputs['Color1'].default_value = (0.20, 0.065, 0.035, 1); br.inputs['Color2'].default_value = (0.32, 0.12, 0.06, 1)
    br.inputs['Mortar'].default_value = (0.30, 0.28, 0.25, 1); br.offset = 0.5
    surf = tex(nt, 'ShaderNodeTexNoise', P, 60.0, Detail=8.0, Roughness=0.7)
    col = mix(nt, mth(nt, 'MULTIPLY', surf.outputs['Fac'], 0.35), br.outputs['Color'], (0.12, 0.05, 0.03, 1))
    soot = tex(nt, 'ShaderNodeTexNoise', P, 2.0, Detail=4.0)
    col = mix(nt, mth(nt, 'MULTIPLY', smooth(nt, soot.outputs['Fac'], 0.45, 0.7), 0.5), col, (0.08, 0.06, 0.05, 1))
    col, low = grime(nt, P, pz, col, 0.35, 0.45)
    h = mth(nt, 'ADD', mth(nt, 'MULTIPLY', mth(nt, 'SUBTRACT', 1.0, br.outputs['Fac']), 1.0), mth(nt, 'MULTIPLY', surf.outputs['Fac'], 0.2))
    principled(nt, col, mth(nt, 'ADD', 0.75, mth(nt, 'MULTIPLY', br.outputs['Fac'], 0.15)), h, 0.004)
    return m


def mat_concrete(name, base=(0.32, 0.31, 0.29, 1)):
    m, nt = new_mat(name); P, (px, py, pz), _ = obj_coords(nt)
    big = tex(nt, 'ShaderNodeTexNoise', P, 3.0, Detail=6.0); pores = tex(nt, 'ShaderNodeTexVoronoi', P, 140.0)
    col = mix(nt, big.outputs['Fac'], tuple(c * 0.8 for c in base[:3]) + (1,), tuple(min(1, c * 1.15) for c in base[:3]) + (1,))
    pm = smooth(nt, pores.outputs['Distance'], 0.12, 0.04)
    col = mix(nt, mth(nt, 'MULTIPLY', pm, 0.6), col, (0.12, 0.115, 0.11, 1))
    e = edge_mask(nt, 0.02)
    col = mix(nt, mth(nt, 'MULTIPLY', e, 0.4), col, (0.45, 0.44, 0.42, 1))
    col, low = grime(nt, P, pz, col, 0.3, 0.5)
    principled(nt, col, 0.88, mth(nt, 'SUBTRACT', 1.0, pm), 0.001)
    return m


def mat_plain(name, color, rough=0.6, noise_amt=0.15):
    m, nt = new_mat(name); P, (px, py, pz), _ = obj_coords(nt)
    n = tex(nt, 'ShaderNodeTexNoise', P, 9.0, Detail=6.0)
    col = mix(nt, mth(nt, 'MULTIPLY', n.outputs['Fac'], noise_amt * 2), color, (0.0, 0.0, 0.0, 1))
    col, low = grime(nt, P, pz, col, 0.2, 0.3)
    principled(nt, col, rough, n.outputs['Fac'], 0.0005)
    return m


def mat_lilypad(name):
    m, nt = new_mat(name); P, (px, py, pz), _ = obj_coords(nt)
    r = mth(nt, 'SQRT', mth(nt, 'ADD', mth(nt, 'MULTIPLY', px, px), mth(nt, 'MULTIPLY', py, py)))
    th = mth(nt, 'ARCTAN2', py, px)
    wob = tex(nt, 'ShaderNodeTexNoise', P, 6.0, Detail=3.0)
    vein = smooth(nt, mth(nt, 'ABSOLUTE', mth(nt, 'SINE', mth(nt, 'ADD', mth(nt, 'MULTIPLY', th, 13.0), mth(nt, 'MULTIPLY', wob.outputs['Fac'], 0.6)))), 0.10, 0.0)
    vein = mth(nt, 'MULTIPLY', vein, smooth(nt, r, 0.03, 0.08))
    fine = tex(nt, 'ShaderNodeTexNoise', P, 40.0, Detail=8.0)
    base = mix(nt, fine.outputs['Fac'], (0.075, 0.17, 0.04, 1), (0.13, 0.25, 0.06, 1))
    edge = smooth(nt, mth(nt, 'ADD', r, mth(nt, 'MULTIPLY', wob.outputs['Fac'], 0.06)), 0.34, 0.42)
    col = mix(nt, mth(nt, 'MULTIPLY', edge, 0.8), base, (0.22, 0.17, 0.05, 1))                 # yellowing rim
    sp = tex(nt, 'ShaderNodeTexVoronoi', P, 9.0)
    spots = mth(nt, 'MULTIPLY', smooth(nt, sp.outputs['Distance'], 0.10, 0.05), smooth(nt, wob.outputs['Fac'], 0.55, 0.65))
    col = mix(nt, spots, col, (0.13, 0.07, 0.03, 1))                                          # brown spots
    col = mix(nt, mth(nt, 'MULTIPLY', vein, 0.6), col, (0.12, 0.20, 0.06, 1))
    principled(nt, col, mth(nt, 'ADD', 0.22, mth(nt, 'MULTIPLY', spots, 0.4)), mth(nt, 'SUBTRACT', 1.0, vein), 0.0008)
    return m


def mat_emit(name, color):
    m, nt = new_mat(name)
    principled(nt, (color[0], color[1], color[2], 1), 0.3)
    return m


# asset -> one material per slot, in slot order. Glow slots stay emissive in Unreal; their bake is unused.
def prop_materials():
    return {
        'SM_HydrantReal': [mat_paint('MB_Hydrant_Paint', (0.33, 0.025, 0.015, 1), 0.55),
                           mat_paint('MB_Hydrant_Metal', (0.30, 0.30, 0.29, 1), 0.7)],
        'SM_LampReal': [mat_paint('MB_Lamp_Metal', (0.035, 0.05, 0.04, 1), 0.35, 0.5, rust=0.8), mat_emit('MB_Lamp_Glow', (1, 0.9, 0.7))],
        'SM_BuildingReal': [mat_brick('MB_Building_Brick'), mat_concrete('MB_Building_Concrete'), mat_emit('MB_Building_Windows', (0.9, 0.8, 0.6)),
                            mat_paint('MB_Building_Dark', (0.025, 0.03, 0.035, 1), 0.4, 0.5), mat_galv('MB_Building_Metal')],
        'SM_TrainReal': [mat_paint('MB_Train_Body', (0.50, 0.51, 0.50, 1), 0.25, 0.38, rust=0.2),
                         mat_paint('MB_Train_Stripe', (0.02, 0.07, 0.25, 1), 0.25, 0.38, rust=0.2),
                         mat_emit('MB_Train_Windows', (0.9, 0.8, 0.6)), mat_plain('MB_Train_Dark', (0.025, 0.025, 0.027, 1), 0.7),
                         mat_emit('MB_Train_Headlight', (1, 1, 0.9)), mat_galv('MB_Train_Metal', (0.10, 0.095, 0.09, 1))],
        'SM_CrossingSignReal': [mat_galv('MB_Crossing_Metal'), mat_plain('MB_Crossing_White', (0.62, 0.62, 0.60, 1), 0.35, 0.08),
                                mat_plain('MB_Crossing_Red', (0.40, 0.025, 0.02, 1), 0.4, 0.08), mat_plain('MB_Crossing_Dark', (0.02, 0.02, 0.02, 1), 0.6)],
        'SM_LilyPadReal': [mat_lilypad('MB_LilyPad')],
    }


def make_props():
    """Copy the earlier prop shapes as *Real objects with the realistic materials."""
    out = {}
    src = {'SM_HydrantReal': 'SM_Hydrant', 'SM_LampReal': 'SM_Lamp', 'SM_BuildingReal': 'SM_Building', 'SM_TrainReal': 'SM_Train',
           'SM_CrossingSignReal': 'SM_CrossingSign', 'SM_LilyPadReal': 'SM_LilyPad'}
    mats = prop_materials()
    for new, old in src.items():
        o = bpy.data.objects[old]
        remove(new)
        me = o.data.copy(); me.name = new
        ob = link_new(new, me); ob.location = (0, 0, 0)
        for i, mt in enumerate(mats[new]):
            me.materials[i] = mt                        # replace in place, never clear
        out[new] = len(me.materials)
    return out


def bake_prop(name, folder, size=2048):
    lo = bpy.data.objects[name]
    remove(name + '_Src')
    hi = link_new(name + '_Src', lo.data.copy()); hi.location = lo.location
    files = bake_set(hi, lo, folder, 'T_' + name[3:], size, 0.01, 0.55)
    remove(name + '_Src')
    return files


# ---------------------------------------------------------------- ground cover: grass tufts, pebbles, leaf litter (scattered by PCG in Unreal)
def build_lawn_tile():
    """Lawn grass blade: U runs base to tip. Pale base, green body with faint veins, slightly yellow dry tip."""
    m, nt = new_mat('M_LawnTile')
    u, v = uv_sep(nt)
    vein = mth(nt, 'MULTIPLY', mth(nt, 'ADD', mth(nt, 'COSINE', mth(nt, 'MULTIPLY', v, TAU * 5)), 1.0), 0.5)
    uvn = nt.nodes.new('ShaderNodeUVMap'); mp = nt.nodes.new('ShaderNodeMapping')
    L(nt, uvn.outputs[0], mp.inputs['Vector']); mp.inputs['Scale'].default_value = (4, 30, 1)
    tn = nt.nodes.new('ShaderNodeTexNoise'); L(nt, mp.outputs[0], tn.inputs['Vector']); tn.inputs['Scale'].default_value = 3.0
    col = mix(nt, smooth(nt, u, 0.0, 0.2), (0.16, 0.17, 0.09, 1), (0.07, 0.13, 0.03, 1))
    col = mix(nt, tn.outputs['Fac'], col, (0.11, 0.17, 0.04, 1))
    col = mix(nt, smooth(nt, u, 0.82, 1.0), col, (0.20, 0.19, 0.08, 1))
    col = mix(nt, mth(nt, 'MULTIPLY', vein, 0.2), col, (0.14, 0.20, 0.07, 1))
    principled(nt, col, 0.55, vein, 0.0005, 0.4)
    return m


def grass_blades(bm, uv, col, rnd, n, h_range, radius, dry=0.0, lean=0.35, w_range=(0.0035, 0.0065)):
    for k in range(n):
        a = rnd.uniform(0, TAU); r = radius * math.sqrt(rnd.random())
        base = Vector((r * math.cos(a), r * math.sin(a), -0.01))
        out = Vector((math.cos(a + rnd.uniform(-0.6, 0.6)), math.sin(a + rnd.uniform(-0.6, 0.6)), 0))
        H = rnd.uniform(*h_range); bend = rnd.uniform(0.1, lean) * (0.5 + r / max(radius, 1e-3))
        w0 = rnd.uniform(*w_range); seg = 4
        side0 = out.cross(Vector((0, 0, 1))).normalized()
        dried = rnd.random() < dry
        g = rnd.uniform(0.75, 1.15)
        tint = (g * 1.25, g * 1.05, g * 0.7, 1) if dried else (g * rnd.uniform(0.9, 1.05), g, g * rnd.uniform(0.85, 1.0), 1)
        rows = []
        for i in range(seg + 1):
            t = i / seg
            p = base + out * bend * H * t * t * 1.6 + Vector((0, 0, H * (t - 0.45 * bend * t ** 3)))
            rows.append((p, w0 * (1 - t ** 1.4) + 0.0004, t))
        for i in range(seg):
            (pa, wa, ta), (pb, wb, tb) = rows[i], rows[i + 1]
            va = [bm.verts.new(pa + side0 * wa), bm.verts.new(pa + Vector((0, 0, 0.0015))), bm.verts.new(pa - side0 * wa)]
            vb = [bm.verts.new(pb + side0 * wb), bm.verts.new(pb + Vector((0, 0, 0.0015))), bm.verts.new(pb - side0 * wb)]
            for j in range(2):
                f = bm.faces.new([va[j], va[j + 1], vb[j + 1], vb[j]]); f.material_index = 0; f.smooth = True
                for lp, u_, v_ in zip(f.loops, [ta, ta, tb, tb], [j * 0.5, (j + 1) * 0.5, (j + 1) * 0.5, j * 0.5]):
                    shade = 0.55 + 0.45 * u_                       # darker near the ground
                    lp[uv].uv = (u_, v_); lp[col] = (tint[0] * shade, tint[1] * shade, tint[2] * shade, 1)


def build_grass(name, seed, n, h_range, radius, dry=0.0, seed_heads=0):
    rnd = random.Random(seed)
    bm = bmesh.new(); uv = bm.loops.layers.uv.new('UVMap'); col = bm.loops.layers.color.new('Col')
    grass_blades(bm, uv, col, rnd, n, h_range, radius, dry)
    for k in range(seed_heads):                     # thin stalks with a seed head
        a = rnd.uniform(0, TAU); r = radius * 0.5 * rnd.random()
        base = Vector((r * math.cos(a), r * math.sin(a), -0.01)); H = h_range[1] * rnd.uniform(1.3, 1.7)
        lean = Vector((math.cos(a), math.sin(a), 0)) * rnd.uniform(0.02, 0.08)
        stem = [base + lean * (i / 4) ** 2 + Vector((0, 0, H * i / 4)) for i in range(5)]
        bark_tube(bm, uv, col, stem, [0.0012] * 5, 3, lambda p: 0.8)
        top = stem[-1]; tdir = (stem[-1] - stem[-2]).normalized()
        hp = [top - tdir * 0.05, top - tdir * 0.03, top]
        bark_tube(bm, uv, col, hp, [0.0025, 0.004, 0.0015], 5, lambda p: 1.0)
    for f in bm.faces:                               # stems/heads sample the pale-green part of the blade
        for lp in f.loops:
            if lp[uv].uv.x > 1.001 or lp[uv].uv.y > 1.001:
                lp[uv].uv = (0.3 + (lp[uv].uv.y % 1.0) * 0.2, 0.45 + (lp[uv].uv.x % 1.0) * 0.1)
    return finish_mesh(name, bm, ['M_Lawn'])


def build_pebbles(name='SM_Pebbles', seed=3):
    rnd = random.Random(seed)
    bm = bmesh.new()
    for k in range(rnd.randint(5, 8)):
        c = Vector((rnd.uniform(-0.12, 0.12), rnd.uniform(-0.12, 0.12), 0)); s = rnd.uniform(0.012, 0.045)
        tmp = bmesh.new(); bmesh.ops.create_icosphere(tmp, subdivisions=2, radius=1.0)
        sq = (rnd.uniform(0.8, 1.2), rnd.uniform(0.7, 1.0), rnd.uniform(0.45, 0.7))
        m = {}
        for v in tmp.verts:
            p = v.co * (1 + 0.18 * noise.noise(v.co * 1.7 + Vector((k * 3.1, seed, 0))))
            m[v] = bm.verts.new(c + Vector((p.x * s * sq[0], p.y * s * sq[1], p.z * s * sq[2] - s * 0.2)))
        for f in tmp.faces:
            nf = bm.faces.new([m[v] for v in f.verts]); nf.smooth = True
        tmp.free()
    me = bpy.data.meshes.new(name); me.materials.append(bpy.data.materials.get('M_RockReal_Game') or bpy.data.materials.new('M_RockReal_Game'))
    bm.normal_update(); bm.to_mesh(me); bm.free()
    ob = link_new(name, me); select_only(ob)
    bpy.ops.object.mode_set(mode='EDIT'); bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.uv.smart_project(angle_limit=math.radians(60), island_margin=0.02)
    bpy.ops.object.mode_set(mode='OBJECT')
    return {'tris': sum(len(p.vertices) - 2 for p in me.polygons)}


def build_litter(name='SM_Litter', seed=9):
    """A few fallen, browned leaves lying flat-ish, plus a twig."""
    rnd = random.Random(seed)
    bm = bmesh.new(); uv = bm.loops.layers.uv.new('UVMap'); col = bm.loops.layers.color.new('Col')
    for k in range(2):
        a = rnd.uniform(0, TAU); d = Vector((math.cos(a), math.sin(a), 0))
        start = Vector((rnd.uniform(-0.12, 0.12), rnd.uniform(-0.12, 0.12), 0.004))
        pts = bend_path(start, d, rnd.uniform(0.12, 0.25), 4, rnd, 0.0, 0.15)
        for p in pts: p.z = 0.004
        bark_tube(bm, uv, col, pts, [0.004 * (1 - 0.5 * i / 4) for i in range(5)], 4, lambda p: 0.7)
    for k in range(rnd.randint(6, 9)):
        a = rnd.uniform(0, TAU); d = Vector((math.cos(a), math.sin(a), rnd.uniform(-0.05, 0.1))).normalized()
        base = Vector((rnd.uniform(-0.16, 0.16), rnd.uniform(-0.16, 0.16), 0.006))
        up = Vector((rnd.uniform(-0.2, 0.2), rnd.uniform(-0.2, 0.2), 1)).normalized()
        if abs(d.dot(up)) > 0.9: up = Vector((0, 0, 1))
        shade = autumn_tint(rnd, rnd.uniform(0.55, 0.8))
        shade = (shade[0] * 0.8, shade[1] * 0.65, shade[2] * 0.55, 1)       # browned on the ground
        before = set(bm.faces)
        leaf(bm, uv, col, base, d, up, rnd.uniform(0.06, 0.09), shade)
        for v in {v for f in set(bm.faces) - before for v in f.verts}:
            v.co.z = max(0.003, v.co.z * 0.35 + 0.004)                        # lying on the ground
    return finish_mesh(name, bm, ['M_TreeBark', 'M_TreeLeafAutumn'])


# ---------------------------------------------------------------- river edge stones and ice floes
def stone(bm, c, size, seed, sub=3):
    tmp = bmesh.new(); bmesh.ops.create_icosphere(tmp, subdivisions=sub, radius=1.0)
    rnd = random.Random(seed)
    sq = Vector((rnd.uniform(0.9, 1.3), rnd.uniform(0.8, 1.2), rnd.uniform(0.5, 0.8)))
    planes = []
    for k in range(5):
        a = rnd.uniform(0, TAU); el = rnd.uniform(-0.2, 1.0)
        n = Vector((math.cos(a) * math.cos(el), math.sin(a) * math.cos(el), math.sin(el)))
        planes.append((n, rnd.uniform(0.72, 0.9)))
    m = {}
    for v in tmp.verts:
        p = v.co.copy()
        for n, d in planes:
            s = p.dot(n) - d
            if s > 0: p -= n * s * 0.9
        p *= 1 + 0.06 * noise.noise(p * 2.5 + Vector((seed, 0, 0)))
        m[v] = bm.verts.new(c + Vector((p.x * sq.x, p.y * sq.y, p.z * sq.z)) * size)
    for f in tmp.faces:
        nf = bm.faces.new([m[v] for v in f.verts]); nf.smooth = True
    tmp.free()


def build_bank_stones(name='SM_BankStones', seed=40, length=2.0):
    """A 2 m run of mossy edge stones along Y, to line a river bank (tiles end to end)."""
    rnd = random.Random(seed); bm = bmesh.new()
    y = -length / 2
    while y < length / 2:
        s = rnd.uniform(0.09, 0.17)
        stone(bm, Vector((rnd.uniform(-0.04, 0.04), y + s * 0.6, rnd.uniform(-0.03, 0.02))), s, rnd.randint(0, 9999))
        if rnd.random() < 0.6:                          # smaller stones tucked in front and behind
            s2 = rnd.uniform(0.04, 0.08)
            stone(bm, Vector((rnd.choice([-1, 1]) * rnd.uniform(0.09, 0.15), y + rnd.uniform(0, s), -0.02)), s2, rnd.randint(0, 9999), 2)
        y += s * rnd.uniform(1.1, 1.5)
    me = bpy.data.meshes.new(name); me.materials.append(bpy.data.materials['M_RockReal'])
    bm.normal_update(); bm.to_mesh(me); bm.free()
    ob = link_new(name, me); select_only(ob)
    bpy.ops.object.mode_set(mode='EDIT'); bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.uv.smart_project(angle_limit=math.radians(60), island_margin=0.004)
    bpy.ops.object.mode_set(mode='OBJECT')
    return {'tris': sum(len(p.vertices) - 2 for p in me.polygons), 'dims': tuple(round(x, 2) for x in ob.dimensions)}


def mat_ice(name='MB_Ice'):
    m, nt = new_mat(name); P, (px, py, pz), (nx, ny, nz) = obj_coords(nt)
    top = smooth(nt, nz, 0.5, 0.85)
    wp = tex(nt, 'ShaderNodeTexNoise', P, 3.0, Detail=3.0)
    wv = nt.nodes.new('ShaderNodeVectorMath'); wv.operation = 'MULTIPLY_ADD'
    L(nt, wp.outputs['Color'], wv.inputs[0]); wv.inputs[1].default_value = (0.25, 0.25, 0.25); L(nt, P, wv.inputs[2])
    cr = tex(nt, 'ShaderNodeTexVoronoi', wv.outputs[0], 2.2); cr.feature = 'DISTANCE_TO_EDGE'
    fn = tex(nt, 'ShaderNodeTexNoise', P, 14.0, Detail=8.0); big = tex(nt, 'ShaderNodeTexNoise', P, 2.5, Detail=4.0)
    cm = tex(nt, 'ShaderNodeTexNoise', P, 1.8, Detail=2.0)
    crack = mth(nt, 'MULTIPLY', smooth(nt, cr.outputs['Distance'], 0.009, 0.0), smooth(nt, cm.outputs['Fac'], 0.45, 0.55))
    side = mix(nt, smooth(nt, pz, -0.1, 0.08), (0.10, 0.25, 0.32, 1), (0.42, 0.60, 0.68, 1))      # blue-green depth on the sides
    snow = mix(nt, fn.outputs['Fac'], (0.62, 0.66, 0.70, 1), (0.85, 0.88, 0.92, 1))
    bare = smooth(nt, big.outputs['Fac'], 0.55, 0.62)                                              # patches of bare ice on top
    topc = mix(nt, bare, snow, (0.30, 0.42, 0.48, 1))
    col = mix(nt, top, side, topc)
    col = mix(nt, mth(nt, 'MULTIPLY', crack, 0.45), col, (0.2, 0.3, 0.34, 1))
    rough = mth(nt, 'ADD', 0.08, mth(nt, 'MULTIPLY', mth(nt, 'MULTIPLY', top, mth(nt, 'SUBTRACT', 1.0, bare)), 0.6))
    h = mth(nt, 'SUBTRACT', mth(nt, 'MULTIPLY', fn.outputs['Fac'], mth(nt, 'MULTIPLY', top, 0.6)), mth(nt, 'MULTIPLY', crack, 0.8))
    principled(nt, col, rough, h, 0.003)
    return m


def build_ice_floe(name='SM_IceFloe', seed=6):
    """1 m x 1 m x 22 cm slab with a broken outline, centred on the origin (scaled by length in Unreal)."""
    rnd = random.Random(seed); bm = bmesh.new()
    n = 48; rings = []
    for z, inset in [(-0.11, 0.06), (0.06, 0.0), (0.10, 0.025)]:
        ring = []
        for k in range(n):
            a = TAU * k / n
            r = 0.5 * (1 + 0.07 * noise.noise(Vector((math.cos(a), math.sin(a), seed)) * 2.2)) - inset
            sx = math.copysign(abs(math.cos(a)) ** 0.35, math.cos(a)); sy = math.copysign(abs(math.sin(a)) ** 0.35, math.sin(a))
            ring.append(bm.verts.new((sx * r, sy * r, z + (0.012 * noise.noise(Vector((a, z, seed))) if z > 0 else 0))))
        rings.append(ring)
    for i in range(len(rings) - 1):
        for k in range(n):
            bm.faces.new([rings[i][k], rings[i][(k + 1) % n], rings[i + 1][(k + 1) % n], rings[i + 1][k]])
    bm.faces.new(rings[-1]); bm.faces.new(list(reversed(rings[0])))
    top = [f for f in bm.faces if len(f.verts) == n and f.calc_center_median().z > 0]
    bmesh.ops.triangulate(bm, faces=top)
    res = bmesh.ops.subdivide_edges(bm, edges=[e for e in bm.edges if all(v.co.z > 0.09 for v in e.verts)], cuts=4, use_grid_fill=True)
    for v in bm.verts:
        if v.co.z > 0.09: v.co.z += 0.01 * noise.noise(v.co * 6 + Vector((seed, 0, 0)))
    me = bpy.data.meshes.new(name); me.materials.append(mat_ice())
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.normal_update(); bm.to_mesh(me); bm.free()
    ob = link_new(name, me); select_only(ob)
    bpy.ops.object.shade_smooth_by_angle(angle=math.radians(40))
    for mod in list(ob.modifiers): bpy.ops.object.modifier_apply(modifier=mod.name)
    bpy.ops.object.mode_set(mode='EDIT'); bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.uv.smart_project(angle_limit=math.radians(60), island_margin=0.01)
    bpy.ops.object.mode_set(mode='OBJECT')
    return {'tris': sum(len(p.vertices) - 2 for p in me.polygons), 'dims': tuple(round(x, 2) for x in ob.dimensions)}


def export(folder, names=('SM_RockReal', 'SM_TreeReal')):
    os.makedirs(folder, exist_ok=True)
    for nm in names:
        o = bpy.data.objects[nm]; select_only(o)
        bpy.ops.export_scene.fbx(filepath=os.path.join(folder, nm + '.fbx'), use_selection=True, object_types={'MESH'},
                                 apply_unit_scale=True, apply_scale_options='FBX_SCALE_NONE', axis_forward='-Z', axis_up='Y',
                                 mesh_smooth_type='FACE', add_leaf_bones=False, bake_anim=False, embed_textures=False,
                                 colors_type='SRGB')  # Unreal reads FBX vertex colours as sRGB
