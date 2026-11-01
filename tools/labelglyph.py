"""Captions the game draws as one special glyph of a font (e.g. font 259 '蒂' is the whole
"—Hat Rack Bonus Multi—" label): replaced by the Russian text in a game font, one colour.
Glyphs with icons or frames (PANELS) are redrawn by retext.py's panel builder instead.

  python labelglyph.py          (re-run after fontgen.py rewrites fonts/font-<ID>.*)

The glyph goes below the font's Cyrillic sheet with "replace": true (patcher/lib/fonts.js).
"""
import json
import os
import re
import sys

from PIL import Image

sys.path.insert(0, os.path.dirname(__file__))
import tempfile

from retext import Font, ROOT, GAME, lum, build_panel, hexcol   # noqa: E402
from modredo import detect_font   # noqa: E402

# (font id, glyph, text, text font, dash length each side or 0)
LABELS = [
    (259, '蒂', 'Множитель вешалки', 75, 12),
]

# (font id, glyph, canvas width or None, retext panel spec): the canvas grows to the right
PANELS = [
    (726, chr(47691), None, {'parts': [   # Halloween: "Keep IdleOn open for another" [time] [109 below]
        {'text': 'Держи IdleOn открытым ещё', 'box': [34, 4, 224, 21], 'clear': [[34, 6, 212, 22, 'flat'], [212, 9, 221, 12, 'flat'], [212, 12, 224, 20, 'flat'], [212, 6, 217, 9, 'flat']],
         'fonts': [475], 'align': 'left', 'flat': True, 'fill': '#ffda90', 'outline': 'auto', 'dy': 4}]}),
    (109, chr(50636), 132, {'erase': 'clear', 'parts': [   # ...[time] "for a FREE Play"
        {'runs': [[{'t': 'до ', 'fill': '#5fd8ff'}, {'t': 'БЕСПЛАТНОЙ игры', 'fill': '#c4f2ff'}]],
         'box': [0, 0, 132, 13], 'clear': [[0, 0, 132, 13]], 'fonts': [109], 'align': 'left'}]}),
    (750, chr(39178), None, {'erase': 'clear', 'parts': [   # tournament pet mart
        {'text': 'Любого питомца можно|обменять, отдав копию|и оставив копию себе!', 'box': [0, 9, 155, 53],
         'clear': [[0, 0, 155, 53]], 'fonts': [475], 'gap': 3, 'outline': 'none', 'cbox': [4, 12, 150, 22]}]}),
    (750, chr(36190), None, {'erase': 'clear', 'parts': [   # tournament: the chest icon stays
        {'text': 'Бонусы постоянные и|действуют на всех героев|вне турниров!', 'box': [52, 7, 224, 53],
         'clear': [[52, 0, 224, 55]], 'fonts': [475], 'gap': 3, 'outline': 'auto', 'cbox': [64, 10, 212, 22]}]}),
]


def orig_glyph(fid, ch):
    fnt = open(os.path.join(GAME, 'graphics', '1x', f'font-{fid}.fnt'), encoding='utf-8').read()
    m = re.search(r'<char [^>]*\bid="%d"[^>]*>' % ord(ch), fnt).group(0)
    g = {k: int(v) for k, v in re.findall(r'\b(x|y|width|height|yoffset)="(-?\d+)"', m)}
    sheet = Image.open(os.path.join(GAME, 'graphics', '1x', f'font-{fid}.png')).convert('RGBA')
    return sheet.crop((g['x'], g['y'], g['x'] + g['width'], g['y'] + g['height'])), g


