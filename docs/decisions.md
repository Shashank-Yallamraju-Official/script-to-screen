# Decisions

Each record is a choice that would be expensive to reverse, with the alternative that was
turned down. Add to the end; do not rewrite history. If a decision is replaced, say so in a
new record.

## 1. Four layers, each a pure function of the one below

**Decision.** Script, world, performance, presentation. Data flows one way. The editor and
the checks read layers and send commands; they hold no show logic.

**Instead of** one model that also knows how things look, which is what the prototype has.

**Because** presentation changed in six rounds of feedback and the model was never cut back.
The thing that changes most must be the cheapest to change.

**Costs.** More structure than a prototype needs. A value that is awkward to express as a
track will be tempting to pass around the side; that temptation is the thing to resist.

## 2. The score is the contract

**Decision.** The performance layer's output is a set of named tracks on the tempo grid.
Renderers, audio, the ledger, the editor and exporters read the score and nothing else.

**Instead of** each consumer calling into the model for what it needs.

**Because** every consumer added so far needed something slightly different from the model,
and got it by the model growing a field. One documented shape stops that.

**Costs.** The score must be designed carefully once. Changing it later touches everything.

## 3. World state is a replay of events

**Decision.** Every change to what is true is an event with a time, a subject, a cause and
a reason. State at a moment is computed by replaying up to it.

**Instead of** mutable state that scenes hand to each other, which is what carry-over does
now.

**Because** carry-over, off-screen events and arcs are the same thing seen three ways, and
the likely next features (facts, who knows them, relationships, fading feelings) are more of
it. It also answers "why is he like this now?" for free.

**Costs.** Replay must be cached to stay fast over a long series. Events need stable
identities so that editing an early scene does not silently change a late one without
saying so.

## 4. Behaviour is derived by ordered, replaceable steps, and every derived value can be pinned

**Decision.** Position, expression, speech, reaction and focus are separate steps. Each
records why it produced each value. If the script supplies a value, the step leaves it.

**Instead of** one function, or a general rule engine.

**Because** the history shows hand-written values turning into derived ones round after
round, always with the right to override kept. A fixed order of named steps is enough for
that and is easy to reason about. A rule engine would be more power than the problem has
shown it needs.

**Costs.** Steps can only see what earlier steps produced. If two steps turn out to need
each other's output, the order was wrong and has to be rethought.

## 5. Channels and parameters are declared in registries

**Decision.** An observable channel (attention, posture) and a tunable parameter (hold,
settle time) are each declared once with a type, a range and a sentence of meaning. Tells,
skins, checks and the editor are driven by the declarations.

**Instead of** adding each one by hand in four places.

**Because** "we need a way to easily tune these" has been asked of every new value, and the
editor code for each was written separately. Slider changes still cannot be undone because
they took a different path from timings.

**Costs.** A registry is indirection. Reading the code to see what a channel does takes one
more hop.

## 6. A body is a skin over abstract channels

**Decision.** The model speaks only in channels. A skin decides how an entity with those
channel values is drawn. The token is the default skin.

**Instead of** a model that knows about limbs, faces or tokens.

**Because** "any entity that can think, act and feel" was a requirement, and the first body
(a paper puppet with arms and a mouth) had to be thrown away to meet it.

**Costs.** A skin cannot show what no channel carries. A richer body will need new channels
before it can use them, which is the intended pressure: the model stays the source of truth.

## 7. Time is counted in steps of a tempo grid

**Decision.** Scripts hold durations in steps. Seconds and frames appear only at the edge,
when rendering.

**Instead of** frames, which the first editor used.

**Because** "match the text to the music exactly" made rhythm part of the writing. A grid
also means a backing track at the same tempo lines up without further work.

**Costs.** A tempo change inside a scene needs a tempo map, which is not built. Timing that
is deliberately off the beat is written as a fraction of a step.

## 8. Files carry a schema number and are migrated, never silently reinterpreted

**Decision.** `show.yaml` states its schema. The engine refuses a different one. A format
change ships with a migration script.

**Instead of** best-effort reading of old files.

**Because** the format changed in most rounds, and a show is the valuable thing. An engine
update must never quietly change what an old scene means.

**Costs.** Every format change now includes writing a migration.

## 9. The engine and a show are separate

**Decision.** `toon/` is the engine. `shows/<name>/` is a show, and can move to its own
repository. Tests build their own throwaway show.

**Instead of** show files at the top of the engine's repository, as in the prototype.

**Because** the engine will be reused and versioned; a show is content with its own history.

**Costs.** Two things to version. The schema number is what ties them.

## 10. Checks stop a render; taste is a warning

**Decision.** A rule is either an error, which blocks rendering (a turn with no reason, a
payoff the audience cannot decode), or a warning (more than one new tell in a scene).

**Instead of** all advice, or all enforcement.

**Because** the working discipline, "explain every detail", only holds if breaking it has a
cost. But rules about taste will sometimes be broken on purpose.

**Costs.** Deciding which side of the line a new rule falls on is a judgment each time.

## 11. Files stay as YAML that a person can read and a person can edit

**Decision.** Scripts are hand-editable text. The editor writes back only the values that
changed and keeps comments.

**Instead of** a database or a binary project file.

**Because** the author reviews scenes by reading them, Claude writes them as text, and git
shows what changed between versions.

**Costs.** YAML has traps (`on` is read as `true`). The schemas in decision 8 are the guard.

## Open questions

These are not decided, because the conversation has not yet produced the evidence.

- **Is the gain rule universal, or a property of each entity?** Round 5 left it open.
- **What exactly carries between scenes?** Feelings and status do; sides and positions do
  not. That was a judgment made once, not a tested rule.
- **Does a background sighting count toward the audience learning a tell?** It does today.
- **Is there ever more than one stage in view?** Cross-cutting between two rooms would make
  "the scene" a weaker unit than it is now.
