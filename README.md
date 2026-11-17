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

## Who they are, and what an event makes them feel

A scene can say what everyone feels (`feel:`), or say what happened and let the feelings
follow from who the characters are. The second way needs three things.

**A profile** on each entity's sheet: four temperament dials (-2 to +2) and the needs that are
strong (2) or absent (0) in them; any need not listed is 1.

    profile:
      temperament: {drive: 2, caution: 1, dominance: -1, warmth: 1}
      needs: {comfort: 2}
    bonds: {bix: 1}            # how they regard someone else, one way

| Dial | High means | Changes |
|---|---|---|
| drive | Pulled hard toward what they want | Good feelings land harder |
| caution | Hit hard by threat | Bad feelings land harder |
| dominance | Takes charge | Power: whether they can answer what happens to them |
| warmth | Moves toward others | What joy and sadness incline them to do (see What if) |

The needs are comfort, safety, belonging, esteem and control.

**Facts**, at the top of a scene: what is true, who did it, and who knows.

    facts:
      dumpling: {doer: otis, knows: [otis, juno]}

**An event** on a turn: what happened, to whom, and which need it touches.

    event: {kind: threat, need: esteem, size: 2, by: juno, target: otis, fact: dumpling, accuses: true}

`kind` is gain, loss, threat or relief. `size` is 1 slight, 2 pointed, 3 undeniable. `accuses`
says the one doing it is accusing the target of the fact; `reveals: true` makes everyone in the
room know the fact from then on; `unseen: true` (in `offscreen:`) means only whoever did it
knows. A turn can carry a list of events.

Everyone present then asks three questions, and the answers pick the feeling:

| Good or bad for my needs? | Whose doing? | Can I answer it? | Feeling |
|---|---|---|---|
| Bad, for esteem or belonging | Mine | (any) | Shame |
| Bad | Someone else's | Yes | Anger |
| Bad, or a threat to safety | Not mine | No | Fear |
| Bad, and over | No one's | No | Sadness |
| Good | (any) | (any) | Joy |

Whoever did it feels joy if they accused someone they know is guilty, and shame if they harmed
someone they are bonded to. A bystander with no stake of their own feels it through their bond
to whoever it happened to. A strong bad feeling still being carried makes the next bad thing
land as more of the same. A slight event stays slight whoever it happens to.

A feeling written on the turn always wins, and `s2s explain <scene:turn> <entity>` says which
it was and why. A reaction with nothing written (`{who: otis, word: dumpling}`) takes the
feeling worked out for that entity and decides only when it lands. The design, and how the
rule was tested against scenes written by hand, is in `docs/lld-profiles.md`.

## Things, regards, and where people stand

A piece in a place can be named, faced and cared about. Its name is its `id:`, or its kind when
it is the only one of that kind. A piece can say which need it `serves`.

    pieces:
      - {kind: fridge, at: 6.6, serves: comfort}
      - {kind: door, at: 8.3}

**A regard** is what a thing makes someone feel. It follows from their needs (a thing that
serves a need that is strong in them is a joy to them), or is written on their sheet, where it
wins: `regards: {plate: {shame: 2}}`.

**Where someone stands need not be written.** Leave `slot` out of `enter:` and:

| Who | Stands |
|---|---|
| Found in the room as the scene opens | Beside the thing that draws them most and facing it; away from what they dread; near whoever they are bonded to; a civil distance from everyone else |
| Arrives later | By the door, or from the side the script names |

    enter: [otis]                               # found by the fridge, which serves his comfort
    enter: {bix: {from: left, orient: otis}}    # rolls in from the left
    enter: {juno: {orient: otis}}               # through the door

`s2s explain <scene:turn> <entity>` says where they were put and why. A thing can also be the
target of `orient`, `attention` and `move`: `do: {otis: {orient: fridge}}`.

**A turn can change what a thing means to someone**, from then on and into later scenes:

    regard: {otis: {plate: {shame: 2}}}      # the empty plate is evidence now

