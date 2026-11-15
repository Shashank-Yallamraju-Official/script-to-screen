"""The turn-based model. Script + entity files -> what an observer can see at every frame.

Three layers, none of which draws anything:
  felt state   what an entity feels (emotion + intensity), written per turn, shared vocabulary
  tells        each entity's own ordered list of how an emotion leaks out
  position     side and status in the room decide how far the valve opens (gain)
Deliberate actions (`do`) set the baseline; tells are laid over it.
"""
import math
from pathlib import Path

import yaml

from . import speech

SLOTS = 9                                   # the stage is one line of nine places
ZONES = {"intimate": 1, "personal": 2, "social": 3, "public": 4}   # distance in slots
POSTURE = {"upright": (1.0, 1.0, 0), "contracted": (1.12, 0.8, 0), "lean_in": (1.0, 1.0, 1), "lean_back": (1.0, 1.0, -1)}
NUMERIC = ("slot", "facing", "lx", "ly", "sx", "sy", "lean", "alpha")
TELL_KEYS = {"attention", "orient", "distance", "posture", "tone", "latency"}


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


def sgn(v):
    return (v > 0) - (v < 0)


def smooth(k):
    k = max(0.0, min(1.0, k))
    return k * k * (3 - 2 * k)


class Show:
    def __init__(self, root):
        self.root = root
        self.cfg = load_yaml(root / "show.yaml")
        self.tones = load_yaml(root / "library/tones.yaml")
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
    def __init__(self, path, script=None):
        self.path = Path(path).resolve()
        self.root = find_root(self.path)
        self.show = Show(self.root)
        cfg = self.show.cfg
        self.W, self.H, self.fps = cfg["width"], cfg["height"], cfg["fps"]
        self.key = self.path.relative_to(self.root / "episodes").with_suffix("").as_posix()
        self.script = script if script is not None else load_yaml(self.path)
        self.title = str(self.script.get("scene", self.path.stem))
        self.problems, self.ents, self.keys, self.turns, self.lines = [], {}, {}, [], []
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
            slot, src = s["slot"], info["at"]
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
            o = s["orient"]
            facing = 0 if o == "out" else -toward(e, o["away"]) if isinstance(o, dict) else toward(e, o)
            if "orient" in expr:
                facing = {"out": 0, "toward": toward(e, src), "away": -toward(e, src)}[expr["orient"]]
            a = expr.get("attention", s["attention"])
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
            sx, sy, lean = POSTURE[expr.get("posture", s["posture"])]
            lean *= (toward(e, src) or facing) if "posture" in expr else facing
            obs[e] = dict(slot=slots[e], facing=facing, lx=lx, ly=ly, sx=sx, sy=sy, lean=lean,
                          alpha=1.0 if s["present"] else 0.0, tone=expr.get("tone"),
                          latency=expr.get("latency", 0), info=info)
        return obs

    # ---- the script, turn by turn -------------------------------------------------------------
    def _build(self):
        T, st, t0 = self.show.cfg["timing"], {}, 0
        for i, raw in enumerate(self.script.get("turns") or []):
            tid = raw.get("id", i + 1)
            if not str(raw.get("why") or "").strip():
                self.flag("error", tid, "no `why`: every turn must say why it happens")
            who, say = raw.get("who"), raw.get("say")
            for e, spec in (raw.get("enter") or {}).items():
                self.ents[e] = self.show.entity(e, self.key)
                self.keys.setdefault(e, [])
                st[e] = dict(present=True, slot=spec["slot"], orient=spec.get("orient", "out"),
                             attention=spec.get("attention", "ahead"), posture=spec.get("posture", "upright"),
                             side=None, status=self.ents[e].get("status", 1), felt=None)

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
            pause, hold, say_at, reveal, react = int(raw.get("pause", T["pause"])), int(raw.get("hold", T["hold"])), 0, 0, 0
            line = None
            if say:
                if who not in st:
                    raise ScriptError(f"turn {tid}: `say` needs `who` to be an entity in the scene")
                tone = a[who]["tone"] or raw.get("tone", "neutral")
                if tone not in self.show.tones:
                    self.flag("error", tid, f"unknown tone '{tone}'")
                    tone = "neutral"
                times, dur = speech.schedule(str(say), self.show.tones[tone]["cps"], self.fps)
                say_at, reveal = pause + a[who]["latency"], math.ceil(dur)
                react = say_at + reveal
                line = dict(who=who, text=str(say), tone=tone, start=t0 + say_at, times=times, reveal=reveal)
            length = (react if say else T["settle"]) + hold
            for e, o in a.items():
                self.keys[e].append((t0, o))
            b = a
            if late:
                for e, f in late.items():
                    feel(e, f)
                b = self._observe(st, tid)
                for e, o in b.items():
                    self.keys[e].append((t0 + react, o))
            if line:
                line["end"] = t0 + length
                self.lines.append(line)
            self.turns.append(dict(id=tid, index=i, start=t0, length=length, who=who, why=str(raw.get("why") or ""),
                                   pause=pause, hold=hold, latency=a[who]["latency"] if say else 0, say_at=say_at,
                                   reveal=reveal, react=react if late else 0, line=line,
                                   relies_on=raw.get("relies_on") or {},
                                   info=[(0, {e: o["info"] for e, o in a.items()})] +
                                        ([(react, {e: o["info"] for e, o in b.items()})] if late else [])))
            t0 += length
        self.total = t0
        if not self.turns:
            raise ScriptError("the scene has no turns")

    # ---- reading it back ----------------------------------------------------------------------
    def turn_at(self, F):
        for t in self.turns:
            if t["start"] <= F < t["start"] + t["length"]:
                return t
        return self.turns[-1]

    def line_at(self, F):
        for ln in self.lines:
            if ln["start"] <= F < ln["end"]:
                return ln
        return None

    def state(self, e, F):
        """What entity e looks like at frame F, easing from its previous snapshot."""
        ks = self.keys[e]
        idx = max((i for i, (f, _) in enumerate(ks) if f <= F), default=None)
        if idx is None:
            return None
        f1, cur = ks[idx]
        prev = ks[idx - 1][1] if idx else dict(cur, alpha=0.0) if f1 else cur     # already there when a scene opens
        k = smooth((F - f1) / self.show.cfg["timing"]["ease"])
        out = dict(cur)
        for n in NUMERIC:
            out[n] = prev[n] + (cur[n] - prev[n]) * k
        return out
