# Contact sheet: one row per model (5 textured views, clay, wireframe close-up) with its stats underneath.
#   python tools/bakeoff_sheet.py <renders_dir> <out.jpg> <label> [<label> ...]
# <renders_dir> is the output folder of Art/Blender/bakeoff_render.py; needs Pillow (any of our venvs).
import sys, json, os
from PIL import Image, ImageDraw, ImageFont
R, out, labels = sys.argv[1], sys.argv[2], sys.argv[3:]
T = 256; views = ['v0', 'v1', 'v2', 'v3', 'v4', 'clay', 'wire']
font = ImageFont.truetype('arial.ttf', 15)
sheet = Image.new('RGB', (T * len(views), (T + 44) * len(labels)), (24, 24, 28))
d = ImageDraw.Draw(sheet)
for r, lab in enumerate(labels):
    y = r * (T + 44)
    for c, v in enumerate(views):
        p = os.path.join(R, f'{lab}_{v}.png')
        if os.path.exists(p):
            sheet.paste(Image.open(p).convert('RGB').resize((T, T), Image.LANCZOS), (c * T, y))
    s = json.load(open(os.path.join(R, lab + '.json')))
    d.text((8, y + T + 4), f"{lab}:  {s['triangles']:,} triangles   textures {', '.join(s['textures']) or 'none'}   "
           f"{s['materials']} material(s)   {s['uv_islands']:,} UV islands   {s['loose_parts']} loose pieces   "
           f"{s['open_edges']} open edges", fill=(235, 235, 235), font=font)
sheet.save(out); print('wrote', out)
