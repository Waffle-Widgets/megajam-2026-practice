"""Colour pass for the AI BRZ (run inside Blender after ai_car_fix.py is loaded into `fx`).
Glass, tyres, rims and arch liners come from the car's shape; lights, grille and diffuser keep the AI texture;
everything else uses the clear-coat WR Blue paint slot."""
import bpy, numpy as np, bmesh


def paint_pass(fx, ob, orig_name='brz_r34clean_textured.jpg'):
    me = ob.data; n = len(me.polygons)
    lab = fx['classify_parts'](ob)
    lab = fx['front_parts'](ob, lab)
    bm = bmesh.new(); bm.from_mesh(me); bm.faces.ensure_lookup_table()
    nb = [[f2.index for e in f.edges for f2 in e.link_faces if f2.index != f.index] for f in bm.faces]; bm.free()
    cen = np.empty(n * 3); me.polygons.foreach_get('center', cen); x, y, z = cen.reshape(-1, 3).T
    img = bpy.data.images['T_AIBRZ_BaseColor']; W, H = img.size; px = np.array(img.pixels[:]).reshape(H, W, 4)
    orig = bpy.data.images[orig_name]; oW, oH = orig.size; op = np.array(orig.pixels[:]).reshape(oH, oW, 4)[..., :3]
    uv = np.empty(len(me.loops) * 2); me.uv_layers.active.data.foreach_get('uv', uv); uv = uv.reshape(-1, 2)
    ls = np.empty(n, int); me.polygons.foreach_get('loop_start', ls); lt = np.empty(n, int); me.polygons.foreach_get('loop_total', lt)
    fu = np.add.reduceat(uv[:, 0], ls) / lt; fv = np.add.reduceat(uv[:, 1], ls) / lt
    ix = np.clip((fu * oW).astype(int), 2, oW - 3); iy = np.clip((fv * oH).astype(int), 2, oH - 3)
    col = sum(op[iy + dy, ix + dx] for dx in range(-2, 3) for dy in range(-2, 3)) / 25
    r, g, b = col.T; lum = col.mean(1); ax = np.abs(x)
    head = (y < -0.66) & (z > -0.06) & (z < 0.06) & (ax > 0.20) & ((lum > 0.35) | ((b < r * 1.2) & (lum > 0.05)))
    tail = (y > 0.66) & (z > -0.05) & (z < 0.10) & (ax > 0.17) & ((r > b * 1.3) | (lum < 0.06))
    grille = (y < -0.76) & (z < -0.08) & (ax < 0.34) & (lum < 0.12)
    diff = (y > 0.74) & (z < -0.13) & (lum < 0.15)
    detail = tail | diff                                      # front details now come from front_parts
    zone = y > 0.66
    house = (z > 0.03) & (ax < 0.37) & (y > -0.40) & (y < 0.66)           # greenhouse: smooth the glass edge the same way
    for _ in range(3):
        gl = (lab == 'glass').astype(float)
        vote = np.array([gl[k].mean() if k else gl[i] for i, k in enumerate(nb)])
        lab[house & (lab == '') & (vote > 0.5)] = 'glass'
        lab[(lab == 'glass') & (vote < 0.34)] = ''
    for name in ('grille', 'fog', 'head', 'head_chrome', 'head_rim', 'cowl'):   # same smoothing for the front parts
        for _ in range(3):
            m = (lab == name).astype(float)
            vote = np.array([m[k].mean() if k else m[i] for i, k in enumerate(nb)])
            lab[(y < -0.3) & (lab == '') & (vote > 0.5)] = name
            lab[(lab == name) & (vote < 0.34)] = ''
    for _ in range(4):                                   # majority vote over neighbours smooths ragged edges
        d = detail.astype(float); detail = np.array([d[k].mean() > 0.5 if k else d[i] > 0.5 for i, k in enumerate(nb)]) & zone
    mats = np.empty(n, int); me.polygons.foreach_get('material_index', mats)
    P = [m.name for m in me.materials].index('MC_PaintWR')
    free = (lab == '') & (mats != 1)
    mats[free] = P; mats[free & detail] = 0; mats[lab != ''] = 0
    me.polygons.foreach_set('material_index', mats); me.update()
    restore = fx['raster_faces'](me, [me.polygons[i] for i in np.nonzero((free & detail) | (lab == 'rim') | (lab == 'tyre'))[0]], W, H)
    px[restore, :3] = op[restore]
    ri = bpy.data.images['T_AIBRZ_Roughness']; rp = np.array(ri.pixels[:]).reshape(H, W, 4); rough = rp[..., 0].copy()
    st = fx['paint_parts'](ob, lab, px, rough)
    st.update(fx['paint_front'](ob, lab, px, rough))
    rp[..., 0] = rough; rp[..., 1] = rough; rp[..., 2] = rough
    img.pixels[:] = px.ravel(); img.save(); ri.pixels[:] = rp.ravel(); ri.save()
    return st
