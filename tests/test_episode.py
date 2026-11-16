"""An episode as one film: scenes and cards in order, with a title card, credits and one soundtrack."""
from pathlib import Path

import numpy as np
import skia

from script_to_screen.presentation import episode
from script_to_screen.script import series

DEMO = Path(__file__).resolve().parent.parent / "shows" / "demo"


def test_an_episode_is_its_scenes_and_cards_in_the_order_series_yaml_gives():
    plan, look, cfg = episode.parts(DEMO, "s01e01")
    assert [p["kind"] for p in plan] == ["scene", "title", "scene", "scene", "scene", "credits"]
    assert plan[1]["frames"] == round(cfg["title_seconds"] * look.fps)
    assert all(p["into"] in ("dip", "fade", "cut") for p in plan)


def test_cards_belong_to_their_episode_and_are_not_scenes():
    ser = series(DEMO)
    assert all(sg["kind"] == "scene" for sg in ser.segments)
    assert [sg["kind"] for sg in ser.episode("s01e01")["segments"]].count("card") == 2


def test_a_card_draws_and_has_a_theme():
    plan, look, _ = episode.parts(DEMO, "s01e01")
    surface = skia.Surface(look.W, look.H)
    for part in plan:
        if part["kind"] == "scene":
            continue
        early = part["draw"](surface.getCanvas(), 3) or surface.makeImageSnapshot().tobytes()
        late = part["draw"](surface.getCanvas(), part["frames"] - 1) or surface.makeImageSnapshot().tobytes()
        assert early != late
        x = part["sound"]()
        assert np.abs(x).max() > 0.05 and np.abs(x).max() <= 0.9
