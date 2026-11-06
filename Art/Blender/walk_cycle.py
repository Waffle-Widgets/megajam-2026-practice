# Looping walk (human) or trot (dog) for a character rigged by trellis_character.py. Headless:
#   blender -b --factory-startup --python Art/Blender/walk_cycle.py -- <Name> human|dog
# Opens Art/Blender/cache/<Name>.blend, keys one loop on the rig, writes
#   Art/Blender/export/Characters/SK_<Name>_Walk.fbx  (mesh + rig + the "Walk" action, outside Content/ on purpose)
#   Art/Blender/cache/<Name>_walk_sheet.png           (8 frames from the side, to check the motion)
# Characters face -Y in Blender (front view), up is +Z, so the side axis is X. Every swing is a rotation about a
# world axis turned into the bone's own frame; the sign of each joint is found by testing which way the end moves,
# so the same script fits any rig with these bone names.
import bpy, math, os, sys, json
from mathutils import Vector, Quaternion, Matrix

args = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else ['CharMan', 'human']
NAME, KIND = args[0], args[1]
D = r"C:\Users\thecl\Projects\megajam-2026-practice\Art\Blender"
CACHE = os.path.join(D, 'cache'); OUTD = os.path.join(D, 'export', 'Characters'); os.makedirs(OUTD, exist_ok=True)
bpy.ops.wm.open_mainfile(filepath=os.path.join(CACHE, NAME + '.blend'))
sc = bpy.context.scene
rig = [o for o in sc.objects if o.type == 'ARMATURE'][0]
mesh = [o for o in sc.objects if o.type == 'MESH' and any(m.type == 'ARMATURE' and m.object == rig for m in o.modifiers)][0]
# Work in centimetres: 1 Blender unit = 1 cm, rig and mesh scaled 100x and applied, so the FBX holds plain cm numbers
# for the bind pose AND the animation. (With metres, the exporter puts the 100x on the armature object; Unreal's old
# FBX importer used that for the mesh but not for the bone tracks, and the walk crushed the man to under 1 cm.)
sc.unit_settings.scale_length = 0.01
bpy.ops.object.mode_set(mode='OBJECT') if bpy.context.object and bpy.context.object.mode != 'OBJECT' else None
for o in sc.objects: o.select_set(False)
for o in (rig, mesh):
    if o.parent is None:
        o.location = o.location * 100.0; o.scale = o.scale * 100.0
for o in (rig, mesh): o.select_set(True)
bpy.context.view_layer.objects.active = rig
bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
bpy.context.view_layer.update()
pb = rig.pose.bones
log = {'rig': rig.name, 'mesh': mesh.name, 'height_cm': round(mesh.dimensions.z, 1)}

SIDE = Vector((1, 0, 0)); FWD = Vector((0, -1, 0)); UP = Vector((0, 0, 1))
FPS = 30; N = 30 if KIND == 'human' else 16          # one loop: 1.0 s walk, ~0.53 s trot
sc.render.fps = FPS; sc.frame_start = 0; sc.frame_end = N


def local_q(name, axis, deg):
    """Rotation by deg about a world axis, in the bone's rest frame (FK: relative to the posed parent)."""
    m = pb[name].bone.matrix_local.to_3x3()
    return Quaternion((m.inverted() @ axis).normalized(), math.radians(deg))


def reset():
    for b in pb:
        b.rotation_mode = 'QUATERNION'; b.rotation_quaternion = (1, 0, 0, 0); b.location = (0, 0, 0)
    bpy.context.view_layer.update()


def tip(name):
    return pb[name].tail.copy()


def sign_for(name, axis, end, want):
    """+1 or -1 so that rotating `name` about `axis` moves bone `end`'s tip along `want`."""
    reset(); a = tip(end)
    pb[name].rotation_quaternion = local_q(name, axis, 20); bpy.context.view_layer.update()
    s = 1.0 if (tip(end) - a).dot(want) > 0 else -1.0
    reset(); return s


