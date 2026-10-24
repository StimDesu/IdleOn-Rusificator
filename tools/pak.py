"""Lime PackedAssetLibrary (default.pak) tools.

The asset manifest is a Haxe-serialized string embedded in N.js
(`Bd.parse('{"name":null,"assets":"<haxe>","rootPath":...,"libraryArgs":["lib/default.pak","gzip"],...}')`).
default.pak = b"lime-asset-pack" + concatenated gzip members; each asset has `position` and `length`
inside the pak (gzip-compressed bytes).

Usage:
  python pak.py list    <N.js>
  python pak.py extract <N.js> <default.pak> <out_dir>
"""
import gzip
import os
import re
import sys
import urllib.parse

MANIFEST_RE = re.compile(r"""\{"name":null,"assets":"(.*?)","rootPath":null,"version":2,"libraryArgs":\["lib/default\.pak","gzip"\]""", re.S)


class HaxeUnserializer:
    def __init__(self, s):
        self.s, self.p, self.cache, self.scache = s, 0, [], []

    def _int(self):
        m = re.compile(r"-?\d+").match(self.s, self.p)
        self.p = m.end()
        return int(m.group())

    def read(self):
        c = self.s[self.p]
        self.p += 1
        if c == "n":
            return None
        if c == "t":
            return True
        if c == "f":
            return False
        if c == "z":
            return 0
        if c == "i":
            return self._int()
        if c == "d":
            m = re.compile(r"[-+0-9.eE]+").match(self.s, self.p)
            self.p = m.end()
            return float(m.group())
        if c == "y":
            n = self._int()
            assert self.s[self.p] == ":"
            self.p += 1
            v = urllib.parse.unquote(self.s[self.p:self.p + n])
            self.p += n
            self.scache.append(v)
            return v
        if c == "R":
            return self.scache[self._int()]
        if c == "a":
            arr = []
            self.cache.append(arr)
            while True:
                ch = self.s[self.p]
                if ch == "h":
                    self.p += 1
                    return arr
                if ch == "u":
                    self.p += 1
                    arr.extend([None] * self._int())
                else:
                    arr.append(self.read())
        if c == "o":
            o = {}
            self.cache.append(o)
            while self.s[self.p] != "g":
                k = self.read()
                o[k] = self.read()
            self.p += 1
            return o
        raise ValueError(f"unsupported haxe tag {c!r} at {self.p}")


def load_manifest(njs_path):
    with open(njs_path, encoding="utf-8") as f:
        d = f.read()
    m = MANIFEST_RE.search(d)
    return HaxeUnserializer(m.group(1)).read()


def main():
    a = sys.argv[1:]
    # music/sfx live as loose files in assets/, only packed entries have a position
    assets = [e for e in load_manifest(a[1]) if "position" in e]
    if a[0] == "list":
        for e in assets:
            print(e["type"], e["position"], e["length"], e["id"])
    elif a[0] == "extract":
        with open(a[2], "rb") as f:
            pak = f.read()
        for e in assets:
            raw = pak[e["position"]:e["position"] + e["length"]]
            try:
                data = gzip.decompress(raw)
            except Exception:
                data = raw
            dst = os.path.join(a[3], *e["id"].split("/"))
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            with open(dst, "wb") as o:
                o.write(data)


if __name__ == "__main__":
    main()
