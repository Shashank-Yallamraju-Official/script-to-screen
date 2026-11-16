"""Placing: where an entity stands when the script does not say."""
from pathlib import Path

from script_to_screen.performance import placing
from script_to_screen.performance.scene import Scene
from script_to_screen.script import load_yaml, place, series, things

DEMO = Path(__file__).resolve().parent.parent / "shows" / "demo"
VALENCE = load_yaml(DEMO / "show.yaml")["valence"]
KITCHEN = things(place(DEMO, "kitchen"))
sheet = lambda e: load_yaml(DEMO / "entities" / f"{e}.yaml")


def test_someone_found_in_a_room_stands_beside_what_serves_their_strongest_need():
    slot, drew, why = placing.found("otis", sheet("otis"), {}, KITCHEN, {}, VALENCE)
    assert drew == "fridge" and abs(slot - KITCHEN["fridge"]["at"]) <= 1 and "comfort" in why
    slot, drew, why = placing.found("juno", sheet("juno"), {}, KITCHEN, {}, VALENCE)
    assert drew is None and slot == 4                              # nothing in the kitchen draws her: the middle


def test_a_written_regard_wins_and_a_dreaded_thing_is_kept_away_from():
    otis = dict(sheet("otis"), regards={"fridge": {"shame": 3}})
    slot, drew, why = placing.found("otis", otis, {}, KITCHEN, {}, VALENCE)
    assert abs(slot - KITCHEN["fridge"]["at"]) >= 4 and drew is None and "away from" in why


def test_someone_who_arrives_comes_in_by_the_door_or_from_the_side_named():
    assert placing.arrives("juno", {}, {"otis": 6}, KITCHEN) == (8, "comes in through the door")
    assert placing.arrives("bix", {"from": "left"}, {"otis": 6}, KITCHEN)[0] == 0
    assert placing.arrives("juno", {}, {"otis": 8}, KITCHEN)[0] == 7                # the place by the door is taken


def test_a_night_kitchen_has_the_kitchens_things_and_things_can_be_faced():
    assert set(things(place(DEMO, "kitchen-night"))) == set(KITCHEN)
    sc = Scene(series(DEMO).by_id["lights-out"]["path"])
    first = sc.keys["otis"][0][1]
    fridge = KITCHEN["fridge"]["at"]
    assert abs(first["slot"] - fridge) <= 1.5 and first["facing"] == (1 if fridge > first["slot"] else -1)   # by the fridge, facing it
    assert first["slot"] > fridge                                                   # and on the side away from the plate, which shames him
    assert not any("slot" in (v or {}) for t in sc.script["turns"] for v in (t["enter"].values() if isinstance(t.get("enter"), dict) else []))


def test_what_a_thing_has_come_to_mean_is_carried_into_later_scenes_and_fires_when_it_is_named():
    sc = Scene(series(DEMO).by_id["lights-out"]["path"])
    assert sc.world.regards["otis"]["plate"] == ("shame", 2)                        # set in the first scene of the episode
    turn = next(t for t in sc.turns if t["id"] == 4)                                # "You ate the dumpling."
    assert turn["fired"]["otis"]["thing"] == "plate" and "dumpling" in turn["fired"]["otis"]["why"]
    info = turn["info"][-1][1]["otis"]
    assert (info["felt"], info["intensity"], info["at"]) == ("shame", 2, "plate")
    assert placing.named("You ate the dump·ling.", KITCHEN) == ("plate", "dumpling")
    assert placing.named("Nothing to see.", KITCHEN) is None


def test_whatever_a_turn_already_makes_someone_feel_wins_over_a_thing_being_named():
    sc = Scene(series(DEMO).by_id["the-last-dumpling"]["path"])
    turn = next(t for t in sc.turns if t["id"] == 2)                                # the accusation names the dumpling too
    assert "otis" not in turn["fired"]
    assert turn["info"][-1][1]["otis"]["at"] == "juno"                              # his shame is about her, from the event


def test_a_feeling_about_a_thing_is_framed_with_the_thing():
    from script_to_screen.performance import camera
    sc = Scene(series(DEMO).by_id["lights-out"]["path"])
    t = next(x for x in sc.turns if x["id"] == 4)
    when = next(at for at, who in camera.changes(t, sc.keys, sc.step, 0.6, {k: v["at"] for k, v in sc.world.things.items()}) if "otis" in who)
    shot = [s for s in sc.score.camera if s["t"] <= when + 2e-3][-1]
    half = camera.FRAME / shot["zoom"] / 2
    assert shot["centre"] - half <= KITCHEN["plate"]["at"] <= shot["centre"] + half
