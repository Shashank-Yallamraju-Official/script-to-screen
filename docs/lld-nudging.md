# Low-level design: the nudging loop

The writer watches a scene, feels that something is off, changes one value, and watches
again. This document designs that loop to the level of data shapes, commands and timings.
It refines build step 2 of [architecture.md](architecture.md) and decisions 16 and 17 of
[decisions.md](decisions.md).

## The design in one page

A nudge has three parts, and each has one idea that carries it.

| Part | The problem | The idea |
|---|---|---|
| **Identify** | "That pause is too long" is a feeling about a moment; the value behind it could be any of seven things | **Every stretch of screen time is owned by exactly one value.** Click the stretch, get its owner |
| **Change** | A value can live at six levels (this syllable up to the whole show), and hand work must survive the assistant's rewrites | **One knob, with a visible scope.** Hand-set values live in `tune:` blocks, so *where* a value is stored says *who* set it |
| **Test** | The feeling fades in about a second | **Release, and the moment replays itself** inside 100 ms, with a one-key flip between before and after |

Three findings from measuring the prototype shape everything else:

1. **A nudge costs 78 ms today, and 70 ms of that is avoidable.** The work a nudge actually
   needs takes about 20 ms. The rest is the audience ledger and a replay of earlier scenes,
   neither of which a nudge can change.
2. **The renderer is eight times faster than playback.** So replay can simply draw frames
   as it plays. No frame cache is needed to hit the target; one is designed here but built
   last, and only if a longer scene demands it.
3. **Mixing a whole scene's sound takes 12 ms.** So sound is remixed whole on every nudge.
   Per-turn audio stems were considered and dropped.

So the loop is fast enough with the plain design. The real work is in *identify* and in
keeping hand-tuned values safe.

**Not in scope:** changing words, feelings, structure or characters' rules (decision 16);
the assistant's command line beyond the three commands this loop shares with it.

## 1. A worked example

*"The gap after 'I saw.' feels too long."* The line is `I saw. You took it.`, two bubbles.

**Today.** The gap is not on the timeline as a thing. It is the breath after a full stop,
and the engine folds it into the length of the syllable "saw". To shorten it the writer must
know that, find the note for "saw" in the piano roll, and drag its right edge, which also
looks like making the word longer. Then press play, and scrub back.

**As designed.**

| Step | The writer | The tool |
|---|---|---|
| 1 | Pauses playback on the gap, or clicks it in the time strip | Selects the owner of that stretch: *breath after "saw"*, 2 steps, **inherited from the show** |
| 2 | Presses ↓ twice (or drags the knob) | Value becomes 1.5. Scope chip reads **this syllable**. The picture updates while the key is held |
| 3 | Lets go | The stretch replays with a second of lead-in and lead-out, with sound, and loops |
| 4 | Presses B | Flips to the old value and replays. B again flips back |
| 5 | Decides every full stop in the show should breathe like this; presses W until the chip reads **show** | The value moves from this syllable to the show's setting. The tool shows a count: *affects 41 breaths in 12 scenes* |
| 6 | Changes their mind; Ctrl+Z | Back to this syllable only |

Nothing was saved by hand, and nothing was typed.

## 2. Vocabulary

| Term | Meaning | Example |
|---|---|---|
| **Parameter** | A kind of tunable value, declared once | `breath`, `hold`, `overshoot` |
| **Instance** | A parameter at one place in the show | the breath after "saw" in turn 2 |
| **Scope** | The level a value is set at | syllable, turn, scene, entity, tone, show |
| **Effective value** | What the engine uses for an instance after looking through the scopes | 1.5 |
| **Address** | The text name of an instance or a scope | `s01/e01/03#2.s2.breath` |
| **Tune** | A value set by hand | everything in a `tune:` block |
| **Audition span** | The stretch of the scene that replays after a nudge | the gap, with a second either side |

## 3. Identify

### 3.1 Time ownership

Every turn's duration is laid end to end out of stretches, and each stretch has one owner.

```
 turn 2 ─────────────────────────────────────────────────────────────────────────────►
 │ pause │ latency │ I │ saw │ breath │ You │ took │ it │ breath │ beat (juno) │ hold │
   turn    entity    syllable  syllable  ...                       reaction      turn
```

