"""Builds a small coffee shop made for the anime look: a new level (Lvl_Cafe) of simple shapes in flat colours with
drawn-on plank and tile lines, sunlight through three windows, hanging lamps, a street outside, the anime
post-process look (tools/unreal_make_anime_look.py must have been built first) and the Third Person template
character to walk around as.

Run it in the Unreal editor's console box (Cmd), with Play mode stopped and everything saved:
    py <repo>/tools/unreal_make_anime_cafe.py build     make the materials and (re)build the whole level, then save it
    py <repo>/tools/unreal_make_anime_cafe.py look Name=1.5 ...   change MI_AnimeLook_Cafe numbers
    py <repo>/tools/unreal_make_anime_cafe.py light Sun=8 Bloom=1.5 ...   try light levels on the open level (not saved)
Results and errors go to Saved/anime_cafe_result.txt.

Why simple shapes: the look wants clean silhouettes, flat colour and lines that are drawn into the surface. One
material (M_AnimeSurface) does every surface; each object passes its colour and pattern as custom primitive data, so
there are no material instances to manage. Everything the script places is tagged CafeGen and replaced on a rebuild.
"""
import math
import os
import random
import sys
import traceback
import unreal

MAP = '/Game/Game/Maps/Lvl_Cafe'
MATS = '/Game/Game/Materials'
SURF = 'M_AnimeSurface'
LOOK_PARENT, LOOK = 'M_AnimeLook', 'MI_AnimeLook_Cafe'
GAMEMODE = '/Game/ThirdPerson/Blueprints/BP_ThirdPersonGameMode'
WALKER = '/Game/ThirdPerson/Blueprints/BP_ThirdPersonCharacter'
# Once our own character is imported (see "character" below) the level uses it instead of the template mannequin.
CHAR_BP = '/Game/Game/Blueprints/BP_CafeWalker'       # child of the template character; cuts between Idle and Walk
CHAR_FOLDER = '/Game/Game/Imported/CafeWalker'        # where Interchange put the mesh, skeleton, animations, texture
TAG = 'CafeGen'
mel = unreal.MaterialEditingLibrary
eal = unreal.EditorAssetLibrary
out = []


def log(*a):
    out.append(' '.join(str(x) for x in a))


# ------------------------------------------------------------------ the surface material
# custom primitive data: 0-2 colour, 3 pattern, 4 pattern size (cm), 5 line width (cm), 6 line darkness, 7 roughness, 8 glow
CPD = ['R', 'G', 'B', 'Mode', 'Size', 'LineW', 'LineDark', 'Rough', 'Glow']

SURF_CODE = r'''
struct FPaint
{
    float H(float2 p) { return frac(sin(dot(p, float2(127.1, 311.7))) * 43758.5453); }
    float Ns(float2 p)
    {
        float2 i = floor(p);
        float2 f = frac(p);
        f = f * f * (3.0 - 2.0 * f);
        return lerp(lerp(H(i), H(i + float2(1, 0)), f.x), lerp(H(i + float2(0, 1)), H(i + float2(1, 1)), f.x), f.y);
    }
};
FPaint Q;
float3 C = float3(R, G, B);
float3 n = abs(N);
float2 p = n.z > 0.5 ? P.xy : (n.x > 0.5 ? P.yz : P.xz);   // flat coordinates on whichever way the surface faces
float up = n.z > 0.5 ? 0.0 : 1.0;                          // upright surface: p.y is height
// painted variation, the way a background painter never leaves an area one flat colour: a big soft wash, a
// smaller mottle, and brush streaks (up and down on walls, along the room on floors), warmer where lighter
float wash = Q.Ns(p / 170.0);
float mid = Q.Ns(p / 41.0 + 19.0);
float streak = Q.Ns(up > 0.5 ? float2(p.x / 13.0, p.y / 150.0) : float2(p.x / 150.0, p.y / 13.0));
float v = (wash - 0.5) * 0.24 + (mid - 0.5) * 0.10 + (streak - 0.5) * 0.05;
C *= 1.0 + v;
C *= lerp(float3(0.95, 0.99, 1.06), float3(1.06, 1.0, 0.93), saturate(0.5 + v * 3.0));
// walls and furniture get darker towards the floor and under the ceiling
C *= lerp(1.0, (0.84 + 0.16 * smoothstep(0.0, 120.0, P.z)) * (1.0 - 0.12 * smoothstep(235.0, 320.0, P.z)), up);
if (Mode < 0.5) { return C; }
float fw = max(length(ddx(p)), length(ddy(p)));            // world cm covered by one pixel
float lw = max(LineW, fw * 1.5);
float fade = saturate(LineW / max(fw * 1.5, 0.0001));      // far away, thin lines fade out instead of flickering
float ln = 0.0;
if (Mode < 1.5)
{   // 1 = floorboards: rows Size wide, boards six times as long, each row shifted
    float row = floor(p.y / Size);
    float u = p.x / (Size * 6.0) + frac(row * 0.37);
    float fx = frac(u) * Size * 6.0;
    float fy = frac(p.y / Size) * Size;
    float d = min(min(fx, Size * 6.0 - fx), min(fy, Size - fy));
    ln = 1.0 - smoothstep(lw * 0.5, lw, d);
    float bh = frac(sin(dot(float2(row, floor(u)), float2(12.9898, 78.233))) * 43758.5453);
    C *= 0.84 + 0.30 * bh;
    C *= lerp(float3(1.05, 1.0, 0.92), float3(0.96, 1.0, 1.05), frac(bh * 7.3));
    C *= 0.93 + 0.14 * Q.Ns(float2(p.x / 60.0 + bh * 50.0, p.y / 1.6));       // grain along each board
}
else if (Mode < 2.5)
{   // 2 = square tiles
    float2 f = frac(p / Size) * Size;
    float d = min(min(f.x, Size - f.x), min(f.y, Size - f.y));
    ln = 1.0 - smoothstep(lw * 0.5, lw, d);
}
else if (Mode < 3.5)
{   // 3 = upright boards (wall panelling)
    float fx = frac(p.x / Size) * Size;
    float d = min(fx, Size - fx);
    ln = 1.0 - smoothstep(lw * 0.5, lw, d);
    C *= 0.90 + 0.20 * frac(sin(floor(p.x / Size) * 91.7) * 43758.5453);
}
else if (Mode < 4.5)
{   // 4 = rows of windows on a far building
    float2 f = frac(p / float2(Size, Size * 1.25));
    float inside = step(0.2, f.x) * step(f.x, 0.8) * step(0.22, f.y) * step(f.y, 0.82);
    return lerp(C, C * LineDark, inside);
}
else
{   // 5 = wood grain: fine streaks along the surface (table tops, chairs, beams)
    float g = Q.Ns(up > 0.5 ? float2(p.x / Size, p.y / (Size * 22.0)) : float2(p.x / (Size * 22.0), p.y / Size));
    return C * (lerp(1.0, LineDark, smoothstep(0.55, 0.8, g)) * (0.94 + 0.12 * g));
}
return lerp(C, C * LineDark, ln * fade);
'''


