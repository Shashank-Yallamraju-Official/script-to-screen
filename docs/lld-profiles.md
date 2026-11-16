# Low-level design: profiles, regards and appraisal

Status: slices P1 and P2 are built (profiles, bonds, facts, events, and appraisal with the three
changes of section 7; see section 10). P3 to P5 are designed only. The prototype the rule was
first tested with is kept in `studies/appraisal/` as it was.

## 1. What this is for

Today a scene says what everyone feels: `feel: {otis: {shame: 2}}`. The engine then works out
what shows, what the music does and where the camera looks. The writer still decides every
feeling by hand, and a single scene implies far more than it states: who else would react, how
it would go in another room, what each character is now inclined to do.

The goal is to say **who the characters are and what happened**, and have the feelings follow.
Then a setup can be explored without writing a story: change who is in the room, who knows
what, or where it happens, and read off how everyone reacts.

Dialogue is out of scope. The tool has no AI inside it (decision 13) and does not choose words.

## 2. The chain

    profile ─┐
    regards ─┤                 what they      what they are
    bonds   ─┼─► APPRAISAL ─►  feel       ─►  inclined to do  ─► (the writer picks what happens next)
    facts   ─┤   of an event     │
    event   ─┘                   └─► tells ─► what shows ─► music, camera      (exists today)

Appraisal is one more derivation step in the performance layer, in front of the steps that
exist. Like them it can be overruled: a `feel:` written on a turn wins over the derived one.

## 3. The records

| Record | What it holds | Lives in | Changes |
|---|---|---|---|
| **Profile** | Temperament (4 dials) and needs (5 strengths) | The entity's sheet | Over a season, through `arc` |
| **Bond** | How one character regards another, one way, -2 to +2 | The entity's sheet | By a turn, logged, carried |
| **Thing** | A place, or a piece in it, with an `id` and the need it `serves` | The place file | Not at all (item state is a later design) |
| **Regard** | A character's ground in a place and charge toward a thing | Derived from profile and thing; a turn can set it | By a turn, logged, carried |
| **Fact** | Something true, who did it, and who knows | A scene, then the world | By a turn (`reveal`), logged, carried |
| **Event** | What happened: kind, who did it, to whom, which need, how big | A turn | n/a |

### Profile

    profile:
      temperament: {drive: 2, caution: 1, dominance: -1, warmth: 1}     # each -2 to +2
      needs: {comfort: 2}                                               # each 0 to 2; unlisted needs are 1

| Dial | From | High means | Drives |
|---|---|---|---|
| drive | Approach system (Gray) | Pulled hard toward what they want | Good feelings land harder; stands nearer wanted things; answers sooner |
| caution | Avoidance system (Gray) | Hit hard by threat | Bad feelings land harder; stands further from dreaded things; hesitates |
| dominance | Interpersonal circumplex | Takes charge | Power (see 4); base `status` |
| warmth | Interpersonal circumplex | Moves toward others | Stands closer to those they are bonded to; turns to whoever speaks |

Needs: comfort, safety, belonging, esteem, control. Everyone has each a little (1); a profile
says which are strong (2) or absent (0). The two temperament models are established. The list
of needs is a working vocabulary trimmed from Maslow's categories plus autonomy, chosen because
household things map onto it; it has no standing as a set.

`status` and `reflex` on today's sheets become defaults derived from dominance and drive, and
can still be written. `tells` do not change: how a feeling leaks is the character's signature.

### Thing and regard

    pieces:
      - {id: fridge, kind: fridge, at: 7.7, serves: comfort}

A regard has two parts. **Ground** is whose turf a place is, and adds to power there.
**Charge** is what a thing makes a character feel, and is a standing feeling aimed `at:` the
thing. By default, charge = the character's need x what the thing serves (Otis, comfort 2, and
a fridge that serves comfort: joy 2). A turn can set a regard outright, which is how an empty
plate becomes evidence:

    regard: {otis: {plate: {shame: 2}}}

A regard drives placement (an entity entering with no slot written stands near what it is
drawn to and away from what it dreads), attention, and triggers (a line that names a thing, or
someone walking to it, fires its charge).

### Fact

    facts:
      dumpling: {doer: otis, knows: [otis, juno]}

### Event

    event: {kind: threat, need: esteem, size: 2, by: juno, target: otis, fact: dumpling, accuses: true}

| Kind | Meaning |
|---|---|
| gain / loss | Something good or bad for a need has happened |
| threat / relief | Something bad may happen / no longer will |
| reveal | A fact becomes known to someone (it changes `knows`, and is usually a loss or relief as well) |

`size` is how big the event is in itself: 1 slight, 2 pointed, 3 undeniable. Common events get
short forms (`accuse`, `prove`, `confess`, `forgive`, `catch`) that expand to these.

## 4. Appraisal