**A thing that means something brings the feeling up** when a line names it, or when anyone
turns to it, looks at it or walks to it. A piece answers to its name and to its `aka`
(`{kind: plate, aka: [dumpling]}`), and the feeling lands on the word. Whatever the turn already
makes someone feel wins. In the last scene of s01e01, three scenes after the plate became
evidence, Bix says "You ate the dumpling" and Otis's eyes drop, with nothing written on that
turn. The camera frames a feeling about a thing with the thing in shot.

## What if

`s2s what-if` maps a situation out without writing it: one setup, one event, and how everyone
would react, as it stands and in variations. Nothing is drawn and nothing is changed.

    s2s what-if thermostat:2 --doer dial=otis --knows dial=otis      # a turn that has an event, with something changed
    s2s what-if shows/demo/what-ifs/the-accusation.yaml              # a file: a setup, an event, and named variations

On a turn, the setup is the scene as it stands when the event lands, and the flags change it:
`--with` and `--without` (who is in the room), `--doer` and `--knows` (the facts), `--side`,
`--feeling` (what someone already feels), and `--dial`, `--need`, `--bond` (who someone is).
A file holds as many variations as you like, and prints one column for each:

           as it stands     Otis didn't do it    Bix is there      Otis outranks her
    juno   joy 1 > press    nothing              joy 1 > press     joy 1 > press
    otis   shame 2 > deny   fear 2 > back away   shame 2 > deny    shame 2 > hit back
    bix    (not here)       (not here)           fear 2 > freeze   (not here)

Add `--sheet` and every column is also staged and drawn as a still, side by side: the engine
plays a two-turn scene for each (everyone as the setup has them, then the event) and takes the
frame where it has landed. A setup can give a `place`, `slots`, a `stance` and the `line` that
carries the event; anyone without a slot stands where their regards put them.

    s2s what-if shows/demo/what-ifs/the-accusation.yaml --sheet

Each cell is what they feel, how strongly, and what that inclines them to do next. Under the
table, every cell that differs from the first column says why. The inclinations are the
branches a scene could take from here; picking one, and writing the line, is the writer's job.

| Feeling | Inclined to | Unless |
|---|---|---|
| Fear | back away | high caution: freeze |
| Anger | confront | cannot answer it: sulk |
| Shame | deny | high dominance: hit back; high caution: withdraw |
| Joy | share | low warmth: press |
| Sadness | withdraw | high warmth: seek company |

## A story as a series of filters

Before any scene exists, a story can be decided in gates, each narrower than the last. The
decisions live in a show's `story.yaml`; `s2s story` carries each one's consequences as far as
the rules reach and reports what is now **forced** (only one thing can be true), **narrowed**
(a few things could be) and **open** (someone has to invent it).

    theme: take-then-give                        # 0. what it is about
    lock: bank                                   # 1. what they go after
    crew: [vera, sam, ruth, nico, ines]          # 2. who they are
    ties: {sam: {vera: [-1, 1]}}                 # 3. how each sees each: [trust, rating]
    plan: [{pin: locks, who: ruth, relies_on: [ines]}]      # 4. the job, and who leans on whom
    twist: staged-failure                        # 5. what the viewer is not told

Three additions to an entity's profile feed it: `standing` (wealth, status, power: where they
sit in society), `craft` (which kinds of obstacle they can get past) and `tells_self` (how they
excuse it). From these the rules work out who is under pressure, who would say yes, who leads,
who holds the group together, who gets blamed, where the plan cracks, and what the group does
when it does. `shows/heist/` is a heist decided this way: six decisions force 45 things and leave six open.
Its theme says nobody is good or bad, so the report requires everyone named, the mark included,
to be surviving something. The design is in `docs/lld-groups.md`. In a show that names its group this way, scenes use it: people turn to listen to whoever they
rate and not to anyone else; what groups usually do (`performance/tendencies.py`) fires on turns
where something happens; `fresh: true` on a scene means time has passed and nobody is still
feeling what they felt; `against: [sam]` on a turn says who opposes what is proposed.

