"""Position and expression: from what is true to what an observer could see.

Two derivation steps in one pass over the room:
  position     side and status give each entity a weight, and weight gives gain
  expression   intensity x gain says how many of an entity's own tells show
A `take` (a deliberate momentary action) outranks the tells.
"""
from ..world import SLOTS, sgn

POSTURE = {"upright": (1.0, 1.0, 0), "contracted": (1.12, 0.8, 0), "lean_in": (1.0, 1.0, 1), "lean_back": (1.0, 1.0, -1)}


def observe(st, ents, gcfg, flag, tid):
    """st: the world's state per entity. -> {entity: observable channels + `info` (why)}."""
    present = [e for e in st if st[e]["present"]]
    sided = [e for e in present if st[e]["side"]]
    sides = {st[e]["side"] for e in sided}
    total = sum(st[e]["status"] for e in sided) or 1
    out = {}
    for e, s in st.items():
        info = dict(side=s["side"], status=s["status"], sympathy=s.get("sympathy", 1), weight=None, gain=1.0, klass="unopposed",
                    mine=1, others=0, felt=None, intensity=0, level=0, at=None)
        if s["side"] and len(sides) > 1 and s["present"]:
            mine = [x for x in sided if st[x]["side"] == s["side"]]
            info["mine"], info["others"] = len(mine), len(sided) - len(mine)
            info["weight"] = sum(st[x]["status"] for x in mine) / total
            info["gain"] = max(gcfg["min"], min(gcfg["max"], gcfg["slope"] * info["weight"]))
            info["klass"] = ("alone" if len(mine) == 1 and info["others"] > 1 else
                             "minority" if len(mine) < info["others"] else
                             "majority" if len(mine) > info["others"] else "even")
        expr = {}
        if s["felt"] and s["present"]:
            emo, inten, at = s["felt"]
            info.update(felt=emo, intensity=inten, at=at)
            tells = ents[e]["tells"].get(emo)
            if tells is None:
                flag("error", tid, f"{e} feels {emo} but entities/{e}.yaml has no tell for it")
            else:
                info["level"] = max(0, min(len(tells), int(inten * info["gain"] + 0.5)))
                for tell in tells[:info["level"]]:
                    for k, v in tell.items():               # (a sheet's tells were checked when its entity entered)
                        expr[k] = expr.get(k, 0) + v if k == "distance" else v
        out[e] = (info, expr)

    # where everyone stands: baseline slot plus any approach/retreat the feeling causes
    slots = {}
    for e, s in st.items():
        info, expr = out[e]
        slot, src = (s.get("take") or {}).get("slot", s["slot"]), info["at"]
        if expr.get("distance") and src in st and src != e:
            away = sgn(slot - st[src]["slot"]) or 1
            slot = max(0, min(SLOTS - 1, slot + expr["distance"] * away))
            slot = max(slot, st[src]["slot"] + 1) if away > 0 else min(slot, st[src]["slot"] - 1)
            taken = {o["slot"] for x, o in st.items() if x != e and o.get("present", True)}
            base = (s.get("take") or {}).get("slot", s["slot"])
            while slot in taken and slot != base:            # nobody backs into a place where someone is standing: they go as far as there is room
                slot -= sgn(slot - base)
        slots[e] = slot

    def toward(e, other):
        return (sgn(slots[other] - slots[e]) or 1) if other in slots and other != e else 0

    obs = {}
    for e, s in st.items():
        info, expr = out[e]
        src = info["at"]
        # body orientation: -1 faces left, 0 faces out to the viewer, 1 faces right
        take = s.get("take") or {}               # a deliberate momentary action outranks the tells
        o = take.get("orient", s["orient"])
        facing = 0 if o == "out" else -toward(e, o["away"]) if isinstance(o, dict) else toward(e, o)
        if "orient" in expr and "orient" not in take:
            facing = {"out": 0, "toward": toward(e, src), "away": -toward(e, src)}[expr["orient"]]
        a = take["attention"] if "attention" in take else expr.get("attention", s["attention"])
        if a == "ahead":
            lx, ly = facing, 0
        elif a == "down":
            lx, ly = facing * 0.3, 1
        elif a == "up":
            lx, ly = 0, -1
        elif a == "viewer":
            lx, ly = 0, 0
        elif a == "source":
            lx, ly = toward(e, src), 0
        elif a == "away":
            lx, ly = -toward(e, src) or -facing, 0
        elif isinstance(a, dict):
            lx, ly = -toward(e, a["away"]), 0
        else:
            lx, ly = toward(e, a), 0
        sx, sy, lean = POSTURE[take.get("posture") or expr.get("posture", s["posture"])]
        lean *= (toward(e, src) or facing) if "posture" in expr and "posture" not in take else facing
        obs[e] = dict(slot=slots[e], facing=facing, lx=lx, ly=ly, sx=sx, sy=sy, lean=lean,
                      alpha=1.0 if s["present"] else 0.0, tone=expr.get("tone"),
                      latency=expr.get("latency", 0), info=info)
    return obs
