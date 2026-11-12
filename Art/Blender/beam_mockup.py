"""Mock-up pictures of new Mega Beam designs, seen from the game camera (nothing goes into Unreal). Headless:
    blender -b --factory-startup --python Art/Blender/beam_mockup.py -- <out folder>
Renders transparent 1920x1080 PNGs with the game camera (35 degrees down, 81.2 mm cine lens on Unreal's 23.76 mm
filmback, 21.65 m away), beam_<option>_<phase>.png, and beam_info.txt with where the beam starts on screen and how
many pixels one metre is, so the pictures can be laid over a real capture.
  A  clean gold body (white-hot middle, gold, dark orange cartoon outline) + 2 white spiral ribbons with outlines
  B  A + 3 energy rings travelling along the beam
  C  reversed: white-hot body + 3 wide red-orange spiral ribbons with outlines
"""
import bpy, bmesh, math, os, sys

OUT = sys.argv[sys.argv.index('--') + 1] if '--' in sys.argv else os.path.abspath('beam_mock')
os.makedirs(OUT, exist_ok=True)
bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene
sc.render.engine = 'BLENDER_EEVEE'
sc.render.resolution_x, sc.render.resolution_y = 1920, 1080
sc.render.film_transparent = True
sc.view_settings.view_transform = 'Standard'
sc.render.image_settings.file_format = 'PNG'
sc.render.image_settings.color_mode = 'RGBA'

Z = 0.41          # mouth height (m)
LEN = 2.55        # set below from the capture's beam length in pixels
BODY_R = 0.17     # 34 cm body, like the current gold streak tube
RIB_R = 0.20      # ribbons sit just outside the body (44 cm across, the current swirl width)

# ---- camera, the same as the game's
cam_d = bpy.data.cameras.new('Cam'); cam_d.lens = 81.2; cam_d.sensor_fit = 'HORIZONTAL'; cam_d.sensor_width = 23.76
cam = bpy.data.objects.new('Cam', cam_d); sc.collection.objects.link(cam); sc.camera = cam
pitch = math.radians(35); dist = 21.65
cam.location = (0, -dist * math.cos(pitch), Z + dist * math.sin(pitch))
cam.rotation_euler = (math.radians(90) - pitch, 0, 0)


def mat_emit(name, ramp=None, color=None, hull=False):
    m = bpy.data.materials.new(name); m.use_nodes = True
    nt = m.node_tree; nt.nodes.clear()
    out = nt.nodes.new('ShaderNodeOutputMaterial'); em = nt.nodes.new('ShaderNodeEmission')
    nt.links.new(em.outputs[0], out.inputs[0])
    if ramp:
        lw = nt.nodes.new('ShaderNodeLayerWeight'); lw.inputs[0].default_value = 0.5
        cr = nt.nodes.new('ShaderNodeValToRGB'); cr.color_ramp.interpolation = 'CONSTANT'   # cartoon bands
        els = cr.color_ramp.elements
        els[0].position, els[0].color = ramp[0][0], (*ramp[0][1], 1)
        els[1].position, els[1].color = ramp[1][0], (*ramp[1][1], 1)
        for pos, col in ramp[2:]:
            e = els.new(pos); e.color = (*col, 1)
        nt.links.new(lw.outputs['Facing'], cr.inputs[0]); nt.links.new(cr.outputs[0], em.inputs[0])
    else:
        em.inputs[0].default_value = (*color, 1)
    if hull:
        m.use_backface_culling = True
    return m


def srgb(c):  # colours written as screen colours
    return tuple(((x + 0.055) / 1.055) ** 2.4 if x > 0.04045 else x / 12.92 for x in c)


OUTLINE = mat_emit('Outline', color=srgb((0.42, 0.13, 0.03)), hull=True)


def outline(o, th):
    o.data.materials.append(OUTLINE)
    s = o.modifiers.new('Hull', 'SOLIDIFY'); s.thickness = th; s.offset = 1.0
    s.use_flip_normals = True; s.material_offset = len(o.data.materials) - 1; s.use_rim = False


def link(name, bm, mat):
    me = bpy.data.meshes.new(name); bm.to_mesh(me); bm.free()
    o = bpy.data.objects.new(name, me); sc.collection.objects.link(o); me.materials.append(mat)
    for p in me.polygons: p.use_smooth = True
    return o


def tube(name, r, mat):
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=True, segments=48, radius1=r, radius2=r, depth=LEN)
    bmesh.ops.rotate(bm, verts=bm.verts, cent=(0, 0, 0), matrix=__import__('mathutils').Matrix.Rotation(math.radians(90), 3, 'Y'))
    bmesh.ops.translate(bm, verts=bm.verts, vec=(LEN / 2, 0, Z))
    # round the ends a little so it isn't a cut pipe
    return link(name, bm, mat)


