"""What if: one setup, one event, and how everyone would react, in as many variations as asked.

This is for mapping a situation out without writing it. A setup is who is in the room, whose
side they are on, what they already feel, and the facts. An event is dropped into it. Each
variation changes something (who is there, who did it, who knows, a dial on someone's sheet)
and the same event is appraised again. Nothing is drawn and no scene is changed.

    setup:  {present: [juno, otis], sides: {}, facts: {dumpling: {doer: otis, knows: [otis, juno]}}, feelings: {}}
    event:  {kind: threat, need: esteem, size: 2, by: juno, target: otis, fact: dumpling, accuses: true}
    variations:
      - {name: Otis did not do it, facts: {dumpling: {doer: bix, knows: [bix]}}}
      - {name: Bix is in the room, present: [juno, otis, bix]}
      - {name: Otis outranks her, dials: {otis: {dominance: 2}}}
"""
import copy

from ..performance import appraisal
from ..performance.scene import Scene
from ..script import ScriptError, Show, load_yaml

CHANGES = ("present", "sides", "facts", "feelings", "dials", "needs", "bonds", "event")


def from_turn(path, tid):
    """The setup a turn's event lands in, and the event: the scene played up to that turn, with the turn's own
    entrances, sides and actions done but nothing yet said or felt."""
    script = load_yaml(path)
    turns = script.get("turns") or []
    at = next((i for i, t in enumerate(turns) if str(t.get("id", i + 1)) == str(tid)), None)
    if at is None:
        raise ScriptError(f"no turn {tid} in this scene")
    turn = turns[at]
    if not turn.get("event"):
        raise ScriptError(f"turn {tid} has no `event:`; what-if asks how people react to an event")
    before = dict(script, turns=turns[:at] + [{k: v for k, v in turn.items() if k in ("id", "enter", "exit", "side", "status", "do", "why")}])
    sc = Scene(path, script=before)
    st = sc.world.st
    present = [e for e, s in st.items() if s["present"]]
    setup = dict(present=present, sides={e: st[e]["side"] for e in present if st[e]["side"]}, facts=copy.deepcopy(sc.facts),
                 feelings={e: list(st[e]["felt"]) for e in present if st[e]["felt"]}, status={e: st[e]["status"] for e in present})
    return setup, turn["event"]