Ties move with what happens. Doing someone good gains their trust, one step a scene; harming
them loses it, a step each time, unless they are warm enough to let it go; `deed: {who: ruth}`
on a turn (a thing done well, in front of whoever is there) raises how they rate her; and
`tie: {ines: {dot: [1, 1]}}` sets one outright. Changes are logged and carried into later scenes.

What a story leaves open forms a tree. Candidate answers go in `branches.yaml`, written in the
model's terms, and `s2s story --branches` works every combination through and ranks them by a
score whose parts are shown. It also says which decision moves the score most, so the most
useful question gets answered next.

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
bubbles wherever the speaker pauses, and each bubble gives way to the next: it eases in
(`feel.bubble_pop`) and fades after its beat ends (`feel.bubble_fade`) while the next arrives. A full stop,
question mark, exclamation mark or ellipsis is a pause; a comma is too short to count (the
threshold is `bubble_break` in `show.yaml`). To choose the breaks yourself, write the line as
a list, one item per bubble; each break gets a pause:

    say: Ha ha ha!                                   # one bubble
    say: Ha. Ha. Ha.                                 # three bubbles
    say: [Ha, ha, ha]                                # three bubbles, without the full stops
    say: [Michael. Get in here.]                     # one bubble, despite the full stop

A bubble's text is all there from the start, in grey. It is split into syllables, each
syllable is one note, and **the words take ink as they are said**: the ink moves through a
syllable for exactly as long as it is voiced, and waits during a breath. So the rhythm of
the line can be read off the bubble, and a viewer who looks late can still read all of it.

Other ways of showing the voice are kept as a choice in `show.yaml`: `style: {indicator: fill}`
is the default; `dot` (a dot that rides under the words, higher for higher notes and larger
on stress), `trace` (the voice draws a line under the words) and `pill` (a block behind the
syllable being said) are the others.

Each syllable has a **stress**, which is what stops speech sounding like a drum pattern:

| Stress | Length | Loudness | Pitch |
|---|---|---|---|
| 0 weak | Half the tone's rate | Quiet | On the contour |
| 1 strong | The tone's rate | Louder | A note higher |
| 2 main accent of the phrase | Half as long again | Loudest | A note higher (lower on a falling line) |

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
| `library/feel.yaml` | The small motions (settle time, overshoot, how long a turn takes, paper flip, stretch, how a bubble eases in and fades out), the speech indicator, how voiced or plucked a syllable sounds, and how strongly a featured reaction is set apart |

A turn can also place a sound by hand: `sfx: [{at: 4, sound: thud}]`.

## The camera and places

**The world is flat and always seen from the front, so the camera never turns.** What it
chooses is who is in the frame, how close, and where in the frame they sit. Who is on screen
decides how a line lands, so the shot is chosen by whose moment it is.

1. A turn belongs to whoever its strongest dramatic event happens to, else to whoever speaks.
   One owner gets a single, two who change together a two-shot, three or more the group.
2. In a single the subject sits to one side, with room in front of them: left of frame if
   they face right, right if they face left, centre if they face us.
3. A reaction that happens outside the frame gets its own shot, at the moment it happens.
   Until then, the line it reacts to is heard from off screen.
4. The same people in the same part of the frame is the same shot: the camera rests. No shot
   is shorter than `min_shot` seconds; the shot before widens to hold the newcomer instead.
5. A hard bad surprise tips the frame.
6. A build-up goes to whoever it is about and pushes in until it lands.

A scene opens wide. Every shot records why it exists (`s2s score <scene> --json`, under
`camera`). To choose a shot yourself, write `camera:` on a turn:

    camera: wide                                   # everyone
    camera: stay                                   # hold the shot we are in
    camera: michael                                # a single, seated by the way he faces
    camera: [chidi, tahani, jason]                 # a group
    camera: {on: michael, at: right}               # seat him left, centre or right of frame
    camera: {on: michael, at: left, zoom: 2.2, tilt: 3}

How tight each kind of shot may get is `camera:` in `show.yaml` (`single`, `two`, `group`,
`margin`, `tilt`, `push`).

