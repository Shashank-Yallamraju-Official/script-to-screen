"""The editor: scrub, play, drag timings, set every syllable's note, tune the small details.

    s2s edit shows/demo/episodes/s01/e01/01-the-last-dumpling.yaml

Runs a small server on this machine only and opens the editor in your browser. Edits live in
memory until you save; saving rewrites only the changed values and keeps comments and layout.
"""
import argparse
import json
import subprocess
import sys
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from ruamel.yaml import YAML
from ruamel.yaml.comments import CommentedSeq

from ..performance import Scene
from ..presentation import sound
from ..presentation.render import frame_jpeg, out_path
from ..presentation.stage import Look, Stage
from ..readers import ledger
from ..script import find_root

HERE = Path(__file__).parent
NUMBERS = {"pause": 200, "hold": 400}            # editable timings and their upper limit, in steps
LISTS = ("rhythm", "melody", "stress")
POSITION = {"unopposed": "nobody has taken sides", "even": "evenly matched", "alone": "alone against {others}",
            "minority": "outnumbered, {mine} against {others}", "majority": "in the majority, {mine} against {others}"}
# sliders: key, min, max, step, what it does
FEEL = [("ease", 0.05, 0.8, 0.01, "Seconds a change takes to settle"),
        ("overshoot", 0, 2, 0.05, "How far a move swings past its mark before settling"),
        ("flip", 0, 1, 0.05, "How thin a token gets mid-turn, like paper flipping"),
        ("squash", 0, 0.4, 0.01, "Stretch while travelling"),
        ("cursor_size", 1, 10, 0.5, "Size of the indicator that travels under a spoken line (it grows on stressed syllables)"),
        ("cursor_lift", 0, 24, 1, "How far the indicator rises and falls with the voice's pitch, in pixels"),
        ("cursor_tail", 0, 0.4, 0.01, "Seconds of trail the indicator leaves behind it"),
        ("voice_attack", 0.001, 0.08, 0.001, "Seconds a syllable's note takes to swell. Short is percussive, long is soft"),
        ("voice_ring", 0, 1, 0.05, "How much of its level a note keeps to its end. 0 is plucked, 1 is held so syllables run together"),
        ("bubble_pop", 0, 0.5, 0.01, "Seconds a bubble takes to pop open"),
        ("focus_dim", 0, 0.8, 0.05, "How far everyone else fades while a featured reaction holds the scene"),
        ("aside_volume", 0, 1, 0.05, "How loud a background reaction's sounds are, next to a featured one")]
SOUND = [("vol", 0, 1, 0.01, "Volume (0 is off)"), ("freq", 40, 2000, 5, "Starting pitch in Hz"),
         ("to", 40, 2000, 5, "Pitch it glides to, in Hz"), ("dur", 0.01, 0.6, 0.01, "Length in seconds")]


def tidy(v):
    v = round(float(v), 3)
    return int(v) if v == int(v) else v


