"""Frames are kept by what they show. The cache must never hand back a frame that a fresh draw would not produce."""
from pathlib import Path

import pytest

from script_to_screen.performance import Scene
from script_to_screen.presentation.framecache import FrameCache
from script_to_screen.presentation.render import frame_jpeg
from script_to_screen.presentation.stage import Look, Stage
from script_to_screen.script import load_yaml, series

DEMO = Path(__file__).resolve().parents[1] / "shows" / "demo"


def staged(scene_id, change=None):
    path = series(DEMO).by_id[scene_id]["path"]
    doc = load_yaml(path)
    if change:
        change(doc)
    return Stage.of(Scene(path, script=doc))


def fill(cache, stage, step=1):
    for F in range(0, stage.total, step):
        cache.get(stage, F)


@pytest.mark.parametrize("scene_id,steps", [("the-vase", 2), ("the-vase", 1), ("the-vase", 0.5), ("the-last-dumpling", 1)])
def test_after_a_turn_gets_longer_every_frame_from_the_cache_is_what_a_fresh_draw_gives(scene_id, steps):
    """Two steps is a whole number of frames, so later turns come from the cache; 1 and 0.5 are not, so they are
    drawn afresh. Either way: the fingerprint must capture everything a frame depends on: easing in from the turn before, a held
    reaction fading across a boundary, bubbles. If it missed anything, some frame here would differ."""
    cache = FrameCache()
    fill(cache, staged(scene_id))

    def longer(doc):
        doc["turns"][1]["hold"] = float(doc["turns"][1].get("hold", 8)) + steps
    after = staged(scene_id, longer)
    for F in range(after.total):
        assert cache.get(after, F) == frame_jpeg(after, F, 0.5, 82), f"frame {F}"


def test_a_turn_that_moved_by_whole_frames_is_not_drawn_again():
    cache = FrameCache()
    before = staged("the-vase")
    fill(cache, before)
    drawn = cache.draws

    def longer(doc):
        doc["turns"][1]["hold"] = float(doc["turns"][1].get("hold", 8)) + 2      # 2 steps = 15 frames at 60 a second
    after = staged("the-vase", longer)
    fill(cache, after)
    changed = after.score.turns[1]
    its_frames = round(changed["length"] * after.score.step * after.fps)
    assert cache.draws - drawn <= its_frames + 2, "only the turn that changed should have been drawn"


def test_going_back_to_a_value_tried_before_draws_nothing():
    cache = FrameCache()
    a = staged("the-vase")
    fill(cache, a, 3)
    b = staged("the-vase", lambda doc: doc["turns"][2].__setitem__("pause", 9))
    fill(cache, b, 3)
    drawn = cache.draws
    fill(cache, staged("the-vase"), 3)                                  # back to the first value: a new build, the same content
    assert cache.draws == drawn


def test_a_change_to_the_sound_keeps_every_frame_and_a_change_to_the_look_keeps_none():
    cache = FrameCache()
    stage = staged("the-vase")
    fill(cache, stage, 5)
    drawn = cache.draws
    louder = Stage(stage.score, Look.load(DEMO, stage.score.cast, lib=dict(feel=dict(load_yaml(DEMO / "library" / "feel.yaml"), voice_ring=0.2))), DEMO)
    fill(cache, louder, 5)
    assert cache.draws == drawn
    bouncier = Stage(stage.score, Look.load(DEMO, stage.score.cast, lib=dict(feel=dict(load_yaml(DEMO / "library" / "feel.yaml"), ease=0.5))), DEMO)
    fill(cache, bouncier, 5)
    assert cache.draws == drawn * 2


def test_the_cache_stays_within_its_size_and_drops_the_oldest_first():
    cache = FrameCache(limit=40_000)
    stage = staged("the-vase")
    fill(cache, stage, 10)
    assert cache.size <= 40_000 and len(cache.frames) < stage.total // 10
    last = cache.key(stage, (stage.total - 1) // 10 * 10, 0.5, 82, False)
    assert last in cache.frames and cache.key(stage, 0, 0.5, 82, False) not in cache.frames


def test_music_drawn_on_screen_is_part_of_what_a_frame_shows():
    """With a way of showing music chosen, every cached frame must still equal a fresh draw."""
    cache = FrameCache()
    path = series(DEMO).by_id["the-morally-righteous-location"]["path"]
    sc = Scene(path)

    def staged_as(style):
        stage = Stage.of(sc)
        stage.look.style = dict(stage.look.style, music=style)
        return stage
    plain, line = staged_as("none"), staged_as("line")
    rise = next(c for c in sc.score.music if c["kind"] == "rise")
    frames = range(round(rise["t"] * plain.fps) - 10, round((rise["t"] + rise["length"]) * plain.fps) + 120, 3)
    for F in frames:
        cache.get(plain, F)
    for F in frames:
        assert cache.get(line, F) == frame_jpeg(line, F, 0.5, 82), f"frame {F}"
