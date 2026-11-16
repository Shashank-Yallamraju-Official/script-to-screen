"""The story as a series of filters.

A story is decided in gates, each narrower than the last: what they go after, who they are, how
they see each other, the plan, what the viewer is not told. At each gate the rules carry the
decision's consequences as far as they reach. Everything about the story is then in one of three
states: forced (only one thing can be true), narrowed (a few things could be), or open (nothing
constrains it yet, so someone has to invent it).

    report(root) -> {gates: [{n, name, decided, forced, narrowed, open, problems}], funnel, always_open}
"""
import copy

from ..performance import appraisal, crew, standing, tendencies
from ..script import ScriptError, load_yaml

GATES = ("the lock", "the crew", "the ties", "the plan", "the twist")
THEME = "the theme"
ASKS = {  # what each gate will answer once it is decided: these are open until then
    "the theme": ["what it is about", "what each excuse has to meet", "whether anyone is to be scored against", "what the ending has to do"],
    "the lock": ["what they go after", "what stands in the way", "what the crew is defined against", "which crafts are needed", "where the inside works"],
    "the crew": ["who is in it", "why each would do it", "who says yes at once and who needs persuading", "which obstacles have nobody for them", "who cannot be lost"],
    "the ties": ["how each sees each", "who leads", "who sides with whom", "who holds it together", "who gets blamed"],
    "the plan": ["the order of the job", "who does what", "where it goes wrong", "what each does when it does", "who takes charge"],
    "the twist": ["what the viewer is not told", "who is in on it", "what it does to the crew afterwards", "who wavers at the split", "how it can end"],
}
ALWAYS_OPEN = ["every line of dialogue", "the places: rooms, and what is in them", "the snag: which obstacle changes before the job", "names, and the title"]
BEATS = ("the score", "the crew", "the plan", "the snag", "the job", "the twist", "the split")


def _sheets(root, names, ties):
    out = {}
    for e in names:
        f = root / "entities" / f"{e}.yaml"
        if not f.exists():
            raise ScriptError(f"story.yaml names '{e}', but there is no entities/{e}.yaml")
        sheet = copy.deepcopy(load_yaml(f))
        sheet["bonds"] = {**(sheet.get("bonds") or {}), **((ties or {}).get(e) or {})}
        out[e] = sheet
    return out


def _craft(sheet):
    return list((sheet.get("profile") or {}).get("craft") or [])


def _theme(root, story, sheets, members):
    g = dict(n=0, name=THEME, decided=None, forced=[], narrowed=[], open=[], problems=[])
    file = root / "library" / "themes.yaml"
    themes = load_yaml(file) if file.exists() else {}
    if not story.get("theme"):
        if themes:
            g["narrowed"].append("what it is about: one of " + ", ".join(themes))
        return g, None
    if story["theme"] not in themes:
        raise ScriptError(f"story.yaml: no theme '{story['theme']}' in library/themes.yaml; there are: " + ", ".join(themes))
    th = themes[story["theme"]]
    g["decided"] = th["says"]
    g["forced"].append(f"the turn: {th['turn']}")
    if th.get("nobody_is_bad"):
        g["forced"].append("nobody is good or bad: the audience is with everyone, so harm to anyone is scored as bad news, and nobody's gain is")
        for e in ([story["mark"]] if story.get("mark") else []) + ([story["world"]] if story.get("world") else []) + list(members):
            if sheets and e in sheets and not standing.pressures(sheets[e]):
                g["problems"].append(f"nothing presses on {e}: they are a wall, not a person. Everyone here is trying to survive something")
        mark = story.get("mark")
        if sheets and mark in sheets and standing.pressures(sheets[mark]):
            need, p, why = standing.pressures(sheets[mark])[0]
            excuse = (sheets[mark].get("profile") or {}).get("tells_self")
            g["forced"].append(f"{mark}, the mark, is surviving too: {need} is strong in them and {why}" +
                               (f". Tells themselves: \"{standing.EXCUSES[excuse]}\"" if excuse in standing.EXCUSES else ""))
    for m in members if sheets else []:
        excuse = (sheets[m].get("profile") or {}).get("tells_self")
        if excuse in standing.BREAKS:
            g["forced"].append(f"{m}'s excuse (\"{standing.EXCUSES[excuse]}\") has to stop working: {standing.BREAKS[excuse]}")
        else:
            g["problems"].append(f"{m} has no excuse to lose: the theme needs each of them to be telling themselves something")
    if sheets and members:
        g["open"].append("how each excuse breaks: the event, and which scene it is in")
    if not story.get("world"):
        g["problems"].append("nobody stands for the world they are taking from. Without someone they come to care about, the harm lands on no one and nothing is felt")
    g["narrowed"].append("what the ending does: " + "; or ".join(th["endings"]))
    return g, th


