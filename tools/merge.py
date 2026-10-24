"""Merge a batch of translations into a translation file (checked with lint first).

  python merge.py <batch.json> <translation/target.json>
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from lint import check  # noqa: E402


def main():
    batch_path, target = sys.argv[1], sys.argv[2]
    batch = json.load(open(batch_path, encoding='utf-8'))
    data = json.load(open(target, encoding='utf-8')) if os.path.exists(target) else {}
    bad = 0
    for en, ru in batch.items():
        if isinstance(ru, str):
            e, w = check(en, ru)
            if e:
                bad += 1
                print('ERR', repr(en[:80]), '->', repr(ru[:80]), '|', '; '.join(e))
                continue
            for x in w:
                print('warn', repr(en[:60]), x)
        data[en] = ru
    with open(target, 'w', encoding='utf-8', newline='\n') as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
        f.write('\n')
    print('merged', len(batch) - bad, 'into', target, '(total %d)' % len(data), 'rejected', bad)


if __name__ == '__main__':
    main()
