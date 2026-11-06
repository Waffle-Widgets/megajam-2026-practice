# Second half of trellis_vehicle.py (exec'd by it with STAGE 'bake'): bake the generator's own texture onto VEH's
# clean UVs, sort texels into paint / glass / dark trim / lamps by colour and height, export FBX + PNGs.
# Coordinates: game metres, front -Y, tyre bottoms at z = GROUND (-0.30).
S = TEX
ob = bpy.data.objects['VEH']; me = ob.data; src = bpy.data.objects['VEH_SRC']
for o in (ob, src): o.hide_viewport = False; o.hide_render = False; o.location = (0, 0, 0)

# 1. position + normal maps on the clean UVs (park nothing aside: an object off the origin bakes black)
me.materials.clear(); me.materials.append(bpy.data.materials.get('MV_Tmp') or bpy.data.materials.new('MV_Tmp'))
P, N = cl['bake_maps'](ob, size=S, margin=8)

# 2. selected-to-active emission bake of the generator's base colour
img = bpy.data.images['VEH_SRC_BaseColor']
msrc = bpy.data.materials.get('MV_SrcBake') or bpy.data.materials.new('MV_SrcBake'); msrc.use_nodes = True; nt = msrc.node_tree
for n in list(nt.nodes): nt.nodes.remove(n)
tex = nt.nodes.new('ShaderNodeTexImage'); tex.image = img; tex.interpolation = 'Closest'
em = nt.nodes.new('ShaderNodeEmission'); outn = nt.nodes.new('ShaderNodeOutputMaterial')
nt.links.new(tex.outputs['Color'], em.inputs['Color']); nt.links.new(em.outputs['Emission'], outn.inputs['Surface'])
src.data.materials.clear(); src.data.materials.append(msrc)
tgt = bpy.data.images.new('T_VehSrcBake', S, S, float_buffer=True); tgt.colorspace_settings.name = 'Non-Color'
mt = bpy.data.materials.get('MV_TgtBake') or bpy.data.materials.new('MV_TgtBake'); mt.use_nodes = True; nt2 = mt.node_tree
for n in list(nt2.nodes): nt2.nodes.remove(n)
tn = nt2.nodes.new('ShaderNodeTexImage'); tn.image = tgt; nt2.nodes.active = tn
me.materials.clear(); me.materials.append(mt)
sc = bpy.context.scene; sc.render.engine = 'CYCLES'; sc.cycles.device = 'GPU'; sc.cycles.samples = 1
bk = sc.render.bake; bk.use_selected_to_active = True; bk.cage_extrusion = 0.02; bk.max_ray_distance = 0.05; bk.margin = 8; bk.target = 'IMAGE_TEXTURES'
for o in bpy.context.view_layer.objects: o.select_set(False)
src.select_set(True); ob.select_set(True); bpy.context.view_layer.objects.active = ob
bpy.ops.object.bake(type='EMIT')
bk.use_selected_to_active = False
px = np.empty(S * S * 4, np.float32); tgt.pixels.foreach_get(px); b = np.clip(px.reshape(S, S, 4)[..., :3], 0, 1)
# the texture node decodes the sRGB image to linear and the Non-Color float target keeps it linear: back to sRGB
srgb_in = np.where(b <= 0.0031308, b * 12.92, 1.055 * np.power(b, 1 / 2.4) - 0.055).astype(np.float32)

# 3. classify by colour + height (heights as a fraction of the vehicle, so the rules fit any vehicle)
x, y, z = P[..., 0], P[..., 1], P[..., 2]
valid = ~np.all(np.abs(P + 1) < 1e-3, -1)                       # empty texels bake as position 0 -> -1
H = REAL['height'] * K; zr = (z - GROUND) / H
lum = srgb_in.mean(-1); mx = srgb_in.max(-1); mn = srgb_in.min(-1); sat = (mx - mn) / (mx + 1e-6)
red = (srgb_in[..., 0] > 1.5 * srgb_in[..., 1]) & (srgb_in[..., 0] > 1.5 * srgb_in[..., 2]) & (srgb_in[..., 0] > 0.30)
dark = lum < globals().get('DARK_LUM', 0.16)
GZ = globals().get('GLASS_Z', [0.52, 0.95])
glass = valid & dark & (zr > GZ[0]) & (zr < GZ[1]) & (N[..., 2] < 0.55)          # windows: dark, upright, cabin height
roof_dark = valid & dark & (N[..., 2] >= 0.55)                                    # a black roof stays glossy paint
trim = valid & dark & ~glass & ~roof_dark                                         # tyres, cladding, grille
paint = valid & ~dark & ~red
out['uv_fill'] = round(float(valid.mean()), 3)
out['texels'] = {k: int(v.sum()) for k, v in (('glass', glass), ('roof_dark', roof_dark), ('trim', trim), ('paint', paint), ('red', red))}
col = srgb_in.copy()

