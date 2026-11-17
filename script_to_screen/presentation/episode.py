"""An episode as one film: its scenes and cards in order, joined by transitions, with one soundtrack.

How it is put together is `episode:` in show.yaml, and every part of it can be changed there:

    episode:
      transition: dip          # between parts: dip (through the paper), fade (one into the next) or cut
      transition_seconds: 0.8
      title_seconds: 5
      credits_seconds: 17

A segment in series.yaml can ask for its own way in with `into: cut | dip | fade`.
"""
import io
from pathlib import Path
import os
import subprocess
import sys
import wave

import numpy as np
import skia

from ..performance.scene import Scene
from ..script import Show, load_yaml, series, tuning
from . import cards, land, sound
from .draw import PAPER, col, draw_frame
from .stage import Look, Stage

DEFAULTS = dict(transition="dip", transition_seconds=0.8, title_seconds=5.0, credits_seconds=17.0)


def _samples(wav_bytes):
    with wave.open(io.BytesIO(wav_bytes)) as w:
        return np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float64) / 32767.0


def parts(root, eid):
    """The episode's parts in order: [{id, kind, frames, draw(canvas, frame), sound() -> samples, into}]."""
    episode, show = series(root).episode(eid), Show(root)
    cfg = {**DEFAULTS, **(show.cfg.get("episode") or {})}
    stages = {sg["id"]: Stage.of(Scene(sg["path"])) for sg in episode["segments"] if sg["kind"] == "scene"}
    cast = list(dict.fromkeys(e for st in stages.values() for e in st.score.pose))          # in order of first appearance
    look = Look.load(root, cast)
    sheets = {e: tuning.overlay(load_yaml(root / "entities" / f"{e}.yaml")) for e in cast}
    step = 60.0 / float(show.cfg["tempo"]) / show.cfg["steps_per_beat"]
    out = []
    land_file = root / "land.yaml"
    model = None

    def the_land():
        nonlocal model
        if model is None:
            data = load_yaml(land_file)
            model = land.Land(look, show.cfg, episode, data, {p["entity"]: tuning.overlay(load_yaml(root / "entities" / f"{p['entity']}.yaml")) for p in data["places"].values()})
        return model

    def frame_of(sg, F):                                             # one frame of a scene, as a picture
        surf = skia.Surface(look.W, look.H)
        draw_frame(surf.getCanvas(), stages[sg["id"]], F if F >= 0 else stages[sg["id"]].total + F)
        return surf.makeImageSnapshot()

    def where(sg):                                                   # a scene's day, and its place on the land
        spot = (load_yaml(root / "places" / f"{load_yaml(sg['path']).get('place')}.yaml") or {}).get("land")
        if sg.get("day") is None or spot is None:
            raise ValueError(f"series.yaml: a travel card needs '{sg['id']}' to have a `day:`, and its place a `land:` (which place on the land it is)")
        return dict(day=int(sg["day"]), at=the_land().land["places"][spot]["at"])

    segs = episode["segments"]
    for n, sg in enumerate(segs):
        if sg["kind"] == "card" and sg["card"] == "travel":           # between two scenes, by way of the land
            before = next(s for s in reversed(segs[:n]) if s["kind"] == "scene")
            after = next(s for s in segs[n + 1:] if s["kind"] == "scene")
            card = land.Travel(the_land(), where(before), where(after), frame_of(before, -1) if segs[n - 1] is before else None, frame_of(after, 0))
            out.append(dict(id=sg["id"], kind="travel", frames=round(card.seconds * look.fps), draw=lambda c, F, card=card: card.draw(c, F / look.fps), sound=card.sound))
        elif sg["kind"] == "scene":
            st = stages[sg["id"]]
            out.append(dict(id=sg["id"], kind="scene", frames=st.total, draw=lambda c, F, st=st: draw_frame(c, st, F),
                            sound=lambda st=st: _samples(sound.mix(st))))
        else:
            card = (the_land()
                    if sg["card"] == "title" and land_file.exists()            # a show with a land gets its title sequence over it
                    else cards.Title(look, show.cfg, episode, cast, step, cfg["title_seconds"]) if sg["card"] == "title"
                    else cards.Caption(look, sg.get("text"), sg.get("seconds")) if sg["card"] == "caption"
                    else cards.Credits(look, show.cfg, episode, cast, sheets, step, cfg["credits_seconds"]))
            out.append(dict(id=sg["id"], kind=sg["card"], frames=round(card.seconds * look.fps), draw=lambda c, F, card=card: card.draw(c, F / look.fps),
                            sound=card.sound))
        out[-1]["into"] = sg.get("into") or ("cut" if sg["kind"] == "scene" and n and segs[n - 1].get("card") == "travel" else cfg["transition"])
    return out, look, cfg


