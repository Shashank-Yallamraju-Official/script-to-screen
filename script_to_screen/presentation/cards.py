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
from .place import mix as place_mix, rgb as place_rgb
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
    """A title sequence over the show's land (`land.yaml`), as a model on a table seen from above and to one side.

    The land is a sheet lying flat. The camera swoops from one place to the next. As it reaches a place, a cog under
    it turns, a platform lifts out of the sheet, and that house's object rises on it. The wall
    is laid, standing up from the sheet, as the camera follows it. Where something has burned, it smokes. The show's
    name arrives on the last chord of the anthem.

    land.yaml says where things are (`places`, `roads`, `wall`), which places this sequence visits and when
    (`at_bar`, in bars of the anthem; a place without one stays dark), what is burning (`smoke`), and the camera's
    path (`camera: [[bar, x, y, zoom], ...]`). Nothing is written on the map but the credit and the title.
    """
    TABLE, SHEET, DARK, IRON, BRASS, INKED, PALE = "#1f181b", "#c9b58f", "#8f7d62", "#4a525e", "#9a7b3f", "#5b4636", "#efe3c8"

    def __init__(self, look, show, episode, land, sheets):
        self.look, self.show, self.episode, self.land, self.sheets = look, show, episode, land, sheets
        self.bar = anthem.BAR
        self.seconds = float(land.get("bars", anthem.BARS)) * self.bar
        for name, colour in (land.get("palette") or {}).items():      # a show's own colours: table, sheet, dark, iron, brass, inked, pale
            setattr(self, name.upper(), colour)

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

    def places(self, day=None):
        """The places as they stand on `day`: land.yaml's `history` ([{day, <place>: {smoke, flags}}]) laid over them, in order."""
        out = {k: dict(p) for k, p in self.land["places"].items()}
        if day is None:
            return out
        for p in out.values():
            p.pop("smoke", None)
        for entry in sorted(self.land.get("history") or [], key=lambda e: e["day"]):
            if entry["day"] <= day:
                for k, change in entry.items():
                    if k != "day":
                        out[k].update(change)
                        out[k]["_since"] = {**out[k].get("_since", {}), **{n: entry["day"] for n in change}}
        return out

    def draw(self, c, t, cam=None, view=1.0, day=None, words=True):
        """`cam` (x, y, zoom) and `view` (1 = the model seen from one side, 0 = from straight above) are for a card that flies
        the camera itself; `day` shows the land as it stands on that day."""
        look, land = self.look, dict(self.land, places=self.places(day))
        W, H = look.W, look.H
        F, K, TILT, H0 = 760.0, 0.85 * view, 1.0 - 0.4 * view, H * (0.5 + 0.1 * view)
        stand = min(1.0, 0.06 + view)                                # how much of a thing's height shows: from straight above, almost none
        cx, cy, zoom = cam or self._camera(t)
        ahead = cam or self._camera(t + 0.25)
        roll = max(-3.5, min(3.5, (ahead[0] - cx) * 0.03))           # it banks into a turn

        def proj(x, y, z=0.0):
            den = max(140.0, F - K * (y - cy))
            sc = F / den * zoom
            return W / 2 + (x - cx) * sc, H0 + (y - cy) * TILT * sc - z * sc * stand, sc

        at = {k: p["at"] for k, p in land["places"].items()}
        when = lambda p: float(p["at_bar"]) * self.bar if "at_bar" in p else None
        c.clear(col(self.TABLE))
        c.save()
        c.rotate(roll, W / 2, H / 2)
        # --- the sheet, lying flat: everything here is drawn in map units and laid back by the matrix ---
        m = skia.Matrix()
        m.setAll(zoom * F, -(W / 2) * K, (W / 2) * F, 0, zoom * TILT * F - H0 * K, H0 * F, 0, -K, F)
        m.preTranslate(-cx, -cy)
        c.save()
        c.concat(m)
        c.drawRect(skia.Rect.MakeLTRB(-26, -26, 946, 866), fill(self.DARK))
        c.drawRect(skia.Rect.MakeLTRB(0, 0, 920, 840), fill(self.SHEET))
        wall = land.get("wall") or {}
        if wall:
            c.drawRect(skia.Rect.MakeLTRB(0, wall["y"], 920, 840), fill("#3b3026", 92))           # behind the wall the sheet is in shadow
        for a, b, bar0 in land.get("roads") or []:                    # a road inks itself out from where it starts
            k = smooth((t - float(bar0) * self.bar) / (2 * self.bar))
            if k > 0:
                (x0, y0), (x1, y1) = (at[a] if isinstance(a, str) else a), (at[b] if isinstance(b, str) else b)
                c.drawLine(x0, y0, x0 + (x1 - x0) * k, y0 + (y1 - y0) * k, stroke(self.INKED, 9, 210))
                c.drawLine(x0, y0, x0 + (x1 - x0) * k, y0 + (y1 - y0) * k, stroke(self.SHEET, 2.5, 150))
        reach = -1.0
        if wall:
            reach = 920 * smooth((t - float(wall["from"]) * self.bar) / ((float(wall["to"]) - float(wall["from"])) * self.bar))
            for i in range(22):                                       # rubble in the breach
                x, y = wall["breach"][0] + (i * 53) % (wall["breach"][1] - wall["breach"][0]), wall["y"] - 22 + (i * 37) % 44
                if reach > x:
                    c.drawRect(skia.Rect.MakeXYWH(x, y, 7 + i % 3 * 4, 6 + i % 2 * 4), fill(self.IRON, 200))
        for name, p in land["places"].items():                        # the cog under each place it visits
            t0 = when(p)
            if t0 is None or t < t0 - 0.6:
                continue
            x, y = p["at"]
            spin = 260 * (1 - smooth((t - t0 + 0.6) / 2.2)) + 14 * (t - t0) * (1 if hash(name) % 2 else -1)
            gear = skia.Path()
            for i in range(24):
                r = 58 if i % 2 else 48
                a0, a1 = math.radians(spin + i * 15), math.radians(spin + (i + 1) * 15)
                (gear.moveTo if i == 0 else gear.lineTo)(x + r * math.cos(a0), y + r * math.sin(a0))
                gear.lineTo(x + r * math.cos(a1), y + r * math.sin(a1))
            gear.close()
            alpha = 255 * smooth((t - t0 + 0.6) / 0.5)
            c.drawPath(gear, fill(self.BRASS, alpha))
            c.drawCircle(x, y, 36, fill(self.INKED, alpha))
            for i in range(4):
                a0 = math.radians(spin + i * 90)
                c.drawLine(x, y, x + 36 * math.cos(a0), y + 36 * math.sin(a0), stroke(self.BRASS, 5, alpha))
        c.restore()
        # --- what stands up from the sheet, farthest first ---
        standing = []
        if wall:
            for x0, x1 in wall["spans"]:
                if reach > x0:
                    standing.append((wall["y"], "wall", (x0, min(x1, reach))))
        for name, p in land["places"].items():
            if when(p) is not None and t > when(p):
                standing.append((p["at"][1], "place", (name, p)))
        for y, kind, what in sorted(standing, key=lambda s: s[0]):
            if kind == "wall":
                x0, x1 = what
                tall = 40 * smooth((reach - x0) / 60)
                quad = lambda pts, paint: c.drawPath(skia.Path().addPoly([skia.Point(*proj(*q)[:2]) for q in pts], True), paint)
                quad([(x0, y, 0), (x1, y, 0), (x1, y, tall), (x0, y, tall)], fill(self.IRON))
                quad([(x0, y - 14, tall), (x1, y - 14, tall), (x1, y, tall), (x0, y, tall)], fill(place_mix(self.IRON, "#ffffff", 0.22)))
                for x in range(int(x0) + 18, int(x1) - 4, 22):
                    (ax, ay, _), (bx, by, _) = proj(x, y, 0), proj(x, y, tall)
                    c.drawLine(ax, ay, bx, by, stroke("#2c323b", 1.5, 170))
                continue
            name, p = what
            x, y = p["at"]
            k = (t - when(p)) / 1.3
            lift = 18 * smooth(k / 0.45)                              # the platform lifts out of the sheet
            (bx, by, sc), (tx, ty, _) = proj(x, y, 0), proj(x, y, lift)
            rx, ry = 40 * sc, 40 * sc * TILT
            c.drawRect(skia.Rect.MakeLTRB(tx - rx, ty, tx + rx, by), fill("#4d3f31"))
            c.drawOval(skia.Rect.MakeXYWH(bx - rx, by - ry, 2 * rx, 2 * ry), fill("#4d3f31"))
            c.drawOval(skia.Rect.MakeXYWH(tx - rx, ty - ry, 2 * rx, 2 * ry), fill("#7a6650"))
            rise = (k - 0.3) / 0.7
            if rise > 0:                                              # and the house's object rises on it
                grow = back(rise, 1.3) if rise < 1 else 1.0
                sheet = dict(self.sheets[p["entity"]])
                sheet["size"] = float(sheet.get("size", 1.0)) * float(p.get("size", 0.42))
                c.save()
                c.translate(tx, ty)
                c.scale(sc, sc * stand)
                draw_body(c, sheet, dict(slot=x / 100.0, facing=float(p.get("facing", 1)), lx=0.0, ly=0.0, sx=1.0, sy=grow, lean=0.0, alpha=min(1.0, rise * 3), going=1.0,
                                         travel=0.0, flip=0.0, lit=(-1, 0.7, "#f6c26b")), t, 0, 0, min(5.0, abs(y - cy) / 110))
                c.restore()
                if p.get("crown"):
                    top = ty - (156 * sheet["size"] * sc + 10 * sc) * stand
                    c.drawPath(skia.Path().moveTo(tx - 15 * sc, top).lineTo(tx - 18 * sc, top - 17 * sc).lineTo(tx - 8 * sc, top - 9 * sc).lineTo(tx, top - 22 * sc)
                               .lineTo(tx + 8 * sc, top - 9 * sc).lineTo(tx + 18 * sc, top - 17 * sc).lineTo(tx + 15 * sc, top).close(), stroke(self.PALE, 3 * sc, 255 * min(1.0, rise)))
            flags = p.get("flags")
            if flags:                                                 # whose it is now: a pennant for each
                up = 1.0 if day is None else smooth((day - p["_since"]["flags"]) / 6.0)
                for i, who in enumerate(flags):
                    fx = x + (i - (len(flags) - 1) / 2) * 30
                    (ax, ay, s2), (qx, qy, _) = proj(fx, y + 34, lift), proj(fx, y + 34, lift + 58 * up)
                    c.drawLine(ax, ay, qx, qy, stroke(self.PALE, 2.5 * s2))
                    c.drawPath(skia.Path().addPoly([skia.Point(qx, qy), skia.Point(qx + 20 * s2, qy + 7 * s2), skia.Point(qx, qy + 15 * s2)], True),
                               fill(land["places"][who].get("color") or self.sheets[land["places"][who]["entity"]]["color"], 255 * up))
            if p.get("smoke") or p.get("_since", {}).get("smoke") is not None:      # it burned; once it is out, the smoke thins and goes
                k = k if p.get("smoke") else 1 - smooth((day - p["_since"]["smoke"]) / 12.0)
                for i in range(7):
                    age = (t * 0.32 + i / 7) % 1.0
                    sx, sy, s2 = proj(x - 20 + 16 * math.sin(i * 2.1 + t * 0.7) + 26 * age, y, 60 + 230 * age)
                    c.drawCircle(sx, sy, (12 + 34 * age) * s2, skia.Paint(AntiAlias=True, Color=col("#2b2528", 120 * (1 - age) * min(1.0, k)),
                                                                        MaskFilter=skia.MaskFilter.MakeBlur(skia.kNormal_BlurStyle, 7)))
        c.restore()
        # --- the air between us and it: distance fades, the corners fall away ---
        r, g, b = place_rgb(self.TABLE)
        c.drawRect(skia.Rect.MakeWH(W, H * 0.42), skia.Paint(Shader=skia.GradientShader.MakeLinear(
            [skia.Point(0, 0), skia.Point(0, H * 0.42)], [skia.Color(r, g, b, int(235 * view)), skia.Color(r, g, b, 0)])))
        c.drawRect(skia.Rect.MakeWH(W, H), skia.Paint(Shader=skia.GradientShader.MakeRadial(
            skia.Point(W / 2, H * 0.55), W * 0.75, [skia.Color(8, 5, 8, 0), skia.Color(8, 5, 8, 0), skia.Color(8, 5, 8, 190)], [0.0, 0.55, 1.0])))
        if not words:
            return
        by = self.land.get("credit")
        if by:                                                        # one credit, beside the land, before the name
            a = smooth((t - float(by["from"]) * self.bar) / 0.6) * (1 - smooth((t - float(by["to"]) * self.bar) / 0.6))
            c.drawString(str(by["role"]).upper(), 70, H - 96, font(15), fill(self.PALE, 190 * a))
            c.drawString(str(by["name"]), 70, H - 62, font(28), fill(self.PALE, 255 * a))
        lands = float(land.get("title_bar", 18)) * self.bar            # the name arrives on the last chord
        k = smooth((t - lands + 0.5) / 1.0)
        if k > 0:
            c.drawRect(skia.Rect.MakeWH(W, H), fill(self.TABLE, 170 * k))
            name = str(self.show.get("title") or "Untitled").upper()
            _centred(c, name, H * 0.50, font(104), fill(self.PALE, 255 * smooth((t - lands) / 0.5)), W)
            _centred(c, str(self.episode.get("title") or ""), H * 0.50 + 62, font(30), fill(self.BRASS, 255 * smooth((t - lands - 0.9) / 0.6)), W)


