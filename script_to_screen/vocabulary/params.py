"""Parameters: every value that can be tuned by hand, declared once.

    key          <scope>.<name>; the scope is the narrowest place the value can be set
    where        where the value is written today
    rebuild      what has to be redone when it changes:
                   look    nothing is worked out again; only frames are redrawn
                   sound   nothing is worked out again; only sound is remixed
                   timing  the scene is worked out again
    owns_time    the value is a duration on screen (a stretch of the timeline belongs to it)
    exercised_by the kinds of event that show this value at work, for values that own no time
    words        how a writer might describe it, for finding it by feel
"""
from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class Param:
    key: str
    label: str
    meaning: str
    unit: str
    lo: float
    hi: float
    step: float
    where: str
    rebuild: str
    fine: float = None
    owns_time: bool = False
    exercised_by: tuple = ()
    words: tuple = ()

    @property
    def scope(self):
        return self.key.split(".")[0]

    @property
    def name(self):
        return self.key.split(".", 1)[1]

    @property
    def scopes(self):
        """Where this value can be set by hand, narrowest first. The first scope that has a value wins."""
        return WIDER.get(self.key, (self.scope,))

    def clamp(self, v):
        return min(max(float(v), self.lo), self.hi)

    def describe(self):
        return dict(asdict(self), scope=self.scope, scopes=list(self.scopes), fine=self.fine if self.fine is not None else self.step / 4)


