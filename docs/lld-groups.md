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
| 1. The lock | What they go after (`library/locks.yaml`) | The obstacles, the crafts needed, what the crew is defined against |
| 2. The crew | Who is in it | The planner, why each would do it, who needs persuading, who cannot be lost |
| 3. The ties | How each sees each | The pecking order, who holds it together, who gets blamed |
| 4. The plan | The order, who does what, who relies on whom | Where it goes wrong, what each does when it does |
| 5. The twist | What the viewer is not told (`library/twists.yaml`) | Who is in on it, what it costs in trust, who wavers at the split |

## 7. The run-of-the-mill heist, as decided

Five decisions (a bank; five people; twenty ties; five steps; a staged failure) force 31 things
and narrow 4 more. Four stay open whatever is decided: the dialogue, the places, which obstacle
changes before the job, and the names.

Things nobody wrote, that came out of the rules:

- Nico, the face, whom nobody rates, is both what holds the crew together and who gets blamed.
- The job cracks at the vault, where Ruth (a locksmith) has to rely on Ines (a contractor), so
  the quarrel in the corridor is skilled labour against tech.
- If the trouble comes from outside instead, ranks close and the blame waits.
- The twist asks the two people who rate each other least to carry it together. The report flags
  that as a choice: either their contempt is the act, or the planner staked everything on it.
- Afterwards Sam, the most cautious and the only one who had to be talked into it, is the one
  kept in the dark, and trusts the planner at -2. The split is where he wavers.

## 8. What is not built

- **The scene engine does not use any of this.** Appraisal reads trust only. Rating, standing,
  craft, tendencies and the plan exist in the story report and nowhere on screen.
- **Ties do not change by rule in a scene.** "Deeds change rating" and "secrets change trust" are
  applied once each, by the report, at the fault line and after the twist.
- **The viewer as someone who knows or does not** is a line in the report, not a record.
- **Obstacles have no state** (set or not), and there is one stage, so no cutting between rooms.
- **The strengths are untested.** Pressure thresholds, strain and the pecking order's weights were
  chosen once, for one crew. A second story is the test.
