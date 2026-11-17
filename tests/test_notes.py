"""Notes pinned in the editor: they stay on their moment, and the assistant can read them."""
import json

from script_to_screen import commands
from script_to_screen.tools.editor import Session

ENTER = dict(id=1, enter={"a": {"slot": 2}, "b": {"slot": 5}}, why="They are here.")
LINE = dict(id=2, who="a", say="Someone ate the last dumpling.", why="She knows.")


def test_a_note_stays_on_its_moment_when_timings_move_and_can_be_read_and_closed(show, capsys):
    sess = Session(show.scene("room", [ENTER, LINE]))
    start = sess.state()["turns"][1]["start"]
    sess.pin(sess.frame_of(1) + 6, "this lands late")
    (pin,) = sess.state()["notes"]
    assert pin["turn"] == 2 and pin["text"] == "this lands late" and start < pin["now"] < start + 2
    sess.patch([dict(path=["turns", 0, "hold"], value=20)], commit=True)                     # everything after turn 1 moves later
    later = sess.state()["turns"][1]["start"]
    assert later > start and sess.state()["notes"][0]["now"] - later == pin["now"] - start
    assert "notes" not in sess.path.read_text()                                              # a note never touches the script

    def notes(*argv):
        assert commands.run(["notes", *argv, "--show", str(show.root), "--json"]) == 0
        return json.loads(capsys.readouterr().out)["notes"]
    assert [(n["part"], n["turn"], n["text"]) for n in notes()] == [("room", 2, "this lands late")]
    notes("--done", "1")
    assert notes() == [] and notes("--all")[0]["done"] and sess.state()["notes"][0]["done"]
    sess.pin(0, "reworded", nid=1)
    assert sess.state()["notes"][0]["text"] == "reworded"
    sess.pin(0, "", nid=1)
    assert sess.state()["notes"] == []


def test_a_take_keeps_the_whole_tuning_and_switching_to_it_is_one_undo_step(show):
    sess = Session(show.scene("room", [ENTER, LINE]))
    hold = lambda: sess.state()["turns"][1]["hold"]
    first = hold()
    sess.take(save="Before")
    sess.patch([dict(path=["turns", 1, "hold"], value=first + 7)], commit=True)
    sess.nudge("show.settle", "set", 9)
    sess.take(save="Long hold")
    assert [(t["name"], t["here"]) for t in sess.takes()] == [("Before", False), ("Long hold", True)]
    sess.take(open="Before")
    assert hold() == first and [t["here"] for t in sess.takes()] == [True, False]
    sess.step("undo")                                                    # both files it changed come back together
    assert hold() == first + 7 and [t["here"] for t in sess.takes()] == [False, True]
    sess.take(drop="Before")
    assert [t["name"] for t in sess.takes()] == ["Long hold"]


def test_a_change_made_by_command_while_the_editor_is_open_is_told_with_its_reason_and_place(show):
    sess = Session(show.scene("room", [ENTER, LINE]))
    assert sess.poll()["news"] == []
    sess.patch([dict(path=["turns", 1, "hold"], value=9)], commit=True)                      # the writer's own change is not news
    assert sess.poll()["news"] == []
    assert commands.run(["tune", "set", "room:2.hold", "14", "--because", "note 1: it lands late", "--show", str(show.root), "--json"]) == 0
    r = sess.poll()
    (n,) = r["news"]
    assert r["changed"] and n["part"] == "room" and n["turn"] == "2" and n["address"] == "room:2.hold" and n["because"] == "note 1: it lands late" and "14" in n["text"]
    assert sess.state()["turns"][1]["hold"] == 14 and sess.poll()["news"] == []              # told once
    sess.take_back()
    assert sess.state()["turns"][1]["hold"] == 9
