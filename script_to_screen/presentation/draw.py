"""The bare renderer. An empty frame, a ground line, and one featureless token per entity.

A token shows only what the model says is observable: where it stands, which way its body
faces (the toe at its base), where its attention is (the dot), and how it holds itself.
The small motions on top (flip, stretch, the bubble's pop) are sized by library/feel.yaml.
A line of speech appears whole; an indicator then travels under it in time with the voice.
"""
import math

import skia

from ..world import SLOTS
from . import place
from .bodies import draw_body
from .motion import back, pose, smooth
from .view import ground, slot_x, view

BODY_W, BODY_H = 66, 156
INK, PAPER, RULE = "#1d1d1f", "#f5f3ee", "#c9c5bb"


def col(h, a=255):
    h = h.lstrip("#")
    return skia.Color(int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16), int(a))


def fill(color, a=255, blur=0.0):
    p = skia.Paint(AntiAlias=True, Color=col(color, a))
    if blur > 0.05:
        p.setMaskFilter(skia.MaskFilter.MakeBlur(skia.kNormal_BlurStyle, blur))     # out of focus
    return p


def stroke(color, w, a=255):
    return skia.Paint(AntiAlias=True, Color=col(color, a), Style=skia.Paint.kStroke_Style, StrokeWidth=w,
                      StrokeJoin=skia.Paint.kRound_Join, StrokeCap=skia.Paint.kRound_Cap)


def font(size=28, mono=False):
    return skia.Font(skia.Typeface("DejaVu Sans Mono" if mono else "DejaVu Sans", skia.FontStyle.Bold()), size)


def draw_token(c, ent, o, W, H, feel, blur=0.0, t=0.0):
    if ent.get("body"):                                          # a thing, drawn as that thing: no face, and its own way of moving
        draw_body(c, ent, o, t, slot_x(o["slot"], W), ground(H) - o.get("rise", 0.0), blur)
        return
    a = 255 * o["alpha"]
    if a < 1:
        return
    stretch = o["travel"] * float(feel["squash"])
    thin = 1 - 0.9 * float(feel["flip"]) * o["flip"]
    c.save()
    c.translate(slot_x(o["slot"], W), ground(H) - o.get("rise", 0.0))
    c.skew(-math.tan(math.radians(9 * o["lean"])), 0)            # lean pivots at the base
    c.scale(o["sx"] * (1 + stretch) * thin, o["sy"] * (1 - stretch))
    f = o["facing"]
    if abs(f) > 0.02:                                            # toe: which way the body faces
        toe = skia.Path()
        toe.moveTo(f * 18, -2)
        toe.lineTo(f * (BODY_W / 2 + 20 * abs(f)), -2)
        toe.lineTo(f * 18, -24)
        toe.close()
        c.drawPath(toe, fill(ent["color"], a, blur))
    c.drawRoundRect(skia.Rect.MakeXYWH(-BODY_W / 2, -BODY_H, BODY_W, BODY_H), BODY_W / 2, BODY_W / 2, fill(ent["color"], a, blur))
    c.drawCircle(o["lx"] * 14, -BODY_H + 40 + o["ly"] * 15, 8, fill(INK, a, blur))   # attention
    c.restore()


def draw_note(c, x, y, tone, secs, ring):
    """Shown only on a line that is sung. Its colour and movement follow the tone."""
    m, w = tone.get("motion", "still"), 2 * math.pi * secs
    dx = dy = rot = 0.0
    sc = 1.0
    if m == "bounce":
        dy = -abs(math.sin(w * 1.6)) * 10
    elif m == "sway":
        rot = math.sin(w) * 17
    elif m == "droop":
        rot, dy = 24 + math.sin(w * 0.4) * 4, 5
    elif m == "shake":
        dx, rot, sc = math.sin(w * 11) * 3.5, math.sin(w * 9) * 7, 1.2
    elif m == "tremble":
        dx, dy = math.sin(w * 14) * 1.6, math.cos(w * 17) * 1.6
    elif m == "float":
        dy, sc = math.sin(w * 0.5) * 4, 0.8
    c.save()
    c.translate(x + dx, y + dy)
    c.rotate(rot)
    c.scale(sc, sc)
    c.drawCircle(0, 0, 24, fill("#ffffff"))
    c.drawCircle(0, 0, 24, stroke(ring, 3))
    p = fill(tone.get("color", INK))
    heads = [(-9, 9), (9, 5)] if tone.get("double") else [(-3, 9)]
    for hx, hy in heads:
        c.save()
        c.translate(hx, hy)
        c.rotate(-22)
        c.drawOval(skia.Rect.MakeLTRB(-7.5, -5.5, 7.5, 5.5), p)
        c.restore()
        c.drawRect(skia.Rect.MakeXYWH(hx + 4.5, hy - 23, 3.2, 23), p)
    hx, hy = heads[0]
    pts = [(-4.5, -14), (16.7, -18), (16.7, -12), (-4.5, -8)] if tone.get("double") else \
          [(hx + 4.5, hy - 23), (hx + 16, hy - 15), (hx + 16, hy - 8), (hx + 7.7, hy - 15)]
    flag = skia.Path()
    flag.moveTo(*pts[0])
    for q in pts[1:]:
        flag.lineTo(*q)
    flag.close()
    c.drawPath(flag, p)
    c.restore()


