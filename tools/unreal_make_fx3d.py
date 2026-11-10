"""3D effects without Niagara (fire, sparks, smoke, beams): imports the shapes and builds the glowing materials.
From the Deep Archive HD-2D test (2026-11-09), where they made Fire Blast and Mega Beam. Make the shapes first with
Art/Blender/fx3d_kit.py. The example colours (MI_*) are a starting point: change them for our game.
Run in the editor's console box:  py <repo>/tools/unreal_make_fx3d.py
Safe to run again (materials are rebuilt in place, so Blueprints keep pointing at them). Writes Saved/fx3d_result.txt.

Shapes (Art/Blender/fx3d_kit.py -> /Game/Game/Meshes/FX3D): Blob3D (a fine ball), Sparks3D (40 streaks, UV u root->tip),
Tube3D (open tube along Z, UV u along it, v around it). All 1 m across: scale = size in cm / 100.

Materials (/Game/Game/Materials). The owner chose "3D with glow" (2026-11-09): emissive above 1 so the engine's
default bloom gives a gentle glow (kept low: 3-4 hazed the whole screen). Shapes stay crisp (Masked, not see-through smears), with toon colour bands.
  M_Flame3D      fire: noise flames rising through a lumpy ball (moved in the vertex shader), coloured in 4 bands
                 from a dark edge to a white-hot middle. Custom primitive data 0 = Burn (0 = whole, 1 = burnt away).
                 MI_Fire3D (orange, Fire Blast), MI_FireCore3D (hot core), MI_Gold3D (Mega Beam's gold orbs)
  M_Spark3D      sparks: CPD 0 = Burn shortens every streak toward its tip. MI_SparkFire3D, MI_SparkGold3D
  M_Smoke3D      lit grey puff with the same flames' noise, CPD 0 = Burn
  M_Beam3D       the beam: energy streaks flowing along the tube. CPD 0 = the beam's length in cm (so the streaks keep
                 their size however far the beam reaches). MI_BeamCore3D (solid white-gold), MI_BeamShell3D (gold
                 streaks), MI_BeamSwirl3D (thin fast strands)
"""
import unreal

import os
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))).replace('\\', '/')   # the repo
MESH = '/Game/Game/Meshes/FX3D'
MAT = '/Game/Game/Materials'
at = unreal.AssetToolsHelpers.get_asset_tools()
eal = unreal.EditorAssetLibrary
mel = unreal.MaterialEditingLibrary
log = []


# ---------------------------------------------------------------- shapes
def import_mesh(name):
    path = f'{MESH}/SM_{name}'
    if not eal.does_asset_exist(path):
        t = unreal.AssetImportTask()
        t.filename = f'{ROOT}/Art/Blender/export/FX3D/SM_{name}.fbx'
        t.destination_path = MESH; t.destination_name = f'SM_{name}'
        t.automated = True; t.replace_existing = True; t.save = False
        at.import_asset_tasks([t])
        for p in t.imported_object_paths:       # Interchange's placeholder materials: we use our own
            a = eal.load_asset(str(p))
            if a is not None and not isinstance(a, unreal.StaticMesh):
                eal.delete_asset(str(p).split('.')[0])
    mesh = eal.load_asset(path)
    nan = mesh.get_editor_property('nanite_settings')
    if nan.enabled:
        nan.enabled = False
        unreal.get_editor_subsystem(unreal.StaticMeshEditorSubsystem).set_nanite_settings(mesh, nan, True)
    eal.save_loaded_asset(mesh)
    b = mesh.get_bounding_box(); s = b.max - b.min
    log.append(f'SM_{name}: tris={mesh.get_num_triangles(0)} size=({s.x:.0f},{s.y:.0f},{s.z:.0f})')
    return mesh


BLOB, SPARKS, TUBE = import_mesh('Blob3D'), import_mesh('Sparks3D'), import_mesh('Tube3D')