def soundtrack(plan, fps):
    """The episode's whole sound: each part's starts where its picture does, and tails ring into what follows."""
    total = sum(p["frames"] for p in plan)
    track, at = np.zeros(int((total / fps + 2.0) * sound.RATE)), 0
    for part in plan:
        x, i = part["sound"](), int(at / fps * sound.RATE)
        track[i:i + len(x)] += x[: len(track) - i]
        at += part["frames"]
    return np.tanh(track / 0.89) * 0.89


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


def shots(root, eid):
    """Every camera shot in an episode, in order: when, on whom, how close, and why. The way to catch a cut or a push-in nobody asked for."""
    plan, look, cfg = parts(root, eid)
    eps = series(root).episode(eid)
    out, at = [], 0.0
    for sg, p in zip(eps["segments"], plan):
        if sg["kind"] == "scene":
            for s in Stage.of(Scene(sg["path"])).score.camera:
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


ENCODE = ["-c:v", "libx264", "-crf", "18", "-preset", "veryfast", "-pix_fmt", "yuv420p"]      # the same for every part, so parts can be joined without encoding again


def _film(plan, look, cfg, k, frames, dest, draft):
    """Part `k`'s frames (numbered within the part) as a film at `dest`: drawn, with its way in and out (the dip through the paper,
    or the part before dissolving into it), and encoded."""
    from . import bodies
    bodies.OUTLINES = not draft
    W, H, fps = look.W, look.H, look.fps
    size, skip = (0.5, 2) if draft else (1.0, 1)
    half = max(1, round(float(cfg["transition_seconds"]) * fps / 2))
    part, paper, last = plan[k], skia.Paint(Color=col(PAPER)), None
    into, out_of = part["into"], (plan[k + 1]["into"] if k + 1 < len(plan) else "dip")
    surface = skia.Surface(int(W * size), int(H * size))
    c = surface.getCanvas()
    c.scale(size, size)
    if into == "fade" and k:                                          # the last frame of the part before, to dissolve from
        plan[k - 1]["draw"](c, plan[k - 1]["frames"] - 1)
        last = surface.makeImageSnapshot()
    tmp = dest.with_name(dest.stem + ".part.mp4")
    ff = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgba", "-s", f"{int(W * size)}x{int(H * size)}", "-r", str(fps / skip), "-i", "-",
                           *ENCODE, str(tmp)], stdin=subprocess.PIPE)
    for F in frames:
        if F % skip:
            continue
        part["draw"](c, F)
        veil = 0.0
        if F < half and (into == "dip" or k == 0):                    # in from the paper
            veil = 1 - (F + 1) / half
        if part["frames"] - F <= half and out_of == "dip":             # out to the paper
            veil = max(veil, 1 - (part["frames"] - F - 1) / half)
        if veil > 0:
            paper.setAlphaf(veil * veil * (3 - 2 * veil))
            c.drawRect(skia.Rect.MakeWH(W, H), paper)
        if last is not None and F < 2 * half:                         # the part before dissolves into this one
            c.drawImageRect(last, skia.Rect.MakeWH(W, H), skia.SamplingOptions(skia.FilterMode.kLinear), skia.Paint(Alphaf=1 - (F + 1) / (2 * half)))
        ff.stdin.write(surface.toarray(colorType=skia.kRGBA_8888_ColorType).tobytes())
    ff.stdin.close()
    if ff.wait() != 0:
        sys.exit("ffmpeg failed")
    os.replace(tmp, dest)                                             # only a finished film gets the real name


def _one(job):
    """One part, in a process of its own (each builds the episode for itself: nothing drawn can be passed between processes)."""
    root, eid, k, frames, dest, draft = job
    plan, look, cfg = parts(root, eid)
    _film(plan, look, cfg, k, frames, dest, draft)
    return k


