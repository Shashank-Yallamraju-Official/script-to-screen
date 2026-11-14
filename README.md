# paper-toon

A paper cut-out animation pipeline where scenes are data. You describe a scene and give notes;
the notes become edits to a scene script; the renderer turns the script into video.

## How it fits together

| Folder | Holds | Changes |
|---|---|---|
| `cast/` | One file per character: colours, hair, voice pitch | Once per character |
| `sets/` | One file per location: paper layers at different depths | Once per location |
| `library/poses.yaml` | Named poses and facial expressions | When the show needs a new one |
| `library/tones.yaml` | Named line deliveries: note colour and motion, typing speed, blip pitch | When the show needs a new one |
| `episodes/` | Scene scripts: shots, camera, beats, dialogue | Every note |
| `toon/` | The renderer | Rarely |
| `out/` | Rendered video (not committed) | Every render |

## Render

    pip install skia-python pyyaml numpy      # plus ffmpeg on the PATH
    python -m toon.render episodes/pilot/scene01.yaml              # whole scene
    python -m toon.render episodes/pilot/scene01.yaml --shots 2    # one shot, then rejoin
    python -m toon.render episodes/pilot/scene01.yaml --still 2:40 # shot 2, frame 40, as a PNG
    python -m toon.render episodes/pilot/scene01.yaml --clean      # without the note-giving slate

The slate in the top-left corner reads `S<shot> · <frame>`. Those are the same numbers the
scene script uses, so a note like "S2 · 060, he should look away sooner" points at one line.

## Scene script

- `cast`: who is in the scene, where they stand (`at`, in pixels from the left of the set) and which way they face.
- `shots`: each has an `id`, a `length` in frames, a `camera`, and `beats`.
- `camera`: `{framing: wide}`, or `medium` / `close` / `two` with a `subject`. A list of keys with `frame` values is a camera move.
- `beats`: at `frame`, change a character's `pose`, `expression` or `facing`, or `say` a line with a `tone`.

Poses and expressions persist across cuts until a later beat changes them.
