"""Render a scene to video.

    s2s render shows/demo/episodes/s01/e01/01-the-last-dumpling.yaml
    s2s render --show shows/demo --episode s01/e01
    s2s render --show shows/demo --all
    s2s render <scene> --still 2:6          # turn 2, six steps in, as a PNG
    --xray shows the director's view (felt against shown, weight in the room); --slate adds turn and step

A scene with errors (a turn with no `why`, a feeling with no tell, a payoff the audience
cannot decode yet) does not render.
"""
import argparse
import os
import subprocess
import sys
from pathlib import Path

import skia

from ..performance import Scene
from ..readers import ledger
from ..script import find_root
from . import sound
from .draw import draw_frame


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
    wav.write_bytes(sound.mix(scene))
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(silent), "-i", str(wav), "-map", "0:v", "-map", "1:a",
                    "-c:v", "copy", "-c:a", "aac", "-b:a", "160k", "-shortest", str(tmp)], check=True)
    os.replace(tmp, out)
    silent.unlink()
    wav.unlink()
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("scene", nargs="?")
    ap.add_argument("--show", default=".", help="the show's folder, for --all and --episode (default: here)")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--episode", help="a folder under episodes/, e.g. s01/e01: render its scenes and join them")
    ap.add_argument("--still")
    ap.add_argument("--xray", action="store_true")
    ap.add_argument("--slate", action="store_true")
    a = ap.parse_args()
    root = find_root(Path(a.scene or a.show).resolve())
    if a.episode:
        a.all = False
    _, problems = ledger.build(root)
    paths = (ledger.scene_paths(root) if a.all else
             sorted((root / "episodes" / a.episode).rglob("*.yaml")) if a.episode else [Path(a.scene).resolve()])
    if not paths:
        sys.exit("no scenes found")
    scenes = [Scene(p) for p in paths]
    mine = {s.key for s in scenes} | {s.path.stem for s in scenes}
    for p in problems:
        print(f"{p['level']}: {p['scene']}" + (f" turn {p['turn']}" if p.get("turn") is not None else "") + f": {p['msg']}", file=sys.stderr)
    if any(p["level"] == "error" and (a.all or p["scene"] in mine) for p in problems):
        sys.exit("not rendered: fix the errors above")
    for sc in scenes:
        if a.still:
            tid, steps = a.still.split(":")
            turn = next(t for t in sc.turns if str(t["id"]) == tid)
            F = round((turn["start"] + float(steps)) * sc.step * sc.fps)
            surface = skia.Surface(sc.W, sc.H)
            draw_frame(surface.getCanvas(), sc, F, a.xray, a.slate)
            png = out_path(sc).with_name(f"{sc.path.stem}_t{tid}_{steps}.png")
            png.parent.mkdir(parents=True, exist_ok=True)
            surface.makeImageSnapshot().save(str(png), skia.kPNG)
            print(png)
        else:
            print(render(sc, a.xray, a.slate), f"{sc.dur:.1f}s")
    if a.episode and not a.still:                        # same encoder settings throughout, so the join is lossless
        listing = root / "out" / (a.episode + ".txt")
        listing.write_text("".join(f"file '{out_path(sc)}'\n" for sc in scenes))
        joined = root / "out" / (a.episode + ".mp4")
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", str(listing), "-c", "copy", str(joined)], check=True)
        listing.unlink()
        print(joined)


if __name__ == "__main__":
    main()
