"""Cards: the parts of an episode that are not scenes. A title card and the credits.

A card is made from show.yaml (the show's `title`, its `credits`) and from the episode it is
in (its title, its cast), so it has no file of its own. Both are drawn in the show's own
vocabulary: the entities stand on the ground line, and a title takes ink the way a spoken
line does.

    credits:                                  # in show.yaml, top to bottom
      - {role: Created by, name: Someone}
      - cast                                  # everyone in the episode, worked out from its scenes
      - {name: A line with no role above it}
"""
import math

import numpy as np
import skia

from . import master, music
from .draw import INK, PAPER, RULE, col, draw_token, fill, font, stroke
from .motion import back, smooth
from .view import MARGIN, ground

GREY = "#8d877c"
WAVES = dict(sine="a sine wave", tri="a triangle wave", square="a square wave")


def _slot(x, W):
    from ..world import SLOTS
    return (x - MARGIN) / ((W - 2 * MARGIN) / (SLOTS - 1))


def _token(c, look, e, x, t0, t, facing=0.0, lx=0.0):
    """One of the cast standing at x, having popped up at t0."""
    k = (t - t0) / 0.45
    if k <= 0:
        return
    grow = back(k, 1.2) if k < 1 else 1.0
    o = dict(slot=_slot(x, look.W), facing=facing, lx=lx, ly=0.0, sx=1.0, sy=grow, lean=0.0, alpha=min(1.0, k * 3), flip=0.0, travel=0.0)
    draw_token(c, look.cast[e], o, look.W, look.H, look.feel)


def _centred(c, text, y, f, paint, W, cx=None):
    c.drawString(text, (cx if cx is not None else W / 2) - f.measureText(text) / 2, y, f, paint)


def _theme(look, kind, seconds, step):
    """The show's theme for a card, mixed and mastered like a scene's music."""
    n = int((seconds + 1.6) * music.RATE)
    feel = look.feel
    tune = music.render([dict(kind=kind, t=0.0, strength=1.0)], step, n, look.music) * float(feel.get("music_volume", 0.6)) * 0.9
    room = dict(look.music.get("mix") or {}, **{k: float(feel.get(k, master.DEFAULTS[k])) for k in ("reverb", "warmth")}, duck=0.0)
    return master.master(np.zeros(n), np.zeros(n), tune, room)


class Title:
    """The show's name takes ink while the theme plays; the cast pop up under it; the episode's title follows."""

    def __init__(self, look, show, episode, cast, step, seconds=5.0):
        self.look, self.show, self.episode, self.cast, self.step, self.seconds = look, show, episode, cast, step, float(seconds)

    def sound(self):
        return _theme(self.look, "theme.title", self.seconds, self.step)

    def draw(self, c, t):
        look = self.look
        W, H, gy, step = look.W, look.H, ground(look.H), self.step
        c.clear(col(PAPER))
        lands = 12 * step                                            # the theme's last note: everything arrives on it
        reach = W / 2 * smooth(t / 0.6)                              # the ground line draws out from the middle
        path = skia.Path()
        for i in range(int(W / 2 - reach), int(W / 2 + reach) + 4, 4):
            age = t - lands
            y = -30 * math.exp(-age / 0.5) * math.exp(-((abs(i - W / 2) - 900 * age) / 80) ** 2) if age > 0 else 0.0   # one ripple, as in a scene
            (path.moveTo if path.isEmpty() else path.lineTo)(i, gy + y)
        c.drawPath(path, stroke(RULE, 2))
        gap = 118
        for k, e in enumerate(self.cast):                            # one of the cast on each of the first notes
            x = W / 2 + (k - (len(self.cast) - 1) / 2) * gap
            side = 0.0 if t > lands else (1.0 if x < W / 2 - 1 else -1.0 if x > W / 2 + 1 else 0.0)      # they look at each other, then at us
            _token(c, look, e, x, 2 * step * k, t, facing=side, lx=side)
        f, name = font(92), str(self.show.get("title") or "Untitled")
        x0, y0 = W / 2 - f.measureText(name) / 2, H * 0.34
        c.drawString(name, x0, y0, f, fill(INK, 70 * smooth(t / 0.4)))
        k = smooth((t - 4 * step) / (lands - 4 * step))              # the name takes ink across the melody, like a line being said
        if k > 0:
            edge, soft = x0 + (f.measureText(name) + 40) * k, 40.0
            box = skia.Rect.MakeLTRB(0, y0 - 110, W, y0 + 40)
            c.saveLayer(box, None)
            c.drawString(name, x0, y0, f, fill(INK))
            c.drawRect(box, skia.Paint(BlendMode=skia.BlendMode.kDstIn, Shader=skia.GradientShader.MakeLinear(
                [skia.Point(edge - soft, 0), skia.Point(edge, 0)], [skia.ColorBLACK, skia.ColorTRANSPARENT])))
            c.restore()
        sub = str(self.episode.get("title") or "")
        _centred(c, sub, y0 + 62, font(30), fill(GREY, 255 * smooth((t - lands - 0.15) / 0.5)), W)


