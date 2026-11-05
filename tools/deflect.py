# Flatten reflections in car paint: keep the broad shading, remove the tree/sky shapes mirrored in the paint.
import sys, numpy as np
from PIL import Image, ImageFilter
src, dst, look, keep = sys.argv[1], sys.argv[2], sys.argv[3], float(sys.argv[4]) if len(sys.argv) > 4 else 0.25
im = Image.open(src).convert('RGBA'); a = np.array(im).astype(np.float32); H, W = a.shape[:2]
rgb = a[..., :3] / 255; al = a[..., 3] / 255
mx = rgb.max(-1); mn = rgb.min(-1); d = mx - mn + 1e-6
hue = np.where(mx == rgb[..., 2], (4 + (rgb[..., 0] - rgb[..., 1]) / d) / 6, np.where(mx == rgb[..., 1], (2 + (rgb[..., 2] - rgb[..., 0]) / d) / 6, ((rgb[..., 1] - rgb[..., 2]) / d) / 6 % 1))
sat = d / (mx + 1e-6)
paint = (al > 0.5) & (hue > 0.55) & (hue < 0.75) & (sat > 0.35) & (mx > 0.12)
def blur(x, s):
    return np.array(Image.fromarray((x * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(s))).astype(np.float32) / 255
# pale highlight streaks inside the paint: bright, low-saturation, not red, surrounded by paint
near = blur(paint.astype(np.float32), W * 0.012) > 0.55
red = (hue < 0.08) | (hue > 0.92)
paint = paint | (near & (al > 0.5) & (mx > 0.45) & (sat < 0.35) & ~red)
def blur(x, s):
    return np.array(Image.fromarray((x * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(s))).astype(np.float32) / 255
s = W * 0.03
m = paint.astype(np.float32)
sm = []
for c in range(3):
    num = blur(rgb[..., c] * m, s); den = blur(m, s) + 1e-4; sm.append(num / den)
sm = np.stack(sm, -1)
flat = sm + keep * (rgb - sm)                  # mostly the smooth colour, a little of the real shading
out = rgb.copy(); pm = paint[..., None]
out = np.where(pm, flat, out)
a[..., :3] = np.clip(out, 0, 1) * 255
res = Image.fromarray(a.astype(np.uint8)); res.save(dst)
lk = Image.new('RGB', res.size, (255, 0, 255)); lk.paste(res, mask=res.split()[3]); lk.thumbnail((1200, 1200)); lk.save(look, quality=85)
print('paint pixels', int(paint.sum()), 'of', int((al > 0.5).sum()))
