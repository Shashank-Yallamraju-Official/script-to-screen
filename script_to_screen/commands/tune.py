"""Tuning by hand, as commands. The editor and the command line both change hand-set values
through the functions here, so there is one way a `tune:` block is ever written.

Addresses (the narrowest scope a value can be set at comes first):

    the-thermostat:2.hold            a turn's pause or hold
    the-thermostat:2.s3.length       syllable 3 of that turn's line: length, breath, pitch or stress
    the-thermostat:2.r1.beat         that turn's first reaction: how long it holds the scene
    the-thermostat.hold              every turn in a scene
    show.hold                        every turn in the show (also show.settle, show.bubble_break)
    show.breath.stop                 the breath after every full stop in the show (also .comma, .ellipsis)
    @otis.reflex                     an entity
    ~angry.rate                      a tone of voice
    feel.overshoot                   motion, the indicator and the voice
    sounds.thud.vol                  one sound
"""
import re
from pathlib import Path

from ruamel.yaml.comments import CommentedMap
from ruamel.yaml.scalarstring import DoubleQuotedScalarString

from ..performance import Scene
from ..script import Show, load_yaml, scene_paths, series, tuning
from ..vocabulary import PARAMS
from . import A, Refused, address, command, edit

played = None        # the editor sets this to hand over a scene it has already worked out: path -> score, or None


def scene_of(path):
    """A scene as it plays (its turns and syllables). Worked out afresh unless someone already has it."""
    return (played and played(Path(path))) or Scene(path)


TONE_DEFAULT = dict(rate=2, stretch=1, range=2, pitch=1, vol=0.5)
ENTITY_DEFAULT = dict(reflex=0)


# ---- writing a tune block (these work on a loaded document; nothing here touches a file) -----------
def tidy(v):
    v = round(float(v), 3)
    return int(v) if v == int(v) else v


def _flow(m):
    m.fa.set_flow_style()
    return m


def _key(n):
    """A syllable or reaction is keyed by its number; a kind of pause by its name."""
    return int(n) if str(n).isdigit() else str(n)


def put(holder, name, value, n=None):
    """Set a hand-set value on whatever owns the block: a turn, a scene, a sheet, a tone, a sound, the show."""
    block = holder.get("tune")
    if block is None:
        block = _flow(CommentedMap())
        if "why" in holder:                              # on a turn, the reason stays last
            holder.insert(list(holder.keys()).index("why"), "tune", block)
        else:
            holder["tune"] = block
    if n is None:
        block[name] = tidy(value)
    else:
        if block.get(name) is None:
            block[name] = _flow(CommentedMap())
        block[name][_key(n)] = tidy(value)
        items = sorted(block[name].items(), key=lambda kv: str(kv[0]).zfill(6))     # keep syllables in order
        block[name].clear()
        block[name].update(items)


def drop(holder, name, n=None):
    """Take a hand-set value off. -> whether there was one. An emptied block is removed."""
    block = holder.get("tune")
    if not block or name not in block or (n is not None and _key(n) not in (block[name] or {})):
        return False
    if n is None:
        del block[name]
    else:
        del block[name][_key(n)]
        if not block[name]:
            del block[name]
    if not any(k in block for k in tuning.SYLLABLE):
        block.pop("for", None)
    if not block:
        del holder["tune"]
    return True


def anchor(turn):
    """Tie a turn's per-syllable tunes to its present words. -> tunes for an earlier wording, now discarded."""
    block, text = turn.get("tune"), tuning.line_text(turn.get("say") or turn.get("sing") or "")
    gone = []
    if block is not None and block.get("for") not in (None, text):
        for k in tuning.SYLLABLE:
            for n, v in (block.pop(k, None) or {}).items():
                gone.append(f"{k} of syllable {n} ({v}), tuned for \"{block['for']}\"")
    if block is None:
        block = _flow(CommentedMap())
        turn.insert(list(turn.keys()).index("why") if "why" in turn else len(turn), "tune", block)
    if block.get("for") != text:
        block.pop("for", None)
        block.insert(0, "for", DoubleQuotedScalarString(text))     # quoted: a line may hold commas, colons or question marks
    return gone


