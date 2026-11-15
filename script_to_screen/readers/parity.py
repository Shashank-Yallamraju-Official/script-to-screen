"""Parity: has a scene changed? Records digests of a scene's score, picture and sound, and
compares against them later. Used as the gate on every restructuring phase: the reference
scene must come out identical unless the phase meant to change it.

    s2s parity record <scene>      write <show>/reference/<scene name>.json
    s2s parity check  <scene>      compare; exit 1 on any difference

The score digest is exact on any machine. Picture and sound digests depend on the fonts and
maths library installed, so they are only meaningful on the machine that recorded them.
"""
import hashlib
import json
from pathlib import Path

import skia

from ..performance import Scene
from ..presentation import sound
from ..presentation.draw import draw_frame
from ..script import find_root


def _plain(v):
    if isinstance(v, dict):
        return {str(k): _plain(x) for k, x in sorted(v.items(), key=lambda kv: str(kv[0]))}
    if isinstance(v, (list, tuple, set)):
        return [_plain(x) for x in (sorted(v, key=str) if isinstance(v, set) else v)]
    if isinstance(v, float):
        return round(v, 6)
    return v


def score_of(scene):
    """Everything the model decided, as plain data."""
    return _plain(dict(turns=scene.turns, keys=scene.keys, lines=scene.lines, events=scene.events,
                       focus=scene.focus, carry_out=scene.carry_out, problems=scene.problems,
                       steps=scene.steps, total=scene.total))


def digests(path):
    scene = Scene(path)
    sha = lambda b: hashlib.sha256(b).hexdigest()[:16]
    score = sha(json.dumps(score_of(scene), sort_keys=True, ensure_ascii=False).encode())   # before drawing caches anything
    surface = skia.Surface(scene.W, scene.H)
    pic = hashlib.sha256()
    for F in range(scene.total):
        draw_frame(surface.getCanvas(), scene, F)
        pic.update(surface.makeImageSnapshot().tobytes())
    return dict(scene=scene.key, frames=scene.total,
                score=score,
                picture=pic.hexdigest()[:16], sound=sha(sound.mix(scene)))


def ref_path(path):
    path = Path(path).resolve()
    return find_root(path) / "reference" / (path.stem + ".json")
