# Low-level design: groups, standing, tendencies, and a story as filters

Status: the model and the gate report are built and run on a second show, `shows/heist/`. None of
it is in the scene engine yet (section 8). No scene of the heist exists.

## 1. What this is for

The aim is to settle as much of a story as can be settled before any invention is needed. A
story is decided in an order, and each decision is a filter: the rules carry its consequences
as far as they reach, and what is left is smaller and better defined. At any moment everything
about the story is in one of three states.

| State | Meaning | Who handles it |
|---|---|---|
| Forced | Given the decisions so far, only one thing can be true | The rules |
| Narrowed | A few things could be | The rules list them; the writer picks |
| Open | Nothing constrains it yet | The writer invents it |

This is constraint propagation. The story does not have to be known in advance, only decided
in an order, and a decision that leaves nothing possible is reported as a problem to undo.

## 2. Standing: capable and willing

What society gave someone is their key, and what it withheld is their motive.

    profile:
      standing: {wealth: -2, status: -1, power: 1}     # after Weber; this is the facet they stand for
      craft: [people, movement]                        # which kinds of obstacle they can get past
      tells_self: loyalties                            # how they excuse it, after Sykes and Matza

- **Pressure** is derived: a need that is strong in them and that their standing does not meet
  (comfort and safety by wealth, esteem by status, control by power; belonging by people).
- **Would they do it** is pressure plus drive less caution: 3 or more says yes, 1 or 2 needs
  persuading, less walks away. This is the fraud triangle: pressure, opportunity (craft),
  rationalisation (`tells_self`).
- A facet is a position: what someone does, has and lacks. It is never a demographic.

## 3. Ties: how each sees each

A tie is one-directional: [trust, rating], each -2 to +2 (after Fiske's warmth and competence).

| | Rates them | Does not rate them |
|---|---|---|
| Trusts them | relies on | carries |
| Does not trust | watches | dismisses |

Read off the ties, never written: the pecking order (rated by the rest, plus dominance and
power), factions (parts joined by mutual trust), the hinge (whoever a part falls apart without),
the weak link (trusted and rated least), and cohesion (mean mutual trust). A bond written as
one number is still read as trust, so existing shows are unchanged.

## 4. The plan routes weight through the ties

A plan is the obstacles in order, who gets past each, and who they have to rely on while they
do. The strain on a step is how little the one relying trusts and rates the one relied on. The
step under most strain is the fault line: where the job goes wrong.

## 5. Tendencies: what groups usually do

A tendency is a general rule, declared once in `performance/tendencies.py`: a condition on the
situation, an effect, the finding it comes from, and how well that finding holds up. A
situation is who is present, whether trouble comes from inside or outside, whether anyone knows
whose doing it is, whether there is a clock, what each feels, and whether something was given.
A stronger tendency can silence a weaker one and says so. Nothing is random.

| Built | When | Then | Evidence |
|---|---|---|---|
| Common enemy | A threat from outside | Ranks close; blame is dropped until it passes | Strong |
| Threat rigidity | A threat and a clock | Everyone looks to the top of the pecking order | Moderate |
| Scapegoating | A loss, and nobody knows whose doing | Blame runs to the weak link; the warmest do not join in | Moderate |
| Emotional contagion | One feels it most | It spreads to those who trust them; a calm leader steadies | Moderate |
| Conformity | One alone against the rest | They go along out loud; one ally, or high dominance, holds out | Strong |
| Reciprocity | Something is given | It is returned in kind | Strong |

Designed and not built: pluralistic ignorance, the bystander effect, ingroup bias, the
attribution error (used once, at the fault line), social facilitation, group polarisation,
escalation of commitment, groupthink, triads, complicity, and trust falling faster than it
rises. Left out on purpose: the Stanford prison experiment and the classic deindividuation
studies, which do not hold up.

## 6. The gates

`story.yaml` holds the decisions in order, and `s2s story` reports each gate.

| Gate | Decision | What follows from it |
|---|---|---|
| 0. The theme | What it is about (`library/themes.yaml`) | What each excuse has to meet, whether anyone is scored against, what the ending has to do |
| 1. The lock | What they go after (`library/locks.yaml`) | The obstacles, the crafts needed, what the crew is defined against |
| 2. The crew | Who is in it | The planner, why each would do it, who needs persuading, who cannot be lost |
| 3. The ties | How each sees each | The pecking order, who holds it together, who gets blamed, what the crew already gives each of them |
| 4. The plan | The order, who does what, who relies on whom | Where it goes wrong, what each does when it does |
| 5. The twist | What the viewer is not told (`library/twists.yaml`) | Who feels it, who turns first, what giving back costs each |

### The theme, and nobody being good or bad

The theme of the heist is the writer's: people take what they think they need to survive, then
find they did not have to be that hard, feel it, and give back. Nobody in it is good or bad.
They are all afflicted by existence: things happen to them, and they try to survive, literally
and otherwise. The model already worked that way (what anyone does follows from what presses on
them), and the theme gate now holds it to that:

- **Everyone named has to be surviving something.** An entity with no pressure is reported as a
  wall, not a person. The mark had none, so he was given one: head office is closing his branch,
  and he too is taking to survive, with his own excuse.
- **Nobody is scored against.** The audience is with everyone, so harm to anyone is bad news.
- **Each excuse has to stop working,** and the excuse says what kind of event does it.
- **"They did not need to be that hard" is computed.** Pressure is a need their standing does not
  meet, and a group meets two needs by itself: enough trust meets belonging, and enough rating
  meets esteem. So the report says who no longer needs what they came for.
- **"They feel it" is the appraisal rule for shame:** bad for someone you are bonded to, and your
  own doing. So someone outside the crew has to stand for the world they are taking from
  (`world:`), and the crew has to have come to care about them before the harm lands.
- **The twist is the turn itself.** The standard twist, a failure that was staged, is reported
  as not serving the theme.

## 7. The heist, as decided

Six decisions (the theme; a bank; five people; their ties; five steps; the turn) force 45 things
and narrow 5 more. Six stay open: how each excuse breaks, a moment in which three of them come to
care about Dot, the dialogue, the places, which obstacle changes before the job, and the names.

Things nobody wrote, that came out of the rules:

- Nico, the face, whom nobody rates, is both what holds the crew together and who gets blamed.
- The job cracks at the vault, where Ruth (a locksmith) has to rely on Ines (a contractor), so
  the quarrel in the corridor is skilled labour against tech.
- By the time of the job the crew has already given Ruth and Nico what they came for (to be
  rated; to belong). Giving it back costs them nothing they still need.
- It costs Sam, Vera and Ines a great deal. Sam needs the money to live on; trust does not pay
  rent. Vera still has no control over anything. Ines is still not rated by anyone.
- Sam, who knows Dot, is the first to turn. Ruth, Nico and Ines have never met her, so the
  report says their turn is not earned until a scene makes them care.

## 8. What is not built

- **The scene engine does not use any of this.** Appraisal reads trust only. Rating, standing,
  craft, tendencies and the plan exist in the story report and nowhere on screen.
- **Ties do not change by rule in a scene.** "Deeds change rating" and "secrets change trust" are
  applied once each, by the report, at the fault line and after the twist.
- **The viewer as someone who knows or does not** is a line in the report, not a record.
- **Scenes still have `sympathy`,** which can set the audience against someone. A show whose theme says nobody is bad should refuse it; nothing checks that yet.
- **Obstacles have no state** (set or not), and there is one stage, so no cutting between rooms.
- **The strengths are untested.** Pressure thresholds, strain and the pecking order's weights were
  chosen once, for one crew. A second story is the test.