# ---- addresses ---------------------------------------------------------------------------------------
class Target:
    """One value at one scope: which file holds it, and where in that file."""

    def __init__(self, root, param, scope, file, **where):
        self.root, self.param, self.scope, self.file, self.where = root, PARAMS[param], scope, Path(file), where

    @property
    def name(self):
        return self.param.name

    @property
    def n(self):
        return self.where.get("n", self.where.get("mark"))

    @property
    def address(self):
        w = self.where
        return {"turn": lambda: f"{w['scene']}:{w['turn']}.{self.name}", "syllable": lambda: f"{w['scene']}:{w['turn']}.s{w['n']}.{self.name}",
                "reaction": lambda: f"{w['scene']}:{w['turn']}.r{w['n']}.{self.name}", "sfx": lambda: f"{w['scene']}:{w['turn']}.x{w['n']}.{self.name}", "scene": lambda: f"{w['scene']}.{self.name}",
                "show": lambda: f"show.{self.name}" + (f".{w['mark']}" if "mark" in w else ""), "feel": lambda: f"feel.{self.name}", "sound": lambda: f"sounds.{w['sound']}.{self.name}",
                "tone": lambda: f"~{w['tone']}.{self.name}", "entity": lambda: f"@{w['entity']}.{self.name}"}[self.scope]()

    def holder(self, doc):
        """The mapping in `doc` that owns this value's tune block."""
        w = self.where
        if self.scope in ("turn", "syllable", "reaction", "sfx"):
            return edit.find_turn(doc, w["turn"])[1]
        if self.scope == "sound":
            return doc[w["sound"]]
        if self.scope == "tone":
            return doc[w["tone"]]
        return doc

    def at(self, scope):
        """The same value one or more scopes out."""
        if scope == self.scope:
            return self
        if scope == "scene":
            return Target(self.root, self.param.key, "scene", self.file, scene=self.where["scene"])
        if scope == "show" and self.name == "breath":
            syl = scene_of(self.file).turns[edit.find_turn(load_yaml(self.file), self.where["turn"])[0]]["sylls"][self.where["n"] - 1]
            if not syl["mark"]:
                raise Refused("this breath was put in by hand; no punctuation follows the syllable, so there is nothing to generalise from")
            return Target(self.root, self.param.key, "show", self.root / "show.yaml", mark=syl["mark"])
        if scope == "show":
            return Target(self.root, self.param.key, "show", self.root / "show.yaml")
        raise Refused(f"{self.param.label.lower()} cannot be set for a whole {scope}", hint="it can be set for: " + ", ".join(self.param.scopes))


def _names(kind, have, want):
    if want not in have:
        raise Refused(f"no {kind} '{want}'", hint=f"{kind}s: " + ", ".join(sorted(map(str, have))))


def _param(scope, name, allowed_from=None):
    for p in PARAMS.values():
        if p.name == name and (scope in p.scopes or p.scope == scope):
            return p.key
    names = sorted({p.name for p in PARAMS.values() if scope in p.scopes or p.scope == scope})
    raise Refused(f"'{name}' cannot be tuned for a {scope}", hint=f"a {scope} has: " + ", ".join(names))


