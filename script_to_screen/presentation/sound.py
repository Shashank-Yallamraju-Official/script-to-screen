"""Sound: synthesises a scene's voices and effects from its events and lines."""
import io
import math
import wave

import numpy as np

from . import master, music

RATE = 44100
LOUD = {0: 0.55, 1: 0.85, 2: 1.0}             # how loud a syllable is, by stress


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


def blast():
    """An explosion (`sfx: [{sound: blast, on: <entity>}]`): the crack, the body of it, and a long low roll dying away."""
    n = int(4.2 * RATE)
    t = np.arange(n) / RATE
    rng = np.random.default_rng(11)
    noise = rng.standard_normal(n)
    crack = noise * np.exp(-t / 0.035)
    body = np.convolve(noise, np.ones(40) / 40, "same") * 6 * np.exp(-t / 0.32)
    roll = np.convolve(noise, np.ones(400) / 400, "same") * 22 * np.exp(-t / 0.9) * np.minimum(1, t / 0.05)
    thud = np.sin(2 * np.pi * np.cumsum(34 + 70 * np.exp(-t / 0.09)) / RATE) * np.exp(-t / 0.55)
    x = 0.9 * crack + 0.8 * body + 0.7 * roll + 1.2 * thud
    return np.tanh(x * 1.2) * 1.6 * np.clip((4.2 - t) / 1.2, 0, 1) ** 2          # it dies away to nothing: it is never cut off


UNITY = 0.8          # the level in library/sounds.yaml at which a built-in sound (blast, swell, air) plays as it was made


def swell(seconds):
    """What comes before an explosion: a low hum that rises and tightens, and stops dead as it goes off."""
    t = np.arange(int(seconds * RATE)) / RATE
    k = t / seconds
    hum = np.sin(2 * np.pi * np.cumsum(46 + 95 * k ** 2) / RATE) + 0.5 * np.sin(2 * np.pi * np.cumsum(92 + 230 * k ** 2) / RATE)
    hiss = np.convolve(np.random.default_rng(12).standard_normal(len(t)), np.ones(30) / 30, "same") * 3
    return (hum * (1 + 0.4 * k * np.sin(2 * np.pi * (5 + 14 * k) * t)) + hiss * k) * k ** 1.5 * 0.55


def air(n, kind="warm"):
    """The sound of a place with nothing happening in it, `n` samples long: `warm` is still evening air, low and soft; `cold` is a
    thin draught through bare stone, higher and emptier. It comes up over the first seconds and is let go at the end, never cut."""
    from scipy.signal import butter, sosfilt
    rng = np.random.default_rng(21 if kind == "warm" else 22)
    t = np.arange(n) / RATE
    noise = rng.standard_normal(n)
    if kind == "cold":
        x = sosfilt(butter(2, [500, 1500], "bandpass", fs=RATE, output="sos"), noise) * 1.3 + sosfilt(butter(2, 180, "lowpass", fs=RATE, output="sos"), noise) * 1.6
        x *= 0.7 + 0.3 * np.sin(2 * np.pi * 0.11 * t) * np.sin(2 * np.pi * 0.037 * t + 1.0)          # it comes and goes
        level = 0.010
    else:
        x = sosfilt(butter(2, 420, "lowpass", fs=RATE, output="sos"), noise) * 2.2 + sosfilt(butter(2, [1800, 4200], "bandpass", fs=RATE, output="sos"), noise) * 0.25
        x *= 0.85 + 0.15 * np.sin(2 * np.pi * 0.07 * t)
        level = 0.012
    return x * level * np.clip(t / 2.0, 0, 1) * np.clip((n / RATE - t) / 1.5, 0, 1)


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


def riser(hz0, hz1, dur, vol, timbre=None):
    """A build-up (see music.riser)."""
    return music.riser(hz0, hz1, dur, vol)


