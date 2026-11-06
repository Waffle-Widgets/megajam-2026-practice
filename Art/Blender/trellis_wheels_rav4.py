# Cut the RAV4 wheels headless: blender -b --factory-startup --python Art/Blender/trellis_wheels_rav4.py [-- "{\"DO_EXPORT\": false}"]
# Adds a sun and sky (the work file has none), runs trellis_wheels.py with the RAV4 sizes, writes cache/rav4_wheels_sheet.jpg.
import bpy, json, sys
R = r"C:\Users\thecl\Projects\megajam-2026-practice\Art\Blender"
bpy.ops.wm.open_mainfile(filepath=R + r"\cache\SM_CarRav4_work.blend")
sc = bpy.context.scene; sc.render.engine = 'BLENDER_EEVEE_NEXT' if 'BLENDER_EEVEE_NEXT' in [e.identifier for e in bpy.types.RenderSettings.bl_rna.properties['engine'].enum_items] else 'BLENDER_EEVEE'
w = bpy.data.worlds.new('VW'); sc.world = w; w.use_nodes = True
w.node_tree.nodes['Background'].inputs[0].default_value = (0.75, 0.78, 0.82, 1); w.node_tree.nodes['Background'].inputs[1].default_value = 0.9
sun = bpy.data.objects.new('VSun', bpy.data.lights.new('VSun', 'SUN')); sun.data.energy = 3.5; sun.rotation_euler = (0.9, 0.2, 0.7); sc.collection.objects.link(sun)
g = dict(SRC='VEH', PFX='RAV', MAT='M_CarRav4', IMG='T_CarRav4_BaseColor', OUT_BODY='SM_CarRav4Body', OUT_WHEEL='SM_CarRav4Wheel',
         TYRE_R=0.15, CUT_PAD=0.006, X_IN=0.21, X_CAP=0.19, X_ORG=0.33, CAND_X=0.36, CAND_R=(0.125, 0.145), PICK=(1, 'front'),
         SP=R + r"\cache", EXPORT_DIR=R + r"\export\Vehicles\CarRav4", SAVE_AS=R + r"\cache\SM_CarRav4_wheels.blend")
g.update(json.loads(sys.argv[sys.argv.index('--') + 1]) if '--' in sys.argv else {})
if 'PICK' in g: g['PICK'] = tuple(g['PICK'])
exec(open(R + r"\trellis_wheels.py").read(), g)
print('WHEELS', json.dumps(g['result']))
import numpy as np
names = ['wh_body_side', 'wh_full_side', 'wh_full_fq', 'wh_full_low', 'wh_wheel_face', 'wh_wheel_back']
ims = []
for n in names:
    im = bpy.data.images.load(g['SP'] + '/%s.png' % n); a = np.empty(im.size[0] * im.size[1] * 4, np.float32); im.pixels.foreach_get(a); ims.append(a.reshape(im.size[1], im.size[0], 4))
h, w_ = ims[0].shape[:2]; S_ = np.ones((3 * h, 2 * w_, 4), np.float32)
for k, a in enumerate(ims):
    r, c = divmod(k, 2); S_[(2 - r) * h:(3 - r) * h, c * w_:(c + 1) * w_] = a
im = bpy.data.images.new('WSheet', 2 * w_, 3 * h); im.pixels.foreach_set(S_.ravel()); im.scale(w_, 3 * h // 2)
sc.render.image_settings.file_format = 'JPEG'; sc.render.image_settings.quality = 85
im.save_render(g['SP'] + '/rav4_wheels_sheet.jpg', scene=sc); print('SHEET ok')
