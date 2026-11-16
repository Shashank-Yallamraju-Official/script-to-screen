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
    assert first["slot"] == 6 and first["facing"] == 1                              # by the fridge, facing it
    assert not any("slot" in (v or {}) for t in sc.script["turns"] for v in (t["enter"].values() if isinstance(t.get("enter"), dict) else []))
