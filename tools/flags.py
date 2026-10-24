"""Russian flag for the game's language pickers.

  python flags.py <pak_dir> <repo_dir>

The Russian flag is the game's own German flag (horizontal tricolor with the same pixel
shading) recolored: black -> white, red -> blue, gold -> red, using the shade ramps of the
French flag. Outputs
  * fonts/font-106-flags.json/png  replacement glyphs 'p' (LANGUAGE button) and 'q' (flag panel)
  * pak/assets/data/UIsound2.png, UIsound3.png  login screen panel with 8 flags
"""
import colorsys
import json
import os
import sys

import numpy as np
from PIL import Image


def lum(c):
    return 0.299 * c[0] + 0.587 * c[1] + 0.114 * c[2]


def hue_class(c):
    r, g, b = [v / 255 for v in c[:3]]
    h, l, s = colorsys.rgb_to_hls(r, g, b)
    if l < 0.22 and s < 0.5:
        return 'dark'
    if l > 0.85 or (s < 0.35 and l > 0.4):
        return 'white'
    if s < 0.25:
        return 'gray'
    h *= 360
    if h < 25 or h > 330:
        return 'red'
    if h < 70:
        return 'gold'
    if 190 < h < 260:
        return 'blue'
    return 'other'


def ramp(img, box, cls):
    """distinct colors of a class inside box, darkest first"""
    x0, y0, x1, y1 = box
    cols = {tuple(int(v) for v in img[y, x]) for y in range(y0, y1) for x in range(x0, x1)
            if img[y, x, 3] and hue_class(img[y, x]) == cls}
    return sorted(cols, key=lum)


def remap_from_top(src_cols, dst_cols):
    """brightest source -> brightest target, next -> next, ... (both sorted darkest first)"""
    m = {}
    for k, c in enumerate(reversed(src_cols)):
        m[c] = dst_cols[max(0, len(dst_cols) - 1 - k)]
    return m


def remap(src_cols, dst_cols):
    m = {}
    for i, c in enumerate(src_cols):
        j = round(i * (len(dst_cols) - 1) / max(1, len(src_cols) - 1))
        m[c] = dst_cols[j]
    return m


def russian(img, de_box, fr_box, outlined=True):
    """recolor the German flag inside de_box using French ramps; returns RGBA crop"""
    x0, y0, x1, y1 = de_box
    flag = img[y0:y1, x0:x1].copy()
    blue = ramp(img, fr_box, 'blue')
    red = ramp(img, fr_box, 'red')
    white = ramp(img, fr_box, 'white')
    # German bands: black (top), red (middle), gold (bottom)
    rows = {}
    for y in range(flag.shape[0]):
        for x in range(flag.shape[1]):
            if flag[y, x, 3]:
                rows.setdefault(hue_class(flag[y, x]), []).append(y)
    band_black = [tuple(int(v) for v in flag[y, x]) for y in range(flag.shape[0]) for x in range(flag.shape[1])
                  if flag[y, x, 3] and hue_class(flag[y, x]) in ('dark', 'gray')]
    # dark pixels are both the black band and the outline; the outline is the outermost ring
    h, w = flag.shape[:2]
    alpha = flag[:, :, 3] > 0
    outline = np.zeros_like(alpha)
    for y in range(h):
        for x in range(w):
            if not alpha[y, x]:
                continue
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                xx, yy = x + dx, y + dy
                if outlined and (not (0 <= xx < w and 0 <= yy < h) or not alpha[yy, xx]):
                    outline[y, x] = True
    black_cols = sorted({tuple(int(v) for v in flag[y, x]) for y in range(h) for x in range(w)
                         if alpha[y, x] and not outline[y, x] and hue_class(flag[y, x]) in ('dark', 'gray')}, key=lum)
    red_cols = sorted({tuple(int(v) for v in flag[y, x]) for y in range(h) for x in range(w)
                       if alpha[y, x] and not outline[y, x] and hue_class(flag[y, x]) == 'red'}, key=lum)
    gold_cols = sorted({tuple(int(v) for v in flag[y, x]) for y in range(h) for x in range(w)
                        if alpha[y, x] and not outline[y, x] and hue_class(flag[y, x]) == 'gold'}, key=lum)
    m = {}
    m.update(remap(black_cols, white))
    m.update(remap(red_cols, blue))
    m.update(remap(gold_cols, red))
    out = flag.copy()
    for y in range(h):
        for x in range(w):
            c = tuple(int(v) for v in flag[y, x])
            if alpha[y, x] and not outline[y, x] and c in m:
                out[y, x] = m[c]
    return out


def russian_from_japan(img, jp_box, fr_box, outlined=True, red_box=None):
    """Japanese flag (white field with the game's shading) -> white/blue/red stripes"""
    x0, y0, x1, y1 = jp_box
    flag = img[y0:y1, x0:x1].copy()
    h, w = flag.shape[:2]
    alpha = flag[:, :, 3] > 0
    outline = np.zeros_like(alpha)
    if outlined:
        for y in range(h):
            for x in range(w):
                if alpha[y, x] and any(not (0 <= x + dx < w and 0 <= y + dy < h) or not alpha[y + dy, x + dx]
                                       for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))):
                    outline[y, x] = True
    field = alpha & ~outline
    # erase the red disc: take the field color of the same row, outside the disc
    for y in range(h):
        row = [x for x in range(w) if field[y, x] and hue_class(flag[y, x]) not in ('red', 'other')]
        for x in range(w):
            if field[y, x] and hue_class(flag[y, x]) in ('red', 'other') and row:
                nx = min(row, key=lambda r: abs(r - x))
                flag[y, x] = flag[y, nx]
    whites = sorted({tuple(int(v) for v in flag[y, x]) for y in range(h) for x in range(w) if field[y, x]}, key=lum)
    blue = ramp(img, fr_box, 'blue')
    red = ramp(img, red_box or fr_box, 'red')
    to_blue, to_red = remap_from_top(whites, blue), remap_from_top(whites, red)
    # split into thirds on the lit face only; darker shadow rows below belong to the red band
    rowlum = {y: np.mean([lum(flag[y, x]) for x in range(w) if field[y, x]]) for y in range(h) if field[y].any()}
    lit = max(rowlum.values())
    face = [y for y, l in rowlum.items() if l > 0.75 * lit]
    top, bottom = face[0], face[-1] + 1
    third = (bottom - top) / 3
    for y in range(h):
        band = min(2, int((y - top) / third)) if third else 0
        for x in range(w):
            if field[y, x] and band >= 1:
                c = tuple(int(v) for v in flag[y, x])
                flag[y, x] = (to_blue if band == 1 else to_red).get(c, flag[y, x])
    return flag


