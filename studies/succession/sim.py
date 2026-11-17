"""The succession, as wind-up toys: every house acts as its personality would, we say "go", and we watch.

Nothing is turn-based and nothing is scripted. The crown never moves. A house wins by HOLDING it, unchallenged, for
a set time. A beaten house is not destroyed: it is routed, goes home, recovers and comes back.

Nothing here is decided by the writers. Every rule is a line already on the house sheet (docs: The Houses), read off
as a rule. A house is one of three things at any moment: it CLAIMS the crown, it BACKS another house's claim, or it
stands aside.

How each house moves (its "Fights" and "Defends" lines):

    signet   goes to the crown and sits. Never chases. Comes back each time it is thrown off, weaker, until it is spent
    lode     never claims. Goes to whoever it backs; with nobody to back, it waits at its gate
    bout     goes for the crown and strikes anything it passes
    rue      goes for Bout and Plumb, the ones who did it; with nobody to punish, goes for the crown
    hasp     keeps its gate. Advances only once the fight at the crown has thinned. Withdraws at half strength
    plumb    moves only when the Breach is clear. Strikes only a false account, unless struck first. Never withdraws
    mallet   goes to the crown. Claims it only if nobody else has for a while
    glass    heads for whatever is happening. Being looked at hurts a house by how false its account is. Rolls home at half

Who backs whom (its "Makes allies" line), and the two stats that were always about this:

    signet   "by sealed treaty; keeps the letter"          backs nobody; takes any backer; never turns on one
    lode     "easily, with anyone strong; first to leave"  backs the strongest house it can see, and changes at once
    bout     "against a shared opponent only"               backs nobody; will not hit a house that is hitting its foe
    rue      "attaches to whoever blames it most"           backs the house that last routed it
    hasp     "very slowly; once closed, never releases"     backs a house only after a long time beside it, then for good
    plumb    "only with those it finds true"                backs nobody; refuses any backer whose account is not sound
    mallet   "with anyone who has work; serves whoever rules"   backs whoever holds the crown, and mends them
    glass    "with whatever interests it, until something else does"   backs whoever took the crown most recently
    standing "how willing the others are to live under it"  nobody backs a house whose standing is below 2 (Bout, Rue)

What a house knows (its "Carries a message" line). News of who holds the crown leaves the crown by road and is
passed from house to house. Hasp keeps it, so nothing goes on through the pass. Rue rubs out the name. So Signet,
Lode, Mallet, Hasp and Rue hear who holds it, late; Bout, Plumb and Glass know only what they can see.

The numbers, all from the sheet:

    reserve   what a house can lose before it is routed        10 x (wealth + stamina)
    blows     what it deals per second, shared among foes      force x (1 + 0.15 x (cunning - 3))      (Glass: 1.2 x (5 - the foe's truth))
    taken     blows land softer on a house others can accept   x (1 - 0.06 x standing)
    tiring    every second away from home costs                0.25 x (5 - stamina)
    fed       the outside world feeds some houses              0.12 x allies per second
    holding   the crown strengthens whoever holds it           +0.8 per second, less 0.3 x (5 - truth) for a false account

`python sim.py` runs it once; `python sim.py 300` runs it that many times with every pace and stat nudged;
add `alone` to either to switch all backing off (every house for itself).
"""
import heapq
import json
import math
import random
import sys

#            force wealth stamina cunning allies standing truth   pace (units a second on a road)
HOUSES = {
    "signet": (3, 5, 2, 3, 2, 2, 1, 1.6),
    "lode":   (2, 4, 4, 2, 5, 2, 2, 2.2),
    "bout":   (5, 1, 2, 3, 4, 1, 3, 3.0),
    "rue":    (4, 3, 5, 3, 2, 1, 1, 0.9),
    "hasp":   (4, 4, 5, 3, 4, 3, 3, 0.6),
    "plumb":  (3, 2, 4, 2, 2, 3, 5, 1.0),
    "mallet": (2, 5, 4, 4, 4, 5, 3, 1.6),
    "glass":  (1, 1, 4, 4, 2, 4, 4, 1.7),
}
AT = {"crown": (30, 16), "lode": (30, 6), "signet": (19, 19), "mallet": (36, 36), "hasp": (60, 24), "rue": (60, 47),
      "bout": (60, 61), "plumb": (84, 56), "glass": (84, 22), "breach": (60, 54)}
