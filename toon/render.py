"""Render a scene script to video.

    python -m toon.render episodes/pilot/scene01.yaml             # whole scene
    python -m toon.render episodes/pilot/scene01.yaml --shots 2   # re-render one shot, rejoin
    python -m toon.render episodes/pilot/scene01.yaml --still 2:40  # one frame (shot:frame) to PNG
    add --clean to drop the shot/frame slate used for giving notes
"""
import argparse
import math
import os
import subprocess
import sys
from pathlib import Path

import skia
import yaml

from . import dialogue, stage
from .paper import col, draw_grain, make_grain
from .puppet import EXPR_DEFAULT, EXPR_KEYS, HEAD_MID, HEAD_TOP, POSE_DEFAULT, POSE_KEYS, draw_puppet


def load_yaml(p):
    with open(p) as fh:
        return yaml.safe_load(fh)


class Scene:
    def __init__(self, path):
        path = Path(path).resolve()
        root = next(p for p in path.parents if (p / "show.yaml").exists())
        self.root, self.path = root, path
        self.show = load_yaml(root / "show.yaml")
        self.W, self.H, self.fps = self.show["width"], self.show["height"], self.show["fps"]
        self.tones = load_yaml(root / "library/tones.yaml")
        lib = load_yaml(root / "library/poses.yaml")
        self.poses, self.exprs = lib["poses"], lib["expressions"]
        self.script = load_yaml(path)
        self.set = load_yaml(root / "sets" / (self.script["set"] + ".yaml"))
        self.cast = {}
        for who, place in self.script["cast"].items():
            ch = load_yaml(root / "cast" / (who + ".yaml"))
            ch["id"] = who
            self.cast[who] = (ch, place)

        # Flatten shot-local beats onto one global timeline so state carries across cuts.
        self.shots, self.changes, self.lines = [], {w: [] for w in self.cast}, []
        start = 0
        for shot in self.script["shots"]:
            shot = dict(shot, start=start, end=start + shot["length"])
            self.shots.append(shot)
            for beat in sorted(shot.get("beats", []), key=lambda b: b["frame"]):
                F = start + beat["frame"]
                for who in self.cast:
                    if who in beat:
                        self.changes[who].append((F, beat[who]))
                if "say" in beat:
                    say = beat["say"]
                    tone = self.tones[say.get("tone", "neutral")]
                    times, dur = dialogue.schedule(say["text"], tone["cps"], self.fps)
                    self.lines.append(dict(who=say["who"], text=say["text"], tone=say.get("tone", "neutral"),
                                           start=F, times=times, reveal_end=F + dur,
                                           end=min(F + dur + say.get("hold", 45), shot["end"])))
            start = shot["end"]
        self.total = start
        for a, b in zip(self.lines, self.lines[1:]):
            a["end"] = min(a["end"], b["start"])
        self.grain = make_grain(self.W, self.H)

    def line_at(self, F):
        for ln in self.lines:
            if ln["start"] <= F < ln["end"]:
                return ln
        return None

    def state(self, who, F):
        ch, place = self.cast[who]
        st = dict(x=place["at"], ground=self.set["ground"], facing=place.get("facing", "right"),
                  scale=ch.get("scale", 1.0))
        pose = [dict(POSE_DEFAULT), dict(POSE_DEFAULT), -999]   # previous, current, changed-at
        expr = [dict(EXPR_DEFAULT), dict(EXPR_DEFAULT), -999]
        for Fc, ch_ in self.changes[who]:
            if Fc > F:
                break
            if "facing" in ch_:
                st["facing"] = ch_["facing"]
            if "pose" in ch_:
                pose = [pose[1], dict(POSE_DEFAULT, **self.poses[ch_["pose"]]), Fc]
            if "expression" in ch_:
                expr = [expr[1], dict(EXPR_DEFAULT, **self.exprs[ch_["expression"]]), Fc]
        k = dialogue.ease_back((F - pose[2]) / 8)      # limbs snap with a little overshoot
        for key in POSE_KEYS:
            st[key] = pose[0][key] + (pose[1][key] - pose[0][key]) * k
        k = stage.smooth((F - expr[2]) / 5)
        for key in EXPR_KEYS:
            st[key] = expr[0][key] + (expr[1][key] - expr[0][key]) * k
        src = expr[1] if k >= 0.5 else expr[0]
        st["mouth"], st["blush"] = src["mouth"], src["blush"]
        ln = self.line_at(F)
        if ln and ln["who"] == who and F < ln["reveal_end"]:   # speaking: a small nod per syllable
            st["bob"] = -abs(math.sin((F - ln["start"]) * 0.55)) * 2.5
        return st

    def draw(self, canvas, F, slate=True):
        shot = next(s for s in self.shots if s["start"] <= F < s["end"])
        f = F - shot["start"]
        states = {w: self.state(w, F) for w in self.cast}
        cam = stage.cam_at(shot.get("camera", {"framing": "wide"}), f, states, self.W, self.H)
        canvas.clear(col(self.set["backdrop"]))
        stage.draw_layers(canvas, self.set["layers"], cam, self.W, self.H, -9, 1.0001, self.script["set"])
        canvas.save()
        stage.layer_xform(canvas, cam, 1.0, self.W, self.H)
        ln = self.line_at(F)
        order = sorted(self.cast, key=lambda w: (ln is not None and ln["who"] == w))  # speaker on top
        for who in order:
            draw_puppet(canvas, self.cast[who][0], states[who], F, self.fps)
        canvas.restore()
        stage.draw_layers(canvas, self.set["layers"], cam, self.W, self.H, 1.0001, 9, self.script["set"])
        if ln:
            st, ch = states[ln["who"]], self.cast[ln["who"]][0]
            hx, htop = stage.to_screen(cam, st["x"], st["ground"] - HEAD_TOP * st["scale"], self.W, self.H)
            _, hmid = stage.to_screen(cam, st["x"], st["ground"] - HEAD_MID * st["scale"], self.W, self.H)
            dialogue.draw_bubble(canvas, ln, F, (hx, htop, hmid), ch["color"], self.tones[ln["tone"]],
                                 self.W, self.H, self.fps)
        draw_grain(canvas, self.grain)
        if slate:
            font = skia.Font(skia.Typeface("DejaVu Sans Mono", skia.FontStyle.Bold()), 16)
            label = f"S{shot['id']} · {f:03d}"
            canvas.drawRoundRect(skia.Rect.MakeXYWH(14, 12, font.measureText(label) + 20, 26), 6, 6,
                                 skia.Paint(AntiAlias=True, Color=skia.Color(30, 25, 20, 150)))
            canvas.drawString(label, 24, 31, font, skia.Paint(AntiAlias=True, Color=skia.Color(250, 245, 235, 230)))


