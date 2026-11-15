# Build phases

The restructure and the nudging loop are built in phases. **Every phase ends the same way:**
the reference scene, "The morally righteous location"
(`shows/demo/episodes/study/the-morally-righteous-location.yaml`), is rendered and compared with `s2s parity check`. Unless a
phase says it means to change the scene, its score, picture and sound must be identical to
the phase before. A phase that does mean to change it re-records the reference and says why.

| # | Phase | Reference scene must be | Status |
|---|---|---|---|
| 0 | **Parity gate.** `s2s parity record|check`; references for every demo scene | Recorded | Done (`phase-0`) |
| 1 | **Four layers.** `script`, `world`, `performance`, `presentation` as packages that only import downward, enforced by a test. The world changes only through its methods and logs every change with its cause | Identical | Done (`phase-1`), byte-identical video |
| 2 | **Commands and the command line.** 22 commands declared once: read, state, explain, check, still, contact sheet, render, eight changes to a scene, history and undo. JSON out, dry run, addresses, a journal with the writer's words. Changes to entity sheets, the library and show settings are not yet commands | Identical | Done (`phase-2`), byte-identical video |
| 3 | **Identities and the series manifest.** `series.yaml` lists seasons, episodes and segments in order; a scene's id is its identity, wherever its file is. Arcs, addresses, references and output files use ids. Status per scene, with locking. `move`, `add-scene`, `set-status`, and `migrate` (schema 1 to 2) | Identical | Done (`phase-3`), byte-identical video |
| 4 | **The score as the contract.** A scene's performance ends in a `Score` of named tracks (turns, pose, speech, events, focus, cast). Drawing, motion, sound, the ledger, parity and the editor are given a score and a look, and nothing else. A test renders a score that has been through JSON and gets the same picture and sound. `s2s score` exports it | Picture and sound identical. The score's fingerprint was re-recorded on purpose: its tracks were renamed and an event now says it is in passing instead of carrying a volume | Done (`phase-4`), byte-identical video |
| 5 | **Registries.** `vocabulary/` declares every tunable parameter (31: meaning, unit, range, step, where it is written, what changing it redoes, which events show it at work, the words a writer might use) and every observable channel (8: what a tell or a deliberate action may set). The editor's sliders, the checks on entity sheets and actions, and `s2s params` / `s2s channels` are driven by them | Identical | Done (`phase-5`), byte-identical video |
| N1 | Nudging: fast and safe (see [lld-nudging.md](lld-nudging.md) section 10) | Identical | |
| N2 | Nudging: cascade and `tune:` blocks | Identical | |
| N3 | Nudging: time ownership, breath as its own value, the knob | Identical | |
| N4 | Nudging: audition and before/after | Identical | |
| N5 | Nudging: in play, widen, anchors | Identical | |
| N6 | Nudging: picking in the picture, search | Identical | |

Left until asked for, with room kept: title cards and skins, dramatic events and music
scoring, cached event replay across a long series, the MCP server.

## Known seams left by phase 1

Phase 1 moved code without changing behaviour, so one thing is in the right package
but still reaches across a line.

| Seam | Removed in |
|---|---|
| The editor keeps its own copy of a scene and overwrites the file on save | N1 |
