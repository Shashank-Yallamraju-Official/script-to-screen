"""Values tuned by hand: where they live, which one wins, and what happens when the words change."""
import json

import pytest
import yaml

from script_to_screen import commands
from script_to_screen.performance import Scene
from script_to_screen.readers import ledger
from script_to_screen.vocabulary import PARAMS

ENTER = dict(id=1, enter={"a": {"slot": 2}, "b": {"slot": 6}}, why="They arrive.")
LINE = dict(id=2, who="a", say="You ate the last one.", hold=5, react=[dict(who="b", do={"attention": "viewer"}, beat=6)], why="She accuses.")
THIRD = dict(id=3, who="b", say="No.", why="He denies it.")


@pytest.fixture
def s2s(show, capsys):
    path = show.scene("kitchen", [ENTER, LINE, THIRD])
    show.scene("later", [ENTER, THIRD])

    def run(*argv):
        code = commands.run([*argv, "--show", str(show.root), "--json"])
        return code, json.loads(capsys.readouterr().out)
    run.path, run.root = path, show.root
    return run


def turn(s2s, n):
    return Scene(s2s.path).turns[n - 1]


def test_a_value_is_looked_for_from_the_narrowest_scope_outward(s2s):
    assert s2s("tune", "get", "kitchen:3.hold")[1]["chain"] == [dict(scope="show", by="written", value=8)]
    s2s("tune", "set", "show.hold", "10")
    s2s("tune", "set", "kitchen.hold", "11")
    assert turn(s2s, 3)["hold"] == 11 and turn(s2s, 2)["hold"] == 5         # a turn's written value beats the scene's
    s2s("tune", "set", "kitchen:2.hold", "12")
    _, out = s2s("tune", "get", "kitchen:2.hold")
    assert [(c["scope"], c["by"], c["value"]) for c in out["chain"]] == [
        ("turn", "hand", 12), ("turn", "written", 5), ("scene", "hand", 11), ("show", "hand", 10), ("show", "written", 8)]
    assert turn(s2s, 2)["hold"] == 12 and Scene(s2s.root / "episodes" / "later.yaml").turns[1]["hold"] == 10


def test_reset_takes_a_hand_set_value_off_and_what_was_written_returns(s2s):
    s2s("tune", "set", "kitchen:2.hold", "12")
    assert s2s("tune", "reset", "kitchen:2.hold")[0] == 0
    assert "tune" not in s2s.path.read_text() and turn(s2s, 2)["hold"] == 5
    code, out = s2s("tune", "reset", "kitchen:2.hold")
    assert code == commands.REFUSED and "5" in out["hint"]


def test_widening_keeps_the_value_here_and_says_how_many_turns_change(s2s):
    s2s("tune", "set", "kitchen:3.hold", "14")
    code, out = s2s("tune", "widen", "kitchen:3.hold")
    assert code == 0 and out["address"] == "kitchen.hold" and out["affects"] == 1     # turn 1 changes; turn 2 has its own; turn 3 already was 14
    assert [turn(s2s, n)["hold"] for n in (1, 2, 3)] == [14, 5, 14]
    assert "tune" not in yaml.safe_load(s2s.path.read_text())["turns"][2]
    assert s2s("undo")[0] == 0                                                        # one undo takes back both halves
    assert [turn(s2s, n)["hold"] for n in (1, 2, 3)] == [8, 5, 14]


def test_a_single_syllable_can_be_tuned_and_keeps_what_it_would_have_been(s2s):
    was = turn(s2s, 2)["sylls"][2]
    s2s("tune", "set", "kitchen:2.s3.length", "4")
    s2s("tune", "set", "kitchen:2.s3.pitch", "9")
    now = turn(s2s, 2)["sylls"][2]
    assert (now["len"], now["semi"]) == (4, 9) and now["base"] == dict(length=was["len"], pitch=was["semi"], stress=was["stress"])
    assert turn(s2s, 2)["sylls"][3]["at"] == turn(s2s, 2)["sylls"][2]["at"] + 4       # what follows moves along
    code, out = s2s("tune", "set", "kitchen:2.s9.length", "4")
    assert code == commands.REFUSED and "5 one." in out["hint"]