Three questions, after Lazarus and Ortony, Clore and Collins, cut down to what the show's six
emotions can express.

| Good or bad for my needs? | Whose doing? | Can I answer it? | Feeling |
|---|---|---|---|
| Bad, for esteem or belonging | Mine | (any) | Shame |
| Bad | Someone else's | Yes | Anger |
| Bad, or a threat to safety | Someone else's, or no one's | No | Fear |
| Bad, and over | No one's | No | Sadness |
| Good | (any) | (any) | Joy |

- **How strong:** the event's size plus the strength of the need it touches, bent one step by
  temperament (caution for bad feelings, drive for good ones), kept within 1 to 3.
- **Whose doing:** from the event's `by` and the fact's `doer`.
- **Can I answer it (power):** dominance + ground + whether my side outnumbers the other.
  At 1 or more, yes.
- **The one who did it** feels joy if they accused someone they know is guilty and need
  control, and shame if they harmed someone they are bonded to.
- **A bystander** feels it through their bond to whoever it happened to: bad for a friend is
  fear, bad for a rival is joy.

### Tendency

Each feeling inclines its owner to do something. These are the branches offered to the writer.

| Feeling | Inclined to | Bent by |
|---|---|---|
| Fear | Retreat, freeze | High caution: freeze |
| Anger | Confront, close in | Low power: sulk |
| Shame | Hide, deny, deflect | High dominance: attack back |
| Joy | Approach, share, press | Low warmth: gloat |
| Sadness | Withdraw | High warmth: seek someone |
| Surprise | Stop and look | |

## 5. What the writer gets

- `s2s what-if <setup> --event ...`: the reaction table for one event, with each feeling's
  reason and each character's inclination. Change who is present, who knows, or the place, and
  compare.
- A scene whose turns carry `event:` in place of `feel:` and most `react:` entries.
- `s2s explain` gains a line per feeling: which need, whose doing, what power.

## 6. Proof: the rule against the four scenes of s01e01

`studies/appraisal/model.py` implements section 4 in about a hundred lines.
`studies/appraisal/setups.yaml` restates the four scenes as profiles, facts and events, beside
the feelings written by hand. The profiles were fixed before the comparison was run and not
adjusted afterwards.

| Scene | Event | Who | Written by hand | Model | Verdict |
|---|---|---|---|---|---|
| the-last-dumpling | Juno says someone ate the last dumpling | juno | joy 1 | joy 2 | right feeling, off by one |
| the-last-dumpling | Juno says someone ate the last dumpling | otis | shame 2 | shame 2 | match |
| the-last-dumpling | Juno points out the sauce on his chin | juno | nothing | joy 2 | extra |
| the-last-dumpling | Juno points out the sauce on his chin | otis | shame 3 | shame 3 | match |
| the-vase | Juno says the vase was fine this morning | bix | nothing | fear 2 | extra |
| the-vase | Juno says the vase was fine this morning | otis | shame 2 | shame 2 | match |
| the-vase | Bix says it saw | bix | nothing | joy 1 and shame 3 | extra |
| the-vase | Bix says it saw | otis | shame 3 | shame 3 | match |
| the-thermostat | (before the scene) Bix bumps the thermostat dial | bix | shame 1 | shame 2 | right feeling, off by one |
| the-thermostat | Juno asks which of them touched the thermostat | otis | shame 3 | fear 2 | wrong feeling |
| the-thermostat | Juno asks which of them touched the thermostat | bix | nothing | shame 3 | extra |
| the-thermostat | Nobody answers, and it is eighty degrees | juno | anger 2 | anger 2 | match |
| the-thermostat | Nobody answers, and it is eighty degrees | bix | nothing | fear 3 | extra |
| lights-out | (before the scene) Otis took the blame for the thermostat | bix | shame 2 | shame 2 | match |
| lights-out | Bix confesses to Otis | otis | nothing | fear 1 | extra |
| lights-out | Bix confesses to Otis | bix | shame 3 | shame 3 | match |
| lights-out | Otis learns he was blamed for what Bix did | otis | joy 3 | joy 3 | match |
| lights-out | Otis hands Bix his own excuse | bix | joy 2 | joy 2 | match |
| lights-out | Juno is in the doorway, having heard | otis | fear 2 | fear 2 | match |
| lights-out | Juno is in the doorway, having heard | bix | fear 2 | fear 3 | right feeling, off by one |
| lights-out | Juno has caught them both | bix | nothing | joy 1 | extra |
| lights-out | Juno has caught them both | juno | joy 1 | joy 2 | right feeling, off by one |

**Of the 15 feelings written by hand: 10 exact, 4 the right feeling one step too strong, 1 the
wrong feeling.** The model also produced 7 feelings the scripts do not have.

What the misses say:

