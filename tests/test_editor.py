"""The tuning editor: nothing is ever unsaved, everything can be undone, and it follows the files."""
import statistics
import time
from pathlib import Path

import pytest

from script_to_screen.commands import edit
from script_to_screen.performance import Scene
from script_to_screen.readers import ledger
from script_to_screen.script import series
from script_to_screen.tools.editor import Session

DEMO = Path(__file__).resolve().parents[1] / "shows" / "demo"
ENTER = dict(id=1, enter={"a": {"slot": 2}, "b": {"slot": 5}}, why="They are here.")
LINE = dict(id=2, who="a", say="Someone ate the last dumpling.", why="She knows.")
HOLD = [dict(path=["turns", 1, "hold"], value=12)]


@pytest.fixture
def sess(show):
    path = show.scene("s01/e01/01", [ENTER, LINE])
    path.write_text("# a comment that must survive\n" + path.read_text())
    return Session(path)


def test_a_drag_previews_without_touching_the_file_and_letting_go_writes_it(sess):
    before_text, before = sess.path.read_text(), sess.scene.turns[1]["length"]
    sess.patch(HOLD)                                                   # still dragging
    assert sess.scene.turns[1]["length"] == before + 4 and sess.path.read_text() == before_text
    melody = [s["semi"] for s in sess.clean[1].turns[1]["sylls"]]
    melody[2] = 12
    sess.patch(HOLD + [dict(path=["turns", 1, "melody"], value=melody)], commit=True)
    text = sess.path.read_text()
    assert "# a comment that must survive" in text
    assert 'tune: {for: "Someone ate the last dumpling.", hold: 12, pitch: {3: 12}}' in text   # only what was touched, as hand-set values
    again = Scene(sess.path)
    assert [s["semi"] for s in again.turns[1]["sylls"]] == melody and again.turns[1]["hold"] == 12


def test_a_value_dragged_back_to_what_it_would_be_anyway_leaves_no_trace(sess):
    sess.patch(HOLD, commit=True)
    assert "tune: {hold: 12}" in sess.path.read_text()
    sess.patch([dict(path=["turns", 1, "hold"], value=8)], commit=True)
    assert "tune" not in sess.path.read_text() and "hold" not in sess.path.read_text()


def test_a_hand_set_value_outranks_a_written_one_and_taking_it_off_restores_the_written_one(show):
    path = show.scene("s01/e01/01", [ENTER, dict(LINE, hold=3)])
    s = Session(path)
    s.patch(HOLD, commit=True)
    assert "hold: 3" in path.read_text() and "tune: {hold: 12}" in path.read_text() and Scene(path).turns[1]["hold"] == 12
    s.patch([dict(path=["turns", 1, "hold"], value=3)], commit=True)
    assert "tune" not in path.read_text() and Scene(path).turns[1]["hold"] == 3


def test_every_change_by_hand_is_journaled_with_its_address(sess):
    sess.patch(HOLD, commit=True)
    done, _ = edit.stacks(sess.root, by="hand")
    assert done[-1]["changes"] == [dict(address="s01/e01/01:2.hold", field="hold", before=8, after=12)]


def test_a_slider_is_written_as_a_hand_set_value_beside_the_written_one(sess):
    feel = sess.root / "library" / "feel.yaml"
    sess.tune("feel", None, "ease", 0.4, commit=True)
    assert "ease: 0.26" in feel.read_text() and "tune: {ease: 0.4}" in feel.read_text()
    assert sess.stage.look.feel["ease"] == 0.4 and sess.state()["feel"][0]["value"] == 0.4
    sess.tune("feel", None, "ease", 0.26, commit=True)
    assert "tune" not in feel.read_text()


def test_undo_and_redo_cover_timings_and_sliders_and_survive_a_restart(sess):
    scene_before = sess.path.read_text()
    feel = sess.root / "library" / "feel.yaml"
    feel_before = feel.read_text()
    sess.patch(HOLD, commit=True)
    sess.tune("feel", None, "ease", 0.4, commit=True)
    assert "tune: {ease: 0.4}" in feel.read_text() and "#" in feel.read_text()  # the library keeps its comments too
    again = Session(sess.path)                                         # the editor was closed and opened
    again.step("undo")
    assert feel.read_text() == feel_before
    again.step("undo")
    assert again.path.read_text() == scene_before and not again.state()["can_undo"]
    again.step("redo")
    assert "hold: 12" in again.path.read_text() and again.scene.turns[1]["hold"] == 12


