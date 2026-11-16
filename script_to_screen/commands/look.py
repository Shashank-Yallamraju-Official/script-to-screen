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


@command("render", "Render to video: one scene, an episode (its scenes, title card and credits as one film), or everything. Refuses while the show has errors.",
         [A("scene", "a scene", nargs="?"), A("--episode", "an episode's id, e.g. s01e01: render it as one film"), A("--all", "every scene", action="store_true"),
          XRAY, A("--slate", "label every frame with its turn and step", action="store_true")],
         "s2s render --episode s01e01", group="look")
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
        film, made = episode.render(root, a.episode)
        return dict(file=str(film), parts=made, problems=problems, seconds=round(sum(m["seconds"] for m in made), 1),
                    text="\n".join([f"warn: {p['scene']}: {p['msg']}" for p in problems] + [f"  {m['seconds']:>5}s  {m['kind']:<8} {m['id']}" for m in made]
                                   + [f"{film} {round(sum(m['seconds'] for m in made), 1)}s"]))
    scenes = [Stage.of(Scene(p)) for p in paths]
    files = [dict(scene=st.score.id, file=str(R.render(st, a.xray, a.slate)), seconds=round(st.score.dur, 1)) for st in scenes]
    out = dict(files=files, problems=problems)
    out["text"] = "\n".join([f"warn: {p['scene']}: {p['msg']}" for p in problems] + [f"{f['file']} {f['seconds']}s" for f in files])
    return out
