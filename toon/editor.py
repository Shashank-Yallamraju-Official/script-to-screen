"""Timing editor: scrub, drag timings, play, save.

    python -m toon.editor episodes/pilot/scene01.yaml

Runs a small server on this machine only and opens the editor in your browser. Edits live in
memory until you save; saving rewrites only the changed numbers in the scene file and keeps
its comments and layout.
"""
import argparse
import io
import json
import subprocess
import sys
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from ruamel.yaml import YAML

from . import ledger, speech
from .model import Scene, find_root
from .render import frame_jpeg, out_path

HERE = Path(__file__).parent
EDITABLE = {"pause": 600, "hold": 900}
POSITION = {"unopposed": "nobody has taken sides", "even": "evenly matched", "alone": "alone against {others}",
            "minority": "outnumbered, {mine} against {others}", "majority": "in the majority, {mine} against {others}"}


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
        self.load()

    @property
    def path(self):
        return self.paths[self.i]

    def load(self):
        with open(self.path) as fh:
            self.doc = self.yaml.load(fh)
        self.dirty = False
        self.rebuild()

    def rebuild(self):
        self.scene = Scene(self.path, script=self.doc)
        self.table, self.problems = ledger.build(self.root, override={self.path: self.doc})
        self.rev += 1
        self.cache = {}

    def save(self):
        with open(self.path, "w") as fh:
            self.yaml.dump(self.doc, fh)
        self.dirty = False

    def state(self):
        sc = self.scene
        turns = []
        for t in sc.turns:
            lanes = {e: [] for e in sc.ents}
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
                say = dict(who=t["who"], text=t["line"]["text"], tone=tone, tone_color=sc.show.tones[tone]["color"],
                           at=t["say_at"], reveal=t["reveal"], latency=t["latency"])
            turns.append(dict(id=t["id"], start=t["start"], length=t["length"], why=t["why"], who=t["who"],
                              pause=t["pause"], hold=t["hold"], react=t["react"], say=say, lanes=lanes,
                              paths=dict(pause=["turns", t["index"], "pause"], hold=["turns", t["index"], "hold"])))
        mine = [p for p in self.problems if p["scene"] in (sc.key, sc.path.stem)]
        return dict(rev=self.rev, dirty=self.dirty, fps=sc.fps, width=sc.W, height=sc.H, total=sc.total,
                    title=sc.title, file=str(self.path.relative_to(self.root)), index=self.i, count=len(self.paths),
                    entities=[dict(id=e, color=ent["color"], kind=str(ent.get("kind", ""))) for e, ent in sc.ents.items()],
                    emotions=sc.show.emotions, turns=turns, problems=mine,
                    ledger={e: {emo: {k: c[k] for k in ("seen", "need", "learned", "positions", "hidden")}
                                for emo, c in row.items()} for e, row in self.table.items()})

    def patch(self, ops):
        """Apply [{path, value}] to the working copy. Only timing numbers can change."""
        dirty_from = self.scene.total
        for op in ops:
            path, value = op["path"], int(round(op["value"]))
            if len(path) != 3 or path[0] != "turns" or path[2] not in EDITABLE:
                raise ValueError("only timings are editable here")
            i = int(path[1])
            turn, key, value = self.doc["turns"][i], path[2], min(max(value, 0), EDITABLE[path[2]])
            if value == self.scene.show.cfg["timing"][key]:
                turn.pop(key, None)                      # the show default needs no line in the file
            elif key in turn:
                turn[key] = value
            else:                                        # new lines go above `why`, which stays last
                keys = list(turn)
                turn.insert(keys.index("why") if "why" in keys else len(keys), key, value)
            dirty_from = min(dirty_from, self.scene.turns[i]["start"])
            self.dirty = True
            self.rebuild()
        return dirty_from

    def frame(self, F, full, xray):
        key = (F, full, xray)
        if key not in self.cache:
            if len(self.cache) > 8000:
                self.cache = {}
            self.cache[key] = frame_jpeg(self.scene, F, 1.0 if full else 0.5, 90 if full else 82, xray)
        return self.cache[key]

    def audio(self):
        sc, buf = self.scene, io.BytesIO()
        speech.write_blips(sc.lines, sc.show.tones, {e: ent["voice"] for e, ent in sc.ents.items()}, sc.fps, sc.total, buf)
        return buf.getvalue()


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
                        F = min(max(int(q["f"][0]), 0), sess.scene.total - 1)
                        return self.send(sess.frame(F, flag("full"), flag("xray")), "image/jpeg")
                    if url.path == "/audio":
                        return self.send(sess.audio(), "audio/wav")
                    if url.path == "/video":
                        return self.send(out_path(sess.scene).read_bytes(), "video/mp4")
                self.send(dict(error="not found"), status=404)
            except BrokenPipeError:
                pass
            except Exception as e:  # show the reason in the browser instead of dying silently
                self.send(dict(error=str(e)), status=500)

        def do_POST(self):
            # Only this page may change the scene: refuse requests sent from other sites.
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
                    run = subprocess.run([sys.executable, "-m", "toon.render", path], cwd=root, capture_output=True, text=True)
                    if run.returncode:
                        lines = [ln for ln in run.stderr.splitlines() if "Fontconfig" not in ln]
                        return self.send(dict(error="\n".join(lines[-6:])), status=500)
                    return self.send(dict(file=str(out_path(sess.scene))))
                with sess.lock:
                    out = {}
                    if self.path == "/patch":
                        out["dirty_from"] = sess.patch(body["ops"])
                    elif self.path == "/save":
                        sess.save()
                    elif self.path == "/open":                # step to the previous or next scene
                        if sess.dirty:
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
