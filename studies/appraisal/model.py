"""A prototype of appraisal, to test the idea before it is built into the engine (see docs/lld-profiles.md).

Given who the characters are (profiles, bonds), what is true and who knows it (facts), and one event,
work out what each character present feels. Nothing here is used by the engine.

    python studies/appraisal/model.py            # prints the comparison with the hand-written scenes
"""
from pathlib import Path

import yaml

HERE = Path(__file__).parent
NEEDS = ("comfort", "safety", "belonging", "esteem", "control")
BAD, GOOD = ("loss", "threat"), ("gain", "relief")


def clamp(n):
    return max(1, min(3, n))


def bend(dial):
    """A strong temperament makes its kind of feeling land harder; a weak one, softer."""
    return 1 if dial >= 2 else -1 if dial <= -1 else 0


class World:
    def __init__(self, cast, scene):
        self.cast, self.scene = cast, scene
        self.facts = scene.get("facts") or {}
        self.sides = scene.get("sides") or {}

    def need(self, c, need):
        return self.cast[c].get("needs", {}).get(need, 1)              # everyone has every need a little; a profile says which are strong or absent

    def dial(self, c, name):
        return self.cast[c].get("temperament", {}).get(name, 0)

    def bond(self, a, b):
        return self.cast[a].get("bonds", {}).get(b, 0)

    def power(self, c):
        """Can they do anything about it? Their dominance, whether this is their ground, and whether their side outnumbers the other."""
        mine = sum(1 for e, s in self.sides.items() if s == self.sides.get(c))
        others = sum(1 for e, s in self.sides.items() if s != self.sides.get(c))
        ground = 1 if self.need(c, "control") >= 2 else 0              # whoever needs control treats the house as theirs
        return self.dial(c, "dominance") + ground + (1 if mine > others else -1 if mine < others else 0)

    def knows(self, c, fact):
        return c in (self.facts.get(fact, {}).get("knows") or [])

    def did(self, c, fact):
        return self.facts.get(fact, {}).get("doer") == c


def appraise(w, c, ev):
    """What c feels about this event: [(emotion, intensity, why)]. Usually one, sometimes none, occasionally two."""
    out, kind, need, size = [], ev["kind"], ev["need"], ev.get("size", 2)
    targets = ev["target"] if isinstance(ev["target"], list) else [ev["target"]]
    by, fact = ev.get("by"), ev.get("fact")
    if ev.get("unseen") and c != by:
        return out                                                     # it happened where they could not see it
    if c in targets:
        n = w.need(c, need)
        if n:
            base = size + n - 1
            if kind in GOOD:
                out.append(("joy", clamp(base + bend(w.dial(c, "drive"))), f"good for their {need}"))
            else:
                mine = by == c or (fact and w.did(c, fact))
                hard = clamp(base + bend(w.dial(c, "caution")))
                if mine and need in ("esteem", "belonging"):
                    out.append(("shame", hard, f"bad for their {need}, and their own doing"))
                elif need == "safety" or (kind == "threat" and w.power(c) < 1):
                    out.append(("fear", hard, f"a threat to their {need} they cannot answer (power {w.power(c)})"))
                elif by and by != c and w.power(c) >= 1 or (not mine and w.power(c) >= 1):
                    out.append(("anger", hard, f"bad for their {need}, someone else's doing, and they can answer (power {w.power(c)})"))
                elif kind == "loss":
                    out.append(("sadness", hard, f"a loss to their {need} with nothing to be done"))
                else:
                    out.append(("fear", hard, f"bad for their {need} and they cannot answer (power {w.power(c)})"))
    elif c == by:
        if ev.get("accuses") and fact and w.knows(c, fact):            # cornering someone you know is guilty serves your need for control
            n = w.need(c, "control")
            if n:
                out.append(("joy", clamp(1 + n - 1 + bend(w.dial(c, "drive"))), "they know they are right: good for their control"))
        hurt = [t for t in targets if kind in BAD and w.bond(c, t) > 0]
        if hurt:                                                       # harming someone you are bonded to is your own doing
            n = w.need(hurt[0], need)
            out.append(("shame", clamp(size + n - 1 - 1 + bend(w.dial(c, "caution"))), f"they did this to {hurt[0]}, who they are bonded to"))
    else:
        for t in targets:                                              # a bystander feels it through their bond to whoever it happened to
            b, n = w.bond(c, t), w.need(t, need)
            if not b or not n:
                continue
            base = size + n - 1 - 1
            if (kind in BAD) == (b > 0):
                out.append(("fear", clamp(base + bend(w.dial(c, "caution"))), f"bad for {t}, who they are bonded to") if b > 0
                           else ("joy", clamp(base + bend(w.dial(c, "drive"))), f"good for {t}, who they are against"))
            else:
                out.append(("joy", clamp(base + bend(w.dial(c, "drive"))), f"good for {t}, who they are bonded to" if b > 0 else f"bad for {t}, who they are against"))
            break
    return out


def compare():
    data = yaml.safe_load((HERE / "setups.yaml").read_text())
    rows = []
    for scene in data["scenes"]:
        w = World(data["cast"], scene)
        for ev in scene["events"]:
            hand = ev.get("hand") or {}
            for c in scene["present"]:
                got = appraise(w, c, ev)
                want = hand.get(c)
                if not got and not want:
                    continue
                g = got[0] if got else None
                if want and g:
                    verdict = "match" if (g[0], g[1]) == (want[0], want[1]) else "right feeling, off by one" if g[0] == want[0] and abs(g[1] - want[1]) == 1 else \
                              "right feeling, wrong strength" if g[0] == want[0] else "wrong feeling"
                elif want:
                    verdict = "missed"
                else:
                    verdict = "extra"
                rows.append(dict(scene=scene["id"], event=ev["what"], who=c, hand=f"{want[0]} {want[1]}" if want else "nothing",
                                 model=" and ".join(f"{e} {i}" for e, i, _ in got) if got else "nothing", verdict=verdict,
                                 why="; ".join(y for _, _, y in got), note=ev.get("note", {}).get(c, "")))
    return rows


if __name__ == "__main__":
    rows = compare()
    print("| Scene | Event | Who | Written by hand | Model | Verdict |\n|---|---|---|---|---|---|")
    for r in rows:
        print(f"| {r['scene']} | {r['event']} | {r['who']} | {r['hand']} | {r['model']} | {r['verdict']} |")
    tally = {}
    for r in rows:
        tally[r["verdict"]] = tally.get(r["verdict"], 0) + 1
    print()
    for k, v in sorted(tally.items(), key=lambda kv: -kv[1]):
        print(f"{v:>3}  {k}")
