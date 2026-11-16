"""Music scoring: the engine names what happened dramatically, then decides which moments get music."""
import io
import json
import wave
from pathlib import Path

import numpy as np
import pytest

from script_to_screen import commands
from script_to_screen.performance import Scene, drama, scoring
from script_to_screen.presentation import sound
from script_to_screen.presentation.stage import Look, Stage
from script_to_screen.script import load_yaml, series

DEMO = Path(__file__).resolve().parents[1] / "shows" / "demo"
ENTER = dict(id=1, enter={"a": {"slot": 2}, "b": {"slot": 6}, "c": {"slot": 7}}, why="They arrive.")
JOY = {"joy": [{"tone": "cheerful"}, {"posture": "lean_in"}], "shame": [{"attention": "down"}, {"tone": "nervous"}, {"orient": "away"}],
       "fear": [{"posture": "lean_back"}], "surprise": [{"attention": "up"}]}


def scene(show, *turns, **top):
    for e in "abc":
        show.entity(e, tells=JOY)
    return Scene(show.scene("one", [ENTER, *turns], **top)).score


def kinds(sc):
    """The cues that mark a moment as it lands (a build-up before one is tested on its own)."""
    return [c["kind"] for c in sc.music if c["kind"] != "rise"]


def test_a_surprise_that_is_bad_news_and_one_that_is_good_news_get_different_music(show):
    bad = scene(show, dict(id=2, who="a", say="You.", feel={"b": {"shame": 3}}, why="x"))
    good = scene(show, dict(id=2, who="a", say="You.", feel={"b": {"joy": 3}}, why="x"))
    assert kinds(bad) == ["turn.bad"] and kinds(good) == ["turn.good"]


def test_surprise_itself_is_a_question_and_the_feeling_that_follows_answers_it(show):
    sc = scene(show, dict(id=2, who="a", say="Look.", feel={"b": {"surprise": 2}}, why="x"), dict(id=3, feel={"b": {"joy": 2}}, why="x"))
    assert kinds(sc) == ["question", "turn.good"]


def test_more_of_the_same_is_not_a_surprise(show):
    """The room is already tense and he was already ashamed: one more notch gets no music."""
    sc = scene(show, dict(id=2, feel={"b": {"shame": 2}, "c": {"shame": 2}}, why="x"), dict(id=3, feel={"c": {"shame": 3}}, why="x"),
               dict(id=4, feel={"b": {"shame": 3}}, why="x"))
    assert len(sc.drama) == 4 and [round(c["t"], 2) for c in sc.music if c["kind"] != "rise"] == [round(sc.drama[0]["t"], 2)]
    assert sc.drama[3]["surprise"] < sc.drama[0]["surprise"]


def test_what_is_good_for_someone_the_audience_is_against_is_bad_news(show):
    with_him = scene(show, dict(id=2, feel={"b": {"joy": 3}}, why="x"))
    against = scene(show, dict(id=2, sympathy={"b": -1}, feel={"b": {"joy": 3}}, why="The mask is off."))
    assert kinds(with_him) == ["turn.good"] and kinds(against) == ["turn.bad"]
    assert "against them" in against.drama[0]["why"]


def test_sympathy_carries_into_the_next_scene_like_any_standing(show):
    scene(show, dict(id=2, sympathy={"b": -1}, why="x"))
    nxt = Scene(show.scene("two", [ENTER, dict(id=2, feel={"b": {"joy": 3}}, why="x")])).score
    assert kinds(nxt) == ["turn.bad"]


def test_a_feeling_that_does_not_show_gets_no_music(show):
    for e in "abc":
        show.entity(e, tells=JOY)
    # b is alone against two who outrank him, so one notch of shame is held in entirely
    sc = Scene(show.scene("one", [dict(ENTER, side={"a": "x", "c": "x", "b": "y"}, status={"a": 2, "c": 2}),
                                  dict(id=2, feel={"b": {"shame": 1}}, why="x")])).score
    assert sc.drama[0]["shown"] is False and sc.drama[0]["weight"] == 0 and sc.music == []


def test_a_reaction_in_passing_alone_is_too_slight_but_a_room_reacting_together_is_a_moment(show):
    one = scene(show, dict(id=2, who="a", say="It was you.", react=[dict(who="b", word="you", feel={"fear": 2})], why="x"))
    both = scene(show, dict(id=2, who="a", say="It was you.", react=[dict(who="b", word="you", feel={"fear": 2}),
                                                                      dict(who="c", word="you", feel={"fear": 2})], why="x"))
    assert one.music == [] and kinds(both) == ["turn.bad"] and both.music[-1]["subject"] == ["b", "c"]


def test_two_cues_are_never_crowded_together_and_the_stronger_is_kept():
    weak, strong = dict(t=1.0, surprise=0.6, weight=0.7, valence=1, subject="a", why="a"), dict(t=1.4, surprise=1.0, weight=1.0, valence=-1, subject="b", why="b")
    got = scoring.cues([weak, strong], step=0.125, apart=4, rise=0)
    assert [(c["kind"], c["subject"]) for c in got] == [("turn.bad", "b")]


def test_the_reveal_is_scored_as_a_question_then_good_news_then_the_worst_news():
    sc = Scene(series(DEMO).by_id["the-morally-righteous-location"]["path"]).score
    by_turn = {sc.turn_at(c["t"])["id"]: c for c in sc.music if c["kind"] != "rise"}
    assert by_turn[5]["kind"] == "question"                             # Eleanor starts to see it
    assert by_turn[8]["kind"] == "turn.good"                            # she has it
    assert by_turn[9]["kind"] == "turn.bad" and len(by_turn[9]["subject"]) > 1     # it lands on the others, together
    assert by_turn[11]["kind"] == "turn.bad" and by_turn[11]["strength"] == max(c["strength"] for c in sc.music)   # his laugh


