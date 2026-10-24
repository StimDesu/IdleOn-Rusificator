"""Render sample text with a game font merged with generated Cyrillic glyphs.

  python preview.py <pak_dir> <fonts_dir> <out.png> <ids> <text> [scale]
"""
import json
import os
import sys

from PIL import Image, ImageDraw

sys.path.insert(0, os.path.dirname(__file__))
from model import load_font


def glyph_source(pak, fonts, fid):
    chars, img, info = load_font(f'{pak}/assets/graphics/1x/font-{fid}.fnt', f'{pak}/assets/graphics/1x/font-{fid}.png')
    base = Image.fromarray(img)
    table = {k: (base, c) for k, c in chars.items()}
    jp = os.path.join(fonts, f'font-{fid}.json')
    if os.path.exists(jp):
        sheet = Image.open(os.path.join(fonts, f'font-{fid}.png')).convert('RGBA')
        for c in json.load(open(jp, encoding='utf-8'))['chars']:
            table[c['id']] = (sheet, dict(x=c['x'], y=c['y'], w=c['width'], h=c['height'], xo=c['xoffset'], yo=c['yoffset'], adv=c['xadvance']))
    return table


def render(table, text):
    H = max(c['h'] + c['yo'] for _, c in table.values()) + 2
    W = sum(table[ord(ch)][1]['adv'] if ord(ch) in table else 6 for ch in text) + 4
    can = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    x = 2
    for ch in text:
        if ord(ch) not in table:
            x += 6
            continue
        src, c = table[ord(ch)]
        if c['w'] and c['h']:
            can.alpha_composite(src.crop((c['x'], c['y'], c['x'] + c['w'], c['y'] + c['h'])), (x + c['xo'], 1 + c['yo']))
        x += c['adv']
    return can


def main():
    pak, fonts, out, ids, text = sys.argv[1:6]
    scale = int(sys.argv[6]) if len(sys.argv) > 6 else 3
    lines = text.split('|')
    rows = []
    for fid in ids.split(','):
        t = glyph_source(pak, fonts, fid)
        for l in lines:
            rows.append((fid, render(t, l)))
    W = max(r.width for _, r in rows) + 40
    H = sum(r.height + 2 for _, r in rows)
    sheet = Image.new('RGBA', (W, H), (60, 62, 92, 255))
    d = ImageDraw.Draw(sheet)
    y = 0
    for fid, r in rows:
        d.text((1, y), fid, fill=(255, 255, 0, 255))
        sheet.alpha_composite(r, (36, y))
        y += r.height + 2
    sheet = sheet.resize((sheet.width * scale, sheet.height * scale), Image.NEAREST)
    sheet.save(out)


if __name__ == '__main__':
    main()