def build_surface():
    tools = unreal.AssetToolsHelpers.get_asset_tools()
    path = MATS + '/' + SURF
    if eal.does_asset_exist(path):
        m = unreal.load_asset(path)
        for _ in range(12):
            if mel.get_num_material_expressions(m) == 0:
                break
            mel.delete_all_material_expressions(m)
    else:
        m = tools.create_asset(SURF, MATS, unreal.Material, unreal.MaterialFactoryNew())

    def node(cls, x, y):
        return mel.create_material_expression(m, cls, x, y)

    params = {}
    for i, n in enumerate(CPD):
        s = node(unreal.MaterialExpressionScalarParameter, -1100, i * 90)
        s.set_editor_property('parameter_name', n)
        s.set_editor_property('default_value', 0.5)
        s.set_editor_property('use_custom_primitive_data', True)
        s.set_editor_property('primitive_data_index', i)
        params[n] = s
    wp = node(unreal.MaterialExpressionWorldPosition, -1100, -260)
    vn = node(unreal.MaterialExpressionVertexNormalWS, -1100, -140)

    def custom(code, names, x, y):
        c = node(unreal.MaterialExpressionCustom, x, y)
        c.set_editor_property('code', code)
        c.set_editor_property('output_type', unreal.CustomMaterialOutputType.CMOT_FLOAT3)
        ins = []
        for n in names:
            ci = unreal.CustomInput()
            ci.set_editor_property('input_name', n)
            ins.append(ci)
        c.set_editor_property('inputs', ins)
        return c

    base = custom(SURF_CODE, ['P', 'N', 'R', 'G', 'B', 'Mode', 'Size', 'LineW', 'LineDark'], -500, 0)
    mel.connect_material_expressions(wp, '', base, 'P')
    mel.connect_material_expressions(vn, '', base, 'N')
    for n in ['R', 'G', 'B', 'Mode', 'Size', 'LineW', 'LineDark']:
        mel.connect_material_expressions(params[n], '', base, n)
    glow = custom('return float3(R, G, B) * Glow;', ['R', 'G', 'B', 'Glow'], -500, 500)
    for n in ['R', 'G', 'B', 'Glow']:
        mel.connect_material_expressions(params[n], '', glow, n)
    spec = node(unreal.MaterialExpressionConstant, -500, 800)
    spec.set_editor_property('r', 0.2)
    mel.connect_material_property(base, '', unreal.MaterialProperty.MP_BASE_COLOR)
    mel.connect_material_property(glow, '', unreal.MaterialProperty.MP_EMISSIVE_COLOR)
    mel.connect_material_property(params['Rough'], '', unreal.MaterialProperty.MP_ROUGHNESS)
    mel.connect_material_property(spec, '', unreal.MaterialProperty.MP_SPECULAR)
    mel.recompile_material(m)
    eal.save_loaded_asset(m)
    log('surface material', mel.get_num_material_expressions(m), 'nodes')
    return m


def build_flat():
    """M_AnimeFlat: one matte colour, for the stand-in character (a skinned mesh can't take a colour per part from
    custom primitive data, so it gets two instances: top and trousers)."""
    tools = unreal.AssetToolsHelpers.get_asset_tools()
    path = MATS + '/M_AnimeFlat'
    if eal.does_asset_exist(path):
        m = unreal.load_asset(path)
    else:
        m = tools.create_asset('M_AnimeFlat', MATS, unreal.Material, unreal.MaterialFactoryNew())
        col = mel.create_material_expression(m, unreal.MaterialExpressionVectorParameter, -400, 0)
        col.set_editor_property('parameter_name', 'Color')
        col.set_editor_property('default_value', unreal.LinearColor(0.5, 0.5, 0.5, 1.0))
        rough = mel.create_material_expression(m, unreal.MaterialExpressionConstant, -400, 250)
        rough.set_editor_property('r', 0.95)
        spec = mel.create_material_expression(m, unreal.MaterialExpressionConstant, -400, 350)
        spec.set_editor_property('r', 0.1)
        mel.connect_material_property(col, '', unreal.MaterialProperty.MP_BASE_COLOR)
        mel.connect_material_property(rough, '', unreal.MaterialProperty.MP_ROUGHNESS)
        mel.connect_material_property(spec, '', unreal.MaterialProperty.MP_SPECULAR)
        m.set_editor_property('used_with_skeletal_mesh', True)
        mel.recompile_material(m)
        eal.save_loaded_asset(m)
    res = []
    for name, c in (('MI_Cafe_Top', (0.80, 0.78, 0.72)), ('MI_Cafe_Trousers', (0.07, 0.08, 0.13))):
        ip = MATS + '/' + name
        if eal.does_asset_exist(ip):
            mi = unreal.load_asset(ip)
        else:
            mi = tools.create_asset(name, MATS, unreal.MaterialInstanceConstant, unreal.MaterialInstanceConstantFactoryNew())
            mel.set_material_instance_parent(mi, m)
        mel.set_material_instance_vector_parameter_value(mi, 'Color', unreal.LinearColor(c[0], c[1], c[2], 1.0))
        mel.update_material_instance(mi)
        eal.save_loaded_asset(mi)
        res.append(mi)
    return res


def find_character():
    """The imported character's assets, found by type: {'mesh', 'walk', 'idle', 'tex'} or None if it isn't imported."""
    reg = unreal.AssetRegistryHelpers.get_asset_registry()
    got = {}
    for ad in reg.get_assets_by_path(CHAR_FOLDER, recursive=True):
        cls = str(ad.asset_class_path.asset_name)
        name = str(ad.asset_name)
        path = str(ad.package_name)
        if cls == 'SkeletalMesh':
            got['mesh'] = path
        elif cls == 'AnimSequence' and '/Anims/' not in path:
            got['idle' if 'idle' in name.lower() else 'walk'] = path      # the hand-keyed pair that came in with the mesh
        elif cls == 'BlendSpace':
            got['blend'] = path      # motion-captured idle/walk/jog from tools/unreal_retarget_mannequin.py; used when present
        elif cls == 'Texture2D' and 'tex' not in got:
            got['tex'] = path
    return got if all(k in got for k in ('mesh', 'walk', 'idle')) else None


def build_character_material(tex_path):
    """M_AnimeChar: the character's painted colour texture on a matte surface (no shine, no bumps), so the look's two
    tones stay clean. One instance per character."""
    tools = unreal.AssetToolsHelpers.get_asset_tools()
    path = MATS + '/M_AnimeChar'
    if eal.does_asset_exist(path):
        m = unreal.load_asset(path)
    else:
        m = tools.create_asset('M_AnimeChar', MATS, unreal.Material, unreal.MaterialFactoryNew())
        tex = mel.create_material_expression(m, unreal.MaterialExpressionTextureSampleParameter2D, -500, 0)
        tex.set_editor_property('parameter_name', 'Tex')
        if tex_path:
            tex.set_editor_property('texture', unreal.load_asset(tex_path))
        rough = mel.create_material_expression(m, unreal.MaterialExpressionConstant, -500, 300)
        rough.set_editor_property('r', 0.95)
        spec = mel.create_material_expression(m, unreal.MaterialExpressionConstant, -500, 400)
        spec.set_editor_property('r', 0.1)
        mel.connect_material_property(tex, 'RGB', unreal.MaterialProperty.MP_BASE_COLOR)
        mel.connect_material_property(rough, '', unreal.MaterialProperty.MP_ROUGHNESS)
        mel.connect_material_property(spec, '', unreal.MaterialProperty.MP_SPECULAR)
        m.set_editor_property('used_with_skeletal_mesh', True)
        mel.recompile_material(m)
        eal.save_loaded_asset(m)
    ip = MATS + '/MI_CafeWalker'
    if eal.does_asset_exist(ip):
        mi = unreal.load_asset(ip)
    else:
        mi = tools.create_asset('MI_CafeWalker', MATS, unreal.MaterialInstanceConstant, unreal.MaterialInstanceConstantFactoryNew())
        mel.set_material_instance_parent(mi, m)
    if tex_path:
        mel.set_material_instance_texture_parameter_value(mi, 'Tex', unreal.load_asset(tex_path))
    mel.update_material_instance(mi)
    eal.save_loaded_asset(mi)
    return mi


