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
from pathlib import Path

import skia

from ..performance import appraisal
from ..performance.scene import Scene
from ..presentation.draw import INK, draw_frame, fill, font
from ..presentation.stage import Stage
from ..script import ScriptError, Show, imagining, load_yaml, series, tuning

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
                 feelings={e: list(st[e]["felt"]) for e in present if st[e]["felt"]}, status={e: st[e]["status"] for e in present},
                 place=script.get("place"), slots={e: st[e]["slot"] for e in present}, scene=str(path),
                 stance={e: {k: st[e][k] for k in ("orient", "attention", "posture")} for e in present})
    if turn.get("who") and turn.get("say"):
        setup["line"] = dict(who=turn["who"], say=turn["say"])
    return setup, turn["event"]

def _sheets(root, everyone, change):
    """Each entity's sheet with a variation's dials, needs and bonds laid over it."""
    out = {}
    for e in everyone:
        sheet = copy.deepcopy(tuning.overlay(load_yaml(root / "entities" / f"{e}.yaml")))
        profile = sheet.setdefault("profile", {})
        profile.setdefault("temperament", {}).update((change.get("dials") or {}).get(e) or {})
        profile.setdefault("needs", {}).update((change.get("needs") or {}).get(e) or {})
        sheet["bonds"] = {**(sheet.get("bonds") or {}), **((change.get("bonds") or {}).get(e) or {})}
        out[e] = sheet
    return out


def staged(root, setup, event, change=None):
    """The same case as a moment on the stage: a two-turn scene (everyone as the setup has them; then the event),
    worked out by the engine itself. -> (stage, frame) for the moment the event has landed."""
    change = change or {}
    was = list(setup.get("present") or [])
    present = list(change.get("present") or was)
    sides = {e: s for e, s in {**(setup.get("sides") or {}), **(change.get("sides") or {})}.items() if e in present and s}
    facts = copy.deepcopy(setup.get("facts") or {})
    for k, v in (change.get("facts") or {}).items():
        facts[k] = {**facts.get(k, {}), **v}
    feelings = {**(setup.get("feelings") or {}), **(change.get("feelings") or {})}
    gone = lambda v: isinstance(v, str) and v in was and v not in present        # facing someone this variation has taken out of the room
    enter = {}
    for e in present:                                                      # where the setup has them, or wherever their regards put them
        spec = {k: v for k, v in ((setup.get("stance") or {}).get(e) or {}).items() if not gone(v)}
        if e in (setup.get("slots") or {}):
            spec["slot"] = setup["slots"][e]
        enter[e] = spec
    felt = {e: ({f[0]: f[1], **({"at": f[2]} if len(f) > 2 and f[2] in present else {})} if isinstance(f, (list, tuple)) else f)
            for e, f in feelings.items() if f and e in present}
    first = dict(id=1, enter=enter, why="The setup.")
    if sides:
        first["side"] = sides
    if felt:
        first["feel"] = felt
    if setup.get("status"):
        first["status"] = {e: v for e, v in setup["status"].items() if e in present}
    line = setup.get("line") or {}
    second = dict(id=2, event=change.get("event") or event, why="The event.", hold=6)
    if line.get("who") in present:
        second.update(who=line["who"], say=line["say"])
    script = dict(scene="what if", turns=[first, second], facts=facts)
    if setup.get("place"):
        script["place"] = setup["place"]
    host = Path(setup["scene"]) if setup.get("scene") else series(root).segments[-1]["path"]     # a what-if borrows a scene's place in the series
    events = second["event"] if isinstance(second["event"], list) else [second["event"]]
    everyone = set(present) | {x for ev in events for x in appraisal._targets(ev) + [ev.get("by")] if x}
    with imagining(root, _sheets(root, everyone, change)):
        stage = Stage.of(Scene(host, script=script, carry={}))
    stage.look.style = dict(stage.look.style, camera="still")              # the whole room, so the columns can be compared
    return stage, max(0, stage.total - 4)


def sheet(root, setup, event, cases, variations, png, cols=4, scale=0.5):
    """Every case as a still, side by side, each captioned with what everyone feels and is inclined to do."""
    stages = [staged(root, setup, event, v) for v in [None] + list(variations)]
    W, H = stages[0][0].W, stages[0][0].H
    w, h, strip = int(W * scale), int(H * scale), 34 + 22 * max(len(c["reactions"]) for c in cases)
    cols = min(cols, len(cases))
    rows = (len(cases) + cols - 1) // cols
    surface = skia.Surface(w * cols, (h + strip) * rows)
    c = surface.getCanvas()
    c.clear(skia.ColorWHITE)
    for k, ((stage, F), case_) in enumerate(zip(stages, cases)):
        x, y = (k % cols) * w, (k // cols) * (h + strip)
        c.save()
        c.translate(x, y)
        c.clipRect(skia.Rect.MakeWH(w - 3, h))
        c.scale(scale, scale)
        draw_frame(c, stage, F)
        c.restore()
        c.drawString(case_["name"], x + 10, y + h + 22, font(15), fill(INK))
        for n, (e, r) in enumerate(case_["reactions"].items()):
            said = "nothing" if not r["feels"] else f"{r['feels']} {r['strength']}, inclined to {r['inclined']}"
            c.drawString(f"{e}: {said}", x + 10, y + h + 44 + 22 * n, font(13), fill(INK, 170))
    Path(png).parent.mkdir(parents=True, exist_ok=True)
    surface.makeImageSnapshot().save(str(png), skia.kPNG)
    return Path(png)


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
