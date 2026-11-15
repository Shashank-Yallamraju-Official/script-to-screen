# Build phases

The restructure and the nudging loop are built in phases. **Every phase ends the same way:**
the reference scene (`shows/demo/episodes/study/the-reveal.yaml`, the staging study of a
scene from The Good Place) is rendered and compared with `s2s parity check`. Unless a
phase says it means to change the scene, its score, picture and sound must be identical to
the phase before. A phase that does mean to change it re-records the reference and says why.

| # | Phase | Reference scene must be | Status |
|---|---|---|---|
| 0 | **Parity gate.** `s2s parity record|check`; references for every demo scene | Recorded | Done (`phase-0`) |
| 1 | **Four layers.** `script`, `world`, `performance`, `presentation` as packages that only import downward, enforced by a test. The world changes only through its methods and logs every change with its cause | Identical | Done (`phase-1`), byte-identical video |
| 2 | **Commands and the command line.** Read, change, rehearse, check, explain, still; JSON out; addresses | Identical | |
| 3 | **Identities and manifests.** Seasons, episodes and segments with IDs; an episode is an ordered list; schema 2 with a migration | Identical | |
| 4 | **The score as the contract.** Presentation, sound, ledger and editor read named tracks and nothing else | Identical | |
| 5 | **Registries.** Channels and parameters declared once | Identical | |
| N1 | Nudging: fast and safe (see [lld-nudging.md](lld-nudging.md) section 10) | Identical | |
| N2 | Nudging: cascade and `tune:` blocks | Identical | |
| N3 | Nudging: time ownership, breath as its own value, the knob | Identical | |
| N4 | Nudging: audition and before/after | Identical | |
| N5 | Nudging: in play, widen, anchors | Identical | |
| N6 | Nudging: picking in the picture, search | Identical | |

Left until asked for, with room kept: title cards and skins, dramatic events and music
scoring, cached event replay across a long series, the MCP server.

## Known seams left by phase 1

Phase 1 moved code without changing behaviour, so three things are in the right package but
still reach across a line. Each is removed by the phase named.

| Seam | Removed in |
|---|---|
| The performance layer reads `feel.aside_volume` to set an event's loudness | 4 |
| `render` asks the ledger whether a show has errors before rendering | 2 (becomes the `check` command) |
| The editor keeps its own copy of a scene and overwrites the file on save | N1 |
