# How the PARANOIA montage was made

This is the technique write-up: how each effect in the video works and where its code lives. The plan behind it is
in [`TREATMENT.md`](TREATMENT.md); the engine API is in [`ENGINE.md`](ENGINE.md); the research that came first is
in [`research/montage-effects.md`](research/montage-effects.md).

Everything below is code. Each output frame is a pure function of video time `t`: the engine looks up which shot is
on screen, which moment of the gameplay clip to show, and how strong every effect is at that instant. Nothing is
keyframed by hand in an editor.

## 1. The pipeline in one minute

1. **Find the plays.** SteelSeries Moments stores the game's kill markers inside every clip. A script ranks 807
   League clips by multikills; 14 scouting agents rated the best 78 from contact sheets.
2. **Pin the kills.** Close-up strips (one frame every 1/30 s) show the exact frame each enemy dies.
3. **Map the song.** Beats, bars, drum hits and sung words, measured from the audio.
4. **Sync.** Each clip is time-remapped so its kills land exactly on drum hits ("velocity" editing).
5. **Stack effects.** GPU effects keyed to the same hits: punch-ins, shakes, flashes, RGB splits, shockwaves,
   glitches, grades, text.
6. **Sound.** The song, plus the clips' game audio following the remap, plus synthesized whooshes and booms, plus
   the game announcer's own "Pentakill!".
7. **Render** on a rented RTX 5090, 60 fps, motion blur from sub-frames.

Six agents wrote the six sections in parallel from one brief, then fixed their sections from rendered review sheets.

## 2. Footage: finding and pinning the plays

- **Kill markers.** Moments writes each clip's game events (kills, assists, deaths, dragon/baron) into the MP4's
  `STEELSERIES_META*` tags and its SQLite database. They're rounded to whole seconds (every kill in a clip shares the
  same fraction), so they only say roughly where to look. `tools/catalog.py` reads them read-only, groups kills less
  than 10 s apart into multikill chains (League's rule), and drops clips that recorded the same fight twice.
- **Scouting.** `tools/scout.py` renders two sheets per clip: an overview (16 frames around the chain) and one row per
  kill (6 frames from -1 s to +0.25 s). Agents rated hype, readability and spectacle, and wrote down where each kill
  happens on screen. Their best trick: the **KDA counter** in the top-right scoreboard ticks up on the exact kill
  frame, which beat the queued, late kill banners.
- **Exact frames.** `tools/killstrip.py` crops a 1280×720 window around each kill and shows every second frame. The
  section agents picked the frame where the big damage numbers pop or the gold "+300" appears, and pinned sync points
  to whole source frames (so the hit frame is a real frame, not a blended one).
- **No reuse.** Every clip and clip range the video uses is listed in `library/footage-ledger.json`; the catalog skips
  clips other videos already used.

## 3. The song map

`analysis/analyze.py` splits the song into stems (Demucs), tracks beats and downbeats (beat_this), finds kick, snare
and hat hits in the drum stem, measures loudness envelopes, and transcribes the words with timestamps
(faster-whisper). `analysis/pattern.py` averages the drum hits per 16th note across bars.

What that found, and how the video uses it:

- **85.71 BPM**: a beat is 0.703 s, a bar 2.81 s. The 60 s window is the song's last minute: a quiet bridge, a build,
  a drum-less break, then the final chorus to the song's real ending.
- **The chorus groove is 3-3-3-3-4**: kicks on 16ths 0, 3, 6, 9 and 12 of every bar, claps on beats 2 and 4. Most
  kills land on those five kicks; the biggest land on bar downbeats.
- **Words** drive text: "ROCK STAR" slams appear on the sung syllables, "FALL HARD" on "fall hard".
- Two fixes were needed: the beat tracker stumbled in the quiet bridge (so that stretch uses evenly spaced beats),
  and the drum-pattern script drifted 0.35 s because its analysis frame rate didn't divide the sample rate (the
  hit list itself was fine; a mismatched rate is now an error).

## 4. Sync: how kills land on the beat

This is the core of the video ("velocity" editing), in `engine/remap.py`.

