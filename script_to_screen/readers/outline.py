"""An episode's outline: its beats in order, each saying what happens, what it is for, and what it uses. It is written before
any scene is, checked against the show's bible, and later the film is checked against it.

    # outlines/the-vote.yaml
    beats:
      - id: arrow
        what: A lit match is shot through Signet's flag and goes off.
        for: The rupture. Everything after is aftermath.
        motions: [shot, through, lit, swell, burst]
        part: the-council          # once it is written: which part of the episode plays it
        from: 9                    # and from which turn (to the next beat's `from`)
        bars: 8

A beat needs only `what` and `for`. Everything else is optional and is checked only once it is there.

**Facets.** What a beat can list is not fixed: each kind of thing is a *facet* (FACETS, below). A facet says which values are
valid, how to read what the film actually shows of it, and how a value is shown. Motions are the first; adding another (weather,
a kind of place) is one more entry, and the checks, the strip and the season grid take it up without being changed.
"""
import difflib
import html
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional

import yaml

from ..performance import Scene
from ..script import load_yaml, series
from ..vocabulary.motions import MOTIONS
from . import motions as motion_reader

KEYS = ("id", "what", "for", "where", "part", "from", "bars", "new")           # a beat's own keys; a facet adds its own


def _kept(root):
    f = Path(root) / "bible.yaml"
    return {str(k["id"]): k for k in ((load_yaml(f) or {}).get("kept") or [] if f.exists() else []) if k.get("id")}


def _land(root):
    f = Path(root) / "land.yaml"
    return ((load_yaml(f) or {}).get("places") or {}) if f.exists() else {}


def _house_of(root, entity):
    return (load_yaml(Path(root) / "entities" / f"{entity}.yaml") or {}).get("house")


def _motions_shown(root, eid):
    return [(u["part"], u["turn"], u["motion"]) for u in motion_reader.seen(root) if u["episode"] == eid]


def _houses_shown(root, eid):
    out = []
    for sg in series(root).episode(eid)["segments"]:
        if sg["kind"] == "scene":
            for n, raw in enumerate(load_yaml(sg["path"]).get("turns") or []):          # whoever a turn brings on, and so their house
                out += [(sg["id"], raw.get("id", n + 1), _house_of(root, e)) for e in raw.get("enter") or {} if _house_of(root, e)]
    return out


@dataclass(frozen=True)
class Facet:
    key: str                                             # the key on a beat
    name: str                                            # what it is called, in a sentence
    known: Callable                                      # root -> {value: what it is}; the values a beat may list
    shown: Optional[Callable] = None                     # (root, episode) -> [(part, turn, value)]: what the film shows; None if it cannot be read
    lasting: bool = False                                # once shown, does it stay (a house on screen), or is it a moment (a motion)?
    mark: Callable = lambda root, value: ""              # a class for its chip: how it should stand out


FACETS = (
    Facet("motions", "motion", lambda root: {m.name: m.sees for m in MOTIONS.values()}, _motions_shown,
          mark=lambda root, v: motion_reader.tiers(root).get(v, ("unsorted", None))[0] if motion_reader.tiers(root) else ""),
    Facet("reveals", "kept secret", lambda root: {k: x["what"] for k, x in _kept(root).items()}, mark=lambda root, v: "reveal"),
    Facet("houses", "house", lambda root: {k: f"House {k.capitalize()}" for k in _land(root)}, _houses_shown, lasting=True, mark=lambda root, v: "house"),
)


def path(root, eid):
    return Path(root) / "outlines" / f"{eid}.yaml"


def load(root, eid):
    """An episode's beats, or None if it has no outline."""
    f = path(root, eid)
    return list((load_yaml(f) or {}).get("beats") or []) if f.exists() else None


def episodes(root):
    """Every episode that has an outline, in the series' order, then any outlined but not yet in the series."""
    d = Path(root) / "outlines"
    have = {f.stem for f in d.glob("*.yaml")} if d.exists() else set()
    inseries = [ep["id"] for se in series(root).seasons for ep in se["episodes"]]
    return [e for e in inseries if e in have] + sorted(have - set(inseries))


