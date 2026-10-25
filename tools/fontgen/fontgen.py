"""Generate Cyrillic glyph sheets for the game's bitmap fonts.

  python fontgen.py <pak_dir> <out_dir> [font ids,comma separated] [--preview <png>]

<pak_dir> is an extracted default.pak (tools/pak.py extract). For every text font the
matching typeface family is detected (designs/<family>.txt, each naming a reference
font), the font's coloring/decoration model is learned from its Latin letters and
Cyrillic letters are rendered from the family designs. Output per font:
  <out_dir>/font-<ID>.png   glyph sheet
  <out_dir>/font-<ID>.json  glyph metrics, merged into the game font by the installer
"""
import glob
import json
import os
import re
import sys

import numpy as np
from PIL import Image

sys.path.insert(0, os.path.dirname(__file__))
from model import (LATIN, fit, fit_bodies, glyph_pixels, load_font, shift)

HERE = os.path.dirname(os.path.abspath(__file__))
CYR_UP = 'АБВГДЕЁЖЗИЙКЛМНОПРСТУФХЦЧШЩЪЫЬЭЮЯ'
CYR_LO = 'абвгдеёжзийклмнопрстуфхцчшщъыьэюя'
EXTRA = '№«»'


# ---- designs ------------------------------------------------------------------------
def parse_designs(path):
    """designs file -> (ref font id, {char: rule}); rule = ('copy', L) | ('mirror', L) |
    ('mask', rows, dy) | ('alias', C)"""
    ref = None
    rules = {}
    cur = None
    for raw in open(path, encoding='utf-8'):
        line = raw.rstrip('\n')
        if line.startswith('//'):
            m = re.match(r'//\s*ref:\s*(\d+)', line)
            if m:
                ref = m.group(1)
            continue
        if not line.strip():
            cur = None
            continue
        m = re.match(r'^(\S)\s*=\s*(copy|mirror|alias)\s+(\S)\s*$', line)
        if m:
            rules[m.group(1)] = (m.group(2), m.group(3))
            cur = None
            continue
        m = re.match(r'^(\S)(?:\s+dy=(-?\d+))?\s*:\s*$', line)
        if m:
            cur = [m.group(1), [], int(m.group(2) or 0)]
            rules[cur[0]] = ('mask', cur[1], cur[2])
            continue
        if cur is not None and re.match(r'^[#.]+$', line.strip()):
            cur[1].append(line.strip())
            continue
        raise ValueError(f'{path}: bad line {line!r}')
    return ref, rules


class Family:
    def __init__(self, name, path, pak):
        self.name = name
        self.ref, self.rules = parse_designs(path)
        chars, img, _ = load_font(*font_paths(pak, self.ref))
        glyphs = {L: glyph_pixels(img, chars[ord(L)]) for L in LATIN if ord(L) in chars and chars[ord(L)]['w']}
        model = fit(list(glyphs.values()), texture=False)
        self.masks = {}
        for cid, c in chars.items():
            if c['w'] and c['h'] and (chr(cid) in LATIN or 0xC0 <= cid < 0x180 or chr(cid) in '0123456789'):
                px = glyph_pixels(img, c)
                b = {p for p, col in px.items() if col in model.body_colors}
                if b:
                    self.masks[chr(cid)] = b
        self.adv = {chr(k): c['adv'] for k, c in chars.items()}
        h = self.masks['H']
        self.origin = (min(x for x, _ in h), min(y for _, y in h))

    def body(self, ch, seen=()):
        rule = self.rules.get(ch)
        if rule is None:
            return None
        kind = rule[0]
        if kind == 'copy':
            return set(self.masks[rule[1]]) if rule[1] in self.masks else None
        if kind == 'alias':
            if rule[1] in seen:
                raise ValueError('alias loop ' + ch)
            return self.body(rule[1], seen + (ch,))
        if kind == 'mirror':
            src = self.masks.get(rule[1])
            if not src:
                return None
            x0 = min(x for x, _ in src); x1 = max(x for x, _ in src)
            return {(x0 + x1 - x, y) for x, y in src}
        rows, dy = rule[1], rule[2]
        ox, oy = self.origin
        return {(ox + x, oy + dy + y) for y, r in enumerate(rows) for x, v in enumerate(r) if v == '#'}

    def advance_for(self, body):
        """advance = body width + the family's spacing (taken from H)"""
        h = self.masks['H']
        hw = max(x for x, _ in h) - min(x for x, _ in h) + 1
        w = max(x for x, _ in body) - min(x for x, _ in body) + 1
        return self.adv['H'] - hw + w