WIDER = {"turn.pause": ("turn", "scene", "show"), "turn.hold": ("turn", "scene", "show"), "syllable.breath": ("syllable", "show")}
MOVES = ("move", "turn", "look", "posture", "enter", "exit")
_ = Param
PARAMS = {p.key: p for p in [
    # ---- time a turn takes -------------------------------------------------------------------------
    _("turn.pause", "Pause", "Steps before the speaker reacts and the line begins.", "steps", 0, 200, 1, "a turn's `pause:`, else show.yaml timing.pause",
      "timing", fine=0.25, owns_time=True, words=("pause", "wait", "gap before", "beat before")),
    _("turn.hold", "Hold", "Steps the scene rests after a turn has played.", "steps", 0, 400, 1, "a turn's `hold:`, else show.yaml timing.hold",
      "timing", fine=0.25, owns_time=True, words=("hold", "silence after", "linger", "breathing room")),
    _("show.settle", "Settle", "Steps a turn with no line takes before its hold.", "steps", 0, 64, 1, "show.yaml timing.settle",
      "timing", fine=0.25, owns_time=True, words=("settle", "wordless turn")),
    _("show.bubble_break", "Bubble break", "A pause of at least this many steps starts a new bubble.", "steps", 0.5, 8, 0.5, "show.yaml timing.bubble_break",
      "timing", words=("bubble", "one moment", "split")),
    _("reaction.beat", "Beat", "Steps a featured reaction holds the scene.", "steps", 1, 200, 1, "a reaction's `beat:`",
      "timing", fine=0.25, owns_time=True, words=("beat", "take", "look to camera", "reaction length")),
    # ---- a syllable ---------------------------------------------------------------------------------
    _("syllable.length", "Length", "Steps a syllable is voiced for.", "steps", 0.25, 32, 0.5, "a turn's `rhythm:` list, less the breath",
      "timing", fine=0.125, owns_time=True, words=("rhythm", "drawn out", "clipped", "quick", "slow")),
    _("syllable.breath", "Breath", "Steps of silence after a syllable, before the next one. Punctuation gives it; a hand can change it.", "steps", 0, 16, 0.5,
      "worked out from punctuation; show.yaml timing.breath.<comma|stop|ellipsis>", "timing", fine=0.125, owns_time=True,
      words=("breath", "gap", "pause after", "full stop", "comma", "breathing room", "beat between")),
    _("syllable.pitch", "Pitch", "A syllable's note, in semitones above the speaker's voice.", "semitones", -12, 24, 1, "a turn's `melody:` list",
      "sound", exercised_by=("bubble",), words=("pitch", "melody", "higher", "lower", "inflection")),
    _("syllable.stress", "Stress", "0 weak, 1 strong, 2 the phrase's main accent. Drives length, loudness and pitch.", "level", 0, 2, 1, "a turn's `stress:` list",
      "timing", exercised_by=("bubble",), words=("stress", "emphasis", "accent", "lands on")),
    # ---- a tone of voice ----------------------------------------------------------------------------
    _("tone.rate", "Rate", "Steps a strong syllable takes in this tone.", "steps", 0.5, 8, 0.5, "library/tones.yaml <tone>.rate",
      "timing", exercised_by=("bubble",), words=("pace", "speed of speech", "fast talker", "slow")),
    _("tone.stretch", "Stretch", "How much longer the last syllable of a line is.", "times", 1, 4, 0.25, "library/tones.yaml <tone>.stretch",
      "timing", exercised_by=("bubble",), words=("drawl", "trail off", "last word")),
    _("tone.range", "Range", "How many notes of the scale the tone's contour spans.", "notes", 0, 6, 1, "library/tones.yaml <tone>.range",
      "sound", exercised_by=("bubble",), words=("sing-song", "flat", "expressive", "monotone")),
    _("tone.pitch", "Voice pitch", "Multiplier on the speaker's voice in this tone.", "times", 0.5, 2, 0.01, "library/tones.yaml <tone>.pitch",
      "sound", exercised_by=("bubble",), words=("higher voice", "lower voice", "register")),
    _("tone.vol", "Voice volume", "How loud this tone is.", "level", 0, 1, 0.05, "library/tones.yaml <tone>.vol",
      "sound", exercised_by=("bubble",), words=("loud", "quiet", "whisper", "shout")),
    # ---- an entity ----------------------------------------------------------------------------------
    _("entity.reflex", "Reflex", "Steps an entity takes to react to something said.", "steps", 0, 16, 1, "entities/<entity>.yaml reflex",
      "timing", fine=0.25, exercised_by=("feel", "look", "turn", "posture"), words=("quick to react", "slow on the uptake", "delay")),
    _("entity.voice", "Voice", "The pitch of an entity's voice, in Hz.", "Hz", 60, 800, 1, "entities/<entity>.yaml voice",
      "sound", exercised_by=("bubble",), words=("voice", "deep", "high")),
    # ---- motion, the indicator and the voice: library/feel.yaml -----------------------------------------
    _("feel.ease", "Ease", "Seconds a change takes to settle.", "seconds", 0.05, 0.8, 0.01, "library/feel.yaml ease",
      "look", exercised_by=MOVES, words=("snappy", "sluggish", "smooth", "abrupt")),
    _("feel.overshoot", "Overshoot", "How far a move swings past its mark before settling.", "amount", 0, 2, 0.05, "library/feel.yaml overshoot",
      "look", exercised_by=("move", "posture"), words=("bouncy", "springy", "stiff")),
    _("feel.flip", "Flip", "How thin a token gets mid-turn, like paper flipping.", "amount", 0, 1, 0.05, "library/feel.yaml flip",
      "look", exercised_by=("turn",), words=("turning", "paper", "flip")),
    _("feel.squash", "Squash", "Stretch while travelling.", "amount", 0, 0.4, 0.01, "library/feel.yaml squash",
      "look", exercised_by=("move",), words=("stretch", "rubbery", "travel")),
    _("feel.cursor_size", "Indicator size", "Size of the indicator that travels under a spoken line (it grows on stressed syllables).", "pixels", 1, 10, 0.5,
      "library/feel.yaml cursor_size", "look", exercised_by=("bubble",), words=("dot", "indicator", "cursor")),
    _("feel.cursor_lift", "Indicator lift", "How far the indicator rises and falls with the voice's pitch, in pixels.", "pixels", 0, 24, 1,
      "library/feel.yaml cursor_lift", "look", exercised_by=("bubble",), words=("dot height", "follows pitch")),
    _("feel.cursor_tail", "Indicator tail", "Seconds of trail the indicator leaves behind it.", "seconds", 0, 0.4, 0.01,
      "library/feel.yaml cursor_tail", "look", exercised_by=("bubble",), words=("trail", "tail")),
    _("feel.voice_attack", "Voice attack", "Seconds a syllable's note takes to swell. Short is percussive, long is soft.", "seconds", 0.001, 0.08, 0.001,
      "library/feel.yaml voice_attack", "sound", exercised_by=("bubble",), words=("percussive", "soft", "plucky", "harsh")),
    _("feel.voice_ring", "Voice ring", "How much of its level a note keeps to its end. 0 is plucked, 1 is held so syllables run together.", "amount", 0, 1, 0.05,
      "library/feel.yaml voice_ring", "sound", exercised_by=("bubble",), words=("staccato", "legato", "choppy", "flowing")),
    _("feel.bubble_pop", "Bubble pop", "Seconds a bubble takes to pop open.", "seconds", 0, 0.5, 0.01, "library/feel.yaml bubble_pop",
      "look", exercised_by=("bubble",), words=("pop", "bubble appears")),
    _("feel.focus_dim", "Focus dim", "How far everyone else fades while a featured reaction holds the scene.", "amount", 0, 0.8, 0.05,
      "library/feel.yaml focus_dim", "look", exercised_by=("beat",), words=("spotlight", "fade the others", "attention")),
    _("feel.aside_volume", "Aside volume", "How loud a background reaction's sounds are, next to a featured one.", "level", 0, 1, 0.05,
      "library/feel.yaml aside_volume", "sound", exercised_by=("feel", "look", "turn", "posture"), words=("background reaction", "side-eye volume")),
    # ---- a sound: library/sounds.yaml -------------------------------------------------------------------
    _("sound.vol", "Volume", "Volume (0 is off).", "level", 0, 1, 0.01, "library/sounds.yaml <sound>.vol", "sound", words=("louder", "quieter", "mute")),
    _("sound.freq", "Pitch", "Starting pitch in Hz.", "Hz", 40, 2000, 5, "library/sounds.yaml <sound>.freq", "sound", words=("higher", "lower", "thud", "ping")),
    _("sound.to", "Glide to", "Pitch it glides to, in Hz.", "Hz", 40, 2000, 5, "library/sounds.yaml <sound>.to", "sound", words=("rising", "falling", "swoop")),
    _("sound.dur", "Length", "Length in seconds.", "seconds", 0.01, 0.6, 0.01, "library/sounds.yaml <sound>.dur", "sound", words=("short", "long", "tail")),
]}
del _


def group(scope):
    """The parameters of one scope, in declared order."""
    return [p for p in PARAMS.values() if p.scope == scope]


def check_library(feel):
    """Problems with library/feel.yaml against the declarations: (level, message)."""
    out, known = [], {p.name: p for p in group("feel")}
    for name, p in known.items():
        if name not in feel:
            out.append(("error", f"library/feel.yaml has no `{name}` ({p.meaning.rstrip('.')})"))
        elif not p.lo <= float(feel[name]) <= p.hi:
            out.append(("warn", f"library/feel.yaml `{name}` is {feel[name]}; it is meant to lie between {p.lo:g} and {p.hi:g}"))
    for name in feel:
        if name not in known and name != "tune":
            out.append(("warn", f"library/feel.yaml has `{name}`, which nothing reads; known settings: {', '.join(known)}"))
    return out
