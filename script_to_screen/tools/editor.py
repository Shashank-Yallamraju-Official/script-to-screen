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
from types import SimpleNamespace
from urllib.parse import parse_qs, urlparse


from ..commands import Refused, address, edit, notes, tune
from ..performance import Scene, carry_into
import numpy as np
import skia

from ..presentation import anthem, sound
from ..presentation import episode as film
from ..presentation.draw import hits
from ..presentation.framecache import FrameCache
from ..presentation.render import out_path
from ..presentation.stage import Look, Stage
from ..readers import inplay, ledger
from ..script import find_root, load_yaml, scene_paths, series, tuning
from ..vocabulary import params

HERE = Path(__file__).parent
FRAMES = FrameCache()                    # shared by every scene opened in this editor
NUMBERS = {p.name: p.hi for p in params.group("turn")}     # editable timings and their upper limit, in steps
LISTS = ("rhythm", "melody", "stress")
POSITION = {"unopposed": "nobody has taken sides", "even": "evenly matched", "alone": "alone against {others}",
            "minority": "outnumbered, {mine} against {others}", "majority": "in the majority, {mine} against {others}"}



LIST_OF = {"rhythm": ("length", "len"), "melody": ("pitch", "semi"), "stress": ("stress", "stress")}


def hand(doc, t, value, changes, was):
    """Put a hand-set value on, or take it off if it only repeats what the value would be anyway."""
    value = tune.tidy(t.param.clamp(value))
    if value == tune.inherited(t, doc):
        tune.reset_in(doc, t)
    else:
        tune.set_in(doc, t, value)
    if value != was:
        changes.append(dict(address=t.address, field=t.name, before=was, after=value))


def apply_ops(root, path, sid, doc, score, ops):
    """Apply timeline edits to a scene document as hand-set values (`tune:` blocks).
    -> (the lowest turn position touched, the changes made).

    An op is {path, value}: ["turns", i, "pause" | "hold"], ["turns", i, "rhythm" | "melody" | "stress"] with a
    value per syllable, or ["turns", i, "react", j, "beat"]. `score` is the scene as `doc` stands before the edit."""
    first, changes = None, []
    for op in ops:
        where, value = op["path"], op["value"]
        if where[0] != "turns":
            raise ValueError("that value is not editable here")
        i = int(where[1])
        turn, played = doc["turns"][i], score.turns[i]
        tid = turn.get("id", i + 1)
        if len(where) == 5 and where[2] == "react" and where[4] == "beat":
            n = int(where[3]) + 1
            was = next(r["beat"] for r in played["reacts"] if r["index"] == n - 1)
            hand(doc, tune.Target(root, "reaction.beat", "reaction", path, scene=sid, turn=tid, n=n), max(float(value), 0.25), changes, tune.tidy(was))
        elif len(where) == 5 and where[2] == "sfx" and where[4] in tuning.SFX:      # one placed sound: when it starts, how long it lasts, how loud it is
            n = int(where[3])
            hand(doc, tune.Target(root, "sfx." + where[4], "sfx", path, scene=sid, turn=tid, n=n), value, changes, tune.tidy(played["sfx"][n - 1][where[4]]))
        elif len(where) == 3 and where[2] in NUMBERS:
            hand(doc, tune.Target(root, "turn." + where[2], "turn", path, scene=sid, turn=tid), value, changes, tune.tidy(played[where[2]]))
        elif len(where) == 3 and where[2] in LISTS and value is not None:
            name, field = LIST_OF[where[2]]
            for k, (syl, v) in enumerate(zip(played["sylls"], value)):
                t = tune.Target(root, "syllable." + name, "syllable", path, scene=sid, turn=tid, n=k + 1)
                now = syl["len"] - syl["rest"] if name == "length" else syl[field]      # a note's length is its voiced part
                v = tune.tidy(t.param.clamp(max(v - syl["rest"], 0.25) if name == "length" else round(v)))
                if v == tune.tidy(now):
                    continue
                if v == tune.tidy(syl["base"][name]):        # back to what it would be anyway: the tune comes off
                    tune.reset_in(doc, t)
                else:
                    tune.set_in(doc, t, v)
                changes.append(dict(address=t.address, field=name, before=tune.tidy(now), after=v))
        else:
            raise ValueError("that value is not editable here")
        first = i if first is None else min(first, i)
    return first, changes


