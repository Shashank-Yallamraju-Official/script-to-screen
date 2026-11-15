"""The four layers only look downward. This is the rule that keeps presentation cheap to change."""
import ast
from pathlib import Path

TOON = Path(__file__).resolve().parents[1] / "script_to_screen"
MAY_USE = {                                   # a layer may import these, and nothing else of ours
    "vocabulary": set(),
    "script": {"vocabulary"},
    "world": {"script", "vocabulary"},
    "performance": {"script", "world", "vocabulary"},
    "presentation": {"script", "world", "performance", "vocabulary"},
    "readers": {"script", "world", "performance", "presentation", "vocabulary"},
    "commands": {"script", "world", "performance", "presentation", "readers", "vocabulary"},
    "tools": {"script", "world", "performance", "presentation", "readers", "commands", "vocabulary"},
}


def uses(py, layer):
    """The layers a file imports."""
    out = set()
    for node in ast.walk(ast.parse(py.read_text())):
        if isinstance(node, ast.ImportFrom) and node.level:
            depth = len(py.relative_to(TOON).parts) - 1          # 1 for a file directly inside a layer
            if node.level > depth:                               # reaches out of its own layer
                names = [node.module.split(".")[0]] if node.module else [a.name for a in node.names]
                out.update(names)
        elif isinstance(node, ast.ImportFrom) and (node.module or "").startswith("script_to_screen."):
            out.add(node.module.split(".")[1])
    return out - {layer}


def test_each_layer_imports_only_the_layers_below_it():
    for layer, allowed in MAY_USE.items():
        for py in (TOON / layer).rglob("*.py"):
            extra = uses(py, layer) - allowed
            assert not extra, f"{py.relative_to(TOON)} imports {sorted(extra)}"


def test_the_story_layers_cannot_draw_or_make_sound():
    for layer in ("script", "world", "performance"):
        for py in (TOON / layer).rglob("*.py"):
            src = py.read_text()
            assert "import skia" not in src and "import numpy" not in src, py.name


def test_the_world_keeps_a_log_of_every_change_and_its_cause(show):
    from script_to_screen.performance import Scene
    sc = Scene(show.scene("one", [dict(id=1, enter={"a": {"slot": 2}, "b": {"slot": 6}}, why="They arrive."),
                                  dict(id=2, who="a", say="You.", feel={"b": {"shame": 2}}, why="She accuses.")]))
    log = sc.world.log
    assert [(x["kind"], x["subject"], x["cause"]) for x in log if x["kind"] in ("enter", "feel")] == \
        [("enter", "a", 1), ("enter", "b", 1), ("feel", "b", 2)]