# The indoor version of the look: a painted room (BgCel 0) with a cel-shaded character in it, late-afternoon sun.
# The old cel numbers (ShadowT, HiT, ...) are unused while BgCel is 0.
SUN_PITCH, SUN_YAW = -17.0, -112.0
LOOK_VALUES = {'BgCel': 0.0, 'Paint': 3.0, 'BgSat': 1.12, 'BgShadowHi': 0.10, 'BgInkOpacity': 0.85, 'BgInkDark': 0.12,
               'BgLineScale': 0.75, 'Smooth': 2.0, 'LineFar': 3000.0, 'LineFarDepth': 9000.0, 'LineWidth': 1.5,
               'GlowT': 14.0, 'LightHue': 0.6, 'Boil': 0.3, 'InkOpacity': 0.95, 'LitLevel': 1.0,
               'CharOn': 1.0, 'CharSmooth': 3.0, 'CharShadowT': 0.15, 'CharSoft': 0.02, 'CharShadowLevel': 0.5,
               'CharLevel': 0.55, 'CharEnv': 0.35, 'CharEnvRef': 0.6, 'RimWidth': 4.0, 'RimStrength': 0.7}
LOOK_TINT = {'InkColor': (0.030, 0.014, 0.012), 'CharShadowTint': (0.66, 0.52, 0.72), 'RimColor': (1.0, 0.80, 0.52),
             'BgShadowTint': (0.84, 0.80, 1.0)}


def key_dir():
    """Towards the sun, so the character's drawn shadow agrees with the light patches on the floor."""
    pr, yr = math.radians(SUN_PITCH), math.radians(SUN_YAW)
    return (-math.cos(pr) * math.cos(yr), -math.cos(pr) * math.sin(yr), -math.sin(pr) + 0.25)


def build_look(pairs=None):
    path = MATS + '/' + LOOK
    if eal.does_asset_exist(path):
        mi = unreal.load_asset(path)
    else:
        mi = unreal.AssetToolsHelpers.get_asset_tools().create_asset(LOOK, MATS, unreal.MaterialInstanceConstant,
                                                                     unreal.MaterialInstanceConstantFactoryNew())
        mel.set_material_instance_parent(mi, unreal.load_asset(MATS + '/' + LOOK_PARENT))
        pairs = None
    if pairs is None:
        for n, v in LOOK_VALUES.items():
            mel.set_material_instance_scalar_parameter_value(mi, n, v)
        for n, v in list(LOOK_TINT.items()) + [('KeyDir', key_dir())]:
            mel.set_material_instance_vector_parameter_value(mi, n, unreal.LinearColor(v[0], v[1], v[2], 1.0))
    else:
        for p in pairs:
            n, v = p.split('=')
            if ',' in v:
                r, g, b = [float(x) for x in v.split(',')]
                mel.set_material_instance_vector_parameter_value(mi, n, unreal.LinearColor(r, g, b, 1.0))
            else:
                mel.set_material_instance_scalar_parameter_value(mi, n, float(v))
            log('look', n, v)
    mel.update_material_instance(mi)
    eal.save_loaded_asset(mi)
    return mi


def build_shaft():
    """M_AnimeShaft: a see-through, glowing slab for the sunbeams (additive, unlit, both sides), brightest by the
    window and gone by the floor. Drawn beams with hard edges, as in a film; real fog gave no visible shafts here."""
    path = MATS + '/M_AnimeShaft'
    if eal.does_asset_exist(path):
        m = unreal.load_asset(path)
        for _ in range(12):
            if mel.get_num_material_expressions(m) == 0:
                break
            mel.delete_all_material_expressions(m)
    else:
        m = unreal.AssetToolsHelpers.get_asset_tools().create_asset('M_AnimeShaft', MATS, unreal.Material, unreal.MaterialFactoryNew())
    m.set_editor_property('blend_mode', unreal.BlendMode.BLEND_ADDITIVE)
    m.set_editor_property('shading_model', unreal.MaterialShadingModel.MSM_UNLIT)
    m.set_editor_property('two_sided', True)
    # drawn after the anime look, like a compositing layer: the beams then also fall across the character
    m.set_editor_property('translucency_pass', unreal.MaterialTranslucencyPass.MTP_AFTER_DOF)
    wp = mel.create_material_expression(m, unreal.MaterialExpressionWorldPosition, -700, 0)
    col = mel.create_material_expression(m, unreal.MaterialExpressionVectorParameter, -700, 200)
    col.set_editor_property('parameter_name', 'Color')
    col.set_editor_property('default_value', unreal.LinearColor(1.0, 0.72, 0.40, 1.0))
    st = mel.create_material_expression(m, unreal.MaterialExpressionScalarParameter, -700, 450)
    st.set_editor_property('parameter_name', 'Strength')
    st.set_editor_property('default_value', SHAFT_GLOW)
    c = mel.create_material_expression(m, unreal.MaterialExpressionCustom, -300, 100)
    c.set_editor_property('code', 'return Color * Strength * smoothstep(5.0, 230.0, P.z);')
    c.set_editor_property('output_type', unreal.CustomMaterialOutputType.CMOT_FLOAT3)
    ins = []
    for n in ('P', 'Color', 'Strength'):
        ci = unreal.CustomInput()
        ci.set_editor_property('input_name', n)
        ins.append(ci)
    c.set_editor_property('inputs', ins)
    mel.connect_material_expressions(wp, '', c, 'P')
    mel.connect_material_expressions(col, '', c, 'Color')
    mel.connect_material_expressions(st, '', c, 'Strength')
    mel.connect_material_property(c, '', unreal.MaterialProperty.MP_EMISSIVE_COLOR)
    mel.recompile_material(m)
    eal.save_loaded_asset(m)
    return m


