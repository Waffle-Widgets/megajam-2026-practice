"""Builds a hand-drawn anime look as one post-process material: ink lines, flat two-tone shading with tinted
shadows, hard highlights and a little line wobble ("boil"). It sits on top of the finished picture, so no mesh or
material in the game changes, and it switches off by removing it from the post-process volume.

Run it in the Unreal editor's console box (Cmd), with Play mode stopped:
    py <repo>/tools/unreal_make_anime_look.py build            make or rebuild M_AnimeLook and MI_AnimeLook
    py <repo>/tools/unreal_make_anime_look.py apply on|off     add it to / remove it from every post-process volume
    py <repo>/tools/unreal_make_anime_look.py set Name=1.5 ... change MI_AnimeLook numbers (no shader recompile)
    py <repo>/tools/unreal_make_anime_look.py tint Name=r,g,b  change an MI_AnimeLook colour
Results and errors go to Saved/anime_look_result.txt. Nothing in the level is saved by this script.

How it works (all in one Custom node, see CODE):
- Light = picture brightness / surface colour, smoothed over a few pixels. Above ShadowT a pixel is "lit", below it is
  "shadow": two flat levels with a hard edge, the shadow tinted (ShadowTint). Above HiT it gets a hard highlight.
- Very bright pixels (lamps, glows) and unlit ones (sky, effects) are left as they are.
- Lines: where the depth bends sharply (1/depth is flat across any flat surface, so the ground at a low angle gives
  no false lines) or where neighbouring normals disagree (creases; faded out past LineFar).
- It runs before depth of field, so Unreal's anti-aliasing smooths the lines, and bloom, grain and vignette land on
  top of the drawing like a film print.
- Two kinds of drawing, as in a real anime: characters are cel-shaded, backgrounds are painted. Anything that renders
  into custom depth (a character's mesh: Render CustomDepth Pass on) gets two flat tones split by a key light we
  choose (KeyDir) and a rim light. Everything else is either cel-shaded too (BgCel 1, the outdoor Frogger look) or
  "painted" (BgCel 0): the real smooth light is kept and a brush filter runs over it, with thinner, softer lines.
- Scene colour is read without pre-exposure (as Unreal's own SceneTexture node does), so the numbers are real light
  levels: with our 7-lux sun, a sunlit surface is about 2.5 x its colour.
"""
import os
import sys
import traceback
import unreal

FOLDER = '/Game/Game/Materials'
M_NAME, MI_NAME = 'M_AnimeLook', 'MI_AnimeLook'
mel = unreal.MaterialEditingLibrary
eal = unreal.EditorAssetLibrary
out = []


def log(*a):
    out.append(' '.join(str(x) for x in a))


