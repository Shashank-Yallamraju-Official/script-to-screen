"""Commands that change a scene's script. Each is checked against the whole show before it is
written, can be rehearsed with --dry-run, and can be undone."""
import json
import re

from ruamel.yaml.comments import CommentedMap, CommentedSeq

from ..performance import speech
from ..vocabulary import PARAMS, params
from . import A, Refused, address, command, edit

TURN = A("turn", "scene:turn, e.g. thermostat:2")


def on_turn(a, fn):
    root, path, tid, _ = address.turn(a.turn, a.show)

    def mutate(doc):
        i, t = edit.find_turn(doc, tid)
        return fn(doc, i, t, address.of(root, path, t.get("id", i + 1)))
    return edit.apply(a, root, path, mutate)


def one(addr, field, before, after):
    return [] if edit.plain(before) == edit.plain(after) else [dict(address=addr, field=field, before=edit.plain(before), after=edit.plain(after))]


def parse(text):
    """A value given on the command line, read as YAML: 3, 2.5, down, {shame: 2, at: juno}."""
    return edit.yaml().load(str(text))


@command("set-line", "Change what is said in a turn. Hand-set rhythm, melody and stress that no longer fit are dropped, and reported.",
         [TURN, A("text", "the new line; use ' | ' between parts to choose the bubble breaks"), A("--who", "change the speaker too"),
          A("--sing", "the line is sung", action="store_true")],
         's2s set-line thermostat:3 "Not me. Ask Bix." --because "he should deflect"', changes=True, group="change")
def set_line(a):
    def fn(doc, i, t, addr):
        parts = [p.strip() for p in a.text.split(" | ")]
        new = parts[0] if len(parts) == 1 else CommentedSeq(parts)
        if len(parts) > 1:
            new.fa.set_flow_style()
        key = "sing" if a.sing or ("sing" in t and "say" not in t) else "say"
        old = t.get("say", t.get("sing"))
        ch = one(addr, "line", old, new)
        other = "say" if key == "sing" else "sing"
        if other in t:
            del t[other]
        edit.put(t, key, new)
        if a.who:
            ch += one(addr, "who", t.get("who"), a.who)
            edit.put(t, "who", a.who)
        if not t.get("who"):
            raise Refused("a line needs a speaker", hint="add --who <entity>")
        n, discards = len(speech.syllables(" ".join(parts))), []
        for k in ("rhythm", "melody", "stress"):
            if k in t and len(t[k]) != n:
                discards.append(f"{k} ({len(t[k])} values, tuned for the old wording; the new line has {n} syllables)")
                del t[k]
        return dict(changes=ch, discards=discards)
    return on_turn(a, fn)


@command("set-feeling", "Set what an entity feels from a turn on. For a listener, the feeling lands as the line ends.",
         [TURN, A("entity", "who feels it"), A("emotion", "an emotion from the show's list, or calm"),
          A("intensity", "1 to 3", nargs="?", type=int, default=1), A("--about", "who the feeling is about (default: the speaker)")],
         "s2s set-feeling thermostat:2 otis shame 3", changes=True, group="change")
def set_feeling(a):
    def fn(doc, i, t, addr):
        feel = t.get("feel")
        if feel is None:
            feel = CommentedMap()
            feel.fa.set_flow_style()
            edit.put(t, "feel", feel)
        if a.emotion == "calm":
            new = "calm"
        else:
            if not 1 <= a.intensity <= 3:
                raise Refused("intensity is 1, 2 or 3")
            new = CommentedMap([(a.emotion, a.intensity)] + ([("at", a.about)] if a.about else []))
            new.fa.set_flow_style()
        ch = one(addr, f"feel.{a.entity}", feel.get(a.entity), new)
        feel[a.entity] = new
        return dict(changes=ch)
    return on_turn(a, fn)


@command("set-timing", "Set a turn's pause (before the line) or hold (after it), in steps.",
         [TURN, A("which", "pause or hold", choices=[p.name for p in params.group("turn")]), A("steps", "steps of the tempo grid; fractions allowed", type=float)],
         "s2s set-timing vase:3 hold 14", changes=True, group="change")
