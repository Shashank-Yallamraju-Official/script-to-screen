"""Notes pinned to moments of the film. The writer drops a pin in the editor (M) and types a few words; the
assistant reads them here with their exact place. Notes live in the show's notes.yaml, outside the script:
they never change the film.

A note is tied to its turn (turn 9, 1.2 steps in), so it stays on the same moment when timings move. On a card,
which has no turns, it is tied to steps from the card's start.
"""
import time

import yaml

from ..performance import Scene
from ..script import load_yaml, series
from . import A, Refused, address, command

FILE = "notes.yaml"


def read(root):
    f = root / FILE
    return list((yaml.safe_load(f.read_text()) or {}).get("notes") or []) if f.exists() else []


def write(root, notes):
    (root / FILE).write_text("# Notes pinned to moments in the editor (press M). Read them with: s2s notes\n" +
                             yaml.safe_dump(dict(notes=notes), sort_keys=False, allow_unicode=True, width=200))


def put(root, part, step, text, turn=None, into=None, nid=None):
    """Add a note, change its words, or (with no words) take it away. -> every note."""
    notes, text = read(root), str(text or "").strip()
    old = next((n for n in notes if n["id"] == nid), None)
    if old is not None and not text:
        notes.remove(old)
    elif old is not None:
        old["text"] = text
    elif text:
        notes.append(dict(id=max([n["id"] for n in notes], default=0) + 1, part=str(part), turn=turn, into=None if into is None else round(float(into), 2),
                          step=round(float(step), 2), text=text, at=time.strftime("%Y-%m-%d %H:%M"), done=False))
    write(root, notes)
    return notes


def placed(notes, part, turns=()):
    """The notes on one part, each with where it is now, in steps from the part's start."""
    starts = {str(t["id"]): t["start"] for t in turns}
    return [dict(n, now=starts[str(n["turn"])] + n["into"] if str(n.get("turn")) in starts and n.get("into") is not None else n["step"])
            for n in notes if n["part"] == str(part)]


@command("notes", "The notes the writer pinned in the editor, each with its exact place. --done marks notes as dealt with.",
         [A("--done", "the numbers of notes that have been dealt with", nargs="*", type=int), A("--all", "include notes already dealt with", action="store_true")],
         "s2s notes", group="read")
def notes(a):
    root = address.show_root(a.show)
    every = read(root)
    if a.done:
        missing = [n for n in a.done if n not in {x["id"] for x in every}]
        if missing:
            raise Refused(f"no note {missing[0]}", hint="s2s notes --all lists every note")
        for n in every:
            n["done"] = n["done"] or n["id"] in a.done
        write(root, every)
    show = load_yaml(root / "show.yaml")
    sec = 60.0 / float(show["tempo"]) / show["steps_per_beat"]
    bar = show["steps_per_beat"] * int(show.get("beats_per_bar") or 0)
    scenes, out = series(root).by_id, []
    for part in dict.fromkeys(n["part"] for n in every):
        turns = Scene(scenes[part]["path"]).score.turns if part in scenes else ()
        for n in placed(every, part, turns):
            if n["done"] and not a.all:
                continue
            where = (f"bar {n['now'] / bar:.2f}, " if bar else "") + (f"turn {n['turn']} +{n['into']:g} steps, " if n.get("turn") is not None else "") + f"{n['now'] * sec:.1f} s in"
            out.append(dict(id=n["id"], part=part, turn=n.get("turn"), step=round(n["now"], 2), bar=round(n["now"] / bar, 2) if bar else None,
                            seconds=round(n["now"] * sec, 2), text=n["text"], done=n["done"], where=where))
    lines = [f"#{n['id']}  {n['part']}  {n['where']}{'  (done)' if n['done'] else ''}\n    \"{n['text']}\"" for n in out]
    return dict(notes=out, text="\n".join(lines) or "no notes" + ("" if a.all else " waiting"))
