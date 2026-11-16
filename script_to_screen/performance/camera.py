"""Where the camera looks, and from where: a derivation step over what the scene already decided.

Who is on screen decides how a line lands, so the camera is chosen by whose moment it is:

  1. It shows whoever the moment happens to. A turn belongs to the one whose change is the
     strongest dramatic event in it, else to whoever speaks. One owner gets a single; two who
     change together get a two-shot; three or more get the group.
  2. A single is taken over the shoulder of the other party: the listener's, if the owner is
     speaking; the speaker's, if the line is landing on the owner. That shoulder is whose side
     of the exchange we are on. The other party's line then arrives from off screen.
  3. A reaction that happens outside the frame gets its own shot, at the moment it happens.
  4. It rests when it can: the same people from the same side is the same shot.
  5. Height is standing: we look up at someone who outranks the room and down at someone the
     room outranks. A hard bad surprise tips the frame.
  6. A build-up goes to whoever it is about and pushes in until it lands.

A scene opens wide, to show the place. A turn can overrule all of this with `camera:`: `wide`,
`stay`, an entity, a list of entities, or {on, over, angle, tilt, zoom}.

A shot is {t, centre, zoom, on, over, angle, tilt, kind, why}. `centre` is a place on the line of
slots; `zoom` is how many times closer than the wide shot; `on` is who it is a shot of; `over` is
whose shoulder it is taken across; `angle` runs from -1 (low, looking up) to 1 (high, looking
down); `tilt` is in degrees; `kind` is open | shot | push (a push has `lasts`, seconds). Whether a
change of shot is a cut or a move is presentation's choice.
"""
from ..world import SLOTS

EDGE = 1.45                                  # how far the wide frame reaches past the first and last slot, in slots
FRAME = SLOTS - 1 + 2 * EDGE                 # slots across the frame at zoom 1
DEFAULTS = dict(single=3.0, two=1.9, group=1.45, margin=3.4, inset=1.0, loose=1.5, lean=0.5, together=0.6, tilt=4.0, tilt_from=0.55, push=1.25)
SEEN = ("slot", "facing", "lx", "ly", "sx", "sy", "lean", "alpha", "tone")


def _clamp(centre, zoom):
    half = FRAME / zoom / 2
    return min(max(centre, -EDGE + half), SLOTS - 1 + EDGE - half)


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


def changes(turn, pose, step, together):
    """What visibly changes during a turn, in the order it happens: [(t, {entity: [slots]})]. Changes within
    `together` seconds of each other are one moment. The first moment is the turn's opening, and has its speaker in it."""
    t0, t1 = turn["start"] * step, (turn["start"] + turn["length"]) * step
    found = []
    for e, keys in pose.items():
        prev = ([o for t, o in keys if t < t0 - 1e-9] or [None])[-1]
        for t, o in keys:
            if t0 - 1e-9 <= t < t1 - 1e-9:
                if prev is None or any(o.get(k) != prev.get(k) for k in SEEN):
                    found.append((t, e, [x["slot"] for x in (prev, o) if x and x["alpha"]]))     # where it was and where it gets to
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


def faced(e, stood):
    """Whoever e is speaking to: the nearest one in the direction e faces."""
    me = stood[e]
    ahead = [(abs(o["slot"] - me["slot"]), x) for x, o in stood.items() if x != e and (o["slot"] - me["slot"]) * me["facing"] > 0]
    return min(ahead)[1] if ahead else None


def height(on, stood):
    """Standing, as an angle: below 0 looks up at someone who outranks the rest of the room, above 0 looks down."""
    rest = [o["info"]["status"] for e, o in stood.items() if e not in on]
    mine = [stood[e]["info"]["status"] for e in on if e in stood]
    if not rest or not mine:
        return 0.0
    s, r = sum(mine) / len(mine), sum(rest) / len(rest)
    return round(max(-1.0, min(1.0, (0.5 - s / (s + r)) * 2)), 2) if s + r else 0.0


def single(owner, other, stood, slots, cfg):
    """A shot of one, with room on the side they are turned to; taken over `other`'s shoulder if there is one."""
    centre, zoom = frame_for(slots, cfg)
    if other in stood and max(slots) - min(slots) < 0.5:
        side = 1 if stood[other]["slot"] > stood[owner]["slot"] else -1
        centre = round(_clamp(centre + side * cfg["lean"], zoom), 3)
    return centre, zoom