def faded(x, fade_in=0.0, fade_out=0.0, end=None):
    """A sound brought up from nothing over its first `fade_in` seconds, and down to nothing over the `fade_out` seconds before
    `end` (a sample; by default its last)."""
    if fade_in <= 0 and fade_out <= 0:
        return x
    x = x.copy()
    a = min(int(fade_in * RATE), len(x))
    x[:a] *= np.linspace(0, 1, a)
    if fade_out > 0:
        end = len(x) if end is None else max(0, min(int(end), len(x)))
        b = min(int(fade_out * RATE), end)
        x[end - b:end] *= np.linspace(1, 0, b)
        x[end:] = 0
    return x


def mix(stage, only=None):
    """The whole scene's sound, or (`only`: voices, sounds or music) one of its three layers alone. Voices (one note per syllable), effects (one per event) and music (the score's
    cues, voiced in the mode their meaning calls for) are made as three buses, then mixed and mastered together."""
    n = int((stage.score.dur + 1.6) * RATE)                      # room for the last note and the room's tail to die away
    voices, effects = np.zeros(n), np.zeros(n)
    feel = stage.look.feel

    def add(bus, at, x):
        i = int(at * RATE)
        if 0 <= i < n:
            bus[i:i + len(x)] += x[: n - i]

    for line in stage.score.speech:
        ent, tone = stage.look.cast[line["who"]], stage.look.tones[line["tone"]]
        for s in line["sylls"]:
            hz = ent["voice"] * tone.get("pitch", 1) * 2 ** (s["semi"] / 12)
            add(voices, s["start"], note(hz, min(s["voiced"], 0.6), tone.get("vol", 0.5) * LOUD[s["stress"]], ent.get("timbre", "sine"),
                                         float(feel["voice_attack"]), float(feel["voice_ring"])))
    aside = float(feel["aside_volume"])                          # a reaction in passing is quieter
    step = stage.score.step
    placed = {(round(fx["start"] * step, 4), fx["sound"]): fx for t in stage.score.turns for fx in t.get("sfx") or []}      # sounds a turn placed by hand, with their own length and level
    kind_level = lambda name: float((stage.look.sounds.get(name) or {}).get("vol", UNITY)) / UNITY      # every sound of a kind: library/sounds.yaml <kind>.vol
    for at, name, _, quiet in stage.score.events:
        fx = placed.get((round(at, 4), name)) or {}
        level, long = kind_level(name) * float(fx.get("vol", 1)), float(fx.get("len") or 16) * step
        fin, fout = float(fx.get("fade_in", 0)) * step, float(fx.get("fade_out", 0)) * step
        if name == "blast":                                      # an explosion: not one of the small sounds, and never quiet
            lead = min(long, at)                                 # the come-up: a rising hum, two bars unless it says
            bang, hum = blast(), swell(lead)
            whole = np.zeros(int(lead * RATE) + len(bang))
            whole[:len(hum)] += hum
            whole[int(lead * RATE):] += bang
            add(effects, at - lead, faded(whole, fin, fout) * level)
            continue
        if name == "swell":                                      # the come-up alone: it rises and stops dead, unless it is asked to fade
            add(effects, at, faded(swell(long), fin, fout) * level)
            continue
        p = sound_for(stage.look.sounds, name)
        if p and float(p.get("vol", 0)) > 0:
            add(effects, at, effect(p) * (aside if quiet else 1.0))
    kind = (stage.look.place or {}).get("air")                   # the room is never dead quiet: the air of the place, under everything
    if kind:
        effects += air(n, kind) * kind_level("air")
    settings, vol = stage.look.music, float(feel.get("music_volume", 0.6))
    cues = stage.score.music if vol > 0 else []                  # the score names the cue; the look says what it sounds like
    tune = music.render(cues, stage.score.step, n, settings) * vol
    room = dict(settings.get("mix") or {}, **{k: float(feel.get(k, master.DEFAULTS[k])) for k in ("reverb", "duck", "warmth")})
    if only:                                                     # one layer alone, as it sits in the mix
        voices, effects, tune = (x if name == only else np.zeros(n) for name, x in (("voices", voices), ("sounds", effects), ("music", tune)))
    return wav_bytes(master.master(voices, effects, tune, room))
