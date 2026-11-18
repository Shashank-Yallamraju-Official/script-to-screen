"""An episode's outline: checked against the bible before its scenes exist, and against the film after."""
import shutil
from pathlib import Path

import pytest
import yaml

from script_to_screen import commands
from script_to_screen.readers import bible, outline

CROWN = Path(__file__).resolve().parents[1] / "shows" / "crown"


@pytest.fixture
def root(tmp_path):
    shutil.copytree(CROWN, tmp_path / "crown", ignore=shutil.ignore_patterns("out", ".s2s", "frames"))
    return tmp_path / "crown"


def beats(root, eid="the-vote"):
    return yaml.safe_load(outline.path(root, eid).read_text())["beats"]


def write(root, bs, eid="the-vote"):
    outline.path(root, eid).parent.mkdir(exist_ok=True)
    outline.path(root, eid).write_text(yaml.safe_dump(dict(beats=bs), sort_keys=False))


def said(root, eid="the-vote"):
    return [(p["turn"], p["msg"]) for p in outline.problems(root) if p["scene"] == f"(outline {eid})"]


def test_the_first_episodes_outline_agrees_with_its_film(root):
    assert said(root) == []
    rows = {r["beat"]["id"]: r for r in outline.rows(root, "the-vote")}
    assert rows["arrow"]["state"] == "filmed" and rows["arrow"]["film"]["motions"] == ["through", "shot", "lit", "swell", "burst"]
    assert rows["arrow"]["film"]["houses"] == ["signet", "cinder"]                                  # Signet was already there: a house stays
    assert rows["refusal"]["film"]["motions"] == ["speak"] and rows["days"]["state"] == "filmed"
    page = bible.build(root, page=True)
    assert '<div class="outline">' in page and 'class="chip reserved"' in page and "| `shot` | reserved | **1** first |" in page
    assert "<div" not in bible.build(root) and "| arrow |" in bible.build(root)                    # as text, a table


def test_an_outline_is_checked_before_any_scene_exists(root):
    write(root, [dict(id="siege", what="Hasp shuts the gate.", **{"for": "The first lockdown."}, motions=["shot", "walk", "lowered"], houses=["hasp", "haps"]),
                 dict(id="second", what="A second arrow.", motions=["shot"], reveals=["shooter", "nobody"], whta="typo"),
                 dict(id="lift", what="A cup is lowered on a string.", **{"for": "Brim reaches out."}, new=[{"lowered": "comes down slowly from above, swinging"}])], "the-siege")
    msgs = dict(said(root, "the-siege"))
    assert "not in series.yaml yet" in [m for t, m in said(root, "the-siege") if t is None][0]
    assert "'lowered', which does not exist" in " ".join(m for t, m in said(root, "the-siege") if t == "siege") and "list it under `new:`" in " ".join(m for t, m in said(root, "the-siege") if t == "siege")
    every = " | ".join(m for _, m in said(root, "the-siege"))
    assert "did you mean 'hasp'?" in every and "did you mean `what:`?" in every and "says no `for:`" in every
    assert "the motion 'walk', which has no tier yet" in every
    assert "use 2 of the reserved motion 'shot'" in msgs["second"] or "use 2 of the reserved motion 'shot'" in every
    assert "the kept secret 'nobody', which does not exist" in every
    assert "needs a new type of motion, 'lowered' (comes down slowly from above, swinging)" in msgs["lift"]
    assert [r["state"] for r in outline.rows(root, "the-siege")] == ["to write"] * 3
    assert "(1)" in outline.grid(root) or "(2)" in outline.grid(root)                               # planned, not filmed, in the season's grid


def test_the_film_is_held_to_its_outline(root):
    bs = beats(root)
    bs[0]["motions"] = ["speak", "hold", "leave"]                      # planned, and the film does not have it
    bs[1]["motions"] = ["shot", "through", "lit", "swell"]             # the film bursts, and the outline did not plan it
    bs[4]["houses"] = ["signet", "mallet"]                             # Hasp is at the table too
    bs = [b for b in bs if b["id"] != "refusal"]
    bs[4]["bars"] = 16
    write(root, bs)
    every = " | ".join(m for _, m in said(root))
    assert "plans the motion 'leave', which the film does not have here (the-council) yet" in every
    assert "the film has the motion 'burst' here (the-council), which the outline did not plan" in every
    assert "the film has the house 'hasp' here (the-council-again)" in every
    assert "add up to 16 bars; the scene runs 40" in every


def test_a_first_outline_can_be_drafted_from_the_film(root, capsys):
    outline.path(root, "the-vote").unlink()
    assert commands.run(["outline", "the-vote", "--draft", "--write", "--show", str(root)]) == 0
    bs = beats(root)
    assert [b["id"] for b in bs][:2] == ["the-council", "the-council-turn"] and bs[1]["from"] == 9 and bs[1]["motions"][0] in ("through", "shot")
    assert bs[0]["houses"] == ["signet"] and bs[1]["houses"] == ["signet", "cinder"]
    every = " | ".join(m for _, m in said(root))
    assert "says no `for:`" in every and "does not exist" not in every and "did not plan" not in every   # only the writer's part is missing
    assert commands.run(["outline", "the-vote", "--draft", "--write", "--show", str(root)]) != 0         # it never overwrites one