ROAD, FAINT, OPEN, RUBBLE = 1.0, 0.75, 0.5, 0.35          # how much of its pace a house keeps on each ground
WAYS = [("crown", "lode", ROAD), ("crown", "signet", ROAD), ("crown", "mallet", ROAD), ("crown", "hasp", ROAD), ("mallet", "hasp", ROAD),
        ("mallet", "rue", FAINT), ("rue", "breach", RUBBLE), ("bout", "breach", RUBBLE), ("plumb", "breach", OPEN),
        ("bout", "mallet", OPEN), ("bout", "crown", OPEN), ("rue", "crown", OPEN), ("breach", "mallet", OPEN),
        ("plumb", "hasp", OPEN), ("glass", "hasp", OPEN), ("plumb", "glass", OPEN)]
GROUND = {frozenset((a, b)): k for a, b, k in WAYS}
REACH, SIGHT, DT, LIMIT, HOLD, BACK, NEWS = 3.0, 30.0, 0.05, 900.0, 40.0, 0.7, 2.0
HEARS = {"signet": 11, "lode": 10, "mallet": 21, "hasp": 48, "rue": 47}     # road distance the news travels to reach each house


def route(start, avoid=()):
    """The quickest way from a house's home to the crown, as the places it passes."""
    best, heap, came = {start: 0.0}, [(0.0, start)], {}
    while heap:
        d, n = heapq.heappop(heap)
        if n == "crown":
            break
        for a, b, k in WAYS:
            if n in (a, b):
                m = b if n == a else a
                if m in avoid:
                    continue
                nd = d + math.dist(AT[a], AT[b]) / k
                if nd < best.get(m, 1e9):
                    best[m], came[m] = nd, n
                    heapq.heappush(heap, (nd, m))
    path, n = ["crown"], "crown"
    while n != start:
        n = came[n]
        path.append(n)
    return path[::-1]