def parse(ref, show=None):
    """An address -> the Target it names."""
    ref = str(ref)
    root = address.show_root(show)
    lib = root / "library"
    if ref.startswith("@"):
        ent, _, name = ref[1:].partition(".")
        _names("entity", Show(root).known(), ent)
        return Target(root, _param("entity", name), "entity", root / "entities" / f"{ent}.yaml", entity=ent)
    if ref.startswith("~"):
        tone, _, name = ref[1:].partition(".")
        _names("tone", load_yaml(lib / "tones.yaml"), tone)
        return Target(root, _param("tone", name), "tone", lib / "tones.yaml", tone=tone)
    if ref.startswith("feel."):
        return Target(root, _param("feel", ref[5:]), "feel", lib / "feel.yaml")
    if ref.startswith("sounds."):
        _, snd, name = (ref.split(".", 2) + [""])[:3]
        _names("sound", load_yaml(lib / "sounds.yaml"), snd)
        return Target(root, _param("sound", name), "sound", lib / "sounds.yaml", sound=snd)
    if ref.startswith("show.breath"):
        mark = ref[12:]
        _names("kind of pause", tuning.BREATH, mark)
        return Target(root, "syllable.breath", "show", root / "show.yaml", mark=mark)
    if ref.startswith("show."):
        return Target(root, _param("show", ref[5:]), "show", root / "show.yaml")
    m = re.fullmatch(r"(.+):([^:.]+)\.(?:([srx])(\d+)\.)?([a-z_]+)", ref)
    if m:
        _, path = address.scene(m.group(1), show)
        sid, kind, name = address.of(root, path), m.group(3), m.group(5)
        doc = load_yaml(path)
        i, turn = edit.find_turn(doc, m.group(2))
        tid = turn.get("id", i + 1)
        if kind == "s":
            sc = Scene(path)
            count = len(sc.turns[i]["sylls"])
            if not 1 <= int(m.group(4)) <= count:
                raise Refused(f"turn {tid} has no syllable {m.group(4)}", hint=(f"its line has {count}: " + " | ".join(
                    f"{k + 1} {s['text'].strip()}" for k, s in enumerate(sc.turns[i]["sylls"]))) if count else "this turn has no line")
            return Target(root, _param("syllable", name), "syllable", path, scene=sid, turn=tid, n=int(m.group(4)))
        if kind == "x":
            placed = turn.get("sfx") or []
            if not 1 <= int(m.group(4)) <= len(placed):
                raise Refused(f"turn {tid} has no placed sound {m.group(4)}", hint=f"it has {len(placed)}" if placed else "this turn places no sound (`sfx:`)")
            return Target(root, _param("sfx", name), "sfx", path, scene=sid, turn=tid, n=int(m.group(4)))
        if kind == "r":
            reacts = turn.get("react") or []
            if not 1 <= int(m.group(4)) <= len(reacts) or "beat" not in reacts[int(m.group(4)) - 1]:
                raise Refused(f"turn {tid} has no featured reaction {m.group(4)}", hint="only a reaction with a `beat` holds the scene")
            return Target(root, _param("reaction", name), "reaction", path, scene=sid, turn=tid, n=int(m.group(4)))
        return Target(root, _param("turn", name), "turn", path, scene=sid, turn=tid)
    if "." in ref:
        scene_ref, _, name = ref.rpartition(".")
        _, path = address.scene(scene_ref, show)
        key = _param("scene", name)
        return Target(root, key, "scene", path, scene=address.of(root, path))
    raise Refused(f"'{ref}' is not something that can be tuned", hint="see `s2s tune --help` for how addresses are written")


# ---- what a value is, and where it comes from ----------------------------------------------------------
def chain(t, doc=None):
    """Every scope's say on a value, narrowest first: [{scope, by, value}]. The first with a value is the one in force."""
    name, w, out = t.name, t.where, []
    doc = doc if doc is not None else load_yaml(t.file)

    def add(scope, by, value):
        if value is not None:
            out.append(dict(scope=scope, by=by, value=value))

    if t.scope in ("turn", "scene", "show") and name in ("pause", "hold"):
        if t.scope == "turn":
            turn = edit.find_turn(doc, w["turn"])[1]
            add("turn", "hand", (turn.get("tune") or {}).get(name))
            add("turn", "written", turn.get(name))
        if t.scope in ("turn", "scene"):
            add("scene", "hand", (doc.get("tune") or {}).get(name))
        cfg = doc if t.scope == "show" else load_yaml(t.root / "show.yaml")
        add("show", "hand", (cfg.get("tune") or {}).get(name))
        add("show", "written", cfg["timing"][name])
    elif name == "breath":
        cfg, mark = (doc if t.scope == "show" else load_yaml(t.root / "show.yaml")), w.get("mark")
        if t.scope == "syllable":
            i, turn = edit.find_turn(doc, w["turn"])
            tunes, _ = tuning.syllable_tunes(turn)
            add("syllable", "hand", (tunes.get("breath") or {}).get(w["n"]))
            syl = scene_of(t.file).turns[i]["sylls"][w["n"] - 1]
            mark = syl["mark"]
            if not mark or syl["base"]["breath"] != (cfg["timing"].get("breath") or {}).get(mark, tuning.BREATH[mark]):
                add("syllable", "worked out", syl["base"]["breath"])     # no punctuation, or a break chosen in the script
                mark = None
        if mark:
            add("show", "hand", ((cfg.get("tune") or {}).get("breath") or {}).get(mark))
            written = (cfg["timing"].get("breath") or {}).get(mark)
            add("show", "written" if written is not None else "default", written if written is not None else tuning.BREATH[mark])
    elif t.scope == "show":
        add("show", "hand", (doc.get("tune") or {}).get(name))
        add("show", "written", doc["timing"].get(name))
    elif t.scope == "syllable":
        i, turn = edit.find_turn(doc, w["turn"])
        tunes, _ = tuning.syllable_tunes(turn)
        add("syllable", "hand", (tunes.get(name) or {}).get(w["n"]))
        base = scene_of(t.file).turns[i]["sylls"][w["n"] - 1]["base"][name]
        written = turn.get({"length": "rhythm", "pitch": "melody", "stress": "stress"}[name])
        add("syllable", "written" if written is not None else "worked out", base)
    elif t.scope == "sfx":
        turn = edit.find_turn(doc, w["turn"])[1]
        item = turn["sfx"][w["n"] - 1]
        add("sfx", "hand", ((turn.get("tune") or {}).get("sfx_" + name) or {}).get(w["n"]))
        default = {"at": 0, "vol": 1, "len": tuning.SFX_LEN.get(str(item["sound"]))}[name]
        add("sfx", "written" if item.get(name) is not None else "default", item.get(name, default))
    elif t.scope == "reaction":
        turn = edit.find_turn(doc, w["turn"])[1]
        add("reaction", "hand", ((turn.get("tune") or {}).get("beat") or {}).get(w["n"]))
        add("reaction", "written", turn["react"][w["n"] - 1]["beat"])
    else:
        holder = t.holder(doc)
        add(t.scope, "hand", (holder.get("tune") or {}).get(name))
        default = {"tone": TONE_DEFAULT, "entity": ENTITY_DEFAULT}.get(t.scope, {}).get(name)
        if t.scope == "sound" and name == "to":
            default = holder.get("freq")
        add(t.scope, "written" if holder.get(name) is not None else "default", holder.get(name, default))
    return out


