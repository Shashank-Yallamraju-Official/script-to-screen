"""The anthem: a title theme in the manner of an epic drama, for a show that asks for one (`theme: anthem` in
library/music.yaml). It is an original tune. What it takes from the genre is the build, not anyone's notes:

    low strings drive a short figure round and round, in a rolling six-to-the-bar
    a single dark string voice states a slow melody over it
    the melody comes back an octave up with everything behind it: more strings, voices, drums on every beat
    it ends on one held chord with no third in it, so it is neither sad nor glad

In D minor, twenty bars: two of the figure alone, eight of melody, eight of the melody again, two of the last chord.
The same piece plays under the title sequence and the end credits. Every sound is built from sine partials.
"""
from functools import lru_cache

import numpy as np
from scipy.signal import fftconvolve

RATE = 44100
BAR = 60.0 / 84 * 2                      # two slow beats a bar, each of three quick ones
E = BAR / 6                              # one quick one
BARS = 20
D3 = 146.83

# The eight-bar phrase. Chord roots, as semitones from D: D minor, C, B flat, A, D minor, C, A, D minor.
ROOTS = [0, -2, -4, -5, 0, -2, -5, 0]
MAJOR = [False, True, True, True, False, True, True, False]
# The melody: (semitones above D3, quick ones long), a bar to a line.
MELODY = [
    [(12, 3), (15, 3)],
    [(14, 3), (10, 2), (12, 1)],
    [(8, 3), (12, 3)],
    [(7, 6)],
    [(12, 3), (15, 3)],
    [(17, 3), (14, 2), (15, 1)],
    [(19, 3), (17, 2), (14, 1)],
    [(12, 6)],
]


def _hz(semi):
    return D3 * 2 ** (semi / 12)


def bowed(f, dur, vel, attack=0.09, release=0.22, dull=1.15):
    """A string section on one note: three players a hair apart, a slow bow, vibrato once the note has settled."""
    n = int((dur + release) * RATE)
    t = np.arange(n) / RATE
    vib = 1 + 0.004 * np.sin(2 * np.pi * 5.3 * t) * np.clip((t - 0.18) / 0.3, 0, 1)
    out = np.zeros(n)
    for off in (-0.0035, 0.0, 0.004):
        phase = 2 * np.pi * f * (1 + off) * np.cumsum(vib) / RATE
        for k in range(1, 10):
            if f * k < 6500:
                out += np.sin(k * phase) / k ** dull
    return out * np.clip(t / attack, 0, 1) * np.clip((dur + release - t) / release, 0, 1) * vel / 3


def struck(f, vel):
    """One short, dug-in stroke of the low strings: the driving figure."""
    x = bowed(f, E * 0.85, vel, attack=0.012, release=0.14, dull=1.0)
    return x * np.exp(-np.arange(len(x)) / RATE / 0.2)


def drum(vel):
    """A big, deep drum: a falling thud, and the slap of the skin."""
    n = int(0.9 * RATE)
    t = np.arange(n) / RATE
    thud = np.sin(2 * np.pi * np.cumsum(46 + 60 * np.exp(-t / 0.05)) / RATE) * np.exp(-t / 0.28)
    rng = np.random.default_rng(3)
    slap = np.convolve(rng.standard_normal(n), np.ones(24) / 24, mode="same") * np.exp(-t / 0.045)
    return (thud + 0.5 * slap) * vel


def voices(f, dur, vel):
    """Held voices, far back: few partials and a very slow swell."""
    n = int((dur + 0.6) * RATE)
    t = np.arange(n) / RATE
    out = sum(np.sin(2 * np.pi * f * k * (1 + d) * t) / k ** 2 for k in (1, 2, 3, 4) for d in (-0.003, 0.003))
    return out * np.clip(t / 0.5, 0, 1) * np.clip((dur + 0.6 - t) / 0.6, 0, 1) * vel / 3