| Stretch | Owner parameter | Narrowest scope |
|---|---|---|
| Before the speaker reacts | `pause` | turn |
| The speaker's own delay | `latency` (from tells) | entity |
| A voiced syllable | `length` | syllable |
| Silence after punctuation | `breath` | syllable |
| A featured reaction | `beat` | reaction |
| After the line | `hold` | turn |
| A turn with no line | `settle` | turn |

**The invariant:** for every scene, the stretches of a turn do not overlap and their lengths
sum to the turn's length. It is a test (section 9), because picking is only trustworthy if
there are no unowned gaps.

This requires one change to the engine: **breath becomes a value of its own.** Today
`speech.plan` adds the rest into the syllable's `len`. In the design a syllable has `length`
(voiced) and `breath` (silent), and its slot on the grid is their sum.

The build step emits the partition alongside the turns:

```python
Stretch = dict(start=float, length=float,    # in steps, from the start of the scene
               address=str,                  # the instance that owns it
               label=str)                    # 'breath after "saw"'
scene.stretches: list[Stretch]               # sorted, gap-free per turn
```

The editor draws it as a single strip under the ruler. That strip replaces the prototype's
separate handles for hold, pause and beat: one thing to learn.

### 3.2 Values that own no time

Overshoot, the bubble's pop, a sound's pitch and a tone's contour take no time of their own.
They are found through what they act on. The registry (4.1) says which events *exercise*
each parameter; the build already emits events with times. So for a playhead position the
editor can list what is **in play**:

```python
def in_play(scene, t, window=4):     # steps either side
    """-> instances, nearest first: the owner of the stretch at t, then every parameter
    exercised by an event within the window, then the speaking tone's and entity's values."""
```

The list is shown as a short row of icons beside the knob, with names on hover. Tab steps
through it. This is the answer to "something about how he turns is wrong": pause on the
turn, and *flip*, *ease* and *overshoot* are the first three icons.

### 3.3 Picking in the picture, and by words

- **Picture.** `draw_frame` already knows where it put each token, bubble and syllable. It
  returns a hit map (`[{box, address}]`) with the frame. Clicking a syllable selects its
  `length`; a token, the nearest event's parameters; the indicator, its three settings.
- **Words.** `/` opens a one-line search over each parameter's label and declared words
  ("bouncy" finds overshoot, "snappy" finds ease). Results are limited to what occurs in the
  current scene.

Build order within identify: strip, then in-play, then picture, then words. The first two
cover every parameter; the last two are shortcuts.

## 4. Change

### 4.1 The parameter registry

One declaration per parameter, in `script_to_screen/vocabulary/params.py` (built in phase 5, without scopes and the cascade, which slice N2 adds). The editor, the commands and the checks
are driven by it (decision 5).

```python
Param(
    key="breath",
    label="Breath",
    meaning="Silence after punctuation, before the next syllable.",
    unit="steps", lo=0, hi=16, step=0.5, fine=0.125,
    scopes=("syllable", "tone", "show"),        # narrowest first
    default=("timing", "breath"),               # where the show-wide value lives
    owns_time=True,
    exercised_by=(),                            # event kinds, for values that own no time
    rebuild="timing",                           # see 5.2
    words=("gap", "pause", "full stop", "breathing room"),
)
```

Initial contents, which also fixes the gap "not every value is reachable":

| Group | Parameters | Scopes |
|---|---|---|
| Turn timing | pause, hold, settle | turn, scene, show |
| Speech timing | length, breath | syllable, (tone, show for breath) |
| Speech shape | pitch, stress | syllable |
| Tone | rate, range, stretch, contour | tone, show |
| Entity | reflex, voice, latency | entity |
| Reactions | beat | reaction, show |
| Motion | ease, overshoot, flip, squash, bubble_pop, focus_dim | show (entity later) |
| Indicator | cursor_size, cursor_lift, cursor_tail | show |
| Voice | voice_attack, voice_ring, aside_volume | show, entity |
| Sounds | per sound: pitch, length, volume, timbre | show |

### 4.2 The scope cascade

The effective value of an instance is the first one found, looking from narrow to wide:

