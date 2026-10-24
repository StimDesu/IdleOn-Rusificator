"""Check translation files for things that break the game or the layout.

  python lint.py [--fix-drafts] [files or dirs, default: translation]

Errors (the entry is dropped from drafts with --fix-drafts):
  * number placeholders differ: { } [ ] $ # * ^ & ~ (the game substitutes numbers there)
  * record strings (comma / space separated data parsed by the code) changed outside text fields
Warnings:
  * '|' (line break) or '@' (paragraph) count differs
  * spaces in a translation whose original uses '_' for spaces
"""
import glob
import json
import os
import re
import sys
from collections import Counter

PLACEHOLDERS = '{}[]$#*^&~'
TEXT_TOKEN = re.compile(r'[A-Za-zА-Яа-яЁё].*_|_.*[A-Za-zА-Яа-яЁё]|^[A-Za-z]+[!?.:;]*$|[А-Яа-яЁё]')


def is_record(en):
    """data rows the code splits: 'BaseDmg,add,1,0,5,...' or 'NAME 3.5 0 add 0 ...'"""
    if ' ' in en and len(re.findall(r'(?:^| )[-+]?\d+(?:\.\d+)?(?= |$)', en)) >= 2:
        return ' '
    if en.count(',') >= 3 and len(re.findall(r'(?:^|,)[-+]?\d+(?:\.\d+)?(?=,|$)', en)) >= 3:
        return ','
    return None


def check(en, ru):
    errors, warnings = [], []
    ce = Counter(c for c in en if c in PLACEHOLDERS)
    cr = Counter(c for c in ru if c in PLACEHOLDERS)
    if ce != cr:
        errors.append('placeholders %s -> %s' % (dict(ce), dict(cr)))
    sep = is_record(en)
    if sep:
        te, tr = en.split(sep), ru.split(sep)
        if len(te) != len(tr):
            errors.append('record fields %d -> %d' % (len(te), len(tr)))
        else:
            for a, b in zip(te, tr):
                if a != b and not TEXT_TOKEN.search(a):
                    errors.append('record field changed %r -> %r' % (a, b))
                    break
    for word in re.split(r"""[_ |@,.!?:;()'"«»\-]+""", ru):
        if re.search(r'[А-Яа-яЁё]', word) and re.search(r'[A-Za-z]', word):
            errors.append('mixed Latin/Cyrillic in %r' % word)
            break
    if en.count('|') != ru.count('|'):
        warnings.append("'|' %d -> %d" % (en.count('|'), ru.count('|')))
    if en.count('@') != ru.count('@'):
        warnings.append("'@' %d -> %d" % (en.count('@'), ru.count('@')))
    if ' ' in ru and ' ' not in en and '_' in en:
        warnings.append('spaces instead of _')
    return errors, warnings


def files(args):
    out = []
    for a in args or ['translation']:
        if os.path.isdir(a):
            out += sorted(glob.glob(os.path.join(a, '**', '*.json'), recursive=True))
        else:
            out.append(a)
    return out


def main():
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    fix = '--fix-drafts' in sys.argv
    total_e = total_w = 0
    for f in files(args):
        d = json.load(open(f, encoding='utf-8'))
        if not isinstance(d, dict):
            continue
        drop = []
        for en, ru in d.items():
            if not isinstance(ru, str):
                continue  # structured entries (items) are checked by their own tools
            e, w = check(en, ru)
            if e:
                total_e += 1
                print('ERR ', os.path.basename(f), repr(en[:70]), '|', '; '.join(e))
                drop.append(en)
            if w:
                total_w += 1
        if fix and drop and os.sep + 'draft' + os.sep in os.path.abspath(f):
            for en in drop:
                del d[en]
            with open(f, 'w', encoding='utf-8', newline='\n') as fh:
                json.dump(d, fh, ensure_ascii=False, indent=1)
                fh.write('\n')
            print('fixed', f, 'dropped', len(drop))
    print('errors', total_e, 'warnings', total_w)


if __name__ == '__main__':
    main()
