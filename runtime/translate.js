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
    // Item descriptions are pre-split into desc_line1..8, so they are translated as a whole
    // (DATA.descs["line1|line2|..."] = "Russian text", '|' = forced break) and the Russian text
    // is re-wrapped to the width of the original lines. Changed originals stay English.
    var DESCS = DATA.descs || {};
    function wrapLines(text, width) {
      var out = [];
      String(text).split('|').forEach(function (para) {
        var words = para.split('_'), line = '';
        for (var i = 0; i < words.length; i++) {
          var cand = line ? line + '_' + words[i] : words[i];
          if (line && cand.length > width) { out.push(line); line = words[i]; } else line = cand;
        }
        out.push(line);
      });
      return out;
    }
    function set(c, k, ru) {
      if (c[k] === ru) return;
      applied.push([c, k, c[k], ru]);
      c[k] = ru;
    }
    function applyItems() {
      var defs = RU.attr('ItemDefinitionsGET');
      if (!defs) return;
      defs = defs.h || defs;
      for (var id in defs) {
        var it = defs[id], h = it && (it.h || it);
        if (!h || h.desc_line1 == null) continue;
        var lines = [];
        for (var i = 1; i <= 8; i++) { var l = h['desc_line' + i]; if (l != null && l !== 'Filler') lines.push(l); }
        var t = DESCS[lines.join('|')];
        if (t == null) continue;
        var width = 0;
        lines.forEach(function (l) { width = Math.max(width, l.length); });
        var ru = lines.length > 1 ? wrapLines(t, width) : [t];
        while (ru.length > 8 && width < 200) { width += 4; ru = wrapLines(t, width); }
        for (var j = 1; j <= 8; j++) set(h, 'desc_line' + j, ru[j - 1] != null ? ru[j - 1] : 'Filler');
      }
    }

    function applyData() {
      revertData();
      if (!RU.isRU()) return;
      keys = new Set();
      eachRoot(function (v) { collectKeys(v, 0); });
      applyItems();
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
    // strings still drawn in English while Russian is on (for finding what to translate)
    var untranslated = RU.untranslated = new Map();
    function tr(s) {
      if (typeof s !== 'string' || s.length < 3) return s;
      var ru = dict.get(s);
      if (ru !== undefined) { RU.stats.draw++; return ru; }
      // the game often draws data strings with '_' already turned into spaces
      if (s.indexOf(' ') >= 0) {
        ru = dict.get(s.replace(/ /g, '_'));
        if (ru !== undefined) { RU.stats.draw++; return ru.replace(/_/g, ' '); }
      }
      ru = trGainLine(s);
      if (ru !== undefined) { RU.stats.draw++; return ru; }
      if (/[A-Za-z]{3}/.test(s) && untranslated.size < 20000) untranslated.set(s, (untranslated.get(s) || 0) + 1);
      return s;
    }
    RU.tr = tr;
    // AFK gains popup lines ("*89_Kills", "*3,344_Coins", "*1_Bored_Bean_Card") are glued
    // together while the save loads, before the data layer has run, so translate the parts here
    var GAIN_WORDS = { Kills: 'убийств', Coins: 'монет', Main_Exp: 'опыта_класса' };
    function trGainLine(s) {
      var m = /^([*^][\d,.]+[A-Za-z]{0,3}_)(.+?)("?)$/.exec(s);
      if (!m) return undefined;
      var rest = m[2], ru = GAIN_WORDS[rest];
      if (ru === undefined) {
        var card = /^(.+)_Card$/.exec(rest);
        if (card) ru = 'Карта:_' + (dict.get(card[1]) || card[1]);
        else ru = dict.get(rest);
      }
      return ru === undefined ? undefined : m[1] + ru + m[3];
    }
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