def test_a_featured_reactions_beat_can_be_tuned(s2s):
    before = turn(s2s, 2)["length"]
    assert s2s("tune", "set", "kitchen:2.r1.beat", "10")[0] == 0
    assert turn(s2s, 2)["length"] == before + 4


def test_tunes_for_an_earlier_wording_are_set_aside_reported_and_never_applied(s2s):
    s2s("tune", "set", "kitchen:2.s3.length", "4")
    s2s("tune", "set", "kitchen:2.pause", "5")
    code, out = s2s("set-line", "kitchen:2", "You ate it.")
    assert code == 0 and any("earlier wording" in p["msg"] for p in out["problems"])
    t = turn(s2s, 2)
    assert t["sylls"][2]["len"] == t["sylls"][2]["base"]["length"] and t["pause"] == 5      # the syllable tune is off; the pause still holds
    assert [r["address"] for r in s2s("tune", "list", "--orphans")[1]["tunes"]] == ["kitchen:2.s3.length"]
    code, out = s2s("tune", "set", "kitchen:2.s1.stress", "2")                              # tuning the new wording clears the old
    assert code == 0 and "syllable 3" in out["discards"][0]
    assert s2s("tune", "list", "--orphans")[1]["tunes"] == []


def test_every_declared_scope_can_be_reached(s2s):
    for addr, value in [("feel.overshoot", "0.9"), ("sounds.thud.vol", "0.2"), ("~angry.rate", "3"), ("@b.reflex", "2"),
                        ("show.settle", "6"), ("show.bubble_break", "3")]:
        code, out = s2s("tune", "set", addr, value)
        assert code == 0 and out["after"]["by"] == "hand", addr
    assert {r["address"] for r in s2s("tune", "list")[1]["tunes"]} == {"feel.overshoot", "sounds.thud.vol", "~angry.rate", "@b.reflex",
                                                                         "show.settle", "show.bubble_break"}
    reached = {"turn.pause", "turn.hold", "reaction.beat", "syllable.length", "syllable.pitch", "syllable.stress"}
    assert all(p.scope in ("feel", "sound", "tone", "entity", "show") or p.key in reached for p in PARAMS.values())


def test_a_value_out_of_range_or_a_name_that_does_not_exist_is_refused_helpfully(s2s):
    assert "0 to 400" in s2s("tune", "set", "kitchen:2.hold", "900")[1]["refused"]
    assert "hold, pause" in s2s("tune", "set", "kitchen:2.wobble", "3")[1]["hint"]
    assert "angry" in s2s("tune", "set", "~furious.rate", "3")[1]["hint"]


def test_a_dry_run_changes_nothing_and_a_locked_scene_refuses(s2s):
    before = s2s.path.read_text()
    code, out = s2s("tune", "set", "kitchen:2.hold", "9", "--dry-run")
    assert code == 0 and out["after"] == dict(value=9, scope="turn", by="hand") and s2s.path.read_text() == before
    s2s("set-status", "kitchen", "locked")
    assert "locked" in s2s("tune", "set", "kitchen:2.hold", "9")[1]["refused"]


def test_no_tuning_can_change_the_story(s2s):
    """The ledger and what each scene hands to the next must be untouched by any hand-set value."""
    def story():
        table, problems = ledger.build(s2s.root)
        carry = Scene(s2s.root / "episodes" / "later.yaml").carried
        return json.dumps([table, [p for p in problems if p["level"] == "error"], carry], sort_keys=True, default=str)
    before = story()
    for addr, value in [("kitchen:2.hold", "30"), ("kitchen:2.pause", "9"), ("kitchen:2.s2.length", "6"), ("kitchen:2.s2.pitch", "12"),
                        ("kitchen:2.s2.stress", "2"), ("kitchen:2.r1.beat", "20"), ("kitchen.hold", "2"), ("show.hold", "1"), ("show.settle", "9"),
                        ("show.bubble_break", "4"), ("feel.ease", "0.6"), ("sounds.thud.freq", "400"), ("~angry.rate", "4"), ("@b.reflex", "6")]:
        assert s2s("tune", "set", addr, value)[0] == 0, addr
    assert story() == before