_LAYOUT = {}


def layout(line, tone):
    """Place every syllable once: which row it sits on, how far along, and how wide."""
    size = 21 if tone.get("text") == "small" else 28
    key = (tuple(s["text"] for s in line["sylls"]), size)
    if key not in _LAYOUT:                               # worked out once per wording; the score is never written to
        f, rows, chunks, row, word = font(size), [], [], "", []

        def flush():
            nonlocal row, word
            text = "".join(word)
            if row and f.measureText((row + text).rstrip()) > 470:
                rows.append(row)
                row = ""
            for part in word:
                chunks.append((len(rows), f.measureText(row), part, f.measureText(part.rstrip())))
                row += part
            word = []

        for s in line["sylls"]:
            word.append(s["text"])
            if s["text"].endswith(" "):
                flush()
        flush()
        rows.append(row)
        _LAYOUT[key] = (f, size, max(f.measureText(r.rstrip()) for r in rows), [r.rstrip() for r in rows], chunks)
    return _LAYOUT[key]


WEIGHT = (0.7, 1.0, 1.4)       # the indicator's size on a weak syllable, a strong one, a main accent


def indicator(line, chunks, t):
    """Where the speech indicator is at time t -> (row, x, height 0..1, weight), or None before the line.

    It travels across each syllable for as long as that syllable is voiced, so its speed is the
    rhythm. It glides up and down with the pitch, swells on stressed syllables, and stops and
    shrinks in the breath after punctuation.
    """
    syl = line["sylls"]
    if t < syl[0]["start"] - 1e-6:
        return None
    lo, hi = line["range"]                                       # the whole utterance's range, shared by its bubbles
    height = lambda k: (syl[k]["semi"] - lo) / (hi - lo) if hi > lo else 0.5
    i = max(k for k, s in enumerate(syl) if s["start"] <= t + 1e-6)
    s, prev = syl[i], max(i - 1, 0)
    p = min(1.0, (t - s["start"]) / max(s["voiced"], 1e-3))
    row, cx, _, cw = chunks[i]
    same_row = i + 1 < len(syl) and chunks[i + 1][0] == row
    x = cx + ((chunks[i + 1][1] if same_row else cx + cw) - cx) * p
    g = smooth(min(1.0, p / 0.35))                              # glide into this syllable's pitch and weight
    h = height(prev) + (height(i) - height(prev)) * g
    w = WEIGHT[syl[prev]["stress"]] + (WEIGHT[s["stress"]] - WEIGHT[syl[prev]["stress"]]) * g
    rest = t - (s["start"] + s["voiced"])
    if rest > 0:                                                # the breath: it waits, smaller
        w *= 1 - 0.45 * smooth(min(1.0, rest / 0.08))
    return row, x, h, w


def bubble_box(stage, line, o, cam):
    """Where a bubble sits in the frame for a speaker in state `o`, and how its text is laid out inside it.
    A bubble is lettering, not scenery: it follows its speaker but stays the same size however close the camera is."""
    feel, tone = stage.look.feel, stage.look.tones[line["tone"]]
    f, size, tw, rows, chunks = layout(line, tone)
    W, H, pad = stage.W, stage.H, 22
    lift, rad = float(feel["cursor_lift"]), float(feel["cursor_size"])
    marked = stage.look.style.get("indicator", "fill") in ("dot", "trace")
    lane = lift + 2 * rad * WEIGHT[2] + 4 if marked else 8       # room under each row, for the styles that draw something there
    lh = size + 6 + lane
    w, h = max(150, tw + 2 * pad), len(rows) * lh + 2 * pad - 14
    hx, top = cam.point(slot_x(o["slot"], W), ground(H) - o.get("rise", 0.0) - BODY_H * o["sy"])
    off = hx < -20 or hx > W + 20                                # the speaker is out of frame: the line comes in from that edge
    hx, top = min(max(hx, 64), W - 64), min(max(top - 24, h + 60), H * 0.72) if not off else H * 0.46
    bx = min(max(hx - w / 2, 24), W - w - 40)
    by = top - h - 24
    return dict(f=f, size=size, rows=rows, chunks=chunks, pad=pad, lift=lift, rad=rad, lh=lh, w=w, h=h, hx=hx, top=top, bx=bx, by=by)


def bubbles_showing(stage, t):
    """The bubbles on screen at time t, oldest first, each with how present it is (0 to 1). A bubble eases in
    as its line begins and lingers, fading, after it ends, so one gives way to the next instead of being swapped for it."""
    feel = stage.look.feel
    pop, fade = float(feel["bubble_pop"]), float(feel.get("bubble_fade", 0.0))
    out, speech = [], stage.score.speech
    for k, line in enumerate(speech):
        if line["start"] - 1e-9 <= t < line["end"] + fade:
            there = smooth((t - line["start"]) / pop) if pop > 0 else 1.0
            if t > line["end"]:
                nxt = speech[k + 1] if k + 1 < len(speech) else None
                same = nxt and nxt["who"] == line["who"] and abs(nxt["start"] - line["end"]) < 1e-6
                there *= 1 - smooth((t - line["end"]) / (min(fade, 0.16) if same else fade))    # when the same speaker goes straight on, the old bubble clears quickly so two are never read at once
            if there > 0.004:
                out.append((line, there))
    return out


