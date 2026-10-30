"""IdleOn fishing minigame overlay.

Shows where the hook will land while you hold the button, and the zones where
each creature on the line can be caught (green) or where a mine ends the game
(red). Reads nothing but the screen: the game is not modified or hooked.

How it works (numbers come from the game code, ActorEvents_229 in N.js):
  * while the button is held the power p = 1 - |sin(t deg)| is shown as the red
    fill of the wooden column (height 64*p); the overlay reads it from the screen;
  * on release the hook flies along vx = 0.4 + 2.06p, vy = -1.4 - 1.45p,
    vy += 0.05 per frame, and lands where it comes back to its start height;
  * a creature is caught when |hook.x - creature.x| < 6 + CATCH_TOL[type]
    (sprite left edges). Creatures are checked before mines: if the hook
    catches anything, a mine under it does no harm.

Auto mode (--auto, toggled with F8) holds and releases Space by itself, timing
the release so the hook lands on a creature where it will be when the hook comes
down: creatures sway as base + A*sin(65 deg/s * t + phase) from the 6th cast on.
"""
import argparse
import ctypes
import json
import math
import sys
import threading
import time
import tkinter as tk
from ctypes import wintypes

from pathlib import Path

import mss
import numpy as np

from sprites import SPRITES

STATE_FILE = Path(__file__).with_name('overlay_state.json')   # learned lead and power speed

# --- game geometry, in game pixels relative to the power column's top-left ---
HOOK_DX = 22          # hook/creature sprite x origin (bx-82 vs column at bx-104)
FISH_DY = 31          # creature sprite top (by-56 vs column at by-87)
COL_ROWS = 64         # fill height at p = 1; fill bottom is at row 64
CATCH_TOL = [6, 6, 9, 10, 12, 13, 17, 17]   # by creature type (sprite MGfsh<type>)
MINE = 5
CREATURES = (2, 3, 4, 6, 7, MINE)
DARK = (83, 61, 39)   # left stripe of the column
LIGHT = (130, 97, 73)  # right stripe
SEPARATOR_ROWS = [10, 19, 28, 37, 46, 55]   # darker rows splitting the column