def resolve(t, doc=None):
    c = chain(t, doc)
    if not c:
        raise Refused(f"{t.address} has no value")
    return dict(c[0], chain=c)


def inherited(t, doc=None):
    """What the value would be without the hand-set one at this target's own scope."""
    rest = [x for x in chain(t, doc) if not (x["scope"] == t.scope and x["by"] == "hand")]
    return rest[0]["value"] if rest else None


def set_in(doc, t, value):
    """Set a hand-set value in a loaded document. -> hand-set values this discards (tunes for an earlier wording)."""
    gone = anchor(t.holder(doc)) if t.scope == "syllable" else []
    put(t.holder(doc), _block(t), value, t.n)
    return gone


def _block(t):
    """The name a value is kept under in a `tune:` block: a placed sound's are marked as such."""
    return "sfx_" + t.name if t.scope == "sfx" else t.name


def reset_in(doc, t):
    return drop(t.holder(doc), _block(t), t.n)


def locked(t):
    if t.scope in ("turn", "syllable", "reaction", "sfx", "scene"):
        seg = series(t.root).by_id[t.where["scene"]]
        if seg["status"] == "locked":
            raise Refused(f"{seg['id']} is locked", hint=f"unlock it first: s2s set-status {seg['id']} tuned")


def write(a, t, mutate, group=None):
    """Change one file through `mutate(doc)`, journal it, and report. `mutate` returns extra fields for the result."""
    locked(t)
    before_text = t.file.read_text()
    doc = edit.yaml().load(before_text)
    was = resolve(t, doc)
    extra = mutate(doc) or {}
    after_text = edit.dump(doc)
    now = resolve(t, doc)
    strip = lambda r: {k: r[k] for k in ("value", "scope", "by")}
    out = dict(address=t.address, param=t.param.key, scope=t.scope, before=strip(was), after=strip(now), rebuild=t.param.rebuild,
               dry_run=bool(getattr(a, "dry_run", False)), **extra)
    if after_text == before_text:
        raise Refused("nothing to change: that is already the value in force at this scope")
    if not out["dry_run"]:
        edit.write(t.file, after_text)
        out["undo"] = edit.record(t.root, "tune " + a.action, getattr(a, "because", None), t.file,
                                  [dict(address=t.address, field=t.name, before=was["value"], after=now["value"])], before_text, after_text,
                                  by=getattr(a, "by", "command"), group=group)
    out["text"] = (("would set " if out["dry_run"] else "") + f"{t.address}: {was['value']} ({was['by']}, {was['scope']}) -> "
                   f"{now['value']} ({now['by']}, {now['scope']})" + "".join(f"\n  discards hand-set {d}" for d in extra.get("discards", [])))
    return out


