"""The camera's path over the land, moved by hand in the editor."""
import shutil
from pathlib import Path

import pytest
import yaml

from script_to_screen.tools.editor import Session

CROWN = Path(__file__).resolve().parents[1] / "shows" / "crown"


@pytest.fixture
def sess(tmp_path):
    root = tmp_path / "crown"
    shutil.copytree(CROWN, root, ignore=shutil.ignore_patterns("out", ".s2s", "frames"))
    s = Session(root / "episodes" / "e01" / "01-the-council.yaml")
    s.open_part("the-vote-title")
    return s


def test_a_camera_stop_can_be_retimed_moved_added_and_removed_and_the_picture_follows(sess):
    cam = lambda: sess.state()["card"]["camera"]
    land = lambda: yaml.safe_load((sess.root / "land.yaml").read_text())
    n, was = len(cam()), sess.frame(300, False, False)
    assert cam()[3][0] == 5.2
    sess.patch([dict(path=["camera", 3, "bar"], value=99)], commit=True)                     # it cannot pass the stop after it
    assert cam()[3][0] == cam()[4][0] - 0.125 == land()["camera"][3][0]
    sess.patch([dict(path=["camera", 3, "xy"], value=[300, 400])])                           # a drag: the picture follows, the file waits
    assert cam()[3][1:3] == [300, 400] and land()["camera"][3][1:3] != [300, 400] and sess.frame(300, False, False) != was
    sess.patch([dict(path=["camera", 3, "xy"], value=[300, 400])], commit=True)
    sess.patch([dict(path=["camera", 3, "z"], value=2.5)], commit=True)
    assert land()["camera"][3][1:] == [300, 400, 2.5]
    sess.patch([dict(path=["camera", "add"], value=1.0)], commit=True)
    assert len(cam()) == n + 1 and cam()[1][0] == 1.0 and 215 < cam()[1][2] < 255            # it starts as what the camera showed there
    sess.patch([dict(path=["camera", "drop"], value=1)], commit=True)
    assert len(cam()) == n
    with pytest.raises(ValueError, match="first and last"):
        sess.patch([dict(path=["camera", "drop"], value=0)], commit=True)
    sess.step("undo")                                                                        # every change is one undo step
    assert len(cam()) == n + 1
    assert "# Lode" in (sess.root / "land.yaml").read_text()                                 # and the file's comments are kept


def test_the_title_sequence_can_be_made_longer_and_its_last_stop_moves_with_the_end(sess):
    bar = sess.state()["bar"]
    assert sess.state()["steps"] == pytest.approx(20 * bar, abs=0.5)
    sess.patch([dict(path=["turns", 0, "hold"], value=24 * bar)], commit=True)
    land = yaml.safe_load((sess.root / "land.yaml").read_text())
    assert land["bars"] == 24 and land["camera"][-1][0] == 24 and sess.state()["steps"] == pytest.approx(24 * bar, abs=0.5)