- A shot's **remap** is a list of keys: at video time `t`, show clip time `s`, moving at speed `v`. Put a kill's clip
  time on a drum hit's video time and it lands there, guaranteed.
- **Between two keys the speed eases**: it accelerates from the first key's speed, cruises, then brakes into the next.
  The cruise speed is solved so the clip arrives exactly on time:
  `cruise = (mean speed − (v0·a + v1·b) / 2) / (1 − (a + b) / 2)`, where `a` and `b` are the fractions of the gap
  spent accelerating and braking. Give the kill keys a low speed (0.2-0.35x) and the stretch between kills runs
  fast (2-4x): the footage rushes, then slows into every hit. That's the "velocity" look.
- **Slow motion** below the footage's 60 fps uses **RIFE** (a neural frame interpolator) to invent in-between frames
  (`engine/clip.py`). In-betweens are cached at 1/64-frame steps, so a frame never depends on render order. RIFE is
  skipped across the recording's own camera snaps (a big jump between two frames), where it would morph.
- **Freeze-frames** are keys with speed 0; **rewinds** are negative speeds (the drop's VHS rewind); a **hit-stop**
  holds the kill frame for 0.13 s (the finale).
- **Time-split tricks** read different clip times per frame: **echo trails** blend the current frame with a few
  earlier ones (Samira's flaming roll, Viego's afterglow); **RGB time split** takes red, green and blue from slightly
  different moments, so movement fringes into colour (Kha'Zix's decloak, Vayne's crit).

## 5. Motion blur

Every output frame averages several sub-frames inside a half-frame shutter. The engine picks how many from how fast
things move: the clip's speed (in source frames per output frame) and the camera's motion in pixels. Calm frames
use 1-3 samples, whips and crash zooms up to 16. Sped-up footage therefore smears like a real camera, and
punch-ins and shakes get blur for free.

## 6. The effects

All in `engine/fx.py` (GPU image operations), `engine/api.py` (montage recipes) and the section files.

| Effect | How it's built |
|---|---|
| **Impact** (most kills) | `impact()`: a whole-frame punch-in toward the kill point (zoom ~1.09 decaying in ~0.15 s), a seeded shake that decays, a short exposure kick (bright, not milky), an RGB split centred on the hit, an expanding shockwave ring that pushes pixels outward, and an impact sound. |
| **Strobes** | Very short flashes (white, red or bone) on the kicks between kills, alternating colours, often with a small rotation kick. |
| **RGB split / chromatic aberration** | Red sampled slightly outward from a centre point, blue slightly inward. |
| **Shockwave** | A ring of radial displacement that expands from the kill, with a colour fringe on the ring. |
| **Glitch tears** | Horizontal bands shifted sideways, per-band RGB offsets and copied blocks; the pattern changes 12-40 times a second from a seeded random generator. Used on cuts (CAM 01 → CAM 02) and to hide the player's own camera jumps. |
| **Speed lines** | Anime-style radial streaks from a centre, flickering by changing their seed a few times a second. |
| **Zoom blur / zoom-through** | Copies of the frame scaled 1 → 1+amount and averaged. The s05 → s06 transition rushes into one shot's centre and arrives zoomed-out in the next. |
| **Whip pan** | The outgoing shot slides and smears sideways, the incoming one slides in from the other side (s04 → s05). |
| **Slices transition** | The next shot arrives as horizontal strips sliding in one after another (Kayn → Samira). |
| **Kaleidoscope** | The frame folded into 6 mirrored wedges around a point: Viego's cyan blast becomes a mandala on his pentakill. |
| **Split-screen "doors"** | Three slanted panels (Sejuani, Viego, Vayne) slam in on the downbeat; one kill per kick, left → middle → right, the scoring panel flashes, the others dim, the sound pans to its side. The middle panel is the real Viego shot, so on the next downbeat the side panels fly off like doors and Viego fills the frame. |
| **Invert flash** | Two inverted frames on the pentakills: the hardest-hitting accent in the video. |
| **Instant replay** | After the drop's pentakill the picture stops dead, rewinds with a VHS look, then replays the kill from a new angle (tighter, Dutch tilt, slight 3D yaw) with the music muffled, landing again on "ROCKSTAR". |
| **CCTV / surveillance look** | A cold grade (low saturation, teal), scanlines, heavy grain and vignette, a REC dot, CAM label and running timecode, a date stamp, target brackets that lock onto the player ("SUBJECT: ART3M1S") and later onto the enemies ("TARGET LOCKED"), digital "enhance" zoom snaps that resolve from pixelated to sharp, and a CRT power-on opening (black → static → a line that opens into the picture). |
| **Paranoia look** | Everything grey except reds (a hue-keyed colour pop), a dark tunnel spotlight around the player, heartbeat sounds on the 808 hits, the song low-passed so it sounds underwater. |
| **HP readouts** | Punch-ins onto the game's own HP number (Ashe at 3/2305), an ECG line that flatlines, and in the finale an HP percentage that counts down with the clip (24% → 9% → 7%). |
| **Text** | Words rendered as glyph sprites (free Google fonts: Anton, Share Tech Mono, others) and drawn on the GPU: slams that scale in from 2-3× with RGB split and glow, kill counters whose letters drop in one by one, a typed wiretap caption ("EVEN ROCK STARS GOT FEELINGS"), and the end, where "ROCKSTAR" scrambles and decodes into "PARANOIA". |
| **Evidence board** | In the hunt, each Kayn kill is logged as a "photo" that flies into a 4-slot hit list and gets crossed out. |
| **Letterbox breathing** | Bars slide in when the beat drops out before the finale's last line, so the frame "breathes". |
| **Grades** | Named looks blended in and out: `surveil`, `paranoia`, `rockstar` (default) and `hot` (peaks). The hunt warms bar by bar from surveillance to full colour; Samira's violet map gets a de-purple correction. |

**The haze lesson.** The first render had too many milky frames: flashes, exposure lifts and bloom stacked up. The
fix, now a rule: white-outs longer than 3 frames only at two planned seams, flashes capped except on the 3-4 biggest
hits, light from short exposure kicks rather than white screen-blends, and a clean image 0.15 s after every hit.

## 7. Sound design

- **The song** is the backbone. The engine edits it in places: a low-pass that opens back up (the CRT power-on, the
  near-death break), a **tape-stop** after the drop's pentakill (the music grinds to a halt with the picture), and
  ducks under the announcer.
- **Game audio** follows each shot's remap like tape: slow-mo pitches down and gets muffled, fast-forward pitches up.
  It sits 15 dB under the music and jumps 9 dB on every kill so the hit sounds punch through. The microphone track is
  never used.
- **Synthesized effects** (`engine/audio.py`, no sample files): whooshes on transitions, impacts and booms on hits,
  risers and reverse cymbals into drops, sub drops, heartbeats, glitches, camera-shutter clicks, ticks and zaps.
- **The announcer** ("Quadra kill!", "Pentakill!") is the real League announcer cut from the clips' game audio:
  `tools/announcer.py` isolates the voice with Demucs and finds the words with whisper. Most raw matches turned out to
  be whisper hearing words in game noise ("Thank you"), so each cut line is transcribed again on its own and kept only
  if it says the right words. Two lines passed; the announcer is the same recording in every game, so they serve every
  callout. **The rule**: one line per kill streak, only at its peak (no "Quadra kill" right before a "Pentakill").
  The three pentakills build up: Viego's quieter and drier, the drop's full, the finale's loudest with the longest
  echo and the deepest music dip.

## 8. Moment by moment

| Time | What happens | Main techniques |
|---|---|---|
| 0.0-2.9 | CRT power-on into CAM 01; Kha'Zix decloaks on "falls" | CCTV look, brackets, RGB time split, slow-mo |
| 2.86 | Kill + PARANOIA title out of the flash | impact, ink-on-white title, glitch |
| 3.6-5.7 | Freeze-frame, "ID: ART3M1S", enhance snaps | freeze key, pixelate → sharp, scan sweeps |
| 5.72 | Glitch cut to CAM 02: HEARTSTEEL Kayn ambush | glitch transition, brackets "SUBJECT" |
| 8.54 | Drums enter: the feed snaps to colour, same Kayn shot continues | seam contract, saturation burst |
| 9.2-13.6 | Kayn's quadra, kills on kicks, hit list fills | velocity remap, evidence board, glitch cut |
| 13.6 | "Quadra kill!" | announcer line |
| 14.2-19.8 | Samira's flaming roll, three kills, strobes, crash-zoom ladder | slices transition, echo trails, de-purple grade |
| 19.8-28.3 | Drums out: Ashe vs. the red rocket, Yi at 65 HP, freeze on 3 HP, "FALL HARD" | paranoia look, RIFE slow-mo, HP punch-ins, ECG |
| 28.28 | White-out into the drop | seam contract |
| 28.3-33.2 | Samira's pentakill, one kill per kick, "ROCK STAR" | velocity remap, strobes, callouts |
| 33.2 | PENTAKILL: invert flash, "Pentakill!", tape-stop | invert, announcer, music edit |
| 33.9-36.8 | Rewind and instant replay from a new angle | negative-speed remap, 3D tilt, echo trails |
| 39.58 | Whip pan to Darius's triple | whip, echo trails |
| 42.4-45.2 | 3-panel split-screen, one kill per kick | doors split-screen |
| 47.36 | Viego's penta in a kaleidoscope, "Pentakill!" | kaleidoscope, announcer |
| 48-50.9 | Freeze, invert snap-back, Vayne's white-out | RGB time split, zoom-blur rush |
| 50.88 | Zoom-through into the finale | zoom-through |
| 51.4-55.8 | Triple, quadra, HP counts down 24% → 7% | HP readout, heartbeat, fast-forward |
| 56.54 | PENTAKILL at 7% HP, the biggest hit | invert, hit-stop, rings, speed lines, loudest announcer |
| 58.5-59.3 | "ROCK" / "STAR" slams, rush into the burst | text slams, speed lines |
| 59.32-62.5 | ROCKSTAR decodes into PARANOIA, CCTV returns: "SUBJECT: ALIVE" | decode text, surveillance callback, fade |

## 9. How the work was split

- **Lead (one session):** research, the engine (`engine/`), song analysis, catalog, scouting tools, the treatment and
  the brief, review, and every render. All heavy work ran on rented RTX 5090s (Vast.ai), never on the user's PC.
- **11 + 3 scouting agents** rated clips from contact sheets.
- **6 section agents** wrote one section each in parallel from `docs/ENGINE.md` and `docs/TREATMENT.md`, agreeing on
  the cuts between sections through "seam contracts" (e.g. at 8.54 the Kayn clip shows clip time 35.85 moving at
  0.6x on both sides). After the first review render they fixed their own sections from contact sheets and
  every-frame strips.
- **One agent** wrote the audio mixer and the synthesized sound effects.

## 10. Rendering

- 1080p trial: 3,750 frames at 60 fps in about 4.5 minutes on one 5090 (average 3 motion-blur samples per frame).
- Effects measured in pixels (RGB split, smears, glitch offsets, text fringes) are written for 1080p and scale with
  frame height, so the 1440p version looks the same, just sharper.
- Audio-only changes (the announcer lines) re-render just the soundtrack and swap it into the finished video without
  re-encoding the picture.

## 11. Things that went wrong (and the fixes)

| Problem | Fix |
|---|---|
| The beat tracker doubled and dropped beats in the quiet bridge | evenly spaced beats over that stretch (`GRID_FIX` in `engine/config.py`) |
| The drum-pattern grid drifted 0.35 s (a rounded analysis frame rate) | the analysis now refuses frame rates that don't divide the sample rate |
| Kill banners lag the kills by up to 2 s | sync to the scoreboard counter and the damage pop-ups instead |
| The first render was hazy | the haze rules above; impact now uses a short exposure kick |
| Whisper "heard" announcer lines in game noise | re-transcribe every cut alone; keep only exact matches |
| Scouts called a big explosion "the Nexus" (it wasn't) | the user caught it; the docs were corrected (no on-screen text claimed it) |
| The newest ffmpeg builds need a GPU driver many rented hosts lack | pinned to the ffmpeg 8.1 build |
| Agents ran small tests on the user's PC | the brief now forbids any local video/audio processing |
