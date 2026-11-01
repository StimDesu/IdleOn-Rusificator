"""Before/after pictures of a batch for review: original | Russian, zoomed, one file each.

  python review.py <out_dir> [name.png ...] [font:code ...] [glyphs]

name.png   a texture (original from the game, Russian from pak/assets/data/ru)
font:code  a replaced font glyph (original from the game font, Russian from fonts/)
glyphs     every glyph made by labelglyph.py
"""
import json
import os
import sys

from PIL import Image

sys.path.insert(0, os.path.dirname(__file__))
from retext import ROOT, GAME   # noqa: E402
from labelglyph import LABELS, PANELS, orig_glyph   # noqa: E402

BG = (70, 50, 40, 255)


def ru_glyph(fid, cid):
    spec = json.load(open(os.path.join(ROOT, 'fonts', f'font-{fid}.json'), encoding='utf-8'))
    c = next(c for c in spec['chars'] if c['id'] == cid)
    sheet = Image.open(os.path.join(ROOT, 'fonts', f'font-{fid}.png')).convert('RGBA')
    return sheet.crop((c['x'], c['y'], c['x'] + c['width'], c['y'] + c['height']))


def pair(a, b, out):
    k = 4 if max(a.width, b.width) < 200 else 3 if max(a.width, b.width) < 400 else 2 if max(a.width, b.width) < 800 else 1
    w, h = max(a.width, b.width) * k, max(a.height, b.height) * k
    img = Image.new('RGBA', (w, h * 2 + 8), (25, 25, 25, 255))
    for i, im in enumerate((a, b)):
        tile = Image.new('RGBA', im.size, BG)
        tile.alpha_composite(im)
        img.paste(tile.resize((im.width * k, im.height * k), Image.NEAREST), (0, i * (h + 8)))
    img.save(out)


def main():
    out = sys.argv[1]
    os.makedirs(out, exist_ok=True)
    items = []
    for a in sys.argv[2:]:
        if a == 'glyphs':
            keys = [f'{f}:{ord(c)}' for f, c, *_ in LABELS + PANELS]
            keys += [k for k in json.load(open(os.path.join(ROOT, 'retext', 'glyphs.json'), encoding='utf-8'))
                     if not k.startswith('_')]
            items += keys
        else:
            items.append(a)
    for it in items:
        if it.endswith('.png'):
            a = Image.open(os.path.join(GAME, 'data', it)).convert('RGBA')
            b = Image.open(os.path.join(ROOT, 'pak', 'assets', 'data', 'ru', it)).convert('RGBA')
            name = it
        else:
            fid, cid = map(int, it.split(':'))
            a, b = orig_glyph(fid, chr(cid))[0], ru_glyph(fid, cid)
            name = f'glyph_{fid}_{cid}.png'
        pair(a, b, os.path.join(out, name))
    print(f'{len(items)} pictures in {out}')


if __name__ == '__main__':
    main()