def encode_shot(scene, shot, out, slate):
    surface = skia.Surface(scene.W, scene.H)
    tmp = out.with_name(out.stem + ".part.mp4")
    ff = subprocess.Popen(
        ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgba",
         "-s", f"{scene.W}x{scene.H}", "-r", str(scene.fps), "-i", "-",
         "-c:v", "libx264", "-crf", "18", "-preset", "veryfast", "-pix_fmt", "yuv420p", str(tmp)],
        stdin=subprocess.PIPE)
    for F in range(shot["start"], shot["end"]):
        scene.draw(surface.getCanvas(), F, slate)
        ff.stdin.write(surface.toarray(colorType=skia.kRGBA_8888_ColorType).tobytes())
    ff.stdin.close()
    if ff.wait() != 0:
        sys.exit(f"ffmpeg failed on shot {shot['id']}")
    os.replace(tmp, out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("scene")
    ap.add_argument("--shots", help="comma-separated shot ids to re-render; others are reused")
    ap.add_argument("--still", help="shot:frame to write as a PNG instead of rendering video")
    ap.add_argument("--clean", action="store_true", help="no shot/frame slate")
    a = ap.parse_args()
    scene = Scene(a.scene)
    rel = scene.path.relative_to(scene.root / "episodes").with_suffix("")
    out_dir = scene.root / "out" / rel
    out_dir.mkdir(parents=True, exist_ok=True)

    if a.still:
        sid, f = a.still.split(":")
        shot = next(s for s in scene.shots if str(s["id"]) == sid)
        surface = skia.Surface(scene.W, scene.H)
        scene.draw(surface.getCanvas(), shot["start"] + int(f), not a.clean)
        png = out_dir / f"still_s{sid}_{int(f):03d}.png"
        surface.makeImageSnapshot().save(str(png), skia.kPNG)
        print(png)
        return

    only = set(a.shots.split(",")) if a.shots else None
    files = []
    for shot in scene.shots:
        mp4 = out_dir / f"shot{int(shot['id']):02d}.mp4"
        if only is None or str(shot["id"]) in only or not mp4.exists():
            encode_shot(scene, shot, mp4, not a.clean)
        files.append(mp4)
    listing = out_dir / "shots.txt"
    listing.write_text("".join(f"file '{p}'\n" for p in files))
    silent, wav = out_dir / "silent.part.mp4", out_dir / "dialogue.wav"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", str(listing),
                    "-c", "copy", str(silent)], check=True)
    voices = {w: ch["voice"] for w, (ch, _) in scene.cast.items()}
    dialogue.write_blips(scene.lines, scene.tones, voices, scene.fps, scene.total, str(wav))
    final = out_dir.with_suffix(".mp4")
    tmp = final.with_name(final.stem + ".part.mp4")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(silent), "-i", str(wav), "-map", "0:v",
                    "-map", "1:a", "-c:v", "copy", "-c:a", "aac", "-b:a", "128k", "-shortest", str(tmp)], check=True)
    os.replace(tmp, final)
    silent.unlink()
    print(final, f"{scene.total} frames, {scene.total / scene.fps:.1f}s")


if __name__ == "__main__":
    main()