def _span(root, eid, beats):
    """For each beat that says which part plays it: the turns it covers. {beat id: (part, [turn ids])}"""
    try:
        segs = {sg["id"]: sg for sg in series(root).episode(eid)["segments"]}
    except Exception:
        return {}
    out, order = {}, {}
    for b in beats:
        sg = segs.get(str(b.get("part")))
        if not sg or sg["kind"] != "scene":
            continue
        if sg["id"] not in order:
            order[sg["id"]] = [t["id"] for t in Scene(sg["path"]).score.turns]
        ids = order[sg["id"]]
        start = ids.index(b["from"]) if b.get("from") in ids else 0
        later = [ids.index(o["from"]) for o in beats if str(o.get("part")) == sg["id"] and o.get("from") in ids and ids.index(o["from"]) > start]
        out[str(b["id"])] = (sg["id"], ids[start:min(later)] if later else ids[start:])
    return out


def film(root, eid, beats):
    """What the film shows of each facet within each beat: {beat id: {facet key: [values]}}. Only for beats that have a part."""
    spans, out = _span(root, eid, beats), {}
    for f in FACETS:
        if not f.shown:
            continue
        seen = f.shown(root, eid)
        for bid, (part, turns) in spans.items():
            order = [t["id"] for t in Scene(next(sg["path"] for sg in series(root).episode(eid)["segments"] if sg["id"] == part)).score.turns]
            upto = order.index(turns[-1]) if turns else -1
            here = [v for p, t, v in seen if p == part and (t in turns or (f.lasting and t in order and order.index(t) <= upto))]
            out.setdefault(bid, {})[f.key] = list(dict.fromkeys(here))
    return out


def problems(root):
    """Everything an outline gets wrong, before or after its scenes exist: [{level, scene, turn, msg}]."""
    out = []
    for eid in episodes(root):
        beats, where = load(root, eid), f"(outline {eid})"
        say = lambda msg, beat=None: out.append(dict(level="warning", scene=where, turn=beat, msg=msg))
        allowed = KEYS + tuple(f.key for f in FACETS)
        ids = [str(b.get("id")) for b in beats]
        try:
            segs = {sg["id"]: sg for sg in series(root).episode(eid)["segments"]}
        except Exception:
            segs = None
            say("this episode is not in series.yaml yet; nothing can be checked against a film")
        used = {}
        for b in beats:
            bid = b.get("id")
            if bid is None:
                say("a beat has no `id:`")
                continue
            if isinstance(bid, bool):
                say(f"a beat's id reads as {'yes' if bid else 'no'}/{bid}: YAML takes a bare yes, no, on or off as true or false. Put it in quotes, or name it otherwise")
            if ids.count(str(bid)) > 1:
                say("two beats share this id", bid)
            for k in b:
                if k not in allowed:
                    near = difflib.get_close_matches(str(k), allowed, 1)
                    say(f"`{k}:` is not something a beat can say" + (f"; did you mean `{near[0]}:`?" if near else f". A beat can say: {', '.join(allowed)}"), bid)
            for need in ("what", "for"):
                if not str(b.get(need) or "").strip():
                    say(f"says no `{need}:`" + (" (what it is there to do for the viewer)" if need == "for" else ""), bid)
            for f in FACETS:
                known = f.known(root)
                for v in b.get(f.key) or []:
                    if str(v) not in known:
                        near = difflib.get_close_matches(str(v), list(known), 1)
                        say(f"lists the {f.name} '{v}', which does not exist" + (f"; did you mean '{near[0]}'?" if near else "") +
                            (" If it is a movement the tool cannot do yet, list it under `new:` with what the viewer would see" if f.key == "motions" else ""), bid)
                    used.setdefault((f.key, str(v)), []).append(bid)
            for item in b.get("new") or []:
                name, sees = (next(iter(item.items())) if isinstance(item, dict) else (item, ""))
                say(f"needs a new type of motion, '{name}'" + (f" ({sees})" if sees else "") + ": it has to be built, and named in the tool, before this beat can be filmed", bid)
            if segs is not None and b.get("part") is not None and str(b["part"]) not in segs:
                near = difflib.get_close_matches(str(b["part"]), list(segs), 1)
                say(f"is played by the part '{b['part']}', which this episode does not have" + (f"; did you mean '{near[0]}'?" if near else ""), bid)
        tier = motion_reader.tiers(root)
        for (key, v), where_used in used.items():                    # a reserved motion planned more often than it is kept to; one not yet sorted
            if key == "motions" and v in MOTIONS and tier:
                kind, most = tier.get(v, (None, None))
                if kind is None:
                    say(f"plans the motion '{v}', which has no tier yet: is it familiar, or reserved?", where_used[0])
                elif kind == "reserved" and len(where_used) > most:
                    say(f"is use {most + 1} of the reserved motion '{v}' in this episode (it is kept to {most}; also in: {', '.join(map(str, where_used[:most]))})", where_used[most])
        seen_reveals = [str(v) for b in beats for v in b.get("reveals") or []]
        for v in {v for v in seen_reveals if seen_reveals.count(v) > 1}:
            say(f"the kept secret '{v}' is revealed in more than one beat")
        if segs is None:
            continue
        shown, spans = film(root, eid, beats), _span(root, eid, beats)
        for b in beats:                                              # the film against the outline, for beats that have been written
            bid = str(b.get("id"))
            if bid not in spans:
                continue
            for f in FACETS:
                if not f.shown or f.key not in b:
                    continue
                planned, got = [str(v) for v in b.get(f.key) or []], shown.get(bid, {}).get(f.key, [])
                for v in got:
                    if v not in planned:
                        say(f"the film has the {f.name} '{v}' here ({spans[bid][0]}), which the outline did not plan", b["id"])
                for v in planned:
                    if v not in got and v in f.known(root):
                        say(f"plans the {f.name} '{v}', which the film does not have here ({spans[bid][0]}) yet", b["id"])
        covered = {p for p, _ in spans.values()} | {str(b.get("part")) for b in beats}
        for sid, sg in segs.items():
            if sg["kind"] == "scene" and sid not in covered:
                say(f"the scene '{sid}' is in the film but no beat is played by it")
        bar = _bar(root)
        for sid in {p for p, _ in spans.values()}:                   # where every beat of a scene says its bars, they should add up to the scene
            mine = [b for b in beats if str(b.get("part")) == sid]
            if bar and all(b.get("bars") is not None for b in mine):
                sc = Scene(segs[sid]["path"]).score
                real = sc.steps * sc.step / bar
                if abs(sum(float(b["bars"]) for b in mine) - real) > 1.0:
                    say(f"the beats played by '{sid}' add up to {sum(float(b['bars']) for b in mine):g} bars; the scene runs {real:g}")
    return out