# ------------------------------------------------------------------ the level
# The player: 300 cm/s is the speed the mannequin's walk animation was captured at, so the feet don't slide.
# POSE_STEP 0 = a new pose every frame; 1/12 = "on twos" like drawn animation (it read as stutter in playtest).
WALK_SPEED, POSE_STEP = 300.0, 0.0
# light levels (the sun in lux; everything else is balanced against it)
SUN_LUX, SKY, SHAFTS, FOG, EXPOSURE, BLOOM, LAMP_CD, OUT_GLOW, SHAFT_GLOW = 8.0, 1.3, 1.0, 0.02, 0.5, 1.5, 1.2, 1.6, 0.035
class Cafe:
    def __init__(self, surface):
        self.eas = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
        self.m = surface
        self.mesh = {k: unreal.load_asset('/Engine/BasicShapes/' + k) for k in ['Cube', 'Cylinder', 'Sphere', 'Cone']}
        self.n = 0
        self.rng = random.Random(7)

    def tag(self, a, name, folder):
        self.n += 1
        a.set_actor_label('Cafe_%s_%03d' % (name, self.n))
        a.set_editor_property('tags', [unreal.Name(TAG)])
        a.set_folder_path('Cafe/' + folder)

    def shape(self, kind, name, loc, scale, col, folder, yaw=0.0, mode=0, size=20.0, linew=0.9, dark=0.45, rough=0.92, glow=0.0):
        a = self.eas.spawn_actor_from_class(unreal.StaticMeshActor, unreal.Vector(loc[0], loc[1], loc[2]),
                                            unreal.Rotator(roll=0.0, pitch=0.0, yaw=yaw))
        c = a.static_mesh_component
        c.set_static_mesh(self.mesh[kind])
        c.set_material(0, self.m)
        a.set_actor_scale3d(unreal.Vector(scale[0], scale[1], scale[2]))
        for i, v in enumerate([col[0], col[1], col[2], mode, size, linew, dark, rough, glow]):
            c.set_default_custom_primitive_data_float(i, float(v))
        self.tag(a, name, folder)
        return a

    # centre + size in cm
    def box(self, name, c, s, col, folder='Room', **kw):
        return self.shape('Cube', name, c, (s[0] / 100.0, s[1] / 100.0, s[2] / 100.0), col, folder, **kw)

    def cyl(self, name, c, dia, h, col, folder='Props', **kw):
        return self.shape('Cylinder', name, c, (dia / 100.0, dia / 100.0, h / 100.0), col, folder, **kw)

    def ball(self, name, c, dia, col, folder='Props', sz=None, **kw):
        return self.shape('Sphere', name, c, (dia / 100.0, dia / 100.0, (sz or dia) / 100.0), col, folder, **kw)

    def cone(self, name, c, dia, h, col, folder='Props', **kw):
        return self.shape('Cone', name, c, (dia / 100.0, dia / 100.0, h / 100.0), col, folder, **kw)

    # ---- colours
    WOOD_FLOOR = (0.30, 0.17, 0.085)
    CREAM = (0.78, 0.70, 0.56)
    GREEN = (0.09, 0.19, 0.16)
    CEIL = (0.80, 0.76, 0.66)
    DARKWOOD = (0.13, 0.072, 0.04)
    MIDWOOD = (0.40, 0.23, 0.115)
    TOP = (0.82, 0.80, 0.74)
    RED = (0.55, 0.075, 0.055)
    METAL = (0.55, 0.57, 0.60)
    WHITE = (0.86, 0.86, 0.83)
    LEAF1, LEAF2 = (0.09, 0.28, 0.10), (0.17, 0.42, 0.15)
    POT = (0.55, 0.22, 0.12)
    BLACK = (0.035, 0.035, 0.045)
    BULB = (1.0, 0.78, 0.48)

    def room(self):
        b = self.box
        b('Floor', (0, 0, -5), (940, 740, 10), self.WOOD_FLOOR, mode=1, size=14, linew=0.7, dark=0.4)
        b('Ceiling', (0, 0, 325), (940, 740, 10), self.CEIL)
        for x in (-300, 0, 300):
            b('Beam', (x, 0, 311), (22, 700, 18), self.DARKWOOD, mode=5, size=2.5, dark=0.7)
        # walls: back (counter), left (booth), front (door), right (windows)
        b('WallBack', (460, 0, 160), (20, 740, 320), self.CREAM)
        b('WallLeft', (0, -360, 160), (940, 20, 320), self.CREAM)
        b('WallFrontA', (-460, -207.5, 160), (20, 305, 320), self.CREAM)
        b('WallFrontB', (-460, 207.5, 160), (20, 305, 320), self.CREAM)
        b('WallFrontTop', (-460, 0, 267.5), (20, 110, 105), self.CREAM)
        b('WallWinLow', (0, 360, 42.5), (940, 20, 85), self.CREAM)
        b('WallWinTop', (0, 360, 292.5), (940, 20, 55), self.CREAM)
        for x0, x1 in ((-470, -400), (-180, -140), (80, 120), (340, 470)):
            b('Pier', ((x0 + x1) / 2.0, 360, 175), (x1 - x0, 20, 180), self.CREAM)
        # green panelling up to a rail, on every wall
        pan = dict(mode=3, size=22, linew=0.8, dark=0.5)
        b('PanelBack', (448.5, 0, 55), (3, 700, 110), self.GREEN, **pan)
        b('PanelLeft', (0, -348.5, 55), (900, 3, 110), self.GREEN, **pan)
        b('PanelFrontA', (-448.5, -202.5, 55), (3, 295, 110), self.GREEN, **pan)
        b('PanelFrontB', (-448.5, 202.5, 55), (3, 295, 110), self.GREEN, **pan)
        b('PanelWin', (0, 348.5, 42), (900, 3, 84), self.GREEN, **pan)
        b('RailBack', (447, 0, 112), (6, 700, 5), self.DARKWOOD)
        b('RailLeft', (0, -347, 112), (900, 6, 5), self.DARKWOOD)
        b('RailFrontA', (-447, -202.5, 112), (6, 295, 5), self.DARKWOOD)
        b('RailFrontB', (-447, 202.5, 112), (6, 295, 5), self.DARKWOOD)
        for nm, cc, ss in (('Back', (446, 0), (8, 700)), ('Left', (0, -346), (900, 8)), ('Win', (0, 346), (900, 8)),
                           ('FrontA', (-446, -202.5), (8, 295)), ('FrontB', (-446, 202.5), (8, 295))):
            b('Skirting' + nm, (cc[0], cc[1], 6), (ss[0], ss[1], 12), self.DARKWOOD)
            b('Moulding' + nm, (cc[0], cc[1], 314), (ss[0] + 4, ss[1] + 4, 12), self.DARKWOOD)
        # door
        b('Door', (-462, 0, 107.5), (7, 106, 213), (0.07, 0.24, 0.27))
        b('DoorGlass', (-462, 0, 150), (8, 62, 86), (0.80, 0.90, 0.95), glow=2.5)
        b('DoorFrameL', (-458, -57, 110), (26, 8, 220), self.DARKWOOD)
        b('DoorFrameR', (-458, 57, 110), (26, 8, 220), self.DARKWOOD)
        b('DoorFrameT', (-458, 0, 219), (26, 122, 8), self.DARKWOOD)
        self.ball('DoorKnob', (-455, 42, 100), 7, (0.75, 0.6, 0.25), 'Room', rough=0.35)
        # window frames and sills
        for x0, x1 in ((-400, -180), (-140, 80), (120, 340)):
            xc, w = (x0 + x1) / 2.0, x1 - x0
            b('WinBottom', (xc, 360, 88), (w, 24, 6), self.DARKWOOD)
            b('WinTop', (xc, 360, 262), (w, 24, 6), self.DARKWOOD)
            b('WinSideA', (x0 + 3, 360, 175), (6, 24, 180), self.DARKWOOD)
            b('WinSideB', (x1 - 3, 360, 175), (6, 24, 180), self.DARKWOOD)
            b('WinPost', (xc, 360, 175), (5, 10, 180), self.DARKWOOD)
            b('WinBar', (xc, 360, 205), (w, 10, 5), self.DARKWOOD)
            b('Sill', (xc, 344, 84), (w + 12, 30, 4), self.MIDWOOD)
            b('Blind', (xc, 352, 247), (w - 14, 3, 30), (0.80, 0.66, 0.42), mode=2, size=5, linew=0.5, dark=0.75)
            b('BlindBar', (xc, 351, 231), (w - 10, 4, 3), self.DARKWOOD)

    def counter(self):
        b, c = self.box, self.cyl
        b('CounterBody', (330, -90, 50), (80, 420, 100), self.DARKWOOD, 'Counter', mode=3, size=28, linew=0.9, dark=0.55)
        b('CounterTop', (328, -90, 103), (94, 432, 6), self.TOP, 'Counter', rough=0.5)
        b('CounterFoot', (289, -90, 6), (4, 420, 12), self.BLACK, 'Counter')
        # espresso machine
        b('Espresso', (335, -205, 129), (50, 72, 44), self.RED, 'Counter', rough=0.35)
        b('EspressoTop', (335, -205, 153), (46, 68, 4), self.METAL, 'Counter', rough=0.3)
        b('EspressoTray', (306, -205, 108), (14, 60, 3), self.METAL, 'Counter', rough=0.3)
        for y in (-222, -188):
            c('GroupHead', (306, y, 121), 9, 6, self.METAL, 'Counter', rough=0.3)
            c('ShotCup', (306, y, 112.5), 6, 5, self.WHITE, 'Counter')
        for i in range(6):
            c('CupOnMachine', (328 + (i % 2) * 12, -228 + (i // 2) * 22, 158.5), 8, 7, self.WHITE, 'Counter')
        # till, cup stack, jar, cakes
        b('Till', (332, -45, 116), (34, 40, 20), self.BLACK, 'Counter')
        b('TillScreen', (320, -45, 137), (4, 30, 22), self.BLACK, 'Counter')
        b('TillGlow', (317.6, -45, 137), (1, 26, 18), (0.55, 0.85, 0.80), 'Counter', glow=1.5)
        c('CupStack', (345, -120, 119), 9, 26, self.WHITE, 'Counter', mode=2, size=3.2, linew=0.25, dark=0.6)
        c('CupStack', (345, -106, 116), 9, 20, self.WHITE, 'Counter', mode=2, size=3.2, linew=0.25, dark=0.6)
        c('Jar', (312, -85, 113), 11, 14, (0.75, 0.86, 0.88), 'Counter', rough=0.3)
        for y, col in ((30, (0.86, 0.55, 0.60)), (65, (0.90, 0.84, 0.66)), (100, (0.22, 0.11, 0.06))):
            c('CakePlate', (322, y, 107), 27, 1.6, self.WHITE, 'Counter')
            c('Cake', (322, y, 112), 20, 8.5, col, 'Counter')
            c('CakeTop', (322, y, 116.8), 20.5, 1.2, self.WHITE if col[0] < 0.5 else (0.6, 0.1, 0.12), 'Counter')
        # shelves on the back wall, full of bottles, jars and cups
        bottle_cols = [(0.45, 0.20, 0.06), (0.10, 0.30, 0.14), (0.14, 0.22, 0.40), (0.55, 0.10, 0.10), (0.80, 0.70, 0.40)]
        for z in (150, 195, 240):
            b('Shelf', (438, -90, z), (24, 410, 4), self.DARKWOOD, 'Counter')
            y = -285.0
            while y < 105:
                kind = self.rng.choice(['bottle', 'bottle', 'jar', 'cup', 'cup'])
                if kind == 'bottle':
                    col = self.rng.choice(bottle_cols)
                    c('Bottle', (438, y, z + 2 + 11), 7, 22, col, 'Counter', rough=0.35)
                    c('BottleNeck', (438, y, z + 2 + 26), 3, 8, col, 'Counter', rough=0.35)
                    y += 12
                elif kind == 'jar':
                    c('Jar', (438, y, z + 2 + 8), 11, 16, self.rng.choice([(0.72, 0.58, 0.36), (0.30, 0.16, 0.08), (0.80, 0.82, 0.78)]), 'Counter')
                    c('JarLid', (438, y, z + 2 + 17), 11.5, 2, self.DARKWOOD, 'Counter')
                    y += 16
                else:
                    c('Cup', (438, y, z + 2 + 4), 8.5, 8, self.rng.choice([self.WHITE, self.WHITE, (0.20, 0.42, 0.45), (0.80, 0.45, 0.20)]), 'Counter')
                    y += 13
                y += self.rng.uniform(2, 9)
        # menu board on the back wall, past the end of the counter
        b('MenuFrame', (447, 240, 205), (5, 180, 120), self.MIDWOOD, 'Counter')
        b('MenuBoard', (445.5, 240, 205), (4, 166, 106), (0.03, 0.05, 0.045), 'Counter')
        for i in range(7):
            w = 120 - (i * 37 % 60)
            b('Chalk', (443.2, 240 + (60 - w / 2.0) - 0.0, 245 - i * 13), (1, w, 3.2 if i else 6), (0.82, 0.82, 0.76), 'Counter')

    def chair(self, x, y, yaw, cushion):
        r = math.radians(yaw)
        ca, sa = math.cos(r), math.sin(r)

        def at(dx, dy, z):
            return (x + dx * ca - dy * sa, y + dx * sa + dy * ca, z)

        self.box('ChairSeat', at(0, 0, 45), (42, 42, 4), self.DARKWOOD, 'Seats', yaw=yaw)
        self.box('ChairPad', at(0, 0, 48.5), (38, 38, 3), cushion, 'Seats', yaw=yaw)
        for dy in (-19, 19):
            self.box('ChairPost', at(-19, dy, 70), (4, 4, 50), self.DARKWOOD, 'Seats', yaw=yaw)
        self.box('ChairRail', at(-19, 0, 91), (4.5, 42, 9), self.DARKWOOD, 'Seats', yaw=yaw)
        self.box('ChairRailLow', at(-19, 0, 58), (3, 36, 4), self.DARKWOOD, 'Seats', yaw=yaw)
        for dy in (-10, 0, 10):
            self.box('ChairSlat', at(-19, dy, 74), (2, 5, 30), self.DARKWOOD, 'Seats', yaw=yaw)
        for dx in (-18, 18):
            for dy in (-18, 18):
                self.box('ChairLeg', at(dx, dy, 21.5), (4, 4, 43), self.DARKWOOD, 'Seats', yaw=yaw)

    def cup(self, x, y, z):
        self.cyl('Saucer', (x, y, z + 0.6), 14, 1.2, self.WHITE, 'Tables')
        self.cyl('Cup', (x, y, z + 4.2), 8, 6, self.WHITE, 'Tables')
        self.cyl('Coffee', (x, y, z + 7.0), 6.6, 0.6, (0.16, 0.08, 0.04), 'Tables')

    def lamp(self, x, y, shade=(0.05, 0.16, 0.17)):
        self.cyl('LampCord', (x, y, 268), 1.5, 104, self.BLACK, 'Lamps')
        self.cone('LampShade', (x, y, 205), 38, 24, shade, 'Lamps')
        self.ball('LampBulb', (x, y, 193), 9, self.BULB, 'Lamps', glow=10.0)
        a = self.eas.spawn_actor_from_class(unreal.PointLight, unreal.Vector(x, y, 186), unreal.Rotator(roll=0.0, pitch=0.0, yaw=0.0))
        lc = a.point_light_component
        lc.set_editor_property('intensity_units', unreal.LightUnits.CANDELAS)
        lc.set_intensity(LAMP_CD)             # tiny: the sun is 8 lux here, so a few candela is already a bright lamp
        lc.set_attenuation_radius(420.0)
        lc.set_light_color(unreal.LinearColor(1.0, 0.74, 0.46, 1.0))
        lc.set_cast_shadows(False)
        self.tag(a, 'LampLight', 'Lamps')

    def seating(self):
        b, c = self.box, self.cyl
        # booth along the left wall, with three small tables
        b('BoothBase', (-150, -322, 21), (520, 54, 42), self.DARKWOOD, 'Seats', mode=3, size=26, linew=0.8, dark=0.55)
        b('BoothSeat', (-150, -322, 46), (520, 54, 8), self.RED, 'Seats')
        b('BoothBack', (-150, -343, 82), (520, 10, 60), self.RED, 'Seats', mode=3, size=65, linew=0.9, dark=0.6)
        for x in (-320, -150, 20):
            b('BoothTable', (x, -255, 73), (70, 62, 4), self.MIDWOOD, 'Tables', mode=5, size=2.2, dark=0.8)
            c('BoothTableLeg', (x, -255, 36), 8, 70, self.BLACK, 'Tables')
            c('BoothTableFoot', (x, -255, 1.5), 42, 3, self.BLACK, 'Tables')
            self.chair(x, -196, -90, self.RED)
            self.cup(x - 12, -262, 75)
            self.lamp(x, -255)
        # two round tables on the window side
        for x in (-285, -55):
            c('RoundTop', (x, 110, 73), 82, 4, self.MIDWOOD, 'Tables', mode=5, size=2.2, dark=0.8)
            c('RoundLeg', (x, 110, 36), 8, 70, self.BLACK, 'Tables')
            c('RoundFoot', (x, 110, 1.5), 46, 3, self.BLACK, 'Tables')
            self.chair(x - 62, 110, 0, (0.10, 0.30, 0.32))
            self.chair(x + 62, 110, 180, (0.10, 0.30, 0.32))
            self.cup(x - 16, 104, 75)
            self.cup(x + 15, 118, 75)
            c('Vase', (x, 96, 81), 6, 12, (0.20, 0.42, 0.45), 'Tables')
            self.ball('Flower', (x, 96, 91), 9, (0.90, 0.70, 0.20), 'Tables')
            self.lamp(x, 110)
        # a bar along the windows, with stools
        b('WindowBar', (-30, 322, 100), (720, 38, 5), self.MIDWOOD, 'Tables', mode=5, size=2.2, dark=0.8)
        for x in (-380, -150, 100, 320):
            b('BarBracket', (x, 332, 88), (5, 22, 20), self.BLACK, 'Tables')
        for x in (-320, -205, -90, 25, 140, 255):
            c('StoolSeat', (x, 280, 70), 34, 6, self.RED, 'Seats')
            c('StoolLeg', (x, 280, 34), 5, 66, self.BLACK, 'Seats')
            c('StoolFoot', (x, 280, 1.5), 30, 3, self.BLACK, 'Seats')
            c('StoolRing', (x, 280, 26), 22, 2, self.BLACK, 'Seats')
        self.cup(-200, 322, 102.5)
        self.cup(140, 320, 102.5)
        for y in (-200, -60, 60):
            self.lamp(322, y, shade=(0.45, 0.07, 0.05))

    def decor(self):
        b, c = self.box, self.cyl

        def plant(x, y, s=1.0, seed=1, leaves=26, tall=1.0, z0=0.0):
            """A potted plant drawn the way a background painter would: a pot, a stem and separate oval leaves
            (flattened balls) fanning up and out, in three greens. Balls stacked into a blob read as computer art."""
            rng = random.Random(seed)
            c('Pot', (x, y, z0 + 19 * s), 38 * s, 38 * s, self.POT, 'Decor')
            c('PotRim', (x, y, z0 + 38 * s), 43 * s, 6 * s, (0.42, 0.16, 0.09), 'Decor')
            c('Soil', (x, y, z0 + 41.2 * s), 36 * s, 1.0, (0.07, 0.045, 0.03), 'Decor')
            c('Stem', (x, y, z0 + (41 + 45 * tall) * s), 3.5 * s, 90 * tall * s, (0.16, 0.20, 0.08), 'Decor')
            greens = [self.LEAF1, self.LEAF2, (0.05, 0.20, 0.09), (0.24, 0.48, 0.16)]
            for i in range(leaves):
                ang = i * 137.5 + rng.uniform(-20, 20)                 # the spiral leaves really grow in
                t = (i + 0.5) / leaves                                 # 0 = lowest leaf, 1 = top
                h = z0 + (48 + 105 * tall * t) * s
                lift = 15 + 60 * t + rng.uniform(-10, 10)              # low leaves lie flat, top ones stand up
                length = (40 - 14 * t + rng.uniform(-4, 4)) * s
                reach = (10 * s + 0.42 * length * math.cos(math.radians(lift))) * (1.0 if t < 0.85 else 0.6)
                a = math.radians(ang)
                leaf = self.shape('Sphere', 'Leaf', (x + math.cos(a) * reach, y + math.sin(a) * reach, h + 0.4 * length * math.sin(math.radians(lift))),
                                  (length / 100.0, length * 0.52 / 100.0, 0.035 * s), greens[i % len(greens)], 'Decor')
                leaf.set_actor_rotation(unreal.Rotator(roll=rng.uniform(-18, 18), pitch=lift, yaw=ang), False)

        plant(-410, 305, 1.0, seed=3)
        plant(405, 305, 0.9, seed=5)
        plant(-408, -160, 0.8, seed=8, tall=0.8)
        # small plants on the window sills: dark shapes against the bright street
        for i, x in enumerate((-345, -235, -30, 175, 290)):
            plant(x, 340, 0.32, seed=20 + i, leaves=11, tall=0.55 + 0.2 * (i % 2), z0=86.0)
        # pictures above the booth
        for x, col in ((-320, (0.80, 0.50, 0.25)), (-150, (0.30, 0.55, 0.62)), (20, (0.72, 0.30, 0.30))):
            b('PictureFrame', (x, -347, 205), (74, 4, 54), self.DARKWOOD, 'Decor')
            b('Picture', (x, -345.5, 205), (64, 3, 44), col, 'Decor')
            c('PictureSun', (x + 14, -343.6, 212), 14, 1, (0.95, 0.90, 0.70), 'Decor').set_actor_rotation(
                unreal.Rotator(roll=90.0, pitch=0.0, yaw=0.0), False)
        # clock on the front wall
        clock = c('Clock', (-448, -200, 215), 46, 5, self.WHITE, 'Decor')
        clock.set_actor_rotation(unreal.Rotator(roll=0.0, pitch=90.0, yaw=0.0), False)
        rim = c('ClockRim', (-449, -200, 215), 50, 4, self.DARKWOOD, 'Decor')
        rim.set_actor_rotation(unreal.Rotator(roll=0.0, pitch=90.0, yaw=0.0), False)
        b('ClockHandA', (-445, -200, 222), (1, 2, 16), self.BLACK, 'Decor')
        b('ClockHandB', (-445, -193, 215), (1, 14, 2), self.BLACK, 'Decor')
        b('DoorMat', (-405, 0, 0.6), (60, 90, 1.2), (0.30, 0.12, 0.10), 'Decor', mode=2, size=10, linew=0.6, dark=0.6)

    def outside(self):
        b, c = self.box, self.cyl
        b('Pavement', (0, 0, -15), (9000, 9000, 10), (0.56, 0.55, 0.52), 'Outside', mode=2, size=120, linew=1.6, dark=0.7)
        b('Road', (0, 1150, -9.6), (9000, 620, 1), (0.13, 0.13, 0.15), 'Outside')
        for x in range(-3900, 4000, 520):
            b('RoadMark', (x, 1150, -9.0), (240, 14, 1), (0.85, 0.85, 0.80), 'Outside')
        b('Kerb', (0, 835, -6), (9000, 14, 10), (0.70, 0.69, 0.66), 'Outside')
        cols = [(0.76, 0.62, 0.50), (0.55, 0.66, 0.74), (0.82, 0.79, 0.70), (0.70, 0.50, 0.45), (0.62, 0.70, 0.58), (0.80, 0.70, 0.52)]
        x = -3300.0
        i = 0
        while x < 3300:
            w = 620 + (i * 173) % 300
            h = 620 + (i * 311) % 480
            b('Building', (x + w / 2.0, 2500, h / 2.0 - 10), (w, 520, h), cols[i % len(cols)], 'Outside', mode=4, size=165, dark=0.6,
              glow=OUT_GLOW).static_mesh_component.set_cast_shadow(False)
            b('Roof', (x + w / 2.0, 2500, h - 4), (w + 30, 550, 14), (0.30, 0.20, 0.17), 'Outside')
            x += w + 14
            i += 1
        # the cafe's own neighbours on the door side, and behind
        b('Neighbour', (-2200, -900, 290), (700, 2400, 600), cols[2], 'Outside', mode=4, size=165, dark=0.6)
        for x, y, s in ((-640, 560, 1.0), (560, 590, 1.15), (-1500, 600, 0.9), (1700, 570, 1.0)):
            c('TreeTrunk', (x, y, 120 * s), 26 * s, 260 * s, (0.20, 0.12, 0.07), 'Outside')
            self.ball('TreeTop', (x, y, 330 * s), 270 * s, self.LEAF1, 'Outside', sz=230 * s)
            self.ball('TreeTop', (x + 70 * s, y - 30 * s, 390 * s), 180 * s, self.LEAF2, 'Outside')
            self.ball('TreeTop', (x - 80 * s, y + 20 * s, 300 * s), 170 * s, self.LEAF2, 'Outside')
        for x in (-900, 150, 1200):
            c('StreetLampPole', (x, 800, 190), 9, 400, self.BLACK, 'Outside')
            self.ball('StreetLampHead', (x, 800, 400), 34, (0.90, 0.90, 0.85), 'Outside')

    def shafts(self, mat):
        """One sunbeam per window pane: a slab from the glass along the sun's direction down into the floor."""
        pr, yr = math.radians(SUN_PITCH), math.radians(SUN_YAW)
        d = (math.cos(pr) * math.cos(yr), math.cos(pr) * math.sin(yr), math.sin(pr))
        length = 262.0 / -d[2] + 40.0                     # far enough for the top of the pane to reach the floor
        for x0, x1 in ((-400, -180), (-140, 80), (120, 340)):
            xc = (x0 + x1) / 2.0
            for px0, px1 in ((x0 + 6, xc - 2.5), (xc + 2.5, x1 - 6)):
                for z0, z1 in ((91, 231),):                        # sill up to the blind
                    cx, cz = (px0 + px1) / 2.0, (z0 + z1) / 2.0
                    loc = unreal.Vector(cx + d[0] * length / 2.0, 348 + d[1] * length / 2.0, cz + d[2] * length / 2.0)
                    a = self.eas.spawn_actor_from_class(unreal.StaticMeshActor, loc, unreal.Rotator(roll=0.0, pitch=SUN_PITCH, yaw=SUN_YAW))
                    c = a.static_mesh_component
                    c.set_static_mesh(self.mesh['Cube'])
                    c.set_material(0, mat)
                    c.set_cast_shadow(False)
                    c.set_collision_profile_name('NoCollision')      # or the camera boom hits the beam and jams into the character
                    c.set_collision_enabled(unreal.CollisionEnabled.NO_COLLISION)
                    a.set_actor_scale3d(unreal.Vector(length / 100.0, (px1 - px0) * abs(math.sin(yr)) / 100.0, (z1 - z0) * math.cos(pr) / 100.0))
                    self.tag(a, 'Sunbeam', 'Lights')

    def lights(self):
        def spawn(cls, loc=(0, 0, 600), pitch=0.0, yaw=0.0):
            return self.eas.spawn_actor_from_class(cls, unreal.Vector(loc[0], loc[1], loc[2]), unreal.Rotator(roll=0.0, pitch=pitch, yaw=yaw))

        sun = spawn(unreal.DirectionalLight, pitch=SUN_PITCH, yaw=SUN_YAW)   # low late-afternoon sun: long patches across the room
        lc = sun.light_component
        lc.set_mobility(unreal.ComponentMobility.MOVABLE)
        lc.set_intensity(SUN_LUX)
        lc.set_light_color(unreal.LinearColor(1.0, 0.70, 0.42, 1.0))
        lc.set_editor_property('volumetric_scattering_intensity', SHAFTS)
        lc.set_editor_property('atmosphere_sun_light', True)
        self.tag(sun, 'Sun', 'Lights')
        sky = spawn(unreal.SkyLight)
        sc = sky.light_component
        sc.set_mobility(unreal.ComponentMobility.MOVABLE)
        sc.set_editor_property('real_time_capture', True)
        sc.set_intensity(SKY)
        sc.set_light_color(unreal.LinearColor(1.0, 0.86, 0.72, 1.0))
        self.tag(sky, 'SkyLight', 'Lights')
        # thin haze, so the sun draws shafts through the windows and the street outside goes soft
        fog = spawn(unreal.ExponentialHeightFog, loc=(0, 0, 0))
        fc = fog.component
        fc.set_editor_property('fog_density', FOG)
        fc.set_editor_property('fog_height_falloff', 0.02)
        fc.set_editor_property('enable_volumetric_fog', True)
        fc.set_editor_property('volumetric_fog_scattering_distribution', 0.75)
        fc.set_editor_property('volumetric_fog_distance', 4000.0)
        fc.set_editor_property('volumetric_fog_extinction_scale', 2.0)
        self.tag(fog, 'Haze', 'Lights')
        self.tag(spawn(unreal.SkyAtmosphere), 'SkyAtmosphere', 'Lights')
        ppv = spawn(unreal.PostProcessVolume)
        ppv.set_editor_property('unbound', True)
        s = ppv.get_editor_property('settings')

        def ov(k, v):
            s.set_editor_property('override_' + k, True)
            s.set_editor_property(k, v)

        # same fixed exposure as the Frogger level, so the look's light levels mean the same thing here
        ov('auto_exposure_method', unreal.AutoExposureMethod.AEM_MANUAL)
        ov('auto_exposure_bias', EXPOSURE)
        ov('auto_exposure_apply_physical_camera_exposure', False)
        ov('bloom_intensity', BLOOM)          # the soft glow anime compositing puts over bright windows and lamps
        ov('film_grain_intensity', 0.12)
        ov('vignette_intensity', 0.42)
        ov('color_saturation', unreal.Vector4(1.12, 1.12, 1.12, 1.0))
        ov('color_contrast', unreal.Vector4(1.08, 1.08, 1.08, 1.0))
        ov('motion_blur_amount', 0.0)          # drawn frames don't smear
        ov('scene_fringe_intensity', 0.0)
        ov('lens_flare_intensity', 0.0)
        s.set_editor_property('weighted_blendables', unreal.WeightedBlendables(
            array=[unreal.WeightedBlendable(weight=1.0, object=unreal.load_asset(MATS + '/' + LOOK))]))
        ppv.set_editor_property('settings', s)
        self.tag(ppv, 'PostProcess', 'Lights')


    def walker(self, flats):
        """The character you walk around as, placed in the room and possessed at Play, with a closer camera for
        indoors and the pose updated 12 times a second ("on twos") while the camera stays smooth. It is our own
        imported character (BP_CafeWalker) when that exists; until then the template mannequin in matte colours."""
        char = find_character() if eal.does_asset_exist(CHAR_BP) else None
        cls = unreal.load_asset(CHAR_BP if char else WALKER).generated_class()
        pawn = self.eas.spawn_actor_from_class(cls, unreal.Vector(-170, -40, 96), unreal.Rotator(roll=0.0, pitch=0.0, yaw=0.0))
        pawn.set_editor_property('auto_possess_player', unreal.AutoReceiveInput.PLAYER0)
        mesh = pawn.mesh
        if char:
            mi = build_character_material(char.get('tex'))
            half = pawn.capsule_component.get_unscaled_capsule_half_height()
            mesh.set_skeletal_mesh_asset(unreal.load_asset(char['mesh']))
            mesh.set_relative_location(unreal.Vector(0.0, 0.0, -half), False, False)
            for i in range(mesh.get_num_materials()):
                mesh.set_material(i, mi)
            mesh.set_animation_mode(unreal.AnimationMode.ANIMATION_SINGLE_NODE)
            data = unreal.SingleAnimationPlayData()
            data.set_editor_property('anim_to_play', unreal.load_asset(char.get('blend') or char['idle']))
            data.set_editor_property('saved_looping', True)
            data.set_editor_property('saved_playing', True)
            mesh.set_editor_property('animation_data', data)
            log('walker: our character', char['mesh'])
        else:
            for i in range(mesh.get_num_materials()):
                mesh.set_material(i, flats[i % 2])
            log('walker: template mannequin stand-in')
        mesh.set_render_custom_depth(True)
        mesh.set_custom_depth_stencil_value(1)
        mesh.set_component_tick_interval(POSE_STEP)
        pawn.character_movement.set_editor_property('max_walk_speed', WALK_SPEED)
        arm = pawn.get_component_by_class(unreal.SpringArmComponent)
        if arm:
            arm.set_editor_property('target_arm_length', 260.0)
            arm.set_editor_property('socket_offset', unreal.Vector(0.0, 0.0, 45.0))
        cam = pawn.get_component_by_class(unreal.CameraComponent)
        if cam:
            cam.set_editor_property('field_of_view', 70.0)
        self.tag(pawn, 'Walker', 'Lights')


def tune(pairs):
    """Try light levels on the level that is open, without rebuilding it (not saved; put the keepers in the
    constants above). Names: Sun Sky Shafts Fog FogExt Exposure Bloom Lamp."""
    v = dict((p.split('=')[0], float(p.split('=')[1])) for p in pairs)
    for a in unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors():
        if not a.actor_has_tag(TAG):
            continue
        if isinstance(a, unreal.DirectionalLight):
            if 'Sun' in v:
                a.light_component.set_intensity(v['Sun'])
            if 'Shafts' in v:
                a.light_component.set_editor_property('volumetric_scattering_intensity', v['Shafts'])
        elif isinstance(a, unreal.SkyLight) and 'Sky' in v:
            a.light_component.set_intensity(v['Sky'])
        elif isinstance(a, unreal.PointLight) and 'Lamp' in v:
            a.point_light_component.set_intensity(v['Lamp'])
        elif isinstance(a, unreal.ExponentialHeightFog):
            if 'Fog' in v:
                a.component.set_editor_property('fog_density', v['Fog'])
            if 'FogExt' in v:
                a.component.set_editor_property('volumetric_fog_extinction_scale', v['FogExt'])
        elif isinstance(a, unreal.PostProcessVolume):
            st = a.get_editor_property('settings')
            if 'Exposure' in v:
                st.set_editor_property('auto_exposure_bias', v['Exposure'])
            if 'Bloom' in v:
                st.set_editor_property('bloom_intensity', v['Bloom'])
            a.set_editor_property('settings', st)
    log('tuned', v)


def build():
    dirty = list(unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()) + list(unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages())
    dirty = [d for d in dirty if str(d.get_name()) != MAP]      # the cafe itself may be half-built from a failed run
    if dirty:
        log('STOPPED: unsaved packages (opening another level would pop a Save window):', [str(p.get_name()) for p in dirty])
        return
    surface = build_surface()
    build_look()
    flats = build_flat()
    shaft = build_shaft()
    les = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
    ues = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    if ues.get_editor_world().get_path_name().split('.')[0] != MAP:
        ok = les.load_level(MAP) if eal.does_asset_exist(MAP) else les.new_level(MAP)
        if not ok or ues.get_editor_world().get_path_name().split('.')[0] != MAP:
            log('STOPPED: could not open', MAP, 'world is', ues.get_editor_world().get_path_name())
            return
    cafe = Cafe(surface)
    old = [a for a in cafe.eas.get_all_level_actors() if a.actor_has_tag(TAG)]
    for a in old:
        cafe.eas.destroy_actor(a)
    cafe.room()
    cafe.counter()
    cafe.seating()
    cafe.decor()
    cafe.outside()
    cafe.lights()
    cafe.shafts(shaft)
    cafe.walker(flats)
    world = ues.get_editor_world()
    world.get_world_settings().set_editor_property('default_game_mode', unreal.load_asset(GAMEMODE).generated_class())
    les.save_current_level()
    log('removed', len(old), 'placed', cafe.n, 'in', world.get_path_name())


try:
    mode = sys.argv[1] if len(sys.argv) > 1 else 'build'
    if mode == 'build':
        build()
    elif mode == 'light':
        tune(sys.argv[2:])
    elif mode == 'look':
        build_look(sys.argv[2:] or None)      # no values given: back to the defaults above
    log('DONE', mode)
except Exception:
    log('ERROR', traceback.format_exc())
with open(os.path.join(unreal.Paths.project_saved_dir(), 'anime_cafe_result.txt'), 'w') as fh:
    fh.write('\n'.join(out) + '\n')
unreal.log('ANIME_CAFE ' + ' | '.join(out)[:900])
