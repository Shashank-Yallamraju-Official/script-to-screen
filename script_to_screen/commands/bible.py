"""The show's bible, the season from above, and an episode as a storyboard."""
from ..readers import bible
from . import A, Refused, address, command


@command("bible", "The show's bible: what the writer wrote (bible.md) with everything the film already knows filled in, and, first, where the film veers from a rule. --write saves it to out/bible.md.",
         [A("--write", "also save it to out/bible.md", action="store_true")], "s2s bible", group="read")
def bible_(a):
    root = address.show_root(a.show)
    try:
        text = bible.build(root)
    except ValueError as e:
        raise Refused(str(e))
    out = dict(veers=bible.veers(root), text=text)
    if a.write:
        (root / "out").mkdir(exist_ok=True)
        (root / "out" / "bible.md").write_text(text)
        out["file"] = str(root / "out" / "bible.md")
    return out


@command("board", "The season from above: one row per episode, with what it is, how long, which days, how finished, and what is open.", [], "s2s board", group="read")
def board(a):
    root = address.show_root(a.show)
    rows = bible.board(root)
    lines = [f"{r['id']}  {r['title']}  {int(r['seconds'] // 60)}:{round(r['seconds'] % 60):02d}" + (f"  {r['bars']:g} bars" if r["bars"] else "") + (f"  days {r['days']}" if r["days"] else "") +
             f"  {r['scenes']} scenes ({r['state']})" + (f"  {r['notes']} open notes" if r["notes"] else "") + (f"  {r['problems']} problems" if r["problems"] else "") + f"\n    {r['logline']}" for r in rows]
    return dict(episodes=rows, text="\n".join(lines) or "no episodes")


@command("storyboard", "An episode as a storyboard: one frame per beat with its reason underneath, in order. The story read as pictures.",
         [A("episode", "an episode's id"), A("--cols", "frames per row", type=int, default=4)], "s2s storyboard the-vote", group="look")
def storyboard(a):
    from ..presentation import readings
    root = address.show_root(a.show)
    png = readings.storyboard(root, a.episode, a.cols)
    return dict(file=str(png), text=str(png))


@command("motions", "Every kind of movement the tool can show: which the film has used and how often, which the show keeps in reserve, and which are possible but unused. A movement on neither list is a new type.",
         [], "s2s motions", group="read")
def motions_(a):
    from ..readers import motions
    root = address.show_root(a.show)
    rows = motions.table(root)
    used = [r for r in rows if r["times"]]
    lines = [f"{r['name']:9} {r['tier'] or 'no tier':9} {r['times']:3}x  first {r['first']:24} {r['sees']}" for r in sorted(used, key=lambda r: (r["tier"] != "reserved", -r["times"]))]
    lines += ["", "possible, not used yet:"] + [f"  {r['name']:9} {r['sees']}  ({r['ask']})" for r in rows if not r["times"]]
    found = motions.problems(root)
    lines += [""] + [f"warn  {p}" + (f":{t}" if t is not None else "") + f"  {m}" for p, t, m in found] if found else lines[:0]
    return dict(motions=rows, problems=[dict(part=p, turn=t, msg=m) for p, t, m in found], text="\n".join(lines))


@command("outline", "An episode's outline: its beats in order, what each is for and what it uses, checked against the bible and against the film. --draft writes a first one from a film that exists.",
         [A("episode", "an episode's id", nargs="?"), A("--draft", "print a first outline written from the film, to correct", action="store_true"),
          A("--write", "with --draft: save it to outlines/<episode>.yaml (refused if one is there)", action="store_true")], "s2s outline the-vote", group="read")
def outline_(a):
    from ..readers import outline
    root = address.show_root(a.show)
    if a.draft:
        if not a.episode:
            raise Refused("which episode?", hint="s2s outline the-vote --draft")
        text = "# A first outline, written from the film. Correct `what`, and say what each beat is `for`.\n" + outline.draft(root, a.episode)
        if a.write:
            if outline.path(root, a.episode).exists():
                raise Refused(f"outlines/{a.episode}.yaml is already there", hint="edit it, or remove it first")
            outline.path(root, a.episode).parent.mkdir(exist_ok=True)
            outline.path(root, a.episode).write_text(text)
        return dict(text=text)
    eps = [a.episode] if a.episode else outline.episodes(root)
    if a.episode and outline.load(root, a.episode) is None:
        raise Refused(f"{a.episode} has no outline", hint=f"s2s outline {a.episode} --draft --write   starts one from the film; or write outlines/{a.episode}.yaml")
    found = [p for p in outline.problems(root) if not a.episode or p["scene"] == f"(outline {a.episode})"]
    lines = []
    for e in eps:
        lines.append(e)
        for r in outline.rows(root, e):
            b = r["beat"]
            uses = "  ".join(f"{f.key}: {', '.join(map(str, b[f.key]))}" for f in outline.FACETS if b.get(f.key))
            lines.append(f"  {str(b.get('id')):12} {str(b.get('bars', '')):>4}  {r['state']:9} {b.get('what', '')}" + (f"\n{'':30}{uses}" if uses else ""))
    lines += [""] + [f"warn  {p['scene']}" + (f":{p['turn']}" if p["turn"] is not None else "") + f"  {p['msg']}" for p in found] if found else []
    return dict(outlines={e: outline.rows(root, e) for e in eps}, problems=found, text="\n".join(lines) or "no outlines yet: s2s outline <episode> --draft --write starts one")
