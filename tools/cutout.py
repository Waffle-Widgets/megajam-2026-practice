"""Cut a car out of a photo with rembg (run with the TRELLIS venv python).
python tools/cutout.py <photo.jpg> <out.png> [x0 y0 x1 y1 of boxes to paint body colour first, e.g. a number plate]"""
import sys
from rembg import remove, new_session
from PIL import Image, ImageDraw
im = Image.open(sys.argv[1]).convert('RGB')
boxes = [int(v) for v in sys.argv[3:]]
if boxes:
    d = ImageDraw.Draw(im); col = im.getpixel((boxes[0] - 5, boxes[1] - 5))
    for i in range(0, len(boxes), 4): d.rectangle(boxes[i:i + 4], fill=col)
out = remove(im, session=new_session('isnet-general-use')); out.save(sys.argv[2]); print('wrote', sys.argv[2], out.size)
