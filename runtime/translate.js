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
        // "Bravery" is an id too when the game builds "Bravery_Monument" from it
        var u = k.indexOf('_');
        if (u > 0) keys.add(k.slice(0, u));
        var x = c[k];
        if (x && typeof x === 'object') collectKeys(x, depth + 1);
      }
    }
    // Item and monster definitions mix text with ids the code compares with its own values
    // (an item's Class against "ARCHER" from the player's class, a monster's Type against a
    // list it builds, its Name searched for "_Rune"). Only their text fields are translated
    // in the data; the rest is translated where it is drawn.
    var ITEM_TEXT = { displayName: 1, UQ1txt: 1, UQ2txt: 1 };
    var MONSTER_TEXT = { Name: 1 };
    function textFields(c) {
      if ('typeGen' in c || 'lvReqToEquip' in c || 'desc_line1' in c) return ITEM_TEXT;
      if ('MonsterFace' in c) return MONSTER_TEXT;
      return null;
    }
    function replaceIn(v, depth) {
      if (depth > 9) return;
      var c = children(v);
      if (!c) return;
      var isArr = Array.isArray(c);
      var list = isArr ? null : Object.keys(c);
      var n = isArr ? c.length : list.length;
      var only = isArr ? null : textFields(c);
      for (var i = 0; i < n; i++) {
        var k = isArr ? i : list[i];
        var x = c[k];
        if (typeof x === 'string') {
          if (!isArr && DESC_KEY.test(k)) continue;   // whole descriptions only, see applyItems
          if (only && !only[k]) continue;
          if (only === MONSTER_TEXT && x.indexOf('_Rune') !== -1) continue;
          var ru = dict.get(x);
          if (ru !== undefined && ru !== x && !protectedStr.has(x) && !keys.has(x)) {
            c[k] = ru;
            applied.push([c, k, x, ru]);
          }
        } else if (x && typeof x === 'object') replaceIn(x, depth + 1);
      }
    }
    // The game rebuilds ItemDefinitionsGET / MonsterDefinitionsGET / DialogueDefGET as deep
    // copies of these cached static maps (when the live map is empty, e.g. around saves), so
    // the sources are translated too and every new copy comes out Russian.
    var SOURCES = ['scripts.ItemDefinitions', 'scripts.ItemDefinitions2', 'scripts.ItemDefinitions3',
      'scripts.ItemDefinitions4', 'scripts.ItemDefinitions5', 'scripts.ItemDefinitions6',
      'scripts.MonsterDefinitions', 'scripts.DialogueDefinitions', 'scripts.DialogueDefinitions2',
      'scripts.CustomMaps'];
    function sources() {
      var out = [];
      for (var i = 0; i < SOURCES.length; i++) {
        var c = HX[SOURCES[i]], m = null;
        try { m = c && typeof c.get === 'function' ? c.get() : null; } catch (e) {}
        if (m && typeof m === 'object') out.push(m);
      }
      return out;
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
      sources().forEach(function (m) { f(m); });
    }
    // copies made from translated sources are not in `applied`: put them back to English
    // through the reverse of what was applied
    var DESC_KEY = /^desc_line\d+$/;
    function revertCopies(rev, v, depth) {
      if (depth > 9) return;
      var c = children(v);
      if (!c) return;
      var isArr = Array.isArray(c);
      var list = isArr ? null : Object.keys(c);
      var n = isArr ? c.length : list.length;
      for (var i = 0; i < n; i++) {
        var k = isArr ? i : list[i], x = c[k];
        if (typeof x === 'string') {
          if (isArr || !DESC_KEY.test(k)) { var en = rev.get(x); if (en !== undefined) c[k] = en; }
        }
        else if (x && typeof x === 'object') revertCopies(rev, x, depth + 1);
      }
    }
    function revertData() {
      if (!applied.length) return;
      var rev = new Map();
      for (var i = applied.length - 1; i >= 0; i--) {
        var a = applied[i];
        if (typeof a[1] !== 'string' || !DESC_KEY.test(a[1])) rev.set(a[3], a[2]);
        if (a[0][a[1]] === a[3]) a[0][a[1]] = a[2];
      }
      applied = [];
      eachRoot(function (v) { revertCopies(rev, v, 0); });
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
      // only the live map: copies from the sources keep English lines, so they can always
      // be matched against DESCS and reverted exactly
      var live = RU.attr('ItemDefinitionsGET');
      if (live) applyItemMap(live.h || live);
    }
    function applyItemMap(defs) {
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
        if (!root) continue;
        var h = root.h || root;
        s.push(h);
        if (ROOTS[r] === 'CustomLists' || ROOTS[r] === 'CustomMaps') {
          for (var name in h) s.push(h[name]);
        } else {
          // definitions are filled in place while the save loads: watch the entry count and
          // the first and last entries, so a refill is noticed and translated again
          var n = 0, first, last;
          for (var id in h) { if (!n) first = h[id]; last = h[id]; n++; }
          s.push(n, first, last);
        }
      }
      return s;
    }
    function sameSig(a, b) {
      if (a.length !== b.length) return false;
      for (var i = 0; i < a.length; i++) if (a[i] !== b[i]) return false;
      return true;
    }
    // a few applied values: if the game writes English back into them, translate again
    function overwritten() {
      var step = Math.max(1, Math.floor(applied.length / 40));
      for (var i = 0; i < applied.length; i += step) {
        var a = applied[i];
        if (a[0][a[1]] !== a[3]) return true;
      }
      return false;
    }
    var lastRU = false;
    setInterval(function () {
      var on = !!RU.isRU && RU.isRU();
      var sig = currentSignature();
      if (on !== lastRU || (on && (!sameSig(sig, signature) || overwritten()))) {
        signature = sig;
        lastRU = on;
        try { applyData(); } catch (e) { RU.logf('applyData: ' + (e && e.stack || e)); }
        if (!on) revertData();
      }
    }, 500);

    // ---- drawing layer --------------------------------------------------------------
    // strings still drawn in English while Russian is on (for finding what to translate)
    var untranslated = RU.untranslated = new Map();
    var upper = null;
    function tr(s) {
      if (typeof s !== 'string' || s.length < 3) return s;
      var ru = dict.get(s);
      if (ru !== undefined) { RU.stats.draw++; return ru; }
      // the game often draws data strings with '_' already turned into spaces
      if (s.indexOf(' ') >= 0) {
        ru = dict.get(s.replace(/ /g, '_'));
        if (ru !== undefined) { RU.stats.draw++; return ru.replace(/_/g, ' '); }
      }
      // protected names stay English in the data; tooltip titles draw them in capitals
      if (s === s.toUpperCase()) {
        if (!upper) { upper = new Map(); protectedStr.forEach(function (k) { var r = dict.get(k); if (r) upper.set(k.toUpperCase(), r.toUpperCase()); }); }
        ru = upper.get(s) || upper.get(s.replace(/ /g, '_'));
        if (ru !== undefined) { RU.stats.draw++; return s.indexOf(' ') >= 0 ? ru.replace(/_/g, ' ') : ru; }
      }
      if (composite.has(s)) return composite.get(s);
      ru = trGainLine(s);
      if (ru === undefined) ru = trTruncated(s);
      if (ru === undefined) ru = trLabel(s);
      if (composite.size > 20000) composite.clear();
      composite.set(s, ru === undefined ? s : ru);
      if (ru !== undefined) { RU.stats.draw++; return ru; }
      if (/[A-Za-z]{3}/.test(s) && untranslated.size < 20000) untranslated.set(s, (untranslated.get(s) || 0) + 1);
      return s;
    }
    RU.tr = tr;
    // results of the slower lookups below (strings are drawn every frame)
    var composite = new Map();
    // "Green_Mushroom:" (Death Note), "COPPER SET: +60% ..." (set list): a label and a colon,
    // maybe followed by more text; each part is translated on its own
    function trLabel(s) {
      var m = /^([^:;]+?)([:;][_ ]?)(.*)$/.exec(s);
      if (!m || m[1].length < 3) return undefined;
      var head = tr(m[1]), tail = m[3] ? tr(m[3]) : '';
      if (head === m[1] && tail === m[3]) return undefined;
      return head + m[2] + tail;
    }
    // long texts cut to fit a box ("*Warrior,_Archer_or_Ma..."): find the full English text
    // by its start and cut the Russian one to the same length; a leading marker (* ^ & #)
    // is kept as is
    var sortedKeys = null, truncCache = new Map();
    function startingWith(prefix) {
      if (!sortedKeys) sortedKeys = Array.from(dict.keys()).sort();
      var lo = 0, hi = sortedKeys.length;
      while (lo < hi) { var mid = (lo + hi) >> 1; if (sortedKeys[mid] < prefix) lo = mid + 1; else hi = mid; }
      return lo < sortedKeys.length && sortedKeys[lo].indexOf(prefix) === 0 ? dict.get(sortedKeys[lo]) : undefined;
    }
    function trTruncated(s) {
      if (s.length < 9 || s.slice(-3) !== '...') return undefined;
      var prefix = s.slice(0, -3);
      if (truncCache.has(prefix)) return truncCache.get(prefix);
      var mark = '', ru = startingWith(prefix);
      if (ru === undefined && /^[*^&#]/.test(prefix)) { mark = prefix[0]; ru = startingWith(prefix.slice(1)); }
      var res;
      if (ru !== undefined) {
        var len = prefix.length - mark.length;
        res = mark + (ru.length <= len ? ru : ru.slice(0, len).replace(/[_,.\s]+$/, '') + '...');
      }
      truncCache.set(prefix, res);
      return res;
    }
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
    // after switching to English, texts the game built while Russian was on (panel labels
    // kept in arrays until the next scene) are put back into English when drawn
    var CYR = /[Ѐ-ӿ]/;
    function back(s) {
      if (typeof s !== 'string' || !RU.rev || !CYR.test(s)) return s;
      var en = RU.rev.get(s);
      return en === undefined ? s : en;
    }
    // ---- fonts without Cyrillic ---------------------------------------------------------
    // Only some of the game's fonts get Cyrillic glyphs (fonts/). Russian text drawn in any
    // other font would come out blank, so it is drawn in the Cyrillic font of the nearest size.
    var Script = HX['com.stencyl.behavior.Script'];
    var cyrFonts = null, subst = new Map();
    function hasCyr(f) {
      var g = f && f.font && f.font._glyphs;
      return !!(g && g.h && g.h[1072] != null && g.h[1040] != null);   // 'а', 'А'
    }
    function height(f) {
      try { return f.font.getFontHeight() * (f.fontScale || 1); } catch (e) { return 0; }
    }
    function substitute(f) {
      if (!f || hasCyr(f)) return f;
      if (subst.has(f)) return subst.get(f);
      if (!cyrFonts) {
        cyrFonts = [];
        (DATA.fonts || []).forEach(function (id) {
          try { var c = Script.getFont(id); if (hasCyr(c)) cyrFonts.push(c); } catch (e) {}
        });
      }
      var h = height(f), best = null, bestD = Infinity;
      cyrFonts.forEach(function (c) {
        var d = Math.abs(height(c) - h);
        if (d < bestD) { bestD = d; best = c; }
      });
      if (best) RU.logf('font ' + f.ID + ' has no Cyrillic, drawn with ' + best.ID);
      subst.set(f, best || f);
      return best || f;
    }
    RU.fontFor = substitute;

    var G = HX['com.stencyl.graphics.G'] || findProto('drawString', 'drawLine');
    if (G) {
      var drawString = G.prototype.drawString;
      G.prototype.drawString = function (text, x, y) {
        text = lastRU ? tr(text) : back(text);
        if (lastRU && typeof text === 'string' && CYR.test(text) && this.font && Script) {
          var f = this.font, s = substitute(f);
          if (s !== f) {
            this.font = s;
            try { return drawString.call(this, text, x, y); } finally { this.font = f; }
          }
        }
        return drawString.call(this, text, x, y);
      };
    } else RU.logf('G.drawString not found');
    var Font = HX['com.stencyl.models.Font'];
    if (Font) {
      var width = Font.prototype.getTextWidth;
      Font.prototype.getTextWidth = function (text) {
        text = lastRU ? tr(text) : back(text);
        if (lastRU && typeof text === 'string' && CYR.test(text) && Script) {
          var s = substitute(this);
          if (s !== this) return width.call(s, text);
        }
        return width.call(this, text);
      };
    } else RU.logf('Font not found');
  });
})(globalThis);
