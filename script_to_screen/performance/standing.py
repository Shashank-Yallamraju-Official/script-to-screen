"""Standing: where someone sits in society, and what that makes them want and able to do.

What society gave someone is their key, and what it withheld is their motive.

    standing        wealth, status and power, each -2 to +2 (after Weber). This is the facet they stand for.
    craft           which kinds of obstacle they can get past: people, locks, systems, movement, paper
    tells_self      how they excuse it (after Sykes and Matza): injury, victim, condemners, loyalties, responsibility

Pressure is not written. It is a need that is strong in them and that their standing does not meet:
comfort and safety are met by wealth, esteem by status, control by power. Belonging is met by people,
not by standing, so someone who needs it strongly is under pressure until a group gives it to them.

Whether they would say yes to something risky that answers the pressure is pressure plus drive less
caution: at 3 or more they say yes, at 1 or 2 they need persuading, below that they walk away.
"""
MEETS = dict(comfort="wealth", safety="wealth", esteem="status", control="power")
CRAFTS = ("people", "locks", "systems", "movement", "paper")
EXCUSES = dict(injury="Nobody gets hurt. They're insured.", victim="They had it coming.", condemners="They're the real thieves.",
               loyalties="It's for the people who depend on me.", responsibility="I only do my part. What happens after is not on me.")
CORNERS = {(True, False): "the respected and broke", (False, True): "new money", (False, False): "has nothing but what they can do"}


def profile(sheet):
    p = sheet.get("profile") or {}
    return p.get("temperament") or {}, p.get("needs") or {}, p.get("standing") or {}


def pressures(sheet):
    """-> [(need, pressure 1..3, why)], strongest first: the needs their standing leaves unmet."""
    _, needs, standing = profile(sheet)
    out = []
    for need, strength in needs.items():
        if need == "belonging":
            short, why = 2, "belonging is met by people, and they have nobody"
        else:
            dial = standing.get(MEETS.get(need), 0)
            short, why = max(0, 1 - dial), f"{MEETS.get(need)} {dial:+d} does not meet it"
        p = min(3, short) if strength >= 2 else max(0, short - 1) if strength == 1 else 0
        if p:
            out.append((need, p, why))
    return sorted(out, key=lambda x: -x[1])


def facet(sheet):
    """Their position in a phrase: what they have and what they lack."""
    _, _, st = profile(sheet)
    has = [k for k in ("wealth", "status", "power") if st.get(k, 0) >= 1]
    lacks = [k for k in ("wealth", "status", "power") if st.get(k, 0) <= -1]
    return ("has " + " and ".join(has) if has else "has none of wealth, status or power") + ("; lacks " + " and ".join(lacks) if lacks else "")


def answer(sheet):
    """Would they say yes to something risky that answers their pressure? -> (yes | persuade | no, score, the need to appeal to, why)."""
    temper, _, _ = profile(sheet)
    press = pressures(sheet)
    top = press[0] if press else (None, 0, "nothing is pressing on them")
    lean = temper.get("drive", 0) - temper.get("caution", 0)
    score = top[1] + lean
    verdict = "yes" if score >= 3 else "persuade" if score >= 1 else "no"
    why = (f"{top[0]} is strong in them and {top[2]} (pressure {top[1]})" if top[0] else top[2]) + \
          f"; drive less caution is {lean:+d}"
    return verdict, score, top[0], why
