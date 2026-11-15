"""In play: which tunable values are at work at one moment of a scene.

"Something about how he turns is wrong" is a feeling about a moment. This turns the moment
into a short, ranked list of the values that could be responsible:

  1. the value that owns the stretch of time under the playhead (a pause, a syllable, a breath, a hold)
  2. the note and stress of the syllable being spoken
  3. for each thing that happens nearby (someone turns, moves, a bubble opens): the motion values it
     shows at work, nearest first, then its sound; and the music, where a cue plays
  4. the tone of the line being spoken, and its speaker's own settings
  5. the voice and the indicator

Each comes with the stretch of the scene that shows it at work, so it can be replayed.
"""
from ..vocabulary import PARAMS

WHAT = {"enter": "{e} arrives", "exit": "{e} leaves", "move": "{e} moves", "turn": "{e} turns", "look": "{e} looks elsewhere",
        "posture": "{e} changes posture", "bubble": "{e}'s bubble opens", "beat": "{e} holds the scene", "feel": "a feeling lands on {e}"}


def in_play(score, steps, window=4.0):
    """-> [{address, param, label, why, span: [start, end] in steps}], most likely first, no address twice."""
    out, seen = [], set()

    def add(address, why, span):
        param = next((p for p in PARAMS.values() if _matches(p, address)), None)
        if param and address not in seen:
            seen.add(address)
            out.append(dict(address=address, param=param.key, label=param.label, group=_group(param), why=why,
                            span=[max(0.0, span[0]), min(score.steps, span[1])]))

    turn = next((t for t in score.turns if t["start"] <= steps < t["start"] + t["length"]), score.turns[-1])
    here = f"{score.id}:{turn['id']}"
    for s in turn["stretches"]:                                  # 1. whose time is it
        if s["address"] and s["start"] <= steps < s["start"] + s["length"]:
            add(s["address"], s["label"], (s["start"], s["start"] + s["length"]))
    say = turn["start"] + turn["say_at"]
    line = (say, say + turn["reveal"]) if turn["line"] else None
    if line and line[0] <= steps < line[1]:                      # 2. the syllable being spoken
        for k, s in enumerate(turn["sylls"], 1):
            if say + s["at"] <= steps < say + s["at"] + s["len"]:
                word = s["text"].strip()
                for name in ("pitch", "stress", "length", "breath"):
                    add(f"{here}.s{k}.{name}", f"“{word}”", (say + s["at"], say + s["at"] + s["len"]))
    near = sorted(((abs(t / score.step - steps), t / score.step, name, e, quiet) for t, name, e, quiet in score.events
                   if abs(t / score.step - steps) <= window), key=lambda x: x[0])
    for _, at, name, e, quiet in near:                           # 3. what happens nearby, and the values it shows at work
        kind = name.split(".")[0]
        why = WHAT.get(kind, name).format(e=e or "something")
        for p in PARAMS.values():
            if p.scope == "feel" and kind in p.exercised_by and p.name != "aside_volume" and (kind != "bubble" or p.name == "bubble_pop"):
                add(p.key, why, (at, at + 2))
        if quiet and e:                                          # a reaction in passing: how soon it comes, and how quiet it is
            add(f"@{e}.reflex", f"{e} reacts in passing", (at - 2, at + 2))
            add("feel.aside_volume", f"{e} reacts in passing", (at, at + 2))
    for _, at, name, e, quiet in near:                           # ...and then the sound each of them makes
        kind = name.split(".")[0]
        for key in ("vol", "freq", "to", "dur"):
            add(f"sounds.{kind}.{key}", "the sound when " + WHAT.get(kind, name).format(e=e or "something"), (at, at + 2))
    for c in score.music:                                        # ...and the music, where a cue plays
        at = c["t"] / score.step
        if at - 1 <= steps <= at + 10:
            add("feel.music_volume", f"music marks this moment ({c['kind']})", (at, at + 8))
    if line and line[0] - window <= steps < line[1] + window:    # 4. the tone of the line, and its speaker
        who, tone = turn["who"], turn["line"]["tone"]
        for name in ("rate", "pitch", "vol", "range", "stretch"):
            add(f"~{tone}.{name}", f"{who} speaks in the {tone} tone", line)
        add(f"@{who}.voice", f"{who}'s voice", line)
        for p in PARAMS.values():                                # 5. the voice and the indicator
            if p.scope == "feel" and "bubble" in p.exercised_by:
                add(p.key, f"{who} is speaking", line)
    return out


def _matches(p, address):
    name = address.rsplit(".", 1)[-1]
    if address.startswith("@"):
        return p.scope == "entity" and p.name == name
    if address.startswith("~"):
        return p.scope == "tone" and p.name == name
    if address.startswith("sounds."):
        return p.scope == "sound" and p.name == name
    if address.startswith("show."):
        return p.key == "show." + name
    if "." in address and address.split(".")[0] == "feel":
        return p.key == address
    return p.name == name and p.scope in ("turn", "syllable", "reaction")


def _group(p):
    """What kind of thing a value is, for its icon."""
    if p.owns_time:
        return "time"
    return {"syllable.pitch": "pitch", "syllable.stress": "stress"}.get(p.key) or \
           {"feel": "sound" if p.rebuild == "sound" else "motion", "sound": "sound", "tone": "tone", "entity": "entity"}.get(p.scope, "time")
