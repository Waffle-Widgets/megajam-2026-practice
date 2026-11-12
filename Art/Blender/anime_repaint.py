# Repaint an AI-generated character as flat anime colour. Headless:
#   blender -b --factory-startup --python Art/Blender/anime_repaint.py -- <Name> <front_drawing_cutout.png> [out.png]
# For a character rigged by trellis_character.py (Art/Blender/cache/<Name>.blend) that was generated from ONE front
# drawing. The generator's own texture is blotchy on flat-coloured drawings (smeared trousers, blank eyes), so:
#   - the front of the model gets the drawing itself, projected straight on (face, line art and all);
#   - the back and sides get flat colours sampled from the drawing, chosen per texel from its height on the body and
#     the generator's colour there (dark = hair/trousers, pale = shirt, warm = skin, the rest = jacket).
# It also replaces the generator's UV layout (thousands of tiny islands that smear together at a distance) with a
# clean one, and saves the .blend, so walk_cycle.py exports the new layout. Run it BEFORE walk_cycle.py.
# Works in the texture's own space: the 3D position and normal of every texel are baked first, then numpy paints.
# Writes Art/Blender/export/Characters/<Name>/T_<Name>_BaseColor.png (or out.png) and a 4-view check sheet in cache/.
import bpy, sys, os, math, json
import numpy as np
from mathutils import Vector

a = sys.argv[sys.argv.index('--') + 1:]
NAME, REF = a[0], a[1]
REPO = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..'))
CACHE = os.path.join(REPO, 'Art', 'Blender', 'cache')
OUT = a[2] if len(a) > 2 else os.path.join(REPO, 'Art', 'Blender', 'export', 'Characters', NAME, 'T_%s_BaseColor.png' % NAME)
W = 2048
log = {}

bpy.ops.wm.open_mainfile(filepath=os.path.join(CACHE, NAME + '.blend'))
sc = bpy.context.scene
rig = [o for o in sc.objects if o.type == 'ARMATURE'][0]
mesh = [o for o in sc.objects if o.type == 'MESH' and any(m.type == 'ARMATURE' for m in o.modifiers)][0]
rig.data.pose_position = 'REST'
bpy.context.view_layer.update()
mat = mesh.active_material
nt = mat.node_tree
src_node = [n for n in nt.nodes if n.type == 'TEX_IMAGE' and n.image][0]
src = src_node.image


def pixels(img):
    arr = np.empty(img.size[0] * img.size[1] * 4, np.float32)
    img.pixels.foreach_get(arr)
    return arr.reshape(img.size[1], img.size[0], 4)       # row 0 = bottom


# ---------- 0. clean UVs ----------
me = mesh.data
old_uv = me.uv_layers[0].name
uvmap = nt.nodes.new('ShaderNodeUVMap'); uvmap.uv_map = old_uv
nt.links.new(uvmap.outputs['UV'], src_node.inputs['Vector'])           # the generator's texture keeps its own layout
new_uv = me.uv_layers.new(name='UVClean')
me.uv_layers.active = new_uv; new_uv.active_render = True
for o in sc.objects: o.select_set(False)
mesh.select_set(True); bpy.context.view_layer.objects.active = mesh
bpy.ops.object.mode_set(mode='EDIT')
bpy.ops.mesh.select_all(action='SELECT')
bpy.ops.uv.smart_project(angle_limit=math.radians(66), island_margin=0.003, correct_aspect=True)
bpy.ops.object.mode_set(mode='OBJECT')
log['uv'] = 'smart_project'

