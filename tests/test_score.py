"""The score is the contract: showing a scene needs the score and the look, and nothing else."""
import hashlib
import json
from pathlib import Path

import skia

from script_to_screen.performance import Scene, Score
from script_to_screen.presentation import sound
from script_to_screen.presentation.draw import draw_frame
from script_to_screen.presentation.stage import Look, Stage
from script_to_screen.script import series

DEMO = Path(__file__).resolve().parents[1] / "shows" / "demo"
PRESENTATION_WORDS = ("color", "colour", "volume", "vol", "timbre", "voice", "width", "height", "fps", "font", "ease", "overshoot")


def picture(stage, frames):
    surface, h = skia.Surface(stage.W, stage.H), hashlib.sha256()
    for F in frames:
        draw_frame(surface.getCanvas(), stage, F, xray=True, slate=True)
        h.update(surface.makeImageSnapshot().tobytes())
    return h.hexdigest()


def test_a_score_that_went_through_json_shows_exactly_the_same():
    """If drawing or sound reached past the score for anything, this could not hold."""
    path = series(DEMO).by_id["the-morally-righteous-location"]["path"]
    live = Stage.of(Scene(path))
    saved = Score.from_data(json.loads(json.dumps(live.score.to_data())))
    revived = Stage(saved, Look.load(DEMO, saved.cast), DEMO)
    frames = range(0, live.total, 37)
    assert picture(revived, frames) == picture(live, frames)
    assert sound.mix(revived) == sound.mix(live)


def test_a_score_says_nothing_about_how_things_look_or_sound(show):
    sc = Scene(show.scene("one", [dict(id=1, enter={"a": {"slot": 2}, "b": {"slot": 6}}, why="They arrive."),
                                  dict(id=2, who="a", say="You ate it.", react=[dict(who="b", word="ate", feel={"shame": 2})], why="She accuses.")]))

    def keys(v):
        if isinstance(v, dict):
            for k, x in v.items():
                yield str(k)
                yield from keys(x)
        elif isinstance(v, list):
            for x in v:
                yield from keys(x)
    found = set(keys(sc.score.to_data())) & set(PRESENTATION_WORDS)
    assert not found, f"the score carries presentation: {found}"


def test_changing_the_look_does_not_change_the_score(show):
    path = show.scene("one", [dict(id=1, enter={"a": {"slot": 2}}, why="x"), dict(id=2, who="a", say="Hello there.", why="x")])
    before = json.dumps(Scene(path).score.to_data(), sort_keys=True)
    feel = show.root / "library" / "feel.yaml"
    feel.write_text(feel.read_text().replace("aside_volume:", "aside_volume: 0.01 #"))
    assert json.dumps(Scene(path).score.to_data(), sort_keys=True) == before


def test_each_way_of_showing_the_voice_draws_and_filling_with_ink_is_the_default():
    """`style: {indicator: ...}` in show.yaml chooses how the voice is shown moving through a bubble."""
    path = series(DEMO).by_id["the-vase"]["path"]
    plain = Stage.of(Scene(path))
    line = plain.score.speech[0]
    F = round((line["sylls"][2]["start"] + 0.05) * plain.fps)
    seen = {}
    for style in ("dot", "fill", "trace", "pill"):
        stage = Stage.of(Scene(path))
        stage.look.style = dict(indicator=style)
        seen[style] = picture(stage, [F])
    assert len(set(seen.values())) == 4 and seen["fill"] == picture(plain, [F])        # ink filling the words is the default
