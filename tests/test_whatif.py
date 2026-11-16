"""What if: one setup and one event, appraised as it stands and in variations."""
from pathlib import Path

import json

from script_to_screen import commands
from script_to_screen.readers import whatif
from script_to_screen.script import series

DEMO = Path(__file__).resolve().parent.parent / "shows" / "demo"
FILE = DEMO / "what-ifs" / "the-accusation.yaml"


def run(argv, capsys):
    capsys.readouterr()
    assert commands.run([*argv, "--json"]) == 0
    return json.loads(capsys.readouterr().out)


def cells(out):
    return {c["name"]: {e: (r["feels"], r["strength"], r["inclined"]) for e, r in c["reactions"].items()} for c in out["cases"]}


def test_a_what_if_file_gives_one_column_per_variation(capsys):
    got = cells(run(["what-if", str(FILE)], capsys))
    assert got["as it stands"] == {"juno": ("joy", 1, "press"), "otis": ("shame", 2, "deny")}
    assert got["Otis didn't do it"]["otis"] == ("fear", 2, "back away")          # innocent, and he cannot answer her
    assert got["Juno doesn't know"]["juno"] == (None, 0, None)                   # she is only asking
    assert got["Bix is there"]["bix"] == ("fear", 2, "freeze")                   # for otis, through its bond
    assert got["Bix did it, and is there"]["bix"] == ("shame", 2, "withdraw")
    assert got["Otis outranks her"]["otis"] == ("shame", 2, "hit back")          # the same feeling, a different inclination


def test_a_what_if_on_a_turn_starts_from_the_scene_as_it_stands_there(capsys):
    setup, event = whatif.from_turn(series(DEMO).by_id["the-thermostat"]["path"], 2)
    assert set(setup["present"]) == {"juno", "otis", "bix"} and setup["sides"]["juno"] == "owner"
    assert setup["feelings"]["otis"][0] == "shame"                               # carried in from the vase
    out = run(["what-if", "thermostat:2", "--doer", "dial=otis", "--knows", "dial=otis", "--show", str(DEMO)], capsys)
    got = cells(out)
    assert got["as it stands"]["bix"] == ("shame", 3, "withdraw") and got["as asked"]["bix"][0] == "fear"
    assert got["as asked"]["otis"] == ("shame", 3, "deny")                       # already at 3: a milder blow does not lessen it


def test_a_what_if_changes_nothing(capsys):
    before = {p: p.read_bytes() for p in DEMO.rglob("*.yaml")}
    run(["what-if", str(FILE)], capsys)
    run(["what-if", "dumpling:2", "--with", "bix", "--show", str(DEMO)], capsys)
    assert before == {p: p.read_bytes() for p in DEMO.rglob("*.yaml")}