```
syllable/reaction → turn → scene → entity → tone → show → the engine's built-in default
```

A parameter uses only the scopes it declares. Within one scope, a hand-set value (in
`tune:`) beats a written one.

```python
def resolve(param, where) -> Resolved:
    """where = (scene, turn, syllable, entity, tone). Returns
    Resolved(value, scope, by)   # by: 'hand' | 'written' | 'default'
    plus .chain: every scope's value, for the scope chip's hover."""
```

Three operations on the cascade, each a command:

| Operation | Key | Effect |
|---|---|---|
| **Set** | ↑ ↓, drag | Writes at the narrowest scope by default, or the scope the chip shows |
| **Reset** | Backspace | Removes the value at the current scope; the instance inherits again |
| **Widen** | W (Shift+W narrows) | Moves the value one scope out and removes it here. Shows how many instances change before it applies |

The scope chip is the answer to "scope is visible": it always shows where the effective
value comes from, and a nudge can never write wider than the chip says.

### 4.3 Where hand-set values are stored

In a `tune:` block at the scope they belong to. The location is the record of who set it
(decision 17), so no per-value metadata is needed.

```yaml
# episodes/s01/e01/01-the-last-dumpling.yaml
tune: {hold: 6}                       # scene scope: every turn in this scene
turns:
  - id: 2
    who: juno
    say: I saw. You took it.
    why: She has waited all day to say this.
    tune:
      for: "I saw. You took it."      # the anchor: the words these values were tuned against
      pause: 3.5
      breath: {2: 1.5}                # syllable 2
      length: {4: 3}
      pitch: {5: 9}
      stress: {5: 2}
      beat: {1: 10}                   # reaction 1
```

```yaml
# entities/otis.yaml            # library/tones.yaml           # show.yaml
tune: {reflex: 1.5}             accusing: {tune: {rate: 2.5}}  tune: {breath: 1.5}
```

Rules:

- **Sparse.** Per-syllable values are keyed by syllable number. This replaces the full
  `rhythm:`, `melody:` and `stress:` lists as the hand-tuning format; the lists stay valid
  as *written* values, for a line the assistant composes whole.
- **Only the nudge commands write `tune:`.** The assistant's authoring commands write
  outside it and never touch it, except through the discard rule below.
- **Removing a `tune:` block always restores what the engine or the assistant chose.**

### 4.4 Anchors: what happens when the words change

A syllable-level tune is only meaningful for the words it was tuned against.

| The line's text | Syllable-level tunes | Turn-level tunes (pause, hold) |
|---|---|---|
| Matches `for:` | Applied | Applied |
| Differs | **Not applied.** Reported as orphaned, kept in the file | Applied, flagged *tuned against earlier wording* |

Orphans are a warning in the checks, visible in the editor as a mark on the turn, and
listed by `s2s tune list --orphans`. The assistant's line-changing command reports
"discards 4 hand-tuned values" when rehearsed, which is rule 2 of
[how-it-is-used.md](how-it-is-used.md). First version: no attempt to carry tunes across to
the matching syllables of the new wording; that is a later refinement.

### 4.5 Addresses

```
<scene>#<turn>.<param>                s01/e01/03#2.hold
<scene>#<turn>.s<n>.<param>           s01/e01/03#2.s2.breath
<scene>#<turn>.r<n>.<param>           s01/e01/03#2.r1.beat
<scene>.<param>                       s01/e01/03.hold
@<entity>.<param>                     @otis.reflex
~<tone>.<param>                       ~accusing.rate
<group>.<param>                       feel.overshoot   sounds.thud.pitch
```

`<turn>` is the turn's `id`. The grammar is the same one the assistant uses on the command
line, so "the pause before turn 2 in the thermostat scene" is one string in both loops.

### 4.6 Commands

Three, shared by the editor and the command line (decision 12).

```
s2s tune set   <address> <value> [--scope S] [--dry-run] [--json]
s2s tune reset <address>         [--scope S]
s2s tune widen <address>         [--to S]
s2s tune list  [<scene>] [--orphans] [--json]     # every hand-set value beside what it replaced
s2s tune undo | redo
```

Each returns the same shape:

