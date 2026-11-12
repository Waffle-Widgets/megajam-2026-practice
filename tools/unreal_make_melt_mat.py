"""M_MeltWall: stone for BP_MeltWall, the wall the Mega Beam melts through (the owner, 2026-11-11: "pierce through the
object, almost like melting through it"). Run in the editor's console box:  py <repo>/tools/unreal_make_melt_mat.py
BP_MeltWall passes the newest bite through custom primitive data: 0-2 = its world position, 3 = game time of the bite,
4-6 = the first bite (the scorch ring stays there). Near the newest bite the stone glows white-orange and cools to dark
red over about 2.5 s; around the hole it stays scorched black. Writes Saved/melt_mat.txt."""
import unreal

ROOT = unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir()).rstrip('/')
MAT = '/Game/Game/Materials'
at = unreal.AssetToolsHelpers.get_asset_tools()
eal = unreal.EditorAssetLibrary
mel = unreal.MaterialEditingLibrary

path = f'{MAT}/M_MeltWall'
if eal.does_asset_exist(path):
    m = unreal.load_asset(path); mel.delete_all_material_expressions(m)
else:
    m = at.create_asset('M_MeltWall', MAT, unreal.Material, unreal.MaterialFactoryNew())
m.set_editor_property('two_sided', True)     # the boolean's inside faces must show from both sides

y = [0]


def e(cls, x=-900):
    y[0] += 120
    return mel.create_material_expression(m, cls, x, y[0])


def cpd(name, index):
    s = e(unreal.MaterialExpressionScalarParameter)
    s.set_editor_property('parameter_name', name)
    s.set_editor_property('use_custom_primitive_data', True)
    s.set_editor_property('primitive_data_index', index)
    return s


wp = e(unreal.MaterialExpressionWorldPosition)
tm = e(unreal.MaterialExpressionTime)
ins = [('WP', wp)] + [(n, cpd(n, i)) for i, n in enumerate(('BiteX', 'BiteY', 'BiteZ', 'BiteTime', 'FirstX', 'FirstY', 'FirstZ'))] + [('T', tm)]


def custom(code, out_type, x, yy):
    c = mel.create_material_expression(m, unreal.MaterialExpressionCustom, x, yy)
    c.set_editor_property('code', code)
    c.set_editor_property('output_type', out_type)
    lst = []
    for n, _ in ins:
        ci = unreal.CustomInput(); ci.set_editor_property('input_name', n); lst.append(ci)
    c.set_editor_property('inputs', lst)
    for n, node in ins:
        mel.connect_material_expressions(node, '', c, n)
    return c


# stone: two scales of cheap hash noise on world position, warm grey; scorched near the hole (distance to the line
# through the first and newest bites, so the whole tunnel is ringed)
STONE = '''struct S {
  float h(float3 p) { return frac(sin(dot(floor(p), float3(12.9898, 78.233, 37.719))) * 43758.5453); }
  float n(float3 p) { float3 i = floor(p); float3 f = frac(p); f = f * f * (3.0 - 2.0 * f);
    float a = lerp(lerp(lerp(h(i), h(i + float3(1,0,0)), f.x), lerp(h(i + float3(0,1,0)), h(i + float3(1,1,0)), f.x), f.y),
                   lerp(lerp(h(i + float3(0,0,1)), h(i + float3(1,0,1)), f.x), lerp(h(i + float3(0,1,1)), h(i + float3(1,1,1)), f.x), f.y), f.z);
    return a; }
};
S s;
float3 p = WP / 18.0;
float v = 0.6 * s.n(p) + 0.4 * s.n(p * 3.1);
float3 stone = lerp(float3(0.20, 0.18, 0.16), float3(0.46, 0.42, 0.36), v);
float3 a = float3(FirstX, FirstY, FirstZ); float3 b = float3(BiteX, BiteY, BiteZ);
float3 ab = b - a; float t = saturate(dot(WP - a, ab) / max(dot(ab, ab), 1.0));
float d = (BiteTime > 0.0) ? length(WP - (a + ab * t)) : 1e6;
float scorch = saturate(1.0 - (d - 22.0) / 30.0);
return stone * lerp(1.0, 0.12, scorch);'''

GLOW = '''float3 b = float3(BiteX, BiteY, BiteZ);
float d = (BiteTime > 0.0) ? length(WP - b) : 1e6;
float heat = saturate(1.0 - (T - BiteTime) / 2.5);
float ring = saturate(1.0 - (d - 18.0) / 26.0);
float k = ring * ring * heat;
float3 hot = lerp(float3(0.9, 0.08, 0.0), float3(2.4, 1.1, 0.25), saturate(k * 1.6));
return hot * k * 2.0;'''

base = custom(STONE, unreal.CustomMaterialOutputType.CMOT_FLOAT3, -300, 0)
glow = custom(GLOW, unreal.CustomMaterialOutputType.CMOT_FLOAT3, -300, 400)
mel.connect_material_property(base, '', unreal.MaterialProperty.MP_BASE_COLOR)
mel.connect_material_property(glow, '', unreal.MaterialProperty.MP_EMISSIVE_COLOR)
rough = e(unreal.MaterialExpressionConstant, -300)
rough.set_editor_property('r', 0.9)
mel.connect_material_property(rough, '', unreal.MaterialProperty.MP_ROUGHNESS)
mel.recompile_material(m)
eal.save_loaded_asset(m)
with open(f'{ROOT}/Saved/melt_mat.txt', 'w') as fh:
    fh.write('M_MeltWall made\n')
unreal.log('MELT MAT made')