if KIND == 'human':
    legs = [('thigh_l', 'calf_l', 'foot_l', 0.0), ('thigh_r', 'calf_r', 'foot_r', math.pi)]
    arms = [('upperarm_l', 'lowerarm_l', 'hand_l', math.pi), ('upperarm_r', 'lowerarm_r', 'hand_r', 0.0)]
    # thigh swing, knee bend, arm swing, arms in toward the body. trellis_character.py rigs arms hanging ~20 deg out
    # from the body (not a wide A-pose), so AD stays small: 62 drove the arms into the chest and crushed the sleeves.
    SW, KN, AS, AD = 24.0, 36.0, 16.0, 10.0
else:
    legs = [('front_upper_l', 'front_lower_l', 'front_paw_l', 0.0), ('back_upper_r', 'back_lower_r', 'back_paw_r', 0.0),
            ('front_upper_r', 'front_lower_r', 'front_paw_r', math.pi), ('back_upper_l', 'back_lower_l', 'back_paw_l', math.pi)]
    arms = []
    SW, KN = 26.0, 34.0
s_sw = {u: sign_for(u, SIDE, e, FWD) for u, l, e, ph in legs}       # swing: paw/foot goes forward
s_kn = {l: sign_for(l, SIDE, e, -FWD) for u, l, e, ph in legs}      # knee: foot goes back
s_ad = {}; s_as = {}; s_el = {}
for u, l, e, ph in arms:
    x0 = abs(tip(e).x); pb[u].rotation_quaternion = local_q(u, FWD, 20); bpy.context.view_layer.update()
    s_ad[u] = 1.0 if abs(tip(e).x) < x0 else -1.0; reset()           # adduct: hand comes in to the body
    s_as[u] = sign_for(u, SIDE, e, FWD); s_el[l] = sign_for(l, SIDE, e, FWD)
log['signs'] = {'swing': s_sw, 'knee': s_kn, 'adduct': s_ad}

act = bpy.data.actions.new('Walk'); rig.animation_data_create(); rig.animation_data.action = act
pel = pb['pelvis']; pm = pel.bone.matrix_local.to_3x3().inverted()
H = (mesh.dimensions.z if mesh.dimensions.z > 0 else 1.0)
for f in range(N + 1):
    p = 2 * math.pi * (f % N) / N
    reset()
    for u, l, e, ph in legs:
        q = p + ph
        sw = SW * math.sin(q); kn = 6 + KN * max(0.0, math.cos(q))
        pb[u].rotation_quaternion = local_q(u, SIDE, s_sw[u] * sw)
        pb[l].rotation_quaternion = local_q(l, SIDE, s_kn[l] * kn)
    for u, l, e, ph in arms:
        q = p + ph
        add = local_q(u, FWD, s_ad[u] * AD); swing = local_q(u, SIDE, s_as[u] * AS * math.sin(q))
        pb[u].rotation_quaternion = swing @ add
        pb[l].rotation_quaternion = local_q(l, SIDE, s_el[l] * (6 + 10 * max(0.0, math.sin(q))))
    if KIND == 'human':
        pb['spine_01'].rotation_quaternion = local_q('spine_01', UP, 4 * math.sin(p))
        bob = -0.012 * H * math.cos(2 * p)
    else:
        for t, k in (('tail_01', 22), ('tail_02', 14)):
            if t in pb: pb[t].rotation_quaternion = local_q(t, UP, k * math.sin(2 * p))
        if 'head' in pb: pb['head'].rotation_quaternion = local_q('head', SIDE, 4 * math.sin(2 * p))
        bob = -0.02 * H * math.cos(2 * p)
    pel.location = pm @ Vector((0, 0, bob))
    for b in pb:
        b.keyframe_insert('rotation_quaternion', frame=f); b.keyframe_insert('location', frame=f)
log['frames'] = N + 1

