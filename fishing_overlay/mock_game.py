"""Stand-in for the IdleOn fishing minigame, for trying the overlay without the game.

Same sprites, geometry and physics as the game. The window can be resized and
moved freely; A/D move the minigame inside it. Hold the left button or Space to
charge, release to cast. Run the overlay with:  python overlay.py --title "fishing mock"

--auto casts by itself (random hold times) and prints where each cast landed.
"""
import argparse
import math
import random
import tkinter as tk

from overlay import CATCH_TOL, FISH_DY, HOOK_DX, MINE, SWAY_SLOT
from sprites import SPRITES

W, H = 960, 540


def scaled_image(key, s):
    sp = SPRITES[key]
    rows, pal = sp['rows'], sp['palette']
    w, h = max(1, round(len(rows[0]) * s)), max(1, round(len(rows) * s))
    img = tk.PhotoImage(width=w, height=h)
    for y in range(h):
        src = rows[min(len(rows) - 1, int(y / s))]
        line = []
        for x in range(w):
            ch = src[min(len(src) - 1, int(x / s))]
            line.append('#%02x%02x%02x' % pal[ch] if ch != '.' else '#4a90c8')
        img.put('{' + ' '.join(line) + '}', to=(0, y))
        for x in range(w):
            if src[min(len(src) - 1, int(x / s))] == '.':
                img.transparency_set(x, y, True)
    return img


