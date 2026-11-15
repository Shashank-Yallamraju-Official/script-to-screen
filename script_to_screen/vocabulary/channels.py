"""Channels: everything an observer can see or hear of an entity, declared once.

A channel is set in two ways. A **tell** sets it because of a feeling, and speaks only in
relation to whoever the feeling is about (toward, away, source). A **deliberate action**
(`do:`, `enter:`, a reaction's `do:`) sets it on purpose and can name another entity.
"""
from dataclasses import dataclass

ENTITY, TONE, AWAY_FROM = "<entity>", "<tone>", "{away: <entity>}"


@dataclass(frozen=True)
class Channel:
    key: str
    meaning: str
    tell: tuple = None          # values a tell may set; None if a tell cannot set this channel
    do: tuple = None            # values a deliberate action may set; None if it cannot

    def describe(self):
        return dict(key=self.key, meaning=self.meaning, tell=list(self.tell) if self.tell else None, do=list(self.do) if self.do else None)


CHANNELS = {c.key: c for c in [
    Channel("attention", "Where the dot is: what the entity is attending to.",
            tell=("ahead", "down", "up", "viewer", "source", "away"), do=("ahead", "down", "up", "viewer", ENTITY, AWAY_FROM)),
    Channel("orient", "Which way the body faces (the toe at its base). `out` faces the viewer.",
            tell=("out", "toward", "away"), do=("out", ENTITY, AWAY_FROM)),
    Channel("posture", "The token's shape.", tell=("upright", "contracted", "lean_in", "lean_back"),
            do=("upright", "contracted", "lean_in", "lean_back")),
    Channel("distance", "Slots to move away from whoever the feeling is about (negative approaches).", tell=("<whole number>",)),
    Channel("tone", "The tone of voice a line is delivered in.", tell=(TONE,)),
    Channel("latency", "Extra steps before the entity starts to speak.", tell=("<steps>",)),
    Channel("slot", "Which of the nine places on the stage the entity stands in.", do=("<0 to 8>",)),
    Channel("move", "Walk to a distance from another entity.", do=("{toward: <entity>, zone: intimate|personal|social|public}",)),
]}
TELL_KEYS = {k for k, c in CHANNELS.items() if c.tell}
DO_KEYS = {k for k, c in CHANNELS.items() if c.do}
ZONES = ("intimate", "personal", "social", "public")


def _number(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def problem(how, key, value, tones=(), entities=None):
    """Why `value` cannot be set on channel `key` by a tell or a deliberate action (`how`), or None.

    `entities`, if given, is every entity the show knows; names are checked against it."""
    c = CHANNELS.get(key)
    allowed = getattr(c, how) if c else None
    if not allowed:
        return f"'{key}' is not something a {'tell' if how == 'tell' else 'deliberate action'} can set; it can set: " + \
               ", ".join(sorted(TELL_KEYS if how == "tell" else DO_KEYS))
    known = lambda e: entities is None or e in entities
    ok = False
    if key == "distance":
        ok = isinstance(value, int) and not isinstance(value, bool)
    elif key == "latency":
        ok = _number(value) and value >= 0
    elif key == "slot":
        ok = _number(value) and 0 <= value <= 8
    elif key == "tone":
        ok = not tones or value in tones
        allowed = tuple(tones) or allowed
    elif key == "move":
        ok = isinstance(value, dict) and set(value) == {"toward", "zone"} and value["zone"] in ZONES and known(value["toward"])
    elif isinstance(value, dict):
        ok = AWAY_FROM in allowed and set(value) == {"away"} and known(value["away"])
    elif isinstance(value, str):
        ok = value in allowed or (ENTITY in allowed and value not in ("toward", "away", "source") and known(value))
        if ENTITY in allowed and entities is not None:
            allowed = tuple(a for a in allowed if a != ENTITY) + ("an entity: " + ", ".join(sorted(entities)),)
    return None if ok else f"{key}: {value!r} is not allowed here; it can be: " + ", ".join(str(a) for a in allowed)
