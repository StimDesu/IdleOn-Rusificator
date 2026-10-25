// Translation of text that lives in the game code itself (UI labels, fragments the game glues
// numbers into: "*" + n + "_Kills"). Every listed double-quoted literal becomes
//   (__ruL?"Russian":"English")
// so the language can still be switched at runtime (runtime/ru.js keeps __ruL up to date).
// Only literals in ordinary code positions are touched: not object keys, not strings the code
// compares with (those are ids), and nothing inside other string literals.
'use strict';

// calls whose string argument is an id, never text
const ID_CALLS = /(?:getGameAttribute|setGameAttribute|shout|indexOf|split|getLoadList|getLoad|addSaveEntry\w*|getActor\w*|getImage\w*|getExternalImage|getSound|playSound|createRecycledActor|getActorType\w*|getScene\w*|getValue|setValue|hasOwnProperty)\($/;

function patchLiterals(src, dict, protect) {
  let out = '', last = 0, count = 0;
  let i = 0, prev = '';
  const n = src.length;
  const REGEX_BEFORE = '(,=:[!&|?{};+-*%<>~^';
  while (i < n) {
    const ch = src[i];
    if (ch === '"' || ch === "'" || ch === '`') {
      let j = i + 1, esc = false;
      while (j < n && src[j] !== ch) {
        if (src[j] === '\\') { esc = true; j += 2; } else j++;
      }
      if (ch === '"' && !esc) {
        const s = src.slice(i + 1, j);
        const ru = dict[s];
        if (ru !== undefined && ru !== s && !protect.has(s)) {
          let k = j + 1;
          while (k < n && src[k] === ' ') k++;
          const isKey = src[k] === ':' && (prev === '{' || prev === ',');
          const before = src.slice(Math.max(0, i - 40), i);
          if (!isKey && !ID_CALLS.test(before) && !/case$/.test(before)) {
            out += src.slice(last, i) + '(__ruL?' + JSON.stringify(ru) + ':"' + s + '")';
            last = j + 1;
            count++;
          }
        }
      }
      i = j + 1;
      prev = ch;
    } else if (ch === '/' && (prev === '' || REGEX_BEFORE.indexOf(prev) >= 0)) {
      let j = i + 1, cls = false;
      while (j < n) {
        const c = src[j];
        if (c === '\\') { j += 2; continue; }
        if (c === '[') cls = true;
        else if (c === ']') cls = false;
        else if (c === '/' && !cls) break;
        else if (c === '\n') break;
        j++;
      }
      i = j + 1;
      prev = '/';
    } else {
      if (ch !== ' ' && ch !== '\n' && ch !== '\t' && ch !== '\r') prev = ch;
      i++;
    }
  }
  return { src: out + src.slice(last), count: count };
}

module.exports = { patchLiterals };