```json
{"ok": true, "address": "s01/e01/03#2.s2.breath", "scope": "syllable",
 "before": {"value": 2, "scope": "show", "by": "default"},
 "after":  {"value": 1.5, "scope": "syllable", "by": "hand"},
 "affects": 1, "rebuild": "timing", "audition": [38.0, 56.0], "undo": "j-0142"}
```

### 4.7 Autosave, undo and following the files

The prototype's editor keeps its own copy and overwrites the file on save. The design
removes the copy.

- **A gesture is one command.** While a key is held or a knob dragged, the editor previews
  in memory. On release it sends one `set`. Ctrl+Z undoes a gesture, not a keystroke.
- **Every command writes the file at once**, by writing a temporary file and renaming it.
  There is no Save and no unsaved state.
- **Undo is a journal** at `<show>/.s2s/journal.jsonl`: one line per command with its
  address, before and after. It survives closing the editor, covers sliders (which the
  prototype could not undo), and is what `s2s tune undo` reads. Not committed to git.
- **The editor follows the files.** The server checks modification times four times a
  second. If a file changed underneath it, it rebuilds and the page refreshes its state.
  Because the editor holds nothing unsaved, there is nothing to merge: the only conflict
  left is a gesture in progress, which is re-applied by address on top of the new file, or
  dropped with a notice if its address no longer exists.
- **Undo after an outside change** applies only if the value is still the one the journal
  recorded as "after"; otherwise it is refused with the reason.

### 4.8 The control

One knob for whichever instance is selected. Per the standing rule for this tool's screens:
almost no text, meaning on hover.

```
┌──────────────────────────── picture ─────────────────────────────┐
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
 ruler      |....|....|....|....|....|....|....|....|
 ownership  [pause][l][ I ][saw][▓▓][You][took][it][▓][ beat ][hold]     ▓▓ = selected
 lanes      (turn / felt / say / notes, as today, read-only context)

 ◉ 1.5   ▸syllable·turn·scene·show   ⟲   A|B        ◌ ◌ ◌ ◌   ← in play
 knob     scope chip                reset  compare    other candidates
```

| Key | Does |
|---|---|
| Click a stretch, a note, or the picture | Select what owns it |
| Tab / Shift+Tab | Next / previous candidate in play |
| ↑ ↓ | Nudge by the parameter's step (Shift: fine step) |
| Backspace | Reset to inherited |
| W / Shift+W | Widen / narrow scope |
| Enter | Replay the audition span |
| B | Flip before / after, and replay |
| L | Loop on or off |
| ← → Space | Move, play (unchanged) |
| / | Find a parameter by word |
| P | Pin this moment (see open questions) |
| Ctrl/Cmd+Z, Shift+Z | Undo, redo |

The slider panel (T) is retired: every slider in it is reachable through the knob.

## 5. Test

### 5.1 Measurements and the budget

Prototype, scene `03-the-thermostat` (11.4 s, 682 frames, 5 turns), median of 10 to 60 runs:

| Operation | ms |
|---|---|
| One nudge end to end, today | **78.4** |
| of which: audience ledger over the show | 69.7 |
| Build the scene, replaying earlier scenes for carry-over | 40.3 |
| Build the scene, carry-over already known | 12.9 |
| Mix the whole scene's audio | 11.5 |
| Draw and encode a frame, half size / full size | 2.1 / 7.8 |
| Read / write the scene file keeping comments | 4.7 / 2.5 |

Budget, from releasing the key to the replay starting:

| Step | Target ms |
|---|---|
| Apply the command and write the file | 5 |
| Rebuild the scene (carry-over from cache) | 15 |
| Remix audio | 15 |
| First frame of the audition span | 5 |
| Network, decode, schedule | 20 |
| **Total** | **60, with a hard limit of 100** |

During a drag, picture-only preview (rebuild plus one frame) is about 15 ms, so the frame
under the playhead tracks the knob live.

### 5.2 What a nudge has to redo

Each parameter declares a rebuild class. This is what takes the ledger and the earlier
scenes off the path.

