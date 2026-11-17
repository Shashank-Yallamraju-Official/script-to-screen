# Pain points

A running ledger of what gets in the way when making the show with this tool, kept by whoever is doing the making.
Add to it at the moment something hurts, not afterwards. One line each: what happened, what it cost, and where it stands.

Status: **open** (still hurts), **eased** (a workaround exists), **fixed** (gone, and how).

| # | Noted | Pain | What it costs | Status |
|---|---|---|---|---|
| 1 | 2026-11-16 | A full episode render takes over ten minutes since bodies got drawn outlines | Three renders were thrown away in one day because the next request arrived first | **eased**: `s2s render --episode <id> --draft` (half size, half the frames, no outlines), and `--only 30-48` for one stretch |
| 2 | 2026-11-16 | No way to look at chosen moments of an episode without a throwaway script | Every check meant writing Python against the engine's insides | **fixed**: `s2s moments <episode> 36 42.5 --part <id> --every 1` |
| 3 | 2026-11-16 | Sound cannot be heard by the maker | The anthem, blast, swell and travel music were all written blind; only loudness is checked | open |
| 4 | 2026-11-16 | Stills are checked, motion is not | Pacing and camera problems (the zoom before the blast) reach the viewer first | open |
| 5 | 2026-11-16 | YAML reads a bare `on:` as true | The hand-set camera was ignored, then the blast lost its owner and the fireball never drew, for several versions | eased: both places now accept it; `s2s check` does not yet warn about it |
| 6 | 2026-11-16 | A new visual idea means engine code (vines, arches, the swell, the sky) | Each idea is a programming job, not a line of script | open |
| 7 | 2026-11-16 | Much of the engine (feelings, tells, automatic camera, scored music) is switched off by this show's style | Dead weight to read past; settings to zero by hand | open |
| 8 | 2026-11-16 | The title sequence never visits Plumb, Brim, Whirl or Glass, so they stay dark on every map | The map the viewer sees is missing four houses | open |
| 9 | 2026-11-16 | Close from above, a house's object stands upright on the map instead of being seen from the top | The arrival reads as a card being raised, not a camera coming down | open |
| 10 | 2026-11-16 | Bodies get only a silhouette outline; the room's pieces get inner lines too | Objects look thinner-lined than the room around them | open |
| 11 | 2026-11-16 | CI results on GitHub have not been looked at since the first push | A broken build could go unnoticed | open |
