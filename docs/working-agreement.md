# How an idea becomes animation

Agreed with the show's maker on 2026-11-17. Whoever (or whatever) is building follows this.

## A new idea gets a written plan first

Nothing is built from a new idea until its plan has been approved. Small fixes ("remove the lamp") go straight through.

A plan has these parts, in this order:

    IDEA      one or two sentences: what was asked, in the maker's sense
    BEATS     bar (and seconds beside it): what we see. For a look with no timing: WHAT WE SEE
    CHOICES I MADE, AND WHY      every place the idea left open, what was chosen, and the reason from the story
    WHAT I WOULD REMOVE          anything the idea makes untrue
    NOT SURE                     questions only the maker can answer; things I think it needs but was not asked for

Rules that go with it:

- **Nothing is added that was not asked for.** If the idea seems to need something more, it goes under NOT SURE and is not built.
- **Gaps are asked about, not filled.** A missing detail that changes the picture is a question before the plan.
- **An open choice is reasoned from the story,** then made and flagged, not asked about one at a time.
- **Timing is the maker's to adjust.** Get the beats in the right order on sensible bars; do not polish timing. The maker moves beats on the timeline.

## Timing is tuned in the editor

The maker adjusts timing by hand in the editor (`Open Editor.command`, or `s2s edit <scene>`): lines dragged to other bars,
sounds moved and stretched, music placed, the camera's stops over the land. The README's "The editor" lists every control.
Anything the editor cannot fix, the maker pins with a note (`M`), and the builder reads the notes (`s2s notes`), treats each as
a request, and closes it (`s2s notes --done N`) when dealt with. A note that asks for a new idea still gets a plan first.

## Two copies of the show, kept in step

The writer tunes on their own computer (`Open Editor.command`); the assistant builds in the repository.

- **Repository to the writer's computer:** the launcher runs `git pull --rebase --autostash` before it opens the editor,
  so the editor always starts from the latest work with the writer's own nudges on top.
- **The writer's computer to the repository:** the assistant does this before any other work whenever the writer says
  they have tuned something, or gives feedback after using the editor. In the linked computer's shell:

      cd ~/mnt/Projects/script-to-screen
      GIT_OPTIONAL_LOCKS=0 git -c safe.directory='*' diff HEAD -- shows

  That patch is applied in the repository with `git apply --3way`, committed as "Nudges from the editor", and pushed.
  Pins come with it (`shows/<show>/notes.yaml`); read them with `s2s notes`, and mark each with `s2s notes --done N` once dealt with.
- If both sides changed the same value, the writer's wins, and the assistant says which value it was.

## Working in the writer's open editor

When the writer has the editor open and wants to watch, the assistant makes its changes in the writer's own folder, through the
linked computer's shell, with the show's commands and always with `--because` (the writer's note or words). The editor shows each
one: a caption with the reason, the playhead on the moment, the knob on the value, a replay. The linked shell cannot load the
drawing library, so it runs the commands that read and change scripts (tune, retime, notes, check) with a stand-in for it; anything
that draws (render, frames, moments) is run in the repository. At the end of the session the changes are brought into the
repository as under "Two copies of the show".

## Motion has a vocabulary

Every kind of movement the tool can show has a name (`s2s motions`), and the show sorts the ones it uses into familiar and
reserved. A plan that involves movement says, in those names, **Uses:** the motions it draws on that exist, their tier, and
whether a reserved one has already been spent in that episode; and **Needs new:** any movement that is not in the list, which
is built once, as a kind, and named in `vocabulary/motions.py`, never as a switch for one scene. A new motion on screen is
sorted (familiar or reserved) by the maker before the scene is called done; the check warns until it is.

## The bible is in the show

The show's bible is `bible.md` and `bible.yaml` in its folder, not a separate document. Before a new idea is planned, the builder
reads `s2s bible` (it opens with where the film veers from a rule) and `s2s board`. A decision the maker makes about the show
is written into `bible.md` or `bible.yaml` in the same change that builds it, so the two cannot drift. If a rule has to be broken,
the plan says so under CHOICES, and the warning stays.
