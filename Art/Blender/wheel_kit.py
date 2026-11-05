"""Wheel kit: SM_CarWheelV4, modelled on the team's own car (side photo in Art/Reference, not in git).

Ten slim gloss-black spokes in a shallow dish, red pinstripe on the rim lip, five red lug nuts,
a silver brake disc behind the spokes and a red caliper. No lettering or logos on the caliper.

Run inside Blender (Text Editor or the Blender MCP): exec this file, then build_wheel_v4().

Conventions (same as SM_CarWheelV3 in car_kit2.py, so it drops into the same places):
- Origin is the wheel centre, the wheel spins around X, the spoke face points +X.
- Tyre radius 0.135 m, width about 0.108 m.
- Material slots: 0 MC_Tyre, 1 MC_Rim (gloss black), 2 MC_Accent (red), 3 MC_Disc (silver).
"""
import bpy, bmesh, math
from mathutils import Vector, Matrix

WHEEL_R = 0.135
TA = 2 * math.pi
K = WHEEL_R / 0.15               # profiles below are drawn for a 0.15 m tyre, then scaled
TYRE, RIM, ACCENT, DISC = range(4)


def _revolve(bm, pts, mat, seg=64):
    """pts: (radius, x) pairs along a profile; spun around X."""
    rows = [[bm.verts.new((x, r * math.cos(TA * i / seg), r * math.sin(TA * i / seg))) for i in range(seg)] for r, x in pts]
    for a, b in zip(rows, rows[1:]):
        for i in range(seg):
            j = (i + 1) % seg
            bm.faces.new((a[i], a[j], b[j], b[i])).material_index = mat


def _spoke(bm, angle, n=8):
    """One slim spoke from the hub to the rim: tapers in the middle, flares into the rim, dished (hub sits deeper)."""
    R = Matrix.Rotation(angle, 3, 'X')
    rings = []
    for i in range(n + 1):
        t = i / n                                           # 0 hub .. 1 rim
        r = (0.026 + t * 0.070) * K
        x = 0.031 + 0.014 * t ** 0.7                        # dish: rim face sits further out than the hub
        w = (0.0080 - 0.0028 * math.sin(math.pi * t) + 0.0030 * t ** 6) * K   # half-width: slim, flares only at the rim
        d = 0.0055 - 0.0015 * t                             # half-depth (front to back)
        rings.append([bm.verts.new(R @ Vector((x + dx, r, dy * w))) for dx, dy in ((d, -1), (d, 1), (-d, 1), (-d, -1))])
    for a, b in zip(rings, rings[1:]):
        for k in range(4):
            j = (k + 1) % 4
            bm.faces.new((a[k], a[j], b[j], b[k])).material_index = RIM
    bm.faces.new(rings[0][::-1]).material_index = RIM


def _cyl(bm, centre, r, depth, mat, seg=12):
    res = bmesh.ops.create_cone(bm, cap_ends=True, segments=seg, radius1=r, radius2=r, depth=depth,
                                matrix=Matrix.Translation(centre) @ Matrix.Rotation(math.pi / 2, 4, 'Y'))
    for v in res['verts']:
        for f in v.link_faces: f.material_index = mat


def _material(name, col, rough, met):
    m = bpy.data.materials.get(name)
    if m: return m                       # shared with the other kit cars: never recolour an existing material
    m = bpy.data.materials.new(name); m.use_nodes = True
    b = m.node_tree.nodes['Principled BSDF']
    b.inputs['Base Color'].default_value = (*col, 1); b.inputs['Roughness'].default_value = rough
    b.inputs['Metallic'].default_value = met
    return m