# ---------- 1. bake each texel's position and normal ----------
sc.render.engine = 'CYCLES'
sc.cycles.samples = 1
sc.cycles.device = 'CPU'
out_node = [n for n in nt.nodes if n.type == 'OUTPUT_MATERIAL' and n.is_active_output][0]
old = out_node.inputs['Surface'].links[0].from_socket if out_node.inputs['Surface'].links else None
geo = nt.nodes.new('ShaderNodeNewGeometry')
mad = nt.nodes.new('ShaderNodeVectorMath'); mad.operation = 'MULTIPLY_ADD'
emi = nt.nodes.new('ShaderNodeEmission')
tgt_node = nt.nodes.new('ShaderNodeTexImage')
nt.links.new(mad.outputs['Vector'], emi.inputs['Color'])
nt.links.new(emi.outputs['Emission'], out_node.inputs['Surface'])
for o in sc.objects: o.select_set(False)
mesh.select_set(True); bpy.context.view_layer.objects.active = mesh


def bake(socket, scale, offset, name):
    for l in list(mad.inputs[0].links): nt.links.remove(l)
    nt.links.new(geo.outputs[socket], mad.inputs[0])
    mad.inputs[1].default_value = (scale, scale, scale); mad.inputs[2].default_value = (offset, offset, offset)
    img = bpy.data.images.new(name, W, W, float_buffer=True, is_data=True)
    tgt_node.image = img; nt.nodes.active = tgt_node
    bpy.ops.object.bake(type='EMIT', margin=16, use_clear=True)
    return pixels(img)


P = bake('Position', 0.25, 0.5, 'bake_pos')                # +-2 m -> 0..1
N = bake('Normal', 0.5, 0.5, 'bake_nrm')
pos = (P[..., :3] - 0.5) / 0.25
nrm = (N[..., :3] - 0.5) / 0.5
covered = P[..., 3] > 0.5
for l in list(emi.inputs['Color'].links): nt.links.remove(l)
nt.links.new(src_node.outputs['Color'], emi.inputs['Color'])
gimg = bpy.data.images.new('bake_gen', W, W, float_buffer=True, is_data=True)
tgt_node.image = gimg; nt.nodes.active = tgt_node
bpy.ops.object.bake(type='EMIT', margin=16, use_clear=True)
gen = np.clip(pixels(gimg)[..., :3], 0.0, 1.0) ** (1.0 / 2.2)           # back to the 0..1 values the file holds
if old: nt.links.new(old, out_node.inputs['Surface'])
nt.nodes.active = src_node

# ---------- 2. line the drawing up with the model's front view ----------
corners = [mesh.matrix_world @ Vector(c) for c in mesh.bound_box]
xs = [c.x for c in corners]; zs = [c.z for c in corners]
x0, x1, z0, z1 = min(xs), max(xs), min(zs), max(zs)
H = z1 - z0
ref_img = bpy.data.images.load(REF)
ref = pixels(ref_img)                                      # sRGB-encoded 0..1, row 0 = bottom
al = ref[..., 3]
rows = np.where(al.max(axis=1) > 0.5)[0]; cols = np.where(al.max(axis=0) > 0.5)[0]
r0, r1, c0, c1 = rows.min(), rows.max(), cols.min(), cols.max()
solid = al > 0.9                                           # shrink by 3 px so the projection never picks up the edge
for dy, dx in ((3, 0), (-3, 0), (0, 3), (0, -3)):
    solid &= np.roll(al, (dy, dx), axis=(0, 1)) > 0.9
log['model_m'] = [round(x1 - x0, 3), round(H, 3)]; log['drawing_px'] = [int(c1 - c0), int(r1 - r0)]
log['aspect_model_vs_drawing'] = [round((x1 - x0) / H, 3), round((c1 - c0) / (r1 - r0), 3)]


def ref_at(u, v):
    """Drawing colour and validity at front-view coordinates u (left-right) and v (bottom-top), both 0..1."""
    col = np.clip(np.rint(c0 + u * (c1 - c0)).astype(int), 0, ref.shape[1] - 1)
    row = np.clip(np.rint(r0 + v * (r1 - r0)).astype(int), 0, ref.shape[0] - 1)
    return ref[row, col, :3], solid[row, col]


def swatch(u, v, half=0.012):
    """Median colour of a small patch of the drawing: a flat colour that ignores thin lines."""
    us, vs = np.meshgrid(np.linspace(u - half, u + half, 15), np.linspace(v - half, v + half, 15))
    c, ok = ref_at(us.ravel(), vs.ravel())
    return np.median(c[ok], axis=0) if ok.sum() > 20 else None


