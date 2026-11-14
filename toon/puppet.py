"""The biped rig. A character file supplies colours and hair; poses and expressions are data."""
import math

import skia

from .paper import cut, ink, oval, poly, rrect

POSE_KEYS = ("sh_l", "el_l", "sh_r", "el_r", "lean", "head")
EXPR_KEYS = ("brow", "brow_y", "eye", "look_x", "look_y")
POSE_DEFAULT = dict(sh_l=6, el_l=4, sh_r=6, el_r=4, lean=0, head=0)
EXPR_DEFAULT = dict(brow=0, brow_y=0, eye=1.0, look_x=0.4, look_y=0, mouth="smile", blush=False)

# Anchor heights above the feet, in rig units, used by the camera and speech bubbles.
HEAD_TOP, HEAD_MID, CHEST = 372, 288, 215


def _hair_back(c, ch):
    if ch["hair_style"] == "bob":
        cut(c, rrect(-92, -162, 184, 156, 62), ch["hair"], key=ch["id"] + "hb")


def _hair_front(c, ch):
    p = skia.Path()
    if ch["hair_style"] == "bob":
        p.moveTo(-87, -70)
        p.cubicTo(-92, -198, 92, -198, 87, -70)
        for q in [(70, -108), (44, -98), (14, -118), (-18, -100), (-48, -116), (-72, -100)]:
            p.lineTo(*q)
    else:  # tuft
        p.moveTo(-83, -92)
        p.cubicTo(-88, -192, 88, -192, 83, -92)
        for q in [(52, -124), (12, -132), (-40, -124)]:
            p.lineTo(*q)
        cut(c, poly([(-14, -146), (2, -196), (16, -158), (36, -186), (44, -146)]), ch["hair"], key=ch["id"] + "ht")
    p.close()
    cut(c, p, ch["hair"], key=ch["id"] + "hf")


def _mouth(c, kind, x, y):
    p = skia.Path()
    if kind == "open":
        cut(c, oval(x, y + 4, 9, 11), "#2b2420", shadow=False, rough=0)
        return
    if kind == "grin":
        p.moveTo(x - 19, y - 3)
        p.quadTo(x, y + 24, x + 19, y - 3)
        p.close()
        cut(c, p, "#2b2420", shadow=False, rough=0)
        cut(c, rrect(x - 12, y - 2, 24, 6, 2), "#fbf6ea", shadow=False, rough=0)
        return
    if kind == "smile":
        p.moveTo(x - 15, y)
        p.quadTo(x, y + 13, x + 15, y)
    elif kind == "frown":
        p.moveTo(x - 14, y + 6)
        p.quadTo(x, y - 7, x + 14, y + 6)
    elif kind == "smirk":
        p.moveTo(x - 12, y + 3)
        p.quadTo(x + 5, y + 8, x + 16, y - 6)
    elif kind == "wobble":
        p.moveTo(x - 15, y + 3)
        for i, q in enumerate([(-8, -2), (0, 3), (8, -2), (15, 3)]):
            p.lineTo(x + q[0], y + q[1])
    else:  # flat
        p.moveTo(x - 12, y + 2)
        p.lineTo(x + 12, y + 2)
    ink(c, p, width=5)


def draw_puppet(c, ch, st, t, fps):
    """Draw character `ch` in resolved state `st` at frame `t`. Origin is the feet."""
    k = ch["id"]
    side_face = 1 if st["facing"] == "right" else -1
    s = ch.get("scale", 1.0)
    breath = math.sin(t / fps * 2 * math.pi * 0.28 + ch.get("phase", 0)) * 1.6
    blink = (t + int(ch.get("phase", 0) * 40)) % 100 < 3

    c.save()
    c.translate(st["x"], st["ground"])
    c.scale(s * side_face, s)

    # legs and shoes
    for lx in (-38, 8):
        cut(c, rrect(lx, -98, 30, 96, 8), ch["pants"], key=f"{k}leg{lx}")
        cut(c, oval(lx + 19, -4, 25, 11), ch["shoes"], key=f"{k}shoe{lx}")

    # torso leans from the hips and carries arms and head with it
    c.translate(0, -92)
    c.rotate(st["lean"])
    c.translate(0, 92 + breath)
    cut(c, rrect(-57, -216, 114, 132, 24), ch["top"], key=k + "torso")
    if ch.get("stripe"):
        cut(c, rrect(-57, -150, 114, 16, 0), ch["stripe"], key=k + "stripe", shadow=False)

    # neck sits under the head but over the collar
    cut(c, rrect(-13, -232, 26, 26, 8), ch["skin"], key=k + "neck", shadow=False)

    def arm(side, sh, el):
        c.save()
        c.translate(side * 52, -200)
        c.rotate(-side * sh)
        cut(c, rrect(-12, -10, 24, 64, 12), ch["top"], key=f"{k}ua{side}")
        c.translate(0, 48)
        c.rotate(-side * el)
        cut(c, rrect(-11, -8, 22, 56, 11), ch["top"], key=f"{k}fa{side}")
        cut(c, oval(0, 52, 13, 13), ch["skin"], key=f"{k}hand{side}")
        c.restore()

    arm(-1, st["sh_l"], st["el_l"])
    arm(1, st["sh_r"], st["el_r"])

    # head pivots at the neck
    c.translate(0, -212)
    c.rotate(st["head"])
    c.translate(0, st.get("bob", 0))
    _hair_back(c, ch)
    cut(c, oval(0, -78, 80, 74), ch["skin"], key=k + "head")

    fx = 10  # features sit toward the facing side for a three-quarter view
    for ex in (-30, 30):
        cx, cy = fx + ex, -80
        open_ = 0.08 if blink else st["eye"]
        if open_ < 0.2:
            line = skia.Path()
            line.moveTo(cx - 14, cy + 2)
            line.quadTo(cx, cy + 8, cx + 14, cy + 2)
            ink(c, line, width=4)
        else:
            white = oval(cx, cy, 15, 19 * min(open_, 1.3))
            cut(c, white, "#fbf6ea", shadow=False, rough=0)
            c.save()
            c.clipPath(white, doAntiAlias=True)
            cut(c, oval(cx + st["look_x"] * 6, cy + st["look_y"] * 6, 8.5, 9.5), "#2b2420", shadow=False, rough=0)
            c.restore()
        # brow: `brow` > 0 lowers the inner end (angry), < 0 raises it (worried)
        c.save()
        c.translate(cx, cy - 31 - st["brow_y"])
        c.rotate(st["brow"] if ex < 0 else -st["brow"])
        b = skia.Path()
        b.moveTo(-13, 0)
        b.lineTo(13, 0)
        ink(c, b, color=ch["hair"], width=7)
        c.restore()
    if st.get("blush"):
        for ex in (-44, 44):
            cut(c, oval(fx + ex, -52, 13, 8), "#e8836f", shadow=False, rough=0, alpha=150)
    _mouth(c, st["mouth"], fx, -42)
    _hair_front(c, ch)
    c.restore()