# name -> default. Order is the Custom node's input order.
SCALARS = [
    ('LineWidth', 2.0),      # line half-width in pixels on a 1080p picture (scales with resolution)
    ('DepthEdge', 0.04),     # how sharp a depth bend must be to draw a line (smaller = more lines)
    ('NormalEdge', 1.1),     # how different neighbouring normals must be (smaller = more crease lines)
    ('LineFar', 3000.0),     # crease lines fade out by this distance (cm)
    ('LineFarDepth', 2600.0),  # outline lines fade out by this distance (cm), so far trees aren't scribbled over
    ('InkOpacity', 0.92),
    ('InkFromColor', 0.12),  # 0 = pure ink colour, 1 = a dark version of the surface colour
    ('Boil', 0.45),          # line wobble in pixels
    ('BoilFps', 8.0),        # how often the wobble changes ("drawn on threes")
    ('Smooth', 5.0),         # blur radius (pixels at 1080p) for light and colour, so shapes are round, not speckled
    ('Poster', 6.0),         # number of brightness steps a colour fill is rounded to (0 = off)
    ('TexFlatten', 0.85),    # 0 = keep texture detail, 1 = flat colour fills
    ('ShadowT', 0.8),        # light level where shadow turns into lit
    ('LitLevel', 1.95),       # brightness of a lit fill
    ('ShadowLevel', 0.42),   # brightness of a shadow fill, as a share of lit
    ('DeepT', 0.0),          # below this light level a shadow goes one step darker (under furniture); 0 = off
    ('DeepLevel', 0.62),     # how dark that deepest tone is, as a share of shadow
    ('HiT', 7.0),            # light level where the hard highlight starts
    ('HiBoost', 0.9),
    ('HiWhite', 0.5),        # how white the highlight is: 1 = pure white, 0 = a brighter version of the surface colour
    ('GlowT', 12.0),         # above this the picture is left alone (lamps, glows)
    ('LightHue', 0.6),       # how much of the real light's colour (sunset orange, night blue) is kept
    ('Flatten', 1.0),        # 0 = original picture, 1 = full anime shading
    ('Debug', 0.0),          # 1 = bands (dark red deepest, red shadow, green lit, blue highlight, white untouched), 2 = lines only, 3 = character tones
    # --- characters (anything with Render CustomDepth Pass on) get their own cel shading; see "Two kinds of drawing"
    ('CharOn', 1.0),
    ('CharSmooth', 2.5),     # how much wider the smoothing is on a character (rounder shadow shapes on a lumpy mesh)
    ('CharShadowT', 0.05),   # where the shadow edge sits: -1 = all lit, 1 = all shadow, 0 = half and half
    ('CharSoft', 0.02),      # softness of the shadow edge
    ('CharShadowLevel', 0.5),
    ('CharLevel', 1.0),      # brightness of the character's lit colour
    ('CharEnv', 0.5),        # how much the room's real light brightens or darkens the character
    ('CharEnvRef', 0.6),     # the light level that counts as "normal" for that
    ('RimWidth', 5.0),       # rim light width in pixels at 1080p
    ('RimStrength', 0.8),
    # --- backgrounds: 1 = cel-shaded like the characters (the Frogger look), 0 = painted (smooth light, brush filter)
    ('BgCel', 1.0),
    ('Paint', 3.0),          # brush size in pixels at 1080p for the painted background (0 = off)
    ('BgSat', 1.0),          # colour strength of the painted background
    ('BgShadowHi', 0.2),     # below this brightness the painted background takes on BgShadowTint
    ('BgInkOpacity', 0.6),   # painted backgrounds get thinner, softer lines in a darker version of their own colour
    ('BgInkDark', 0.3),
    ('BgLineScale', 0.7),
]
VECTORS = [
    ('InkColor', (0.012, 0.010, 0.022)),
    ('ShadowTint', (0.60, 0.64, 1.0)),
    ('KeyDir', (0.35, 0.86, 0.38)),          # direction towards the characters' key light (world)
    ('CharShadowTint', (0.62, 0.55, 0.78)),
    ('RimColor', (1.0, 0.9, 0.7)),
    ('BgShadowTint', (0.8, 0.78, 1.0)),
]