def _bar(root):
    show = load_yaml(Path(root) / "show.yaml")
    return 60.0 / float(show["tempo"]) * int(show.get("beats_per_bar") or 0)


def draft(root, eid):
    """A first outline written from a film that exists: a beat per scene, split where a reserved motion first happens. -> yaml text.
    It is a start to correct, not a finished outline: `what` is taken from the turns' reasons, and `for` is left to the writer."""
    bar, tier, beats = _bar(root), motion_reader.tiers(root), []
    seen_m, seen_h = _motions_shown(root, eid), _houses_shown(root, eid)
    for sg in series(root).episode(eid)["segments"]:
        if sg["kind"] != "scene":
            beats.append(dict(id=sg["id"], what={"title": "The title sequence.", "travel": "A journey over the land.", "credits": "The credits."}.get(sg["card"], "A card."), **{"for": ""}, part=sg["id"]))
            continue
        sc = Scene(sg["path"]).score
        ids = [t["id"] for t in sc.turns]
        cut = next((ids.index(t) for p, t, m in seen_m if p == sg["id"] and tier.get(m, ("",))[0] == "reserved"), None)
        for n, (a, b) in enumerate([(0, cut), (cut, len(ids))] if cut else [(0, len(ids))]):
            turns = sc.turns[a:b]
            long = (turns[-1]["start"] + turns[-1]["length"] - turns[0]["start"]) * sc.step / bar if bar else None
            beat = dict(id=sg["id"] + ("-turn" if n else ""), where=f"{sg['place'] if sg.get('place') else sc.place}" + (f", day {sg['day']}" if sg.get("day") is not None else ""),
                        what=" ".join(t["why"] for t in turns[:2] if t["why"]), **{"for": ""},
                        motions=list(dict.fromkeys(m for p, t, m in seen_m if p == sg["id"] and t in ids[a:b])),
                        houses=list(dict.fromkeys(h for p, t, h in seen_h if p == sg["id"] and t in ids and ids.index(t) < b)), part=sg["id"])
            if n:
                beat["from"] = ids[a]
            if long is not None:
                beat["bars"] = round(long)
            beats.append(beat)
    return yaml.safe_dump(dict(beats=beats), sort_keys=False, allow_unicode=True, width=120)