def set_timing(a):
    def fn(doc, i, t, addr):
        p = PARAMS["turn." + a.which]
        if not p.lo <= a.steps <= p.hi:
            raise Refused(f"{a.which} is {p.lo:g} to {p.hi:g} {p.unit}")
        v = int(a.steps) if a.steps == int(a.steps) else a.steps
        ch = one(addr, a.which, t.get(a.which), v)
        edit.put(t, a.which, v)
        return dict(changes=ch)
    return on_turn(a, fn)


@command("set-why", "Change the reason a turn happens.", [TURN, A("text", "the reason")],
         's2s set-why thermostat:5 "Nobody answers her."', changes=True, group="change")
def set_why(a):
    def fn(doc, i, t, addr):
        if not a.text.strip():
            raise Refused("every turn must say why it happens")
        ch = one(addr, "why", t.get("why"), a.text)
        t["why"] = a.text
        return dict(changes=ch)
    return on_turn(a, fn)


@command("retime", "Move several of a scene's beats at once: each turn to the bar it should land on (and `bars=N` for the scene's length). Checked together, so beats can swap places.",
         [A("scene", "the scene"), A("beats", "turn=bar pairs, e.g. 8=24 9=27.68, and optionally bars=32", nargs="+")],
         "s2s retime the-council 8=24 9=27.68", changes=True, group="change")
def retime(a):
    root, path = address.scene(a.scene, a.show)

    def mutate(doc):
        ch = []
        for pair in a.beats:
            k, _, v = pair.partition("=")
            try:
                v = float(v)
            except ValueError:
                raise Refused(f"'{pair}' is not turn=bar", hint="for example 8=24, or bars=32 for the scene's length")
            v = int(v) if v == int(v) else round(v, 3)
            if k == "bars":
                ch += one(address.of(root, path), "bars", doc.get("bars"), v)
                doc["bars"] = v
                continue
            i, t = edit.find_turn(doc, int(k) if k.isdigit() else k)
            ch += one(address.of(root, path, t.get("id", i + 1)), "bar", t.get("bar"), v)
            edit.put(t, "bar", v)
        return dict(changes=ch)
    return edit.apply(a, root, path, mutate)


@command("put", "Set any one field of a turn to a value written as YAML. For what the named commands do not cover.",
         [TURN, A("field", "one of: " + ", ".join(k for k in edit.TURN_KEYS if k != "id")), A("value", "the value, as YAML; `null` removes the field")],
         "s2s put thermostat:2 do '{juno: {orient: otis}}'", changes=True, group="change")
def put(a):
    def fn(doc, i, t, addr):
        if a.field not in edit.TURN_KEYS or a.field == "id":
            raise Refused(f"a turn has no field '{a.field}'", hint="fields: " + ", ".join(k for k in edit.TURN_KEYS if k != "id"))
        v = parse(a.value)
        ch = one(addr, a.field, t.get(a.field), v)
        if v is None:
            t.pop(a.field, None)
        else:
            if isinstance(v, (CommentedMap, CommentedSeq)):
                v.fa.set_flow_style()
            edit.put(t, a.field, v)
        return dict(changes=ch)
    return on_turn(a, fn)


@command("add-reaction", "Add a reaction to a turn's line: in passing (on a word), or featured (with --beat, the scene waits).",
         [TURN, A("who", "who reacts"), A("--word", "fire on this word of the line"), A("--syllable", "or on this syllable number", type=int),
          A("--feel", "what they now feel, as YAML: '{shame: 2}' or calm"), A("--do", "a deliberate action, as YAML: '{attention: viewer}'"),
          A("--beat", "featured: hold the scene this many steps", type=float), A("--keep", "the action persists after the moment", action="store_true")],
         "s2s add-reaction dumpling:2 otis --word dumpling --feel '{shame: 2}'", changes=True, group="change")
