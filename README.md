# toon

A bare-bones, turn-based animation pipeline. The frame starts empty. Something appears on
screen only because the script says so, and every turn has to say why.

The earlier paper cut-out renderer is kept in git history under the tag `paper-v1`.

## The model

An **entity** is anything that can think, act and feel. It is drawn as a featureless token.

| Layer | What it is | Where it lives |
|---|---|---|
| Felt state | An emotion and an intensity (1 to 3), from one list every entity shares | `feel:` in a turn |
| Tells | An entity's own ordered list of how each emotion leaks out | `entities/<name>.yaml` |
| Position | Side and status in the room, which set how many tells show | `side:` and `status:` in a turn |
| Deliberate action | Something an entity chooses to do | `do:` in a turn |

Position works like this: weight = status on my side / status of everyone who has taken a
side, and tells shown = intensity x gain, where gain = 2 x weight (limits in `show.yaml`).
At equal weight, what is felt is what shows. Outnumbered, less leaks. Backed up, more does.

What an observer can see of a token:

| Mark | Meaning |
|---|---|
| Where it stands | One of nine slots. Distance between two: 1 intimate, 2 personal, 3 social, 4+ public |
| The toe at its base | Which way the body faces. No toe means facing out |
| The dot | Where its attention is |
| Its shape | Posture: upright, contracted, leaning in, leaning back |
| Bubble | The line. A music note appears on it only when the line is sung (`sing:` in place of `say:`) |

## A series

    episodes/<season>/<episode>/<scene>.yaml      e.g. episodes/s01/e01/02-the-vase.yaml

Scenes run in path order, so number them. Each level of the hierarchy has its own clock:

| Level | What changes | Written as |
|---|---|---|
| Turn | What an entity feels | `feel:` |
| Scene | Who is in the room and who stands with whom | `enter:`, `side:` |
| Between scenes | Nothing, unless something happened unseen | `offscreen:` at the top of the next scene |
| Across a season | How an entity expresses a feeling | `arc:` in its entity file |

**Nothing resets between scenes.** What each entity feels, who that feeling is about, and
its status carry from the end of one scene into the next, including for entities that sit a
scene out. Where they stand and which side they are on belong to the room, so each scene
sets those itself. To change what is carried, the next scene says what happened off-screen:

    offscreen:
      - feel: {otis: calm, juno: calm}
        why: A day has passed.
      - feel: {bix: {shame: 1, at: juno}}
        why: An hour ago Bix bumped the thermostat dial.

Off-screen events need a `why` like any turn. The audience never sees them, only their
effects, which is the point.

An `arc` changes an entity's tells from a given scene onward:

    arc:
      - from: s01/e03/02-the-apology
        tells: {shame: [{attention: source}]}

## Time and music

Time is counted in **steps** of a tempo grid (`tempo` and `steps_per_beat` in `show.yaml`;
at the defaults one step is an eighth of a second). Pauses, holds and syllables all land on
the grid, and fractions of a step are allowed for nudges. A scene can set its own `tempo`.

A line is split into syllables. Each syllable is one sung note, and its text appears on the
frame that note starts. The tone supplies a default rhythm and melody; a line can set its own:

    say: Some·one ate the last dumpling.
    rhythm: [2, 2, 2, 2, 2, 2, 6]       # steps per syllable
    melody: [0, 0, 7, 4, 7, 4, 7]       # semitones above the speaker's voice

Syllables are guessed from spelling. Where the guess is wrong, write a middle dot in the word.

| File | Tunes |
|---|---|
| `library/tones.yaml` | Per tone: rhythm, melody contour, voice, letter size, and the note shown on sung lines |
| `library/sounds.yaml` | One synthesised sound per kind of event: enter, exit, move, turn, look, posture, bubble, feel |
| `library/feel.yaml` | The small motions: settle time, overshoot, paper flip, stretch, hops, pops |

A turn can also place a sound by hand: `sfx: [{at: 4, sound: thud}]`.

## The audience ledger

    python -m toon.ledger

A viewer sees only the outputs, and one sighting of a tell is ambiguous. The ledger walks
every scene in order and counts, per entity and emotion, how many scenes have shown that
tell. After three it counts as learned. Two rules:

- A turn can declare `relies_on: {otis: shame}`. It is an error unless that tell was learned
  in earlier scenes.
- A scene that shows more than one never-seen tell for the same entity gets a warning.

A changed tell (an arc step) starts its count again.

## The editor

    pip install -r requirements.txt           # plus ffmpeg on the PATH
    python -m toon.editor episodes/s01/e01/01-the-last-dumpling.yaml

| Do this | To |
|---|---|
| Click or drag the ruler; arrow keys (Shift for a whole step) | Move through the scene |
| Drag a turn's right edge | Change its hold |
| Drag a line | Change the pause before it starts |
| Drag a note up or down | Change a syllable's pitch (Alt for notes outside the scale) |
| Drag a note's right edge | Change a syllable's length |
| Hold Shift while dragging | Move in quarter steps |
| T | Open the sliders for motion and sounds. Click a sound's name to hear it |
| Space, L | Play or pause, loop the current turn |
| X | X-ray: weight, and felt against shown, drawn below the ground line |
| [ and ] | Previous and next scene |
| Ctrl/Cmd+Z, Ctrl/Cmd+S | Undo (not for sliders), save |

The arrow-into-a-wall icon appears when a scene inherits something; hover it to see what was
carried in and what happened off-screen. Saving rewrites only the values you changed.

## Render

    python -m toon.render episodes/s01/e01/01-the-last-dumpling.yaml
    python -m toon.render --episode s01/e01          # every scene in the episode, joined
    python -m toon.render --all
    python -m toon.render episodes/s01/e01/01-the-last-dumpling.yaml --still 2:6   # turn 2, six steps in

Add `--xray` for the director's view or `--slate` for a turn and step label. A scene with
errors does not render: a turn with no `why`, a feeling with no tell, a rhythm or melody
that does not match the syllable count, or a payoff the audience cannot decode yet.
