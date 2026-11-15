"""Speech as music. A line is split into syllables; each syllable gets a stress, a place on
the tempo grid and one note. The text and the sound are built from the same plan, so they
cannot drift apart. Stress is what keeps it from sounding like a drum: weak syllables are
short, quiet and still; strong ones are longer, louder and higher; the last strong syllable
of a phrase carries the most. Sound effects are synthesised here too."""
import io
import math
import re
import wave
import zlib

import numpy as np

RATE = 44100
REST = {",": 1, ";": 1, ":": 1, ".": 2, "!": 2, "?": 2, "…": 3}     # breath after punctuation, in steps
WEAK = set("""a an the of to in on at by for from with and or but so if as than is am are was were be been
it its i you he she we they me him her us them my your his our their this that these those there
do does did have has had will would can could should shall may might must i'm i'd i'll i've you're you'd
you'll you've he's she's it's we're we'd we'll we've they're they'd they'll they've that's there's""".split())
SECOND = set("""about again away alone around along among ago ahead apart enough because before behind believe
between below beyond become began begin today tonight tomorrow already degrees decide forget forgive hello
myself yourself himself herself itself ourselves themselves without within until unless upon perhaps
okay except explain instead indeed arrive agree allow appear""".split())   # words stressed on their second syllable
STRETCH = {0: 0.5, 1: 1.0, 2: 1.5}                                   # how long a syllable lasts, by stress
LOUD = {0: 0.55, 1: 0.85, 2: 1.0}


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
    """-> [{text, rest, stress}]. stress: 0 weak, 1 strong, 2 the main accent of its phrase.

    Stress is guessed: small grammatical words are weak, other words are strong on their first
    syllable (or second, for a list of common exceptions). Write ^ before a syllable to force
    the strong one (to^day), and a middle dot to say where syllables break (some·one).
    """
    words = [w for w in str(text).split(" ") if w]
    out = []
    for wi, w in enumerate(words):
        forced = []
        if "·" in w:
            parts = [p for p in w.split("·") if p]
            forced = [i for i, p in enumerate(parts) if "^" in p]
        else:
            mark, pos = w.find("^"), 0
            parts = split_word(w.replace("^", ""))
            for i, p in enumerate(parts if mark >= 0 else []):
                if mark < pos + len(p) or i == len(parts) - 1:
                    forced = [i]
                    break
                pos += len(p)
        bare = re.sub(r"[^a-z']", "", w.lower())
        strong = forced[0] if forced else None if bare in WEAK else (1 if bare in SECOND and len(parts) > 1 else 0)
        for pi, part in enumerate(parts):
            last = pi == len(parts) - 1
            part = part.replace("^", "")
            out.append(dict(text=part + (" " if last and wi < len(words) - 1 else ""),
                            rest=REST.get(part.rstrip("\"')")[-1:], 0) if last else 0,
                            stress=1 if pi == strong else 0))
    if not out:
        return out
    out[-1]["rest"] = 0
    start = 0
    for i, s in enumerate(out):                           # the last strong syllable of each phrase carries it
        if s["rest"] or i == len(out) - 1:
            strong = [j for j in range(start, i + 1) if out[j]["stress"]]
            out[strong[-1] if strong else i]["stress"] = 2
            start = i + 1
    return out


def semi_of(degree, scale):
    return 12 * (degree // len(scale)) + scale[degree % len(scale)]


def plan(text, tone, scale, rhythm=None, melody=None, stress=None, breaks=(), gap=2):
    """-> [{text, at, len, semi, stress, rest}]: each syllable's start and length in steps, its pitch
    in semitones, its stress, and how much of its length is the breath after punctuation.

    Anything not given is worked out. Stress comes from the words. Rhythm is the tone's `rate`
    (steps for a strong syllable), halved for weak ones and half as long again for a phrase's
    main accent. Melody is the tone's `contour` over `range` notes of the scale, with strong
    syllables a note higher.
    """
    syl = syllables(text)
    n = len(syl)
    for k in breaks:                                      # a break chosen by hand is a pause too
        if 0 < k < n:
            syl[k - 1]["rest"] = max(syl[k - 1]["rest"], gap)
    if stress is not None:
        for s, v in zip(syl, stress):
            s["stress"] = max(0, min(2, int(v)))
    if rhythm is None:
        rhythm = [max(0.5, tone.get("rate", 2) * STRETCH[s["stress"]]) + s["rest"] for s in syl]
        rhythm[-1] *= tone.get("stretch", 1)
    if melody is None:
        span, contour, seed = tone.get("range", 2), tone.get("contour", "flat"), zlib.crc32(str(text).encode())
        melody = []
        for k, s in enumerate(syl):
            u = k / max(1, n - 1)
            d = {"rise": span * u, "fall": -span * u, "wobble": span * 0.5 * math.sin(k * 2.2)}.get(contour, 0)
            if s["stress"] == 2 and contour == "fall":
                d -= 1                                    # a falling line lands low on its accent
            elif s["stress"]:
                d += 1                                    # strong syllables sit a note higher
            elif span >= 2:                               # a little wander among the weak ones
                d += (0, 0, 0, -1)[(seed >> ((k % 16) * 2)) & 3]
            melody.append(semi_of(round(d), scale))
    out, at = [], 0
    for s, ln, m in zip(syl, rhythm, melody):                 # `rest` is the silent part at the end of `len`
        out.append(dict(text=s["text"], at=at, len=ln, semi=m, stress=s["stress"], rest=max(0, min(s["rest"], ln - 0.5))))
        at += ln
    return out


# ---- sound ---------------------------------------------------------------------------------
def _osc(kind, phase):
    if kind == "square":
        return np.tanh(3 * np.sin(phase)) * 0.7
    if kind == "tri":
        return 2 / np.pi * np.arcsin(np.sin(phase))
    return np.sin(phase) + 0.3 * np.sin(2 * phase) + 0.12 * np.sin(3 * phase)


def note(hz, dur, vol, timbre="sine", attack=0.015, ring=0.7):
    """One voiced syllable. `attack` is how long it takes to swell; `ring` is how much of its
    level it keeps to the end (0 = plucked, 1 = held), so neighbours can run together."""
    n = max(1, int(dur * RATE))
    t = np.arange(n) / RATE
    env = np.minimum(1, t / max(attack, 0.001)) * (ring + (1 - ring) * np.exp(-t / 0.05)) * np.clip((dur - t) / 0.02, 0, 1)
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
    feel = scene.show.feel

    def add(at, x):
        i = int(at * RATE)
        if 0 <= i < len(audio):
            audio[i:i + len(x)] += x[: len(audio) - i]

    for line in scene.lines:
        ent, tone = scene.ents[line["who"]], scene.show.tones[line["tone"]]
        for s in line["sylls"]:
            hz = ent["voice"] * tone.get("pitch", 1) * 2 ** (s["semi"] / 12)
            add(s["start"], note(hz, min(s["voiced"], 0.6), tone.get("vol", 0.5) * LOUD[s["stress"]], ent.get("timbre", "sine"),
                                 float(feel["voice_attack"]), float(feel["voice_ring"])))
    for at, name, _ in scene.events:
        p = sound_for(scene.show.sounds, name)
        if p and float(p.get("vol", 0)) > 0:
            add(at, effect(p))
    return wav_bytes(audio)
