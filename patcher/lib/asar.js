// Minimal ASAR reader/writer (Electron archive). Node 12 compatible.
'use strict';
const fs = require('fs');
const path = require('path');

function readHeader(file) {
  const fd = fs.openSync(file, 'r');
  try {
    const head = Buffer.alloc(16);
    fs.readSync(fd, head, 0, 16, 0);
    const headerPickleSize = head.readUInt32LE(4);
    const jsonLen = head.readUInt32LE(12);
    const json = Buffer.alloc(jsonLen);
    fs.readSync(fd, json, 0, jsonLen, 16);
    return { header: JSON.parse(json.toString('utf8')), base: 8 + headerPickleSize };
  } finally {
    fs.closeSync(fd);
  }
}

// Flat list of entries: { path, entry }
function walk(node, prefix, out) {
  out = out || [];
  const files = node.files || {};
  for (const name of Object.keys(files)) {
    const p = prefix ? prefix + '/' + name : name;
    const e = files[name];
    if (e.files) walk(e, p, out);
    else out.push({ path: p, entry: e });
  }
  return out;
}

class Archive {
  constructor(file) {
    this.file = file;
    const h = readHeader(file);
    this.header = h.header;
    this.base = h.base;
    this.entries = walk(this.header, '');
    this.byPath = {};
    for (const e of this.entries) this.byPath[e.path] = e.entry;
  }
  has(p) { return Object.prototype.hasOwnProperty.call(this.byPath, p); }
  read(p) {
    const e = this.byPath[p];
    if (!e) throw new Error('not in archive: ' + p);
    if (e.unpacked) throw new Error('unpacked file: ' + p);
    const buf = Buffer.alloc(e.size);
    const fd = fs.openSync(this.file, 'r');
    try { fs.readSync(fd, buf, 0, e.size, this.base + Number(e.offset)); } finally { fs.closeSync(fd); }
    return buf;
  }
}

// Write a new archive: every file of `src` (Archive) plus `overrides` {path: Buffer}.
// Files are copied in chunks so the 130 MB archive is never fully in memory.
function writeArchive(src, overrides, outFile) {
  const header = { files: {} };
  const plan = []; // { from: 'src'|'buf', path, size }
  let offset = 0;
  function put(p, entry) {
    const parts = p.split('/');
    let node = header;
    for (let i = 0; i < parts.length - 1; i++) {
      node.files[parts[i]] = node.files[parts[i]] || { files: {} };
      node = node.files[parts[i]];
    }
    node.files[parts[parts.length - 1]] = entry;
  }
  const seen = {};
  for (const { path: p, entry } of src.entries) {
    seen[p] = true;
    if (entry.unpacked || entry.link) { put(p, entry); continue; }
    const ov = overrides[p];
    const size = ov ? ov.length : entry.size;
    const e = { size: size, offset: String(offset) };
    if (entry.executable) e.executable = true;
    put(p, e);
    plan.push(ov ? { buf: ov } : { srcPath: p, size: size });
    offset += size;
  }
  for (const p of Object.keys(overrides)) {
    if (seen[p]) continue;
    const ov = overrides[p];
    put(p, { size: ov.length, offset: String(offset) });
    plan.push({ buf: ov });
    offset += ov.length;
  }
  const json = Buffer.from(JSON.stringify(header), 'utf8');
  const pad = (4 - (json.length % 4)) % 4;
  const pickle = Buffer.alloc(8 + json.length + pad);
  pickle.writeUInt32LE(4 + json.length + pad, 0);
  pickle.writeUInt32LE(json.length, 4);
  json.copy(pickle, 8);
  const sizeBuf = Buffer.alloc(8);
  sizeBuf.writeUInt32LE(4, 0);
  sizeBuf.writeUInt32LE(pickle.length, 4);

  const tmp = outFile + '.tmp';
  const out = fs.openSync(tmp, 'w');
  const inp = fs.openSync(src.file, 'r');
  try {
    fs.writeSync(out, sizeBuf);
    fs.writeSync(out, pickle);
    const chunk = Buffer.alloc(4 << 20);
    for (const item of plan) {
      if (item.buf) { fs.writeSync(out, item.buf); continue; }
      const e = src.byPath[item.srcPath];
      let pos = src.base + Number(e.offset), left = e.size;
      while (left > 0) {
        const n = fs.readSync(inp, chunk, 0, Math.min(chunk.length, left), pos);
        fs.writeSync(out, chunk, 0, n);
        pos += n; left -= n;
      }
    }
  } finally {
    fs.closeSync(out);
    fs.closeSync(inp);
  }
  if (fs.existsSync(outFile)) fs.unlinkSync(outFile);
  fs.renameSync(tmp, outFile);
}

module.exports = { Archive, writeArchive, readHeader };
