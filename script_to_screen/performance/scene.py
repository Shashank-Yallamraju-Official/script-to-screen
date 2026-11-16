"""Layer 3, the performance: the scene played out on the tempo grid.

The Scene is the conductor. For each turn of the script it changes the world, asks the
expression step what now shows, plans the line as syllables on the grid, and places
reactions. What it leaves behind is the score (see score.py), which is all that drawing,
sound, the ledger and the editor are given. Nothing here draws or makes a sound.

All times inside `_build` are in steps; the score is in seconds.
"""
import re
from pathlib import Path

from ..script import ScriptError, Show, find_root, load_yaml, place, scene_key, scene_paths, things, tuning
from ..world import World
from . import appraisal, camera, drama, placing, scoring, speech
from .expression import observe
from .score import Score


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
        self.key = scene_key(self.path, self.root)
        self.script = script if script is not None else load_yaml(self.path)
        self.title = str(self.script.get("scene", self.path.stem))
        self.tempo = float(self.script.get("tempo", cfg["tempo"]))
        self.step = 60.0 / self.tempo / cfg["steps_per_beat"]          # seconds per step
        self.problems, self.keys, self.turns, self.lines, self.events = [], {}, [], [], []
        self.focus, self.quiet = [], set()       # featured reactions (start, end, who); background ones (time, who)
        self.world = World(self.show, self.key, carry, self.flag)
        if self.script.get("place"):                         # what in the place can be named, faced and cared about
            self.world.things = things(place(self.root, str(self.script["place"])))
            clash = set(self.world.things) & self.world.known
            if clash:
                raise ScriptError(f"the place has a piece called '{sorted(clash)[0]}', which is also an entity; give the piece another `id:`")
        self.carry, self.ents = self.world.carry, self.world.ents
        self._score = None
        self._build()

    def flag(self, level, turn, msg):
        self.problems.append(dict(level=level, turn=turn, msg=msg))

    def _observe(self, tid):
        return observe(self.world.st, self.ents, self.show.cfg["gain"], self.flag, tid, self.world.things)

    # ---- the script, turn by turn (all times here are in steps) --------------------------------
    def _build(self):
        T, t0, sec = self.show.cfg["timing"], 0.0, self.step
        world = self.world
        st, need = world.st, world.need
        self.carried = {e: v["felt"] for e, v in self.carry.items() if v.get("felt")}   # as the last scene left it
        self.offscreen = []
        self.facts = {k: dict(doer=v.get("doer"), knows=list(v.get("knows") or [])) for k, v in (self.script.get("facts") or {}).items()}
        for e, r in (self.script.get("regards") or {}).items():       # what things mean to people as the scene opens
            for thing, f in r.items():
                world.regard(e, thing, f)
        for ev in self.script.get("offscreen") or []:       # what happened between scenes, unseen
            if not str(ev.get("why") or "").strip():
                self.flag("error", None, "an `offscreen` event has no `why`")
            if ev.get("event"):                              # an event nobody saw: those with a stake in it carry what it made them feel
                events = self._events(ev["event"], None)
                involved = [e for x in events for e in appraisal._targets(x) + [x.get("by")] if e]
                felt = self._appraise(events, list(dict.fromkeys(involved)), None)
                ev = dict(ev, feel={**{e: v["feel"] for e, v in felt.items()}, **(ev.get("feel") or {})})
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
            entering = raw.get("enter") or {}
            entering = {e: {} for e in entering} if isinstance(entering, list) else entering
            for e, spec in entering.items():
                spec = dict(spec or {})
                src = spec.pop("from", None)
                if "slot" not in spec:                       # not written: they stand where what they care about puts them, or come in by the door
                    sheet = self.show.entity(e, self.key)
                    taken = {x: y["slot"] for x, y in st.items() if y["present"]}
                    try:
                        if i == 0 and src is None:
                            spec["slot"], drew, why = placing.found(e, sheet, taken, world.things, sheet.get("bonds") or {}, self.show.cfg.get("valence"),
                                                                    world.regards.get(e))
                            if drew and "orient" not in spec:
                                spec["orient"] = drew        # and they face what drew them
                        else:
                            spec["slot"], why = placing.arrives(e, dict(spec, **({"from": src} if src else {})), taken, world.things)
                    except ValueError as err:
                        raise ScriptError(f"turn {tid}: {e} cannot enter: {err}")
                    world.cause = tid
                    world._note("placed", e, f"slot {spec['slot']}: {why}")
                world.enter(e, spec)
                self.keys.setdefault(e, [])
            for e in raw.get("exit") or []:
                world.exit(e)
            for e, v in (raw.get("side") or {}).items():
                world.side(e, v)
            for e, v in (raw.get("status") or {}).items():
                world.status(e, v)
            for e, v in (raw.get("sympathy") or {}).items():
                world.sympathy(e, v)
            for e, spec in (raw.get("do") or {}).items():
                world.do(e, spec)

            def feel(e, f, who=who):
                world.feel(e, f, who)

            for e, r in (raw.get("regard") or {}).items():       # a thing comes to mean something to someone, from now on
                for thing, f in r.items():
                    world.regard(e, thing, f)
            # what the turn's events make everyone feel; a feeling written on the turn wins over the one worked out
            appraised = {}
            if raw.get("event"):
                events = self._events(raw["event"], tid)
                appraised = self._appraise(events, [e for e, x in st.items() if x["present"]], tid)
                for x in events:
                    if x.get("reveals") and x.get("fact") in self.facts:          # now everyone in the room knows
                        self.facts[x["fact"]]["knows"] = sorted(set(self.facts[x["fact"]]["knows"]) | {e for e, y in st.items() if y["present"]})
                written = set(raw.get("feel") or {}) | {r["who"] for r in raw.get("react") or [] if "feel" in r}
                reacts_to = [r for r in raw.get("react") or [] if "feel" not in r and "do" not in r]
                for r in reacts_to:                          # a reaction with nothing written takes the feeling worked out for it
                    if r["who"] in appraised:
                        r["feel"] = appraised[r["who"]]["feel"]
                raw = dict(raw, feel={**{e: v["feel"] for e, v in appraised.items() if e not in written and e not in {r["who"] for r in reacts_to}},
                                      **(raw.get("feel") or {})})

            # A thing that means something to someone brings that feeling up when a line names it, or when anyone turns to it,
            # looks at it or walks to it. Whatever the turn already makes them feel wins.
            fired = {}
            busy = set(raw.get("feel") or {}) | {r["who"] for r in raw.get("react") or []}
            said = placing.named(" ".join(map(str, say)) if isinstance(say, (list, tuple)) else say, world.things) if say else None
            for thing, how in ([(said[0], ("named", said[1]))] if said else []) + [(t, ("turned to", by)) for t, by in placing.touched(raw.get("do"), world.things).items()]:
                for e, x in st.items():
                    r = x["present"] and e not in busy and e not in fired and placing.regard(self.ents[e], thing, world.things[thing], self.show.cfg.get("valence"), world.regards.get(e))
                    if r:
                        fired[e] = dict(thing=thing, feel={r[0]: r[1], "at": thing}, why=(f"the {thing} is named ('{how[1]}')" if how[0] == "named" else f"{how[1]} turns to the {thing}") + f": {r[3]}", word=how[1] if how[0] == "named" else None)
            if fired:
                raw = dict(raw, react=list(raw.get("react") or []) + [dict(who=e, word=f["word"], feel=f["feel"]) for e, f in fired.items() if f["word"] and e != who],
                           feel={**{e: f["feel"] for e, f in fired.items() if not f["word"] or e == who}, **(raw.get("feel") or {})})
                for e, f in fired.items():
                    world._note("fired", e, f["why"])

            # the speaker's own feeling colours the line; everyone else reacts once it has landed
            late = {}
            for e, f in (raw.get("feel") or {}).items():
                if say and e != who:
                    late[e] = f
                else:
                    feel(e, f)
            a = self._observe(tid)
            pause, hold = (tuning.turn_value(raw, self.script, k, T[k]) for k in ("pause", "hold"))
            hand = raw.get("tune") or {}
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
                tunes, orphaned = tuning.syllable_tunes(raw)
                if orphaned:                              # tuned for words that have since changed: set aside, and said so
                    count = sum(len(v) for v in orphaned.values())
                    self.flag("warn", tid, f"{count} hand-tuned syllable value(s) were tuned for an earlier wording and are not applied; "
                                           f"see `s2s tune list --orphans`")
                for name, vals in tunes.items():
                    for k in vals:
                        if not 1 <= k <= n:
                            self.flag("error", tid, f"a hand-tuned {name} is set for syllable {k}, but the line has {n}")
                sylls = speech.plan(say, self.show.tones[tone], self.show.cfg["scale"], rhythm, melody, stress, cuts, gap, tunes,
                                    self.show.breath, self.show.breath_written)
                say_at = pause + a[who]["latency"]
                reveal = sum(s["len"] for s in sylls)
                react = say_at + reveal
                b = 0
                for k, s in enumerate(sylls):
                    s["bubble"] = b
                    ends = (k + 1) in cuts if parts else s["base"]["breath"] >= gap     # tuning a breath never moves a bubble break
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
                    n = float((hand.get("beat") or {}).get(j + 1, r["beat"]))
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
                                   fired={e: dict(thing=f["thing"], why=f["why"]) for e, f in fired.items()},
                                   appraised={e: dict(v, used=e in (raw.get("feel") or {}) or any(r["who"] == e for r in raw.get("react") or [])) for e, v in appraised.items()},
                                   reacts=reacts, stretches=self._stretches(tid, t0, who, bool(say), pause, say_at, sylls, reacts, length, hold),
                                   info=[(at, {e: o["info"] for e, o in obs.items()}) for at, obs in snaps]))
            t0 += length
        if not self.turns:
            raise ScriptError("the scene has no turns")
        self.carry_out = world.carry_out()
        self.steps = t0
        self.dur = t0 * sec
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
        # what happened dramatically, and which of it gets music: two derivation steps over what was just worked out
        music = self.show.cfg.get("music") or {}
        self.drama = drama.dramatic_events(self.keys, self.focus, self.quiet, self.show.cfg.get("valence"))
        self.music = scoring.cues(self.drama, sec, float(music.get("threshold", scoring.THRESHOLD)), float(music.get("apart", scoring.APART)),
                                  rise=float(music.get("rise", scoring.RISE)), rise_from=float(music.get("rise_from", scoring.RISE_FROM)))
        # where the camera looks: a third derivation step, over the turns, what everyone shows, and the music
        asked = {i: raw["camera"] for i, raw in enumerate(self.script.get("turns") or []) if raw.get("camera")}
        self.camera = camera.shots(self.turns, self.keys, self.focus, self.music, self.drama, sec, asked, self.show.cfg.get("camera"),
                                   {k: v["at"] for k, v in world.things.items()})
        self.place = self.script.get("place")
        # the fourth value says the event belongs to a reaction in passing; how much quieter that is, is presentation's call
        self.events = sorted(((t, n, e, (round(t, 4), e) in self.quiet) for t, n, e in self.events), key=lambda ev: ev[0])

    def _events(self, written, tid):
        events = written if isinstance(written, list) else [written]
        for ev in events:
            why = appraisal.problems(ev, self.world.known, self.facts)
            if why:
                raise ScriptError(f"turn {tid}: {why}" if tid is not None else f"offscreen: {why}")
        return events

    def _appraise(self, events, who, tid):
        """What these events make these entities feel, from their sheets, sides, standing feelings and the facts."""
        world = self.world
        sheets = {e: world.ents.get(e) or self.show.entity(e, self.key) for e in set(who) | {x for ev in events for x in appraisal._targets(ev) + [ev.get("by")] if x}}
        sides = {e: x["side"] for e, x in world.st.items() if x["present"] and x["side"] is not None}
        standing = {e: world.st[e]["felt"] for e in sheets if e in world.st}      # what they feel in the room now; between scenes time has passed, and an event there starts fresh
        minds = appraisal.Minds(sheets, sides, standing, self.facts, self.show.cfg.get("valence"))
        return appraisal.feelings(minds, events, who)

    def _stretches(self, tid, t0, who, spoken, pause, say_at, sylls, reacts, length, hold):
        """Who owns each stretch of a turn's time. Laid end to end they are the whole turn, with no gaps
        and no overlaps, so any moment on screen can be traced to the one value that sets how long it lasts.

        -> [{start, length, param, address, label}] with `start` in steps from the start of the scene.
        `address` is how that value is tuned (see `s2s tune`); it is None for time no tunable value owns."""
        out, at, here = [], 0.0, f"{self.key}:{tid}"

        def add(n, param, address, label):
            nonlocal at
            if n > 1e-9:
                out.append(dict(start=t0 + at, length=n, param=param, address=address, label=label))
                at += n

        if spoken:
            add(pause, "turn.pause", f"{here}.pause", f"pause before {who} speaks")
            add(say_at - pause, None, None, f"{who} is slow to answer (a tell)")
            for k, s in enumerate(sylls, 1):
                word = s["text"].strip()
                add(s["len"] - s["rest"], "syllable.length", f"{here}.s{k}.length", f"\u201c{word}\u201d")
                add(s["rest"], "syllable.breath", f"{here}.s{k}.breath", f"breath after \u201c{word}\u201d")
        else:
            add(float(self.show.cfg["timing"]["settle"]), "show.settle", "show.settle", "a turn with no line settles")
        for r in sorted((r for r in reacts if r["beat"]), key=lambda r: r["at"]):
            add(r["beat"], "reaction.beat", f"{here}.r{r['index'] + 1}.beat", f"{r['who']} holds the scene")
        late = [r for r in reacts if not r["beat"] and r["at"] > at + 1e-9]
        if late:                                             # the line is over, but someone has yet to react
            slow = max(late, key=lambda r: r["at"])
            add(slow["at"] - at, "entity.reflex", f"@{slow['who']}.reflex", f"waiting for {slow['who']} to react")
        add(length - at, "turn.hold", f"{here}.hold", "hold after the turn")
        return out

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

    @property
    def score(self):
        """What this scene decided, as the contract every consumer reads. See score.py."""
        if self._score is None:
            cfg = self.show.cfg
            self._score = Score(
                id=self.key, title=self.title, tempo=self.tempo, step=self.step, steps=self.steps, dur=self.dur,
                grid=dict(steps_per_beat=cfg["steps_per_beat"], scale=list(cfg["scale"]), timing=dict(cfg["timing"])),
                turns=self.turns, pose=self.keys, speech=self.lines, events=self.events, focus=self.focus,
                drama=self.drama, music=self.music, camera=self.camera, place=self.place,
                cast={e: dict(tells=ent["tells"]) for e, ent in self.ents.items()},
                carried=self.carried, offscreen=self.offscreen, carry_out=self.carry_out, problems=self.problems)
        return self._score
