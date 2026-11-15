"""The turn-based model. Script + entity files -> what an observer can see and hear at any moment.

Three layers, none of which draws anything:
  felt state   what an entity feels (emotion + intensity), written per turn, shared vocabulary
  tells        each entity's own ordered list of how an emotion leaks out
  position     side and status in the room decide how far the valve opens (gain)
Deliberate actions (`do`) set the baseline; tells are laid over it.

Time is counted in steps of the tempo grid (a sixteenth note by default), so every pause,
hold and syllable lands on the beat unless it is deliberately nudged off it.

Scenes are read in path order (episodes/<season>/<episode>/<scene>.yaml). What an entity
feels and its standing carry from the end of one scene into the next; nothing resets unless
the next scene says what happened `offscreen`.
"""
import math
import re
from pathlib import Path

import yaml

from . import speech

SLOTS = 9                                   # the stage is one line of nine places
ZONES = {"intimate": 1, "personal": 2, "social": 3, "public": 4}   # distance in slots
POSTURE = {"upright": (1.0, 1.0, 0), "contracted": (1.12, 0.8, 0), "lean_in": (1.0, 1.0, 1), "lean_back": (1.0, 1.0, -1)}
TELL_KEYS = {"attention", "orient", "distance", "posture", "tone", "latency"}
LIBRARY = ("tones", "sounds", "feel")
SCHEMA = 1                                  # the file format this engine reads; see docs/architecture.md


class ScriptError(Exception):
    pass


def load_yaml(p):
    with open(p) as fh:
        return yaml.safe_load(fh)


def find_root(path):
    path = Path(path).resolve()
    for p in [path] + list(path.parents):
        if (p / "show.yaml").exists():
            return p
    raise ScriptError("no show.yaml above " + str(path))


def scene_paths(root):
    return sorted((Path(root) / "episodes").rglob("*.yaml"))


def carry_into(path, root, lib=None):
    """What every entity brings into this scene: the end state of all the scenes before it."""
    carry = {}
    for p in scene_paths(root):
        if p == path:
            break
        carry = Scene(p, lib=lib, carry=carry).carry_out
    return carry


def sgn(v):
    return (v > 0) - (v < 0)


def smooth(k):
    k = max(0.0, min(1.0, k))
    return k * k * (3 - 2 * k)


def back(k, amount):
    """Ease out that swings past its mark by `amount` and settles."""
    k, c = max(0.0, min(1.0, k)), 1.70158 * amount
    return 1 + (c + 1) * (k - 1) ** 3 + c * (k - 1) ** 2


class Show:
    def __init__(self, root, lib=None):
        self.root = root
        self.cfg = load_yaml(root / "show.yaml")
        if self.cfg.get("schema", SCHEMA) != SCHEMA:
            raise ScriptError(f"this show is written for schema {self.cfg['schema']}, and this engine reads schema {SCHEMA}")
        for name in LIBRARY:                 # the editor passes its unsaved copies in `lib`
            setattr(self, name, (lib or {}).get(name) or load_yaml(root / "library" / f"{name}.yaml"))
        self.emotions = self.cfg["emotions"]

    def entity(self, eid, scene_key):
        p = self.root / "entities" / f"{eid}.yaml"
        if not p.exists():
            raise ScriptError(f"no entity file entities/{eid}.yaml")
        ent = load_yaml(p)
        ent["id"] = eid
        tells = dict(ent.get("tells") or {})
        for step in ent.get("arc") or []:          # the slow clock: the map itself changes
            if str(step["from"]) <= scene_key:
                tells.update(step.get("tells") or {})
        ent["tells"] = tells
        return ent


