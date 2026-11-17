"""Every key a show's files may use, in one place. A key nobody reads is a typo, and `s2s check` says so.

Adding a key to the engine means adding it here: that is the whole of declaring it. `s2s check` warns about any key in a show's
files that is not listed, and suggests the nearest that is.
"""
import difflib

KNOWN = dict(
    turn=("id", "who", "say", "sing", "tone", "enter", "exit", "side", "status", "sympathy", "do", "feel", "react", "sfx", "rhythm", "melody", "stress", "pause", "hold",
          "relies_on", "why", "against", "bar", "through", "camera", "clock", "deed", "event", "regard", "tie", "tune"),
    place=("name", "like", "land", "wall", "floor", "window", "sky", "sun", "light", "grade", "vignette", "ink", "shadow", "shade", "air", "bench", "pieces"),
    light=("at", "up", "color", "reach", "strength", "side", "cast", "warm"),
    bench=("from", "to", "rise", "front", "color"),
    piece=("kind", "at", "up", "wide", "color", "depth", "sun", "id", "aka", "serves"),
    land=("bars", "palette", "title_bar", "days_by_bar", "credit", "places", "history", "roads", "wall", "camera"),
    # an entity's sheet: who it is, and (for an object) what it is made of and how it carries itself
    sheet=("color", "voice", "timbre", "kind", "status", "profile", "tells", "bonds", "regards", "reflex", "sympathy", "arc", "body", "size", "pair", "wrapped", "sprung",
           "swinging", "line", "claw", "outfit", "outfit_color", "trim", "plate", "upright", "climbs", "shot", "alight", "point"),
)


def unknown(doc, kind):
    """The keys of `doc` that nothing reads. -> [(key, the nearest known key or None)]"""
    out = []
    for k in (doc or {}):
        if str(k) not in KNOWN[kind] and not str(k).startswith("_"):
            near = difflib.get_close_matches(str(k), KNOWN[kind], 1, 0.6)
            out.append((str(k), near[0] if near else None))
    return out


def problems(doc, kind, where):
    """The same, as lines for `s2s check`."""
    return [f"{where}: nothing reads `{k}`" + (f" (did you mean `{near}`?)" if near else "") for k, near in unknown(doc, kind)]
