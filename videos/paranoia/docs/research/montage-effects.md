# Gaming montage research (2026-10-02)

What League and Valorant montage editors do, what our footage looks like, and how we could build one in code.
(Written before the video. What we actually built, effect by effect: [`../HOW-IT-WAS-MADE.md`](../HOW-IT-WAS-MADE.md).)

## 1. What a montage is

A montage is a set of short gameplay clips cut to one song. The best plays (multikills, outplays, steals, clutches)
are timed so the hits land on the music. Two common formats:

- **YouTube montage:** 16:9, 2 to 4 minutes, a slow intro, then the hardest clips on the drops and choruses.
- **Short / TikTok "edit":** 9:16, 15 to 60 seconds, one or two plays, heavy effects on every beat.

Rules of thumb from editing guides (DOR, Eklipse):

- Clips run about 3 to 8 seconds. Start just before the climax and keep only the core action.
- Collect 2 to 3 times the footage you plan to use.
- Pick the song first. Slow sections get longer clips; fast sections get quick cuts.
- Put the biggest play on the hardest drop. Don't cut on every beat: cut on strong beats, and use zooms or shakes on
  the weaker ones.
- Plain cuts work best in fast sections. Save fancy transitions for places where the mood changes.

These fit our pacing rules (no shot under 2 beats; see memory "pacing-rules").

## 2. The effects, and how we'd do each in code

"Sync" is the core of the craft. Montage makers say a clip is "synced" when its kills, shots or ability hits land
exactly on beats of the song. Everything below serves that.

| Effect | What it looks like | How editors make it | How we'd make it |
|---|---|---|---|
| Sync | Each kill lands on a kick, snare or drop | Hand-placed in After Effects or Premiere | Solve it: we know kill times (section 4) and beat times (song analysis), so we pick where each kill lands |
| Velocity / speed ramp | Fast between moments, slows into the hit, snaps back to full speed on the beat | Time remapping plus Twixtor | A time-remap curve per clip. Between two kills, speed = game seconds ÷ song seconds, so velocity falls out of the sync |
| Slow motion | Smooth slow-mo on the key moment | Twixtor (optical flow), or footage recorded at high fps | Our clips are 60 fps, so 0.5× is native. Deeper slow-mo needs made-up in-between frames: RIFE (free, MIT licence) |
| Motion blur | Smears on fast motion, speed-ups and shakes | RSMB (ReelSmart Motion Blur) | Average several source frames per output frame when sped up (60 fps footage gives this for free); sub-sample the camera moves (the gen renderer already does this) |
| Zoom punch | Quick push-in on a beat, then back out | Scale keyframes | Scale the frame around the action point with a fast ease |
| Camera shake | The frame jolts for 2 or 3 frames on a hit | Sapphire S_Shake, wiggle expressions, shake preset packs | Seeded-noise offset and rotation, slightly zoomed so edges never show |
| Flash | One white (or bright) frame where a cut lands | Exposure or solid layer | Add exposure that decays over 2 to 4 frames. Flash already exists in the base and gen engines |
| RGB split / chromatic aberration | Red and blue edges pull apart on impact | Built-in or plugin effects | Shader that samples red and blue at offset positions. Gen `post.ts` has CA |
| Glow | Ability effects bloom | Deep Glow, Sapphire Glow | Bloom on the bright parts. League's spell effects are already bright, so this works well |
| Color correction ("CC") | Punchier contrast and colour, all clips matching | Lumetri, Magic Bullet Looks, LUTs, vignette | One grade shader for every clip, plus vignette and grain (gen `post.ts`) |
| Transitions | Zoom-through, whip/swipe, spin, glitch, flash, ink or mask wipes | Presets, plugins, hand masks | gl-transitions (a free collection of GLSL transitions) or our own whip smear |
| Overlays | Film grain, dust, light leaks, letterbox bars | Stock overlay packs | Shaders; no stock footage needed |
| Text | Intro card with the player name, "PENTAKILL" counters, 3D titles | After Effects text, Element 3D | Gen typography. League also shows its own "DOUBLE KILL!" banners we can lean on |
| Freeze frame | Frame stops, zooms on the champion, label pops | Hold frame plus zoom | Hold source time while the zoom keeps moving |
| 3D camera | The flat clip tilts and turns in space | Plugins like CC Sphere, 3D layers | Draw the clip on a 3D plane in three.js |

Sound design matters as much as the picture:

- **Whoosh** on each transition, as long as the move it covers.
- **Riser** that builds into a drop, and an **impact** on the drop.
- **Game audio under the music**, pushed up on the hits so you hear the kill sound and the announcer.
- **Low-pass filter** (muffled sound) during slow-mo, opening back up when speed returns.
- A short **silence** right before a drop.

## 3. Tools people use

- **Pro:** After Effects with Twixtor (slow-mo), RSMB (motion blur), Sapphire (shake, glow, flares), Deep Glow,
  Magic Bullet Looks (colour). Premiere for the edit. Sony Vegas was the classic montage tool and some still use it.
- **Free:** DaVinci Resolve (its Speed Warp does Twixtor-style slow-mo), CapCut (velocity and shake presets, mobile
  edits), Flowframes and RIFE (frame interpolation).
- **Auto-montage apps:** Eklipse, Medal, DOR and Insights find kills and cut clips to music, with simple effects.
- **Open source:** Crispy (MIT) uses a neural network to find kills in Valorant, Overwatch and CS footage.
  ClipSyncAI (MIT) does the same for Valorant with YOLO. Both cut clips; neither does the effects.

