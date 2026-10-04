# PARANOIA: treatment

A 60-second League of Legends montage of the user's own plays, cut to the last minute of HEARTSTEEL's "PARANOIA"
(song 135.70 → 198.2 s: quiet bridge, build, a drum-less break, then the final chorus to the song's real ending; the
last hit is t 59.32 and a 3 s end card holds over the song's tail, so the video runs 62.5 s).
16:9, trial 1920×1080 at 60 fps. The user's brief: "the biggest things I want to see is synced to the video and
special effects ... go wild, this is a test of your capabilities". Keep the in-game HUD.

## Idea

**Everyone is praying for the death of a rock star. The rock star keeps answering.**

The lyric in our window is "They're praying for the death of a rock star / Everybody hates it ever since you got
more". The player is the rock star: watched, hunted, nearly killed, and every time the chorus says they should die,
they take a pentakill instead. The video moves through three registers, each with its own look:

1. **SURVEILLANCE** (bars 0-6, t 0-19.8): we watch the player like a target on a security feed. Cold desaturated
   grade, scanlines, REC dot and timecode, CAM labels, target brackets. At the start the brackets track the player
   ("SUBJECT"); in the build they flip onto the enemies ("TARGET LOCKED") and the kills begin.
2. **PARANOIA** (bars 7-9, t 19.8-28.3): the drums drop out ("oh-oh... Every time you pop up, they hoping that you
   fall hard"). Slow-mo near-death: tunnel vision, everything grey except red, heartbeat on the beat, glitch tears,
   the song muffles, a freeze-frame on the lowest HP, then a riser and a white-out.
3. **ROCK STAR** (bars 10-21, t 28.3-60): the final chorus. Full colour, stage-light strobes on the 3-3-3-3-4 kick
   pattern, every kill on a hit, kill callouts, lyric slams, speed lines, whip and zoom transitions, one split-screen
   and one kaleidoscope burst. Ends on the best pentakill: the last kill lands on bar 20 ("praying for the death of a
   ROCKSTAR"), freeze, colour drains to red, title.

## Look

- **Palette.** Signal red (1.0, 0.16, 0.22), electric cyan (0.2, 0.95, 1.0), bone white (0.96, 0.94, 0.9),
  ink (0.02, 0.02, 0.04), and League gold (1.0, 0.82, 0.3) for kill callouts only. RGB splits push red out and cyan
  in.
- **Grade.** Surveillance: sat 0.35-0.5, slight teal (temp -0.3), contrast 1.15, scanlines 0.12, grain 0.05.
  Paranoia: `color_pop` on red, contrast 1.25, vignette 0.6 (tunnel), exposure -0.3. Rock star: sat 1.25,
  contrast 1.12, bloom 0.45 (stage glow), grain 0.02.
- **Type.** Anton for slams and callouts (caps, tight); Share Tech Mono ('mono') for the surveillance HUD; the title
  "PARANOIA" in Anton with RGB split and glitch. Text stays minimal: title, HUD labels, kill callouts, a few lyric
  slams ("ROCK STAR", "FALL HARD"). Nothing the viewer must read stays under 1.2 s; the title holds ≥ 3 s.
- **Motion.** Velocity edits: fast between kills, slowing to 0.2-0.35x through each kill, snapping back on the hit.
  Zoom punches (≤ 1.6x) toward the kill point. Shake decays within 0.25 s. Motion blur everywhere (auto sub-samples).

## Effect vocabulary (don't use everything everywhere)

| Register | Use | Avoid |
|---|---|---|
| Surveillance | REC/timecode HUD (E.top), brackets + crosshair, slow push-ins, scanlines, glitch tears on cuts, `tick` and `heartbeat` sfx, `shutter` sfx on freeze-frames | strobes, gold callouts, speed lines |
| Paranoia | slow-mo 0.15-0.35x, `color_pop` red, `spotlight` tunnel, chroma pulses on beats, freeze-frame, ripple/shockwave, music lowpass sweep, `riser` + `reverse` into the drop | fast cuts, bright bloom |
| Rock star | `impact` on kills, strobe flashes (white/red alternating) on the 16ths 0-3-6-9-12, speed lines, kill callouts, lyric slams, whip/zoom/spin transitions, kaleido/mirror burst (once), split-screen (once), echo trails, invert flash on a clap | surveillance HUD (except as a callback in the finale) |

## Sections

One file each, written in parallel. Bar numbers count from video t = 0 (bar b starts at `song.bar(b)`).

| File | Span (t) | Bars | Music | Job |
|---|---|---|---|---|
| `s01_feed.py` | 0.00-8.54 | 0-2 | Quiet bridge: "Hoping that the Eiffel falls / You don't understand the life we chose / My life's a pool... need my silence" | Open from black on a CCTV feed. Slow, ominous. CAM 01: Kha'Zix stalking a dark river. Title PARANOIA glitches in on bar 1 (2.86) and holds ≥ 3 s. Glitch cut on bar 2 (5.72) to CAM 02: HEARTSTEEL Kayn walking in, brackets tracking him ("SUBJECT: ART3M1S"). |
| `s02_hunt.py` | 8.54-19.82 | 3-6 | Drums + bass enter: "my privacy so I can heal / even rock stars got feelings / In reality, it's just a piece I could drill / Always" | The hunt starts: the same Kayn shot continues and he takes his quadra (velocity-synced); brackets flip onto the enemies ("TARGET LOCKED"). Then Samira's flaming-ult run. The surveillance look warms bar by bar to full colour by 19.8. A HEARTSTEEL member on "even rock stars got feelings" (10.9-13.3). |
| `s03_fall.py` | 19.82-28.28 | 7-9 | Drums out: "oh-oh... oh-oh... Every time you pop up, they hoping that you fall hard" | Near-death in slow-mo: Ashe's double kill, then a giant red rocket sweeps the screen and drops her to 69, then 3 HP. Heartbeat, tunnel, red-only colour, punch into the HP bar, freeze on 3/2305 ("FALL HARD" slam on "fall" 27.42 / "hard" 27.68), riser from ~26.1, white-out on 28.18 into the drop. Optional second near-death (Master Yi at 65 HP). |
| `s04_drop.py` | 28.28-39.58 | 10-13 | Chorus: "They praying for the death of a rock star / Everybody hates it, ever since you got more / They're praying for the death of a rockstar / Ooh, they love you when you're lost" | THE DROP. Samira's tight pentakill (5 kills in 6.8 s), velocity-synced: kill 1 on the drop (28.28), kills on the kick pattern, callouts DOUBLE→PENTA, strobes. "ROCK STAR" slams when sung (30.26, 35.90). After the penta: an instant-replay trick (rewind, replay the last kill from a new angle). Last shot runs to 39.76 for s05's whip. |
| `s05_star.py` | 39.58-50.88 | 14-17 | "Mother, love, life at the top / Everybody hates it ever since you got born / praying for the death of a rockstar / Hop on, they don't think that you're born" | Rapid highlight run: Darius triple under a turret, a 3-panel split-screen on "Everybody hates it ever since you got born" (42.2-44.6), Viego's quadra + penta 0.4 s apart with the cyan blast (kaleidoscope burst), Vayne's white-out explosion. Whip in from s04 (owned here, 39.40-39.76). Peak density. Last shot runs to 51.06 for s06's zoom-through. |
| `s06_finale.py` | 50.88-62.50 | 18-21 + tail | "They're praying for the death of a rockstar / Everybody hates it ever since you got born / They're praying for the death of a rockstar" (sung to 58.5), last hit 59.32, then the song's tail | Samira's pentakill at 7% HP: quadra, HP crashes to 7%, the penta lands on bar 20 (56.54) with the biggest impact of the video, slow-mo afterglow, "ROCKSTAR" slam on 58.50, a huge red-orange burst on the last hit 59.32 (the scouts called it the Nexus exploding; the user says the game didn't end there). Surveillance HUD returns for a beat ("SUBJECT: ALIVE"), colour drains to red, end card PARANOIA holds 59.3-62.5, fade to black by 62.5. Zoom-through in from s05 (owned here, 50.70-51.06). |

### Seams (what both sides of each cut agree on)

- **8.54 (s01→s02):** drums enter. The same Kayn clip runs straight across the seam: at t 8.54 it shows clip time
  **35.85** moving at **0.6x** (both files must match exactly). s01's last 0.3 s: glitch tear + "LIVE" flicker; at
  8.54 the feed snaps from grey toward colour with a kick punch-in (s02). Both draw the REC HUD in their own spans (s02
  lets it fade out by ~14).
- **19.82 (s02→s03):** drums drop. s02's last hit lands on 19.11 (bar 6, 16th 12) at the latest; s03 opens with a
  hard cut to slow-mo and the colour already drained to red-only.
- **28.28 (s03→s04):** s03 ends in a full white-out (flash 1.0 from 28.18); s04 starts from white (flash 1.0 at
  28.28 decaying over 0.25 s) with an impact on 28.28.
- **39.58 (s04→s05):** whip pan to the left, transition window 39.40-39.76, owned by s05 (s04's last shot must run to
  39.76 so s05 can overlap it; s05 adds the transition).
- **50.88 (s05→s06):** zoom-through, window 50.70-51.06, owned by s06 (s05's last shot runs to 51.06).

## Clips

Every clip used goes into `library/footage-ledger.json` (tools/ledger.py) so later videos use fresh footage.

## Clip assignments

Scouting notes for every candidate: `data/scouting.json` (champion, what happens, kills with screen positions, low-HP
moments, camera, issues, tips). Kill times there come from the scoreboard counter (±0.13 s). Close-up strips at
1/30 s around each kill (and a few other moments) are in `out/wip/kills/<clip stem>_<t>.jpg`, labelled with exact
clip times: open them and pin each hit to the frame where the enemy dies (big damage numbers, death, gold pop-up).
The player's in-game name is **Art3m1s** (their own chat lines); their most-played champion here is Samira.

| Section | Clips (League-of-Legends__...) | Key moments (clip seconds) |
|---|---|---|
| s01 | `2026-04-06__23-04-42` Kha'Zix (CAM 01); `2026-02-19__23-12-48` HEARTSTEEL Kayn (CAM 02, continues into s02) | Kha'Zix dark river stalk 44.3-47.4, purple glow ~46.5. Kayn's dark approach 32.1-35.85 |
| s02 | `2026-02-19__23-12-48` Kayn; `2026-02-20__01-08-10` Samira | Kayn kills 36.25, 41.35, 43.85, 45.35 (the last two at ~13% HP; camera repositions at ~41.75). Samira: flaming ult rolls across 33.0-34.5, kills 31.35, 34.75, 38.75; red blast 39.7 |
| s03 | `2026-03-20__00-52-41` Ashe; optional `2026-04-07__21-21-36` Master Yi | Ashe kills 32.90, 34.10; red rocket hits 34.4-34.6 (HP 878 → 69); 3/2305 HP at 35.2 (zoom ~(0.42, 0.33); HP readout bottom-centre). Yi: 65/1672 HP 52.0-52.5, kill 52.55 |
| s04 | `2026-02-20__01-11-57` Samira | Penta kills 46.70 (strip-checked), 49.05, 50.65, 52.05, 53.55; purple R ring 48.7, orange R ring 50.5-51.7, white-green flash 53.45; all in the upper-middle (zoom ~(0.5, 0.3)); in-game PENTAKILL banner 55.7 |
| s05 | `2026-03-03__00-18-26` Darius; `2026-09-29__22-41-54` Viego (Summoner's Rift); `2026-02-25__01-03-33` Vayne; `2026-01-29__02-48-55` giant Sejuani (split-screen panel) | Darius triple 52.62, 53.02, 54.32 (centre, explosion ring 54.9). Viego kills 33.65, 38.92, 43.68, quadra 47.08 + penta 47.48 with the cyan R blast (zoom ~(0.43, 0.25)). Vayne crit 53.0 (2316), white-out explosion 54.55-54.70. Sejuani triple 51.3, quadra 54.35 |
| s06 | `2026-02-22__20-45-40` Samira | Quadra 20.05; HP 650 at 21.5 → 235 at 24.0 → 7% at 24.5; PENTA 24.65 (inside her R ring, ~(0.47, 0.45)); PENTAKILL banner after; big red-orange burst 26.2-26.9 (~(0.62, 0.28); not the Nexus); level-up 27.4 |

Use other clips from `data/scouting.json` only if one of yours turns out unusable, and say so in your report.

## Revision notes

- **2026-10-02, trial 1** (1080p60): six sections by parallel agents; review round 2 cut the haze (flash caps, short
  exposure kicks), fixed clipped text and pinned kills to whole source frames. The user: "Holy fucking this this is
  amazing".
- **Trial 2**: the game announcer's own "Quadra kill!" / "Pentakill!" lines on the callouts (`sections/s90_voice.py`).
  The user noted the finale's last burst is not the Nexus; docs corrected.
- **Trial 3**: one announcer line per kill streak, only at its peak (no quadra line right before a pentakill, no
  double/triple lines); the three pentakills escalate (Viego quieter and drier, the finale loudest).
- **Final**: 1440p60 (the footage's native size), effects scaled per resolution. Write-up:
  [`HOW-IT-WAS-MADE.md`](HOW-IT-WAS-MADE.md).