def label(fid, ch, text, tfont, dash):
    old, g = orig_glyph(fid, ch)
    px = old.load()
    col = max((px[x, y] for y in range(old.height) for x in range(old.width) if px[x, y][3] > 200),
              key=lambda c: (lum(c), c))
    t = Font(str(tfont)).render(text)
    tp = t.load()
    ls = [lum(tp[x, y]) for y in range(t.height) for x in range(t.width) if tp[x, y][3] > 100]
    # the letter bodies only (the outline goes): the label is one flat colour like the original
    lo = min(ls) if max(ls) - min(ls) > 40 else -41   # a one-colour font is all body
    rows = [y for y in range(t.height) if any(tp[x, y][3] > 100 and lum(tp[x, y]) > lo + 40 for x in range(t.width))]
    y0, y1 = rows[0], rows[-1] + 1
    w = t.width + 2 * (dash + 3) if dash else t.width
    out = Image.new('RGBA', (w, max(old.height, y1 - y0)), (0, 0, 0, 0))
    op = out.load()
    ox = dash + 3 if dash else 0
    for y in range(y0, y1):
        for x in range(t.width):
            if tp[x, y][3] > 100 and lum(tp[x, y]) > lo + 40:
                op[ox + x, y - y0] = col
    if dash:   # "—" on both sides, on the middle row of the lowercase letters
        my = (out.height - 1) // 2 + 1
        for x in list(range(dash)) + list(range(w - dash, w)):
            op[x, my] = col
    return out, g


def panel(fid, ch, width, sp, height=None):
    old, g = orig_glyph(fid, ch)
    src = Image.new('RGBA', (width or old.width, height or old.height), (0, 0, 0, 0))
    src.paste(old, (0, 0))
    with tempfile.TemporaryDirectory() as tmp:
        build_panel('glyph.png', sp, src, src.copy(), tmp)
        out = Image.open(os.path.join(tmp, 'glyph.png')).convert('RGBA')
        out.load()
    return out, g


# small capitals of the game's caption fonts (2 px stems, 1 px bars) that no Cyrillic font has
PIX = {
    7: {'О': ['######', '##..##', '##..##', '##..##', '##..##', '##..##', '######'],
        'Т': ['######', '..##..', '..##..', '..##..', '..##..', '..##..', '..##..'],
        'К': ['##.##', '####.', '###..', '###..', '###..', '####.', '##.##'],
        'Р': ['#####.', '##..##', '##..##', '#####.', '##....', '##....', '##....'],
        'Ы': ['##.....##', '##.....##', '##.....##', '#####..##', '##..##.##', '##..##.##', '#####..##'],
        'И': ['##..##', '##..##', '##.###', '######', '###.##', '##..##', '##..##'],
        'Н': ['##..##', '##..##', '##..##', '######', '##..##', '##..##', '##..##'],
        'Ф': ['...##...', '########', '##.##.##', '##.##.##', '##.##.##', '########', '...##...']},
    6: {'С': ['#####', '##...', '##...', '##...', '##...', '#####'],
        'Л': ['..####', '.##.##', '.##.##', '.##.##', '.##.##', '##..##'],
        'Е': ['#####', '##...', '####.', '##...', '##...', '#####'],
        'Д': ['..####.', '.##.##.', '.##.##.', '.##.##.', '#######', '##...##'],
        '.': ['..', '..', '..', '..', '..', '##'],
        'Б': ['#####', '##...', '#####', '##.##', '##.##', '#####'],
        'Р': ['#####', '##.##', '##.##', '#####', '##...', '##...'],
        'О': ['######', '##..##', '##..##', '##..##', '##..##', '######']},
}