| Class | Parameters | Redo |
|---|---|---|
| `look` | Motion, indicator, focus_dim | Nothing but frames |
| `sound` | Sounds, voice, pitch | Audio only |
| `timing` | Everything that owns time; stress; tone rate; reflex | Scene build, audio, frames from the change onward |

No tunable parameter can change what is felt, who stands where, or which tells show, so
**carry-over and the ledger are never recomputed by a nudge.** Carry-over into the scene is
computed once when the scene is opened and again only when an earlier scene's file changes.
The ledger runs when the files change through the writing loop, and one second after the
last nudge as a safety net. A test asserts that a `tune` command leaves the ledger's output
identical.

### 5.3 Frames

Naive design, and it is enough: after a nudge, drop the frames the rebuild class
invalidates, and draw from the start of the audition span as playback needs them. At 2 ms a
frame against 16.7 ms of playback per frame, the renderer stays eight times ahead.

Where it would break: full-size preview (only twice as fast as playback), scenes of several
minutes when scrubbing far from the change, and richer skins later. The fix is designed but
deferred:

```python
fingerprint(turn) = hash(state entering the turn, the turn's resolved values,
                         every look-class value, preview size)
cache[(fingerprint, frame number within the turn)] -> jpeg
```

Frames are keyed by what the turn *is*, not when it happens, so a turn that merely moved
later in time keeps its frames. **Build it when a 99th-percentile nudge exceeds 100 ms on a
real scene, not before.**

The renderer stays the single Python one (decision: the replay must be the final picture).
Drawing in the browser would be faster to respond but would be a second renderer to keep
identical. Revisit only if the budget cannot be met with the cache.

### 5.4 Sound

The whole scene is remixed on every `sound` or `timing` nudge (12 ms) and sent as one
buffer; the browser plays it from the audition span's start with WebAudio so picture and
sound share a clock. Per-turn stems were considered and are not needed at this cost.
Revisit when a scene's mix exceeds 30 ms.

### 5.5 The audition span

What replays after a nudge. It must show the change with enough before it to feel the
rhythm, and no more.

| Selected | Span |
|---|---|
| A stretch that owns time | The stretch, plus 8 steps (one second) before and after |
| A syllable's pitch, stress or length | Its bubble, plus 4 steps either side |
| A value that owns no time | The nearest event that exercises it, plus 8 steps either side |
| A value at tone, entity or show scope | As above, in the current scene; [ and ] step through other places it applies |

Lead-in and lead-out are themselves show settings. The span is returned by every command
(`"audition"` in 4.6), so the assistant can render the same clip the writer just watched.

After a release: replay once; with loop on, keep replaying with half a second of silence
between passes.

### 5.6 Before and after

When an instance is selected, the server keeps two builds: **A**, the scene as it was at
selection, and **B**, the scene now. B flips between them and replays. Both are already
built, so the flip costs one audio swap and no rebuild. The A build is dropped when the
selection changes. A small A|B mark shows which is playing; nothing else on screen changes,
so the comparison is of the scene and not of the interface.

## 6. Server interface

The editor's server becomes a thin layer over the commands.

| Request | Returns |
|---|---|
| `GET /state?scene=` | Turns, stretches, events, the file's version, orphans |
| `GET /in-play?t=` | Ranked instances with resolved value, scope chain, range |
| `POST /preview {address, value}` | Applies in memory only; returns the changed stretches and a frame at `t` |
| `POST /tune {op, address, value?, scope?}` | The command result of 4.6; writes the file |
| `POST /undo`, `/redo` | The command result |
| `GET /frame?n=&build=A\|B` | JPEG, with the hit map in a header on request |
| `GET /audio?build=A\|B` | WAV of the scene |
| `GET /events` (server-sent) | `changed` when files move underneath, with the new version |

`/patch`, `/tune` (old meaning), `/save` and the prototype's `Session` copy are removed.

## 7. Module changes

