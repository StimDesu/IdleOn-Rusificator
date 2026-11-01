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

        if '•' not in self.glyphs and '.' in self.glyphs and 'x' in self.glyphs:
            # bullet: the full stop lifted to the middle of the small letters
            def rows(g):   # opaque rows of a glyph cell
                bb = g[0].crop((g[1], g[2], g[1] + g[3], g[2] + g[4])).getbbox()
                return g[6] + bb[1], g[6] + bb[3]
            d, x = self.glyphs['.'], self.glyphs['x']
            (d0, d1), (x0, x1) = rows(d), rows(x)
            self.glyphs['•'] = d[:6] + (d[6] + (x0 + x1) // 2 - (d0 + d1) // 2, d[7])

    def render(self, text, spacing=0, crop_y=True):
        """text -> RGBA image cropped to its pixels (only sideways with crop_y=False, so
        pieces of one line share the baseline)"""
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
            x += adv + spacing + (3 if ch == ' ' and spacing < 0 else 0)
        bb = img.getbbox()
        if bb and not crop_y:
            return img.crop((bb[0], 0, bb[2], img.height))
        return img.crop(bb) if bb else img


def big_letters(font, text, spacing, scale, fill, outline):
    """letter bodies of a small font scaled up, with a fresh 1px outline (pop-up captions)"""
    t = font.render(text, spacing)
    px = t.load()
    cols = [px[x, y] for x in range(t.width) for y in range(t.height) if px[x, y][3]]
    if not cols:
        return t
    hi = max(lum(c) for c in cols)
    body = [(x, y) for x in range(t.width) for y in range(t.height) if px[x, y][3] and lum(px[x, y]) > hi * 0.6]
    W, H = t.width * scale + 2, t.height * scale + 2
    out = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    o = out.load()
    filled = set()
    for (x, y) in body:
        for dx in range(scale):
            for dy in range(scale):
                filled.add((1 + x * scale + dx, 1 + y * scale + dy))
    for (x, y) in filled:
        for ax in (-1, 0, 1):
            for ay in (-1, 0, 1):
                q = (x + ax, y + ay)
                if q not in filled and 0 <= q[0] < W and 0 <= q[1] < H:
                    o[q] = tuple(outline[:3]) + (255,)
    for (x, y) in filled:
        o[x, y] = tuple(fill[:3]) + (255,)
    bb = out.getbbox()
    return out.crop(bb) if bb else out


def hexcol(s):
    s = s.lstrip('#')
    return tuple(int(s[i:i + 2], 16) for i in (0, 2, 4)) + (int(s[6:8], 16) if len(s) == 8 else 255,)


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


def two_tone(img, fill, outline):
    """crisp lettering: every pixel of the font becomes either the fill or the outline colour"""
    px = img.load()
    ls = [lum(px[x, y]) for x in range(img.width) for y in range(img.height) if px[x, y][3]]
    if not ls:
        return img
    if max(ls) - min(ls) < 40:   # a font without outline: letters + a shadow right and down
        out = Image.new('RGBA', (img.width + 1, img.height + 1), (0, 0, 0, 0))
        q = out.load()
        on = {(x, y) for x in range(img.width) for y in range(img.height) if px[x, y][3]}
        for x, y in on:
            for d in ((1, 0), (0, 1), (1, 1)):
                if (x + d[0], y + d[1]) not in on:
                    q[x + d[0], y + d[1]] = tuple(outline[:3]) + (255,)
        for x, y in on:
            q[x, y] = tuple(fill[:3]) + (255,)
        return out
    mid = (min(ls) + max(ls)) / 2
    for y in range(img.height):
        for x in range(img.width):
            if px[x, y][3]:
                px[x, y] = tuple((fill if lum(px[x, y]) > mid else outline)[:3]) + (255,)
    return img


def add_ring(img, colors):
    """one more outline ring around the lettering, its colour going down the rows
    through colors (the orange rim of decorated titles)"""
    out = Image.new('RGBA', (img.width + 2, img.height + 2), (0, 0, 0, 0))
    out.alpha_composite(img, (1, 1))
    src, q = out.copy().load(), out.load()
    for y in range(out.height):
        c = colors[min(len(colors) - 1, y * len(colors) // out.height)]
        c = c if isinstance(c, tuple) else tuple(c)
        for x in range(out.width):
            if src[x, y][3]:
                continue
            if any(0 <= x + dx < out.width and 0 <= y + dy < out.height and src[x + dx, y + dy][3]
                   for dx in (-1, 0, 1) for dy in (-1, 0, 1)):
                q[x, y] = tuple(c[:3]) + (255,)
    return out


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


def row_fills(img, box, skip_white=False):
    """for each row of the box: its most common bright colour (the letter fill)"""
    x0, y0, x1, y1 = box
    px = img.load()
    out = []
    for y in range(y0, y1):
        cols = Counter(px[x, y] for x in range(x0, x1) if px[x, y][3] > 200 and lum(px[x, y]) > 90
                       and not (skip_white and min(px[x, y][:3]) > 235))
        if cols:
            out.append(cols.most_common(1)[0][0])
    return out


def regrade(t, fills, outline):
    """repaint the light part of rendered text with the original's top-to-bottom colours"""
    if not fills:
        return t
    px = t.load()
    ol = tuple(outline[:3])
    rows = [y for y in range(t.height) if any(px[x, y][3] and px[x, y][:3] != ol for x in range(t.width))]
    if not rows:
        return t
    top, bot = rows[0], rows[-1]
    for y in range(t.height):
        f = fills[min(len(fills) - 1, int((y - top) / max(1, bot - top + 1) * len(fills)))] if top <= y <= bot else None
        for x in range(t.width):
            c = px[x, y]
            if c[3] and c[:3] != ol and f is not None:
                k = lum(c) / 255.0
                px[x, y] = tuple(int(f[i] * (0.75 + 0.25 * k)) for i in range(3)) + (c[3],)
    return t


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


LIGHT = [None]
DARK = [None]
SOFT = [False]   # tinted white lettering (coloured frames)    # outline colour of the original lettering   # luminance threshold for non-white lettering (set per image)


def is_white(c):
    if LIGHT[0] is not None:
        return lum(c) >= LIGHT[0]
    if SOFT[0]:
        return min(c) > 200 and lum(c) > 222
    return min(c) > 228 and max(c) - min(c) < 24


def auto_box(img, pad, band=0):
    """bounding box of the light, unsaturated pixels (white lettering), plus its outline"""
    px = img.load()
    xs, ys = [], []
    def lit(x, y):
        return 0 <= x < img.width and 0 <= y < img.height and px[x, y][3] > 200 and is_white(px[x, y][:3])
    for y in range(band, img.height):
        for x in range(img.width):
            # lettering strokes, not lone sparkles: at least 2 lit neighbours
            if lit(x, y) and sum(lit(x + dx, y + dy) for dx in (-1, 0, 1) for dy in (-1, 0, 1) if dx or dy) >= 2:
                xs.append(x); ys.append(y)
    if not xs:
        return [0, 0, img.width, img.height]
    return [max(min(xs) - pad, 0), max(min(ys) - pad, 0), min(max(xs) + 1 + pad, img.width), min(max(ys) + 1 + pad, img.height)]


def text_mask(img, box, shade=None, dark=None):
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
                    if a > 200 and (max(r, g, b) < 40 or (shade is not None and (r, g, b, a) == shade)
                                    or (dark is not None and abs(lum((r, g, b)) - lum(dark)) < 18 and lum((r, g, b)) < 90)):
                        grow.add(q)
        mask |= grow
    return mask


def erase(img, box, mode, shade=None):
    x0, y0, x1, y1 = box
    px = img.load()
    if mode == 'none':
        return
    if mode == 'clear':
        for y in range(y0, y1):
            for x in range(x0, x1):
                px[x, y] = (0, 0, 0, 0)
        return
    if mode == 'mask-fill':
        mask = text_mask(img, box, shade, DARK[0])
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


def gfont_mask(text, sp, cap):
    """letter bodies (no outline) of a game font, scaled up by `px`"""
    font = FONT_CACHE.get(sp['gfont']) or FONT_CACHE.setdefault(sp['gfont'], Font(sp['gfont']))
    if '!' in text and not font.render('!').getbbox():   # some pixel fonts have no '!': draw one
        parts = text.split('!')
        ms = [gfont_mask(p_, dict(sp, px=1), cap) if p_.strip() else None for p_ in parts]
        h = max(m_.height for m_ in ms if m_ is not None)
        bang = Image.new('L', (2, h), 255)
        bang.paste(0, (0, h - 3, 2, h - 2))
        pieces = []
        for i, m_ in enumerate(ms):
            if m_ is not None:
                pieces.append((m_, 0 if not parts[i].endswith(' ') else 3))
            if i < len(ms) - 1:
                pieces.append((bang, 0))
        W = sum(m_.width + 1 + extra for m_, extra in pieces)
        m = Image.new('L', (W, h), 0)
        x = 0
        for m_, extra in pieces:
            m.paste(m_, (x, h - m_.height))
            x += m_.width + 1 + extra
        k = sp.get('px', 1)
        return m.resize((m.width * k, m.height * k), Image.NEAREST) if k != 1 else m
    t = font.render(text, sp.get('spacing', 0))
    px = t.load()
    cols = [px[x, y] for x in range(t.width) for y in range(t.height) if px[x, y][3]]
    hi = max(lum(c) for c in cols)
    m = Image.new('L', t.size, 0)
    mp = m.load()
    for y in range(t.height):
        for x in range(t.width):
            if px[x, y][3] > 128 and lum(px[x, y]) > min(70, hi * 0.6):
                mp[x, y] = 255
    m = m.crop(m.getbbox())
    k = sp.get('px', 1)
    return m.resize((m.width * k, m.height * k), Image.NEAREST) if k != 1 else m


def ttf_mask(text, sp, cap):
    """letter bodies of a system font (no anti-aliasing) whose capitals are `cap` pixels tall"""
    from PIL import ImageFont, ImageDraw
    if 'gfont' in sp:
        return gfont_mask(text, sp, cap)
    path = os.path.join(os.environ.get('WINDIR', r'C:\Windows'), 'Fonts', sp['ttf'])
    k = sp.get('px', 1)   # chunky pixels: draw small, scale up
    cap = max(4, round(cap / k))
    size = cap
    for _ in range(40):
        f = ImageFont.truetype(path, size)
        if sp.get('var'):
            f.set_variation_by_name(sp['var'])
        bb = f.getbbox('НЕ')
        if bb[3] - bb[1] >= cap:
            break
        size += 1
    top = f.getbbox('Н')[1]
    w = int(f.getlength(text)) + 8
    m = Image.new('L', (w, cap + size), 0)
    d = ImageDraw.Draw(m)
    d.fontmode = '1'
    d.text((4, -top), text, font=f, fill=255, spacing=0)
    bb = m.getbbox()
    m = m.crop(bb) if bb else m
    sq = sp.get('squeeze', 1)
    if sq != 1:
        m = m.resize((max(1, round(m.width * sq)), m.height), Image.NEAREST)
    if k != 1:
        m = m.resize((m.width * k, m.height * k), Image.NEAREST)
    return m


def ttf_text(text, sp, cap, fills, outline, ow):
    """system-font lettering painted like the original: row colours + dark outline"""
    m = ttf_mask(text, sp, cap)
    W, H = m.width + 2 * ow, m.height + 2 * ow + sp.get('drop', 0)
    out = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    mp, o = m.load(), out.load()
    body = {(x + ow, y + ow) for x in range(m.width) for y in range(m.height) if mp[x, y]}
    ol = tuple(outline[:3]) + (255,)
    drop = sp.get('drop', 0)
    for (x, y) in body:
        for dx in range(-ow, ow + 1):
            for dy in range(-ow, ow + 1 + drop):
                if 0 <= x + dx < W and 0 <= y + dy < H:
                    o[x + dx, y + dy] = ol
    n = len(fills)
    for (x, y) in body:
        t = (y - ow) / max(1, m.height)
        o[x, y] = tuple(fills[min(n - 1, int(t * n))][:3]) + (255,)
    return out


def add_glow(t, color, r, peak):
    """soft halo around the lettering, like the original's"""
    from PIL import ImageFilter
    a = t.getchannel('A').point(lambda v: 255 if v else 0)
    pad = Image.new('L', (t.width + 2 * r, t.height + 2 * r), 0)
    pad.paste(a, (r, r))
    halo = pad.filter(ImageFilter.MaxFilter(3)).filter(ImageFilter.GaussianBlur(r / 2))
    halo = halo.point(lambda v: min(peak, v * peak // 128))
    out = Image.new('RGBA', pad.size, tuple(color[:3]) + (0,))
    out.putalpha(halo)
    out.alpha_composite(t, (r, r))
    return out


def build_ttf(name, sp, src, img, out_dir):
    """the whole caption redrawn: clear the lettering box, draw a system font in its colours"""
    band = sp.get('band', 0)
    box = sp.get('box')
    if not box:
        box = list(src.crop((0, band, src.width, src.height)).getbbox())
        box[1] += band; box[3] += band
    lines = sp['text'].split('|')
    orig_lines = sp.get('orig_lines', len(lines))
    allf = row_fills(src, box, sp.get('skip_white')) if not sp.get('fills') else [hexcol(c) for c in sp['fills']]
    per = max(1, len(allf) // orig_lines)
    fills = allf[:per] if not sp.get('fills') else allf
    _, dark = text_colors(src, box)
    outline = hexcol(sp['outline']) if sp.get('outline') else dark
    ow = sp.get('ow', 1)
    cap = sp.get('cap') or max(6, per)
    glow = None
    if sp.get('glow'):
        semi = Counter(c[:3] for c in (src.get_flattened_data() if hasattr(src, 'get_flattened_data') else src.getdata()) if 0 < c[3] < 200)
        glow = (semi.most_common(1)[0][0] if semi else (255, 255, 255), sp['glow'], sp.get('glow_peak', 110))
    x0, y0, x1, y1 = box
    px = img.load()
    if sp.get('erase', 'clear') == 'clear':
        for y in range(y0, y1):
            for x in range(x0, x1):
                px[x, y] = (0, 0, 0, 0)
    elif sp['erase'] == 'clone':
        if not clone_erase(img, box, sp.get('cols')):
            inpaint_rows(img, box)
    else:
        erase(img, box, sp['erase'])
    if sp.get('tbox'):   # where the new caption goes, when it differs from the erased area
        x0, y0, x1, y1 = sp['tbox']
    maxw = (sp.get('fit') == 'image' and src.width - 2) or (x1 - x0)
    while True:
        rendered = [ttf_text(ln, sp, cap, fills, outline, ow) for ln in lines]
        if glow:
            rendered = [add_glow(t, *glow) for t in rendered]
        if max(t.width for t in rendered) <= maxw + (2 * glow[1] if glow else 0):
            break
        if 'gfont' in sp:   # the pixel font is too wide: tighter, then a condensed system font
            if sp.get('spacing', 0) > -1:
                sp['spacing'] = -1
                continue
            cap = rendered[0].height - 2 * ow - sp.get('drop', 0)
            sp = dict(sp, ttf='bahnschrift.ttf', var='Bold Condensed')
            del sp['gfont']
            continue
        if sp.get('squeeze', 1) > 0.72:
            sp['squeeze'] = round(sp.get('squeeze', 1) - 0.04, 2)
        elif cap > 6:
            cap -= 1
        else:
            break
    gap = sp.get('gap', 0)
    th = sum(t.height for t in rendered) + gap * (len(rendered) - 1)
    y = int(round((y0 + y1) / 2 - th / 2)) + sp.get('dy', 0)
    if sp.get('texture'):
        # the old letters' own texture: what differs from the cleaned background and is not outline
        bgp, sp_ = img.load(), src.load()
        tex = {(x, yy) for yy in range(src.height) for x in range(src.width)
               if sp_[x, yy][3] > 200 and lum(sp_[x, yy]) > 60
               and sum(abs(sp_[x, yy][i] - bgp[x, yy][i]) for i in range(3)) > 60}
    for t in rendered:
        x = (x0 + x1 - t.width) // 2 + sp.get('dx', 0)
        if sp.get('texture'):
            tp = t.load()
            for ty in range(t.height):
                for tx in range(t.width):
                    c = tp[tx, ty]
                    if not c[3] or c[:3] == tuple(outline[:3]):
                        continue
                    X, Y = x + tx, y + ty
                    for d in range(0, 16):
                        q = (X - d, Y) if (X - d, Y) in tex else (X + d, Y) if (X + d, Y) in tex else None
                        if q:
                            tp[tx, ty] = sp_[q][:3] + (255,)
                            break
        img.alpha_composite(t, (max(0, x), max(0, y)))
        y += t.height + gap
    img.save(os.path.join(out_dir, name))


def row_modes(img, y0, y1):
    """most common body colour of each row (no white lettering, no outline black)"""
    px = img.load()
    out = {}
    for y in range(y0, y1):
        c = Counter(px[x, y] for x in range(img.width)
                    if px[x, y][3] > 200 and not is_white(px[x, y][:3]) and max(px[x, y][:3]) >= 40)
        out[y] = c.most_common(1)[0][0] if c else None
    return out


def near(a, b, tol=40):
    return a is not None and b is not None and sum(abs(a[i] - b[i]) for i in range(3)) <= tol


def clean_column(img, x, step, y0, y1, limit, modes=None):
    """nearest column from x (moving by step) that shows only the button body between y0 and y1"""
    px = img.load()
    modes = modes or row_modes(img, y0, y1)
    start = x
    while 0 <= x < img.width and x != limit and abs(x - start) <= 6:   # never borrow from a neighbour
        col = [px[x, y] for y in range(y0, y1)]
        if all(c[3] > 200 and not is_white(c[:3]) and max(c[:3]) >= 40 for c in col):
            # icons are not body: most of the column must look like its rows
            good = sum(near(px[x, y], modes[y], 60) for y in range(y0, y1))
            if good >= 0.7 * (y1 - y0):
                return x
        x += step
    return None


def clone_erase(img, box, cols=None):
    """repaint the lettering box row by row from clean body columns left and right of it
    (blended across), so the button's own vertical shading comes back exactly"""
    x0, y0, x1, y1 = box
    px = img.load()
    # the columns must be clean in the rows that hold the lettering (borders may differ above/below)
    if cols:
        xl, xr = cols
    else:
        xl = clean_column(img, x0 - 1, -1, y0, y1, -1)
        xr = clean_column(img, x1, 1, y0, y1, img.width)
    if xl is None and xr is None:
        return False
    # one clean side is enough: copy it across the whole box
    lo = xl if xl is not None else x0 - 1
    hi = xr if xr is not None else x1
    xl = xr if xl is None else xl
    xr = xl if xr is None else xr
    def ref(x, y):
        # a lone sparkle in the reference column would become a stripe: take its neighbours instead
        c = px[x, y]
        if 0 < y < img.height - 1:
            u, d = px[x, y - 1], px[x, y + 1]
            if not near(c, u, 90) and not near(c, d, 90) and near(u, d, 60):
                return u
        return c
    for y in range(y0, y1):
        a, b = ref(xl, y), ref(xr, y)
        if cols:   # explicit columns sit inside the caption area: a lone speck there goes too
            px[xl, y], px[xr, y] = a, b
        for x in range(lo + 1, hi):
            t = (x - lo) / max(1, hi - lo)
            px[x, y] = tuple(int(round(a[i] + (b[i] - a[i]) * t)) for i in range(4)) if a != b else a
    return True


def inpaint_rows(img, box):
    """only the lettering pixels (white, its outline and shade) are replaced, each run in a row
    blended between the body pixels just left and right of it; gradients and icons stay"""
    x0, y0, x1, y1 = box
    px = img.load()
    shade = shadow_color(img, box)
    mask = text_mask(img, box, shade, DARK[0])
    # light shading next to the letters belongs to them too
    for _ in range(2):
        grow = set()
        for (x, y) in mask:
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                q = (x + dx, y + dy)
                if q not in mask and x0 <= q[0] < x1 and y0 <= q[1] < y1 and px[q][3] > 200 and lum(px[q]) > 160:
                    grow.add(q)
        mask |= grow
    for y in range(y0, y1):
        x = x0
        while x < x1:
            if (x, y) not in mask:
                x += 1
                continue
            s_ = x
            while x < x1 and (x, y) in mask:
                x += 1
            l = px[s_ - 1, y] if s_ > 0 else None
            r = px[x, y] if x < img.width else None
            l = l or r
            r = r or l
            if l is None:
                continue
            for k in range(s_, x):
                t = (k - s_ + 1) / (x - s_ + 1)
                px[k, y] = tuple(int(round(l[i] + (r[i] - l[i]) * t)) for i in range(4))


def tint(t, fill, shade, outline):
    """font colours -> the original lettering's colours (white body, shade, dark outline)"""
    px = t.load()
    for y in range(t.height):
        for x in range(t.width):
            c = px[x, y]
            if not c[3]:
                continue
            if is_white_font(c):
                n = fill
            elif lum(c) < 60:
                n = outline
            else:
                n = shade
            if n is not None:
                px[x, y] = tuple(n[:3]) + (c[3],)
    return t


def is_white_font(c):
    return min(c[:3]) > 225


def emboss(t, outl, dark):
    """drop the outline, put a dark copy of the letters 1px right and down"""
    px = t.load()
    body = [(x, y) for y in range(t.height) for x in range(t.width)
            if px[x, y][3] and px[x, y][:3] != tuple(outl[:3])]
    out = Image.new('RGBA', (t.width + 1, t.height + 1), (0, 0, 0, 0))
    o = out.load()
    for (x, y) in body:
        o[x + 1, y + 1] = tuple(dark[:3]) + (255,)
    for (x, y) in body:
        o[x, y] = px[x, y]
    return out


def build_button(name, sp, src, img, out_dir, save=True):
    """button caption: clone the body over the old lettering, set the game's own button font on top"""
    if sp.get('clip'):
        cx0, cy0, cx1, cy1 = sp['clip']
        part = src.crop((cx0, cy0, cx1, cy1))
        b_ = auto_box(part, 0)
        wb = [b_[0] + cx0, b_[1] + cy0, b_[2] + cx0, b_[3] + cy0]
    else:
        wb = sp.get('wbox') or auto_box(src, 0, sp.get('band', 0))
    x0, y0, x1, y1 = wb
    # lettering = white strokes + 1px outline + 1px shade below
    box = [max(x0 - 2, 0), max(y0 - 2, 0), min(x1 + 2, src.width), min(y1 + 3, src.height)]
    if sp.get('box'):
        box = sp['box']
    # original colours: shade under the white, outline around it
    px = src.load()
    shade = Counter(px[x, y + 1] for x in range(x0, x1) for y in range(y0, y1)
                    if is_white(px[x, y][:3]) and y + 1 < src.height and not is_white(px[x, y + 1][:3])
                    and lum(px[x, y + 1]) > 110).most_common(1)
    shade = shade[0][0] if shade else None
    # outline = what sits right beside the white strokes, left and right
    outl = Counter(px[x + d, y] for x in range(x0, x1) for y in range(y0, y1) for d in (-1, 1)
                   if is_white(px[x, y][:3]) and 0 <= x + d < src.width and px[x + d, y][3] > 200
                   and not is_white(px[x + d, y][:3]) and lum(px[x + d, y]) < 110).most_common(1)
    outl = outl[0][0] if outl else (0, 0, 0, 255)
    if sp.get('outline'):
        outl = hexcol(sp['outline'])
    DARK[0] = outl
    if sp.get('erase') == 'inpaint' or not clone_erase(img, box, sp.get('cols')):
        inpaint_rows(img, box)
    fill = hexcol(sp['fill']) if sp.get('fill') and sp['fill'] != 'auto' else None
    if sp.get('fill') == 'auto':
        fill = text_colors(src, wb)[0]
    if sp.get('shade'):
        shade = hexcol(sp['shade'])
    lines = sp['text'].split('|')
    maxw = (sp.get('maxw') or (src.width - 4))
    mixed = any(ch.islower() for ch in sp['text'])
    tries = ([(f, sp_) for f in sp['fonts'] for sp_ in (0, -1)] if 'fonts' in sp else
             [(sp['font'], sp.get('spacing', 0))] if 'font' in sp else
             [(472, 0), (472, -1), (109, 0), (109, -1), (75, 0), (75, -1)] if mixed and sp.get('size') != 'small' else
             [(109, 0), (109, -1), (75, 0), (75, -1)] if mixed else
             [(309, 0), (309, -1), (309, -2), (109, 0), (109, -1), (75, -1)])
    for fid, spacing in tries:
        font = FONT_CACHE.get(fid) or FONT_CACHE.setdefault(fid, Font(fid))
        rendered = [font.render(ln, spacing) for ln in lines]
        if max(t.width for t in rendered) * sp.get('px', 1) <= maxw:
            break
    rendered = [tint(t, fill, shade, outl) for t in rendered]
    if sp.get('px', 1) > 1:
        k = sp['px']
        rendered = [t.resize((t.width * k, t.height * k), Image.NEAREST) for t in rendered]
    if sp.get('style') == 'shadow':
        # embossed lettering: no outline, a dark copy 1px right and down
        dark = Counter(px[x, y] for x in range(box[0], box[2]) for y in range(box[1], box[3])
                       if px[x, y][3] > 200 and lum(px[x, y]) < 45).most_common(1)
        dark = dark[0][0] if dark else (0, 0, 0, 255)
        rendered = [emboss(t, outl, dark) for t in rendered]
    gap = sp.get('gap', 0)
    th = sum(t.height for t in rendered) + gap * (len(rendered) - 1)
    # the white of the new caption sits where the old white was (outline 1px above it)
    cy = (y0 - 1 + y1 + 2) / 2
    y = int(round(cy - th / 2)) + sp.get('dy', 0)
    cx = (x0 + x1) / 2 if not sp.get('center_image') else src.width / 2
    for t in rendered:
        x = int(round(cx - t.width / 2)) + sp.get('dx', 0)
        img.alpha_composite(t, (max(0, x), max(0, y)))
        y += t.height + gap
    if save:
        img.save(os.path.join(out_dir, name))


def flat_fill(img, rect, limit=110, lo=12):
    """paint a rectangle of a flat panel with each row's own panel colour; rows the lettering
    covers more than half of take the colour of the nearest clean row"""
    x0, y0, x1, y1 = rect
    px = img.load()
    # the panel's own colour: rows are clean only when their colour is near it (not an outline)
    allc = Counter(px[x, y] for y in range(y0, y1) for x in range(x0, x1)
                   if px[x, y][3] > 100 and lo < lum(px[x, y]) < limit)
    panel = allc.most_common(1)[0][0] if allc else None
    modes = {}
    for y in range(y0, y1):
        # the panel is dark (often semi-transparent), the lettering light with a dark outline
        body = Counter(px[x, y] for x in range(x0, x1) if px[x, y][3] > 100 and lo < lum(px[x, y]) < limit)
        if body:
            m = body.most_common(1)[0][0]
            n = sum(k for c, k in body.items() if near(c, m, 24))   # noisy panels
            if n >= (x1 - x0) / 2 and (panel is None or near(m, panel, 60)):
                modes[y] = m
    if not modes:
        modes = {y0: panel} if panel else {}
    if not modes:
        return
    for y in range(y0, y1):
        m = modes[min(modes, key=lambda r: abs(r - y))]
        for x in range(x0, x1):
            px[x, y] = m


def text_fill(img, rect, limit=110, anysat=False, dark_lum=60, ranges=None, dark_r=1):
    """repaint only the lettering inside rect (light pixels and the dark outline touching
    them) with each row's panel colour; whatever else is there stays"""
    x0, y0, x1, y1 = rect
    px = img.load()
    if ranges:   # the lettering's colours given as [r0, r1, g0, g1, b0, b1] boxes (text over sprites)
        light = {(x, y) for y in range(y0, y1) for x in range(x0, x1)
                 if any(all(q[2 * i] <= px[x, y][i] <= q[2 * i + 1] for i in range(3)) for q in ranges)}
    else:
        light = {(x, y) for y in range(y0, y1) for x in range(x0, x1)
                 if px[x, y][3] > 100 and lum(px[x, y]) > 140 and (anysat or max(px[x, y][:3]) - min(px[x, y][:3]) < 60)}
    dark = {(x + dx, y + dy) for x, y in light for dx in range(-dark_r, dark_r + 1) for dy in range(-dark_r, dark_r + 1)
            if x0 <= x + dx < x1 and y0 <= y + dy < y1 and lum(px[x + dx, y + dy]) < dark_lum}
    for y in range(y0, y1):
        row = Counter(px[x, y] for x in range(x0, x1) if lum(px[x, y]) < limit and (x, y) not in dark)
        if not row:
            continue
        m = row.most_common(1)[0][0]
        for x in range(x0, x1):
            if (x, y) in light or (x, y) in dark:
                px[x, y] = m


def drop_outline(t):
    """the font's dark outline off: panel captions are plain letters"""
    px = t.load()
    cols = [px[x, y] for y in range(t.height) for x in range(t.width) if px[x, y][3]]
    if not cols:
        return t
    lo = min(lum(c) for c in cols)
    for y in range(t.height):
        for x in range(t.width):
            if px[x, y][3] and lum(px[x, y]) < lo + 40:
                px[x, y] = (0, 0, 0, 0)
    return t


def erase_known(img, t, fid, region, limit=110, at=None):
    """erase exactly the pixels of English text t drawn in font fid somewhere inside region:
    the rendered line (letters + the font's own outline) is matched by its light pixels,
    then every pixel it covers takes its row's panel colour"""
    font = FONT_CACHE.get(fid) or FONT_CACHE.setdefault(fid, Font(fid))
    r = font.render(t)
    rp = r.load()
    mask = [(x, y) for x in range(r.width) for y in range(r.height) if rp[x, y][3]]
    light = [(x, y) for x, y in mask if lum(rp[x, y]) > 140]
    px = img.load()
    x0, y0, x1, y1 = region
    best = (0, at[0], at[1]) if at else None
    for oy in ([] if at else range(y0, y1 - r.height + 1)):
        for ox in range(x0, x1 - r.width + 1):
            n = sum(1 for x, y in light if lum(px[ox + x, oy + y]) > 140)
            if best is None or n > best[0]:
                best = (n, ox, oy)
    if not best:
        return
    _, ox, oy = best
    cover = {(ox + x, oy + y) for x, y in mask}
    # the game may add its own dark rim around the line: dark pixels touching it go too
    for _ in range(2):
        cover |= {(x + dx, y + dy) for x, y in cover for dx in (-1, 0, 1) for dy in (-1, 0, 1)
                  if 0 <= x + dx < img.width and 0 <= y + dy < img.height and lum(px[x + dx, y + dy]) < 45}
    for y in sorted({y for _, y in cover}):
        row = Counter(px[x, y] for x in range(x0, x1) if (x, y) not in cover and 12 < lum(px[x, y]) < limit)
        if row:
            m = row.most_common(1)[0][0]
            for x in range(x0, x1):
                if (x, y) in cover:
                    px[x, y] = m


def draw_runs(img, src, p):
    """lines made of differently coloured pieces and icons cut from the original:
    "runs": [[{"t": "text", "fill": "#rrggbb"}, {"icon": [x0, y0, x1, y1]}, ...], ...]"""
    x0, y0, x1, y1 = p['box']
    outl = hexcol(p.get('outline', '#000000'))
    space = None

    def build(fid, spacing):
        nonlocal space
        font = FONT_CACHE.get(fid) or FONT_CACHE.setdefault(fid, Font(fid))
        space = font.glyphs[' '][7] + spacing
        out = []
        for line in p['runs']:
            pieces = []
            for r in line:
                if 'icon' in r:
                    pieces.append((src.crop(tuple(r['icon'])), 'icon'))
                    continue
                t = r['t']
                lead, trail = len(t) - len(t.lstrip(' ')), len(t) - len(t.rstrip(' '))
                im = font.render(t.strip(' '), spacing, crop_y=False) if t.strip(' ') else Image.new('RGBA', (0, 1))
                if p.get('px', 1) > 1:
                    im = im.resize((im.width * p['px'], im.height * p['px']), Image.NEAREST)
                im = two_tone(im, hexcol(r.get('fill', p.get('fill', '#ffffff'))), outl) if im.width else im
                pieces.append((im, (lead, trail, r.get('uline'), hexcol(r.get('fill', p.get('fill', '#ffffff'))), r.get('dx', 0))))
            boxes = [im.getbbox() for im, sp in pieces if sp != 'icon' and im.width and im.getbbox()]
            if boxes:   # one vertical crop for the whole line keeps the baseline
                t0, t1 = min(b[1] for b in boxes), max(b[3] for b in boxes)
                pieces = [(im.crop((0, t0, im.width, t1)) if sp != 'icon' and im.width else im, sp)
                          for im, sp in pieces]
            w = sum(im.width + (space * (sp[0] + sp[1]) + sp[4] if sp != 'icon' else 1) for im, sp in pieces)
            out.append((pieces, w))
        return out

    tries = [(f, s) for f in p.get('fonts', [475]) for s in (0, -1)]
    for fid, spacing in tries:
        lines = build(fid, spacing)
        if max(w for _, w in lines) <= x1 - x0 + 2:
            break
    if spacing < 0:
        print(f'  runs squeezed to fit (font {fid}, spacing {spacing})')
    lh = [max(im.height for im, _ in pieces) for pieces, _ in lines]
    gap = p.get('gap', 2)
    y = int(round((y0 + y1) / 2 - (sum(lh) + gap * (len(lh) - 1)) / 2)) + p.get('dy', 0)
    for (pieces, w), h in zip(lines, lh):
        x = x0 if p.get('align') == 'left' else (x0 + x1 - w) // 2
        for im, sp in pieces:
            if sp == 'icon':
                img.alpha_composite(im, (x, y + (h - im.height) // 2))
                x += im.width + 1
                continue
            x += space * sp[0] + sp[4]   # dx: a pixel or two of air before a piece
            if im.width:
                img.alpha_composite(im, (x, y + (h - im.height) // 2))
                if sp[2]:   # an underlined piece ("all the time"), in its own colour
                    bb = im.getbbox()
                    for ux in range(x + bb[0], x + bb[2]):
                        img.putpixel((ux, y + (h - im.height) // 2 + bb[3] + sp[2] - 1), tuple(sp[3][:3]) + (255,))
            x += im.width + space * sp[1]
        y += h + gap


def build_panel(name, sp, src, img, out_dir):
    """plain text on a flat panel: rows refilled with the panel colour, game font in the old colours"""
    base = {k: v for k, v in sp.items() if k != 'parts'}
    parts = [dict(base, **p) for p in sp.get('parts', [{}])]
    for p in parts:   # English lines known exactly: erased pixel for pixel
        for k in p.get('orig_text', []):
            at = k.get('at')
            region = k.get('region') or [at[0] - 2, at[1] - 2, img.width, img.height]
            erase_known(img, k['t'], k['font'], region, p.get('limit', 110), at)
    clean = img.copy()   # icons inside text are cut from here: no English letters touch them
    for p in parts:   # erase everything first: parts may share rows
        for r in p.get('clear', [p['box']]):
            mode = r[4] if len(r) > 4 else p.get('erase')   # a rect may name its own erase mode
            r5, r = r, r[:4]
            if p.get('bg'):   # plain ground of one known colour
                px = img.load()
                for yy in range(r[1], r[3]):
                    for xx in range(r[0], r[2]):
                        px[xx, yy] = hexcol(p['bg'])
            elif mode == 'flat':
                flat_fill(img, r, p.get('limit', 110), p.get('lo', 12))
            elif mode == 'clear':   # text on transparent ground
                erase(img, r, 'clear')
            elif mode == 'interp':   # ground shaded both ways: lettering (very light or very dark)
                px = img.load()          # filled in from the ground on its left and right
                for yy in range(r[1], r[3]):
                    row = [px[xx, yy] for xx in range(r[0], r[2])]
                    txt = [lum(c) > p.get('limit', 200) or lum(c) < p.get('lo', 30) for c in row]
                    good = [i for i, t in enumerate(txt) if not t]
                    for i, t in enumerate(txt):
                        if not t or not good:
                            continue
                        lft = max((g for g in good if g < i), default=None)
                        rgt = min((g for g in good if g > i), default=None)
                        a_, b_ = row[lft if lft is not None else rgt], row[rgt if rgt is not None else lft]
                        k = 0.5 if lft is None or rgt is None else (i - lft) / (rgt - lft)
                        px[r[0] + i, yy] = tuple(round(a_[j] + (b_[j] - a_[j]) * k) for j in range(3)) + (255,)
            elif mode == 'edge':   # gradient ground: each row takes the colour of its left edge
                px = img.load()
                for yy in range(r[1], r[3]):
                    for xx in range(r[0] + 1, r[2]):
                        px[xx, yy] = px[r[0], yy]
            elif mode == 'text':   # sprites over the text: only its own pixels go
                text_fill(img, r, p.get('limit', 110), p.get('anysat', False), p.get('dark_lum', 60),
                          r5[5] if len(r5) > 5 else None, p.get('dark_r', 1))
            else:
                flat_fill(img, r, p.get('limit', 110), p.get('lo', 12))
    for p in parts:
        if 'runs' in p:
            draw_runs(img, clean, p)
            continue
        x0, y0, x1, y1 = p['box']
        lines = p['text'].split('|')
        allf = row_fills(src, p.get('cbox', p['box'])) if not p.get('fill') else [hexcol(p['fill'])]
        allf = allf or [hexcol('#ffffff')]   # no lettering found to take colours from
        if p.get('fill'):
            fills = allf
        else:
            # one line of the original: the rows of its first lettering band
            per = max(1, len(allf) // p.get('orig_lines', len(lines)))
            fills = allf[:per]
        mixed = any(ch.islower() for ch in p['text'])
        tries = ([(f, s + p.get('spacing', 0)) for f in p['fonts'] for s in (0, -1)] if 'fonts' in p else
                 [(p['font'], p.get('spacing', 0))] if 'font' in p else
                 [(472, 0), (472, -1), (109, 0), (109, -1), (75, 0), (75, -1)] if mixed else
                 [(309, 0), (309, -1), (309, -2), (109, 0), (109, -1), (75, -1)])
        maxw = p.get('maxw', x1 - x0)
        for fid, spacing in tries:
            font = FONT_CACHE.get(fid) or FONT_CACHE.setdefault(fid, Font(fid))
            rendered = [font.render(ln, spacing) for ln in lines]
            if p.get('px', 1) > 1:   # chunky captions: a small font doubled, outline and all
                k = p['px']
                rendered = [t.resize((t.width * k, t.height * k), Image.NEAREST) for t in rendered]
            if max(t.width for t in rendered) <= maxw + 2:
                break
        if spacing < p.get('spacing', 0) and not p.get('tight'):   # squeezed letters read badly
            print(f'  {name}: "{lines[0]}..." squeezed to fit (font {fid}, spacing {spacing})')
        for t in rendered:
            if t.width > maxw + 2:
                print(f'  {name}: "{lines}" is {t.width}px wide, box {maxw}px')
        outl = (None if p.get('outline') == 'none' else text_colors(src, p['box'])[1] if p.get('outline') == 'auto'
                else hexcol(p.get('outline', '#000000')))
        out = []
        for t in rendered:
            if p.get('native'):   # the font's own colours (decorated caption fonts)
                out.append(t)
                continue
            if p.get('flat'):   # one fill colour, one outline colour, no shading
                if p.get('solid'):   # outline-less font: the whole glyph is the fill, outline around
                    t = add_ring(tint_all(t, fills[0]), [outl or (0, 0, 0, 255)])
                elif p.get('bodies'):   # the font's own shadow goes, a thin even outline instead
                    t = drop_outline(recolor(t, (255, 255, 255, 255), (0, 0, 0, 255)))
                    t = add_ring(tint_all(t, fills[0]), [outl or (0, 0, 0, 255)])
                else:
                    t = two_tone(t, fills[0], outl or (0, 0, 0, 255))
                for c in p.get('rings', []):   # whole rings one after another (outline, then glow)
                    t = add_ring(t, [hexcol(c)])
                out.append(add_ring(t, [hexcol(c) for c in p['ring']]) if p.get('ring') else t)
                continue
            t = recolor(t, (255, 255, 255, 255), outl or (0, 0, 0, 255))
            if not outl:
                t = drop_outline(t)
                bb = t.getbbox()
                t = t.crop(bb) if bb else t
            out.append(regrade(t, fills, outl or (0, 0, 0, 255)) if len(fills) > 1 else
                       recolor(t, fills[0], outl or fills[0]) if outl else tint_all(t, fills[0]))
        gap = p.get('gap', 2)
        th = sum(t.height for t in out) + gap * (len(out) - 1)
        y = int(round((y0 + y1) / 2 - th / 2)) + p.get('dy', 0)
        for t in out:
            if p.get('align') == 'left':
                x = x0 + p.get('dx', 0)
            elif p.get('align') == 'right':   # a number is drawn after it by the game
                x = x1 - t.width + p.get('dx', 0)
            else:
                x = (x0 + x1 - t.width) // 2 + p.get('dx', 0)
            img.alpha_composite(t, (max(0, x), max(0, y)))
            if p.get('uline'):   # underlined link-like words ("world 3")
                bb = t.getbbox()
                for ux in range(max(0, x + bb[0]), x + bb[2]):
                    img.putpixel((ux, y + bb[3] + p['uline'] - 1), tuple(fills[0][:3]) + (255,))
            y += t.height + gap
    for r in sp.get('restore', []):   # pieces of the original put back over the redraw (icons)
        img.paste(src.crop(tuple(r)), tuple(r[:2]))
    if sp.get('keep_mod'):   # lettering of the Russian mod's own image that looks fine:
        mod = Image.open(os.path.join(ROOT, 'work', 'modsrc', name)).convert('RGBA').load()
        org, px = src.load(), img.load()   # only its pixels far from the original ground
        for x0, y0, x1, y1 in sp['keep_mod']:
            for y in range(y0, y1):
                for x in range(x0, x1):
                    if sum(abs(a - b) for a, b in zip(mod[x, y], org[x, y])) > 90:
                        px[x, y] = mod[x, y]
    img.save(os.path.join(out_dir, name))


def tint_all(t, fill):
    px = t.load()
    for y in range(t.height):
        for x in range(t.width):
            if px[x, y][3]:
                px[x, y] = tuple(fill[:3]) + (px[x, y][3],)
    return t


BIG_FONTS = [(259, 0), (259, -1), (322, 0), (322, -1), (309, 0), (309, -1), (309, -2)]
AUTO_FONTS = [(309, 0), (309, -1), (309, -2), (109, 0), (109, -1), (75, -1)]
FONT_CACHE = {}


def build_one(name, sp, out_dir):
    LIGHT[0] = sp.get('light')
    SOFT[0] = sp.get('white') == 'soft'
    src = Image.open(os.path.join(GAME, 'data', name)).convert('RGBA')
    img = src.copy()
    if sp.get('mode') == 'button':
        if 'parts' not in sp:
            return build_button(name, sp, src, img, out_dir)
        base = {k: v for k, v in sp.items() if k != 'parts'}
        for part in sp['parts']:   # several captions on one picture
            q = dict(base, **part)
            LIGHT[0] = q.get('light')
            SOFT[0] = q.get('white') == 'soft'
            build_button(name, q, src, img, out_dir, save=False)
        return img.save(os.path.join(out_dir, name))
    if sp.get('mode') == 'panel':
        return build_panel(name, sp, src, img, out_dir)
    if 'ttf' in sp or 'gfont' in sp:
        return build_ttf(name, sp, src, img, out_dir)
    box = sp.get('box') or 'auto'
    if box == 'auto' and sp.get('erase') == 'clear':
        box = list(src.crop((0, sp.get('band', 0), src.width, src.height)).getbbox())
        box[1] += sp.get('band', 0); box[3] += sp.get('band', 0)
    elif box == 'auto':
        box = auto_box(src, sp.get('pad', 3), sp.get('band', 0))
        if sp.get('erase', 'rows-fill') == 'rows-fill':   # keep the button's own border
            box = [max(box[0], 1), max(box[1], 1), min(box[2], src.width - 1), min(box[3], src.height - 1)]
    light, dark = text_colors(src, box)
    # the outline colour helps the eraser only when it is not the background itself
    bx = src.crop(tuple(box)).convert('RGBA')
    common = Counter(bx.get_flattened_data() if hasattr(bx, "get_flattened_data") else bx.getdata()).most_common(1)[0][0]
    DARK[0] = dark if dark != common else None
    shade = shadow_color(src, box) if sp.get('erase') != 'clear' else None
    wb = auto_box(src, 0, sp.get('band', 0)) if sp.get('erase') != 'clear' else box
    fill = hexcol(sp['fill']) if sp.get('fill', 'auto') != 'auto' else light
    outline = hexcol(sp['outline']) if sp.get('outline', 'auto') != 'auto' else dark
    fills = None
    lines_n = len(sp.get('lines') or sp['text'].split('|'))
    if sp.get('colors') == 'rows':
        # one line of the original is enough to learn the colours
        allf = row_fills(src, box)
        orig_lines = sp.get('orig_lines', lines_n)
        fills = allf[:max(1, len(allf) // orig_lines)]
    erase(img, box, sp.get('erase', 'rows-fill'), shade)
    scale = sp.get('scale', 1)
    lines = sp.get('lines') or sp['text'].split('|')
    bw = box[2] - box[0] if sp.get('fit') != 'image' else src.width - 6
    # the first font/spacing whose widest line fits the box (bold outlined -> narrower)
    tries = [(sp['font'], sp.get('spacing', 0))] if 'font' in sp else (BIG_FONTS if sp.get('big') else AUTO_FONTS)
    if sp.get('big') == 'x2':
        tries = [(309, -2, 2), (322, 0, 1), (322, -1, 1)]
    for tr_ in tries:
        fid, spacing = tr_[0], tr_[1]
        big = tr_[2] if len(tr_) > 2 else 0
        font = FONT_CACHE.get(fid) or FONT_CACHE.setdefault(fid, Font(fid))
        rendered = []
        for ln in lines:
            if big > 1:
                t = big_letters(font, ln, spacing, big, fill, outline)
                if sp.get('colors') == 'rows':
                    t = regrade(t, fills, outline)
                rendered.append(t)
                continue
            t = recolor(font.render(ln, spacing), fill, outline)
            if shade and sp.get('shadow', True):
                t = add_shadow(t, fill, shade)
            if sp.get('colors') == 'rows':
                t = regrade(t, fills, outline)
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
    elif sp.get('valign') == 'bottom':
        y = min(wb[3] + 1, src.height) - th + sp.get('dy', 0)   # same baseline as the original
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
        defaults = spec.get('_defaults', {})
        for name, sp in spec.items():
            if name.startswith('_') or (only and name not in only):
                continue
            build_one(name, dict(defaults, **sp), out_dir)
        names = [k for k in spec if not k.startswith('_') and (not only or k in only)]
        print('built', len(names))
        preview(names, out_dir, os.path.join(ROOT, 'work', 'retext_preview.png'))


if __name__ == '__main__':
    main()