# ---------------------------------------------------------------- material helpers
def fresh_material(name):
    path = f'{MAT}/{name}'
    if eal.does_asset_exist(path):      # rebuilt in place, so Blueprints keep pointing at it
        m = unreal.load_asset(path)
        mel.delete_all_material_expressions(m)
        return m
    return at.create_asset(name, MAT, unreal.Material, unreal.MaterialFactoryNew())


class G:
    def __init__(self, m):
        self.m = m; self.y = 0

    def e(self, cls, x=-900):
        self.y += 110
        return mel.create_material_expression(self.m, cls, x, self.y)

    def scalar(self, name, v, cpd=None):
        s = self.e(unreal.MaterialExpressionScalarParameter)
        s.set_editor_property('parameter_name', name); s.set_editor_property('default_value', v)
        if cpd is not None:
            s.set_editor_property('use_custom_primitive_data', True)
            s.set_editor_property('primitive_data_index', cpd)
        return s

    def vec(self, name, c):
        s = self.e(unreal.MaterialExpressionVectorParameter)
        s.set_editor_property('parameter_name', name); s.set_editor_property('default_value', c)
        return s

    def custom(self, code, inputs, out_type, x=-400):
        c = self.e(unreal.MaterialExpressionCustom, x)
        c.set_editor_property('code', code)
        c.set_editor_property('output_type', out_type)
        ins = []
        for n, _ in inputs:
            ci = unreal.CustomInput(); ci.set_editor_property('input_name', n); ins.append(ci)
        c.set_editor_property('inputs', ins)
        for n, (node, pin) in inputs:
            mel.connect_material_expressions(node, pin, c, n)
        return c


F1, F3 = unreal.CustomMaterialOutputType.CMOT_FLOAT1, unreal.CustomMaterialOutputType.CMOT_FLOAT3

# value noise, 4 octaves, with a hash that stays clean for big inputs (no sin). Custom-node code can't declare
# functions, so they live in a local struct.
NOISE = """struct Nz {
  float h(float3 p) { p = frac(p * 0.1031); p += dot(p, p.zyx + 31.32); return frac((p.x + p.y) * p.z); }
  float vn(float3 p) {
    float3 c = floor(p); float3 f = frac(p); f = f * f * (3.0 - 2.0 * f);
    return lerp(lerp(lerp(h(c), h(c + float3(1,0,0)), f.x), lerp(h(c + float3(0,1,0)), h(c + float3(1,1,0)), f.x), f.y),
                lerp(lerp(h(c + float3(0,0,1)), h(c + float3(1,0,1)), f.x), lerp(h(c + float3(0,1,1)), h(c + float3(1,1,1)), f.x), f.y), f.z);
  }
  float fbm(float3 p) { float n = 0.0; float a = 0.5; for (int i = 0; i < 4; i++) { n += a * vn(p); p = p * 2.03 + 3.7; a *= 0.5; } return n / 0.9375; }
};
Nz nz;
"""
# the flames' noise, in the ball's own space (so it moves with the ball), rising over time
FLAME_N = NOISE + "float3 q = P / max(R, 1.0) * Freq + float3(0.0, 0.0, -fmod(T, 200.0) * Rise);\nfloat n = nz.fbm(q);\n"


def flame_inputs(g, extra=()):
    wp = g.e(unreal.MaterialExpressionWorldPosition)
    op = g.e(unreal.MaterialExpressionObjectPositionWS)
    rel = g.e(unreal.MaterialExpressionSubtract)
    mel.connect_material_expressions(wp, '', rel, 'A'); mel.connect_material_expressions(op, '', rel, 'B')
    rad = g.e(unreal.MaterialExpressionObjectRadius)
    tm = g.e(unreal.MaterialExpressionTime)
    return [('P', (rel, '')), ('R', (rad, '')), ('T', (tm, ''))] + list(extra)


