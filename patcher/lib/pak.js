// Lime PackedAssetLibrary: lib/default.pak + its manifest embedded in N.js.
'use strict';
const zlib = require('zlib');
const haxe = require('./haxe');

const MANIFEST_RE = /(\{"name":null,"assets":")([^"]*)(","rootPath":null,"version":2,"libraryArgs":\["lib\/default\.pak","gzip"\])/;

class Pak {
  constructor(njs, pakBuf) {
    const m = MANIFEST_RE.exec(njs);
    if (!m) throw new Error('asset manifest not found in N.js');
    this.njs = njs;
    this.match = m;
    this.assets = haxe.unserialize(m[2]);
    this.byId = {};
    for (const a of this.assets) this.byId[a.id] = a;
    this.chunks = [pakBuf];
    this.size = pakBuf.length;
    this.orig = pakBuf;
  }
  has(id) { return Object.prototype.hasOwnProperty.call(this.byId, id); }
  get(id) {
    const a = this.byId[id];
    if (!a || a.position == null) return null;
    const raw = this.orig.slice(a.position, a.position + a.length);
    try { return zlib.gunzipSync(raw); } catch (e) { return raw; }
  }
  // Add or replace an asset. Data is appended; the old bytes stay (harmless).
  set(id, data, type) {
    const gz = zlib.gzipSync(data, { level: 9 });
    let a = this.byId[id];
    if (!a) {
      a = { position: 0, size: 0, type: type || 'IMAGE', id: id, length: 0, preload: true };
      this.assets.push(a);
      this.byId[id] = a;
    }
    a.position = this.size;
    a.length = gz.length;
    this.chunks.push(gz);
    this.size += gz.length;
  }
  build() {
    const s = haxe.serialize(this.assets);
    const i = this.match.index + this.match[1].length;
    const njs = this.njs.slice(0, i) + s + this.njs.slice(i + this.match[2].length);
    return { njs: njs, pak: Buffer.concat(this.chunks) };
  }
}

module.exports = { Pak };
