import io
import wave

import numpy as np

from toon.performance import Scene, speech
from toon.presentation import sound

TONE, SCALE = dict(rate=2, contour="rise", range=3), [0, 2, 4, 7, 9]


def stresses(text):
    return [s["stress"] for s in speech.syllables(text)]


def test_syllables_and_stress_are_guessed_from_the_words():
    assert [s["text"].strip() for s in speech.syllables("There's sauce on your chin.")] == ["There's", "sauce", "on", "your", "chin."]
    assert stresses("There's sauce on your chin.") == [0, 1, 0, 0, 2]          # small words weak, last strong one the accent


def test_marks_override_the_guess():
    assert [s["text"].strip() for s in speech.syllables("Some·one ate")] == ["Some", "one", "ate"]
    assert stresses("to^day") == [0, 2]
    assert stresses("today") == [0, 2]                                          # on the exceptions list
    assert stresses("^everybody")[0] == 2


def test_stress_shapes_the_rhythm():
    plan = speech.plan("There's sauce on your chin.", TONE, SCALE)
    assert [p["len"] for p in plan] == [1, 2, 1, 1, 3]                           # weak half, strong full, accent half as long again
    assert len({p["len"] for p in plan}) > 1                                     # never one even pulse


def test_punctuation_is_a_breath():
    plan = speech.plan("Send me. I can't.", TONE, SCALE)
    assert plan[1]["rest"] == 2 and plan[-1]["rest"] == 0


def test_a_line_can_set_its_own_rhythm_melody_and_stress():
    plan = speech.plan("Ha ha ha", TONE, SCALE, rhythm=[4, 1, 1], melody=[0, 7, 12], stress=[2, 0, 0])
    assert [(p["at"], p["len"], p["semi"], p["stress"]) for p in plan] == [(0, 4, 0, 2), (4, 1, 7, 0), (5, 1, 12, 0)]


def test_every_note_starts_where_its_syllable_is_shown(show):
    path = show.scene("s01/e01/01", [dict(id=1, enter={"a": {"slot": 2}}, why="x"),
                                      dict(id=2, who="a", say="Someone ate the last dumpling.", why="x")])
    sc = Scene(path)
    sc.events = []                                                               # voices only
    w = wave.open(io.BytesIO(sound.mix(sc)))
    audio = np.abs(np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(float))
    for s in sc.lines[0]["sylls"]:
        i = int(s["start"] * sound.RATE)
        onset = i + int(np.argmax(audio[i:i + 4000] > 200))
        assert (onset - i) / sound.RATE < 0.005                                 # within 5 ms