def number(t, raw):
    try:
        v = float(raw)
    except (TypeError, ValueError):
        raise Refused(f"'{raw}' is not a number")
    p = t.param
    if not p.lo <= v <= p.hi:
        raise Refused(f"{p.label.lower()} is {p.lo:g} to {p.hi:g} {p.unit}")
    return v


def turns_affected(t, apply):
    """How many turns' pause or hold in force would change if `apply(docs)` were done. docs: {path: document}."""
    paths = [t.file] if t.scope != "show" else scene_paths(t.root)
    if t.scope == "show" or t.at is None:
        pass
    docs = {p: edit.load(p) for p in set(paths) | ({t.file} if t.file.suffix == ".yaml" and t.file.name != "show.yaml" else set())}
    cfg = edit.load(t.root / "show.yaml")

    def values():
        timing = {**cfg["timing"], **{k: v for k, v in (cfg.get("tune") or {}).items() if k in tuning.TIMING}}
        return [tuning.turn_value(turn, d, t.name, timing[t.name]) for p, d in sorted(docs.items()) for turn in d.get("turns") or []]
    before = values()
    apply(docs, cfg)
    return sum(a != b for a, b in zip(before, values()))


@command("tune", "Set, take off, widen or list values tuned by hand. A hand-set value outranks a written one and survives rewrites.",
         [A("action", "get: what a value is and where it comes from. set / reset: put a hand-set value on, or take it off. "
                      "widen: move it out a scope (a turn's hold to its scene, then the show). list: every hand-set value",
            choices=["get", "set", "reset", "widen", "list"]),
          A("address", "what to tune, e.g. the-thermostat:2.hold, feel.overshoot, @otis.reflex (for list: a scene, or nothing)", nargs="?"),
          A("value", "the value, for set", nargs="?"), A("--to", "for widen: the scope to move to (default: the next one out)"),
          A("--orphans", "for list: only values tuned for words that have since changed", action="store_true")],
         "s2s tune set the-thermostat:2.hold 14", changes=True, group="change")
def tune(a):
    if a.action == "list":
        return listing(a)
    if not a.address:
        raise Refused("say what to tune", hint="e.g. s2s tune get the-thermostat:2.hold")
    t = parse(a.address, a.show)
    if a.action == "get":
        r = resolve(t)
        text = [f"{t.address} = {r['value']}   ({t.param.meaning} {t.param.lo:g} to {t.param.hi:g} {t.param.unit})"] + \
               [("  > " if k == 0 else "    ") + f"{c['scope']:9} {c['by']:10} {c['value']}" for k, c in enumerate(r["chain"])]
        return dict(address=t.address, param=t.param.describe(), **r, text="\n".join(text))
    if a.action == "set":
        if a.value is None:
            raise Refused("say the value", hint=f"s2s tune set {t.address} <{t.param.lo:g} to {t.param.hi:g}>")
        v = number(t, a.value)
        return write(a, t, lambda doc: dict(discards=set_in(doc, t, v)))
    if a.action == "reset":
        def mutate(doc):
            if not reset_in(doc, t):
                r = resolve(t, doc)
                raise Refused(f"nothing is set by hand at {t.address}", hint=f"it is {r['value']} ({r['by']}, {r['scope']})")
        return write(a, t, mutate)
    # widen: the value in force here moves one scope out, and comes off here
    scopes = list(t.param.scopes)
    if t.scope not in scopes or scopes.index(t.scope) == len(scopes) - 1:
        raise Refused(f"{t.address} is already as wide as it goes" if len(scopes) > 1 else f"{t.param.label.lower()} has only one scope ({t.scope})")
    to = a.to or scopes[scopes.index(t.scope) + 1]
    if to not in scopes[scopes.index(t.scope) + 1:]:
        raise Refused(f"cannot widen {t.address} to '{to}'", hint="wider scopes: " + ", ".join(scopes[scopes.index(t.scope) + 1:]))
    wide, value = t.at(to), resolve(t)["value"]

    def both(docs, cfg):
        reset_in(docs[t.file], t) if t.file in docs else None
        set_in(cfg if to == "show" else docs[wide.file], wide, value)
    if t.name == "breath":                               # every breath after that kind of pause, unless it has its own
        affects, carry = 0, {}
        for p in scene_paths(t.root):                    # each scene is worked out once, handing on to the next
            sc = Scene(p, carry=carry)
            carry = sc.carry_out
            affects += sum(1 for turn in sc.turns for k, s in enumerate(turn["sylls"], 1) if s["mark"] == wide.where["mark"] and s["rest"] != value
                           and not (p == t.file and str(turn["id"]) == str(t.where["turn"]) and k == t.n))
    else:
        affects = turns_affected(wide, both)
    group = f"widen-{len(edit.entries(t.root)) + 1}"
    out = write(a, wide, lambda doc: dict(discards=set_in(doc, wide, value)), group=group)
    try:
        write(a, t, lambda doc: reset_in(doc, t) and None, group=group)
    except Refused:
        pass                                             # nothing was set by hand at the narrow scope; it simply inherits now
    out.update(widened_from=t.address, affects=affects)
    what = "other breath(s)" if t.name == "breath" else "turn(s)"
    out["text"] = f"{t.address} -> {wide.address} = {value}; changes {affects} {what}" + (" (dry run)" if out["dry_run"] else "")
    return out


