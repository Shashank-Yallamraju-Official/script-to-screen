# How the requirements evolved

The prototype was built over about twenty rounds of feedback. This document reads those
rounds as data: what was asked, what each ask revealed, the patterns across them, and what
those patterns predict will be asked next. The architecture in
[architecture.md](architecture.md) is designed against the predictions, not just the present.

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

## What is likely next

Ranked by how strongly the conversation points at each. The last column is what the
architecture must already allow, so that the ask is an addition.

| Likely ask | The signal | What must already be true |
|---|---|---|
| **Appraisal**: derive feelings from what was said and what is true | Offered in round 15 and deferred; pattern 2 | A derivation step can be inserted before expression. The world holds facts and who knows them |
| **Camera and cutting**: framing, cuts, reaction shots | "I've been paying very close attention to how TV is shot, edited, directed"; featured reactions already carry focus | Framing is a track like any other. Focus exists in the model, separate from how it is shown |
| **Masking**: showing a feeling other than the one felt | It is a puzzle show; a `take` already outranks tells | Felt and shown are separate values, with a step between them |
| **Decoration, on purpose**: sets, props, richer bodies | "We can add the decoration later"; the paper look was parked, not rejected | A body is a skin over abstract channels. A prop is an entity that cannot feel |
| **Real sound**: a backing track, recorded effects, export to a music tool | "Match the text to the music"; the tempo grid exists for it | Audio is a track on the same grid. Sounds are assets with a synthesised fallback |
| **Per-character exceptions to universal rules** | "Some people get louder when outnumbered" was left open in round 5 | A universal rule can be overridden per entity, like a tell |
| **Relationships**: state between two entities | A feeling already records who it is about; status is still one number | World state can be keyed by a pair, not only by one entity |
| **Richer audience model**: background sightings count less; setups and payoffs; running gags | Round 16; the references to Whedon and Hurwitz | The ledger reads the same resolved timeline as the renderer, including prominence |
| **Feelings that fade, and mixed feelings** | Carry-over made a feeling permanent until changed | Felt state is a set with a time behaviour, not a single slot |
| **Authoring at scale**: a series bible, scene drafts from a description, review of changes | The original division of labour in round 1 | The script format has a published schema, stable across engine versions |
| **A different stage**: depth, levels, entrances and exits | Position is one line of nine slots | Position is a channel with a type, not an integer baked into the renderer |

Two things the conversation suggests will *not* be asked for, and so are not designed for:
real-time interactivity (round 11: "this isn't a game"), and photorealism or generated
video (rejected at the start for lack of control).
