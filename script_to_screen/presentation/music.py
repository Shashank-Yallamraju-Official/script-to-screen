"""Music: harmony and instruments for the cues the score names.

Harmony. Every figure is written in scale degrees, and the mode is chosen by what the cue
means. The seven modes of one key run from bright to dark as their notes are lowered one at
a time, so "how good or bad is this news" maps onto a single dial:

    lydian      1 2 3 #4 5 6 7     the raised fourth floats: wonder, relief, a door opening
    major       1 2 3 4 5 6 7      plain good news
    mixolydian  1 2 3 4 5 6 b7
    dorian      1 2 b3 4 5 6 b7
    aeolian     1 2 b3 4 5 b6 b7   plain bad news: natural minor
    phrygian    1 b2 b3 4 5 b6 b7  the lowered second leans on the root from a semitone above: dread
    locrian     1 b2 b3 4 b5 b6 b7 even the fifth is gone, so there is nowhere to rest: the worst news

A question uses none of them: it is voiced in stacked fourths with no third at all. The third
is the note that makes a chord major or minor, so leaving it out says "not yet good or bad".
A build-up climbs to the leading tone, a semitone under the root, which the ear wants resolved;
the moment it leads to begins on the root and resolves it.

Instruments. Each is built from sine partials with its own envelope, never a bare square or
triangle wave, because raw waveforms are what make synthesised music sound harsh:

    keys    a soft mallet: upper partials die away faster than the fundamental, as in a struck bar
    warm    a low, rounded tone, gently saturated so it is still heard on small speakers
    glass   a slow-swelling held tone with a little vibrato
"""
from functools import lru_cache

import numpy as np

RATE = 44100
MODES = {"lydian": (0, 2, 4, 6, 7, 9, 11), "major": (0, 2, 4, 5, 7, 9, 11), "mixolydian": (0, 2, 4, 5, 7, 9, 10),
         "dorian": (0, 2, 3, 5, 7, 9, 10), "aeolian": (0, 2, 3, 5, 7, 8, 10), "phrygian": (0, 1, 3, 5, 7, 8, 10),
         "locrian": (0, 1, 3, 5, 6, 8, 10)}
BRIGHT_TO_DARK = tuple(MODES)

# Which mode a cue is voiced in: the first entry whose strength the cue reaches.
MODE_FOR = {"turn.good": ((0.5, "lydian"), (0.0, "major")),
            "turn.bad": ((0.6, "locrian"), (0.45, "phrygian"), (0.0, "aeolian")),
            "question": ((0.0, "mixolydian"),), "rise": ((0.0, "major"),)}

# A figure is a list of notes: [steps after the cue, scale degree (1 = the root; 8 = the root an octave up),
# octaves above or below, steps long, how hard it is played (0 to 1)], each with the instrument that plays it.
FIGURES = {
    "turn.good": {"keys": [[0, 1, -1, 8, 0.7], [0, 1, 0, 2, 0.8], [1, 3, 0, 2, 0.75], [2, 5, 0, 2, 0.8], [3, 7, 0, 3, 0.85], [4, 9, 0, 8, 1.0],
                           [4, 4, 0, 8, 0.45]]},      # an arpeggio up through the seventh to the ninth; the fourth sounds under the last note (in lydian it is the raised one)
    "turn.bad": {"warm": [[0, 1, -2, 12, 1.0], [0, 5, -1, 5, 0.6]],                                   # a low root; over it the fifth (in locrian, a tritone)
                 "keys": [[0, 3, -1, 2.5, 0.8], [2, 2, -1, 2.5, 0.75], [4, 1, -1, 7, 0.9]]},          # a sigh down 3, 2, 1: in phrygian the 2 is a semitone above the root
    "question": {"glass": [[0, 1, 1, 12, 0.7], [0.75, 4, 1, 11, 0.7], [1.5, 7, 1, 10, 0.75], [2.25, 9, 1, 9, 0.6]]},    # root, fourth, flat seventh, ninth: fourths stacked up, and no third anywhere
    "rise": {},                                       # (a build-up is a glide, not notes: see `riser`)
}


def _bars(*bars):
    """Notes written a bar at a time (16 steps to the bar) -> one list of notes."""
    return [[16 * k + at, degree, octave, length, vel] for k, bar in enumerate(bars) for at, degree, octave, length, vel in bar]


