"""Drama: naming what happened, before deciding how it sounds or looks.

This step reads a scene's performance and writes a track of dramatic events. Each says what
happened to whom, whether it was good or bad for them (valence), how surprising it was to the
audience, and how prominent it was. Music scoring reads this track; a camera could too.

Surprising to whom? To the audience, who expect a scene to go on as it is going. A feeling
landing is surprising to the degree that it departs from two things the audience can see:

  - where that character was a moment ago, and
  - the mood of the room (a running average of everyone's feelings so far in the scene).

Feelings are compared by their charge: valence (-1 bad to +1 good, declared per emotion in
show.yaml) times intensity (1 to 3). An emotion with no valence, such as surprise itself, is
a question: something has turned, and the next feeling says which way.

Good or bad for whom? For the audience, who are with some characters and against others
(`sympathy`, set in a turn like `side`: +1 with, -1 against). A villain's delight is bad news.
So an event's valence is the feeling's own valence times the audience's sympathy for whoever has it.

The audience can only be surprised by what it can see. A feeling that is entirely held in
(none of its tells show) is recorded, with weight 0, and gets no music.
"""
VALENCE = {"fear": -1, "anger": -1, "sadness": -1, "shame": -1, "joy": 1, "surprise": 0}     # unless show.yaml says otherwise
WEIGHT = {"featured": 1.0, "plain": 0.7, "passing": 0.4}                                     # how prominent the moment is


def charge(info, valence):
    """How a feeling sits with the audience: good or bad for its owner, times how strong, times whose side we are on."""
    return valence.get(info["felt"], 0) * info["intensity"] * info.get("sympathy", 1) if info["felt"] else 0.0


def dramatic_events(pose, focus, quiet_at, valence=None):
    """pose: {entity: [(seconds, what it shows, with `info`)]}; focus: [(start, end, who)] of featured reactions;
    quiet_at: {(seconds, entity)} of reactions in passing.
    -> [{t, kind, subject, emotion, intensity, valence, surprise, weight, shown, why}], in time order."""
    valence = {**VALENCE, **(valence or {})}
    landings, opening = [], []
    for e, keys in pose.items():
        prev = None
        for t, o in keys:
            info = o["info"]
            if prev is None:
                if o["alpha"]:
                    opening.append(charge(info, valence))        # what they brought in sets the room's mood as the scene opens
            elif o["alpha"] and info["felt"] and (info["felt"], info["intensity"]) != (prev["felt"], prev["intensity"]):
                landings.append((t, e, info, prev))
            prev = info
    mood = sum(opening) / len(opening) if opening else 0.0
    out = []
    for t, e, info, prev in sorted(landings, key=lambda x: (x[0], x[1])):
        v, c, was = valence.get(info["felt"], 0) * info.get("sympathy", 1), charge(info, valence), charge(prev, valence)
        surprise = min(1.0, (abs(c - was) + abs(c - mood)) / 6)
        if valence.get(info["felt"], 0) == 0:                    # the character is surprised: the scene has turned, we do not yet know which way
            surprise = max(surprise, info["intensity"] / 3)
        place = ("featured" if any(a - 1e-9 <= t <= b + 1e-9 and who == e for a, b, who in focus) else
                 "passing" if (round(t, 4), e) in quiet_at else "plain")
        shown = info["level"] > 0
        out.append(dict(t=t, kind="feeling", subject=e, emotion=info["felt"], intensity=info["intensity"], valence=v,
                        surprise=round(surprise, 3), weight=WEIGHT[place] if shown else 0.0, shown=shown, place=place,
                        why=f"{e} feels {info['felt']} {info['intensity']}" + (f" about {info['at']}" if info["at"] else "") +
                            ("; the audience is against them" if info.get("sympathy", 1) < 0 else "") + f"; was at {was:+g}, the room at {mood:+.1f}" + ("" if shown else "; nothing of it shows")))
        mood = 0.5 * mood + 0.5 * c
    return out
