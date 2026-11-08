# Optional, between build and bake: glass panes over side-window openings (photo taken with the windows down).
# Between build and bake for the front-3/4 (cc8) body: close the side-window openings with glass panes,
# record the rear deck height, and transplant the wing from the rear-3/4 (TR_CC7) model.
import bpy, bmesh, numpy as np, math
import os
REPO = globals().get('REPO', (os.environ.get('MEGAJAM_REPO') or os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(globals().get('__file__', os.path.join(os.getcwd(), 'Art', 'Blender', '_')))), '..', '..'))))   # repo = two folders up from this script; pass REPO=... or set MEGAJAM_REPO to override
D = REPO + r"\Art\Blender"; SP = D + r"\cache"                                   # cache: baked maps, lamp points (gitignored)
import os; os.makedirs(SP, exist_ok=True)
from mathutils import Vector
from mathutils.bvhtree import BVHTree
ob = bpy.data.objects['TR_BRZ']; me = ob.data; ob.location = (0, 0, 0)
fin = {}
bm = bmesh.new(); bm.from_mesh(me); bvh = BVHTree.FromBMesh(bm)

# 1. rear deck height table (before the wing goes on): top surface z per 1 cm cell
xs_ = np.arange(-0.44, 0.44 + 1e-6, 0.01); ys_ = np.arange(0.50, 0.87 + 1e-6, 0.01)
top = np.full((len(ys_), len(xs_)), np.nan)
for j, yy in enumerate(ys_):
    for i, xx in enumerate(xs_):
        h = bvh.ray_cast(Vector((xx, yy, 0.6)), Vector((0, 0, -1)), 1.0)
        if h[0] is not None: top[j, i] = h[0].z
np.save(SP + r"\deck_top.npy", top); np.save(SP + r"\deck_axes.npy", np.array([xs_[0], ys_[0], 0.01]))

# 2. side windows: rays from outside; cells that reach the cabin are openings
Y0, Y1, Z0, Z1, st = -0.24, 0.37, 0.08, 0.24, 0.01
gy = np.arange(Y0, Y1 + 1e-6, st); gz = np.arange(Z0, Z1 + 1e-6, st)
added = 0
for s in (-1, 1):
    hit = np.full((len(gz), len(gy)), np.nan)
    for j, zz in enumerate(gz):
        for i, yy in enumerate(gy):
            h = bvh.ray_cast(Vector((s * 1.0, yy, zz)), Vector((-s, 0, 0)), 2.0)
            if h[0] is not None: hit[j, i] = s * h[0].x            # signed: the far side of the cabin counts as an opening
    opening = ~np.isnan(hit) & (hit < 0.22)
    frame = ~np.isnan(hit) & (hit > 0.24)
    if opening.sum() < 20: continue
    # quadratic fit of the frame around the opening, x = f(y, z)
    k = np.pad(opening, 2); near = np.zeros_like(opening)
    for dj in range(-2, 3):
        for di in range(-2, 3): near |= k[2 + dj:2 + dj + len(gz), 2 + di:2 + di + len(gy)]
    ring = frame & near
    J, I = np.nonzero(ring); yy = gy[I]; zz = gz[J]; xx = hit[J, I]
    B = np.stack([np.ones_like(yy), yy, zz, yy * yy, zz * zz, yy * zz], -1); c, *_ = np.linalg.lstsq(B, xx, rcond=None)
    fit = lambda y_, z_: c[0] + c[1] * y_ + c[2] * z_ + c[3] * y_ * y_ + c[4] * z_ * z_ + c[5] * y_ * z_
    cells = opening | ring
    V = {}
    for j in range(len(gz)):
        for i in range(len(gy)):
            if cells[j, i]:
                x = (fit(gy[i], gz[j]) - 0.004) if opening[j, i] else (hit[j, i] - 0.003)
                V[(j, i)] = bm.verts.new((s * x, gy[i], gz[j]))
    for j in range(len(gz) - 1):
        for i in range(len(gy) - 1):
            q = [(j, i), (j, i + 1), (j + 1, i + 1), (j + 1, i)]
            if all(p in V for p in q):
                f = bm.faces.new([V[p] for p in (q if s > 0 else q[::-1])]); f.material_index = 0; added += 1
                if f.normal.x * s < 0: f.normal_flip()
    fin['opening_%d' % s] = int(opening.sum())
fin['window_faces'] = added

bm.to_mesh(me); bm.free(); me.update()
for p in me.polygons: p.use_smooth = True
result_finish = fin