def _lock(root, story):
    locks = load_yaml(root / "library" / "locks.yaml")
    g = dict(n=1, name=GATES[0], decided=None, forced=[], narrowed=[], open=[], problems=[])
    if not story.get("lock"):
        g["narrowed"].append("what they go after: one of " + ", ".join(locks))
        return g, None
    if story["lock"] not in locks:
        raise ScriptError(f"story.yaml: no lock '{story['lock']}' in library/locks.yaml; there are: " + ", ".join(locks))
    lock = locks[story["lock"]]
    kinds = list(dict.fromkeys(p["kind"] for p in lock["pins"]))
    g["decided"] = f"a {story['lock']}"
    g["forced"] += [f"{len(lock['pins'])} things stand in the way: " + "; ".join(f"{p['what']} ({p['kind']})" for p in lock["pins"]),
                    f"so the crew needs {len(kinds)} crafts between them: " + ", ".join(kinds),
                    f"everyone in the crew is defined against {lock['stands_for']}",
                    f"the inside is {lock['inside']}; the mark is {lock['mark']}",
                    f"what they take is {lock['takes']}"]
    return g, lock


def _crew(root, story, lock):
    g = dict(n=2, name=GATES[1], decided=None, forced=[], narrowed=[], open=[], problems=[])
    if not story.get("crew"):
        return g, None, None
    members = list(story["crew"])
    sheets = _sheets(root, members + [story[k] for k in ("mark", "world") if story.get(k)], story.get("ties"))
    g["decided"] = ", ".join(members)
    planners = [m for m in members if not _craft(sheets[m])]
    planner = planners[0] if planners else None
    g["forced"].append(f"{planner} is the planner: the only one with no craft, so the one who sees the whole lock" if len(planners) == 1 else
                       "nobody is the planner: everyone has a craft" if not planners else "more than one has no craft: " + ", ".join(planners))
    for m in members:
        verdict, score, need, why = standing.answer(sheets[m])
        excuse = (sheets[m].get("profile") or {}).get("tells_self")
        said = {"yes": "says yes at once", "persuade": "needs persuading", "no": "walks away"}[verdict]
        g["forced"].append(f"{m} ({standing.facet(sheets[m])}) {said}: {why}" + (f". Tells themselves: \"{standing.EXCUSES[excuse]}\"" if excuse in standing.EXCUSES else ""))
        if verdict == "persuade":
            g["narrowed"].append(f"how {m} is talked round: an appeal to their {need}, or to their excuse" + (f" (\"{standing.EXCUSES[excuse]}\")" if excuse in standing.EXCUSES else ""))
        if verdict == "no":
            g["problems"].append(f"{m} would not do it: nothing presses on them hard enough. Change them, or leave them out")
    if lock:
        for kind in dict.fromkeys(p["kind"] for p in lock["pins"]):
            can = [m for m in members if kind in _craft(sheets[m])]
            if not can:
                g["problems"].append(f"nobody can get past {kind}: the crew has a hole")
            elif len(can) == 1:
                g["forced"].append(f"only {can[0]} can get past {kind}: lose them and the job is off")
            else:
                g["narrowed"].append(f"{kind} can be done by " + " or ".join(can))
    return g, sheets, planner