# ---- shown ----------------------------------------------------------------------------------------------------
def rows(root, eid):
    """Each beat with its state: [{beat, state ('filmed' | 'to write'), film: {facet: [values]}, problems: n}]."""
    beats = load(root, eid) or []
    try:
        shown, spans = film(root, eid, beats), _span(root, eid, beats)
        cards = {sg["id"] for sg in series(root).episode(eid)["segments"] if sg["kind"] != "scene"}
    except Exception:
        shown, spans, cards = {}, {}, set()
    found = [p for p in problems(root) if p["scene"] == f"(outline {eid})"]
    return [dict(beat=b, state="filmed" if str(b.get("id")) in spans or str(b.get("part")) in cards else "to write", film=shown.get(str(b.get("id")), {}),
                 problems=sum(str(p["turn"]) == str(b.get("id")) for p in found)) for b in beats]


def markdown(root, eid):
    out = ["| Beat | What happens | What it is for | " + " | ".join(f.key.capitalize() for f in FACETS) + " | Bars | State |", "| --- | --- | --- | " + " | ".join("---" for _ in FACETS) + " | --- | --- |"]
    for r in rows(root, eid):
        b = r["beat"]
        new = [str(next(iter(i)) if isinstance(i, dict) else i) + " (new)" for i in b.get("new") or []]
        cells = [", ".join([f"`{v}`" for v in b.get(f.key) or []] + (new if f.key == "motions" else [])) for f in FACETS]
        out.append("| " + " | ".join(str(x).replace("|", "/") for x in (b.get("id"), b.get("what", ""), b.get("for", ""), *cells, b.get("bars", ""),
                                                                      r["state"] + (f", {r['problems']} to look at" if r["problems"] else ""))) + " |")
    return "\n".join(out)


def strip(root, eid):
    """The outline as a strip of cards, each as wide as its bars, with what it uses as chips. One line of HTML."""
    esc = lambda s: html.escape(str(s), quote=True)
    land = _land(root)
    cards = []
    for r in rows(root, eid):
        b, chips = r["beat"], []
        for f in FACETS:
            known = f.known(root)
            for v in b.get(f.key) or []:
                kind = f.mark(root, str(v)) if str(v) in known else "missing"
                style = f' style="--c:{land[v]["color"]}"' if f.key == "houses" and (land.get(v) or {}).get("color") else ""
                chips.append(f'<span class="chip {esc(kind)}"{style} title="{esc(f.name)}: {esc(known.get(str(v), "does not exist"))}{" (" + esc(kind) + ")" if kind in ("reserved", "familiar", "unsorted") else ""}">{esc(v)}</span>')
        for item in b.get("new") or []:
            name, sees = (next(iter(item.items())) if isinstance(item, dict) else (item, ""))
            chips.append(f'<span class="chip new" title="a new type of motion, to be built: {esc(sees)}">{esc(name)}</span>')
        cards.append(f'<div class="beat {"filmed" if r["state"] == "filmed" else "towrite"}" style="flex-grow:{max(float(b.get("bars") or 6), 3):g}" '
                     f'title="{esc(b.get("what", ""))}&#10;&#10;For: {esc(b.get("for", ""))}&#10;{esc(r["state"])}{", " + str(r["problems"]) + " to look at" if r["problems"] else ""}">'
                     f'<b>{esc(b.get("id"))}</b><i>{esc(b.get("bars", ""))}</i><p>{esc(b.get("what", ""))}</p>{"".join(chips)}</div>')
    return '<div class="outline">' + "".join(cards) + "</div>"


def grid(root):
    """When the viewer meets each motion: one row per motion that is used or planned, one column per episode. A number is how
    often the film uses it; a number in brackets is how often an outline plans it, where there is no film of it yet."""
    eps = [ep["id"] for se in series(root).seasons for ep in se["episodes"]]
    eps += [e for e in episodes(root) if e not in eps]
    used = motion_reader.seen(root)
    tier = motion_reader.tiers(root)
    lines, met = [], set()
    for m in MOTIONS:
        cells, any_ = [], False
        for e in eps:
            n = sum(u["motion"] == m and u["episode"] == e for u in used)
            planned = sum(m in (b.get("motions") or []) for b in (load(root, e) or []))
            cell = str(n) if n else f"({planned})" if planned else ""
            if cell and m not in met:
                cell, _ = f"**{cell}** first", met.add(m)
            any_ = any_ or bool(cell)
            cells.append(cell)
        if any_:
            lines.append((tier.get(m, ("",))[0] != "reserved", f"| `{m}` | {tier.get(m, ('no tier yet',))[0]} | " + " | ".join(cells) + " |"))
    return "\n".join(["| Motion | Tier | " + " | ".join(eps) + " |", "| --- | --- | " + " | ".join("---" for _ in eps) + " |"] + [l for _, l in sorted(lines, key=lambda x: x[0])])
