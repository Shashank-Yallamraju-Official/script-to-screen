"""Commands that read: what is in the show, what is true at a moment, and why."""
import json

from ..performance import Scene
from ..readers import ledger, parity
from ..script import ScriptError, scene_key, scene_paths
from . import A, COMMANDS, FAILED, Refused, address, command, describe, edit


def built(root, path, tid=None):
    sc = Scene(path)
    if tid is None:
        return sc, None
    for t in sc.turns:
        if str(t["id"]) == str(tid):
            return sc, t
    raise Refused(f"no turn '{tid}' in {sc.key}", hint="its turns are: " + ", ".join(str(t["id"]) for t in sc.turns))


@command("commands", "List every command with its arguments and an example.", [], "s2s commands --json")
def commands(a):
    cs = [describe(c) for c in COMMANDS.values()]
    text = []
    for g in ("read", "look", "change", "history"):
        text.append(g.upper())
        text += [f"  {c['name']:13} {c['summary']}" for c in cs if c["group"] == g]
    return dict(commands=cs, text="\n".join(text + ["", "s2s <command> --help for arguments. Add --json to any command."]))


@command("list", "The show from above: every scene in order, with its length and problems.",
         [], "s2s list --show shows/demo")
def list_(a):
    root = address.show_root(a.show)
    _, problems = ledger.build(root)
    rows, carry = [], {}
    for p in scene_paths(root):
        key = scene_key(p, root)
        mine = [x for x in problems if x["scene"] in (key, p.stem)]
        row = dict(scene=key, errors=sum(x["level"] == "error" for x in mine), warnings=sum(x["level"] == "warn" for x in mine))
        try:
            sc = Scene(p, carry=carry)
            carry = sc.carry_out
            row.update(title=sc.title, seconds=round(sc.dur, 1), turns=len(sc.turns), entities=sorted(sc.ents))
        except (ScriptError, KeyError, TypeError) as e:
            row.update(title=None, broken=str(e))
        rows.append(row)
    text = [f"{r['scene']:34} {r.get('seconds', '?'):>6}s {r.get('turns', '?'):>3} turns  "
            f"{', '.join(r.get('entities', []))}" + (f"   {r['errors']} errors" if r["errors"] else "") +
            (f"   {r['warnings']} warnings" if r["warnings"] else "") for r in rows]
    return dict(show=str(root), scenes=rows, text="\n".join(text))


@command("read", "A scene's script as written, turn by turn, with each turn's address and timing.",
         [A("scene", "a scene, or scene:turn for one turn")], "s2s read thermostat:2")
def read(a):
    ref = a.scene
    root, path, tid = (*address.turn(ref, a.show)[:3],) if ":" in ref and not ref.endswith(".yaml") else (*address.scene(ref, a.show), None)
    sc, _ = built(root, path)
    doc = edit.plain(edit.load(path))
    rows = []
    for raw, t in zip(doc.get("turns") or [], sc.turns):
        if tid is None or str(t["id"]) == str(tid):
            rows.append(dict(address=address.of(root, path, t["id"]), start=round(t["start"], 3), length=round(t["length"], 3), script=raw))
    if tid is not None and not rows:
        raise Refused(f"no turn '{tid}' in {sc.key}", hint="its turns are: " + ", ".join(str(t["id"]) for t in sc.turns))
    text = []
    for r in rows:
        s = r["script"]
        head = f"{r['address']}  [{r['start']:g} +{r['length']:g} steps]"
        line = (f"  {s.get('who')}: {json.dumps(s.get('say') or s.get('sing'), ensure_ascii=False)}" if s.get("say") or s.get("sing") else "")
        rest = {k: v for k, v in s.items() if k not in ("id", "who", "say", "sing", "why")}
        text += [head + line] + ([f"    {json.dumps(rest, ensure_ascii=False)}"] if rest else []) + [f"    why: {s.get('why')}"]
    return dict(scene=sc.key, title=sc.title, steps=sc.steps, seconds=round(sc.dur, 2), offscreen=doc.get("offscreen") or [],
                turns=rows, text="\n".join(text))


def snapshot(sc, t):
    """Everyone's resolved state as a turn ends."""
    out = {}
    end = (t["start"] + t["length"]) * sc.step
    for e, info in t["info"][-1][1].items():
        obs = [o for when, o in sc.keys[e] if when <= end + 1e-9][-1]
        out[e] = dict(present=bool(obs["alpha"]), slot=obs["slot"], facing={-1: "left", 0: "out", 1: "right"}[obs["facing"]],
                      look=[obs["lx"], obs["ly"]], side=info["side"], status=info["status"], position=info["klass"],
                      weight=None if info["weight"] is None else round(info["weight"], 3), gain=round(info["gain"], 3),
                      feels=info["felt"], intensity=info["intensity"], about=info["at"],
                      tells_shown=info["level"], tone=obs["tone"])
    return out


@command("state", "What is true as a turn ends: where everyone stands, what they feel, how much of it shows.",
         [A("turn", "scene:turn")], "s2s state thermostat:2")
def state(a):
    root, path, tid, _ = address.turn(a.turn, a.show)
    sc, t = built(root, path, tid)
    snap = snapshot(sc, t)
    text = [f"{e:8} slot {s['slot']:g} facing {s['facing']:5} {s['position']:9} gain {s['gain']:<5g} " +
            (f"feels {s['feels']} {s['intensity']}" + (f" about {s['about']}" if s["about"] else "") + f", shows {s['tells_shown']} tell(s)" if s["feels"] else "calm")
            for e, s in snap.items()]
    return dict(address=address.of(root, path, t["id"]), entities=snap, text="\n".join(text))