def add_reaction(a):
    def fn(doc, i, t, addr):
        if not (a.feel or a.do):
            raise Refused("a reaction needs --feel or --do")
        if a.word:
            words = [re.sub(r"[^a-z']", "", w.lower()) for w in str(t.get("say") or t.get("sing") or "").replace("·", "").split()] \
                if not isinstance(t.get("say"), list) else [re.sub(r"[^a-z']", "", w.lower()) for part in t["say"] for w in str(part).split()]
            if re.sub(r"[^a-z']", "", a.word.lower()) not in words:
                raise Refused(f"no word '{a.word}' in this line", hint="its words are: " + ", ".join(w for w in words if w))
        r = CommentedMap([("who", a.who)])
        for k, v in (("word", a.word), ("syllable", a.syllable), ("feel", parse(a.feel) if a.feel else None),
                     ("do", parse(a.do) if a.do else None), ("beat", None if a.beat is None else (int(a.beat) if a.beat == int(a.beat) else a.beat)),
                     ("keep", True if a.keep else None)):
            if v is not None:
                r[k] = v
        r.fa.set_flow_style()
        rs = t.get("react")
        if rs is None:
            rs = CommentedSeq()
            edit.put(t, "react", rs)
        rs.append(r)
        return dict(changes=[dict(address=addr, field=f"react[{len(rs)}]", before=None, after=edit.plain(r))])
    return on_turn(a, fn)


@command("add-turn", "Add a turn to a scene. It needs a reason.",
         [A("scene", "the scene"), A("--after", "put it after this turn (default: at the end)"), A("--why", "why this turn happens", required=True),
          A("--who", "the speaker"), A("--say", "the line")],
         's2s add-turn thermostat --who bix --say "It was me." --why "Bix cannot stand the silence."', changes=True, group="change")
def add_turn(a):
    root, path = address.scene(a.scene, a.show)

    def mutate(doc):
        turns = doc["turns"]
        nums = [int(t["id"]) for t in turns if str(t.get("id", "")).isdigit()]
        tid = max(nums + [len(turns)]) + 1
        t = CommentedMap([("id", tid)] + ([("who", a.who)] if a.who else []) + ([("say", a.say)] if a.say else []) + [("why", a.why)])
        if a.say and not a.who:
            raise Refused("a line needs a speaker", hint="add --who <entity>")
        at = len(turns) if a.after is None else edit.find_turn(doc, a.after)[0] + 1
        turns.insert(at, t)
        return dict(changes=[dict(address=address.of(root, path, tid), field="turn", before=None, after=edit.plain(t))], turn=tid)
    return edit.apply(a, root, path, mutate)


@command("remove-turn", "Remove a turn from a scene.", [TURN], "s2s remove-turn thermostat:5", changes=True, group="change")
def remove_turn(a):
    def fn(doc, i, t, addr):
        before = edit.plain(t)
        del doc["turns"][i]
        return dict(changes=[dict(address=addr, field="turn", before=before, after=None)])
    return on_turn(a, fn)


@command("history", "The changes made, newest last: by command or by hand in the editor, with the words that caused each.",
         [A("--by", "only changes made this way", choices=["command", "hand"])], "s2s history --by hand", group="history")
def history(a):
    root = address.show_root(a.show)
    done, undone = edit.stacks(root, a.by)
    gone = {e["id"] for e in undone}
    rows = [dict(id=e["id"], at=e["at"], by=e.get("by", "command"), command=e["command"], because=e.get("because"), path=e["path"],
                 changes=e.get("changes", []), undone=e["id"] in gone) for e in sorted(done + undone, key=lambda e: e["id"])]
    text = [f"{r['id']:>3} {r['at']} {r['by']:7} {r['command']:12} " + "; ".join(f"{c['address']} {c['field']} {json.dumps(c['before'])} -> {json.dumps(c['after'])}" for c in r["changes"]) +
            (f"   \"{r['because']}\"" if r["because"] else "") + ("   (undone)" if r["undone"] else "") for r in rows]
    return dict(history=rows, text="\n".join(text or ["no changes yet"]))


@command("undo", "Put back the last change, whoever made it. Refuses if the file has been changed since.", [], "s2s undo", group="history")
def undo(a):
    e = edit.undo(address.show_root(a.show))
    return dict(undone=e["id"], undid=e["command"], by=e.get("by", "command"), changes=e.get("changes", []),
                text=f"undid change {e['id']} ({e['command']}, by {e.get('by', 'command')})")


@command("redo", "Make again the change most recently undone.", [], "s2s redo", group="history")
def redo(a):
    e = edit.redo(address.show_root(a.show))
    return dict(redone=e["id"], redid=e["command"], changes=e.get("changes", []), text=f"redid change {e['id']} ({e['command']})")