def bbox_alpha(img, x0, y0, x1, y1):
    a = img[y0:y1, x0:x1, 3] > 0
    ys, xs = np.nonzero(a)
    return x0 + xs.min(), y0 + ys.min(), x0 + xs.max() + 1, y0 + ys.max() + 1


def drop_columns(flag, n):
    """narrow a flag by removing n columns from its middle (stripes survive this)"""
    w = flag.shape[1]
    mid = w // 2
    keep = [x for x in range(w) if not (mid - n // 2 <= x < mid - n // 2 + n)]
    return flag[:, keep]


def main():
    pak, repo = sys.argv[1], sys.argv[2]
    font = np.array(Image.open(f'{pak}/assets/graphics/1x/font-106.png').convert('RGBA'))

    # ---- glyph q: 7 big flags (44 px pitch) + caption; becomes 8 flags --------------------
    qx, qy, qw, qh = 9, 495, 306, 44
    q = font[qy:qy + qh, qx:qx + qw].copy()
    pitch = 44
    de = bbox_alpha(q, 3 * pitch, 0, 4 * pitch, 30)
    fr = bbox_alpha(q, 2 * pitch, 0, 3 * pitch, 30)
    jp = bbox_alpha(q, 5 * pitch, 0, 6 * pitch, 30)
    ru_big = russian_from_japan(q, jp, fr)
    new_q = np.zeros((qh, qw + pitch, 4), np.uint8)
    new_q[:, :qw] = q
    fx = 7 * pitch + (de[0] - 3 * pitch)
    new_q[de[1]:de[3], fx:fx + ru_big.shape[1]] = ru_big
    # caption below the flags: move it to the middle of the wider panel
    cap_top = de[3] + 1
    cap = new_q[cap_top:, :qw].copy()
    new_q[cap_top:, :] = 0
    new_q[cap_top:, pitch // 2:pitch // 2 + qw] = cap

    # ---- glyph p: LANGUAGE button, small flags (KO JA ZH on top, US UK FR DE below) -------
    px_, py_, pw, ph = 3, 437, 117, 52
    p = font[py_:py_ + ph, px_:px_ + pw].copy()
    # small flags have no outline; the top row gets the 4th slot at x=95 (pitch 24)
    ru_small = russian_from_japan(p, (47, 0, 68, 14), (59, 15, 80, 29), outlined=False)
    new_p = p.copy()
    new_p[0:14, 95:116] = ru_small
    # sheet with both glyphs
    sheet = np.zeros((qh + ph + 2, max(new_q.shape[1], new_p.shape[1]), 4), np.uint8)
    sheet[:qh, :new_q.shape[1]] = new_q
    sheet[qh + 2:qh + 2 + ph, :new_p.shape[1]] = new_p
    os.makedirs(f'{repo}/fonts', exist_ok=True)
    Image.fromarray(sheet).save(f'{repo}/fonts/font-106.png')
    spec = {'family': 'flags', 'chars': [
        dict(id=ord('q'), x=0, y=0, width=new_q.shape[1], height=qh, xoffset=0, yoffset=0, xadvance=new_q.shape[1], replace=True),
        dict(id=ord('p'), x=0, y=qh + 2, width=new_p.shape[1], height=ph, xoffset=0, yoffset=5, xadvance=new_p.shape[1], replace=True),
    ]}
    with open(f'{repo}/fonts/font-106.json', 'w', encoding='utf-8') as f:
        json.dump(spec, f, indent=0)

    # ---- login panel: 8 flags of 22 px at a 23 px pitch from x=150 -------------------------
    os.makedirs(f'{repo}/pak/assets/data', exist_ok=True)
    for name in ('UIsound2', 'UIsound3'):
        u = np.array(Image.open(f'{pak}/assets/data/{name}.png').convert('RGBA'))
        y0, y1 = 65, 81
        flags = []
        for k in range(7):
            x = 154 + 25 * k
            flags.append(u[y0:y1, x:x + 24].copy())
        bg = u[y0:y1, 150:151].copy()  # panel background column
        ru = russian_from_japan(u, (154 + 25 * 5, y0, 154 + 25 * 5 + 24, y1), (154 + 25 * 2, y0, 154 + 25 * 2 + 24, y1),
                                red_box=(154 + 25 * 6, y0, 154 + 25 * 6 + 24, y1))
        flags.append(ru)
        out = u.copy()
        out[y0:y1, 146:338] = np.repeat(bg, 338 - 146, axis=1)
        for k, fl in enumerate(flags):
            nf = drop_columns(fl, 2)
            x = 150 + 23 * k
            out[y0:y1, x:x + nf.shape[1]] = nf
        Image.fromarray(out).save(f'{repo}/pak/assets/data/{name}.png')
    print('ok')


if __name__ == '__main__':
    main()
