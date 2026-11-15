"""Motion: how a token gets from one snapshot of the score to the next.

The score says what an entity shows and from when. How it eases there (how fast, how far
past the mark) is presentation, set in library/feel.yaml.
"""
import math


def smooth(k):
    k = max(0.0, min(1.0, k))
    return k * k * (3 - 2 * k)


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
    u = max(0.0, min(1.0, (t - t1) / max(float(feel["ease"]), 1e-3)))
    soft, swing = smooth(u), back(u, float(feel["overshoot"]))
    out = dict(cur)
    for n in ("facing", "lx", "ly", "alpha"):
        out[n] = prev[n] + (cur[n] - prev[n]) * soft
    for n in ("slot", "sx", "sy", "lean"):
        out[n] = prev[n] + (cur[n] - prev[n]) * swing
    pulse = math.sin(math.pi * u) if u < 1 else 0.0
    out["flip"] = pulse if cur["facing"] != prev["facing"] else 0.0       # mid-turn, thin as paper
    out["travel"] = pulse if cur["slot"] != prev["slot"] else 0.0         # stretched while moving
    return out
