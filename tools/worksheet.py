"""Worksheets for translating: original text, where it is used, and the mod's draft.

  python worksheet.py items <gamedata.json> <out_dir> [per_file]
  python worksheet.py dialogue <gamedata.json> <out_dir> [chars_per_file]

gamedata.json is a dump of the game data (see docs/DEVELOPMENT.md). Items already present
in translation/items.json are skipped, so re-running shows only what is left.
"""
import glob
import json
import os
import sys


def load_dict(root):
    d = {}
    for f in sorted(glob.glob(os.path.join(root, 'translation', 'draft', '*.json'))):
        d.update(json.load(open(f, encoding='utf-8')))
    return d


def load_json(path):
    return json.load(open(path, encoding='utf-8')) if os.path.exists(path) else {}


def items(game, out_dir, per_file, root):
    """unique item names and unique descriptions that are not translated yet"""
    defs = game['ItemDefinitionsGET']
    draft = load_dict(root)
    names_done = load_json(os.path.join(root, 'translation', 'items.json'))
    descs_done = load_json(os.path.join(root, 'translation', 'item_desc.json'))
    names, descs = {}, {}
    for iid, it in defs.items():
        name = it.get('displayName')
        if not name or name in ('DONTFILL', 'ERROR', 'Not_Yet', 'Filler', 'Blank', 'NULL'):
            continue
        if name not in names_done:
            names.setdefault(name, []).append('%s:%s' % (iid, it.get('Type')))
        lines = [it.get('desc_line%d' % i) for i in range(1, 9)]
        lines = [l for l in lines if l not in (None, 'Filler')]
        key = '|'.join(lines)
        if lines and key not in descs_done and lines[0] not in ('You_shouldnt_be_seeing_this...',):
            descs.setdefault(key, []).append(name)
    os.makedirs(out_dir, exist_ok=True)
    for old in glob.glob(os.path.join(out_dir, 'items_*.txt')) + glob.glob(os.path.join(out_dir, 'desc_*.txt')):
        os.remove(old)
    rows = list(names.items())
    for n in range(0, len(rows), per_file):
        with open(os.path.join(out_dir, 'items_%03d.txt' % (n // per_file)), 'w', encoding='utf-8') as f:
            for name, where in rows[n:n + per_file]:
                f.write('%s\t%s\t%s\n' % (name, draft.get(name, ''), ' '.join(where[:3])))
    rows = list(descs.items())
    for n in range(0, len(rows), per_file):
        with open(os.path.join(out_dir, 'desc_%03d.txt' % (n // per_file)), 'w', encoding='utf-8') as f:
            for key, where in rows[n:n + per_file]:
                lines = key.split('|')
                dl = [draft.get(l, '?') for l in lines]
                f.write('## %s\n%s\n' % (', '.join(where[:4]), key))
                if any(x != '?' for x in dl):
                    f.write('draft: %s\n' % '|'.join(dl))
                f.write('\n')
    print(len(names), 'names,', len(descs), 'descriptions')


def dialogue(game, out_dir, per_file, root):
    """NPC dialogue lines not in translation/dialogue.json, grouped by NPC in game order"""
    draft = load_dict(root)
    done = load_json(os.path.join(root, 'translation', 'dialogue.json'))
    npcs = load_json(os.path.join(root, 'translation', 'npcs.json'))
    os.makedirs(out_dir, exist_ok=True)
    for old in glob.glob(os.path.join(out_dir, 'dlg_*.txt')):
        os.remove(old)
    seen, files, buf, size, total = set(), 0, [], 0, 0

    def flush():
        nonlocal files, buf, size
        if buf:
            with open(os.path.join(out_dir, 'dlg_%03d.txt' % files), 'w', encoding='utf-8') as f:
                f.write(''.join(buf))
            files += 1
        buf, size = [], 0

    for npc, v in game['DialogueDefGET'].items():
        lines = [s for s in v[0] if isinstance(s, str) and s not in done and s not in seen]
        if not lines:
            continue
        seen.update(lines)
        if size > per_file:
            flush()
        block = '## %s = %s\n' % (npc, npcs.get(npc, '?'))
        for s in lines:
            block += s + '\n'
            if s in draft:
                block += 'draft: ' + draft[s] + '\n'
        buf.append(block + '\n')
        size += len(block)
        total += len(lines)
    flush()
    print(total, 'lines in', files, 'files')


def main():
    a = sys.argv[1:]
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    game = json.load(open(a[1], encoding='utf-8'))
    if a[0] == 'items':
        items(game, a[2], int(a[3]) if len(a) > 3 else 150, root)
    elif a[0] == 'dialogue':
        dialogue(game, a[2], int(a[3]) if len(a) > 3 else 12000, root)


if __name__ == '__main__':
    main()
