from pathlib import Path

import skia

from toon import ledger
from toon.draw import draw_frame
from toon.editor import Session
from toon.model import Scene, scene_paths
from toon.render import frame_jpeg

DEMO = Path(__file__).resolve().parents[1] / "shows" / "demo"
ENTER = dict(id=1, enter={"a": {"slot": 2}, "b": {"slot": 5}}, why="They are here.")
SHAME = dict(id=2, feel={"b": {"shame": 1}}, why="x")


def test_a_tell_is_learned_after_three_scenes(show):
    for n in (1, 2):
        show.scene(f"s01/e01/0{n}", [ENTER, SHAME])
    assert ledger.build(show.root)[0]["b"]["shame"]["learned"] is False
    show.scene("s01/e01/03", [ENTER, SHAME])
    row = ledger.build(show.root)[0]["b"]["shame"]
    assert row["learned"] and row["seen"] == 3


def test_a_payoff_cannot_rely_on_a_tell_the_audience_has_not_learned(show):
    show.scene("s01/e01/01", [ENTER, SHAME])
    show.scene("s01/e01/02", [ENTER, dict(SHAME, relies_on={"b": "shame"})])
    assert any(p["level"] == "error" and "relies on" in p["msg"] for p in ledger.build(show.root)[1])


def test_a_changed_tell_starts_its_count_again(show):
    show.entity("b", arc=[{"from": "s01/e01/03", "tells": {"shame": [{"posture": "contracted"}]}}])
    for n in (1, 2, 3):
        show.scene(f"s01/e01/0{n}", [ENTER, SHAME], offscreen=[dict(feel={"b": "calm"}, why="Time passes.")])
    assert ledger.build(show.root)[0]["b"]["shame"]["seen"] == 1


def test_the_demo_show_has_no_errors():
    table, problems = ledger.build(DEMO)
    assert not [p for p in problems if p["level"] == "error"]
    assert table["otis"]["shame"]["learned"]


def test_every_demo_scene_draws_and_sounds():
    from toon import speech
    for path in scene_paths(DEMO):
        sc = Scene(path)
        surface = skia.Surface(sc.W, sc.H)
        for F in range(0, sc.total, max(1, sc.total // 12)):
            draw_frame(surface.getCanvas(), sc, F, xray=F % 2 == 0, slate=True)
        assert frame_jpeg(sc, sc.total // 2, 0.5)[:2] == b"\xff\xd8"
        assert len(speech.mix(sc)) > 44


def test_the_editor_saves_only_what_changed(show):
    path = show.scene("s01/e01/01", [ENTER, dict(id=2, who="a", say="Someone ate the last dumpling.", why="She knows.")])
    path.write_text("# a comment that must survive\n" + path.read_text())
    sess = Session(path)
    before = sess.scene.turns[1]["length"]
    sess.patch([dict(path=["turns", 1, "hold"], value=12), dict(path=["turns", 1, "melody"], value=[0, 2, 4, 7, 9, 7, 4])])
    assert sess.scene.turns[1]["length"] == before + 4 and sess.dirty
    sess.tune("feel", None, "ease", 0.4)
    sess.save()
    text = path.read_text()
    assert "# a comment that must survive" in text and "hold: 12" in text and "melody: [0, 2, 4, 7, 9, 7, 4]" in text
    assert "ease: 0.4" in (show.root / "library" / "feel.yaml").read_text()
    again = Scene(path)
    assert [s["semi"] for s in again.turns[1]["sylls"]] == [0, 2, 4, 7, 9, 7, 4] and again.turns[1]["hold"] == 12
    sess.patch([dict(path=["turns", 1, "hold"], value=8)])                         # back to the default: no line needed
    sess.save()
    assert "hold:" not in path.read_text()


def test_the_reference_scenes_have_not_changed():
    """The gate on every restructuring phase. If a phase means to change a scene, re-record it
    with `toon parity record` and say so in the commit."""
    import json
    from toon import parity
    for ref in sorted((DEMO / "reference").glob("*.json")):
        was = json.loads(ref.read_text())
        path = DEMO / "episodes" / (was["scene"] + ".yaml")
        sc = Scene(path)
        now = __import__("hashlib").sha256(json.dumps(parity.score_of(sc), sort_keys=True, ensure_ascii=False).encode()).hexdigest()[:16]
        assert now == was["score"], f"{was['scene']} no longer produces the recorded score"
