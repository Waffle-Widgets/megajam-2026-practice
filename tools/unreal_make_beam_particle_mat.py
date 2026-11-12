"""M_BeamParticle3D: a solid-colour material for the Mega Beam's particle ribbons (NS_MegaBeam3D), so the red-orange
spiral reads as red-orange in front of the white-hot core. Niagara's default ribbon material adds light, so red over
white came out white (2026-11-10).
Unlit, masked (solid, sorted by depth, no glow haze), two-sided. Colour = the particle's colour, in cartoon bands on
the round tube ribbons: a dark outline where the tube turns away from the camera (facing below Edge), a lighter band
where it faces it. Dark sets how dark the outline is.
Run in the editor's console box:  py <repo>/tools/unreal_make_beam_particle_mat.py   Writes Saved/beam_particle_mat.txt."""
import unreal

ROOT = unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir()).rstrip('/')
MAT = '/Game/Game/Materials'
at = unreal.AssetToolsHelpers.get_asset_tools()
eal = unreal.EditorAssetLibrary
mel = unreal.MaterialEditingLibrary

path = f'{MAT}/M_BeamParticle3D'
if eal.does_asset_exist(path):
    m = unreal.load_asset(path); mel.delete_all_material_expressions(m)
else:
    m = at.create_asset('M_BeamParticle3D', MAT, unreal.Material, unreal.MaterialFactoryNew())
m.set_editor_property('blend_mode', unreal.BlendMode.BLEND_MASKED)
m.set_editor_property('shading_model', unreal.MaterialShadingModel.MSM_UNLIT)
m.set_editor_property('two_sided', True)
for flag in ('used_with_niagara_ribbons', 'used_with_niagara_sprites', 'used_with_niagara_mesh_particles'):
    m.set_editor_property(flag, True)

y = [0]


def e(cls, x=-900):
    y[0] += 120
    return mel.create_material_expression(m, cls, x, y[0])


def scalar(name, v):
    s = e(unreal.MaterialExpressionScalarParameter)
    s.set_editor_property('parameter_name', name); s.set_editor_property('default_value', v)
    return s


pc = e(unreal.MaterialExpressionParticleColor)
nrm = e(unreal.MaterialExpressionVertexNormalWS)
cam = e(unreal.MaterialExpressionCameraVectorWS)
edge, dark = scalar('Edge', 0.32), scalar('Dark', 0.22)


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


# The ribbons are round tubes (2026-11-10, the owner: "the spiral should be round"), so the outline follows the
# tube's silhouette: dark where the surface turns away from the camera, a lighter band where it faces it (round look).
ins = [('C', pc, 'RGB'), ('N', nrm, ''), ('V', cam, ''), ('Edge', edge, ''), ('Dark', dark, '')]
col = custom("float f = abs(dot(normalize(N), normalize(V)));\n"
             "return f < Edge ? C * Dark : (f > 0.8 ? lerp(C, float3(1.0, 1.0, 1.0) * max(C.r, max(C.g, C.b)), 0.35) : C);",
             ins, unreal.CustomMaterialOutputType.CMOT_FLOAT3)
mel.connect_material_property(col, '', unreal.MaterialProperty.MP_EMISSIVE_COLOR)
mel.connect_material_property(pc, 'A', unreal.MaterialProperty.MP_OPACITY_MASK)
mel.recompile_material(m)
eal.save_loaded_asset(m)
with open(f'{ROOT}/Saved/beam_particle_mat.txt', 'w') as fh:
    fh.write('M_BeamParticle3D made\n')
unreal.log('BEAM PARTICLE MAT made')
