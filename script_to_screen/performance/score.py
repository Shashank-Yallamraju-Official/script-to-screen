"""The score: everything a scene's performance decided, as plain data on a clock.

This is the contract between deciding and showing. Drawing, sound, the audience ledger and
the editor read a score and nothing else, so any of them can be replaced without touching
how a scene is worked out, and a score can be saved, compared or sent somewhere as JSON.

    track       what it holds                                                    times in
    turns       each turn's place and length, its timings, and why it happens    steps
    pose        per entity: what it shows, and from when (with `info`, the why)  seconds
    speech      bubbles in order: who, tone, and every syllable's note           seconds
    events      everything that happened that could make a sound                 seconds
    focus       who holds the scene during a featured reaction                   seconds
    cast        per entity: its tells as they stand in this scene
    carried     what entities brought in; `carry_out` is what they take away
    grid        the tempo grid and the show's default timings

A score holds nothing about how things look or sound: no colours, sizes, voices or volumes.
"""
FIELDS = ("id", "title", "tempo", "step", "steps", "dur", "grid", "turns", "pose", "speech", "events", "focus",
          "cast", "carried", "offscreen", "carry_out", "problems")


def _plain(v):
    if isinstance(v, dict):
        return {str(k): _plain(x) for k, x in v.items()}
    if isinstance(v, (list, tuple)):
        return [_plain(x) for x in v]
    if isinstance(v, (str, int, float, bool)) or v is None:
        return v
    return str(v)


class Score:
    def __init__(self, **fields):
        missing = set(FIELDS) - set(fields)
        if missing:
            raise TypeError("a score needs: " + ", ".join(sorted(missing)))
        self.__dict__.update(fields)

    def to_data(self):
        """The score as JSON-ready data."""
        return {k: _plain(getattr(self, k)) for k in FIELDS}

    @classmethod
    def from_data(cls, data):
        return cls(**{k: data[k] for k in FIELDS})

    # ---- lookups (times in seconds) --------------------------------------------------------------
    def turn_at(self, t):
        s = t / self.step
        for turn in self.turns:
            if turn["start"] <= s < turn["start"] + turn["length"]:
                return turn
        return self.turns[-1]

    def line_at(self, t):
        for ln in self.speech:
            if ln["start"] <= t < ln["end"]:
                return ln
        return None
