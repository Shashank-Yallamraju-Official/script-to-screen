import pytest

from script_to_screen.performance import Scene
from script_to_screen.presentation.motion import pose
from script_to_screen.script import ScriptError

ENTER = dict(id=1, enter={"a": {"slot": 2}, "b": {"slot": 5}}, why="They are here.")


def last_info(sc, turn=-1):
    return sc.turns[turn]["info"][-1][1]


def test_every_turn_needs_a_reason(show):
    sc = Scene(show.scene("s01/e01/01", [ENTER, dict(id=2, feel={"a": {"joy": 1}})]))
    assert any("why" in p["msg"] and p["level"] == "error" for p in sc.problems)


def test_a_feeling_needs_a_tell_and_a_known_emotion(show):
    sc = Scene(show.scene("s01/e01/01", [ENTER, dict(id=2, feel={"a": {"fear": 1}}, why="x"), dict(id=3, feel={"a": {"glee": 1}}, why="x")]))
    msgs = " ".join(p["msg"] for p in sc.problems)
    assert "no tell" in msgs and "emotion list" in msgs


def test_what_is_felt_is_what_shows_when_nobody_has_taken_sides(show):
    sc = Scene(show.scene("s01/e01/01", [ENTER, dict(id=2, feel={"b": {"shame": 2}}, why="x")]))
    assert last_info(sc)["b"]["level"] == 2 and last_info(sc)["b"]["klass"] == "unopposed"


@pytest.mark.parametrize("sides, status, level, klass", [
    ({"a": "x", "c": "x", "b": "y"}, {}, 1, "alone"),            # outnumbered: less leaks
    ({"a": "x", "b": "y", "c": "y"}, {}, 3, "majority"),         # backed up: more does
    ({"a": "x", "c": "x", "b": "y"}, {"b": 6}, 3, "alone"),      # alone but with standing: not suppressed
])
def test_position_sets_how_much_leaks(show, sides, status, level, klass):
    turns = [dict(id=1, enter={"a": {"slot": 1}, "b": {"slot": 4}, "c": {"slot": 7}}, side=sides, status=status, why="x"),
             dict(id=2, feel={"b": {"shame": 2}}, why="x")]
    info = last_info(Scene(show.scene("s01/e01/01", turns)))["b"]
    assert (info["level"], info["klass"]) == (level, klass)


def test_tells_are_resolved_into_what_can_be_seen(show):
    sc = Scene(show.scene("s01/e01/01", [ENTER, dict(id=2, who="a", do={"a": {"orient": "b"}}, say="You.", feel={"b": {"shame": 3}}, why="x")]))
    o = sc.keys["b"][-1][1]
    assert (o["ly"], o["facing"]) == (1, 1)            # eyes down, and turned away from a (who is to the left)


@pytest.mark.parametrize("say, count", [
    ("Ha ha ha!", 1), ("Ha. Ha. Ha.", 3), ("Ha, ha, ha.", 1), (["Ha", "ha", "ha"], 3), (["Ha. Ha. Ha."], 1), ("Michael. Get in here.", 2),
])
def test_a_pause_separates_bubbles(show, say, count):
    sc = Scene(show.scene("s01/e01/01", [ENTER, dict(id=2, who="a", say=say, why="x")]))
    assert len(sc.lines) == count
    assert all(x["end"] == y["start"] for x, y in zip(sc.lines, sc.lines[1:]))     # each gives way to the next


def test_a_reaction_in_passing_fires_on_its_word_after_the_reflex(show):
    show.entity("b", reflex=2)
    turn = dict(id=2, who="a", say="Someone ate the last dumpling.", react=[dict(who="b", word="dumpling", feel={"shame": 1})], why="x")
    sc = Scene(show.scene("s01/e01/01", [ENTER, turn]))
    t = sc.turns[1]
    dum = next(s for s in t["sylls"] if s["text"].startswith("dum"))
    assert t["reacts"][0]["at"] == t["say_at"] + dum["at"] + 2
    assert t["reacts"][0]["at"] < t["say_at"] + t["reveal"]                        # while the line is still being said
    assert not sc.focus


def test_a_featured_reaction_makes_the_scene_wait(show):
    plain = dict(id=2, who="a", say="You.", why="x")
    sc0 = Scene(show.scene("s01/e01/01", [ENTER, plain]))
    sc1 = Scene(show.scene("s01/e01/01", [ENTER, dict(plain, react=[dict(who="b", do={"attention": "viewer"}, beat=8)])]))
    assert sc1.turns[1]["length"] == sc0.turns[1]["length"] + 8
    (start, end, who), = sc1.focus
    assert who == "b" and end - start == pytest.approx(8 * sc1.step)
    assert sc1.lines[-1]["end"] == pytest.approx(start)                            # the speaker's bubble closes for it
    mid, after = pose(sc1, "b", (start + end) / 2), pose(sc1, "b", end + 1)
    assert (mid["lx"], mid["ly"]) == (0, 0) and after["lx"] == pytest.approx(0)    # looks out; b faces out anyway