def case(root, setup, event, change=None):
    """One setup with one variation applied -> {entity: {feels, strength, about, why, power, shows, inclined, looks}}."""
    change = change or {}
    unknown = set(change) - set(CHANGES) - {"name"}
    if unknown:
        raise ScriptError(f"a variation can change {', '.join(CHANGES)}; not {', '.join(sorted(unknown))}")
    show = Show(root)
    present = list(change.get("present") or setup.get("present") or [])
    sides = {e: s for e, s in {**(setup.get("sides") or {}), **(change.get("sides") or {})}.items() if e in present and s}
    facts = copy.deepcopy(setup.get("facts") or {})
    for k, v in (change.get("facts") or {}).items():
        facts[k] = {**facts.get(k, {}), **v}
    feelings = {**(setup.get("feelings") or {}), **(change.get("feelings") or {})}
    events = change.get("event") or event
    events = events if isinstance(events, list) else [events]
    everyone = set(present) | {x for ev in events for x in appraisal._targets(ev) + [ev.get("by")] if x}
    for ev in events:
        why = appraisal.problems(ev, show.known(), facts)
        if why:
            raise ScriptError(why)
    sheets = {}
    for e in everyone:
        sheet = copy.deepcopy(load_yaml(root / "entities" / f"{e}.yaml"))
        profile = sheet.setdefault("profile", {})
        profile.setdefault("temperament", {}).update((change.get("dials") or {}).get(e) or {})
        profile.setdefault("needs", {}).update((change.get("needs") or {}).get(e) or {})
        sheet["bonds"] = {**(sheet.get("bonds") or {}), **((change.get("bonds") or {}).get(e) or {})}
        sheets[e] = sheet
    standing = {e: tuple(f) if isinstance(f, (list, tuple)) else (next(iter(f)), next(iter(f.values())), None) for e, f in feelings.items() if f}
    m = appraisal.Minds(sheets, sides, standing, facts, show.cfg.get("valence"))
    felt = appraisal.feelings(m, events, present)
    status = {e: (setup.get("status") or {}).get(e, sheets[e].get("status", 1)) for e in present}
    total, gcfg, out = sum(status[e] for e in sides) or 1, show.cfg["gain"], {}
    for e in present:
        row = dict(power=m.power(e), feels=None, strength=0, about=None, why="", shows=[], inclined=None, looks=None)
        if e in felt:
            emo = next(k for k in felt[e]["feel"] if k != "at")
            gain = 1.0
            if e in sides and len(set(sides.values())) > 1:                # the same rule the engine uses: standing on my side, as a share of the room's
                gain = max(gcfg["min"], min(gcfg["max"], gcfg["slope"] * sum(status[x] for x in sides if sides[x] == sides[e]) / total))
            tells = (sheets[e].get("tells") or {}).get(emo) or []
            word, looks = appraisal.inclined(m, e, emo)
            row.update(feels=emo, strength=felt[e]["feel"][emo], about=felt[e]["feel"].get("at"), why=felt[e]["why"],
                       shows=tells[:max(0, min(len(tells), int(felt[e]["feel"][emo] * gain + 0.5)))], inclined=word, looks=looks)
        out[e] = row
    return out


def table(root, setup, event, variations=()):
    """-> [{name, changed, reactions}] : the setup as it stands, then each variation."""
    out = [dict(name="as it stands", changed={}, reactions=case(root, setup, event))]
    for v in variations:
        out.append(dict(name=str(v.get("name") or "variation"), changed={k: x for k, x in v.items() if k != "name"}, reactions=case(root, setup, event, v)))
    return out


def describe(event):
    events = event if isinstance(event, list) else [event]
    said = []
    for ev in events:
        who = ", ".join(appraisal._targets(ev))
        said.append((f"{ev['by']} to {who}" if ev.get("by") and ev["by"] not in appraisal._targets(ev) else who) +
                    f": a {('slight', 'pointed', 'undeniable')[max(1, min(3, int(ev.get('size', 2)))) - 1]} {ev['kind']} to {ev['need']}" +
                    (f", about '{ev['fact']}'" if ev.get("fact") else "") + (" (an accusation)" if ev.get("accuses") else ""))
    return "; ".join(said)


def text(event, cases):
    """The table as text: one column per variation, then why each cell that differs from the first column differs."""
    who = list(dict.fromkeys(e for c in cases for e in c["reactions"]))
    cell = lambda r: "(not here)" if r is None else "nothing" if not r["feels"] else f"{r['feels']} {r['strength']} > {r['inclined']}"
    cols = [[c["name"]] + [cell(c["reactions"].get(e)) for e in who] for c in cases]
    widths = [max(len(x) for x in col) + 3 for col in cols]
    left = max(len(e) for e in who + [""]) + 3
    lines = [describe(event), ""]
    for i in range(len(who) + 1):
        lines.append(("" if i == 0 else who[i - 1]).ljust(left) + "".join(col[i].ljust(w) for col, w in zip(cols, widths)).rstrip())
    base = cases[0]["reactions"]
    for c in cases:
        notes = [f"  {e}: {r['why']}; {r['looks']}" + (f" (shows {len(r['shows'])} of their {r['feels']} tells)" if r["feels"] else "")
                 for e, r in c["reactions"].items() if r["feels"] and (c is cases[0] or cell(r) != cell(base.get(e)))]
        if notes:
            lines += ["", c["name"] + ":"] + notes
    return "\n".join(lines)
