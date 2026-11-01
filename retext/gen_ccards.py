"""Class cards (Ccards*.png): the panel under the portrait redrawn in the game fonts.
Writes the entries into retext/mod.json:  python retext/gen_ccards.py"""
import json
import os
import sys
from collections import Counter

from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'tools'))
from retext import Font, GAME, lum   # noqa: E402

LABELS = {'D': 'Урон', 'H': 'Здоровье', 'S': 'Скорость', 'M': 'Фарм'}
WORLD = {3: '#a4eff1', 5: None}   # None: sampled from the original
# name: (title, labels, icon x (right edge of line 1), line 1, more lines, world n | None, sprites over text)
CARDS = {
    'Ccards1': ('НОВИЧОК', 'DHS', 192, '• Спец по добыче руды', ['• Высшие классы воина', 'качают навыки левее города'], None, False),
    'Ccards10': ('КРОВАВЫЙ БЕРСЕРК', 'DHM', 161, '• Спец по кулинарии', ['• Бьёт одну цель и копит', 'силу, пока стоит на месте'], None, True),
    'Ccards2': ('ПОДМАСТЕРЬЕ', 'DHS', 164, '• Спец по луту', [], None, False),
    'Ccards20': ('СТРЕЛОК', 'DSM', 167, '• Спец по ловле жуков', [], None, False),
    'Ccards21': ('ОХОТНИК', 'DSM', 169, '• Спец по ловушкам', [], 3, False),
    'Ccards22': ('СОКРУШИТЕЛЬ ОСАД', 'DHS', 159, '• Спец по плаванию', [], 5, False),
    'Ccards25': ('ПОВЕЛИТЕЛЬ ЗВЕРЕЙ', 'DHM', 164, '• Спец по разведению', ['• Призывает питомцев', 'на помощь в бою'], None, True),
    'Ccards31': ('МАГ', 'DHS', 166, '• Спец по рубке леса', [], None, False),
    'Ccards32': ('ЧАРОДЕЙ', 'DHM', 166, '• Спец по поклонению', [], 3, False),
    'Ccards33': ('ШАМАН', 'DHM', 164, '• Спец по алхимии', [], None, False),
    'Ccards36': ('БУБОННЫЙ ЗАКЛИНАТЕЛЬ', 'DHM', 166, '• Спец по лаборатории', ['• Покрывает карту', 'облаками яда'], None, True),
    'Ccards7': ('ВОИН', 'DHS', 159, '• Спец по добыче руды', [], None, False),
    'Ccards8': ('ВАРВАР', 'DHM', 161, '• Спец по рыбалке', [], None, False),
    'Ccards9': ('ОРУЖЕНОСЕЦ', 'DHM', 171, '• Спец по стройке', [], 3, False),
}


def light(img, box, t=150):
    """most common light colour of the lettering in box"""
    x0, y0, x1, y1 = box
    c = Counter(img.getpixel((x, y))[:3] for y in range(y0, y1) for x in range(x0, x1)
                if lum(img.getpixel((x, y))) > t)
    return '#%02x%02x%02x' % c.most_common(1)[0][0]


def outline(img, box, t=150):
    """the colour around the lettering (not always black)"""
    x0, y0, x1, y1 = box
    px = img.load()
    c = Counter()
    for y in range(y0, y1):
        for x in range(x0, x1):
            if lum(px[x, y]) > t:
                for dx, dy in ((1, 0), (0, 1), (-1, 0), (0, -1)):
                    q = px[x + dx, y + dy]
                    if lum(q) < 80:
                        c[q[:3]] += 1
    return '#%02x%02x%02x' % c.most_common(1)[0][0]


def title_extent(img):
    """columns of the English title: the lines beside it are at most 2 rows thick"""
    cols = [x for x in range(20, 188)
            if sum(lum(img.getpixel((x, y))) > 150 for y in range(193, 207)) >= 3]
    return min(cols), max(cols) + 1


