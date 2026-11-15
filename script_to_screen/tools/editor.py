"""The editor: scrub, play, drag timings, set every syllable's note, tune the small details.

    s2s edit the-thermostat

Runs a small server on this machine only and opens the editor in your browser. There is no
Save: letting go of a value writes it to the file (only that value; comments and layout are
kept) and records it in the journal, where it can be undone. The editor follows the files.
"""
import argparse
import json
import subprocess
import sys
import threading
import time
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from ruamel.yaml.comments import CommentedSeq

from ..commands import Refused, address, edit
from ..performance import Scene, carry_into
from ..presentation import sound
from ..presentation.render import frame_jpeg, out_path
from ..presentation.stage import Look, Stage
from ..readers import ledger
from ..script import find_root, scene_paths, series
from ..vocabulary import params

HERE = Path(__file__).parent
NUMBERS = {p.name: p.hi for p in params.group("turn")}     # editable timings and their upper limit, in steps
LISTS = ("rhythm", "melody", "stress")
POSITION = {"unopposed": "nobody has taken sides", "even": "evenly matched", "alone": "alone against {others}",
            "minority": "outnumbered, {mine} against {others}", "majority": "in the majority, {mine} against {others}"}
# sliders: key, min, max, step, what it does; all from the declarations in vocabulary/params.py
FEEL = [(p.name, p.lo, p.hi, p.step, p.meaning.rstrip(".")) for p in params.group("feel")]
SOUND = [(p.name, p.lo, p.hi, p.step, p.meaning.rstrip(".")) for p in params.group("sound")]


def tidy(v):
    v = round(float(v), 3)
    return int(v) if v == int(v) else v


def apply_ops(doc, ops, timing):
    """Apply timeline edits to a scene document. -> the lowest turn position touched.

    An op is {path, value}: ["turns", i, "pause" | "hold" | "rhythm" | "melody" | "stress"], or
    ["turns", i, "react", j, "beat"] for how long a featured reaction holds the scene."""
    first = None
    for op in ops:
        path, value = op["path"], op["value"]
        if len(path) == 5 and path[0] == "turns" and path[2] == "react" and path[4] == "beat":
            doc["turns"][int(path[1])]["react"][int(path[3])]["beat"] = tidy(params.PARAMS["reaction.beat"].clamp(max(float(value), 0.25)))
        elif len(path) == 3 and path[0] == "turns" and path[2] in tuple(NUMBERS) + LISTS:
            key, turn = path[2], doc["turns"][int(path[1])]
            if key in NUMBERS:
                value = tidy(min(max(float(value), 0), NUMBERS[key]))
                if value == timing[key]:
                    value = None                         # the show default needs no line in the file
            elif value is not None:
                seq = CommentedSeq(tidy(max(v, 0.25)) if key == "rhythm" else max(0, min(2, int(v))) if key == "stress" else int(round(v)) for v in value)
                seq.fa.set_flow_style()
                value = seq
            if value is None:
                turn.pop(key, None)
            else:
                edit.put(turn, key, value)               # a new line goes above `why`, which stays last
        else:
            raise ValueError("that value is not editable here")
        first = int(path[1]) if first is None else min(first, int(path[1]))
    return first


def value_at(doc, path):
    v = doc
    for k in path:
        v = v.get(k) if isinstance(v, dict) else v[k]
        if v is None:
            return None
    return edit.plain(v)


