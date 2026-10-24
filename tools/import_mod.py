"""Build draft translation files from the community mod (Steam guide 3800560343).

  python import_mod.py <mod N.js> <strings dump .json> <original N.js> <out dir>

* <mod N.js>       - N.js from the mod's app.asar (its dictionary is embedded in the prelude)
* <strings dump>   - game data strings: {"EN string": "first path"} (tools/dump_strings.py)
* <original N.js>  - unmodified game code, for string literals drawn by the code

Output: <out dir>/<group>.json = {"EN": "RU"} in game order. Keys are the exact strings
the game uses ('_' = space), so the runtime can match them directly. The mod is machine
translated: everything written here is a draft that still has to be reviewed.
"""
import json
import re
import sys
from collections import OrderedDict

NUM = r'([+\-]?[0-9][0-9.,]*(?:[KMBTQ]|e[+\-]?\d+)?)'
FOREIGN = re.compile(r'CustomLists\.(\w*LANG\w*|LangMapName|CardBonusDesc|EquipmentBonusMISC|SkillInfoDesc)\[|CustomMaps\.NPCdialogue\d')
LETTERS = re.compile(r'[A-Za-z]{2}')
ID_LIKE = re.compile(r'^[A-Za-z]+[0-9]+[A-Za-z0-9]*$|^[a-z]+[A-Z][A-Za-z0-9]*$')  # StampB16, mobRock2, slimeG


def load_mod(path):
    s = open(path, encoding='utf-8').read()
    i = s.find('})(globalThis,{"exact":')
    if i < 0:
        raise SystemExit('mod dictionary not found')
    obj, _ = json.JSONDecoder().raw_decode(s, i + len('})(globalThis,'))
    return obj


def template_literals(templates):
    """mod regex templates -> {EN literal with { } tokens: RU}"""
    out = {}
    for t in templates:
        rx, ru, tokens = t[0], t[1], t[2]
        if not isinstance(ru, str) or not rx.startswith('^') or not rx.endswith('$'):
            continue
        body = rx[1:-1]
        parts = body.split(NUM)
        if len(parts) - 1 != len(tokens):
            continue
        lit = ''
        ok = True
        for j, p in enumerate(parts):
            if re.search(r'(?<!\\)[\[\](){}*+?|^$.]', p.replace('\\.', '').replace('\\', '')) and '(' in p:
                ok = False
                break
            lit += re.sub(r'\\(.)', r'\1', p)
            if j < len(tokens):
                lit += tokens[j]
        if ok:
            out.setdefault(lit, ru)
    return out


def code_literals(njs):
    """string literals that the code draws (drawString args, _DummyTexto etc.)"""
    found = OrderedDict()
    for m in re.finditer(r'"((?:[^"\\]|\\.){3,300})"', njs):
        s = m.group(1)
        if '\\' in s or not LETTERS.search(s):
            continue
        if ID_LIKE.match(s) or s.endswith('.png') or s.startswith('http'):
            continue
        found.setdefault(s, None)
    return list(found)


def lookup(s, exact, tmpl):
    cands = [s]
    if '_' in s:
        cands.append(s.replace('_', ' '))
    for c in cands:
        ru = exact.get(c)
        if ru is None:
            ru = tmpl.get(c)
        if ru is not None:
            if c is not s and '_' in s:
                ru = ru.replace(' ', '_')
            return ru
    return None


def group_of(path):
    root = path.split('[')[0].split('.')[0]
    return {
        'ItemDefinitionsGET': 'items',
        'MonsterDefinitionsGET': 'monsters',
        'DialogueDefGET': 'dialogue',
        'AttackMoveGET': 'attacks',
    }.get(root, 'lists')


def main():
    mod_njs, dump, orig_njs, out_dir = sys.argv[1:5]
    mod = load_mod(mod_njs)
    exact = mod['exact']
    tmpl = template_literals(mod.get('templates', []))
    data = json.load(open(dump, encoding='utf-8'))
    groups = OrderedDict((g, OrderedDict()) for g in ('items', 'monsters', 'dialogue', 'attacks', 'lists', 'ui'))
    seen = set()
    stats = {'data': 0, 'data_hit': 0, 'ui': 0, 'ui_hit': 0}
    for s, path in data.items():
        if FOREIGN.match(path) or not LETTERS.search(s) or ID_LIKE.match(s):
            continue
        stats['data'] += 1
        ru = lookup(s, exact, tmpl)
        if ru is not None and ru != s:
            groups[group_of(path)][s] = ru
            stats['data_hit'] += 1
        seen.add(s)
    njs = open(orig_njs, encoding='utf-8').read()
    for s in code_literals(njs):
        if s in seen:
            continue
        stats['ui'] += 1
        ru = lookup(s, exact, tmpl)
        if ru is not None and ru != s:
            groups['ui'][s] = ru
            stats['ui_hit'] += 1
    import os
    os.makedirs(out_dir, exist_ok=True)
    for g, d in groups.items():
        with open(os.path.join(out_dir, g + '.json'), 'w', encoding='utf-8', newline='\n') as f:
            json.dump(d, f, ensure_ascii=False, indent=1)
            f.write('\n')
    print(json.dumps(stats), {g: len(d) for g, d in groups.items()})


if __name__ == '__main__':
    main()
