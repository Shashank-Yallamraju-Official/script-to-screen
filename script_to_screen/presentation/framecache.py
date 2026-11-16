"""A frame cache keyed by what a frame shows, not by when it happens.

A frame inside a turn depends only on that turn (what everyone shows and when, its bubbles,
who holds the scene), on how each entity stood as the turn began, and on the look. So a
turn has a fingerprint, and a frame is found by (the turn's fingerprint, how far into the
turn it is). Consequences:

  - a turn that merely moved later in time, by a whole number of frames, keeps its frames
  - going back to a value tried before (undo, redo, before against after, a nudge and its
    reverse) costs nothing: those frames are still here
  - a change that touches only sound keeps every frame

The cache holds encoded frames up to a size limit and drops the least recently used.
"""
import hashlib
import json
from collections import OrderedDict

from ..vocabulary import params
from .draw import music_marks
from .render import frame_jpeg

LOOK_SETTINGS = [p.name for p in params.group("feel") if p.rebuild == "look"]     # settings that change the picture
CAST_LOOK = ("color", "kind")


def _digest(v):
    return hashlib.sha1(json.dumps(v, sort_keys=True, default=str, separators=(",", ":")).encode()).hexdigest()


def _r(x):
    return round(x, 6)


def look_print(stage):
    """Everything about the look that a frame depends on."""
    look = stage.look
    return _digest([stage.W, stage.H, stage.fps, {k: look.feel[k] for k in LOOK_SETTINGS}, look.tones, look.emotions, look.style,
                    {e: {k: v for k, v in sheet.items() if k in CAST_LOOK} for e, sheet in look.cast.items()}])


def turn_print(score, i, settled, marks=()):
    """Everything about turn i that its frames depend on, with all times measured from the turn's start.
    `settled` is how many seconds a change takes to finish easing; anything older than that as the turn
    begins has stopped moving, so exactly how much older does not matter."""
    turn = score.turns[i]
    t0, t1 = turn["start"] * score.step, (turn["start"] + turn["length"]) * score.step
    inside = lambda t: t0 - 1e-9 <= t < t1 - 1e-9
    pose = {}
    for e, keys in score.pose.items():
        before = [(t, o) for t, o in keys if t < t0 - 1e-9][-2:]          # how it stood coming in: the last two snapshots
        pose[e] = [[_r(max(t - t0, -settled)), o] for t, o in before] + [[_r(t - t0), o] for t, o in keys if inside(t)]
    music = [[_r(m["t"] - t0), _r(m["lands"] - t0), _r(m["until"] - t0), m["kind"], m["strength"], _r(m["x"])]
             for m in marks if m["until"] > t0 - 0.3 and m["t"] < t1]          # music that is drawn during this turn, and where it is aimed
    speech = []
    for b in score.speech:
        if inside(b["start"]):
            speech.append(dict(who=b["who"], tone=b["tone"], sung=b["sung"], range=b["range"], text=b["text"], start=_r(b["start"] - t0),
                               end=_r(b["end"] - t0), sylls=[dict(s, start=_r(s["start"] - t0)) for s in b["sylls"]]))
    focus = [[_r(a - t0), _r(b - t0), who] for a, b, who in score.focus if b > t0 - 0.2 and a < t1 + 0.2]   # a held reaction fades in and out
    return _digest([turn["id"], _r(t1 - t0), pose, speech, focus, music])


class FrameCache:
    def __init__(self, limit=384 * 1024 * 1024):
        self.limit, self.size, self.frames = limit, 0, OrderedDict()
        self.hits = self.draws = 0
        self._prints = {}                                    # (id of a score, turn) -> fingerprint; scores are never changed once built

    def key(self, stage, F, scale, quality, xray):
        score, t = stage.score, F / stage.fps
        turn = score.turn_at(t)
        settled = round(float(stage.look.feel["ease"]) * 1.1 + 0.05, 3)
        shown = stage.look.style.get("music", "none") != "none"
        mark = (id(score), turn["index"], settled, shown)
        if mark not in self._prints:
            if len(self._prints) > 4000:
                self._prints.clear()
            self._prints[mark] = (score, turn_print(score, turn["index"], settled, music_marks(stage) if shown else ()))   # holding the score keeps its id from being reused
        look = getattr(stage, "_look_print", None) or look_print(stage)
        stage._look_print = look
        into = round((t - turn["start"] * score.step) * stage.fps * 1000)     # thousandths of a frame into the turn
        return (self._prints[mark][1], look, into, scale, quality, bool(xray))

    def get(self, stage, F, scale=0.5, quality=82, xray=False):
        k = self.key(stage, F, scale, quality, xray)
        if k in self.frames:
            self.frames.move_to_end(k)
            self.hits += 1
            return self.frames[k]
        jpeg = frame_jpeg(stage, F, scale, quality, xray)
        self.draws += 1
        self.frames[k] = jpeg
        self.size += len(jpeg)
        while self.size > self.limit and self.frames:
            self.size -= len(self.frames.popitem(last=False)[1])
        return jpeg
