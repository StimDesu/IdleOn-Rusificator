// Quick EN <-> RU switch in the window title bar (next to "IdleOn"). Works on any screen;
// the choice is the same one the 8th flag makes and is remembered on this computer.
(function (g) {
  'use strict';
  var RU = g.__idleonRU;
  RU.modules.push(function (HX, RU) {
    var doc;
    try { doc = g.top.document; } catch (e) { return; }
    function install() {
      var bar = doc.getElementById('menuBar');
      if (!bar) return false;
      if (doc.getElementById('idleonRuToggle')) return true;
      var btn = doc.createElement('div');
      btn.id = 'idleonRuToggle';
      // inline styles: the launcher's stylesheet wins over an added <style>
      btn.style.cssText = 'position:absolute;left:96px;top:5px;height:22px;padding:0 9px;z-index:10;' +
        '-webkit-app-region:no-drag;cursor:pointer;border:1px solid rgba(255,255,255,.35);border-radius:4px;' +
        'background:rgba(0,0,0,.35);color:#fff;font:bold 11px/20px Verdana,Arial,sans-serif;letter-spacing:.5px;' +
        'user-select:none;display:flex;align-items:center;gap:6px;box-sizing:border-box';
      btn.onmouseenter = function () { btn.style.background = 'rgba(255,255,255,.18)'; };
      btn.onmouseleave = function () { btn.style.background = 'rgba(0,0,0,.35)'; };
      btn.title = 'Язык игры / Game language';
      btn.addEventListener('click', function (ev) {
        ev.stopPropagation();
        RU.setRU(!RU.isRU());
        render();
      });
      bar.appendChild(btn);
      render();
      return true;
    }
    function render() {
      var btn = doc.getElementById('idleonRuToggle');
      if (!btn) return;
      var on = RU.isRU && RU.isRU();
      var stripes = on ? ['#fff', '#1c3faa', '#d52b1e'] : ['#b22234', '#fff', '#b22234', '#fff', '#b22234'];
      btn.textContent = '';
      var f = doc.createElement('span');
      f.style.cssText = 'display:inline-flex;flex-direction:column;width:18px;height:12px;border:1px solid rgba(0,0,0,.6);box-sizing:border-box';
      for (var i = 0; i < stripes.length; i++) {
        var st = doc.createElement('span');
        st.style.cssText = 'flex:1;background:' + stripes[i];
        f.appendChild(st);
      }
      btn.appendChild(f);
      btn.appendChild(doc.createTextNode(on ? 'РУССКИЙ' : 'ENGLISH'));
    }
    RU.onChange(render);
    var t = setInterval(function () { if (install()) { clearInterval(t); } }, 500);
    setInterval(render, 1000); // options may load after the button appears
  });
})(globalThis);
