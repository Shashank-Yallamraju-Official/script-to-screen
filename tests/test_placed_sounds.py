"""Small timings set by hand in the editor: when a sound starts, how long it lasts, how loud it is,
which bar a line lands on, and where a card's music lands."""
import io
import wave

import numpy as np
import pytest
import yaml

from script_to_screen.commands import edit
from script_to_screen.presentation import sound
from script_to_screen.presentation.episode import parts, soundtrack
from script_to_screen.tools.editor import Session

ENTER = dict(id=1, enter={"a": {"slot": 2}, "b": {"slot": 5}}, why="They are here.")
LINE = dict(id=2, who="a", say="Someone ate the last dumpling.", bar=4, why="She knows.")
BANG = dict(id=3, sfx=[dict(at=0, sound="blast", on="b")], why="It goes off.")


@pytest.fixture
def sess(show):
    with open(show.root / "show.yaml", "a") as f:
        f.write("\nbeats_per_bar: 2\n")
    return Session(show.scene("room", [ENTER, LINE, BANG]))


def heard(stage):
    with wave.open(io.BytesIO(sound.mix(stage))) as w:
        return np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(float)


def test_a_placed_sound_can_be_moved_stretched_and_turned_down_by_hand(sess):
    fx = lambda: sess.state()["turns"][2]["sfx"][0]
    assert (fx()["at"], fx()["len"], fx()["vol"]) == (0, 16, 1)
    loud = np.abs(heard(sess.stage)).max()
    for name, value in (("at", 3), ("len", 9), ("vol", 0.4)):
        sess.patch([dict(path=["turns", 2, "sfx", 1, name], value=value)], commit=True)
    assert (fx()["at"], fx()["len"], fx()["vol"]) == (3, 9, 0.4)
    assert yaml.safe_load(sess.path.read_text())["turns"][2]["tune"] == {"sfx_at": {1: 3}, "sfx_len": {1: 9}, "sfx_vol": {1: 0.4}}
    assert yaml.safe_load(sess.path.read_text())["turns"][2]["sfx"] == BANG["sfx"]              # what was written stays as written
    assert np.abs(heard(sess.stage)).max() < loud * 0.8


def test_the_same_sound_is_on_the_knob_by_its_address(sess):
    assert sess.value("room:3.x1.len")["value"] == 16
    sess.nudge("room:3.x1.len", "set", 12)
    assert sess.state()["turns"][2]["sfx"][0]["len"] == 12
    sess.nudge("room:3.x1.len", "reset")
    assert sess.state()["turns"][2]["sfx"][0]["len"] == 16 and "tune" not in yaml.safe_load(sess.path.read_text())["turns"][2]


def test_every_sound_of_a_kind_has_one_level_of_its_own(sess):
    before = np.abs(heard(sess.stage)).max()
    (sess.root / "library" / "sounds.yaml").write_text((sess.root / "library" / "sounds.yaml").read_text() + "\nblast: {vol: 0.3}\n")
    sess.sync()
    assert np.abs(heard(sess.stage)).max() < before * 0.8             # quieter, though the mix is evened out afterwards


def test_a_line_can_be_slid_to_another_bar(sess):
    bar = sess.state()["bar"]
    assert bar == 8 and sess.state()["turns"][1]["start"] + sess.state()["turns"][1]["say"]["at"] == pytest.approx(4 * bar)
    sess.patch([dict(path=["turns", 1, "bar"], value=5.5)], commit=True)
    t = sess.state()["turns"][1]
    assert t["bar"] == 5.5 and t["start"] + t["say"]["at"] == pytest.approx(5.5 * bar)
    assert yaml.safe_load(sess.path.read_text())["turns"][1]["tune"] == {"bar": 5.5}
    edit.undo(sess.root, by="hand")
    sess.load()
    assert sess.state()["turns"][1]["bar"] == 4


