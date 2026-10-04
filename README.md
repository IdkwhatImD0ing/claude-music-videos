# Music videos made with Claude

Music videos I made with Claude (Opus 5.5) in Claude Code, with everything they need to render. Every video here is
code: each frame is rendered from the song time by programs Claude wrote, then encoded with ffmpeg. There is no
editing software in the loop. I directed in conversation, and Claude agents wrote the plans, the engines, the scenes
and the review passes and ran the renders.

## Videos

| Video | Song | Look | Made with | Watch |
|---|---|---|---|---|
| [`pdoom-tabletop`](videos/pdoom-tabletop/) | "I'm Upping My P(doom)" (Claude-Pop version) | Stop-motion-style miniature on a researcher's desk at night: Clawd as a vinyl toy, a peg-doll researcher, a brass P(doom) gauge | Blender 5.2 (EEVEE) from Python scripts; 4K 60 fps | [YouTube](https://www.youtube.com/watch?v=Hu3Gupp-wKc) |
| [`paranoia`](videos/paranoia/) | HEARTSTEEL, "PARANOIA" (last minute) | League of Legends montage of my own plays: CCTV intro, pentakills synced to the drums, impacts, split-screens, kill callouts | Python/PyTorch footage engine (RIFE slow-mo, time remaps, GPU effects, synthesized SFX); 1440p 60 fps | [YouTube](https://youtu.be/4_YzMI2pPY8) |

Each folder is self-contained: its README covers the concept, layout, requirements, render commands and credits,
and its `docs/` hold the planning doc (`TREATMENT.md`), the brief the agents worked from (`ENGINE.md`) and notes on
how it was made.

## How the videos are made

The same rules run through every video:

1. **Every frame is a pure function of song time `t`.** No randomness, clocks or state carried between frames; seeded
   hashes instead. Frames can then render in parallel, out of order and resumably, and the previews match the final
   render exactly.
2. **Plan first.** A treatment (concept, look, palette, typography, one section per scene) comes before any code.
3. **Timing drives the edit.** The song is analysed first (beats, downbeats, drum hits, word-level lyric times), and
   cuts land on downbeats, hits on beats.
4. **One file per scene, written by parallel agents.** A lead agent writes the shared engine and a brief, then hands
   each agent one scene. The scene agents never edit shared code; they report engine bugs or needs to the lead.
5. **Look at the frames.** Contact sheets, frame strips and stills are rendered and read back by the agents, and each
   shot is revised until it reads well: first and last frames, motion across consecutive frames, transitions.
6. **Something happens in every shot.**
7. **Render offline, on rented GPUs when it's heavy.** Trials at 1080p; finals at full resolution and 60 fps on
   Vast.ai RTX 5090s, encoded with NVENC.

## License

The code is released under the [MIT License](LICENSE). Songs, gameplay footage, fonts and other third-party pieces
keep their own licenses; each video's README lists them.
