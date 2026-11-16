"""The view: where the camera is at a given moment, and how the stage maps onto the frame.

The score lists shots (where the frame is centred, how close, and why). How the camera gets from
one to the next is decided here, by `style: {camera: ...}` in show.yaml:

    drift   it eases from shot to shot, starting a little before the turn it is for (the default)
    cut     it cuts between shots; only a build-up's slow push is a move
    still   it never leaves the wide shot

Things further from the camera move less when it moves (parallax): depth 0 is where the entities
stand, 1 is infinitely far, and below 0 is in front of them.
"""
import math

from ..world import SLOTS
from .motion import glide

MARGIN = 170                                  # pixels from the frame's edge to the first and last slot, in the wide shot


def slot_x(slot, W):
    return MARGIN + slot * (W - 2 * MARGIN) / (SLOTS - 1)


def ground(H):
    return round(H * 0.78)


class View:
    def __init__(self, W, H, cx, zoom):
        self.W, self.H, self.zoom = W, H, zoom
        self.cx = min(max(cx, W / (2 * zoom)), W - W / (2 * zoom))          # the frame never leaves the stage
        self.gy = ground(H)
        self.rise = -H * 0.07 * min(1.0, (zoom - 1) / 0.9)                  # closer in, the ground sits a little higher in the frame

    def at(self, depth=0.0):
        """-> (zoom, centre x, shift y) for a layer at this depth."""
        k = 1 - depth
        return 1 + (self.zoom - 1) * k, self.W / 2 + (self.cx - self.W / 2) * k, self.rise * k

    def x(self, wx, depth=0.0):
        z, cx, _ = self.at(depth)
        return (wx - cx) * z + self.W / 2

    def y(self, wy, depth=0.0):
        z, _, up = self.at(depth)
        return (wy - self.gy) * z + self.gy + up

    def apply(self, c, depth=0.0):
        """Draw what follows in stage coordinates, as seen at this depth."""
        z, cx, up = self.at(depth)
        c.translate(self.W / 2 - cx * z, self.gy + up - self.gy * z)
        c.scale(z, z)


def path(stage):
    """The camera's moves, each with where it starts from: [(begins, lasts, from, to)], with (centre, zoom) pairs."""
    if getattr(stage, "_path", None) is None:
        feel, style = stage.look.feel, stage.look.style.get("camera", "drift")
        shots = stage.score.camera if style != "still" else stage.score.camera[:1]
        move, lead = float(feel.get("camera_move", 1.4)), float(feel.get("camera_lead", 0.3))
        cur, out = (shots[0]["centre"], shots[0]["zoom"]), []
        for s in shots[1:]:
            if s["kind"] == "push":
                begins, lasts = s["t"], max(float(s.get("over") or 0), 1e-3)
            else:
                begins, lasts = (s["t"], 1e-3) if style == "cut" else (s["t"] - lead, max(move, 1e-3))
            if out:
                cur = _between(out[-1], begins)                  # a move that interrupts another starts from wherever that one had got to
            out.append((begins, lasts, cur, (s["centre"], s["zoom"])))
            cur = (s["centre"], s["zoom"])
        stage._path = (cur if not out else out[0][2], out)
    return stage._path


def _between(leg, t):
    begins, lasts, a, b = leg
    k = glide((t - begins) / lasts)
    return a[0] + (b[0] - a[0]) * k, math.exp(math.log(a[1]) + (math.log(b[1]) - math.log(a[1])) * k)


def view(stage, t):
    first, legs = path(stage)
    cur = first
    for leg in legs:
        if leg[0] > t:
            break
        cur = _between(leg, t)
    return View(stage.W, stage.H, slot_x(cur[0], stage.W), cur[1])