# ---------------------------------------------------------------- M_Flame3D
m = fresh_material('M_Flame3D')
m.set_editor_property('blend_mode', unreal.BlendMode.BLEND_MASKED)
m.set_editor_property('shading_model', unreal.MaterialShadingModel.MSM_UNLIT)
m.set_editor_property('opacity_mask_clip_value', 0.5)
g = G(m)
burn = g.scalar('Burn', 0.0, cpd=0)
freq, rise, lump, glow = g.scalar('Freq', 2.2), g.scalar('Rise', 2.5), g.scalar('Lump', 0.3), g.scalar('Glow', 1.6)
# saturated on purpose: the tonemapper washes bright colours toward cream
cd, cm, ch, cw = (g.vec('ColDeep', unreal.LinearColor(0.42, 0.025, 0.005, 1)), g.vec('ColMid', unreal.LinearColor(0.95, 0.16, 0.015, 1)),
                  g.vec('ColHot', unreal.LinearColor(1.0, 0.42, 0.04, 1)), g.vec('ColWhite', unreal.LinearColor(1.0, 0.78, 0.3, 1)))
nrm = g.e(unreal.MaterialExpressionVertexNormalWS)
cam = g.e(unreal.MaterialExpressionCameraVectorWS)
ins = flame_inputs(g, [('Freq', (freq, '')), ('Rise', (rise, '')), ('Burn', (burn, ''))])
# colour: hotter where the ball faces the camera and where the noise is strong, cooler as it burns away; 4 bands
col = g.custom(FLAME_N + """float face = saturate(dot(normalize(N), normalize(V)));
float heat = face * 0.6 + n * 0.55 - 0.1 - Burn * 0.55;
float3 c = heat > 0.85 ? White : heat > 0.62 ? Hot : heat > 0.38 ? Mid : Deep;
return c * Glow;""", ins + [('N', (nrm, '')), ('V', (cam, '')), ('Deep', (cd, '')), ('Mid', (cm, '')), ('Hot', (ch, '')),
                            ('White', (cw, '')), ('Glow', (glow, ''))], F3)
mel.connect_material_property(col, '', unreal.MaterialProperty.MP_EMISSIVE_COLOR)
# burning away: the weakest flames go first
op = g.custom(FLAME_N + "return n + 0.5 - Burn * 1.25;", ins, F1)
mel.connect_material_property(op, '', unreal.MaterialProperty.MP_OPACITY_MASK)
# lumps: push the ball out along its normals by the noise, and stretch the top upward into tongues
wpo = g.custom(FLAME_N + """float3 nn = normalize(N);
return nn * R * Lump * (n - 0.35) * 2.0 + float3(0.0, 0.0, 1.0) * R * Lump * saturate(P.z / max(R, 1.0)) * n * 1.6;""",
               ins + [('N', (nrm, '')), ('Lump', (lump, ''))], F3)
mel.connect_material_property(wpo, '', unreal.MaterialProperty.MP_WORLD_POSITION_OFFSET)
mel.recompile_material(m); eal.save_loaded_asset(m)
M_FLAME = m


def mi(name, parent, scalars=None, vectors=None):
    path = f'{MAT}/{name}'
    inst = unreal.load_asset(path) if eal.does_asset_exist(path) else \
        at.create_asset(name, MAT, unreal.MaterialInstanceConstant, unreal.MaterialInstanceConstantFactoryNew())
    mel.set_material_instance_parent(inst, parent)
    for k, v in (scalars or {}).items():
        mel.set_material_instance_scalar_parameter_value(inst, k, v)
    for k, v in (vectors or {}).items():
        mel.set_material_instance_vector_parameter_value(inst, k, unreal.LinearColor(*v, 1.0))
    mel.update_material_instance(inst)
    eal.save_loaded_asset(inst)
    log.append(f'{name} -> {parent.get_name()}')
    return inst


