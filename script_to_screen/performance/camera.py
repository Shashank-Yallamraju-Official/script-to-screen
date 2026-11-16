"""Where the camera looks: a derivation step over what the scene already decided.

The world is flat and is always seen from the front, so the camera never turns. What it chooses
is who is in the frame, how close, and where in the frame they sit. Who is on screen decides how
a line lands, so the shot is chosen by whose moment it is:

  1. A turn belongs to the one whose change is the strongest dramatic event in it, else to
     whoever speaks. One owner gets a single; two who change together get a two-shot; three or
     more get the group.
  2. In a single, the subject sits to one side with room in front of them: on the left if they
     face right, on the right if they face left, in the centre if they face us.
  3. A reaction that happens outside the frame gets its own shot, at the moment it happens.
     Until then the line it reacts to is heard from off screen.
  4. It rests when it can: the same people in the same part of the frame is the same shot, and no
     shot is shorter than `min_shot` seconds (the shot before widens to hold the newcomer instead).
  5. A hard bad surprise tips the frame.
  6. A build-up goes to whoever it is about and pushes in until it lands.
  7. A feeling about a thing is framed with the thing: the plate is in the shot when it matters.

A scene opens wide, to show the place. A turn can overrule all of this with `camera:`: `wide`,
`stay`, an entity, a list of entities, or {on, at, zoom, tilt}, where `at` is left | centre | right.

A shot is {t, centre, zoom, on, at, tilt, kind, why}. `centre` is a place on the line of slots;
`zoom` is how many times closer than the wide shot; `on` is who it is a shot of; `at` is where
in the frame they sit; `tilt` is in degrees; `kind` is open | shot | push (a push has `lasts`,
seconds). Whether a change of shot is a cut or a move is presentation's choice.
"""
from ..world import SLOTS

EDGE = 1.45                                  # how far the wide frame reaches past the first and last slot, in slots
FRAME = SLOTS - 1 + 2 * EDGE                 # slots across the frame at zoom 1
OVER = 1.3                                   # how far past the stage's edge a frame may reach, to seat someone at the edge of the stage to one side
DEFAULTS = dict(single=3.0, two=1.9, group=1.45, margin=3.4, inset=1.0, loose=1.5, together=0.6, tilt=4.0, tilt_from=0.55, push=1.25, min_shot=1.8)
SIDES = dict(left=1, centre=0, center=0, right=-1)
SEEN = ("slot", "facing", "lx", "ly", "sx", "sy", "lean", "alpha", "tone")


def _clamp(centre, zoom):
    half = FRAME / zoom / 2
    return min(max(centre, -EDGE - OVER + half), SLOTS - 1 + EDGE + OVER - half) if half * 2 <= FRAME else (SLOTS - 1) / 2


def frame_for(slots, cfg, cap=None):
    """The tightest frame that holds these places with room around them: (centre, zoom)."""
    lo, hi = min(slots), max(slots)
    cap = cap or (cfg["single"] if hi - lo < 0.5 else cfg["two"] if hi - lo <= 2.2 else cfg["group"])
    zoom = max(1.0, min(cap, FRAME / (hi - lo + cfg["margin"])))
    return round(_clamp((lo + hi) / 2, zoom), 3), round(zoom, 3)


def holds(shot, slots, cfg):
    half = FRAME / shot["zoom"] / 2 - cfg["inset"]
    return all(shot["centre"] - half - 1e-6 <= s <= shot["centre"] + half + 1e-6 for s in slots)


def at(pose, t):
    """What every entity on stage shows at time t: {entity: snapshot}."""
    out = {}
    for e, keys in pose.items():
        now = [o for kt, o in keys if kt <= t + 1e-9]
        if now and now[-1]["alpha"]:
            out[e] = now[-1]
    return out