def shots(turns, pose, focus, music, drama, step, written=None, cfg=None):
    """-> the scene's shots in time order. `written` is {turn index: what the script asked for}."""
    cfg, written = {**DEFAULTS, **(cfg or {})}, written or {}
    names = lambda who: ", ".join(sorted(who)) or "no one"
    wide = dict(centre=round((SLOTS - 1) / 2, 3), zoom=1.0, on=[], over=None, angle=0.0, tilt=0.0)
    out = [dict(wide, t=0.0, kind="open", why="a scene opens wide, to show the place")]
    moments = [(c["t"], 1, c, None) for c in music if c["kind"] == "rise"]
    for turn in turns[1:]:
        for k, (t, who) in enumerate(changes(turn, pose, step, cfg["together"])):
            moments.append((t, 0, turn, (k, who)))
    for t, is_rise, x, extra in sorted(moments, key=lambda m: (m[0], m[1])):
        cur = out[-1]
        if is_rise:                                              # rule 6: go to whoever the moment is about, and push in until it lands
            who = x["subject"] if isinstance(x["subject"], str) else x["subject"][0]
            stood = at(pose, x["t"] + x.get("length", 0) + 0.01)
            if who not in stood:
                continue
            centre, zoom = frame_for([stood[who]["slot"]], cfg)
            h = height([who], stood)
            out.append(dict(t=t, centre=centre, zoom=round(zoom / cfg["push"], 3), on=[who], over=None, angle=h, tilt=0.0, kind="shot",
                            why=f"the music is building toward {who}"))
            out.append(dict(t=t + 1e-3, centre=centre, zoom=zoom, on=[who], over=None, angle=h, tilt=0.0, kind="push", lasts=x.get("length", 0),
                            why=f"the frame creeps in on {who} until the moment lands"))
            continue
        turn, (k, who) = x, extra
        t1 = (turn["start"] + turn["length"]) * step
        stood = at(pose, t1 - 0.01)
        ask = written.get(turn["index"]) if k == 0 else None
        if ask == "stay" or (k and written.get(turn["index"])):  # a written shot holds for its whole turn
            continue
        speaker = turn["who"] if turn["who"] in stood else None
        tilt = 0.0
        if ask == "wide":
            shot, why = dict(wide), "the script asks for the wide shot"
        elif ask:
            spec = ask if isinstance(ask, dict) else dict(on=ask)
            on = [e for e in ([spec["on"]] if isinstance(spec.get("on"), str) else spec.get("on") or []) if e in stood]
            if not on:
                continue
            over = spec.get("over") if spec.get("over") in stood else None
            slots = [stood[e]["slot"] for e in on]
            centre, zoom = single(on[0], over, stood, slots, cfg) if len(on) == 1 else frame_for(slots, cfg)
            zoom = float(spec.get("zoom", zoom))
            shot = dict(centre=round(_clamp(centre, zoom), 3), zoom=zoom, on=sorted(on), over=over,
                        angle=float(spec.get("angle", height(on, stood) if len(on) == 1 else 0.0)), tilt=float(spec.get("tilt", 0.0)))
            why = "the script asks for " + names(on) + (f", over {over}'s shoulder" if over else "")
        else:
            slots = [s for v in who.values() for s in v]
            events = [d for d in drama if d["subject"] in who and turn["start"] * step - 1e-9 <= d["t"] < t1 and d.get("shown")]
            top = max(events, key=lambda d: d["surprise"] * d["weight"], default=None)
            if len(who) >= 3:                                    # rule 1: three or more is the group
                centre, zoom = frame_for(slots, cfg)
                shot, why = dict(centre=centre, zoom=zoom, on=sorted(who), over=None, angle=0.0), f"{names(who)} all change at once"
            elif len(who) == 2:
                centre, zoom = frame_for(slots, cfg)
                shot, why = dict(centre=centre, zoom=zoom, on=sorted(who), over=None, angle=0.0), f"{names(who)} change together"
            else:
                owner = next(iter(who))
                other = (faced(owner, stood) if owner in stood else None) if owner == speaker else speaker     # rule 2
                centre, zoom = single(owner, other, stood, slots, cfg)
                over = other if other in stood and max(slots) - min(slots) < 0.5 else None
                shot = dict(centre=centre, zoom=zoom, on=[owner], over=over, angle=height([owner], stood))
                why = (f"it is {owner}'s moment" if top or owner != speaker else f"{owner} is speaking") + \
                      (f"; over {over}'s shoulder, " + ("who is being spoken to" if owner == speaker else "whose line is landing") if over else "")
            if top and top["valence"] < 0 and top["surprise"] * top["weight"] >= cfg["tilt_from"]:           # rule 5
                tilt = cfg["tilt"] * (1 if shot["centre"] < (SLOTS - 1) / 2 else -1)
                why += "; a hard bad surprise tips the frame"
            shot["tilt"] = tilt
            same = cur["on"] == shot["on"] and cur["over"] == shot["over"]
            inside = holds(cur, slots, cfg)
            if k and inside and cur["zoom"] < cfg["two"] + 1e-6:
                continue                                         # rule 3: a reaction already in a shared frame needs no shot of its own
            if same and inside and not tilt and not cur["tilt"]:
                continue                                         # rule 4
            if not cur["on"] and inside and shot["zoom"] / cur["zoom"] <= cfg["loose"]:
                continue
            if k:
                why = "a reaction outside the frame: " + why
        out.append(dict(shot, t=t, kind="shot", why=why))
    return out
