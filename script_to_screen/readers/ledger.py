"""The audience ledger: what a viewer has had the chance to learn, scene by scene.

    s2s ledger [show folder]

A viewer only sees outputs. One sighting of a tell is ambiguous, so a tell counts as learned
after it has shown in `learn_after` separate scenes. Rules checked here:
  - a turn that `relies_on` a tell fails unless that tell was learned in earlier scenes
  - a scene should show at most one tell the audience has never seen, per entity
"""
import json
from pathlib import Path

from ..performance import Scene
from ..script import ScriptError, load_yaml, scene_key, scene_paths


def build(root, override=None, lib=None):
    """Walk every scene in order. Returns (table, problems).

    table[entity][emotion] = dict(seen, need, learned, positions, hidden)
    """
    override = override or {}
    need = load_yaml(Path(root) / "show.yaml")["ledger"]["learn_after"]
    seen, table, problems, carry = {}, {}, [], {}
    for path in scene_paths(root):
        try:
            sc = Scene(path, script=override.get(path), lib=lib, carry=carry)
        except (ScriptError, KeyError, TypeError) as e:
            problems.append(dict(level="error", scene=scene_key(path, root), turn=None, msg=str(e)))
            continue
        carry = sc.carry_out                                 # feelings and standing carry into the next scene
        for p in sc.problems:
            problems.append(dict(p, scene=sc.key))
        for t in sc.turns:                                   # payoffs must rest on learned tells
            for e, emo in t["relies_on"].items():
                sig = json.dumps(sc.ents[e]["tells"].get(emo), sort_keys=True) if e in sc.ents else None
                n = len(seen.get((e, emo, sig), []))
                if n < need:
                    problems.append(dict(level="error", scene=sc.key, turn=t["id"],
                                         msg=f"relies on {e}'s {emo} tell, which the audience has seen in {n} of {need} scenes"))
        cells = {}
        for t in sc.turns:
            for _, infos in t["info"]:
                for e, info in infos.items():
                    if info["felt"]:
                        c = cells.setdefault((e, info["felt"]), dict(level=0, positions=set()))
                        c["level"] = max(c["level"], info["level"])
                        if info["level"]:
                            c["positions"].add(info["klass"])
        fresh = {}
        for (e, emo), c in cells.items():
            # a changed tell (an arc step) has a new signature, so the audience starts over on it
            sig = json.dumps(sc.ents[e]["tells"].get(emo), sort_keys=True)
            row = table.setdefault(e, {}).setdefault(emo, dict(seen=0, need=need, learned=False, positions=[], hidden=0, sig=sig))
            if row["sig"] != sig:
                row.update(seen=0, learned=False, positions=[], sig=sig)
            if c["level"] == 0:
                row["hidden"] += 1                          # felt, but nothing leaked
                continue
            prior = seen.setdefault((e, emo, sig), [])
            if not prior:
                fresh.setdefault(e, []).append(emo)
            prior.append(sc.key)
            row["seen"] = len(prior)
            row["learned"] = row["seen"] >= need
            row["positions"] = sorted(set(row["positions"]) | c["positions"])
        for e, emos in fresh.items():
            if len(emos) > 1:
                problems.append(dict(level="warn", scene=sc.key, turn=None,
                                     msg=f"{e} shows {len(emos)} tells the audience has never seen ({', '.join(emos)}); one new thing per scene reads more clearly"))
    return table, problems
