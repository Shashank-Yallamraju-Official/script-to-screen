"""Music scoring: the engine names what happened dramatically, then decides which moments get music."""
import io
import json
import wave
from pathlib import Path

import numpy as np

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
    return [c["kind"] for c in sc.music]


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
    assert len(sc.drama) == 4 and [round(c["t"], 2) for c in sc.music] == [round(sc.drama[0]["t"], 2)]
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
    assert one.music == [] and kinds(both) == ["turn.bad"] and both.music[0]["subject"] == ["b", "c"]


def test_two_cues_are_never_crowded_together_and_the_stronger_is_kept():
    weak, strong = dict(t=1.0, surprise=0.6, weight=0.7, valence=1, subject="a", why="a"), dict(t=1.4, surprise=1.0, weight=1.0, valence=-1, subject="b", why="b")
    got = scoring.cues([weak, strong], step=0.125, apart=4)
    assert [(c["kind"], c["subject"]) for c in got] == [("turn.bad", "b")]


def test_the_reveal_is_scored_as_a_question_then_good_news_then_the_worst_news():
    sc = Scene(series(DEMO).by_id["the-morally-righteous-location"]["path"]).score
    by_turn = {sc.turn_at(c["t"])["id"]: c for c in sc.music}
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
    cue = sc.music[0]["t"]
    i = int(cue * sound.RATE)
    assert np.abs(with_music[i:i + 8000] - without[i:i + 8000]).max() > 500         # something is added where the cue is
    assert np.abs(with_music[:i - 2000] - without[:i - 2000]).max() == 0            # and nothing before it


def test_the_score_names_a_cue_and_says_nothing_of_how_it_sounds(show):
    sc = scene(show, dict(id=2, feel={"b": {"shame": 3}}, why="x"))
    assert set(sc.to_data()["music"][0]) == {"t", "kind", "strength", "subject", "why"}


def test_the_command_line_explains_the_scoring(capsys):
    assert commands.run(["drama", "the-vase", "--show", str(DEMO), "--json"]) == 0
    out = json.loads(capsys.readouterr().out)
    assert [c["kind"] for c in out["cues"]] == ["turn.bad", "turn.bad"] and out["events"][0]["turn"] == 2
