"""A stage: a score, and the look it is to be shown with.

The score says what happens. The look says how that appears and sounds: frame size and rate,
the small motions, the place, each tone's lettering, each sound, each emotion's colour, and each
entity's colour and voice. A change to the look never needs the scene worked out again.
"""
from ..script import ScriptError, Show, load_yaml, tuning


class Look:
    def __init__(self, W, H, fps, feel, tones, sounds, emotions, cast, music=None, style=None):
        self.place = None                                        # the room, if the scene names one (see place.py)
        self.W, self.H, self.fps = W, H, fps
        self.feel, self.tones, self.sounds, self.emotions, self.cast, self.music = feel, tones, sounds, emotions, cast, music or {}
        self.style = style or {}                                 # choices of kind, not amount: e.g. how the voice is shown in a bubble

    @classmethod
    def load(cls, root, entities, lib=None):
        """A show's look, for the given entities. `lib` holds unsaved copies of library files."""
        show = Show(root, lib)
        cfg = show.cfg
        cast = {}
        for e in entities:
            sheet = tuning.overlay(load_yaml(root / "entities" / f"{e}.yaml"))
            cast[e] = {k: sheet[k] for k in ("color", "voice", "timbre", "kind") if k in sheet}
        return cls(cfg["width"], cfg["height"], cfg["fps"], show.feel, show.tones, show.sounds, show.emotions, cast, show.music, cfg.get("style"))


class Stage:
    def __init__(self, score, look, root):
        self.score, self.look, self.root = score, look, root
        if score.place and look.place is None:                   # the score names the place; what it looks like is the show's
            file = root / "places" / f"{score.place}.yaml"
            if not file.exists():
                raise ScriptError(f"no place '{score.place}': there is no places/{score.place}.yaml")
            look.place = load_yaml(file)
        self.W, self.H, self.fps = look.W, look.H, look.fps
        self.total = max(1, round(score.dur * look.fps))         # frames

    @classmethod
    def of(cls, scene, lib=None):
        """Stage a scene that has been worked out."""
        return cls(scene.score, Look.load(scene.root, scene.score.cast, lib), scene.root)