def _ties(story, sheets, members):
    g = dict(n=3, name=GATES[2], decided=None, forced=[], narrowed=[], open=[], problems=[])
    if not story.get("ties"):
        return g, None
    said = sum(len([k for k in v if k in members]) for a_, v in story["ties"].items() if a_ in members)
    g["decided"] = f"{said} of {len(members) * (len(members) - 1)} ways one member sees another"
    read = crew.readings(sheets, members)
    notable = []
    for a in members:
        for b in members:
            if a != b:
                t, r = crew.tie(sheets, a, b)
                if crew.attitude(t, r) != "relies on":
                    notable.append(f"{a} {crew.attitude(t, r)} {b}")
    g["forced"].append("where it is not simple reliance: " + "; ".join(notable))
    g["forced"].append("the pecking order is " + ", ".join(read["order"]) + f": {read['order'][0]} speaks first and is deferred to")
    g["forced"].append("one crew, with no factions yet" if len(read["factions"]) == 1 else "factions: " + " | ".join(", ".join(f) for f in read["factions"]))
    if read["hinge"]:
        g["forced"].append(f"{read['hinge']} holds it together: take them out and it comes apart")
    g["forced"].append(f"{read['weak_link']} is the weak link, trusted and rated least by the rest: when something fails and nobody knows why, the blame goes there")
    g["forced"].append(f"cohesion is {read['cohesion']:+.2f} on a scale of -2 to +2: " + ("tight" if read["cohesion"] >= 1 else "holding, not tight" if read["cohesion"] >= 0.4 else "loose"))
    for m in members:                                            # what the group already gives each of them, and what it cannot
        before, after = standing.pressures(sheets[m]), standing.pressures(sheets[m], read["incoming"][m])
        met = [n for n, _, _ in before if n not in [x[0] for x in after]]
        if met:
            g["forced"].append(f"the crew already gives {m} their {' and '.join(met)}" + (": nothing they came for is still needed" if not after else
                               f"; what is left is {after[0][0]} (pressure {after[0][1]})"))
        elif before:
            g["forced"].append(f"the crew does not give {m} what they came for: {before[0][0]} is still unmet (pressure {before[0][1]})")
    said = sum(len([k for k in v if k in members]) for a_, v in story["ties"].items() if a_ in members)
    missing = len(members) * (len(members) - 1) - said
    if missing:
        g["open"].append(f"{missing} ways one sees another are undecided and count as neutral")
    return g, read


def _crack(sheets, members, a, b, read):
    """What everyone does when the plan fails at its fault line, with a relying on b."""
    m = appraisal.Minds(sheets, {}, {}, {}, {"fear": -1, "anger": -1, "shame": -1, "sadness": -1, "joy": 1})
    felt = appraisal.feelings(m, [dict(kind="threat", need="safety", size=3, target=members)], members)
    feels = {e: next((k, v) for k, v in f["feel"].items() if k != "at") for e, f in felt.items()}
    lines = [f"{e}: {emo} {n}, inclined to {appraisal.inclined(m, e, emo)[0]}" for e, (emo, n) in feels.items()]
    base = dict(present=members, clock=True, loss=True, blame="unclear", felt=feels)
    inside = tendencies.apply(dict(base, threat="inside"), sheets)
    outside = tendencies.apply(dict(base, threat="outside"), sheets)
    return lines, inside, outside


def _plan(story, sheets, members, lock, read):
    g = dict(n=4, name=GATES[3], decided=None, forced=[], narrowed=[], open=[], problems=[])
    if not story.get("plan"):
        return g, None
    steps = story["plan"]
    g["decided"] = " then ".join(f"{s['who']} ({s['pin']})" for s in steps)
    for s in steps:
        if s["pin"] not in _craft(sheets[s["who"]]):
            g["problems"].append(f"{s['who']} is down for {s['pin']} and has no such craft")
    if lock:
        left = [p["kind"] for p in lock["pins"] if p["kind"] not in [s["pin"] for s in steps]]
        if left:
            g["problems"].append("the plan leaves these in the way: " + ", ".join(left))
    strains = sorted(((crew.strain(sheets, s["who"], other), k + 1, s["who"], other, s["pin"]) for k, s in enumerate(steps) for other in s.get("relies_on") or []), reverse=True)
    if not strains:
        g["forced"].append("nobody relies on anybody: the plan has no weak point, and no tension")
        return g, None
    top = strains[0]
    t, r = crew.tie(sheets, top[2], top[3])
    plural = {"relies on": "does not simply rely on", "carries": "carries", "watches": "watches", "dismisses": "dismisses"}[crew.attitude(t, r)]
    g["forced"].append(f"it goes wrong at step {top[1]}, {top[4]}: {top[2]} has to rely on {top[3]}, and {top[2]} {plural} {top[3]} (strain {top[0]} of 6)")
    if len(strains) > 1 and strains[1][0] > 0:
        g["narrowed"].append(f"or, less likely, at step {strains[1][1]}: {strains[1][2]} relying on {strains[1][3]} (strain {strains[1][0]})")
    lines, inside, outside = _crack(sheets, members, top[2], top[3], read)
    g["forced"].append("when it does, everyone is afraid; what each is inclined to do: " + "; ".join(lines))
    for name in dict.fromkeys(x["name"] for x in inside):
        hits = [x for x in inside if x["name"] == name]
        say = lambda x: f"{', '.join(x['to'])} {x['effect'].replace('blames', 'blame') if len(x['to']) > 1 else x['effect']}"
        g["forced"].append(f"{name}: " + "; ".join(dict.fromkeys(say(x) if x["effect"][0] != "(" else x["why"] for x in hits)) +
                           (f" ({hits[0]['why']})" if len(hits) == 1 and hits[0]["effect"][0] != "(" else ""))
    g["forced"].append(f"{top[2]} marks {top[3]} down for it (rating {r:+d} to {max(-2, r - 1):+d}): other people's failures read as character")
    shut = [x for x in outside if x["effect"] == "(silenced)"]
    if shut:
        g["narrowed"].append("if the trouble comes from outside instead (a guard, an alarm): ranks close and the blame waits. " + shut[0]["why"])
    return g, dict(a=top[2], b=top[3], step=top[1])


