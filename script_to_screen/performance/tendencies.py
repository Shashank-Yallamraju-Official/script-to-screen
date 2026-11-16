"""Tendencies: what groups usually do in a kind of situation. General rules, declared once.

A tendency reads the situation and the group, and says what it does to whom. Each is a finding
from social psychology cut down to one condition and one effect; `evidence` says how well the
finding holds up. They are tendencies, so each can be switched off for a show (`tendencies: {name: off}`
in show.yaml), and a character's temperament can resist one.

A situation is: who is here (`present`), whether the trouble comes from inside the group or outside
(`threat`), whether anyone knows whose doing it is (`blame`), whether there is a clock (`clock`), what
each person feels about it (`felt`: {member: (emotion, strength)}), and whether someone has just
given something (`gift`: {from, to, what}).

    apply(situation, sheets, off) -> [{name, to, effect, why}] in the order they bite; a stronger
    tendency can silence a weaker one, and says so.
"""
from . import crew

TENDENCIES = {
    "common enemy": dict(when="a threat from outside the group", then="ranks close: quarrels and blame are dropped until it has passed",
                         evidence="strong", source="Sherif, Robbers Cave"),
    "threat rigidity": dict(when="a threat and a clock", then="everyone looks to whoever is top of the pecking order, and nobody improvises",
                            evidence="moderate", source="Staw, Sandelands and Dutton"),
    "scapegoating": dict(when="a loss and nobody knows whose doing it is", then="blame runs to the weak link",
                         evidence="moderate", source="scapegoat theory"),
    "emotional contagion": dict(when="one member's feeling is stronger than the others'", then="it spreads to those who trust them; a calm leader steadies the rest",
                                evidence="moderate", source="Hatfield, Cacioppo and Rapson"),
    "conformity": dict(when="one member stands alone against the rest", then="they go along out loud; one ally is enough to hold out",
                       evidence="strong", source="Asch"),
    "reciprocity": dict(when="someone gives something: a favour, a secret, a confession", then="it is returned in kind",
                        evidence="strong", source="Gouldner; Cialdini"),
}


def _dial(sheets, m, name):
    return ((sheets[m].get("profile") or {}).get("temperament") or {}).get(name, 0)


def apply(situation, sheets, off=()):
    present = list(situation["present"])
    felt, read = dict(situation.get("felt") or {}), crew.readings(sheets, present)
    top, out = read["order"][0], []
    on = lambda name: name not in off
    outside = situation.get("threat") == "outside"
    if on("common enemy") and outside:
        out.append(dict(name="common enemy", to=present, effect="close ranks", why="the threat is from outside: whatever they were quarrelling about waits"))
    if on("threat rigidity") and situation.get("threat") and situation.get("clock"):
        for m in present:
            if m != top:
                out.append(dict(name="threat rigidity", to=[m], effect=f"looks to {top}", why=f"under threat and against the clock, the decision goes to {top}, who is top of the pecking order"))
        out.append(dict(name="threat rigidity", to=[top], effect="decides", why="everyone is looking at them"))
    if on("scapegoating") and situation.get("loss") and situation.get("blame") == "unclear":
        weak = read["weak_link"]
        if outside and on("common enemy"):
            out.append(dict(name="scapegoating", to=[weak], effect="(silenced)", why=f"blame would run to {weak}, the weak link, but the threat from outside is stronger; it comes back when the threat has passed"))
        else:
            blamers = [m for m in present if m != weak and _dial(sheets, m, "warmth") < 2]      # the warmest will not join in
            out.append(dict(name="scapegoating", to=blamers, effect=f"blames {weak}", why=f"nobody knows whose doing it is, and {weak} is the one the group trusts and rates least"))
    if on("emotional contagion") and felt:
        source = max(felt, key=lambda m: felt[m][1])
        emo, n = felt[source]
        if felt.get(top, (None, 9))[1] <= 1 and source != top:
            out.append(dict(name="emotional contagion", to=[m for m in present if m != top], effect=f"steadied by {top}", why=f"{top} is calm, and the rest take their cue from the top"))
        else:
            caught = [m for m in present if m != source and crew.tie(sheets, m, source)[0] >= 1 and felt.get(m, (None, 0))[1] < n and _dial(sheets, m, "warmth") >= 0]
            if caught:
                out.append(dict(name="emotional contagion", to=caught, effect=f"catches {source}'s {emo}", why=f"{source} feels it most ({emo} {n}), and it spreads to those who trust them"))
    if on("conformity") and situation.get("dissenter") in present:
        d = situation["dissenter"]
        allies = [m for m in present if m != d and situation.get("sides", {}).get(m) == situation.get("sides", {}).get(d)]
        if not allies and _dial(sheets, d, "dominance") < 2:
            out.append(dict(name="conformity", to=[d], effect="goes along out loud", why="alone against everyone else, and not dominant enough to hold out"))
    gift = situation.get("gift")
    if on("reciprocity") and gift:
        out.append(dict(name="reciprocity", to=[gift["to"]], effect=f"returns it to {gift['from']} in kind", why=f"{gift['from']} gave {gift['what']}, and a gift asks for one back"))
    return out