def draw_bubble(c, stage, line, t, o, ent, cam, there=1.0):
    feel, tone = stage.look.feel, stage.look.tones[line["tone"]]
    g = bubble_box(stage, line, o, cam)
    f, size, rows, chunks, pad, lift, rad, lh = (g[k] for k in ("f", "size", "rows", "chunks", "pad", "lift", "rad", "lh"))
    w, h, hx, top, bx, by = (g[k] for k in ("w", "h", "hx", "top", "bx", "by"))
    tx = min(max(hx, bx + 36), bx + w - 36)
    box = skia.Path()
    box.addRoundRect(skia.Rect.MakeXYWH(bx, by, w, h), 18, 18)
    tail = skia.Path()
    tail.moveTo(tx - 15, by + h - 2)
    tail.lineTo(tx + 15, by + h - 2)
    tail.lineTo(hx, top)
    tail.close()
    shape = skia.Op(box, tail, skia.PathOp.kUnion_PathOp)
    age = t - line["start"]
    pop = float(feel["bubble_pop"])
    c.saveLayerAlpha(None, int(255 * max(0.0, min(1.0, there))))  # the whole bubble fades as one thing
    if pop > 0 and age < pop:                                    # it grows gently out of the speaker, with no bounce
        s = 0.86 + 0.14 * smooth(age / pop)
        c.translate(hx, top)
        c.scale(s, s)
        c.translate(-hx, -top)
    c.drawPath(shape, fill("#ffffff"))
    c.drawPath(shape, stroke(ent["color"], 4))
    style = stage.look.style.get("indicator", "fill")            # how the voice is shown moving through the words
    ink = fill(INK)
    end = line["sylls"][-1]["start"] + line["sylls"][-1]["voiced"]
    fade = 1 - smooth((t - end) / 0.3) if t > end else 1.0       # it leaves once the line is said
    here = indicator(line, chunks, min(t, end))
    base = lambda r: by + pad + size - 6 + r * lh                 # a row's text baseline

    def place(q):                                                # indicator -> a point under its row
        row, x, hgt, wt = q
        return bx + pad + x, by + pad + size + 4 + row * lh + rad * WEIGHT[2] + (1 - hgt) * lift, rad * wt

    if style == "pill" and here and fade > 0.01:                 # a soft block of the speaker's colour sits behind the syllable being said
        i = max(k for k, s in enumerate(line["sylls"]) if s["start"] <= min(t, end) + 1e-6)
        s, (row, x0, _, cw) = line["sylls"][i], chunks[i]
        g = smooth(min(1.0, (min(t, end) - s["start"]) / max(0.35 * s["voiced"], 1e-3)))
        prow, px0, _, pcw = chunks[max(i - 1, 0)]
        if prow == row and i:                                    # it slides from the last syllable on the same row
            x0, cw = px0 + (x0 - px0) * g, pcw + (cw - pcw) * g
        grow = 2 + 3 * WEIGHT[s["stress"]]                       # a stressed syllable gets a taller block
        c.drawRoundRect(skia.Rect.MakeXYWH(bx + pad + x0 - 5, base(row) - size + 2 - grow, cw + 10, size + 6 + 2 * grow), 9, 9,
                        fill(ent["color"], 95 * fade))
    if style == "fill":                                          # the words wait in grey and take ink as they are said
        for r, text in enumerate(rows):
            c.drawString(text, bx + pad, base(r), f, fill(INK, 70))
        if here:
            soft = 16.0                                              # the ink arrives over this many pixels, so no letter is sliced in two
            for r, text in enumerate(rows[:here[0] + 1]):
                edge = bx + w if r < here[0] else bx + pad + here[1] + soft * 0.5
                box = skia.Rect.MakeLTRB(bx, base(r) - size - 6, bx + w, base(r) + size)
                c.saveLayer(box, None)
                c.drawString(text, bx + pad, base(r), f, ink)
                wipe = skia.Paint(BlendMode=skia.BlendMode.kDstIn, Shader=skia.GradientShader.MakeLinear(
                    [skia.Point(edge - soft, 0), skia.Point(edge, 0)], [skia.ColorBLACK, skia.ColorTRANSPARENT]))
                c.drawRect(box, wipe)
                c.restore()
    else:
        for r, text in enumerate(rows):                          # the whole line is there from the start
            c.drawString(text, bx + pad, base(r), f, ink)
    if style == "trace" and here:                                # the voice leaves a line under the words: its height is pitch, its weight is stress
        t0, n = line["sylls"][0]["start"], max(2, int((min(t, end) - line["sylls"][0]["start"]) * 240))
        for k in range(n + 1):
            q = indicator(line, chunks, t0 + (min(t, end) - t0) * k / n)
            if q:
                x, y, r = place(q)
                c.drawCircle(x, y, max(1.2, r * 0.42), fill(ent["color"], 255))
        x, y, r = place(here)
        c.drawCircle(x, y, r * 0.75, fill(INK, 255 * fade))      # the tip, where the voice is now
    if style == "dot" and here and fade > 0.01:
        n, span = 16, float(feel["cursor_tail"])
        for k in range(n, 0, -1):                                # a short tail shows which way it is moving
            past = indicator(line, chunks, min(t, end) - span * k / n) if span > 0 else None
            if past and past[0] == here[0]:
                x, y, r = place(past)
                c.drawCircle(x, y, r * (1 - 0.6 * k / n), fill(INK, 110 * fade * (1 - k / n)))
        x, y, r = place(here)
        c.drawCircle(x, y, r, fill(INK, 255 * fade))                # dark, so it reads on any speaker's bubble
    if line["sung"]:
        draw_note(c, bx + w - 2, by + 2, tone, max(age, 0), ent["color"])
    c.restore()


