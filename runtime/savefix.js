// Keeps Russian text out of the cloud save.
// The game copies some text into the save (quest helper labels in QuestHelperMenu, maybe
// more): saved in Russian, it would stay Russian after switching back to English, and the
// old mod's wording would live on forever. Everything sent to the save is passed through a
// Russian -> English map, and QuestHelperMenu in memory is kept English (it is translated
// on screen by the draw layer like any other text).
(function (g) {
  'use strict';
  var RU = g.__idleonRU;
  RU.modules.push(function (HX, RU) {
    var DATA = g.__IDLEON_RU_DATA__ || {};
    var CYR = /[Ѐ-ӿ]/;
    var rev = new Map();
    var dict = DATA.dict || {};
    for (var en in dict) if (Object.prototype.hasOwnProperty.call(dict, en) && !rev.has(dict[en])) rev.set(dict[en], en);
    var extra = DATA.rev || {};
    for (var k in extra) if (Object.prototype.hasOwnProperty.call(extra, k) && !rev.has(k)) rev.set(k, extra[k]);
    RU.rev = rev;

    function hasCyr(v, depth) {
      if (typeof v === 'string') return CYR.test(v);
      if (depth > 8 || !v || typeof v !== 'object') return false;
      var c = v.h && typeof v.h === 'object' ? v.h : v;
      for (var k in c) if (hasCyr(c[k], depth + 1)) return true;
      return false;
    }
    function toEn(s) {
      if (!CYR.test(s)) return s;
      var en = rev.get(s);
      if (en !== undefined) return en;
      // ids the game glues from a list entry and a suffix ("Bravery" + "_Monument"): an older
      // build translated the entry and "Храбрость_Monument" reached the save, where no monster
      // has that id and the game stops on load
      for (var i = s.indexOf('_'); i > 0; i = s.indexOf('_', i + 1)) {
        en = rev.get(s.slice(0, i));
        if (en !== undefined && !CYR.test(s.slice(i))) return en + s.slice(i);
      }
      var c = s.charAt(0);
      if (c === '[' || c === '{') {          // JSON lists saved as strings
        try { return JSON.stringify(clean(JSON.parse(s), 0)); } catch (e) {}
      }
      return s;
    }
    // copy of v with Russian strings mapped back; v itself is not touched
    function clean(v, depth) {
      if (typeof v === 'string') return toEn(v);
      if (depth > 8 || !v || typeof v !== 'object') return v;
      if (Array.isArray(v)) return v.map(function (x) { return clean(x, depth + 1); });
      if (v.h && typeof v.h === 'object') return v;   // Haxe maps: leave as they are
      var o = {};
      for (var k in v) o[k] = clean(v[k], depth + 1);
      return o;
    }
    RU.cleanForSave = clean;

    var R = g.React;
    function hook() {
      R = g.React;
      if (!R || !R.createElement || R.createElement.__ruSave) return;
      var orig = R.createElement;
      var wrapped = function (type, args) {
        if (typeof type === 'string' && type.indexOf('addSaveEntry') === 0 && args && hasCyr(args[1], 0)) {
          try {
            var fixed = clean(args[1], 0);
            if (RU.logf) RU.logf('save: ' + args[0] + ' kept in English');
            return orig.call(this, type, [args[0], fixed]);
          } catch (e) {}
        }
        var res = orig.apply(this, arguments);
        // and the other way: Russian that an older build left in the save is read back as English
        if (typeof type === 'string' && type.indexOf('getLoad') === 0 && hasCyr(res, 0)) {
          try {
            var en = clean(res, 0);
            if (RU.logf) RU.logf('load: ' + (args && args[0]) + ' read back in English');
            if (Array.isArray(res) && Array.isArray(en)) { for (var i = 0; i < en.length; i++) res[i] = en[i]; }
            else res = en;
          } catch (e) {}
        }
        return res;
      };
      wrapped.__ru = orig.__ru;
      wrapped.__ruSave = true;
      R.createElement = wrapped;
    }

    // quest helper rows: ["QuestId", label, have, need, label, have, need, ...]
    function fixMemory() {
      // AFK target is a monster id: a Russian one makes the game stop
      var t = RU.attr('AFKtarget'), E = HX['com.stencyl.Engine'];
      if (typeof t === 'string' && CYR.test(t) && E && E.engine) E.engine.gameAttributes.h.AFKtarget = toEn(t);
      var q = RU.attr('QuestHelperMenu');
      if (!Array.isArray(q)) return;
      for (var i = 0; i < q.length; i++) {
        var row = q[i];
        if (!Array.isArray(row)) continue;
        for (var j = 0; j < row.length; j++) {
          if (typeof row[j] === 'string' && CYR.test(row[j])) {
            var en = rev.get(row[j]);
            if (en !== undefined) row[j] = en;
          }
        }
      }
    }
    setInterval(function () { try { hook(); fixMemory(); } catch (e) {} }, 500);
  });
})(globalThis);
