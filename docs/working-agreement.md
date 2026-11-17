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

## The timeline

The Beat Timeline page (https://claude.ai/artifact/Y92QSWrNDr8n28y4Pp6V62) shows each scene's beats on the bar grid. The maker
drags them and saves; the builder applies what was saved.

- Beats snap to an eighth of a bar (the show's smallest step).
- Dragging moves one beat. Holding Shift moves everything after it too.
- A beat that could not play where it is (the one before has not finished, or it runs past the scene's end) turns red, and
  nothing can be saved until it is fixed.

To apply saved timings (the page's store: `episodes/<episode>` is what the show has, `edits/<episode>` is what was saved):

    1. read  edits/<episode>            -> {moves: {<scene>: {<turn>: <bar>}}}
    2. s2s retime <scene> <turn>=<bar> ...      once per scene; all of a scene's moves together
    3. s2s render --episode <episode>
    4. s2s beats <episode> --json       -> write its parts to  episodes/<episode>
    5. set   edits/<episode>            to {moves: {}}

The map sequence (camera stops and the days) is not on the timeline yet.
