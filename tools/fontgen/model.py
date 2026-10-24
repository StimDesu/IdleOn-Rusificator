"""Decompose a game bitmap font into glyph *bodies* and a decoration model.

Every IdleOn text font is one of a few pixel typefaces, recolored and decorated:
  * body pixels colored by row (flat color, gradient, tinted bottom row ...)
  * decoration = copies of the body shifted by small offsets (outline = 4 neighbours,
    drop shadow = (-1,+1), ...), each offset with its own color, painted below the body.
The model is learned from the font's Latin glyphs, then reused to draw Cyrillic bodies
so the new letters get exactly the same look.
"""
import itertools
import re
from collections import Counter, defaultdict

import numpy as np
from PIL import Image

OFFSETS = [(dx, dy) for dy in range(-2, 3) for dx in range(-2, 3) if (dx, dy) != (0, 0)]
LATIN = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz'


def load_font(fnt_path, png_path):
    s = open(fnt_path, encoding='utf-8').read()
    chars = {}
    for m in re.finditer(r'<char [^>]*>', s):
        t = m.group(0)
        g = lambda k: int(re.search(r'\s' + k + r'="(-?\d+)"', t).group(1))
        chars[g('id')] = dict(x=g('x'), y=g('y'), w=g('width'), h=g('height'), xo=g('xoffset'), yo=g('yoffset'), adv=g('xadvance'))
    info = dict(lineHeight=int(re.search(r'lineHeight="(\d+)"', s).group(1)), xml=s)
    img = np.array(Image.open(png_path).convert('RGBA'))
    return chars, img, info


def glyph_pixels(img, c):
    """glyph as dict (x,y)->rgba in cell coordinates (x from xoffset, y from yoffset)"""
    px = {}
    for y in range(c['h']):
        for x in range(c['w']):
            p = tuple(int(v) for v in img[c['y'] + y, c['x'] + x])
            if p[3]:
                px[(x + c['xo'], y + c['yo'])] = p
    return px


def shift(mask, o):
    return {(x + o[0], y + o[1]) for x, y in mask}


class Model:
    """body colors + row coloring + decoration offsets"""

    def __init__(self):
        self.body_colors = set()
        self.row_color = {}        # y (cell coords) -> color; fallback self.body_default
        self.body_default = None
        self.layers = []           # [(offset, color)], earlier = on top
        self.tex_yn = {}
        self.tex_n = {}
        self.layer_y = {}          # (offset, y) -> color (shadow gradients)
        self.error = 0
        self.total = 0

    # ---- rendering ---------------------------------------------------------------
    def body_color(self, body, p):
        n = neigh(body, p)
        for key, table in ((('yn', p[1], n), self.tex_yn), (('n', n), self.tex_n)):
            c = table.get(key[1:])
            if c is not None:
                return c
        return self.row_color.get(p[1], self.body_default)

    def render(self, body):
        out = {}
        for p in body:
            out[p] = self.body_color(body, p)
        for o, col in self.layers:
            for p in shift(body, o):
                if p not in out:
                    out[p] = self.layer_y.get((o, p[1]), col)
        return out


def neigh(body, p):
    x, y = p
    bits = 0
    for i, (dx, dy) in enumerate(((-1, -1), (0, -1), (1, -1), (-1, 0), (1, 0), (-1, 1), (0, 1), (1, 1))):
        if (x + dx, y + dy) in body:
            bits |= 1 << i
    return bits


def majority(counter_map, min_share=0.0):
    out = {}
    for k, c in counter_map.items():
        col, n = c.most_common(1)[0]
        if n >= min_share * sum(c.values()):
            out[k] = col
    return out


def fit(glyphs, texture=True):
    """glyphs: list of pixel dicts (Latin letters of one font) -> best Model"""
    colors = Counter()
    for g in glyphs:
        colors.update(g.values())
    allc = [c for c, _ in colors.most_common()]
    palette = allc[:10]
    best = None
    # decoration uses few colors (outline, shadow); everything else is body
    for r in range(0, 4):
        for deco_cols in itertools.combinations(palette, r):
            body_cols = set(allc) - set(deco_cols)
            if not body_cols:
                continue
            m = fit_with_body(glyphs, body_cols, texture)
            if m and (best is None or m.error < best.error):
                best = m
            if best is not None and best.error == 0:
                return best
    return best


