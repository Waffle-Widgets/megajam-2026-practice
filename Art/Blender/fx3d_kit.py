"""Shapes for 3D effects without Niagara (from the Deep Archive HD-2D test's Fire Blast and Mega Beam). Headless:
    blender -b --factory-startup --python Art/Blender/fx3d_kit.py
Writes Art/Blender/export/FX3D/SM_<Piece>.fbx and a check render Art/Blender/cache/fx3d_kit.png.
All pieces are centred on their origin and 1 m across (Unreal's basic shapes convention: scale 1 = 100 cm), so a
Blueprint scales them by "size in cm / 100". The look (colour, flicker, flow, fading) is all in the Unreal materials:
  Blob3D     a round ball with plenty of points, so the fire material can push it into lumpy, moving flames
  Sparks3D   40 thin streaks shooting out from the middle; UV u runs from the root (0) to the tip (1), so the material
             can shorten them toward their tips as they fly out
  Tube3D     an open tube along Z (-0.5..0.5 m), 0.5 m radius, cut into rings along its length; UV u runs along the
             tube (0 at -Z, 1 at +Z) and v around it, so the beam material can make energy flow along it
"""
import bpy, bmesh, math, os, random
from mathutils import Vector

REPO = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..'))
OUT = os.path.join(REPO, 'Art', 'Blender', 'export', 'FX3D'); os.makedirs(OUT, exist_ok=True)
CACHE = os.path.join(REPO, 'Art', 'Blender', 'cache'); os.makedirs(CACHE, exist_ok=True)
bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene
rnd = random.Random(11)
made = []


def export(o):
    for x in sc.objects: x.select_set(x is o)
    bpy.context.view_layer.objects.active = o
    fbx = os.path.join(OUT, f'SM_{o.name}.fbx')
    bpy.ops.export_scene.fbx(filepath=fbx, use_selection=True, axis_forward='-Z', axis_up='Y', global_scale=1.0,
                             apply_unit_scale=True, apply_scale_options='FBX_SCALE_UNITS', mesh_smooth_type='FACE',
                             path_mode='STRIP', embed_textures=False, bake_anim=False, add_leaf_bones=False)
    V = [v.co for v in o.data.vertices]
    size = [round(max(v[i] for v in V) - min(v[i] for v in V), 3) for i in range(3)]
    made.append((o.name, sum(len(p.vertices) - 2 for p in o.data.polygons), size))


def new_obj(name, bm):
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me); bm.free()
    o = bpy.data.objects.new(name, me); sc.collection.objects.link(o)
    return o


# ---- Blob3D
bm = bmesh.new()
bmesh.ops.create_icosphere(bm, subdivisions=5, radius=0.5)
uv = bm.loops.layers.uv.new('UV')
for f in bm.faces:
    f.smooth = True
    for l in f.loops:
        p = l.vert.co
        l[uv].uv = (0.5 + math.atan2(p.y, p.x) / (2 * math.pi), 0.5 + p.z)
export(new_obj('Blob3D', bm))

# ---- Sparks3D: diamond streaks (root point, a ring of 4 a third of the way out, tip point)
bm = bmesh.new()
uv = bm.loops.layers.uv.new('UV')
N = 40
for i in range(N):
    # spread over the sphere (golden spiral), jittered, a little more upward than downward
    z = 1 - 2 * (i + 0.5) / N
    z = max(-0.55, min(1.0, z + rnd.uniform(-0.08, 0.08)))
    a = i * math.pi * (3 - math.sqrt(5)) + rnd.uniform(-0.3, 0.3)
    r = math.sqrt(max(0.0, 1 - z * z))
    d = Vector((r * math.cos(a), r * math.sin(a), z)).normalized()
    side = d.cross(Vector((0, 0, 1)) if abs(d.z) < 0.9 else Vector((1, 0, 0))).normalized()
    up = d.cross(side).normalized()
    r0, r1 = rnd.uniform(0.06, 0.14), rnd.uniform(0.34, 0.5)
    w = rnd.uniform(0.012, 0.022)
    tm = 0.3
    root = bm.verts.new(d * r0)
    tip = bm.verts.new(d * r1)
    mid = d * (r0 + (r1 - r0) * tm)
    ring = [bm.verts.new(mid + (side * math.cos(k * math.pi / 2) + up * math.sin(k * math.pi / 2)) * w) for k in range(4)]
    for k in range(4):
        a_, b_ = ring[k], ring[(k + 1) % 4]
        for tri, us in (((root, b_, a_), (0, tm, tm)), ((a_, b_, tip), (tm, tm, 1))):
            f = bm.faces.new(tri)
            for l, u in zip(f.loops, us):
                l[uv].uv = (u, 0.5)
export(new_obj('Sparks3D', bm))

# ---- Tube3D: open, 32 around, 48 rings along
bm = bmesh.new()
uv = bm.loops.layers.uv.new('UV')
SEG, RINGS = 32, 48
rows = []
for j in range(RINGS + 1):
    zz = -0.5 + j / RINGS
    rows.append([bm.verts.new((0.5 * math.cos(2 * math.pi * k / SEG), 0.5 * math.sin(2 * math.pi * k / SEG), zz))
                 for k in range(SEG)])
for j in range(RINGS):
    for k in range(SEG):
        k2 = (k + 1) % SEG
        f = bm.faces.new((rows[j][k], rows[j][k2], rows[j + 1][k2], rows[j + 1][k]))
        f.smooth = True
        for l, (uu, vv) in zip(f.loops, ((j / RINGS, k / SEG), (j / RINGS, (k + 1) / SEG),
                                          ((j + 1) / RINGS, (k + 1) / SEG), ((j + 1) / RINGS, k / SEG))):
            l[uv].uv = (uu, vv)
bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
export(new_obj('Tube3D', bm))

# ---- check render
for i, o in enumerate(sc.objects):
    o.location.x = (i - 1) * 1.4
cam = bpy.data.objects.new('cam', bpy.data.cameras.new('cam')); sc.collection.objects.link(cam)
cam.location = (0, -4.2, 1.6); cam.rotation_euler = (math.radians(72), 0, 0); sc.camera = cam
sun = bpy.data.objects.new('sun', bpy.data.lights.new('sun', 'SUN')); sc.collection.objects.link(sun)
sun.rotation_euler = (0.6, 0.2, 0.4)
sc.render.engine = 'BLENDER_WORKBENCH'
sc.render.resolution_x, sc.render.resolution_y = 960, 400
sc.render.filepath = os.path.join(CACHE, 'fx3d_kit.png')
bpy.ops.render.render(write_still=True)
for m in made:
    print('FX3D', m)
