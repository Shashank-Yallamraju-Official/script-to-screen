"""Layer 2, the world: what is true. Who is present, where they stand, whose side they are
on, what they feel and about whom.

The world has no clock and draws nothing. It changes only through the methods below, and
every change is appended to `log` with the turn that caused it, so "why is he like this
now?" can be answered by reading the log. It imports only the script layer.
"""
from ..script import ScriptError

SLOTS = 9                                   # the stage is one line of nine places
ZONES = {"intimate": 1, "personal": 2, "social": 3, "public": 4}   # distance in slots
BODY = ("slot", "orient", "attention", "posture")                  # what a deliberate action can set


def sgn(v):
    return (v > 0) - (v < 0)


class World:
    def __init__(self, show, key, carry, flag):
        self.show, self.key, self.flag = show, key, flag
        self.carry = {e: dict(v) for e, v in carry.items()}      # what each entity brings from earlier scenes
        self.st, self.ents, self.log = {}, {}, []
        self.cause = None                                         # the turn now being played (None: off-screen)

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

    # ---- in the room -------------------------------------------------------------------------
    def enter(self, e, spec):
        self.ents[e] = self.show.entity(e, self.key)
        got = self.carry.get(e, {})
        self.st[e] = dict(present=True, slot=spec["slot"], orient=spec.get("orient", "out"),
                          attention=spec.get("attention", "ahead"), posture=spec.get("posture", "upright"),
                          side=None, status=got.get("status", self.ents[e].get("status", 1)), felt=got.get("felt"))
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

    def do(self, e, spec):
        """A deliberate action: it sets the baseline that tells are laid over."""
        s = self.need(e)
        for k in BODY:
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
            out[e] = dict(felt=s["felt"], status=s["status"])
        return out
