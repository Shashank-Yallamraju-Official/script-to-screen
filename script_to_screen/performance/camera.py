"""Where the camera looks: a derivation step over what the scene already decided.

The camera follows three rules, in this order:

  1. It never hides a change. Whoever speaks, moves, or shows something new during a turn is in frame,
     and a speaker is framed with whoever the line is said to (the nearest one they face).
  2. It moves only when it has to. If everyone who matters is already comfortably in frame, and the
     frame is not much looser than they need, it stays where it is.
  3. A build-up pushes in. While the music rises into the scene's strongest moment, the frame
     creeps toward whoever that moment is about.

A scene opens wide, to show the place. A turn can overrule all of this with `camera:` (`wide`,
`stay`, an entity, or a list of entities).

A shot is {t, centre, zoom, kind, on, why}: `centre` is a place on the line of slots, `zoom` is how
many times closer than the wide shot, `kind` is open | move | push (a push also has `over`, seconds).
How a move is eased, or whether it is a cut, is presentation's choice.
"""
from ..world import SLOTS

EDGE = 1.45                                  # how far the wide frame reaches past the first and last slot, in slots
FRAME = SLOTS - 1 + 2 * EDGE                 # slots across the frame at zoom 1
DEFAULTS = dict(close=1.9, two=1.7, group=1.45, margin=3.4, inset=1.0, loose=1.5, push=1.2, toward=0.4)
SEEN = ("slot", "facing", "lx", "ly", "sx", "sy", "lean", "alpha", "tone")


def _clamp(centre, zoom):
    half = FRAME / zoom / 2
    return min(max(centre, -EDGE + half), SLOTS - 1 + EDGE - half)


def frame_for(slots, cfg):
    """The tightest frame that holds these places with room around them: (centre, zoom)."""
    lo, hi = min(slots), max(slots)
    cap = cfg["close"] if hi - lo < 0.5 else cfg["two"] if hi - lo <= 2.2 else cfg["group"]
    zoom = max(1.0, min(cap, FRAME / (hi - lo + cfg["margin"])))
    return round(_clamp((lo + hi) / 2, zoom), 3), round(zoom, 3)


def holds(shot, slots, cfg):
    half = FRAME / shot["zoom"] / 2 - cfg["inset"]
    return all(shot["centre"] - half - 1e-6 <= s <= shot["centre"] + half + 1e-6 for s in slots)


def subjects(turn, pose, focus, step):
    """Who must be seen during this turn, and every place they stand in it: {entity: [slots]}."""
    t0, t1 = turn["start"] * step, (turn["start"] + turn["length"]) * step
    out = {}
    for e, keys in pose.items():
        before = [o for t, o in keys if t < t0 - 1e-9]
        during = [o for t, o in keys if t0 - 1e-9 <= t < t1 - 1e-9]
        prev, changed, here = (before[-1] if before else None), False, []
        for o in during:
            if prev is None or any(o.get(k) != prev.get(k) for k in SEEN):
                changed = True
                here += [x["slot"] for x in (prev, o) if x and x["alpha"]]     # where it was and where it gets to
            prev = o
        featured = any(who == e and a < t1 and b > t0 for a, b, who in focus)
        if (e == turn["who"] or featured) and prev is not None and prev["alpha"]:
            changed = True
            here.append(prev["slot"])
        if changed and here:
            out[e] = here
    speaker = turn["who"]
    if speaker in out:                                           # a line is framed with whoever it is said to: the nearest one the speaker faces
        now = [o for t, o in pose[speaker] if t < t1 - 1e-9][-1]
        stood = present(pose, t1 - 0.01)
        ahead = [(abs(s - now["slot"]), e) for e, s in stood.items() if e != speaker and (s - now["slot"]) * now["facing"] > 0]
        if ahead:
            e = min(ahead)[1]
            out.setdefault(e, []).append(stood[e])
    return out


def present(pose, t):
    out = {}
    for e, keys in pose.items():
        now = [o for kt, o in keys if kt <= t + 1e-9]
        if now and now[-1]["alpha"]:
            out[e] = now[-1]["slot"]
    return out


def shots(turns, pose, focus, music, step, written=None, cfg=None):
    """-> the scene's shots in time order. `written` is {turn index: what the script asked for}."""
    cfg, written = {**DEFAULTS, **(cfg or {})}, written or {}
    names = lambda who: ", ".join(sorted(who)) or "no one"
    out = [dict(t=0.0, centre=round((SLOTS - 1) / 2, 3), zoom=1.0, kind="open", on=[], why="a scene opens wide, to show the place")]
    rises = sorted((c for c in music if c["kind"] == "rise"), key=lambda c: c["t"])
    moments = [(turn["start"] * step, 0, turn) for turn in turns[1:]] + [(c["t"], 1, c) for c in rises]
    for t, is_rise, x in sorted(moments, key=lambda m: (m[0], m[1])):
        cur = out[-1]
        if is_rise:                                              # rule 3: creep toward whoever the moment is about
            who = x["subject"] if isinstance(x["subject"], str) else x["subject"][0]
            at = present(pose, x["t"] + x.get("length", 0) + 0.01).get(who)
            zoom = round(min(cur["zoom"] * cfg["push"], cfg["close"]), 3)
            if at is None or zoom <= cur["zoom"] + 1e-6:
                continue
            centre = round(_clamp(cur["centre"] + cfg["toward"] * (at - cur["centre"]), zoom), 3)
            out.append(dict(t=t, centre=centre, zoom=zoom, kind="push", over=x.get("length", 0), on=[who],
                            why=f"the music is building toward {who}, so the frame creeps in"))
            continue
        ask = written.get(x["index"])
        if ask == "stay":
            continue
        if ask == "wide":
            who, slots, forced = present(pose, t + x["length"] * step - 0.01), [-EDGE + FRAME / 2], "the script asks for the wide shot"
            centre, zoom = round((SLOTS - 1) / 2, 3), 1.0
        else:
            stood = present(pose, t + x["length"] * step - 0.01)
            if ask:
                who = {e: [stood[e]] for e in ([ask] if isinstance(ask, str) else ask) if e in stood}
                forced = "the script asks for " + names(who)
            else:
                who, forced = subjects(x, pose, focus, step), None
            if not who:
                continue                                         # nothing new to see: the frame rests
            slots = [s for v in who.values() for s in v]
            centre, zoom = frame_for(slots, cfg)
        if forced:
            why = forced
        elif not holds(cur, slots, cfg):                         # rule 1
            why = f"not everyone who matters would be in frame ({names(who)})"
        elif zoom / cur["zoom"] > cfg["loose"]:                  # rule 2: only tighten when the frame is much looser than needed
            why = f"the frame is much wider than needed for {names(who)}"
        else:
            continue
        if abs(centre - cur["centre"]) < 1e-6 and abs(zoom - cur["zoom"]) < 1e-6:
            continue
        out.append(dict(t=t, centre=centre, zoom=zoom, kind="move", on=sorted(who), why=why))
    return out
