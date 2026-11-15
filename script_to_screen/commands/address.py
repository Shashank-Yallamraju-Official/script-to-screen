"""Addresses: short names for places in a show, the same for a person and an assistant.

    s01/e01/03-the-thermostat      a scene, by its key
    thermostat                     the same scene, by any part of its name that is unique
    thermostat:2                   turn 2 of it (a turn's `id`, or its number if it has none)
    thermostat:2+6                 six steps into that turn
    path/to/scene.yaml             a file path works wherever a scene is expected
"""
import re
from pathlib import Path

from ..script import ScriptError, find_root, scene_key, scene_paths
from . import Refused


def show_root(hint=None):
    """The show a command is about: --show, else the show around here, else the only one below here."""
    try:
        return find_root(Path(hint or ".").resolve())
    except ScriptError:
        found = sorted(Path(hint or ".").resolve().glob("shows/*/show.yaml")) + sorted(Path(hint or ".").resolve().glob("*/show.yaml"))
        if len(found) == 1:
            return found[0].parent
        raise Refused("no show found here", hint="run inside a show's folder, or pass --show <folder>" +
                      (". Shows below here: " + ", ".join(f.parent.name for f in found) if found else ""))


def scene(ref, show=None):
    """-> (root, path) for a scene reference."""
    ref = str(ref)
    if ref.endswith((".yaml", ".yml")) and Path(ref).exists():
        p = Path(ref).resolve()
        return find_root(p), p
    root = show_root(show)
    keys = {scene_key(p, root): p for p in scene_paths(root)}
    if ref in keys:
        return root, keys[ref]
    bare = lambda k: re.sub(r"^\d+-", "", k.rsplit("/", 1)[-1])
    for test in (lambda k: k.endswith("/" + ref) or bare(k) == ref, lambda k: ref in k):
        hits = [k for k in keys if test(k)]
        if len(hits) == 1:
            return root, keys[hits[0]]
        if len(hits) > 1:
            raise Refused(f"'{ref}' matches {len(hits)} scenes", hint="say which: " + ", ".join(hits))
    raise Refused(f"no scene '{ref}'", hint="scenes: " + ", ".join(keys))


def turn(ref, show=None):
    """-> (root, path, turn id as written, steps into the turn) for `scene:turn[+steps]`."""
    m = re.fullmatch(r"(.+):([^:+]+)(?:\+([\d.]+))?", str(ref))
    if not m:
        raise Refused(f"'{ref}' is not a turn", hint="write it as scene:turn, e.g. thermostat:2")
    root, path = scene(m.group(1), show)
    return root, path, m.group(2), float(m.group(3) or 0)


def of(root, path, tid=None):
    return scene_key(path, root) + (f":{tid}" if tid is not None else "")
