"""Rendering: a scene to video, one frame to a picture, several frames to a contact sheet.

These are plain functions. Deciding whether a show is fit to render is the `render` command's job.
"""
import os
import subprocess
import sys
from pathlib import Path

import skia

from . import sound
from .draw import draw_frame


def frame_jpeg(stage, F, scale=1.0, quality=85, xray=False, slate=False):
    surface = skia.Surface(int(stage.W * scale), int(stage.H * scale))
    c = surface.getCanvas()
    c.scale(scale, scale)
    draw_frame(c, stage, F, xray, slate)
    return bytes(surface.makeImageSnapshot().encodeToData(skia.kJPEG, quality))


def out_path(stage):
    return stage.root / "out" / (stage.score.id + ".mp4")


def render(stage, xray=False, slate=False):
    out = out_path(stage)
    out.parent.mkdir(parents=True, exist_ok=True)
    silent, wav, tmp = out.with_suffix(".silent.mp4"), out.with_suffix(".wav"), out.with_suffix(".part.mp4")
    ff = subprocess.Popen(
        ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgba", "-s", f"{stage.W}x{stage.H}",
         "-r", str(stage.fps), "-i", "-", "-c:v", "libx264", "-crf", "18", "-preset", "veryfast",
         "-pix_fmt", "yuv420p", str(silent)], stdin=subprocess.PIPE)
    surface = skia.Surface(stage.W, stage.H)
    for F in range(stage.total):
        draw_frame(surface.getCanvas(), stage, F, xray, slate)
        ff.stdin.write(surface.toarray(colorType=skia.kRGBA_8888_ColorType).tobytes())
    ff.stdin.close()
    if ff.wait() != 0:
        sys.exit("ffmpeg failed")
    wav.write_bytes(sound.mix(stage))
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(silent), "-i", str(wav), "-map", "0:v", "-map", "1:a",
                    "-c:v", "copy", "-c:a", "aac", "-b:a", "160k", "-shortest", str(tmp)], check=True)
    os.replace(tmp, out)
    silent.unlink()
    wav.unlink()
    return out


def still(stage, F, png, xray=False, slate=False):
    """One frame as a PNG."""
    surface = skia.Surface(stage.W, stage.H)
    draw_frame(surface.getCanvas(), stage, F, xray, slate)
    Path(png).parent.mkdir(parents=True, exist_ok=True)
    surface.makeImageSnapshot().save(str(png), skia.kPNG)
    return Path(png)


def sheet(stage, frames, png, cols=4, scale=0.25, xray=False):
    """A contact sheet: the given frames side by side, each with its turn label."""
    w, h = int(stage.W * scale), int(stage.H * scale)
    rows = (len(frames) + cols - 1) // cols
    surface = skia.Surface(w * min(cols, len(frames)), h * rows)
    c = surface.getCanvas()
    c.clear(skia.ColorWHITE)
    for k, F in enumerate(frames):
        c.save()
        c.translate((k % cols) * w, (k // cols) * h)
        c.clipRect(skia.Rect.MakeWH(w, h))
        c.scale(scale, scale)
        draw_frame(c, stage, F, xray, True)
        c.restore()
    Path(png).parent.mkdir(parents=True, exist_ok=True)
    surface.makeImageSnapshot().save(str(png), skia.kPNG)
    return Path(png)


def join(root, name, scenes):
    """Join rendered scenes into one file. Same encoder settings throughout, so nothing is re-encoded."""
    listing = root / "out" / (name + ".txt")
    listing.write_text("".join(f"file '{out_path(sc)}'\n" for sc in scenes))
    joined = root / "out" / (name + ".mp4")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", str(listing), "-c", "copy", str(joined)], check=True)
    listing.unlink()
    return joined
