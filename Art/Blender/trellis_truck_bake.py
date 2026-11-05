# Second half of trellis_truck.py (exec'd by it with STAGE 'bake'): bake the generator's own texture onto
# TR_TAC's clean UVs, derive roughness + mask from colour and position, paint out the grille insert and the
# tailgate badge area, neutralise the paint towards grey, export FBX + PNGs. Coordinates: game metres,
# front -Y, tyre bottoms at z = GROUND (-0.30).
S = TEX
GREY = globals().get('GREY', 0.35)              # keep this much of the paint's blue saturation (1 = as generated)
ob = bpy.data.objects['TR_TAC']; me = ob.data; src = bpy.data.objects['TR_TAC_SRC']
src.hide_viewport = False; src.hide_render = False; ob.hide_render = False; ob.hide_viewport = False
ob.location = (0, 0, 0); src.location = (0, 0, 0)

# 1. position + normal maps on the clean UVs (park nothing aside: an object off the origin bakes black)
for s_ in list(me.materials): pass
me.materials.clear(); me.materials.append(bpy.data.materials.get('MC_TacTmp') or bpy.data.materials.new('MC_TacTmp'))
P, N = cl['bake_maps'](ob, size=S, margin=8)
np.save(SP + r"\tac_P.npy", P.astype(np.float32)); np.save(SP + r"\tac_N.npy", N.astype(np.float32))

# 2. selected-to-active emission bake of the generator's base colour
img = bpy.data.images['TAC_SRC_BaseColor']
msrc = bpy.data.materials.get('M_TacSrcBake') or bpy.data.materials.new('M_TacSrcBake'); msrc.use_nodes = True; nt = msrc.node_tree
for n in list(nt.nodes): nt.nodes.remove(n)
tex = nt.nodes.new('ShaderNodeTexImage'); tex.image = img; tex.interpolation = 'Closest'
em = nt.nodes.new('ShaderNodeEmission'); outn = nt.nodes.new('ShaderNodeOutputMaterial')
nt.links.new(tex.outputs['Color'], em.inputs['Color']); nt.links.new(em.outputs['Emission'], outn.inputs['Surface'])
src.data.materials.clear(); src.data.materials.append(msrc)
tgt = bpy.data.images.get('T_TacSrcBake')
if tgt: bpy.data.images.remove(tgt)
tgt = bpy.data.images.new('T_TacSrcBake', S, S, float_buffer=True); tgt.colorspace_settings.name = 'Non-Color'
mt = bpy.data.materials.get('M_TacTgtBake') or bpy.data.materials.new('M_TacTgtBake'); mt.use_nodes = True; nt2 = mt.node_tree
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

# 3. classify by colour + position
x, y, z = P[..., 0], P[..., 1], P[..., 2]
valid = ~np.all(np.abs(P + 1) < 1e-3, -1)                       # empty texels bake as position 0 -> -1
out['uv_fill'] = round(float(valid.mean()), 3); out['baked_mean_srgb'] = float(srgb_in[valid].mean())
lum = srgb_in.mean(-1); mx = srgb_in.max(-1); mn = srgb_in.min(-1); sat = (mx - mn) / (mx + 1e-6)
red = (srgb_in[..., 0] > 1.5 * srgb_in[..., 1]) & (srgb_in[..., 0] > 1.5 * srgb_in[..., 2]) & (srgb_in[..., 0] > 0.30)
dark = lum < 0.16
glass = dark & (z > 0.255) & (y < 0.42)                         # cab windows, above the bed rails and the hood
plastic = dark & ~glass
col = srgb_in.copy()

# 3a. grille insert: everything inside the chrome surround becomes dark slats (no badge, no brand shape)
gx = np.abs(x)
GZ0, GZ1 = 0.049, 0.140                                         # insert bottom / top (front view, measured)
def grille_half(zz):                                            # hexagon: widest at the middle, cut corners
    zm = (GZ0 + GZ1) / 2; t = np.abs(zz - zm) / ((GZ1 - GZ0) / 2)
    return 0.210 - 0.032 * np.clip(t, 0, 1)
front = N[..., 1] < -0.35
gr = valid & front & (y < -0.95) & (z > GZ0) & (z < GZ1) & (gx < grille_half(z))
slat = (np.mod((z - GZ0) / 0.012, 1.0) < 0.55)
col[gr] = np.where(slat[gr, None], np.array([0.085, 0.088, 0.095]), np.array([0.025, 0.026, 0.03]))
out['grille_texels'] = int(gr.sum())

