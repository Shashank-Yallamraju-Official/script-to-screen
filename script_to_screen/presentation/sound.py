"""Sound: synthesises a scene's voices and effects from its events and lines."""
import io
import math
import wave

import numpy as np

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


# One short figure per kind of cue, unless library/music.yaml says otherwise. `key` is the pitch of note 0 in Hz.
# A note is [steps after the cue, semitones above the key, steps long].
MUSIC = {"key": 220, "attack": 0.03, "ring": 0.35,
         "turn.bad": {"wave": "tri", "vol": 0.5, "notes": [[0, -12, 7], [0, -6, 7], [2, -13, 6]]},              # low, with a tritone: it sinks
         "turn.good": {"wave": "sine", "vol": 0.45, "notes": [[0, 0, 2], [1, 4, 2], [2, 7, 2], [3, 12, 6]]},      # a rising bright arpeggio
         "question": {"wave": "sine", "vol": 0.35, "notes": [[0, 14, 9], [0.5, 19, 8]]},                          # two high held notes: unresolved
         "rise": {"wave": "tri", "vol": 0.4, "from": -17, "to": -5}}                                              # a tone that climbs and swells until the moment lands


def riser(hz0, hz1, dur, vol, timbre="tri"):
    """A build-up: one tone gliding from hz0 to hz1 over `dur` seconds, swelling as it goes, with a slow shiver that quickens."""
    n = max(1, int(dur * RATE))
    u = np.arange(n) / n
    hz = hz0 * (hz1 / hz0) ** u
    phase = 2 * np.pi * np.cumsum(hz) / RATE
    shiver = 1 - 0.25 * (0.5 + 0.5 * np.sin(2 * np.pi * np.cumsum(3 + 9 * u) / RATE))
    out = _osc(timbre, phase) * vol * u ** 2 * shiver
    out[-int(0.02 * RATE):] *= np.linspace(1, 0, int(0.02 * RATE))      # let go just as the moment lands
    return out


def figure(music, kind):
    """A cue kind's figure: the show's own, else the built-in one."""
    return {**MUSIC.get(kind, {}), **(music.get(kind) or {})}


def mix(stage):
    """The whole scene's sound: one note per syllable, plus an effect per event."""
    audio = np.zeros(int((stage.score.dur + 0.6) * RATE), dtype=np.float64)
    feel = stage.look.feel

    def add(at, x):
        i = int(at * RATE)
        if 0 <= i < len(audio):
            audio[i:i + len(x)] += x[: len(audio) - i]

    for line in stage.score.speech:
        ent, tone = stage.look.cast[line["who"]], stage.look.tones[line["tone"]]
        for s in line["sylls"]:
            hz = ent["voice"] * tone.get("pitch", 1) * 2 ** (s["semi"] / 12)
            add(s["start"], note(hz, min(s["voiced"], 0.6), tone.get("vol", 0.5) * LOUD[s["stress"]], ent.get("timbre", "sine"),
                                 float(feel["voice_attack"]), float(feel["voice_ring"])))
    aside = float(feel["aside_volume"])                          # a reaction in passing is quieter
    for at, name, _, quiet in stage.score.events:
        p = sound_for(stage.look.sounds, name)
        if p and float(p.get("vol", 0)) > 0:
            add(at, effect(p) * (aside if quiet else 1.0))
    music, step = stage.look.music, stage.score.step
    key, vol = float(music.get("key", MUSIC["key"])), float(feel.get("music_volume", 0.6))
    for cue in stage.score.music if vol > 0 else []:             # the score names the cue; the look says what it sounds like
        fig = figure(music, cue["kind"])
        if cue["kind"] == "rise":
            add(cue["t"], riser(key * 2 ** (float(fig.get("from", -17)) / 12), key * 2 ** (float(fig.get("to", -5)) / 12), cue["length"],
                                float(fig.get("vol", 0.4)) * vol * (0.5 + 0.5 * cue["strength"]), fig.get("wave", "tri")))
            continue
        for at, semi, length in fig.get("notes", []):
            add(cue["t"] + at * step, note(key * 2 ** (semi / 12), min(length * step, 1.6), float(fig.get("vol", 0.4)) * vol * (0.5 + 0.5 * cue["strength"]),
                                           fig.get("wave", "sine"), float(music.get("attack", MUSIC["attack"])), float(music.get("ring", MUSIC["ring"]))))
    return wav_bytes(audio)
