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

**Decision.** `script_to_screen/` is the engine. `shows/<name>/` is a show, and can move to its own
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

## 12. Every change is a command, and the tool is built to be operated by an assistant

**Decision.** There is one set of typed, validated, undoable commands. The command line is
generated from it, as the MCP server will be (decision 18), and the editor uses it too.
Every command can be rehearsed with a dry run, can answer in JSON, and never asks a
question. Each applied change records who asked and in what words.

**Instead of** an assistant editing the show's files as text, which is how the whole
prototype was written.

**Because** the stated way of working is that a writer iterates with an assistant and the
assistant uses the tool, through MCP or a good command line. Text edits
fail silently (a key YAML read as `true` did nothing), and an author who never opens a file
cannot catch that. A command either applies or says exactly why not.

**Costs.** Every capability must be given a command before anyone can use it, including the
assistant. That is slower than editing a file, and it is the point.

## 13. No AI inside the tool

**Decision.** The tool is deterministic, has no model and calls no AI service. Writers bring
their own assistant, which reaches the tool through the command line or MCP.

**Instead of** a chat box in the editor wired to one model.

**Because** the engine has to be testable, reproducible and usable by other writers with
whatever assistant they have. A built-in model would tie rendering a show to a service.

**Costs.** There is no single app to open and type into; a writer needs an assistant as well
as the tool.

## 14. An episode is an ordered list of segments, and things have identities

**Decision.** A manifest lists an episode's segments in order. A scene is one kind; a title
card is another. Seasons, episodes and segments each have an ID, a title, a logline and a
status. References (an arc starting at a scene) use IDs, not paths.

**Instead of** a folder of scene files read in filename order, where the path is the name.

**Because** title screens showed that an episode holds things that are not scenes, and
tracking and comparing need every unit to be describable and to survive being renamed.

**Costs.** One more file per episode, and IDs that must stay unique. Reordering becomes an
edit to the manifest and not a rename.

## 15. The engine names what happened before deciding how it sounds or looks

**Decision.** A derivation step writes a track of dramatic events, each with a kind, a
subject, a valence, an expectedness and a weight. Music scoring reads that track. So can a
camera and the series index.

**Instead of** placing every music cue by hand, or wiring music directly to feelings.

**Because** the ask was for music that tells surprising-and-bad from surprising-and-good,
which is a statement about the story. Placing cues by hand would drift the way hand-written
poses did. One description of what happened, shared by every consumer, keeps music, camera
and overview telling the same story.

**Costs.** Emotions must declare a valence, and "expected by whom" must be answered; the
audience ledger is the first answer. A wrong reading of an event is now wrong in three
places at once, which is also what makes it noticeable.

## 16. The editor is a tuning instrument, not an authoring tool

**Decision.** By hand, the writer nudges values and replays: timings, pitch, stress, motion,
sound. The editor never changes words, feelings, structure or characters' rules. It shows
them, read-only, because knowing why something happens helps judge how it feels.

**Instead of** growing the editor until a scene can be written in it.

**Because** the writer's stated use is "only to tweak params and replay scenes to check if
the tweaks match my feeling". Tuning is perceptual and fast; anything that makes the editor
heavier slows the one loop the writer runs by hand. Authoring already has a better operator.

**Costs.** Fixing a typo needs the assistant. A pin on the moment is the bridge.

## 17. Every value remembers who set it, and hand-tuned values are protected

**Decision.** A value is derived by the engine, set by the assistant, or tuned by hand, and
records which. Hand-tuned outranks the others. A command that would discard hand-tuned
values reports that when rehearsed. A unit can be locked, after which commands refuse to
change it. The editor follows the files on disk and merges value by value.

**Instead of** treating all values in a file alike, and letting the editor save its own copy
over the file, which is what the prototype does.

**Because** the two loops alternate on the same scene. Tuning is slow, careful work that
leaves no trace except numbers; without this, one rewrite by the assistant erases it
silently. It also lets the assistant list what the writer keeps changing by hand and
propose a rule, which is how every derived value in this project began.

**Costs.** More bookkeeping per value, and a merge to get right.

## 18. The command line first; MCP is the end state

**Decision.** The assistant's way in is a command line built for it. An MCP server comes
much later and is generated from the same commands.

**Instead of** building the MCP server first.

**Because** a good command line is enough for an assistant working in a terminal, is usable
by scripts and people too, and proves the commands before a second interface is built on
them.

**Costs.** An assistant without a terminal cannot operate the tool until the server exists.

## 19. Where a value is stored says who set it

**Decision.** Hand-set values live in `tune:` blocks at the scope they apply to, written
only by the tune commands. A value resolves from the narrowest scope outward, hand-set
before written. Syllable-level tunes carry the words they were tuned against and are set
aside, not applied, when the words change. See [lld-nudging.md](lld-nudging.md).

**Instead of** a marker on every value recording its author.

**Because** it makes decision 17 visible in the file and in a git diff, and deleting a block
always restores what the engine or the assistant chose.

**Costs.** A value can now be in two places in one file, and a reader must know that
`tune:` wins.

## 20. The tuning loop keeps one renderer and no cleverness it has not earned

**Decision.** Replay draws frames with the final renderer as it plays, and remixes the whole
scene's sound on each nudge. The audience ledger and earlier scenes are never recomputed by
a nudge. A frame cache is designed and deferred until a measured nudge exceeds 100 ms.

**Instead of** a second renderer in the browser, per-turn audio stems, or a cache built up
front.

**Because** measured on the prototype the renderer is eight times faster than playback and
a full mix takes 12 ms; 70 of a nudge's 78 ms was work a nudge cannot affect.

**Costs.** The numbers hold for tokens and short scenes. Richer skins or long scenes will
reopen this, which is why the cache is designed now.

## 21. One series.yaml, not a manifest per episode

**Decision.** Decision 14 stands, in one file: `series.yaml` at the top of a show lists
seasons, episodes and segments in order, with each segment's id, file and status. A scene
file does not know its own id or place.

**Instead of** a manifest in every episode folder, or an id written inside each scene file.

**Because** the manifest is also the view from above, and one file can be read, reordered
and diffed at a glance. Keeping the id out of the scene file means a scene can be moved
between episodes, or reused, without being edited.

**Costs.** Two people adding episodes at once will touch the same file. A scene file on its
own no longer says where it belongs.

## Open questions

These are not decided, because the conversation has not yet produced the evidence.

- **Is the gain rule universal, or a property of each entity?** Round 5 left it open.
- **What exactly carries between scenes?** Feelings and status do; sides and positions do
  not. That was a judgment made once, not a tested rule.
- **Does a background sighting count toward the audience learning a tell?** It does today.
- **Is there ever more than one stage in view?** Cross-cutting between two rooms would make
  "the scene" a weaker unit than it is now.
- **Expected by whom?** A stinger for a surprise can follow what the audience expected or
  what a character expected. They differ exactly when the audience knows more than the
  character, which is the root of dramatic irony.
- **Is music heard by the characters?** A title card's theme is not. A character singing is.
  The `sing:` line already sits on this boundary.
- **Should the tool itself hold changes for approval?** As designed it does not: rehearsing
  and undoing are the tool's job, and asking the writer first is the assistant's.
