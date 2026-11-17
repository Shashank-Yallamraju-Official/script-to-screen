"""Motion: how a token gets from one snapshot of the score to the next.

The score says what an entity shows and from when. How it eases there (how fast, how far
past the mark) is presentation, set in library/feel.yaml.
"""
import math


def smooth(k):
    k = max(0.0, min(1.0, k))
    return k * k * (3 - 2 * k)


def glide(k):
    """Ease in and out with no sudden start or stop: slower to leave and slower to arrive than `smooth`."""
    k = max(0.0, min(1.0, k))
    return k * k * k * (k * (6 * k - 15) + 10)


def back(k, amount):
    """Ease out that swings past its mark by `amount` and settles."""
    k, c = max(0.0, min(1.0, k)), 1.70158 * amount
    return 1 + (c + 1) * (k - 1) ** 3 + c * (k - 1) ** 2


def pose(stage, e, t):
    """What entity e looks like at time t, easing from its previous snapshot."""
    ks, feel = stage.score.pose[e], stage.look.feel
    idx = max((i for i, (kt, _) in enumerate(ks) if kt <= t + 1e-9), default=None)
    if idx is None:
        return None
    t1, cur = ks[idx]
    prev = ks[idx - 1][1] if idx else dict(cur, alpha=0.0) if t1 > 1e-9 else cur   # already there when a scene opens
    thing = bool(stage.look.cast.get(e, {}).get("body"))             # a thing does not fade in or out: it travels on and off, the way it travels
    off = lambda slot: slot + (-2.6 if slot <= 4 else 2.6)           # just past the nearer edge of the stage
    leaving = thing and idx and cur["alpha"] == 0 and prev["alpha"] > 0
    if thing and not idx and t1 > 1e-9:
        prev = dict(cur, slot=off(cur["slot"]), alpha=1.0)
    if leaving:
        cur = dict(prev, slot=off(prev["slot"]))
    u = max(0.0, min(1.0, (t - t1) / max(float(feel["ease"]), 1e-3)))
    v = max(0.0, min(1.0, (t - t1) / max(float(feel.get("turn", feel["ease"])), 1e-3)))     # turning round has its own, slower clock
    soft, swing, round_ = smooth(u), back(u, float(feel["overshoot"])), glide(v)
    out = dict(cur)
    for n in ("lx", "ly", "alpha"):
        out[n] = prev[n] + (cur[n] - prev[n]) * soft
    out["facing"] = prev["facing"] + (cur["facing"] - prev["facing"]) * round_
    for n in ("slot", "sx", "sy", "lean"):
        out[n] = prev[n] + (cur[n] - prev[n]) * swing
    out["flip"] = math.sin(math.pi * round_) if v < 1 and cur["facing"] != prev["facing"] else 0.0   # mid-turn, thin as paper; it thins and fills gradually
    out["travel"] = math.sin(math.pi * u) if u < 1 and cur["slot"] != prev["slot"] else 0.0            # stretched while moving
    if leaving:
        out["alpha"] = 1.0 if u < 1 else 0.0
    if thing and not idx and t1 > 1e-9 and u < 1:                    # on its way in: how far through its entrance, and where it is headed
        out["arriving"], out["to"] = u, cur["slot"]
    out["going"] = u if u < 1 and cur["slot"] != prev["slot"] else 1.0                            # how far through a move it is (1 = at rest)
    return out
