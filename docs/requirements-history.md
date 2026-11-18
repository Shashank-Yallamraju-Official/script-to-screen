# How the requirements evolved

The prototype was built over about twenty rounds of feedback. This document reads those
rounds as data: what was asked, what each ask revealed, the patterns across them, and what
those patterns predict will be asked next. The architecture in
[architecture.md](architecture.md) is designed against the predictions, not just the present.

The predictions were tested once already. Rounds 18 to 21 arrived after the first version of
this document, and [How the first predictions did](#how-the-first-predictions-did) scores them.

## The rounds

| # | The ask | What it revealed |
|---|---|---|
| 1 | Animate a TV show; Claude does the work while I describe scenes | The author works in intent, not in software. The script is the interface |
| 2 | Code-generated 2D, paper cut-out, speech bubbles with no lip sync | Speech is a visual object, not a mouth |
| 3 | A UI to tune timings myself | Anything adjustable must be adjustable without a round trip to Claude |
| 4 | Strip to bare bones; every detail must be explainable | Defaults are decisions. Nothing may appear without a reason |
| 5 | Same emotions inside, different expression outside; majority and minority change behaviour | Behaviour should be derived from a character and a situation, not written per moment |
| 6 | Ground it in research; arcs; the audience learns characters slowly | The audience is part of the system and has state of its own |
| 7 | Generalise to any entity that can think, act and feel | Nothing may assume a human body |
| 8 | Small details are everything; match text to music on every syllable | Precision moved from pixels to time. Sound is half the medium |
| 9 | A full series; off-screen events; state carries over | The unit is the series. A scene is a window onto continuous state |
| 10 | Colours for characters; test against a scene I know | Evaluation is by comparison with real television |
| 11 | No wavy text; a music note only when singing | A reference is not a spec. Two things just built were removed |
| 12 | A bounce on every syllable sounds monotone | Uniformity reads as false. Speech needs stress |
| 13 | Show the text at once; move an indicator along it | The same information was moved to a different visual channel |
| 14 | A bubble holds one moment | The show has named units of meaning, and they keep being discovered |
| 15 | Non-verbal reactions: can they be codified? | The author wants rules, and asks before assuming |
| 16 | Some reactions are the moment; others are in passing | Attention is a resource, and directing it is part of the script |
| 17 | Design it for real, anticipating what comes next | This document |
| 18 | Title screens | An episode contains things that are not scenes |
| 19 | Music scoring that knows surprising-and-bad from surprising-and-good | The engine must know what happened dramatically, not only what moved |
| 20 | Track scenes, episodes and seasons so they are easy to compare | The author needs to see the series from above |
| 21 | Easy for an AI to use, through MCP and a great command line; no AI in the tool itself. Writers iterate with Claude, and Claude uses the tool | The primary operator is an assistant, and the author may never open a file |
| 22 | MCP is the end state, not the start | The command line is the interface that has to be good now |
| 23 | I touch the tool only to tweak values and replay; everything else goes through Claude. Two loops; cover both | The tool has two users with different speeds and needs. See [how-it-is-used.md](how-it-is-used.md) |
| 24 | Focus on nudging: easy to identify what to change, change it, and test it quickly | The hand loop has three separate problems, and finding the value is the hardest. See [lld-nudging.md](lld-nudging.md) |
| 25 | Build it in phases, and show me the same known scene after each | A fixed yardstick turns "did it break?" into a yes or no. See [phases.md](phases.md) |
| 26 | Remove the slider panel; no pins; build the frame cache; then music scoring | Fewer ways to do one thing. Music arrived as predicted, and needed one new idea: whose side the audience is on |

## Five patterns

**1. Presentation churns; the model accumulates.** Rounds 2, 4, 11, 12, 13 and 14 each
changed how something looks or sounds, and four of them removed something built in an
earlier round (the paper look, moving text, the music note, the syllable hop). Over the same
rounds almost nothing was removed from the model: felt state, tells, position, stress and
carry-over were only ever added to. *Consequence: the model and its presentation must be
separate layers, with presentation cheap to replace.*

**2. Hand-written things become derived things.** Poses became tells (5). Tone became a
result of feeling (5). Rhythm became a result of stress (12). Bubble breaks became a result
of pauses (14). Reaction timing became a result of reflex (16). Each time, the author kept
the right to override. *Consequence: the engine is a chain of derivation steps, each
replaceable, each overridable, each able to say why it produced what it did.*

**3. Every value must be tunable by hand.** Timings (3), syllable notes and motion and
sounds (8), stress (12), beats (16). Each new parameter needed its own editor code, and
slider changes still cannot be undone. *Consequence: parameters are declared once, with
their range and meaning, and the editor is generated from the declarations.*

**4. The show keeps acquiring vocabulary.** Turn, scene, episode, season, beat, bubble,
take, featured, in passing. Each new word arrived as a correction ("a bubble should contain
one moment"). *Consequence: these units need to be first-class things in the data, so that a
new one is an addition and not a rewrite.*

**5. Rules are wanted wherever taste can be made consistent.** A turn needs a reason (4).
The audience ledger (6). No render with errors. "Is this codifiable?" (15). *Consequence:
checks are a first-class, extensible part of the engine, not a list inside one function.*

**6. The author works from above.** Carry-over and arcs (9), a known scene as a yardstick
(10), comparing units of the series (20). *Consequence: the series needs an index built from
the same resolved data the renderer uses, with descriptions and stable identities for every
unit.*

**7. The operator is an assistant.** "Claude does the work while I explain the scenes" (1),
"writers should use Claude to iterate, and Claude accesses the tool" (21). Between those rounds the assistant edited files by
hand, and one such edit failed silently. *Consequence: every change goes through typed,
validated commands, and the engine's replies are written to be read by an assistant: what
changed, what is wrong, how to look.*
| 27 | An object show: no people, no faces; a metaphor in which every detail, the room and the land included, has to fit; "we don't offer any information we don't have to" | The look is part of the meaning. A place needed rules of its own (symmetry, colour, nearness), and the engine's feelings and tells were switched off, not removed |
| 28 | Fewer cuts, a slower pace; a map between scenes that shows time passing | The viewer's sense of the world is built outside the scenes. An episode needed a land, days, and a title sequence that carries story |
| 29 | How do we find the rhythm of the whole show, so it flows like a song? | Time needed a second, coarser grid: bars and phrases, and beats that are placed on them |
| 30 | A ledger of what hurts; then pay it off. Then tech debt | The author manages the tool's health as well as the show's. See [pain-points.md](pain-points.md), [tech-debt.md](tech-debt.md) |
| 31 | A q+a and a written plan before a new idea is built; "nothing I didn't ask for" | The gap was never capability, it was unasked-for choices. See [working-agreement.md](working-agreement.md) |
| 32 | Nudge micro-timings of dialogue, sound and music myself, inside the tool, on my own computer | Round 3 again, at a finer grain: sounds, bars, cards and the camera all became things to drag |
| 33 | What do professional tools have? Build what would help you (the assistant) most | The assistant is a user whose needs can be asked about. Its answers were all about the hand-off: notes, a picture of the sound, the two copies in step |
| 34 | Let me watch you edit | Round 21's "seeing what the assistant changed", asked for outright. The editor became the place both loops are visible |
| 35 | Why two places to update? Put the bible in the tool, so we can see when we veer | The show's own rules are data the film can be checked against, not a document beside it |
| 36 | Name the kinds of motion; keep some for critical moments; say them in the storyboard before the details | The author is designing the viewer's experience over time: what becomes familiar, and what is held back. The level above the scene (outline, season) is where that is decided |

## How the first predictions did

The first version of this document ranked eleven likely asks. Four new requirements then
arrived:

| What was asked | Predicted? | Verdict |
|---|---|---|
| A writer works through an assistant | Yes, as "authoring at scale", ranked tenth of eleven | Right idea, badly under-weighted. Round 1 said it plainly and it was the premise of the whole project |
| Music scoring by dramatic meaning | Partly: "a backing track, recorded effects" | Predicted the plumbing and missed the point. The ask is for music that understands the story |
| Title screens | No | Missed. Nothing in the list imagined an episode holding anything but scenes |
| Tracking and comparing | No | Missed. The list was all about what is on screen, none about the author's view of the whole |

And the design, which matters more than the ranking:

| What was asked | Did it land in one place? |
|---|---|
| A writer works through an assistant | Yes. "The editor sends commands" generalised to "every operator sends commands" |
| Music scoring | Mostly. It is a derivation step and a track, as designed, but it needed a new idea: a track of dramatic events |
| Tracking and comparing | Yes, as a new reader of the score, but it exposed that units had no descriptions or stable identities |
| Title screens | **No.** The design assumed a scene was the only thing in an episode. It needed the segment |

The lesson taken: the first list extrapolated the last few rounds, which were all about
on-screen detail, and under-read the first round and the author's position outside the show.
The list below is rebuilt with that corrected.

## How the second predictions did

Of the fourteen likely asks listed below when rounds 27 to 34 began, these arrived:

| What was asked | Predicted? | Verdict |
|---|---|---|
| Decoration, on purpose: sets, props, richer bodies | Yes | Right, and larger than predicted: the look became part of the meaning, with rules of its own |
| A different stage | Partly | It arrived as a land and a raised bench, not as depth within a room |
| The rest of an episode's furniture | Yes | Right: a title sequence, journeys, captions, credits |
| Seeing what the assistant changed | Yes | Right, including "a way back" |
| The rhythm of a whole episode; bars | No | Missed. "Time is musical" was a decision, but only at the scale of a syllable |
| Tuning on the writer's own computer; two copies of a show | No | Missed. "Other writers using it" was the nearest, and assumed one place where a show lives |
| A written plan before building | No | Missed, and it is about the collaboration, not the tool: the list has never predicted one of those |

The lesson taken: the misses are again about the author's position outside the show (how they work, where, and at what
scale they hear it), which is the same lesson as last time.

## What is likely next

Ranked by how strongly the conversation points at each. The last column is what the
architecture must already allow, so that the ask is an addition.

| Likely ask | The signal | What must already be true |
|---|---|---|
| **Appraisal**: derive feelings from what was said and what is true | Offered in round 15 and deferred; pattern 2 | A derivation step can be inserted before expression. The world holds facts and who knows them |
| **Camera and cutting**: framing, cuts, reaction shots | "I've been paying very close attention to how TV is shot, edited, directed"; featured reactions already carry focus | Framing is a track like any other. Focus exists in the model, separate from how it is shown |
| **Masking**: showing a feeling other than the one felt | It is a puzzle show; a `take` already outranks tells | Felt and shown are separate values, with a step between them |
| **Decoration, on purpose**: sets, props, richer bodies | "We can add the decoration later"; the paper look was parked, not rejected | A body is a skin over abstract channels. A prop is an entity that cannot feel |
| **Seeing what the assistant changed**: each change next to its reason, and a way back | Round 21, and "I like to be very particular" | Changes can be rehearsed and undone; every change keeps the words that caused it |
| **The rest of an episode's furniture**: cold open, recap, credits, act breaks | Round 18 | An episode is a list of segments of different kinds |
| **Themes**: a motif for a character or an idea, recurring and varied | Round 19; the running-gag structure of the shows cited | Music is written as notes on the show's scale, and a cue can quote a theme |
| **Recorded sound and export to a music tool** | "Match the text to the music"; the tempo grid exists for it | Audio is a track on the same grid. Sounds are assets with a synthesised fallback |
| **Other writers using it** | "I assume many writers would want this too" | The engine and a show are separate; no step requires reading code or YAML |
| **Per-character exceptions to universal rules** | "Some people get louder when outnumbered" was left open in round 5 | A universal rule can be overridden per entity, like a tell |
| **Relationships**: state between two entities | A feeling already records who it is about; status is still one number | World state can be keyed by a pair, not only by one entity |
| **Richer audience model**: background sightings count less; setups and payoffs; running gags | Round 16; the references to Whedon and Hurwitz | The ledger reads the same resolved timeline as the renderer, including prominence |
| **Feelings that fade, and mixed feelings** | Carry-over made a feeling permanent until changed | Felt state is a set with a time behaviour, not a single slot |
| **A different stage**: depth, levels, entrances and exits | Position is one line of nine slots | Position is a channel with a type, not an integer baked into the renderer |

Three things the conversation suggests will *not* be asked for, and so are not designed for:
real-time interactivity (round 11: "this isn't a game"), photorealism or generated video
(rejected at the start for lack of control), and a model built into the engine (the author
wants an assistant to operate the tool, not a tool that is an assistant).
