"""Commands on the shape of the series: which scenes exist, in what order, and how finished they are."""
import json
import re
from pathlib import Path

from ruamel.yaml.comments import CommentedMap, CommentedSeq

from ..script import SCHEMA, STATUSES, find_root, load_yaml, series
from . import A, Refused, address, command, edit


def series_file(root):
    return Path(root) / "series.yaml"


def locate(doc, sid):
    """-> (the segment list holding it, its position, the episode) for a segment id in series.yaml as loaded."""
    for se in doc.get("seasons") or []:
        for ep in se.get("episodes") or []:
            for i, sg in enumerate(ep.get("segments") or []):
                if str(sg["id"]) == sid:
                    return ep["segments"], i, ep
    raise Refused(f"no scene '{sid}' in series.yaml")


def episode_of(doc, eid):
    eps = [ep for se in doc.get("seasons") or [] for ep in se.get("episodes") or []]
    for ep in eps:
        if str(ep["id"]) == eid:
            return ep
    raise Refused(f"no episode '{eid}'", hint="episodes: " + ", ".join(str(ep["id"]) for ep in eps))


def flow(pairs):
    m = CommentedMap(pairs)
    m.fa.set_flow_style()
    return m


@command("set-status", "Mark how finished a scene is: draft, staged, tuned or locked. A locked scene refuses every change.",
         [A("scene", "the scene"), A("status", "its new status", choices=list(STATUSES))], "s2s set-status thermostat locked",
         changes=True, group="change")
def set_status(a):
    root, path = address.scene(a.scene, a.show)
    sid = address.of(root, path)

    def mutate(doc):
        segs, i, _ = locate(doc, sid)
        old = segs[i].get("status", "draft")
        if a.status == "draft":
            segs[i].pop("status", None)
        else:
            segs[i]["status"] = a.status
        return dict(changes=[] if old == a.status else [dict(address=sid, field="status", before=old, after=a.status)])
    return edit.apply(a, root, series_file(root), mutate, series_file=True)


@command("move", "Move a scene to another place in the series. What entities carry between scenes follows the new order.",
         [A("scene", "the scene to move"), A("--before", "put it just before this scene"), A("--after", "or just after this one"),
          A("--episode", "or at the end of this episode")], "s2s move thermostat --before vase", changes=True, group="change")
def move(a):
    root, path = address.scene(a.scene, a.show)
    sid = address.of(root, path)
    if sum(x is not None for x in (a.before, a.after, a.episode)) != 1:
        raise Refused("say where: exactly one of --before, --after, --episode")
    target = address.of(root, address.scene(a.before or a.after, a.show)[1]) if (a.before or a.after) else None
    if target == sid:
        raise Refused("a scene cannot be moved next to itself")

    def mutate(doc):
        order = lambda: [str(sg["id"]) for se in doc["seasons"] for ep in se.get("episodes") or [] for sg in ep.get("segments") or []]
        was = order()
        segs, i, ep0 = locate(doc, sid)
        seg = segs.pop(i)
        if a.episode:
            ep = episode_of(doc, a.episode)
            if ep.get("segments") is None:
                ep["segments"] = CommentedSeq()
            ep["segments"].append(seg)
        else:
            dest, j, _ = locate(doc, target)
            dest.insert(j if a.before else j + 1, seg)
        now = order()
        return dict(changes=[] if now == was else [dict(address=sid, field="position", before=was.index(sid) + 1, after=now.index(sid) + 1)], order=now)
    return edit.apply(a, root, series_file(root), mutate, series_file=True)


@command("add-scene", "Create a scene and give it a place in the series. It starts with one turn: who is there, and why.",
         [A("id", "the scene's id: short, lower-case, unique in the show"), A("--episode", "the episode it belongs to", required=True),
          A("--title", "its title", required=True), A("--enter", "who is there as it opens, as YAML: '{juno: {slot: 2}, otis: {slot: 6}}'", required=True),
          A("--why", "why the scene opens this way", required=True), A("--after", "put it after this scene (default: the end of the episode)")],
         "s2s add-scene the-apology --episode s01e01 --title \"The apology\" --enter '{otis: {slot: 3}, juno: {slot: 6}}' --why \"He has come to say it.\"",
         changes=True, group="change")
