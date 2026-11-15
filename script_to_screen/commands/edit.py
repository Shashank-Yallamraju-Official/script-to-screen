"""Changing a script file: keep its comments, check the result, write it whole or not at all,
and remember how to put it back."""
import io
import json
import os
import time
from pathlib import Path

from ruamel.yaml import YAML

from ..readers import ledger
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


def apply(a, root, path, mutate):
    """Run `mutate(doc)` on a scene file. It returns the list of changes it made:
    [{address, field, before, after}], and may raise Refused.

    The change is checked against the whole show before it is written. A change that
    introduces an error is refused unless --force."""
    before_text = Path(path).read_text()
    doc = yaml().load(before_text)
    was = errors(ledger.build(root)[1])
    result = mutate(doc) or {}
    changes = result.pop("changes", [])
    after_text = dump(doc)
    _, problems = ledger.build(root, override={Path(path): doc})
    now = errors(problems)
    introduces = sorted(now - was)
    out = dict(changes=changes, **result, introduces=introduces, fixes=sorted(was - now),
               problems=[p for p in problems if p["scene"] == address.of(root, path)],
               dry_run=bool(a.dry_run), see=f"s2s sheet {address.of(root, path)}")
    if not changes:
        raise Refused("nothing to change: the script already says that")
    if introduces and not a.force:
        raise Refused("this change would introduce " + ("an error" if len(introduces) == 1 else f"{len(introduces)} errors"),
                      hint="fix the cause, or pass --force to apply it anyway", introduces=introduces, changes=changes)
    if not a.dry_run:
        write(path, after_text)
        n = len(entries(root)) + 1
        journal(root).parent.mkdir(exist_ok=True)
        with open(journal(root), "a") as fh:
            fh.write(json.dumps(dict(id=n, at=time.strftime("%Y-%m-%dT%H:%M:%S"), command=a.command, because=a.because,
                                     path=str(Path(path).relative_to(root)), changes=changes,
                                     before=before_text, after=after_text), ensure_ascii=False) + "\n")
        out["undo"] = n
    lines = [("would change " if a.dry_run else "changed ") + f"{c['address']} {c['field']}: {json.dumps(c['before'], ensure_ascii=False)} -> {json.dumps(c['after'], ensure_ascii=False)}" for c in changes]
    lines += ["discards hand-set " + d for d in out.get("discards", [])]
    lines += ["introduces: " + p for p in introduces] + ["fixes: " + p for p in out["fixes"]]
    lines += [f"{p['level']}: turn {p['turn']}: {p['msg']}" for p in out["problems"]]
    out["text"] = "\n".join(lines + ["look: " + out["see"]])
    return out
