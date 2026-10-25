"""Redraw English text baked into game images with Russian, using the game's own bitmap fonts
(Latin from the game, Cyrillic from fonts/font-<ID>.png/json made by tools/fontgen).

  python retext.py fonts <out.png> [text]       preview every font that has Cyrillic
  python retext.py build <spec.json> [names]    redraw images listed in the spec -> pak/assets/data/ru

spec.json: {"Claim.png": {"text": "ЗАБРАТЬ", "font": 75, "scale": 2, "box": [x0,y0,x1,y1],
             "fill": "auto"|"#rrggbb", "outline": "auto"|"#rrggbb", "dx": 0, "dy": 0, "lines": ["..",".."]}}
* box: area holding the English text; it is cleared by stretching the columns just left and
  right of it across (works for flat, gradient and textured-by-row backgrounds), unless
  "erase": "rows" (copy the row above/below) or "none".
* the text is centred in the box; "lines" (or "|" in text) gives several lines.
* the font's own colours are mapped: its lightest colour -> fill, its darkest -> outline;
  "auto" takes the most common light / dark colour of the original text inside the box.
"""
import json
import os
import re
import sys
from collections import Counter

from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GAME = os.path.join(ROOT, 'work', 'orig_pak', 'assets')
FONTS = os.path.join(ROOT, 'fonts')


class Font:
    def __init__(self, fid):
        self.id = fid
        base = os.path.join(GAME, 'graphics', '1x', f'font-{fid}')
        xml = open(base + '.fnt', encoding='utf-8').read()
        self.sheet = Image.open(base + '.png').convert('RGBA')
        self.line = int(re.search(r'lineHeight="(\d+)"', xml).group(1))
        self.glyphs = {}
        for m in re.finditer(r'<char [^>]*/>', xml):
            a = dict(re.findall(r'(\w+)="(-?\d+)"', m.group(0)))
            if 'id' not in a:
                continue
            self.glyphs[chr(int(a['id']))] = (self.sheet, int(a['x']), int(a['y']), int(a['width']),
                                              int(a['height']), int(a['xoffset']), int(a['yoffset']), int(a['xadvance']))
        cyr = os.path.join(FONTS, f'font-{fid}')
        if os.path.exists(cyr + '.json'):
            spec = json.load(open(cyr + '.json', encoding='utf-8'))
            sh = Image.open(cyr + '.png').convert('RGBA')
            for c in spec['chars']:
                self.glyphs[chr(c['id'])] = (sh, c['x'], c['y'], c['width'], c['height'], c['xoffset'], c['yoffset'], c['xadvance'])

    def render(self, text, spacing=0):
        """text -> RGBA image cropped to its pixels"""
        w = sum(self.glyphs.get(ch, self.glyphs.get(' '))[7] + spacing for ch in text) + 40
        h = max([g[4] + max(0, g[6]) for g in self.glyphs.values()] + [self.line]) + 20
        img = Image.new('RGBA', (w, h), (0, 0, 0, 0))
        x = 10
        for ch in text:
            g = self.glyphs.get(ch)
            if g is None:
                g = self.glyphs.get(ch.upper()) or self.glyphs.get(' ')
            sh, gx, gy, gw, gh, xo, yo, adv = g
            if gw and gh:
                piece = sh.crop((gx, gy, gx + gw, gy + gh))
                img.alpha_composite(piece, (x + xo, 10 + yo))
            x += adv + spacing
        bb = img.getbbox()
        return img.crop(bb) if bb else img


def hexcol(s):
    s = s.lstrip('#')
    return tuple(int(s[i:i + 2], 16) for i in (0, 2, 4)) + (255,)


def lum(c):
    return 0.299 * c[0] + 0.587 * c[1] + 0.114 * c[2]


def recolor(img, fill, outline):
    """map the font's colours: light ones -> fill, dark ones -> outline, keep shading between"""
    px = img.load()
    cols = Counter(px[x, y][:3] for x in range(img.width) for y in range(img.height) if px[x, y][3] > 0)
    if not cols:
        return img
    ls = [lum(c) for c in cols]
    lo, hi = min(ls), max(ls)
    for y in range(img.height):
        for x in range(img.width):
            r, g, b, a = px[x, y]
            if not a:
                continue
            t = 1.0 if hi == lo else (lum((r, g, b)) - lo) / (hi - lo)
            px[x, y] = tuple(int(outline[i] + (fill[i] - outline[i]) * t) for i in range(3)) + (a,)
    return img


def shadow_color(img, box):
    """the light cyan shade at the bottom of white letters, if the lettering has one"""
    x0, y0, x1, y1 = box
    px = img.load()
    cols = Counter()
    for y in range(max(y0, 1), y1):
        for x in range(x0, x1):
            c, up = px[x, y], px[x, y - 1]
            if c[3] > 200 and not is_white(c[:3]) and lum(c) > 150 and is_white(up[:3]):
                cols[c] += 1
    return cols.most_common(1)[0][0] if cols and cols.most_common(1)[0][1] >= 3 else None


