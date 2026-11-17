"""Bodies: an entity that is a thing, drawn as that thing and moving the way that thing can.

An entity's sheet may name a `body:` (seal, needle, glove, eraser, padlock, bob, hammer, glass). It is then
drawn as that object instead of the featureless token: no face, no attention dot. Everything it shows is
motion. Each body has one way of getting about, and it is the only way that object could:

    seal      lifts and comes down flat, three stamps to a move
    needle    stands on its point, never quite still; leans to what it attends to; tips end over end to travel
    glove     lunges: every move is a punch (`pair: true` is two laced together, which jostle each other)
    eraser    lies flat and rubs back and forth along the ground
    padlock   rocks from corner to corner
    bob       hangs from its own tripod, and swings when the tripod steps
    hammer    rests head down, and flips head over handle
    glass     stands on its handle and rolls on its rim
    match     stands on its end and shuffles; told to lean in, it tips over, strikes its head on the ground, and is alight

A sheet's `size:` scales it (a head of house is bigger, a stub is smaller). Shapes stand on (0, 0), up is
negative y, and fill roughly the same box as a token, so the camera and the speech bubbles need no changes.
"""
import math

import skia

BODIES = ("seal", "needle", "glove", "eraser", "padlock", "bob", "hammer", "glass", "match")
PAPER = "#f5f3ee"


def _rgb(h):
    h = h.lstrip("#")
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def _mix(a, b, k):
    (r1, g1, b1), (r2, g2, b2) = _rgb(a), _rgb(b)
    return "#%02x%02x%02x" % (round(r1 + (r2 - r1) * k), round(g1 + (g2 - g1) * k), round(b1 + (b2 - b1) * k))


class Ink:
    """The paints for one body: its colour, a darker and a lighter step of it, at one opacity and focus."""

    def __init__(self, color, alpha, blur):
        self.color, self.alpha, self.blur = color, alpha, blur
        self.dark, self.light = _mix(color, "#1d1d1f", 0.38), _mix(color, PAPER, 0.62)
        self.mid = _mix(color, PAPER, 0.3)

    def _paint(self, color, a=1.0):
        r, g, b = _rgb(color)
        p = skia.Paint(AntiAlias=True, Color=skia.Color(r, g, b, int(self.alpha * a)))
        if self.blur > 0.05:
            p.setMaskFilter(skia.MaskFilter.MakeBlur(skia.kNormal_BlurStyle, self.blur))
        return p

    def fill(self, color, a=1.0):
        return self._paint(color, a)

    def line(self, color, w, a=1.0):
        p = self._paint(color, a)
        p.setStyle(skia.Paint.kStroke_Style)
        p.setStrokeWidth(w)
        p.setStrokeCap(skia.Paint.kRound_Cap)
        p.setStrokeJoin(skia.Paint.kRound_Join)
        return p


def _poly(*pts):
    p = skia.Path()
    p.moveTo(*pts[0])
    for q in pts[1:]:
        p.lineTo(*q)
    p.close()
    return p


def _rr(c, x, y, w, h, r, paint):
    c.drawRoundRect(skia.Rect.MakeXYWH(x, y, w, h), r, r, paint)


def _seal(c, k, o, t, f, ent):
    going = o["going"]
    if going < 1:
        c.translate(0, -abs(math.sin(going * math.pi * 3)) * 46)          # three stamps to a move
    _rr(c, -36, -30, 72, 30, 4, k.fill(k.color))                         # the die
    _rr(c, -36, -9, 72, 9, 3, k.fill(k.dark))                            # its face, inked
    c.drawPath(_poly((-22, -30), (22, -30), (13, -92), (-13, -92)), k.fill(k.color))
    c.drawCircle(0, -112, 26, k.fill(k.color))                           # the grip
    c.drawCircle(-8, -120, 7, k.fill(k.light, 0.7))


