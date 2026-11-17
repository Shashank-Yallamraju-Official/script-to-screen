# Tech debt

What makes a small change risky or slow, found by looking at what actually went wrong while making the first episode.
The test for an entry: *a small change needed edits in several places, or broke something nobody was looking at.*

## Paid off (2026-11-17)

| Debt | How it bit | What was done |
|---|---|---|
| Nothing noticed when the picture changed | Every look change was checked by eye, one still at a time; a refactor could move something and nobody would know | **Kept frames.** `shows/<show>/frames/<episode>.png` holds four small frames of every part; `s2s frames <episode>` and the test suite compare. A meant change is accepted with `--accept` |
| A new sheet flag had to be added to a second list or it was silently ignored | `climbs`, `shot`, `alight`, `plate`, `upright` each needed an edit in `stage.py` | The whole sheet reaches the drawing. A key is declared once, in `vocabulary/keys.py` |
| A typo in a file's key was silent | A bare `on:` was read as true; a misspelt place key would simply do nothing | `vocabulary/keys.py` lists every key a turn, place, light, bench, piece, land and sheet may use. `s2s check` warns about any other, and suggests the nearest |
| The bench's height was worked out in four places, the lean of a shadow in three | Changing the bench or the shadow length meant finding them all | `place.bench_top()`, `place.cast_lean()` |
| Drawing a body outside a scene meant writing out every number by hand | The land's models crashed (`KeyError: 'travel'`) when a body gained a number | `motion.REST`: a body standing still. Anything outside a scene starts from it |
| Tests and tools dug a card out of a closure (`part["draw"].__defaults__[0]`) | Fragile, and unreadable | A part carries its `card` or `stage` |
| `episode.py` held assembly, rendering and four ways of looking | 500 lines; every new reading made it longer | The readings (`moments`, `listen`, `rhythm`, `shots`, `frames`) live in `presentation/readings.py` |
| Frames were not repeatable | The map's cogs turned a different way each run | Fixed checksums; the kept frames depend on it |

## Still owed, most costly first

1. **House colours are typed in three files.** Signet's red, Mallet's orange and Hasp's blue appear in the rebuilt chamber's flags, in the land's places and in the first chamber's flag. "Colour is ownership" is a rule of the show, so a house's colour should be said once (on the house) and read everywhere.
2. **The order of effects in a frame is hard-wired.** `draw_frame` calls `seat`, `shot_in`, `light`, `swell`, the bench front and the fireball in a fixed sequence, each handing `states` to the next. A new effect means editing `draw_frame` and knowing the order. A list of effects, each declaring what it needs, would localise that.
3. **One `Land` object serves both the title sequence and the travel card, and carries state** (`span`, `where`). They work because of the order they are called in. Each card should hold its own.
4. **Three things know how long a bar is** (`anthem.BAR`, the show's tempo, `Scene.bar`), and they agree only because show.yaml says 84. Nothing checks it. The anthem should take its tempo from the show.
5. **Any change to the engine makes every part render again** (five minutes), because a part's stamp covers the whole engine. Stamping by the modules a part actually uses would bring most engine edits down to one part.
6. **Where the camera is on a given day is solved by hand.** The title sequence maps days to bars with a curve, and the camera path is in bars; lining up "the camera is over the crown when the wall closes" took trial and error. A reading that prints the day at each camera stop would remove it.
7. **Keys of scenes and of series.yaml are not yet declared** in `vocabulary/keys.py`; only turns, places, land and sheets are.
8. **`s2s listen` always reports the credits' start** as a jump at a join. It is the anthem beginning, as meant; the check needs to know that.
9. **Much of the engine is unused by an object show** (feelings, tells, the automatic camera, scored music). It is not in the way of a change, only of reading. Left alone because the other shows use it.
10. **Only real errors are linted;** there are no type checks.
11. **The Series Bible is behind the show.** It does not yet have the look (the three rules of the room), the arrow, or the land's history. Not code, but the same kind of debt.
