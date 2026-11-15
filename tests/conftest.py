"""A throwaway show for each test, built from the demo show's settings and library."""
import shutil
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml

DEMO = Path(__file__).resolve().parents[1] / "shows" / "demo"
TELLS = {"shame": [{"attention": "down"}, {"tone": "nervous", "latency": 5}, {"orient": "away"}],
         "joy": [{"tone": "cheerful"}, {"posture": "lean_in"}]}


@pytest.fixture
def show(tmp_path):
    shutil.copy(DEMO / "show.yaml", tmp_path)
    shutil.copytree(DEMO / "library", tmp_path / "library")
    (tmp_path / "entities").mkdir()

    def entity(name, tells=TELLS, **extra):
        data = {**dict(color="#888888", voice=300, status=1, reflex=0, tells=tells), **extra}
        (tmp_path / "entities" / f"{name}.yaml").write_text(yaml.safe_dump(data))

    def scene(name, turns, **top):
        path = tmp_path / "episodes" / f"{name}.yaml"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(yaml.safe_dump(dict(scene=name, turns=turns, **top), allow_unicode=True))
        names.add(name)                                  # the scene's id is the name it was given; order is by name
        segments = [dict(id=n, scene=f"episodes/{n}.yaml") for n in sorted(names)]
        (tmp_path / "series.yaml").write_text(yaml.safe_dump(dict(seasons=[dict(id="s", episodes=[dict(id="e", segments=segments)])])))
        return path

    names = set()

    for name in ("a", "b", "c"):
        entity(name)
    return SimpleNamespace(root=tmp_path, entity=entity, scene=scene)
