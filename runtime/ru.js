// IdleOn Russian translation runtime. Loaded by index.html after N.js, before lime.embed().
// The game module itself runs inside lime.embed(), so hooks are installed right before
// ApplicationMain.main() starts the engine (all game classes exist at that point).
(function (g) {
  'use strict';
  var RU = g.__idleonRU = g.__idleonRU || { version: 1, log: [] };
  function log(s) { RU.log.push(String(s)); if (RU.log.length > 300) RU.log.shift(); }
  RU.logf = log;

  var RU_VALUE = 8;            // OptionsListAccount[153]: 1..7 are the game's flags, 8 is ours
  var RU_INDEX = RU_VALUE - 3; // _customBlock_Language()
  var STORE = 'IdleOnRU';
  RU.RU_VALUE = RU_VALUE;
  RU.RU_INDEX = RU_INDEX;

  // __ruL: true while Russian is on; code literals patched by patcher/lib/literals.js read it
  // Until the save's options have switched to Russian once, trust the stored choice: the AFK
  // gains popup is built while loading, before OptionsListAccount[153] says 8.
  Object.defineProperty(g, '__ruL', { configurable: true, get: function () {
    if (!stored()) return false;
    if (!RU.isRU) return true;
    if (RU.isRU()) { RU.ruSeen = true; return true; }
    return !RU.ruSeen;
  } });

  function stored() { try { return g.localStorage.getItem(STORE) === '1'; } catch (e) { return false; } }
  function store(on) { try { g.localStorage.setItem(STORE, on ? '1' : '0'); } catch (e) {} }
  RU.stored = stored;

  // ---- wait for the class registry (exposed by the N.js patch) ------------------------
  var registry = null, booted = false;
  function onRegistry(reg) {
    registry = reg;
    var appMain;
    Object.defineProperty(reg, 'ApplicationMain', {
      configurable: true, enumerable: true,
      get: function () { return appMain; },
      set: function (M) {
        appMain = M;
        var mainFn;
        Object.defineProperty(M, 'main', {
          configurable: true, enumerable: true,
          get: function () {
            return function () {
              boot();
              return mainFn.apply(this, arguments);
            };
          },
          set: function (f) { mainFn = f; },
        });
      },
    });
  }
  if (g.__idleonHx) onRegistry(g.__idleonHx);
  else {
    Object.defineProperty(g, '__idleonHx', {
      configurable: true, enumerable: false,
      get: function () { return registry; },
      set: function (v) { onRegistry(v); },
    });
  }

  function boot() {
    if (booted) return;
    booted = true;
    try {
      install(registry);
      log('boot ok');
    } catch (e) {
      log('boot failed: ' + (e && e.stack || e));
    }
  }

  RU.modules = RU.modules || [];   // other runtime files push install(HX, RU) functions here

  function install(HX) {
    RU.HX = HX;
    var Engine = HX['com.stencyl.Engine'];
    function attr(n) { var e = Engine && Engine.engine; return e && e.gameAttributes ? e.gameAttributes.h[n] : undefined; }
    RU.attr = attr;
    function options() { var o = attr('OptionsListAccount'); return Array.isArray(o) && o.length > 153 ? o : null; }
    function isRU() { var o = options(); return !!o && Number(o[153]) === RU_VALUE; }
    RU.isRU = isRU;
    // keywords the game finds inside dialogue text to colour them (see patcher/patches.js)
    var KW = { 'QUEST:': 'КВЕСТ:', 'REWARD:': 'НАГРАДА:' };
    globalThis.__ruKW = function (k) { return isRU() && KW[k] || k; };

    var Blocks = null;
    for (var k in HX) {
      var c = HX[k];
      if (c && Object.prototype.hasOwnProperty.call(c, '_customBlock_Language')) { Blocks = c; break; }
    }
    if (Blocks) {
      // Russian runs the game's English code path (Language() = -1): every translated
      // string comes from our dictionary, the game's own FR/DE/KO/JA/ZH tables are unused.
      var origLanguage = Blocks._customBlock_Language;
      Blocks._customBlock_Language = function () {
        if (isRU()) return -1;
        return origLanguage.apply(this, arguments);
      };
    } else log('Language block not found');

    // ---- cloud save: never send our language value -------------------------------------
    // Other clients (web/mobile without the mod) only know values 1..7.
    function hookSave() {
      var R = g.React;
      if (!R || !R.createElement || R.createElement.__ru) return;
      var orig = R.createElement;
      var wrapped = function (type, args) {
        // the game saves OptionsListAccount under the key "OptLacc"; match the array itself
        if (type === 'addSaveEntryList' && args && Array.isArray(args[1]) && (args[1] === options() || args[0] === 'OptLacc') && Number(args[1][153]) === RU_VALUE) {
          var copy = args[1].slice();
          copy[153] = 1;
          return orig.call(this, type, [args[0], copy]);
        }
        var res = orig.apply(this, arguments);
        // account options arrive from the save: switch to Russian right away, before the
        // game builds its first screens (AFK gains popup) from them
        if (type === 'getLoadList' && args && args[0] === 'OptLacc' && Array.isArray(res) && res.length > 153 && stored()) {
          res[153] = RU_VALUE;
          setTimeout(function () { if (RU.applyData) RU.applyData(); }, 0);
        }
        return res;
      };
      wrapped.__ru = true;
      R.createElement = wrapped;
    }

    // ---- local save (Script.saveGame -> SharedObject): same rule, and no translated data ----
    // The local save holds the raw game attributes; an unpatched game reading [153]=8 or our
    // Russian strings from it would break, so the save is written from the English state.
    var Script = null;
    for (var sk in HX) {
      var sc = HX[sk];
      if (sc && typeof sc.saveGame === 'function' && typeof sc.loadGame === 'function') { Script = sc; break; }
    }
    if (Script && !Script.saveGame.__ru) {
      var origSave = Script.saveGame;
      Script.saveGame = function () {
        var o = options(), was = o && Number(o[153]) === RU_VALUE, data = was && RU.revertData;
        if (was) o[153] = 1;
        if (data) RU.revertData();
        try { return origSave.apply(this, arguments); }
        finally {
          if (was) o[153] = RU_VALUE;
          // the game swaps its data maps for empty ones around saveGame and puts them back
          // right after it returns, so translate again once the real maps are back
          if (data && RU.applyData) setTimeout(function () { RU.applyData(); }, 0);
        }
      };
      Script.saveGame.__ru = true;
    } else if (!Script) log('saveGame not found');

    // ---- keep the language choice in sync with localStorage ----------------------------
    var lastOptions = null, lastValue = null, prevLang = 1;
    var listeners = [];
    RU.onChange = function (f) { listeners.push(f); };
    function changed(on) {
      for (var i = 0; i < listeners.length; i++) {
        try { listeners[i](on); } catch (e) { log('listener: ' + (e && e.stack || e)); }
      }
    }
    function watch() {
      hookSave();
      var o = options();
      if (!o) return;
      var before = lastValue === RU_VALUE;
      if (o !== lastOptions) {            // save loaded from the cloud
        lastOptions = o;
        if (stored() && Number(o[153]) !== RU_VALUE) o[153] = RU_VALUE;
      } else if (before && Number(o[153]) !== RU_VALUE) {
        store(false);                     // player picked another flag
      } else if (!before && Number(o[153]) === RU_VALUE) {
        store(true);                      // player picked the Russian flag
      }
      lastValue = Number(o[153]);
      if (lastValue !== RU_VALUE && lastValue >= 1) prevLang = lastValue;
      var now = lastValue === RU_VALUE;
      if (now !== before) changed(now);
    }
    RU.watch = watch;
    setInterval(watch, 200);
    RU.setRU = function (on) {
      var o = options();
      store(on);
      if (o) o[153] = on ? RU_VALUE : prevLang;
      watch();
    };

    for (var i = 0; i < RU.modules.length; i++) {
      try { RU.modules[i](HX, RU); } catch (e) { log('module ' + i + ': ' + (e && e.stack || e)); }
    }
  }
})(globalThis);