def add_shadow(t, fill, shade):
    """bottom row of every letter stroke in the shadow colour"""
    px = t.load()
    f = tuple(fill[:3])
    for y in range(t.height - 1):
        for x in range(t.width):
            if px[x, y][3] and px[x, y][:3] == f and px[x, y + 1][:3] != f:
                px[x, y] = tuple(shade[:3]) + (px[x, y][3],)
    return t


def text_colors(img, box):
    """most common light and dark colours in the box (the original lettering)"""
    x0, y0, x1, y1 = box
    px = img.load()
    cols = Counter(px[x, y] for x in range(x0, x1) for y in range(y0, y1) if px[x, y][3] > 200)
    common = [c for c, _ in cols.most_common(12)]
    light = max(common, key=lum)
    dark = min(common, key=lum)
    return light, dark


def is_white(c):
    return min(c) > 228 and max(c) - min(c) < 24


def auto_box(img, pad, band=0):
    """bounding box of the light, unsaturated pixels (white lettering), plus its outline"""
    px = img.load()
    xs, ys = [], []
    for y in range(band, img.height):
        for x in range(img.width):
            r, g, b, a = px[x, y]
            if a > 200 and is_white((r, g, b)):
                xs.append(x); ys.append(y)
    if not xs:
        return [0, 0, img.width, img.height]
    return [max(min(xs) - pad, 0), max(min(ys) - pad, 0), min(max(xs) + 1 + pad, img.width), min(max(ys) + 1 + pad, img.height)]


def text_mask(img, box, shade=None):
    """white lettering + the dark outline and light shadow touching it"""
    x0, y0, x1, y1 = box
    px = img.load()
    white = {(x, y) for y in range(y0, y1) for x in range(x0, x1) if px[x, y][3] > 200 and is_white(px[x, y][:3])}
    mask = set(white)
    for _ in range(4):   # outline, shadow, outline of the shadow, stray outline
        grow = set()
        for (x, y) in mask:
            for dx in (-1, 0, 1):
                for dy in (-1, 0, 1):
                    q = (x + dx, y + dy)
                    if q in mask or not (x0 <= q[0] < x1 and y0 <= q[1] < y1):
                        continue
                    r, g, b, a = px[q]
                    if a > 200 and (max(r, g, b) < 40 or (shade is not None and (r, g, b, a) == shade)):
                        grow.add(q)
        mask |= grow
    return mask


def erase(img, box, mode, shade=None):
    x0, y0, x1, y1 = box
    px = img.load()
    if mode == 'none':
        return
    if mode == 'mask-fill':
        mask = text_mask(img, box, shade)
        for y in range(y0, y1):
            body = Counter(px[x, y] for x in range(x0, x1) if (x, y) not in mask and px[x, y][3] > 200 and max(px[x, y][:3]) >= 45)
            if not body:
                continue
            m = body.most_common(1)[0][0]
            for x in range(x0, x1):
                if (x, y) in mask:
                    px[x, y] = m
        return
    if mode == 'rows-fill':
        # buttons are flat along each row: paint the text area with the row's own body colour
        def texty(c):
            return c[3] < 200 or is_white(c[:3]) or max(c[:3]) < 45 or (shade is not None and c == shade)
        for y in range(y0, y1):
            row = [px[x, y] for x in range(img.width)]
            body = Counter(c for c in row if not texty(c))
            if not body:
                continue
            m = body.most_common(1)[0][0]
            xs = [x for x, c in enumerate(row) if not texty(c)]
            lo, hi = max(min(xs), x0), min(max(xs) + 1, x1)
            for x in range(lo, hi):
                px[x, y] = m
        return
    if mode == 'mask':
        mask = text_mask(img, box)
        for x in range(x0, x1):
            ys = [y for y in range(y0, y1) if (x, y) in mask]
            for y in ys:
                up = y - 1
                while (x, up) in mask:
                    up -= 1
                dn = y + 1
                while (x, dn) in mask:
                    dn += 1
                cu = px[x, max(up, 0)]
                cd = px[x, min(dn, img.height - 1)]
                t = (y - up) / (dn - up)
                px[x, y] = tuple(int(cu[i] + (cd[i] - cu[i]) * t) for i in range(4))
        return
    if mode == 'rows':
        for y in range(y0, y1):
            src = y0 - 1 if y - y0 < (y1 - y) else y1
            src = min(max(src, 0), img.height - 1)
            for x in range(x0, x1):
                px[x, y] = px[x, src]
        return
    for y in range(y0, y1):
        l = px[max(x0 - 1, 0), y]
        r = px[min(x1, img.width - 1), y]
        for x in range(x0, x1):
            t = (x - x0 + 1) / (x1 - x0 + 1)
            px[x, y] = tuple(int(l[i] + (r[i] - l[i]) * t) for i in range(4))