def _twist(root, story, sheets, members, planner, read, fault, theme=None):
    twists = load_yaml(root / "library" / "twists.yaml")
    g = dict(n=5, name=GATES[4], decided=None, forced=[], narrowed=[], open=[], problems=[])
    if not story.get("twist"):
        g["narrowed"].append("what the viewer is not told: one of " + ", ".join(twists))
        return g
    if story["twist"] not in twists:
        raise ScriptError(f"story.yaml: no twist '{story['twist']}' in library/twists.yaml; there are: " + ", ".join(twists))
    tw = twists[story["twist"]]
    watchers = [m for m in members if planner and m != planner and crew.attitude(*crew.tie(sheets, m, planner)) == "watches"]
    roles = dict(planner=planner, fault_a=(fault or {}).get("a"), fault_b=(fault or {}).get("b"), weak_link=read["weak_link"] if read else None,
                 watcher=watchers[0] if watchers else None)
    inside = [roles[r] for r in tw["in_on_it"] if roles.get(r)]
    missing = [r for r in tw["in_on_it"] if not roles.get(r)]
    if missing:
        g["problems"].append(f"this twist needs {', '.join(missing)}, and the story so far has none: {tw['needs']}")
    fooled = [m for m in members if m not in inside]
    g["decided"] = f"{story['twist']}: {tw['hides']}"
    if theme and story.get("theme") not in (tw.get("serves") or []):
        g["problems"].append(f"this twist does not serve the theme: nothing in it makes {theme['turn'].split(' and ')[0]}")
    world = story.get("world")
    if story["twist"] == "the-turn":
        if not world or world not in sheets:
            g["problems"].append("the turn needs someone for the harm to land on: set `world:`")
            return g
        where = f"at step {fault['step']}, where the plan cracks" if fault else "during the job"
        g["forced"].append(f"the harm lands on {world} {where}, in front of them")
        care = sorted(members, key=lambda m: -crew.tie(sheets, m, world)[0])
        feels = [m for m in care if crew.tie(sheets, m, world)[0] >= 1]
        cold = [m for m in care if crew.tie(sheets, m, world)[0] < 1]
        if feels:
            g["forced"].append(f"{', '.join(feels)} feel it as shame: it is bad for someone they care about, and their own doing. {feels[0]} turns first")
        if cold:
            g["forced"].append(f"{', '.join(cold)} do not feel it yet: {world} is nobody to them")
            g["open"].append(f"a moment, before the job, in which {' and '.join(cold)} come to care about {world}; without it their turn is not earned")
        still = [(m, standing.pressures(sheets[m], read["incoming"][m])) for m in members] if read else []
        costly = [f"{m} ({p[0][0]}, pressure {p[0][1]})" for m, p in still if p]
        free = [m for m, p in still if not p]
        if free:
            g["forced"].append(f"giving it back costs {', '.join(free)} nothing they still need: the crew already gave it to them")
        if costly:
            g["forced"].append("giving it back is a real loss for " + ", ".join(costly) + ": they still need what they came for")
            g["narrowed"].append("what the others do about that: the crew makes it up to them (reciprocity); or they give it back anyway and carry the cost; or they are the one who cannot")
        return g
    if fault and fault["a"] in inside and fault["b"] in inside and crew.strain(sheets, fault["a"], fault["b"]) > 0:
        t, r = crew.tie(sheets, fault["a"], fault["b"])
        g["narrowed"].append(f"{fault['a']} and {fault['b']} are in on it together, yet {fault['a']} {crew.attitude(t, r)} {fault['b']}: either that is the act "
                             f"(and what they really think of each other is hidden from the crew too), or {planner} staked the job on two people who do not rate each other")
    g["forced"].append("in on it: " + (", ".join(inside) or "nobody in the crew") + ". Not told: " + ", ".join(fooled) + ", the mark, and the viewer")
    g["forced"].append("the viewer is shown: " + "; ".join(f"{b} ({'what is not true' if b in tw['viewer_fooled_during'] else 'the truth, as far as it goes'})" for b in BEATS[:5]) + "; then the twist")
    after = copy.deepcopy(sheets)
    for f in fooled:                                             # a secret kept from you costs the keeper your trust; whoever planned it, most
        for k in inside:
            t, r = crew.tie(after, f, k)
            after[f].setdefault("bonds", {})[k] = [max(-2, t - (2 if k == planner else 1)), r]
    if inside and fooled and read:
        then = crew.readings(after, members)
        g["forced"].append(f"once it is out, those kept in the dark trust the others less: cohesion {read['cohesion']:+.2f} to {then['cohesion']:+.2f}; " +
                           ("the crew is now " + " | ".join(", ".join(x) for x in then["factions"]) if len(then["factions"]) > 1 else "still one crew"))
        worst = min(fooled, key=lambda f: (crew.tie(after, f, planner)[0] if planner else 0, -standing.answer(after[f])[1]))
        t = crew.tie(after, worst, planner)[0] if planner else 0
        g["forced"].append(f"{worst} wavers at the split: trust in {planner} is now {t:+d}, and they were the least sure to begin with")
        need = standing.answer(after[worst])[2]
        g["narrowed"].append(f"how it ends: {worst} takes a share and is never seen again; or {worst} goes to the mark; or {planner} tells {worst} first, "
                             f"before the rest, and it is returned (reciprocity). What decides it is {worst}'s {need}")
    return g