class Credits:
    """The credits roll past the cast, who watch them go by and then look at us."""

    def __init__(self, look, show, episode, cast, sheets, step, seconds=17.0):
        self.look, self.show, self.episode, self.cast, self.sheets, self.step, self.seconds = look, show, episode, cast, sheets, step, float(seconds)
        self.blocks, y = [], 0.0
        for entry in show.get("credits") or [dict(role="Made with", name="script-to-screen")]:
            if entry == "cast":
                self.blocks.append((y, "role", "Cast", None))
                y += 44
                for e in cast:
                    sheet = sheets[e]
                    self.blocks.append((y, "cast", e, f"{sheet.get('kind', 'entity')}  ·  voiced by {WAVES.get(sheet.get('timbre', 'sine'), 'a wave')} at {sheet.get('voice', 0)} Hz"))
                    y += 74
                y += 36
                continue
            if entry.get("role"):
                self.blocks.append((y, "role", str(entry["role"]), None))
                y += 44
            for line in str(entry.get("name", "")).split("\n"):
                self.blocks.append((y, "name", line, None))
                y += 44
            y += 46
        self.last = y + 40                                           # where the closing title sits
        self.height = self.last + 120

    def sound(self):
        return _theme(self.look, "theme.credits", self.seconds, self.step)

    def draw(self, c, t):
        look = self.look
        W, H, gy = look.W, look.H, ground(look.H)
        c.clear(col(PAPER))
        cx = W * 0.64
        roll = self.seconds - 3.2                                    # the roll ends early, and the closing title holds
        top = H + 30 - (H + 30 + self.last - H * 0.44) * min(1.0, t / roll)
        for y, kind, text, more in self.blocks:
            at = top + y
            if at < -80 or at > H + 60:
                continue
            if kind == "role":
                _centred(c, text.upper(), at, font(17), fill(GREY), W, cx)
            elif kind == "name":
                _centred(c, text, at, font(30), fill(INK), W, cx)
            else:
                f, name = font(30), text.capitalize()
                w = f.measureText(name)
                c.drawRoundRect(skia.Rect.MakeXYWH(cx - w / 2 - 34, at - 30, 18, 38), 9, 9, fill(look.cast[text]["color"]))
                c.drawString(name, cx - w / 2, at, f, fill(INK))
                _centred(c, more, at + 26, font(15), fill(GREY), W, cx)
        at = top + self.last
        _centred(c, str(self.show.get("title") or ""), at, font(54), fill(INK), W, cx)
        _centred(c, str(self.episode.get("title") or ""), at + 44, font(24), fill(GREY), W, cx)
        fade = skia.Paint(Shader=skia.GradientShader.MakeLinear([skia.Point(0, 0), skia.Point(0, 90)], [col(PAPER), col(PAPER, 0)]))
        c.drawRect(skia.Rect.MakeWH(W, 90), fade)                    # lines leave softly at the top
        bar = (t / self.step) % 16                                   # the ground hums on each bar of the theme
        path = skia.Path()
        for i in range(0, int(W * 0.40), 4):
            y = 5 * math.exp(-bar / 4) * math.sin(i / 11 - t * 20) * math.exp(-((i - 250) / 220) ** 2)
            (path.moveTo if i == 0 else path.lineTo)(i, gy + y)
        c.drawPath(path, stroke(RULE, 2, 255))
        c.drawRect(skia.Rect.MakeXYWH(W * 0.30, gy - 8, W * 0.10 + 4, 16), skia.Paint(Shader=skia.GradientShader.MakeLinear(
            [skia.Point(W * 0.30, 0), skia.Point(W * 0.40, 0)], [col(PAPER, 0), col(PAPER)])))
        turned = smooth((t - roll) / 0.5)                            # when the roll stops they turn to us
        for k, e in enumerate(self.cast):
            _token(c, look, e, 130 + 115 * k, 0.15 * k, t + 1.0, facing=1.0 - turned, lx=1.0 - turned)
