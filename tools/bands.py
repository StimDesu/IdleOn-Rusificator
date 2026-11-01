"""Text bands of a game image: runs of rows holding light pixels, with their column extent.
  python bands.py <name.png> [x0 x1] [lum]"""
import os
import sys

from PIL import Image

sys.path.insert(0, os.path.dirname(__file__))
from retext import GAME, lum   # noqa: E402

name = sys.argv[1]
img = Image.open(os.path.join(GAME, 'data', name)).convert('RGBA')
x0, x1 = (int(sys.argv[2]), min(img.width, int(sys.argv[3]))) if len(sys.argv) > 3 else (0, img.width)
t = int(sys.argv[4]) if len(sys.argv) > 4 else 150
px = img.load()
run = None
for y in range(img.height + 1):
    xs = [x for x in range(x0, x1) if y < img.height and px[x, y][3] > 100 and lum(px[x, y]) > t]
    if xs and run is None:
        run = [y, y, min(xs), max(xs)]
    elif xs:
        run[1], run[2], run[3] = y, min(run[2], min(xs)), max(run[3], max(xs))
    elif run:
        print(f'y {run[0]}-{run[1] + 1}  x {run[2]}-{run[3] + 1}')
        run = None
