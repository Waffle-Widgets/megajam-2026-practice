# Renders 3D models the same way so generators can be compared side by side, and measures what costs cleanup time.
# Headless:
#   blender -b --factory-startup --python Art/Blender/bakeoff_render.py -- <out_dir> <label>=<model.glb|fbx> [...]
# For each model it writes <out_dir>/<label>_<view>.png (5 textured views + 1 shape-only + 1 wireframe close-up, 512 px)
# and <out_dir>/<label>.json with: triangles, vertices, materials, texture sizes, UV islands, loose parts and
# open (non-manifold) edges after welding, and the size it was scaled by. Every model is scaled to 1.8 units tall and
# stood on the ground, so silhouettes compare directly; the camera orbits it, so the facing direction doesn't matter.
import bpy, bmesh, sys, os, json, math
from mathutils import Vector

args = sys.argv[sys.argv.index('--') + 1:]
OUT = args[0]; os.makedirs(OUT, exist_ok=True)
jobs = [a.split('=', 1) for a in args[1:]]
RES = 512


def reset():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    sc.render.engine = 'BLENDER_EEVEE'
    sc.render.resolution_x = sc.render.resolution_y = RES
    sc.render.film_transparent = False
    sc.view_settings.view_transform = 'Standard'
    w = bpy.data.worlds.new('W'); sc.world = w
    w.use_nodes = True
    w.node_tree.nodes['Background'].inputs[0].default_value = (0.42, 0.44, 0.47, 1)
    w.node_tree.nodes['Background'].inputs[1].default_value = 0.9
    for name, rot, power in (('Key', (50, 0, 35), 3.2), ('Fill', (65, 0, -140), 1.2)):
        sun = bpy.data.objects.new(name, bpy.data.lights.new(name, 'SUN'))
        sun.data.energy = power; sun.rotation_euler = [math.radians(v) for v in rot]
        sc.collection.objects.link(sun)
    cam = bpy.data.objects.new('Cam', bpy.data.cameras.new('Cam'))
    cam.data.lens = 70; sc.collection.objects.link(cam); sc.camera = cam
    return sc, cam


def import_model(path):
    before = set(bpy.data.objects)
    if path.lower().endswith(('.glb', '.gltf')):
        bpy.ops.import_scene.gltf(filepath=path)
    else:
        bpy.ops.import_scene.fbx(filepath=path)
    new = [o for o in bpy.data.objects if o not in before]
    meshes = [o for o in new if o.type == 'MESH']
    for o in new:                       # drop armatures/empties' transforms into the meshes, keep only geometry
        if o.type == 'MESH':
            o.select_set(True)
    bpy.context.view_layer.objects.active = meshes[0]
    bpy.ops.object.parent_clear(type='CLEAR_KEEP_TRANSFORM')
    for o in meshes:
        for m in list(o.modifiers):
            o.modifiers.remove(m)       # rest pose only (no armature deform)
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    for o in new:
        if o.type != 'MESH':
            bpy.data.objects.remove(o)
    return meshes


def measure(meshes):
    tris = verts = 0; mats = set(); texs = []
    islands = loose = open_edges = 0
    for o in meshes:
        me = o.data
        for poly in me.polygons:
            tris += len(poly.vertices) - 2
        verts += len(me.vertices)
        for m in me.materials:
            if m:
                mats.add(m.name)
                if m.node_tree:
                    for n in m.node_tree.nodes:
                        if n.type == 'TEX_IMAGE' and n.image:
                            texs.append(f'{n.image.size[0]}x{n.image.size[1]}')
        bm = bmesh.new(); bm.from_mesh(me)
        uv = bm.loops.layers.uv.active
        if uv:                          # UV islands: faces joined across an edge whose UVs match on both sides
            bm.faces.index_update(); bm.verts.index_update()
            parent = list(range(len(bm.faces)))
            def find(i):
                while parent[i] != i:
                    parent[i] = parent[parent[i]]; i = parent[i]
                return i
            for e in bm.edges:
                if len(e.link_faces) != 2:
                    continue
                f1, f2 = e.link_faces
                def uvs(f):
                    d = {}
                    for l in f.loops:
                        d[l.vert.index] = l[uv].uv.copy()
                    return d
                a, b = uvs(f1), uvs(f2)
                if all((a[v.index] - b[v.index]).length < 1e-5 for v in e.verts):
                    pa, pb = find(f1.index), find(f2.index)
                    if pa != pb:
                        parent[pa] = pb
            islands += len({find(i) for i in range(len(bm.faces))})
        bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-5)   # weld UV-seam splits before topology checks
        open_edges += sum(1 for e in bm.edges if not e.is_manifold)
        seen = set()
        for v in bm.verts:                                        # loose parts = connected pieces of geometry
            if v in seen:
                continue
            loose += 1; stack = [v]; seen.add(v)
            while stack:
                for e in stack.pop().link_edges:
                    for x in e.verts:
                        if x not in seen:
                            seen.add(x); stack.append(x)
        bm.free()
    return {'triangles': tris, 'vertices': verts, 'materials': len(mats), 'textures': sorted(set(texs)),
            'uv_islands': islands, 'loose_parts': loose, 'open_edges': open_edges}


