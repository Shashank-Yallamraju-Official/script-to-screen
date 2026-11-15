# script-to-screen

A script goes in; a rendered episode comes out. The command is `s2s` (or `script-to-screen`).

A turn-based animation engine. The frame starts empty. Something appears on screen only
because the script says so, and every turn has to say why.

    pip install -e ".[dev]"        # plus ffmpeg on the PATH, for rendering
    s2s edit shows/demo/episodes/s01/e01/01-the-last-dumpling.yaml
    s2s list                       # run from the repository or a show's folder
    s2s render --episode s01e01
    s2s parity check righteous
    pytest

| | |
|---|---|
| `script_to_screen/vocabulary/` | What can be tuned and what can be observed, declared once |
| `script_to_screen/script/` | Layer 1: reads a show's files |
| `script_to_screen/world/` | Layer 2: what is true, and a log of every change and its cause |
| `script_to_screen/performance/` | Layer 3: the scene played out on the tempo grid. Its output is the score: named tracks of plain data |
| `script_to_screen/presentation/` | Layer 4: how a score looks and sounds. It is given a score and a look, and nothing else |
| `script_to_screen/readers/` | The audience ledger and the parity check |
| `script_to_screen/commands/` | Every command, declared once; the command line is generated from them |
| `script_to_screen/tools/` | The editor |
| `shows/demo/` | A small show used for development: one episode of three scenes, plus a staging study |
| `tests/` | What the engine promises, as tests |
| [docs/how-it-is-used.md](docs/how-it-is-used.md) | The two loops the tool serves: writing through an assistant, tuning by hand |
| [docs/architecture.md](docs/architecture.md) | The target design, and the order to build it in |
| [docs/phases.md](docs/phases.md) | The build phases, and the reference scene every phase must reproduce |
| [docs/lld-nudging.md](docs/lld-nudging.md) | Low-level design of the hand-tuning loop: identify, change, test |
| [docs/requirements-history.md](docs/requirements-history.md) | How the requirements evolved, and what is likely to be asked next |
| [docs/decisions.md](docs/decisions.md) | The choices that would be expensive to reverse |

**Status.** This is a working prototype in a real project's clothes: it is packaged, tested
and versioned, and its internals are being rebuilt to the design in `docs/`, phase by phase
([docs/phases.md](docs/phases.md)). Two
earlier stages are kept as git tags: `paper-v1` (the paper cut-out renderer) and
`prototype-v1` (the prototype before this restructure).

Everything below describes how a show is written. Paths are relative to a show's folder.

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

## Reactions

A reaction is what someone who is not speaking does about a line. There are two kinds, and
the difference is who holds the scene's attention.

| | In passing | Featured |
|---|---|---|
| Written as | `{who: otis, word: dumpling, feel: {shame: 2}}` | `{who: juno, do: {attention: viewer}, beat: 8}` |
| When | On a word of the line, plus the entity's `reflex` | After the line, in order |
| Time | Takes none; the line carries on | The scene waits `beat` steps |
| Everyone else | Unaffected | Fades back a little; the speaker's bubble closes |
| Sound | Quieter | Full, with a soft marker |

Both go in a turn's `react:` list. A reaction can change what the entity feels (`feel:`), in
which case its own tells decide what shows, or be a deliberate action (`do:`). A `do` inside
a reaction is a **take**: it outranks the tells while it lasts and is then dropped, at the
end of the beat for a featured one and at the end of the turn for one in passing. Add
`keep: true` to make it stick.

`reflex` in an entity's file is how many steps it takes to react to something said. The
trigger is `word:` (a word of the line) or `syllable:` (its number); with neither, the
reaction fires as the line ends. The older `feel:` on a turn still works and means "everyone
listed reacts as the line ends".

## A series

`series.yaml` is the show from above: seasons, episodes and their segments, in order.

    seasons:
      - id: s01
        title: Season one
        episodes:
          - id: s01e01
            title: The kitchen
            logline: Three small accusations in one room.
            segments:
              - {id: the-last-dumpling, scene: episodes/s01/e01/01-the-last-dumpling.yaml}
              - {id: the-vase, scene: episodes/s01/e01/02-the-vase.yaml, status: tuned}