def run(jitter=0.0, rng=None, trace=False, backing=True):
    rng = rng or random.Random(0)
    wob = lambda v: v * (1 + rng.uniform(-jitter, jitter)) if jitter else v
    H = {}
    for name, (force, wealth, stamina, cunning, allies, standing, truth, pace) in HOUSES.items():
        force, wealth, stamina, cunning, allies, standing = (wob(v) for v in (force, wealth, stamina, cunning, allies, standing))
        full = 10 * (wealth + stamina)
        H[name] = dict(name=name, pos=list(AT[name]), path=route(name), i=1, reserve=full, full=full, first=full, blows=force * (1 + 0.15 * (cunning - 3)),
                       soft=1 - 0.06 * standing, tiring=0.25 * max(0.0, 5 - stamina), fed=0.12 * allies, truth=truth, standing=HOUSES[name][5], pace=wob(pace),
                       mode="wait" if name in ("hasp", "plumb") else "go", routs=0, flee=0.5 if name in ("hasp", "glass") else 0.0, spent=False)
    H["plumb"]["path"] = route("plumb", avoid=("hasp",))                 # Plumb does not walk into a shut gate: it goes by the Breach
    t, log, frames = 0.0, [], []
    backs = {n: None for n in H}                                         # who each house backs right now
    foes_before, engaged_before = {n: [] for n in H}, set()
    held, holder, claims, taken_by = 0.0, None, 0.0, None                # taken_by: whoever took the crown most recently
    news, heard = [], {n: None for n in H}                               # news on the road, and what each house last heard
    routed_by, beside, bound = {n: None for n in H}, {}, None            # Rue's punisher; Hasp's long acquaintance; who Hasp closed on
    say = lambda kind, **kw: log.append(dict(t=round(t, 2), kind=kind, **kw))
    crown = AT["crown"]
    near = lambda h, p, r: math.dist(h["pos"], p) <= r
    out = lambda h: h["mode"] in ("routed", "mend")
    home = lambda h: near(h, AT[h["name"]], 0.5)
    at_crown = lambda h: not out(h) and near(h, crown, 1.0)
    west = lambda p: p[0] <= 60.5

    def toward(h, p, k):
        d = math.dist(h["pos"], p)
        step = h["pace"] * k * DT
        if d <= step:
            h["pos"] = list(p)
            return True
        h["pos"][0] += (p[0] - h["pos"][0]) / d * step
        h["pos"][1] += (p[1] - h["pos"][1]) / d * step
        return False

    def along(h, back=False):
        j = h["i"] - 1 if back else h["i"]
        if j < 0 or j >= len(h["path"]):
            return True
        a, b = h["path"][max(j - 1, 0)] if not back else h["path"][min(j + 1, len(h["path"]) - 1)], h["path"][j]
        if toward(h, AT[b], GROUND.get(frozenset((a, b)), OPEN)):
            h["i"] += -1 if back else 1
        return False

    def seek(h, goal, clear, stop=1.5):
        """Go to a point anywhere in the land. The ridge can be crossed only at the pass (if Hasp is away) or the Breach (if it is clear)."""
        if west(h["pos"]) != west(goal):
            ways = (["hasp"] if not home(H["hasp"]) or out(H["hasp"]) or h["name"] == "hasp" else []) + (["breach"] if clear else [])
            if not ways:
                return
            gate = AT[min(ways, key=lambda w: math.dist(h["pos"], AT[w]) + math.dist(AT[w], goal))]
            if toward(h, gate, OPEN):
                h["pos"][0] = 60.0 if west(goal) else 61.0
            return
        if not near(h, goal, stop):
            toward(h, goal, OPEN)

    while t < LIMIT:
        live = [h for h in H.values() if not out(h)]
        there = [h for h in live if at_crown(h)]
        # --- what each house knows about who holds the crown ---
        for item in [x for x in news if x[0] <= t]:
            heard[item[1]] = item[2]
            news.remove(item)
        knows = {n: (taken_by if near(H[n], crown, SIGHT) else heard[n]) for n in H}
        # --- who backs whom: each house's own line from the sheet ---
        if backing:
            def takes(c, n):                                             # will claimant c have n beside it?
                if out(H[c]) or backs[c] or H[c]["standing"] < 2 or c == n or c == "bout" or c == "lode" or (c == "mallet" and claims <= 10):
                    return False
                if c == "plumb":
                    return H[n]["truth"] >= 4
                return True
            want = dict(backs)
            seen = [h["name"] for h in live if h["name"] != "lode" and not home(h) and math.dist(H["lode"]["pos"], h["pos"]) < SIGHT and takes(h["name"], "lode")]
            want["lode"] = max(seen, key=lambda n: H[n]["reserve"], default=None)
            want["rue"] = routed_by["rue"] if routed_by["rue"] and takes(routed_by["rue"], "rue") else None
            for h in live:                                               # Hasp closes slowly on whoever stays beside it unharmed
                if h["name"] != "hasp" and not out(H["hasp"]) and near(h, H["hasp"]["pos"], 12) and h not in foes_before["hasp"]:
                    beside[h["name"]] = beside.get(h["name"], 0.0) + DT
                    if bound is None and beside[h["name"]] >= 60 and takes(h["name"], "hasp"):
                        bound = h["name"]
            want["hasp"] = bound if bound and not H[bound]["spent"] else None
            want["mallet"] = knows["mallet"] if knows["mallet"] and takes(knows["mallet"], "mallet") and knows["mallet"] != "mallet" else None
            want["glass"] = knows["glass"] if knows["glass"] and takes(knows["glass"], "glass") and knows["glass"] != "glass" else None
            for n in ("signet", "plumb", "bout"):
                want[n] = None
            for n in H:
                if out(H[n]):
                    want[n] = backs[n] if n == "hasp" else None
                if want[n] != backs[n]:
                    if backs[n]:
                        say("leaves", who=n, with_=backs[n])
                    backs[n] = want[n]
                    if backs[n]:
                        say("backs", who=n, with_=backs[n])
        side = lambda n: backs[n] or n
        waiting = lambda n: backing and not backs[n] and (n == "lode" or (n == "mallet" and claims <= 10))    # stands aside: neither claims nor backs

        def hostile(a, b):
            x, y = a["name"], b["name"]
            if side(x) == side(y):
                return False
            if x == "bout":
                return not (backing and {o["name"] for o in foes_before["bout"]} & {o["name"] for o in foes_before[y]})     # it will not hit a house that is hitting its foe
            if waiting(x) or waiting(y):
                return False
            if backs[x]:
                return b in foes_before[backs[x]] or H[backs[x]] in foes_before[y]            # a backer fights whoever its claimant fights
            if x in ("plumb", "glass"):
                return b["truth"] <= 2
            if x == "hasp" and home(a):
                return near(b, AT["hasp"], REACH)
            return True

        foes = {h["name"]: [] for h in H.values()}
        for i, a in enumerate(live):
            for b in live[i + 1:]:
                if near(a, b["pos"], REACH) and (hostile(a, b) or hostile(b, a)):
                    foes[a["name"]].append(b)
                    foes[b["name"]].append(a)
        for a in live:                                                   # a backer in reach joins its claimant's fight
            c = backs[a["name"]]
            if c and not out(H[c]):
                for o in foes[c]:
                    if o is not a and o not in foes[a["name"]] and side(o["name"]) != side(a["name"]) and near(a, o["pos"], REACH + 2):
                        foes[a["name"]].append(o)
                        foes[o["name"]].append(a)
        engaged = {frozenset((a, b["name"])) for a in foes for b in foes[a]}
        for pair in sorted(engaged - engaged_before, key=sorted):
            say("meet", who=sorted(pair))
        engaged_before = engaged
        # --- blows ---
        hurt = {n: 0.0 for n in H}
        for h in live:
            for o in foes[h["name"]]:
                dealt = 1.2 * (5 - o["truth"]) if h["name"] == "glass" else h["blows"]
                hurt[o["name"]] += dealt / len(foes[h["name"]]) * o["soft"] * DT
        # --- movement ---
        clear = not any(near(o, AT["breach"], 9) for o in live if o["name"] in ("bout", "rue"))
        for h in H.values():
            n = h["name"]
            if h["mode"] == "routed":
                if n in ("lode", "glass", "rue", "hasp", "mallet") and not near(h, AT[n], 0.05):
                    seek(h, AT[n], True, stop=0.0)
                    done = near(h, AT[n], 0.05)
                else:
                    done = h["i"] <= 0 or along(h, back=True) or near(h, AT[n], 0.05)
                if done:
                    h["mode"], h["i"], h["pos"] = "mend", 1, list(AT[n])
                continue
            if h["mode"] == "mend":
                if n == "signet" and h["full"] < 0.3 * h["first"]:
                    if not h["spent"]:
                        h["spent"] = True
                        say("spent", who=n)                              # the habit is gone: it does not come back again
                    continue
                if h["reserve"] >= BACK * h["full"]:
                    h["mode"] = "wait" if n in ("hasp", "plumb") else "go"
                    say("returns", who=n)
                continue
            if foes[n]:
                continue                                                 # in a fight: it stays in it
            if backs[n] and not out(H[backs[n]]):                        # beside whoever it backs
                was = at_crown(h)
                seek(h, H[backs[n]]["pos"], clear)
                if at_crown(h) and not was:
                    say("arrive", who=n)
                continue
            if n == "lode":
                if not near(h, AT["lode"], 0.05):
                    toward(h, AT["lode"], ROAD)
                continue
            if n == "hasp" and h["mode"] == "wait":
                fit = [o for o in live if o is not h and near(o, crown, 8) and o["reserve"] > 0.4 * o["full"] and not backs[o["name"]] and not waiting(o["name"])]
                if len(fit) <= 1 and t > 20:
                    h["mode"] = "go"
                    say("advances", who=n)
                continue
            if n == "plumb" and h["mode"] == "wait":
                if clear:
                    h["mode"] = "go"
                    say("advances", who=n)
                continue
            if n == "rue":
                blame = [o for o in (H["bout"], H["plumb"]) if not out(o) and west(o["pos"]) == west(h["pos"]) and math.dist(h["pos"], o["pos"]) < 40]
                if blame:
                    toward(h, min(blame, key=lambda o: math.dist(h["pos"], o["pos"]))["pos"], OPEN)
                    continue
            was = at_crown(h)
            if n == "glass":
                fights = [H[sorted(p)[0]]["pos"] for p in engaged if "glass" not in p]
                seek(h, min(fights, key=lambda p: math.dist(h["pos"], p)) if fights else crown, clear, stop=1.5 if fights else 0.0)
            elif h["i"] < len(h["path"]) and near(h, AT[h["path"][h["i"] - 1]], 80):
                along(h)
            if h["i"] >= len(h["path"]) and not near(h, crown, 0.05) and n != "glass":
                toward(h, crown, OPEN)
            if at_crown(h) and not was:
                say("arrive", who=n)
        # --- who holds ---
        there = [h for h in live if at_crown(h)]
        claims = claims + DT if H["mallet"] in there and not [h for h in there if h["name"] != "mallet" and not backs[h["name"]] and not waiting(h["name"])] else 0.0
        sides_there = {side(h["name"]) for h in there if not waiting(h["name"])}
        sole = H[next(iter(sides_there))] if len(sides_there) == 1 else None
        if sole is not None and (sole not in there or foes[sole["name"]] or any(foes[h["name"]] for h in there if side(h["name"]) == sole["name"])):
            sole = None
        # --- reserves ---
        for h in H.values():
            n = h["name"]
            if h["mode"] == "mend":
                h["reserve"] = min(h["full"], h["reserve"] + (1.2 + h["fed"]) * DT)
                continue
            if h["mode"] == "routed":
                continue
            gain = h["fed"] - (0.0 if home(h) else h["tiring"])
            if h is sole:
                gain += 0.8 - 0.3 * (5 - h["truth"]) + (0.5 if backs["mallet"] == n and H["mallet"] in there else 0.0)
            h["reserve"] = min(h["full"], h["reserve"] + gain * DT - hurt[n])
            if h["reserve"] <= 0 or (h["flee"] and foes[n] and h["reserve"] < h["flee"] * h["full"]):
                gave = h["reserve"] > 0
                h["reserve"], h["mode"], h["routs"] = max(h["reserve"], 0.03 * h["full"]), "routed", h["routs"] + 1
                if n == "signet":
                    h["full"] *= 0.75                                    # a habit that fails comes back weaker
                    h["reserve"] = min(h["reserve"], h["full"])
                if foes[n]:
                    routed_by[n] = max(foes[n], key=lambda o: o["blows"])["name"]
                say("withdraws" if gave else "fall", who=n, by=sorted(o["name"] for o in foes[n]))
        foes_before = foes
        now = sole["name"] if sole is not None else None
        if now != holder:
            holder, held = now, 0.0
            if holder:
                say("holds", who=holder)
                if holder != taken_by:
                    taken_by = holder
                    news += [(t + d / NEWS, n, holder) for n, d in HEARS.items()]
        elif holder:
            held += DT
            if held >= HOLD:
                t += DT
                say("end", who=holder, with_=sorted(n for n in H if backs[n] == holder and not out(H[n])))
                break
        if trace and round(t / DT) % 5 == 0:
            order = list(H)
            frames.append([round(t, 2)] + [[round(h["pos"][0], 1), round(h["pos"][1], 1), round(max(0, h["reserve"]) / h["first"], 2), int(out(h)),
                                           order.index(backs[h["name"]]) if backs[h["name"]] else -1] for h in H.values()])
        t += DT
    else:
        say("end", who=None, with_=[])
    end = log[-1]
    return dict(winner=end["who"], company=end["with_"], seconds=round(t, 1), log=log, frames=frames, order=list(H))