# 3a. paint: optional desaturate / lift / soften the photo's baked shading (the game lights it again)
SAT = globals().get('PAINT_SAT', 1.0); LUM = globals().get('PAINT_LUM', None); CON = globals().get('PAINT_CONTRAST', 0.7)
med_ = np.median(col[paint], 0); out['paint_median'] = med_.round(3).tolist()
g_ = col[paint].mean(-1, keepdims=True); col[paint] = g_ + (col[paint] - g_) * SAT
med2 = np.median(col[paint], 0); scale = (LUM / max(med2.mean(), 1e-3)) if LUM else 1.0
col[paint] = np.clip(scale * med2 + (col[paint] - med2) * CON, 0, 1)

# 3b. flat-colour boxes for anything the photo fix missed (badges)
for bx in globals().get('PAINT_BOXES', []):
    lo_, hi_ = np.array(bx['min']), np.array(bx['max'])
    sel = valid & np.all((P >= lo_) & (P <= hi_), -1); col[sel] = np.array(bx['rgb']); out.setdefault('boxes', []).append(int(sel.sum()))

# 4. roughness + mask (R clear-coat, G metallic), the same convention as M_CarMasked
GLASS = cl['GLASS']; RED = cl['RED']; PLASTIC = cl['PLASTIC']
rough = np.full(lum.shape, globals().get('ROUGH', 0.3), np.float32)
m0 = np.full(lum.shape, 1.0, np.float32); m1 = np.full(lum.shape, globals().get('METALLIC', 0.0), np.float32)
for sel, mat in ((trim, PLASTIC), (glass, GLASS), (red, RED)):
    rough[sel] = mat[1]; m0[sel] = 0; m1[sel] = 0
col[glass] = np.minimum(col[glass], 0.06)
mask = np.zeros((S, S, 3), np.float32); mask[..., 0] = m0; mask[..., 1] = m1

# 5. write PNGs (base colour stays sRGB: it came from an sRGB texture), material, FBX
os.makedirs(DEST, exist_ok=True)
def put(name, rgb, srgb):
    im = bpy.data.images.get(name)
    if im: bpy.data.images.remove(im)
    im = bpy.data.images.new(name, S, S, alpha=False)
    im.colorspace_settings.name = 'sRGB' if srgb else 'Non-Color'
    arr = np.ones((S, S, 4), np.float32); arr[..., :3] = rgb; im.pixels.foreach_set(arr.ravel())
    im.filepath_raw = DEST + '\\%s.png' % name; im.file_format = 'PNG'; im.save()
    return im
ibc = put('T_%s_BaseColor' % NAME, np.clip(col, 0, 1), True)
irg = put('T_%s_Roughness' % NAME, np.repeat(rough[..., None], 3, -1), False)
imk = put('T_%s_Mask' % NAME, mask, False)
mat = bpy.data.materials.get('M_' + NAME) or bpy.data.materials.new('M_' + NAME); mat.use_nodes = True; nt = mat.node_tree
for n in list(nt.nodes): nt.nodes.remove(n)
bsdf = nt.nodes.new('ShaderNodeBsdfPrincipled'); o_ = nt.nodes.new('ShaderNodeOutputMaterial'); nt.links.new(bsdf.outputs[0], o_.inputs[0])
t1 = nt.nodes.new('ShaderNodeTexImage'); t1.image = ibc; nt.links.new(t1.outputs[0], bsdf.inputs['Base Color'])
t2 = nt.nodes.new('ShaderNodeTexImage'); t2.image = irg; t2.image.colorspace_settings.name = 'Non-Color'; nt.links.new(t2.outputs[0], bsdf.inputs['Roughness'])
t3 = nt.nodes.new('ShaderNodeTexImage'); t3.image = imk; t3.image.colorspace_settings.name = 'Non-Color'; sp = nt.nodes.new('ShaderNodeSeparateColor')
nt.links.new(t3.outputs[0], sp.inputs[0]); nt.links.new(sp.outputs[0], bsdf.inputs['Coat Weight']); nt.links.new(sp.outputs[1], bsdf.inputs['Metallic'])
me.materials.clear(); me.materials.append(mat)
select_only(ob)
src.hide_viewport = True; src.hide_render = True
# EXPORT_FBX=False re-bakes textures only: re-importing the mesh would reset its materials and LODs in Unreal
if globals().get('EXPORT_FBX', True):
    bpy.ops.export_scene.fbx(filepath=DEST + '\\%s.fbx' % OUT, use_selection=True, axis_forward='-Z', axis_up='Y', global_scale=1.0,
                             apply_unit_scale=True, mesh_smooth_type='FACE', use_mesh_modifiers=True, path_mode='STRIP',
                             embed_textures=False, bake_anim=False)
bpy.ops.wm.save_as_mainfile(filepath=SP + '\\%s_work.blend' % OUT)
