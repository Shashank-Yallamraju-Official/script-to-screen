"""The bible lives in the show: what the film knows is read from the film, and the rules are checked against it."""
import shutil
from pathlib import Path

import pytest
import yaml

from script_to_screen import commands
from script_to_screen.readers import bible
from script_to_screen.script import place

CROWN = Path(__file__).resolve().parents[1] / "shows" / "crown"


@pytest.fixture
def root(tmp_path):
    shutil.copytree(CROWN, tmp_path / "crown", ignore=shutil.ignore_patterns("out", ".s2s", "frames"))
    return tmp_path / "crown"


def edit(path, old, new):
    text = path.read_text()
    assert text.count(old) >= 1, old
    path.write_text(text.replace(old, new, 1))


def test_the_show_as_it_stands_keeps_its_own_rules_and_every_slot_is_filled(root):
    assert bible.veers(root) == []
    text = bible.build(root)
    assert "{{" not in text and "**On track.**" in text
    assert "| 38 to 85 | Signet is rebuilt as it was | Mallet's work |" in text                   # the days, from the land's history
    assert "| seven arches | a seat each" in text and "The vote is called." in text              # a room's notes; a scene's beats
    assert "| the-vote | One: the vote |" in text and "116 bars" in text                         # the season from above
    assert "<table>" in bible.to_html(text) and "<h2 id=\"the-120-days\">" in bible.to_html(text)


def test_a_line_a_colour_a_piece_or_a_word_that_breaks_a_rule_is_a_warning_that_says_where(root):
    scene = root / "episodes" / "e01" / "01-the-council.yaml"
    edit(scene, "say: By order of the crown. We vote.", "say: By order of the crown. He votes on the motion.")
    edit(root / "places" / "crown.yaml", '{kind: vine, at: 7, wide: 0.8, color: "#4a9a52"}', '{kind: vine, at: 6, wide: 0.8, color: "#d81bd8"}')
    b = yaml.safe_load((root / "bible.yaml").read_text())
    b["kept"][0]["words"] = ["motion"]
    (root / "bible.yaml").write_text(yaml.safe_dump(b, sort_keys=False))
    found = {(v["rule"], v["scene"]): v["msg"] for v in bible.veers(root)}
    assert "the line says he" in found[("agender", "the-council")]
    assert "motion" in found[("unexplained", "the-council")] and "What the vote is on" in found[("unexplained", "the-council")]
    assert "no house's" in found[("colour", "crown")]
    assert "has no mirror" in found[("order", "crown")]
    assert all(v["level"] == "warning" for v in bible.veers(root))                               # a veer never stops a render
    assert commands.run(["check", "--show", str(root), "--json"]) == 0
    assert "veers from a rule" in bible.build(root)


def test_a_house_says_its_colour_once_and_a_place_takes_it_by_name(root):
    assert {pc["color"] for pc in place(root, "crown")["pieces"] if pc["kind"] == "banner"} == {"#c8324e"}
    edit(root / "land.yaml", 'color: "#c8324e"', 'color: "#aa2040"')
    assert {pc["color"] for pc in place(root, "crown")["pieces"] if pc["kind"] == "banner"} == {"#aa2040"}
    edit(root / "places" / "crown.yaml", '"@signet"', '"@nobody"')
    with pytest.raises(Exception, match="no house of that name"):
        place(root, "crown")


def test_a_slot_the_tool_cannot_fill_is_refused_by_name(root):
    (root / "bible.md").write_text("# X\n\n{{weather}}\n")
    with pytest.raises(ValueError, match="weather"):
        bible.build(root)


def test_the_film_is_read_for_its_motions_and_a_reserved_one_spent_twice_is_a_warning(root):
    from script_to_screen.readers import motions
    rows = {r["name"]: r for r in motions.table(root)}
    assert (rows["shot"]["tier"], rows["shot"]["times"], rows["shot"]["first"]) == ("reserved", 1, "the-council:9")
    assert rows["speak"]["tier"] == "familiar" and rows["speak"]["times"] > 20 and rows["walk"]["times"] == 0
    assert motions.problems(root) == [] and "`through`" in bible.build(root) and "Possible but not used yet" in bible.build(root)
    again = root / "episodes" / "e01" / "02-the-council-again.yaml"
    text = again.read_text()
    again.write_text(text.replace("sfx: [{at: 10, sound: swell}]", "sfx: [{at: 10, sound: blast, on: great-seal}]", 1))
    assert text != again.read_text()
    found = {v["scene"]: v["msg"] for v in bible.veers(root) if v["rule"] == "reserve"}
    assert "use 2 of it in this episode" in found["the-council-again"]
    b = yaml.safe_load((root / "bible.yaml").read_text())
    b["motions"]["reserved"] = {"shot": 1, "through": 1, "lit": 1, "swell": 2, "burst": 2}          # two a show, said outright
    b["motions"]["familiar"] = ["hold"]                                                           # and speaking left unsorted
    (root / "bible.yaml").write_text(yaml.safe_dump(b, sort_keys=False))
    msgs = [v["msg"] for v in bible.veers(root) if v["rule"] == "reserve"]
    assert len(msgs) == 1 and "'speak'" in msgs[0] and "has no tier yet" in msgs[0]