def add_scene(a):
    root = address.show_root(a.show)
    ser = series(root)
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]*", a.id):
        raise Refused(f"'{a.id}' cannot be an id", hint="use lower-case letters, digits and hyphens, e.g. the-apology")
    if a.id in ser.by_id:
        raise Refused(f"there is already a scene called '{a.id}'")
    ep = ser.episode(a.episode)
    rel = Path("episodes") / ep["season"] / a.episode / f"{a.id}.yaml"
    path = Path(root) / rel
    if path.exists():
        raise Refused(f"{rel} already exists")
    enter = edit.yaml().load(a.enter)
    enter.fa.set_flow_style()
    scene_doc = CommentedMap([("scene", a.title), ("turns", CommentedSeq([CommentedMap([("id", 1), ("enter", enter), ("why", a.why)])]))])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(edit.dump(scene_doc))                    # the file must exist for the change to be checked

    def mutate(doc):
        new = flow([("id", a.id), ("scene", rel.as_posix())])
        if a.after:
            dest, j, _ = locate(doc, address.of(root, address.scene(a.after, a.show)[1]))
            dest.insert(j + 1, new)
        else:
            e = episode_of(doc, a.episode)
            if e.get("segments") is None:
                e["segments"] = CommentedSeq()
            e["segments"].append(new)
        return dict(changes=[dict(address=a.id, field="scene", before=None, after=rel.as_posix())], file=str(path))
    try:
        out = edit.apply(a, root, series_file(root), mutate, series_file=True)
    except Refused:
        path.unlink()
        raise
    if a.dry_run:
        path.unlink()
    return out


@command("migrate", "Bring a show's files up to the format this engine reads. Safe to run twice.", [], "s2s migrate --show shows/demo",
         group="history")
def migrate(a):
    try:
        root = find_root(Path(a.show or ".").resolve())
    except Exception:
        root = address.show_root(a.show)
    cfg_file = Path(root) / "show.yaml"
    have = (load_yaml(cfg_file) or {}).get("schema", 1)
    if have == SCHEMA:
        return dict(schema=SCHEMA, did=[], text=f"already at schema {SCHEMA}")
    if have != 1:
        raise Refused(f"this show is at schema {have}; this engine reads {SCHEMA} and can only migrate from 1")
    did, used, ids = [], set(), {}
    seasons = CommentedSeq()
    for p in sorted((Path(root) / "episodes").rglob("*.yaml")):          # schema 1: scenes ran in path order
        old = p.relative_to(Path(root) / "episodes").with_suffix("").as_posix()
        parts = old.split("/")[:-1] or ["s01"]
        sid = base = re.sub(r"^\d+-", "", p.stem)
        n = 2
        while sid in used:
            sid, n = f"{base}-{n}", n + 1
        used.add(sid)
        ids[old] = sid
        season_id, ep_id = parts[0], "".join(parts) if len(parts) > 1 else parts[0] + "-e01"
        season = next((s for s in seasons if s["id"] == season_id), None)
        if season is None:
            season = CommentedMap([("id", season_id), ("title", season_id), ("episodes", CommentedSeq())])
            seasons.append(season)
        ep = next((e for e in season["episodes"] if e["id"] == ep_id), None)
        if ep is None:
            ep = CommentedMap([("id", ep_id), ("title", ep_id), ("segments", CommentedSeq())])
            season["episodes"].append(ep)
        ep["segments"].append(flow([("id", sid), ("scene", p.relative_to(root).as_posix())]))
    doc = CommentedMap([("seasons", seasons)])
    doc.yaml_set_start_comment("The series from above: seasons, episodes and their segments, in order.\n"
                               "A segment's id is its identity; its file can be renamed or moved without changing it.")
    series_file(root).write_text(edit.dump(doc))
    did.append(f"wrote series.yaml with {len(used)} scenes")
    for f in sorted((Path(root) / "entities").glob("*.yaml")):           # arcs named scenes by path; now by id
        ent = edit.load(f)
        changed = False
        for step in ent.get("arc") or []:
            if str(step["from"]) in ids:
                step["from"], changed = ids[str(step["from"])], True
        if changed:
            f.write_text(edit.dump(ent))
            did.append(f"entities/{f.name}: arc now names scenes by id")
    ref = Path(root) / "reference"
    for f in sorted(ref.glob("*.json")) if ref.exists() else []:
        data = json.loads(f.read_text())
        if data.get("scene") in ids:
            data["scene"] = ids[data["scene"]]
            f.unlink()
            (ref / (data["scene"] + ".json")).write_text(json.dumps(data, indent=2) + "\n")
            did.append(f"reference/{f.name} -> {data['scene']}.json")
    text = cfg_file.read_text()
    text = re.sub(r"(?m)^schema:\s*\d+", f"schema: {SCHEMA}", text) if re.search(r"(?m)^schema:", text) else f"schema: {SCHEMA}\n" + text
    cfg_file.write_text(text)
    did.append(f"show.yaml: schema {SCHEMA}")
    return dict(schema=SCHEMA, did=did, ids=ids, text="\n".join(did))