def draw_xray(c, stage, states):
    """Director's view, kept below the ground line: weight in the room, and felt against shown."""
    W, gy = stage.W, ground(stage.H)
    for s in range(SLOTS):
        x = slot_x(s, W)
        c.drawLine(x, gy, x, gy + 7, stroke(RULE, 2))
    for e, o in states.items():
        info, x = o["info"], slot_x(o["slot"], W)
        if o["alpha"] < 0.5:
            continue
        if info["weight"] is not None:                          # bar: share of the room's weight
            c.drawRoundRect(skia.Rect.MakeXYWH(x - 32, gy + 16, 64, 6), 3, 3, fill(RULE))
            c.drawRoundRect(skia.Rect.MakeXYWH(x - 32, gy + 16, 64 * info["weight"], 6), 3, 3, fill(INK))
        if info["felt"]:                                        # ringed pip = felt, filled pip = shown
            color, n = stage.look.emotions.get(info["felt"], INK), max(info["intensity"], info["level"])
            for i in range(n):                                  # a small solid pip = amplified beyond what is felt
                px = x + (i - (n - 1) / 2) * 16
                if i < info["level"]:
                    c.drawCircle(px, gy + 38, 5.5 if i < info["intensity"] else 3.5, fill(color))
                if i < info["intensity"]:
                    c.drawCircle(px, gy + 38, 5.5, stroke(color, 2))


# ---- music you can see ---------------------------------------------------------------------------
# Sound that something visible causes needs no mark: the motion is the mark. Music has no visible
# source, so the look gives it one: `style: {music: [line, frame]}` in show.yaml, any of line, rings, frame, or none.
RING_GOOD, RING_ASK = "#e0a01e", "#2f9e8f"
MUSIC_SHOWN = ("line", "frame")          # unless the show says otherwise


def music_shown(stage):
    """The ways this show draws its music."""
    v = stage.look.style.get("music", MUSIC_SHOWN)
    return tuple(x for x in ([v] if isinstance(v, str) else v) if x != "none")


def music_marks(stage):
    """Each cue with where it is aimed: the place its subject stands as the moment lands."""
    if getattr(stage, "_marks", None) is None:
        cues, marks = stage.score.music, []
        for k, c in enumerate(cues):
            lands = c["t"] + c.get("length", 0)
            who = c["subject"] if isinstance(c["subject"], str) else c["subject"][0]
            o = pose(stage, who, lands + 0.01) or {}
            later = [n["t"] for n in cues[k + 1:] if n["kind"] != "rise"]
            marks.append(dict(c, x=slot_x(o.get("slot", (SLOTS - 1) / 2), stage.W), lands=lands,
                              until=lands if c["kind"] == "rise" else min(c["t"] + 3.0, later[0]) if c["kind"] == "question" and later
                              else lands + (3.0 if c["kind"] == "question" else 1.4)))
        stage._marks = marks
    return stage._marks


def ground_line(c, stage, t, marks, rule=RULE):
    """The ground, drawn as a string the music plays. A build-up makes it hum, tighter and faster, toward where
    the moment will land; the moment itself sends one ripple outward, down for bad news and up for good."""
    W, gy = stage.W, ground(stage.H)
    live = [m for m in marks if m["t"] <= t <= m["until"]]
    if not live:
        return c.drawLine(-W, gy, 2 * W, gy, stroke(rule, 2))
    path, loud = skia.Path(), 0.0
    for i in range(0, W + 4, 4):
        y = 0.0
        for m in live:
            if m["kind"] == "rise":
                p = (t - m["t"]) / max(m["length"], 1e-3)
                wide = 620 - 500 * p                                  # it gathers toward the spot
                y += 26 * p * p * m["strength"] * math.exp(-((i - m["x"]) / wide) ** 2) * math.sin(i / (16 - 9 * p) - t * (14 + 40 * p))
                loud = max(loud, p * p)
            elif m["kind"] == "question":
                fade = 1 - (t - m["t"]) / (m["until"] - m["t"])
                y += 5 * fade * math.exp(-((i - m["x"]) / 260) ** 2) * math.sin(i / 9 - t * 26)
                loud = max(loud, 0.4 * fade)
            else:
                age = t - m["t"]
                front = abs(i - m["x"]) - 900 * age                    # one ripple runs outward from whoever it is about
                y += (1 if m["kind"] == "turn.bad" else -1) * 44 * m["strength"] * math.exp(-age / 0.45) * math.exp(-(front / 70) ** 2)
                loud = max(loud, math.exp(-age / 0.45))
        (path.moveTo if i == 0 else path.lineTo)(i, gy + y)
    c.drawLine(-W, gy, 2 * W, gy, stroke(rule, 2, 255 * (1 - 0.8 * loud)))       # the line at rest fades as the played line takes over
    c.drawPath(path, stroke(INK, 2 + 1.5 * loud, 60 + 150 * loud))


