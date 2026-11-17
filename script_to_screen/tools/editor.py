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

from ruamel.yaml.comments import CommentedMap, CommentedSeq
from urllib.parse import parse_qs, urlparse


from ..commands import Refused, address, edit, notes, tune
from ..performance import Scene, carry_into
import numpy as np
import skia

from ..presentation import anthem, sound
from ..presentation import episode as film
from ..presentation.draw import draw_frame, hits
from ..presentation.framecache import FrameCache
from ..presentation.render import out_path
from ..presentation.stage import Look, Stage
from ..readers import bible, inplay, ledger
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


def apply_ops(root, path, sid, doc, score, ops, ripple=False):
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
            was = tune.tidy(played[where[2]])
            hand(doc, tune.Target(root, "turn." + where[2], "turn", path, scene=sid, turn=tid), value, changes, was)
            per = score.grid["steps_per_beat"] * int(load_yaml(Path(root) / "show.yaml").get("beats_per_bar") or 0)
            moved = (float(tune.tidy(value)) - float(was or 0)) * (1.0 if where[2] == "bar" else 1.0 / per if per else 0.0)      # in bars
            if ripple and per and moved:                         # ripple: every later line that is pinned to a bar moves by as much, and the scene grows to match
                for j in range(i + 1, len(doc["turns"])):
                    later = tuning.bar_of(doc["turns"][j])
                    if later is not None:
                        hand(doc, tune.Target(root, "turn.bar", "turn", path, scene=sid, turn=doc["turns"][j].get("id", j + 1)), later + moved, changes, tune.tidy(later))
                if doc.get("bars") is not None:
                    changes.append(dict(address=sid, field="bars", before=doc["bars"], after=tune.tidy(float(doc["bars"]) + moved)))
                    doc["bars"] = tune.tidy(float(doc["bars"]) + moved)
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
        pinned = (self.root / notes.FILE).stat().st_mtime_ns if (self.root / notes.FILE).exists() else 0
        if pinned != getattr(self, "_pinned", pinned):               # a note was closed or added elsewhere
            self.info_rev += 1
        self._pinned = pinned
        return dict(rev=self.rev, info_rev=self.info_rev, changed=changed, news=self.news())

    def news(self):
        """Changes made from outside the editor since it last looked (by the assistant, with a command): what changed, why, and
        where to look. The journal is only read when it has grown."""
        j = edit.journal(self.root)
        size = j.stat().st_size if j.exists() else 0
        if not hasattr(self, "_journal"):                            # the first look: everything already there is old news
            self._journal = (size, len(edit.entries(self.root)))
            return []
        if size == self._journal[0]:
            return []
        es = edit.entries(self.root)
        seen = self._journal[1]
        self._journal = (size, len(es))
        out = []
        for e in es[seen:]:
            if e.get("by", "command") == "hand" or not e.get("changes"):
                continue
            c = e["changes"][0]
            addr, field = str(c["address"]), str(c.get("field") or "")
            knob = label = None
            for a in (addr, f"{addr}.{field}"):
                try:
                    label = tune.parse(a, self.root).param.label
                    knob = a
                    break
                except Exception:
                    pass
            try:
                part = series(self.root).of(self.root / e["path"])["id"]
            except Exception:
                part = addr.split(".")[0] if e["path"] in ("series.yaml",) else None
            turn = addr.split(":")[1].split(".")[0] if ":" in addr else None
            says = "; ".join(f"{x['address']}{'' if str(x.get('field')) in str(x['address']) else ' ' + str(x.get('field'))}: {json.dumps(x.get('before'), ensure_ascii=False)} \u2192 {json.dumps(x.get('after'), ensure_ascii=False)}"
                             for x in e["changes"][:3]) + (f" (and {len(e['changes']) - 3} more)" if len(e["changes"]) > 3 else "")
            if label and len(e["changes"]) == 1:                  # in the knob's own words: "the-council-again, turn 9 · Lasts: 16 → 12"
                says = ", turn ".join(x for x in (part or addr.split(".")[0], turn) if x) + f" \u00b7 {label}: {json.dumps(c.get('before'))} \u2192 {json.dumps(c.get('after'))}"
            out.append(dict(id=e["id"], text=says, because=e.get("because"), part=part, turn=turn, address=knob))
        return out

    def take_back(self):
        """Undo the assistant's last change (the writer's own are undone with Undo)."""
        edit.undo(self.root, by="command")
        self.load()

    # ---- the episode's other parts: its title sequence, its journeys over the land, its credits -----------
    CARD = dict(title=("anthem", "The title sequence: the anthem, whole."), travel=("anthem (low figure)", "A journey over the land, down to the next scene."),
                credits=("anthem", "The credits."), caption=(None, "A caption."), episode=(None, "The whole episode."))
    MUSIC = dict(music_at=(-16.0, 64.0, 0.0), music_vol=(0.0, 2.0, 1.0), music_in=(0.0, 32.0, 0.0), music_out=(0.0, 32.0, 0.0))      # a card's hand-set values: lowest, highest, and what it is when not set

    def plan(self):
        """The episode this scene is in, as its parts in order. Worked out when first asked for, and again when a file has changed."""
        key = tuple(sorted(self.stamp().items()))
        if self._plan is None or self._plan[0] != key:
            self._plan, self._shots = (key, film.parts(self.root, self.seg["episode"])), {}
        return self._plan[1]

    WHOLE = "*"                                                  # the name, among parts, of the whole episode as one timeline

    def part(self):
        plan, look, _ = self.plan()
        if self.card != self.WHOLE:
            return next(p for p in plan if p["id"] == self.card)
        if getattr(self, "_whole", (None,))[0] is not plan:      # every part end to end: one picture, one soundtrack
            ends = np.cumsum([p["frames"] for p in plan])

            def draw(c, F):
                k = min(int(np.searchsorted(ends, F, side="right")), len(plan) - 1)
                plan[k]["draw"](c, F - (ends[k - 1] if k else 0))
            self._whole = (plan, dict(id=self.seg["episode"], kind="episode", frames=int(ends[-1]), draw=draw, sound=lambda: film.soundtrack(plan, look.fps)))
        return self._whole[1]

    def whole(self, step):
        """The whole episode laid out: where each part starts and how long it is, in steps, with every line and placed sound in its place."""
        plan, look, _ = self.plan()
        parts, lines, sounds, at = [], [], [], 0.0
        for p in plan:
            long = p["frames"] / look.fps / step
            if self.sketch.get("length", (None,))[0] == p["id"]:
                long = self.sketch["length"][1]
            parts.append(dict(id=p["id"], kind=p["kind"], start=at, length=long))
            if p["kind"] == "scene":
                sc, cast = p["stage"].score, p["stage"].look.cast
                for t in sc.turns:
                    if t["line"]:
                        lines.append(dict(at=at + t["start"] + t["say_at"], len=t["reveal"], text=t["line"]["text"], color=cast[t["who"]]["color"]))
                    sounds += [dict(at=at + fx["start"] - (fx["len"] if fx["sound"] == "blast" and fx["len"] else 0), len=fx["len"] or 2, name=fx["sound"]) for fx in t["sfx"]]
            at += long
        return parts, lines, sounds

    def episode(self):
        """Every part of the episode, for the strip above the timeline: what it is, where it starts and how long it runs, in bars."""
        (plan, look, _), show = self.plan(), load_yaml(self.root / "show.yaml")
        out, at = [], 0.0
        bar = 60.0 / float(show["tempo"]) * int(show.get("beats_per_bar") or 0) or anthem.BAR
        for p in plan:
            bars = p["frames"] / look.fps / bar
            out.append(dict(id=p["id"], kind=p["kind"], at=round(at, 2), bars=round(bars, 2), here=p["id"] == (self.card or self.seg["id"])))
            at += bars
        return [dict(id=self.WHOLE, kind="episode", at=0, bars=round(at, 2), here=self.card == self.WHOLE)] + out

    def levels(self):
        """How loud each part of the episode is: its average level in decibels, leaving out its silences."""
        out = {}
        for p in self.plan()[0]:
            if "heard" not in p:
                p["heard"] = p["sound"]()
            x = p["heard"][: int(p["frames"] / self.plan()[1].fps * sound.RATE)]
            n = sound.RATE * 4 // 10                                      # in blocks of 0.4 s
            power = (x[: len(x) // n * n].reshape(-1, n) ** 2).mean(axis=1) if len(x) >= n else np.array([float((x ** 2).mean())])
            loud = power[power > 1e-6]                                    # quieter than -60 dB is silence, and is left out
            out[p["id"]] = round(float(10 * np.log10(loud.mean())), 1) if len(loud) else None
        return out

    def open_part(self, pid):
        """Open another part of the episode: a scene, or a card."""
        if pid == self.WHOLE:
            self.card, self.sketch = pid, {}
            self.rev += 1
            return
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
        done, undone = edit.stacks(self.root, by="hand")
        if self.card == self.WHOLE:
            parts, lines, sounds = self.whole(step)
            turns = [dict(id=p["id"], index=k, start=p["start"], length=p["length"], why=f"{p['id']}: {p['kind']}", who=None, bar=None, sfx=[], pause=0, hold=p["length"], say=None,
                          lanes={}, reacts=[], stretches=[], orphans=0) for k, p in enumerate(parts)]
            steps = parts[-1]["start"] + parts[-1]["length"]
            return dict(rev=self.rev, info_rev=self.info_rev, id=part["id"], can_undo=bool(done), can_redo=bool(undone), status="draft", fps=look.fps, step=step, tempo=float(show["tempo"]),
                        spb=show["steps_per_beat"], scale=[], lead=self.lead, bar=bar, bars=None, width=look.W, height=look.H, total=part["frames"], steps=steps,
                        title=f"{part['id']} (the whole episode)", file="series.yaml", index=self.i, count=len(self.paths), entities=[], emotions={}, turns=turns, problems=[],
                        music=[], carried=[], offscreen=[], ledger={}, card=dict(id=self.WHOLE, kind="episode", music=None, lines=lines, sounds=sounds))
        sg = next(s for s in series(self.root).episode(self.seg["episode"])["segments"] if s["id"] == self.card)
        hand = {**(sg.get("tune") or {}), **{k: v for k, v in self.sketch.items() if k in self.MUSIC}}
        name, why = self.CARD[part["kind"]]
        camera = [list(map(float, k)) for k in part["card"].land["camera"]] if self.over_land(part) else None
        if "length" in self.sketch:
            steps = self.sketch["length"][1]
        music = name and dict(name=name, at=float(hand.get("music_at", 0)), vol=float(hand.get("music_vol", 1)), fade_in=float(hand.get("music_in", 0)), fade_out=float(hand.get("music_out", 0)),
                              len=min(len(self.card_sound()) / sound.RATE / step, steps * 2))
        turn = dict(id=part["kind"], index=0, start=0, length=steps, why=why, who=None, bar=None, sfx=[], pause=0, hold=steps if camera else 0, say=None, lanes={}, reacts=[], stretches=[], orphans=0)
        return dict(rev=self.rev, info_rev=self.info_rev, id=self.card, can_undo=bool(done), can_redo=bool(undone), status="draft", fps=look.fps, step=step, tempo=float(show["tempo"]),
                    spb=show["steps_per_beat"], scale=[], lead=self.lead, bar=bar, bars=None, width=look.W, height=look.H, total=part["frames"], steps=steps,
                    title=f"{self.card} ({part['kind']})", file="series.yaml", index=self.i, count=len(self.paths), entities=[], emotions={}, turns=[turn], problems=[],
                    music=[], carried=[], offscreen=[], ledger={}, card=dict(id=self.card, kind=part["kind"], music=music, camera=camera))

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

    def length_patch(self, ops, commit):
        """In the whole-episode view, a part's right edge dragged: only a part whose length is its own to set (the credits) can change."""
        (plan, _, _), show = self.plan(), load_yaml(self.root / "show.yaml")
        op = ops[-1]
        if op["path"][0] != "turns" or op["path"][-1] != "hold":
            raise ValueError("in the whole-episode view only a part's length can be dragged; double-click a part to open it and tune what is inside")
        part = plan[int(op["path"][1])]
        if part["kind"] != "credits":
            raise ValueError(f"{part['id']} takes its length from " + ("its script: open it and change a hold or a bar" if part["kind"] == "scene" else "its camera's path over the land"))
        per = show["steps_per_beat"] * int(show.get("beats_per_bar") or 1)
        bars = max(2.0, round(float(op["value"]) / per * 2) / 2)                  # in half bars, and never shorter than two
        self.sketch = {"length": (part["id"], bars * per)}
        if not commit:
            return None
        file = self.root / "series.yaml"
        before = file.read_text()
        doc = edit.yaml().load(before)
        sg = next(s for se in doc["seasons"] for ep in se["episodes"] for s in ep["segments"] if str(s["id"]) == part["id"])
        was = (sg.get("tune") or {}).get("bars")
        tune.put(sg, "bars", bars)
        after = edit.dump(doc)
        self.sketch = {}
        if after != before:
            edit.write(file, after)
            edit.record(self.root, "nudge", None, file, [dict(address=f"{part['id']}.bars", field="bars", before=was, after=bars)], before, after, by="hand")
        self.stamps = self.stamp()
        self.rev += 1
        return 0

    @staticmethod
    def over_land(part):
        """Is this part the title sequence over the land, whose camera follows a written path?"""
        return part["kind"] == "title" and hasattr(part.get("card"), "land")

    def camera_patch(self, op, commit):
        """The camera's path over the land (land.yaml `camera: [[bar, x, y, zoom], ...]`): a stop retimed, moved, brought closer, added or
        removed; or the sequence made longer or shorter. While dragging, the picture follows; on release it is written and journaled."""
        part, where, value = self.part(), op["path"], op["value"]
        show = load_yaml(self.root / "show.yaml")
        per = show["steps_per_beat"] * int(show.get("beats_per_bar") or 1)
        file = self.root / "land.yaml"
        before = file.read_text()
        doc = edit.yaml().load(before)
        keys, end = doc["camera"], float(doc.get("bars", anthem.BARS))
        if where[0] == "turns":                                   # the sequence's length, in half bars; a last stop at the end moves with it
            bars = max(4.0, round(float(value) / per * 2) / 2)
            self.sketch["length"] = (part["id"], bars * per)
            if float(keys[-1][0]) == end and bars > float(keys[-2][0]):
                keys[-1][0] = tune.tidy(bars)
            doc["bars"] = tune.tidy(bars)
        elif where[1] == "add":
            bar = min(max(float(value), float(keys[0][0]) + 0.125), float(keys[-1][0]) - 0.125)
            at = part["card"]._camera(bar * part["card"].bar)
            i = next(k for k, key in enumerate(keys) if float(key[0]) > bar)
            keys.insert(i, tune._flow(CommentedSeq([tune.tidy(bar), round(at[0]), round(at[1]), round(at[2], 2)])))
        elif where[1] == "drop":
            if not 0 < int(value) < len(keys) - 1:
                raise ValueError("the first and last stops stay: the camera has to start and end somewhere")
            del keys[int(value)]
        else:
            i, what = int(where[1]), where[2]
            if what == "bar":
                lo = float(keys[i - 1][0]) + 0.125 if i else 0.0
                hi = float(keys[i + 1][0]) - 0.125 if i + 1 < len(keys) else end
                keys[i][0] = tune.tidy(min(max(float(value), lo), hi))
            elif what == "xy":
                keys[i][1], keys[i][2] = round(float(value[0])), round(float(value[1]))
            elif what == "z":
                keys[i][3] = round(min(max(float(value), 0.5), 4.0), 2)
            else:
                raise ValueError("a camera stop has a bar, a place it looks at, and a closeness")
        part["card"].land["camera"] = [list(map(float, k)) for k in keys]         # the picture follows at once
        self._shots = {}
        self.rev += 1
        if not commit:
            return 0
        after = edit.dump(doc)
        self.sketch = {}
        if after != before:
            edit.write(file, after)
            edit.record(self.root, "nudge", None, file, [dict(address=f"land.{'.'.join(map(str, where))}", field="camera", before=None, after=edit.plain(value))], before, after, by="hand")
        self.stamps = self.stamp()
        return 0

    def card_patch(self, ops, commit):
        """A card's music moved or made louder or quieter. While dragging it only shows; on release it is written to series.yaml
        as a hand-set value on that segment, and journaled."""
        if self.card == self.WHOLE:
            return self.length_patch(ops, commit)
        if ops[-1]["path"][0] in ("camera", "turns") and self.over_land(self.part()):
            return self.camera_patch(ops[-1], commit)
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

    # ---- takes: the whole show's tuning as it stood, kept under a name ----------------------------------
    def _takes(self):
        return self.root / ".s2s" / "takes"

    def _now(self):
        return {str(p.relative_to(self.root)): p.read_text() for p in self.files() if p.exists()}

    def takes(self):
        """Every take, oldest first, and whether it is what the show says now."""
        now, out = self._now(), []
        for f in sorted(self._takes().glob("*.json"), key=lambda f: f.stat().st_mtime):
            t = json.loads(f.read_text())
            out.append(dict(name=t["name"], at=t["at"], here=all(now.get(k) == v for k, v in t["files"].items())))
        return out

    def take(self, save=None, open=None, drop=None):
        """Keep the show as it stands under a name; or switch the show to a take (one undo step); or throw a take away."""
        slug = lambda name: "".join(c if c.isalnum() else "-" for c in str(name).strip().lower()) or "take"
        if save and str(save).strip():
            self._takes().mkdir(parents=True, exist_ok=True)
            (self._takes() / f"{slug(save)}.json").write_text(json.dumps(dict(name=str(save).strip(), at=time.strftime("%Y-%m-%d %H:%M"), files=self._now()), ensure_ascii=False))
        elif drop:
            (self._takes() / f"{slug(drop)}.json").unlink(missing_ok=True)
        elif open:
            t = json.loads((self._takes() / f"{slug(open)}.json").read_text())
            group = f"take-{time.time()}"
            for rel, text in t["files"].items():
                path = self.root / rel
                before = path.read_text() if path.exists() else None
                if before is not None and before != text:
                    edit.write(path, text)
                    edit.record(self.root, "take", None, path, [dict(address=rel, field="take", before=None, after=t["name"])], before, text, by="hand", group=group)
            self.load()

    def curves(self):
        """The level curves of the part that is open: {layer: [[steps, level], ...]}."""
        if self.card == self.WHOLE:
            return {}
        if self.card:
            sg = next(s for s in series(self.root).episode(self.seg["episode"])["segments"] if s["id"] == self.card)
            return {k: [list(p) for p in v] for k, v in (sg.get("levels") or {}).items()}
        return {k: [list(map(float, p)) for p in v] for k, v in (self.doc.get("levels") or {}).items()}

    def curve(self, layer, points):
        """Set a layer's level curve (no points takes it away). Written to the scene's file, or to the card's segment, and journaled."""
        if layer not in self.LAYERS or (self.card and layer != "music") or self.card == self.WHOLE:
            raise ValueError("a level curve belongs to the voices, the sounds or the music of one part")
        pts = sorted([tune.tidy(max(0.0, float(a))), tune.tidy(min(max(float(v), 0.0), 2.0))] for a, v in points)
        file = self.root / "series.yaml" if self.card else self.path
        before = file.read_text()
        doc = edit.yaml().load(before)
        holder = next(s for se in doc["seasons"] for ep in se["episodes"] for s in ep["segments"] if str(s["id"]) == self.card) if self.card else doc
        was = (holder.get("levels") or {}).get(layer)
        if pts:
            if holder.get("levels") is None:
                holder["levels"] = tune._flow(CommentedMap()) if self.card else CommentedMap()
            seq = CommentedSeq(tune._flow(CommentedSeq(p)) for p in pts)
            holder["levels"][layer] = tune._flow(seq)
        elif was is not None:
            del holder["levels"][layer]
            if not holder["levels"]:
                del holder["levels"]
        after = edit.dump(doc)
        if after != before:
            edit.write(file, after)
            edit.record(self.root, "nudge", None, file, [dict(address=f"{self.card or self.seg['id']}.levels.{layer}", field="levels", before=edit.plain(was), after=pts)], before, after, by="hand")
        if self.card:
            self.stamps = self.stamp()
            self.rev += 1
        else:
            self.doc = edit.load(self.path)
            self.stamps = self.stamp()
            self.work(score=False)
            self.clean = (self.path.read_text(), self.scene)

    def render_range(self, F0, F1):
        """A stretch of the part that is open, as a video file of its own: out/<part>.range.mp4."""
        import io
        import wave as wav
        if self.card:
            (_, look, _), part = self.plan(), self.part()
            W, H, fps, total, draw, name = look.W, look.H, look.fps, part["frames"], part["draw"], part["id"]
        else:
            st = self.stage
            W, H, fps, total, draw, name = st.W, st.H, st.fps, st.total, (lambda c, F: draw_frame(c, st, F)), self.seg["id"]
        F0, F1 = max(0, int(F0)), min(total, int(F1))
        if F1 - F0 < 2:
            raise ValueError("that range is empty")
        out = self.root / "out" / f"{name}.range.mp4"
        out.parent.mkdir(parents=True, exist_ok=True)
        silent, sound_file, tmp = out.with_suffix(".silent.mp4"), out.with_suffix(".wav"), out.with_suffix(".part.mp4")
        ff = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgba", "-s", f"{W}x{H}", "-r", str(fps), "-i", "-",
                               "-c:v", "libx264", "-crf", "18", "-preset", "veryfast", "-pix_fmt", "yuv420p", str(silent)], stdin=subprocess.PIPE)
        surface = skia.Surface(W, H)
        for F in range(F0, F1):
            draw(surface.getCanvas(), F)
            ff.stdin.write(surface.toarray(colorType=skia.kRGBA_8888_ColorType).tobytes())
        ff.stdin.close()
        if ff.wait() != 0:
            raise ValueError("ffmpeg failed")
        with wav.open(io.BytesIO(self.audio())) as w:
            x = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float64) / 32767.0
        sound_file.write_bytes(sound.wav_bytes(x[int(F0 / fps * sound.RATE): int(F1 / fps * sound.RATE)]))
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(silent), "-i", str(sound_file), "-map", "0:v", "-map", "1:a",
                        "-c:v", "copy", "-c:a", "aac", "-b:a", "160k", str(tmp)], check=True)
        tmp.replace(out)
        silent.unlink()
        sound_file.unlink()
        self.ranged = out
        return out

    def pins(self):
        """The writer's notes on the part that is open, each where it is now."""
        if self.card == self.WHOLE:                               # every part's notes, each moved along to where its part starts
            (plan, look, _), out, at = self.plan(), [], 0.0
            step = self.card_state()["step"]
            for p in plan:
                out += [dict(n, now=n["now"] + at) for n in notes.placed(notes.read(self.root), p["id"], p["stage"].score.turns if p["kind"] == "scene" else ())]
                at += p["frames"] / look.fps / step
            return out
        return notes.placed(notes.read(self.root), self.card or self.seg["id"], () if self.card else self.scene.turns)

    def pin(self, F, text, nid=None):
        """Drop a note at frame F, or change one's words, or (with no words) take it away."""
        if self.card == self.WHOLE:                               # the note belongs to whichever part is under the playhead
            (plan, look, _), step = self.plan(), self.card_state()["step"]
            for p in plan:
                if F < p["frames"] or p is plan[-1]:
                    steps = F / look.fps / step
                    turns = p["stage"].score.turns if p["kind"] == "scene" else ()
                    t = next((t for t in turns if t["start"] <= steps + 1e-6 < t["start"] + t["length"]), None)
                    notes.put(self.root, p["id"], steps, text, turn=t and t["id"], into=t and steps - t["start"], nid=nid)
                    break
                F -= p["frames"]
        elif self.card:
            st = self.card_state()
            notes.put(self.root, self.card, F / st["fps"] / st["step"], text, nid=nid)
        else:
            steps = F / self.stage.fps / self.scene.step
            t = next((t for t in self.scene.turns if t["start"] <= steps + 1e-6 < t["start"] + t["length"]), self.scene.turns[-1])
            notes.put(self.root, self.seg["id"], steps, text, turn=t["id"], into=steps - t["start"], nid=nid)
        self.info_rev += 1

    def state(self):
        if self.card:
            return dict(self.card_state(), notes=self.pins(), levels=self.curves())
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
                    spb=sc.grid["steps_per_beat"], scale=list(sc.grid["scale"]), lead=self.lead, notes=self.pins(), levels=self.curves(),
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

    def patch(self, ops, commit=False, ripple=False):
        """A timeline edit. While dragging it is a preview in memory; on release (`commit`) it is
        applied on top of the file as it now stands, written as hand-set values, and journaled."""
        if self.card:
            return self.card_patch(ops, commit)
        self._locked()
        if not commit:
            first, _ = apply_ops(self.root, self.path, self.seg["id"], self.doc, self.scene, ops, ripple)
            dirty = self.frame_of(first)
            self.work()
            return dirty
        before_text = self.path.read_text()
        doc = edit.yaml().load(before_text)                      # the file as it is now, not as it was when opened
        if self.clean[0] != before_text:                         # it changed underneath: work it out as it now stands
            self.clean = (before_text, Scene(self.path, script=doc, carry=self.carry).score)
        first, changes = apply_ops(self.root, self.path, self.seg["id"], doc, self.clean[1], ops, ripple)
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


