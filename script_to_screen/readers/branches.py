"""Branches: every combination of the candidate answers to what a story leaves open, worked through and scored.

A story's open decisions form a tree. `branches.yaml` holds candidate answers to each, written in the
model's terms; this reader takes every combination, applies it to the story, and measures what comes out.
"Interesting" is a score with visible parts, so it can be argued with:

    earned     x3   members whose excuse stops working AND who feel it (they care about who it lands on)
    felt       x1   members who feel it but can still excuse it
    knows      x0   members whose excuse stops working but who feel nothing: a turn that is not earned
    in front   x2   the harm happens where they can see it, by their own hands
    resolved   x1   needs still pressing on anyone (the mark and the world included) that the ending answers
    remaining  x-1  needs still pressing on anyone that it does not
    strain     x0.5 how much the plan leans on ties that cannot bear it (up to 6)
    blows      x-1  each harm after the first: every one has to be staged, and they land on one person

A branch can use more than one harm (up to three), because one blow rarely breaks every excuse.
"""
import copy
import itertools

from ..performance import crew, standing
from ..script import ScriptError, load_yaml
from . import story as S

WEIGHTS = dict(earned=3, felt=1, knows=0, in_front=2, resolved=1, remaining=-1, strain=0.5, blows=-1)


def _apply_snag(plan, snag):
    plan = copy.deepcopy(plan)
    for pin, change in (snag.get("plan") or {}).items():
        for step in plan:
            if step["pin"] == pin:
                step.update(change)
                break
    return plan


def leaf(root, story, sheets0, members, choice):
    snag, harms, cares, ending = choice
    present = bool(snag.get("world_present"))
    if any(h.get("needs_present") for h in harms) and not present:
        return None                                              # it cannot happen: they are not in the building
    harm = dict(breaks=sorted({b for h in harms for b in h.get("breaks") or []}), own_doing=max(h.get("own_doing", 0) for h in harms),
                name=" + ".join(h["name"] for h in harms))
    world, mark = story.get("world"), story.get("mark")
    sheets = copy.deepcopy(sheets0)
    for c in cares:
        for a, ties in c["ties"].items():
            sheets[a].setdefault("bonds", {}).update(ties)
    plan = _apply_snag(story["plan"], snag)
    for step in plan:
        if step["pin"] not in S._craft(sheets[step["who"]]):
            return None
    strains = sorted(((crew.strain(sheets, s["who"], o), k + 1, s["who"], o) for k, s in enumerate(plan) for o in s.get("relies_on") or []), reverse=True)
    read = crew.readings(sheets, members)
    excuse = {m: (sheets[m].get("profile") or {}).get("tells_self") for m in members}
    cares_for = {m: crew.tie(sheets, m, world)[0] for m in members}
    feels = [m for m in members if cares_for[m] >= 1]
    broken = [m for m in members if excuse[m] in (harm.get("breaks") or [])]
    earned = [m for m in members if m in feels and m in broken]
    pressing, resolved, remaining = [], [], []
    for e in members + [x for x in (mark, world) if x]:
        for need, p, _ in standing.pressures(sheets[e], read["incoming"].get(e)):
            (resolved if need in (ending.get("meets") or {}).get(e, []) else remaining).append(f"{e}'s {need}")
    in_front = present and any(h.get("needs_present") or h.get("own_doing", 0) >= 2 for h in harms)
    parts = dict(earned=len(earned), felt=len([m for m in feels if m not in earned]), knows=len([m for m in broken if m not in feels]),
                 in_front=int(in_front), resolved=len(resolved), remaining=len(remaining), strain=min(6, sum(x[0] for x in strains)), blows=len(harms) - 1)
    return dict(snag=snag["name"], harm=harm["name"], harms=[h["name"] for h in harms], care=[c["name"] for c in cares], ending=ending["name"],
                score=round(sum(WEIGHTS[k] * v for k, v in parts.items()), 1), parts=parts,
                fault=(f"step {strains[0][1]}: {strains[0][2]} relying on {strains[0][3]} (strain {strains[0][0]})" if strains and strains[0][0] else "nowhere: nothing in the plan is under strain"),
                earned=earned, feels=feels, unearned=[m for m in broken if m not in feels], unbroken=[m for m in members if m not in broken],
                first=max(members, key=lambda m: cares_for[m]) if feels else None, resolved=resolved, remaining=remaining)


