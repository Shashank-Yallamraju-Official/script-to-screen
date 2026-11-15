"""The command line an assistant operates the show with."""
import json

import pytest

from script_to_screen import commands

TURNS = [dict(id=1, enter={"a": {"slot": 2}, "b": {"slot": 6}}, why="They arrive."),
         dict(id=2, who="a", say="You ate the last one.", feel={"b": {"shame": 2}}, rhythm=[2, 2, 2, 2, 2], why="She accuses.")]


@pytest.fixture
def s2s(show, capsys):
    path = show.scene("s01/01-kitchen", TURNS)

    def run(*argv):
        code = commands.run([*argv, "--show", str(show.root), "--json"])
        return code, json.loads(capsys.readouterr().out)
    run.path = path
    return run


def test_every_command_describes_itself(s2s):
    code, out = s2s("commands")
    assert code == 0
    for c in out["commands"]:
        assert c["summary"] and c["example"], c["name"]


def test_a_scene_can_be_named_by_any_unique_part_of_its_name(s2s):
    assert s2s("read", "kitchen:2")[1]["turns"][0]["address"] == "s01/01-kitchen:2"
    code, out = s2s("read", "bathroom")
    assert code == commands.REFUSED and "s01/01-kitchen" in out["hint"]


def test_explain_says_why_in_sentences(s2s):
    _, out = s2s("explain", "kitchen:2", "b")
    assert out["now"]["feels"] == "shame" and out["shown"] == [{"attention": "down"}, {"tone": "nervous", "latency": 5}]
    assert any("set in turn 2" in s for s in out["because"])


def test_a_dry_run_reports_and_changes_nothing(s2s):
    before = s2s.path.read_text()
    code, out = s2s("set-timing", "kitchen:2", "hold", "14", "--dry-run")
    assert code == 0 and out["dry_run"] and out["changes"][0]["after"] == 14
    assert s2s.path.read_text() == before


def test_a_change_is_written_journaled_and_can_be_undone_exactly(s2s):
    before = s2s.path.read_text()
    code, out = s2s("set-timing", "kitchen:2", "hold", "14", "--because", "let it breathe")
    assert code == 0 and "hold: 14" in s2s.path.read_text()
    assert s2s("history")[1]["history"][0]["because"] == "let it breathe"
    assert s2s("undo")[0] == 0 and s2s.path.read_text() == before
    assert s2s("undo")[0] == commands.REFUSED


def test_undo_refuses_if_the_file_changed_underneath(s2s):
    s2s("set-timing", "kitchen:2", "hold", "14")
    s2s.path.write_text(s2s.path.read_text() + "\n# a note written by hand\n")
    code, out = s2s("undo")
    assert code == commands.REFUSED and "has changed since" in out["refused"]


def test_a_change_that_would_introduce_an_error_is_refused_and_says_which(s2s):
    before = s2s.path.read_text()
    code, out = s2s("set-feeling", "kitchen:2", "b", "envy", "2")
    assert code == commands.REFUSED and any("envy" in p for p in out["introduces"])
    assert s2s.path.read_text() == before


def test_rewording_a_line_reports_the_hand_set_values_it_discards(s2s):
    code, out = s2s("set-line", "kitchen:2", "You ate it.")
    assert code == 0 and "rhythm" in out["discards"][0] and "rhythm" not in s2s.path.read_text()


def test_a_reaction_on_a_word_that_is_not_in_the_line_is_refused_with_the_words(s2s):
    code, out = s2s("add-reaction", "kitchen:2", "b", "--word", "dumpling", "--feel", "{shame: 3}")
    assert code == commands.REFUSED and "last" in out["hint"]
    assert s2s("add-reaction", "kitchen:2", "b", "--word", "last", "--feel", "{shame: 3}")[0] == 0


def test_put_refuses_a_field_a_turn_does_not_have(s2s):
    code, out = s2s("put", "kitchen:2", "on", "{x: 1}")
    assert code == commands.REFUSED and "react" in out["hint"]


def test_check_exits_3_when_the_show_has_errors(s2s, show):
    assert s2s("check")[0] == 0
    show.scene("s01/02-broken", [dict(id=1, enter={"a": {"slot": 2}})])
    code, out = s2s("check")
    assert code == commands.FAILED and out["errors"] == 1


def test_a_still_and_a_contact_sheet_say_where_they_went(s2s):
    from pathlib import Path
    assert Path(s2s("still", "kitchen:2")[1]["file"]).exists()
    assert Path(s2s("sheet", "kitchen")[1]["file"]).exists()