A segment's `id` is its identity: arcs, addresses, references and output files use it, so a
file can be renamed or moved without breaking anything, and reordering is moving a line
(`s2s move the-vase --before the-last-dumpling`). A scene's `status` is draft, staged, tuned
or locked; a locked scene refuses every change. Today every segment is a scene; a title
card will be another kind. `s2s list` prints this view with each scene's length and problems.

Scenes run in the order listed. Each level of the hierarchy has its own clock:

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
      - from: the-apology            # a scene's id
        tells: {shame: [{attention: source}]}

## Time and music

Time is counted in **steps** of a tempo grid (`tempo` and `steps_per_beat` in `show.yaml`;
at the defaults one step is an eighth of a second). Pauses, holds and syllables all land on
the grid, and fractions of a step are allowed for nudges. A scene can set its own `tempo`.

**One bubble holds one beat, and a pause is what separates beats.** A line breaks into
bubbles wherever the speaker pauses, and each bubble replaces the one before it. A full stop,
question mark, exclamation mark or ellipsis is a pause; a comma is too short to count (the
threshold is `bubble_break` in `show.yaml`). To choose the breaks yourself, write the line as
a list, one item per bubble; each break gets a pause:

    say: Ha ha ha!                                   # one bubble
    say: Ha. Ha. Ha.                                 # three bubbles
    say: [Ha, ha, ha]                                # three bubbles, without the full stops
    say: [Michael. Get in here.]                     # one bubble, despite the full stop

A bubble's text appears all at once. It is split into syllables, each syllable is one note,
and an **indicator** travels under the text in time with the voice:

| What the indicator does | What it shows |
|---|---|
| How fast it crosses a syllable | Rhythm: it takes exactly as long as the syllable is voiced |
| How high it rides | Pitch, scaled to the line's own highest and lowest notes |
| How big it is | Stress |
| Stopping and shrinking | The breath after punctuation |

Each syllable has a **stress**, which is what stops speech sounding like a drum pattern:

| Stress | Length | Loudness | Pitch | Indicator |
|---|---|---|---|---|
| 0 weak | Half the tone's rate | Quiet | On the contour | Small |
| 1 strong | The tone's rate | Louder | A note higher | Medium |
| 2 main accent of the phrase | Half as long again | Loudest | A note higher (lower on a falling line) | Large |

Stress, rhythm and melody are worked out from the words and the tone; a line can set its own:

    say: Some·one ate the last dumpling.
    stress: [1, 0, 1, 0, 1, 2, 0]       # 0 weak, 1 strong, 2 main accent
    rhythm: [2, 1, 2, 1, 2, 3, 2]       # steps per syllable
    melody: [2, 0, 4, 4, 7, 9, 7]       # semitones above the speaker's voice

Syllables and stress are guessed from spelling. Where a guess is wrong, write a middle dot
to break a word (some·one) or a caret before the syllable that should be strong (to^day).

