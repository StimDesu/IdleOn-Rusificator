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
    // login screen panel (UIsound2/3.png) is redrawn with 8 flags at a 23 px pitch from x=150
    name: 'login flags: click maps to 8 flags',
    find: /(\[153\]=Math\.min\()7(,Math\.floor\(\(\w+\.getMouseX\(\)-)154(\)\/)25(\+1\)\))/,
    replace: (m, a, b, c, d) => a + '8' + b + '150' + c + '23' + d,
  },
  {
    name: 'login flags: click area',
    find: /(IsXYmouseWithinBounds\()154,327(,56,84\))/,
    replace: (m, a, b) => a + '150,334' + b,
  },
  {
    name: 'login flags: selection frame position',
    find: /(drawString\("s",Math\.round\()154\+25(\*\(\w+\.asNumber\(\w+\.engine\.getGameAttribute\("OptionsListAccount"\)\[153\]\)-1\)\),65\))/,
    replace: (m, a, b) => a + '149+23' + b,
  },
  {
    name: 'language panel: click area for the 8th flag',
    find: /(IsXYmouseWithinBounds\(382,)690(,480,530\))/,
    replace: (m, a, b) => a + '734' + b,
  },
  {
    // dialogue colours the "QUEST:"/"REWARD:" keyword by its position; in Russian the
    // keyword is translated, so look for whatever runtime/ru.js says it is
    name: 'dialogue keyword colouring',
    find: /\.indexOf\("(QUEST|REWARD):"\)(\+[56])?/g,
    replace: (m, k, plus) => '.indexOf(globalThis.__ruKW?__ruKW("' + k + ':"):"' + k + ':")' +
      (plus ? '+(globalThis.__ruKW?__ruKW("' + k + ':").length-1:' + plus.slice(1) + ')' : ''),
  },
  {
    // sailing island board: the name is an adjective in Russian (runtime/translate.js)
    name: 'island names',
    find: /(this\._DT1=)(""\+\w+\.string\(this\._GenINFO\[8\]\[0\|this\._DRI\]\))/,
    replace: (m, a, b) => a + '(globalThis.__ruIsle?__ruIsle(' + b + '):' + b + ')',
  },
];
