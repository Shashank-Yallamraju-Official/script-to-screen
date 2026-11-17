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

from . import anthem, master, music
from .bodies import draw_body
from .draw import INK, PAPER, RULE, col, draw_token, fill, font, stroke
from .motion import back, smooth
from .view import MARGIN, ground

GREY = "#8d877c"
WAVES = dict(sine="a sine wave", tri="a triangle wave", square="a square wave")


def _slot(x, W):
    from ..world import SLOTS
    return (x - MARGIN) / ((W - 2 * MARGIN) / (SLOTS - 1))


def _token(c, look, e, x, t0, t, facing=0.0, lx=0.0, size=1.0):
    """One of the cast standing at x, having popped up at t0."""
    k = (t - t0) / 0.45
    if k <= 0:
        return
    grow = back(k, 1.2) if k < 1 else 1.0
    o = dict(slot=_slot(x, look.W), facing=facing, lx=lx, ly=0.0, sx=size, sy=grow * size, lean=0.0, alpha=min(1.0, k * 3), flip=0.0, travel=0.0)
    draw_token(c, look.cast[e], o, look.W, look.H, look.feel)


def _centred(c, text, y, f, paint, W, cx=None):
    c.drawString(text, (cx if cx is not None else W / 2) - f.measureText(text) / 2, y, f, paint)


def _theme(look, kind, seconds, step):
    """The show's theme for a card, mixed and mastered like a scene's music."""
    feel = look.feel
    if look.music.get("theme") == "anthem":                          # a show can ask for the anthem under its title and its credits alike
        return anthem.render(seconds) * min(1.0, float(feel.get("music_volume", 0.6)) * 1.5)
    n = int((seconds + 1.6) * music.RATE)
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


