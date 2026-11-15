"""The bare renderer. An empty frame, a ground line, and one featureless token per entity.

A token shows only what the model says is observable: where it stands, which way its body
faces (the toe at its base), where its attention is (the dot), and how it holds itself.
The small motions on top (flip, stretch, the bubble's pop) are sized by library/feel.yaml.
A line of speech appears whole; an indicator then travels under it in time with the voice.
"""
import math

import skia

from ..world import SLOTS
from .motion import back, pose, smooth

BODY_W, BODY_H, MARGIN = 66, 156, 170
INK, PAPER, RULE = "#1d1d1f", "#f5f3ee", "#c9c5bb"


def col(h, a=255):
    h = h.lstrip("#")
    return skia.Color(int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16), int(a))


def fill(color, a=255):
    return skia.Paint(AntiAlias=True, Color=col(color, a))


def stroke(color, w, a=255):
    return skia.Paint(AntiAlias=True, Color=col(color, a), Style=skia.Paint.kStroke_Style, StrokeWidth=w,
                      StrokeJoin=skia.Paint.kRound_Join, StrokeCap=skia.Paint.kRound_Cap)


def slot_x(slot, W):
    return MARGIN + slot * (W - 2 * MARGIN) / (SLOTS - 1)


def ground(H):
    return round(H * 0.78)


def font(size=28, mono=False):
    return skia.Font(skia.Typeface("DejaVu Sans Mono" if mono else "DejaVu Sans", skia.FontStyle.Bold()), size)


def draw_token(c, ent, o, W, H, feel):
    a = 255 * o["alpha"]
    if a < 1:
        return
    stretch = o["travel"] * float(feel["squash"])
    thin = 1 - 0.9 * float(feel["flip"]) * o["flip"]
    c.save()
    c.translate(slot_x(o["slot"], W), ground(H))
    c.skew(-math.tan(math.radians(9 * o["lean"])), 0)            # lean pivots at the base
    c.scale(o["sx"] * (1 + stretch) * thin, o["sy"] * (1 - stretch))
    f = o["facing"]
    if abs(f) > 0.02:                                            # toe: which way the body faces
        toe = skia.Path()
        toe.moveTo(f * 18, -2)
        toe.lineTo(f * (BODY_W / 2 + 20 * abs(f)), -2)
        toe.lineTo(f * 18, -24)
        toe.close()
        c.drawPath(toe, fill(ent["color"], a))
    c.drawRoundRect(skia.Rect.MakeXYWH(-BODY_W / 2, -BODY_H, BODY_W, BODY_H), BODY_W / 2, BODY_W / 2, fill(ent["color"], a))
    c.drawCircle(o["lx"] * 14, -BODY_H + 40 + o["ly"] * 15, 8, fill(INK, a))   # attention
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


def bubble_box(stage, line, o):
    """Where a bubble sits for a speaker in state `o`, and how its text is laid out inside it."""
    feel, tone = stage.look.feel, stage.look.tones[line["tone"]]
    f, size, tw, rows, chunks = layout(line, tone)
    W, H, pad = stage.W, stage.H, 22
    lift, rad = float(feel["cursor_lift"]), float(feel["cursor_size"])
    lane = lift + 2 * rad * WEIGHT[2] + 4                        # room under each row for the indicator
    lh = size + 6 + lane
    w, h = max(150, tw + 2 * pad), len(rows) * lh + 2 * pad - 14
    hx, top = slot_x(o["slot"], W), ground(H) - BODY_H * o["sy"] - 24
    bx = min(max(hx - w / 2, 24), W - w - 40)
    by = top - h - 24
    return dict(f=f, size=size, rows=rows, chunks=chunks, pad=pad, lift=lift, rad=rad, lh=lh, w=w, h=h, hx=hx, top=top, bx=bx, by=by)


def draw_bubble(c, stage, line, t, o, ent):
    feel, tone = stage.look.feel, stage.look.tones[line["tone"]]
    g = bubble_box(stage, line, o)
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
    c.save()
    if pop > 0 and age < pop:                                    # pops open from the speaker
        s = 0.55 + 0.45 * back(age / pop, 1.0)
        c.translate(hx, top)
        c.scale(s, s)
        c.translate(-hx, -top)
    c.drawPath(shape, fill("#ffffff"))
    c.drawPath(shape, stroke(ent["color"], 4))
    style = stage.look.style.get("indicator", "dot")             # how the voice is shown moving through the words
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
            for r, text in enumerate(rows[:here[0] + 1]):
                c.save()
                right = bx + w if r < here[0] else bx + pad + here[1] + 2
                c.clipRect(skia.Rect.MakeLTRB(bx, base(r) - size - 6, right, base(r) + size))
                c.drawString(text, bx + pad, base(r), f, ink)
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


def hits(stage, F):
    """What is where in frame F, front to back: [{kind, box: [x, y, w, h], ...}] in frame pixels.
    kind is `syllable` (with `line`, the bubble, and `n`, its place in that bubble from 0), `bubble`, or `token` (with `entity`).
    This is how a click on the picture finds the thing it landed on."""
    t = F / stage.fps
    states = {e: s for e in stage.score.pose if (s := pose(stage, e, t)) is not None and s["alpha"] > 0.5}
    out, line = [], stage.score.line_at(t)
    if line and line["who"] in states:
        g = bubble_box(stage, line, states[line["who"]])
        for n, (row, x0, _, width) in enumerate(g["chunks"]):
            out.append(dict(kind="syllable", line=line, n=n, box=[g["bx"] + g["pad"] + x0, g["by"] + g["pad"] - 8 + row * g["lh"], max(width, 6), g["lh"]]))
        out.append(dict(kind="bubble", line=line, box=[g["bx"], g["by"], g["w"], g["h"]]))
    for e, o in states.items():
        w, h = BODY_W * o["sx"] + 24, BODY_H * o["sy"]
        out.append(dict(kind="token", entity=e, box=[slot_x(o["slot"], stage.W) - w / 2, ground(stage.H) - h, w, h]))
    return out


def draw_frame(c, stage, F, xray=False, slate=False):
    W, H, t, feel = stage.W, stage.H, F / stage.fps, stage.look.feel
    c.clear(col(PAPER))
    c.drawLine(0, ground(H), W, ground(H), stroke(RULE, 2))
    states = {e: s for e in stage.score.pose if (s := pose(stage, e, t)) is not None}
    if xray:
        draw_xray(c, stage, states)
    line = stage.score.line_at(t)
    focal, dim = None, 0.0
    for a0, a1, who in stage.score.focus:                             # a featured reaction: everyone else recedes
        if a0 - 0.15 <= t <= a1 + 0.15:
            focal = who
            dim = float(feel["focus_dim"]) * smooth((t - a0 + 0.15) / 0.15) * (1 - smooth((t - a1) / 0.15))
    for e in sorted(states, key=lambda e: bool(line and line["who"] == e)):
        o = states[e] if e == focal or not dim else dict(states[e], alpha=states[e]["alpha"] * (1 - dim))
        draw_token(c, stage.look.cast[e], o, W, H, feel)
    if line and line["who"] in states:
        draw_bubble(c, stage, line, t, states[line["who"]], stage.look.cast[line["who"]])
    if slate:
        turn = stage.score.turn_at(t)
        c.drawString(f"T{turn['id']} · {t / stage.score.step - turn['start']:.2f}", 20, 32, font(16, mono=True), fill(INK, 150))
