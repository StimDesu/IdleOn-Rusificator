// Russian versions of images with English text baked in (pak/assets/data/ru/<name>, same size
// as the originals). The game builds its UI from images once (getExternalImage -> Bitmap
// attached to an actor), so every image name gets one shared picture whose pixels are copied
// from the English or the Russian version; switching the language repaints them in place.
(function (g) {
  'use strict';
  var RU = g.__idleonRU;
  RU.modules.push(function (HX, RU) {
    var Script = HX['com.stencyl.behavior.Script'];
    var Point = HX['openfl.geom.Point'];
    if (!Script || !Script.getExternalImage || !Point) { RU.logf('images: hooks not found'); return; }
    var names = new Set((g.__IDLEON_RU_DATA__ || {}).images || []);
    var shown = new Map();   // image name -> {img, en, ru}
    var subs = [];           // pieces cut from a shown image: {img, from, args}
    var tagged = new WeakMap();  // shown picture -> its entry
    var ORIGIN = new Point(0, 0);
    function on() { return !!(RU.isRU && RU.isRU()); }
    function paint(dst, src) {
      try { dst.copyPixels(src, src.rect, ORIGIN); } catch (e) { RU.logf('images: ' + e); }
    }

    var origGet = Script.getExternalImage;
    Script.getExternalImage = function (name) {
      if (!names.has(name)) return origGet.apply(this, arguments);
      var s = shown.get(name);
      if (!s) {
        var img = origGet.call(this, name), en, ru;
        // the loader may hand out the same object again, so keep a real copy of the English one
        try { en = img.clone(); ru = origGet.call(this, 'ru/' + name); } catch (e) {
          RU.logf('images: no ru/' + name); return img;
        }
        if (!img || !en || !ru) return img;
        s = { img: img, en: en, ru: ru, isRu: false };
        shown.set(name, s);
        tagged.set(img, s);
        if (on()) { paint(img, ru); s.isRu = true; }
      }
      return s.img;
    };

    if (Script.getSubImage) {
      var origSub = Script.getSubImage;
      Script.getSubImage = function (img) {
        var s = img && typeof img === 'object' ? tagged.get(img) : null;
        var piece = origSub.apply(this, arguments);
        if (s && piece) subs.push({ img: piece, from: s, args: Array.prototype.slice.call(arguments, 1), isRu: s.isRu });
        return piece;
      };
    }

    // each picture remembers which version it shows, so nothing depends on when the
    // language became known
    function repaint() {
      var ru = on();
      shown.forEach(function (s) {
        if (s.isRu !== ru) { paint(s.img, ru ? s.ru : s.en); s.isRu = ru; }
      });
      subs.forEach(function (p) {
        if (p.isRu === ru) return;
        var piece = origSub.apply(Script, [ru ? p.from.ru : p.from.en].concat(p.args));
        if (piece) paint(p.img, piece);
        p.isRu = ru;
      });
    }
    if (RU.onChange) RU.onChange(repaint);
    setInterval(repaint, 500);
    RU.logf('images: ' + names.size + ' Russian images');
  });
})(globalThis);