def font_paths(pak, fid):
    return (f'{pak}/assets/graphics/1x/font-{fid}.fnt', f'{pak}/assets/graphics/1x/font-{fid}.png')


class ScaledFamily:
    """a family drawn k times bigger (the game's zoomed title fonts): every pixel -> k x k"""
    def __init__(self, base, k):
        self.base, self.k = base, k
        self.name = f'{base.name}x{k}'
        self.masks = {L: self._up(m) for L, m in base.masks.items()}
        self.adv = {L: a * k for L, a in base.adv.items()}
        self.origin = (base.origin[0] * k, base.origin[1] * k)

    def _up(self, m):
        k = self.k
        return {(x * k + dx, y * k + dy) for x, y in m for dx in range(k) for dy in range(k)}

    def body(self, ch, seen=()):
        b = self.base.body(ch, seen)
        return self._up(b) if b else b

    advance_for = Family.advance_for


def load_families(pak):
    fams = []
    for p in sorted(glob.glob(os.path.join(HERE, 'designs', '*.txt'))):
        fams.append(Family(os.path.splitext(os.path.basename(p))[0], p, pak))
    return fams + [ScaledFamily(f, 2) for f in fams]


# ---- matching a font to a family ------------------------------------------------------
def match(fam, glyphs):
    """best (error_rate, model, offset) for this family; bodies = family masks shifted"""
    best = None
    letters = [L for L in glyphs if L in fam.masks]
    if len(letters) < 20:
        return None
    r = 3 * getattr(fam, 'k', 1)
    for dy in range(-r, r + 1):
        for dx in range(-r, r + 1):
            bodies, used = [], []
            for L in letters:
                b = shift(fam.masks[L], (dx, dy))
                if b <= set(glyphs[L]):
                    bodies.append(b)
                    used.append(L)
            # a few letters may be drawn differently in a family member
            if len(used) < 0.7 * len(letters):
                continue
            # the texture model can explain almost any alignment, so alignment is judged
            # by the plain per-row model; texture is only used for rendering
            plain = fit_bodies([glyphs[L] for L in used], bodies, texture=False)
            miss = 1 - len(used) / len(letters)
            key = (plain.error / max(1, plain.total) + miss, abs(dx) + abs(dy))
            if best is None or key < best[0]:
                best = (key, bodies, (dx, dy), used)
    if best is None:
        return None
    key, bodies, off, letters = best
    m = fit_bodies([glyphs[L] for L in letters], bodies, texture=True)
    return (m.error / max(1, m.total), m, off)


# ---- output -------------------------------------------------------------------------
def cyrillic(glyphs, fams):
    """Latin glyph pixels of one font/letter set -> (status dict, [(char, pixels, advance)])"""
    results = [(match(f, glyphs), f) for f in fams]
    results = [(r, f) for r, f in results if r]
    if not results:
        return {'status': 'no family'}, []
    (rate, model, off), fam = min(results, key=lambda t: t[0][0])
    if rate > 0.3:
        return {'status': 'no family', 'closest': fam.name, 'error': round(rate, 3)}, []
    caps_only = all(_same(glyphs.get(l), glyphs.get(l.upper())) for l in 'abcdeghkmnrs' if l in glyphs) or         not any(l in glyphs for l in 'abcdeghkmnrs')
    out = []
    for ch in CYR_UP + CYR_LO + EXTRA:
        key = ch
        if caps_only and ch in CYR_LO:
            key = CYR_UP[CYR_LO.index(ch)]
        b = fam.body(key)
        if not b and ch in CYR_LO:
            b = fam.body(CYR_UP[CYR_LO.index(ch)])
        if not b:
            continue
        b = shift(b, off)
        out.append((ch, model.render(b), fam.advance_for(b)))
    return {'status': 'ok', 'family': fam.name, 'error': round(rate, 4), 'offset': off, 'glyphs': len(out)}, out