# 3b. tailgate: replace the panel with its own row-median paint (removes badge remnants, spots, lettering),
#     then a plain black handle in the middle
rear = N[..., 1] > 0.5
tg = valid & rear & (y > 1.05) & (np.abs(x) < 0.265) & (z > 0.035) & (z < 0.232) & ~red
zb = np.clip(((z - 0.035) / 0.004).astype(int), 0, 60)
med = np.zeros((61, 3), np.float32)
for k in range(61):
    s_ = tg & (zb == k)
    if s_.sum() > 30: med[k] = np.median(srgb_in[s_], 0)
filled = med.sum(1) > 0; ks = np.arange(61)
for c_ in range(3): med[:, c_] = np.interp(ks, ks[filled], med[filled, c_])
col[tg] = med[zb[tg]]
handle = tg & (np.abs(x) < 0.062) & (z > 0.192) & (z < 0.222)
col[handle] = np.array([0.03, 0.03, 0.033])
out['tailgate_texels'] = int(tg.sum())

# 3c. paint towards neutral grey (the generator made "Cement" grey too blue)
paint = valid & ~dark & ~red & ~gr & (sat < 0.6)
g_ = col[paint].mean(-1, keepdims=True)
col[paint] = g_ + (col[paint] - g_) * GREY
# the photo's shading is baked in (sides in shadow): median paint came out sRGB 0.35, "Cement" grey is ~0.55.
# Lift the paint to PAINT_LUM and soften the baked light/dark by PAINT_CONTRAST, so the game's own light does the shading.
PAINT_LUM = globals().get('PAINT_LUM', 0.44); PAINT_CONTRAST = globals().get('PAINT_CONTRAST', 0.6)
med_ = np.median(col[paint], 0)
col[paint] = np.clip(PAINT_LUM / med_.mean() * med_ + (col[paint] - med_) * PAINT_CONTRAST, 0, 1)
out['paint_texels'] = int(paint.sum()); out['paint_median_before'] = med_.round(3).tolist()

# 4. roughness + mask (R clear-coat, G metallic), the same convention as M_CarT
PAINT = (None, 0.35, 1.0, 0.0)                  # solid (non-metallic) grey: the coupe's 0.3 metallic read dark under trees
GLASS = cl['GLASS']; RED = cl['RED']; PLASTIC = cl['PLASTIC']
rough = np.full(lum.shape, PAINT[1], np.float32); m0 = np.full(lum.shape, PAINT[2], np.float32); m1 = np.full(lum.shape, PAINT[3], np.float32)
for sel, mat in ((plastic, PLASTIC), (gr, PLASTIC), (glass, GLASS), (red, RED)):
    rough[sel] = mat[1]; m0[sel] = 0; m1[sel] = 0
col[glass] = np.minimum(col[glass], 0.06)
rough[handle] = PLASTIC[1]; m0[handle] = 0; m1[handle] = 0
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
ibc = put('T_CarTacoma_BaseColor', np.clip(col, 0, 1), True)
irg = put('T_CarTacoma_Roughness', np.repeat(rough[..., None], 3, -1), False)
imk = put('T_CarTacoma_Mask', mask, False)
mat = bpy.data.materials.get('M_CarTacoma') or bpy.data.materials.new('M_CarTacoma'); mat.use_nodes = True; nt = mat.node_tree
for n in list(nt.nodes): nt.nodes.remove(n)
bsdf = nt.nodes.new('ShaderNodeBsdfPrincipled'); o_ = nt.nodes.new('ShaderNodeOutputMaterial'); nt.links.new(bsdf.outputs[0], o_.inputs[0])
t1 = nt.nodes.new('ShaderNodeTexImage'); t1.image = ibc; nt.links.new(t1.outputs[0], bsdf.inputs['Base Color'])
t2 = nt.nodes.new('ShaderNodeTexImage'); t2.image = irg; nt.links.new(t2.outputs[0], bsdf.inputs['Roughness'])
t3 = nt.nodes.new('ShaderNodeTexImage'); t3.image = imk; sp = nt.nodes.new('ShaderNodeSeparateColor')
nt.links.new(t3.outputs[0], sp.inputs[0]); nt.links.new(sp.outputs[0], bsdf.inputs['Coat Weight']); nt.links.new(sp.outputs[1], bsdf.inputs['Metallic'])
me.materials.clear(); me.materials.append(mat)
select_only(ob)
# EXPORT_FBX=False re-bakes textures only: re-importing the mesh would reset its materials and LODs in Unreal
if globals().get('EXPORT_FBX', True): bpy.ops.export_scene.fbx(filepath=DEST + '\\%s.fbx' % OUT, use_selection=True, axis_forward='-Z', axis_up='Y', global_scale=1.0,
                         apply_unit_scale=True, mesh_smooth_type='FACE', use_mesh_modifiers=True, path_mode='STRIP',
                         embed_textures=False, bake_anim=False)
src.hide_viewport = True; src.hide_render = True
bpy.ops.wm.save_as_mainfile(filepath=SP + r"\tacoma_work.blend")
