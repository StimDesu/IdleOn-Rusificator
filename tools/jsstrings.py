"""String literals of a minified JS file (no comments), skipping regex literals.

  python jsstrings.py <file.js> <out.json>
"""
import json
import sys

REGEX_BEFORE = set('(,=:[!&|?{};+-*%<>~^')


def strings(src):
    out, i, n, prev = [], 0, len(src), ''
    while i < n:
        ch = src[i]
        if ch in '"\'`':
            j = i + 1
            buf = []
            while j < n and src[j] != ch:
                if src[j] == '\\' and j + 1 < n:
                    nxt = src[j + 1]
                    buf.append({'n': '\n', 't': '\t', 'r': '\r'}.get(nxt, nxt))
                    j += 2
                else:
                    buf.append(src[j])
                    j += 1
            out.append(''.join(buf))
            i, prev = j + 1, ch
        elif ch == '/' and (prev in REGEX_BEFORE or prev == ''):
            j, cls = i + 1, False
            while j < n:
                c = src[j]
                if c == '\\':
                    j += 2
                    continue
                if c == '[':
                    cls = True
                elif c == ']':
                    cls = False
                elif c == '/' and not cls:
                    break
                elif c == '\n':
                    break
                j += 1
            i, prev = j + 1, '/'
        else:
            if not ch.isspace():
                prev = ch
            i += 1
    return out


def main():
    src = open(sys.argv[1], encoding='utf-8').read()
    lits = strings(src)
    json.dump(lits, open(sys.argv[2], 'w', encoding='utf-8'), ensure_ascii=False)
    print(len(lits), 'literals')


if __name__ == '__main__':
    main()
