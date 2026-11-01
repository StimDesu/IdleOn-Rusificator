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
    part.update({k: v for k, v in sp.items() if k not in ('x0', 'x1', 'height', 'restore', 'stripes', 'more')})
    more = [dict({'outline': 'auto', 'erase': sp.get('erase', 'clear')}, **m) for m in sp.get('more', [])]   # other captions
    img, g = panel(fid, ch, w, {'erase': sp.get('erase', 'clear'), 'parts': [part] + more,
                                'restore': sp.get('restore', [])}, h)
    if sp.get('stripes'):   # diagonal bands "\" over the fill colour: [colour, period, width]
        col, period, width = sp['stripes']
        fill, col = hexcol(sp['fill'])[:3], hexcol(col)
        ip = img.load()
        for y in range(img.height):
            for x in range(img.width):
                if ip[x, y][:3] == fill and (x - y) % period < width:
                    ip[x, y] = col
    return img, g


def main():
    jobs = [(fid, ch, lambda a=a: label(*a)) for a in LABELS for fid, ch in [a[:2]]]
    jobs += [(fid, ch, lambda a=a: panel(*a)) for a in PANELS for fid, ch in [a[:2]]]
    for key, sp in json.load(open(os.path.join(ROOT, 'retext', 'glyphs.json'), encoding='utf-8')).items():
        if not key.startswith('_'):
            fid, cid = map(int, key.split(':'))
            jobs.append((fid, chr(cid), lambda f=fid, c=chr(cid), s=sp: simple(f, c, s)))
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