BIBLE_PAGE = """<!doctype html><html><head><meta charset="utf-8"><title>{{title}}: bible</title><meta name="viewport" content="width=device-width,initial-scale=1"><style>
  :root { --bg: #0f1012; --panel: #16171b; --line: #292b30; --text: #d7dae0; --dim: #8b909a; --accent: #5e6ad2; }
  body { margin: 0; background: var(--bg); color: var(--text); font: 14px/1.6 Inter, system-ui, sans-serif; }
  main { max-width: 980px; margin: 0 auto; padding: 32px 20px 80px; }
  h1 { font-size: 26px; margin: 0 0 16px; } h2 { font-size: 18px; margin: 40px 0 10px; padding-top: 16px; border-top: 1px solid var(--line); } h3 { font-size: 15px; margin: 26px 0 8px; color: #fff; }
  p { margin: 10px 0; } a { color: #aab1ee; } code { font: 12px "JetBrains Mono", ui-monospace, Menlo, monospace; background: var(--panel); padding: 1px 5px; border-radius: 4px; }
  table { border-collapse: collapse; width: 100%; margin: 12px 0; font-size: 13px; display: block; overflow-x: auto; } th, td { text-align: left; vertical-align: top; padding: 6px 10px; border-bottom: 1px solid var(--line); }
  th { color: var(--dim); font-weight: 500; } ul, ol { padding-left: 22px; } li { margin: 3px 0; } li.task { list-style: none; margin-left: -18px; }
  main > p:first-of-type { padding: 10px 14px; border: 1px solid var(--accent); border-radius: 8px; background: #5e6ad214; } main > p:first-of-type + ul { border-left: 2px solid #e0a43a; }
  img { max-width: 100%; border-radius: 8px; border: 1px solid var(--line); margin-top: 8px; } details summary { cursor: pointer; color: var(--dim); margin: 30px 0 6px; }
</style></head><body><main>{{body}}
<details><summary title="One frame per beat, with its reason underneath. Drawn when opened; it takes a few seconds.">Storyboard</summary><img loading="lazy" alt="The episode as a storyboard" src="/storyboard.png?episode={{episode}}"></details>
</main></body></html>"""


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
                    if url.path == "/bible":                  # the show's bible, assembled now, as a page
                        return self.send(BIBLE_PAGE.replace("{{body}}", bible.to_html(bible.build(sess.root))).replace("{{title}}", str(load_yaml(sess.root / "show.yaml").get("title", "Bible")))
                                         .replace("{{episode}}", sess.seg["episode"]).encode(), "text/html; charset=utf-8")
                    if url.path == "/storyboard.png":
                        from ..presentation import readings
                        return self.send(readings.storyboard(sess.root, q.get("episode", [sess.seg["episode"]])[0]).read_bytes(), "image/png")
                    if url.path == "/levels":
                        return self.send(sess.levels())
                    if url.path == "/takes":
                        return self.send(sess.takes())
                    if url.path == "/episode":               # every part of the episode this scene is in
                        return self.send(sess.episode())
                    if url.path == "/audio":                 # only=voices|sounds|music is one layer alone
                        return self.send(sess.audio(q.get("only", [None])[0], q.get("build") == ["A"]), "audio/wav")
                    if url.path == "/wave":                  # the shape of the sound, for the lane under the timeline
                        return self.send(sess.wave(q.get("only", [None])[0]))
                    if url.path == "/video" and flag("range"):
                        return self.send(sess.ranged.read_bytes(), "video/mp4")
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
                if self.path == "/render" and (body.get("to") or sess.card):      # a marked stretch, or a card, which has no film of its own
                    with sess.lock:
                        out = sess.render_range(body.get("from", 0), body.get("to") or 10 ** 9)
                    return self.send(dict(file=str(out.relative_to(sess.root)), range=True))
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
                        out["dirty_from"] = sess.patch(body["ops"], bool(body.get("commit")), bool(body.get("ripple")))
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
                    elif self.path == "/take-back":
                        sess.take_back()
                        out["dirty_from"] = 0
                    elif self.path in ("/undo", "/redo"):
                        sess.step(self.path[1:])
                        out["dirty_from"] = 0
                    elif self.path == "/take":                # keep the show as it stands, switch to a take, or drop one
                        sess.take(body.get("save"), body.get("open"), body.get("drop"))
                        out["dirty_from"], out["takes"] = 0, sess.takes()
                    elif self.path == "/curve":               # a layer's level, bent over time
                        sess.curve(body["layer"], body.get("points") or [])
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