def pick(points, fallback):
    for u, v in points:
        s = swatch(u, v)
        if s is not None: return s
    return np.array(fallback, np.float32)


JACKET = pick([(0.22, 0.70), (0.80, 0.70)], (0.80, 0.56, 0.18))
SHIRT = pick([(0.50, 0.66)], (0.96, 0.96, 0.96))
TROUSER = pick([(0.40, 0.30), (0.62, 0.30)], (0.27, 0.28, 0.30))
HAIR = pick([(0.50, 0.975), (0.44, 0.965)], (0.24, 0.17, 0.13))
SKIN = pick([(0.50, 0.862), (0.50, 0.90)], (0.96, 0.80, 0.69))
SHOE = pick([(0.25, 0.02), (0.75, 0.02)], (0.93, 0.93, 0.94))
log['palette'] = {k: [round(float(x), 3) for x in v] for k, v in
                  (('jacket', JACKET), ('shirt', SHIRT), ('trouser', TROUSER), ('hair', HAIR), ('skin', SKIN), ('shoe', SHOE))}

# ---------- 3. paint ----------
u = (pos[..., 0] - x0) / (x1 - x0)
h = (pos[..., 2] - z0) / H
lum = gen.mean(axis=2); sat = gen.max(axis=2) - gen.min(axis=2)
skinlike = (gen[..., 0] > 0.55) & (gen[..., 0] > gen[..., 2] + 0.12) & (lum > 0.45)
def near(c, target, tol=0.16):
    return np.abs(c - target).max(axis=-1) < tol


def scan_up(uu, lo, hi, target):
    """Lowest height v in lo..hi where the drawing at column uu turns into `target` colour (None if it never does)."""
    for v in np.linspace(lo, hi, 200):
        c, k = ref_at(np.array([uu]), np.array([v]))
        if k[0] and near(c[0], target):
            return float(v)
    return None


# Where the arms are, from the drawing: at hand height it is three blobs (hand, hips, hand).
row = solid[int(round(r0 + 0.455 * (r1 - r0))), c0:c1 + 1]
edges = np.flatnonzero(np.diff(np.concatenate(([0], row.astype(np.int8), [0]))))
runs = [(edges[i], edges[i + 1]) for i in range(0, len(edges), 2) if edges[i + 1] - edges[i] > 8]
n_px = float(c1 - c0)
if len(runs) >= 3:
    arm_lo, arm_hi = (runs[0][1] + runs[1][0]) / 2.0 / n_px, (runs[-2][1] + runs[-1][0]) / 2.0 / n_px
    arm_mid = (runs[0][0] + runs[0][1]) / 2.0 / n_px
else:
    arm_lo, arm_hi, arm_mid = 0.20, 0.80, 0.10
hem = scan_up(0.33, 0.40, 0.62, JACKET) or 0.515           # bottom edge of the jacket on the body
cuff = scan_up(arm_mid, 0.38, 0.62, JACKET) or 0.50        # bottom edge of the sleeve on the arm
log['arms_u'] = [round(arm_lo, 3), round(arm_hi, 3)]; log['hem'] = round(hem, 3); log['cuff'] = round(cuff, 3)

