"""Dialogue without lip sync: a speech bubble that types itself out, a musical note whose
colour and movement carry the tone, and voice blips whose pitch and speed follow the same tone."""
import math
import wave

import numpy as np
import skia

from .paper import col, cut, oval, poly, rrect, seed_of

PAUSE = {",": 0.14, ";": 0.14, ".": 0.26, "!": 0.26, "?": 0.26, "…": 0.3, "-": 0.05}
PAD, LINE_H, SIZE, MAX_W = 22, 38, 28, 470


def font():
    tf = skia.Typeface("DejaVu Sans", skia.FontStyle.Bold())
    return skia.Font(tf, SIZE)


def schedule(text, cps, fps):
    """Frame offset at which each character appears. Punctuation adds a breath."""
    t, out = 0.0, []
    for ch in text:
        out.append(t * fps)
        t += 1.0 / cps + PAUSE.get(ch, 0)
    return out, t * fps


def wrap(text, f):
    lines, cur = [], ""
    for word in text.split(" "):
        trial = (cur + " " + word).strip()
        if cur and f.measureText(trial) > MAX_W:
            lines.append(cur)
            cur = word
        else:
            cur = trial
    return lines + [cur]


def ease_back(k):
    k = max(0.0, min(1.0, k))
    return 1 + 2.70158 * (k - 1) ** 3 + 1.70158 * (k - 1) ** 2


def draw_note(c, x, y, tone, secs):
    """The tone marker. `motion` decides how the note behaves; the reader feels it before reading."""
    m = tone.get("motion", "still")
    w = 2 * math.pi * secs
    dx = dy = rot = 0.0
    sc = 1.0
    if m == "bounce":
        dy = -abs(math.sin(w * 1.6)) * 10
    elif m == "sway":
        rot = math.sin(w * 1.0) * 17
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
    cut(c, oval(0, 0, 26, 26), "#fbf6ea", key="notetab", rough=0.8)
    ink_c = tone.get("color", "#3a3531")
    heads = [(-9, 9), (9, 5)] if tone.get("double") else [(-3, 9)]
    for hx, hy in heads:
        c.save()
        c.translate(hx, hy)
        c.rotate(-22)
        cut(c, oval(0, 0, 7.5, 5.5), ink_c, shadow=False, rough=0)
        c.restore()
        cut(c, rrect(hx + 4.5, hy - 23, 3.2, 23, 1), ink_c, shadow=False, rough=0)
    if tone.get("double"):
        cut(c, poly([(-4.5, -14), (16.7, -18), (16.7, -12), (-4.5, -8)]), ink_c, shadow=False, rough=0)
    else:
        hx, hy = heads[0]
        cut(c, poly([(hx + 4.5, hy - 23), (hx + 16, hy - 15), (hx + 16, hy - 8), (hx + 7.7, hy - 15)]),
            ink_c, shadow=False, rough=0)
    c.restore()


def draw_bubble(c, line, F, head, accent, tone, W, H, fps):
    """`head` is (x, top y, middle y) of the speaker's head on screen."""
    f = font()
    lines = wrap(line["text"], f)
    w = max(150, max(f.measureText(s) for s in lines) + 2 * PAD)
    h = len(lines) * LINE_H + 2 * PAD - 8
    hx, htop, hmid = head
    onscreen = 0 < hx < W
    above = onscreen and htop - h - 50 >= 40
    bx = min(max(hx - w / 2, 28), W - w - 28)
    if above:
        by = htop - h - 50
        tx = min(max(hx, bx + 40), bx + w - 40)
        tail, tip = [(tx - 18, by + h - 4), (tx + 18, by + h - 4), (hx, htop - 10)], (hx, htop - 10)
    else:
        by = H - h - 34
        if onscreen:
            tx = min(max(hx, bx + 40), bx + w - 40)
            tail, tip = [(tx - 18, by + 4), (tx + 18, by + 4), (tx, by - 24)], (tx, by - 24)
        elif hx <= 0:
            tail, tip = [(bx + 4, by + h / 2 - 16), (bx + 4, by + h / 2 + 16), (bx - 22, by + h / 2)], (bx - 22, by + h / 2)
        else:
            tail, tip = [(bx + w - 4, by + h / 2 - 16), (bx + w - 4, by + h / 2 + 16), (bx + w + 22, by + h / 2)], (bx + w + 22, by + h / 2)

    age = F - line["start"]
    pop = 0.6 + 0.4 * ease_back(age / 6)
    c.save()
    c.translate(*tip)
    c.scale(pop, pop)
    c.translate(-tip[0], -tip[1])

    # backing card in the speaker's colour, set slightly askew, tells you who is talking
    c.save()
    c.rotate(-1.3, bx + w / 2, by + h / 2)
    cut(c, rrect(bx - 7, by - 7, w + 14, h + 14, 26), accent, key="bub-back" + line["who"])
    c.restore()
    cut(c, poly(tail), "#fbf6ea", key="bub-tail", rough=0.6)
    cut(c, rrect(bx, by, w, h, 20), "#fbf6ea", key="bub" + line["who"], shadow=False)

    shown = sum(1 for t in line["times"] if t <= age)
    paint = skia.Paint(AntiAlias=True, Color=col("#2b2420"))
    idx = 0
    for i, s in enumerate(lines):
        n = max(0, min(len(s), shown - idx))
        if n:
            c.drawString(s[:n], bx + PAD, by + PAD + SIZE - 4 + i * LINE_H, f, paint)
        idx += len(s) + 1
    draw_note(c, bx + w - 6, by - 2, tone, age / fps)
    c.restore()


def write_blips(lines, tones, voices, fps, total_frames, path, rate=44100):
    """One short pitched blip per second character. Tone sets pitch, loudness and melodic contour."""
    audio = np.zeros(int(total_frames / fps * rate) + rate // 2, dtype=np.float32)
    n = int(0.07 * rate)
    env = np.exp(-np.arange(n) / (0.018 * rate)) * np.minimum(1, np.arange(n) / 60)
    for line in lines:
        tone = tones[line["tone"]]
        rng = np.random.default_rng(seed_of(line["text"]))
        vis = [i for i, ch in enumerate(line["text"]) if ch.isalnum()]
        for j, i in enumerate(vis[::2]):
            k = j / max(1, len(vis[::2]) - 1)
            contour = {"rise": 1 + 0.2 * k * k, "fall": 1 - 0.16 * k,
                       "wobble": 1 + 0.07 * math.sin(k * 21)}.get(tone.get("contour"), 1.0)
            hz = voices[line["who"]] * tone.get("pitch", 1) * contour * (1 + rng.uniform(-0.03, 0.03))
            ph = 2 * np.pi * hz * np.arange(n) / rate
            blip = (np.sin(ph) + 0.35 * np.sin(2 * ph) + 0.15 * np.sin(3 * ph)) * env * tone.get("vol", 0.5) * 0.3
            at = int((line["start"] + line["times"][i]) / fps * rate)
            audio[at:at + n] += blip[: len(audio) - at]
    pcm = (np.clip(audio, -1, 1) * 32767).astype(np.int16)
    with wave.open(path, "wb") as wv:
        wv.setnchannels(1)
        wv.setsampwidth(2)
        wv.setframerate(rate)
        wv.writeframes(pcm.tobytes())
