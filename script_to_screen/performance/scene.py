"""Layer 3, the performance: the scene played out on the tempo grid.

The Scene is the conductor. For each turn of the script it changes the world, asks the
expression step what now shows, plans the line as syllables on the grid, and places
reactions. What it leaves behind is the score: `turns`, `keys` (what each entity shows, and
when), `lines` (bubbles and their syllables), `events` (everything that can make a sound)
and `focus` (who holds the scene). Nothing here draws or makes a sound.

All times inside `_build` are in steps; the score is in seconds.
"""
import re
from pathlib import Path

from ..script import ScriptError, Show, find_root, load_yaml, scene_key, scene_paths
from ..world import World
from . import speech
from .expression import observe


def carry_into(path, root, lib=None):
    """What every entity brings into this scene: the end state of all the scenes before it."""
    carry = {}
    for p in scene_paths(root):
        if p == path:
            break
        carry = Scene(p, lib=lib, carry=carry).carry_out
    return carry


class Scene:
    def __init__(self, path, script=None, lib=None, carry=None):
        self.path = Path(path).resolve()
        self.root = find_root(self.path)
        carry = carry_into(self.path, self.root, lib) if carry is None else carry
        self.show = Show(self.root, lib)
        cfg = self.show.cfg
        self.W, self.H, self.fps = cfg["width"], cfg["height"], cfg["fps"]
        self.key = scene_key(self.path, self.root)
        self.script = script if script is not None else load_yaml(self.path)
        self.title = str(self.script.get("scene", self.path.stem))
        self.tempo = float(self.script.get("tempo", cfg["tempo"]))
        self.step = 60.0 / self.tempo / cfg["steps_per_beat"]          # seconds per step
        self.problems, self.keys, self.turns, self.lines, self.events = [], {}, [], [], []
        self.focus, self.quiet = [], set()       # featured reactions (start, end, who); background ones (time, who)
        self.world = World(self.show, self.key, carry, self.flag)
        self.carry, self.ents = self.world.carry, self.world.ents
        self._build()

    def flag(self, level, turn, msg):
        self.problems.append(dict(level=level, turn=turn, msg=msg))

    def _observe(self, tid):
        return observe(self.world.st, self.ents, self.show.cfg["gain"], self.flag, tid)

    # ---- the script, turn by turn (all times here are in steps) --------------------------------
    def _build(self):
        T, t0, sec = self.show.cfg["timing"], 0.0, self.step
        world = self.world
        st, need = world.st, world.need
        self.carried = {e: v["felt"] for e, v in self.carry.items() if v.get("felt")}   # as the last scene left it
        self.offscreen = []
        for ev in self.script.get("offscreen") or []:       # what happened between scenes, unseen
            if not str(ev.get("why") or "").strip():
                self.flag("error", None, "an `offscreen` event has no `why`")
            world.offscreen(ev)
            self.offscreen.append(str(ev.get("why") or ""))
        for i, raw in enumerate(self.script.get("turns") or []):
            tid = raw.get("id", i + 1)
            if not str(raw.get("why") or "").strip():
                self.flag("error", tid, "no `why`: every turn must say why it happens")
            who, say = raw.get("who"), raw.get("say") or raw.get("sing")      # `sing:` is a line that is sung
            bubbles = []
            world.cause = tid
            world.drop_takes()                       # a background take ends with the turn it happened in
            for e, spec in (raw.get("enter") or {}).items():
                world.enter(e, spec)
                self.keys.setdefault(e, [])
            for e in raw.get("exit") or []:
                world.exit(e)
            for e, v in (raw.get("side") or {}).items():
                world.side(e, v)
            for e, v in (raw.get("status") or {}).items():
                world.status(e, v)
            for e, spec in (raw.get("do") or {}).items():
                world.do(e, spec)

            def feel(e, f, who=who):
                world.feel(e, f, who)

            # the speaker's own feeling colours the line; everyone else reacts once it has landed
            late = {}
            for e, f in (raw.get("feel") or {}).items():
                if say and e != who:
                    late[e] = f
                else:
                    feel(e, f)
            a = self._observe(tid)
            pause, hold = float(raw.get("pause", T["pause"])), float(raw.get("hold", T["hold"]))
            say_at = reveal = react = 0.0
            line, sylls = None, []
            if say:
                if who not in st:
                    raise ScriptError(f"turn {tid}: a line needs `who` to be an entity in the scene")
                tone = a[who]["tone"] or raw.get("tone", "neutral")
                if tone not in self.show.tones:
                    self.flag("error", tid, f"unknown tone '{tone}'")
                    tone = "neutral"
                # One bubble holds one beat, and a pause is what separates beats. A line breaks into
                # bubbles wherever the speaker pauses for `bubble_break` steps or more (a full stop
                # does; a comma does not). A list (say: [Ha, ha, ha]) breaks exactly where it says.
                parts = [str(x) for x in say] if isinstance(say, (list, tuple)) else None
                say = " ".join(parts) if parts else str(say)
                cuts, k = set(), 0
                for part in parts or []:
                    k += len(speech.syllables(part))
                    cuts.add(k)
                n = len(speech.syllables(say))
                rhythm, melody, stress = raw.get("rhythm"), raw.get("melody"), raw.get("stress")
                for name, v in (("rhythm", rhythm), ("melody", melody), ("stress", stress)):
                    if v is not None and len(v) != n:
                        self.flag("error", tid, f"`{name}` has {len(v)} entries but the line has {n} syllables")
                rhythm = list(rhythm) if rhythm is not None and len(rhythm) == n else None
                melody = list(melody) if melody is not None and len(melody) == n else None
                stress = list(stress) if stress is not None and len(stress) == n else None
                gap = float(T.get("bubble_break", 2))
                sylls = speech.plan(say, self.show.tones[tone], self.show.cfg["scale"], rhythm, melody, stress, cuts, gap)
                say_at = pause + a[who]["latency"]
                reveal = sum(s["len"] for s in sylls)
                react = say_at + reveal
                b = 0
                for k, s in enumerate(sylls):
                    s["bubble"] = b
                    ends = (k + 1) in cuts if parts else s["rest"] >= gap
                    if ends and k < len(sylls) - 1:
                        b += 1
                span = (min(s["semi"] for s in sylls), max(s["semi"] for s in sylls))
                line = dict(text="".join(s["text"] for s in sylls), tone=tone, sung="sing" in raw)
                bubbles = [dict(who=who, tone=tone, sung="sing" in raw, range=span,
                                text="".join(s["text"] for s in sylls if s["bubble"] == g).strip(),
                                sylls=[dict(text=s["text"], start=(t0 + say_at + s["at"]) * sec, dur=s["len"] * sec,
                                            voiced=(s["len"] - s["rest"]) * sec, semi=s["semi"], stress=s["stress"])
                                       for s in sylls if s["bubble"] == g]) for g in range(b + 1)]
            # Everything that changes after the turn opens, on one timeline (steps from the turn's start).
            ops = []
            if late:
                ops.append((react, lambda late=late: [feel(e, f) for e, f in late.items()]))
            cursor, reacts = (react if say else float(T["settle"])), []
            for j, r in enumerate(raw.get("react") or []):
                e = r["who"]
                need(e)

                def apply(r=r, e=e):
                    if "feel" in r:
                        feel(e, r["feel"])
                    if "do" in r:                            # a take: it lasts for the moment, then is dropped
                        world.take(e, r["do"], keep=bool(r.get("keep")))

                if "beat" in r:                              # featured: the reaction takes the floor and the scene waits
                    n = float(r["beat"])
                    ops.append((cursor, apply))
                    if "do" in r and not r.get("keep"):
                        ops.append((cursor + n, lambda e=e: world.drop_take(e)))
                    self.focus.append(((t0 + cursor) * sec, (t0 + cursor + n) * sec, e))
                    self.events.append(((t0 + cursor) * sec, "beat", e))
                    reacts.append(dict(who=e, at=cursor, beat=n, index=j, on=None))
                    cursor += n
                else:                                        # background: it happens inside the line and takes no time
                    on = r.get("word", r.get("syllable"))    # (not `on:`, which YAML reads as the word "true")
                    at = self._trigger(on, sylls, say_at, tid) + float(self.ents[e].get("reflex", 0))
                    ops.append((at, apply))
                    self.quiet.add((round((t0 + at) * sec, 4), e))
                    reacts.append(dict(who=e, at=at, beat=0, index=j, on=on))
            length = max([cursor] + [at for at, _ in ops]) + hold
            snaps = [(0.0, a)]
            for at in sorted({at for at, _ in ops}):
                for when, fn in ops:
                    if when == at:
                        fn()
                snap = (at, self._observe(tid))
                if at == 0:
                    snaps[0] = snap
                else:
                    snaps.append(snap)
            for at, obs in snaps:
                for e, o in obs.items():
                    self.keys[e].append(((t0 + at) * sec, o))
            if line:
                for g, bub in enumerate(bubbles):            # each bubble gives way to the next
                    bub["start"] = bub["sylls"][0]["start"]
                    bub["end"] = bubbles[g + 1]["sylls"][0]["start"] if g + 1 < len(bubbles) else (t0 + length) * sec
                    if g + 1 == len(bubbles) and any(r["beat"] for r in reacts):     # a featured reaction is a new moment
                        bub["end"] = (t0 + min(r["at"] for r in reacts if r["beat"])) * sec
                    self.lines.append(bub)
                    self.events.append((bub["start"], "bubble", who))
            for fx in raw.get("sfx") or []:          # explicit sounds: [{at: steps, sound: name}]
                self.events.append(((t0 + float(fx.get("at", 0))) * sec, str(fx["sound"]), None))
            self.turns.append(dict(id=tid, index=i, start=t0, length=length, who=who, why=str(raw.get("why") or ""),
                                   pause=pause, hold=hold, latency=a[who]["latency"] if say else 0, say_at=say_at,
                                   reveal=reveal, react=react if late else 0, line=line, sylls=sylls,
                                   rhythm=raw.get("rhythm"), melody=raw.get("melody"), stress=raw.get("stress"),
                                   relies_on=raw.get("relies_on") or {},
                                   reacts=reacts,
                                   info=[(at, {e: o["info"] for e, o in obs.items()}) for at, obs in snaps]))
            t0 += length
        if not self.turns:
            raise ScriptError("the scene has no turns")
        self.carry_out = world.carry_out()
        self.steps = t0
        self.dur = t0 * sec
        self.total = max(1, round(self.dur * self.fps))
        # every visible change is also an event that can make a sound
        for e, ks in self.keys.items():
            prev = None
            for t, o in ks:
                if prev is None or o["alpha"] != prev["alpha"]:
                    if (prev is not None or o["alpha"]) and t > 1e-9:     # already there when a scene opens: no sound
                        self.events.append((t, "enter" if o["alpha"] else "exit", e))
                elif o["alpha"]:
                    turned = o["facing"] != prev["facing"]
                    if o["slot"] != prev["slot"]:
                        self.events.append((t, "move", e))
                    if turned:
                        self.events.append((t, "turn", e))
                    elif (o["lx"], o["ly"]) != (prev["lx"], prev["ly"]):
                        self.events.append((t, "look", e))
                    if (o["sx"], o["sy"], o["lean"]) != (prev["sx"], prev["sy"], prev["lean"]):
                        self.events.append((t, "posture", e))
                    f0, f1 = prev["info"], o["info"]
                    if f1["felt"] and (f1["felt"], f1["intensity"]) != (f0["felt"], f0["intensity"]):
                        self.events.append((t, "feel." + f1["felt"], e))
                prev = o
        aside = float(self.show.feel["aside_volume"])            # background reactions are quieter
        self.events = sorted(((t, n, e, aside if (round(t, 4), e) in self.quiet else 1.0) for t, n, e in self.events),
                             key=lambda ev: ev[0])

    def _trigger(self, on, sylls, say_at, tid):
        """When a background reaction fires, in steps from the turn's start: on a word of the line
        (`word: dumpling`), on a syllable by number (`syllable: 3`), or, with neither, as the line ends."""
        end = say_at + sum(s["len"] for s in sylls)
        if on is None or not sylls:
            return end
        if isinstance(on, int):
            if 1 <= on <= len(sylls):
                return say_at + sylls[on - 1]["at"]
        else:
            first, word = 0, ""
            for k, s in enumerate(sylls):
                word += s["text"]
                if s["text"].endswith(" ") or k == len(sylls) - 1:
                    if re.sub(r"[^a-z']", "", word.lower()) == re.sub(r"[^a-z']", "", str(on).lower()):
                        return say_at + sylls[first]["at"]
                    first, word = k + 1, ""
        self.flag("error", tid, f"a reaction is set to fire on '{on}', which is not in the line")
        return end

    # ---- reading it back (times in seconds) ----------------------------------------------------
    def turn_at(self, t):
        s = t / self.step
        for turn in self.turns:
            if turn["start"] <= s < turn["start"] + turn["length"]:
                return turn
        return self.turns[-1]

    def line_at(self, t):
        for ln in self.lines:
            if ln["start"] <= t < ln["end"]:
                return ln
        return None
