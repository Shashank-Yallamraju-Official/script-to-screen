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
    sess.patch(HOLD + [dict(path=["turns", 1, "melody"], value=[0, 2, 4, 7, 9, 7, 4])], commit=True)
    text = sess.path.read_text()
    assert "# a comment that must survive" in text and "hold: 12" in text and "melody: [0, 2, 4, 7, 9, 7, 4]" in text
    assert [s["semi"] for s in Scene(sess.path).turns[1]["sylls"]] == [0, 2, 4, 7, 9, 7, 4]


def test_a_value_set_back_to_the_shows_default_leaves_no_line_in_the_file(sess):
    sess.patch(HOLD, commit=True)
    sess.patch([dict(path=["turns", 1, "hold"], value=8)], commit=True)
    assert "hold:" not in sess.path.read_text()


def test_every_change_by_hand_is_journaled_with_its_address(sess):
    sess.patch(HOLD, commit=True)
    done, _ = edit.stacks(sess.root, by="hand")
    assert done[-1]["changes"] == [dict(address="s01/e01/01:2", field="hold", before=None, after=12)]


def test_undo_and_redo_cover_timings_and_sliders_and_survive_a_restart(sess):
    scene_before = sess.path.read_text()
    feel = sess.root / "library" / "feel.yaml"
    feel_before = feel.read_text()
    sess.patch(HOLD, commit=True)
    sess.tune("feel", None, "ease", 0.4, commit=True)
    assert "ease: 0.4" in feel.read_text() and "#" in feel.read_text()          # the library keeps its comments too
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
