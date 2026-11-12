"""M_FireFlipbook3D: real fire on particles. Plays a flipbook baked from our Niagara Fluids explosion (the Niagara
Baker: NS_FireBoomFluid3D > Baker tab, Front camera, ortho width 300, 8x8 frames of 256 px, 0-1.6 s, source
"SceneColor (HDR) in RGB, Inv Opacity in A") over each particle's life, so every trail puff is a small burst of
simulated fire instead of a noise blob (the owner, 2026-11-11: "Yes, try the bake").
Unlit, translucent. Colour = baked fire * Glow * particle colour's brightness; opacity = (1 - baked A) * particle alpha.
Run in the editor's console box:  py <repo>/tools/unreal_make_fire_flipbook_mat.py   Writes Saved/fire_flipbook_mat.txt."""
import unreal

ROOT = unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir()).rstrip('/')
MAT = '/Game/Game/Materials'
TEX = '/Game/Game/FX/NS_FireBoomFluid3D_BakedAtlas_Texture2D_0'
FRAMES = 8                       # frames per side of the atlas
at = unreal.AssetToolsHelpers.get_asset_tools()
eal = unreal.EditorAssetLibrary
mel = unreal.MaterialEditingLibrary

path = f'{MAT}/M_FireFlipbook3D'
if eal.does_asset_exist(path):
    m = unreal.load_asset(path); mel.delete_all_material_expressions(m)
else:
    m = at.create_asset('M_FireFlipbook3D', MAT, unreal.Material, unreal.MaterialFactoryNew())
m.set_editor_property('blend_mode', unreal.BlendMode.BLEND_TRANSLUCENT)
m.set_editor_property('shading_model', unreal.MaterialShadingModel.MSM_UNLIT)
m.set_editor_property('two_sided', True)
for flag in ('used_with_niagara_sprites', 'used_with_niagara_ribbons', 'used_with_niagara_mesh_particles'):
    m.set_editor_property(flag, True)

y = [0]


def e(cls, x=-900):
    y[0] += 130
    return mel.create_material_expression(m, cls, x, y[0])


def scalar(name, v):
    s = e(unreal.MaterialExpressionScalarParameter)
    s.set_editor_property('parameter_name', name); s.set_editor_property('default_value', v)
    return s


# UV of the current frame: frame = floor(age * N*N) (age = Particle Relative Time, 0..1 over the particle's life)
age = e(unreal.MaterialExpressionParticleRelativeTime)
uv = e(unreal.MaterialExpressionTextureCoordinate)
uvc = mel.create_material_expression(m, unreal.MaterialExpressionCustom, -600, 0)
# FrameStart/FrameEnd (0-1) pick part of the bake: the head plays only the hot early frames (MI_FireFlipbookHead)
uvc.set_editor_property('code', f"""float n = {FRAMES}.0;
float t = lerp(FrameStart, FrameEnd, saturate(T));
float f = min(floor(t * n * n), n * n - 1.0);
float2 cell = float2(fmod(f, n), floor(f / n));
return (cell + saturate(UV)) / n;""")
uvc.set_editor_property('output_type', unreal.CustomMaterialOutputType.CMOT_FLOAT2)
ins = []
for n in ('T', 'UV', 'FrameStart', 'FrameEnd'):
    ci = unreal.CustomInput(); ci.set_editor_property('input_name', n); ins.append(ci)
uvc.set_editor_property('inputs', ins)
mel.connect_material_expressions(age, '', uvc, 'T')
mel.connect_material_expressions(uv, '', uvc, 'UV')
mel.connect_material_expressions(scalar('FrameStart', 0.0), '', uvc, 'FrameStart')
mel.connect_material_expressions(scalar('FrameEnd', 1.0), '', uvc, 'FrameEnd')

tex = mel.create_material_expression(m, unreal.MaterialExpressionTextureSampleParameter2D, -350, 0)
tex.set_editor_property('parameter_name', 'Flipbook')
tex.set_editor_property('texture', unreal.load_asset(TEX))
tex.set_editor_property('sampler_type', unreal.MaterialSamplerType.SAMPLERTYPE_COLOR)   # the bake saves an sRGB 8-bit texture
mel.connect_material_expressions(uvc, '', tex, 'UVs')

pc = e(unreal.MaterialExpressionParticleColor)
glow = scalar('Glow', 0.7)
col = mel.create_material_expression(m, unreal.MaterialExpressionCustom, -100, 200)
# tint by the particle's heat colour (white-hot -> orange -> red -> dark), not just its brightness: brightness alone
# left the young puffs pale grey-white
col.set_editor_property('code', 'return C * PC * Glow;')
col.set_editor_property('output_type', unreal.CustomMaterialOutputType.CMOT_FLOAT3)
ins = []
for n in ('C', 'PC', 'Glow'):
    ci = unreal.CustomInput(); ci.set_editor_property('input_name', n); ins.append(ci)
col.set_editor_property('inputs', ins)
mel.connect_material_expressions(tex, 'RGB', col, 'C')
mel.connect_material_expressions(pc, 'RGB', col, 'PC')
mel.connect_material_expressions(glow, '', col, 'Glow')

