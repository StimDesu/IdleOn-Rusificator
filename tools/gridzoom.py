"""Zoomed original images with a coordinate grid, for placing text boxes.
  python gridzoom.py <out.png> <name.png>[:k[:x0,y0,x1,y1]] ..."""
import os
import sys

from PIL import Image, ImageDraw

sys.path.insert(0, os.path.dirname(__file__))
from retext import GAME   # noqa: E402

tiles = []
for arg in sys.argv[2:]:
    name, _, rest = arg.partition(':')
    k, _, crop = rest.partition(':')
    a = Image.open(os.path.join(GAME, 'data', name)).convert('RGBA')
    ox, oy = 0, 0
    if crop:
        ox, oy, x1, y1 = map(int, crop.split(','))
        a = a.crop((ox, oy, x1, y1))
    k = int(k or 4)
    bg = Image.new('RGBA', a.size, (255, 0, 255, 255))
    bg.alpha_composite(a)
    z = bg.resize((a.width * k, a.height * k), Image.NEAREST)
    d = ImageDraw.Draw(z)
    for x in range(-ox % 10, a.width, 10):
        d.line([(x * k, 0), (x * k, z.height)], fill=(255, 0, 0) if (x + ox) % 50 == 0 else (120, 0, 0))
    for y in range(-oy % 10, a.height, 10):
        d.line([(0, y * k), (z.width, y * k)], fill=(255, 255, 0) if (y + oy) % 50 == 0 else (120, 120, 0))
    for x in range(-ox % 20, a.width, 20):
        d.text((x * k + 2, 1), str(x + ox), fill=(0, 255, 0))
    for y in range(-oy % 10, a.height, 10):
        d.text((1, y * k + 1), str(y + oy), fill=(0, 255, 255))
    t = Image.new('RGB', (z.width, z.height + 12), (40, 40, 40))
    t.paste(z, (0, 12))
    ImageDraw.Draw(t).text((2, 0), name, fill=(255, 255, 0))
    tiles.append(t)
s = Image.new('RGB', (max(t.width for t in tiles), sum(t.height for t in tiles)), (40, 40, 40))
y = 0
for t in tiles:
    s.paste(t, (0, y))
    y += t.height
s.save(sys.argv[1])
