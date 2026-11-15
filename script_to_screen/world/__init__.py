"""Layer 2, the world: what is true. Who is present, where they stand, whose side they are
on, what they feel and about whom.

The world has no clock and draws nothing. It changes only through the methods below, and
every change is appended to `log` with the turn that caused it, so "why is he like this
now?" can be answered by reading the log. It imports only the script layer.
"""
from ..script import ScriptError
from ..vocabulary import channels

SLOTS = 9                                   # the stage is one line of nine places
ZONES = {"intimate": 1, "personal": 2, "social": 3, "public": 4}   # distance in slots


def sgn(v):
    return (v > 0) - (v < 0)


class World:
    def __init__(self, show, key, carry, flag):
        self.show, self.key, self.flag = show, key, flag
        self.carry = {e: dict(v) for e, v in carry.items()}      # what each entity brings from earlier scenes
        self.st, self.ents, self.log = {}, {}, []
        self.cause = None                                         # the turn now being played (None: off-screen)
        self.known = show.known()

    def _allowed(self, e, spec, what):
        """Flag anything in a deliberate action that the channel declarations do not allow."""
        for k, v in spec.items():
            why = channels.problem("do", k, v, entities=self.known)
            if why:
                self.flag("error", self.cause, f"{e}'s {what}: {why}")

    def _note(self, kind, subject, value=None):
        self.log.append(dict(kind=kind, subject=subject, value=value, cause=self.cause))

    def need(self, e):
        if e not in self.st:
            raise ScriptError(f"turn {self.cause}: '{e}' has not entered the scene")
        return self.st[e]

    def _felt(self, f, default_at=None, where=None):
        if f in (None, "calm"):
            return None
        emo = next(k for k in f if k != "at")
        if emo not in self.show.emotions:
            self.flag("error", self.cause, (where or "") + f"'{emo}' is not in the show's emotion list")
        return (emo, f[emo], f.get("at", default_at))

    # ---- between scenes ----------------------------------------------------------------------
    def offscreen(self, ev):
        """Something that happened unseen. It changes what entities carry in, before they enter."""
        for e, f in (ev.get("feel") or {}).items():
            self.carry.setdefault(e, {})["felt"] = self._felt(f, where="offscreen: ")
            self._note("offscreen.feel", e, self.carry[e]["felt"])
        for e, v in (ev.get("status") or {}).items():
            self.carry.setdefault(e, {})["status"] = v
            self._note("offscreen.status", e, v)
        for e, v in (ev.get("sympathy") or {}).items():
            self.carry.setdefault(e, {})["sympathy"] = v
            self._note("offscreen.sympathy", e, v)

    # ---- in the room -------------------------------------------------------------------------
    def enter(self, e, spec):
        self.ents[e] = self.show.entity(e, self.key)
        for emo, tells in self.ents[e]["tells"].items():           # a sheet is checked once, as its entity arrives
            for n, tell in enumerate(tells or []):
                for k, v in tell.items():
                    why = channels.problem("tell", k, v, tones=self.show.tones)
                    if why:
                        self.flag("error", self.cause, f"entities/{e}.yaml, {emo} tell {n + 1}: {why}")
        self._allowed(e, spec, "entrance")
        got = self.carry.get(e, {})
        self.st[e] = dict(present=True, slot=spec["slot"], orient=spec.get("orient", "out"),
                          attention=spec.get("attention", "ahead"), posture=spec.get("posture", "upright"),
                          side=None, status=got.get("status", self.ents[e].get("status", 1)), felt=got.get("felt"),
                          sympathy=got.get("sympathy", self.ents[e].get("sympathy", 1)))
        self._note("enter", e, spec["slot"])

    def exit(self, e):
        self.need(e)["present"] = False
        self._note("exit", e)

    def side(self, e, v):
        self.need(e)["side"] = v
        self._note("side", e, v)

    def status(self, e, v):
        self.need(e)["status"] = v
        self._note("status", e, v)

    def sympathy(self, e, v):
        """Where the audience stands toward e: +1 with them, -1 against them, 0 neither. What is good for
        someone the audience is against is bad news, and music is scored that way."""
        if not -1 <= v <= 1:
            self.flag("error", self.cause, f"sympathy for {e} is {v}; it runs from -1 (against) to 1 (with)")
        self.need(e)["sympathy"] = v
        self._note("sympathy", e, v)

    def do(self, e, spec):
        """A deliberate action: it sets the baseline that tells are laid over."""
        s = self.need(e)
        self._allowed(e, spec, "action")
        for k in ("slot", "orient", "attention", "posture"):
            if k in spec:
                s[k] = spec[k]
        if "move" in spec:                   # {toward: other, zone: personal}
            other = self.need(spec["move"]["toward"])
            side = sgn(s["slot"] - other["slot"]) or -1
            s["slot"] = max(0, min(SLOTS - 1, other["slot"] + side * ZONES[spec["move"]["zone"]]))
        self._note("do", e, spec)

    def feel(self, e, f, speaker=None):
        """Set what e feels. Unless it says otherwise, a feeling is about whoever is speaking."""
        self.need(e)["felt"] = self._felt(f, speaker if speaker != e else None)
        self._note("feel", e, self.st[e]["felt"])

    def take(self, e, spec, keep=False):
        """A momentary deliberate action inside a reaction. It outranks tells until dropped."""
        self._allowed(e, spec, "reaction")
        if keep:
            self.st[e].update(spec)
        else:
            self.st[e]["take"] = dict(spec)
        self._note("take", e, spec)

    def drop_take(self, e):
        if self.st[e].pop("take", None) is not None:
            self._note("drop_take", e)

    def drop_takes(self):
        for e in self.st:
            self.drop_take(e)

    # ---- handing on ----------------------------------------------------------------------------
    def carry_out(self):
        """What every entity takes into the next scene. Those not in this scene pass through untouched."""
        out = dict(self.carry)
        for e, s in self.st.items():
            out[e] = dict(felt=s["felt"], status=s["status"], sympathy=s["sympathy"])
        return out