def text_mask(font, text, fit=False):
    """rows of 0/1 of the letter bodies of one line: a PIX size ('pix7') or a game font"""
    if str(font).startswith('pix'):
        h = int(font[3:])
        cols = []
        for ch in text:
            g = PIX[h][ch] if ch != ' ' else ['...'] * h
            if cols:
                cols.append([0] * h)
            cols += [[int(g[y][x] == '#') for y in range(h)] for x in range(len(g[0]))]
        return [[c[y] for c in cols] for y in range(h)]
    t = Font(str(font)).render(text)
    tp = t.load()
    ls = [lum(tp[x, y]) for y in range(t.height) for x in range(t.width) if tp[x, y][3] > 100]
    lo = min(ls) if max(ls) - min(ls) > 40 else -41
    m = [[int(tp[x, y][3] > 100 and lum(tp[x, y]) > lo + 40) for x in range(t.width)] for y in range(t.height)]
    rows = [y for y in range(t.height) if any(m[y])]
    m = m[rows[0]:rows[-1] + 1]
    xs = [x for x in range(t.width) if any(r[x] for r in m)]
    m = [r[xs[0]:xs[-1] + 1] for r in m]
    if not fit:
        return m
    # capitals only: Д, Ц, Щ feet go back into the capital height (they read as a stripe under the line)
    cnt = [sum(r) for r in m]
    core = [y for y in range(len(m)) if cnt[y] * 3 >= max(cnt)]
    c0, c1 = core[0], core[-1] + 1
    w = len(m[0])
    x = 0
    while x < w:
        if not any(r[x] for r in m):
            x += 1
            continue
        e = x
        while e < w and any(r[e] for r in m):
            e += 1
        ys = [y for y in range(len(m)) if any(m[y][x:e])]
        if ys[0] < c0 or ys[-1] >= c1:
            g = shrink_rows([r[x:e] for r in m[ys[0]:ys[-1] + 1]], c1 - c0)
            for y in range(len(m)):
                m[y][x:e] = g[y - c0] if c0 <= y < c1 else [0] * (e - x)
        x = e
    return m[c0:c1]


def shrink_rows(rows, h):
    """a letter squeezed to h rows by dropping the rows most like the one above, lowest first
    (Д keeps its long walls, a one-row base and one-row feet)"""
    rows = [r[:] for r in rows]
    while len(rows) > h:
        n = len(rows)
        i = min(range(1, n), key=lambda i: (sum(a != b for a, b in zip(rows[i], rows[i - 1])), -i))
        del rows[i]
    return rows