def report(root):
    file = root / "story.yaml"
    if not file.exists():
        raise ScriptError(f"no story.yaml in {root}: a story is decided there, gate by gate")
    story = load_yaml(file) or {}
    gates = []
    g1, lock = _lock(root, story)
    g2, sheets, planner = _crew(root, story, lock)
    members = list(story.get("crew") or [])
    g0, theme = _theme(root, story, sheets, members)
    gates += [g0, g1, g2]
    g3, read = _ties(story, sheets, members) if sheets else (dict(n=3, name=GATES[2], decided=None, forced=[], narrowed=[], open=[], problems=[]), None)
    gates.append(g3)
    g4, fault = _plan(story, sheets, members, lock, read) if sheets and read else (dict(n=4, name=GATES[3], decided=None, forced=[], narrowed=[], open=[], problems=[]), None)
    gates.append(g4)
    gates.append(_twist(root, story, sheets, members, planner, read, fault, theme) if sheets else dict(n=5, name=GATES[4], decided=None, forced=[], narrowed=[], open=[], problems=[]))
    for g in gates:
        if not g["decided"]:
            g["open"] = list(ASKS[g["name"]])
        elif g["name"] != THEME:
            pass
    funnel, forced, narrowed = [], 0, 0
    for k, g in enumerate(gates):
        if g["decided"]:
            forced, narrowed = forced + len(g["forced"]), narrowed + len(g["narrowed"])
        still = sum(len(ASKS[x["name"]]) for x in gates[k + 1:] if not x["decided"] or True) + len(ALWAYS_OPEN) + sum(len(x["open"]) for x in gates[:k + 1] if x["decided"]) if g["decided"] else None
        funnel.append(dict(gate=g["name"], decided=bool(g["decided"]), forced=forced, narrowed=narrowed, open=still))
    return dict(gates=gates, funnel=funnel, always_open=ALWAYS_OPEN, next=next((g["name"] for g in gates if not g["decided"]), None))


def text(rep):
    lines = []
    for g in rep["gates"]:
        lines.append(f"GATE {g['n']}  {g['name']}" + (f": {g['decided']}" if g["decided"] else "  (not decided)"))
        for kind in ("problems", "forced", "narrowed", "open"):
            for item in g[kind]:
                lines.append(f"  {kind[:-1] if kind == 'problems' else kind:<9} {item}")
        lines.append("")
    lines.append("HOW MUCH EACH DECISION NARROWED IT")
    lines.append(f"  {'after':<12}{'forced':>8}{'narrowed':>10}{'open':>7}")
    start = sum(len(v) for v in ASKS.values()) + len(rep["always_open"])
    lines.append(f"  {'nothing':<12}{0:>8}{0:>10}{start:>7}")
    for f in rep["funnel"]:
        if f["decided"]:
            lines.append(f"  {f['gate']:<12}{f['forced']:>8}{f['narrowed']:>10}{f['open']:>7}")
    lines += ["", "STILL OPEN, WHATEVER IS DECIDED: " + "; ".join(rep["always_open"])]
    if rep["next"]:
        lines.append(f"NEXT DECISION: {rep['next']}")
    return "\n".join(lines)
