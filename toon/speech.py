"""Speech as music. A line is split into syllables; each syllable gets a place on the tempo
grid and one sung note. The text and the sound are built from the same plan, so they cannot
drift apart. Sound effects are synthesised here too."""
import io
import math
import re
import wave
import zlib

import numpy as np

RATE = 44100
REST = {",": 1, ";": 1, ":": 1, ".": 2, "!": 2, "?": 2, "…": 3}     # breath after punctuation, in steps


def split_word(w):
    """Best-guess syllables for one English word. Write a middle dot (some·one) to override."""
    m = re.match(r"^([^A-Za-z]*)([A-Za-z]+)(.*)$", w)
    if not m:
        return [w]
    lead, core, tail = m.groups()
    low = core.lower()
    groups = [(g.start(), g.end()) for g in re.finditer(r"[aeiouy]+", low)]
    if len(groups) > 1:                                   # endings that are written but not said
        s, e = groups[-1]
        if e == len(low) and e - s == 1 and low.endswith("e") and not low.endswith("le"):
            groups.pop()
        elif s == len(low) - 2 and e - s == 1 and low.endswith("ed") and low[-3] not in "td":
            groups.pop()
        elif s == len(low) - 2 and e - s == 1 and low.endswith("es") and low[-3] not in "sxzhc":
            groups.pop()
    if len(groups) <= 1:
        return [w]
    cuts = [e0 if s1 - e0 <= 1 else e0 + 1 for (_, e0), (s1, _) in zip(groups, groups[1:])]
    parts = [core[a:b] for a, b in zip([0] + cuts, cuts + [len(core)])]
    parts[0], parts[-1] = lead + parts[0], parts[-1] + tail
    return parts


def syllables(text):
    words = [w for w in str(text).split(" ") if w]
    out = []
    for wi, w in enumerate(words):
        parts = w.split("·") if "·" in w else split_word(w)
        for pi, part in enumerate(parts):
            last = pi == len(parts) - 1
            out.append(dict(text=part + (" " if last and wi < len(words) - 1 else ""),
                            rest=REST.get(part.rstrip("\"')")[-1:], 0) if last else 0))
    if out:
        out[-1]["rest"] = 0
    return out


def semi_of(degree, scale):
    return 12 * (degree // len(scale)) + scale[degree % len(scale)]


def plan(text, tone, scale, rhythm=None, melody=None):
    """-> [{text, at, len, semi}]: each syllable's start and length in steps, and its pitch in semitones.

    Without `rhythm` or `melody` the tone supplies them: `rate` steps per syllable, the last one
    stretched by `stretch`, and a `contour` spanning `range` notes of the show's scale.
    """
    syl = syllables(text)
    n = len(syl)
    if rhythm is None:
        rhythm = [tone.get("rate", 2) + s["rest"] for s in syl]
        rhythm[-1] *= tone.get("stretch", 1)
    if melody is None:
        span, contour, seed = tone.get("range", 2), tone.get("contour", "flat"), zlib.crc32(str(text).encode())
        melody = []
        for k in range(n):
            u = k / max(1, n - 1)
            d = {"rise": span * u, "fall": -span * u, "wobble": span * 0.5 * math.sin(k * 2.2)}.get(contour, 0)
            if span >= 2:                                 # a little wander so a line is not one note
                d += (0, 1, 0, -1)[(seed >> ((k % 16) * 2)) & 3]
            melody.append(semi_of(round(d), scale))
    out, at = [], 0
    for s, ln, m in zip(syl, rhythm, melody):
        out.append(dict(text=s["text"], at=at, len=ln, semi=m))
        at += ln
    return out


# ---- sound ---------------------------------------------------------------------------------
def _osc(kind, phase):
    if kind == "square":
        return np.tanh(3 * np.sin(phase)) * 0.7
    if kind == "tri":
        return 2 / np.pi * np.arcsin(np.sin(phase))
    return np.sin(phase) + 0.3 * np.sin(2 * phase) + 0.12 * np.sin(3 * phase)


def note(hz, dur, vol, timbre="sine"):
    n = max(1, int(dur * RATE))
    t = np.arange(n) / RATE
    env = np.minimum(1, t / 0.004) * np.exp(-t / (0.3 * dur + 0.02)) * np.clip((dur - t) / 0.01, 0, 1)
    return _osc(timbre, 2 * np.pi * hz * t) * env * vol * 0.3


def effect(p):
    """One sound effect from its settings: wave, freq (gliding to `to`), dur, vol."""
    dur = max(0.005, float(p.get("dur", 0.1)))
    n = max(1, int(dur * RATE))
    t = np.arange(n) / RATE
    f0 = max(20.0, float(p.get("freq", 440)))
    f1 = max(20.0, float(p.get("to", f0)))
    f = f0 * (f1 / f0) ** (t / dur)
    if p.get("wave") == "noise":
        w = max(1, int(RATE / ((f0 + f1) / 2) / 2))
        x = np.convolve(np.random.default_rng(7).uniform(-1, 1, n), np.ones(w) / w, "same") * math.sqrt(w) * 0.6
    else:
        x = _osc(p.get("wave", "sine"), 2 * np.pi * np.cumsum(f) / RATE)
    return x * np.minimum(1, t / 0.003) * np.exp(-t / (dur / 3)) * float(p.get("vol", 0.3)) * 0.5


def wav_bytes(samples):
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wv:
        wv.setnchannels(1)
        wv.setsampwidth(2)
        wv.setframerate(RATE)
        wv.writeframes((np.clip(samples, -1, 1) * 32767).astype(np.int16).tobytes())
    return buf.getvalue()


def sound_for(sounds, name):
    """`feel.shame` falls back to `feel`."""
    return sounds.get(name) or sounds.get(name.split(".")[0])


def mix(scene):
    """The whole scene's sound: one note per syllable, plus an effect per event."""
    audio = np.zeros(int((scene.dur + 0.6) * RATE), dtype=np.float64)

    def add(at, x):
        i = int(at * RATE)
        if 0 <= i < len(audio):
            audio[i:i + len(x)] += x[: len(audio) - i]

    for line in scene.lines:
        ent, tone = scene.ents[line["who"]], scene.show.tones[line["tone"]]
        for s in line["sylls"]:
            hz = ent["voice"] * tone.get("pitch", 1) * 2 ** (s["semi"] / 12)
            add(s["start"], note(hz, min(s["dur"] * 0.95, 0.32), tone.get("vol", 0.5), ent.get("timbre", "sine")))
    for at, name, _ in scene.events:
        p = sound_for(scene.show.sounds, name)
        if p and float(p.get("vol", 0)) > 0:
            add(at, effect(p))
    return wav_bytes(audio)