def test_music_is_heard_and_turning_it_down_to_nothing_removes_it():
    path = series(DEMO).by_id["the-vase"]["path"]
    sc = Scene(path).score
    feel = load_yaml(DEMO / "library" / "feel.yaml")

    def audio(volume):
        stage = Stage(sc, Look.load(DEMO, sc.cast, lib=dict(feel=dict(feel, music_volume=volume))), DEMO)
        w = wave.open(io.BytesIO(sound.mix(stage)))
        return np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(float)
    with_music, without = audio(0.6), audio(0)
    cue = next(c for c in sc.music if c["kind"] != "rise")["t"]
    i = int(cue * sound.RATE)
    assert np.abs(with_music[i:i + 8000] - without[i:i + 8000]).max() > 500         # something is added where the cue is
    assert np.abs(with_music[:i - 2000] - without[:i - 2000]).max() == 0            # and nothing before it


def test_the_score_names_a_cue_and_says_nothing_of_how_it_sounds(show):
    sc = scene(show, dict(id=2, feel={"b": {"shame": 3}}, why="x"))
    for cue in sc.to_data()["music"]:
        assert set(cue) - {"length", "into"} == {"t", "kind", "strength", "subject", "why"}


def test_the_command_line_explains_the_scoring(capsys):
    assert commands.run(["drama", "the-vase", "--show", str(DEMO), "--json"]) == 0
    out = json.loads(capsys.readouterr().out)
    assert [c["kind"] for c in out["cues"] if c["kind"] != "rise"] == ["turn.bad", "turn.bad"] and out["events"][0]["turn"] == 2


# ---- the build-up ---------------------------------------------------------------------------------------
def test_only_the_strongest_moment_gets_a_build_up_and_it_ends_as_the_moment_lands(show):
    sc = scene(show, dict(id=2, feel={"b": {"shame": 2}}, why="x"), dict(id=3, why="A long silence.", hold=30),
               dict(id=4, sympathy={"c": -1}, feel={"c": {"joy": 3}}, why="The mask comes off."))
    rises = [c for c in sc.music if c["kind"] == "rise"]
    peak = max((c for c in sc.music if c["kind"] != "rise"), key=lambda c: c["strength"])
    assert len(rises) == 1 and rises[0]["into"] == peak["kind"] == "turn.bad"
    assert rises[0]["t"] + rises[0]["length"] == pytest.approx(peak["t"]) and rises[0]["length"] == pytest.approx(16 * sc.step)


def test_a_moment_that_is_not_strong_enough_gets_no_build_up_and_a_show_can_turn_them_off(show):
    mild = scene(show, dict(id=2, feel={"b": {"shame": 1}}, why="x"), dict(id=3, why="x"), dict(id=4, feel={"b": {"shame": 2}}, why="x"))
    assert all(c["kind"] != "rise" for c in mild.music)
    strong = [dict(t=3.0, surprise=1.0, weight=1.0, valence=-1, subject="b", why="b")]
    assert [c["kind"] for c in scoring.cues(strong, step=0.125)] == ["rise", "turn.bad"]
    assert [c["kind"] for c in scoring.cues(strong, step=0.125, rise=0)] == ["turn.bad"]


def test_a_build_up_never_starts_before_the_cue_ahead_of_it_has_had_its_room():
    first, peak = dict(t=2.0, surprise=0.6, weight=0.7, valence=-1, subject="a", why="a"), dict(t=3.0, surprise=1.0, weight=1.0, valence=-1, subject="b", why="b")
    got = scoring.cues([first, peak], step=0.125, apart=4)
    rise = next(c for c in got if c["kind"] == "rise")
    assert rise["t"] == pytest.approx(2.5) and rise["length"] == pytest.approx(0.5)      # squeezed to start after the first cue, not on top of it


def test_the_build_up_swells_and_stops_as_the_moment_lands():
    r = sound.riser(110, 220, 2.0, 0.5)
    quarter = len(r) // 4
    loud = lambda a: float(np.abs(a).mean())
    assert loud(r[:quarter]) < loud(r[quarter:2 * quarter]) < loud(r[2 * quarter:3 * quarter]) and abs(r[-1]) < 1e-3


def test_each_way_of_showing_music_draws_and_the_line_with_the_closing_frame_is_the_default():
    import hashlib
    import skia
    from script_to_screen.presentation.draw import draw_frame
    path = series(DEMO).by_id["the-morally-righteous-location"]["path"]
    sc = Scene(path)
    rise = next(c for c in sc.score.music if c["kind"] == "rise")
    seen = {}
    for style in ("default", "none", "line", "rings", "frame", ("line", "frame")):
        stage = Stage.of(sc)
        if style != "default":
            stage.look.style = dict(stage.look.style, music=list(style) if isinstance(style, tuple) else style)
        surface = skia.Surface(stage.W, stage.H)
        draw_frame(surface.getCanvas(), stage, round((rise["t"] + rise["length"] * 0.8) * stage.fps))
        seen[style] = hashlib.sha256(surface.makeImageSnapshot().tobytes()).hexdigest()
    assert seen["default"] == seen[("line", "frame")] and len(set(seen.values())) == 5
