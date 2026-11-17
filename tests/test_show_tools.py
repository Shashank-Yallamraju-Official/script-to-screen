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
