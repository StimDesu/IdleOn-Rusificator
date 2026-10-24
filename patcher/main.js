// IdleOn Russian translation installer.
// Runs on the game's own Electron in Node mode (ELECTRON_RUN_AS_NODE=1), Node 12.
//
//   main.js install   [--game <dir>]   patch resources/app.asar (keeps a backup of the original)
//   main.js uninstall [--game <dir>]   restore the original app.asar
//   main.js dev <orig.asar> <dir>      write patched files into an unpacked app folder (development)
'use strict';
const fs = require('fs');
const path = require('path');
const { Archive, writeArchive } = require('./lib/asar');
const { Pak } = require('./lib/pak');
const patches = require('./patches');
const fonts = require('./lib/fonts');

const ROOT = path.resolve(__dirname, '..');
const GAME_DIR = 'distBuild/static/game/';
const MARKER = '<!--IDLEON_RU-->';
const BACKUP = 'app.asar.ru-backup';

function log(s) { process.stdout.write(s + '\n'); }

function applyTextPatches(njs, report) {
  for (const p of patches) {
    let count = 0;
    njs = njs.replace(p.find, function () {
      count++;
      return p.replace.apply(null, arguments);
    });
    report.push((count ? 'ok   ' : 'MISS ') + p.name + (p.all ? ' (' + count + ')' : ''));
    if (!count && p.required) throw new Error('required patch failed: ' + p.name);
  }
  return njs;
}

function readJson(p) { return JSON.parse(fs.readFileSync(p, 'utf8')); }

function readDictDir(dir, into) {
  if (!fs.existsSync(dir)) return 0;
  let n = 0;
  for (const f of fs.readdirSync(dir).sort()) {
    if (!f.endsWith('.json')) continue;
    const d = readJson(path.join(dir, f));
    for (const k of Object.keys(d)) {
      if (typeof d[k] === 'string' && d[k] !== '') { into[k] = d[k]; n++; }
    }
  }
  return n;
}

// Literals the code compares strings with: such strings are ids, not text, and must keep
// their English value inside the game data (they are still translated on screen).
function comparedLiterals(njs) {
  const out = new Set();
  const res = [
    /"((?:[^"\\]|\\.)+)"(?:==|!=)/g,
    /(?:==|!=)"((?:[^"\\]|\\.)+)"/g,
    /\.indexOf\("((?:[^"\\]|\\.)+)"\)/g,
    /case"((?:[^"\\]|\\.)+)":/g,
    /\.h\["((?:[^"\\]|\\.)+)"\]/g,
  ];
  for (const re of res) {
    let m;
    while ((m = re.exec(njs))) out.add(m[1]);
  }
  return out;
}

// Everything the runtime needs, bundled into one script (file:// pages cannot fetch JSON).
// Reviewed translations (translation/*.json) override drafts (translation/draft/*.json).
function buildRuntimeData(njs, report) {
  const dict = {};
  const nDraft = readDictDir(path.join(ROOT, 'translation', 'draft'), dict);
  const nFinal = readDictDir(path.join(ROOT, 'translation'), dict);
  const lits = comparedLiterals(njs);
  const protect = Object.keys(dict).filter(k => lits.has(k));
  report.push('ok   translation: ' + Object.keys(dict).length + ' strings (draft ' + nDraft + ', reviewed ' + nFinal + '), protected ' + protect.length);
  return 'globalThis.__IDLEON_RU_DATA__=' + JSON.stringify({ dict: dict, protect: protect }) + ';\n';
}