def test_a_cards_music_can_be_moved_and_turned_down_and_the_film_follows(sess):
    series = yaml.safe_load((sess.root / "series.yaml").read_text())
    series["seasons"][0]["episodes"][0]["segments"].append(dict(id="end", card="credits"))
    (sess.root / "series.yaml").write_text(yaml.safe_dump(series))
    sess.sync()
    assert [(p["id"], p["kind"], p["here"]) for p in sess.episode()] == [("room", "scene", True), ("end", "credits", False)]
    plan, look, _ = parts(sess.root, "e")
    was = soundtrack(plan, look.fps)
    sess.open_part("end")
    st = sess.state()
    assert st["card"]["music"]["at"] == 0 and st["card"]["music"]["vol"] == 1 and len(sess.frame(0, False, False)) > 1000
    sess.patch([dict(path=["card", "music_at"], value=1.5)])                                    # a drag only shows
    assert sess.state()["card"]["music"]["at"] == 1.5 and "tune" not in (sess.root / "series.yaml").read_text()
    sess.patch([dict(path=["card", "music_at"], value=1.5)], commit=True)
    sess.patch([dict(path=["card", "music_vol"], value=0.5)], commit=True)
    seg = yaml.safe_load((sess.root / "series.yaml").read_text())["seasons"][0]["episodes"][0]["segments"][-1]
    assert seg["tune"] == {"music_at": 1.5, "music_vol": 0.5}
    plan, look, _ = parts(sess.root, "e")
    now = soundtrack(plan, look.fps)
    start = int(sum(p["frames"] for p in plan[:-1]) / look.fps * sound.RATE)
    assert np.abs(now[start:]).max() < np.abs(was[start:]).max() and not np.allclose(now[start:start + sound.RATE * 2], was[start:start + sound.RATE * 2])
    sess.step("undo")
    sess.step("undo")
    assert "tune" not in (sess.root / "series.yaml").read_text()
    with pytest.raises(ValueError):
        sess.patch([dict(path=["turns", 0, "hold"], value=3)], commit=True)                     # a card has no turns to drag
    sess.open_part("room")
    assert sess.state()["turns"][2]["sfx"]


def test_one_layer_can_be_heard_alone_and_the_sound_has_a_shape(sess):
    everything, sounds, voices = (np.frombuffer(sess.audio(only), dtype=np.int16).astype(float) for only in (None, "sounds", "voices"))
    assert np.abs(sounds).max() > 1000 and np.abs(voices).max() > 1000 and not np.array_equal(everything, sounds)
    bang = int(sess.state()["turns"][2]["start"] * sess.scene.step * sound.RATE) + 2000
    assert np.abs(voices[bang:bang + 20000]).max() < np.abs(sounds[bang:bang + 20000]).max() * 0.2      # the explosion is not in the voices
    shape = sess.wave("sounds")
    assert shape["per"] == 4 and len(shape["peaks"]) >= int(sess.scene.steps * 4) and 0 < max(shape["peaks"]) <= 1
    at = int(np.argmax(shape["peaks"])) / 4
    assert sess.state()["turns"][2]["start"] - 1 <= at                                                 # and its tallest point is the explosion


def test_a_sound_and_a_cards_music_can_fade(sess):
    x = np.ones(sound.RATE)
    y = sound.faded(x, 0.25, 0.5)
    assert y[0] == 0 and y[-1] == 0 and y[sound.RATE // 2 - 100] == 1 and x[0] == 1                     # and the sound it was given is untouched
    before = heard(sess.stage)
    sess.patch([dict(path=["turns", 2, "sfx", 1, "fade_in"], value=12)], commit=True)
    assert sess.state()["turns"][2]["sfx"][0]["fade_in"] == 12 and yaml.safe_load(sess.path.read_text())["turns"][2]["tune"] == {"sfx_fade_in": {1: 12}}
    assert not np.array_equal(before, heard(sess.stage))
    series = yaml.safe_load((sess.root / "series.yaml").read_text())
    series["seasons"][0]["episodes"][0]["segments"].append(dict(id="end", card="credits"))
    (sess.root / "series.yaml").write_text(yaml.safe_dump(series))
    sess.sync()
    sess.open_part("end")
    sess.patch([dict(path=["card", "music_out"], value=2)], commit=True)
    assert sess.state()["card"]["music"]["fade_out"] == 2
    plan, look, _ = parts(sess.root, "e")
    x, end = plan[-1]["sound"](), int(plan[-1]["frames"] / look.fps * sound.RATE)
    assert np.abs(x[end:]).max() == 0 and np.abs(x[end - 3 * sound.RATE:end - 2 * sound.RATE]).max() > 0  # silent by the card's end, sounding before it
