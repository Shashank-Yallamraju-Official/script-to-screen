"""Every kind of movement the tool can show, declared once.

A motion has a name, a kind (how something gets somewhere; what it does to what is in its way; the state it is in; what it
does where it stands; what the camera does), what the viewer sees, and how a script asks for it. A movement that is not here
is a new type: it has to be built, and named here, before a scene can use it.

A show sorts these into tiers in its bible.yaml (`motions: {familiar: [...], reserved: [...]}`): the ones the viewer is meant
to get used to, and the ones kept for critical moments. See readers/motions.py for what the film has actually used.
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class Motion:
    name: str
    kind: str          # path | contact | state | in place | camera
    sees: str          # what the viewer sees
    ask: str           # how a script asks for it


KINDS = dict(path="How it gets there", contact="What it does to what is in its way", state="The state it is in", place="What it does where it stands", camera="What the camera does")

MOTIONS = {m.name: m for m in (
    Motion("walk", "path", "Comes in along the floor from the nearer side and takes its place.", "a turn's `enter:`, after the scene has opened"),
    Motion("jump", "path", "Jumps up onto the bench, from either end.", "`climbs: true` on its sheet, then `enter:`"),
    Motion("shot", "path", "Flies in straight, foot first, like an arrow, and sticks where it lands, quivering.", "`shot: true` on its sheet, then `enter:`"),
    Motion("leave", "path", "Goes out the nearer side.", "a turn's `exit:`"),
    Motion("approach", "path", "Moves toward someone, or away, and stops at a distance that means something.", "`do: {who: {move: {toward: ...}}}`"),
    Motion("through", "contact", "Comes in through whatever hangs in a window: tears a hole in it, sets it swinging, and lets a spot of light in.", "a turn's `through: <slot>`, with `enter:`"),
    Motion("lit", "state", "Is burning when it arrives.", "`alight: true` on its sheet"),
    Motion("swell", "state", "Grows, with a rising hum, for two bars.", "`sfx: [{sound: blast, on: who}]` (the swell comes first), or `sound: swell` for the sound alone"),
    Motion("burst", "state", "Goes off: the frame is thrown and fills with light.", "`sfx: [{sound: blast, on: who}]`"),
    Motion("speak", "place", "Speaks: a bubble, the words lighting as they are said, and the object moving as it talks.", "a turn's `say:`"),
    Motion("turn", "place", "Turns to face someone, or away.", "`do: {who: {orient: ...}}`, or a line addressed to someone"),
    Motion("look", "place", "Looks at someone without turning its body.", "`do: {who: {attention: ...}}`"),
    Motion("lean", "place", "Leans in, or draws back.", "a feeling strong enough to move it; or its object's own verb"),
    Motion("tell", "place", "Shows a feeling the way it always does.", "a `feel:` or `react:`, and a tell on its sheet"),
    Motion("hold", "camera", "The wide shot, held.", "the default; `stage: wide` on the show holds it"),
    Motion("cut", "camera", "Cuts to whoever the moment belongs to.", "the camera's own rules; or `shot:` on a turn"),
    Motion("push", "camera", "Moves in slowly on a held moment.", "the camera's own rules"),
)}
