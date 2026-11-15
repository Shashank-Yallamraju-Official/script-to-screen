from pathlib import Path

import skia

from script_to_screen.performance import Scene
from script_to_screen.presentation.draw import draw_frame
from script_to_screen.presentation.render import frame_jpeg
from script_to_screen.presentation.stage import Stage
from script_to_screen.readers import ledger
from script_to_screen.script import scene_paths, series

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
    from script_to_screen.presentation import sound
    for path in scene_paths(DEMO):
        sc = Stage.of(Scene(path))
        surface = skia.Surface(sc.W, sc.H)
        for F in range(0, sc.total, max(1, sc.total // 12)):
            draw_frame(surface.getCanvas(), sc, F, xray=F % 2 == 0, slate=True)
        assert frame_jpeg(sc, sc.total // 2, 0.5)[:2] == b"\xff\xd8"
        assert len(sound.mix(sc)) > 44


def test_the_reference_scenes_have_not_changed():
    """The gate on every restructuring phase. If a phase means to change a scene, re-record it
    with `s2s parity record` and say so in the commit."""
    import json
    from script_to_screen.readers import parity
    for ref in sorted((DEMO / "reference").glob("*.json")):
        was = json.loads(ref.read_text())
        path = series(DEMO).by_id[was["scene"]]["path"]
        sc = Scene(path).score
        now = __import__("hashlib").sha256(json.dumps(parity.score_of(sc), sort_keys=True, ensure_ascii=False).encode()).hexdigest()[:16]
        assert now == was["score"], f"{was['scene']} no longer produces the recorded score"