@command("explain", "Why an entity looks the way it does as a turn ends: the feeling, the position, and the tells that follow.",
         [A("turn", "scene:turn"), A("entity", "the entity to explain")], "s2s explain thermostat:2 otis")
def explain(a):
    root, path, tid, _ = address.turn(a.turn, a.show)
    sc, t = built(root, path, tid)
    snap = snapshot(sc, t)
    if a.entity not in snap:
        raise Refused(f"'{a.entity}' is not in this scene", hint="in it: " + ", ".join(snap))
    s, ent = snap[a.entity], sc.ents[a.entity]
    ids = [str(x["id"]) for x in sc.turns]
    upto = set(ids[:ids.index(str(t["id"])) + 1]) | {"None"}
    history = [dict(turn=x["cause"], what=x["kind"], value=edit.plain(x["value"])) for x in sc.world.log
               if x["subject"] == a.entity and str(x["cause"]) in upto]
    steps = []
    carried = sc.carried.get(a.entity)
    if carried:
        steps.append(f"Came into the scene feeling {carried[0]} {carried[1]}" + (f" about {carried[2]}" if carried[2] else "") + ", carried from earlier scenes.")
    tells, shown, held = [], [], []
    if s["feels"]:
        tells = edit.plain(ent["tells"].get(s["feels"]) or [])
        shown, held = tells[:s["tells_shown"]], tells[s["tells_shown"]:]
        last = [h for h in history if h["what"] in ("feel", "offscreen.feel")]
        steps.append(f"Feels {s['feels']} at intensity {s['intensity']}" + (f", about {s['about']}" if s["about"] else "") +
                     (f" (set in turn {last[-1]['turn']})" if last and last[-1]["turn"] is not None else " (carried in)" if last or carried else "") + ".")
        if s["weight"] is None:
            steps.append("Nobody is opposed in the room, so gain is 1: what is felt is what shows.")
        else:
            steps.append(f"Is on side '{s['side']}', which holds {s['weight']:.0%} of the room's standing ({s['position']}), so gain is {s['gain']:g}.")
        steps.append(f"Intensity {s['intensity']} x gain {s['gain']:g} rounds to {s['tells_shown']} of {a.entity}'s {len(tells)} {s['feels']} tell(s).")
        steps.append("Showing: " + (json.dumps(shown, ensure_ascii=False) if shown else "nothing") + ("; held back: " + json.dumps(held, ensure_ascii=False) if held else "") + ".")
    else:
        steps.append("Feels nothing in particular, so only deliberate actions show.")
    return dict(address=address.of(root, path, t["id"]), entity=a.entity, now=s, tells=tells, shown=shown, held_back=held,
                history=history, because=steps, text="\n".join(steps))


@command("check", "Every problem in the show, or in one scene. Exit code 3 if there are errors.",
         [A("scene", "limit to one scene", nargs="?")], "s2s check thermostat")
def check(a):
    if a.scene:
        root, path = address.scene(a.scene, a.show)
        only = address.of(root, path)
    else:
        root, only = address.show_root(a.show), None
    _, problems = ledger.build(root)
    problems = [p for p in problems if only is None or p["scene"] in (only, only.rsplit("/", 1)[-1])]
    nerr = sum(p["level"] == "error" for p in problems)
    text = [f"{p['level']:5} {p['scene']}" + (f":{p['turn']}" if p.get("turn") is not None else "") + f"  {p['msg']}" for p in problems]
    return dict(ok=nerr == 0, errors=nerr, warnings=len(problems) - nerr, problems=problems,
                text="\n".join(text or ["no problems"]), exit=FAILED if nerr else 0)


@command("ledger", "What the audience has had the chance to learn about each entity, scene by scene.", [], "s2s ledger")
def ledger_(a):
    root = address.show_root(a.show)
    table, _ = ledger.build(root)
    text = []
    for e, row in table.items():
        for emo, c in row.items():
            c.pop("sig", None)
            mark = "learned" if c["learned"] else f"{c['seen']}/{c['need']}"
            text.append(f"{e:8} {emo:9} {mark:8} seen as: {', '.join(c['positions']) or '-'}" + (f", felt but hidden in {c['hidden']}" if c["hidden"] else ""))
    return dict(ledger=table, text="\n".join(text))


@command("parity", "Has a scene's score, picture or sound changed since its reference was recorded?",
         [A("action", "record a new reference, or check against it", choices=["record", "check"]), A("scene", "the scene")],
         "s2s parity check the-reveal")
def parity_(a):
    root, path = address.scene(a.scene, a.show)
    now, ref = parity.digests(path), parity.ref_path(path)
    if a.action == "record":
        ref.parent.mkdir(exist_ok=True)
        ref.write_text(json.dumps(now, indent=2) + "\n")
        return dict(recorded=now, text=f"recorded {now['scene']}")
    if not ref.exists():
        raise Refused(f"no reference recorded for {now['scene']}", hint=f"s2s parity record {now['scene']}")
    was = json.loads(ref.read_text())
    diff = {k: dict(was=was.get(k), now=now[k]) for k in now if was.get(k) != now[k]}
    return dict(ok=not diff, scene=now["scene"], changed=diff, exit=FAILED if diff else 0,
                text=f"{now['scene']}: " + ("identical" if not diff else "changed: " + ", ".join(diff)))