class Session:
    """One scene open for tuning. It holds no unsaved work: while a value is being dragged it
    previews in memory, and on release the change is written to the file and journaled. It
    follows the files, so a change made elsewhere (by the assistant, or in a text editor) shows up."""

    def __init__(self, path):
        self.root = find_root(Path(path).resolve())
        self.path = Path(path).resolve()
        self.lock = threading.Lock()
        self.rev = self.info_rev = 0
        self.card, self.sketch, self._plan, self._shots = None, {}, None, {}     # the card that is open, if one is; a value of its being dragged; the episode's parts; card frames already drawn
        self.load()
        tune.played = lambda p: self.clean[1] if p == self.path and self.clean[0] == p.read_text() else None   # spare the tune commands a rebuild

    # ---- reading the files ---------------------------------------------------------------------
    def files(self):
        """Everything this scene's picture and sound depend on."""
        return [self.root / "show.yaml", self.root / "series.yaml", self.root / "land.yaml", *sorted((self.root / "library").glob("*.yaml")),
                *sorted((self.root / "entities").glob("*.yaml")), *sorted((self.root / "places").glob("*.yaml")), *scene_paths(self.root)]

    def stamp(self):
        return {str(p): p.stat().st_mtime_ns for p in self.files() if p.exists()}

    def load(self):
        self.paths = scene_paths(self.root)
        if self.path not in self.paths:
            self.path = self.paths[0]
        self.i = self.paths.index(self.path)
        self.seg = series(self.root).of(self.path)
        ed = load_yaml(self.root / "show.yaml").get("editor") or {}      # how much of the scene replays around a nudged value, in steps
        self.lead = [float(ed.get("lead_in", 8)), float(ed.get("lead_out", 8))]
        self.doc = edit.load(self.path)
        self.lib = {name: edit.load(self.root / "library" / f"{name}.yaml") for name in ("feel", "sounds")}
        try:
            self.carry = carry_into(self.path, self.root)        # earlier scenes are worked out once, not on every nudge
        except Exception:
            self.carry = {}
        self.stamps = self.stamp()
        self.work()
        self.before = (self.stage, None)                         # until the knob picks something, "before" is simply now
        self.clean = (self.path.read_text(), self.scene)         # the file's text, and the scene as that text plays
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

    # ---- the episode's other parts: its title sequence, its journeys over the land, its credits -----------
    CARD = dict(title=("anthem", "The title sequence: the anthem, whole."), travel=("anthem (low figure)", "A journey over the land, down to the next scene."),
                credits=("anthem", "The credits."), caption=(None, "A caption."))
    MUSIC = dict(music_at=(-16.0, 64.0, 0.0), music_vol=(0.0, 2.0, 1.0))      # a card's hand-set values: lowest, highest, and what it is when not set

    def plan(self):
        """The episode this scene is in, as its parts in order. Worked out when first asked for, and again when a file has changed."""
        key = tuple(sorted(self.stamp().items()))
        if self._plan is None or self._plan[0] != key:
            self._plan, self._shots = (key, film.parts(self.root, self.seg["episode"])), {}
        return self._plan[1]

    def part(self):
        return next(p for p in self.plan()[0] if p["id"] == self.card)

    def episode(self):
        """Every part of the episode, for the strip above the timeline: what it is, where it starts and how long it runs, in bars."""
        plan, look, _ = self.plan()
        out, at = [], 0.0
        for p in plan:
            bars = p["frames"] / look.fps / anthem.BAR
            out.append(dict(id=p["id"], kind=p["kind"], at=round(at, 2), bars=round(bars, 2), here=p["id"] == (self.card or self.seg["id"])))
            at += bars
        return out

    def open_part(self, pid):
        """Open another part of the episode: a scene, or a card."""
        sg = next(s for s in series(self.root).episode(self.seg["episode"])["segments"] if s["id"] == pid)
        if sg["kind"] == "scene":
            self.card, self.path = None, sg["path"]
            self.load()
        else:
            self.card, self.sketch = pid, {}
            self.rev += 1

    def card_state(self):
        """A card, in the shape the timeline expects of a scene: one turn as long as the card, and its music as a placed sound."""
        (_, look, _), part = self.plan(), self.part()
        show = load_yaml(self.root / "show.yaml")
        step = 60.0 / float(show["tempo"]) / show["steps_per_beat"]
        bar = show["steps_per_beat"] * int(show.get("beats_per_bar") or 0)
        steps = part["frames"] / look.fps / step
        sg = next(s for s in series(self.root).episode(self.seg["episode"])["segments"] if s["id"] == self.card)
        hand = {**(sg.get("tune") or {}), **self.sketch}
        name, why = self.CARD[part["kind"]]
        music = name and dict(name=name, at=float(hand.get("music_at", 0)), vol=float(hand.get("music_vol", 1)),
                              len=min(len(self.card_sound()) / sound.RATE / step, steps * 2))
        done, undone = edit.stacks(self.root, by="hand")
        turn = dict(id=part["kind"], index=0, start=0, length=steps, why=why, who=None, bar=None, sfx=[], pause=0, hold=0, say=None, lanes={}, reacts=[], stretches=[], orphans=0)
        return dict(rev=self.rev, info_rev=self.info_rev, id=self.card, can_undo=bool(done), can_redo=bool(undone), status="draft", fps=look.fps, step=step, tempo=float(show["tempo"]),
                    spb=show["steps_per_beat"], scale=[], lead=self.lead, bar=bar, bars=None, width=look.W, height=look.H, total=part["frames"], steps=steps,
                    title=f"{self.card} ({part['kind']})", file="series.yaml", index=self.i, count=len(self.paths), entities=[], emotions={}, turns=[turn], problems=[],
                    music=[], carried=[], offscreen=[], ledger={}, card=dict(id=self.card, kind=part["kind"], music=music))

    def card_sound(self):
        part = self.part()
        if "heard" not in part:
            part["heard"] = part["sound"]()
        return part["heard"]

    def card_audio(self):
        """The card's sound as the film will have it: its music where it has been asked to land."""
        x, i = self.card_sound(), int(self.part().get("music_at", 0.0) * sound.RATE)
        x = x[-i:] if i < 0 else np.concatenate([np.zeros(i), x])
        return sound.wav_bytes(np.tanh(x / 0.89) * 0.89)

    def card_frame(self, F, full):
        (_, look, _), part = self.plan(), self.part()
        F = min(max(F, 0), part["frames"] - 1)
        if (self.card, F, full) not in self._shots:
            scale = 1.0 if full else 0.5
            surface = skia.Surface(int(look.W * scale), int(look.H * scale))
            c = surface.getCanvas()
            c.scale(scale, scale)
            part["draw"](c, F)
            if len(self._shots) > 6000:
                self._shots.clear()
            self._shots[(self.card, F, full)] = bytes(surface.makeImageSnapshot().encodeToData(skia.kJPEG, 90 if full else 82))
        return self._shots[(self.card, F, full)]

    def card_patch(self, ops, commit):
        """A card's music moved or made louder or quieter. While dragging it only shows; on release it is written to series.yaml
        as a hand-set value on that segment, and journaled."""
        for op in ops:
            if op["path"][0] != "card" or op["path"][1] not in self.MUSIC:
                raise ValueError("a card's music can be moved, and made louder or quieter; nothing else of a card is editable here yet")
            lo, hi, _ = self.MUSIC[op["path"][1]]
            self.sketch[op["path"][1]] = tune.tidy(min(max(float(op["value"]), lo), hi))
        if not commit:
            return None
        file = self.root / "series.yaml"
        before = file.read_text()
        doc = edit.yaml().load(before)
        sg = next(s for se in doc["seasons"] for ep in se["episodes"] for s in ep["segments"] if str(s["id"]) == self.card)
        changes = []
        for key, value in self.sketch.items():
            was = (sg.get("tune") or {}).get(key, self.MUSIC[key][2])
            if value == self.MUSIC[key][2]:
                tune.drop(sg, key)
            else:
                tune.put(sg, key, value)
            if value != was:
                changes.append(dict(address=f"{self.card}.{key}", field=key, before=was, after=value))
        after = edit.dump(doc)
        self.sketch = {}
        if after != before:
            edit.write(file, after)
            edit.record(self.root, "nudge", None, file, changes, before, after, by="hand")
        self.stamps = self.stamp()
        self.rev += 1
        return None

    LAYERS = ("voices", "sounds", "music")

    def audio(self, only=None, before=False):
        """The sound of the part that is open: all of it, or one layer alone. Kept until the scene changes."""
        if self.card:
            return self.card_audio()
        only = only if only in self.LAYERS else None
        key = (id(self.before[0] if before else self.stage), only)
        if getattr(self, "_heard", (None,))[0] != key:
            self._heard = (key, sound.mix(self.before[0] if before else self.stage, only))
        return self._heard[1]

    def wave(self, only=None, per=4):
        """The shape of that sound: its loudest moment in every quarter of a step, from 0 to 1."""
        import io
        import wave as wav
        with wav.open(io.BytesIO(self.audio(only))) as w:
            x = np.abs(np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float32)) / 32767.0
        st = self.card_state() if self.card else dict(step=self.scene.step, steps=self.scene.steps)
        size = max(1, int(st["step"] / per * sound.RATE))
        n = min(len(x) // size, int(st["steps"] * per) + 1)
        return dict(per=per, peaks=[round(float(v), 3) for v in x[: n * size].reshape(n, size).max(axis=1)])

    def pins(self):
        """The writer's notes on the part that is open, each where it is now."""
        return notes.placed(notes.read(self.root), self.card or self.seg["id"], () if self.card else self.scene.turns)

    def pin(self, F, text, nid=None):
        """Drop a note at frame F, or change one's words, or (with no words) take it away."""
        if self.card:
            st = self.card_state()
            notes.put(self.root, self.card, F / st["fps"] / st["step"], text, nid=nid)
        else:
            steps = F / self.stage.fps / self.scene.step
            t = next((t for t in self.scene.turns if t["start"] <= steps + 1e-6 < t["start"] + t["length"]), self.scene.turns[-1])
            notes.put(self.root, self.seg["id"], steps, text, turn=t["id"], into=steps - t["start"], nid=nid)
        self.info_rev += 1

    def state(self):
        if self.card:
            return dict(self.card_state(), notes=self.pins())
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
            turns.append(dict(id=t["id"], index=t["index"], start=t["start"], length=t["length"], why=t["why"], who=t["who"], bar=t["bar"], sfx=t["sfx"],
                              pause=t["pause"], hold=t["hold"], say=say, lanes=lanes, reacts=t["reacts"], stretches=t["stretches"],
                              orphans=sum(len(v) for v in tuning.syllable_tunes(self.doc["turns"][t["index"]])[1].values())))
        mine = [p for p in self.problems if p["scene"] == sc.id]
        done, undone = edit.stacks(self.root, by="hand")
        return dict(rev=self.rev, info_rev=self.info_rev, id=sc.id, can_undo=bool(done), can_redo=bool(undone), status=self.seg["status"], fps=stage.fps, step=sc.step, tempo=sc.tempo,
                    spb=sc.grid["steps_per_beat"], scale=list(sc.grid["scale"]), lead=self.lead, notes=self.pins(),
                    bar=sc.grid["steps_per_beat"] * int(load_yaml(self.root / "show.yaml").get("beats_per_bar") or 0),       # steps in a bar, or 0 if the show has no bars
                    bars=self.doc.get("bars"),
                    width=stage.W, height=stage.H, total=stage.total, steps=sc.steps,
                    title=sc.title, file=str(self.path.relative_to(self.root)), index=self.i, count=len(self.paths),
                    entities=[dict(id=e, color=ent["color"], kind=str(ent.get("kind", ""))) for e, ent in look.cast.items()],
                    emotions=look.emotions, turns=turns, problems=mine,
                    music=[dict(at=c["t"] / sc.step, kind=c["kind"], strength=c["strength"], why=c["why"]) for c in sc.music],
                    carried=[f"{e} still feels {f[0]} {f[1]}" + (f" about {f[2]}" if f[2] else "") for e, f in sc.carried.items() if e in sc.cast],
                    offscreen=list(sc.offscreen),
                    ledger={e: {emo: {k: c[k] for k in ("seen", "need", "learned", "positions", "hidden")}
                                for emo, c in row.items()} for e, row in self.table.items()})

    # ---- changing values ------------------------------------------------------------------------
    def _locked(self):
        if self.seg["status"] == "locked":
            raise ValueError(f"{self.seg['id']} is locked. Unlock it with: s2s set-status {self.seg['id']} tuned")

    def frame_of(self, i):
        return round(self.scene.turns[i]["start"] * self.scene.step * self.stage.fps)

    def patch(self, ops, commit=False):
        """A timeline edit. While dragging it is a preview in memory; on release (`commit`) it is
        applied on top of the file as it now stands, written as hand-set values, and journaled."""
        if self.card:
            return self.card_patch(ops, commit)
        self._locked()
        if not commit:
            first, _ = apply_ops(self.root, self.path, self.seg["id"], self.doc, self.scene, ops)
            dirty = self.frame_of(first)
            self.work()
            return dirty
        before_text = self.path.read_text()
        doc = edit.yaml().load(before_text)                      # the file as it is now, not as it was when opened
        if self.clean[0] != before_text:                         # it changed underneath: work it out as it now stands
            self.clean = (before_text, Scene(self.path, script=doc, carry=self.carry).score)
        first, changes = apply_ops(self.root, self.path, self.seg["id"], doc, self.clean[1], ops)
        after_text = edit.dump(doc)
        self.doc = doc
        if after_text != before_text:
            edit.write(self.path, after_text)
            edit.record(self.root, "nudge", None, self.path, changes, before_text, after_text, by="hand")
            self.stale = time.monotonic()
        self.stamps = self.stamp()
        self.work()
        self.clean = (after_text, self.scene)
        return self.frame_of(first)

    # ---- the knob: any tunable value, by its address ---------------------------------------------
    def value(self, address):
        """What a value is, where it comes from, and how it can be changed. For the knob and its scope marks."""
        t = tune.parse(address, self.root)
        r = tune.resolve(t)
        scopes = list(t.param.scopes)
        here = scopes.index(t.scope) if t.scope in scopes else 0
        return dict(address=t.address, value=r["value"], scope=r["scope"], by=r["by"], chain=r["chain"],
                    hand_here=any(c["scope"] == t.scope and c["by"] == "hand" for c in r["chain"]),
                    wider=scopes[here + 1] if here + 1 < len(scopes) else None, rebuild=t.param.rebuild,
                    param=dict(label=t.param.label, meaning=t.param.meaning, unit=t.param.unit, lo=t.param.lo, hi=t.param.hi,
                               step=t.param.step, fine=t.param.fine if t.param.fine is not None else t.param.step / 4, scopes=scopes))

    def in_play(self, F):
        """The values at work at frame F, most likely first, each with what it is now."""
        if self.card:
            return []
        steps = F / self.stage.fps / self.scene.step
        out = []
        marked = self.stage.look.style.get("indicator", "fill") in ("dot", "trace")
        for c in inplay.in_play(self.scene, steps):
            if c["address"].startswith("feel.cursor_") and not marked:      # settings of a mark this show's bubbles do not draw
                continue
            try:
                t = tune.parse(c["address"], self.root)
                r = tune.resolve(t)
            except Refused:                                      # e.g. an event with no sound of its own
                continue
            out.append(dict(c, value=r["value"], by=r["by"], scope=r["scope"], meaning=t.param.meaning))
        return out

    def hit(self, F, x, y):
        """A click on the picture at (x, y) in frame pixels -> the address of the value to put on the knob, or None.
        A syllable in the bubble gives its length; the bubble gives the line's tone; a token gives whatever
        that entity is doing at this moment, else its own settings."""
        if self.card:
            return None
        sid, turn = self.seg["id"], self.scene.turn_at(F / self.stage.fps)
        for h in hits(self.stage, F):
            bx, by, bw, bh = h["box"]
            if not (bx <= x <= bx + bw and by <= y <= by + bh):
                continue
            if h["kind"] == "syllable":
                mine = [b for b in self.scene.speech if turn["start"] * self.scene.step - 1e-9 <= b["start"] < (turn["start"] + turn["length"]) * self.scene.step]
                before = sum(len(b["sylls"]) for b in mine if b["start"] < h["line"]["start"] - 1e-9)
                return f"{sid}:{turn['id']}.s{before + h['n'] + 1}.length"
            if h["kind"] == "bubble":
                return f"~{h['line']['tone']}.rate"
            e = h["entity"]
            doing = [c["address"] for c in self.in_play(F) if c["why"].startswith(e + " ") or c["why"].endswith(" " + e)]
            return doing[0] if doing else f"@{e}.voice" if turn["line"] and turn["who"] == e else f"@{e}.reflex"
        return None

    def find(self, words, F):
        """Values in this scene that a writer might mean by `words` ("bouncy", "the gap", "louder"), the
        best match first and, among equals, the one nearest the playhead."""
        want = [w for w in words.lower().split() if w]
        if not want or self.card:
            return dict(found=[], unseen=[])

        def fit(p):                                              # how well a parameter answers to the words
            text = [p.label.lower(), p.name.replace("_", " "), *p.words]
            exact = sum(any(w == t or w in t.split() for t in text) for w in want)
            loose = sum(any(w in t for t in text + [p.meaning.lower()]) for w in want)
            return exact * 10 + loose
        good = {p.key: fit(p) for p in params.PARAMS.values() if fit(p) > 0}
        steps, sc, found = F / self.stage.fps / self.scene.step, self.scene, {}
        moments = {s["start"] + s["length"] / 2 for t in sc.turns for s in t["stretches"]} | {t / sc.step for t, *_ in sc.events}
        for at in moments:
            for c in inplay.in_play(sc, at):
                if c["param"] in good:
                    far = abs((c["span"][0] + c["span"][1]) / 2 - steps)
                    if c["address"] not in found or far < found[c["address"]][0]:
                        found[c["address"]] = (far, c)
        owned = {s["address"] for t in sc.turns for s in t["stretches"]}     # a stretch that is really there beats one that could be added
        out = []
        for far, c in sorted(found.values(), key=lambda x: (-good[x[1]["param"]], params.PARAMS[x[1]["param"]].owns_time and x[1]["address"] not in owned, x[0]))[:9]:
            t = tune.parse(c["address"], self.root)
            r = tune.resolve(t)
            out.append(dict(c, value=r["value"], by=r["by"], scope=r["scope"], meaning=t.param.meaning))
        seen = {c["param"] for c in out}                         # what answers to the words but is not at work anywhere in this scene
        return dict(found=out, unseen=[params.PARAMS[k].label for k in sorted(good, key=lambda k: -good[k]) if k not in seen][:3])

    def nudge(self, address, op, value=None):
        """Set, take off or widen a hand-set value from the knob. Each is written at once; a quick run of
        nudges on one value is one undo step. -> the first frame to redraw, or None if the picture is unchanged."""
        t = tune.parse(address, self.root)
        if op == "set":
            value = tune.tidy(t.param.clamp(value))
            if value == tune.inherited(t):                       # back to what it would be anyway: the hand-set value comes off
                op = "reset"
        ask = SimpleNamespace(action=op, address=address, value=value, to=None, orphans=False, show=str(self.root),
                              dry_run=False, because=None, by="hand")
        try:
            self.last = tune.tune(ask)                           # what the command reported: for a widening, how much it changed
        except Refused as e:
            if "nothing" not in str(e):                          # already that value: not an error for a knob
                raise ValueError(str(e) + (f". {e.hint}" if e.hint else ""))
            return None
        if op == "set":
            edit.coalesce(self.root)
        score = t.param.rebuild == "timing"
        if t.file == self.path:
            self.doc = edit.load(self.path)
        elif t.file.parent.name == "library" and t.file.stem in self.lib:
            self.lib[t.file.stem] = edit.load(t.file)
        self.stamps = self.stamp()
        self.work(score=score)
        if score:
            self.clean = (self.path.read_text(), self.scene)
            self.stale = time.monotonic()
        if not score:
            return 0 if t.param.rebuild == "look" else None
        turn = t.where.get("turn")
        i = next((k for k, x in enumerate(self.scene.turns) if str(x["id"]) == str(turn)), 0) if t.file == self.path and turn is not None else 0
        return self.frame_of(i)

    def step(self, which):
        """Undo or redo the writer's own last change (never the assistant's)."""
        (edit.undo if which == "undo" else edit.redo)(self.root, by="hand")
        self.load()

    def open(self, step):
        self.card = None
        self.path = self.paths[(self.i + int(step)) % len(self.paths)]
        self.load()

    def pick(self):
        """The knob has been put on a value: remember the scene as it stands now, to compare against later."""
        self.before = (self.stage, None)
        return dict(total=self.stage.total, rev=self.rev)

    def frame(self, F, full, xray, before=False):
        """A frame of the scene now, or as it stood when the knob picked a value. Frames are kept by what
        they show, so anything seen before (an undo, the other side of a comparison) is not drawn again."""
        if self.card:
            return self.card_frame(F, full)
        stage = self.before[0] if before else self.stage
        F = min(max(F, 0), stage.total - 1)
        return FRAMES.get(stage, F, 1.0 if full else 0.5, 90 if full else 82, xray)


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
                    if url.path == "/value":                 # the knob: what a value is and where it comes from
                        return self.send(sess.value(q["address"][0]))
                    if url.path == "/hit":                   # a click on the picture
                        return self.send(dict(address=sess.hit(int(q["f"][0]), float(q["x"][0]), float(q["y"][0]))))
                    if url.path == "/find":                  # a value, by the words a writer would use for it
                        return self.send(sess.find(q.get("q", [""])[0], int(q["f"][0])))
                    if url.path == "/in-play":               # the values at work at this frame
                        return self.send(sess.in_play(int(q["f"][0])))
                    if url.path == "/poll":                  # has anything changed underneath?
                        return self.send(sess.poll())
                    if url.path == "/frame":                 # build=A is the scene as it stood when the knob was put on a value
                        return self.send(sess.frame(int(q["f"][0]), flag("full"), flag("xray"), q.get("build") == ["A"]), "image/jpeg")
                    if url.path == "/episode":               # every part of the episode this scene is in
                        return self.send(sess.episode())
                    if url.path == "/audio":                 # only=voices|sounds|music is one layer alone
                        return self.send(sess.audio(q.get("only", [None])[0], q.get("build") == ["A"]), "audio/wav")
                    if url.path == "/wave":                  # the shape of the sound, for the lane under the timeline
                        return self.send(sess.wave(q.get("only", [None])[0]))
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
                    elif self.path == "/pick":
                        return self.send(sess.pick())
                    elif self.path == "/nudge":
                        sess.last = None
                        out["dirty_from"] = sess.nudge(body["address"], body["op"], body.get("value"))
                        out["affects"] = (sess.last or {}).get("affects")
                        try:
                            out["value"] = sess.value(body["address"])
                        except Refused:
                            out["value"] = None
                    elif self.path in ("/undo", "/redo"):
                        sess.step(self.path[1:])
                        out["dirty_from"] = 0
                    elif self.path == "/note":                # a note pinned to a moment
                        sess.pin(int(body.get("f", 0)), body.get("text"), body.get("id"))
                    elif self.path == "/open" and body.get("part"):      # open a part of the episode by name: a scene, or a card
                        sess.open_part(body["part"])
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