def explore(root):
    file = root / "branches.yaml"
    if not file.exists():
        raise ScriptError(f"no branches.yaml in {root}: candidate answers to what the story leaves open go there")
    story, options = load_yaml(root / "story.yaml"), load_yaml(file)
    for need in ("crew", "plan", "world", "ties"):
        if not story.get(need):
            raise ScriptError(f"branches need the story decided as far as `{need}:`")
    members = list(story["crew"])
    sheets = S._sheets(root, members + [story[k] for k in ("mark", "world") if story.get(k)], story.get("ties"))
    cares = options.get("care") or []
    subsets = [list(c) for n in range(len(cares) + 1) for c in itertools.combinations(cares, n)]
    leaves, skipped = [], 0
    harms = options.get("harm") or []
    blows = [list(c) for n in range(1, min(3, len(harms)) + 1) for c in itertools.combinations(harms, n)]
    for choice in itertools.product(options.get("snag") or [{"name": "nothing changes"}], blows, subsets, options.get("ending") or []):
        got = leaf(root, story, sheets, members, choice)
        if got is None:
            skipped += 1
        else:
            leaves.append(got)
    leaves.sort(key=lambda x: -x["score"])
    sway = {}
    by = {}
    for x in leaves:
        by.setdefault(f"{len(x['harms'])} blow{'s' if len(x['harms']) > 1 else ''}", []).append(x["score"])
    means = {k: sum(v) / len(v) for k, v in by.items()}
    sway["blows"] = dict(spread=round(max(means.values()) - min(means.values()), 1), options={k: round(v, 1) for k, v in sorted(means.items(), key=lambda kv: -kv[1])})
    fewest = min((len(x["harms"]) for x in leaves if len(x["earned"]) == len(members)), default=None)
    for key in ("snag", "ending"):                        # how much each decision moves the score: the spread between its best and worst option
        by = {}
        for x in leaves:
            by.setdefault(x[key], []).append(x["score"])
        means = {k: sum(v) / len(v) for k, v in by.items()}
        sway[key] = dict(spread=round(max(means.values()) - min(means.values()), 1), options={k: round(v, 1) for k, v in sorted(means.items(), key=lambda kv: -kv[1])})
    by = {}
    for x in leaves:
        by.setdefault(len(x["care"]), []).append(x["score"])
    means = {f"{k} of {len(cares)} moments": sum(v) / len(v) for k, v in by.items()}
    sway["care"] = dict(spread=round(max(means.values()) - min(means.values()), 1), options={k: round(v, 1) for k, v in sorted(means.items(), key=lambda kv: -kv[1])})
    each = {h["name"]: round(sum(x["score"] for x in leaves if h["name"] in x["harms"]) / max(1, sum(1 for x in leaves if h["name"] in x["harms"])), 1) for h in harms}
    sway["harm"] = dict(spread=round(max(each.values()) - min(each.values()), 1), options=dict(sorted(each.items(), key=lambda kv: -kv[1])))
    return dict(leaves=leaves, skipped=skipped, sway=sway, members=members, fewest=fewest, all_earned=sum(1 for x in leaves if len(x["earned"]) == len(members)))


def _tell(x, n=None):
    p = x["parts"]
    out = [(f"{n}. " if n else "") + f"score {x['score']}   (earned {p['earned']}, felt {p['felt']}, in front {p['in_front']}, resolved {p['resolved']}, remaining {p['remaining']}, strain {p['strain']}, blows {p['blows'] + 1})",
           f"     snag     {x['snag']}",
           f"     harm     " + "\n              ".join(x["harms"]),
           f"     care     " + ("; ".join(x["care"]) or "nobody new comes to care"),
           f"     ending   {x['ending']}",
           f"     so       it cracks at {x['fault']}" + (f"; {x['first']} turns first" if x["first"] else "; nobody feels it"),
           f"              earned turns: {', '.join(x['earned']) or 'none'}" + (f"; knows but does not feel: {', '.join(x['unearned'])}" if x["unearned"] else "") +
           (f"; can still excuse it: {', '.join(x['unbroken'])}" if x["unbroken"] else ""),
           f"              left unanswered: {', '.join(x['remaining']) or 'nothing'}"]
    return out


def text(rep, top=5):
    leaves = rep["leaves"]
    lines = [f"{len(leaves)} branches worked through ({rep['skipped']} could not happen). Scores run from {leaves[-1]['score']} to {leaves[0]['score']}.",
             f"In {rep['all_earned']} of them every one of the {len(rep['members'])} has an earned turn" +
             (f"; the fewest blows that manages it is {rep['fewest']}." if rep["fewest"] else ": no combination of these candidates breaks every excuse for someone who feels it."), "",
             "WHICH DECISION MATTERS MOST (average score by option; the spread is how much the choice moves it)"]
    for key, s in sorted(rep["sway"].items(), key=lambda kv: -kv[1]["spread"]):
        lines.append(f"  {key:<7} spread {s['spread']:>4}   " + "   ".join(f"{v}: {k}" for k, v in s["options"].items()))
    lines += ["", f"THE {top} THAT SCORE HIGHEST"]
    seen = set()
    shown = 0
    for x in leaves:                                             # one per combination of snag and harm, so the list is not five versions of the same story
        key = (x["snag"], x["harm"])
        if key in seen:
            continue
        seen.add(key)
        shown += 1
        lines += _tell(x, shown) + [""]
        if shown == top:
            break
    lines += ["THE ONE THAT SCORES LOWEST"] + _tell(leaves[-1])
    return "\n".join(lines)