CODE = r'''
struct FAnimeLook
{
    float3 S(float2 UV, int Id) { return SceneTextureLookup(UV, Id, false).rgb; }
    float Lum(float3 C) { return dot(C, float3(0.2126, 0.7152, 0.0722)); }
    // 1 where a character (anything drawn into custom depth) is the surface you see
    float Ch(float2 UV, float SceneD)
    {
        float cd = SceneTextureLookup(UV, 13, false).r;
        return (cd < 200000.0 && cd <= SceneD + 3.0) ? 1.0 : 0.0;
    }
};
FAnimeLook A;
// scene texture ids: 14 = PostProcessInput0 (the picture), 1 = SceneDepth, 8 = WorldNormal, 5 = BaseColor, 13 = CustomDepth
float2 uv  = GetDefaultSceneTextureUV(Parameters, 14);
float2 uvg = GetDefaultSceneTextureUV(Parameters, 1);
float2 px  = View.BufferSizeAndInvSize.zw;
float  ope = View.OneOverPreExposure;
float  res = View.ViewSizeAndInvSize.y / 1080.0;

float3 scene = A.S(uv, 14) * ope;
float  d0    = A.S(uvg, 1).r;
float3 base  = A.S(uvg, 5);
float  ch0   = A.Ch(uvg, d0) * CharOn;

// --- light, colour and normal, smoothed over two rings of 8 neighbours on the same surface ---
static const float2 K[8] = { float2(1, 0), float2(-1, 0), float2(0, 1), float2(0, -1),
                             float2(0.7071, 0.7071), float2(-0.7071, 0.7071), float2(0.7071, -0.7071), float2(-0.7071, -0.7071) };
float3 bs = base;
float3 ss = scene;
float3 ns = A.S(uvg, 8);
float ws = 1.0;
float sm = Smooth * lerp(1.0, CharSmooth, ch0);
for (int i = 0; i < 16; i++)
{
    float2 k = K[i % 8];
    if (i >= 8) { k = float2(k.x * 0.9239 - k.y * 0.3827, k.x * 0.3827 + k.y * 0.9239) * 0.5; }
    float2 o = k * px * sm * res;
    float di = A.S(uvg + o, 1).r;
    float w = abs(di - d0) < 0.04 * d0 ? 1.0 : 0.0;
    bs += A.S(uvg + o, 5) * w;
    ss += A.S(uv + o, 14) * ope * w;
    ns += A.S(uvg + o, 8) * w;
    ws += w;
}
bs /= ws;
ss /= ws;

float L = A.Lum(ss) / max(A.Lum(bs), 0.015);
float band = smoothstep(ShadowT * 0.94, ShadowT * 1.06, L);
float hi = smoothstep(HiT * 0.95, HiT * 1.05, L);
float3 lr = (ss + 0.03) / (bs + 0.03);
float3 hue = lr / max(A.Lum(lr), 0.001);
hue = lerp(float3(1, 1, 1), clamp(hue, 0.4, 1.8), LightHue);
float3 fill = lerp(base, bs, TexFlatten);
float fl = max(A.Lum(fill), 0.0001);
float q = floor(sqrt(fl) * max(Poster, 1.0) + 0.5) / max(Poster, 1.0);
fill = lerp(fill, fill * (q * q / fl), step(0.5, Poster));
float3 level = lerp(ShadowTint * ShadowLevel, float3(1, 1, 1), band) * LitLevel;
float deep = (1.0 - smoothstep(DeepT * 0.9, DeepT * 1.1, L)) * step(0.0001, DeepT);
level *= lerp(1.0, DeepLevel, deep);
float3 cel = fill * hue * level + hi * HiBoost * LitLevel * lerp(fill, float3(1, 1, 1), HiWhite);

float unlit = step(A.Lum(base), 0.004);
float glow = smoothstep(GlowT, GlowT * 2.0, L);
float sky = step(400000.0, d0);                    // nothing nearer than 4 km: the sky
float keep = saturate(unlit + glow + sky);
float3 bgCel = lerp(lerp(scene, cel, Flatten), scene, keep);

// --- painted background: keep the real, smooth light, and run a brush filter over it (Kuwahara: of the four
//     quarters around a pixel, take the average of the calmest one; edges stay sharp, noise turns into dabs) ---
float3 kw = scene;
if (Paint > 0.01 && BgCel < 0.99)
{
    float bestV = 1e9;
    for (int qd = 0; qd < 4; qd++)
    {
        float2 sg = float2((qd & 1) ? 1.0 : -1.0, (qd & 2) ? 1.0 : -1.0);
        float3 m = scene;
        float l0 = A.Lum(scene);
        float m2 = l0 * l0;
        for (int j = 0; j < 4; j++)
        {
            float2 of = sg * float2((j & 1) ? 0.9 : 0.4, (j & 2) ? 0.9 : 0.4) * Paint * res * px;
            float3 c = A.S(uv + of, 14) * ope;
            float lc = A.Lum(c);
            m += c;
            m2 += lc * lc;
        }
        m /= 5.0;
        float lm = A.Lum(m);
        float var = (m2 / 5.0 - lm * lm) / max(lm * lm, 0.0001);
        if (var < bestV) { bestV = var; kw = m; }
    }
}
float kl = A.Lum(kw);
float3 bgPaint = lerp(float3(kl, kl, kl), kw, BgSat);
bgPaint *= lerp(BgShadowTint, float3(1, 1, 1), smoothstep(0.0, max(BgShadowHi, 0.0001), kl));
bgPaint = lerp(bgPaint, scene, saturate(glow + sky));
float3 col = lerp(bgPaint, bgCel, BgCel);

// --- characters: two flat tones split by a key light we choose (KeyDir), plus a rim light on the side facing it ---
float3 kd = normalize(KeyDir);
float ndk = dot(normalize(ns), kd);
float cb = smoothstep(CharShadowT - CharSoft, CharShadowT + CharSoft, ndk);
float eg = lerp(1.0, clamp(L / max(CharEnvRef, 0.001), 0.6, 1.6), CharEnv);
float3 ccol = base * hue * lerp(CharShadowTint * CharShadowLevel, float3(1, 1, 1), cb) * CharLevel * eg;
float3 kv = mul(float4(kd, 0.0), View.TranslatedWorldToView).xyz;
float2 rd = float2(kv.x, -kv.y) + float2(0.0, -0.25);
rd /= max(length(rd), 0.001);
float2 ur = uvg + rd * px * RimWidth * res;
float rim = 1.0 - A.Ch(ur, A.S(ur, 1).r + 60.0);
ccol += RimColor * RimStrength * rim * CharLevel * eg;
col = lerp(col, ccol, ch0);

// --- ink lines ---
float tick = floor(T * BoilFps);
float2 wob = float2(sin(uvg.y * 173.0 + tick * 1.7) + sin(uvg.y * 61.0 - tick * 2.9),
                    cos(uvg.x * 191.0 + tick * 2.3) + cos(uvg.x * 67.0 + tick * 1.3)) * 0.5 * Boil * px;
float2 ul = uvg + wob;
float paintOn = 1.0 - BgCel;
float2 lo = px * LineWidth * res * lerp(lerp(1.0, BgLineScale, paintOn), 1.0, ch0);
float dc  = A.S(ul, 1).r;
float dA = A.S(ul + float2(-lo.x, -lo.y), 1).r;
float dB = A.S(ul + float2( lo.x,  lo.y), 1).r;
float dC = A.S(ul + float2(-lo.x,  lo.y), 1).r;
float dD = A.S(ul + float2( lo.x, -lo.y), 1).r;
float iz0 = 1.0 / clamp(dc, 1.0, 1e7);
float izA = 1.0 / clamp(dA, 1.0, 1e7);
float izB = 1.0 / clamp(dB, 1.0, 1e7);
float izC = 1.0 / clamp(dC, 1.0, 1e7);
float izD = 1.0 / clamp(dD, 1.0, 1e7);
float dE = (abs(izA + izB - 2.0 * iz0) + abs(izC + izD - 2.0 * iz0)) / iz0;
float3 nA = A.S(ul + float2(-lo.x, -lo.y), 8);
float3 nB = A.S(ul + float2( lo.x,  lo.y), 8);
float3 nC = A.S(ul + float2(-lo.x,  lo.y), 8);
float3 nD = A.S(ul + float2( lo.x, -lo.y), 8);
float nE = (1.0 - dot(nA, nB)) + (1.0 - dot(nC, nD));
float nearF = saturate(1.0 - dc / LineFar);
float nearD = saturate(2.0 - 2.0 * dc / LineFarDepth);
float ln = saturate(max(smoothstep(DepthEdge, DepthEdge * 2.0, dE) * nearD, smoothstep(NormalEdge, NormalEdge * 1.6, nE) * nearF));
// a line that touches a character is a character line: full strength, ink colour
float chl = saturate(ch0 + A.Ch(ul + float2(-lo.x, -lo.y), dA) + A.Ch(ul + float2(lo.x, lo.y), dB)
                         + A.Ch(ul + float2(-lo.x, lo.y), dC) + A.Ch(ul + float2(lo.x, -lo.y), dD)) * CharOn;
float3 inkCel = lerp(InkColor, fill * 0.18, InkFromColor) * LitLevel;
float3 inkBg = lerp(inkCel, kw * BgInkDark, paintOn);
float3 ink = lerp(inkBg, InkColor * CharLevel * eg, chl);
float op = lerp(lerp(InkOpacity, BgInkOpacity, paintOn), InkOpacity, chl);
col = lerp(col, ink, ln * op);

if (Debug > 2.5) { return lerp(float3(0.1, 0.1, 0.1), lerp(float3(0.3, 0.3, 1), float3(1, 1, 0.3), cb) + rim, ch0) * LitLevel; }
if (Debug > 1.5) { return lerp(float3(1, 1, 1), float3(0, 0, 0), ln) * LitLevel; }
if (Debug > 0.5) { return lerp(lerp(lerp(lerp(float3(1, 0, 0), float3(0.25, 0, 0), deep), float3(0, 1, 0), band), float3(0, 0, 1), hi), float3(1, 1, 1), keep) * LitLevel; }
return col;
'''


