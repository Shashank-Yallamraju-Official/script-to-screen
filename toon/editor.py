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

from . import dialogue
from .render import Scene, frame_jpeg

HERE = Path(__file__).parent
EDITABLE = {"frame", "length", "hold"}


class Session:
    def __init__(self, path):
        self.path = Path(path).resolve()
        self.yaml = YAML()
        self.yaml.preserve_quotes = True
        self.yaml.width = 4096
        self.yaml.indent(mapping=2, sequence=4, offset=2)
        self.lock = threading.Lock()
        self.rev = 0
        self.load()

    def load(self):
        with open(self.path) as fh:
            self.doc = self.yaml.load(fh)
        self.dirty = False
        self.rebuild()

    def rebuild(self):
        self.scene = Scene(self.path, script=self.doc)
        self.rev += 1
        self.cache = {}

    def save(self):
        with open(self.path, "w") as fh:
            self.yaml.dump(self.doc, fh)
        self.dirty = False

    # -- the timeline model the browser draws ------------------------------------------------
    def state(self):
        sc = self.scene
        lines = {ln["start"]: ln for ln in sc.lines}
        shots = []
        for i, shot in enumerate(sc.shots):
            raw = self.doc["shots"][i]
            cam = raw.get("camera", {"framing": "wide"})
            keys = []
            for k, key in enumerate(cam if isinstance(cam, list) else [cam]):
                subject = key.get("subject", "")
                subject = "+".join(subject) if isinstance(subject, list) else subject
                keys.append(dict(frame=int(key.get("frame", 0)), label=f"{key.get('framing', 'wide')} {subject}".strip(),
                                 path=["shots", i, "camera", k, "frame"] if isinstance(cam, list) else None))
            beats, latest = [], max([k["frame"] for k in keys] + [0])
            for j, beat in enumerate(raw.get("beats", [])):
                f = int(beat["frame"])
                latest = max(latest, f)
                item = dict(frame=f, path=["shots", i, "beats", j, "frame"], who={})
                for who in sc.cast:
                    if who in beat:
                        item["who"][who] = " · ".join(str(beat[who][k]) for k in ("pose", "expression", "facing") if k in beat[who])
                if "say" in beat:
                    ln, say = lines[shot["start"] + f], beat["say"]
                    item["say"] = dict(who=say["who"], text=str(say["text"]), tone=ln["tone"],
                                       tone_color=sc.tones[ln["tone"]]["color"],
                                       reveal=round(ln["reveal_end"] - ln["start"]), hold=int(say.get("hold", 45)),
                                       shown=ln["end"] - ln["start"], hold_path=["shots", i, "beats", j, "say", "hold"])
                beats.append(item)
            shots.append(dict(id=shot["id"], start=shot["start"], length=int(shot["length"]), min_length=latest + 1,
                              path=["shots", i, "length"], camera=keys, beats=beats))
        return dict(rev=self.rev, dirty=self.dirty, fps=sc.fps, width=sc.W, height=sc.H, total=sc.total,
                    title=str(self.doc.get("scene", self.path.stem)), file=str(self.path.relative_to(sc.root)),
                    cast=[dict(id=w, color=ch["color"]) for w, (ch, _) in sc.cast.items()], shots=shots)

    # -- edits -------------------------------------------------------------------------------
    def patch(self, ops):
        """Apply [{path, value}] to the working copy. Only timing numbers can change."""
        dirty_from = self.scene.total
        for op in ops:
            path, value = op["path"], int(round(op["value"]))
            if path[0] != "shots" or path[-1] not in EDITABLE:
                raise ValueError("only timings are editable here")
            i = int(path[1])
            shot = self.doc["shots"][i]
            low = self.state()["shots"][i]["min_length"]
            if path[-1] == "length":
                value = max(value, low, 2)
            elif path[-1] == "frame":
                value = min(max(value, 0), int(shot["length"]) - 1)
            else:
                value = min(max(value, 0), 600)
            node = self.doc
            for part in path[:-1]:
                node = node[part]
            node[path[-1]] = value
            dirty_from = min(dirty_from, self.scene.shots[i]["start"])
            self.dirty = True
            self.rebuild()
        return dirty_from

    def frame(self, F, full):
        key = (F, full)
        if key not in self.cache:
            if len(self.cache) > 6000:
                self.cache = {}
            self.cache[key] = frame_jpeg(self.scene, F, 1.0 if full else 0.5, 88 if full else 80)
        return self.cache[key]

    def audio(self):
        sc = self.scene
        buf = io.BytesIO()
        dialogue.write_blips(sc.lines, sc.tones, {w: ch["voice"] for w, (ch, _) in sc.cast.items()},
                             sc.fps, sc.total, buf)
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
            try:
                with sess.lock:
                    if url.path == "/":
                        return self.send((HERE / "editor.html").read_bytes(), "text/html; charset=utf-8")
                    if url.path == "/state":
                        return self.send(sess.state())
                    if url.path == "/frame":
                        F = min(max(int(q["f"][0]), 0), sess.scene.total - 1)
                        return self.send(sess.frame(F, q.get("full", ["0"])[0] == "1"), "image/jpeg")
                    if url.path == "/audio":
                        return self.send(sess.audio(), "audio/wav")
                    if url.path == "/video":
                        return self.send(video_path(sess).read_bytes(), "video/mp4")
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
                            return self.send(dict(error="save first"), status=409)
                    run = subprocess.run([sys.executable, "-m", "toon.render", str(sess.path), "--clean"],
                                         cwd=sess.scene.root, capture_output=True, text=True)
                    if run.returncode:
                        return self.send(dict(error=run.stderr[-600:]), status=500)
                    return self.send(dict(file=str(video_path(sess))))
                with sess.lock:
                    out = {}
                    if self.path == "/patch":
                        out["dirty_from"] = sess.patch(body["ops"])
                    elif self.path == "/save":
                        sess.save()
                    elif self.path == "/revert":
                        sess.load()
                        out["dirty_from"] = 0
                    else:
                        return self.send(dict(error="not found"), status=404)
                    out["state"] = sess.state()
                self.send(out)
            except Exception as e:
                self.send(dict(error=str(e)), status=400)

    return Handler


def video_path(sess):
    rel = sess.path.relative_to(sess.scene.root / "episodes").with_suffix(".mp4")
    return sess.scene.root / "out" / rel


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
