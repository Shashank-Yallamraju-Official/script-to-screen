"""Ways of looking at an episode without rendering it: its frames at chosen moments, its sound as a picture, its rhythm in
bars, and its camera shots. Each reads the same parts the renderer does (`episode.parts`), so what they show is what will be made.
"""
import numpy as np
import skia

from ..script import Show
from . import sound
from .draw import PAPER, col
from .episode import parts, soundtrack


def listen(root, eid):
    """Look at an episode's sound, for a maker who cannot hear it: how loud it is over time (a picture), and what is wrong with
    it in words. -> (png, [findings]). It looks for: sound that stops dead, long silences, clipping, and a jump in level where
    two parts join."""
    from .draw import INK, fill, font, stroke
    plan, look, cfg = parts(root, eid)
    fps, rate = look.fps, sound.RATE
    x = soundtrack(plan, fps)
    win = rate // 20                                                 # twentieths of a second
    n = len(x) // win
    db = 20 * np.log10(np.sqrt(np.mean(x[: n * win].reshape(n, win) ** 2, axis=1)) + 1e-6)
    sec = lambda i: i / 20
    found, at, joins = [], 0, []
    for p in plan:
        a, b = int(at / fps * 20), min(n, int((at + p["frames"]) / fps * 20))
        joins.append((sec(a), p["id"], float(np.mean(db[a:b])) if b > a else -120.0))
        at += p["frames"]
    end = sum(p["frames"] for p in plan) / fps
    for i in range(2, n - 2):                                        # sound that stops dead: loud, then nothing, within a tenth of a second
        held = i >= 60 and float(np.min(db[i - 60:i - 1])) > -45        # it had been sounding for three seconds: a spoken line ending is not this
        if held and db[i - 1] > -34 and db[i + 1] < db[i - 1] - 30 and sec(i) < end - 0.6:
            if not found or found[-1][0] != "stops dead" or sec(i) - found[-1][1] > 0.5:
                found.append(("stops dead", sec(i), f"{db[i - 1]:.0f} dB to {db[i + 1]:.0f} dB"))
    quiet, start = db < -55, None
    for i in range(n + 1):                                           # silence of more than two seconds
        if i < n and quiet[i] and sec(i) < end:
            start = i if start is None else start
        elif start is not None:
            if sec(i - start) > 3.0:
                found.append(("silent", sec(start), f"for {sec(i - start):.1f}s"))
            start = None
    if np.max(np.abs(x)) > 0.885:
        found.append(("at the limit", float(np.argmax(np.abs(x))) / rate, "the loudest moment is pressed flat"))
    for (t0, a, la), (t1, b, lb) in zip(joins, joins[1:]):           # the level across a join: a second either side
        i = int(t1 * 20)
        before, after = float(np.mean(db[max(0, i - 20):i])), float(np.mean(db[i:i + 20]))
        if abs(before - after) > 18:
            found.append(("jump at a join", t1, f"{a} ends at {before:.0f} dB, {b} starts at {after:.0f} dB"))
    W, H, pad = 1600, 420, 50
    surf = skia.Surface(W, H)
    c = surf.getCanvas()
    c.clear(col(PAPER))
    X, Y = (lambda s: pad + (W - 2 * pad) * s / max(end, 1e-6)), (lambda d: 40 + (H - 110) * (min(0, max(-70, d)) / -70))
    for d in (0, -20, -40, -60):
        c.drawLine(pad, Y(d), W - pad, Y(d), stroke("#d8d2c4", 1))
        c.drawString(f"{d}", 12, Y(d) + 4, font(12, mono=True), fill(INK, 150))
    path = skia.Path()
    for i in range(n):
        if sec(i) > end:
            break
        (path.moveTo if i == 0 else path.lineTo)(X(sec(i)), Y(db[i]))
    c.drawPath(path, stroke("#3f6fd0", 1.6))
    for t0, name, level in joins:
        c.drawLine(X(t0), 30, X(t0), H - 60, stroke(INK, 1, 120))
        c.drawString(f"{name}  {level:.0f} dB", X(t0) + 4, H - 44, font(12, mono=True), fill(INK))
        c.drawString(f"{t0:.0f}s", X(t0) + 4, H - 26, font(12, mono=True), fill(INK, 150))
    for kind, t, _ in found:
        c.drawCircle(X(t), 24, 6, fill("#c8324e"))
    png = root / "out" / f"{eid}_sound.png"
    png.parent.mkdir(parents=True, exist_ok=True)
    surf.makeImageSnapshot().save(str(png), skia.kPNG)
    return png, [dict(what=k, at=round(t, 1), detail=d) for k, t, d in found], [dict(part=nm, at=round(t0, 1), level=round(lv)) for t0, nm, lv in joins]