class Land:
    """A title sequence over the show's land (`land.yaml`): the camera travels the map while it draws itself, each house's
    object rises at its place as the music reaches it, and the show's name arrives on the last chord.

    land.yaml says where things are (`places`, `roads`, `wall`), when each rises (`at`, in bars of the anthem), and the
    camera's path (`camera: [[bar, x, y, zoom], ...]`). Nothing is written on the map: the only words are the title.
    """

    def __init__(self, look, show, episode, land, sheets):
        self.look, self.show, self.episode, self.land, self.sheets = look, show, episode, land, sheets
        self.bar = anthem.BAR
        self.seconds = float(land.get("bars", anthem.BARS)) * self.bar

    def sound(self):
        return _theme(self.look, "theme.title", self.seconds, self.bar / 16)

    def _camera(self, t):
        keys = [(float(b) * self.bar, x, y, z) for b, x, y, z in self.land["camera"]]
        for (t0, *a), (t1, *b) in zip(keys, keys[1:]):
            if t <= t1:
                k = max(0.0, (t - t0) / (t1 - t0))
                k = k * k * k * (k * (6 * k - 15) + 10)
                return [p + (q - p) * k for p, q in zip(a, b)]
        return list(keys[-1][1:])

    def draw(self, c, t):
        look, land = self.look, self.land
        W, H = look.W, look.H
        c.clear(col(PAPER))
        cx, cy, zoom = self._camera(t)
        at = {k: p["at"] for k, p in land["places"].items()}
        c.save()
        c.translate(W / 2, H / 2)
        c.scale(zoom, zoom)
        c.translate(-cx, -cy)
        ink, soft = stroke(INK, 5, 150), stroke(RULE, 5)
        for a, b, bar0 in land.get("roads") or []:                    # a road draws itself out from where it starts
            k = smooth((t - float(bar0) * self.bar) / (2 * self.bar))
            if k > 0:
                (x0, y0), (x1, y1) = (at[a] if isinstance(a, str) else a), (at[b] if isinstance(b, str) else b)
                c.drawLine(x0, y0, x0 + (x1 - x0) * k, y0 + (y1 - y0) * k, soft)
        wall = land.get("wall")
        if wall:                                                      # the wall is laid from one end to the other, leaving its gaps
            reach = 40 + 860 * smooth((t - float(wall["from"]) * self.bar) / ((float(wall["to"]) - float(wall["from"])) * self.bar))
            for x0, x1 in wall["spans"]:
                if reach > x0:
                    x1 = min(x1, reach)
                    c.drawRect(skia.Rect.MakeLTRB(x0, wall["y"] - 9, x1, wall["y"] + 9), fill(INK, 215))
                    for x in range(int(x0) + 14, int(x1) - 4, 18):
                        c.drawLine(x, wall["y"] - 9, x, wall["y"] + 9, stroke(PAPER, 1.5, 120))
            for i in range(16):                                       # rubble in the breach
                x, y = wall["breach"][0] + (i * 53) % (wall["breach"][1] - wall["breach"][0]), wall["y"] - 13 + (i * 37) % 26
                if reach > x:
                    c.drawRect(skia.Rect.MakeXYWH(x, y, 6 + i % 3 * 3, 5 + i % 2 * 3), fill(INK, 110))
        for name, p in land["places"].items():                        # each house's object rises where it lives
            k = (t - float(p["at_bar"]) * self.bar) / 0.75
            if k <= 0:
                continue
            x, y = p["at"]
            grow = back(k, 1.3) if k < 1 else 1.0
            c.drawLine(x - 30, y, x + 30, y, ink)
            sheet = dict(self.sheets[p["entity"]])
            sheet["size"] = float(sheet.get("size", 1.0)) * float(p.get("size", 0.42))
            draw_body(c, sheet, dict(slot=x / 100.0, facing=float(p.get("facing", 1)), lx=0.0, ly=0.0, sx=1.0, sy=grow, lean=0.0, alpha=min(1.0, k * 3), going=1.0, travel=0.0, flip=0.0),
                      t, x, y)
            if p.get("crown"):
                top = y - 156 * sheet["size"] - 12
                c.drawPath(skia.Path().moveTo(x - 15, top).lineTo(x - 18, top - 17).lineTo(x - 8, top - 9).lineTo(x, top - 22).lineTo(x + 8, top - 9)
                           .lineTo(x + 18, top - 17).lineTo(x + 15, top).close(), stroke(INK, 3, 255 * min(1.0, k)))
        c.restore()
        lands = float(land.get("title_bar", 18)) * self.bar            # the name arrives on the last chord
        k = smooth((t - lands + 0.5) / 1.0)
        if k > 0:
            c.drawRect(skia.Rect.MakeWH(W, H), fill(PAPER, 205 * k))
            name = str(self.show.get("title") or "Untitled")
            _centred(c, name, H * 0.50, font(104), fill(INK, 255 * smooth((t - lands) / 0.5)), W)
            _centred(c, str(self.episode.get("title") or ""), H * 0.50 + 62, font(30), fill(GREY, 255 * smooth((t - lands - 0.9) / 0.6)), W)


class Caption:
    """A few words on bare paper, in silence: `{card: caption, text: Months later}`. For a jump in time."""

    def __init__(self, look, text, seconds=3.0):
        self.look, self.text, self.seconds = look, str(text or ""), float(seconds or 3.0)

    def sound(self):
        return np.zeros(int(self.seconds * music.RATE))

    def draw(self, c, t):
        c.clear(col(PAPER))
        ink = smooth((t - 0.9) / 0.6) * (1 - smooth((t - (self.seconds - 0.7)) / 0.5))       # the paper is bare for a moment first
        _centred(c, self.text, self.look.H * 0.52, font(40), fill(GREY, 255 * ink), self.look.W)


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
                    self.blocks.append((y, "cast", e, f"{str(sheet.get('kind', 'entity')).split('.')[0]}  ·  voiced by {WAVES.get(sheet.get('timbre', 'sine'), 'a wave')} at {sheet.get('voice', 0)} Hz"))
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
        gap = min(115.0, (W * 0.44 - 90) / max(1, len(self.cast) - 1))      # a large cast stands closer, and smaller, to stay clear of the roll
        for k, e in enumerate(self.cast):
            _token(c, look, e, (130 if gap > 100 else 70) + gap * k, 0.15 * k, t + 1.0, facing=1.0 - turned, lx=1.0 - turned, size=min(1.0, gap / 92))
