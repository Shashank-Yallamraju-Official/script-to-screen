"""A group: how each member sees each other, and what that adds up to.

A tie is how one member sees another: [trust, rating], each -2 to +2 (after Fiske: do you mean me
well, and can you deliver). It is one-directional. The four corners are the four attitudes:

                      rates them        does not rate them
    trusts them       relies on         carries
    does not trust    watches           dismisses

Everything else here is read off the ties, never written: the pecking order, the factions, the
hinge (whoever holds two parts together), the weak link, cohesion.
"""
def tie(sheets, a, b):
    """How a sees b: (trust, rating)."""
    v = (sheets[a].get("bonds") or {}).get(b, 0)
    return (v[0], v[1]) if isinstance(v, (list, tuple)) else (v, 0)


def attitude(trust, rate):
    return ("relies on" if rate >= 1 else "carries") if trust >= 1 else ("watches" if rate >= 1 else "dismisses")


def _mutual(sheets, a, b):
    return tie(sheets, a, b)[0] >= 1 and tie(sheets, b, a)[0] >= 1


def _parts(members, linked):
    left, out = list(members), []
    while left:
        part, grow = [left.pop(0)], True
        while grow:
            grow = False
            for m in list(left):
                if any(linked(m, x) for x in part):
                    part.append(m)
                    left.remove(m)
                    grow = True
        out.append(part)
    return out


def readings(sheets, members):
    """-> {order, factions, hinge, weak_link, cohesion, incoming}: what the ties add up to."""
    incoming = {}
    for m in members:
        seen = [tie(sheets, o, m) for o in members if o != m]
        incoming[m] = (sum(t for t, _ in seen) / len(seen), sum(r for _, r in seen) / len(seen)) if seen else (0.0, 0.0)
    temper = lambda m, k: ((sheets[m].get("profile") or {}).get("temperament") or {}).get(k, 0)
    power = lambda m: ((sheets[m].get("profile") or {}).get("standing") or {}).get("power", 0)
    score = {m: incoming[m][1] + temper(m, "dominance") + power(m) / 2 for m in members}       # rated by the others, takes charge, has clout
    order = sorted(members, key=lambda m: -score[m])
    linked = lambda a, b: _mutual(sheets, a, b)
    factions = _parts(members, linked)
    hinge = None
    for m in members:                                            # take them out: does a part that held together come apart?
        rest = [x for x in members if x != m]
        if len(_parts(rest, linked)) > len(factions) - (1 if [m] in factions else 0):
            hinge = m
            break
    pairs = [(a, b) for i, a in enumerate(members) for b in members[i + 1:]]
    cohesion = sum((tie(sheets, a, b)[0] + tie(sheets, b, a)[0]) / 2 for a, b in pairs) / len(pairs) if pairs else 0.0
    weak = min(members, key=lambda m: (incoming[m][0] + incoming[m][1], score[m]))
    return dict(order=order, score=score, factions=factions, hinge=hinge, weak_link=weak, cohesion=round(cohesion, 2), incoming=incoming)


def strain(sheets, a, b):
    """How much it costs a to have to rely on b: 0 if a trusts and rates them, up to 6 if neither at all."""
    t, r = tie(sheets, a, b)
    return max(0, 1 - t) + max(0, 1 - r)