class Session:
    def __init__(self, path):
        first = Path(path).resolve()
        self.root = find_root(first)
        self.paths = ledger.scene_paths(self.root)
        self.i = self.paths.index(first)
        self.yaml = YAML()
        self.yaml.preserve_quotes = True
        self.yaml.width = 4096
        self.yaml.indent(mapping=2, sequence=4, offset=2)
        self.lock = threading.Lock()
        self.rev = 0
        self.lib, self.lib_dirty = {}, set()
        for name in ("feel", "sounds"):
            with open(self.root / "library" / f"{name}.yaml") as fh:
                self.lib[name] = self.yaml.load(fh)
        self.load()

    @property
    def path(self):
        return self.paths[self.i]

    @property
    def dirty(self):
        return self.scene_dirty or bool(self.lib_dirty)

    def load(self):
        with open(self.path) as fh:
            self.doc = self.yaml.load(fh)
        self.scene_dirty = False
        self.rebuild()

    def rebuild(self):
        self.scene = Scene(self.path, script=self.doc, lib=self.lib).score     # the editor reads the score and the look
        self.stage = Stage(self.scene, Look.load(self.root, self.scene.cast, self.lib), self.root)
        self.table, self.problems = ledger.build(self.root, override={self.path: self.doc}, lib=self.lib)
        self.rev += 1
        self.cache = {}

    def save(self):
        if self.scene_dirty:
            with open(self.path, "w") as fh:
                self.yaml.dump(self.doc, fh)
        for name in self.lib_dirty:
            with open(self.root / "library" / f"{name}.yaml", "w") as fh:
                self.yaml.dump(self.lib[name], fh)
        self.scene_dirty, self.lib_dirty = False, set()

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
        return dict(rev=self.rev, dirty=self.dirty, fps=stage.fps, step=sc.step, tempo=sc.tempo,
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

    def patch(self, ops):
        """Apply [{path: [turns, i, key], value}] to the scene's working copy."""
        dirty_from = self.stage.total
        for op in ops:
            path, value = op["path"], op["value"]
            if len(path) == 5 and path[0] == "turns" and path[2] == "react" and path[4] == "beat":
                i = int(path[1])                         # how long a featured reaction holds the scene
                self.doc["turns"][i]["react"][int(path[3])]["beat"] = tidy(min(max(float(value), 0.25), 200))
                dirty_from = min(dirty_from, round(self.scene.turns[i]["start"] * self.scene.step * self.stage.fps))
                self.scene_dirty = True
                self.rebuild()
                continue
            if len(path) != 3 or path[0] != "turns" or path[2] not in tuple(NUMBERS) + LISTS:
                raise ValueError("that value is not editable here")
            i, key = int(path[1]), path[2]
            turn = self.doc["turns"][i]
            if key in NUMBERS:
                value = tidy(min(max(float(value), 0), NUMBERS[key]))
                if value == self.scene.grid["timing"][key]:
                    value = None                         # the show default needs no line in the file
            elif value is not None:
                seq = CommentedSeq(tidy(max(v, 0.25)) if key == "rhythm" else max(0, min(2, int(v))) if key == "stress" else int(round(v)) for v in value)
                seq.fa.set_flow_style()
                value = seq
            if value is None:
                turn.pop(key, None)
            elif key in turn:
                turn[key] = value
            else:                                        # new lines go above `why`, which stays last
                keys = list(turn)
                turn.insert(keys.index("why") if "why" in keys else len(keys), key, value)
            dirty_from = min(dirty_from, round(self.scene.turns[i]["start"] * self.scene.step * self.stage.fps))
            self.scene_dirty = True
            self.rebuild()
        return dirty_from

    def tune(self, group, name, key, value):
        """Change one slider: a feel setting, or one setting of one sound."""
        spec = {k: (lo, hi) for k, lo, hi, _, _ in (FEEL if group == "feel" else SOUND)}
        lo, hi = spec[key]
        value = tidy(min(max(float(value), lo), hi))
        if group == "feel":
            self.lib["feel"][key] = value
        else:
            self.lib["sounds"][name][key] = value
        self.lib_dirty.add(group)
        self.rebuild()

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
                        if sess.dirty:
                            return self.send(dict(error="Save first, then render."), status=409)
                        path, root = str(sess.path), sess.root
                    run = subprocess.run([sys.executable, "-m", "script_to_screen.render", path], cwd=root, capture_output=True, text=True)
                    if run.returncode:
                        lines = [ln for ln in run.stderr.splitlines() if "Fontconfig" not in ln]
                        return self.send(dict(error="\n".join(lines[-6:])), status=500)
                    return self.send(dict(file=str(out_path(sess.stage))))
                with sess.lock:
                    out = {}
                    if self.path == "/patch":
                        out["dirty_from"] = sess.patch(body["ops"])
                    elif self.path == "/tune":
                        sess.tune(body["group"], body.get("name"), body["key"], body["value"])
                        out["dirty_from"] = 0
                    elif self.path == "/save":
                        sess.save()
                    elif self.path == "/open":                # step to the previous or next scene
                        if sess.scene_dirty:
                            return self.send(dict(error="Save first, then switch scenes."), status=409)
                        sess.i = (sess.i + int(body.get("step", 1))) % len(sess.paths)
                        sess.load()
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
    sess = Session(a.scene)
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
