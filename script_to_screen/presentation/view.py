"""The view: where the camera is at a given moment, and how the stage maps onto the frame.

The score lists shots (who each is of, where the frame is centred, how close, from what height,
and why). How the camera gets from one to the next is decided here, by `style: {camera: ...}`:

    film    a new subject is a cut; the same subject, reframed, is an eased move (the default)
    drift   it eases from every shot to the next, starting a little before
    cut     every change of shot is a cut; only a build-up's slow push is a move
    still   it never leaves the wide shot

Things further from the camera move less when it moves (parallax): depth 0 is where the entities
stand, 1 is infinitely far, and below 0 is in front of them. The camera never turns: the world is
flat and always seen from the front. A tipped frame is a turn of the whole picture.
"""
import math

import skia

from ..world import SLOTS
from .motion import glide

MARGIN = 170                                  # pixels from the frame's edge to the first and last slot, in the wide shot
NUMBERS = ("centre", "tilt")
OVER = 1.3                                    # slots past the stage's edge a frame may reach (see performance/camera.py)


def slot_x(slot, W):
    return MARGIN + slot * (W - 2 * MARGIN) / (SLOTS - 1)


def ground(H):
    return round(H * 0.78)


class View:
    def __init__(self, W, H, cx, zoom, tilt=0.0, on=()):
        self.W, self.H, self.zoom, self.tilt = W, H, zoom, tilt
        self.on = tuple(on)                                                 # who the shot is of
        over = OVER * (W - 2 * MARGIN) / (SLOTS - 1)
        self.cx = min(max(cx, W / (2 * zoom) - over), W - W / (2 * zoom) + over) if zoom > 1 + 1e-9 or abs(cx - W / 2) > 1 else W / 2
        self.gy = ground(H)
        # where the ground sits in the frame: a little higher as the camera closes in, then lower again once a figure fills it
        k = min(1.0, (zoom - 1) / 0.9)
        self.floor = H * (0.78 - 0.07 * k) + (H * 0.19 * min(1.0, (zoom - 1.9) / 1.1) if zoom > 1.9 else 0.0)
        self._m = {}

    def matrix(self, depth=0.0):
        """Stage coordinates -> frame coordinates, for a layer at this depth."""
        if depth not in self._m:
            k = 1 - depth
            z, cx = 1 + (self.zoom - 1) * k, self.W / 2 + (self.cx - self.W / 2) * k
            m = skia.Matrix()
            m.setTranslate(-cx, -self.gy)
            m.postScale(z, z)
            if abs(self.tilt) > 1e-4:
                m.postRotate(self.tilt)
            m.postTranslate(self.W / 2, self.gy + (self.floor - self.gy) * k)
            self._m[depth] = m
        return self._m[depth]

    def point(self, wx, wy, depth=0.0):
        p = self.matrix(depth).mapXY(wx, wy)
        return p.x(), p.y()

    def x(self, wx, depth=0.0):
        return self.point(wx, self.gy, depth)[0]

    def apply(self, c, depth=0.0):
        """Draw what follows in stage coordinates, as seen at this depth."""
        c.concat(skia.M44(self.matrix(depth)))


def _state(shot):
    return dict(centre=shot["centre"], zoom=shot["zoom"], tilt=shot.get("tilt", 0.0), on=tuple(shot.get("on") or ()))


def path(stage):
    """The camera's moves, each with where it starts from: (first state, [(begins, lasts, from, to)])."""
    if getattr(stage, "_path", None) is None:
        feel, style = stage.look.feel, stage.look.style.get("camera", "film")
        shots = stage.score.camera if style != "still" else stage.score.camera[:1]
        move, lead = float(feel.get("camera_move", 1.4)), float(feel.get("camera_lead", 0.3))
        first = cur = _state(shots[0])
        out = []
        for s in shots[1:]:
            to = _state(s)
            if s["kind"] == "push":
                begins, lasts = s["t"], max(float(s.get("lasts") or 0), 1e-3)
            elif style == "cut" or (style == "film" and to["on"] != cur["on"]):
                begins, lasts = s["t"], 1e-3
            elif style == "film":
                begins, lasts = s["t"], max(move, 1e-3)
            else:
                begins, lasts = s["t"] - lead, max(move, 1e-3)
            if out:
                cur = _between(out[-1], begins)                  # a move that interrupts another starts from wherever that one had got to
            out.append((begins, lasts, cur, to))
            cur = to
        stage._path = (first, out)
    return stage._path


def _between(leg, t):
    begins, lasts, a, b = leg
    if t >= begins + lasts:
        return dict(b)                                           # the move is over: the camera is where it was going
    k = glide((t - begins) / lasts)
    out = {n: a[n] + (b[n] - a[n]) * k for n in NUMBERS}
    out["zoom"] = math.exp(math.log(a["zoom"]) + (math.log(b["zoom"]) - math.log(a["zoom"])) * k)
    out["on"] = b["on"] if k >= 0.5 else a["on"]
    return out


def view(stage, t):
    first, legs = path(stage)
    cur = first
    for leg in legs:
        if leg[0] > t:
            break
        cur = _between(leg, t)
    return View(stage.W, stage.H, slot_x(cur["centre"], stage.W), cur["zoom"], cur["tilt"], cur["on"])
