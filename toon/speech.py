"""Dialogue timing and sound: text that types itself out, and voice blips that follow the tone."""
import math
import wave
import zlib

import numpy as np

PAUSE = {",": 0.14, ";": 0.14, ".": 0.26, "!": 0.26, "?": 0.26, "…": 0.3, "-": 0.05}


def schedule(text, cps, fps):
    """Frame offset at which each character appears. Punctuation adds a breath."""
    t, out = 0.0, []
    for ch in text:
        out.append(t * fps)
        t += 1.0 / cps + PAUSE.get(ch, 0)
    return out, t * fps


def wrap(text, font, max_w):
    lines, cur = [], ""
    for word in text.split(" "):
        trial = (cur + " " + word).strip()
        if cur and font.measureText(trial) > max_w:
            lines.append(cur)
            cur = word
        else:
            cur = trial
    return lines + [cur]


def write_blips(lines, tones, voices, fps, total_frames, out, rate=44100):
    """One short pitched blip per second character. `out` is a path or a file-like object."""
    audio = np.zeros(int(total_frames / fps * rate) + rate // 2, dtype=np.float32)
    n = int(0.07 * rate)
    env = np.exp(-np.arange(n) / (0.018 * rate)) * np.minimum(1, np.arange(n) / 60)
    for line in lines:
        tone = tones[line["tone"]]
        rng = np.random.default_rng(zlib.crc32(line["text"].encode()))
        vis = [i for i, ch in enumerate(line["text"]) if ch.isalnum()][::2]
        for j, i in enumerate(vis):
            k = j / max(1, len(vis) - 1)
            contour = {"rise": 1 + 0.2 * k * k, "fall": 1 - 0.16 * k,
                       "wobble": 1 + 0.07 * math.sin(k * 21)}.get(tone.get("contour"), 1.0)
            hz = voices[line["who"]] * tone.get("pitch", 1) * contour * (1 + rng.uniform(-0.03, 0.03))
            ph = 2 * np.pi * hz * np.arange(n) / rate
            blip = (np.sin(ph) + 0.35 * np.sin(2 * ph) + 0.15 * np.sin(3 * ph)) * env * tone.get("vol", 0.5) * 0.3
            at = int((line["start"] + line["times"][i]) / fps * rate)
            audio[at:at + n] += blip[: len(audio) - at]
    pcm = (np.clip(audio, -1, 1) * 32767).astype(np.int16)
    with wave.open(out, "wb") as wv:
        wv.setnchannels(1)
        wv.setsampwidth(2)
        wv.setframerate(rate)
        wv.writeframes(pcm.tobytes())
