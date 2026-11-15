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
| Bubble and note | The line, and the tone it is said in |

## Files

| Path | Holds |
|---|---|
| `show.yaml` | Frame size, the emotion list, the gain rule, default timings, the ledger threshold |
| `entities/` | One file per entity: colour, voice, status, tells, and an optional `arc` |
| `library/tones.yaml` | Named tones: note colour and movement, typing speed, voice pitch |
| `episodes/` | Scene scripts, read in path order. The keys are explained at the top of `episodes/pilot/scene01.yaml` |
| `toon/` | The model, renderer, ledger and editor |

An `arc` changes an entity's tells from a given scene onward:

    arc:
      - from: ep02/scene04
        tells: {shame: [{attention: source}]}

## The audience ledger

    python -m toon.ledger

A viewer sees only the outputs, and one sighting of a tell is ambiguous. The ledger walks
every scene in order and counts, per entity and emotion, how many scenes have shown that
tell. After three it counts as learned. Two rules:

- A turn can declare `relies_on: {otis: shame}`. It is an error unless that tell was learned
  in earlier scenes.
- A scene that shows more than one never-seen tell for the same entity gets a warning.

A changed tell (an arc step) starts its count again.

## Edit timings

    pip install -r requirements.txt           # plus ffmpeg on the PATH
    python -m toon.editor episodes/pilot/scene01.yaml

| Do this | To |
|---|---|
| Click or drag the ruler, or arrow keys | Move through the scene |
| Drag a turn's right edge | Change its hold |
| Drag a line | Change the pause before it starts |
| Click a timing and type, or Alt+arrow | Set an exact number of frames |
| Space, L | Play or pause, loop the current turn |
| X | X-ray: weight, and felt against shown, drawn below the ground line |
| [ and ] | Previous and next scene |
| Ctrl/Cmd+Z, Ctrl/Cmd+S | Undo, save |

The editor changes timings only. Saving rewrites just those numbers in the scene file.

## Render

    python -m toon.render episodes/pilot/scene01.yaml
    python -m toon.render --all
    python -m toon.render episodes/pilot/scene01.yaml --still 2:40   # turn 2, frame 40

Add `--xray` for the director's view or `--slate` for a turn and frame label. A scene with
errors does not render: a turn with no `why`, a feeling with no tell, or a payoff the
audience cannot decode yet.
