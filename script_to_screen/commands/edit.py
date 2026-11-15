"""Changing a script file: keep its comments, check the result, write it whole or not at all,
and remember how to put it back."""
import io
import json
import os
import time
from pathlib import Path

from ruamel.yaml import YAML

from ..readers import ledger
from ..script import ScriptError, rehearsing, series
from . import Refused
from . import address

TURN_KEYS = ("id", "who", "say", "sing", "tone", "enter", "exit", "side", "status", "do", "feel", "react", "sfx",
             "rhythm", "melody", "stress", "pause", "hold", "relies_on", "why")


def yaml():
    y = YAML()
    y.preserve_quotes = True
    y.width = 4096
    y.indent(mapping=2, sequence=4, offset=2)
    return y


def load(path):
    return yaml().load(Path(path).read_text())


def dump(doc):
    buf = io.StringIO()
    yaml().dump(doc, buf)
    return buf.getvalue()


def plain(v):
    """ruamel's commented containers -> ordinary data, for reporting."""
    if isinstance(v, dict):
        return {str(k): plain(x) for k, x in v.items()}
    if isinstance(v, (list, tuple)):
        return [plain(x) for x in v]
    if isinstance(v, (int, float, bool)) or v is None:
        return v
    return str(v)


def find_turn(doc, tid):
    """-> (position, the turn) for a turn's id (or its number when it has no id)."""
    turns = doc.get("turns") or []
    ids = [str(t.get("id", i + 1)) for i, t in enumerate(turns)]
    if str(tid) not in ids:
        raise Refused(f"no turn '{tid}' in this scene", hint="its turns are: " + ", ".join(ids))
    i = ids.index(str(tid))
    return i, turns[i]


def put(turn, key, value):
    """Set a key on a turn, placing a new key above `why` so the reason stays last."""
    if key in turn or "why" not in turn:
        turn[key] = value
    else:
        turn.insert(list(turn.keys()).index("why"), key, value)


def errors(problems):
    return {f"{p['scene']}" + (f":{p['turn']}" if p.get("turn") is not None else "") + f": {p['msg']}"
            for p in problems if p["level"] == "error"}


def journal(root):
    return Path(root) / ".s2s" / "journal.jsonl"


def entries(root):
    j = journal(root)
    return [json.loads(line) for line in j.read_text().splitlines() if line.strip()] if j.exists() else []


def write(path, text):
    tmp = Path(str(path) + ".part")
    tmp.write_text(text)
    os.replace(tmp, path)


def apply(a, root, path, mutate, series_file=False):
    """Run `mutate(doc)` on a scene file (or on series.yaml). It returns a dict with the list
    of changes it made, [{address, field, before, after}], and may raise Refused.

    The change is checked against the whole show before it is written. A change that
    introduces an error is refused unless --force. A locked scene refuses every change."""
    if not series_file:
        seg = series(root).of(path)
        if seg["status"] == "locked":
            raise Refused(f"{seg['id']} is locked", hint=f"unlock it first: s2s set-status {seg['id']} tuned")
    before_text = Path(path).read_text()
    doc = yaml().load(before_text)
    was = errors(ledger.build(root)[1])
    result = mutate(doc) or {}
    changes = result.pop("changes", [])
    after_text = dump(doc)
    if series_file:
        try:
            with rehearsing(root, plain(doc)):
                _, problems = ledger.build(root)
        except ScriptError as e:
            raise Refused(str(e))
        mine, see = problems, "s2s list"
    else:
        _, problems = ledger.build(root, override={Path(path): doc})
        mine, see = [p for p in problems if p["scene"] == address.of(root, path)], f"s2s sheet {address.of(root, path)}"
    now = errors(problems)
    introduces = sorted(now - was)
    out = dict(changes=changes, **result, introduces=introduces, fixes=sorted(was - now), problems=mine,
               dry_run=bool(a.dry_run), see=see)
    if not changes:
        raise Refused("nothing to change: the show already says that")
    if introduces and not a.force:
        raise Refused("this change would introduce " + ("an error" if len(introduces) == 1 else f"{len(introduces)} errors"),
                      hint="fix the cause, or pass --force to apply it anyway", introduces=introduces, changes=changes)
    if not a.dry_run:
        write(path, after_text)
        out["undo"] = record(root, a.command, a.because, path, changes, before_text, after_text)
    lines = [("would change " if a.dry_run else "changed ") + f"{c['address']} {c['field']}: {json.dumps(c['before'], ensure_ascii=False)} -> {json.dumps(c['after'], ensure_ascii=False)}" for c in changes]
    lines += ["discards hand-set " + d for d in out.get("discards", [])]
    lines += ["introduces: " + p for p in introduces] + ["fixes: " + p for p in out["fixes"]]
    lines += [f"{p['level']}: {p['scene']}" + (f":{p['turn']}" if p.get("turn") is not None else "") + f": {p['msg']}" for p in mine]
    out["text"] = "\n".join(lines + ["look: " + see])
    return out


def record(root, command, because, path, changes, before_text, after_text, by="command"):
    """Append a change to the journal. -> its number. `by` is who made it: a command, or a hand in the editor."""
    n = len(entries(root)) + 1
    journal(root).parent.mkdir(exist_ok=True)
    with open(journal(root), "a") as fh:
        fh.write(json.dumps(dict(id=n, at=time.strftime("%Y-%m-%dT%H:%M:%S"), by=by, command=command, because=because,
                                 path=str(Path(path).relative_to(root)), changes=changes,
                                 before=before_text, after=after_text), ensure_ascii=False) + "\n")
    return n


def stacks(root, by=None):
    """-> (done, undone): changes that stand, oldest first, and changes taken back, most recent last.
    With `by`, only that maker's changes."""
    done, undone, byid = [], [], {}
    for e in entries(root):
        if "undoes" in e:
            x = byid[e["undoes"]]
            done.remove(x)
            undone.append(x)
        elif "redoes" in e:
            x = byid[e["redoes"]]
            undone.remove(x)
            done.append(x)
        else:
            byid[e["id"]] = e
            done.append(e)
            undone = [u for u in undone if u.get("by", "command") != e.get("by", "command")]   # a new change ends that maker's redo
    pick = lambda xs: [x for x in xs if by is None or x.get("by", "command") == by]
    return pick(done), pick(undone)


def _mark(root, key, n):
    with open(journal(root), "a") as fh:
        fh.write(json.dumps({"id": len(entries(root)) + 1, key: n}) + "\n")


def undo(root, by=None):
    """Put back the last change that stands. Refuses if its file has changed since, because that would lose work."""
    done, _ = stacks(root, by)
    if not done:
        raise Refused("nothing to undo")
    e = done[-1]
    path = Path(root) / e["path"]
    if path.read_text() != e["after"]:
        raise Refused(f"{e['path']} has changed since change {e['id']}, so undoing it would lose that work",
                      hint="undo by hand, or make the opposite change")
    write(path, e["before"])
    _mark(root, "undoes", e["id"])
    return e


def redo(root, by=None):
    """Make again the change most recently taken back."""
    _, undone = stacks(root, by)
    if not undone:
        raise Refused("nothing to redo")
    e = undone[-1]
    path = Path(root) / e["path"]
    if path.read_text() != e["before"]:
        raise Refused(f"{e['path']} has changed since change {e['id']} was undone, so redoing it would lose that work")
    write(path, e["after"])
    _mark(root, "redoes", e["id"])
    return e
