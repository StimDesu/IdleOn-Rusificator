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

from retext import Font, ROOT, GAME, lum, build_panel   # noqa: E402

# (font id, glyph, text, text font, dash length each side or 0)
LABELS = [
    (259, '蒂', 'Множитель бонусов вешалки', 223, 12),
]

# (font id, glyph, canvas width or None, retext panel spec): the canvas grows to the right
PANELS = [
    (726, chr(47691), None, {'parts': [   # Halloween: "Keep IdleOn open for another" [time] [109 below]
        {'text': 'Держи IdleOn открытым ещё', 'box': [34, 4, 224, 21], 'clear': [[34, 4, 224, 22, 'flat']],
         'fonts': [475], 'align': 'left', 'outline': 'auto', 'cbox': [36, 6, 222, 18]}]}),
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
    lo = min(lum(tp[x, y]) for y in range(t.height) for x in range(t.width) if tp[x, y][3] > 100)
    # the letter bodies only (the outline goes): the label is one flat colour like the original
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


def panel(fid, ch, width, sp):
    old, g = orig_glyph(fid, ch)
    src = Image.new('RGBA', (width or old.width, old.height), (0, 0, 0, 0))
    src.paste(old, (0, 0))
    with tempfile.TemporaryDirectory() as tmp:
        build_panel('glyph.png', sp, src, src.copy(), tmp)
        out = Image.open(os.path.join(tmp, 'glyph.png')).convert('RGBA')
        out.load()
    return out, g


def main():
    jobs = [(fid, ch, lambda a=a: label(*a)) for a in LABELS for fid, ch in [a[:2]]]
    jobs += [(fid, ch, lambda a=a: panel(*a)) for a in PANELS for fid, ch in [a[:2]]]
    for fid, ch, make in jobs:
        img, g = make()
        jp = os.path.join(ROOT, 'fonts', f'font-{fid}.json')
        pp = os.path.join(ROOT, 'fonts', f'font-{fid}.png')
        if os.path.exists(jp):
            spec = json.load(open(jp, encoding='utf-8'))
            sheet = Image.open(pp).convert('RGBA')
        else:   # a font without Cyrillic of its own
            spec, sheet = {'chars': []}, Image.new('RGBA', (1, 1), (0, 0, 0, 0))
        spec['chars'] = [c for c in spec['chars'] if c['id'] != ord(ch)]
        h = max([c['y'] + c['height'] for c in spec['chars']] or [-2])
        new = Image.new('RGBA', (max(sheet.width, img.width), h + 2 + img.height), (0, 0, 0, 0))
        if h > 0:
            new.paste(sheet.crop((0, 0, sheet.width, h)), (0, 0))
        new.paste(img, (0, h + 2))
        spec['chars'].append({'id': ord(ch), 'x': 0, 'y': h + 2, 'width': img.width, 'height': img.height,
                              'xoffset': 0, 'yoffset': g.get('yoffset', 0), 'xadvance': img.width, 'replace': True})
        new.save(pp)
        open(jp, 'w', encoding='utf-8', newline='\n').write(json.dumps(spec, ensure_ascii=False, indent=0) + '\n')
        print(f'font {fid} U+{ord(ch):04X}: {img.width}x{img.height}')


if __name__ == '__main__':
    main()
