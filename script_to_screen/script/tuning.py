"""Hand-set values. A value tuned by hand lives in a `tune:` block at the scope it applies to:

    a turn         tune: {for: "the line's words", pause: 3.5, length: {4: 3}, pitch: {5: 9}, stress: {5: 2}, beat: {1: 10}}
    a scene        tune: {hold: 6}                      (top of the scene file: every turn in it)
    an entity      tune: {reflex: 1.5}                  (its sheet)
    a tone         angry: {..., tune: {rate: 2.5}}      (library/tones.yaml)
    a sound        thud: {..., tune: {vol: 0.5}}        (library/sounds.yaml)
    the show       tune: {hold: 10}                     (show.yaml), and tune: {ease: 0.3} in library/feel.yaml

Where a value is stored says who set it: anything in a `tune:` block was set by hand, and it
outranks the written value at the same scope. Deleting a block restores what was written or
worked out. A value is looked for from the narrowest scope outward, and the first one found wins.
"""
SYLLABLE = ("length", "pitch", "stress")          # per-syllable tunes, keyed by the syllable's number (from 1)
TIMING = ("pause", "hold", "settle", "bubble_break")


def overlay(d):
    """A mapping with its `tune:` block laid over it."""
    if not isinstance(d, dict) or "tune" not in d:
        return d
    out = {k: v for k, v in d.items() if k != "tune"}
    out.update(d["tune"] or {})
    return out


def each(d):
    """Every entry of a library file (tones, sounds), each with its own tunes laid over it."""
    return {k: overlay(v) for k, v in d.items()}


def turn_value(raw, scene_doc, key, default):
    """A turn's pause or hold: its own hand-set value, else its written one, else the scene's, else the show's."""
    for src in ((raw.get("tune") or {}), raw, (scene_doc.get("tune") or {})):
        if src.get(key) is not None:
            return float(src[key])
    return float(default)


def line_text(say):
    """A line's words as one string, however it was written."""
    return " ".join(str(x) for x in say) if isinstance(say, (list, tuple)) else str(say)


def syllable_tunes(raw):
    """-> (tunes, orphaned). A turn's per-syllable tunes apply only to the words they were tuned
    against (`for:`). If the line has changed since, they are set aside, not applied."""
    tune = raw.get("tune") or {}
    mine = {k: {int(n): v for n, v in (tune.get(k) or {}).items()} for k in SYLLABLE if tune.get(k)}
    say = raw.get("say") or raw.get("sing")
    if mine and say is not None and tune.get("for") != line_text(say):
        return {}, mine
    return mine, {}
