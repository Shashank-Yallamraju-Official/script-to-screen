"""Branches: every combination of the candidate answers to what a story leaves open, worked through and scored."""
import shutil
from pathlib import Path

from script_to_screen.readers import branches

HEIST = Path(__file__).resolve().parent.parent / "shows" / "heist"


def test_every_combination_is_worked_through_and_what_cannot_happen_is_left_out():
    rep = branches.explore(HEIST)
    assert len(rep["leaves"]) + rep["skipped"] == 4 * 14 * 8 * 3            # snags x sets of up to three harms x sets of moments x endings
    assert rep["skipped"] > 0 and all("knocked down" not in x["harm"] or x["snag"] == "Dot is working late that night" for x in rep["leaves"])
    assert [x["score"] for x in rep["leaves"]] == sorted((x["score"] for x in rep["leaves"]), reverse=True)


def test_one_blow_cannot_break_every_excuse_and_three_can():
    rep = branches.explore(HEIST)
    assert rep["fewest"] == 3 and rep["all_earned"] >= 1
    best = rep["leaves"][0]
    assert sorted(best["earned"]) == sorted(rep["members"]) and best["snag"] == "Dot is working late that night"
    assert all(len(x["earned"]) < 5 for x in rep["leaves"] if len(x["harms"]) < 3)


def test_a_turn_is_earned_only_by_someone_who_cares_and_whose_excuse_breaks():
    rep = branches.explore(HEIST)
    cold = next(x for x in rep["leaves"] if not x["care"] and x["harms"] == ["Dot is blamed for it the next morning"])
    assert cold["earned"] == [] and sorted(cold["unearned"]) == ["ines", "nico"]          # their excuses break, but she is nobody to them
    assert sorted(cold["feels"]) == ["sam", "vera"]                                         # these two know her, and can still excuse it


def test_the_score_is_the_sum_of_its_visible_parts(tmp_path):
    rep = branches.explore(HEIST)
    for x in rep["leaves"][:20]:
        assert x["score"] == round(sum(branches.WEIGHTS[k] * v for k, v in x["parts"].items()), 1)
    assert set(rep["sway"]) == {"snag", "harm", "care", "ending", "blows"}
    shutil.copytree(HEIST, tmp_path / "heist")
    (tmp_path / "heist" / "branches.yaml").unlink()
    try:
        branches.explore(tmp_path / "heist")
        assert False
    except Exception as err:
        assert "branches.yaml" in str(err)