- **The wrong feeling (Otis, asked about the thermostat).** The script has him still carrying
  shame from the vase and re-aiming it at Juno. The model appraises the new accusation alone:
  he did not do it and cannot answer her, so it gives fear. A standing strong feeling should
  colour the next appraisal (mood carry-over). The model has no such rule. It needs one, or
  this stays a hand-written override.
- **Off by one, three of four on the strong side for joy and shame.** Juno's joy at being right
  is 2 where the scripts say 1, twice. Either her drive should not be bent upward or a slight
  gain should stay slight. One rule change would fix all three; it has not been made, so that
  the count above is honest.

What the extras say:

| Extra | Verdict |
|---|---|
| Bix, shame 3, when Juno asks who touched the thermostat | A catch. Bix did it, and the script gives it no reaction at all |
| Bix, shame 3, on telling Juno it saw Otis break the vase | A catch. The next scene says Otis will not face Bix for this; Bix's side of it was never written |
| Bix, fear 2, when Otis is accused over the vase | Plausible: it knows, and is bonded to him |
| Juno, joy again, at the sauce | Harmless: the same feeling continuing |
| Bix, fear 3, when Juno is angry that nobody answers | Wrong reason. It fires through Bix's bond to Juno, but Bix caused the problem |
| Otis, fear 1, when Bix confesses | Wrong. He is about to be delighted |
| Bix, joy 1, when Juno catches them | Wrong. Bix is one of the two caught |

Three look like things the scripts missed, one is harmless, and three are wrong. The three
wrong ones share a cause: the bystander rule fires even when the bystander has a stake of
their own in the event. It should apply only to those with none.

**How much this proves.** The emotion and who feels it are fair tests. The strength is a
weaker one, because the events were restated by someone who knew the answers, and an event's
size feeds its strength directly. Fifteen feelings in one episode with three characters is a
small sample. It is enough to say the rule is worth building and to name three changes; it is
not enough to say the rule is right.

## 7. Changes the proof calls for

1. Mood carry-over: a standing feeling at 2 or more bends the next appraisal toward itself.
2. The bystander rule applies only to someone with no stake of their own in the event.
3. A slight gain stays slight: temperament bends size 2 and 3 events, not size 1.

## 8. Build order

| Slice | What | Ends with |
|---|---|---|
| P1 | Profiles on the three sheets; facts and bonds in the world, logged and carried; `event:` on a turn; appraisal as a derivation step with `feel:` as the override | s01e01 re-rendered from events, with every difference from today's feelings listed |
| P2 | The three changes in section 7, each checked against the table above | The same table, re-run |
| P3 | `s2s what-if` and tendencies | A reaction table for one setup in four variations |
| P4 | Things that `serve` needs; regards; placement and attention from regards | A scene where nobody's slot is written |
| P5 | Regards and facts changed by turns; the camera puts a charged thing in frame | The dumpling scene with the plate in shot when it matters |

## 9. Open questions

- **Is power one number?** Dominance, ground and numbers are added together. They may need to
  stay separate (someone can be on their own ground and still outnumbered into silence).
- **Guilt against shame, envy, relief, pride.** The six emotions cannot say these. Add
  emotions, or accept the loss?
- **Do bonds change by rule?** Being told on should lower a bond. Derived, or always written?
- **Who knows what the audience knows?** Facts have knowers among the characters. The audience
  is a knower too, and dramatic irony is the gap between them. The ledger is the place for it.
- **Zones and item state** (a doorway; a vase that is broken) are deliberately left out.

## 10. What was built (P1, P2), and what it changed in s01e01

`performance/appraisal.py` is the step. The four scenes of s01e01 now carry `facts:` and
`event:` in place of every `feel:` but one, and the three entities have profiles and bonds.
Compared with the feelings that were written by hand, turn by turn:

| Scene | Who | By hand | From events | Verdict |
|---|---|---|---|---|
| The vase, as Bix says "I saw." | bix | calm | shame 3, about otis | Kept. Bix told on someone it is bonded to, and now says the line turning away from him |
| The thermostat, as Juno asks who touched it | bix | shame 1 | shame 3, about juno | Kept. Bix did it and is being asked |
| Lights out, "Vases fall." | bix | joy 2 | joy 1 | A slight event stays slight. Arguably forgiveness is not slight; the event's size was left as first written |
| Lights out, Juno in the doorway | bix | fear 2 | fear 3 | Bix's caution and its need for safety both raise it |

Every other feeling in the episode (13) comes out as it was written, including Otis carrying
his shame from the vase into the thermostat, which the first prototype got wrong and the
carry-over rule now gets right. One worked-out feeling is overruled in the script: Bix's fear
for Otis when Juno first mentions the vase, so that Juno and Bix still read as a pair there.

Differences from the design: facts are declared per scene and are not yet carried between
scenes; the short forms for common events (`accuse`, `confess`) are not built; `warmth` drives
nothing yet.
