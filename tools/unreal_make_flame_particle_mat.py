"""M_FlameParticle3D: solid cartoon flame blobs for round sprite particles (Fire Blast drill, 2026-11-11; niagara-fx skill).
Unlit, masked (crisp, no bloom haze), round: the sprite is cut to a circle, coloured in 4 bands from the middle out:
hot (the particle colour lifted toward white), the particle colour, a darker rim and a dark outline. Colour and size come
from the particles, so one material serves flames, embers, sparks and smoke.
Run in the editor's console box:  py <repo>/tools/unreal_make_flame_particle_mat.py   Writes Saved/flame_particle_mat.txt."""
import unreal

ROOT = unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir()).rstrip('/')
MAT = '/Game/Game/Materials'
at = unreal.AssetToolsHelpers.get_asset_tools()
eal = unreal.EditorAssetLibrary
mel = unreal.MaterialEditingLibrary

path = f'{MAT}/M_FlameParticle3D'
if eal.does_asset_exist(path):
    m = unreal.load_asset(path); mel.delete_all_material_expressions(m)
else:
    m = at.create_asset('M_FlameParticle3D', MAT, unreal.Material, unreal.MaterialFactoryNew())
m.set_editor_property('blend_mode', unreal.BlendMode.BLEND_MASKED)
m.set_editor_property('shading_model', unreal.MaterialShadingModel.MSM_UNLIT)
m.set_editor_property('two_sided', True)
for flag in ('used_with_niagara_sprites', 'used_with_niagara_ribbons', 'used_with_niagara_mesh_particles'):
    m.set_editor_property(flag, True)

y = [0]


def e(cls, x=-900):
    y[0] += 120
    return mel.create_material_expression(m, cls, x, y[0])


def custom(code, inputs, out_type):
    c = e(unreal.MaterialExpressionCustom, -400)
    c.set_editor_property('code', code); c.set_editor_property('output_type', out_type)
    ins = []
    for n, _, _ in inputs:
        ci = unreal.CustomInput(); ci.set_editor_property('input_name', n); ins.append(ci)
    c.set_editor_property('inputs', ins)
    for n, node, pin in inputs:
        mel.connect_material_expressions(node, pin, c, n)
    return c


pc = e(unreal.MaterialExpressionParticleColor)
uv = e(unreal.MaterialExpressionTextureCoordinate)
ins = [('C', pc, 'RGB'), ('UV', uv, '')]
D = "float d = length(UV - 0.5) * 2.0;\n"
col = custom(D + "float m = max(C.r, max(C.g, C.b));\n"
             # a small, only slightly lighter centre: a big white one made the blobs look like coins
             "return d < 0.3 ? lerp(C, float3(m, m, m), 0.3) : (d < 0.7 ? C : (d < 0.86 ? C * 0.62 : C * 0.22));",
             ins, unreal.CustomMaterialOutputType.CMOT_FLOAT3)
mask = custom(D + "return d < 1.0 ? 1.0 : 0.0;", [('UV', uv, '')], unreal.CustomMaterialOutputType.CMOT_FLOAT1)
mel.connect_material_property(col, '', unreal.MaterialProperty.MP_EMISSIVE_COLOR)
mel.connect_material_property(mask, '', unreal.MaterialProperty.MP_OPACITY_MASK)
mel.recompile_material(m)
eal.save_loaded_asset(m)
with open(f'{ROOT}/Saved/flame_particle_mat.txt', 'w') as fh:
    fh.write('M_FlameParticle3D made\n')
unreal.log('FLAME PARTICLE MAT made')
