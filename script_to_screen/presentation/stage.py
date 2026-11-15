"""A stage: a score, and the look it is to be shown with.

The score says what happens. The look says how that appears and sounds: frame size and rate,
the small motions, each tone's lettering, each sound, each emotion's colour, and each
entity's colour and voice. A change to the look never needs the scene worked out again.
"""
from ..script import Show, load_yaml


class Look:
    def __init__(self, W, H, fps, feel, tones, sounds, emotions, cast):
        self.W, self.H, self.fps = W, H, fps
        self.feel, self.tones, self.sounds, self.emotions, self.cast = feel, tones, sounds, emotions, cast

    @classmethod
    def load(cls, root, entities, lib=None):
        """A show's look, for the given entities. `lib` holds unsaved copies of library files."""
        show = Show(root, lib)
        cfg = show.cfg
        cast = {}
        for e in entities:
            sheet = load_yaml(root / "entities" / f"{e}.yaml")
            cast[e] = {k: sheet[k] for k in ("color", "voice", "timbre", "kind") if k in sheet}
        return cls(cfg["width"], cfg["height"], cfg["fps"], show.feel, show.tones, show.sounds, show.emotions, cast)


class Stage:
    def __init__(self, score, look, root):
        self.score, self.look, self.root = score, look, root
        self.W, self.H, self.fps = look.W, look.H, look.fps
        self.total = max(1, round(score.dur * look.fps))         # frames

    @classmethod
    def of(cls, scene, lib=None):
        """Stage a scene that has been worked out."""
        return cls(scene.score, Look.load(scene.root, scene.score.cast, lib), scene.root)