def rhythm(root, eid):
    """An episode read as a song. Time is counted in bars (the show's tempo); a phrase is eight. For every bar: how loud it is and
    how much moves on screen. -> (png, parts, flats): each part's length in bars and whether that is a whole number, and every
    stretch of twelve bars or more in which neither sound nor picture rises or falls (the places a song would have lost its listener)."""
    from .draw import INK, fill, font, stroke
    plan, look, cfg = parts(root, eid)
    show = Show(root).cfg
    fps, rate = look.fps, sound.RATE
    bar = 60.0 / float(show["tempo"]) * float(show.get("beats_per_bar", 2))
    x = soundtrack(plan, fps)
    one, prev, moved, at = skia.Surface(look.W, look.H), None, [], 0
    for p in plan:                                                   # movement: how much of the picture changes, four times a second
        for F in range(0, p["frames"], max(1, round(fps / 4))):
            p["draw"](one.getCanvas(), F)
            a = one.toarray(colorType=skia.kRGBA_8888_ColorType)[::8, ::8, :3].astype(np.int16)
            moved.append(((at + F) / fps, 0.0 if prev is None else float(np.mean(np.abs(a - prev)))))
            prev = a
        at += p["frames"]
    total = at / fps
    n = int(np.ceil(total / bar - 1e-6))
    t, mv = np.array([m[0] for m in moved]), np.array([m[1] for m in moved])
    loud, move = [], []
    for b in range(n):
        seg = x[int(b * bar * rate):int((b + 1) * bar * rate)]
        loud.append(min(1.0, max(0.0, (20 * np.log10(np.sqrt(np.mean(seg ** 2)) + 1e-6) + 60) / 60)))
        m = mv[(t >= b * bar) & (t < (b + 1) * bar)]
        move.append(min(1.0, float(np.mean(m)) / 8.0) if len(m) else 0.0)
    out_parts, at = [], 0
    for p in plan:
        length = p["frames"] / fps / bar
        out_parts.append(dict(part=p["id"], kind=p["kind"], starts=round(at / fps / bar, 2), bars=round(length, 2), on_grid=abs(length - round(length)) < 0.03 and abs(at / fps / bar - round(at / fps / bar)) < 0.03))
        at += p["frames"]
    flats, start = [], 0
    for b in range(1, n + 1):                                        # a flat stretch: the level of both stays within a narrow band
        band = lambda v: max(v[start:b]) - min(v[start:b])
        if b == n or band(loud + [loud[min(b, n - 1)]]) > 0.22 or band(move + [move[min(b, n - 1)]]) > 0.25:
            scene_at = lambda q: any(p["kind"] == "scene" and p["starts"] <= q < p["starts"] + p["bars"] for p in out_parts)
            if b - start >= 12 and scene_at(start) and scene_at(b - 1):      # in a scene: a card is carried by its music
                flats.append(dict(starts=start, bars=b - start))
            start = b
    W, H, pad = 1600, 460, 50
    surf = skia.Surface(W, H)
    c = surf.getCanvas()
    c.clear(col(PAPER))
    X, Y = (lambda b: pad + (W - 2 * pad) * b / max(n, 1)), (lambda v: 50 + (H - 140) * (1 - v))
    for b in range(0, n + 1, 8):                                     # a line at every phrase
        c.drawLine(X(b), 50, X(b), H - 90, stroke("#d8d2c4", 1))
        c.drawString(str(b), X(b) - 6, H - 72, font(12, mono=True), fill(INK, 150))
    for f in flats:
        c.drawRect(skia.Rect.MakeLTRB(X(f["starts"]), 50, X(f["starts"] + f["bars"]), H - 90), fill("#c8324e", 26))
    for values, colour in ((move, "#e0952f"), (loud, "#3f6fd0")):
        path = skia.Path()
        for b, v in enumerate(values):
            (path.moveTo if b == 0 else path.lineTo)(X(b + 0.5), Y(v))
        c.drawPath(path, stroke(colour, 2))
    for p in out_parts:
        c.drawLine(X(p["starts"]), 30, X(p["starts"]), H - 60, stroke(INK, 1.5, 160))
        c.drawString(f"{p['part']}  {p['bars']:g} bars" + ("" if p["on_grid"] else "  (off the grid)"), X(p["starts"]) + 4, H - 44, font(12, mono=True), fill(INK if p["on_grid"] else "#c8324e"))
    c.drawString("sound", pad, 32, font(13), fill("#3f6fd0"))
    c.drawString("movement on screen", pad + 70, 32, font(13), fill("#e0952f"))
    c.drawString("shaded: twelve bars or more with no rise or fall", pad + 250, 32, font(13), fill("#c8324e"))
    png = root / "out" / f"{eid}_rhythm.png"
    png.parent.mkdir(parents=True, exist_ok=True)
    surf.makeImageSnapshot().save(str(png), skia.kPNG)
    return png, out_parts, flats, dict(bar=round(bar, 3), bars=round(total / bar, 2), loud=[round(v, 2) for v in loud], move=[round(v, 2) for v in move])