How the camera gets from shot to shot is a style in `show.yaml` (`style: {camera: film}`):
`film`, the default, cuts to a new subject and eases when the same subject is reframed
(`feel.camera_move` is how long); `drift` eases everything; `cut` cuts everything; `still`
never leaves the wide shot. In a close shot, whoever it is not a shot of goes out of focus.

**A place is the room a scene happens in.** A scene names one with `place: kitchen`, and the
place is a file in `places/`: a wall colour, a floor colour, and pieces standing along the same
slots the entities use.

    pieces:
      - {kind: table, at: 3.5, wide: 1.2}
      - {kind: plate, at: 3.5, up: 72}                     # 72 pixels up: on the table
      - {kind: thermostat, at: 3.6, color: "#e2703a"}      # a piece given a colour keeps it in every style
      - {kind: plant, at: 8.6, depth: front}               # between the entities and the camera

The kinds are door, window, picture, shelf, sofa, lamp, plant, table, rug, counter, fridge,
thermostat, pedestal, vase, shards and plate. A place can start `like:` another and change only
what differs: the kitchen at night is `like: kitchen` with dark walls and a moonlit `window:`
colour. The wall, the furniture, the floor and the foreground are separate layers, so they
slide against each other when the camera moves. A place is drawn in one of three styles
(`style: {place: wash}`): `wash` is one hue with light from windows and lamps, `paper` is muted
cut paper, and `line` is ink outline. Bubbles follow their speaker but stay the same size
however close the camera is.

## An episode as one film

`s2s render --episode s01e01` makes one file: the episode's scenes and cards in the order
`series.yaml` lists them, joined by transitions, with one soundtrack.

    segments:
      - {id: the-last-dumpling, scene: episodes/s01/e01/01-the-last-dumpling.yaml}     # the cold open
      - {id: s01e01-title, card: title}
      - {id: the-vase, scene: episodes/s01/e01/02-the-vase.yaml}
      - {id: lights-out, scene: episodes/s01/e01/04-lights-out.yaml, into: fade}
      - {id: s01e01-credits, card: credits}

A card has no file. The title card shows the show's `title` (in `show.yaml`) and the episode's
title; the name takes ink while the theme plays, the way a spoken line does, and the cast pop
up under it. The credits roll past the cast, who then turn to look at us.

Everything about it is set in `show.yaml`:

| Setting | What it changes |
|---|---|
| `title` | The show's name |
| `credits` | The credits, top to bottom: `{role, name}` entries, and `cast` for everyone in the episode (name, kind, and what voices them) |
| `episode.transition` | How one part gives way to the next: `dip` (through the paper), `fade` (one into the next) or `cut`. A segment can ask for its own with `into:` |
| `episode.transition_seconds`, `title_seconds`, `credits_seconds` | How long each takes |
| `style` | How rooms are drawn, how the camera moves, how the voice shows in a bubble, how music shows |
| `camera` | How tight each kind of shot may get, the shortest a shot may be (`min_shot`), and how far the frame tips (`tilt`; 0 turns it off) |

The theme is two figures in `music.py`, `theme.title` and `theme.credits`, written in scale
degrees like every other cue; write your own under `figures:` in `library/music.yaml`.

## Music

Music is scored from what happens, not placed by hand. Two steps run after a scene is worked out:

1. **Drama** names what happened: each feeling that lands, for whom, whether it is good or bad
   news, how surprising it is, and how prominent the moment is.
2. **Scoring** gives a cue to the moments that are surprising and prominent enough. Music is
   sparse: it marks a turn in the scene, not every feeling.

| The moment is | Cue | Sounds like |
|---|---|---|
| A surprise, and bad news | `turn.bad` | A low root with a sigh falling onto it |
| A surprise, and good news | `turn.good` | An arpeggio rising through the seventh to the ninth |
| A surprise, not yet good or bad (someone is surprised) | `question` | Held notes in stacked fourths, unresolved |

**Harmony follows meaning.** Figures are written in scale degrees, and the mode is chosen by
how good or bad the news is. The seven modes of one key run from bright to dark as their
notes are lowered one at a time, so the strength of a cue turns one dial:

