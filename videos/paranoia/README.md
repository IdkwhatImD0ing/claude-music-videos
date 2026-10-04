# PARANOIA: a League of Legends montage

A 62.5 s gaming montage of my own League of Legends plays, cut to the last minute of **HEARTSTEEL - "PARANOIA"
(ft. BAEKHYUN, tobi lou, ØZI and Cal Scruby)**. It opens on a CCTV feed, then runs through pentakills synced to the
drums, impact frames, split-screens and kill callouts, and ends on the game announcer's own "Pentakill!".

**Watch it on YouTube:** https://youtu.be/4_YzMI2pPY8

There is no editing software involved: every frame is rendered from code. A Python/PyTorch engine samples the
gameplay clips at any time, with RIFE in-between frames for slow motion. It remaps time so kills land on drum hits
("velocity" edits) and stacks GPU effects (punch-ins, shakes, RGB splits, shockwaves, glitches, grades, text slams).
Each output frame is a pure function of video time.

The video was made with Claude (Opus 5.5) in Claude Code. Claude agents did the clip scouting, the song analysis, the
engine, all six sections, the review passes and the renders. A lead agent owned the engine and one agent wrote each
section, all directed in conversation. Every render ran on rented RTX 5090s.

The song and the gameplay footage are not in this repository: see [Credits](#credits).

- **How every effect was made** (sync, slow-mo, impacts, transitions, sound, announcer, what went wrong):
  [`docs/HOW-IT-WAS-MADE.md`](docs/HOW-IT-WAS-MADE.md)
- Concept, look and section plan: [`docs/TREATMENT.md`](docs/TREATMENT.md)
- The section agents' brief (the engine API): [`docs/ENGINE.md`](docs/ENGINE.md)
- Research on what montage editors do: [`docs/research/montage-effects.md`](docs/research/montage-effects.md)

## Layout

- `engine/`: the footage engine.
  - `clip.py`, `remap.py`: decoding clips at any time, RIFE slow motion (`rife/`), velocity time remaps.
  - `song.py`: beats, bars, drum hits, envelopes and sung words, read from `data/audio.json`.
  - `fx.py`, `type.py`: GPU effects and text.
  - `edit.py`, `api.py`: shots, transitions and montage recipes, the API the sections use.
  - `audio.py`: the mix (song, game audio following the remap, synthesized whooshes and booms).
- `sections/`: one script per section (`s01_feed`, `s02_hunt`, `s03_fall`, `s04_drop`, `s05_star`, `s06_finale`),
  plus `s90_voice`, which places the announcer's lines.
- `analysis/`: song analysis (Demucs stems, beat_this beats and downbeats, drum onsets, whisper word times) and the
  drum pattern per 16th note.
- `tools/`: clip catalog, scouting sheets, kill strips, announcer extraction, review renders, footage ledger, and
  `cloud/` for running everything on a rented GPU.
- `data/`: the song map, the clip catalog, the scouting ratings and the final picks.
- `assets/fonts/`: the fonts (SIL Open Font License).
- `render.py`: the front end (check, stills, sheets, strips, audio, video).
- `out/`: the song, renders and caches (not in the repo).

## Footage

The clips come from my SteelSeries Moments library (about 800 League clips at 1440p, 60 fps). `tools/catalog.py`
reads the Moments database (read-only) and the kill markers SteelSeries embeds in each MP4, then ranks clips by
multikills. It also skips any clip listed in a footage ledger (`library/footage-ledger.json` in my private working
repo), so later montages use fresh plays. To catalog your own clips, run it on a PC with SteelSeries GG installed:
it finds the clips through the Moments database (`DB` in `tools/catalog.py`), and it works without a ledger.

## Pipeline

All heavy work runs on a rented Vast.ai RTX 5090. `tools/cloud/remote.py` syncs the code, runs a command there and
copies the outputs back.

1. `tools/catalog.py` (PC) → `data/catalog.json`: candidates.
2. Upload candidates to the machine (`scp`).
3. `analysis/analyze.py` (cloud): Demucs stems, beat_this beats and downbeats, kick/snare/hat onsets, envelopes,
   whisper word times → `data/audio.json`, `data/bars.txt`. `analysis/pattern.py`: the drum pattern per 16th.
4. `tools/scout.py` (cloud): contact sheets per clip; scouting agents rated every clip → `data/scouting.json`.
5. `tools/killstrip.py` (cloud): 1/30 s strips around each chosen kill to pin exact frames.
6. Sections (`sections/s01..s06`), one per agent, on the engine in `engine/`.
7. `render.py` (cloud): `check`, `sheet`, `strip`, `stills`, `audio`, `video`.
8. `tools/announcer.py` (cloud): cuts the announcer's lines ("Quadra kill!", "Pentakill!") from the clips' game audio
   (Demucs vocals + faster-whisper), keeping only lines that re-transcribe to the right words on their own.
   `sections/s90_voice.py` places them on the kill callouts.

## Requirements

- An NVIDIA GPU. `tools/cloud/setup.sh` sets up a fresh Vast.ai machine: a static ffmpeg with NVENC, a Python venv
  with CUDA PyTorch, PyAV, librosa, Demucs, beat_this and faster-whisper, and the RIFE 4.25 weights.
- The song as `out/song/paranoia.wav`, and the clips in `clips/` (or set `LM_CLIPS`).
- `VAST_API_KEY` in the environment for `tools/cloud/vast.py`, and `out/cloud/machines.json` naming the machines
  (`{"A": {"host": ..., "port": ...}}`).

## Render

All commands run from this video's folder (`videos/paranoia/`). Times are video seconds.

```sh
python tools/cloud/remote.py A run render.py check                                         # shot list, gaps, remap warnings
python tools/cloud/remote.py A run render.py sheet --from 28 --to 40 --n 16 --out out/wip/drop.jpg
python tools/cloud/remote.py A run render.py video --out out/wip/paranoia_trial.mp4        # 1080p60 trial
python tools/cloud/remote.py A run render.py video --w 2560 --out out/paranoia.mp4         # 1440p60 final
```

The final is 1440p60, the footage's native size; `--w 3840` would upscale the footage 1.5x for 4K. Pixel-sized
effects scale with frame height, so every size looks alike. For audio-only changes, run `render.py audio` and remux
the new WAV into the existing video (`-c:v copy`) instead of re-rendering the picture.

## Credits

- **Gameplay:** my own League of Legends games. *PARANOIA (montage) was created under Riot Games' "Legal Jibber
  Jabber" policy using assets owned by Riot Games. Riot Games does not endorse or sponsor this project.*
- **Song:** HEARTSTEEL - "PARANOIA" (ft. BAEKHYUN, tobi lou, ØZI and Cal Scruby), Riot Games Music. Not included.
- **Announcer voice lines:** League of Legends' announcer, cut from my own game recordings.
- **Frame interpolation:** RIFE 4.25 (Practical-RIFE weights via [HolyWu/vs-rife](https://github.com/HolyWu/vs-rife),
  MIT), in `engine/rife/` with its license.
- **Fonts** in `assets/fonts/`: Anton, Bebas Neue, Black Ops One, Share Tech Mono, Orbitron, Rubik Glitch and Cinzel
  (Google Fonts, SIL Open Font License, in `OFL.txt`).
- **Analysis:** Demucs (MIT), beat_this (MIT), faster-whisper (MIT), librosa (ISC).

## License

The code is released under the [MIT License](../../LICENSE). RIFE and the fonts keep their own licenses (see
Credits). The song, the gameplay footage and the announcer lines are not covered by it: they belong to their owners.