def draw_text(img, sp):
    ip = img.load()
    cx0, cy0, cx1, cy1 = sp.get('clip', [0, 0, img.width, img.height])

    def put(p, col):
        if cx0 <= p[0] < cx1 and cy0 <= p[1] < cy1:
            ip[p] = hexcol(col)
    body = {}   # (x, y) -> row index within its line, line height
    y = sp['y']
    for line in sp['text'].split('|'):
        m = text_mask(sp['font'], line, sp.get('fit', False))
        h, w = len(m), len(m[0])
        x = sp['x'] if 'x' in sp else round(sp['cx'] - w / 2)
        for r in range(h):
            for c in range(w):
                if m[r][c]:
                    body[(x + c, y + r)] = (r, h)
        y += h + sp.get('gap', 1)
    split = sp.get('split', 10 ** 6)
    rings = sorted(sp.get('rings', []))
    paint = {}
    if rings:
        rmax = rings[-1][0]
        k = int(rmax ** 0.5) + 1
        for (bx, by) in body:
            for dy in range(-k, k + 1):
                for dx in range(-k, k + 1):
                    d = dx * dx + dy * dy
                    p = (bx + dx, by + dy)
                    if d <= rmax and p not in body and d < paint.get(p, 10 ** 6):
                        paint[p] = d
    shape = set(body) | set(paint)
    if sp.get('shadow'):
        dx, dy, col, *bands = sp['shadow']
        for (x, y) in shape:
            p = (x + dx, y + dy)
            if p not in shape:
                put(p, ([c for y0, c in (bands[0] if bands else []) if p[1] >= y0] or [col])[-1])
    for p, d in paint.items():
        r = next(r for r in rings if d <= r[0])
        put(p, r[2] if len(r) > 2 and p[1] >= split else r[1])
    fills = sp.get('fills', ['#ffffff'])
    for p, (r, h) in body.items():
        put(p, fills[min(len(fills) - 1, r * len(fills) // h)])


def custom(fid, ch, sp):
    """retext/glyphs.json entry with "draw": "custom": the lettering is drawn here pixel by pixel.
      clear   [[x0, y0, x1, y1, mode]]: 'none' transparent, '#rrggbb', 'colN' each row from column N,
              'near:#c1,#c2' the nearest pixel of the row in one of these ground colours
      text, font ('pixN' or a font id), x (left) or cx (centre of each line), y (top of the bodies), gap
      fills   body colours top to bottom, stretched over the letter height
      rings   [[r², colour above split, colour from split]] outlines by squared distance, inner first
      shadow  [dx, dy, colour, [[from y, colour], ...]] behind everything, darker on lower bands
      clip    [x0, y0, x1, y1] nothing drawn outside
      parts   several such texts (text .. clip) on one glyph
    (a simple() entry takes such a spec as "then", drawn over its result)"""
    old, g = orig_glyph(fid, ch)
    img = Image.new('RGBA', (sp.get('width', old.width), sp.get('height', old.height)), (0, 0, 0, 0))
    img.paste(old, (0, 0))
    paint(img, old, sp)
    return img, g


def paint(img, old, sp):
    op, ip = old.load(), img.load()
    for x0, y0, x1, y1, mode in sp.get('clear', []):
        ground = {hexcol(c) for c in mode[5:].split(',')} if mode.startswith('near:') else None
        for y in range(y0, y1):
            for x in range(x0, x1):
                if ground:   # the nearest pixel of the row in one of the ground colours
                    near = [op[q, y] for d in range(1, old.width) for q in (x - d, x + d)
                            if 0 <= q < old.width and op[q, y] in ground]
                    ip[x, y] = near[0] if near else ip[x, y]
                else:
                    ip[x, y] = ((0, 0, 0, 0) if mode == 'none' else hexcol(mode) if mode.startswith('#')
                                else op[int(mode[3:]), y])
    for part in sp.get('parts', [sp]):
        draw_text(img, part)


def simple(fid, ch, sp):
    """retext/glyphs.json entry: the English lettering right of x0 (an icon left of it stays)
    is erased and the Russian text drawn in the font that drew it, in its colours"""
    old, g = orig_glyph(fid, ch)
    x0, x1 = sp.get('x0', 0), sp.get('x1', old.width)
    px = old.load()
    pts = [(x, y) for y in range(old.height) for x in range(x0, x1) if px[x, y][3] > 100]
    bx = [min(p[0] for p in pts), min(p[1] for p in pts), max(p[0] for p in pts) + 1, max(p[1] for p in pts) + 1]
    fonts = sp.get('fonts') or [int(f) for f in detect_font(old, bx)[:1]] or [475]
    w = max([old.width] + [x0 + Font(str(fonts[0])).render(t).width * sp.get('px', 1) + 2 for t in sp['text'].split('|')])
    h = sp.get('height', old.height)   # the glyph may grow downwards
    part = {'text': sp['text'], 'box': [x0, 0, x1 if 'x1' in sp else w, h], 'clear': [[x0, 0, x1, old.height]],
            'fonts': fonts, 'outline': 'auto', 'cbox': bx, 'align': sp.get('align', 'left' if x0 else 'center')}
    part.update({k: v for k, v in sp.items() if k not in ('x0', 'x1', 'height', 'restore', 'stripes', 'more', 'then')})
    more = [dict({'outline': 'auto', 'erase': sp.get('erase', 'clear')}, **m) for m in sp.get('more', [])]   # other captions
    marks = []
    for i, p in enumerate([part] + more):   # from_orig: [x0, y0, x1, y1] of the English lettering whose colours
        if p.get('from_orig'):               # (rainbow letters, gradients) the Russian takes over point by point
            key = (254, 1, 250 - i)
            p.update(flat=True, fill='#%02x%02x%02x' % key)
            marks.append((key, p['from_orig'], p.get('src_lum', 100)))
    img, g = panel(fid, ch, w, {'erase': sp.get('erase', 'clear'), 'parts': [part] + more,
                                'restore': sp.get('restore', [])}, h)
    ip = img.load()
    for key, (ox0, oy0, ox1, oy1), src_lum in marks:
        pts = [(x, y) for y in range(img.height) for x in range(img.width) if ip[x, y][:3] == key]
        if not pts:
            continue
        nx0, ny0 = min(p[0] for p in pts), min(p[1] for p in pts)
        nw, nh = max(p[0] for p in pts) - nx0 + 1, max(p[1] for p in pts) - ny0 + 1
        src = [(x, y) for y in range(oy0, oy1) for x in range(ox0, ox1) if px[x, y][3] > 150 and lum(px[x, y]) > src_lum]
        for x, y in pts:
            tx = ox0 + (x - nx0) * (ox1 - ox0) / nw
            ty = oy0 + (y - ny0) * (oy1 - oy0) / nh
            best = min(src, key=lambda q: (q[0] - tx) ** 2 + 4 * (q[1] - ty) ** 2)   # rows matter more
            ip[x, y] = px[best]
    if sp.get('stripes'):   # diagonal bands "\" over the fill colour: [colour, period, width]
        col, period, width = sp['stripes']
        fill, col = hexcol(sp['fill'])[:3], hexcol(col)
        ip = img.load()
        for y in range(img.height):
            for x in range(img.width):
                if ip[x, y][:3] == fill and (x - y) % period < width:
                    ip[x, y] = col
    if sp.get('then'):
        paint(img, old, sp['then'])
    return img, g


def main():
    jobs = [(fid, ch, lambda a=a: label(*a)) for a in LABELS for fid, ch in [a[:2]]]
    jobs += [(fid, ch, lambda a=a: panel(*a)) for a in PANELS for fid, ch in [a[:2]]]
    for key, sp in json.load(open(os.path.join(ROOT, 'retext', 'glyphs.json'), encoding='utf-8')).items():
        if not key.startswith('_'):
            fid, cid = map(int, key.split(':'))
            draw = custom if sp.get('draw') == 'custom' else simple
            jobs.append((fid, chr(cid), lambda f=fid, c=chr(cid), s=sp, d=draw: d(f, c, s)))
    byfont = {}
    for fid, ch, make in jobs:
        byfont.setdefault(fid, []).append((ch, make))
    for fid, items in byfont.items():
        jp = os.path.join(ROOT, 'fonts', f'font-{fid}.json')
        pp = os.path.join(ROOT, 'fonts', f'font-{fid}.png')
        if os.path.exists(jp):
            spec = json.load(open(jp, encoding='utf-8'))
            sheet = Image.open(pp).convert('RGBA')
        else:   # a font without Cyrillic of its own
            spec, sheet = {'chars': []}, Image.new('RGBA', (1, 1), (0, 0, 0, 0))
        ours = {ord(ch) for ch, _ in items}
        spec['chars'] = [c for c in spec['chars'] if c['id'] not in ours]
        h = max([c['y'] + c['height'] for c in spec['chars']] or [-2])
        made = [(ch, *make()) for ch, make in items]
        # shelf packing below the other glyphs, rows no wider than the sheet (or 512)
        W = max([sheet.width if h > 0 else 0, 512] + [img.width for _, img, _ in made])
        x, y, rh, pos = 0, h + 2, 0, []
        for ch, img, g in sorted(made, key=lambda m: -m[1].height):
            if x + img.width > W:
                x, y, rh = 0, y + rh + 2, 0
            pos.append((ch, img, g, x, y))
            x, rh = x + img.width + 2, max(rh, img.height)
        new = Image.new('RGBA', (W, y + rh), (0, 0, 0, 0))
        if h > 0:
            new.paste(sheet.crop((0, 0, sheet.width, h)), (0, 0))
        for ch, img, g, gx, gy in pos:
            new.paste(img, (gx, gy))
            spec['chars'].append({'id': ord(ch), 'x': gx, 'y': gy, 'width': img.width, 'height': img.height,
                                  'xoffset': 0, 'yoffset': g.get('yoffset', 0), 'xadvance': img.width, 'replace': True})
        new.save(pp)
        open(jp, 'w', encoding='utf-8', newline='\n').write(json.dumps(spec, ensure_ascii=False, indent=0) + '\n')
        print(f'font {fid}: {len(made)} glyphs, sheet {new.width}x{new.height}')


if __name__ == '__main__':
    main()
