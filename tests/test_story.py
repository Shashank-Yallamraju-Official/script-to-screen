"""A story as a series of filters: what each decision forces, narrows and leaves open."""
import shutil
from pathlib import Path

import pytest

from script_to_screen.performance import crew, standing, tendencies
from script_to_screen.readers import story
from script_to_screen.script import load_yaml

HEIST = Path(__file__).resolve().parent.parent / "shows" / "heist"


@pytest.fixture
def copy(tmp_path):
    shutil.copytree(HEIST, tmp_path / "heist")
    return tmp_path / "heist"


def cut(root, after):
    """Keep story.yaml only as far as the given gate's decision."""
    text = (root / "story.yaml").read_text()
    (root / "story.yaml").write_text(text[:text.index(after)])


def all_of(gate):
    return " | ".join(gate["forced"] + gate["narrowed"] + gate["problems"])


def test_each_gate_is_decided_and_the_consequences_follow():
    g = {x["name"]: x for x in story.report(HEIST)["gates"]}
    assert "needs 5 crafts" in all_of(g["the lock"])
    assert "vera is the planner" in all_of(g["the crew"]) and "sam (has power; lacks wealth and status) needs persuading" in all_of(g["the crew"])
    assert "nico holds it together" in all_of(g["the ties"]) and "nico is the weak link" in all_of(g["the ties"])
    assert "it goes wrong at step 3, locks: ruth has to rely on ines" in all_of(g["the plan"])
    assert "the harm lands on dot at step 3" in all_of(g["the twist"]) and "sam turns first" in all_of(g["the twist"])
    assert not any(x["problems"] for x in g.values())


def test_the_theme_says_what_everything_after_has_to_do(copy):
    g = {x["name"]: x for x in story.report(copy)["gates"]}
    said = all_of(g["the theme"])
    assert "nobody is good or bad" in said and "hale, the mark, is surviving too" in said
    assert "ruth's excuse" in said and "someone is hurt, and has a face" in said
    assert "giving it back costs ruth, nico nothing they still need" in all_of(g["the twist"])            # the crew already gave it to them
    assert "a real loss for vera (control, pressure 3), sam (safety, pressure 3), ines (esteem, pressure 3)" in all_of(g["the twist"])
    assert any("come to care about dot" in x for x in g["the twist"]["open"])
    text = (copy / "story.yaml").read_text()
    (copy / "story.yaml").write_text(text.replace("twist: the-turn", "twist: staged-failure"))
    assert any("does not serve the theme" in p for p in story.report(copy)["gates"][-1]["problems"])       # the standard twist is the wrong one here
    (copy / "story.yaml").write_text(text.replace("world: dot", "# world: dot"))
    assert any("nobody stands for the world" in p for p in story.report(copy)["gates"][0]["problems"])


def test_nobody_is_a_wall_everyone_is_surviving_something(copy):
    sheet = (copy / "entities" / "hale.yaml").read_text().replace("power: -1", "power: 2")
    (copy / "entities" / "hale.yaml").write_text(sheet)
    assert any("nothing presses on hale" in p for p in story.report(copy)["gates"][0]["problems"])


def test_what_a_group_gives_someone_no_longer_presses_on_them():
    nico = load_yaml(HEIST / "entities" / "nico.yaml")
    assert standing.pressures(nico)[0][0] == "belonging" and standing.pressures(nico, given=(1.0, -1.0)) == []
    sam = load_yaml(HEIST / "entities" / "sam.yaml")
    assert standing.pressures(sam, given=(1.0, 1.0))[0][:2] == ("safety", 3)                               # trust does not pay the rent


def test_every_decision_leaves_less_open(copy):
    full = [f["open"] for f in story.report(copy)["funnel"]]
    assert full == sorted(full, reverse=True) and full[0] > full[-1] >= len(story.ALWAYS_OPEN)
    cut(copy, "# Gate 3.")
    rep = story.report(copy)
    assert rep["next"] == "the ties" and [g["decided"] is not None for g in rep["gates"]] == [True, True, True, False, False, False]
    assert rep["gates"][3]["open"] == story.ASKS["the ties"]
    cut(copy, "# Gate 1.")
    rep = story.report(copy)
    assert rep["next"] == "the lock" and "one of bank" in rep["gates"][1]["narrowed"][0]