def frame(meshes):
    lo = Vector((1e9,) * 3); hi = Vector((-1e9,) * 3)
    for o in meshes:
        for v in o.data.vertices:
            p = o.matrix_world @ v.co
            lo = Vector(map(min, lo, p)); hi = Vector(map(max, hi, p))
    size = hi - lo
    s = 1.8 / max(size.z, 1e-6)
    for o in meshes:                    # 1.8 units tall, centred, standing on z = 0
        o.location = (-(lo.x + hi.x) / 2 * s, -(lo.y + hi.y) / 2 * s, -lo.z * s)
        o.scale = (s, s, s)
    bpy.context.view_layer.update()
    return s, size * s


def shoot(sc, cam, path, yaw_deg, pitch_deg, dist, target_z):
    yaw, pitch = math.radians(yaw_deg), math.radians(pitch_deg)
    t = Vector((0, 0, target_z))
    cam.location = t + Vector((math.sin(yaw) * math.cos(pitch), -math.cos(yaw) * math.cos(pitch), math.sin(pitch))) * dist
    cam.rotation_euler = (t - cam.location).to_track_quat('-Z', 'Y').to_euler()
    sc.render.filepath = path
    bpy.ops.render.render(write_still=True)


for label, path in jobs:
    sc, cam = reset()
    meshes = import_model(path)
    stats = measure(meshes)
    s, size = frame(meshes)
    stats['scaled_by'] = round(s, 4); stats['file'] = path
    stats['size_after_scaling'] = [round(c, 3) for c in size]
    span = max(size.x, size.y, size.z)
    d = span * 2.6
    for i, yaw in enumerate((0, 45, 90, 180, 270)):
        shoot(sc, cam, os.path.join(OUT, f'{label}_v{i}.png'), yaw, 12, d, size.z * 0.5)
    # shape only: plain clay material, to judge the geometry without the paint
    clay = bpy.data.materials.new('Clay'); clay.diffuse_color = (0.75, 0.75, 0.75, 1)
    clay.use_nodes = True
    bsdf = clay.node_tree.nodes['Principled BSDF']; bsdf.inputs['Base Color'].default_value = (0.7, 0.7, 0.7, 1)
    bsdf.inputs['Roughness'].default_value = 0.6
    saved = {o.name: [m for m in o.data.materials] for o in meshes}
    for o in meshes:
        for i in range(len(o.data.materials)):
            o.data.materials[i] = clay
        if not o.data.materials:
            o.data.materials.append(clay)
    shoot(sc, cam, os.path.join(OUT, f'{label}_clay.png'), 45, 12, d, size.z * 0.5)
    wire = bpy.data.materials.new('Wire'); wire.use_nodes = True
    wire.node_tree.nodes['Principled BSDF'].inputs['Base Color'].default_value = (0.02, 0.02, 0.03, 1)
    for o in meshes:                    # wireframe close-up of the top third (face / roof) to show the topology
        o.data.materials.append(wire)   # last slot: the wire's material index is clamped onto it
        wf = o.modifiers.new('WF', 'WIREFRAME'); wf.thickness = 0.003 / s; wf.use_replace = False
        wf.use_even_offset = False; wf.material_offset = len(o.data.materials) - 1
    shoot(sc, cam, os.path.join(OUT, f'{label}_wire.png'), 45, 15, d * 0.45, size.z * 0.8)
    json.dump(stats, open(os.path.join(OUT, f'{label}.json'), 'w'), indent=1)
    print('BAKEOFF', label, json.dumps(stats))
