"""Render a scene to video.

    python -m toon.render episodes/pilot/scene01.yaml
    python -m toon.render --all
    python -m toon.render episodes/pilot/scene01.yaml --still 2:40   # turn 2, frame 40, as a PNG
    --xray shows the director's view (felt against shown, weight in the room); --slate adds turn and frame

A scene with errors (a turn with no `why`, a feeling with no tell, a payoff the audience
cannot decode yet) does not render.
"""
import argparse
import os
import subprocess
import sys
from pathlib import Path

import skia

from . import ledger, speech
from .draw import draw_frame
from .model import Scene, find_root


def frame_jpeg(scene, F, scale=1.0, quality=85, xray=False, slate=False):
    surface = skia.Surface(int(scene.W * scale), int(scene.H * scale))
    c = surface.getCanvas()
    c.scale(scale, scale)
    draw_frame(c, scene, F, xray, slate)
    return bytes(surface.makeImageSnapshot().encodeToData(skia.kJPEG, quality))


def out_path(scene):
    return scene.root / "out" / (scene.key + ".mp4")


def render(scene, xray=False, slate=False):
    out = out_path(scene)
    out.parent.mkdir(parents=True, exist_ok=True)
    silent, wav, tmp = out.with_suffix(".silent.mp4"), out.with_suffix(".wav"), out.with_suffix(".part.mp4")
    ff = subprocess.Popen(
        ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgba", "-s", f"{scene.W}x{scene.H}",
         "-r", str(scene.fps), "-i", "-", "-c:v", "libx264", "-crf", "18", "-preset", "veryfast",
         "-pix_fmt", "yuv420p", str(silent)], stdin=subprocess.PIPE)
    surface = skia.Surface(scene.W, scene.H)
    for F in range(scene.total):
        draw_frame(surface.getCanvas(), scene, F, xray, slate)
        ff.stdin.write(surface.toarray(colorType=skia.kRGBA_8888_ColorType).tobytes())
    ff.stdin.close()
    if ff.wait() != 0:
        sys.exit("ffmpeg failed")
    speech.write_blips(scene.lines, scene.show.tones, {e: ent["voice"] for e, ent in scene.ents.items()},
                       scene.fps, scene.total, str(wav))
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(silent), "-i", str(wav), "-map", "0:v", "-map", "1:a",
                    "-c:v", "copy", "-c:a", "aac", "-b:a", "128k", "-shortest", str(tmp)], check=True)
    os.replace(tmp, out)
    silent.unlink()
    wav.unlink()
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("scene", nargs="?")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--still")
    ap.add_argument("--xray", action="store_true")
    ap.add_argument("--slate", action="store_true")
    a = ap.parse_args()
    root = find_root(Path(a.scene).resolve() if a.scene else Path.cwd())
    _, problems = ledger.build(root)
    paths = ledger.scene_paths(root) if a.all else [Path(a.scene).resolve()]
    scenes = [Scene(p) for p in paths]
    errors = [p for p in problems if p["level"] == "error" and (a.all or p["scene"] in {s.key for s in scenes} | {s.path.stem for s in scenes})]
    for p in problems:
        print(f"{p['level']}: {p['scene']}" + (f" turn {p['turn']}" if p.get("turn") is not None else "") + f": {p['msg']}", file=sys.stderr)
    if errors:
        sys.exit("not rendered: fix the errors above")
    for sc in scenes:
        if a.still:
            tid, f = a.still.split(":")
            turn = next(t for t in sc.turns if str(t["id"]) == tid)
            surface = skia.Surface(sc.W, sc.H)
            draw_frame(surface.getCanvas(), sc, turn["start"] + int(f), a.xray, a.slate)
            png = out_path(sc).with_name(f"{sc.path.stem}_t{tid}_{int(f):03d}.png")
            png.parent.mkdir(parents=True, exist_ok=True)
            surface.makeImageSnapshot().save(str(png), skia.kPNG)
            print(png)
        else:
            print(render(sc, a.xray, a.slate), f"{sc.total} frames, {sc.total / sc.fps:.1f}s")


if __name__ == "__main__":
    main()