class Session:
    """One scene open for tuning. It holds no unsaved work: while a value is being dragged it
    previews in memory, and on release the change is written to the file and journaled. It
    follows the files, so a change made elsewhere (by the assistant, or in a text editor) shows up."""

    def __init__(self, path):
        self.root = find_root(Path(path).resolve())
        self.path = Path(path).resolve()
        self.lock = threading.Lock()
        self.rev = self.info_rev = 0
        self.load()

    # ---- reading the files ---------------------------------------------------------------------
    def files(self):
        """Everything this scene's picture and sound depend on."""
        return [self.root / "show.yaml", self.root / "series.yaml", *sorted((self.root / "library").glob("*.yaml")),
                *sorted((self.root / "entities").glob("*.yaml")), *scene_paths(self.root)]

    def stamp(self):
        return {str(p): p.stat().st_mtime_ns for p in self.files() if p.exists()}

    def load(self):
        self.paths = scene_paths(self.root)
        if self.path not in self.paths:
            self.path = self.paths[0]
        self.i = self.paths.index(self.path)
        self.seg = series(self.root).of(self.path)
        self.doc = edit.load(self.path)
        self.lib = {name: edit.load(self.root / "library" / f"{name}.yaml") for name in ("feel", "sounds")}
        try:
            self.carry = carry_into(self.path, self.root)        # earlier scenes are worked out once, not on every nudge
        except Exception:
            self.carry = {}
        self.stamps = self.stamp()
        self.work()
        self.inform()

    def sync(self):
        """Reload if any file changed underneath. -> whether it did."""
        if self.stamp() == self.stamps:
            return False
        self.load()
        return True

    def work(self, score=True):
        """Work the scene out again (or, for a change of look only, just restage it)."""
        if score:
            self.scene = Scene(self.path, script=self.doc, carry=self.carry).score
            self.cache = {}
        self.stage = Stage(self.scene, Look.load(self.root, self.scene.cast, self.lib), self.root)
        self.rev += 1

    def inform(self):
        """The audience ledger and the show's problems. Not on the nudge path: a nudge cannot change the story."""
        self.table, self.problems = ledger.build(self.root, override={self.path: self.doc})
        self.stale, self.info_rev = None, self.info_rev + 1

    def poll(self):
        changed = self.sync()
        if self.stale is not None and time.monotonic() - self.stale > 1.0:
            self.inform()
        return dict(rev=self.rev, info_rev=self.info_rev, changed=changed)

    def state(self):
        sc, look, stage = self.scene, self.stage.look, self.stage
        turns = []
        for t in sc.turns:
            lanes = {e: [] for e in sc.cast}
            for at, infos in t["info"]:
                for e, info in infos.items():
                    if not info["felt"]:
                        lanes[e].append(dict(at=at))
                        continue
                    where = POSITION[info["klass"]].format(mine=info["mine"], others=info["others"])
                    lanes[e].append(dict(at=at, felt=info["felt"], intensity=info["intensity"], level=info["level"],
                                         tip=f"{e} feels {info['felt']} {info['intensity']}, shows {info['level']} · {where}"
                                             + (f" (gain {info['gain']:.2f})" if info["weight"] is not None else "")))
            say = None
            if t["line"]:
                tone = t["line"]["tone"]
                say = dict(who=t["who"], text=t["line"]["text"], tone=tone, sung=t["line"]["sung"], tone_color=look.tones[tone]["color"],
                           at=t["say_at"], reveal=t["reveal"], latency=t["latency"], sylls=t["sylls"],
                           rhythm=list(t["rhythm"]) if t["rhythm"] is not None else None,
                           melody=list(t["melody"]) if t["melody"] is not None else None,
                           stress=list(t["stress"]) if t["stress"] is not None else None)
            turns.append(dict(id=t["id"], index=t["index"], start=t["start"], length=t["length"], why=t["why"], who=t["who"],
                              pause=t["pause"], hold=t["hold"], say=say, lanes=lanes, reacts=t["reacts"]))
        mine = [p for p in self.problems if p["scene"] == sc.id]
        feel, sounds = self.lib["feel"], self.lib["sounds"]
        done, undone = edit.stacks(self.root, by="hand")
        return dict(rev=self.rev, info_rev=self.info_rev, can_undo=bool(done), can_redo=bool(undone), status=self.seg["status"], fps=stage.fps, step=sc.step, tempo=sc.tempo,
                    spb=sc.grid["steps_per_beat"], scale=list(sc.grid["scale"]),
                    width=stage.W, height=stage.H, total=stage.total, steps=sc.steps,
                    title=sc.title, file=str(self.path.relative_to(self.root)), index=self.i, count=len(self.paths),
                    entities=[dict(id=e, color=ent["color"], kind=str(ent.get("kind", ""))) for e, ent in look.cast.items()],
                    emotions=look.emotions, turns=turns, problems=mine,
                    carried=[f"{e} still feels {f[0]} {f[1]}" + (f" about {f[2]}" if f[2] else "") for e, f in sc.carried.items() if e in sc.cast],
                    offscreen=list(sc.offscreen),
                    ledger={e: {emo: {k: c[k] for k in ("seen", "need", "learned", "positions", "hidden")}
                                for emo, c in row.items()} for e, row in self.table.items()},
                    feel=[dict(key=k, min=lo, max=hi, step=st, tip=tip, value=float(feel[k])) for k, lo, hi, st, tip in FEEL],
                    sounds=[dict(name=str(n), params=[dict(key=k, min=lo, max=hi, step=st, tip=tip, value=float(p.get(k, p.get("freq", 440) if k == "to" else 0)))
                                                      for k, lo, hi, st, tip in SOUND]) for n, p in sounds.items()])

    # ---- changing values ------------------------------------------------------------------------
    def _locked(self):
        if self.seg["status"] == "locked":
            raise ValueError(f"{self.seg['id']} is locked. Unlock it with: s2s set-status {self.seg['id']} tuned")

    def frame_of(self, i):
        return round(self.scene.turns[i]["start"] * self.scene.step * self.stage.fps)

    def patch(self, ops, commit=False):
        """A timeline edit. While dragging it is a preview in memory; on release (`commit`) it is
        applied on top of the file as it now stands, written, and journaled."""
        self._locked()
        timing = self.scene.grid["timing"]
        if not commit:
            first = apply_ops(self.doc, ops, timing)
            dirty = self.frame_of(first)
            self.work()
            return dirty
        before_text = self.path.read_text()
        doc = edit.yaml().load(before_text)                      # the file as it is now, not as it was when opened
        before = [value_at(doc, op["path"]) for op in ops]
        first = apply_ops(doc, ops, timing)
        after_text = edit.dump(doc)
        dirty = self.frame_of(first)
        self.doc = doc
        if after_text != before_text:
            edit.write(self.path, after_text)
            changes = []
            for op, was in zip(ops, before):
                turn = doc["turns"][int(op["path"][1])]
                tid = turn.get("id", int(op["path"][1]) + 1)
                field = op["path"][2] if len(op["path"]) == 3 else f"react[{int(op['path'][3]) + 1}].beat"
                changes.append(dict(address=f"{self.seg['id']}:{tid}", field=field, before=was, after=value_at(doc, op["path"])))
            edit.record(self.root, "nudge", None, self.path, changes, before_text, after_text, by="hand")
            self.stale = time.monotonic()
        self.stamps = self.stamp()
        self.work()
        return dirty

    def tune(self, group, name, key, value, commit=False):
        """One slider: a feel setting, or one setting of one sound. -> the first frame to redraw, or None."""
        p = params.PARAMS[("feel." if group == "feel" else "sound.") + key]
        value = tidy(p.clamp(value))
        file = self.root / "library" / f"{group}.yaml"
        if commit:
            before_text = file.read_text()
            lib = edit.yaml().load(before_text)
            target = lib if group == "feel" else lib[name]
            was = edit.plain(target.get(key))
            target[key] = value
            after_text = edit.dump(lib)
            self.lib[group] = lib
            if after_text != before_text:
                edit.write(file, after_text)
                where = f"feel.{key}" if group == "feel" else f"sounds.{name}.{key}"
                edit.record(self.root, "nudge", None, file, [dict(address=where, field="value", before=was, after=value)],
                            before_text, after_text, by="hand")
            self.stamps = self.stamp()
        else:
            (self.lib["feel"] if group == "feel" else self.lib["sounds"][name])[key] = value
        if p.rebuild == "look":
            self.cache = {}
        self.work(score=False)                                   # the score does not depend on the look
        return 0 if p.rebuild == "look" else None

    def step(self, which):
        """Undo or redo the writer's own last change (never the assistant's)."""
        (edit.undo if which == "undo" else edit.redo)(self.root, by="hand")
        self.load()

    def open(self, step):
        self.path = self.paths[(self.i + int(step)) % len(self.paths)]
        self.load()

    def frame(self, F, full, xray):
        key = (F, full, xray)
        if key not in self.cache:
            if len(self.cache) > 12000:
                self.cache = {}
            self.cache[key] = frame_jpeg(self.stage, F, 1.0 if full else 0.5, 90 if full else 82, xray)
        return self.cache[key]


