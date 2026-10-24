// Safety net: a missing image (e.g. a letter image for a character the game has no picture
// for) makes Lime throw, which kills the game. Return a blank image instead and log it.
(function (g) {
  'use strict';
  var RU = g.__idleonRU;
  RU.modules.push(function (HX, RU) {
    var Script = HX['com.stencyl.behavior.Script'];
    if (!Script || !Script.getExternalImage) { RU.logf('getExternalImage not found'); return; }
    var orig = Script.getExternalImage;
    var missing = RU.missingImages = {};
    Script.getExternalImage = function (name) {
      try {
        return orig.apply(this, arguments);
      } catch (e) {
        if (!missing[name]) { missing[name] = 1; RU.logf('missing image ' + name); }
        var m = /^.*_(\w)\.png$/.exec(String(name));
        var tries = m ? ['__' + m[1] + '.png', 'Blank.png'] : ['Blank.png'];
        for (var i = 0; i < tries.length; i++) {
          try { return orig.call(this, tries[i]); } catch (e2) {}
        }
        throw e;
      }
    };
  });
})(globalThis);
