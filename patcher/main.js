// IdleOn Russian translation installer.
// Runs on the game's own Electron in Node mode (ELECTRON_RUN_AS_NODE=1), Node 12.
//
//   main.js install   [--game <dir>]   patch resources/app.asar (keeps a backup of the original)
//   main.js uninstall [--game <dir>]   restore the original app.asar
//   main.js dev <orig.asar> <dir>      write patched files into an unpacked app folder (development)
'use strict';
// Electron's fs treats *.asar files as folders; we need the raw archive files
process.noAsar = true;
const fs = require('fs');
const path = require('path');
const { Archive, writeArchive } = require('./lib/asar');
const { Pak } = require('./lib/pak');
const patches = require('./patches');
const fonts = require('./lib/fonts');
const { patchLiterals } = require('./lib/literals');
const crypto = require('crypto');

const ROOT = path.resolve(__dirname, '..');
const GAME_DIR = 'distBuild/static/game/';
const MARKER = '<!--IDLEON_RU';
const BACKUP = 'app.asar.ru-backup';

// The game exe is a GUI program: its stdout may not reach the console, so run.ps1 shows this file.
const LOG_FILE = path.join(__dirname, 'last-run.log');
try { fs.writeFileSync(LOG_FILE, ''); } catch (e) {}
function log(s) {
  if (!process.env.IDLEON_RU_LOG_ONLY) process.stdout.write(s + '\n');
  try { fs.appendFileSync(LOG_FILE, s + '\n'); } catch (e) {}
}

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

// Fingerprint of everything that goes into the build: the launcher re-installs when it changes.
const BUILD_DIRS = ['patcher', 'runtime', 'translation', 'fonts', 'pak'];
function buildVersion() {
  const h = crypto.createHash('sha1');
  for (const d of BUILD_DIRS) {
    (function walk(dir, rel) {
      if (!fs.existsSync(dir)) return;
      for (const f of fs.readdirSync(dir).sort()) {
        const full = path.join(dir, f);
        if (fs.statSync(full).isDirectory()) walk(full, rel + f + '/');
        else if (!/\.(log|ps1|md)$/.test(f)) { h.update(rel + f); h.update(fs.readFileSync(full)); }
      }
    })(path.join(ROOT, d), d + '/');
  }
  return h.digest('hex').slice(0, 12);
}

function readJson(p) { return JSON.parse(fs.readFileSync(p, 'utf8')); }

// translation/*.json: {"English string": "Russian"}. item_desc.json is special: item
// descriptions are split into lines in the game data, so they are keyed by the original
// lines joined with '|' and re-wrapped by the runtime.
const DESC_FILE = 'item_desc.json';
function readDictDir(dir, into, descs) {
  if (!fs.existsSync(dir)) return 0;
  let n = 0;
  for (const f of fs.readdirSync(dir).sort()) {
    if (!f.endsWith('.json')) continue;
    const d = readJson(path.join(dir, f));
    const target = f === DESC_FILE ? descs : into;
    for (const k of Object.keys(d)) {
      if (typeof d[k] === 'string' && d[k] !== '') { target[k] = d[k]; n++; }
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
  const dict = {}, descs = {};
  const nDraft = readDictDir(path.join(ROOT, 'translation', 'draft'), dict, descs);
  const draft = Object.assign({}, dict);
  const nFinal = readDictDir(path.join(ROOT, 'translation'), dict, descs);
  // Russian -> English for strings the game copies into the save (quest helper labels):
  // older drafts and the old mod wrote them there, the runtime turns them back into English
  const rev = {};
  for (const k of Object.keys(draft)) if (draft[k] !== dict[k]) rev[draft[k]] = k;
  const lits = comparedLiterals(njs);
  const protect = Object.keys(dict).filter(k => lits.has(k));
  report.push('ok   translation: ' + Object.keys(dict).length + ' strings (draft ' + nDraft + ', reviewed ' + nFinal + '), protected ' + protect.length);
  return 'globalThis.__IDLEON_RU_DATA__=' + JSON.stringify({ dict: dict, descs: descs, protect: protect, rev: rev }) + ';\n';
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
  html = html.replace(anchor, s => MARKER + ' v=' + buildVersion() + '-->' + tags + '\n    ' + s);
  out[GAME_DIR + 'index.html'] = Buffer.from(html, 'utf8');

  let njs = src.read(GAME_DIR + 'N.js').toString('utf8');
  njs = applyTextPatches(njs, report);
  const codeFile = path.join(ROOT, 'translation', 'code.json');
  if (fs.existsSync(codeFile)) {
    const r = patchLiterals(njs, readJson(codeFile), comparedLiterals(njs));
    njs = r.src;
    report.push('ok   code text: ' + r.count + ' literals');
  }

  const pak = new Pak(njs, src.read(GAME_DIR + 'lib/default.pak'));
  fonts.apply(pak, path.join(ROOT, 'fonts'), report);
  // pak/ mirrors asset ids inside default.pak; U+XXXX in a file name is that character
  // (Windows file names are case-insensitive, Cyrillic letter images need both cases)
  let nImg = 0;
  const pakDir = path.join(ROOT, 'pak');
  (function walk(dir, rel) {
    if (!fs.existsSync(dir)) return;
    for (const f of fs.readdirSync(dir)) {
      const full = path.join(dir, f);
      const id = (rel ? rel + '/' : '') + f.replace(/U\+([0-9A-F]{4,5})/g, (m, h) => String.fromCodePoint(parseInt(h, 16)));
      if (fs.statSync(full).isDirectory()) walk(full, id);
      else if (f.endsWith('.png')) { pak.set(id, fs.readFileSync(full), 'IMAGE'); nImg++; }
    }
  })(pakDir, '');
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

// null = not patched, otherwise the build version stored in index.html
function installedVersion(asarFile) {
  try {
    const html = new Archive(asarFile).read(GAME_DIR + 'index.html').toString('utf8');
    const i = html.indexOf(MARKER);
    if (i < 0) return null;
    const m = /v=([0-9a-f]+)/.exec(html.slice(i, i + 60));
    return m ? m[1] : '';
  } catch (e) {
    return null;
  }
}
function isPatched(asarFile) { return installedVersion(asarFile) !== null; }

// Install only when needed: after a Steam update (unpatched files) or a new translation build.
function ensure(gameDir) {
  const v = installedVersion(path.join(gameDir, 'resources', 'app.asar'));
  if (v === buildVersion()) { log('Russian translation is up to date.'); return; }
  log(v === null ? 'Game files are not patched (new install or game update).' : 'New translation build.');
  install(gameDir);
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
    else if (a[0] === 'ensure') ensure(findGame(gameArg));
    else if (a[0] === 'uninstall') uninstall(findGame(gameArg));
    else if (a[0] === 'dev') dev(a[1], a[2]);
    else log('usage: main.js install|ensure|uninstall [--game dir] | dev <orig.asar> <dir>');
  } catch (e) {
    log('ERROR: ' + (e && e.stack || e));
    process.exitCode = 1;
  }
}

main();