def make_handler(sess):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def send(self, body, ctype="application/json", status=200):
            if not isinstance(body, bytes):
                body = json.dumps(body).encode()
            self.send_response(status)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            url = urlparse(self.path)
            q = parse_qs(url.query)
            flag = lambda k: q.get(k, ["0"])[0] == "1"
            try:
                with sess.lock:
                    if url.path == "/":
                        return self.send((HERE / "editor.html").read_bytes(), "text/html; charset=utf-8")
                    if url.path == "/state":
                        return self.send(sess.state())
                    if url.path == "/poll":                  # has anything changed underneath?
                        return self.send(sess.poll())
                    if url.path == "/frame":
                        F = min(max(int(q["f"][0]), 0), sess.stage.total - 1)
                        return self.send(sess.frame(F, flag("full"), flag("xray")), "image/jpeg")
                    if url.path == "/audio":
                        return self.send(sound.mix(sess.stage), "audio/wav")
                    if url.path == "/sfx":                   # one sound on its own, to audition it
                        p = sound.sound_for(sess.stage.look.sounds, q["name"][0])
                        return self.send(sound.wav_bytes(sound.effect(p)), "audio/wav")
                    if url.path == "/video":
                        return self.send(out_path(sess.stage).read_bytes(), "video/mp4")
                self.send(dict(error="not found"), status=404)
            except BrokenPipeError:
                pass
            except Exception as e:  # show the reason in the browser instead of dying silently
                self.send(dict(error=str(e)), status=500)

        def do_POST(self):
            # Only this page may change the files: refuse requests sent from other sites.
            origin = self.headers.get("Origin")
            if origin and urlparse(origin).netloc != self.headers.get("Host"):
                return self.send(dict(error="forbidden"), status=403)
            n = int(self.headers.get("Content-Length") or 0)
            body = json.loads(self.rfile.read(n) or b"{}")
            try:
                if self.path == "/render":
                    with sess.lock:
                        sid, root = sess.seg["id"], sess.root
                    run = subprocess.run([sys.executable, "-m", "script_to_screen.cli", "render", sid, "--show", str(root), "--json"],
                                         capture_output=True, text=True)
                    reply = json.loads(run.stdout or "{}")
                    if run.returncode:
                        return self.send(dict(error=reply.get("text") or reply.get("refused") or "the render failed"), status=500)
                    return self.send(dict(file=reply["files"][0]["file"]))
                with sess.lock:
                    out = {}
                    if self.path == "/patch":
                        out["dirty_from"] = sess.patch(body["ops"], bool(body.get("commit")))
                    elif self.path == "/tune":
                        out["dirty_from"] = sess.tune(body["group"], body.get("name"), body["key"], body["value"], bool(body.get("commit")))
                    elif self.path in ("/undo", "/redo"):
                        sess.step(self.path[1:])
                        out["dirty_from"] = 0
                    elif self.path == "/open":                # step to the previous or next scene
                        sess.open(body.get("step", 1))
                    else:
                        return self.send(dict(error="not found"), status=404)
                    out["state"] = sess.state()
                self.send(out)
            except Exception as e:
                self.send(dict(error=str(e)), status=400)

    return Handler


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("scene")
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--no-open", action="store_true")
    a = ap.parse_args()
    try:
        _, scene = address.scene(a.scene)
    except Refused as e:
        sys.exit(f"{e}" + (f"\n  {e.hint}" if e.hint else ""))
    sess = Session(scene)
    server = ThreadingHTTPServer(("127.0.0.1", a.port), make_handler(sess))
    url = f"http://127.0.0.1:{a.port}/"
    print(f"Editing {sess.path.name} at {url}  (Ctrl+C to stop)")
    if not a.no_open:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print()


if __name__ == "__main__":
    main()
