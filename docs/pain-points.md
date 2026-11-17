# Pain points

A running ledger of what gets in the way when making the show with this tool, kept by whoever is doing the making.
Add to it at the moment something hurts, not afterwards. One line each: what happened, what it cost, and where it stands.

Status: **open** (still hurts), **eased** (a workaround exists), **fixed** (gone, and how).

| # | Noted | Pain | What it costs | Status |
|---|---|---|---|---|
| 1 | 2026-11-16 | A full episode render took 10 to 25 minutes once bodies had outlines and rooms had cast shadows | Three renders were thrown away in one day because the next request arrived first | **fixed**: rooms are painted once and kept, shadow layers cover only the floor, parts render in parallel and unchanged parts are kept. Full episode 3m49s; a repeat with nothing changed 6s; `--draft` 51s |
| 2 | 2026-11-16 | No way to look at chosen moments of an episode without a throwaway script | Every check meant writing Python against the engine's insides | **fixed**: `s2s moments <episode> 36 42.5 --part <id> --every 1` |
| 3 | 2026-11-16 | Sound cannot be heard by the maker | The anthem, blast, swell and travel music were all written blind | **eased**: `s2s listen` draws loudness over time and reports sound that stops dead, long silences and jumps at joins. It cannot judge whether something sounds good |
| 4 | 2026-11-16 | Stills are checked, motion is not | Pacing and camera problems (the zoom before the blast) reach the viewer first | **eased**: `s2s shots` lists every shot and why; `s2s moments --every 0.1` makes a strip. Feel over time is still unjudged |
| 5 | 2026-11-16 | YAML reads a bare `on:` as true | The hand-set camera was ignored, then the blast lost its owner and the fireball never drew | **fixed**: the loader puts `on` and `off` keys back as words, everywhere |
| 6 | 2026-11-16 | A new visual idea means engine code (vines, arches, the swell, the sky) | Each idea is a programming job, not a line of script | open |
| 7 | 2026-11-16 | Much of the engine (feelings, tells, automatic camera, scored music) is switched off by this show's style | Dead weight to read past; settings to zero by hand | open |
| 8 | 2026-11-16 | The title sequence never visits Plumb, Brim, Whirl or Glass, so they stay dark on every map | The map the viewer sees is missing four houses | kept on purpose: a house the story has not shown is not shown on the map. A writer's choice, not a fault |
| 9 | 2026-11-16 | Close from above, a house's object stood upright on the map | The arrival read as a card being raised | **fixed**: what stands up is seen end on from straight above |
| 10 | 2026-11-16 | Bodies got only a silhouette outline; the room's pieces got inner lines too | Objects looked thinner-lined than the room | **fixed**: bodies are inked shape by shape (`bodies.Inked`) |
| 11 | 2026-11-16 | CI results on GitHub had not been looked at since the first push | A broken build could go unnoticed | **fixed**: looked, green; CI now also lints and checks the crown show |
| 12 | 2026-11-16 | `s2s moments` failed to draw and left the old sheet in place | A stale picture read as the new one | **fixed**: the old sheet is removed before drawing |
| 13 | 2026-11-16 | `--only` wrote its stretch over the whole film | The real film was replaced by ten seconds of it | **fixed**: a stretch goes to `<episode>.stretch.mp4` |
| 14 | 2026-11-16 | The map's cogs turned a different way on each run (Python's per-run string hashing) | Frames were not repeatable; parts rendered in separate processes could disagree | **fixed**: a fixed checksum decides |
| 15 | 2026-11-16 | Scenes have no sound at all between spoken lines: complete digital silence, found by `s2s listen` | Each scene may feel dead between lines against the music before and after | **fixed**: a place can have `air: warm | cold`, a quiet bed under the scene |
| 16 | 2026-11-16 | Nothing said whether an episode had a rhythm: scenes and music ran on different tempos and nothing landed on a beat | The second council was 40 bars with no rise or fall and nobody could see it | **fixed**: one tempo; `bar:` on a turn and `bars:` on a scene place beats on the grid (and `s2s check` refuses a beat that cannot land); `s2s rhythm` draws the episode as a song |
| 17 | 2026-11-17 | Small timings could only be changed by asking: moving a sound a few steps, shortening a swell, sliding a line to another bar | Each was a request and a render | **fixed**: in the editor, placed sounds are blocks (start, length, level, fades), a line with a `bar:` drags to another bar, cards open like scenes, and the camera's stops over the land are moved by dragging the picture |
| 18 | 2026-11-17 | The maker cannot hear, so a level set on one scene by feel went unchecked against the rest | The second council sits about 7 dB under every other part and nobody knew | **eased**: the editor's meter gives each part's level and marks one that is off; the waveform lane shows it. Whether it should be quieter is the writer's call, and is still open |
| 19 | 2026-11-17 | The writer could not see what the assistant changed, only that something had | A change had to be described in words and then hunted for | **fixed**: a change made while the editor is open is captioned with its reason, and the editor goes to it and replays it |
| 20 | 2026-11-17 | The writer tunes on their own computer and the assistant builds in the repository: two copies | Nudges and notes have to be carried across, by a routine the assistant must remember | **eased**: the launcher fetches the latest; the working agreement says how nudges come back. Not automatic |
| 21 | 2026-11-17 | The assistant's shell on the writer's computer cannot load the drawing library | There it can tune, retime, check and read notes, but not render or draw a still | **eased**: a stand-in lets the script commands run; anything that draws runs in the repository |
| 22 | 2026-11-17 | The editor had never been run on the writer's computer while a dozen features were built on it | Any launch problem would have been found late | **fixed** when it was opened; since then a feature is tried there before the next is built on it |