POINTS = {t: t - 1 + 14 * (t // 7) for t in (2, 3, 4, 6, 7)}   # score for catching each type
SWAY = math.radians(1.3 / 0.020)    # creature sway phase speed, rad/s (+1.3 deg every 20 ms)
SWAY_SLOT = {2: 1, 3: 2, 4: 0, 6: 1, 7: 2}   # sway phase offset in 120 deg steps (sprite slot mod 3)


def flight(p):
    """(hook x offset in game px, frames in the air) after a cast with power p, like the game."""
    x = y = 0.0
    vx, vy = 0.4 + 2.06 * p, -1.4 - 1.45 * p
    n = 0
    while y + vy < 5 or x < 5:
        x += vx
        y += vy
        vy += 0.05
        n += 1
    return x, n


def land_x(p):
    return flight(p)[0]


LAND = [land_x(i / 256) for i in range(257)]
LAND_P = np.linspace(0, 1, 257)
LAND_N = np.array([flight(i / 256)[1] for i in range(257)], float)


def land_at(p):
    p = min(1.0, max(0.0, p))
    i = min(255, int(p * 256))
    f = p * 256 - i
    return LAND[i] * (1 - f) + LAND[i + 1] * f


def sprite_box(key):
    rows = SPRITES[key]['rows']
    xs = [x for r in rows for x, ch in enumerate(r) if ch != '.']
    return min(xs), max(xs) + 1


HOOK_CX = sum(sprite_box(1)) / 2   # visual centre of the hook inside its 35 px sprite


def catch_radius(t):
    return 6 + CATCH_TOL[t]


# --- screen reading -----------------------------------------------------------

def near(img, color, tol):
    return (np.abs(img - np.array(color, np.int16)) <= tol).all(axis=-1)


def runs(idx):
    """Split sorted indices into [start, end] runs of consecutive values."""
    if len(idx) == 0:
        return []
    cut = np.nonzero(np.diff(idx) > 1)[0]
    starts = np.r_[idx[0], idx[cut + 1]]
    ends = np.r_[idx[cut], idx[-1]]
    return list(zip(starts.tolist(), ends.tolist()))


def find_column(img):
    """Locate the power column: returns (fx, fy, s) = its top-left on img and the scale."""
    dark = near(img, DARK, 10)
    cols = np.nonzero(dark.sum(axis=0) >= 25)[0]
    for xa, xb in runs(cols):
        s0 = (xb - xa + 1) / 5                      # dark stripe is 5 sprite px wide
        if s0 < 0.6:
            continue
        xc = (xa + xb) // 2
        segs = [r for r in runs(np.nonzero(dark[:, xc])[0]) if r[1] - r[0] + 1 >= 5 * s0]
        # 7 stripe pieces of 8 rows each, separated by 1-row separators
        for i in range(len(segs) - 6):
            group = segs[i:i + 7]
            lens = [b - a + 1 for a, b in group]
            gaps = [group[k + 1][0] - group[k][1] - 1 for k in range(6)]
            if max(lens) - min(lens) > 2 or max(gaps) > 2 * s0 + 3:
                continue
            centers = [(group[k][1] + 1 + group[k + 1][0]) / 2 for k in range(6)]
            rows = np.array(SEPARATOR_ROWS) + 0.5
            s, fy = np.polyfit(rows, centers, 1)
            if not 0.6 < s / s0 < 1.6:
                continue
            fx = (xa + xb + 1) / 2 - 4.5 * s
            lx, ly = int(fx + 8.5 * s), int(fy + 5.5 * s)
            if 0 <= lx < img.shape[1] and near(img[ly, lx], LIGHT, 14):
                return fx, fy, s
    return None


def power_level(img, fx, fy, s):
    """Height of the red fill in game px (0..64, the game shows round(64p));
    None when the column is not there any more."""
    xc = int(fx + 4.5 * s)
    y0, y1 = int(fy), int(fy + 64 * s)
    if xc < 0 or y0 < 0 or xc >= img.shape[1] or y1 >= img.shape[0]:
        return None
    col = img[y0:y1, xc]
    red = (col[:, 0] > 150) & (col[:, 1] < 70) & (col[:, 2] < 70)
    brown = near(col, DARK, 14) | (np.abs(col - np.array((34, 23, 13), np.int16)).max(axis=-1) < 40)
    inner = slice(int(2 * s), int(63 * s))     # rows 0 and 64 are border/separator
    if (red | brown)[inner].mean() < 0.8:
        return None
    ys = np.nonzero(red)[0]
    if len(ys) == 0:
        return 0
    return max(0, min(COL_ROWS, round((fy + COL_ROWS * s - y0 - ys[0]) / s)))


class PowerModel:
    """Smooth power while charging.

    The column only shows round(64p), redrawn once per game frame, so a marker
    driven by it moves in steps. The game's p is 1 - |sin(theta)| with theta
    growing by 1 degree per frame from 90, so theta(t) is fitted to the moments
    the shown height changes and the marker uses theta at the current time.
    """

    def __init__(self, rate=60.0):
        self.rate = rate      # degrees per second to assume until the fit has enough points
        self.reset()

    def reset(self):
        self.level = 0
        self.events = []      # (time, theta)
        self.fit = None       # (degrees per second, theta at t0)
        self.t0 = None

    def observe(self, t, level):
        if level == self.level:
            return
        # the shown height switched between the two levels when 64p crossed their midpoint
        a = math.degrees(math.asin(max(0.0, min(1.0, 1 - (self.level + level) / 128))))
        self.level = level
        if self.t0 is None:
            self.t0 = t
        if self.fit:
            guess = self.theta(t)
        elif self.events:
            guess = self.events[-1][1] + self.rate * (t - self.events[-1][0])
        else:
            guess = 90
        n = round(guess / 180)
        theta = min((180 * k + sign * a for k in (n - 1, n, n + 1) for sign in (-1, 1)),
                    key=lambda c: abs(c - guess))
        if not self.events and theta < 90:
            theta = 180 - a
        self.events = self.events[-40:] + [(t, theta)]
        if len(self.events) >= 3 and self.events[-1][0] - self.events[0][0] > 0.05:
            ts = np.array([e[0] for e in self.events]) - self.t0
            th = np.array([e[1] for e in self.events])
            rate, base = np.polyfit(ts, th, 1)
            if 20 < rate < 300:
                self.fit = (rate, base)
                self.rate = rate

    def theta(self, t):
        rate, base = self.fit
        return base + rate * (t - self.t0)

    def power(self, t):
        """Power at time t, or None until enough of the charge has been seen."""
        if not self.fit:
            return None
        return 1 - abs(math.sin(math.radians(self.theta(t))))


class Matcher:
    """Finds creature sprites on the fishing line at a given scale."""

    def __init__(self, s):
        self.s = s
        self.kinds = []
        self.colours = []
        for t in CREATURES:
            rows = SPRITES[t]['rows']
            pal = {k: v for k, v in SPRITES[t]['palette'].items()}
            pts = []
            for y in range(1, len(rows) - 1):
                for x in range(1, len(rows[0]) - 1):
                    ch = rows[y][x]
                    # pixels whose 4 neighbours share their colour: edges get blended
                    # when the game scales sprites
                    if ch != '.' and all(rows[y + dy][x + dx] == ch for dx, dy in ((0, 1), (0, -1), (1, 0), (-1, 0))):
                        pts.append((x, y, pal[ch]))
            step = max(1, len(pts) // 60)
            pts = pts[::step]
            for _, _, c in pts:
                if c not in self.colours:
                    self.colours.append(c)
            samples = [(int((x + 0.5) * s), int((y + 0.5) * s), self.colours.index(c)) for x, y, c in pts]
            self.kinds.append((t, samples))
        self.w = int(38 * s) + 2
        self.h = int(28 * s) + 2

    def find(self, band):
        """band: image whose rows start a bit above the creatures' top. Returns [(type, x)]."""
        H, W = band.shape[:2]
        nx, ny = W - self.w, H - self.h
        if nx <= 0 or ny <= 0:
            return []
        # one comparison per distinct colour, then the sprites just add shifted masks
        masks = [(np.abs(band - np.array(c, np.int16)).max(axis=-1) <= 14).astype(np.uint8)
                 for c in self.colours]
        found = []
        for t, samples in self.kinds:
            score = np.zeros((ny, nx), np.uint8)
            for ox, oy, ci in samples:
                score += masks[ci][oy:oy + ny, ox:ox + nx]
            best = score.max(axis=0) / len(samples)
            r = max(2, round(3 * self.s))
            last = -r - 1
            for x in np.nonzero(best >= 0.55)[0]:
                # local maximum within +-3 game px; equal neighbours keep the first
                if best[x] == best[max(0, x - r):x + r + 1].max() and x - last > r:
                    found.append((t, int(x)))
                    last = x
        return found


# --- windows ------------------------------------------------------------------

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32
WNDENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)


def process_name(pid):
    h = kernel32.OpenProcess(0x1000, False, pid)   # PROCESS_QUERY_LIMITED_INFORMATION
    if not h:
        return ''
    try:
        buf = ctypes.create_unicode_buffer(1024)
        size = wintypes.DWORD(1024)
        if kernel32.QueryFullProcessImageNameW(h, 0, buf, ctypes.byref(size)):
            return buf.value.rsplit('\\', 1)[-1].lower()
        return ''
    finally:
        kernel32.CloseHandle(h)


def window_pid(hwnd):
    pid = wintypes.DWORD()
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    return pid.value


def client_rect(hwnd):
    r = wintypes.RECT()
    user32.GetClientRect(hwnd, ctypes.byref(r))
    pt = wintypes.POINT(0, 0)
    user32.ClientToScreen(hwnd, ctypes.byref(pt))
    return pt.x, pt.y, r.right, r.bottom


def find_game_window(exe, title):
    best = [None, 0]

    def cb(hwnd, _):
        if not user32.IsWindowVisible(hwnd) or user32.IsIconic(hwnd):
            return True
        if title:
            buf = ctypes.create_unicode_buffer(512)
            user32.GetWindowTextW(hwnd, buf, 512)
            if title.lower() not in buf.value.lower():
                return True
        elif process_name(window_pid(hwnd)) != exe:
            return True
        _, _, w, h = client_rect(hwnd)
        if w * h > best[1]:
            best[:] = [hwnd, w * h]
        return True

    user32.EnumWindows(WNDENUMPROC(cb), 0)
    return best[0]


def button_held():
    return bool(user32.GetAsyncKeyState(0x01) & 0x8000 or user32.GetAsyncKeyState(0x20) & 0x8000)


# --- overlay ------------------------------------------------------------------

KEY = '#ff00ff'   # transparent colour of the overlay window


def grabber():
    return mss.MSS() if hasattr(mss, 'MSS') else mss.mss()


def grab(sct, x, y, w, h):
    shot = sct.grab({'left': x, 'top': y, 'width': w, 'height': h})
    return np.frombuffer(shot.raw, np.uint8).reshape(h, w, 4)[:, :, 2::-1].astype(np.int16)


class FishScanner(threading.Thread):
    """Looks for creatures in the background: it is slow next to reading the column."""

    def __init__(self):
        super().__init__(daemon=True)
        self.job = None       # (id, screen region, matcher, region x -> hook x converter)
        self.result = (None, 0.0, [])

    def run(self):
        sct = grabber()
        while True:
            job = self.job
            if job is None:
                time.sleep(0.05)
                continue
            jid, (x, y, w, h), matcher, to_u = job
            try:
                t0 = time.perf_counter()
                found = matcher.find(grab(sct, x, y, w, h))
                self.result = (jid, t0, [(t, to_u(px)) for t, px in found])
            except Exception:   # window moved off screen etc.; the main loop re-locks
                self.result = (jid, time.perf_counter(), [])
            time.sleep(0.02)


class FishTracker:
    """Follows the creatures between scans and predicts where they will be.

    The game sways creature i as A*sin(phase + 120 deg * k_i), where the phase
    grows at SWAY for everyone and is never reset, and k_i comes from the
    creature's slot (SWAY_SLOT). So A and the phase are fitted once over all
    creatures together and carried over to the next cast as a starting point.
    Mines only sway after 17 casts, with slots that can't be told apart: they
    are kept but not used for the fit.
    """

    def __init__(self):
        self.tracks = []          # {'type', 'pts': [(t, x)], 'base', 'seen'}
        self.shared = None        # (A cos phase, A sin phase) from the last fit
        self.sigma = 3.0
        self.last_t = 0.0

    def reset(self):
        self.tracks = []

    def update(self, t, objs):
        if t <= self.last_t:
            return
        self.last_t = t
        free = list(self.tracks)
        for typ, u in objs:
            tr = min((tr for tr in free if tr['type'] == typ), key=lambda tr: abs(self.at(tr, t) - u), default=None)
            if tr is None or abs(self.at(tr, t) - u) > 10:
                tr = {'type': typ, 'pts': [], 'base': u}
                self.tracks.append(tr)
            else:
                free.remove(tr)
            tr['pts'] = [q for q in tr['pts'] if q[0] > t - 4] + [(t, u)]
            tr['seen'] = t
        self.tracks = [tr for tr in self.tracks if tr['seen'] > t - 0.5]
        self.refit()

    def refit(self):
        fish = [tr for tr in self.tracks if tr['type'] != MINE]
        if fish:
            span = max(tr['pts'][-1][0] - tr['pts'][0][0] for tr in fish)
            # a sway fitted to a short stretch is mostly noise: wait for 0.8 s of data
            # unless the last cast's sway is there to start from
            sway = self.shared is not None or span > 0.8
            k = len(fish) + (2 if sway else 0)
            rows, ys = [], []
            for i, tr in enumerate(fish):
                d = math.radians(120 * SWAY_SLOT[tr['type']])
                for t, x in tr['pts']:
                    row = [0.0] * k
                    row[i] = 1.0
                    if sway:
                        row[-2], row[-1] = math.sin(SWAY * t + d), math.cos(SWAY * t + d)
                    rows.append(row)
                    ys.append(x)
            n = len(ys)
            if self.shared is not None:   # last cast's sway, worth a few samples
                for j in (0, 1):
                    row = [0.0] * k
                    row[len(fish) + j] = 2.0
                    rows.append(row)
                    ys.append(2.0 * self.shared[j])
            a, y = np.array(rows), np.array(ys)
            coef, *_ = np.linalg.lstsq(a, y, rcond=None)
            if sway:
                self.shared = (float(coef[-2]), float(coef[-1]))
            for i, tr in enumerate(fish):
                tr['base'] = float(coef[i])
            resid = a[:n] @ coef - y[:n]
            # without a sway fit yet the creatures may still move by up to its amplitude
            self.sigma = float(np.sqrt(np.mean(resid ** 2))) + 0.7
        for tr in self.tracks:
            if tr['type'] == MINE:
                tr['base'] = float(np.mean([q[1] for q in tr['pts']]))

    def at(self, tr, t):
        if tr['type'] == MINE or self.shared is None:
            return tr['base'] + 0 * t
        d = math.radians(120 * SWAY_SLOT[tr['type']])
        return tr['base'] + self.shared[0] * np.sin(SWAY * t + d) + self.shared[1] * np.cos(SWAY * t + d)

    def creatures(self):
        return [tr for tr in self.tracks if tr['type'] != MINE and len(tr['pts']) >= 3]


def plan(now, model, lead, tracker, targets, most=False, avoid=()):
    """Best moment to release, looking up to one full swing of the power ahead.

    targets: {creature type: value}; most: go for the largest total value
    (several creatures can be caught at once), otherwise for anything in targets;
    avoid: types the hook must stay clear of. Returns (release time, value,
    margin in game px); margin < 0 means nothing in the window is likely to work."""
    rate = model.fit[0]
    taus = now + 0.015 + np.arange(0, 360 / rate, 0.002)
    theta = np.radians(model.theta(taus + lead))
    p = 1 - np.abs(np.sin(theta))
    u = np.interp(p, LAND_P, LAND)
    land_t = taus + (np.interp(p, LAND_P, LAND_N) + 1) / rate
    # releasing half a game frame early or late moves the hook by this much
    spread = np.abs(np.gradient(u, taus)) * 0.5 / rate
    pts = np.zeros_like(taus)
    margin = np.full_like(taus, -1e6)     # -1e9 marks moments that hit something to avoid
    sigma = np.sqrt(spread ** 2 + tracker.sigma ** 2)
    for tr in tracker.creatures():
        dist = np.abs(u - tracker.at(tr, land_t))
        if tr['type'] in avoid:
            margin = np.where(dist - catch_radius(tr['type']) < 2 * sigma, -1e9, margin)
        elif tr['type'] in targets:
            m = catch_radius(tr['type']) - dist - 2 * sigma
            if most:
                pts += np.where(m > 0, targets[tr['type']], 0)
            margin = np.where(margin > -1e8, np.maximum(margin, m), margin)
    # the earliest moment that is good enough: chasing the very best would keep
    # putting the release off as the window slides forward and finds better ones
    ok = margin >= min(margin.max() - 2, 5)
    if most:
        ok &= pts == pts.max()
    i = int(np.argmax(ok))
    return taus[i], pts[i], margin[i]


class _KEYBDINPUT(ctypes.Structure):
    _fields_ = [('wVk', wintypes.WORD), ('wScan', wintypes.WORD), ('dwFlags', wintypes.DWORD),
                ('time', wintypes.DWORD), ('dwExtraInfo', ctypes.c_size_t)]


class _INPUT(ctypes.Structure):
    class _U(ctypes.Union):
        _fields_ = [('ki', _KEYBDINPUT), ('pad', ctypes.c_byte * 32)]
    _anonymous_ = ('u',)
    _fields_ = [('type', wintypes.DWORD), ('u', _U)]


def press_space(down):
    inp = _INPUT(type=1)   # INPUT_KEYBOARD
    inp.ki = _KEYBDINPUT(0, 0x39, 0x8 | (0 if down else 0x2), 0, 0)   # scan code, KEYEVENTF_SCANCODE
    user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(inp))


def key_pressed(vk, state={}):
    """True once per press of a virtual key (polled each tick)."""
    down = bool(user32.GetAsyncKeyState(vk) & 0x8000)
    hit = down and not state.get(vk)
    state[vk] = down
    return hit


class AutoPilot:
    """Casts by itself: holds Space, waits for a good moment, lets go."""

    MODES = {'any': 'любая рыба', 'best': 'самая выгодная', 'bobber': 'испытание поплавка'}
    WHALE, MONSTER = 6, 7

    def __init__(self, mode):
        self.mode = mode or 'any'
        self.enabled = False
        self.holding = False
        self.released = False
        self.since = 0.0      # when the line became ready for the next cast
        self.whales = 0       # whales caught this minigame, for the bobber challenge

    def goal(self, tracker):
        """(targets, most, avoid) for the planner."""
        if self.mode == 'best':
            return POINTS, True, ()
        if self.mode == 'any':
            return dict.fromkeys(POINTS, 1), False, ()
        # The Bobber Challenge: a whale shows up after more than 12 catches in a
        # row and resets the streak when caught; after two whales the monster
        # shows up at a streak above 18. So: whales until there are two, then
        # anything but whales, and the monster as soon as it is there.
        seen = {tr['type'] for tr in tracker.creatures()}
        if self.MONSTER in seen:
            return {self.MONSTER: 1}, False, ()
        if self.whales < 2:
            if self.WHALE in seen:
                return {self.WHALE: 1}, False, ()
            return dict.fromkeys(POINTS, 1), False, ()
        return {t: 1 for t in POINTS if t != self.WHALE}, False, (self.WHALE,)

    def caught(self, types):
        """Called after each cast with what the hook landed on."""
        if self.WHALE in types:
            self.whales += 1
        if self.MONSTER in types:
            self.whales = 0
            if self.mode == 'bobber' and self.enabled:
                self.enabled = False
                return 'Чудище поймано, испытание пройдено. Авторежим выключен.'
        return None

    def stop(self):
        if self.holding and not self.released:
            press_space(False)
        self.holding = self.released = False

    def release_at(self, t):
        self.released = True

        def run():
            while True:
                left = t - time.perf_counter()
                if left <= 0:
                    break
                time.sleep(left - 0.002 if left > 0.003 else 0)
            press_space(False)

        threading.Thread(target=run, daemon=True).start()

    def step(self, now, level, model, lead, tracker):
        if not self.enabled:
            self.stop()
            return
        if not self.holding:
            # the next cast's creatures are placed ~0.45 s after the hook comes back
            if level == 0 and now - self.since > 0.9 and tracker.creatures():
                press_space(True)
                self.holding, self.released, self.start = True, False, now
            return
        if self.released:
            if level == 0 and now - self.start > 0.3:   # hook back: next round
                self.holding = self.released = False
                self.since = now
            return
        if now - self.start > 12 or (model.fit is None and now - self.start > 8):
            self.release_at(now)      # cast anyway rather than hold forever
            return
        if model.fit is None:
            return
        when, pts, margin = plan(now, model, lead, tracker, *self.goal(tracker))
        # after 8 s with nothing reachable, take any moment that keeps clear of what to avoid
        if (margin > 0 or (now - self.start > 8 and margin > -1e8)) and when - now < 0.02:
            self.release_at(when)


class Overlay:
    def __init__(self, args):
        self.args = args
        self.root = tk.Tk()
        self.root.overrideredirect(True)
        self.root.attributes('-topmost', True)
        self.root.attributes('-transparentcolor', KEY)
        self.root.geometry('1x1+0+0')
        self.canvas = tk.Canvas(self.root, bg=KEY, highlightthickness=0)
        self.canvas.pack(fill='both', expand=True)
        self.root.update_idletasks()
        hwnd = user32.GetParent(self.root.winfo_id())
        ex = user32.GetWindowLongW(hwnd, -20)
        # layered + click-through + no taskbar button + never takes focus
        user32.SetWindowLongW(hwnd, -20, ex | 0x80000 | 0x20 | 0x80 | 0x8000000)
        if not args.debug:
            # keep our own drawings out of screen captures (Windows 10 2004+)
            user32.SetWindowDisplayAffinity(hwnd, 0x11)
        ctypes.windll.winmm.timeBeginPeriod(1)   # let the update loop run every few ms
        self.sct = grabber()
        self.scanner = FishScanner()
        self.scanner.start()
        saved = load_state()
        self.model = PowerModel(saved.get('rate', 60.0))
        self.tracker = FishTracker()
        self.auto = AutoPilot(args.auto)
        self.prev_level = 0
        self.game = None
        self.game_pid = 0
        self.rect = None
        self.lock = None          # (fx, fy, s) relative to the client area
        self.job_id = 0
        self.next_find = 0
        self.next_scan = 0
        self.status = ''
        self.cast_p = None        # predicted power at the moment the button was released
        self.cast_t = 0.0
        self.cast_theta = None    # model angle behind cast_p, checked against the game once
        self.judged = True        # whether the last cast's catch has been worked out
        self.lead = (args.lead if args.lead is not None else saved.get('lead_ms', 40)) / 1000

    def say(self, text):
        if text != self.status:
            self.status = text
            print(time.strftime('%H:%M:%S'), text, flush=True)

    def set_lock(self, lock):
        self.lock = lock
        self.model.reset()
        self.job_id += 1
        self.scanner.job = None
        if lock is None:
            return
        fx, fy, s = lock
        x, y, w, h = self.rect
        matcher = Matcher(s)
        bx0 = int(fx + s * (HOOK_DX + 14))     # skip the hook resting at x = 0
        by0 = int(fy + (FISH_DY - 4) * s)
        bx1 = min(w, int(fx + s * (HOOK_DX + 345 + 40)))
        by1 = min(h, by0 + matcher.h + int(8 * s))
        if bx1 - bx0 > matcher.w and by1 > by0:
            self.scanner.job = (self.job_id, (x + bx0, y + by0, bx1 - bx0, by1 - by0), matcher,
                                lambda px: (bx0 + px - fx) / s - HOOK_DX)

    def tick(self):
        try:
            self.update()
        except Exception as e:   # keep running through transient capture errors
            self.say(f'Ошибка: {e!r}')
            self.set_lock(None)
        self.root.after(4, self.tick)

    def update(self):
        now = time.perf_counter()
        if self.args.auto and key_pressed(0x77):      # F8
            self.auto.enabled = not self.auto.enabled
            self.say('Авторежим (%s): %s' % (AutoPilot.MODES[self.auto.mode], 'включён' if self.auto.enabled else 'выключен'))
        if self.args.auto and key_pressed(0x79):      # F10: fix the whale count by hand
            self.auto.whales = (self.auto.whales + 1) % 3
            self.say('Испытание поплавка: китов %d из 2' % self.auto.whales)
        if self.args.auto and key_pressed(0x78):      # F9
            modes = list(AutoPilot.MODES)
            self.auto.mode = modes[(modes.index(self.auto.mode) + 1) % len(modes)]
            self.say('Авторежим: цель — %s' % AutoPilot.MODES[self.auto.mode])
        self.auto_ok = False
        self.update_screen(now)
        if not self.auto_ok:
            self.auto.stop()

    def update_screen(self, now):
        if self.game is None or not user32.IsWindow(self.game):
            self.game = None
            self.set_lock(None)
            self.canvas.delete('all')
            if now >= self.next_find:
                self.next_find = now + 1
                self.game = find_game_window(self.args.exe.lower(), self.args.title)
                if self.game:
                    self.game_pid = window_pid(self.game)
                    self.say('Окно игры найдено, жду мини-игру рыбалки')
                else:
                    self.say('Окно игры не найдено')
            return
        rect = client_rect(self.game)
        if rect != self.rect:
            self.rect = rect
            self.set_lock(None)
            x, y, w, h = rect
            self.root.geometry(f'{max(w, 1)}x{max(h, 1)}+{x}+{y}')
        x, y, w, h = rect
        fg = user32.GetForegroundWindow()
        if user32.IsIconic(self.game) or w < 50 or h < 50 or (fg and window_pid(fg) != self.game_pid):
            self.canvas.delete('all')
            return
        if self.lock is None:
            self.canvas.delete('all')
            if now < self.next_scan:
                return
            self.next_scan = now + 0.25
            found = find_column(grab(self.sct, x, y, w, h))
            if not found:
                self.say('Окно игры найдено, жду мини-игру рыбалки')
                return
            self.set_lock(found)
            self.say('Мини-игра найдена: масштаб %.2f, шкала силы в (%d, %d)' % (found[2], found[0], found[1]))
        fx, fy, s = self.lock
        # every tick only the column is captured: a few hundred pixels
        rx0, ry0 = max(0, int(fx - 2 * s)), max(0, int(fy - 2 * s))
        rx1, ry1 = min(w, int(fx + 14 * s)), min(h, int(fy + 67 * s))
        level = power_level(grab(self.sct, x + rx0, y + ry0, rx1 - rx0, ry1 - ry0), fx - rx0, fy - ry0, s)
        if level is None:
            self.set_lock(None)
            self.canvas.delete('all')
            self.auto.whales = 0           # the game starts the count over with the minigame
            self.say('Мини-игра закрыта')
            return
        jid, t_objs, objs = self.scanner.result
        objs = objs if jid == self.job_id else []
        if jid == self.job_id:
            self.tracker.update(t_objs, objs)
        if self.prev_level and not level:      # the hook came back
            self.auto.since = now
            self.reset_tracks_at = now + 0.45
        self.prev_level = level
        if getattr(self, 'reset_tracks_at', None) and now >= self.reset_tracks_at:
            self.tracker.reset()               # the creatures have been placed anew
            self.reset_tracks_at = None
        self.auto_ok = True
        self.auto.step(now, level, self.model, self.lead, self.tracker)
        held = button_held()
        p = None
        if held:
            self.model.observe(now, level)
            p = self.model.power(now + self.lead)
            self.cast_theta = self.model.theta(now + self.lead) if p is not None else None
            if p is None:
                p = level / COL_ROWS
            self.cast_p, self.cast_t = p, now
            self.judged = False
        elif level:
            # released: the game freezes the fill at the power it cast with until the
            # hook lands, so from here on the column itself is the truth (to 1/64)
            p = level / COL_ROWS
            if self.cast_p is not None:
                p = min((level + 0.5) / COL_ROWS, max((level - 0.5) / COL_ROWS, self.cast_p))
                if not self.judged and now - self.cast_t > 0.1:   # screen caught up
                    self.judged = True
                    self.judge(level)
                if self.cast_theta is not None and now - self.cast_t > 0.1:
                    self.learn(level)
        else:
            self.model.reset()
            self.cast_p = None
        self.draw(fx, fy, s, p, objs, level)

    def judge(self, level):
        """Work out what the cast just made will catch, from where the hook lands."""
        p = min((level + 0.5) / COL_ROWS, max((level - 0.5) / COL_ROWS, self.cast_p))
        u, n = flight(p)
        rate = self.model.fit[0] if self.model.fit else self.model.rate
        t_land = self.cast_t + (n + 1) / rate
        hits = [tr['type'] for tr in self.tracker.creatures()
                if abs(u - self.tracker.at(tr, t_land)) < catch_radius(tr['type'])]
        msg = self.auto.caught(hits)
        if self.args.debug or self.auto.mode == 'bobber':
            names = {2: 'рыба', 3: 'жёлтая', 4: 'фиолетовая', 6: 'кит', 7: 'чудище'}
            print('Заброс: %s%s' % (', '.join(names[t] for t in hits) or 'мимо',
                                    ', китов %d из 2' % self.auto.whales if self.auto.mode == 'bobber' else ''),
                  flush=True)
        if msg:
            self.say(msg)

    def learn(self, level):
        """Shift the lead so that the next prediction matches the power this cast really had."""
        theta, self.cast_theta = self.cast_theta, None
        rate = self.model.fit[0]
        a = math.degrees(math.asin(max(0.0, min(1.0, 1 - level / COL_ROWS))))
        n = round(theta / 180)
        true = min((180 * k + sign * a for k in (n - 1, n, n + 1) for sign in (-1, 1)),
                   key=lambda c: abs(c - theta))
        # near p = 0 the fill barely moves, so one level there says little about timing
        if abs(math.cos(math.radians(theta))) > 0.35 and abs(true - theta) < 30:
            target = self.lead + (true - theta) / rate
            self.lead = min(0.25, max(0.0, 0.6 * self.lead + 0.4 * target))
        save_state({'lead_ms': round(self.lead * 1000, 1), 'rate': round(rate, 1)})
        if self.args.debug:
            print('cast: predicted p=%.3f, game p=%d/64=%.3f, %.0f deg/s, lead now %.0f ms'
                  % (self.cast_p, level, level / COL_ROWS, rate, self.lead * 1000), flush=True)

    def draw(self, fx, fy, s, p, objs, level):
        c = self.canvas
        c.delete('all')
        to_x = lambda u: fx + s * (HOOK_DX + u + HOOK_CX)   # hook centre on screen for hook x = u
        y_line = fy + s * (FISH_DY + 30)
        th = max(3, round(1.5 * s))
        zones = []
        for t, u in sorted(objs, key=lambda o: o[0] != MINE):   # mines first, creatures on top
            r = catch_radius(t)
            colour = '#ff3030' if t == MINE else '#30ff60'
            zones.append((t, u - r, u + r))
            c.create_rectangle(to_x(u - r), y_line, to_x(u + r), y_line + th, fill=colour, outline='')
            for edge in (u - r, u + r):
                c.create_line(to_x(edge), y_line - 3 * s, to_x(edge), y_line + th, fill=colour, width=1)
        if p is not None:
            u = land_at(p)
            hit_fish = any(a < u < b for t, a, b in zones if t != MINE)
            hit_mine = any(a < u < b for t, a, b in zones if t == MINE)
            colour = '#30ff60' if hit_fish else '#ff3030' if hit_mine else '#ffe030'
            xm = to_x(u)
            top = fy + s * (FISH_DY - 2)
            c.create_line(xm, top, xm, y_line + th + 2 * s, fill=colour, width=max(2, round(s)))
            a = 4 * s
            c.create_polygon(xm - a, top - a, xm + a, top - a, xm, top, fill=colour, outline='black')
        lines = []
        if self.auto.enabled:
            lines.append('АВТО (F8 стоп, F9 цель): %s%s' % (
                AutoPilot.MODES[self.auto.mode], ', китов %d из 2' % self.auto.whales if self.auto.mode == 'bobber' else ''))
        if self.args.debug:
            c.create_rectangle(fx, fy, fx + 12 * s, fy + 66 * s, outline='#00ffff')
            lines.append('level=%d p=%s s=%.2f objs=%d lead=%.0fms' % (
                level, '-' if p is None else '%.3f' % p, s, len(objs), self.lead * 1000))
        for i, text in enumerate(reversed(lines)):
            label = c.create_text(fx, fy - 12 - 20 * i, anchor='w', fill='black', font=('Consolas', 11, 'bold'), text=text)
            x0, y0, x1, y1 = c.bbox(label)
            c.tag_lower(c.create_rectangle(x0 - 3, y0 - 1, x1 + 3, y1 + 1, fill='white', outline='black'), label)

    def run(self):
        self.say('Оверлей запущен. Закрыть: Ctrl+C в этом окне.')
        if self.args.auto:
            self.say('Авторежим (%s) готов: F8 включает и выключает, F9 меняет цель' % AutoPilot.MODES[self.auto.mode])
        self.root.after(0, self.tick)
        try:
            self.root.mainloop()
        except KeyboardInterrupt:
            pass
        finally:
            self.auto.stop()


def load_state():
    try:
        return json.loads(STATE_FILE.read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return {}


def save_state(state):
    try:
        STATE_FILE.write_text(json.dumps(state), encoding='utf-8')
    except OSError:
        pass


def main():
    ap = argparse.ArgumentParser(description='Оверлей для мини-игры рыбалки в IdleOn')
    ap.add_argument('--exe', default='LegendsOfIdleon.exe', help='имя процесса игры')
    ap.add_argument('--title', help='искать окно по части заголовка вместо процесса (например, для браузерной версии)')
    ap.add_argument('--lead', type=float,
                    help='начальное упреждение в мс (по умолчанию запомненное, иначе 40); дальше подстраивается само')
    ap.add_argument('--auto', choices=list(AutoPilot.MODES),
                    help='авторежим: any — любая рыба, в которую проще попасть; best — самая выгодная; '
                         'bobber — испытание поплавка (два кита, потом чудище). '
                         'Включается и выключается клавишей F8, F9 меняет цель')
    ap.add_argument('--debug', action='store_true',
                    help='рисовать найденную шкалу, печатать прогноз каждого заброса, показывать оверлей на скриншотах')
    args = ap.parse_args()
    try:   # per-monitor DPI aware: window and capture coordinates in physical pixels
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except OSError:
        user32.SetProcessDPIAware()
    Overlay(args).run()


if __name__ == '__main__':
    sys.exit(main())