# side-view check sheet: 8 frames of one loop
w = bpy.data.worlds.get('W') or bpy.data.worlds.new('W'); sc.world = w
cams = [o for o in sc.objects if o.type == 'CAMERA']
cam = cams[0] if cams else bpy.data.objects.new('Cam', bpy.data.cameras.new('Cam'))
if not cams: sc.collection.objects.link(cam)
sc.camera = cam; cam.data.type = 'ORTHO'; cam.data.ortho_scale = max(mesh.dimensions) * 1.3
ctr = Vector((0, 0, H / 2)); cam.location = ctr + Vector((H * 3, 0, 0)); cam.rotation_euler = (ctr - cam.location).to_track_quat('-Z', 'Y').to_euler()
sc.render.resolution_x = 300; sc.render.resolution_y = 400
import numpy as np
tiles = []
for k in range(8):
    sc.frame_set(int(round(k * N / 8))); fp = os.path.join(CACHE, '%s_walk_%d.png' % (NAME, k))
    sc.render.filepath = fp; bpy.ops.render.render(write_still=True); tiles.append(fp)
ims = [bpy.data.images.load(fp) for fp in tiles]
Wd, Ht = ims[0].size; sheet = np.zeros((Ht, Wd * 8, 4), np.float32)
for k, im in enumerate(ims):
    a = np.empty(Wd * Ht * 4, np.float32); im.pixels.foreach_get(a); sheet[:, k * Wd:(k + 1) * Wd] = a.reshape(Ht, Wd, 4)
img = bpy.data.images.new('walk_sheet', Wd * 8, Ht); img.pixels.foreach_set(sheet.ravel())
img.filepath_raw = os.path.join(CACHE, '%s_walk_sheet.png' % NAME); img.file_format = 'PNG'; img.save()
log['sheet'] = img.filepath_raw
# front views (arms are only readable from the front): 4 frames of the loop, camera on the -Y (face) side
cam.location = ctr + Vector((0, -H * 3, 0)); cam.rotation_euler = (ctr - cam.location).to_track_quat('-Z', 'Y').to_euler()
ft = []
for k in range(4):
    sc.frame_set(int(round(k * N / 4))); fp = os.path.join(CACHE, '%s_walkfront_%d.png' % (NAME, k))
    sc.render.filepath = fp; bpy.ops.render.render(write_still=True); ft.append(fp)
fims = [bpy.data.images.load(fp) for fp in ft]; fs = np.zeros((Ht, Wd * 4, 4), np.float32)
for k, im in enumerate(fims):
    a = np.empty(Wd * Ht * 4, np.float32); im.pixels.foreach_get(a); fs[:, k * Wd:(k + 1) * Wd] = a.reshape(Ht, Wd, 4)
fimg = bpy.data.images.new('walk_front', Wd * 4, Ht); fimg.pixels.foreach_set(fs.ravel())
fimg.filepath_raw = os.path.join(CACHE, '%s_walk_front.png' % NAME); fimg.file_format = 'PNG'; fimg.save()

# export mesh + rig + the Walk action (same axes as trellis_character.py, so it matches the imported skeleton).
# The scene is in centimetres (see the top), so the file's numbers are already cm and every importer reads them right.
sc.frame_set(0)
for o in sc.objects: o.select_set(o in (mesh, rig))
bpy.context.view_layer.objects.active = rig
fbx = os.path.join(OUTD, 'SK_%s_Walk.fbx' % NAME)
bpy.ops.export_scene.fbx(filepath=fbx, use_selection=True, object_types={'ARMATURE', 'MESH'}, axis_forward='-Z', axis_up='Y',
                         global_scale=1.0, apply_unit_scale=True, apply_scale_options='FBX_SCALE_ALL', mesh_smooth_type='FACE',
                         add_leaf_bones=False, primary_bone_axis='Y', secondary_bone_axis='X', bake_anim=True,
                         bake_anim_use_all_actions=False, bake_anim_use_nla_strips=False, bake_anim_force_startend_keying=True,
                         bake_anim_simplify_factor=0.0, path_mode='STRIP', embed_textures=False)
log['fbx'] = fbx
print('WALK ' + json.dumps(log))
