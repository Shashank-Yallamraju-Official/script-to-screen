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
    assert "in on it: vera, ruth, ines. Not told: sam, nico" in all_of(g["the twist"]) and "sam wavers at the split" in all_of(g["the twist"])
    assert not any(x["problems"] for x in g.values())


def test_every_decision_leaves_less_open(copy):
    full = [f["open"] for f in story.report(copy)["funnel"]]
    assert full == sorted(full, reverse=True) and full[-1] == len(story.ALWAYS_OPEN)
    cut(copy, "# Gate 3.")
    rep = story.report(copy)
    assert rep["next"] == "the ties" and [g["decided"] is not None for g in rep["gates"]] == [True, True, False, False, False]
    assert rep["gates"][2]["open"] == story.ASKS["the ties"]
    cut(copy, "# Gate 1.")
    rep = story.report(copy)
    assert rep["next"] == "the lock" and "one of bank" in rep["gates"][0]["narrowed"][0]


def test_a_decision_that_leaves_nothing_possible_is_reported(copy):
    sheet = (copy / "entities" / "ruth.yaml").read_text().replace("needs: {esteem: 2}", "needs: {esteem: 0}").replace("drive: 2", "drive: -1")
    (copy / "entities" / "ruth.yaml").write_text(sheet)
    crew_gate = story.report(copy)["gates"][1]
    assert any("ruth would not do it" in p for p in crew_gate["problems"])
    plan = (copy / "story.yaml").read_text().replace("{pin: systems, who: ines}", "{pin: systems, who: nico}")
    (copy / "story.yaml").write_text(plan)
    assert any("nico is down for systems and has no such craft" in p for p in story.report(copy)["gates"][3]["problems"])


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
    assert rep["funnel"][-1]["forced"] > 25


def test_conformity_needs_someone_alone_and_reciprocity_needs_a_gift():
    members = ["vera", "sam", "ruth"]
    sheets = story._sheets(HEIST, members, {})
    alone = tendencies.apply(dict(present=members, dissenter="sam", sides={"sam": "no", "vera": "yes", "ruth": "yes"}), sheets)
    assert any(x["name"] == "conformity" and x["to"] == ["sam"] for x in alone)
    backed = tendencies.apply(dict(present=members, dissenter="sam", sides={"sam": "no", "vera": "yes", "ruth": "no"}), sheets)
    assert not any(x["name"] == "conformity" for x in backed)
    given = tendencies.apply(dict(present=members, gift={"from": "vera", "to": "sam", "what": "the truth, first"}), sheets)
    assert any(x["name"] == "reciprocity" and x["to"] == ["sam"] for x in given)
