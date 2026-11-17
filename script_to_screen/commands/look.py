"""Commands that look: a still, a contact sheet, a rendered clip. Each prints where its file went."""
from ..performance import Scene
from ..presentation import render as R
from ..presentation.stage import Stage
from ..readers import ledger
from ..script import scene_key, scene_paths, series
from . import A, FAILED, Refused, address, command
from .read import built

XRAY = A("--xray", "the director's view: weight in the room, and felt against shown", action="store_true")


def frame_of(st, t, steps):
    return min(st.total - 1, round((t["start"] + steps) * st.score.step * st.fps))


def landed(t):
    """The step in a turn at which it has fully played: the line said, reactions done, before the hold runs out."""
    return max(0.0, t["length"] - t["hold"] / 2)


@command("still", "One frame as a PNG: a turn once it has landed, or `scene:turn+steps` for an exact moment.",
         [A("turn", "scene:turn or scene:turn+steps"), XRAY, A("--slate", "label the frame with its turn and step", action="store_true")],
         "s2s still thermostat:2+6 --xray", group="look")
def still(a):
    root, path, tid, steps = address.turn(a.turn, a.show)
    sc, t = built(root, path, tid)
    steps = steps if "+" in a.turn else landed(t)
    st = Stage.of(sc)
    png = R.out_path(st).with_name(f"{R.out_path(st).stem}_t{t['id']}_{steps:g}.png")
    R.still(st, frame_of(st, t, steps), png, a.xray, a.slate)
    return dict(file=str(png), address=address.of(root, path, t["id"]), steps=steps, text=str(png))


@command("sheet", "A contact sheet: one labelled frame per turn, each once the turn has landed. The quick way to see a whole scene.",
         [A("scene", "the scene"), XRAY, A("--cols", "frames per row", type=int, default=4)], "s2s sheet thermostat", group="look")
def sheet(a):
    root, path = address.scene(a.scene, a.show)
    sc, _ = built(root, path)
    st = Stage.of(sc)
    png = R.out_path(st).with_name(R.out_path(st).stem + "_sheet.png")
    R.sheet(st, [frame_of(st, t, landed(t)) for t in sc.turns], png, a.cols, xray=a.xray)
    return dict(file=str(png), frames=[address.of(root, path, t["id"]) for t in sc.turns], text=str(png))


@command("moments", "A contact sheet of an episode at the moments you name (seconds), or one frame every so often. With --part, times count from that part's start.",
         [A("episode", "an episode's id"), A("times", "seconds into the episode (or the part)", nargs="*", type=float), A("--every", "one frame every this many seconds", type=float),
          A("--part", "a segment's id: look at just that part"), A("--cols", "frames per row", type=int, default=4)],
         "s2s moments the-vote --part months-later --every 1", group="look")
def moments(a):
    from ..presentation import readings
    root = address.show_root(a.show)
    if not a.times and not a.every:
        raise Refused("no moments named", hint="give times in seconds, or --every <seconds>")
    try:
        png = readings.sheet(root, a.episode, a.times, a.every, a.part, a.cols)
    except ValueError as e:
        raise Refused(str(e))
    return dict(file=str(png), text=str(png))


@command("listen", "Look at an episode's sound without hearing it: a picture of its loudness, and a list of what is wrong (stops dead, silences, a jump at a join).",
         [A("episode", "an episode's id")], "s2s listen the-vote", group="look")
def listen(a):
    from ..presentation import readings
    root = address.show_root(a.show)
    png, found, levels = readings.listen(root, a.episode)
    lines = [f"  {p['at']:>6}s  {p['level']:>4} dB  {p['part']}" for p in levels] + ([f"  ! {f['at']:>6}s  {f['what']}: {f['detail']}" for f in found] or ["  nothing wrong found"])
    return dict(file=str(png), findings=found, levels=levels, text="\n".join(lines + [str(png)]))


@command("rhythm", "An episode read as a song: each part's length in bars, the rise and fall of sound and movement bar by bar, and where it goes flat.",
         [A("episode", "an episode's id")], "s2s rhythm the-vote", group="look")
def rhythm(a):
    from ..presentation import readings
    png, made, flats, curve = readings.rhythm(address.show_root(a.show), a.episode)
    lines = [f"  one bar is {curve['bar']}s; a phrase is 8 bars; the episode is {curve['bars']:g} bars"]
    lines += [f"  bar {p['starts']:>6g}  {p['bars']:>6g} bars  {p['part']}" + ("" if p["on_grid"] else "   ! off the grid") for p in made]
    lines += [f"  ! flat: {f['bars']} bars from bar {f['starts']} with no rise or fall" for f in flats] or ["  no flat stretches"]
    return dict(file=str(png), parts=made, flats=flats, curve=curve, text="\n".join(lines + [str(png)]))