@lru_cache(maxsize=1)
def _piece():
    track = np.zeros(int((BARS * BAR + 4.0) * RATE))

    def put(at, x, gain=1.0):
        i = int(at * RATE)
        track[i:i + len(x)] += x[: len(track) - i] * gain

    def figure(bar, root, major, loud, doubled=False):
        steps = [0, 7, 9 if major else 8, 7, 0, 7]                   # root, fifth, the note above it, and back: round and round
        for k, s in enumerate(steps):
            put(bar * BAR + k * E, struck(_hz(root + s - 12), loud * (1.0 if k in (0, 3) else 0.7)))
            if doubled:
                put(bar * BAR + k * E, struck(_hz(root + s), loud * 0.45))

    for bar in range(2):                                             # the figure alone
        figure(bar, 0, False, 0.75)
        put(bar * BAR, drum(0.9))
    for rep in range(2):                                             # the melody, then the melody with everything
        full = rep == 1
        for k in range(8):
            bar = 2 + 8 * rep + k
            figure(bar, ROOTS[k], MAJOR[k], 0.8 if full else 0.6, doubled=full)
            at = bar * BAR
            for semi, length in MELODY[k]:
                put(at, bowed(_hz(semi + (12 if full else 0)), length * E * 0.96, 0.95 if full else 0.8, dull=1.25 if full else 1.4))
                if full:
                    put(at, bowed(_hz(semi), length * E * 0.96, 0.5, dull=1.3))
                at += length * E
            if full:
                third = 4 if MAJOR[k] else 3
                for s in (0, third, 7, 12):
                    put(bar * BAR, voices(_hz(ROOTS[k] + s), BAR * 0.95, 0.34))
                put(bar * BAR, drum(1.0))
                put(bar * BAR + 3 * E, drum(0.55))
            elif k % 2 == 0:
                put(bar * BAR, drum(0.6))
    last = 18 * BAR                                                  # the last chord: root and fifth only, every octave
    put(last, drum(1.2))
    for s, v in ((-24, 0.9), (-12, 0.9), (-5, 0.6), (0, 0.8), (7, 0.6), (12, 0.7), (24, 0.35)):
        put(last, bowed(_hz(s), 2 * BAR + 0.6, v, attack=0.05, release=1.4, dull=1.2))
    for s in (0, 7, 12):
        put(last, voices(_hz(s), 2 * BAR + 0.4, 0.4))
    rng = np.random.default_rng(5)                                   # a large stone room around all of it
    n = int(1.6 * RATE)
    room = np.convolve(rng.standard_normal(n), np.ones(6) / 6, mode="same") * np.exp(-np.arange(n) / RATE / 0.42)
    wet = fftconvolve(track, room / np.sqrt(np.sum(room ** 2)), mode="full")[: len(track)]
    out = track + 0.3 * wet
    return np.tanh(out / np.max(np.abs(out)) * 1.4) * 0.8


def bed(seconds, ring=3.2):
    """The anthem's low figure alone, going round its chords, for `seconds`: what plays under a journey over the land. It comes up
    from nothing over its first bar, and ends on the bare last chord, held and let go slowly, so it rings on into whatever follows."""
    n = int((seconds + ring + 0.5) * RATE)
    track = np.zeros(n)

    def put(at, x, gain=1.0):
        i = int(at * RATE)
        if 0 <= i < n:
            track[i:i + len(x)] += x[: n - i] * gain

    bars = int(seconds / BAR)
    for bar in range(bars):
        k = bar % 8
        steps = [0, 7, 9 if MAJOR[k] else 8, 7, 0, 7]
        for j, s in enumerate(steps):
            put(bar * BAR + j * E, struck(_hz(ROOTS[k] + s - 12), 0.6 * (1.0 if j in (0, 3) else 0.7)))
        put(bar * BAR, drum(0.45))
        put(bar * BAR, voices(_hz(ROOTS[k]), BAR * 0.95, 0.22))
        put(bar * BAR, voices(_hz(ROOTS[k] + 7), BAR * 0.95, 0.16))
    last = bars * BAR                                                # the last chord: root and fifth, let go slowly
    for s, v in ((-24, 0.7), (-12, 0.7), (-5, 0.45), (0, 0.5), (7, 0.35)):
        put(last, bowed(_hz(s), max(0.4, seconds - last) + ring * 0.4, v * 0.45, attack=0.08, release=ring * 0.6, dull=1.3))
    put(last, drum(0.4))
    t = np.arange(n) / RATE
    track *= np.clip(t / BAR, 0, 1) ** 1.5
    rng = np.random.default_rng(5)
    m = int(1.6 * RATE)
    room = np.convolve(rng.standard_normal(m), np.ones(6) / 6, mode="same") * np.exp(-np.arange(m) / RATE / 0.42)
    out = track + 0.3 * fftconvolve(track, room / np.sqrt(np.sum(room ** 2)), mode="full")[:n]
    out[-int(0.4 * RATE):] *= np.linspace(1, 0, int(0.4 * RATE))
    return np.tanh(out / np.max(np.abs(out)) * 1.2) * 0.62


def render(seconds):
    """The anthem as samples, `seconds` long (plus its tail). Shorter than the piece, it is faded out early."""
    piece = _piece()
    n = int((seconds + 1.6) * RATE)
    out = np.zeros(n)
    m = min(n, len(piece))
    out[:m] = piece[:m]
    if seconds < BARS * BAR - 0.5:
        fade = int(1.5 * RATE)
        k = int(seconds * RATE)
        out[k - fade:k] *= np.linspace(1, 0, fade)
        out[k:] = 0
    return out