| File | Change |
|---|---|
| `script_to_screen/params.py` (new) | The registry, `resolve`, address parsing |
| `script_to_screen/tune.py` (new) | The three commands, the journal, atomic writes, anchors and orphans |
| `script_to_screen/speech.py` | `breath` separate from `length`; accepts sparse per-syllable values |
| `script_to_screen/model.py` | Reads values through `resolve`; emits `stretches`; accepts carry-over from a cache |
| `script_to_screen/draw.py` | Returns a hit map |
| `script_to_screen/editor.py` | Becomes the server of section 6; holds two builds and no file copy; watches files |
| `script_to_screen/editor.html` | Ownership strip, knob, scope chip, in-play row, A/B; slider panel removed |
| `script_to_screen/cli.py` | `s2s tune ...` |
| `script_to_screen/ledger.py` | No change; no longer called on a nudge |

## 8. Migration

Schema 1 to 2, with a script (decision 8):

- `pause:` and `hold:` on a turn stay where they are, as written values.
- `rhythm:` lists are split into `length` and `breath` where the line has punctuation.
- Nothing is moved into `tune:` automatically: the prototype did not record who set a value.

## 9. Tests

| Promise | Test |
|---|---|
| Every moment has one owner | For every scene in the demo show and for generated scenes: stretches in a turn do not overlap and sum to the turn's length |
| The cascade resolves narrowest first, hand over written | Table-driven, every scope pair |
| Reset restores inheritance; widen preserves the effective value here | Round trips |
| A nudge changes only its value in the file | Diff of the file is one line; comments and order kept |
| A tune survives the assistant changing another turn | Edit the file outside, nudge value still resolved |
| Changed words orphan syllable tunes and keep turn tunes | Anchor mismatch case |
| A nudge cannot change the story | Ledger output and carry-out identical before and after any `tune set`, for every registered parameter |
| Undo is exact, including after restart | File bytes equal after set then undo, with the process restarted between |
| Undo refuses when the value moved underneath | Outside edit between set and undo |
| The loop is fast | `tune set` on the benchmark scene: median under 40 ms, worst under 100 ms, in CI with a generous multiplier |
| The picture is honest | A frame from the editor's B build equals the same frame from `s2s render` |

## 10. Build order

Each slice is usable on its own and ends with something the writer can feel.

| # | Slice | Done when |
|---|---|---|
| 1 | **Fast and safe.** Take the ledger and earlier scenes off the nudge path. Autosave by command, journal undo, follow the files | A nudge is under 40 ms. Editing the file in another window while the editor is open loses nothing. Sliders undo |
| 2 | **Registry and cascade.** `params.py`, `resolve`, `tune:` blocks, the three commands, addresses, schema 2 | `s2s tune set s01/e01/03#2.hold 9 --dry-run --json` works; every value in 4.1 is settable |
| 3 | **Ownership.** Breath as its own value, stretches, the strip, the knob and scope chip | The worked example in section 1 can be done up to step 3 without touching the piano roll |
| 4 | **Audition and compare.** Spans, auto-replay, loop, A/B | Steps 3 and 4 of the worked example |
| 5 | **In play, widen, anchors.** The candidate row, W with its count, orphans | Steps 5 and 6. "How he turns is wrong" finds flip, ease and overshoot |
| 6 | **Shortcuts.** Picking in the picture, search by word | Clicking a syllable in the bubble selects it |
| 7 | **Frame cache.** Only if measured need | Worst nudge under 100 ms on the longest real scene |

Slices 1 and 2 are the ones that also unblock the writing loop: they are build steps 1 and 2
of the architecture, done for the tuning commands first.

## 11. Open questions

| Question | Recommendation | Why it is open |
|---|---|---|
| **Keep pins?** A mark on a moment with a few words, for the assistant | Yes, minimal: P, one line of text, stored in the scene's `pins:` list. It is the only non-number the editor writes | It is the one place the editor accepts typing, which cuts against "only to tweak params" |
| **Default scope of a nudge** | Narrowest, always; widening is deliberate | The alternative, "remember my last scope", saves keystrokes and risks silent show-wide changes |
| **Motion per entity** | Not yet; show-wide only, with the cascade ready for it | Per-character motion is characterisation, which may belong to tells and the writing loop |
| **Should widening look for a pattern?** "You shortened 9 of 11 breaths after accusations" | Leave to the assistant, reading `s2s tune list` | It is inference, and the tool holds no AI (decision 13) |
| **Carrying tunes across a reworded line** | Later, by matching unchanged syllables | Needs real cases to see what the writer expects |
