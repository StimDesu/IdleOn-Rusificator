// Haxe serialization (subset used by the Lime asset manifest embedded in N.js).
'use strict';

function unserialize(s) {
  let p = 0;
  const scache = [];
  function int() {
    const m = /^-?\d+/.exec(s.slice(p, p + 24));
    p += m[0].length;
    return parseInt(m[0], 10);
  }
  function read() {
    const c = s[p++];
    switch (c) {
      case 'n': return null;
      case 't': return true;
      case 'f': return false;
      case 'z': return 0;
      case 'i': return int();
      case 'd': {
        const m = /^[-+0-9.eE]+/.exec(s.slice(p, p + 40));
        p += m[0].length;
        return parseFloat(m[0]);
      }
      case 'y': {
        const n = int();
        p++; // ':'
        const v = decodeURIComponent(s.substr(p, n));
        p += n;
        scache.push(v);
        return v;
      }
      case 'R': return scache[int()];
      case 'a': {
        const arr = [];
        for (;;) {
          const ch = s[p];
          if (ch === 'h') { p++; return arr; }
          if (ch === 'u') { p++; const k = int(); for (let i = 0; i < k; i++) arr.push(null); }
          else arr.push(read());
        }
      }
      case 'o': {
        const o = {};
        while (s[p] !== 'g') { const k = read(); o[k] = read(); }
        p++;
        return o;
      }
      default: throw new Error('haxe: unsupported tag ' + c + ' at ' + (p - 1));
    }
  }
  return read();
}

function serialize(v) {
  const out = [];
  const cache = new Map();
  function str(x) {
    if (cache.has(x)) { out.push('R' + cache.get(x)); return; }
    cache.set(x, cache.size);
    const e = encodeURIComponent(x);
    out.push('y' + e.length + ':' + e);
  }
  function w(x) {
    if (x === null || x === undefined) out.push('n');
    else if (x === true) out.push('t');
    else if (x === false) out.push('f');
    else if (typeof x === 'number') {
      if (x === 0) out.push('z');
      else if (Number.isInteger(x) && Math.abs(x) < 2147483648) out.push('i' + x);
      else out.push('d' + x);
    } else if (typeof x === 'string') str(x);
    else if (Array.isArray(x)) { out.push('a'); x.forEach(w); out.push('h'); }
    else { out.push('o'); for (const k of Object.keys(x)) { str(k); w(x[k]); } out.push('g'); }
  }
  w(v);
  return out.join('');
}

module.exports = { unserialize, serialize };