def ribbons(name, n, width, pitch, phase, mat, r=RIB_R, th=0.012):
    """n flat stripes wound round the beam like a drill bit; phase turns them (spin)."""
    bm = bmesh.new()
    steps = 220
    for k in range(n):
        prev = None
        for i in range(steps + 1):
            x = LEN * i / steps
            a = 2 * math.pi * (x / pitch) + 2 * math.pi * k / n + phase
            p = []
            for off in (-width / 2, width / 2):
                aa = a + off / r     # stripe width measured around the tube
                for rr in (r, r + th):
                    p.append(bm.verts.new((x, rr * math.cos(aa), Z + rr * math.sin(aa))))
            if prev:
                bm.faces.new((prev[2], prev[0], p[0], p[2]))   # outer face of the stripe (r)
                bm.faces.new((prev[1], prev[3], p[3], p[1]))   # outer face (r + th)
                bm.faces.new((prev[0], prev[1], p[1], p[0]))   # edges
                bm.faces.new((prev[3], prev[2], p[2], p[3]))
            prev = p
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return link(name, bm, mat)


def rings(name, xs, mat):
    bm = bmesh.new()
    M = __import__('mathutils').Matrix
    for x in xs:
        if not (0.15 < x < LEN - 0.1):
            continue
        # a torus made by hand: major 0.235 m, minor 0.035 m
        segs, rs = 40, 10
        ring = []
        for i in range(segs):
            a = 2 * math.pi * i / segs
            row = []
            for j in range(rs):
                b = 2 * math.pi * j / rs
                rr = 0.235 + 0.035 * math.cos(b)
                row.append(bm.verts.new((x + 0.035 * math.sin(b), rr * math.cos(a), Z + rr * math.sin(a))))
            ring.append(row)
        for i in range(segs):
            for j in range(rs):
                a, b = ring[i][j], ring[i][(j + 1) % rs]
                c, d = ring[(i + 1) % segs][(j + 1) % rs], ring[(i + 1) % segs][j]
                bm.faces.new((a, b, c, d))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return link(name, bm, mat)


GOLD_BODY = mat_emit('GoldBody', ramp=[(0.0, srgb((1.0, 0.98, 0.86))), (0.16, srgb((1.0, 0.82, 0.26))),
                                       (0.55, srgb((1.0, 0.64, 0.08))), (0.8, srgb((0.93, 0.42, 0.04)))])
WHITE_BODY = mat_emit('WhiteBody', ramp=[(0.0, srgb((1.0, 1.0, 0.96))), (0.55, srgb((1.0, 0.95, 0.72))),
                                         (0.8, srgb((1.0, 0.82, 0.38)))])
WHITE_RIB = mat_emit('WhiteRib', ramp=[(0.0, srgb((1.0, 1.0, 1.0))), (0.6, srgb((1.0, 0.96, 0.8)))])
RED_RIB = mat_emit('RedRib', ramp=[(0.0, srgb((1.0, 0.42, 0.08))), (0.55, srgb((0.92, 0.25, 0.04)))])
RING = mat_emit('Ring', ramp=[(0.0, srgb((1.0, 1.0, 0.92))), (0.6, srgb((1.0, 0.86, 0.45)))])


def clear():
    for o in list(sc.objects):
        if o.type == 'MESH':
            bpy.data.objects.remove(o)


def project(p):
    from bpy_extras.object_utils import world_to_camera_view
    v = world_to_camera_view(sc, cam, __import__('mathutils').Vector(p))
    return v.x * 1920, (1 - v.y) * 1080


# length: the current beam runs about 505 px on the capture
bpy.context.view_layer.update()   # the camera's matrix, or the projection is garbage
x0, y0 = project((0, 0, Z)); x1, _ = project((1, 0, Z))
# the capture shows 200 px per metre (Smugshi: 62 cm = 124 px); match it by the lens
cam_d.lens *= 200.0 / (x1 - x0)
bpy.context.view_layer.update()
x0, y0 = project((0, 0, Z)); x1, _ = project((1, 0, Z))
pxpm = x1 - x0
LEN = 505 / pxpm
with open(os.path.join(OUT, 'beam_info.txt'), 'w') as fh:
    fh.write(f'{x0:.1f} {y0:.1f} {pxpm:.2f} {LEN:.3f}\n')

PHASES = [0.0, 0.7, 1.4]          # spin steps (radians)
for opt in 'ABC':
    for pi, ph in enumerate(PHASES):
        clear()
        if opt in 'AB':
            b = tube('Body', BODY_R, GOLD_BODY); outline(b, 0.035)
            rb = ribbons('Rib', 2, 0.085, 0.62, ph, WHITE_RIB); outline(rb, 0.02)
            if opt == 'B':
                step = LEN / 3
                rg = rings('Rings', [((i * step) + ph / 1.4 * step * 0.5) % LEN for i in range(3)], RING); outline(rg, 0.018)
        else:
            b = tube('Body', 0.15, WHITE_BODY); outline(b, 0.03)
            rb = ribbons('Rib', 3, 0.13, 0.75, ph, RED_RIB, r=0.18, th=0.03); outline(rb, 0.022)
        sc.render.filepath = os.path.join(OUT, f'beam_{opt}_{pi}.png')
        bpy.ops.render.render(write_still=True)
print('BEAM MOCKUP DONE', OUT)
