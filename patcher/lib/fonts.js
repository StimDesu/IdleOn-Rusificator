// Adds Cyrillic glyphs to the game's own bitmap fonts at install time.
// fonts/font-<ID>.png is a glyph sheet, fonts/font-<ID>.json describes its glyphs:
//   { "chars": [{ "id": 1040, "x":0, "y":0, "width":7, "height":9, "xoffset":0, "yoffset":0, "xadvance":8 }, ...] }
// The sheet is appended below the game's font texture, so fonts updated by the game
// keep their new Latin glyphs and still receive ours.
'use strict';
const fs = require('fs');
const path = require('path');
const png = require('./png');

function apply(pak, dir, report) {
  if (!fs.existsSync(dir)) { report.push('MISS fonts: folder not found'); return; }
  let n = 0;
  const skipped = [];
  for (const f of fs.readdirSync(dir).sort()) {
    const m = /^font-(\d+)\.json$/.exec(f);
    if (!m) continue;
    const id = m[1];
    const fntId = 'assets/graphics/1x/font-' + id + '.fnt';
    const pngId = 'assets/graphics/1x/font-' + id + '.png';
    const fnt = pak.get(fntId), tex = pak.get(pngId);
    if (!fnt || !tex) { skipped.push(id); continue; }
    const spec = JSON.parse(fs.readFileSync(path.join(dir, f), 'utf8'));
    const sheet = png.decode(fs.readFileSync(path.join(dir, 'font-' + id + '.png')));
    const base = png.decode(tex);
    const top = base.height + 2;
    const img = png.create(Math.max(base.width, sheet.width), top + sheet.height);
    png.blit(base, 0, 0, base.width, base.height, img, 0, 0);
    png.blit(sheet, 0, 0, sheet.width, sheet.height, img, 0, top);

    let xml = fnt.toString('utf8');
    const have = {};
    xml.replace(/<char [^>]*\bid="(\d+)"/g, (s, cid) => { have[cid] = true; return s; });
    // replace: true swaps a glyph the font already has (e.g. the flag panel glyphs)
    for (const c of spec.chars) {
      if (c.replace && have[c.id]) {
        xml = xml.replace(new RegExp('<char [^>]*\\bid="' + c.id + '"[^>]*/>\\s*'), '');
        xml = xml.replace(/<chars count="(\d+)"/, (s, k) => '<chars count="' + (Number(k) - 1) + '"');
        delete have[c.id];
      }
    }
    const add = spec.chars.filter(c => !have[c.id]).map(c =>
      '<char id="' + c.id + '" x="' + c.x + '" y="' + (c.y + top) + '" width="' + c.width + '" height="' + c.height +
      '" xoffset="' + c.xoffset + '" yoffset="' + c.yoffset + '" xadvance="' + c.xadvance + '" page="0" chnl="0"/>');
    xml = xml.replace('</chars>', add.join('\n') + '\n</chars>');
    // Ё/Й marks above the capitals have a negative yoffset, and the engine renders a string
    // into an image starting at the line top, so they were cut off: move the whole font down
    const lift = -Math.min(0, ...spec.chars.map(c => c.yoffset));
    if (lift) {
      xml = xml.replace(/(<char [^>]*\byoffset=")(-?\d+)"/g, (s, a, y) => a + (Number(y) + lift) + '"');
      xml = xml.replace(/(lineHeight|base)="(\d+)"/g, (s, k, v) => k + '="' + (Number(v) + lift) + '"');
    }
    xml = xml.replace(/<chars count="(\d+)"/, (s, k) => '<chars count="' + (Number(k) + add.length) + '"');
    xml = xml.replace(/scaleW="\d+"/, 'scaleW="' + img.width + '"').replace(/scaleH="\d+"/, 'scaleH="' + img.height + '"');
    pak.set(fntId, Buffer.from(xml, 'utf8'), 'TEXT');
    pak.set(pngId, png.encode(img), 'IMAGE');
    n++;
  }
  report.push('ok   fonts: ' + n + (skipped.length ? ' (not in game: ' + skipped.join(',') + ')' : ''));
}

module.exports = { apply };
