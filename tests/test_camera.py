"""The camera: it never hides a change, it rests when it can, and a place is drawn behind the entities."""
from pathlib import Path

from script_to_screen.performance import camera
from script_to_screen.performance.scene import Scene
from script_to_screen.presentation.stage import Stage
from script_to_screen.presentation.view import view
from script_to_screen.script import series

DEMO = Path(__file__).resolve().parent.parent / "shows" / "demo"
SCENES = [sg["path"] for sg in series(DEMO).segments if sg["kind"] == "scene"]


def test_whoever_changes_or_speaks_is_in_frame_as_it_happens():
    for path in SCENES:
        score = Scene(path).score
        for turn in score.turns[1:]:
            for t, who in camera.changes(turn, score.pose, score.step, camera.DEFAULTS["together"]):
                shot = [s for s in score.camera if s["t"] <= t + 2e-3][-1]
                half = camera.FRAME / shot["zoom"] / 2
                for e, slots in who.items():
                    assert all(shot["centre"] - half <= s <= shot["centre"] + half for s in slots), f"{score.id} turn {turn['id']}: {e} is out of frame"


def test_a_single_seats_its_subject_with_room_on_the_side_they_face():
    score = Scene(series(DEMO).by_id["the-morally-righteous-location"]["path"]).score
    chidi = [s for s in score.camera if s["on"] == ["chidi"]][0]          # he faces right, toward tahani
    assert chidi["at"] == "left" and chidi["centre"] > 5                 # so he sits left, and the frame's centre is to his right
    tahani = [s for s in score.camera if s["on"] == ["tahani"]][0]
    assert tahani["at"] == "right" and tahani["centre"] < 6
    assert any(s["tilt"] for s in score.camera if s["on"] == ["michael"])   # his laugh, a hard bad surprise, tips the frame


def test_a_scene_opens_wide_and_every_shot_says_why():
    for path in SCENES:
        shots = Scene(path).score.camera
        assert shots[0]["zoom"] == 1.0 and shots[0]["t"] == 0
        assert all(s["why"] for s in shots)
        assert [s["t"] for s in shots] == sorted(s["t"] for s in shots)


def test_the_script_can_ask_for_a_shot():
    path = series(DEMO).by_id["the-morally-righteous-location"]["path"]
    from script_to_screen.script import load_yaml
    script = load_yaml(path)
    script["turns"][2]["camera"] = "wide"
    script["turns"][3]["camera"] = "jason"
    shots = Scene(path, script=script).score.camera
    assert [s for s in shots if s["why"] == "the script asks for the wide shot"]
    assert [s for s in shots if s["on"] == ["jason"] and s["zoom"] > 1.5]
    centres = {}
    for side in ("left", "centre", "right"):
        script["turns"][8]["camera"] = dict(on="chidi", at=side)
        shot = [s for s in Scene(path, script=script).score.camera if s["on"] == ["chidi"] and s["why"].startswith("the script")][0]
        centres[side] = shot["centre"]
    assert centres["left"] > centres["centre"] > centres["right"]        # seated left, the frame looks to his right


def test_the_still_style_never_leaves_the_wide_shot_and_drift_does():
    stage = Stage.of(Scene(series(DEMO).by_id["the-morally-righteous-location"]["path"]))
    assert max(view(stage, t / 2).zoom for t in range(60)) > 1.5
    stage.look.style = dict(stage.look.style, camera="still")
    stage._path = None
    assert all(view(stage, t / 2).zoom == 1.0 for t in range(60))
