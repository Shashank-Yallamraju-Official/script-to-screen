"""Layer 1, the script: what the writer and the assistant write. Files in, plain data out.

This layer reads a show's files and knows their layout. It decides nothing about what
happens; it imports no other layer.
"""
import copy
from pathlib import Path

import yaml

from . import tuning

LIBRARY = ("tones", "sounds", "feel")
SCHEMA = 2                                  # the file format this engine reads; see docs/architecture.md


class ScriptError(Exception):
    pass


_Loader = getattr(yaml, "CSafeLoader", yaml.SafeLoader)    # the C parser where it is installed; the same result, much sooner
_read = {}                                                  # path -> (what the file was when read, its parsed content)


def load_yaml(p):
    """A file's content. A file that has not changed since it was last read is not parsed again;
    each caller gets its own copy, so nobody's changes leak into anyone else's."""
    p = Path(p)
    st = p.stat()
    key, stamp = str(p), (st.st_mtime_ns, st.st_size)
    if _read.get(key, (None,))[0] != stamp:
        with open(p) as fh:
            _read[key] = (stamp, yaml.load(fh, Loader=_Loader))
    return copy.deepcopy(_read[key][1])


def place(root, name):
    """A place's file, with `like:` resolved: a place that starts as another and changes only what differs."""
    file = Path(root) / "places" / f"{name}.yaml"
    if not file.exists():
        raise ScriptError(f"no place '{name}': there is no places/{name}.yaml")
    data = load_yaml(file) or {}
    return {**place(root, data["like"]), **data} if data.get("like") else data


def things(place_data):
    """What in a place can be named, faced and cared about: {id: {at, kind, serves}}. A piece's id is its `id:`,
    or its kind when it is the only piece of that kind."""
    pieces = (place_data or {}).get("pieces") or []
    kinds = [p["kind"] for p in pieces]
    out = {}
    for p in pieces:
        name = p.get("id") or (p["kind"] if kinds.count(p["kind"]) == 1 else None)
        if name:
            out[str(name)] = dict(at=float(p.get("at", 0)), kind=p["kind"], serves=p.get("serves"))
    return out


def find_root(path):
    path = Path(path).resolve()
    for p in [path] + list(path.parents):
        if (p / "show.yaml").exists():
            return p
    raise ScriptError("no show.yaml above " + str(path))


STATUSES = ("draft", "staged", "tuned", "locked")
CARDS = ("title", "credits")
_override = {}                              # root -> series data being rehearsed (see `rehearsing`)


class Series:
    """The series from above: seasons, episodes and their segments, in order (series.yaml).

    A segment has an identity that does not depend on where its file is or what it is called.
    A segment is a scene or a card (the title, the credits). Cards belong to their episode only:
    `segments` and `by_id` hold scenes, and an episode's own `segments` holds both, in order.
    """

    def __init__(self, root, data=None):
        self.root = Path(root)
        if data is None:
            f = self.root / "series.yaml"
            if not f.exists():
                raise ScriptError(f"no series.yaml in {self.root}: a show lists its seasons, episodes and scenes there")
            data = load_yaml(f) or {}
        self.seasons, self.segments, self.by_id, self.by_path = [], [], {}, {}
        for se in data.get("seasons") or []:
            season = dict(id=str(se["id"]), title=se.get("title"), episodes=[])
            self.seasons.append(season)
            for ep in se.get("episodes") or []:
                episode = dict(id=str(ep["id"]), title=ep.get("title"), logline=ep.get("logline"), status=ep.get("status"),
                               season=season["id"], segments=[])
                season["episodes"].append(episode)
                for sg in ep.get("segments") or []:
                    kind = next((k for k in ("scene", "card") if k in sg), None)
                    if kind is None:
                        raise ScriptError(f"series.yaml: segment '{sg.get('id')}' has no kind; write `scene: <file>` or `card: title | credits`")
                    if kind == "card":                           # a title card or the credits: made from show.yaml, with no file of its own
                        if sg["card"] not in CARDS:
                            raise ScriptError(f"series.yaml: '{sg.get('id')}' is a card of kind '{sg['card']}'; the kinds are {', '.join(CARDS)}")
                        episode["segments"].append(dict(id=str(sg["id"]), kind="card", card=str(sg["card"]), into=sg.get("into"),
                                                        season=season["id"], episode=episode["id"]))
                        continue
                    seg = dict(id=str(sg["id"]), kind=kind, path=(self.root / str(sg[kind])).resolve(), file=str(sg[kind]),
                               status=sg.get("status", "draft"), logline=sg.get("logline"), into=sg.get("into"),
                               season=season["id"], episode=episode["id"], index=len(self.segments))
                    if seg["id"] in self.by_id:
                        raise ScriptError(f"series.yaml: two segments are called '{seg['id']}'")
                    if seg["status"] not in STATUSES:
                        raise ScriptError(f"series.yaml: '{seg['id']}' has status '{seg['status']}'; it must be one of {', '.join(STATUSES)}")
                    self.segments.append(seg)
                    episode["segments"].append(seg)
                    self.by_id[seg["id"]] = self.by_path[seg["path"]] = seg

    def of(self, path):
        seg = self.by_path.get(Path(path).resolve())
        if seg is None:
            raise ScriptError(f"{Path(path).name} is not listed in series.yaml, so it has no place in the series")
        return seg

    def episode(self, eid):
        for se in self.seasons:
            for ep in se["episodes"]:
                if ep["id"] == eid:
                    return ep
        raise ScriptError(f"no episode '{eid}'; episodes are: " + ", ".join(ep["id"] for se in self.seasons for ep in se["episodes"]))


