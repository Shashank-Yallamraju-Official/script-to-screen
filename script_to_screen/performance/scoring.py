"""Scoring: which dramatic events get music, and what kind.

Music is sparse on purpose: a cue marks a turn in the scene, not every feeling. An event gets
a cue when its strength (how surprising it was, times how prominent) reaches the show's
threshold. Reactions that land together count as one moment, and when two cues would crowd
each other the stronger is kept.

    surprising and bad      cue `turn.bad`
    surprising and good     cue `turn.good`
    surprising, undecided   cue `question`

This step only names the cue. What a `turn.bad` sounds like is presentation: library/music.yaml.
"""
THRESHOLD, APART = 0.35, 4          # the least strength that gets music; steps two cues must be apart


def cues(drama, step, threshold=THRESHOLD, apart=APART, together=2):
    """drama: the dramatic events; step: seconds per step. -> [{t, kind, strength, subject, why}], in time order.

    Events within `together` steps of each other are one moment: a room that reacts as one is a bigger
    moment than any of its reactions, so their strengths add (up to 1)."""
    moments = []
    for d in sorted(drama, key=lambda d: d["t"]):
        strength = d["surprise"] * d["weight"]
        if strength <= 0:
            continue
        if moments and d["t"] - moments[-1]["t"] <= together * step + 1e-9:
            moments[-1]["parts"].append((d, strength))
        else:
            moments.append(dict(t=d["t"], parts=[(d, strength)]))
    wanted = []
    for m in moments:
        strength = min(1.0, sum(s for _, s in m["parts"]))
        if strength + 1e-9 < threshold:
            continue
        lean = sum(d["valence"] * s for d, s in m["parts"])       # which way the moment tips, each part counted by its strength
        kind = "turn.good" if lean > 1e-9 else "turn.bad" if lean < -1e-9 else "question"
        who = list(dict.fromkeys(d["subject"] for d, _ in m["parts"]))
        wanted.append(dict(t=m["t"], kind=kind, strength=round(strength, 3), subject=who[0] if len(who) == 1 else who,
                           why="; ".join(d["why"] for d, _ in m["parts"])))
    kept = []
    for c in sorted(wanted, key=lambda c: -c["strength"]):       # strongest first; a weaker cue too close to a kept one is dropped
        if all(abs(c["t"] - k["t"]) >= apart * step - 1e-9 for k in kept):
            kept.append(c)
    return sorted(kept, key=lambda c: c["t"])