Our edge over the apps: we control every frame and every beat. The apps make generic clips; editors spend hours on
sync by hand. Since we know the kill times and the beat times, sync becomes something we solve once and then tune.

## 4. Our footage: SteelSeries Moments

The user doesn't want Riot replays. The clips come from SteelSeries Moments.

- **Where:** `D:\PubgHighlights` (Moments' capture folder) holds almost everything. `C:\Users\Bill\Videos\SteelSeries
  Moments` holds 11 older clips. Moments' database: `C:\ProgramData\SteelSeries\GG\apps\moments\db\database.db`.
- **What:** 807 League clips (about 13 hours, 153 GB) from Dec 2025 to Oct 2026. 9 Valorant clips, all from one day
  (2026-09-24). A few other games.
- **Quality:** 796 of the League clips are 2560×1440 at 60 fps, H.264. The 11 oldest are 1920×1080 at 30 fps.
  Each clip is about 60 seconds.
- **Audio:** two tracks, "Game" and "Mic". We'd use only Game.
- **Kill markers:** each clip stores the game's events as JSON inside the file (and in the database): kills, assists,
  deaths, dragon/baron/herald kills, with times. 1,682 kill markers in total. The markers are rounded to whole
  seconds (all kills in a clip share the same fraction), so we'd snap each one to the exact frame using the game
  audio or the on-screen kill banner. In one clip I checked, the markers matched the kills to within a second.
- **Multikills:** grouping kills less than 10 s apart gives roughly 359 doubles, 120 triples, 38 quadras and
  8 pentas. These are estimates: some clips overlap and catch the same fight twice.
- **The HUD is burned in.** Ability bar, minimap, scoreboard, chat and an FPS counter are all in the picture. Chat and
  name tags show other players' summoner names, so we'd blur chat at least. Zooming in crops some of the HUD, and
  1440p leaves room to zoom about 1.33× for a 1080p trial.

Sample frames from a five-kill fight: `scratchpad/peek/sheet.jpg` (temporary; not in the repo).

## 5. How we'd build it (proposal)

1. **Index** all clips' markers into one table: kills, multikill size, objectives.
2. **Shortlist** the pentas, quadras and steals, then make contact sheets so the user can pick favourites.
3. **Snap** each kill to the exact frame from the game audio near the marker.
4. **Analyse the song** with gen's tools (`analysis/analyze.py`): beats, downbeats, kick/snare hits, sections, drops.
5. **Plan the edit** as data (`edit.json`): which clip goes in which section, and which beat each kill lands on, with
   speed kept between about 0.25× and 4×. Review it as a table before rendering anything.
6. **Render** each output frame as a pure function of song time `t`: look up the shot, its source time (from the
   time-remap curve), and effect strengths from the beat data. The gen engine fits: it has post effects (bloom, CA,
   grain, vignette, flash), sub-frame motion blur, the beat API and review sheets. Source frames get extracted to image
   sequences first, and RIFE fills in extra frames only where we go below 0.5× speed.
7. **Trial at 1080p, production at 4K 60 fps**, on Vast machines. 4K means upscaling the 1440p footage 1.5×.

Things to test early: RIFE on League's busy spell effects (it may smear), the kill-snap accuracy, and how much HUD
cropping the user wants.

## 6. Rules to follow

- **Riot's "Legal Jibber Jabber" policy** allows fan videos with game footage and passive ad revenue. No paywalls
  (Patreon, YouTube Premium) without a licence. No Riot logos or trademarks. Include the line: "[Title] was created
  under Riot Games' 'Legal Jibber Jabber' policy using assets owned by Riot Games. Riot Games does not endorse or
  sponsor this project."
- **Music:** a commercial song will get claimed on YouTube. Use one of the user's own songs or a cleared track.
  Popular montage genres: phonk, trap, dubstep/EDM, hyperpop; League montages also use epic or orchestral tracks.

## Sources

- DOR, how to make a gaming montage: https://clip.dor.gg/en/blog/how-to-make-gaming-montage
- Eklipse, montage editing principles: https://eklipse.gg/help/what-are-the-principles-of-good-editing-for-creating-seamless-and-engaging-clip-montages/
- Eklipse montage tools: https://eklipse.gg/tool
- Velocity edits and speed ramps: https://videowizardtools.com/does-capcut-have-motion-blur-and-velocity/
- Slow-mo and source frame rates: https://develop2.insights.gg/blog/how-to-record-valorant
- Boris FX Sapphire effect list: https://borisfx.com/documentation/sapphire/ae/intro
- Shake effect tutorial: https://borisfx.com/blog/shake-effect-after-effects-tutorial/
- After Effects plugins 2026: https://spotlightfx.com/blog/best-after-effects-plugins
- Flowframes (RIFE GUI): https://aihubsearch.com/tools/flowframes
- RIFE: https://github.com/megvii-research/ECCV2022-RIFE (Practical-RIFE is MIT)
- Crispy: https://github.com/Flowtter/crispy
- ClipSyncAI: https://github.com/Frozen-Bugg/ClipSyncAI
- gl-transitions: https://cdn.jsdelivr.net/npm/gl-transitions@1.67.0/README.md
- Riot Legal Jibber Jabber: https://www.riotgames.com/en/legal
- Royalty-free montage music: https://blog.slip.stream/royalty-free-music-for-game-highlights-montages-livestreams-and-more/
- Valorant replays (not used, for reference): https://playvalorant.com/en-us/news/dev/replays-everything-you-need-to-know
