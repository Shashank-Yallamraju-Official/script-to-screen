"""Appraisal: what an event makes each character feel, worked out from who they are."""
from pathlib import Path

from script_to_screen.performance import appraisal
from script_to_screen.performance.scene import Scene
from script_to_screen.script import load_yaml, series

DEMO = Path(__file__).resolve().parent.parent / "shows" / "demo"
SHEETS = {e: load_yaml(DEMO / "entities" / f"{e}.yaml") for e in ("juno", "otis", "bix")}
VALENCE = load_yaml(DEMO / "show.yaml")["valence"]
ACCUSE = dict(kind="threat", need="esteem", size=2, by="juno", target="otis", fact="it", accuses=True)


def minds(facts, sides=None, standing=None):
    return appraisal.Minds(SHEETS, sides or {}, standing or {}, facts, VALENCE)


def felt(m, ev, who=("juno", "otis", "bix")):
    return {e: next(iter(v["feel"].items())) for e, v in appraisal.feelings(m, [ev], who).items()}


def test_the_same_accusation_lands_differently_on_the_guilty_and_the_innocent():
    guilty = felt(minds({"it": dict(doer="otis", knows=["otis", "juno"])}), ACCUSE, ("juno", "otis"))
    assert guilty["otis"] == ("shame", 2) and guilty["juno"] == ("joy", 1)        # his doing; and she knows she is right
    innocent = felt(minds({"it": dict(doer="bix", knows=["bix"])}), ACCUSE, ("juno", "otis"))
    assert innocent["otis"] == ("fear", 2) and "juno" not in innocent            # not his doing, and he cannot answer her; she is only asking


def test_who_can_answer_gets_angry_and_who_cannot_gets_afraid():
    loss = dict(kind="loss", need="control", size=2, target="juno")
    assert felt(minds({}), loss)["juno"] == ("anger", 2)                         # dominant, on her own ground
    assert felt(minds({}), dict(loss, target="bix", need="belonging"))["bix"][0] in ("sadness", "fear")


def test_a_bystander_feels_it_through_a_bond_unless_they_have_a_stake_of_their_own():
    m = minds({"it": dict(doer="otis", knows=["otis"])})
    assert felt(m, ACCUSE)["bix"][0] == "fear"                                   # bad for otis, who bix is bonded to
    m = minds({"it": dict(doer="bix", knows=["bix"])})
    caught = dict(kind="gain", need="control", size=1, target="juno", fact="it")
    assert "bix" not in felt(m, caught)                                          # bix did it: no joy on juno's behalf


def test_a_strong_bad_feeling_still_carried_colours_the_next_bad_thing():
    m = minds({"it": dict(doer="bix", knows=["bix"])}, standing={"otis": ("shame", 3, "bix")})
    assert felt(m, ACCUSE, ("otis",))["otis"] == ("shame", 3)


def test_a_slight_event_stays_slight_and_nobody_else_feels_what_was_unseen():
    slight = dict(kind="relief", need="belonging", size=1, by="otis", target="bix")
    assert felt(minds({}), slight)["bix"] == ("joy", 1)
    unseen = dict(kind="loss", need="control", size=1, by="bix", target="juno", unseen=True)
    assert set(felt(minds({}), unseen)) == {"bix"}


def test_a_feeling_written_on_a_turn_wins_over_the_one_worked_out():
    path = series(DEMO).by_id["the-vase"]["path"]
    sc = Scene(path)
    turn = sc.turns[1]
    assert turn["appraised"]["bix"]["feel"] == {"fear": 2, "at": "juno"}         # worked out
    assert turn["info"][-1][1]["bix"]["felt"] is None                            # but the script says calm, and the script wins


def test_an_event_that_makes_no_sense_is_refused():
    assert appraisal.problems(dict(kind="oops", need="esteem", target="otis"), {"otis"}, {})
    assert appraisal.problems(dict(kind="loss", need="esteem", target="otis", fact="nope"), {"otis"}, {})
    assert appraisal.problems(dict(kind="loss", need="esteem", target="otis"), {"otis"}, {}) is None
