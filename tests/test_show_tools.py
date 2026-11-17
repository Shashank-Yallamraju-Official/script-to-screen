"""The tools added while making an object show: the land and travel between scenes, looking at sound and shots, and a render
that keeps what has not changed."""
from pathlib import Path

import numpy as np
import skia

from script_to_screen.presentation import bodies, episode
from script_to_screen.script import load_yaml

CROWN = Path(__file__).resolve().parent.parent / "shows" / "crown"


def test_a_bare_on_key_in_yaml_stays_the_word_on(tmp_path):
    f = tmp_path / "x.yaml"
    f.write_text("camera: {on: match, zoom: 2}\nsfx: [{on: match, off: seal}]\n")
    data = load_yaml(f)
    assert data["camera"]["on"] == "match" and data["sfx"][0] == {"on": "match", "off": "seal"}


def test_an_inked_canvas_draws_a_line_round_a_solid_shape_and_not_round_a_shine():
    surf = skia.Surface(60, 60)
    c = bodies.Inked(surf.getCanvas(), "#000000", 4)
    c.drawRect(skia.Rect.MakeXYWH(20, 20, 20, 20), skia.Paint(Color=skia.ColorWHITE))
    px = surf.toarray(colorType=skia.kRGBA_8888_ColorType)
    assert tuple(px[20, 30][:3]) == (0, 0, 0) and tuple(px[30, 30][:3]) == (255, 255, 255)      # its edge is inked, its middle is not
    surf2 = skia.Surface(60, 60)
    bodies.Inked(surf2.getCanvas(), "#000000", 4).drawRect(skia.Rect.MakeXYWH(20, 20, 20, 20), skia.Paint(Color=skia.Color(255, 255, 255, 120)))
    assert surf2.toarray(colorType=skia.kRGBA_8888_ColorType)[20, 30][3] < 200                   # a see-through shape gets no line


def test_travel_leaves_at_dusk_and_arrives_in_the_morning_of_the_next_scenes_day():
    plan, look, cfg = episode.parts(CROWN, "the-vote")
    card = next(p for p in plan if p["kind"] == "travel")["draw"].__defaults__[0]
    first, last = card._clock(0.0), card._clock(card.seconds)
    assert int(first) == 1 and 0.5 < first % 1 < 1.0                # the evening of day 1
    assert int(last) == 120 and 0.25 < last % 1 < 0.5               # the morning of day 120
    assert all(card._clock(t + 0.1) >= card._clock(t) for t in np.arange(0, card.seconds, 0.1))      # time never runs backwards


def test_the_land_changes_on_the_days_its_history_says():
    plan, look, cfg = episode.parts(CROWN, "the-vote")
    land = next(p for p in plan if p["kind"] == "travel")["draw"].__defaults__[0].land
    assert land.places(5)["signet"].get("smoke") and not land.places(5)["signet"].get("flags")
    assert not land.places(110)["signet"].get("smoke") and land.places(110)["signet"]["flags"] == ["mallet", "signet", "hasp"]


def test_the_council_scene_is_one_held_wide_shot():
    shots = [s for s in episode.shots(CROWN, "the-vote") if s["part"] == "the-council"]
    assert len(shots) == 1 and shots[0]["zoom"] == 1.0


def test_a_part_is_made_again_only_when_what_it_is_made_from_changes(tmp_path):
    import shutil
    root = tmp_path / "crown"
    shutil.copytree(CROWN, root, ignore=shutil.ignore_patterns("out"))
    plan, look, cfg = episode.parts(root, "the-vote")
    before = [episode._stamp(root, "the-vote", k, p, False) for k, p in enumerate(plan)]
    scene = root / "episodes" / "e01" / "02-the-council-again.yaml"
    scene.write_text(scene.read_text() + "\n# a note\n")
    after = [episode._stamp(root, "the-vote", k, p, False) for k, p in enumerate(plan)]
    changed = [p["id"] for p, a, b in zip(plan, before, after) if a != b]
    assert "the-council-again" in changed and "the-council" not in changed


def test_a_turn_lands_on_the_bar_it_asks_for_and_a_scene_is_as_long_as_it_says():
    from script_to_screen.performance.scene import Scene
    sc = Scene(CROWN / "episodes" / "e01" / "01-the-council.yaml")
    assert sc.steps == 32 * sc.bar                                   # `bars: 32`
    blast = next(e for e in sc.events if e[1] == "blast")
    assert abs(blast[0] / sc.step / sc.bar - 30) < 1e-6             # the blast, on bar 30
    spoken = {t["id"]: (t["start"] + t["pause"]) / sc.bar for t in sc.turns if t["who"]}
    assert spoken[2] == 2 and spoken[10] == 24                      # lines start on their bars


def test_every_part_of_the_episode_is_a_whole_number_of_bars():
    plan, look, cfg = episode.parts(CROWN, "the-vote")
    bar = 60 / 84 * 2
    assert [round(p["frames"] / look.fps / bar, 1) for p in plan] == [32.0, 20.0, 10.0, 40.0, 20.0]