def changes(turn, pose, step, together, things=None):
    """What visibly changes during a turn, in the order it happens: [(t, {entity: [slots]})]. Changes within
    `together` seconds of each other are one moment. The first moment is the turn's opening, and has its speaker in it."""
    t0, t1 = turn["start"] * step, (turn["start"] + turn["length"]) * step
    found = []
    for e, keys in pose.items():
        prev = ([o for t, o in keys if t < t0 - 1e-9] or [None])[-1]
        for t, o in keys:
            if t0 - 1e-9 <= t < t1 - 1e-9:
                if prev is None or any(o.get(k) != prev.get(k) for k in SEEN):
                    about = (o.get("info") or {}).get("at")
                    found.append((t, e, [x["slot"] for x in (prev, o) if x and x["alpha"]] +
                                  ([things[about]] if things and about in things and o["alpha"] else [])))     # where it was, where it gets to, and the thing it is about
                prev = o
    out = [(t0, {})]
    for t, e, slots in sorted(found, key=lambda f: f[0]):
        if not slots:
            continue
        if t - out[-1][0] > together and (len(out) > 1 or t - t0 > together):
            out.append((t, {}))
        out[-1][1].setdefault(e, []).extend(slots)
    stood = at(pose, t1 - 0.01)
    if turn["who"] in stood:
        out[0][1].setdefault(turn["who"], []).append(stood[turn["who"]]["slot"])
    return [(t, who) for t, who in out if who]


def seat(slots, at, cfg, zoom=None):
    """A frame for these places with them seated left, centre or right in it: (centre, zoom).
    Seated left, they are a third of the way in from the left edge, and the room in the frame is to their right."""
    centre, fit = frame_for(slots, cfg)
    zoom = zoom or fit
    return round(_clamp((min(slots) + max(slots)) / 2 + SIDES[at] * FRAME / zoom / 6, zoom), 3), round(zoom, 3)


def inside(shot, slots):
    half = FRAME / shot["zoom"] / 2
    return all(shot["centre"] - half <= s <= shot["centre"] + half for s in slots)