mi('MI_Fire3D', M_FLAME, {'Glow': 1.6})
mi('MI_FireCore3D', M_FLAME, {'Glow': 2.0, 'Lump': 0.08, 'Freq': 1.6},
   {'ColDeep': (1.0, 0.3, 0.03), 'ColMid': (1.0, 0.5, 0.08), 'ColHot': (1.0, 0.7, 0.25), 'ColWhite': (1.0, 0.9, 0.6)})
mi('MI_Gold3D', M_FLAME, {'Glow': 1.8, 'Lump': 0.12, 'Rise': 1.0, 'Freq': 2.6},
   {'ColDeep': (0.7, 0.28, 0.01), 'ColMid': (1.0, 0.55, 0.05), 'ColHot': (1.0, 0.78, 0.25), 'ColWhite': (1.0, 0.95, 0.7)})

# ---------------------------------------------------------------- M_Spark3D
m = fresh_material('M_Spark3D')
m.set_editor_property('blend_mode', unreal.BlendMode.BLEND_MASKED)
m.set_editor_property('shading_model', unreal.MaterialShadingModel.MSM_UNLIT)
m.set_editor_property('two_sided', True)
g = G(m)
burn = g.scalar('Burn', 0.0, cpd=0)
glow = g.scalar('Glow', 4.0)
cr, ct = g.vec('ColRoot', unreal.LinearColor(1.0, 0.35, 0.05, 1)), g.vec('ColTip', unreal.LinearColor(1.0, 0.92, 0.6, 1))
uv = g.e(unreal.MaterialExpressionTextureCoordinate)
col = g.custom("return lerp(Root, Tip, UV.x) * Glow;", [('UV', (uv, '')), ('Root', (cr, '')), ('Tip', (ct, '')), ('Glow', (glow, ''))], F3)
mel.connect_material_property(col, '', unreal.MaterialProperty.MP_EMISSIVE_COLOR)
op = g.custom("return UV.x + 0.5 - Burn;", [('UV', (uv, '')), ('Burn', (burn, ''))], F1)
mel.connect_material_property(op, '', unreal.MaterialProperty.MP_OPACITY_MASK)
mel.recompile_material(m); eal.save_loaded_asset(m)
mi('MI_SparkFire3D', m, {'Glow': 2.2})
mi('MI_SparkGold3D', m, {'Glow': 2.4}, {'ColRoot': (1.0, 0.68, 0.12), 'ColTip': (1.0, 1.0, 0.85)})

# ---------------------------------------------------------------- M_Smoke3D (lit, so the sun and the fire light it)
m = fresh_material('M_Smoke3D')
m.set_editor_property('blend_mode', unreal.BlendMode.BLEND_MASKED)
g = G(m)
burn = g.scalar('Burn', 0.0, cpd=0)
freq, rise, lump = g.scalar('Freq', 1.8), g.scalar('Rise', 0.8), g.scalar('Lump', 0.3)
nrm = g.e(unreal.MaterialExpressionVertexNormalWS)
ins = flame_inputs(g, [('Freq', (freq, '')), ('Rise', (rise, '')), ('Burn', (burn, ''))])
col = g.custom(FLAME_N + "return n > 0.55 ? float3(0.34, 0.31, 0.29) : float3(0.2, 0.18, 0.17);", ins, F3)
mel.connect_material_property(col, '', unreal.MaterialProperty.MP_BASE_COLOR)
rough = g.e(unreal.MaterialExpressionConstant); rough.set_editor_property('r', 1.0)
mel.connect_material_property(rough, '', unreal.MaterialProperty.MP_ROUGHNESS)
op = g.custom(FLAME_N + "return n + 0.5 - Burn * 1.25;", ins, F1)
mel.connect_material_property(op, '', unreal.MaterialProperty.MP_OPACITY_MASK)
wpo = g.custom(FLAME_N + "return normalize(N) * R * Lump * (n - 0.35) * 2.0;", ins + [('N', (nrm, '')), ('Lump', (lump, ''))], F3)
mel.connect_material_property(wpo, '', unreal.MaterialProperty.MP_WORLD_POSITION_OFFSET)
mel.recompile_material(m); eal.save_loaded_asset(m)
log.append('M_Smoke3D made')

