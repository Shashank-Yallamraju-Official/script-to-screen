"""Layer 1, the script: what the writer and the assistant write. Files in, plain data out.

This layer reads a show's files and knows their layout. It decides nothing about what
happens; it imports no other layer.
"""
from pathlib import Path

import yaml

LIBRARY = ("tones", "sounds", "feel")
SCHEMA = 1                                  # the file format this engine reads; see docs/architecture.md


class ScriptError(Exception):
    pass


def load_yaml(p):
    with open(p) as fh:
        return yaml.safe_load(fh)


def find_root(path):
    path = Path(path).resolve()
    for p in [path] + list(path.parents):
        if (p / "show.yaml").exists():
            return p
    raise ScriptError("no show.yaml above " + str(path))


def scene_paths(root):
    return sorted((Path(root) / "episodes").rglob("*.yaml"))


def scene_key(path, root):
    return Path(path).relative_to(Path(root) / "episodes").with_suffix("").as_posix()


class Show:
    """A show's settings, library and entity sheets."""

    def __init__(self, root, lib=None):
        self.root = root
        self.cfg = load_yaml(root / "show.yaml")
        if self.cfg.get("schema", SCHEMA) != SCHEMA:
            raise ScriptError(f"this show is written for schema {self.cfg['schema']}, and this engine reads schema {SCHEMA}")
        for name in LIBRARY:                 # the editor passes its unsaved copies in `lib`
            setattr(self, name, (lib or {}).get(name) or load_yaml(root / "library" / f"{name}.yaml"))
        self.emotions = self.cfg["emotions"]

    def entity(self, eid, key):
        """An entity's sheet as it stands at scene `key`: its arc has changed its tells up to here."""
        p = self.root / "entities" / f"{eid}.yaml"
        if not p.exists():
            raise ScriptError(f"no entity file entities/{eid}.yaml")
        ent = load_yaml(p)
        ent["id"] = eid
        tells = dict(ent.get("tells") or {})
        for step in ent.get("arc") or []:          # the slow clock: the map itself changes
            if str(step["from"]) <= key:
                tells.update(step.get("tells") or {})
        ent["tells"] = tells
        return ent