# The show's theme, in major. The melody is one bar-long shape, a fall from the fifth and a climb back, moved through
# four chords (I, vi, IV, V); the title card plays its first bar and resolves, the credits play it twice and come home.
_A = [[0, 5, 1, 2, .8], [2, 3, 1, 2, .7], [4, 8, 1, 2, .85], [6, 5, 1, 2, .7], [8, 6, 1, 2, .8], [10, 5, 1, 2, .7], [12, 3, 1, 4, .75]]
_B = [[0, 6, 1, 2, .8], [2, 5, 1, 2, .7], [4, 3, 1, 2, .75], [6, 1, 1, 2, .7], [8, 2, 1, 2, .75], [10, 3, 1, 2, .7], [12, 1, 1, 4, .75]]
_C = [[0, 4, 1, 2, .8], [2, 6, 1, 2, .7], [4, 8, 1, 2, .85], [6, 6, 1, 2, .7], [8, 4, 1, 2, .75], [10, 6, 1, 2, .7], [12, 5, 1, 4, .8]]
_D = [[0, 5, 1, 2, .8], [2, 7, 1, 2, .7], [4, 9, 1, 2, .85], [6, 7, 1, 2, .7], [8, 5, 1, 2, .75], [10, 4, 1, 2, .7], [12, 2, 1, 4, .75]]
_HOME = [[0, 5, 1, 2, .8], [2, 3, 1, 2, .75], [4, 2, 1, 4, .75], [8, 1, 1, 10, .9], [8, 8, 1, 10, .6]]
_LOW = dict(I=[[0, 1, -1, 8, .8], [8, 5, -1, 6, .6]], vi=[[0, 6, -2, 8, .8], [8, 3, -1, 6, .6]], IV=[[0, 4, -1, 8, .8], [8, 8, -1, 6, .6]],
            V=[[0, 5, -2, 8, .8], [8, 2, -1, 6, .6]], home=[[0, 5, -2, 6, .8], [8, 1, -1, 12, .9]])
_PAD = dict(I=[[0, 1, 0, 14, .32], [0, 3, 0, 14, .28], [0, 5, 0, 14, .28]], vi=[[0, 6, -1, 14, .32], [0, 1, 0, 14, .28], [0, 3, 0, 14, .28]],
            IV=[[0, 4, -1, 14, .32], [0, 6, -1, 14, .28], [0, 1, 0, 14, .28]], V=[[0, 5, -1, 14, .32], [0, 7, -1, 14, .28], [0, 2, 0, 14, .28]],
            home=[[8, 1, 0, 16, .4], [8, 3, 0, 16, .32], [8, 5, 0, 16, .32], [8, 9, 0, 16, .25]])
FIGURES["theme.title"] = {"keys": _A[:6] + [[12, 8, 1, 12, .9]], "warm": [[0, 1, -1, 10, .8], [12, 1, -1, 14, .9]],
                          "glass": [[12, 1, 0, 16, .4], [12, 3, 0, 16, .32], [12, 5, 0, 16, .32], [12, 9, 0, 16, .25]]}
FIGURES["theme.credits"] = {"keys": _bars(_A, _B, _C, _D, _A, _B, _C, _HOME),
                            "warm": _bars(*[_LOW[c] for c in ("I", "vi", "IV", "V", "I", "vi", "IV", "home")]),
                            "glass": _bars(*[_PAD[c] for c in ("I", "vi", "IV", "V", "I", "vi", "IV", "home")])}


def mode_for(kind, strength, table=None):
    for least, mode in (table or MODE_FOR).get(kind, ((0.0, "major"),)):
        if strength + 1e-9 >= least:
            return mode
    return "major"