# ---------------------------------------------------------------- M_Beam3D
m = fresh_material('M_Beam3D')
m.set_editor_property('blend_mode', unreal.BlendMode.BLEND_MASKED)
m.set_editor_property('shading_model', unreal.MaterialShadingModel.MSM_UNLIT)
m.set_editor_property('two_sided', True)
g = G(m)
ln = g.scalar('Len', 500.0, cpd=0)
size, speed, around, thr = g.scalar('StreakCm', 60.0), g.scalar('Speed', 9.0), g.scalar('Around', 1.2), g.scalar('Threshold', 0.5)
twist, wob, glow = g.scalar('Twist', 0.0), g.scalar('Wobble', 0.06), g.scalar('Glow', 3.5)
c1, c2 = g.vec('ColEdge', unreal.LinearColor(1.0, 0.5, 0.04, 1)), g.vec('ColHot', unreal.LinearColor(1.0, 0.82, 0.3, 1))
uv = g.e(unreal.MaterialExpressionTextureCoordinate)
tm = g.e(unreal.MaterialExpressionTime)
nrm = g.e(unreal.MaterialExpressionVertexNormalWS)
BEAM_N = NOISE + """float along = UV.x * Len / StreakCm;
float ang = (UV.y + Twist * along) * 6.2831853;
float3 q = float3(along - fmod(T, 300.0) * Speed, cos(ang) * Around, sin(ang) * Around);
float n = nz.fbm(q);
"""
bi = [('UV', (uv, '')), ('Len', (ln, '')), ('StreakCm', (size, '')), ('Speed', (speed, '')), ('Around', (around, '')),
      ('Twist', (twist, '')), ('T', (tm, ''))]
col = g.custom(BEAM_N + "return (n > Thr + 0.12 ? Hot : Edge) * Glow;", bi + [('Thr', (thr, '')), ('Edge', (c1, '')), ('Hot', (c2, '')), ('Glow', (glow, ''))], F3)
mel.connect_material_property(col, '', unreal.MaterialProperty.MP_EMISSIVE_COLOR)
op = g.custom(BEAM_N + "return n + 0.5 - Thr;", bi + [('Thr', (thr, ''))], F1)
mel.connect_material_property(op, '', unreal.MaterialProperty.MP_OPACITY_MASK)
# a ripple that runs along the beam (the tube is 50 cm in radius before scaling, so Wobble is a fraction of it)
wpo = g.custom(BEAM_N + "return normalize(N) * 50.0 * Wobble * sin(UV.x * Len / 45.0 - fmod(T, 300.0) * 25.0);",
               bi + [('N', (nrm, '')), ('Wobble', (wob, ''))], F3)
mel.connect_material_property(wpo, '', unreal.MaterialProperty.MP_WORLD_POSITION_OFFSET)
mel.recompile_material(m); eal.save_loaded_asset(m)
mi('MI_BeamCore3D', m, {'Threshold': -1.0, 'Glow': 2.2, 'Wobble': 0.04, 'StreakCm': 40.0}, {'ColEdge': (1.0, 0.8, 0.4), 'ColHot': (1.0, 0.95, 0.75)})
mi('MI_BeamShell3D', m, {'Threshold': 0.48, 'Glow': 1.8})
mi('MI_BeamSwirl3D', m, {'Threshold': 0.66, 'Glow': 1.7, 'Twist': 0.35, 'Speed': 14.0, 'StreakCm': 35.0, 'Around': 2.0, 'Wobble': 0.0},
   {'ColEdge': (1.0, 0.55, 0.06), 'ColHot': (1.0, 0.85, 0.4)})

with open(os.path.join(unreal.Paths.project_saved_dir(), 'fx3d_result.txt'), 'w') as fh:
    fh.write('\n'.join(log) + '\n')
for line in log:
    unreal.log(f'FX3D {line}')