def preview(names, out_dir, out_png, zoom=3):
    pairs = []
    for n in names:
        a = Image.open(os.path.join(GAME, 'data', n)).convert('RGBA')
        b = Image.open(os.path.join(out_dir, n)).convert('RGBA')
        pairs.append((a, b))
    W = max(a.width + b.width for a, b in pairs) * zoom + 30
    H = sum(max(a.height, b.height) * zoom + 8 for a, b in pairs)
    out = Image.new('RGBA', (W, H), (60, 60, 75, 255))
    y = 0
    for a, b in pairs:
        out.alpha_composite(a.resize((a.width * zoom, a.height * zoom), Image.NEAREST), (0, y))
        out.alpha_composite(b.resize((b.width * zoom, b.height * zoom), Image.NEAREST), (a.width * zoom + 20, y))
        y += max(a.height, b.height) * zoom + 8
    out.save(out_png)


AUTO_FONTS = [(309, 0), (309, -1), (309, -2), (109, 0), (109, -1), (75, -1)]
FONT_CACHE = {}


def build_one(name, sp, out_dir):
    src = Image.open(os.path.join(GAME, 'data', name)).convert('RGBA')
    img = src.copy()
    box = sp.get('box') or 'auto'
    if box == 'auto':
        box = auto_box(src, sp.get('pad', 3), sp.get('band', 0))
        if sp.get('erase', 'rows-fill') == 'rows-fill':   # keep the button's own border
            box = [max(box[0], 1), max(box[1], 1), min(box[2], src.width - 1), min(box[3], src.height - 1)]
    light, dark = text_colors(src, box)
    shade = shadow_color(src, box)
    wb = auto_box(src, 0, sp.get('band', 0))
    fill = hexcol(sp['fill']) if sp.get('fill', 'auto') != 'auto' else light
    outline = hexcol(sp['outline']) if sp.get('outline', 'auto') != 'auto' else dark
    erase(img, box, sp.get('erase', 'rows-fill'), shade)
    scale = sp.get('scale', 1)
    lines = sp.get('lines') or sp['text'].split('|')
    bw = box[2] - box[0] if sp.get('fit') != 'image' else src.width - 6
    # the first font/spacing whose widest line fits the box (bold outlined -> narrower)
    tries = [(sp['font'], sp.get('spacing', 0))] if 'font' in sp else AUTO_FONTS
    for fid, spacing in tries:
        font = FONT_CACHE.get(fid) or FONT_CACHE.setdefault(fid, Font(fid))
        rendered = []
        for ln in lines:
            t = recolor(font.render(ln, spacing), fill, outline)
            if shade and sp.get('shadow', True):
                t = add_shadow(t, fill, shade)
            if scale != 1:
                t = t.resize((t.width * scale, t.height * scale), Image.NEAREST)
            rendered.append(t)
        if max(t.width for t in rendered) <= bw + 2:
            break
    gap = sp.get('gap', scale)
    th = sum(t.height for t in rendered) + gap * (len(rendered) - 1)
    cy = (wb[1] + wb[3]) / 2 if sp.get('box', 'auto') == 'auto' else (box[1] + box[3]) / 2
    y = int(round(cy - th / 2)) + sp.get('dy', 0)
    if sp.get('box', 'auto') == 'auto' and sp.get('erase') == 'mask-fill' and wb[3] >= src.height - 1:
        y = src.height - th + sp.get('dy', 0)   # lettering cut by the bottom edge: keep it there
    for t in rendered:
        if t.width > bw + 2:
            print(f'  {name}: "{lines}" is {t.width}px wide, box {bw}px')
        x = (box[0] + box[2] - t.width) // 2 + sp.get('dx', 0)
        img.alpha_composite(t, (x, y))
        y += t.height + gap
    img.save(os.path.join(out_dir, name))


def main():
    cmd = sys.argv[1]
    if cmd == 'fonts':
        text = sys.argv[3] if len(sys.argv) > 3 else 'ЗАБРАТЬ Собрать CLAIM 0123'
        ids = sorted(int(f[5:-5]) for f in os.listdir(FONTS) if f.endswith('.json') and f.startswith('font-'))
        rows = []
        for fid in ids:
            try:
                rows.append((fid, Font(fid).render(text)))
            except Exception as e:  # noqa
                print(fid, e)
        W = max(r.width for _, r in rows) + 60
        H = sum(r.height + 6 for _, r in rows)
        out = Image.new('RGBA', (W, H), (60, 60, 75, 255))
        from PIL import ImageDraw
        d = ImageDraw.Draw(out)
        y = 0
        for fid, r in rows:
            d.text((2, y), str(fid), fill=(255, 255, 0, 255))
            out.alpha_composite(r, (50, y))
            y += r.height + 6
        out.save(sys.argv[2])
    elif cmd == 'build':
        spec = json.load(open(sys.argv[2], encoding='utf-8'))
        only = set(sys.argv[3:])
        out_dir = os.path.join(ROOT, 'pak', 'assets', 'data', 'ru')
        os.makedirs(out_dir, exist_ok=True)
        for name, sp in spec.items():
            if name.startswith('_') or (only and name not in only):
                continue
            build_one(name, sp, out_dir)
        names = [k for k in spec if not k.startswith('_') and (not only or k in only)]
        print('built', len(names))
        preview(names, out_dir, os.path.join(ROOT, 'work', 'retext_preview.png'))


if __name__ == '__main__':
    main()
