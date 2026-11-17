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