def series(root):
    root = Path(root).resolve()
    return Series(root, _override.get(root))


_imagined = {}                              # root -> {entity: sheet}: sheets being tried out (see `imagining`)


class imagining:
    """While inside, the entities of the show at `root` are read as if their sheets were `sheets`. For what-ifs."""

    def __init__(self, root, sheets):
        self.root, self.sheets = Path(root).resolve(), sheets

    def __enter__(self):
        _imagined[self.root] = self.sheets

    def __exit__(self, *exc):
        _imagined.pop(self.root, None)


class rehearsing:
    """While inside, the show at `root` is read as if series.yaml held `data`. For dry runs."""

    def __init__(self, root, data):
        self.root, self.data = Path(root).resolve(), data

    def __enter__(self):
        _override[self.root] = self.data

    def __exit__(self, *exc):
        _override.pop(self.root, None)


def scene_paths(root):
    """Every scene's file, in series order."""
    return [sg["path"] for sg in series(root).segments if sg["kind"] == "scene"]


def scene_key(path, root):
    """A scene's identity: its segment id in series.yaml."""
    return series(root).of(path)["id"]


class Show:
    """A show's settings, library and entity sheets."""

    def __init__(self, root, lib=None):
        self.root = root
        self.cfg = load_yaml(root / "show.yaml")
        if self.cfg.get("schema", 1) != SCHEMA:
            raise ScriptError(f"this show is written for schema {self.cfg.get('schema', 1)}, and this engine reads schema {SCHEMA}; run `s2s migrate`")
        hand = self.cfg.get("tune") or {}
        self.breath_written = {**tuning.BREATH, **(self.cfg["timing"].get("breath") or {})}      # steps of breath after each kind of pause
        self.breath = {**self.breath_written, **(hand.get("breath") or {})}
        self.cfg["timing"] = {**self.cfg["timing"], **{k: v for k, v in hand.items() if k in tuning.TIMING}, "breath": self.breath}
        for name in LIBRARY:                 # the editor passes its copies in `lib`, to preview a value before it is written
            raw = (lib or {}).get(name) or load_yaml(root / "library" / f"{name}.yaml")
            setattr(self, name, tuning.overlay(raw) if name == "feel" else tuning.each(raw))     # hand-set values laid over written ones
        music = root / "library" / "music.yaml"              # what each kind of cue sounds like; a show without the file gets the built-in figures
        self.music = (lib or {}).get("music") or (load_yaml(music) if music.exists() else {})
        self.emotions = self.cfg["emotions"]

    def known(self):
        """Every entity this show has a sheet for."""
        return {p.stem for p in (self.root / "entities").glob("*.yaml")}

    def entity(self, eid, key):
        """An entity's sheet as it stands at scene `key`: its arc has changed its tells up to here."""
        p = self.root / "entities" / f"{eid}.yaml"
        if not p.exists():
            raise ScriptError(f"no entity file entities/{eid}.yaml")
        ent = copy.deepcopy(_imagined.get(Path(self.root).resolve(), {}).get(eid)) or tuning.overlay(load_yaml(p))
        ent["id"] = eid
        tells = dict(ent.get("tells") or {})
        order = {sg["id"]: sg["index"] for sg in series(self.root).segments}
        for step in ent.get("arc") or []:          # the slow clock: the map itself changes
            start = str(step["from"])
            if start not in order:
                raise ScriptError(f"{eid}'s arc starts at '{start}', which is not a scene in series.yaml")
            if order[start] <= order[key]:
                tells.update(step.get("tells") or {})
        ent["tells"] = tells
        return ent