def load(name):
    path = FOLDER + '/' + name
    return unreal.load_asset(path) if eal.does_asset_exist(path) else None


def build():
    tools = unreal.AssetToolsHelpers.get_asset_tools()
    m = load(M_NAME)
    if m is None:
        m = tools.create_asset(M_NAME, FOLDER, unreal.Material, unreal.MaterialFactoryNew())
        log('created', M_NAME)
    else:
        # Rebuild in place: volumes and the instance keep pointing at it. One call leaves about half the nodes
        # behind (it skips entries while it deletes), so repeat until the graph is empty.
        for _ in range(12):
            if mel.get_num_material_expressions(m) == 0:
                break
            mel.delete_all_material_expressions(m)
        log('rebuilding', M_NAME)
    m.set_editor_property('material_domain', unreal.MaterialDomain.MD_POST_PROCESS)
    m.set_editor_property('blendable_location', unreal.BlendableLocation.BL_SCENE_COLOR_BEFORE_DOF)

    def node(cls, x, y):
        return mel.create_material_expression(m, cls, x, y)

    custom = node(unreal.MaterialExpressionCustom, -400, 0)
    custom.set_editor_property('code', CODE)
    custom.set_editor_property('output_type', unreal.CustomMaterialOutputType.CMOT_FLOAT3)
    custom.set_editor_property('description', 'AnimeLook')
    names = ['PP0', 'BaseC', 'Nrm', 'Dep', 'CDep', 'T'] + [n for n, _ in SCALARS] + [n for n, _ in VECTORS]
    ins = []
    for n in names:
        ci = unreal.CustomInput()
        ci.set_editor_property('input_name', n)
        ins.append(ci)
    custom.set_editor_property('inputs', ins)

    # The five scene textures are plugged in (unused by name in the code) so the compiler knows the material reads them.
    y = -700
    for pin, tid in [('PP0', unreal.SceneTextureId.PPI_POST_PROCESS_INPUT0), ('BaseC', unreal.SceneTextureId.PPI_BASE_COLOR),
                     ('Nrm', unreal.SceneTextureId.PPI_WORLD_NORMAL), ('Dep', unreal.SceneTextureId.PPI_SCENE_DEPTH),
                     ('CDep', unreal.SceneTextureId.PPI_CUSTOM_DEPTH)]:
        st = node(unreal.MaterialExpressionSceneTexture, -900, y)
        st.set_editor_property('scene_texture_id', tid)
        mel.connect_material_expressions(st, 'Color', custom, pin)
        y += 220
    t = node(unreal.MaterialExpressionTime, -900, y)
    mel.connect_material_expressions(t, '', custom, 'T')
    y += 120
    for n, v in SCALARS:
        s = node(unreal.MaterialExpressionScalarParameter, -900, y)
        s.set_editor_property('parameter_name', n)
        s.set_editor_property('default_value', v)
        mel.connect_material_expressions(s, '', custom, n)
        y += 90
    for n, v in VECTORS:
        s = node(unreal.MaterialExpressionVectorParameter, -900, y)
        s.set_editor_property('parameter_name', n)
        s.set_editor_property('default_value', unreal.LinearColor(v[0], v[1], v[2], 1.0))
        mel.connect_material_expressions(s, '', custom, n)
        y += 200
    mel.connect_material_property(custom, '', unreal.MaterialProperty.MP_EMISSIVE_COLOR)
    mel.recompile_material(m)
    eal.save_loaded_asset(m)
    log('expressions', mel.get_num_material_expressions(m))

    mi = load(MI_NAME)
    if mi is None:
        mi = tools.create_asset(MI_NAME, FOLDER, unreal.MaterialInstanceConstant, unreal.MaterialInstanceConstantFactoryNew())
        mel.set_material_instance_parent(mi, m)
        log('created', MI_NAME)
    mel.update_material_instance(mi)
    eal.save_loaded_asset(mi)