@command("frames", "Has the episode's picture changed since its frames were last kept? Lists the moments that look different. --accept keeps how it looks now.",
         [A("episode", "an episode's id"), A("--accept", "the change was meant: keep how it looks now", action="store_true")], "s2s frames the-vote", group="look")
def frames(a):
    from ..presentation import readings
    changed, png = readings.frames(address.show_root(a.show), a.episode, a.accept)
    if a.accept:
        return dict(ok=True, text="kept: this is now how the episode is expected to look")
    lines = [f"  ! {label}: differs by {by}" for label, by in changed] or ["  the picture is as it was kept"]
    return dict(ok=not changed, changed=changed, file=str(png) if png else None, text="\n".join(lines + ([f"  before (above) and now (below): {png}", "  if the change was meant: s2s frames <episode> --accept"] if changed else [])),
                exit=FAILED if changed else 0)


@command("beats", "An episode's beats on the bar grid: where every turn lands, how long it needs, and how early the next could come. --json gives it as data, for the timeline.",
         [A("episode", "an episode's id")], "s2s beats the-vote", group="look")
def beats(a):
    from ..presentation import readings
    data = readings.beats(address.show_root(a.show), a.episode)
    lines = []
    for p in data["parts"]:
        lines.append(f"  bar {p['starts']:>6g}  {p['id']}  ({p['bars']:g} bars)")
        for b in p["beats"]:
            lines.append(f"      {b['bar']:>6g}  turn {b['turn']:<3} {b['kind']:<6} {(b['who'] or ''):<12} {b['text'] or b['why'][:60]}")
    return dict(text="\n".join(lines), **data)


@command("shots", "Every camera shot in an episode, in order: when, how close, on whom, and why.", [A("episode", "an episode's id")], "s2s shots the-vote", group="look")
def shots(a):
    from ..presentation import readings
    made = readings.shots(address.show_root(a.show), a.episode)
    return dict(shots=made, text="\n".join(f"  {s['at']:>6}s  {s['part']:<20} {'x' + str(s['zoom']) if s['zoom'] else '':<6} {', '.join(s['on']) or 'everyone':<12} {s['why']}" for s in made))


@command("render", "Render to video: one scene, an episode (its scenes, title card and credits as one film), or everything. Refuses while the show has errors.",
         [A("scene", "a scene", nargs="?"), A("--episode", "an episode's id, e.g. s01e01: render it as one film"), A("--all", "every scene", action="store_true"),
          XRAY, A("--slate", "label every frame with its turn and step", action="store_true"),
          A("--draft", "with --episode: a quick look, not for showing. Half size, half the frames, no outlines on bodies", action="store_true"),
          A("--only", "with --episode: just this stretch, in seconds, e.g. 30-48"),
          A("--fresh", "with --episode: make every part again, even those that have not changed", action="store_true")],
         "s2s render --episode s01e01 --draft", group="look")
def render(a):
    if a.scene:
        root, path = address.scene(a.scene, a.show)
        paths = [path]
    else:
        root = address.show_root(a.show)
        paths = [sg["path"] for sg in series(root).episode(a.episode)["segments"] if sg["kind"] == "scene"] if a.episode else scene_paths(root) if a.all else []
    if not paths:
        raise Refused("nothing to render", hint="name a scene, or use --episode <folder> or --all")
    _, problems = ledger.build(root)
    mine = {scene_key(p, root) for p in paths}
    problems = [p for p in problems if a.all or p["scene"] in mine]
    if any(p["level"] == "error" for p in problems):
        return dict(ok=False, problems=problems, exit=FAILED,
                    text="not rendered: fix these first\n" + "\n".join(f"  {p['scene']}" + (f":{p['turn']}" if p.get("turn") is not None else "") + f"  {p['msg']}" for p in problems if p["level"] == "error"))
    if a.episode:                                                # one film: scenes and cards in order, joined by transitions, one soundtrack
        from ..presentation import episode
        only = tuple(float(x) for x in a.only.split("-")) if a.only else None
        film, made = episode.render(root, a.episode, only, a.draft, a.fresh)
        return dict(file=str(film), parts=made, problems=problems, seconds=round(sum(m["seconds"] for m in made), 1),
                    text="\n".join([f"warn: {p['scene']}: {p['msg']}" for p in problems] + [f"  {m['seconds']:>5}s  {m['kind']:<8} {m['id']}" + ("" if m["made"] else "  (unchanged: kept)") for m in made]
                                   + [f"{film} {round(sum(m['seconds'] for m in made), 1)}s"]))
    scenes = [Stage.of(Scene(p)) for p in paths]
    files = [dict(scene=st.score.id, file=str(R.render(st, a.xray, a.slate)), seconds=round(st.score.dur, 1)) for st in scenes]
    out = dict(files=files, problems=problems)
    out["text"] = "\n".join([f"warn: {p['scene']}: {p['msg']}" for p in problems] + [f"{f['file']} {f['seconds']}s" for f in files])
    return out
