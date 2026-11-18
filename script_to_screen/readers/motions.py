"""What the film has actually used of the tool's motions (vocabulary/motions.py), and whether a motion the show keeps in
reserve is being spent too often.

`seen` reads every scene as it plays and names each movement in it. `table` joins that with the show's tiers (bible.yaml
`motions:`): familiar, the ones the viewer is meant to settle into; reserved, the ones kept for critical moments.
"""
from pathlib import Path

from ..performance import Scene
from ..script import load_yaml, series
from ..vocabulary.motions import KINDS, MOTIONS

EVENTS = {"bubble": "speak", "exit": "leave", "move": "approach", "turn": "turn", "look": "look", "posture": "lean", "beat": "tell"}
CAMERA = {"open": "hold", "shot": "cut", "push": "push"}


def seen(root):
    """Every movement in the film, in order: [{motion, episode, part, turn, who}]."""
    root, out = Path(root), []
    s = series(root)
    for se in s.seasons:
        for ep in se["episodes"]:
            for sg in ep["segments"]:
                if sg["kind"] != "scene":
                    continue
                scene = Scene(sg["path"])
                sc = scene.score
                sec = sc.step
                opened = (sc.turns[0]["start"] + sc.turns[0]["length"]) * sec           # whoever is there when the scene opens did not arrive
                turn_at = lambda t: next((x["id"] for x in reversed(sc.turns) if x["start"] * sec <= t + 1e-6), sc.turns[0]["id"])
                add = lambda motion, t, who=None: out.append(dict(motion=motion, episode=ep["id"], part=sg["id"], turn=turn_at(t), who=who))
                for t, name, who, *_ in sorted(scene.events, key=lambda e: e[0]):
                    name = str(name)
                    sheet = (load_yaml(root / "entities" / f"{who}.yaml") or {}) if who else {}
                    if name == "enter" and t >= opened - 1e-6:
                        add("shot" if sheet.get("shot") else "jump" if sheet.get("climbs") else "walk", t, who)
                        if sheet.get("alight"):
                            add("lit", t, who)
                    elif name.startswith("through:"):
                        add("through", t, who)
                    elif name == "blast":
                        add("swell", t, who)
                        add("burst", t, who)
                    elif name.startswith("feel."):
                        add("tell", t, who)
                    elif name in EVENTS:
                        add(EVENTS[name], t, who)
                for c in sc.camera:
                    add(CAMERA.get(c.get("kind"), "cut"), c["t"])
    return out


def tiers(root):
    """The show's sorting of motions: {name: (tier, how often a reserved one may be used in an episode)}."""
    f = Path(root) / "bible.yaml"
    said, out = ((load_yaml(f) or {}).get("motions") or {}) if f.exists() else {}, {}
    for name in said.get("familiar") or []:
        out[str(name)] = ("familiar", None)
    reserved = said.get("reserved") or []
    for name, most in (reserved.items() if isinstance(reserved, dict) else ((n, 1) for n in reserved)):
        out[str(name)] = ("reserved", int(most or 1))
    return out


def table(root):
    """Every motion the tool has, with the show's tier for it and what the film has used: [{name, kind, sees, ask, tier, most, times, first, by_episode}]."""
    used, tier = seen(root), tiers(root)
    rows = []
    for m in MOTIONS.values():
        mine = [u for u in used if u["motion"] == m.name]
        per = {}
        for u in mine:
            per[u["episode"]] = per.get(u["episode"], 0) + 1
        rows.append(dict(name=m.name, kind=m.kind, sees=m.sees, ask=m.ask, tier=tier.get(m.name, (None, None))[0], most=tier.get(m.name, (None, None))[1],
                         times=len(mine), first=f"{mine[0]['part']}:{mine[0]['turn']}" if mine else None, by_episode=per))
    return rows


def problems(root):
    """Where the film spends a reserved motion too often, uses one that has no tier, or names one the tool does not have:
    [(part, turn, message)]."""
    tier, out = tiers(root), []
    if not tier:                                                     # a show that has not sorted its motions is not held to a sorting
        return out
    used = seen(root)
    for name in tier:
        if name not in MOTIONS:
            out.append(("(bible)", None, f"bible.yaml sorts a motion called '{name}', which the tool does not have. It has: {', '.join(MOTIONS)}"))
    count = {}
    for u in used:
        kind, most = tier.get(u["motion"], (None, None))
        n = count[(u["episode"], u["motion"])] = count.get((u["episode"], u["motion"]), 0) + 1
        if kind is None and n == 1:
            out.append((u["part"], u["turn"], f"the motion '{u['motion']}' ({MOTIONS[u['motion']].sees.rstrip('.').lower()}) has no tier yet: is it familiar, or reserved?"))
        elif kind == "reserved" and n > most:
            out.append((u["part"], u["turn"], f"'{u['motion']}' is a reserved motion and this is use {n} of it in this episode (it is kept to {most}): the viewer has seen it, and it will not land the same"))
    return out


def markdown(root):
    rows = table(root)
    cell = lambda v: str(v if v is not None else "").replace("|", "/")
    line = lambda r, cols: "| " + " | ".join(cell(c) for c in cols) + " |"
    used = [r for r in rows if r["times"]]
    spare = [r for r in rows if not r["times"]]
    out = ["| Motion | Tier | What the viewer sees | Used | First seen |", "| --- | --- | --- | --- | --- |"]
    for r in sorted(used, key=lambda r: (r["tier"] != "reserved", r["tier"] is None, -r["times"])):
        tier = "**reserved**" + (f" (kept to {r['most']} an episode)" if r["most"] else "") if r["tier"] == "reserved" else r["tier"] or "*no tier yet*"
        out.append(line(r, (f"`{r['name']}`", tier, r["sees"], f"{r['times']} time{'s' if r['times'] != 1 else ''}", r["first"])))
    out += ["", "**Possible but not used yet.** The tool can already do these; no scene has asked for one. Anything on neither list is a new type and has to be built.", "",
            "| Motion | Kind | What the viewer would see | How a script asks for it |", "| --- | --- | --- | --- |"]
    out += [line(r, (f"`{r['name']}`" + (f" ({r['tier']})" if r["tier"] else ""), KINDS[r["kind"]].lower(), r["sees"], r["ask"])) for r in spare]
    return "\n".join(out)
