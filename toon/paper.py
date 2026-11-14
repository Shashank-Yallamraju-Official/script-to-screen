"""Paper cut-out drawing primitives: every shape is a piece of paper with a soft shadow."""
import zlib

import numpy as np
import skia


def col(h, a=255):
    h = h.lstrip("#")
    return skia.Color(int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16), a)


def seed_of(key):
    return zlib.crc32(str(key).encode()) % 9973


def rrect(x, y, w, h, r=0):
    p = skia.Path()
    p.addRoundRect(skia.Rect.MakeXYWH(x, y, w, h), r, r)
    return p


def oval(cx, cy, rx, ry):
    p = skia.Path()
    p.addOval(skia.Rect.MakeLTRB(cx - rx, cy - ry, cx + rx, cy + ry))
    return p


def poly(pts):
    p = skia.Path()
    p.moveTo(*pts[0])
    for q in pts[1:]:
        p.lineTo(*q)
    p.close()
    return p


def cut(canvas, path, fill, key=0, shadow=True, rough=1.2, alpha=255):
    """Draw one paper piece. `key` fixes its hand-cut edge so it never boils between frames."""
    eff = skia.DiscretePathEffect.Make(16, rough, seed_of(key)) if rough else None
    if shadow:
        # Keep the shadow falling down-right on screen, however the piece is rotated or flipped.
        m = canvas.getTotalMatrix()
        a, b, c, d = m.getScaleX(), m.getSkewX(), m.getSkewY(), m.getScaleY()
        det = a * d - b * c
        s = abs(det) ** 0.5
        dx, dy = 2.5 * s, 4.0 * s
        lx, ly = (d * dx - b * dy) / det, (-c * dx + a * dy) / det
        p = skia.Paint(AntiAlias=True, Color=skia.Color(40, 25, 10, 80))
        p.setMaskFilter(skia.MaskFilter.MakeBlur(skia.kNormal_BlurStyle, 2.2 * s))
        if eff:
            p.setPathEffect(eff)
        canvas.save()
        canvas.translate(lx, ly)
        canvas.drawPath(path, p)
        canvas.restore()
    p = skia.Paint(AntiAlias=True, Color=col(fill, alpha))
    if eff:
        p.setPathEffect(eff)
    canvas.drawPath(path, p)


def ink(canvas, path, color="#2b2420", width=5):
    """A stroked line (brows, mouths): marker on paper, no shadow."""
    p = skia.Paint(AntiAlias=True, Color=col(color), Style=skia.Paint.kStroke_Style,
                   StrokeWidth=width, StrokeCap=skia.Paint.kRound_Cap,
                   StrokeJoin=skia.Paint.kRound_Join)
    canvas.drawPath(path, p)


def make_grain(w, h, seed=7):
    """Paper fibre texture, multiplied over the finished frame."""
    rng = np.random.default_rng(seed)
    fine = rng.random((h, w))
    coarse = np.kron(rng.random((h // 8 + 1, w // 8 + 1)), np.ones((8, 8)))[:h, :w]
    g = (255 - fine * 16 - coarse * 12).astype(np.uint8)
    rgba = np.dstack([g, g, g, np.full_like(g, 255)])
    return skia.Image.fromarray(np.ascontiguousarray(rgba), colorType=skia.kRGBA_8888_ColorType)


def draw_grain(canvas, grain):
    canvas.drawImage(grain, 0, 0, skia.SamplingOptions(), skia.Paint(BlendMode=skia.BlendMode.kMultiply))
