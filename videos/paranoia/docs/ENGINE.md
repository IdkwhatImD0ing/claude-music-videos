# Engine brief: writing a section of the PARANOIA montage

You own ONE file: `sections/sNN_<name>.py`. Never edit anything else (engine/, other sections, data/, tools/). If the
engine lacks something or has a bug, work around it inside your file and report it in your final message.

Read `docs/TREATMENT.md` first (concept, look, the section plan and your clips), then this page.

## The video

60 s, 1920×1080 trial at 60 fps, cut to HEARTSTEEL "PARANOIA" (song 135.70 → 195.70 s). Gameplay is the user's own
League of Legends clips (2560×1440 60 fps, HUD burned in; we keep the HUD). Every frame is a pure function of video
time `t` (no randomness without a seed, no state between frames). Rendering happens on a cloud GPU; you can't render
yourself (see "Checking your work").

## Timing (video seconds)

- Tempo 85.71 BPM: beat = 0.7025 s, bar = 2.81 s (4 beats), 16th = 0.1756 s.
- `song.bar(b)` = video time of bar b's downbeat (bar 0 = t 0.00). Bars: 0→0.00, 1→2.86, 2→5.72, 3→8.54, 4→11.36,
  5→14.18, 6→17.00, 7→19.82, 8→22.66, 9→25.48, 10→28.28 (DROP), 11→31.12, 12→33.94, 13→36.76, 14→39.58, 15→42.42,
  16→45.24, 17→48.06, 18→50.88, 19→53.70, 20→56.54, 21→59.32 (the song's last hit).
- `song.beat(i)` = beat i (beat 0 = t 0); fractional i works (`song.beat(4 * b + 1.75)` = 16th 7 of bar b).
- Drum pattern (measured): in the chorus (bars 10-20) the kick/808 hits land on 16ths **0, 3, 6, 9, 12** of every bar
  (a 3-3-3-3-4 groove: +0, +0.527, +1.054, +1.581, +2.108 s after the downbeat), with a clap on beats 2 and 4
  (16ths 4 and 12). In the build (bars 3-6) kicks are on every beat plus 16ths 3 and 11. Bars 7-9 are the tension
  break: drums mostly out. Bars 0-2 are the quiet intro (no drums).
- Exact hits: `song.onsets('kick', t0, t1, min_s=0.8)` → list of times; `song.pulse(t, 'kick', decay=0.1)` → 0..1
  envelope for pumping effects; `song.env('vocals', t)` etc. for continuous drive.
- Lyrics: `song.words` = [(t0, t1, word)], `song.words_like('rock')`.

## Building blocks (from engine.api import *)

```python
E.shot(t0, t1, clip, remap, cam=Cam(...) or fn(t)->Cam, fx=[fn(img, t, ctx)->img], src=None, name='', hits=[...])
E.transition(t0, t1, T.zoom()/T.whip()/T.flash()/T.spin()/T.glitch()/T.luma()/T.slices()/T.iris()/T.ink()/T.rgb())
E.layer(t0, t1, fn(img, t, ctx)->img, z=0)   # over the shots; gets shaken + motion-blurred with the frame
E.top(t0, t1, fn, z=0)                       # crisp UI after blur/post (doesn't shake)
E.screen(t0, t1, fn(t)->dict(zoom, ax, ay, ox, oy, rot, lens))   # whole-frame camera (punches, global shake)
E.post(t0, t1, fn(P, t))                     # edit post params P in place: exposure contrast sat temp tint shadows
                                             # highlights bloom bloom_threshold chroma flash flash_color invert
                                             # zoom_blur glitch duotone duo_dark duo_light ink desat vignette grain
                                             # letterbox scanlines (see POST in engine/edit.py for defaults)
E.samples(t0, t1, n)                         # force n motion-blur sub-samples (e.g. during a spin)
E.sfx(kind, t, gain_db=0, ...)               # whoosh(dur, direction) impact(strength) boom(dur) riser(dur, ends at t)
                                             # reverse(dur, ends at t) subdrop glitch tick heartbeat zap shutter
E.music(kind, t0, t1, ...)                   # on the SONG: lowpass(cutoff_from, cutoff_to) tapestop stutter(div)
                                             # reverse mute gain(db) duck(db)
E.voice(wav_path, t, gain_db, echo, room, duck_db)   # a recorded line starting at t (leading silence trimmed),
                                             # e.g. the announcer lines in out/voice/ (sections/s90_voice.py)
```

- **Shots.** Shots in your SPAN must cover it with no gaps. Overlap two shots only for a transition (the later one
  wins outside the transition window). Game audio follows each shot's remap automatically; pass `hits=[video times
  of kills]` so the kill sounds punch through; `game_db=-15` default.
- **Remap = sync.** `velocity([(t_video, s_clip), ...], t_in, s_in, t_out, s_out=None, hit=0.3, ease=(0.25, 0.5),
  hold=0)` lands each clip time exactly on its video time, slowing to `hit` speed through it and running fast between
  (the velocity look). `Remap([K(t, s, v, ease)...])` for full control (v = speed, 0 = freeze, negative = rewind),
  `Remap.constant(t0, s0, speed, t1)`, `Remap.hold(t0, t1, s)`. Keep cruise speeds within ~0.15x-6x (`render.py
  check` prints warnings). Slow-mo below 1x uses RIFE in-between frames automatically: it looks good down to ~0.15x.
- **Kills.** `kills(clip)` = the clip's best kill chain (clip seconds, Moments markers, accurate to about ±0.5 s).
  Your clip notes in TREATMENT.md give refined times where we have them. Land the kill moment (death/explosion of the
  enemy, or the "+300 gold"/banner pop) on a drum hit.
- **Camera.** `Cam(zoom, cx, cy, rot, ox, oy, yaw, pitch, lens)`: cx, cy = the clip point (0..1) at screen centre,
  so `Cam(zoom=1.35, cx=0.55, cy=0.45)` frames that area. Zoom ≥ 1 always (we must fill the frame); 1.0-1.6 is the
  useful range at 1080p (the source is 1440p). `shake(t, amount, freq, seed)` → (ox, oy, rot) for `cam.add(...)`.
  `follow([(t, cx, cy), ...])` → smooth focus path. The HUD stays: don't zoom so far that the fight leaves the frame.
- **Order matters.** Posts run in the order you register them, and `look()` sets values (exposure, sat, bloom...),
  so register looks first and hits/strobes after.
- **Looks.** `look(E, t0, t1, 'surveil'|'paranoia'|'rockstar'|'hot', fade_in=0, fade_out=0, amount=1)` applies a
  named grade (see `LOOKS` in engine/api.py) blended in/out. The default grade is 'rockstar'. Post params also include
  `pop` (0..1, keep only reds) and `pop_hue`.
- **Recipes.** `impact(E, t, strength, cx, cy, ..., end=SPAN[1])` = punch-in + shake + flash + RGB split + shockwave +
  sound in one call (pass `end` so a late hit can't spill into the next section); `beat_pulse(E, t0, t1)` = zoom pulse on every kick. Layers: `L.slam(text, t0, ...)`,
  `L.counter('TRIPLE KILL', t0)`, `L.lock(t0, t1, cx, cy)` (target brackets), `L.rec()` (CCTV HUD), `L.bars(fn)`,
  `L.words(t0, t1)` (sung words pop up). `panel(img, clip, s, x0, y0, x1, y1, cam)` draws another clip into a
  rectangle (split-screens, picture-in-picture). Effects in `fx`: zoom_blur, dir_blur, spin_blur, blur, bloom, grade,
  vignette, flash, exposure, invert, duotone, ink, posterize, tint, color_pop, spotlight, light_leak, grain,
  scanlines, chroma, shockwave, ripple, glitch, slices, pixelate, mirror, kaleido, ring, disc, line, rect,
  brackets, crosshair, speed_lines, letterbox, over, place. Text: `ty.text(img, s, x, y, size, font, color, scale,
  rot, alpha, tracking, stroke, stroke_color, shadow, glow, glow_color, split, anchor, weight)` and
  `ty.letters(..., per=fn(i, n)->dict(dx, dy, scale, rot, alpha))`; fonts 'anton' 'bebas' 'blackops' 'mono'
  'orbitron' 'glitch' 'cinzel'. Read engine/fx.py, engine/type.py and engine/api.py for exact signatures.
- **Pixel amounts** (chroma, dir_blur, glitch RGB offsets, text `split`) are 1080p pixels: the engine scales them by
  frame height (`fx.PX`), so write them for 1080p and every render size looks the same.
- **Per-shot fx** run in output space after the camera: `fx=[lambda img, t, ctx: fx.chroma(img, 8)]`.
- **Custom source sampling** for time effects: `src=lambda t, ctx, shot: ...` returning a source frame
  `shot.clip.at(s)`; e.g. echo trails = weighted sum of `clip.at(s - k*0.05)`, RGB time split = channels from
  different s. These cost one clip sample each, so keep them short.

## Rules

1. Something happens in every shot, and every big hit lands on a drum hit you can name (bar + 16th).
2. Pacing (the user's rule): no shot shorter than 2 beats (1.4 s); flashes and strobes inside a shot are fine.
   Any text the viewer must read stays ≥ 1.2 s (titles ≥ 3 s). Keep text minimal: one-word slams, kill callouts,
   lyric punches. No paragraphs.
3. Keep the action readable: after every crazy moment, give the eye a few frames of clean image. Don't stack every
   effect at once; pick a vocabulary per moment (see TREATMENT "Effect vocabulary").
4. Your first and last 0.3 s must match the hand-off described in TREATMENT (what the neighbouring sections do at
   the seam), so cuts between sections land on the beat and feel intentional.
5. Determinism: seed any randomness from t or constants (`hashf`, `noise1`, `fx.glitch(img, int(t*12))`).
6. Performance: each sub-sample samples every active shot; a 2-shot transition with 8 samples = 16 clip samples.
   Fine, but avoid sampling more than ~4 extra source frames per sub-sample in custom `src` functions.

## Checking your work

You can't run the renderer (it runs on a cloud GPU the lead controls). **Never run ffmpeg, torch, the engine or any
video/audio processing on this PC, not even a small test** (the user's rule: nothing heavy on their machine; they play
games on it). Reading files, images and the strips/sheets already rendered is fine. Before you finish:
- Re-read your file for Python errors; it's imported with `from engine.api import *`. Only use names that exist.
- Sanity-check every remap by hand: for each key, is the clip time inside the clip (0..duration ≈ 60 s) and does
  the kill land where you intend? Write the math in comments.
- In your final message, list: shots (t0-t1, clip, what happens), every synced hit (video t ↔ bar/16th ↔ clip time),
  and up to 12 times you most want the lead to render as a contact sheet to check your work.
The lead renders sheets/strips, sends them back to you, and you fix what looks wrong.

## Commands the lead runs for you (on the cloud machine)

```
python render.py check --only s03                          # shot list, gaps, remap warnings
python render.py sheet --t 8.6,9.2,... --only s03 --out out/wip/s03/a.jpg
python render.py strip --from 28.2 --to 28.6 --only s04 --out out/wip/s04/strip.jpg   # every frame
python render.py video --from 28.28 --to 39.58 --only s04 --out out/wip/s04/v.mp4
```
