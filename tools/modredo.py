"""Help redraw the Russian mod's textures (smooth vector lettering) in the game's own fonts.

  python modredo.py scan <names...>      text blocks (where the mod changed the image) with the
                                         game font that drew the English there -> stdout JSON
  python modredo.py sheet <out.png> <names...>   original | mod | current redraw, zoomed

The mod's versions are kept in work/modsrc (they are the reference for the Russian text);
the redraw specs live in retext/mod.json and are built by retext.py.
"""
import glob
import json
import os
import re
import sys

import numpy as np
from PIL import Image, ImageDraw

sys.path.insert(0, os.path.dirname(__file__))
from retext import Font, ROOT, GAME   # noqa: E402

ORIG = os.path.join(GAME, 'data')
MOD = os.path.join(ROOT, 'work', 'modsrc')
RU = os.path.join(ROOT, 'pak', 'assets', 'data', 'ru')
LATIN = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789'

_fonts = None


def fonts():
    """font id -> {letter: glyph mask}, for every game font with Cyrillic made"""
    global _fonts
    if _fonts is None:
        _fonts = {}
        for f in glob.glob(os.path.join(ROOT, 'fonts', 'font-*.json')):
            fid = re.search(r'font-(\d+)', f).group(1)
            fo = Font(fid)
            masks = {}
            for ch in LATIN:
                g = fo.glyphs.get(ch)
                if not g or not g[3] or not g[4]:
                    continue
                sh, x, y, w, h = g[:5]
                a = np.array(sh.crop((x, y, x + w, y + h)))
                if a[..., 3].any():
                    masks[ch] = shape(a)
            _fonts[fid] = masks
    return _fonts


def shape(a):
    """letter mask: opaque pixels that are lighter than the darkest third (body, no outline)"""
    op = a[..., 3] > 100
    if not op.any():
        return op
    lum = a[..., :3].astype(int) @ [299, 587, 114] // 1000
    lo, hi = lum[op].min(), lum[op].max()
    return op & (lum > lo + (hi - lo) / 3) if hi - lo > 40 else op


def detect_font(img, box):
    """the font whose Latin letters occur most (by pixel area) inside box of the original"""
    x0, y0, x1, y1 = box
    a = np.array(img.crop((max(0, x0 - 2), max(0, y0 - 2), x1 + 2, y1 + 2)))
    m = shape(a)
    scores = []
    for fid, masks in fonts().items():
        hit = 0
        for ch, g in masks.items():
            h, w = g.shape
            if h > m.shape[0] or w > m.shape[1] or g.sum() < 4:
                continue
            win = np.lib.stride_tricks.sliding_window_view(m, (h, w))
            eq = (win == g).all(axis=(2, 3))
            if eq.any():
                hit += g.sum() * min(int(eq.sum()), 3)
        scores.append((hit, fid))
    scores.sort(reverse=True)
    return [f for s, f in scores[:3] if s]


def blocks(name):
    """rectangles where the mod repainted the original: its lettering, grouped by line"""
    a = np.array(Image.open(os.path.join(ORIG, name)).convert('RGBA')).astype(int)
    b = np.array(Image.open(os.path.join(MOD, name)).convert('RGBA')).astype(int)
    d = np.abs(a - b).sum(2) > 150
    rows = d.any(1)
    out = []
    y = 0
    H = d.shape[0]
    while y < H:
        if not rows[y]:
            y += 1
            continue
        y1 = y
        while y1 < H and rows[y1:y1 + 3].any():   # gaps of up to 2 rows join a line
            y1 += 1
        cols = np.nonzero(d[y:y1].any(0))[0]
        # split a band into pieces separated by wide empty columns
        start = prev = cols[0]
        for c in list(cols[1:]) + [None]:
            if c is None or c - prev > 12:
                out.append([int(start), y, int(prev) + 1, y1])
                start = c
            if c is not None:
                prev = c
        y = y1
    return out


def scan(names):
    res = {}
    for n in names:
        img = Image.open(os.path.join(ORIG, n)).convert('RGBA')
        res[n] = [{'box': bx, 'fonts': detect_font(img, bx)} for bx in blocks(n)]
    print(json.dumps(res, ensure_ascii=False))


def sheet(out, names):
    tiles = []
    for n in names:
        ims = [Image.open(os.path.join(d, n)).convert('RGBA') for d in (ORIG, MOD, RU)]
        w, h = ims[0].size
        k = 3 if w <= 120 else 2 if w <= 260 else 1
        t = Image.new('RGBA', ((w * k + 4) * 3, h * k + 12), (40, 40, 40, 255))
        for i, im in enumerate(ims):
            t.paste(im.resize((w * k, h * k), Image.NEAREST), (i * (w * k + 4), 12))
        ImageDraw.Draw(t).text((2, 0), f'{n} {w}x{h}', fill=(255, 255, 0, 255))
        tiles.append(t)
    W = max(t.width for t in tiles)
    s = Image.new('RGBA', (W, sum(t.height for t in tiles)), (40, 40, 40, 255))
    y = 0
    for t in tiles:
        s.paste(t, (0, y))
        y += t.height
    s.save(out)


if __name__ == '__main__':
    if sys.argv[1] == 'scan':
        scan(sys.argv[2:])
    elif sys.argv[1] == 'sheet':
        sheet(sys.argv[2], sys.argv[3:])