def shots(root, eid):
    """Every camera shot in an episode, in order: when, on whom, how close, and why. The way to catch a cut or a push-in nobody asked for."""
    plan, look, cfg = parts(root, eid)
    out, at = [], 0.0
    for p in plan:
        if p["kind"] == "scene":
            for s in p["stage"].score.camera:
                out.append(dict(at=round(at + s["t"], 1), part=p["id"], zoom=round(s["zoom"], 2), on=s["on"], why=s["why"]))
        else:
            out.append(dict(at=round(at, 1), part=p["id"], zoom=None, on=[], why=f"a {p['kind']} card"))
        at += p["frames"] / look.fps
    return out


def sheet(root, eid, times=None, every=None, part=None, cols=4, wide=480):
    """A contact sheet of an episode: one small labelled frame for each of `times` (seconds), or one every `every` seconds.
    With `part` (a segment's id) the times are counted from that part's start, and `every` covers just that part.
    -> the PNG's path. The quick way to look at chosen moments without rendering the film."""
    from .draw import INK, fill, font
    png = root / "out" / f"{eid}_moments.png"
    png.parent.mkdir(parents=True, exist_ok=True)
    png.unlink(missing_ok=True)                                      # so a sheet that fails to draw never leaves the last one looking like the new one
    plan, look, cfg = parts(root, eid)
    fps, starts, at = look.fps, {}, 0
    for p in plan:
        starts[p["id"]] = at
        at += p["frames"]
    if part and part not in starts:
        raise ValueError(f"no part called '{part}' in {eid}; the parts are: " + ", ".join(starts))
    first, length = (starts[part], next(p["frames"] for p in plan if p["id"] == part)) if part else (0, at)
    if every:
        times = [k * float(every) for k in range(int(length / fps / float(every)) + 1)]
    frames = [min(at - 1, first + round(float(t) * fps)) for t in times or [0]]
    scale = wide / look.W
    w, h = wide, round(look.H * scale)
    rows = (len(frames) + cols - 1) // cols
    out, one = skia.Surface(cols * w, rows * (h + 22)), skia.Surface(look.W, look.H)
    out.getCanvas().clear(col(PAPER))
    for i, G in enumerate(frames):
        p = next(q for q in reversed(plan) if starts[q["id"]] <= G)
        p["draw"](one.getCanvas(), G - starts[p["id"]])
        c, x, y = out.getCanvas(), (i % cols) * w, (i // cols) * (h + 22)
        c.drawImageRect(one.makeImageSnapshot(), skia.Rect.MakeXYWH(x, y, w, h), skia.SamplingOptions(skia.FilterMode.kLinear))
        c.drawString(f"{G / fps:.1f}s  {p['id']} +{(G - starts[p['id']]) / fps:.1f}s", x + 6, y + h + 16, font(13, mono=True), fill(INK))
    out.makeImageSnapshot().save(str(png), skia.kPNG)
    return png


SPOTS = (0.12, 0.38, 0.62, 0.9)                 # where in each part a kept frame is taken
SMALL = (160, 90)


def _kept(plan, look):
    """The frames an episode is remembered by: four from each part, small. -> (labels, array of shape [n, 90, 160, 3])"""
    one, labels, shots = skia.Surface(look.W, look.H), [], []
    for p in plan:
        for spot in SPOTS:
            F = min(p["frames"] - 1, int(p["frames"] * spot))
            p["draw"](one.getCanvas(), F)
            small = skia.Surface(*SMALL)
            small.getCanvas().drawImageRect(one.makeImageSnapshot(), skia.Rect.MakeWH(*SMALL), skia.SamplingOptions(skia.FilterMode.kLinear, skia.MipmapMode.kLinear))
            shots.append(small.toarray(colorType=skia.kRGBA_8888_ColorType)[:, :, :3].copy())
            labels.append(f"{p['id']} at {F / look.fps:.1f}s")
    return labels, np.stack(shots)


def frames(root, eid, accept=False, tolerance=2.5):
    """Has the episode's picture changed? Compares its kept frames (frames/<episode>.png in the show, kept in git) with how they
    draw now. -> (changed: [(label, how much)], png of now beside before, or None). With `accept`, how they draw now becomes the
    kept frames: do that when the change was meant. A change in the look that nobody meant shows up here before anyone watches."""
    plan, look, cfg = parts(root, eid)
    labels, now = _kept(plan, look)
    kept = root / "frames" / f"{eid}.png"
    strip = lambda a: np.ascontiguousarray(np.dstack([np.hstack(list(a)), np.full((SMALL[1], SMALL[0] * len(a), 1), 255, np.uint8)]))
    if accept or not kept.exists():
        kept.parent.mkdir(parents=True, exist_ok=True)
        skia.Image.fromarray(strip(now), colorType=skia.kRGBA_8888_ColorType).save(str(kept), skia.kPNG)
        return [], None
    was = skia.Image.open(str(kept)).toarray(colorType=skia.kRGBA_8888_ColorType)[:, :, :3]
    if was.shape[1] != SMALL[0] * len(now):
        return [("the episode has a different number of parts than when its frames were kept", 255.0)], None
    was = np.stack(np.split(was, len(now), axis=1))
    apart = np.abs(now.astype(np.int16) - was.astype(np.int16)).mean(axis=3)                       # [n, 90, 160]
    by = apart.reshape(len(now), 9, 10, 16, 10).mean(axis=(2, 4)).max(axis=(1, 2))               # the most-changed patch of each frame: a small change in one corner still counts
    changed = [(labels[i], round(float(by[i]), 1)) for i in range(len(now)) if by[i] > tolerance]
    png = None
    if changed:
        png = root / "out" / f"{eid}_frames_changed.png"
        png.parent.mkdir(parents=True, exist_ok=True)
        pick = [i for i in range(len(now)) if by[i] > tolerance]
        both = np.vstack([strip(was[pick]), strip(now[pick])])           # before above, now below
        skia.Image.fromarray(np.ascontiguousarray(both), colorType=skia.kRGBA_8888_ColorType).save(str(png), skia.kPNG)
    return changed, png


def beats(root, eid):
    """An episode's beats on the bar grid, for looking at and for moving: every turn of every scene, with the bar it lands on,
    how long it needs (`after`: bars from where it lands until the next thing could begin) and how much run-up the next line
    would need before it (`lead`). A beat can be moved to any bar where `bar >= previous.bar + previous.after + its own lead`,
    and the last must end by the scene's length. Cards are given as fixed blocks. -> plain data."""
    from ..script import load_yaml
    plan, look, cfg = parts(root, eid)
    show = Show(root).cfg
    bar_s = 60.0 / float(show["tempo"]) * float(show.get("beats_per_bar", 2))
    out, at = [], 0.0
    for p in plan:
        length = p["frames"] / look.fps / bar_s
        block = dict(id=p["id"], kind=p["kind"], starts=round(at, 3), bars=round(length, 3), beats=[])
        if p["kind"] == "scene":
            score = p["stage"].score
            per = float(show["steps_per_beat"]) * float(show.get("beats_per_bar", 2))
            raw = {t.get("id", i + 1): t for i, t in enumerate(load_yaml(score.place and next(s["path"] for s in _segments(root, eid) if s["id"] == p["id"])).get("turns") or [])}
            for t in score.turns:
                r = raw.get(t["id"], {})
                said = r.get("say") or r.get("sing")
                lands = t["start"] + (t["pause"] if said else 0.0)
                what = "line" if said else "sound" if r.get("sfx") else "enter" if r.get("enter") else "exit" if r.get("exit") else "move" if r.get("do") else "hold"
                block["beats"].append(dict(turn=t["id"], bar=round(lands / per, 3), after=round((t["start"] + t["length"] - t["waited"] - lands) / per, 3),
                                           lead=round(t["pause"] / per, 3) if said else 0.0, kind=what, who=t["who"] or next(iter(r.get("enter") or r.get("do") or {}), None),
                                           text=str(said or ""), why=t["why"], placed=r.get("bar") is not None))
        out.append(block)
        at += length
    return dict(episode=eid, show=str(Show(root).cfg.get("title") or ""), bar_seconds=round(bar_s, 4), snap=1 / (float(show["steps_per_beat"]) * float(show.get("beats_per_bar", 2))), parts=out)


def _segments(root, eid):
    from ..script import series
    return series(root).episode(eid)["segments"]
