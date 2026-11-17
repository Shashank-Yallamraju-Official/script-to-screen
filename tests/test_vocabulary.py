"""What can be tuned and what can be observed is declared once, and the rest follows from it."""
from pathlib import Path

import yaml

from script_to_screen import commands
from script_to_screen.performance import Scene
from script_to_screen.tools import editor
from script_to_screen.vocabulary import CHANNELS, PARAMS, channels, params

DEMO = Path(__file__).resolve().parents[1] / "shows" / "demo"
ENTER = dict(id=1, enter={"a": {"slot": 2}, "b": {"slot": 6}}, why="They arrive.")


def errors(sc):
    return [p["msg"] for p in sc.problems if p["level"] == "error"]


def test_every_parameter_is_fully_declared():
    for p in PARAMS.values():
        assert p.lo < p.hi and p.step > 0 and p.meaning.endswith(".") and p.rebuild in ("look", "sound", "timing"), p.key
        assert p.owns_time or p.exercised_by or p.scope in ("sound", "show"), f"{p.key} could not be found from a moment on screen"


def test_the_demo_library_matches_the_declarations():
    feel = yaml.safe_load((DEMO / "library" / "feel.yaml").read_text())
    assert params.check_library(feel) == []
    assert set(feel) == {p.name for p in params.group("feel")}


def test_the_editors_timing_limits_come_from_the_declarations():
    assert editor.NUMBERS == {"pause": 200, "hold": 400, "bar": 400}


def test_a_tell_cannot_name_an_entity_but_an_action_can():
    assert channels.problem("tell", "attention", "otis") is not None
    assert channels.problem("do", "attention", "otis", entities={"otis"}) is None
    assert "an entity: otis" in channels.problem("do", "attention", "nobody", entities={"otis"})


def test_a_sheet_with_a_misspelt_tell_is_an_error_that_lists_what_is_allowed(show):
    show.entity("b", tells={"shame": [{"atention": "down"}]})
    msgs = errors(Scene(show.scene("one", [ENTER])))
    assert any("entities/b.yaml, shame tell 1" in m and "attention" in m for m in msgs)


def test_a_tell_with_a_value_its_channel_does_not_allow_is_an_error(show):
    show.entity("b", tells={"shame": [{"posture": "slumped"}]})
    assert any("slumped" in m and "contracted" in m for m in errors(Scene(show.scene("one", [ENTER]))))


def test_an_action_that_names_an_unknown_entity_is_an_error(show):
    sc = Scene(show.scene("one", [ENTER, dict(id=2, do={"a": {"orient": "zed"}}, why="x")]))
    assert any("a's action" in m and "zed" in m for m in errors(sc))


def test_the_command_line_lists_the_vocabulary(capsys):
    import json
    assert commands.run(["params", "--json", "--scope", "turn"]) == 0
    assert [p["key"] for p in json.loads(capsys.readouterr().out)["params"]] == ["turn.pause", "turn.hold", "turn.bar"]
    assert commands.run(["channels", "--json"]) == 0
    assert {c["key"] for c in json.loads(capsys.readouterr().out)["channels"]} == set(CHANNELS)
