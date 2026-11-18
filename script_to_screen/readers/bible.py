"""The show's bible, kept inside the show so there is one place to update.

What the film already knows is read from the film (the houses on the land, what the land does day by day, each scene's beats,
what each thing in a room means, the season from above). What only the writer knows is written once, in the show's `bible.md`,
with a slot such as `{{days}}` wherever a generated part belongs. The rules live in `bible.yaml`; the ones a machine can judge
are checked against the film, and a place where the film veers from one is a warning, never an error: a rule may be broken on
purpose, but not by accident.
"""
import colorsys
import html
import re
from pathlib import Path

from ..performance import Scene
from ..script import load_yaml, place, series

GENDERED = ("he", "she", "him", "her", "his", "hers", "himself", "herself", "man", "woman", "men", "women", "boy", "girl", "king", "queen",
            "lord", "lady", "sir", "madam", "mr", "mrs", "ms", "brother", "sister", "father", "mother", "son", "daughter")


def load(root):
    f = Path(root) / "bible.yaml"
    return (load_yaml(f) or {}) if f.exists() else None


def _scenes(root):
    """Every scene of the show, in order, as it plays: [(segment, score)]."""
    return [(sg, Scene(sg["path"]).score) for sg in series(root).segments]


def _words(text):
    return set(re.findall(r"[a-z']+", str(text).lower()))


def _hsv(c):
    return colorsys.rgb_to_hsv(*(int(c[i:i + 2], 16) / 255 for i in (1, 3, 5)))


def _far(a, b):
    return sum((int(a[i:i + 2], 16) - int(b[i:i + 2], 16)) ** 2 for i in (1, 3, 5)) ** 0.5


def houses(root):
    """The houses that have a colour of their own: {name: colour}, from the land."""
    f = Path(root) / "land.yaml"
    return {k: p["color"] for k, p in ((load_yaml(f) or {}).get("places") or {}).items() if p.get("color")} if f.exists() else {}


# ---- the checks: one per kind of rule a machine can judge --------------------------------------------------
def no_gendered_words(root, rule, scenes):
    for sg, sc in scenes:
        for t in sc.turns:
            said = _words(t["line"]["text"]) & set(GENDERED) if t["line"] else ()
            if said:
                yield sg["id"], t["id"], f"the line says {', '.join(sorted(said))}"


def cast_are_objects(root, rule, scenes):
    for sg, sc in scenes:
        for e in sc.cast:
            sheet = load_yaml(Path(root) / "entities" / f"{e}.yaml") or {}
            if not sheet.get("body"):
                yield sg["id"], None, f"{e} is not drawn as an object (its sheet has no `body:`)"


def kept_words(root, rule, scenes):
    for item in (load(root) or {}).get("kept") or []:
        for sg, sc in scenes:
            for t in sc.turns:
                said = _words(t["line"]["text"]) & {str(w).lower() for w in item.get("words") or []} if t["line"] else ()
                if said:
                    yield sg["id"], t["id"], f"the line says {', '.join(sorted(said))}, which gives away: {item['what']}"


def colour_is_owned(root, rule, scenes):
    owned = houses(root)
    for name in rule.get("in") or []:
        for pc in place(root, name).get("pieces") or []:
            c = pc.get("color")
            if not c or not str(c).startswith("#"):
                continue
            hue, strength, _ = _hsv(c)
            alive = 80 <= hue * 360 <= 170
            if strength >= 0.45 and not alive and not any(_far(c, h) <= 60 for h in owned.values()):
                yield name, None, f"the {pc['kind']} at {pc.get('at')} has a strong colour ({c}) that is no house's"


def mirrored(root, rule, scenes):
    for name in rule.get("in") or []:
        pieces = [(pc["kind"], float(pc.get("at", 0))) for pc in place(root, name).get("pieces") or [] if pc["kind"] not in (rule.get("except") or [])]
        middle = float(rule.get("about", 4))
        for kind, at in pieces:
            if abs(at - middle) > 0.05 and not any(k == kind and abs((2 * middle - at) - a) <= 0.05 for k, a in pieces):
                yield name, None, f"the {kind} at {at:g} has no mirror at {2 * middle - at:g}"


