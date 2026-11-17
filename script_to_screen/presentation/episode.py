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
import os
import subprocess
import sys
import wave

import numpy as np
import skia

from ..performance.scene import Scene
from ..script import Show, load_yaml, series, tuning
from . import cards, sound
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
    for sg in episode["segments"]:
        if sg["kind"] == "scene":
            st = stages[sg["id"]]
            out.append(dict(id=sg["id"], kind="scene", frames=st.total, draw=lambda c, F, st=st: draw_frame(c, st, F),
                            sound=lambda st=st: _samples(sound.mix(st))))
        else:
            card = (cards.Title(look, show.cfg, episode, cast, step, cfg["title_seconds"]) if sg["card"] == "title"
                    else cards.Caption(look, sg.get("text"), sg.get("seconds")) if sg["card"] == "caption"
                    else cards.Credits(look, show.cfg, episode, cast, sheets, step, cfg["credits_seconds"]))
            out.append(dict(id=sg["id"], kind=sg["card"], frames=round(card.seconds * look.fps), draw=lambda c, F, card=card: card.draw(c, F / look.fps),
                            sound=card.sound))
        out[-1]["into"] = sg.get("into") or cfg["transition"]
    return out, look, cfg


def render(root, eid, only=None):
    """Render an episode to out/<episode>.mp4. `only` = (first, last) seconds renders just that stretch, for looking at a join."""
    plan, look, cfg = parts(root, eid)
    W, H, fps = look.W, look.H, look.fps
    out = root / "out" / f"{eid}.mp4"
    out.parent.mkdir(parents=True, exist_ok=True)
    silent, wav, tmp = out.with_suffix(".silent.mp4"), out.with_suffix(".wav"), out.with_suffix(".part.mp4")
    half = max(1, round(float(cfg["transition_seconds"]) * fps / 2))
    total = sum(p["frames"] for p in plan)
    lo, hi = (0, total) if only is None else (max(0, round(only[0] * fps)), min(total, round(only[1] * fps)))
    ff = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgba", "-s", f"{W}x{H}", "-r", str(fps), "-i", "-",
                           "-c:v", "libx264", "-crf", "18", "-preset", "veryfast", "-pix_fmt", "yuv420p", str(silent)], stdin=subprocess.PIPE)
    surface = skia.Surface(W, H)
    paper, last, at = skia.Paint(Color=col(PAPER)), None, 0
    for k, part in enumerate(plan):
        into, out_of = part["into"], (plan[k + 1]["into"] if k + 1 < len(plan) else "dip")
        for F in range(part["frames"]):
            G = at + F
            if not lo <= G < hi:
                continue
            c = surface.getCanvas()
            part["draw"](c, F)
            veil = 0.0
            if F < half and (into == "dip" or k == 0):                # in from the paper
                veil = 1 - (F + 1) / half
            if part["frames"] - F <= half and out_of == "dip":         # out to the paper
                veil = max(veil, 1 - (part["frames"] - F - 1) / half)
            if veil > 0:
                paper.setAlphaf(veil * veil * (3 - 2 * veil))
                c.drawRect(skia.Rect.MakeWH(W, H), paper)
            if into == "fade" and last is not None and F < 2 * half:   # the part before dissolves into this one
                c.drawImage(last, 0, 0, skia.SamplingOptions(), skia.Paint(Alphaf=1 - (F + 1) / (2 * half)))
            ff.stdin.write(surface.toarray(colorType=skia.kRGBA_8888_ColorType).tobytes())
        if k + 1 < len(plan) and plan[k + 1]["into"] == "fade":
            part["draw"](surface.getCanvas(), part["frames"] - 1)
            last = surface.makeImageSnapshot()
        at += part["frames"]
    ff.stdin.close()
    if ff.wait() != 0:
        sys.exit("ffmpeg failed")
    track, at = np.zeros(int((total / fps + 2.0) * sound.RATE)), 0     # each part's sound starts where its picture does; tails ring into what follows
    for part in plan:
        x, i = part["sound"](), int(at / fps * sound.RATE)
        track[i:i + len(x)] += x[: len(track) - i]
        at += part["frames"]
    track = np.tanh(track / 0.89) * 0.89
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
    return out, [dict(id=p["id"], kind=p["kind"], seconds=round(p["frames"] / fps, 1)) for p in plan]
