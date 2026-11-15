"""Parity: has a scene changed? Records digests of a scene's score, picture and sound, and
compares against them later. Used as the gate on every restructuring phase: the reference
scene must come out identical unless the phase meant to change it.

    toon parity record <scene>      write <show>/reference/<scene name>.json
    toon parity check  <scene>      compare; exit 1 on any difference

The score digest is exact on any machine. Picture and sound digests depend on the fonts and
maths library installed, so they are only meaningful on the machine that recorded them.
"""
import hashlib
import json
import sys
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


def main():
    if len(sys.argv) != 3 or sys.argv[1] not in ("record", "check"):
        sys.exit(__doc__)
    path = Path(sys.argv[2])
    now, ref = digests(path), ref_path(path)
    if sys.argv[1] == "record":
        ref.parent.mkdir(exist_ok=True)
        ref.write_text(json.dumps(now, indent=2) + "\n")
        print(json.dumps(now))
        return
    was = json.loads(ref.read_text())
    diff = {k: dict(was=was[k], now=now[k]) for k in now if was.get(k) != now[k]}
    print(json.dumps(dict(ok=not diff, scene=now["scene"], changed=diff)))
    sys.exit(1 if diff else 0)