def listing(a):
    """Every hand-set value, beside what it replaced."""
    root = address.show_root(a.show)
    only = address.of(root, address.scene(a.address, a.show)[1]) if a.address else None
    rows = []

    def row(t, value, orphan=False):
        rows.append(dict(address=t.address, value=value, replaces=None if orphan else inherited(t), scope=t.scope, orphan=orphan))

    if only is None:
        for name, v in (load_yaml(root / "show.yaml").get("tune") or {}).items():
            if name == "breath":
                for mark, steps in v.items():
                    row(Target(root, "syllable.breath", "show", root / "show.yaml", mark=mark), steps)
            else:
                row(Target(root, _param("show", name), "show", root / "show.yaml"), v)
        for name, v in (load_yaml(root / "library" / "feel.yaml").get("tune") or {}).items():
            row(Target(root, "feel." + name, "feel", root / "library" / "feel.yaml"), v)
        for kind, file, scope in (("sound", "sounds.yaml", "sound"), ("tone", "tones.yaml", "tone")):
            for key, entry in load_yaml(root / "library" / file).items():
                for name, v in (entry.get("tune") or {}).items():
                    row(Target(root, f"{scope}.{name}", scope, root / "library" / file, **{kind: key}), v)
        for f in sorted((root / "entities").glob("*.yaml")):
            for name, v in (load_yaml(f).get("tune") or {}).items():
                row(Target(root, "entity." + name, "entity", f, entity=f.stem), v)
    for sg in series(root).segments:
        if only is not None and sg["id"] != only:
            continue
        doc = load_yaml(sg["path"])
        for name, v in (doc.get("tune") or {}).items():
            row(Target(root, "turn." + name, "scene", sg["path"], scene=sg["id"]), v)
        for i, turn in enumerate(doc.get("turns") or []):
            block, tid = turn.get("tune") or {}, turn.get("id", i + 1)
            for name in ("pause", "hold"):
                if name in block:
                    row(Target(root, "turn." + name, "turn", sg["path"], scene=sg["id"], turn=tid), block[name])
            _, orphaned = tuning.syllable_tunes(turn)
            for name in tuning.SYLLABLE:
                for n, v in (block.get(name) or {}).items():
                    row(Target(root, "syllable." + name, "syllable", sg["path"], scene=sg["id"], turn=tid, n=int(n)), v, orphan=bool(orphaned))
            for n, v in (block.get("beat") or {}).items():
                row(Target(root, "reaction.beat", "reaction", sg["path"], scene=sg["id"], turn=tid, n=int(n)), v)
    if a.orphans:
        rows = [r for r in rows if r["orphan"]]
    text = [f"{r['address']:38} {r['value']:<8} " + ("ORPHAN: tuned for an earlier wording, not applied" if r["orphan"] else f"(otherwise {r['replaces']})") for r in rows]
    return dict(tunes=rows, text="\n".join(text or ["nothing is tuned by hand" + (" here" if only else "")]))
