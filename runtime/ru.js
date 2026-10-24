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
        if (type === 'addSaveEntryList' && args && args[0] === 'OptionsListAccount' && Array.isArray(args[1]) && Number(args[1][153]) === RU_VALUE) {
          var copy = args[1].slice();
          copy[153] = 1;
          return orig.call(this, type, [args[0], copy]);
        }
        return orig.apply(this, arguments);
      };
      wrapped.__ru = true;
      R.createElement = wrapped;
    }

    // ---- keep the language choice in sync with localStorage ----------------------------
    var lastOptions = null, lastValue = null;
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
      var now = lastValue === RU_VALUE;
      if (now !== before) changed(now);
    }
    RU.watch = watch;
    setInterval(watch, 200);
    RU.setRU = function (on) {
      var o = options();
      store(on);
      if (o) o[153] = on ? RU_VALUE : 1;
      watch();
    };

    for (var i = 0; i < RU.modules.length; i++) {
      try { RU.modules[i](HX, RU); } catch (e) { log('module ' + i + ': ' + (e && e.stack || e)); }
    }
  }
})(globalThis);