def _needle(c, k, o, t, f, ent):
    going = o["going"]
    quiver = math.sin(t * 23.0 + o["slot"]) * 2.2                         # a needle is never fully still
    if going < 1:
        c.rotate(f * going * 360, 0, -78)                                # tips end over end
    else:
        c.rotate(o["lx"] * 34 + quiver, 0, 0)                             # points at whatever it attends to
    c.drawPath(_poly((0, -156), (14, -78), (-14, -78)), k.fill(k.color))
    c.drawPath(_poly((0, 0), (14, -78), (-14, -78)), k.fill(k.dark, 0.6))
    c.drawCircle(0, -78, 6, k.fill(k.dark))


def _one_glove(c, k, f):
    _rr(c, -26, -56, 52, 56, 6, k.fill(k.dark))                          # the cuff
    for y in (-42, -28, -14):
        c.drawLine(-12, y, 12, y, k.line(k.light, 3, 0.8))                # laces
    _rr(c, -38, -152, 76, 104, 36, k.fill(k.color))                      # the fist
    c.drawOval(skia.Rect.MakeXYWH(f * 30 - 16, -108, 32, 46), k.fill(k.color))   # the thumb
    c.drawLine(-f * 4, -140, -f * 22, -100, k.line(k.dark, 3, 0.35))


def _glove(c, k, o, t, f, ent):
    lunge = o["travel"]
    c.translate(f * lunge * 22, 0)
    c.rotate(f * lunge * 26, 0, 0)                                       # every move is a punch
    if not ent.get("pair"):
        _one_glove(c, k, f)
        return
    jostle = math.sin(t * 8.0) * 7                                       # laced together, they can only hit each other
    c.drawLine(-30, -20, 30, -20, k.line(k.light, 4))                    # the lace between them
    for side in (-1, 1):
        c.save()
        c.translate(side * 34, 0)
        c.rotate(-side * (6 + jostle * side), 0, 0)
        c.scale(0.82, 0.82)
        _one_glove(c, k, -side)
        c.restore()


def _eraser(c, k, o, t, f, ent):
    going = o["going"]
    if going < 1:
        c.translate(math.sin(going * math.pi * 6) * 15, 0)               # rubs back and forth
    c.rotate(-f * 5, 0, 0)
    _rr(c, -50, -46, 100, 46, 9, k.fill(k.color))
    if ent.get("wrapped"):
        _rr(c, -30, -48, 70, 50, 3, k.fill(PAPER))                       # still in its sleeve
        _rr(c, -30, -34, 70, 8, 0, k.fill(k.dark, 0.5))
    else:
        _rr(c, -50, -12, 100, 12, 6, k.fill(k.dark, 0.45))               # the worn edge


def _padlock(c, k, o, t, f, ent):
    going = o["going"]
    if going < 1:
        rock = math.sin(going * math.pi * 4) * 13                        # corner to corner
        c.rotate(rock, 40 if rock > 0 else -40, 0)
    arc = skia.Path()
    arc.moveTo(-23, -84)
    arc.lineTo(-23, -118)
    arc.arcTo(skia.Rect.MakeLTRB(-23, -141, 23, -95), 180, 180, False)
    arc.lineTo(23, -84)
    if ent.get("sprung"):
        c.save()
        c.rotate(-32, -23, -84)                                          # the shackle hangs open
        c.drawPath(arc, k.line(k.dark, 14))
        c.restore()
    else:
        c.drawPath(arc, k.line(k.dark, 14))
    _rr(c, -42, -88, 84, 88, 12, k.fill(k.color))
    c.drawCircle(0, -52, 9, k.fill(k.dark))
    _rr(c, -4, -52, 8, 26, 3, k.fill(k.dark))


def _bob(c, k, o, t, f, ent):
    going, line = o["going"], float(ent.get("line", 1.0))
    c.drawLine(0, -156, -44, 0, k.line(k.dark, 5))                        # its own tripod
    c.drawLine(0, -156, 44, 0, k.line(k.dark, 5))
    c.drawLine(0, -156, 8, -8, k.line(k.dark, 4, 0.6))
    swing = math.sin(going * math.pi * 4) * 22 * (1 - going * 0.6) if going < 1 else 0.0
    if ent.get("swinging"):
        swing += math.sin(t * 2.6) * 16                                  # the one on the long line has not settled
    c.rotate(swing, 0, -156)
    drop = -156 + 78 * line
    c.drawLine(0, -156, 0, drop, k.line(k.dark, 2.5))
    _rr(c, -9, drop - 4, 18, 10, 3, k.fill(k.dark))
    c.drawPath(_poly((-17, drop + 6), (17, drop + 6), (0, drop + 56)), k.fill(k.color))
    c.drawLine(-6, drop + 12, -1, drop + 40, k.line(k.light, 3, 0.7))


