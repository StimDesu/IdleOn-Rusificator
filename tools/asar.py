"""Minimal ASAR (Electron archive) reader/writer.

Usage:
  python asar.py list    <archive.asar>
  python asar.py extract <archive.asar> <out_dir>
  python asar.py pack    <src_dir> <archive.asar> [--unpacked-from <original.asar>]

Format: [uint32 4][uint32 hdr_pickle_size][uint32 payload_size][uint32 json_len][json][pad] [file data...]
File offsets in the JSON header are relative to the end of the header pickle.
"""
import json
import os
import struct
import sys


def read_header(path):
    with open(path, "rb") as f:
        size_pickle_size, header_pickle_size = struct.unpack("<II", f.read(8))
        payload_size, json_len = struct.unpack("<II", f.read(8))
        header = json.loads(f.read(json_len).decode("utf-8"))
    base = 8 + header_pickle_size
    return header, base


def walk(node, prefix=""):
    for name, entry in node.get("files", {}).items():
        p = f"{prefix}/{name}" if prefix else name
        if "files" in entry:
            yield from walk(entry, p)
        else:
            yield p, entry


def cmd_list(archive):
    header, _ = read_header(archive)
    for p, e in walk(header):
        flag = " [unpacked]" if e.get("unpacked") else ""
        print(f"{e.get('size', 0):>12}  {p}{flag}")


def cmd_extract(archive, out_dir):
    header, base = read_header(archive)
    with open(archive, "rb") as f:
        for p, e in walk(header):
            if e.get("unpacked") or "link" in e:
                continue
            dst = os.path.join(out_dir, *p.split("/"))
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            f.seek(base + int(e["offset"]))
            with open(dst, "wb") as o:
                o.write(f.read(e["size"]))


def cmd_pack(src_dir, archive, unpacked_from=None):
    unpacked = set()
    if unpacked_from:
        h, _ = read_header(unpacked_from)
        unpacked = {p for p, e in walk(h) if e.get("unpacked")}
        unpacked_entries = {p: e for p, e in walk(h) if e.get("unpacked")}
    files_order = []
    offset = 0

    def build(dir_path, rel):
        nonlocal offset
        node = {"files": {}}
        for name in sorted(os.listdir(dir_path)):
            full = os.path.join(dir_path, name)
            r = f"{rel}/{name}" if rel else name
            if os.path.isdir(full):
                node["files"][name] = build(full, r)
            else:
                size = os.path.getsize(full)
                node["files"][name] = {"size": size, "offset": str(offset)}
                files_order.append(full)
                offset += size
        return node

    header = build(src_dir, "")
    # re-insert unpacked entries (they live in app.asar.unpacked, no data in archive)
    for p in unpacked:
        parts = p.split("/")
        node = header
        for part in parts[:-1]:
            node = node["files"].setdefault(part, {"files": {}})
        node["files"][parts[-1]] = unpacked_entries[p]

    js = json.dumps(header, separators=(",", ":")).encode("utf-8")
    json_len = len(js)
    pad = (4 - json_len % 4) % 4
    payload = struct.pack("<I", json_len) + js + b"\0" * pad
    header_pickle = struct.pack("<I", len(payload)) + payload
    with open(archive, "wb") as o:
        o.write(struct.pack("<II", 4, len(header_pickle)))
        o.write(header_pickle)
        for full in files_order:
            with open(full, "rb") as i:
                o.write(i.read())


if __name__ == "__main__":
    a = sys.argv[1:]
    if a[0] == "list":
        cmd_list(a[1])
    elif a[0] == "extract":
        cmd_extract(a[1], a[2])
    elif a[0] == "pack":
        uf = a[a.index("--unpacked-from") + 1] if "--unpacked-from" in a else None
        cmd_pack(a[1], a[2], uf)