def reserved_is_rare(root, rule, scenes):
    from . import motions
    yield from motions.problems(root)


CHECKS = dict(reserved_is_rare=reserved_is_rare, no_gendered_words=no_gendered_words, cast_are_objects=cast_are_objects, kept_words=kept_words, colour_is_owned=colour_is_owned, mirrored=mirrored)


def rules(root):
    b = load(root) or {}
    return list(b.get("rules") or []) + list(b.get("look") or [])


def veers(root):
    """Where the film veers from a rule: [{level, scene, turn, msg, rule}]. Warnings only."""
    if load(root) is None:
        return []
    scenes, out = _scenes(root), []
    for rule in rules(root):
        check = CHECKS.get(rule.get("check"))
        if rule.get("check") and not check:
            out.append(dict(level="warning", scene="(bible)", turn=None, rule=rule["id"], msg=f"rule '{rule['id']}' asks for a check called '{rule['check']}'; the checks are: {', '.join(CHECKS)}"))
        for where, turn, msg in (check(root, rule, scenes) if check else ()):
            out.append(dict(level="warning", scene=where, turn=turn, rule=rule["id"], msg=f"veers from \"{rule['name']}\": {msg}"))
    return out


# ---- the parts the film already knows -----------------------------------------------------------------------
def _table(head, rows):
    cell = lambda v: str(v if v is not None else "").replace("|", "/").replace("\n", " ")
    return "\n".join(["| " + " | ".join(head) + " |", "| " + " | ".join("---" for _ in head) + " |"] + ["| " + " | ".join(cell(v) for v in r) + " |" for r in rows])


def part_rules(root, key="rules"):
    found = {}
    for v in veers(root):
        found[v["rule"]] = found.get(v["rule"], 0) + 1
    rows = []
    for r in (load(root) or {}).get(key) or []:
        state = "yours to judge" if not r.get("check") else "kept" if not found.get(r["id"]) else f"{found[r['id']]} veer{'s' if found[r['id']] > 1 else ''}"
        rows.append((f"**{r['name']}**", r.get("says", ""), state))
    return _table(("Rule", "What it means", "In the film"), rows)


def part_kept(root):
    rows = [(k["what"], k.get("where", ""), ", ".join(map(str, k.get("words") or [])) or "no words given yet, so not checked") for k in (load(root) or {}).get("kept") or []]
    return _table(("Kept from the viewer", "Where", "Words that would give it away"), rows)


def part_houses(root):
    land = load_yaml(Path(root) / "land.yaml") or {}
    rows = []
    for name, p in (land.get("places") or {}).items():
        sheet = load_yaml(Path(root) / "entities" / f"{p['entity']}.yaml") or {}
        rows.append((name.capitalize(), sheet.get("kind", p["entity"]), p.get("color", "none of its own yet"),
                     f"visited on bar {p['at_bar']:g} of the title sequence" if "at_bar" in p else "not shown yet: dark on the land"))
    return _table(("House", "Its head, as drawn", "Colour", "On the land"), rows)


SAYS = dict(smoke={True: "burns", False: "is no longer burning"}, ruin={1: "lies in ruins", 0: "is rebuilt as it was"}, ring={1: "has a wall closed round it"})


def part_days(root):
    rows = []
    for e in sorted((load_yaml(Path(root) / "land.yaml") or {}).get("history") or [], key=lambda e: e["day"]):
        what = []
        if e.get("reach"):
            what.append(f"{e['reach'][0].capitalize()}'s colour travels to {e['reach'][1].capitalize()}")
        for name, change in e.items():
            if isinstance(change, dict):
                bits = [SAYS[k][v] for k, v in change.items() if k in SAYS and v in SAYS[k]]
                if change.get("flags"):
                    bits.append("flies the flags of " + ", ".join(f.capitalize() for f in change["flags"]) + (f" ({', '.join(w.capitalize() for w in change['worn'])}'s is worn)" if change.get("worn") else ""))
                what.append(f"{name.capitalize()} " + ", and ".join(bits))
        rows.append((f"{e['day']} to {e['day'] + e['over']}" if e.get("over") else e["day"], "; ".join(what), e.get("why", "")))
    return _table(("Day", "What the land shows", "Why"), rows)