class Mock:
    def __init__(self, auto):
        self.auto = auto
        self.root = tk.Tk()
        self.root.title('IdleOn fishing mock')
        self.root.geometry('1100x620')
        self.canvas = tk.Canvas(self.root, bg='#20304a', highlightthickness=0)
        self.canvas.pack(fill='both', expand=True)
        self.bx, self.by = 300, 360
        self.held = False
        self.t = 90
        self.p = 0.0
        self.state = 0            # 0 aim, 1 flying, 2 landed
        self.hook = [0.0, 5.0]
        self.vel = [0.0, 0.0]
        self.wait = 0
        self.casts = self.streak = self.score = self.whales = 0
        self.phase = [0.0, 120.0, 240.0]   # sway phase per sprite slot mod 3, like the game
        self.objs = []            # [x, type]
        self.auto_hold = 0
        self.scale = None
        self.imgs = {}
        self.respawn()
        c = self.canvas
        c.bind('<ButtonPress-1>', lambda e: self.press())
        c.bind('<ButtonRelease-1>', lambda e: self.release())
        self.root.bind('<KeyPress-space>', lambda e: self.press())
        self.root.bind('<KeyRelease-space>', lambda e: self.release())
        self.root.bind('<KeyPress-a>', lambda e: self.move(-10))
        self.root.bind('<KeyPress-d>', lambda e: self.move(10))

    def move(self, dx):
        self.bx = min(W - 300, max(125, self.bx + dx))

    def respawn(self):
        """Creature layout for the next cast, after the game's rules."""
        self.objs = [[random.randint(45, 205), 2, SWAY_SLOT[2]]]
        if self.streak > 2:
            self.objs.append([random.randint(130, 262), 3, SWAY_SLOT[3]])
        if self.streak > 5:
            self.objs.append([random.randint(200, 290), 4, SWAY_SLOT[4]])
        if self.streak > 12:
            self.objs.append([random.randint(240, 295), 6, SWAY_SLOT[6]])
        if self.streak > 18 and self.whales >= 2:
            self.objs.append([random.randint(200, 295), 7, SWAY_SLOT[7]])
        for k in range(6):
            if self.casts > 5 * k + (2 + (k // 2) ** 2):
                x = random.randint(40, 295)
                for _ in range(8):
                    if abs(x - self.objs[0][0]) >= 20:
                        break
                    x = random.randint(40, 295)
                self.objs.append([x, MINE, (4 + k) % 3])

    def wobble(self, i):
        _, t, slot = self.objs[i]
        if self.casts < 6 or (t == MINE and self.casts < 17):
            return 0.0
        amp = 13 if self.casts < 17 else 13 + (self.casts - 17) / self.casts * 23
        return amp * math.sin(math.radians(self.phase[slot]))

    def press(self):
        if self.state == 0:
            self.held = True

    def release(self):
        if self.state == 0 and self.held:
            self.held = False
            self.state = 1
            self.hook = [0.0, 0.0]
            self.vel = [0.4 + 2.06 * self.p, -1.4 - 1.45 * self.p]

    def step(self):
        for i in range(3):
            self.phase[i] += 1.3 * 16 / 20
        if self.auto and self.state == 0:
            if not self.held and self.wait <= 0:
                self.held, self.auto_hold = True, random.randint(5, 175)
            elif self.held:
                self.auto_hold -= 1
                if self.auto_hold <= 0:
                    self.release()
        if self.state == 0 and self.held:
            self.t += 1
            self.p = 1 - abs(math.sin(math.radians(self.t)))
        elif self.state == 1:
            ny = self.hook[1] + self.vel[1]
            if ny < 5 or self.hook[0] < 5:
                self.hook[0] += self.vel[0]
                self.hook[1] = ny
                self.vel[1] += 0.05
            else:
                self.land()
        elif self.state == 2:
            self.wait -= 1
            if self.wait <= 0:
                self.state, self.t, self.p, self.hook = 0, 90, 0.0, [0.0, 5.0]
                self.casts += 1
                self.respawn()
                self.wait = 20
        elif self.wait > 0:
            self.wait -= 1

    def land(self):
        hx = self.hook[0]
        caught = []
        over = False
        order = sorted(range(len(self.objs)), key=lambda i: self.objs[i][1] == MINE)
        for i in order:
            x, t, _ = self.objs[i]
            if abs(hx - (x + self.wobble(i))) < 6 + CATCH_TOL[t]:
                if t != MINE:
                    caught.append(t)
                elif not caught:
                    over = True
                    break
        # like the game: +1 streak per creature; a whale resets the streak and counts
        # towards the monster, the monster resets both
        for t in sorted(caught):
            self.streak += 1
            self.score += t - 1 + 14 * (t // 7)
            if t == 6:
                self.streak = 0
                self.whales += 1
            elif t == 7:
                self.streak = self.whales = 0
                print('MONSTER caught', flush=True)
        if not caught:
            self.streak = 0
        if over:
            self.streak = self.whales = 0
            self.casts = 0
        print('landed x=%.1f p=%.3f caught=%s%s' % (hx, self.p, caught, ' MINE' if over else ''), flush=True)
        self.state, self.wait = 2, 40

    def draw(self):
        c = self.canvas
        cw, ch = c.winfo_width(), c.winfo_height()
        s = min(cw / W, ch / H)
        if s != self.scale:
            self.scale = s
            self.imgs = {k: scaled_image(k, s) for k in SPRITES}
        ox, oy = (cw - W * s) / 2, (ch - H * s) / 2
        fx, fy = ox + (self.bx - 104) * s, oy + (self.by - 87) * s
        c.delete('all')
        c.create_rectangle(ox, oy, ox + W * s, oy + H * s, fill='#4a90c8', outline='')
        c.create_rectangle(fx + 18 * s, fy + 58 * s, fx + (HOOK_DX + 350) * s, fy + 66 * s, fill='#1f5fa0', outline='')
        c.create_image(round(fx), round(fy), image=self.imgs['pow'], anchor='nw')
        if self.p > 0 and self.state == 0:
            c.create_rectangle(round(fx + s), round(fy + (64 - 64 * self.p) * s), round(fx + 11 * s), round(fy + 64 * s),
                               fill='#e90000', outline='')
        for i, (x, t, _) in enumerate(self.objs):
            y = FISH_DY + 2 * math.sin(math.radians(self.phase[0] / 1.4))
            c.create_image(round(fx + (HOOK_DX + x + self.wobble(i)) * s), round(fy + y * s), image=self.imgs[t], anchor='nw')
        c.create_image(round(fx + (HOOK_DX + self.hook[0]) * s), round(fy + (25 + self.hook[1]) * s), image=self.imgs[1], anchor='nw')
        c.create_text(ox + 10, oy + 10, anchor='nw', fill='white',
                      text=f'очки {self.score}   серия {self.streak}   китов {self.whales}   забросов {self.casts}   (A/D двигают полоску)')

    def tick(self):
        self.step()
        self.draw()
        self.root.after(16, self.tick)

    def run(self):
        self.root.after(100, self.tick)
        self.root.after(300, self.root.focus_force)
        self.root.mainloop()


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--auto', action='store_true', help='забрасывать самому и печатать, куда упал крючок')
    Mock(ap.parse_args().auto).run()
