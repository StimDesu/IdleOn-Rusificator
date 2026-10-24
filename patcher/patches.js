// Text patches for N.js. Minified identifiers change between game builds, so every
// pattern matches identifiers with \w+ / backreferences instead of literal names.
// A patch that finds nothing is reported and skipped: the game keeps working,
// only that feature is missing.
'use strict';

const ID = '[\\w$]+';

module.exports = [
  {
    name: 'expose Haxe class registry',
    required: true,
    find: new RegExp('(' + ID + ')\\.lime=\\1\\.lime\\|\\|\\{\\};var (' + ID + ')=\\{\\},'),
    replace: (m, L, A) => L + '.lime=' + L + '.lime||{};var ' + A + '=globalThis.__idleonHx={},',
  },
  {
    name: 'language panel: 8 flags (character creation)',
    find: /(\[153\]=Math\.max\(1,Math\.min\()7(,Math\.floor\(\(\w+\.getMouseX\(\)-382\)\/44\)\+1\)\))/,
    replace: (m, a, b) => a + '8' + b,
  },
  {
    name: 'language panel: 8 flags (login)',
    find: /(\[153\]=Math\.min\()7(,Math\.floor\(\(\w+\.getMouseX\(\)-154\)\/25\+1\)\))/,
    replace: (m, a, b) => a + '8' + b,
  },
  {
    name: 'language panel: click area for the 8th flag',
    find: /(IsXYmouseWithinBounds\(382,)690(,480,530\))/,
    replace: (m, a, b) => a + '734' + b,
  },
];