def card(name, title, labels, icon, line1, more, world, sprites):
    img = Image.open(os.path.join(GAME, 'data', name + '.png')).convert('RGBA')
    f95, f223 = Font('95'), Font('223')
    w = f95.render(title).getbbox()
    w = w[2] - w[0]
    ex0, ex1 = title_extent(img)
    cx = 103
    t0, t1 = min(ex0, cx - w // 2 - 3), max(ex1, cx + w // 2 + 4)
    body = {'fonts': [223, 109], 'flat': True, 'outline': outline(img, (14, 208, 192, 221))}
    parts = [{'text': title, 'box': [t0, 193, t1, 207], 'clear': [[max(20, t0), 192, min(190, t1), 208]],
              'fonts': [95], 'flat': True, 'outline': outline(img, (ex0, 193, ex1, 207)), 'fill': light(img, (ex0, 193, ex1, 207))}]
    for i, k in enumerate(labels):
        x0 = (10, 72, 134)[i]
        parts.append(dict(body, text=LABELS[k], box=[x0, 209, x0 + 62, 224],
                          clear=[[x0 + 4, 207, x0 + 58, 224]], fill=light(img, (14, 208, 192, 221))))
    fill = light(img, (16, 244, icon - 2, 258))
    erase = {'erase': 'text'} if sprites else {}
    parts.append(dict(body, **erase, text=line1, box=[16, 244, icon - 2, 258], align='left',
                      clear=[[15, 242, icon - 1, 261]], fill=fill))
    if more:
        parts.append(dict(body, **erase, text='|'.join(more), box=[16, 261, 191, 290], gap=3,
                          clear=[[15, 261, 191, 291]], fill=fill))
    if world:
        # "(This is a world 3 skill)": the mountain icon over "world" stays, the rest is redrawn
        col = WORLD[world] or light(img, (96, 268, 141, 280))
        a, b, c = '(Навык ', f'{world}-го мира', ')'
        wa, wb, wc = (f223.render(s).getbbox() for s in (a, b, c))
        wa, wb, wc = wa[2] - wa[0], wb[2] - wb[0], wc[2] - wc[0]
        x = 114 - wb // 2 - wa - 2
        parts += [
            dict(body, text=a.strip(), box=[x, 267, x + wa, 279], align='left', clear=[[15, 264, 103, 281], [125, 264, 191, 281], [103, 268, 125, 281]], fill=fill),
            dict(body, text=b, box=[x + wa + 4, 267, x + wa + 4 + wb, 279], align='left', fill=col, uline=1),
            dict(body, text=c, box=[x + wa + wb + 6, 267, x + wa + wb + 6 + wc, 279], align='left', fill=fill),
        ]
    return {'parts': parts, 'restore': [[96, 259, 134, 268]]} if world else {'parts': parts}


def stats(name):
    """CcardsTrans*: the four stat names, each in its own colour"""
    img = Image.open(os.path.join(GAME, 'data', name + '.png')).convert('RGBA')
    parts = []
    for i, t in enumerate(('СИЛ:', 'ЛВК:', 'МУД:', 'УДЧ:')):
        y = 88 + 14 * i
        parts.append({'text': t, 'box': [8, y - 1, 60, y + 11], 'clear': [[6, y - 2, 40, y + 12]], 'align': 'left',
                      'fonts': [223], 'flat': True, 'fill': light(img, (8, y, 37, y + 10), 90),
                      'outline': outline(img, (8, y, 37, y + 10), 90)})
    return {'parts': parts}


def main():
    path = os.path.join(HERE, 'mod.json')
    spec = json.load(open(path, encoding='utf-8'))
    for name, args in CARDS.items():
        spec[name + '.png'] = card(name, *args)
    for i in range(1, 5):
        spec[f'CcardsTrans{i}.png'] = stats(f'CcardsTrans{i}')
    open(path, 'w', encoding='utf-8').write(json.dumps(spec, ensure_ascii=False, indent=1) + '\n')


if __name__ == '__main__':
    main()