class Travel:
    """From one scene to the next, by way of the land (`{card: travel}` between two scenes in series.yaml).

    The scene we are leaving tips over until we are looking straight down on it, and we rise until the whole land is in view. The
    days between the two scenes go by, counted, and the land changes as they do (land.yaml `history`). Then the camera finds where
    the next scene is, goes there, comes down, and the scene stands up in front of us.

    Everything is worked out from the scenes either side: their `day:` in series.yaml, and their place's `land:` (which place on the
    land it is). After a card instead of a scene (the title sequence, say) there is nothing to leave: it begins with the whole land.
    """
    WHOLE = (460.0, 500.0, 0.88)
    TIP, RISE = 1.6, 2.6

    def __init__(self, land, before, after, last, first):
        self.land, self.look = land, land.look
        self.a, self.b = before, after                               # {day, at: the place on the land} for the scene before and the scene after
        self.last, self.first = last, first                           # their last and first frames, as images (last is None after a card)
        self.days = max(0, int(after["day"]) - int(before["day"]))
        self.lapse = 0.0 if not self.days else min(10.0, 4.0 + 2.4 * math.log10(self.days + 1))
        self.lead = (self.TIP + self.RISE) if last is not None else 0.8
        self.seconds = self.lead + self.lapse + self.RISE + self.TIP

    def sound(self):                                                 # the anthem's low figure keeps going under it, and rings on into the next scene
        return anthem.bed(self.seconds) * min(1.0, float(self.look.feel.get("music_volume", 0.6)) * 1.5)

    def _clock(self, t):
        """The time at `t`, in days (1.5 = noon on day 1). It leaves at dusk and arrives in the morning, slow at both ends and fast
        between, so the first and last days can be watched and the ones between go by in a blur."""
        d0, d1 = self.a["day"] + 0.72, self.b["day"] + 0.3
        k = min(1.0, max(0.0, (t - self.lead) / self.lapse)) if self.lapse else 1.0
        e = 0.5 * (2 * k) ** 3 if k < 0.5 else 1 - 0.5 * (2 - 2 * k) ** 3
        return d0 + (d1 - d0) * e

    def _sky(self, c, t, strength):
        """The sun and the moon over the land, and its light on it. The sun rises in the east (the right) at a quarter of the way
        through a day and sets in the west; the moon has the other half. When days go by faster than a frame can show, both smear
        into arcs and the light evens out, as in any time-lapse."""
        W, H = self.look.W, self.look.H
        now, was = self._clock(t), self._clock(t - 1 / self.look.fps)
        span = now - was
        span += (1 - span) * min(1.0, max(0.0, (span - 0.03) / 0.12)) if span < 1 else 0.0      # once days go by several a second, show the whole day at once: no flicker
        span = min(span, 1.0)
        n = 1 if span < 0.004 else 40
        horizon, light, lean, bodies = H * 0.35, 0.0, 0.0, []
        for i in range(n):
            f = (now - span + span * (i + 1) / n) % 1.0
            up = math.sin(2 * math.pi * (f - 0.25))                  # the sun's height: above the horizon from 0.25 to 0.75
            for body, h, ph in (("sun", up, (f - 0.25) % 1.0 * 2), ("moon", -up, (f - 0.75) % 1.0 * 2)):
                if h <= -0.12:
                    continue
                bodies.append((body, W * (0.86 - 0.72 * ph), horizon + 26 - h * H * 0.27, 255 * strength / n ** 0.6))
            day = smooth((up + 0.12) / 0.4)
            light += (0.34 + 0.66 * day) / n                           # full by day; a third of it by moonlight
            lean += (0.86 - 0.72 * ((f - 0.25) % 1.0 * 2 if up > 0 else (f - 0.75) % 1.0 * 2) - 0.5) / n      # which side the light is on
        dim = (1 - light) * strength
        if dim > 0.004:                                               # the land under it: darker and bluer by night, and darkest on the side away from the light
            near, far = place_mix("#ffffff", "#3346c8", dim * 0.8), place_mix("#ffffff", "#3346c8", min(1.0, dim * 1.15))
            a, b = (near, far) if lean < 0 else (far, near)
            c.drawRect(skia.Rect.MakeWH(W, H), skia.Paint(BlendMode=skia.BlendMode.kMultiply, Shader=skia.GradientShader.MakeLinear(
                [skia.Point(0, 0), skia.Point(W, 0)], [col(a), col(b)])))
        dusk = 0.0 if n > 1 else max(0.0, 1 - abs(math.sin(2 * math.pi * (now % 1.0 - 0.25))) / 0.35)
        if dusk * strength > 0.004:                                   # and gold when the sun is on the horizon
            c.drawRect(skia.Rect.MakeWH(W, H), skia.Paint(BlendMode=skia.BlendMode.kMultiply, Color=col(place_mix("#ffffff", "#f2b25a", 0.45 * dusk * strength))))
        c.save()
        c.clipRect(skia.Rect.MakeWH(W, horizon))                      # they come up from behind the far edge of the land
        for body, x, y, a in bodies:
            if body == "sun":
                c.drawCircle(x, y, 30, fill("#ffe9a0", a * 0.35))
                c.drawCircle(x, y, 20, fill("#fff6d0", a))
            else:
                c.drawCircle(x, y, 17, fill("#dfe6ff", a))
        c.restore()

    def _tipped(self, c, image, k):
        """A scene's frame, `k` of the way over from standing in front of us (0) to lying under us (1)."""
        W, H = self.look.W, self.look.H
        k = smooth(k)
        floor, squash, wide, shrink = H * 0.72, 1 - 0.86 * k, 1 + 0.2 * k, 1 - 0.55 * k
        m = skia.Matrix()
        m.setPolyToPoly([skia.Point(0, 0), skia.Point(W, 0), skia.Point(W, H), skia.Point(0, H)],
                        [skia.Point(W / 2 - W / 2 * wide * shrink, floor - floor * squash * shrink), skia.Point(W / 2 + W / 2 * wide * shrink, floor - floor * squash * shrink),
                         skia.Point(W / 2 + W / 2 * shrink, floor + (H - floor) * squash * shrink), skia.Point(W / 2 - W / 2 * shrink, floor + (H - floor) * squash * shrink)])
        c.save()
        c.concat(m)
        c.drawImage(image, 0, 0, skia.SamplingOptions(skia.FilterMode.kLinear), skia.Paint(Alphaf=1 - smooth((k - 0.45) / 0.5)))
        c.restore()

    def draw(self, c, t):
        (ax, ay), (bx, by), whole, close = self.a["at"], self.b["at"], self.WHOLE, 3.6
        mix = lambda p, q, k: tuple(u + (v - u) * smooth(k) for u, v in zip(p, q))
        t1 = self.lead                                                # the days start to pass
        t2 = t1 + self.lapse                                          # the camera sets off for the next place
        t3 = t2 + self.RISE                                           # it is over the place: the scene stands up
        day = self._clock(t)
        if t < t1 and self.last is not None:
            k = (t - self.TIP * 0.5) / (self.RISE + self.TIP * 0.5)
            self.land.draw(c, 500 + t, mix((ax, ay, close), whole, k), smooth(k), day, False)
            self._sky(c, t, smooth(k) ** 2)
            if t < self.TIP:
                self._tipped(c, self.last, t / self.TIP)
        elif t < t2:
            self.land.draw(c, 500 + t, whole, 1.0, day, False)
            self._sky(c, t, 1.0)
        else:
            k = (t - t2) / (self.RISE + self.TIP * 0.5)
            self.land.draw(c, 500 + t, mix(whole, (bx, by, close), k), 1 - smooth(k), day, False)
            self._sky(c, t, (1 - smooth(k)) ** 2)
            if t > t3:
                self._tipped(c, self.first, 1 - (t - t3) / self.TIP)
        if self.days:                                                 # the count of days, while they pass
            a = smooth((t - t1 + 0.6) / 0.5) * (1 - smooth((t - t2 - 0.9) / 0.6))
            c.drawString(f"Day {int(day)}", 70, self.look.H - 62, font(28), fill(self.land.PALE, 255 * a))


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