def render_font(fid, pak, fams, out_dir):
    chars, img, info = load_font(*font_paths(pak, fid))
    glyphs = {L: glyph_pixels(img, chars[ord(L)]) for L in LATIN if ord(L) in chars and chars[ord(L)]['w'] and chars[ord(L)]['h']}
    if len(glyphs) < 20:
        return None
    st, out = cyrillic(glyphs, fams)
    st['id'] = fid
    if not out:
        return st
    rate = st['error']
    fam = type('F', (), {'name': st['family']})
    # pack
    pad = 1
    items = []
    for ch, px, adv in out:
        xs = [x for x, _ in px]; ys = [y for _, y in px]
        x0, y0 = min(xs), min(ys)
        w, h = max(xs) - x0 + 1, max(ys) - y0 + 1
        g = np.zeros((h, w, 4), np.uint8)
        for (x, y), col in px.items():
            g[y - y0, x - x0] = col
        items.append(dict(ch=ch, img=g, xo=x0, yo=y0, adv=adv))
    W = 256
    x = y = rowh = 0
    for it in items:
        h, w = it['img'].shape[:2]
        if x + w > W:
            x, y, rowh = 0, y + rowh + pad, 0
        it['x'], it['y'] = x, y
        x += w + pad
        rowh = max(rowh, h)
    H = y + rowh
    sheet = np.zeros((H, W, 4), np.uint8)
    spec = []
    for it in items:
        h, w = it['img'].shape[:2]
        sheet[it['y']:it['y'] + h, it['x']:it['x'] + w] = it['img']
        spec.append(dict(id=ord(it['ch']), x=it['x'], y=it['y'], width=w, height=h, xoffset=it['xo'], yoffset=it['yo'], xadvance=it['adv']))
    os.makedirs(out_dir, exist_ok=True)
    Image.fromarray(sheet).save(os.path.join(out_dir, f'font-{fid}.png'))
    with open(os.path.join(out_dir, f'font-{fid}.json'), 'w', encoding='utf-8') as f:
        json.dump({'family': fam.name, 'fit_error': round(rate, 4), 'chars': spec}, f, ensure_ascii=False, indent=0)
    return st


# ---- letter images (dialogue boxes, item popups, anvil): one PNG per character -------
def letter_name(ch):
    return ('1' + ch) if 'a' <= ch <= 'z' else ch


def render_letters(pak, style, fams, out_dir):
    """assets/data/<letter>_<style>.png sets -> Cyrillic letter PNGs with the same look"""
    base = f'{pak}/assets/data'
    glyphs, size = {}, None
    for L in LATIN:
        p = f'{base}/{letter_name(L)}_{style}.png'
        if not os.path.exists(p):
            continue
        a = np.array(Image.open(p).convert('RGBA'))
        size = a.shape[:2]
        glyphs[L] = {(x, y): tuple(int(v) for v in a[y, x]) for y in range(a.shape[0]) for x in range(a.shape[1]) if a[y, x, 3]}
    if len(glyphs) < 20:
        return {'style': style, 'status': 'too few letters'}
    st, out = cyrillic(glyphs, fams)
    st['style'] = style
    os.makedirs(out_dir, exist_ok=True)
    H = size[0]
    for ch, px, adv in out:
        w = max(adv, max(x for x, _ in px) + 1)
        h = max(H, max(y for _, y in px) + 1)
        g = np.zeros((h, w, 4), np.uint8)
        for (x, y), col in px.items():
            if x >= 0 and y >= 0:
                g[y, x] = col
        # Windows file names are case-insensitive (А/а would collide): store code points,
        # the installer turns U+XXXX back into the character for the asset id
        Image.fromarray(g).save(os.path.join(out_dir, f'U+{ord(ch):04X}_{style}.png'))
    return st


def _same(a, b):
    return a is not None and b is not None and a == b


def main():
    a = sys.argv[1:]
    if a[0] == '--letters':  # --letters <pak_dir> <out_dir> <styles>
        fams = load_families(a[1])
        for style in a[3].split(','):
            print(json.dumps(render_letters(a[1], style, fams, a[2]), ensure_ascii=False), flush=True)
        return
    pak, out_dir = a[0], a[1]
    ids = a[2].split(',') if len(a) > 2 and not a[2].startswith('--') else None
    fams = load_families(pak)
    if ids is None:
        ids = sorted({re.search(r'font-(\d+)\.fnt', p).group(1) for p in glob.glob(f'{pak}/assets/graphics/1x/font-*.fnt')}, key=int)
    report = []
    for fid in ids:
        r = render_font(fid, pak, fams, out_dir)
        if r:
            report.append(r)
            print(json.dumps(r, ensure_ascii=False), flush=True)
    with open(os.path.join(out_dir, 'report.json'), 'w', encoding='utf-8') as f:
        json.dump(report, f, ensure_ascii=False, indent=1)


if __name__ == '__main__':
    main()