def apply(on):
    mi = load(MI_NAME)
    for a in unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors():
        if not isinstance(a, unreal.PostProcessVolume):
            continue
        s = a.get_editor_property('settings')
        arr = [b for b in s.get_editor_property('weighted_blendables').get_editor_property('array')
               if b.get_editor_property('object') != mi]
        if on:
            arr.append(unreal.WeightedBlendable(weight=1.0, object=mi))
        s.set_editor_property('weighted_blendables', unreal.WeightedBlendables(array=arr))
        a.set_editor_property('settings', s)
        log('volume', a.get_name(), 'anime look', 'ON' if on else 'off', 'blendables', len(arr))


def set_values(pairs, colour):
    mi = load(MI_NAME)
    for p in pairs:
        n, v = p.split('=')
        if colour:
            r, g, b = [float(x) for x in v.split(',')]
            mel.set_material_instance_vector_parameter_value(mi, n, unreal.LinearColor(r, g, b, 1.0))
        else:
            mel.set_material_instance_scalar_parameter_value(mi, n, float(v))
        log('set', n, v)
    mel.update_material_instance(mi)
    eal.save_loaded_asset(mi)


try:
    mode = sys.argv[1] if len(sys.argv) > 1 else 'build'
    if mode == 'build':
        build()
    elif mode == 'apply':
        apply(sys.argv[2] == 'on')
    elif mode == 'set':
        set_values(sys.argv[2:], False)
    elif mode == 'tint':
        set_values(sys.argv[2:], True)
    log('OK', mode)
except Exception:
    log('ERROR', traceback.format_exc())
with open(os.path.join(unreal.Paths.project_saved_dir(), 'anime_look_result.txt'), 'w') as fh:
    fh.write('\n'.join(out) + '\n')
unreal.log('ANIME_LOOK ' + ' | '.join(out)[:900])