def build_wheel_v4(name='SM_CarWheelV4'):
    bm = bmesh.new()
    # tyre: rounded shoulders and a few tread grooves (same profile as V3)
    tyre = [(0.106, 0.050), (0.124, 0.054), (0.140, 0.050), (0.148, 0.040), (0.150, 0.030), (0.146, 0.025), (0.150, 0.020),
            (0.150, 0.006), (0.146, 0.001), (0.146, -0.003), (0.150, -0.008), (0.150, -0.022), (0.146, -0.026), (0.150, -0.031),
            (0.148, -0.041), (0.140, -0.050), (0.124, -0.054), (0.106, -0.050)]
    _revolve(bm, [(r * K, x) for r, x in tyre], TYRE)
    # rim barrel (inside) and the outer lip that the spokes meet
    _revolve(bm, [(r * K, x) for r, x in [(0.106, -0.050), (0.102, -0.040), (0.100, -0.030), (0.099, 0.020)]], RIM)
    _revolve(bm, [(r * K, x) for r, x in [(0.106, 0.050), (0.1045, 0.0475), (0.1015, 0.0465), (0.097, 0.044), (0.095, 0.036), (0.095, 0.020)]], RIM)
    _revolve(bm, [(r * K, x + 0.0004) for r, x in [(0.1045, 0.0475), (0.1015, 0.0465)]], ACCENT)    # red pinstripe on the lip
    # brake disc (silver, seen through the spokes) and the hub face behind it
    _revolve(bm, [(r * K, x) for r, x in [(0.080, 0.008), (0.080, 0.012), (0.034, 0.012), (0.034, 0.008)]], DISC)
    _revolve(bm, [(r * K, x) for r, x in [(0.034, 0.014), (0.0, 0.014)]], RIM)
    # red caliper hugging the disc at the front (towards -Y), no lettering
    cal = bmesh.ops.create_cube(bm, size=1.0)
    for v in cal['verts']:
        a = math.radians(35) + v.co.y * 1.05                          # ~52 degrees of arc, upper front (like the photo)
        rr = (0.058 + (v.co.z + 0.5) * 0.032) * K
        v.co = Vector((0.019 + v.co.x * 0.014, -rr * math.sin(a), rr * math.cos(a)))
    for f in {f for v in cal['verts'] for f in v.link_faces}: f.material_index = ACCENT
    # ten single spokes, evenly spaced
    for s in range(10):
        _spoke(bm, TA * s / 10)
    # centre: gloss-black hub with a small cap, five red lug nuts
    _cyl(bm, (0.031, 0, 0), 0.024 * K, 0.010, RIM, seg=24)
    _cyl(bm, (0.037, 0, 0), 0.010 * K, 0.004, RIM, seg=16)
    for i in range(5):
        a = TA * i / 5 + math.pi / 2
        _cyl(bm, (0.038, 0.017 * K * math.cos(a), 0.017 * K * math.sin(a)), 0.0035 * K, 0.006, ACCENT, seg=6)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-6)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)

    me = bpy.data.meshes.new(name)
    for m in (_material('MC_Tyre', (0.015, 0.015, 0.016), 0.85, 0.0),
              _material('MC_Rim', (0.012, 0.012, 0.013), 0.15, 0.6),
              _material('MC_Accent', (0.5, 0.01, 0.01), 0.3, 0.0),
              _material('MC_Disc', (0.55, 0.55, 0.56), 0.35, 1.0)):
        me.materials.append(m)
    bm.to_mesh(me); bm.free()
    old = bpy.data.objects.get(name)
    if old: bpy.data.objects.remove(old)
    ob = bpy.data.objects.new(name, me); bpy.context.scene.collection.objects.link(ob)
    for o in bpy.context.view_layer.objects: o.select_set(False)
    ob.select_set(True); bpy.context.view_layer.objects.active = ob
    bpy.ops.object.shade_smooth_by_angle(angle=math.radians(40))
    for m in list(ob.modifiers): bpy.ops.object.modifier_apply(modifier=m.name)
    bpy.ops.object.mode_set(mode='EDIT'); bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.uv.smart_project(angle_limit=math.radians(60), island_margin=0.01)
    bpy.ops.object.mode_set(mode='OBJECT')
    return ob