class Scene:
    def __init__(self, path, script=None, lib=None, carry=None):
        self.path = Path(path).resolve()
        self.root = find_root(self.path)
        carry = carry_into(self.path, self.root, lib) if carry is None else carry
        self.carry = {e: dict(v) for e, v in carry.items()}
        self.show = Show(self.root, lib)
        cfg = self.show.cfg
        self.W, self.H, self.fps = cfg["width"], cfg["height"], cfg["fps"]
        self.key = self.path.relative_to(self.root / "episodes").with_suffix("").as_posix()
        self.script = script if script is not None else load_yaml(self.path)
        self.title = str(self.script.get("scene", self.path.stem))
        self.tempo = float(self.script.get("tempo", cfg["tempo"]))
        self.step = 60.0 / self.tempo / cfg["steps_per_beat"]          # seconds per step
        self.problems, self.ents, self.keys, self.turns, self.lines, self.events = [], {}, {}, [], [], []
        self.focus, self.quiet = [], set()       # featured reactions (start, end, who); background ones (time, who)
        self._build()

    def flag(self, level, turn, msg):
        self.problems.append(dict(level=level, turn=turn, msg=msg))

    # ---- one snapshot: persistent state -> what shows -----------------------------------------
    def _observe(self, st, tid):
        gcfg = self.show.cfg["gain"]
        present = [e for e in st if st[e]["present"]]
        sided = [e for e in present if st[e]["side"]]
        sides = {st[e]["side"] for e in sided}
        total = sum(st[e]["status"] for e in sided) or 1
        out = {}
        for e, s in st.items():
            info = dict(side=s["side"], status=s["status"], weight=None, gain=1.0, klass="unopposed",
                        mine=1, others=0, felt=None, intensity=0, level=0, at=None)
            if s["side"] and len(sides) > 1 and s["present"]:
                mine = [x for x in sided if st[x]["side"] == s["side"]]
                info["mine"], info["others"] = len(mine), len(sided) - len(mine)
                info["weight"] = sum(st[x]["status"] for x in mine) / total
                info["gain"] = max(gcfg["min"], min(gcfg["max"], gcfg["slope"] * info["weight"]))
                info["klass"] = ("alone" if len(mine) == 1 and info["others"] > 1 else
                                 "minority" if len(mine) < info["others"] else
                                 "majority" if len(mine) > info["others"] else "even")
            expr = {}
            if s["felt"] and s["present"]:
                emo, inten, at = s["felt"]
                info.update(felt=emo, intensity=inten, at=at)
                tells = self.ents[e]["tells"].get(emo)
                if tells is None:
                    self.flag("error", tid, f"{e} feels {emo} but entities/{e}.yaml has no tell for it")
                else:
                    info["level"] = max(0, min(len(tells), int(inten * info["gain"] + 0.5)))
                    for tell in tells[:info["level"]]:
                        for k, v in tell.items():
                            if k not in TELL_KEYS:
                                self.flag("error", tid, f"{e}: unknown tell channel '{k}'")
                            expr[k] = expr.get(k, 0) + v if k == "distance" else v
            out[e] = (info, expr)

        # where everyone stands: baseline slot plus any approach/retreat the feeling causes
        slots = {}
        for e, s in st.items():
            info, expr = out[e]
            slot, src = (s.get("take") or {}).get("slot", s["slot"]), info["at"]
            if expr.get("distance") and src in st and src != e:
                away = sgn(slot - st[src]["slot"]) or 1
                slot = max(0, min(SLOTS - 1, slot + expr["distance"] * away))
                slot = max(slot, st[src]["slot"] + 1) if away > 0 else min(slot, st[src]["slot"] - 1)
            slots[e] = slot

        def toward(e, other):
            return (sgn(slots[other] - slots[e]) or 1) if other in slots and other != e else 0

        obs = {}
        for e, s in st.items():
            info, expr = out[e]
            src = info["at"]
            # body orientation: -1 faces left, 0 faces out to the viewer, 1 faces right
            take = s.get("take") or {}               # a deliberate momentary action outranks the tells
            o = take.get("orient", s["orient"])
            facing = 0 if o == "out" else -toward(e, o["away"]) if isinstance(o, dict) else toward(e, o)
            if "orient" in expr and "orient" not in take:
                facing = {"out": 0, "toward": toward(e, src), "away": -toward(e, src)}[expr["orient"]]
            a = take["attention"] if "attention" in take else expr.get("attention", s["attention"])
            if a == "ahead":
                lx, ly = facing, 0
            elif a == "down":
                lx, ly = facing * 0.3, 1
            elif a == "up":
                lx, ly = 0, -1
            elif a == "viewer":
                lx, ly = 0, 0
            elif a == "source":
                lx, ly = toward(e, src), 0
            elif a == "away":
                lx, ly = -toward(e, src) or -facing, 0
            elif isinstance(a, dict):
                lx, ly = -toward(e, a["away"]), 0
            else:
                lx, ly = toward(e, a), 0
            sx, sy, lean = POSTURE[take.get("posture") or expr.get("posture", s["posture"])]
            lean *= (toward(e, src) or facing) if "posture" in expr and "posture" not in take else facing
            obs[e] = dict(slot=slots[e], facing=facing, lx=lx, ly=ly, sx=sx, sy=sy, lean=lean,
                          alpha=1.0 if s["present"] else 0.0, tone=expr.get("tone"),
                          latency=expr.get("latency", 0), info=info)
        return obs

    # ---- the script, turn by turn (all times here are in steps) --------------------------------
    def _build(self):
        T, st, t0, sec = self.show.cfg["timing"], {}, 0.0, self.step
        self.carried = {e: v["felt"] for e, v in self.carry.items() if v.get("felt")}   # as the last scene left it
        self.offscreen = []
        for ev in self.script.get("offscreen") or []:       # what happened between scenes, unseen
            if not str(ev.get("why") or "").strip():
                self.flag("error", None, "an `offscreen` event has no `why`")
            for e, f in (ev.get("feel") or {}).items():
                felt = None
                if f not in (None, "calm"):
                    emo = next(k for k in f if k != "at")
                    if emo not in self.show.emotions:
                        self.flag("error", None, f"offscreen: '{emo}' is not in the show's emotion list")
                    felt = (emo, f[emo], f.get("at"))
                self.carry.setdefault(e, {})["felt"] = felt
            for e, v in (ev.get("status") or {}).items():
                self.carry.setdefault(e, {})["status"] = v
            self.offscreen.append(str(ev.get("why") or ""))
        for i, raw in enumerate(self.script.get("turns") or []):
            tid = raw.get("id", i + 1)
            if not str(raw.get("why") or "").strip():
                self.flag("error", tid, "no `why`: every turn must say why it happens")
            who, say = raw.get("who"), raw.get("say") or raw.get("sing")      # `sing:` is a line that is sung
            bubbles = []
            for s in st.values():
                s.pop("take", None)                  # a background take ends with the turn it happened in
            for e, spec in (raw.get("enter") or {}).items():
                self.ents[e] = self.show.entity(e, self.key)
                self.keys.setdefault(e, [])
                st[e] = dict(present=True, slot=spec["slot"], orient=spec.get("orient", "out"),
                             attention=spec.get("attention", "ahead"), posture=spec.get("posture", "upright"),
                             side=None, status=self.carry.get(e, {}).get("status", self.ents[e].get("status", 1)),
                             felt=self.carry.get(e, {}).get("felt"))

            def need(e):
                if e not in st:
                    raise ScriptError(f"turn {tid}: '{e}' has not entered the scene")
                return st[e]

            for e in raw.get("exit") or []:
                need(e)["present"] = False
            for e, v in (raw.get("side") or {}).items():
                need(e)["side"] = v
            for e, v in (raw.get("status") or {}).items():
                need(e)["status"] = v
            for e, spec in (raw.get("do") or {}).items():
                s = need(e)
                for k in ("slot", "orient", "attention", "posture"):
                    if k in spec:
                        s[k] = spec[k]
                if "move" in spec:                   # {toward: other, zone: personal}
                    other = need(spec["move"]["toward"])
                    side = sgn(s["slot"] - other["slot"]) or -1
                    s["slot"] = max(0, min(SLOTS - 1, other["slot"] + side * ZONES[spec["move"]["zone"]]))

            def feel(e, f):
                s = need(e)
                if f in (None, "calm"):
                    s["felt"] = None
                    return
                emo = next(k for k in f if k != "at")
                if emo not in self.show.emotions:
                    self.flag("error", tid, f"'{emo}' is not in the show's emotion list")
                s["felt"] = (emo, f[emo], f.get("at", who if who != e else None))

            # the speaker's own feeling colours the line; everyone else reacts once it has landed
            late = {}
            for e, f in (raw.get("feel") or {}).items():
                if say and e != who:
                    late[e] = f
                else:
                    feel(e, f)
            a = self._observe(st, tid)
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
                        st[e].update(r["do"]) if r.get("keep") else st[e].__setitem__("take", dict(r["do"]))

                if "beat" in r:                              # featured: the reaction takes the floor and the scene waits
                    n = float(r["beat"])
                    ops.append((cursor, apply))
                    if "do" in r and not r.get("keep"):
                        ops.append((cursor + n, lambda e=e: st[e].pop("take", None)))
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
                snap = (at, self._observe(st, tid))
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
        self.carry_out = dict(self.carry)                    # entities not in this scene pass through untouched
        for e, s in st.items():
            self.carry_out[e] = dict(felt=s["felt"], status=s["status"])
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

    def state(self, e, t):
        """What entity e looks like at time t, easing from its previous snapshot."""
        ks, feel = self.keys[e], self.show.feel
        idx = max((i for i, (kt, _) in enumerate(ks) if kt <= t + 1e-9), default=None)
        if idx is None:
            return None
        t1, cur = ks[idx]
        prev = ks[idx - 1][1] if idx else dict(cur, alpha=0.0) if t1 > 1e-9 else cur   # already there when a scene opens
        u = max(0.0, min(1.0, (t - t1) / max(float(feel["ease"]), 1e-3)))
        soft, swing = smooth(u), back(u, float(feel["overshoot"]))
        out = dict(cur)
        for n in ("facing", "lx", "ly", "alpha"):
            out[n] = prev[n] + (cur[n] - prev[n]) * soft
        for n in ("slot", "sx", "sy", "lean"):
            out[n] = prev[n] + (cur[n] - prev[n]) * swing
        pulse = math.sin(math.pi * u) if u < 1 else 0.0
        out["flip"] = pulse if cur["facing"] != prev["facing"] else 0.0       # mid-turn, thin as paper
        out["travel"] = pulse if cur["slot"] != prev["slot"] else 0.0         # stretched while moving
        return out