def rings(c, stage, t, marks):
    """Rings that draw in toward where a moment will land while it builds, and one that bursts outward when it does."""
    cy = ground(stage.H) - BODY_H / 2
    for m in marks:
        if not m["t"] <= t <= m["until"]:
            continue
        if m["kind"] == "rise":
            p = (t - m["t"]) / max(m["length"], 1e-3)
            for k in range(3):
                u = (p * 2.5 + k / 3) % 1                              # each ring shrinks to the spot, then another starts
                c.drawCircle(m["x"], cy, 40 + 520 * (1 - u), stroke(INK, 2, 150 * p * u))
        else:
            age = t - m["t"]
            color = INK if m["kind"] == "turn.bad" else RING_GOOD if m["kind"] == "turn.good" else RING_ASK
            c.drawCircle(m["x"], cy, 50 + 760 * age, stroke(color, 5 if m["kind"] == "turn.bad" else 3, 230 * m["strength"] * max(0.0, 1 - age / 1.1)))


def frame_bars(c, stage, t, marks):
    """The frame closes in while a moment builds, and springs open as it lands."""
    amount = 0.0
    for m in marks:
        if m["kind"] == "rise" and m["t"] <= t <= m["lands"] + 0.25:
            p = min(1.0, (t - m["t"]) / max(m["length"], 1e-3))
            amount = max(amount, p ** 1.5 if t <= m["lands"] else 1 - back((t - m["lands"]) / 0.25, 1.0))
    if amount > 0.002:
        h = stage.H * 0.11 * amount
        c.drawRect(skia.Rect.MakeWH(stage.W, h), fill(INK))
        c.drawRect(skia.Rect.MakeXYWH(0, stage.H - h, stage.W, h), fill(INK))


def hits(stage, F):
    """What is where in frame F, front to back: [{kind, box: [x, y, w, h], ...}] in frame pixels.
    kind is `syllable` (with `line`, the bubble, and `n`, its place in that bubble from 0), `bubble`, or `token` (with `entity`).
    This is how a click on the picture finds the thing it landed on."""
    t = F / stage.fps
    states = {e: s for e in stage.score.pose if (s := pose(stage, e, t)) is not None and s["alpha"] > 0.5}
    out, line = [], stage.score.line_at(t)
    cam = view(stage, t)
    if line and line["who"] in states:
        g = bubble_box(stage, line, states[line["who"]], cam)
        for n, (row, x0, _, width) in enumerate(g["chunks"]):
            out.append(dict(kind="syllable", line=line, n=n, box=[g["bx"] + g["pad"] + x0, g["by"] + g["pad"] - 8 + row * g["lh"], max(width, 6), g["lh"]]))
        out.append(dict(kind="bubble", line=line, box=[g["bx"], g["by"], g["w"], g["h"]]))
    for e, o in states.items():
        w, h = (BODY_W * o["sx"] + 24) * cam.zoom, BODY_H * o["sy"] * cam.zoom
        fx, fy = cam.point(slot_x(o["slot"], stage.W), ground(stage.H))
        out.append(dict(kind="token", entity=e, box=[fx - w / 2, fy - h, w, h]))
    return out


SWELL_STEPS = 16                                                 # how long a thing swells for before it bursts: two bars