def shots(turns, pose, focus, music, drama, step, written=None, cfg=None, things=None):
    """-> the scene's shots in time order. `written` is {turn index: what the script asked for}."""
    cfg, written = {**DEFAULTS, **(cfg or {})}, written or {}
    names = lambda who: ", ".join(sorted(who)) or "no one"
    wide = dict(centre=round((SLOTS - 1) / 2, 3), zoom=1.0, on=[], at="centre", tilt=0.0)
    out = [dict(wide, t=0.0, kind="open", why="a scene opens wide, to show the place")]
    moments = [(c["t"], 1, c, None) for c in music if c["kind"] == "rise"]
    for turn in turns[1:]:
        for k, (t, who) in enumerate(changes(turn, pose, step, cfg["together"], things)):
            moments.append((t, 0, turn, (k, who)))
    for t, is_rise, x, extra in sorted(moments, key=lambda m: (m[0], m[1])):
        cur = out[-1]
        if is_rise:                                              # rule 6: go to whoever the moment is about, and push in until it lands
            who = x["subject"] if isinstance(x["subject"], str) else x["subject"][0]
            stood = at(pose, t + 0.01)                           # where they stand while it builds
            if who not in stood:
                continue
            on, side = [who], looking(stood[who])
            if cur["kind"] == "shot" and cur["on"] and t - cur["t"] < cfg["min_shot"]:       # too soon to leave whoever we just cut to: push in on both
                on, side = sorted(set(cur["on"]) | {who}), "centre"
            slots = [stood[e]["slot"] for e in on if e in stood]
            centre, zoom = seat(slots, side, cfg)
            wider = round(max(1.0, zoom / cfg["push"]), 3)
            first = dict(centre=seat(slots, side, cfg, wider)[0], zoom=wider, on=on, at=side, tilt=0.0, kind="shot", why=f"the music is building toward {who}")
            if len(on) > 1:
                cur.update(first)                                # the shot we are in becomes the start of the push
            else:
                out.append(dict(first, t=t))
            out.append(dict(t=t + 1e-3, centre=centre, zoom=zoom, on=on, at=side, tilt=0.0, kind="push", lasts=x.get("length", 0),
                            why=f"the frame creeps in on {names(on)} until the moment lands"))
            continue
        turn, (k, who) = x, extra
        t1 = (turn["start"] + turn["length"]) * step
        stood = at(pose, t1 - 0.01)
        ask = written.get(turn["index"]) if k == 0 else None
        if ask == "stay" or (k and written.get(turn["index"])):  # a written shot holds for its whole turn
            continue
        if ask == "wide":
            shot, why = dict(wide), "the script asks for the wide shot"
        elif ask:
            spec = ask if isinstance(ask, dict) else dict(on=ask)
            on = [e for e in ([spec["on"]] if isinstance(spec.get("on"), str) else spec.get("on") or []) if e in stood]
            if not on:
                continue
            side = str(spec.get("at") or (looking(stood[on[0]]) if len(on) == 1 else "centre"))
            if side not in SIDES:
                raise ValueError(f"turn {turn['id']}: `camera: at` is left, centre or right, not '{side}'")
            centre, zoom = seat([stood[e]["slot"] for e in on], side, cfg, float(spec["zoom"]) if spec.get("zoom") else None)
            shot = dict(centre=centre, zoom=zoom, on=sorted(on), at=side, tilt=float(spec.get("tilt", 0.0)))
            why = f"the script asks for {names(on)}, {side} of frame"
        else:
            slots = [s for v in who.values() for s in v]
            events = [d for d in drama if d["subject"] in who and turn["start"] * step - 1e-9 <= d["t"] < t1 and d.get("shown")]
            top = max(events, key=lambda d: d["surprise"] * d["weight"], default=None)
            if len(who) >= 2:                                    # rule 1: two change together, or the group
                centre, zoom = frame_for(slots, cfg)
                shot = dict(centre=centre, zoom=zoom, on=sorted(who), at="centre")
                why = f"{names(who)} " + ("all change at once" if len(who) > 2 else "change together")
            else:
                owner = next(iter(who))
                side = looking(stood[owner]) if owner in stood and max(slots) - min(slots) < 0.5 else "centre"       # rule 2
                centre, zoom = seat(slots, side, cfg)
                shot = dict(centre=centre, zoom=zoom, on=[owner], at=side)
                why = (f"it is {owner}'s moment" if top or owner != turn["who"] else f"{owner} is speaking") + \
                      (f"; {side} of frame, with room on the side they face" if side != "centre" else "")
            tilt = 0.0
            if top and top["valence"] < 0 and top["surprise"] * top["weight"] >= cfg["tilt_from"]:           # rule 5
                tilt = cfg["tilt"] * (1 if shot["centre"] < (SLOTS - 1) / 2 else -1)
                why += "; a hard bad surprise tips the frame"
            shot["tilt"] = tilt
            same = cur["on"] == shot["on"] and cur["at"] == shot["at"]
            held = holds(cur, slots, cfg)
            if k and inside(cur, slots) and (cur["zoom"] < cfg["two"] + 1e-6 or held):
                continue                                         # rule 3: a reaction already in frame needs no shot of its own
            if same and inside(cur, slots) and not tilt and not cur["tilt"]:
                continue                                         # rule 4
            if not cur["on"] and held and shot["zoom"] / cur["zoom"] <= cfg["loose"]:
                continue
            if k:
                why = "a reaction outside the frame: " + why
            if cur["kind"] == "shot" and cur["on"] and t - cur["t"] < cfg["min_shot"]:       # rule 4: no shot shorter than this
                on = sorted(set(cur["on"]) | set(shot["on"]))
                both = [stood[e]["slot"] for e in on if e in stood] + slots + cur.get("_held", [])     # and everywhere the shot already had to reach
                centre, zoom = frame_for(both, cfg)
                cur.update(centre=centre, zoom=zoom, on=on, at="centre", tilt=cur["tilt"] or shot["tilt"], _held=both,
                           why=cur["why"] + f"; widened to hold {names(shot['on'])} too, rather than cut again so soon")
                continue
        out.append(dict(shot, t=t, kind="shot", why=why, _held=[] if ask else list(slots)))
    return [{k: v for k, v in shot.items() if k != "_held"} for shot in out]


def looking(o):
    """Where someone sits in a single: opposite the way they face, so the room in the frame is in front of them."""
    return "left" if o["facing"] > 0 else "right" if o["facing"] < 0 else "centre"
