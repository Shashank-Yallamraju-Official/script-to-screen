"""Placing: where an entity stands when the script does not say.

Someone found in the room as a scene opens stands where what they care about puts them: beside
the thing that serves their strongest need, near whoever they are bonded to, at a civil distance
from everyone else. Someone who arrives later comes in through the door, or from the side the
script names (`from: left`).

A regard is what a thing makes someone feel. It is written on their sheet
(`regards: {plate: {shame: 2}}`), or follows from their needs: a thing that serves a need that is
strong in them is a joy to them, as strong as the need.
"""
from ..world import SLOTS


def regard(sheet, name, thing, valence, came=None):
    """-> (emotion, strength, pull, why): what this thing is to them. pull is above 0 if it draws them and below if it repels.
    `came` is what the story has made of it for them ({thing: (emotion, strength)}), which outranks everything."""
    if came and name in came:
        emo, n = came[name]
        return emo, n, (valence or {}).get(emo, 0) * n, f"the {name} has come to mean {emo} {n} to them"
    written = (sheet.get("regards") or {}).get(name)
    if written:
        emo = next(iter(written))
        return emo, written[emo], (valence or {}).get(emo, 0) * written[emo], f"their sheet says the {name} is {emo} {written[emo]} to them"
    need = ((sheet.get("profile") or {}).get("needs") or {}).get(thing.get("serves"), 1) if thing.get("serves") else 0
    if need >= 2:
        return "joy", need, need, f"the {name} serves their {thing['serves']}, which is strong in them"
    return None


def _dial(sheet, name):
    return ((sheet.get("profile") or {}).get("temperament") or {}).get(name, 0)


def _near(d, best):
    return max(0.0, 1 - abs(d - best) / 4)


def found(e, sheet, taken, things, bonds_to, valence, came=None):
    """Where e stands in a room they are already in: (slot, what drew them or None, why)."""
    best, why_best, drew = None, "", None
    free = [s for s in range(SLOTS) if s not in taken.values()]
    for s in free:
        score, reasons = 0.1 * _near(abs(s - (SLOTS - 1) / 2), 0), []
        for name, thing in things.items():
            r = regard(sheet, name, thing, valence, came)
            if not r:
                continue
            d = abs(s - thing["at"])
            if r[2] > 0:
                part = r[2] * (1 + _dial(sheet, "drive") / 2) * _near(d, 1)                # right beside it, not on top of it
            else:
                part = r[2] * (1 + _dial(sheet, "caution") / 2) * max(0.0, 1 - d / 4)       # the further the better
            score += part
            reasons.append((abs(part), name, r[3], r[2] > 0))
        for other, at in taken.items():
            b, d = bonds_to.get(other, 0), abs(s - at)
            part = b * (1 + _dial(sheet, "warmth") / 2) * _near(d, 2) if b else 0.3 * _near(d, 3)   # close to a friend; a civil distance from anyone else
            score += part
            if b:
                reasons.append((abs(part), other, f"they are bonded to {other}", b > 0))
        key = (round(score, 6), -abs(s - (SLOTS - 1) / 2), -s)
        if best is None or key > best[0]:
            top = max(reasons, default=None)
            best = (key, s)
            drew = top[1] if top and top[3] and top[1] in things else None
            why_best = (f"{'beside' if top[3] else 'away from'} {'the ' if top[1] in things else ''}{top[1]}: {top[2]}" if top else
                        "nothing here draws them, so they stand at a civil distance from the others" if taken else "nothing here draws them, so they stand in the middle")
    if best is None:
        raise ValueError("the room is full")
    return best[1], drew, why_best


def arrives(e, spec, taken, things):
    """Where e stands having just come in: (slot, why)."""
    src = spec.get("from")
    doors = {k: v for k, v in things.items() if v["kind"] == "door"}
    if src in things:
        at, why = things[src]["at"], f"comes in by the {src}"
    elif src in ("left", "right"):
        at, why = (0 if src == "left" else SLOTS - 1), f"comes in from the {src}"
    elif doors:
        name = next(iter(doors))
        at, why = doors[name]["at"], "comes in through the door"
    else:
        at, why = 0, "comes in from the left (the place has no door)"
    free = [s for s in range(SLOTS) if s not in taken.values()]
    if not free:
        raise ValueError("the room is full")
    return min(free, key=lambda s: (abs(s - at), s)), why


def named(text, things):
    """The first thing a line names, and the word that names it: (thing, word) or None. A thing answers to its name and its `aka`."""
    plain = lambda w: "".join(ch for ch in w.lower() if ch.isalpha() or ch == "'")
    words = [plain(w.replace("\u00b7", "").replace("^", "")) for w in str(text).split()]
    for w in words:
        for name, thing in things.items():
            if w and w in [plain(x) for x in [name] + list(thing.get("aka") or [])]:
                return name, w
    return None


def touched(do, things):
    """The things a turn's deliberate actions turn to, look at or walk toward: {thing: who did}."""
    out = {}
    for e, spec in (do or {}).items():
        for v in [spec.get("orient"), spec.get("attention"), (spec.get("move") or {}).get("toward")]:
            if isinstance(v, str) and v in things:
                out.setdefault(v, e)
    return out