// Returns {path: Buffer} of files to write into the archive.
function build(src, report) {
  const out = {};
  let html = src.read(GAME_DIR + 'index.html').toString('utf8');
  if (html.indexOf(MARKER) >= 0) throw new Error('source archive is already patched');
  const anchor = /<script[^>]*>\s*lime\.embed\(/;
  if (!anchor.test(html)) throw new Error('lime.embed not found in index.html');
  // ru.js first (it sets up the boot hook), then the feature modules
  const runtime = fs.readdirSync(path.join(ROOT, 'runtime')).filter(f => f.endsWith('.js') && f !== 'ru.js').sort();
  const tags = ['data.js', 'ru.js'].concat(runtime).map(f => '<script src="./ru/' + f + '"></script>').join('');
  html = html.replace(anchor, s => MARKER + tags + '\n    ' + s);
  out[GAME_DIR + 'index.html'] = Buffer.from(html, 'utf8');

  let njs = src.read(GAME_DIR + 'N.js').toString('utf8');
  njs = applyTextPatches(njs, report);

  const pak = new Pak(njs, src.read(GAME_DIR + 'lib/default.pak'));
  fonts.apply(pak, path.join(ROOT, 'fonts'), report);
  const imgDir = path.join(ROOT, 'images');
  let nImg = 0;
  if (fs.existsSync(imgDir)) {
    for (const f of fs.readdirSync(imgDir)) {
      if (!f.endsWith('.png')) continue;
      pak.set('assets/data/ru/' + f, fs.readFileSync(path.join(imgDir, f)), 'IMAGE');
      nImg++;
    }
  }
  report.push('ok   images: ' + nImg);
  const built = pak.build();
  out[GAME_DIR + 'N.js'] = Buffer.from(built.njs, 'utf8');
  out[GAME_DIR + 'lib/default.pak'] = built.pak;

  out[GAME_DIR + 'ru/data.js'] = Buffer.from(buildRuntimeData(njs, report), 'utf8');
  for (const f of fs.readdirSync(path.join(ROOT, 'runtime'))) {
    if (f.endsWith('.js')) out[GAME_DIR + 'ru/' + f] = fs.readFileSync(path.join(ROOT, 'runtime', f));
  }
  return out;
}

function isPatched(asarFile) {
  try {
    const a = new Archive(asarFile);
    return a.read(GAME_DIR + 'index.html').toString('utf8').indexOf(MARKER) >= 0;
  } catch (e) {
    return false;
  }
}

function findGame(arg) {
  const candidates = [];
  if (arg) candidates.push(arg);
  candidates.push(path.resolve(ROOT, '..'), process.cwd(), path.dirname(process.execPath));
  for (const c of candidates) {
    if (fs.existsSync(path.join(c, 'resources', 'app.asar'))) return c;
  }
  throw new Error('Legends of Idleon not found. Use --game "<game folder>"');
}

function install(gameDir) {
  const res = path.join(gameDir, 'resources');
  const asar = path.join(res, 'app.asar');
  const backup = path.join(res, BACKUP);
  if (!isPatched(asar)) {
    // Fresh game files (first install or after a Steam update): they become the new backup.
    fs.copyFileSync(asar, backup);
    log('Backup: ' + backup);
  } else if (!fs.existsSync(backup)) {
    throw new Error('app.asar is patched but ' + BACKUP + ' is missing. Verify game files in Steam and retry.');
  }
  const src = new Archive(backup);
  const report = [];
  const files = build(src, report);
  report.forEach(log);
  writeArchive(src, files, asar);
  log('Installed.');
}

function uninstall(gameDir) {
  const res = path.join(gameDir, 'resources');
  const backup = path.join(res, BACKUP);
  if (!fs.existsSync(backup)) { log('Nothing to restore (no backup).'); return; }
  fs.copyFileSync(backup, path.join(res, 'app.asar'));
  fs.unlinkSync(backup);
  log('Original files restored.');
}

function dev(origAsar, dir) {
  const src = new Archive(origAsar);
  const report = [];
  const files = build(src, report);
  report.forEach(log);
  for (const p of Object.keys(files)) {
    const dst = path.join(dir, p);
    fs.mkdirSync(path.dirname(dst), { recursive: true });
    fs.writeFileSync(dst, files[p]);
  }
  log('Dev files written: ' + Object.keys(files).length);
}

function main() {
  const a = process.argv.slice(2);
  const gi = a.indexOf('--game');
  const gameArg = gi >= 0 ? a[gi + 1] : null;
  try {
    if (a[0] === 'install') install(findGame(gameArg));
    else if (a[0] === 'uninstall') uninstall(findGame(gameArg));
    else if (a[0] === 'dev') dev(a[1], a[2]);
    else log('usage: main.js install|uninstall [--game dir] | dev <orig.asar> <dir>');
  } catch (e) {
    log('ERROR: ' + (e && e.stack || e));
    process.exitCode = 1;
  }
}

main();