def _stamp(root, eid, k, part, draft):
    """What part `k` is made from, as a short code: if none of it has changed, the film made last time is still right.
    Every part depends on the engine and on the show's own files; a scene depends on its own script, a card on every scene's."""
    import hashlib
    h = hashlib.sha256(f"{eid}|{k}|{part['id']}|{part['frames']}|{part['into']}|{draft}".encode())
    segs = series(root).episode(eid)["segments"]
    mine = [sg["path"] for sg in segs if sg["kind"] == "scene" and (part["kind"] != "scene" or sg["id"] == part["id"] or k and segs[k]["into"] == "fade")]
    shared = [f for d in ("library", "entities", "places") for f in sorted((root / d).rglob("*.yaml"))] + [root / n for n in ("show.yaml", "series.yaml", "land.yaml")]
    for f in sorted(Path(__file__).resolve().parent.parent.rglob("*.py")) + shared + mine:
        if Path(f).exists():
            h.update(str(f).encode() + Path(f).read_bytes())
    return h.hexdigest()[:16]


def render(root, eid, only=None, draft=False, fresh=False):
    """Render an episode to out/<episode>.mp4. Each part (a scene or a card) is made as a film of its own, as many at once as the
    machine has processors, and the parts are joined without encoding again. A part whose script, show files and engine have not
    changed since last time is not made again (`fresh` makes everything again regardless).
    `only` = (first, last) seconds renders just that stretch, for looking at a join.
    `draft` is for checking, not for showing: half the size and half the frames, to out/<episode>.draft.mp4."""
    from concurrent.futures import ProcessPoolExecutor
    plan, look, cfg = parts(root, eid)
    fps = look.fps
    out = root / "out" / (eid + (".draft" if draft else "") + (".stretch" if only else "") + ".mp4")       # a stretch never replaces the whole film
    store = root / "out" / ".parts" / (eid + (".draft" if draft else ""))
    store.mkdir(parents=True, exist_ok=True)
    silent, wav, tmp, listing = out.with_suffix(".silent.mp4"), out.with_suffix(".wav"), out.with_suffix(".part.mp4"), store / "join.txt"
    total = sum(p["frames"] for p in plan)
    lo, hi = (0, total) if only is None else (max(0, round(only[0] * fps)), min(total, round(only[1] * fps)))
    jobs, films, made, at = [], [], [], 0
    for k, part in enumerate(plan):
        a, b = max(lo, at) - at, min(hi, at + part["frames"]) - at     # the frames of this part that are wanted
        at += part["frames"]
        if b <= a:
            continue
        whole = a == 0 and b == part["frames"]
        dest = store / (f"{k:02d}-{part['id']}-{_stamp(root, eid, k, part, draft)}.mp4" if whole else f"{k:02d}-{part['id']}-stretch.mp4")
        films.append(dest)
        if whole and dest.exists() and not fresh:
            continue                                                  # made before, from exactly this
        for old in store.glob(f"{k:02d}-*.mp4"):
            old.unlink()
        jobs.append((root, eid, k, range(a, b), dest, draft))
        made.append(part["id"])
    if len(jobs) > 1 and (os.cpu_count() or 1) > 1:
        with ProcessPoolExecutor(max_workers=min(len(jobs), os.cpu_count())) as pool:
            list(pool.map(_one, sorted(jobs, key=lambda j: -len(j[3]))))        # longest first
    else:
        for job in jobs:
            _film(plan, look, cfg, job[2], job[3], job[4], draft)
    listing.write_text("".join(f"file '{f.resolve()}'\n" for f in films))
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", str(listing), "-c", "copy", str(silent)], check=True)
    track = soundtrack(plan, fps)
    end = np.linspace(1, 0, int(0.5 * sound.RATE))
    a, b = int(lo / fps * sound.RATE), int(hi / fps * sound.RATE)
    track = track[a:b].copy()
    track[-len(end):] *= end[-len(track):] if len(track) < len(end) else end
    wav.write_bytes(sound.wav_bytes(track))
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(silent), "-i", str(wav), "-map", "0:v", "-map", "1:a",
                    "-c:v", "copy", "-c:a", "aac", "-b:a", "160k", "-shortest", str(tmp)], check=True)
    os.replace(tmp, out)
    silent.unlink()
    wav.unlink()
    return out, [dict(id=p["id"], kind=p["kind"], seconds=round(p["frames"] / fps, 1), made=p["id"] in made) for p in plan]