orange = (gen[..., 0] > 0.28) & (gen[..., 0] > 1.6 * gen[..., 2])       # the generator's jacket colour
arm = ((u < arm_lo) | (u > arm_hi)) & (h < 0.80) & (h > 0.36)
flat = np.empty((W, W, 3), np.float32)
flat[:] = JACKET
flat[(lum > 0.70) & (sat < 0.16) & (-nrm[..., 1] > -0.2) & (np.abs(u - 0.5) < 0.14) & (h > hem - 0.02) & (h < 0.84)] = SHIRT   # only the strip between the jacket's edges: pale texels under the arms are jacket
flat[skinlike & (h > 0.80)] = SKIN                                       # neck
flat[(h < hem) & ~arm] = TROUSER
flat[arm & (h < cuff)] = SKIN                                            # hands
flat[(h < hem) & (h > 0.38) & skinlike] = SKIN                           # fingers that reach past the arm's column
flat[(h < 0.075) & (lum > 0.55)] = SHOE
flat[h < 0.04] = SHOE
head = h >= 0.845
flat[head] = SKIN
flat[head & (lum < 0.36)] = HAIR
flat[head & orange & (lum < 0.45) & (h < 0.885)] = JACKET                               # the collar stands up into the head zone
front, ok = ref_at(np.clip(u, 0, 1), np.clip(h, 0, 1))
facing = -nrm[..., 1]                                      # the character faces -Y
w = np.clip((facing - 0.22) / 0.25, 0.0, 1.0)             # only where the surface faces the viewer well: no smears on the sides
w = (w * w * (3 - 2 * w)) * ok
final = flat * (1 - w[..., None]) + front * w[..., None]
final[~covered] = flat[~covered]
log['front_share'] = round(float((w[covered] > 0.5).mean()), 3)

res = bpy.data.images.new('repaint', W, W, alpha=False)
res.colorspace_settings.name = 'sRGB'
buf = np.ones((W, W, 4), np.float32); buf[..., :3] = final
res.pixels.foreach_set(buf.ravel())
res.filepath_raw = OUT; res.file_format = 'PNG'; res.save()
log['out'] = OUT

# ---------- 3b. keep only the clean layout, show the new texture, save the .blend for walk_cycle.py ----------
for l in list(src_node.inputs['Vector'].links): nt.links.remove(l)
me.uv_layers.remove(me.uv_layers[old_uv])
src_node.image = bpy.data.images.load(OUT)
if old: nt.links.new(old, out_node.inputs['Surface'])
nt.nodes.active = src_node
rig.data.pose_position = 'POSE'         # saved in REST, walk_cycle.py found no movement and keyed a broken walk
bpy.ops.wm.save_mainfile()
log['uv_layers'] = [l.name for l in me.uv_layers]

# ---------- 4. check sheet: the model with the new texture from four sides, unlit ----------
em2 = nt.nodes.new('ShaderNodeEmission')
nt.links.new(src_node.outputs['Color'], em2.inputs['Color'])
nt.links.new(em2.outputs['Emission'], out_node.inputs['Surface'])
world = bpy.data.worlds.new('W'); sc.world = world; world.use_nodes = True
world.node_tree.nodes['Background'].inputs[0].default_value = (0.55, 0.6, 0.65, 1)
cam = bpy.data.objects.new('Cam', bpy.data.cameras.new('Cam')); sc.collection.objects.link(cam); sc.camera = cam
cam.data.type = 'ORTHO'; cam.data.ortho_scale = H * 1.12
sc.render.resolution_x = 420; sc.render.resolution_y = 760; sc.view_settings.view_transform = 'Standard'
ctr = Vector(((x0 + x1) / 2, 0, z0 + H / 2)); tiles = []
for k, ang in enumerate((0, 50, 180, 270)):
    d = Vector((math.sin(math.radians(ang)), -math.cos(math.radians(ang)), 0))
    cam.location = ctr + d * H * 3; cam.rotation_euler = (ctr - cam.location).to_track_quat('-Z', 'Y').to_euler()
    fp = os.path.join(CACHE, '%s_repaint_%d.png' % (NAME, k)); sc.render.filepath = fp
    bpy.ops.render.render(write_still=True); tiles.append(fp)
ims = [pixels(bpy.data.images.load(fp)) for fp in tiles]
sheet = np.concatenate(ims, axis=1)
si = bpy.data.images.new('sheet', sheet.shape[1], sheet.shape[0]); si.pixels.foreach_set(sheet.ravel())
si.filepath_raw = os.path.join(CACHE, NAME + '_repaint_sheet.png'); si.file_format = 'PNG'; si.save()
log['sheet'] = si.filepath_raw
print('REPAINT ' + json.dumps(log))
