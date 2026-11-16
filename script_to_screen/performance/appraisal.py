"""Appraisal: what an event makes each character feel, worked out from who they are.

A derivation step, in front of expression. A turn says what happened (`event:`); this step asks,
for everyone present, three questions (after Lazarus, and Ortony, Clore and Collins):

    is it good or bad for my needs?      the need the event touches, and how strong that need is in me
    whose doing is it?                   the event's `by`, and who did the thing a fact records
    can I answer it?                     power: my dominance + whether this is my ground + whether my side outnumbers the other

    bad for esteem or belonging, and my doing        shame
    bad, someone else's doing, and I can answer      anger
    bad or a threat to safety, and I cannot          fear
    bad, over, nobody's doing                        sadness
    good                                             joy

How strong: the event's `size` (1 slight, 2 pointed, 3 undeniable), raised a step by a strong need
and bent a step by temperament (caution for bad feelings, drive for good ones). A slight event stays
slight whoever it happens to. Whoever did it feels joy if they cornered someone they know is guilty,
and shame if they harmed someone they are bonded to. A bystander with no stake of their own feels it
through their bond to whoever it happened to. A strong bad feeling still being carried colours the
next bad thing: it lands as more of the same.

A feeling written on a turn (`feel:`) always wins over the one worked out here.
"""
BAD, GOOD = ("loss", "threat"), ("gain", "relief")
KINDS = BAD + GOOD
NEEDS = ("comfort", "safety", "belonging", "esteem", "control")
DIALS = ("drive", "caution", "dominance", "warmth")


def clamp(n):
    return max(1, min(3, n))


class Minds:
    """Everything appraisal reads: each character's sheet, side and standing feeling, and the facts."""

    def __init__(self, sheets, sides, standing, facts, valence):
        self.sheets, self.sides, self.standing, self.facts, self.valence = sheets, sides, standing, facts, valence or {}

    def need(self, c, name):
        return ((self.sheets[c].get("profile") or {}).get("needs") or {}).get(name, 1)       # everyone has every need a little

    def dial(self, c, name):
        return ((self.sheets[c].get("profile") or {}).get("temperament") or {}).get(name, 0)

    def bond(self, a, b):
        """How far a trusts b. A bond is written as one number (trust) or as [trust, rating]: see crew.py."""
        v = (self.sheets[a].get("bonds") or {}).get(b, 0)
        return v[0] if isinstance(v, (list, tuple)) else v

    def power(self, c):
        mine = sum(1 for s in self.sides.values() if s == self.sides.get(c))
        others = sum(1 for s in self.sides.values() if s != self.sides.get(c))
        ground = 1 if self.need(c, "control") >= 2 else 0                 # whoever needs control treats the house as theirs
        return self.dial(c, "dominance") + ground + (1 if mine > others else -1 if mine < others else 0)

    def knows(self, c, fact):
        return c in (self.facts.get(fact, {}).get("knows") or [])

    def did(self, c, fact):
        return bool(fact) and self.facts.get(fact, {}).get("doer") == c


def _strength(size, need, dial, less=0):
    """`less` is 1 for a feeling at one remove: about what was done to someone else."""
    if size <= 1:
        return 1                                                          # a slight event stays slight
    return clamp(size + need - 1 + (1 if dial >= 2 else -1 if dial <= -1 else 0) - less)


def _targets(ev):
    t = ev.get("target") or []
    return [t] if isinstance(t, str) else list(t)


def stake(m, c, ev):
    return c in _targets(ev) or c == ev.get("by") or m.did(c, ev.get("fact"))