def _hammer(c, k, o, t, f, ent):
    going = o["going"]
    if going < 1:
        c.rotate(f * going * 360, 0, -76)                                # head over handle
    _rr(c, -8, -152, 16, 116, 6, k.fill(k.mid))                          # the handle
    _rr(c, -40, -44, 80, 44, 6, k.fill(k.color))                         # the head, resting on the ground
    _rr(c, -40, -12, 80, 12, 4, k.fill(k.dark, 0.6))
    if ent.get("claw"):
        c.drawPath(_poly((-40, -44), (-58, -66), (-48, -40)), k.fill(k.color))
        c.drawPath(_poly((-40, -30), (-62, -46), (-48, -24)), k.fill(k.color))


def _glass(c, k, o, t, f, ent):
    going = o["going"]
    if going < 1:
        c.rotate(f * going * 360, 0, -78)                                # rolls on its rim
    else:
        c.rotate(o["lx"] * 12, 0, 0)
    _rr(c, -8, -62, 16, 62, 6, k.fill(k.dark))                           # the handle it stands on
    c.drawCircle(0, -106, 46, k.fill(k.light, 0.5))                       # the lens
    c.drawCircle(0, -106, 46, k.line(k.color, 11))
    c.drawLine(-22, -128, -8, -138, k.line(PAPER, 5, 0.8))


def _match(c, k, o, t, f, ent):
    going, lean = o["going"], o["lean"]
    if going < 1:
        c.rotate(math.sin(going * math.pi * 6) * 5, 0, 0)                 # a quick shuffle on its end
    strike = min(1.0, abs(lean))
    c.rotate((1 if lean >= 0 else -1) * 24 * math.sin(strike * math.pi) * (1 - 0.5 * strike), 0, 0)   # it tips to strike, and comes back up
    _rr(c, -5, -128, 10, 128, 3, k.fill(k.mid))                           # the stick
    c.drawOval(skia.Rect.MakeXYWH(-10, -152, 20, 30), k.fill(k.color))    # the head
    if strike > 0.55:                                                    # alight
        grow = (strike - 0.55) / 0.45
        flick = 1 + 0.12 * math.sin(t * 31.0)
        c.save()
        c.translate(0, -146)
        c.scale(grow * flick, grow * (2 - flick))
        c.drawPath(_poly((0, -74), (20, -26), (13, 2), (-13, 2), (-20, -26)), k.fill("#f2a33a"))
        c.drawPath(_poly((0, -44), (10, -14), (6, 2), (-6, 2), (-10, -14)), k.fill("#fbe6a2"))
        c.restore()


DRAW = dict(match=_match, seal=_seal, needle=_needle, glove=_glove, eraser=_eraser, padlock=_padlock, bob=_bob, hammer=_hammer, glass=_glass)


def draw_body(c, ent, o, t, x, y, blur=0.0):
    """Draw entity `ent` as its body, standing at (x, y), in pose `o` at time `t`."""
    body = ent["body"]
    if body not in DRAW:
        raise ValueError(f"an entity has no body of kind '{body}'; the kinds are: " + ", ".join(BODIES))
    a = 255 * o["alpha"]
    if a < 1:
        return
    size = float(ent.get("size", 1.0))
    f = 1 if o["facing"] >= 0 else -1
    c.save()
    c.translate(x, y)
    c.scale(o["sx"] * size, o["sy"] * size)
    DRAW[body](c, Ink(ent["color"], a, blur), dict(o, going=o.get("going", 1.0)), t, f, ent)
    c.restore()
