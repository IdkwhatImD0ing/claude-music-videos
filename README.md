# I'm Upping My P(doom): Tabletop

A music video made entirely in Blender, from code. It is a stop-motion-style miniature on a researcher's desk at
night: Clawd as a vinyl toy, a wooden peg-doll researcher, a brass P(doom) gauge that jumps at each "DOOM", and a
single paperclip by the laptop that ends up as the whole planet. Every model, rig, animation, simulation and frame
comes from the Python scripts in this repository, rendered with Blender 5.2's EEVEE.

The video was made with Claude (Opus 5.5) in Claude Code: the treatment, the pipeline, the puppets, all 18 scenes,
the QA passes and the renders were done by Claude agents (a lead agent owning the shared libraries, one agent per
scene), directed in conversation. The final 4K 60 fps render ran on rented RTX 5090s.

The song is not ours: see [Credits](#credits).

The concept, look, cast and scene-by-scene plan are in [`docs/TREATMENT.md`](docs/TREATMENT.md). The pipeline, its
rules and the Blender 5.2 traps found along the way are in [`docs/ENGINE.md`](docs/ENGINE.md), and each library has
its own guide in [`docs/lib/`](docs/lib/).

## Layout

- `audio/song.mp3`: the song (the Claude-Pop version, see Credits).
- `data/lyrics.json`, `data/audio.json`: word-level lyric timings and the beat, downbeat and section analysis, from
  [mexicat/pdoom-video](https://github.com/mexicat/pdoom-video).
- `blender/run.py`: runs inside Blender; builds a scene from its script, saves it, renders frames.
- `blender/lib/pdoom/`: the shared libraries.
  - `kit.py`, `timing.py`, `timeline.py`: scene setup, keying by song time, the edit (18 scene windows on the
    downbeats).
  - `chars/`: the puppets (Clawd, Sydney, the researcher) and their engine, `rig.py`: tracks keyed by song time,
    baked on a stop-motion grid at 24 fps or smooth on every frame at 60 fps.
  - `sets/`: the desk, lamp, laptop, gauge, window and props.
  - `fx/`: rigid-body paperclip avalanches, fracture, Mantaflow smoke and liquid, dominoes, particles.
  - `lyrics/`: typography as physical objects in the miniature (used by an earlier revision; off by default).
- `blender/scenes/`: one script per scene (`boot`, `training`, `eat`, `room`, `singularity`, `sydney`, `moon`,
  `safe`, `backprop`, `leftturn`, `paperclips`, `fuse`, `disobey`, `gpus`, `loom`, `ilya`, `finale`, `coda`) plus
  their helpers; `_test_*.py` are library test scenes.
- `tools/render.py`: the front end (build, stills, sheets, strips, frame ranges, final assembly).
- `tools/subtitles.py`: the karaoke subtitles (ASS, burned in at assembly).
- `tools/fetch_assets.py`: downloads the CC0 textures and HDRIs into `assets/` (not in the repo).
- `tools/cloud/`: scripts for rendering on rented GPUs (see [Rendering on rented GPUs](#rendering-on-rented-gpus)).
- `out/`: builds, frames and renders (not in the repo).

## Requirements

- Blender 5.2.2. On Windows the tools look in the default install folder; elsewhere set `BLENDER` to the binary.
- Python 3 with Pillow (for contact sheets).
- ffmpeg. The final assembly encodes with NVIDIA's `h264_nvenc`; without an NVIDIA GPU, change the encoder in
  `assemble()` in `tools/render.py` (for example to `libx264 -crf 16`).
- A few scenes use Windows system fonts (Bahnschrift for the gauge dials, Arial Black for the title, KaiTi, FangSong
  and SimHei for the Chinese room). On other systems, put those `.ttf` files in a folder and set `PDOOM_FONT_DIR`.

Then fetch the textures and HDRIs (about 110 MB):

```sh
python tools/fetch_assets.py
```

## Render

All commands run from the repository root. Times are song seconds.

```sh
python tools/render.py build boot                                  # build + save out/blend/boot.blend
python tools/render.py sheet boot --from 0 --to 5.7 --n 12 --reuse # contact sheet -> out/wip/boot/sheet.png
python tools/render.py stills boot --t 3.5,4.2 --reuse             # full-size stills
python tools/render.py range boot --workers 4 --reuse              # every frame of the scene -> out/frames/boot/
python tools/render.py assemble                                    # all scenes + song + subtitles -> out/pdoom-blender.mp4
bash tools/render_all.sh                                           # every scene in edit order, resumable
```

That is the 1080p, 24 fps version, where the puppets move on twos like a stop-motion film.

### 4K at 60 fps

```sh
python tools/render.py build <scene> --fps 60
python tools/render.py range <scene> --scale 200 --fps 60 --workers 4 --reuse    # -> out/frames_2160p60/<scene>/
python tools/render.py assemble --scale 200 --fps 60
```

- `--fps 60` at build time sets `PDOOM_FPS=60`: every puppet and per-frame prop is sampled on the 60 fps grid with
  smooth keys, so nothing steps between output frames. Teleports at cuts still jump, between two exposures.
- At render time, output frame k shows song time k/60. Every on/off switch moves to just before its cut frame, so no
  frame shows the next shot's staging, and the motion-blur shutter scales from 0.5 to 0.18 of a 24 fps frame.
- `--scale 200` renders a true 3840×2160 frame; each light's shadow resolution is halved to keep shadow memory and
  detail the same as at 1080p.
- Cost: on an RTX 5090, about 35 to 40 4K frames a minute with 4 Blender workers. The 9,400 frames took about an hour
  on 11 rented GPUs. More workers per GPU help because each frame spends about 3 s of single-threaded CPU time
  evaluating rigs and caches before the GPU renders it.

Other switches: `PDOOM_LYRICS=1` rebuilds an earlier revision that stages every sung word as an object in the scene,
and `assemble --nosubs` leaves the subtitles out.

## Rendering on rented GPUs

[`tools/cloud/`](tools/cloud/) holds the scripts used with Vast.ai RTX 5090 instances: machine setup, parallel builds
with retries, 4K60 renders, lossless packing of each finished scene, a collector that gathers every scene on one
machine and assembles the video there, and `remote.sh`, which runs a build or a check render on a rented machine
from your own checkout. Its [README](tools/cloud/README.md) has the steps and the problems hit along the way.

## Credits

- **Song:** "I'm Upping My P(doom)". The lyrics are by
  [osmarks](https://docs.osmarks.net/hypha/p%28doom%29_song_objectively_correct_interpretation), built on an opening
  verse and chorus by [MusicPerson](https://www.udio.com/creators/MusicPerson), with lines suggested on the EleutherAI
  Discord and help from Claude on the outro and final chorus. The original was generated with Udio and released in
  November 2024 ([YouTube](https://www.youtube.com/watch?v=uEB5E67vcPA)). This video uses the "Claude-Pop" version
  made with Suno, posted by [deckard (@slimer48484)](https://x.com/slimer48484/status/2097752569212756134) in
  September 2026.
- **Timing data:** `data/lyrics.json` and `data/audio.json` come from Giacomo Magnanini's
  [code-rendered video of the same song](https://github.com/mexicat/pdoom-video) (MIT), which also inspired this
  repository's layout.
- **Clawd:** the Claude Code mascot, modelled after the model sheets in John Heibel's
  [ClaudeAnimationBase](https://github.com/JohnHeibel/ClaudeAnimationBase) (MIT).
- **Textures and HDRIs:** [Poly Haven](https://polyhaven.com) and [ambientCG](https://ambientcg.com), CC0, downloaded
  by `tools/fetch_assets.py` (the list is in that script).
- **Fonts** in `blender/lib/pdoom/lyrics/fonts/`: Alfa Slab One, Archivo, Courier Prime, IBM Plex Mono and Stardos
  Stencil (SIL Open Font License), Permanent Marker (Apache 2.0) and the Hershey fonts; their licenses are in the same
  folder.

## License

The code is released under the [MIT License](LICENSE). The fonts keep their own licenses (see Credits), and the song
and lyrics (`audio/`, `data/lyrics.json`) are not covered by it: they belong to their authors.
