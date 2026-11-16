"""Mixing and mastering: three buses (voices, effects, music) made into one finished signal.

The aim is a sound that is pleasant at any volume and never harsh. In order:

  each bus   a high-pass removes rumble nobody hears but every speaker has to move; a low-pass takes
             the edge off synthesised tones
  music      a dip around 3 kHz, where the ear is most sensitive and harshness lives; gentle
             saturation for warmth; a compressor so its loudest and softest moments sit closer together
  ducking    while someone speaks, the music steps back a few dB, and returns when they stop
  room       music, and a little of the voices, are sent to one shared room, so everything
             sounds as if it is in the same place
  master     a soft limiter rounds off any peak before it can clip
"""
from functools import lru_cache

import numpy as np
from scipy.fft import irfft, next_fast_len, rfft
from scipy.ndimage import maximum_filter1d
from scipy.signal import butter, lfilter

RATE = 44100
DEFAULTS = dict(reverb=0.22, room=1.1, duck=5.0, warmth=0.5, ceiling=0.89, music=0.7)
BLOCK = 64                                   # loudness is followed in blocks of this many samples: plenty for something that changes over milliseconds


def highpass(x, hz):
    return lfilter(*butter(2, hz, "highpass", fs=RATE), x)


def lowpass(x, hz):
    return lfilter(*butter(2, hz, "lowpass", fs=RATE), x)


@lru_cache(maxsize=16)
def curve(size, hp=0.0, lp=0.0, dip_hz=0.0, dip_db=0.0):
    """An equaliser as a gain per frequency: a high-pass, a low-pass (both 12 dB an octave), and a bell-shaped dip.
    Applied to a spectrum it changes levels only and shifts nothing in time."""
    f = np.fft.rfftfreq(size, 1 / RATE)
    g = np.ones(len(f))
    if hp:
        g *= (f / hp) ** 2 / np.sqrt(1 + (f / hp) ** 4)
    if lp:
        g /= np.sqrt(1 + (f / lp) ** 4)
    if dip_hz:
        g *= 10 ** (dip_db * np.exp(-0.5 * (np.log2(np.maximum(f, 1) / dip_hz) / 0.6) ** 2) / 20)     # about an octave and a half wide
    return g


def level(x, attack=0.01, release=0.15):
    """How loud a signal is from moment to moment: quick to rise, slow to fall."""
    n = len(x) // BLOCK * BLOCK
    power = (x[:n] ** 2).reshape(-1, BLOCK).mean(axis=1)
    rate = RATE / BLOCK
    k = np.exp(-1 / (attack * rate))
    fast = np.sqrt(np.maximum(lfilter([1 - k], [1, -k], power), 0))
    hold = max(1, int(release * rate))
    held = maximum_filter1d(fast, hold, origin=(hold - 1) // 2, mode="constant")       # each peak is held for the release time, looking back only
    k = np.exp(-1 / (release * 0.5 * rate))
    env = lfilter([1 - k], [1, -k], held)
    return np.interp(np.arange(len(x)), np.arange(len(env)) * BLOCK + BLOCK / 2, env)


def compress(x, threshold_db=-26.0, ratio=3.0, makeup_db=2.0):
    """Turn down what is above the threshold, by `ratio`, then bring the whole back up."""
    over = np.maximum(20 * np.log10(level(x) + 1e-9) - threshold_db, 0)
    return x * 10 ** ((makeup_db - over * (1 - 1 / ratio)) / 20)


def saturate(x, amount):
    """Soft saturation: the louder a moment, the more it is rounded off. Adds warmth; removes spikes."""
    if amount <= 0:
        return x
    drive = 1 + 2.5 * amount
    return np.tanh(drive * x) / drive


@lru_cache(maxsize=4)
def room(seconds):
    """The sound of a small room: a burst of noise dying away smoothly, dull at the top like soft walls."""
    n = int(seconds * RATE)
    t = np.arange(n) / RATE
    ir = np.random.default_rng(5).standard_normal(n) * np.exp(-6.9 * t / seconds)           # 60 dB down by the end
    ir = lowpass(highpass(ir, 250), 4500)
    ir[: int(0.012 * RATE)] = 0                                                              # a short gap before the room answers
    return ir / np.sqrt((ir ** 2).sum())


@lru_cache(maxsize=8)
def _room_spectrum(seconds, size):
    return rfft(room(seconds), size)


def master(voices, effects, music, settings=None):
    """Three dry buses of equal length -> one finished signal."""
    s = {**DEFAULTS, **(settings or {})}
    n = len(voices)
    seconds = float(s["room"])
    size = next_fast_len(n + int(seconds * RATE), real=True)
    said = rfft(voices, size) * curve(size, hp=90, lp=5200)
    spectrum = said + rfft(effects, size) * curve(size, hp=60, lp=7000)
    send = said * (float(s["reverb"]) * 0.3)                     # a little of the voices goes to the room; most of the music does
    if np.any(music):
        music = irfft(rfft(music, size) * curve(size, hp=40, lp=6500, dip_hz=3000, dip_db=-3.0), size)[:n] * float(s["music"])
        music = compress(saturate(music, float(s["warmth"])))
        talking = np.clip(level(voices, 0.02, 0.25) / 0.02, 0, 1)                           # 1 while a line is being spoken
        tune = rfft(music * 10 ** (-float(s["duck"]) * talking / 20), size)                 # the music steps back under a line
        spectrum = spectrum + tune
        send = send + tune * float(s["reverb"])
    if s["reverb"] > 0:                                          # one room for everything sent to it
        spectrum = spectrum + send * _room_spectrum(seconds, size)
    out = irfft(spectrum * curve(size, hp=30), size)[:n]
    c = float(s["ceiling"])
    return np.tanh(out / c) * c                                                              # nothing can pass the ceiling, and nothing near it is squared off
