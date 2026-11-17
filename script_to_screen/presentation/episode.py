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
from . import anthem, cards, land, sound
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
            titled = segs[n - 1].get("card") == "title" and land_file.exists()      # the days already passed during the title sequence: this only comes down
            card = land.Travel(the_land(), where(after) if titled else where(before), where(after), frame_of(before, -1) if segs[n - 1] is before else None, frame_of(after, 0))
            out.append(dict(id=sg["id"], kind="travel", card=card, frames=round(card.seconds * look.fps), draw=lambda c, F, card=card: card.draw(c, F / look.fps), sound=card.sound))
        elif sg["kind"] == "scene":
            st = stages[sg["id"]]
            out.append(dict(id=sg["id"], kind="scene", stage=st, frames=st.total, draw=lambda c, F, st=st: draw_frame(c, st, F),
                            sound=lambda st=st: _samples(sound.mix(st))))
        else:
            card = (the_land()
                    if sg["card"] == "title" and land_file.exists()            # a show with a land gets its title sequence over it
                    else cards.Title(look, show.cfg, episode, cast, step, cfg["title_seconds"]) if sg["card"] == "title"
                    else cards.Caption(look, sg.get("text"), sg.get("seconds")) if sg["card"] == "caption"
                    else cards.Credits(look, show.cfg, episode, cast, sheets, step, cfg["credits_seconds"]))
            if sg["card"] == "title" and land_file.exists():           # between two scenes, the days from one to the other pass during it
                around = [next((s for s in seq if s["kind"] == "scene" and s.get("day") is not None), None) for seq in (reversed(segs[:n]), segs[n + 1:])]
                card.span = (int(around[0]["day"]), int(around[1]["day"])) if all(around) else None
            out.append(dict(id=sg["id"], kind=sg["card"], card=card, frames=round(card.seconds * look.fps), draw=lambda c, F, card=card: card.draw(c, F / look.fps),
                            sound=card.sound))
        if sg["kind"] == "card":                                         # a card's music can be set by hand: where it lands (in bars, later or earlier) and how loud it is
            hand = sg.get("tune") or {}
            out[-1]["music_at"] = float(hand.get("music_at", 0)) * anthem.BAR
            if float(hand.get("music_vol", 1)) != 1:
                out[-1]["sound"] = lambda made=out[-1]["sound"], vol=float(hand["music_vol"]): made() * vol
        out[-1]["into"] = sg.get("into") or ("cut" if sg["kind"] == "scene" and n and segs[n - 1].get("card") == "travel" else cfg["transition"])
    return out, look, cfg


def soundtrack(plan, fps):
    """The episode's whole sound: each part's starts where its picture does, and tails ring into what follows."""
    total = sum(p["frames"] for p in plan)
    track, at = np.zeros(int((total / fps + 2.0) * sound.RATE)), 0
    for part in plan:
        x, i = part["sound"](), int((at / fps + part.get("music_at", 0.0)) * sound.RATE)
        if i < 0:                                                    # music asked to land before the film starts: it comes in already going
            x, i = x[-i:], 0
        track[i:i + len(x)] += x[: len(track) - i]
        at += part["frames"]
    return np.tanh(track / 0.89) * 0.89


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