def fit_with_body(glyphs, body_cols, texture=True):
    bodies = [{p for p, c in g.items() if c in body_cols} for g in glyphs]
    if any(not b for b in bodies):
        return None
    m = fit_bodies(glyphs, bodies, texture)
    m.body_colors = body_cols
    return m


def fit_bodies(glyphs, bodies, texture=True):
    """glyph pixel dicts + their body masks -> Model (colors, texture, decoration)"""
    m = Model()
    # row coloring by cell y
    by_row = defaultdict(Counter)
    for g, b in zip(glyphs, bodies):
        for p in b:
            by_row[p[1]][g[p]] += 1
    m.row_color = {y: c.most_common(1)[0][0] for y, c in by_row.items()}
    total = Counter()
    for c in by_row.values():
        total += c
    m.body_default = total.most_common(1)[0][0]
    # texture: color by (row, 3x3 neighbourhood) and by neighbourhood alone
    yn, nn = defaultdict(Counter), defaultdict(Counter)
    for g, b in zip(glyphs, bodies):
        for p in b:
            n = neigh(b, p)
            yn[(p[1], n)][g[p]] += 1
            nn[(n,)][g[p]] += 1
    flat = len(total) == 1 or not texture
    m.tex_yn = {} if flat else majority(yn)
    m.tex_n = {} if flat else majority(nn, 0.6)
    # decoration: greedy layer selection
    deco = [{p: c for p, c in g.items() if p not in b} for g, b in zip(glyphs, bodies)]
    assigned = [dict() for _ in glyphs]
    remaining = set(OFFSETS)
    while True:
        cand = None
        for o in remaining:
            stats = Counter()
            bad = 0
            for b, d, a in zip(bodies, deco, assigned):
                for p in shift(b, o):
                    if p in b or p in a:
                        continue
                    if p in d:
                        stats[d[p]] += 1
                    else:
                        bad += 1
            if not stats:
                continue
            # colors may vary by row (gradient outlines), see layer_y below
            col = stats.most_common(1)[0][0]
            good = sum(stats.values())
            score = good - 3 * bad
            if score > 0 and (cand is None or score > cand[0]):
                cand = (score, o, col)
        if not cand:
            break
        _, o, col = cand
        remaining.discard(o)
        m.layers.append((o, col))
        for b, a in zip(bodies, assigned):
            for p in shift(b, o):
                if p not in b and p not in a:
                    a[p] = o
    ly = defaultdict(Counter)
    for d, a in zip(deco, assigned):
        for p, o in a.items():
            if p in d:
                ly[(o, p[1])][d[p]] += 1
    m.layer_y = majority(ly)
    # error
    err = tot = 0
    for g, b in zip(glyphs, bodies):
        r = m.render(b)
        keys = set(r) | set(g)
        tot += len(g)
        err += sum(1 for k in keys if r.get(k) != g.get(k))
    m.error, m.total = err, tot
    return m


def font_model(chars, img, letters=LATIN, texture=True):
    glyphs = {}
    for L in letters:
        c = chars.get(ord(L))
        if c and c['w'] and c['h']:
            glyphs[L] = glyph_pixels(img, c)
    if len(glyphs) < 10:
        return None, glyphs
    return fit(list(glyphs.values()), texture), glyphs


def body_of(model, g):
    return {p for p, c in g.items() if c in model.body_colors}


def ascii_mask(mask):
    if not mask:
        return []
    xs = [x for x, _ in mask]; ys = [y for _, y in mask]
    return [''.join('#' if (x, y) in mask else '.' for x in range(min(xs), max(xs) + 1)) for y in range(min(ys), max(ys) + 1)]