def test_the_editor_never_undoes_a_change_it_did_not_make(sess):
    edit.record(sess.root, "set-line", "the assistant's change", sess.path, [], sess.path.read_text(), sess.path.read_text())
    assert not sess.state()["can_undo"]
    with pytest.raises(Exception, match="nothing to undo"):
        sess.step("undo")


def test_a_change_made_elsewhere_while_the_editor_is_open_is_picked_up_and_not_lost(sess):
    """The prototype kept its own copy and overwrote the file on save. Now the file is the truth."""
    sess.patch(HOLD)                                                   # the writer is mid-drag
    text = sess.path.read_text().replace("Someone ate the last dumpling.", "Who ate it?")
    sess.path.write_text(text)                                         # the assistant rewrites the line underneath
    sess.patch(HOLD, commit=True)                                      # the writer lets go
    now = sess.path.read_text()
    assert "Who ate it?" in now and "hold: 12" in now                  # both changes stand
    assert sess.scene.turns[1]["line"]["text"].strip() == "Who ate it?"


def test_polling_notices_a_file_that_changed_underneath(sess):
    assert sess.poll()["changed"] is False
    rev = sess.rev
    sess.path.write_text(sess.path.read_text().replace("Someone ate the last dumpling.", "Who ate it?"))
    assert sess.poll()["changed"] is True and sess.rev > rev
    assert sess.scene.turns[1]["line"]["text"].strip() == "Who ate it?"


def test_a_locked_scene_cannot_be_nudged(sess):
    f = sess.root / "series.yaml"
    f.write_text(f.read_text().replace("id: s01/e01/01", "id: s01/e01/01\n      status: locked"))
    assert sess.poll()["changed"]
    with pytest.raises(ValueError, match="locked"):
        sess.patch(HOLD, commit=True)


def test_a_nudge_does_not_rebuild_the_ledger_or_earlier_scenes(sess, monkeypatch):
    calls = []
    monkeypatch.setattr(ledger, "build", lambda *a, **k: calls.append(1) or ({}, []))
    from script_to_screen.tools import editor
    monkeypatch.setattr(editor, "carry_into", lambda *a, **k: calls.append(1) or {})
    sess.patch(HOLD)
    sess.patch(HOLD, commit=True)
    sess.tune("feel", None, "overshoot", 0.9, commit=True)
    assert calls == []


def test_a_slider_that_only_changes_the_look_does_not_work_the_scene_out_again(sess):
    score = sess.scene
    assert sess.tune("feel", None, "overshoot", 0.9) == 0              # redraw every frame
    assert sess.tune("feel", None, "voice_ring", 0.5) is None          # sound only: frames are kept
    assert sess.scene is score


def test_a_nudge_is_fast():
    """The design budget is 40 ms from release to a rebuilt scene; allow 3x for a slow test machine."""
    import shutil
    import tempfile
    root = Path(tempfile.mkdtemp()) / "demo"
    shutil.copytree(DEMO, root, ignore=shutil.ignore_patterns("out", ".s2s"))
    s = Session(series(root).by_id["the-thermostat"]["path"])
    took = []
    for n in range(12):
        t = time.perf_counter()
        s.patch([dict(path=["turns", 1, "hold"], value=9 + n % 2)], commit=True)
        took.append((time.perf_counter() - t) * 1000)
    assert statistics.median(took) < 120, f"median {statistics.median(took):.0f} ms"


# ---- the knob: any value, by its address ------------------------------------------------------------
TALK = dict(id=2, who="a", say="I saw. You took it.", why="She has waited.")


@pytest.fixture
def talk(show):
    show.scene("s01/e01/02", [ENTER, dict(id=2, who="b", say="No. Never.", why="He denies it.")])
    return Session(show.scene("s01/e01/01", [ENTER, TALK]))


def test_the_knob_shows_where_a_value_comes_from_and_how_it_can_change(talk):
    gap = next(x for x in talk.state()["turns"][1]["stretches"] if x["param"] == "syllable.breath")
    v = talk.value(gap["address"])
    assert (v["value"], v["scope"], v["by"], v["hand_here"], v["wider"]) == (2, "show", "default", False, "show")
    assert v["param"]["scopes"] == ["syllable", "show"] and v["param"]["step"] == 0.5