def room_notes(root, name):
    """What each thing in a room means, as its place file says in the notes at its top: [(thing, meaning)]."""
    out = []
    for line in (Path(root) / "places" / f"{name}.yaml").read_text().splitlines():
        if not line.startswith("#"):
            break
        m = re.match(r"#\s{3}(\S.*?)\s{3,}(\S.*)$", line)
        more = re.match(r"#\s{12,}(\S.*)$", line)
        if m and not re.match(r"\d\.", m.group(1)):
            out.append([m.group(1), m.group(2)])
        elif more and out:
            out[-1][1] += " " + more.group(1)
    return out


def part_rooms(root):
    names = list(dict.fromkeys(load_yaml(sg["path"]).get("place") for sg in series(root).segments))
    out = []
    for name in [n for n in names if n]:
        data = place(root, name)
        out.append(f"**{data.get('name', name)}**\n\n" + _table(("In the room", "What it means"), room_notes(root, name) or [("(nothing noted)", f"write notes at the top of places/{name}.yaml")]))
    return "\n\n".join(out)


def board(root):
    """The season from above: one row per episode."""
    from ..presentation import episode as film
    from . import ledger
    show = load_yaml(Path(root) / "show.yaml")
    bar = 60.0 / float(show["tempo"]) * int(show.get("beats_per_bar") or 0)
    problems, pinned = ledger.build(root)[1], [n for n in ((load_yaml(Path(root) / "notes.yaml") or {}).get("notes") or [] if (Path(root) / "notes.yaml").exists() else []) if not n["done"]]
    rows = []
    for se in series(root).seasons:
        for ep in se["episodes"]:
            ids = [sg["id"] for sg in ep["segments"]]
            scenes = [sg for sg in ep["segments"] if sg["kind"] == "scene"]
            plan, look, _ = film.parts(root, ep["id"])
            seconds = sum(p["frames"] for p in plan) / look.fps
            days = [sg["day"] for sg in scenes if sg.get("day") is not None]
            rows.append(dict(season=se["id"], id=ep["id"], title=ep["title"], logline=ep.get("logline") or "", scenes=len(scenes), cards=len(ids) - len(scenes),
                             seconds=round(seconds, 1), bars=round(seconds / bar, 1) if bar else None, days=f"{min(days)} to {max(days)}" if days else "",
                             state=", ".join(f"{sum(s['status'] == st for s in scenes)} {st}" for st in dict.fromkeys(s["status"] for s in scenes)),
                             notes=sum(n["part"] in ids for n in pinned), problems=sum(p["scene"] in ids for p in problems)))
    return rows


def part_board(root):
    rows = [(r["id"], r["title"], r["logline"], f"{r['scenes']} scenes, {r['cards']} cards", f"{int(r['seconds'] // 60)} min {round(r['seconds'] % 60)} s" + (f" ({r['bars']:g} bars)" if r["bars"] else ""),
             r["days"], r["state"], r["notes"] or "", r["problems"] or "") for r in board(root)]
    return _table(("Episode", "Title", "What it is", "Parts", "Length", "Days", "Scenes are", "Open notes", "Problems"), rows)


def part_episodes(root):
    out, scores = [], {sg["id"]: sc for sg, sc in _scenes(root)}
    cards = dict(title="The title sequence", travel="A journey over the land", credits="The credits", caption="A caption")
    for se in series(root).seasons:
        for ep in se["episodes"]:
            out.append(f"### {ep['title']}\n\n{ep.get('logline') or ''}")
            for sg in ep["segments"]:
                if sg["kind"] != "scene":
                    out.append(f"*{cards.get(sg['card'], sg['card'])}.*")
                    continue
                sc = scores[sg["id"]]
                out.append(f"**{sc.title}**" + (f" (day {sg['day']})" if sg.get("day") is not None else "") + "\n\n" + "\n".join(f"{n}. {t['why']}" for n, t in enumerate(sc.turns, 1)))
    return "\n\n".join(out)