def grade(c, stage, W, H):
    """The last pass over the picture, under the lettering: the scene's tint, darker corners, and a little paper grain."""
    room = stage.look.place or {}
    tint = room.get("grade")
    if tint:
        c.drawRect(skia.Rect.MakeWH(W, H), skia.Paint(Color=col(place.mix("#ffffff", tint.get("color", "#8aa0b8"), float(tint.get("amount", 0.2)))), BlendMode=skia.BlendMode.kMultiply))
    dark = float(room.get("vignette", 0))
    if dark > 0:                                                 # the same every frame: painted once and kept
        kept = getattr(stage, "_vignette", None)
        if kept is None or kept[0] != dark:
            surf = skia.Surface(W, H)
            surf.getCanvas().drawRect(skia.Rect.MakeWH(W, H), skia.Paint(Shader=skia.GradientShader.MakeRadial(
                skia.Point(W / 2, H * 0.48), W * 0.72, [skia.Color(10, 6, 12, 0), skia.Color(10, 6, 12, 0), skia.Color(10, 6, 12, int(210 * dark))], [0.0, 0.5, 1.0])))
            kept = stage._vignette = (dark, surf.makeImageSnapshot())
        c.drawImage(kept[1], 0, 0)
    grain = float(stage.look.style.get("grain", 0))
    if grain > 0:
        img = getattr(stage.look, "_grain", None)
        if img is None:
            import numpy as np
            v = np.repeat(np.repeat(np.random.default_rng(2).integers(96, 160, (H // 2, W // 2), dtype=np.uint8), 2, axis=0), 2, axis=1)     # at full size, so it is copied and not stretched
            img = stage.look._grain = skia.Image.fromarray(np.ascontiguousarray(np.dstack([v, v, v, np.full_like(v, 255)])), colorType=skia.kRGBA_8888_ColorType)
        c.drawImage(img, 0, 0, skia.SamplingOptions(), skia.Paint(BlendMode=skia.BlendMode.kOverlay, Alphaf=min(1.0, grain)))


def seat(stage, states, bench):
    """Who is at the room's raised bench. -> (states, those sat up behind it, those standing on it). Whoever stands along a bench
    sits up behind it; an entity that `climbs` does not sit: it jumps up onto it, from either end."""
    seated, up = [], []
    if not bench:
        return states, seated, up
    states = dict(states)
    for e, s in list(states.items()):
        if stage.look.cast[e].get("climbs"):
            near = min(s["slot"] - float(bench["from"]), float(bench["to"]) - s["slot"]) + 0.5
            top = place.bench_top(bench) * smooth(near)
            states[e] = dict(s, rise=top + 120 * s.get("travel", 0.0))
            if near > 0:
                up.append(e)
        elif float(bench["from"]) <= s["slot"] <= float(bench["to"]):
            states[e] = dict(s, rise=float(bench.get("rise", 58)))
            seated.append(e)
    return states, seated, up


def shot_in(stage, states, room, bench, up, t):
    """An entity whose sheet says `shot: true` does not walk in. It is shot in like an arrow, foot first, and sticks where it lands,
    quivering upright; on a bench it lands on the bench. If its turn says `through: <slot>` it comes through whatever hangs over
    that window (see place.pierced) and is not seen until it does. Otherwise it comes out of the arch the light is in, growing as
    it nears. -> states."""
    W = stage.W
    went = place.pierced(stage, 1e9)                               # which window, if any (asked of the end of time, so it has always happened)
    for e, s in list(states.items()):
        if not stage.look.cast[e].get("shot") or s.get("arriving") is None:
            continue
        u, to_slot = s["arriving"], s["to"]
        if went:
            if u < place.HIDDEN:                                  # still outside: out of the picture altogether
                states[e] = dict(s, slot=-60.0)
                continue
            v, from_slot, high, small = min(1.0, (u - place.HIDDEN) / (FLIGHT - place.HIDDEN)) ** 1.25, went[0], place.FLOOR_UP + 300.0, 0.85
        else:
            v, from_slot, high, small = min(1.0, u / FLIGHT) ** 1.25, float((room.get("light") or {}).get("at", to_slot - 3)), place.FLOOR_UP + 250.0, 0.3
        on_bench = bench and float(bench["from"]) <= to_slot <= float(bench["to"])
        low = place.bench_top(bench) if on_bench else 0.0
        angle = math.degrees(math.atan2(-(slot_x(to_slot, W) - slot_x(from_slot, W)), high - low))       # foot toward where it is going
        w = max(0.0, (u - FLIGHT) / (1 - FLIGHT))                 # the flight is the first part of the entrance; the rest is the quiver
        size = small + (1 - small) * v
        states[e] = dict(s, slot=from_slot + (to_slot - from_slot) * v, rise=high + (low - high) * v, sx=s["sx"] * size, sy=s["sy"] * size,
                         spin=angle if v < 1 else angle * math.exp(-6 * w) * math.cos(w * 20))
        if e not in up:
            up.append(e)                                          # it comes over everyone's heads
    return states


FLIGHT = 0.42                                                    # how much of an entrance the flight takes


def light(c, stage, states, room, bench, seated, up, t):
    """The room's one light on the entities: each gets a lit side, and throws a shadow away from it. -> states, each told how it is lit.
    With `cast` on the light, the sun or moon is behind the room and the shadows fall across the floor toward us, each the shape of
    what throws it; without, each is a soft patch on the wall behind and the floor beneath."""
    lamp, cool = room.get("light"), room.get("shadow")
    if not lamp:
        return states
    W, H = stage.W, stage.H
    side = -1 if lamp.get("side", "left") == "left" else 1
    k = float(lamp.get("strength", 0.7))
    cast = float(lamp.get("cast", 0))
    if cast:
        lean, y0 = place.cast_lean(lamp), ground(H) - place.FLOOR_UP + 46 * cast
        r, g, b = place.rgb(place.shade_of(room))
        c.saveLayer(skia.Rect.MakeLTRB(-W, ground(H) - 30, 2 * W, 1.4 * H), skia.Paint(Alphaf=place.SHADE * k,       # only the floor: a layer the size of the frame is slow
                                     ColorFilter=skia.ColorFilters.Blend(skia.Color(r, g, b), skia.BlendMode.kSrcIn)))
        went = place.pierced(stage, t)
        c.clipPath(place.sunlit(stage, went and went[0]), True)                    # a shadow shows only where light would have fallen: the rest of the floor is already in the wall's shade
        if bench:                                                # the bench's own, and everyone at it
            tall = place.bench_top(bench)
            x0, x1 = slot_x(float(bench["from"]), W) - 70, slot_x(float(bench["to"]), W) + 70
            c.drawPath(skia.Path().addPoly([skia.Point(x0, y0 - 16), skia.Point(x1, y0 - 16), skia.Point(x1 + lean * tall, y0 + cast * tall), skia.Point(x0 + lean * tall, y0 + cast * tall)], True), fill("#000000"))
        for e, s in states.items():
            high = s.get("rise", 0.0)
            on_floor = not bench or e not in seated and e not in up
            c.save()
            c.translate(slot_x(s["slot"], W) + lean * high, (ground(H) if on_floor else y0) + cast * high)
            c.concat(skia.Matrix().setAll(1, -lean, 0, 0, -cast, 0, 0, 0, 1))
            draw_body(c, stage.look.cast[e], {k2: v for k2, v in s.items() if k2 not in ("ink", "lit")}, t, 0, 0)
            c.restore()
        c.restore()
    out = {}
    for e, s in states.items():
        out[e] = dict(s, lit=(side, k, lamp.get("color", "#f6c26b"), cool))
        if cast:
            continue
        x, y = slot_x(s["slot"], W), ground(H) - s.get("rise", 0.0)
        soft = skia.Paint(AntiAlias=True, Color=col(place.mix(cool, "#120c14", 0.35) if cool else "#120c14", 95 * k * s["alpha"]), MaskFilter=skia.MaskFilter.MakeBlur(skia.kNormal_BlurStyle, 10))
        c.drawOval(skia.Rect.MakeXYWH(x - side * 26 - 44, y - 150, 88, 150), soft)            # on the wall behind it
        if not s.get("rise"):
            c.drawOval(skia.Rect.MakeXYWH(x - side * 30 - 46, y - 7, 92, 18), soft)           # and on the floor under it
    return out


def swell(c, stage, states, t):
    """Whatever is about to go off (a `blast` on it, within two bars) swells first: slowly, glowing, and shaking harder as it
    fills, until the frame shakes with it. -> states, with that one grown."""
    W, H = stage.W, stage.H
    step = stage.score.step
    own = {round(fx["start"] * step, 4): fx["len"] for turn in stage.score.turns for fx in turn.get("sfx") or [] if fx["sound"] == "blast" and fx["len"]}     # a blast can say how long it swells
    coming = next(((at, who, (own.get(round(at, 4)) or SWELL_STEPS) * step) for at, name, who, _ in stage.score.events if name == "blast" and who in states
                   and t < at <= t + (own.get(round(at, 4)) or SWELL_STEPS) * step), None)
    if not coming:
        return states
    long = coming[2]
    k = 1 - (coming[0] - t) / long
    grow, shake = 1 + 1.5 * k ** 1.4, 1 + 0.035 * k * math.sin(t * 70)
    s = states[coming[1]]
    states = dict(states, **{coming[1]: dict(s, sx=s["sx"] * grow * shake, sy=s["sy"] * grow / shake)})
    gx, gy, gr = slot_x(s["slot"], W), ground(H) - s.get("rise", 0.0) - 110 * grow, 60 + 330 * k
    c.drawCircle(gx, gy, gr, skia.Paint(AntiAlias=True, Shader=skia.GradientShader.MakeRadial(
        skia.Point(gx, gy), gr, [col("#fff3c4", 200 * k), col("#f2a33a", 110 * k), col("#f2a33a", 0)], [0.0, 0.45, 1.0])))
    c.translate(5 * k * k * math.sin(t * 83), 4 * k * k * math.cos(t * 71))
    return states


def bench_front(c, stage, states, bench, seated, edge):
    """The bench's front, between whoever sits at it and us, with a plate at each seat: a name if the entity has one, else its colour."""
    W, H = stage.W, stage.H
    rise, front = float(bench.get("rise", 58)), float(bench.get("front", 30))
    x0, x1, y0 = slot_x(float(bench["from"]), W) - 62, slot_x(float(bench["to"]), W) + 62, ground(H) - rise - front
    wood = bench.get("color", "#a08a70")
    boards = ((x0, y0, x1, ground(H) + 8), (x0 - 8, y0 - 9, x1 + 8, y0 + 3), (x0 - 16, ground(H) - 6, x1 + 16, ground(H) + 10))
    for r, shade in zip(boards, (0.0, 0.3, 0.18)):
        c.drawRect(skia.Rect.MakeLTRB(*r), fill(place.mix(wood, "#2e2a24", shade) if shade else wood))
    if edge:
        for r in boards:
            c.drawRect(skia.Rect.MakeLTRB(*r), place.pen(edge, 3))
    for e in seated:
        px, ent = slot_x(round(states[e]["slot"]), W), stage.look.cast[e]
        c.drawRoundRect(skia.Rect.MakeXYWH(px - 30, y0 + 16, 60, 26), 4, 4, fill("#f1e9dc", 255 * states[e]["alpha"]))
        if ent.get("plate"):
            f = font(15)
            c.drawString(str(ent["plate"]), px - f.measureText(str(ent["plate"])) / 2, y0 + 35, f, fill(INK, 230 * states[e]["alpha"]))
        else:
            c.drawCircle(px, y0 + 29, 7, fill(ent["color"], 255 * states[e]["alpha"]))


def fireball(c, stage, s, age):
    """An explosion, `age` seconds after it went off: from where it started, out past the edges of the frame."""
    bx, by, r = slot_x(s["slot"], stage.W), ground(stage.H) - 200 - s.get("rise", 0.0), 230 + 2300 * age
    c.drawCircle(bx, by, r, skia.Paint(AntiAlias=True, Shader=skia.GradientShader.MakeRadial(
        skia.Point(bx, by), r, [col("#fffdf6"), col("#fffdf6"), col("#fbe6a2"), col("#f2a33a"), col("#f2a33a", 0)], [0.0, 0.5, 0.72, 0.9, 1.0])))


def draw_frame(c, stage, F, xray=False, slate=False):
    W, H, t, feel = stage.W, stage.H, F / stage.fps, stage.look.feel
    c.clear(col(PAPER))
    cam = view(stage, t)
    housed = place.draw_behind(c, stage, cam, t)                    # the room, if the scene is somewhere
    c.save()
    cam.apply(c)                                                 # from here to the restore, everything is on the stage and seen through the camera
    seen = music_shown(stage)                                    # how music is shown, if at all
    marks = music_marks(stage) if seen else []
    rule = place.mix(stage.look.place.get("floor", "#d6cdbb"), "#2e2a24", 0.22) if housed and stage.look.style.get("place", "wash") != "line" else RULE
    if "line" in seen:
        ground_line(c, stage, t, marks, rule)
    else:
        c.drawLine(-W, ground(H), 2 * W, ground(H), stroke(rule, 2))
    if "rings" in seen:
        rings(c, stage, t, marks)
    states = {e: s for e in stage.score.pose if (s := pose(stage, e, t)) is not None}
    room = (stage.look.place or {}) if housed else {}
    bench, edge = (stage.look.place or {}).get("bench"), room.get("ink")
    states, seated, up = seat(stage, states, bench)
    states = shot_in(stage, dict(states), room, bench, up, t)
    if edge:
        states = {e: dict(s, ink=edge) for e, s in states.items()}
    states = light(c, stage, states, room, bench, seated, up, t)
    burst = next(((at, who) for at, name, who, _ in stage.score.events if name == "blast" and at <= t), None)     # an explosion, once it has gone off
    states = swell(c, stage, states, t)
    if burst:
        age = t - burst[0]
        c.translate(22 * math.exp(-age / 0.12) * math.sin(age * 95), 16 * math.exp(-age / 0.12) * math.cos(age * 81))    # the frame is thrown
    if xray:
        draw_xray(c, stage, states)
    line = stage.score.line_at(t)
    focal, dim, lead = None, 0.0, 0.28                           # everyone else recedes for a featured reaction, and returns, over this long
    for a0, a1, who in stage.score.focus:
        if a0 - lead / 2 <= t <= a1 + lead / 2:
            focal = who
            dim = float(feel["focus_dim"]) * smooth((t - a0 + lead / 2) / lead) * (1 - smooth((t - a1 + lead / 2) / lead))
    soft = min(1.0, max(0.0, (cam.zoom - 1.9) / 0.8)) if cam.on else 0.0     # in a close shot, whoever it is not a shot of goes out of focus
    def token(e):
        o = states[e] if e == focal or not dim else dict(states[e], alpha=states[e]["alpha"] * (1 - dim))
        draw_token(c, stage.look.cast[e], o, W, H, feel, 0.0 if e in cam.on else 2.2 * soft, t)

    for e in sorted(states, key=lambda e: (e in cam.on, bool(line and line["who"] == e))):
        if e not in up:
            token(e)
    if bench:
        bench_front(c, stage, states, bench, seated, edge)
    for e in up:                                                 # on the bench: in front of it, and of everyone sat behind it
        token(e)
    if burst and burst[1] in states:
        fireball(c, stage, states[burst[1]], t - burst[0])
    c.restore()
    if housed:
        place.draw_in_front(c, stage, cam)
    if housed:
        grade(c, stage, W, H)
    for said, there in bubbles_showing(stage, t):                # a bubble that has ended is still fading as the next one grows
        if said["who"] in states:
            draw_bubble(c, stage, said, t, states[said["who"]], stage.look.cast[said["who"]], cam, there)
    if "frame" in seen:
        frame_bars(c, stage, t, marks)
    if burst:                                                    # then nothing but light, settling to bare paper
        age = t - burst[0]
        c.drawRect(skia.Rect.MakeWH(W, H), fill(place.mix("#fffdf6", PAPER, smooth((age - 0.5) / 0.8)), 255 * smooth((age - 0.2) / 0.3)))
    if slate:
        turn = stage.score.turn_at(t)
        c.drawString(f"T{turn['id']} · {t / stage.score.step - turn['start']:.2f}", 20, 32, font(16, mono=True), fill(INK, 150))
