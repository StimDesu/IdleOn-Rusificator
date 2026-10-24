// Translation layers.
//  1. Game data: strings inside CustomLists / CustomMaps / item, monster, dialogue and attack
//     definitions are replaced in place (originals are remembered, switching back restores
//     them). Everything that reads the data - quest log, quest helper, tooltips, shops - then
//     shows the same Russian name, so items requested by quests match the inventory.
//  2. Drawing: strings that are hardcoded in the game code are translated when drawn
//     (drawString / getTextWidth), as a safety net for anything not stored in the data.
// Strings the game uses as keys (map keys, literals compared in code) are never replaced in
// the data, only on screen.
(function (g) {
  'use strict';
  var RU = g.__idleonRU;
  RU.modules.push(function (HX, RU) {
    var DATA = g.__IDLEON_RU_DATA__ || {};
    var dict = new Map();
    var src = DATA.dict || {};
    for (var k in src) if (Object.prototype.hasOwnProperty.call(src, k)) dict.set(k, src[k]);
    var protectedStr = new Set(DATA.protect || []);
    RU.dict = dict;
    RU.stats = { data: 0, draw: 0 };

    var ROOTS = ['CustomLists', 'CustomMaps', 'ItemDefinitionsGET', 'MonsterDefinitionsGET', 'DialogueDefGET', 'AttackMoveGET'];
    // other languages' data, never shown in Russian mode
    var SKIP = /^(NPCdialogue\d+|\w*LANG\w*|LangMapName|CardBonusDesc|EquipmentBonusMISC|SkillInfoDesc)$/;

    // ---- data layer -----------------------------------------------------------------
    var applied = [];       // [container, key, en, ru]
    var keys = new Set();   // map keys seen in game data (ids)

    function children(v) {
      if (Array.isArray(v)) return v;
      if (v && typeof v === 'object') return v.h && typeof v.h === 'object' ? v.h : v;
      return null;
    }
    function collectKeys(v, depth) {
      if (depth > 9) return;
      var c = children(v);
      if (!c) return;
      if (Array.isArray(c)) { for (var i = 0; i < c.length; i++) if (c[i] && typeof c[i] === 'object') collectKeys(c[i], depth + 1); return; }
      for (var k in c) {
        keys.add(k);
        var x = c[k];
        if (x && typeof x === 'object') collectKeys(x, depth + 1);
      }
    }
    function replaceIn(v, depth) {
      if (depth > 9) return;
      var c = children(v);
      if (!c) return;
      var isArr = Array.isArray(c);
      var list = isArr ? null : Object.keys(c);
      var n = isArr ? c.length : list.length;
      for (var i = 0; i < n; i++) {
        var k = isArr ? i : list[i];
        var x = c[k];
        if (typeof x === 'string') {
          var ru = dict.get(x);
          if (ru !== undefined && ru !== x && !protectedStr.has(x) && !keys.has(x)) {
            c[k] = ru;
            applied.push([c, k, x, ru]);
          }
        } else if (x && typeof x === 'object') replaceIn(x, depth + 1);
      }
    }
    function eachRoot(f) {
      for (var r = 0; r < ROOTS.length; r++) {
        var root = RU.attr(ROOTS[r]);
        if (!root) continue;
        var h = root.h || root;
        if (ROOTS[r] === 'CustomLists' || ROOTS[r] === 'CustomMaps') {
          for (var name in h) if (!SKIP.test(name)) f(h[name]);
        } else f(root);
      }
    }
    function revertData() {
      for (var i = applied.length - 1; i >= 0; i--) {
        var a = applied[i];
        if (a[0][a[1]] === a[3]) a[0][a[1]] = a[2];
      }
      applied = [];
    }
    function applyData() {
      revertData();
      if (!RU.isRU()) return;
      keys = new Set();
      eachRoot(function (v) { collectKeys(v, 0); });
      eachRoot(function (v) { replaceIn(v, 0); });
      RU.stats.data = applied.length;
    }
    RU.applyData = applyData;
    RU.revertData = revertData;

    // re-apply when the game rebuilds its data (login, language switch, new lists)
    var signature = [];
    function currentSignature() {
      var s = [];
      for (var r = 0; r < ROOTS.length; r++) {
        var root = RU.attr(ROOTS[r]);
        s.push(root);
        if (root && (ROOTS[r] === 'CustomLists' || ROOTS[r] === 'CustomMaps')) {
          var h = root.h || root;
          for (var name in h) s.push(h[name]);
        }
      }
      return s;
    }
    function sameSig(a, b) {
      if (a.length !== b.length) return false;
      for (var i = 0; i < a.length; i++) if (a[i] !== b[i]) return false;
      return true;
    }
    var lastRU = false;
    setInterval(function () {
      var on = !!RU.isRU && RU.isRU();
      var sig = currentSignature();
      if (on !== lastRU || (on && !sameSig(sig, signature))) {
        signature = sig;
        lastRU = on;
        try { applyData(); } catch (e) { RU.logf('applyData: ' + (e && e.stack || e)); }
        if (!on) revertData();
      }
    }, 500);

    // ---- drawing layer --------------------------------------------------------------
    function tr(s) {
      if (typeof s !== 'string' || s.length < 3) return s;
      var ru = dict.get(s);
      if (ru !== undefined) { RU.stats.draw++; return ru; }
      return s;
    }
    RU.tr = tr;
    function findProto(method, other) {
      for (var k in HX) {
        var c = HX[k];
        if (c && c.prototype && typeof c.prototype[method] === 'function' && (!other || typeof c.prototype[other] === 'function')) return c;
      }
      return null;
    }
    var G = HX['com.stencyl.graphics.G'] || findProto('drawString', 'drawLine');
    if (G) {
      var drawString = G.prototype.drawString;
      G.prototype.drawString = function (text, x, y) {
        if (lastRU) text = tr(text);
        return drawString.call(this, text, x, y);
      };
    } else RU.logf('G.drawString not found');
    var Font = HX['com.stencyl.models.Font'];
    if (Font) {
      var width = Font.prototype.getTextWidth;
      Font.prototype.getTextWidth = function (text) {
        if (lastRU) text = tr(text);
        return width.call(this, text);
      };
    } else RU.logf('Font not found');
  });
})(globalThis);