| File | Tunes |
|---|---|
| `library/tones.yaml` | Per tone: rhythm, melody contour, voice, letter size, and the note shown on sung lines |
| `library/sounds.yaml` | One synthesised sound per kind of event: enter, exit, move, turn, look, posture, bubble, feel |
| `library/feel.yaml` | The small motions (settle time, overshoot, paper flip, stretch, the bubble's pop), the speech indicator, how voiced or plucked a syllable sounds, and how strongly a featured reaction is set apart |

A turn can also place a sound by hand: `sfx: [{at: 4, sound: thud}]`.

## The audience ledger

    s2s ledger

A viewer sees only the outputs, and one sighting of a tell is ambiguous. The ledger walks
every scene in order and counts, per entity and emotion, how many scenes have shown that
tell. After three it counts as learned. Two rules:

- A turn can declare `relies_on: {otis: shame}`. It is an error unless that tell was learned
  in earlier scenes.
- A scene that shows more than one never-seen tell for the same entity gets a warning.

A changed tell (an arc step) starts its count again.

## Values tuned by hand

A value tuned by hand is kept apart from what was written, in a `tune:` block at the scope it
applies to. Where a value is stored says who set it.

    - id: 2
      who: juno
      say: I saw. You took it.
      hold: 3                                         # written
      tune: {for: "I saw. You took it.", hold: 14, length: {2: 3}, pitch: {5: 9}}     # set by hand
      why: She has waited all day to say this.

A value is looked for from the narrowest scope outward, and the first one found wins; at the
same scope, hand-set beats written. Taking a hand-set value off restores what was written or
worked out.

| Scope | Address | Holds |
|---|---|---|
| A syllable | `the-vase:2.s3.length` | length (voiced), breath (the silence after it), pitch, stress |
| A featured reaction | `the-vase:2.r1.beat` | how long it holds the scene |
| A turn | `the-vase:2.hold` | pause, hold |
| A scene | `the-vase.hold` | pause, hold for every turn in it |
| The show | `show.hold`, `show.breath.stop`, `feel.overshoot` | timings, the breath after each kind of pause (comma, stop, ellipsis), motion, the indicator, the voice |
| An entity, a tone, a sound | `@otis.reflex`, `~angry.rate`, `sounds.thud.vol` | their own settings |

    s2s tune get the-vase:2.hold          # the value, and every scope's say on it
    s2s tune set the-vase:2.hold 14
    s2s tune reset the-vase:2.hold        # take the hand-set value off
    s2s tune widen the-vase:2.hold        # move it out to the scene (then the show); says how many turns change
    s2s tune list                         # everything set by hand, beside what it replaced

Tuning changes how a scene feels, never its structure: shortening a breath does not merge
two bubbles, because bubbles break where the script's punctuation says, not where a tuned
silence happens to fall.

Per-syllable values belong to the words they were tuned against (`for:`). If the line is
reworded they are set aside, not applied and not deleted, and `s2s check` and
`s2s tune list --orphans` say so. The editor writes every nudge this way.

## The editor

    s2s edit the-thermostat

The editor is for tuning by hand: nudge a value, replay, compare. It does not change words,
feelings or structure. **There is no Save.** While you drag, the picture previews; when you
let go, that one value is written to the file (comments and layout kept) and recorded in the
journal. The editor follows the files, so a change made elsewhere, by the assistant or in a
text editor, appears within half a second and is never overwritten.

**Whose time is it?** The top strip of the timeline divides the scene into stretches, and
every stretch belongs to exactly one value: a pause, a syllable, a breath (hatched), a held
reaction, a hold. Click a stretch and the **knob** appears on that value.

| Do this | To |
|---|---|
| Click a stretch in the top strip | Put the knob on the value that owns that time |
| Up or Down with nothing picked | Pick whatever owns the moment under the playhead |
| Up, Down (Shift for a fine step); or type a number | Nudge the picked value. Each nudge is written at once; a quick run is one undo step |
| Backspace | Take the hand-set value off; it goes back to what it inherits |
| W | Widen: use this value for the next scope out (a turn's hold for its scene, then the show; a breath for every pause of its kind) |
| Tab, Shift+Tab; or click an icon beside the knob | Step the knob through everything **in play** at the playhead: the value that owns the moment, then the syllable's note and stress, then what nearby events show at work (ease and flip where someone turns), their sounds, the line's tone, its speaker, the voice. Hover an icon to see what it is and why it is listed |
| (after any nudge) | The moment replays by itself: the value's stretch with a second before and after, with sound |
| Enter | Replay that moment again |
| B | Flip between **A**, the scene as it was when you picked the value, and **B**, the scene now, and replay. A badge on the picture says when A is showing |
| L | Loop: with the knob on a value, the moment repeats with a half-second gap until you press Space |
| Escape | Put the knob away |
| Hover the dots beside the value | See every scope's say. One dot per scope, narrowest first; the filled one is where the value comes from, and it is coloured if set by hand |
| Click or drag the ruler; Left and Right (Shift for a whole step) | Move through the scene |
| Drag a turn's right edge | Change its hold |
| Drag a line | Change the pause before it starts |
| Drag the right edge of an outlined box in an entity's lane | Change how long a featured reaction holds the scene |
| Drag a note up or down | Change a syllable's pitch (Alt for notes outside the scale) |
| Drag a note's right edge | Change a syllable's length |
| Double-click a note | Cycle its stress: weak, strong, main accent |
| Hold Shift while dragging | Move in quarter steps |
| T | Open the sliders for motion and sounds. Click a sound's name to hear it |
| Space, L | Play or pause; loop the current turn (or, with the knob on a value, the moment around it) |
| X | X-ray: weight, and felt against shown, drawn below the ground line |
| [ and ] | Previous and next scene |
| Ctrl/Cmd+Z, Ctrl/Cmd+Shift+Z | Undo and redo your own changes, sliders included. It survives closing the editor |

Undo in the editor only ever takes back changes made by hand; it never undoes the
assistant's. It refuses if the file has changed since, because that would lose work.
`s2s history --by hand` lists what was tuned by hand. A locked scene cannot be nudged. A turn
with an amber dot has hand-tuned syllable values left over from an earlier wording.

How much replays around a nudge is set in `show.yaml`: `editor: {lead_in: 8, lead_out: 8}`, in steps.

The arrow-into-a-wall icon appears when a scene inherits something; hover it to see what was
carried in and what happened off-screen.

## The command line

    s2s commands                 # every command, with arguments and an example
    s2s <command> --help

Scenes and turns have short addresses: `thermostat` is the scene whose name contains that
word, `thermostat:2` is its turn 2, `thermostat:2+6` is six steps into that turn. Every
command takes `--json`; a command that changes something also takes `--dry-run`, `--because
"the writer's words"` and `--force`. Exit codes: 0 done, 2 refused, 3 the show has errors.

| To | Run |
|---|---|
| See the show from above | `s2s list` |
| Read a scene or a turn | `s2s read thermostat:2` |
| See what is true as a turn ends | `s2s state thermostat:2` |
| Ask why someone looks the way they do | `s2s explain thermostat:2 otis` |
| List problems | `s2s check` |
| Export what a scene decided, as JSON | `s2s score thermostat` |
| Learn the vocabulary: what can be tuned, what can be observed | `s2s params`, `s2s channels` |
| Ask what could be tuned at a moment | `s2s in-play the-vase:2+0` |
| Look at a moment, or a whole scene at a glance | `s2s still thermostat:2 --xray`, `s2s sheet thermostat` |
| Render | `s2s render thermostat`, `s2s render --episode s01e01`, `s2s render --all` |
| Change a line, a feeling, a timing, a reason | `set-line`, `set-feeling`, `set-timing`, `set-why` |
| Add or remove | `add-scene`, `add-turn`, `add-reaction`, `remove-turn` |
| Reorder, or mark how finished a scene is | `move`, `set-status` |
| Tune a value by hand, at any scope | `s2s tune set the-vase:2.hold 14` (also `get`, `reset`, `widen`, `list`) |
| Set any other field of a turn | `s2s put thermostat:2 do '{juno: {orient: otis}}'` |
| See and reverse changes | `s2s history`, `s2s undo`, `s2s redo` |
| Bring an older show up to date | `s2s migrate` |

A change is checked against the whole show before it is written. One that would introduce
an error is refused and says which error; a refusal says what would work ("no word
'degree' in this line; its words are: it, is, eighty, degrees, in, here"). A scene with
errors does not render: a turn with no `why`, a feeling with no tell, a rhythm or melody
that does not match the syllable count, or a payoff the audience cannot decode yet.

Entity sheets, the library and show settings can be tuned by command (`s2s tune`), but their
written values and a character's tells are still edited as files.