def semitones(mode, degree, octave=0):
    """Semitones above the key for a scale degree of a mode. Degrees run on past 7 into the next octave."""
    d = int(degree) - 1
    return MODES[mode][d % 7] + 12 * (d // 7 + octave)


def _fade(n, attack, release):
    """A smooth rise and fall (raised cosine), so no note begins or ends with a click."""
    env = np.ones(n)
    a, r = min(n, max(1, int(attack * RATE))), min(n, max(1, int(release * RATE)))
    env[:a] *= 0.5 - 0.5 * np.cos(np.pi * np.arange(a) / a)
    env[-r:] *= 0.5 + 0.5 * np.cos(np.pi * np.arange(r) / r)
    return env


def remembered(fn):
    """A note of the same pitch, length and force is the same sound: work it out once."""
    made = lru_cache(maxsize=512)(fn)
    return lambda hz, dur, vel=0.8: made(round(float(hz), 3), round(float(dur), 4), round(float(vel), 3))


@remembered
def keys(hz, dur, vel=0.8):
    """A soft mallet. Six partials; the higher a partial, the quieter it starts and the sooner it dies, and a
    harder stroke brings out more of them. Two copies a few cents apart give it a gentle shimmer."""
    n = max(1, int((dur + 1.2) * RATE))                    # it rings on after the note's written length
    t = np.arange(n) / RATE
    out = np.zeros(n)
    for cents in (-3.5, 3.5):
        f = hz * 2 ** (cents / 1200)
        for k, amp in enumerate((1.0, 0.42, 0.2, 0.09, 0.04, 0.02), 1):
            if f * k < 6000:                               # nothing bright enough to sting
                out += amp * (0.35 + 0.65 * vel) ** (k - 1) * np.sin(2 * np.pi * f * k * t) * np.exp(-t * (1.6 + 1.3 * k) / max(dur * 2.2, 0.5))
    return out * 0.2 * _fade(n, 0.006, 0.25) * vel


@remembered
def warm(hz, dur, vel=0.8):
    """A low, rounded tone: a sine with a little second harmonic, pushed gently into saturation. The saturation adds
    quiet overtones, which is what lets a low note be heard on small speakers without being turned up."""
    n = max(1, int((dur + 0.5) * RATE))
    t = np.arange(n) / RATE
    x = np.sin(2 * np.pi * hz * t) + 0.25 * np.sin(4 * np.pi * hz * t + 0.6)
    x = np.tanh(1.6 * x) / np.tanh(1.6)
    return x * 0.3 * _fade(n, 0.05, 0.45) * np.exp(-t / max(dur * 3, 1.0)) * vel


@remembered
def glass(hz, dur, vel=0.7):
    """A held tone that swells in slowly, with a slight vibrato that deepens as it goes."""
    n = max(1, int((dur + 0.8) * RATE))
    t = np.arange(n) / RATE
    vib = 1 + 0.0035 * np.minimum(1, t / 0.8) * np.sin(2 * np.pi * 5.2 * t)
    phase = 2 * np.pi * np.cumsum(hz * vib) / RATE
    x = np.sin(phase) + 0.12 * np.sin(2 * phase) + 0.05 * np.sin(3 * phase)
    return x * 0.22 * _fade(n, 0.18, 0.7) * vel


@lru_cache(maxsize=32)
def riser(hz0, hz1, dur, vol, timbre=None):
    """A build-up: a tone gliding from hz0 to hz1 that swells as it goes, with breath over it that opens up
    (filtered noise whose brightness rises), and a tremble that quickens. It lets go as the moment lands."""
    from scipy.signal import butter, lfilter
    n = max(1, int(dur * RATE))
    u = np.arange(n) / n
    phase = 2 * np.pi * np.cumsum(hz0 * (hz1 / hz0) ** u) / RATE
    tone = np.sin(phase) + 0.3 * np.sin(2 * phase) + 0.1 * np.sin(3 * phase)
    noise = np.random.default_rng(11).standard_normal(n)
    breath = np.zeros(n)
    for k, (lo, hi) in enumerate(((0.0, 0.5), (0.5, 0.8), (0.8, 1.0))):          # the breath brightens in three stages
        band = lfilter(*butter(2, [300 + 500 * k, 900 + 1100 * k], "bandpass", fs=RATE), noise)
        breath += band * np.clip((u - lo) / max(hi - lo, 1e-6), 0, 1) * (1 if k == 0 else 0.6)
    tremble = 1 - 0.18 * (0.5 + 0.5 * np.sin(2 * np.pi * np.cumsum(3 + 8 * u) / RATE))
    out = (0.55 * tone + 0.22 * breath) * u ** 2 * tremble * vol
    tail = min(n, int(0.03 * RATE))
    out[-tail:] *= 0.5 + 0.5 * np.cos(np.pi * np.arange(tail) / tail)
    return out


INSTRUMENTS = {"keys": keys, "warm": warm, "glass": glass}


def render(cues, step, total, settings=None):
    """The music for a scene: every cue's figure, in its mode, as one dry signal of `total` samples."""
    settings = settings or {}
    key = float(settings.get("key", 220))
    out = np.zeros(total)

    def add(at, x):
        i = int(at * RATE)
        if 0 <= i < total:
            out[i:i + len(x)] += x[: total - i]

    for cue in cues:
        level = 0.55 + 0.45 * cue["strength"]
        if cue["kind"] == "rise":
            lo, hi = settings.get("rise", {}).get("from", -17), settings.get("rise", {}).get("to", -1)     # up to the leading tone, a semitone under the root
            add(cue["t"], riser(round(key * 2 ** (lo / 12), 3), round(key * 2 ** (hi / 12), 3), round(cue["length"], 4), round(0.32 * level, 4)))
            continue
        mode = mode_for(cue["kind"], cue["strength"], settings.get("modes"))
        figure = (settings.get("figures") or {}).get(cue["kind"]) or FIGURES.get(cue["kind"], {})
        for name, notes in figure.items():
            for at, degree, octave, length, vel in notes:
                add(cue["t"] + at * step, INSTRUMENTS[name](key * 2 ** (semitones(mode, degree, octave) / 12), length * step, vel) * level)
    return out