def test_the_worked_example_shorten_one_breath_then_every_full_stop_then_change_your_mind(talk):
    """docs/lld-nudging.md, section 1."""
    gap = "s01/e01/01:2.s2.breath"
    word = talk.scene.turns[1]["sylls"][1]
    voiced = word["len"] - word["rest"]
    talk.nudge(gap, "set", 1.5)                                         # steps 1 to 3
    now = talk.scene.turns[1]["sylls"][1]
    assert now["rest"] == 1.5 and now["len"] - now["rest"] == voiced and talk.value(gap)["by"] == "hand"
    assert 'breath: {2: 1.5}' in talk.path.read_text()
    talk.nudge(gap, "widen")                                            # step 5
    assert talk.value(gap)["chain"][0] == dict(scope="show", by="hand", value=1.5)
    assert "tune" not in talk.path.read_text() and "breath: {stop: 1.5}" in (talk.root / "show.yaml").read_text()
    other = Scene(talk.root / "episodes" / "s01/e01/02.yaml").turns[1]["sylls"][0]
    assert other["rest"] == 1.5
    talk.step("undo")                                                   # step 6: back to this syllable only
    assert talk.value(gap)["chain"][0] == dict(scope="syllable", by="hand", value=1.5)
    assert "tune:" not in (talk.root / "show.yaml").read_text()
    talk.nudge(gap, "reset")
    assert talk.value(gap)["value"] == 2 and "tune" not in talk.path.read_text()


def test_a_quick_run_of_nudges_is_one_undo_step(talk):
    before = talk.path.read_text()
    for v in (9, 10, 11, 12):
        talk.nudge("s01/e01/01:2.hold", "set", v)
    assert len(edit.stacks(talk.root, by="hand")[0]) == 1 and talk.scene.turns[1]["hold"] == 12
    talk.step("undo")
    assert talk.scene.turns[1]["hold"] == 8 and Scene(talk.path).turns[1]["hold"] == 8
    assert "tune" not in talk.path.read_text() and before.count("why") == talk.path.read_text().count("why")


def test_nudging_a_value_back_to_what_it_would_be_takes_the_hand_set_value_off(talk):
    talk.nudge("feel.overshoot", "set", 0.9)
    assert "tune: {overshoot: 0.9}" in (talk.root / "library" / "feel.yaml").read_text()
    talk.nudge("feel.overshoot", "set", 0.6)
    assert "tune" not in (talk.root / "library" / "feel.yaml").read_text()


def test_the_knob_is_fast():
    """Design budget: 60 ms from a keypress to a rebuilt scene; allow 3x for a slow test machine."""
    import shutil
    import tempfile
    root = Path(tempfile.mkdtemp()) / "demo"
    shutil.copytree(DEMO, root, ignore=shutil.ignore_patterns("out", ".s2s"))
    s = Session(series(root).by_id["the-vase"]["path"])
    took = []
    for n in range(12):
        t = time.perf_counter()
        s.nudge("the-vase:3.s3.length", "set", 3 + n % 3)
        took.append((time.perf_counter() - t) * 1000)
    assert statistics.median(took) < 180, f"median {statistics.median(took):.0f} ms"


# ---- audition, and before against after ---------------------------------------------------------------
def test_before_is_the_scene_as_it_stood_when_the_value_was_picked(talk):
    gap = "s01/e01/01:2.s2.breath"
    talk.pick()
    total = talk.stage.total
    you = talk.stage.score.speech[1]["sylls"][0]["start"]               # when "You" begins, before any change
    late = round(you * talk.stage.fps) - 3                              # just before it: still the silence after "saw."
    was = talk.frame(late, False, False)
    talk.nudge(gap, "set", 0.5)
    talk.nudge("s01/e01/01:2.hold", "set", 20)
    assert talk.stage.total != total
    assert talk.frame(late, False, False, before=True) == was and talk.frame(late, False, False) != was
    assert talk.before[0].total == total                                # A keeps its own length
    talk.pick()                                                         # picking again moves "before" up to now
    assert talk.frame(late, False, False, before=True) == talk.frame(late, False, False)


def test_how_much_replays_around_a_nudge_is_a_show_setting(talk):
    assert talk.state()["lead"] == [8, 8]
    f = talk.root / "show.yaml"
    f.write_text(f.read_text() + "\neditor: {lead_in: 12, lead_out: 4}\n")
    assert talk.poll()["changed"] and talk.state()["lead"] == [12, 4]
