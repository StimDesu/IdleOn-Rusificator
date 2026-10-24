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
    // CJK-only branches (Asian font, ';' instead of ':', etc.) are guarded by comparisons
    // like 2<=Language(). Russian is language index 5, so those calls get an argument:
    // the runtime answers "German" for Russian when called with it, the original function
    // ignores arguments (so the game still works if the runtime is missing). Checks for
    // "any translation" (0<=Language()) and list indexing stay untouched.
    name: 'CJK checks ignore Russian',
    all: true,
    find: new RegExp('([2-9]|\\.5)(<=|==|<|>|>=)(' + ID + ')\\._customBlock_Language\\(\\)', 'g'),
    replace: (m, n, op, cls) => n + op + cls + '._customBlock_Language(1)',
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