if __name__ == "__main__":
    args = sys.argv[1:]
    backing = "alone" not in args
    n = next((int(a) for a in args if a.isdigit()), 0)
    if not n:
        res = run(trace=True, backing=backing)
        for e in res["log"]:
            extra = (f"  by {e['by']}" if e.get("by") else "") + (f"  with {e['with_']}" if e.get("with_") else "")
            print(f"{e['t']:7.1f}s  {e['kind']:9} {e.get('who')}{extra}")
        json.dump(res, open("run.json" if backing else "run-alone.json", "w"))
    else:
        rng, wins, holds, secs = random.Random(1), {}, {}, []
        for _ in range(n):
            res = run(jitter=0.2, rng=rng, backing=backing)
            key = (res["winner"], tuple(res["company"]))
            wins[key] = wins.get(key, 0) + 1
            secs.append(res["seconds"])
            for e in res["log"]:
                if e["kind"] == "holds":
                    holds[e["who"]] = holds.get(e["who"], 0) + 1
        print("who ends up holding it (and who backs them):")
        for k, v in sorted(wins.items(), key=lambda kv: -kv[1]):
            print(f"  {v:4}  {k[0]}  {list(k[1])}")
        print("times each house held the crown at some point, per run:", {k: round(v / n, 2) for k, v in sorted(holds.items(), key=lambda kv: -kv[1])})
        print("median length:", sorted(secs)[n // 2], "s")
