// Tiny PNG codec: decode any non-interlaced PNG to RGBA8, encode RGBA8.
'use strict';
const zlib = require('zlib');

const CRC_TABLE = (() => {
  const t = new Int32Array(256);
  for (let n = 0; n < 256; n++) {
    let c = n;
    for (let k = 0; k < 8; k++) c = c & 1 ? 0xedb88320 ^ (c >>> 1) : c >>> 1;
    t[n] = c;
  }
  return t;
})();
function crc32(buf) {
  let c = -1;
  for (let i = 0; i < buf.length; i++) c = CRC_TABLE[(c ^ buf[i]) & 255] ^ (c >>> 8);
  return (c ^ -1) >>> 0;
}

function decode(buf) {
  let p = 8, width, height, depth, ctype, interlace, palette = null, trns = null;
  const idat = [];
  while (p < buf.length) {
    const len = buf.readUInt32BE(p), type = buf.toString('ascii', p + 4, p + 8);
    const data = buf.slice(p + 8, p + 8 + len);
    if (type === 'IHDR') {
      width = data.readUInt32BE(0); height = data.readUInt32BE(4);
      depth = data[8]; ctype = data[9]; interlace = data[12];
    } else if (type === 'PLTE') palette = data;
    else if (type === 'tRNS') trns = data;
    else if (type === 'IDAT') idat.push(data);
    else if (type === 'IEND') break;
    p += 12 + len;
  }
  if (interlace) throw new Error('interlaced PNG not supported');
  const channels = { 0: 1, 2: 3, 3: 1, 4: 2, 6: 4 }[ctype];
  const bpp = Math.max(1, (channels * depth) >> 3);
  const stride = (width * channels * depth + 7) >> 3;
  const raw = zlib.inflateSync(Buffer.concat(idat));
  const px = Buffer.alloc(height * stride);
  let prev = Buffer.alloc(stride);
  for (let y = 0; y < height; y++) {
    const f = raw[y * (stride + 1)];
    const line = raw.slice(y * (stride + 1) + 1, (y + 1) * (stride + 1));
    const cur = px.slice(y * stride, (y + 1) * stride);
    for (let x = 0; x < stride; x++) {
      const a = x >= bpp ? cur[x - bpp] : 0, b = prev[x], c = x >= bpp ? prev[x - bpp] : 0;
      let v = line[x];
      if (f === 1) v += a;
      else if (f === 2) v += b;
      else if (f === 3) v += (a + b) >> 1;
      else if (f === 4) {
        const pp = a + b - c, pa = Math.abs(pp - a), pb = Math.abs(pp - b), pc = Math.abs(pp - c);
        v += pa <= pb && pa <= pc ? a : pb <= pc ? b : c;
      }
      cur[x] = v & 255;
    }
    prev = cur;
  }
  const out = Buffer.alloc(width * height * 4);
  const max = (1 << depth) - 1;
  function sample(row, i) { // i-th sample in row
    if (depth === 8) return px[row * stride + i];
    if (depth === 16) return px[row * stride + i * 2];
    const bit = i * depth;
    return (px[row * stride + (bit >> 3)] >> (8 - depth - (bit & 7))) & max;
  }
  for (let y = 0; y < height; y++) {
    for (let x = 0; x < width; x++) {
      const o = (y * width + x) * 4;
      let r, g, b, a = 255;
      if (ctype === 3) {
        const i = sample(y, x);
        r = palette[i * 3]; g = palette[i * 3 + 1]; b = palette[i * 3 + 2];
        if (trns && i < trns.length) a = trns[i];
      } else if (ctype === 0 || ctype === 4) {
        let v = sample(y, x * channels);
        if (depth < 8) v = Math.round(v * 255 / max);
        r = g = b = v;
        if (ctype === 4) a = sample(y, x * 2 + 1);
        else if (trns && v === (depth < 8 ? Math.round(trns.readUInt16BE(0) * 255 / max) : trns.readUInt16BE(0))) a = 0;
      } else {
        r = sample(y, x * channels); g = sample(y, x * channels + 1); b = sample(y, x * channels + 2);
        if (ctype === 6) a = sample(y, x * channels + 3);
      }
      out[o] = r; out[o + 1] = g; out[o + 2] = b; out[o + 3] = a;
    }
  }
  return { width, height, data: out };
}

function chunk(type, data) {
  const len = Buffer.alloc(4);
  len.writeUInt32BE(data.length, 0);
  const td = Buffer.concat([Buffer.from(type, 'ascii'), data]);
  const crc = Buffer.alloc(4);
  crc.writeUInt32BE(crc32(td), 0);
  return Buffer.concat([len, td, crc]);
}

function encode(img) {
  const { width, height, data } = img;
  const raw = Buffer.alloc(height * (width * 4 + 1));
  for (let y = 0; y < height; y++) {
    raw[y * (width * 4 + 1)] = 0;
    data.copy(raw, y * (width * 4 + 1) + 1, y * width * 4, (y + 1) * width * 4);
  }
  const ihdr = Buffer.alloc(13);
  ihdr.writeUInt32BE(width, 0); ihdr.writeUInt32BE(height, 4);
  ihdr[8] = 8; ihdr[9] = 6; ihdr[10] = 0; ihdr[11] = 0; ihdr[12] = 0;
  return Buffer.concat([
    Buffer.from([137, 80, 78, 71, 13, 10, 26, 10]),
    chunk('IHDR', ihdr),
    chunk('IDAT', zlib.deflateSync(raw, { level: 9 })),
    chunk('IEND', Buffer.alloc(0)),
  ]);
}

function create(width, height) {
  return { width, height, data: Buffer.alloc(width * height * 4) };
}

// Copy a rectangle of src into dst at (dx, dy).
function blit(src, sx, sy, w, h, dst, dx, dy) {
  for (let y = 0; y < h; y++) {
    src.data.copy(dst.data, ((dy + y) * dst.width + dx) * 4, ((sy + y) * src.width + sx) * 4, ((sy + y) * src.width + sx + w) * 4);
  }
}

module.exports = { decode, encode, create, blit };