| News | Mode | Why it sounds that way |
|---|---|---|
| Strong good | Lydian | The raised fourth floats: wonder, relief |
| Good | Major | Plain good news |
| Bad | Aeolian (natural minor) | Plain bad news |
| Worse | Phrygian | The lowered second leans on the root from a semitone above: dread |
| Worst | Locrian | The fifth is lowered too, a tritone over the root: nowhere to rest |
| A question | No third at all | The third is what makes a chord major or minor; leaving it out says "not yet" |
| A build-up | Climbs to the leading tone | A semitone under the root, which the moment it leads to resolves |

**Instruments** are built from sine partials with shaped envelopes, never bare square or
triangle waves, which is what makes synthesised music harsh: `keys` (a soft mallet whose upper
partials die away first), `warm` (a low rounded tone, gently saturated so small speakers can
still play it) and `glass` (a slow-swelling held tone). No note begins or ends with a click,
and none has energy above 6.5 kHz.

**The mix.** Voices, effects and music are three buses, mastered together: rumble and edge
filtered off each; the music dipped around 3 kHz where the ear is most sensitive, softly
saturated and compressed; ducked a few dB while someone speaks; music and a little of the
voices sent to one shared room; and a soft limiter so nothing can clip. `feel.reverb`,
`feel.duck`, `feel.warmth` and `feel.music_volume` are on the knob; `library/music.yaml` holds
the key and which strength gets which mode.

**Surprising to whom?** To the audience, who expect a scene to go on as it is going. A feeling
is surprising to the degree that it departs from where that character just was and from the
mood of the room so far. More of the same gets no music.

**Good or bad for whom?** Also the audience. `valence` in `show.yaml` says whether each emotion
is good or bad for whoever has it, and `sympathy` says whose side the audience is on. It is set
in a turn, like `side`, and carries between scenes:

    - id: 11
      who: michael
      sympathy: {michael: -1}          # from here the audience is against him
      feel: {michael: {joy: 3}}        # ...so his delight is scored as bad news
      why: The mask comes off as a laugh.

Other rules: a feeling that does not show gets no music (the audience cannot be surprised by
what it cannot see); a reaction in passing is too slight alone, but a room reacting together
is one moment and its strengths add; two cues never crowd each other, the stronger is kept.
**The build-up.** The strongest moment of a scene, if it is strong enough, also gets a `rise`:
a tone that climbs and swells for two seconds and stops as the moment lands. The music then
knows what the characters do not, trading surprise for suspense, so there is at most one per
scene (`music: {rise: 16, rise_from: 0.55}`; `rise: 0` turns build-ups off).

**Music you can see.** A sound that something visible causes needs no mark: the motion is
the mark. Music has no visible source, so the picture gives it one:

| The music | On screen |
|---|---|
| A build-up | The ground line hums, tighter and faster, gathering toward where the moment will land, and the frame closes in from top and bottom |
| The moment lands | The frame springs open and one ripple runs outward along the ground from whoever it is about: down for bad news, up for good |
| A question | The ground trembles faintly around them until the next cue settles it |

`style: {music: [line, frame]}` in `show.yaml` is the default; `rings` is another way, and `none` shows nothing.

`music: {threshold, apart}` in `show.yaml` sets how strong a moment must be and how far apart
cues stay. `s2s drama <scene>` explains every event and cue; in the editor, cues are the small
marks above the top strip, and `feel.music_volume` sets how loud the music is.

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

In a show with bars (`beats_per_bar` in show.yaml) the ruler counts bars, with a stronger line every
eight. If a nudge pushes a line off the bar it was asked to land on, the editor says so, and Undo takes it back.

**Whose time is it?** The top strip of the timeline divides the scene into stretches, and
every stretch belongs to exactly one value: a pause, a syllable, a breath (hatched), a held
reaction, a hold. Click a stretch and the **knob** appears on that value.