def test_a_decision_that_leaves_nothing_possible_is_reported(copy):
    sheet = (copy / "entities" / "ruth.yaml").read_text().replace("needs: {esteem: 2}", "needs: {esteem: 0}").replace("drive: 2", "drive: -1")
    (copy / "entities" / "ruth.yaml").write_text(sheet)
    crew_gate = story.report(copy)["gates"][2]
    assert any("ruth would not do it" in p for p in crew_gate["problems"])
    plan = (copy / "story.yaml").read_text().replace("{pin: systems, who: ines}", "{pin: systems, who: nico}")
    (copy / "story.yaml").write_text(plan)
    assert any("nico is down for systems and has no such craft" in p for p in story.report(copy)["gates"][4]["problems"])


def test_pressure_is_a_strong_need_that_standing_does_not_meet():
    sam = load_yaml(HEIST / "entities" / "sam.yaml")
    assert standing.pressures(sam)[0][:2] == ("safety", 3)                 # needs safety, has no money
    assert standing.answer(sam)[0] == "persuade"                           # but far more cautious than driven
    hale = load_yaml(HEIST / "entities" / "hale.yaml")
    assert standing.pressures(hale) == [] and standing.answer(hale)[0] == "no"


def test_a_tie_is_trust_and_rating_and_the_group_is_read_off_the_ties():
    assert crew.attitude(1, 1) == "relies on" and crew.attitude(1, -1) == "carries" and crew.attitude(-1, 1) == "watches" and crew.attitude(0, 0) == "dismisses"
    sheets = {"a": {"bonds": {"b": [1, 1], "c": [1, -1]}}, "b": {"bonds": {"a": [1, 1], "c": [1, -1]}}, "c": {"bonds": {"a": [1, 0], "b": [1, 0]}}}
    read = crew.readings(sheets, ["a", "b", "c"])
    assert read["weak_link"] == "c" and len(read["factions"]) == 1 and read["cohesion"] == 1.0
    assert crew.strain(sheets, "a", "b") == 0 and crew.strain(sheets, "a", "c") == 2


def test_a_threat_from_outside_closes_ranks_and_silences_the_blame():
    rep = story.report(HEIST)
    members = ["vera", "sam", "ruth", "nico", "ines"]
    sheets = story._sheets(HEIST, members, load_yaml(HEIST / "story.yaml")["ties"])
    base = dict(present=members, clock=True, loss=True, blame="unclear", felt={m: ("fear", 3) for m in members})
    inside = tendencies.apply(dict(base, threat="inside"), sheets)
    assert any(x["name"] == "scapegoating" and x["effect"] == "blames nico" for x in inside)
    assert "nico" not in next(x["to"] for x in inside if x["name"] == "scapegoating")
    outside = tendencies.apply(dict(base, threat="outside"), sheets)
    assert any(x["name"] == "common enemy" for x in outside) and any(x["name"] == "scapegoating" and x["effect"] == "(silenced)" for x in outside)
    assert not any(x["name"] == "scapegoating" for x in tendencies.apply(dict(base, threat="inside"), sheets, off=("scapegoating",)))
    assert rep["funnel"][-1]["forced"] > 35


def test_conformity_needs_someone_alone_and_reciprocity_needs_a_gift():
    members = ["vera", "sam", "ruth"]
    sheets = story._sheets(HEIST, members, {})
    alone = tendencies.apply(dict(present=members, dissenter="sam", sides={"sam": "no", "vera": "yes", "ruth": "yes"}), sheets)
    assert any(x["name"] == "conformity" and x["to"] == ["sam"] for x in alone)
    backed = tendencies.apply(dict(present=members, dissenter="sam", sides={"sam": "no", "vera": "yes", "ruth": "no"}), sheets)
    assert not any(x["name"] == "conformity" for x in backed)
    given = tendencies.apply(dict(present=members, gift={"from": "vera", "to": "sam", "what": "the truth, first"}), sheets)
    assert any(x["name"] == "reciprocity" and x["to"] == ["sam"] for x in given)
