"""The bare renderer. An empty frame, a ground line, and one featureless token per entity.

A token shows only what the model says is observable: where it stands, which way its body
faces (the toe at its base), where its attention is (the dot), and how it holds itself.
The small motions on top (flip, stretch, hop, pops) are sized by library/feel.yaml.
"""
import math

import skia

from .model import SLOTS, back

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


def draw_token(c, ent, o, W, H, feel, hop=0.0):
    a = 255 * o["alpha"]
    if a < 1:
        return
    stretch = o["travel"] * float(feel["squash"])
    thin = 1 - 0.9 * float(feel["flip"]) * o["flip"]
    c.save()
    c.translate(slot_x(o["slot"], W), ground(H) - hop)
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


def layout(line, tone):
    """Place every syllable once: which row it sits on and how far along."""
    if "_layout" not in line:
        size = 21 if tone.get("text") == "small" else 28
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
        line["_layout"] = (f, size, max(f.measureText(r.rstrip()) for r in rows), len(rows), chunks)
    return line["_layout"]


def draw_bubble(c, scene, line, t, o, ent, hop):
    feel, tone = scene.show.feel, scene.show.tones[line["tone"]]
    f, size, tw, nrows, chunks = layout(line, tone)
    W, H, pad, lh = scene.W, scene.H, 22, size + 10
    w, h = max(150, tw + 2 * pad), nrows * lh + 2 * pad - 8
    hx, top = slot_x(o["slot"], W), ground(H) - BODY_H * o["sy"] - 24 - hop
    bx = min(max(hx - w / 2, 24), W - w - 40)
    by = top - h - 24
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
    ink = fill(INK)
    tp, ts = float(feel["text_pop"]), float(feel["text_pop_scale"])
    for i, (row, cx, text, cw) in enumerate(chunks):
        a = t - line["sylls"][i]["start"]
        if a < -1e-6:
            continue
        accent = (0.0, 0.6, 1.0)[line["sylls"][i]["stress"]]                # weak syllables just appear
        s = 1 + (ts - 1) * accent * (1 - a / tp) if tp > 0 and a < tp else 1.0
        c.save()
        c.translate(bx + pad + cx + cw / 2, by + pad + size - 4 + row * lh)
        c.scale(s, s)
        c.drawString(text.rstrip(), -cw / 2, 0, f, ink)
        c.restore()
    if line["sung"]:
        draw_note(c, bx + w - 2, by + 2, tone, max(age, 0), ent["color"])
    c.restore()


def draw_xray(c, scene, states):
    """Director's view, kept below the ground line: weight in the room, and felt against shown."""
    W, gy = scene.W, ground(scene.H)
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
            color, n = scene.show.emotions.get(info["felt"], INK), max(info["intensity"], info["level"])
            for i in range(n):                                  # a small solid pip = amplified beyond what is felt
                px = x + (i - (n - 1) / 2) * 16
                if i < info["level"]:
                    c.drawCircle(px, gy + 38, 5.5 if i < info["intensity"] else 3.5, fill(color))
                if i < info["intensity"]:
                    c.drawCircle(px, gy + 38, 5.5, stroke(color, 2))


def draw_frame(c, scene, F, xray=False, slate=False):
    W, H, t, feel = scene.W, scene.H, F / scene.fps, scene.show.feel
    c.clear(col(PAPER))
    c.drawLine(0, ground(H), W, ground(H), stroke(RULE, 2))
    states = {e: s for e in scene.keys if (s := scene.state(e, t)) is not None}
    if xray:
        draw_xray(c, scene, states)
    line = scene.line_at(t)
    hop = 0.0
    if line:                                                    # the speaker nods on stressed syllables only
        hit = [(t - s["start"], s["stress"]) for s in line["sylls"] if s["stress"] and s["start"] <= t + 1e-6]
        if hit and min(hit)[0] < 0.24:
            age, stress = min(hit)
            hop = float(feel["talk_hop"]) * (0.55 if stress == 1 else 1.0) * math.sin(math.pi * age / 0.24)
    for e in sorted(states, key=lambda e: bool(line and line["who"] == e)):
        draw_token(c, scene.ents[e], states[e], W, H, feel, hop if line and line["who"] == e else 0.0)
    if line and line["who"] in states:
        draw_bubble(c, scene, line, t, states[line["who"]], scene.ents[line["who"]], hop)
    if slate:
        turn = scene.turn_at(t)
        c.drawString(f"T{turn['id']} · {t / scene.step - turn['start']:.2f}", 20, 32, font(16, mono=True), fill(INK, 150))