def appraise(m, c, ev, others=()):
    """What c feels about one event: [(emotion, strength, about, why)]. `others` are the turn's other events:
    someone with a stake in any of them is not a bystander to this one."""
    out, kind, need, size = [], ev["kind"], ev["need"], int(ev.get("size", 2))
    targets, by, fact = _targets(ev), ev.get("by"), ev.get("fact")
    if c in targets:
        n = m.need(c, need)
        if not n:
            return out
        if kind in GOOD:
            return [("joy", _strength(size, n, m.dial(c, "drive")), by if by != c else None, f"good for their {need}")]
        mine, hard, power = by == c or m.did(c, fact), _strength(size, n, m.dial(c, "caution")), m.power(c)
        about = by if by and by != c else None
        if mine and need in ("esteem", "belonging"):
            out.append(("shame", hard, about, f"bad for their {need}, and their own doing"))
        elif need == "safety" or (kind == "threat" and power < 1):
            out.append(("fear", hard, about, f"a threat to their {need} they cannot answer (power {power})"))
        elif power >= 1:
            out.append(("anger", hard, about, f"bad for their {need}, not their doing, and they can answer (power {power})"))
        elif kind == "loss" and not by:
            out.append(("sadness", hard, None, f"a loss to their {need} with nothing to be done"))
        else:
            out.append(("fear", hard, about, f"bad for their {need} and they cannot answer (power {power})"))
    elif c == by or m.did(c, fact):
        if c == by and ev.get("accuses") and m.knows(c, fact) and m.need(c, "control"):
            out.append(("joy", _strength(1, m.need(c, "control"), m.dial(c, "drive")), targets[0] if targets else None,
                        "they know they are right: good for their control"))
        hurt = [t for t in targets if kind in BAD and m.bond(c, t) > 0]
        if hurt:
            out.append(("shame", _strength(size, m.need(hurt[0], need), m.dial(c, "caution"), 1), hurt[0],
                        f"they did this to {hurt[0]}, who they are bonded to"))
    elif not any(stake(m, c, o) for o in others):
        for t in targets:                                                  # a bystander feels it through their bond to whoever it happened to
            b, n = m.bond(c, t), m.need(t, need)
            if not b or not n:
                continue
            good = (kind in GOOD) == (b > 0)
            s = _strength(size, n, m.dial(c, "drive" if good else "caution"), 1)
            out.append(("joy", s, t, f"{'good' if kind in GOOD else 'bad'} for {t}, who they are {'bonded to' if b > 0 else 'against'}") if good
                       else ("fear", s, by, f"bad for {t}, who they are bonded to"))
            break
    return out


def feelings(m, events, present):
    """-> {entity: {"feel": {emotion: n, "at": about}, "why": text}} for everyone the turn's events make feel something."""
    out = {}
    for c in present:
        found = [r for ev in events if not (ev.get("unseen") and not (c == ev.get("by") or m.did(c, ev.get("fact"))))    # unseen: only whoever did it knows
                 for r in appraise(m, c, ev, [o for o in events if o is not ev])]
        if not found:
            continue
        emo, n, about, why = max(found, key=lambda r: r[1])                # the strongest wins
        was = m.standing.get(c)
        if was and was[1] >= 2 and m.valence.get(was[0], 0) < 0 and m.valence.get(emo, 0) < 0:
            if was[0] != emo:
                why += f"; still carrying {was[0]} {was[1]}, so it lands as {was[0]}"   # a strong bad feeling colours the next bad thing
            elif was[1] > n:
                why += f"; already at {was[0]} {was[1]}, and a milder blow does not lessen it"
            emo, n = was[0], max(n, was[1])
        out[c] = dict(feel={emo: n, **({"at": about} if about else {})}, why=why)
    return out


def inclined(m, c, emotion):
    """What a feeling inclines its owner to do next, bent by temperament: (a word, what it looks like).
    These are the branches a scene could take from here; choosing one is the writer's job."""
    if emotion == "fear":
        return ("freeze", "goes still and small") if m.dial(c, "caution") >= 2 else ("back away", "puts distance between them")
    if emotion == "anger":
        return ("confront", "closes in and says it") if m.power(c) >= 1 else ("sulk", "turns away and says little")
    if emotion == "shame":
        if m.dial(c, "dominance") >= 1:
            return "hit back", "turns it on whoever raised it"
        return ("withdraw", "backs off and looks away") if m.dial(c, "caution") >= 2 else ("deny", "says it was not them, without facing anyone")
    if emotion == "joy":
        return ("press", "moves in and makes the most of it") if m.dial(c, "warmth") <= 0 else ("share", "turns to someone and lets it show")
    if emotion == "sadness":
        return ("seek company", "moves toward someone they are bonded to") if m.dial(c, "warmth") >= 1 else ("withdraw", "goes quiet and turns away")
    return "stop and look", "everything else waits"


def problems(ev, known, facts):
    """What is wrong with an event as written, if anything."""
    if ev.get("kind") not in KINDS:
        return f"an event's kind is one of {', '.join(KINDS)}, not '{ev.get('kind')}'"
    if ev.get("need") not in NEEDS:
        return f"an event touches one of {', '.join(NEEDS)}, not '{ev.get('need')}'"
    for e in _targets(ev) + ([ev["by"]] if ev.get("by") else []):
        if e not in known:
            return f"an event names '{e}', who is not an entity of this show"
    if not _targets(ev):
        return "an event needs a `target`: who it happens to"
    if ev.get("fact") and ev["fact"] not in facts:
        return f"an event is about the fact '{ev['fact']}', which the scene does not declare under `facts:`"
    return None