def test_a_take_is_dropped_when_its_moment_ends(show):
    turns = [dict(id=1, enter={"a": {"slot": 2}, "b": {"slot": 5, "orient": "a"}}, why="x"),
             dict(id=2, who="a", say="You.", react=[dict(who="b", do={"attention": "viewer"}, beat=4)], why="x")]
    sc = Scene(show.scene("s01/e01/01", turns))
    (start, end, _), = sc.focus
    assert pose(sc, "b", (start + end) / 2 + 0.1)["lx"] == pytest.approx(0)        # at the viewer during the beat
    assert pose(sc, "b", end + 1)["lx"] == -1                                      # back to a afterwards


def test_a_reaction_on_a_word_that_is_not_there_is_an_error(show):
    sc = Scene(show.scene("s01/e01/01", [ENTER, dict(id=2, who="a", say="You.", react=[dict(who="b", word="dumpling", feel={"shame": 1})], why="x")]))
    assert any("not in the line" in p["msg"] for p in sc.problems)


def test_feelings_carry_into_the_next_scene(show):
    show.scene("s01/e01/01", [ENTER, dict(id=2, who="a", say="You.", feel={"b": {"shame": 2}}, why="x")])
    nxt = Scene(show.scene("s01/e01/02", [ENTER]))
    assert nxt.carried == {"b": ("shame", 2, "a")}
    assert nxt.turns[0]["info"][0][1]["b"]["felt"] == "shame"                      # there from the first frame


def test_offscreen_events_change_what_is_carried(show):
    show.scene("s01/e01/01", [ENTER, dict(id=2, feel={"b": {"shame": 2}}, why="x")])
    nxt = Scene(show.scene("s01/e01/02", [ENTER], offscreen=[dict(feel={"b": "calm", "a": {"joy": 1}}, why="A night's sleep.")]))
    info = nxt.turns[0]["info"][0][1]
    assert info["b"]["felt"] is None and info["a"]["felt"] == "joy"


def test_an_entity_that_sits_a_scene_out_keeps_its_state(show):
    show.scene("s01/e01/01", [ENTER, dict(id=2, feel={"b": {"shame": 2}}, why="x")])
    show.scene("s01/e01/02", [dict(id=1, enter={"a": {"slot": 2}}, why="Alone.")])
    assert Scene(show.scene("s01/e01/03", [ENTER])).carried == {"b": ("shame", 2, None)}


def test_an_arc_changes_how_a_feeling_shows_from_a_scene_onward(show):
    show.entity("b", arc=[{"from": "s01/e01/02", "tells": {"shame": [{"posture": "contracted"}]}}])
    turns = [ENTER, dict(id=2, feel={"b": {"shame": 1}}, why="x")]
    first, second = show.scene("s01/e01/01", turns), show.scene("s01/e01/02", turns)
    before, after = Scene(first), Scene(second)
    assert before.keys["b"][-1][1]["ly"] == 1 and after.keys["b"][-1][1]["sy"] < 1


def test_a_show_written_for_another_schema_is_refused(show):
    (show.root / "show.yaml").write_text((show.root / "show.yaml").read_text().replace("schema: 2", "schema: 99"))
    with pytest.raises(ScriptError, match="schema"):
        Scene(show.scene("s01/e01/01", [ENTER]))


def test_an_arc_follows_series_order_not_file_names(show):
    """The scene called z comes first in series.yaml, so an arc that starts at it applies to a."""
    import yaml
    show.entity("b", arc=[{"from": "z", "tells": {"shame": [{"posture": "contracted"}]}}])
    turns = [ENTER, dict(id=2, feel={"b": {"shame": 1}}, why="x")]
    a, z = show.scene("a", turns), show.scene("z", turns)
    order = [dict(id="z", scene="episodes/z.yaml"), dict(id="a", scene="episodes/a.yaml")]
    (show.root / "series.yaml").write_text(yaml.safe_dump(dict(seasons=[dict(id="s", episodes=[dict(id="e", segments=order)])])))
    assert Scene(a).keys["b"][-1][1]["sy"] < 1 and Scene(z).keys["b"][-1][1]["sy"] < 1


def test_a_scene_that_is_not_in_the_series_is_refused(show):
    path = show.scene("s01/e01/01", [ENTER])
    (show.root / "series.yaml").write_text("seasons: []\n")
    with pytest.raises(ScriptError, match="not listed in series.yaml"):
        Scene(path)