def part_motions(root):
    from . import motions
    return motions.markdown(root)


PARTS = dict(motions=part_motions, rules=part_rules, look=lambda root: part_rules(root, "look"), kept=part_kept, houses=part_houses, days=part_days, rooms=part_rooms, board=part_board, episodes=part_episodes)


def build(root):
    """The bible as markdown: the written file with every `{{slot}}` filled from the film; and, first, where the film veers."""
    f = Path(root) / "bible.md"
    text = f.read_text() if f.exists() else "# " + str(load_yaml(Path(root) / "show.yaml").get("title", "Bible")) + "\n\n" + "\n\n".join(f"## {k.capitalize()}\n\n{{{{{k}}}}}" for k in PARTS)
    unknown = sorted(set(re.findall(r"\{\{(\w+)\}\}", text)) - set(PARTS))
    if unknown:
        raise ValueError(f"bible.md has a slot the tool cannot fill: {{{{{unknown[0]}}}}}. The slots are: " + ", ".join(PARTS))
    found = veers(root)
    track = ("**On track.** The film keeps every rule that can be checked." if not found else
             f"**{len(found)} place{'s' if len(found) > 1 else ''} where the film veers from a rule:**\n\n" + "\n".join(f"- {v['scene']}" + (f", turn {v['turn']}" if v["turn"] is not None else "") + f": {v['msg']}" for v in found))
    text = re.sub(r"\{\{(\w+)\}\}", lambda m: PARTS[m.group(1)](root), text)
    head, _, rest = text.partition("\n")
    return f"{head}\n\n{track}\n{rest}"


# ---- as a page, for the editor -------------------------------------------------------------------------------
def _inline(s):
    s = html.escape(s, quote=False)
    s = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", s)
    s = re.sub(r"(?<!\*)\*(?!\*)(.+?)\*", r"<i>\1</i>", s)
    s = re.sub(r"`(.+?)`", r"<code>\1</code>", s)
    return re.sub(r"\[(.+?)\]\((https?://[^)\s]+)\)", r'<a href="\2" target="_blank" rel="noopener">\1</a>', s)


def to_html(md):
    """Enough markdown for a bible: headings, paragraphs, lists, checklists and tables."""
    out, lines, i = [], md.splitlines(), 0
    while i < len(lines):
        line = lines[i]
        if not line.strip():
            i += 1
        elif line.startswith("#"):
            n = len(line) - len(line.lstrip("#"))
            title = line[n:].strip()
            out.append(f'<h{n} id="{re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")}">{_inline(title)}</h{n}>')
            i += 1
        elif line.startswith("|"):
            rows = []
            while i < len(lines) and lines[i].startswith("|"):
                rows.append([c.strip() for c in lines[i].strip().strip("|").split("|")])
                i += 1
            body = [r for r in rows[2:]] if len(rows) > 1 and set("".join(rows[1])) <= set("-: ") else rows[1:]
            out.append("<table><thead><tr>" + "".join(f"<th>{_inline(c)}</th>" for c in rows[0]) + "</tr></thead><tbody>" +
                       "".join("<tr>" + "".join(f"<td>{_inline(c)}</td>" for c in r) + "</tr>" for r in body) + "</tbody></table>")
        elif re.match(r"(\d+\.|-) ", line):
            tag = "ol" if line[0].isdigit() else "ul"
            items = []
            while i < len(lines) and re.match(r"(\d+\.|-) ", lines[i]):
                item = re.sub(r"^(\d+\.|-) ", "", lines[i])
                box = re.match(r"\[( |x)\] (.*)", item)
                items.append(f'<li class="{"task" if box else ""}">' + (("&#9745; " if box.group(1) == "x" else "&#9744; ") + _inline(box.group(2)) if box else _inline(item)) + "</li>")
                i += 1
            out.append(f"<{tag}>" + "".join(items) + f"</{tag}>")
        else:
            para = []
            while i < len(lines) and lines[i].strip() and not re.match(r"(#|\||\d+\. |- )", lines[i]):
                para.append(lines[i])
                i += 1
            out.append("<p>" + _inline(" ".join(para)) + "</p>")
    return "\n".join(out)