op = mel.create_material_expression(m, unreal.MaterialExpressionCustom, -100, 400)
# the saved bake holds opacity in A (empty = 0), despite the "Inv Opacity" name: 1 - A drew black squares
# and the near-empty frame edges keep a little A: cut it, or each old puff shows a faint dark square
# EdgeFade (0 = off, the trail): fades the sprite's edges, mostly the top (the flame tips, which the head bake cuts
# at the frame edge), so no square edges show
op.set_editor_property('code', '''float o = saturate((A - 0.06) / 0.94) * saturate(PA);
float2 u = saturate(UV);
float edge = smoothstep(0.0, 0.15, u.x) * smoothstep(1.0, 0.85, u.x) * smoothstep(0.0, 0.35, u.y) * smoothstep(1.0, 0.92, u.y);
// DarkCut (0 = off): drop the dark smoke, keep only the glowing fire (the head's smoke showed as dark smudges)
float glowv = max(C.r, max(C.g, C.b));
float dark = DarkCut > 0.0 ? saturate(glowv * DarkCut) : 1.0;
return o * lerp(1.0, edge, EdgeFade) * dark;''')
op.set_editor_property('output_type', unreal.CustomMaterialOutputType.CMOT_FLOAT1)
ins = []
for n in ('A', 'PA', 'UV', 'EdgeFade', 'C', 'DarkCut'):
    ci = unreal.CustomInput(); ci.set_editor_property('input_name', n); ins.append(ci)
op.set_editor_property('inputs', ins)
mel.connect_material_expressions(tex, 'A', op, 'A')
mel.connect_material_expressions(pc, 'A', op, 'PA')
mel.connect_material_expressions(uv, '', op, 'UV')
mel.connect_material_expressions(scalar('EdgeFade', 0.0), '', op, 'EdgeFade')
mel.connect_material_expressions(tex, 'RGB', op, 'C')
mel.connect_material_expressions(scalar('DarkCut', 0.0), '', op, 'DarkCut')

mel.connect_material_property(col, '', unreal.MaterialProperty.MP_EMISSIVE_COLOR)
mel.connect_material_property(op, '', unreal.MaterialProperty.MP_OPACITY)
mel.recompile_material(m)
eal.save_loaded_asset(m)

# the head around the fireball: only the hot first third of the bake (the whole bake flashed smoke as dark boxes)
mi_path = f'{MAT}/MI_FireFlipbookHead'
mi = unreal.load_asset(mi_path) if eal.does_asset_exist(mi_path) else at.create_asset(
    'MI_FireFlipbookHead', MAT, unreal.MaterialInstanceConstant, unreal.MaterialInstanceConstantFactoryNew())
mi.set_editor_property('parent', m)
mel.set_material_instance_scalar_parameter_value(mi, 'FrameEnd', 0.3)
mel.set_material_instance_scalar_parameter_value(mi, 'Glow', 0.8)
mel.update_material_instance(mi)
eal.save_loaded_asset(mi)

# the fireball head (the owner, 2026-11-11: "Bake a fireball head" + a photo of a white-hot ball trailing flames):
# its own centred bake of a steady fire (NS_FireHeadFluid3D: ball low in the frame, flames rising to the top), played
# on the Flame emitter turned so the frame's top points backward along the flight
HEAD_TEX = '/Game/Game/FX/NS_FireHeadFluid3D_BakedAtlas_Texture2D_0'
mi_path = f'{MAT}/MI_FireHeadBake3D'
if eal.does_asset_exist(HEAD_TEX):
    mi = unreal.load_asset(mi_path) if eal.does_asset_exist(mi_path) else at.create_asset(
        'MI_FireHeadBake3D', MAT, unreal.MaterialInstanceConstant, unreal.MaterialInstanceConstantFactoryNew())
    mi.set_editor_property('parent', m)
    mel.set_material_instance_texture_parameter_value(mi, 'Flipbook', unreal.load_asset(HEAD_TEX))
    mel.set_material_instance_scalar_parameter_value(mi, 'FrameStart', 0.0)
    mel.set_material_instance_scalar_parameter_value(mi, 'FrameEnd', 0.4)
    mel.set_material_instance_scalar_parameter_value(mi, 'Glow', 1.0)
    mel.set_material_instance_scalar_parameter_value(mi, 'EdgeFade', 1.0)
    mel.set_material_instance_scalar_parameter_value(mi, 'DarkCut', 4.0)
    mel.update_material_instance(mi)
    eal.save_loaded_asset(mi)
# the trail (the owner, 2026-11-11: "I think you can do better"): only the burning part of the explosion bake (its
# last frames are smoke, which made the trail a dark lumpy cloud), with the darkest smoke half cut
mi_path = f'{MAT}/MI_FireTrail3D'
mi = unreal.load_asset(mi_path) if eal.does_asset_exist(mi_path) else at.create_asset(
    'MI_FireTrail3D', MAT, unreal.MaterialInstanceConstant, unreal.MaterialInstanceConstantFactoryNew())
mi.set_editor_property('parent', m)
mel.set_material_instance_scalar_parameter_value(mi, 'FrameStart', 0.05)
mel.set_material_instance_scalar_parameter_value(mi, 'FrameEnd', 0.6)
mel.set_material_instance_scalar_parameter_value(mi, 'Glow', 0.8)
mel.set_material_instance_scalar_parameter_value(mi, 'DarkCut', 2.5)
mel.update_material_instance(mi)
eal.save_loaded_asset(mi)
t = unreal.load_asset(TEX)
info = f"tex {t.blueprint_get_size_x()}x{t.blueprint_get_size_y()} compression={t.get_editor_property('compression_settings')} srgb={t.get_editor_property('srgb')}"
with open(f'{ROOT}/Saved/fire_flipbook_mat.txt', 'w') as fh:
    fh.write('M_FireFlipbook3D made; ' + info + '\n')
unreal.log('FIRE FLIPBOOK MAT made')