| Do this | To |
|---|---|
| Click a stretch in the top strip | Put the knob on the value that owns that time |
| Click the picture | A word in the bubble puts the knob on that syllable; the bubble, on the line's tone; a token, on whatever that entity is doing at that moment |
| / then a word, then Enter | Find a value by how you would describe it (gap, snappy, louder, bouncy). The knob goes to the best match nearest the playhead, and the playhead goes to where it shows at work |
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
| Drag a line | Change the pause before it starts. In a show with bars, a line that has a `bar:` moves to another bar instead (it snaps to eighths of a bar; Shift for finer), and what comes before it waits |
| Drag a sound in the sounds lane | Change when it starts. Drag its edge to change how long it lasts (for an explosion, how long it swells first) |
| Click a sound, then Tab | Put the knob on its start, its length, then its level. `/` then "louder" finds the level of every sound of that kind |
| Drag the dot at a sound's top corner | Fade it in (left dot) or out (right dot). A card's music has the same two dots |
| M | Drop a note at the playhead, for the assistant to read (`s2s notes`). It stays on its moment when timings move; Enter with no words removes it |
| H; or the button beside Play | Hear, and see in the waveform lane, everything, or the voices, the sounds or the music alone |
| Shift-drag on the timeline | Mark a stretch. Play stays inside it, and Render makes a video of only that (out/<part>.range.mp4). Escape clears it |
| The layers button | Takes: keep the whole show's tuning under a name, and switch between takes. Switching is one undo step. Takes stay on this computer (.s2s/takes) |
| The meter at the start of the strip | Measure each part's average level in decibels; a part more than 3 dB from the middle one turns amber |
| The film button at the start of the strip | The whole episode as one timeline: play through the joins, see every line and sound in its place, drop notes anywhere. Double-click a part to open it; drag the credits' right edge for their length |
| With one layer chosen (H), double-click the waveform lane | Add a point to that layer's level curve; drag a point to bend the level over time; double-click a point to remove it. On a card the curve is its music's |
| On the title sequence: the camera lane | A diamond at each stop of the camera's path. Drag to retime; click one, then drag the picture to move where the camera looks, Up and Down for closer or further; double-click to add or remove a stop. The title block's right edge sets its length |
| R; or the button beside Loop | Ripple: when on, moving a line to another bar or changing a hold or pause moves every later pinned line by as much, and the scene's length with it. Off, a change stays inside its own gap |
| The pointer button beside Loop | Follow the assistant. When it changes something while the editor is open, a caption on the picture says what and why; with follow on, the editor also goes to that moment, puts the knob on the value and replays it. Click the caption to go there again; its arrow takes the change back |
| Click a part in the strip above the timeline | Open another part of the episode: a scene, the title sequence, a journey over the land, the credits |
| On a card: drag its music; Up, Down | Change where the music lands, by eighths of a bar; make it louder or quieter. Written to that segment in series.yaml as `tune: {music_at, music_vol}` |
| Drag the right edge of an outlined box in an entity's lane | Change how long a featured reaction holds the scene |
| Drag a note up or down | Change a syllable's pitch (Alt for notes outside the scale) |
| Drag a note's right edge | Change a syllable's length |
| Double-click a note | Cycle its stress: weak, strong, main accent |
| Hold Shift while dragging | Move in quarter steps |
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
| See what happens dramatically and which moments get music | `s2s drama the-vase` |
| Export what a scene decided, as JSON | `s2s score thermostat` |
| Learn the vocabulary: what can be tuned, what can be observed | `s2s params`, `s2s channels` |
| Ask what could be tuned at a moment, or what a word might mean | `s2s in-play the-vase:2+0`, `s2s params --find bouncy` |
| Look at a moment, or a whole scene at a glance | `s2s still thermostat:2 --xray`, `s2s sheet thermostat` |
| Render | `s2s render thermostat`, `s2s render --episode s01e01` (`--draft`, `--only 30-48`, `--fresh`), `s2s render --all` |
| Look at an episode without rendering it | `s2s moments s01e01 36 42.5`, `s2s shots s01e01`, `s2s listen s01e01` |
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
