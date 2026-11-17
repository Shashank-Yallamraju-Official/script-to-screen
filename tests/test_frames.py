"""The look of a finished episode is kept (shows/<show>/frames/<episode>.png) and compared here, so a change to the engine that
moves something on screen is noticed even when nobody is watching. If the change was meant: `s2s frames <episode> --accept`."""
from pathlib import Path

from script_to_screen.presentation import readings

CROWN = Path(__file__).resolve().parent.parent / "shows" / "crown"


def test_the_vote_looks_as_it_was_kept():
    changed, png = readings.frames(CROWN, "the-vote")
    assert not changed, f"these moments look different: {changed}. Before and now: {png}. If that was meant: s2s frames the-vote --accept --show shows/crown"
