# lyrics: the words in the picture

`blender/lib/pdoom/lyrics/` puts every sung word INTO the miniature as a physical, lit, animated thing: painted
wooden letter blocks, letter tiles, brass, cardboard, rubber-stamped ink, typewriter strips, glowing screen text,
chalk, bent paperclip wire, neon tubes, brass stencils, sticky notes, embossing tape, writing in a fogged pane and
gilding on a pane in front of the lens. Every word lands on its sung time from `data/lyrics.json` (the letters of
spelled words, A-G-I, N-V-D-A, R-L-H-F..., on their syllables), on twos like the puppets. One call shows a whole
scene's lines on an automatic "lyric stand"; per-line calls stage a line (or a few words) creatively.

Test scenes: `blender/scenes/_test_lyrics.py` (the first 30 s on the real desk: the default presentation plus A-G-I
light-up blocks, "training loss" typed on the laptop, line 4 rubber-stamped, line 5 as tiles Clawd eats, P(DOOM) and
FOOM slammed in brass), `_test_lyrics_gallery.py` (lines 10-23, one style or placement each) and
`_test_lyrics_scene.py` (a real scene script, unchanged, plus `ly.default(scene)`; pick it with `LYRICS_SCENE=`).

## Quick start

```python
from pdoom import chars, kit
from pdoom import lyrics as ly

def build():
    ...                                            # set, puppets, cameras, cuts (kit.cut_to), simulations
    chars.finish()                                 # so the stand sees the puppets' real poses
    # stage the lines you have ideas for (they claim their words) ...
    ly.accent(0, 'AGI', 'glow')                    # A-G-I light up inside whatever row shows line 0
    ly.line(3, words='training loss', style='screen', place=ly.laptop(d))
    ly.line(5, style='tiles', place=ly.At((7, -13.5, 0), flat=True, size=1.2),
            exit='eaten', exit_opts=dict(target=ly.mouth(clawd), t=lambda pc: chomp[pc.word.index] - 0.25))
    ly.line(7, words='FOOM', style='brass', place=ly.At((4, -22, 0), size=4.2), t_end=26.32)
    # ... then everything else, as painted blocks on the per-shot lyric stand
    ly.default('eat')
```

`default()` must come LAST (it shows only the words nobody claimed) and after the cameras and cuts exist. Call it
after `chars.finish()` and after `fx.bake()`: the stand probes the set with rays at a few frames of each shot.
`ly.finish()` writes the stands' visibility; `default()` calls it, and it also runs on save.

Build output lines starting `[run] lyrics:` name the shots where the automatic stand had to compromise (something in
the way, or only a blurry spot free): stage those lines yourself.

## How it works

- **Timing** (`data.py`). A scene shows every line with a word sung (or still held) in its window; the line's
  earlier words are already up on the scene's first frame, so a line that straddles a cut reads whole on both
  sides. Words starting in the last 0.25 s of a window are left to the next scene. `ly.lines_in('eat')` lists them.
  Letters ripple in over the start of their word (1-2 frames apart); letters of spelled words land on their `syl`
  times (ChatGPT: Chat, G, P, T; P(doom): P, (doom); hyphenated words by halves). A row leaves 0.25 s before the
  next line starts (so it is gone when the next first word lands), at the earliest 0.3 s after its last word
  starts and at the latest 0.6 s after the line's last word ends (`exit_time()`).
- **Rows.** Lines longer than `max_chars` (22) wrap into balanced rows (up to `rows`, 2), preferring a break after
  a comma or where staged words were taken out. Units: a block / a letter's cap height is 1 unit; the row's root
  Empty carries the placement and the size (cm per unit) as its scale.
- **Pieces.** One object per letter, parented to the row root, with a rest pose in row space. Meshes are shared
  (one per glyph per style). Letters face local -Y (the viewer); a flat row is the same row laid on its back.
- **Animation.** Reveals and exits are poses keyed on twos (CONSTANT keys half a frame early, like the chars
  library: no motion blur on letters) or on ones (slams, tumbles, typing) or smooth (draw-on wipes, fades).
  Visibility is keyed per object (`hide_render` and `hide_viewport`), clipped to each copy's shot.
- **State per letter** lives in custom properties read by the materials: `ly_on` (0..1 lit/sung), `ly_wipe` (0..1
  drawn), `ly_fade` (opacity). Key them yourself for extra effects: `pc.obj['ly_on']` etc.
- **Copies.** Automatic and lens placements build one copy of a row per shot (each cheated to its camera);
  explicit placements build one copy that every camera sees until `t_end`.

## API (`from pdoom import lyrics as ly`)

| Call | What it does |
|---|---|
| `line(q, *, words=None, style='blocks', place='auto', reveal=None, exit=None, preview='style', t_show=None, t_exit=None, t_end=None, hold=0.6, lead=0.35, size=None, max_chars=22, rows=2, align='center', support='style', reveal_opts=None, exit_opts=None, strings=False, name=None, window=None, spec=None, **style_opts)` | Stage a line or some of its words. Returns a `Lyric`. Words already staged are skipped (with a message). |
| `default(scene_id, *, window=None, style='blocks', place='auto', max_chars=22, rows=2, spec=None, **kw)` | Every unclaimed word of the scene, line by line, on the automatic stand. `kw` go to `line()` (e.g. `preview='blank'`, `color=`). Test scenes pass `window=`. |
| `accent(q, words, style, **opts)` | Those words take another style inside whatever row shows them (A-G-I as light-up blocks, P(DOOM) as brass slamming onto the stand). `opts`: style options plus `reveal=`, `preview=`, `exit=`, `reveal_opts=`, `exit_opts=`. Call before `line()`/`default()`. |
| `skip(q, words=None)` | Mark words as shown some other way (the scene's own title letters, a prop that IS the word). |
| `finish()` | Write the stands' visibility and drop the temporary text scene (runs on save too). |
| `lines_in(scene_id)`, `text(q)` | `{line: [word indices]}` a scene shows by default; a line's text. |
| `mouth(char, name='mouth')` | A moving target for `exit='eaten'` (Clawd's jaw socket over time). |
| `rack(cam, t0, t1, dist, dur=0.3)` | Rack a camera's focus to `dist` cm in front of the lens and back (for lens panes). |

`q` is a line index or a text fragment (`'sudden drop'`). `words`: `None` (all), `'training loss'` (a run of
words), `(a, b)` (slice), an index or a list. `style_opts` go to the style: `color=` (block paint: one '#hex' or a
list), `glow_color=`, `ink=`, `note=` (sticky colour), `radius=` (strokes), `strength=` (glows), `case=`, `punct=`
('minimal' drops , . ; : and quotes; 'keep'; 'none'), `font=` (a key of `text.FONTS`/`text.STROKES` or a file in
`fonts/`).

A `Lyric` has `.words` (`data.Word`: `.text`, `.start`, `.end`, `.letters` with `.t`), `.copies` (each with
`.root`, `.pieces`, `.supports`, `.seat`), `.pieces` (all copies) and `.objects`. A `Piece` has `.obj`, `.word`,
`.letter`, `.rest`, `.row`; add your own keys to `pc.obj` after `line()` (they merge with the library's).

### Placements

| Place | Meaning |
|---|---|
| `'auto'` / `Auto(**spec)` | The **lyric stand**: one per shot, found by `place.auto_seat` (below). Lines placed 'auto' in the same shot share it. |
| `At(loc, *, face='camera', flat=False, size=1.2, up=(0,0,1), parent=None, tilt=0)` | A spot in the world: `loc` = the row's base centre (cm). `face`: 'camera' (the camera live at `t_show`), a yaw in degrees (0 faces -Y) or a direction. `flat=True` lays the row on the surface, letter tops away from `face`. A `(x, y, z)` tuple means `At(loc)` with the style's size. |
| `On(origin, normal, up, *, size=1.0, parent=None, lift=0.01)` | A surface frame (world, or local to `parent`). |
| `on_object(obj, origin, normal, up, *, size, lift)` | Text on an object that follows it (jar, box side, clipboard, notebook): local origin/normal/up; the object's scale is compensated. |
| `laptop(desk, *, u=0.5, v=0.3, size=None, lift=0.02, follow=True)` | The laptop screen at (u, v); rides the lid. |
| `Lens(*, dist=None, u=0.5, v=0.12, height=0.07, max_width=0.8, cells=None)` | Camera-attached, per shot: a pane `dist` cm in front of the live camera (default 45 % of the focus distance). Soft unless the scene racks focus to it: `ly.rack(cam, t0, t1, dist)`. |

`strings=True` hangs each letter on a cotton thread going up out of frame (letters on strings).

### The lyric stand (the default presentation)

For each shot that shows a line, `auto_seat` tries candidate spots (lower half of the frame, centred then to the
sides; at depths from the focus plane forward) and keeps the one that is:

1. clear: rays from the camera to the row's face hit nothing in front of it or through it, no character's face is
   behind it, and it covers no other lyric, at the start, middle and end of the shot;
2. in frame for the whole shot (the camera may move);
3. sharp: the blur from the depth of field at its depth (thin-lens formula, which EEVEE matches with physical
   f-stops) is smallest;
4. low and central.

It then stands on whatever surface is under it ('desk': on the desk, a book, the laptop), on a little beech shelf
unit with legs down to that surface ('stand'), or floats on its shelf ('float': space, no surface below). Two-row
lines get two shelves. A soft warm spot light rides the stand (`StageSpec.light`, 0.22 of the desk lamp's
illuminance) so the letters read in dark scenes. Rows pop up on twos with a squash and drop off the back of the
shelf when they leave. Painted colours go by word (`blocks.colors`).

`StageSpec` (pass `spec=` to `default()`, or keywords to `Auto()`): `height` (a block as a fraction of the frame
height, 0.075), `max_width` (0.8), `blur` (px at 1920 wide, 2), `v` / `u` (candidate base heights and centres),
`row_gap` (1.6), `support` ('auto' | 'stand' | 'float' | 'desk' | 'none'), `flat_pitch` (cameras looking down
steeper than -55 deg get rows lying flat on the desk), `margin`, `light`.

### Styles (`STYLES`; `styles.py`)

| style | a letter is | reveal | preview (unsung) | exit | support | size (cm/unit) |
|---|---|---|---|---|---|---|
| `blocks` | painted beech ABC block, raised cream slab-serif letter | pop | - (or `'blank'`) | drop | stand / shelves | stand / 1.2 |
| `glow` | smoked acrylic block, amber letter lit from inside, a small light per block | light (flicker on) | dim (unlit) | fade | - | 1.2 |
| `tiles` | ivory letter tile with its score (lies flat by default) | flip | blank (face down) | sweep | - | 1.6 |
| `brass` | cast brass letter (slab serif, 0.3 deep) | slam (on ones, lands on the letter) | - | topple | - | 2.4 |
| `cardboard` | letter cut from corrugated cardboard | tumble (arcs in, lands on the letter) | - | topple | - | 2.0 |
| `stencil` | brass stencil plate with the letter cut out | slide | - | sweep | - | 1.6 |
| `stamp` | rubber-stamped red ink (a stamp slams per word) | stamp | - | none | paper card | 0.9 |
| `typed` | typewriter ink (Courier Prime) | type (key by key) | - | none | paper strip | 0.55 |
| `screen` | glowing monospace (IBM Plex Mono) | type | dim | fade | dark panel | 0.9 |
| `marker` | felt-tip handwriting (Permanent Marker) | draw (wipe) | - | none | a sticky note per word, slapped on | 0.7 |
| `chalk` | chalk script, single-stroke (Hershey script) | draw (along the strokes) | - | fade | slate | 1.4 |
| `wire` | bent steel wire, single-stroke (Hershey sans) | grow (along the strokes) | - | topple | - | 3.0 |
| `neon` | neon tube script (Hershey script) | light (flicker on) | dim (unlit glass) | fade | black board | 2.4 |
| `tape` | embossing tape, raised white condensed caps | type (the tape grows letter by letter) | - | none | tape strip per word | 0.5 |
| `fog` | letters wiped clear in a fogged pane (clear glass over frosted glass) | draw | - | fade | frosted pane | 1.2 |
| `goldleaf` | gilded sign-writing on glass | draw | - | fade | clear pane | 0.8 |

`support=` overrides ('paper', 'strip', 'panel', 'slate', 'pane', 'glass', 'backing', 'notes', 'tape', 'shelves',
'none'); to write on real glass (the snow globe, the jar, the window) use `fog` with `support='none'` and
`on_object(...)`. Solid styles (blocks, glow, tiles, brass, cardboard, stencil) standing in two rows get a little
shelf unit. A new style subclasses `styles.Style` (see `Brass` for a 15-line example).

### Reveals and exits (`core.REVEALS`, `core.EXITS`)

| reveal | options (`reveal_opts`) | | exit | options (`exit_opts`) |
|---|---|---|---|---|
| `pop` squash-stretch pop on twos | `hop` | | `drop` tip back off the shelf, fall | `stagger`, `floor` |
| `appear` / `stamp` just there | | | `topple` tip over like a domino | `back`, `stagger` |
| `type` a key strike | `bump` | | `sweep` swept sideways, spinning | `side`, `stagger` |
| `draw` / `grow` wipe or stroke draw-on | `dur` | | `shrink` | `stagger` |
| `light` flicker on | `flicker` | | `fade` light and paint fade | `dur` |
| `flip` face down to face up (hop) | `axis` | | `eaten` fly into a mouth | `target`, `frames`, `stagger` |
| `slam` drop from above, heavy land | `height`, `frames` | | `none` stays until `t_end` | |
| `tumble` tossed in on an arc | `frames`, `side` | | | |
| `slide` along the row | `dist`, `frames`, `side` | | | |

Any exit also takes `t=`: a time or a function of the piece (`lambda pc: chomp[pc.word.index]`) for per-word exits.
`target` for `eaten` is a world point or a function of time (`ly.mouth(clawd)`).

## Costs (measured, RTX 5080, shared with other renders)

- **Render:** +0.13 s per final frame (1080p, 64 samples, motion blur): median 2.20 s with the lyrics vs 2.06 s
  without, paired over 24 frames of `_test_lyrics`. About 25 lyric objects are visible at a time (360 in the 30 s
  test, the rest hidden by keys).
- **Build:** about 2-3 s per scene (glyph meshes are cached; the stand costs ~0.2 s a shot: ray probes at three
  frames). `_test_lyrics` builds in 8 s, 5 of them the desk.
- Fonts: 0.8 MB. No bakes, no images.

## Fonts and licences (`blender/lib/pdoom/lyrics/fonts/`)

Bundled with the library, not in `assets/` (which is git-ignored), so every checkout builds the same letters.

| key | file | family | licence |
|---|---|---|---|
| `slab` | AlfaSlabOne-Regular.ttf | Alfa Slab One (JM Solé) | SIL OFL 1.1 (`OFL-AlfaSlabOne.txt`) |
| `sans`, `cond` | Archivo-Bold.ttf, Archivo-CondensedBold.ttf | Archivo (Omnibus-Type), copied from `library/sources/mexicat-pdoom-generative` | SIL OFL 1.1 (`OFL-Archivo.txt`) |
| `type` | CourierPrime-Bold.ttf | Courier Prime (Quote-Unquote Apps) | SIL OFL 1.1 (`OFL-CourierPrime.txt`) |
| `mono` | IBMPlexMono-Medium.ttf | IBM Plex Mono (IBM), from the same library source | SIL OFL 1.1 (`OFL-IBMPlexMono.txt`) |
| `marker` | PermanentMarker-Regular.ttf | Permanent Marker (Font Diner) | Apache 2.0 (`LICENSE-PermanentMarker.txt`) |
| `stencil` | StardosStencil-Bold.ttf | Stardos Stencil (Vernon Adams) | SIL OFL 1.1 (`OFL-StardosStencil.txt`) |
| `line`, `roman`, `script`, `cursive` | hershey-*.jhf | Hershey single-stroke fonts (Dr. A. V. Hershey, U.S. National Bureau of Standards; data format by James Hurt), from github.com/kamalmostafa/hershey-fonts | free use with the acknowledgement (`LICENSE-Hershey.txt`) |

Outline glyphs are measured and meshed in a tiny temporary scene (`ly.work`, removed by `finish()`), so the real
scene's depsgraph is never re-evaluated per letter.

## Limits and gotchas

- **Depth of field is the hard constraint.** Readable text must sit near the focus plane. In tight tele shots at
  desk level (hero_low, 85 mm close-ups) the only sharp place is where the subject is, so the stand either floats
  in front of the subject's legs (soft, 10-20 px) or finds a clear spot to the side; the build says which shots
  were compromised. Those lines want a staged idea: text on a prop at the subject's depth, the laptop, or a lens
  pane with `rack()`.
- The stand treats the puppets at their baked poses only after `chars.finish()`; characters' faces (Clawd's face,
  the researcher's eyes) are kept clear. Objects that `fx.vis()` hides only in renders still block its rays.
- World-placed rows (`At`, `On`) are seen by every camera until `t_end` (default `t_exit` + 0.75): end them on a
  cut if the next shot shouldn't see them.
- A line that straddles a scene cut appears in both scenes (the second shows the earlier words already up).
- `accent` words share the row's exit and layout; the stand is sized when the first line of a shot is placed
  ('auto' lines added after `default()` reuse that size).
- Single-stroke fonts are ASCII only; curly quotes become straight ones. Wire and neon letters draw all strokes of
  a letter at once (not stroke after stroke).
- Fog writing needs EEVEE raytraced refraction (on by default); it reads best against something bright behind the
  glass. Letters read the right way round from the side their normal points to (for the snow globe, point it out
  at the camera even if the story says Sydney writes from inside).
- The stand's light is a real light: it lights what is near the stand. `StageSpec(light=0)` turns it off.
- Consecutive lines share the stand: the old row starts dropping off 0.25 s before the next line's first word, so
  for a few frames the last letters are still falling behind the shelf as the new ones pop up.

## Ideas per scene (for the scene agents)

| scene | lines | a staging idea |
|---|---|---|
| boot | 0 | `ly.accent(0, 'AGI', 'glow')` and the default row; or three light-up blocks along the USB cable (`d.cable.at(u)`) that light as each spark passes (A 3.677, G 4.06, I 4.355). |
| training | 1-4 | "Your circuits make me nervous" typed on the laptop behind Clawd; "that's no surprise" on sticky notes slapped on the lid; "sudden drop ... training loss" as bent wire along the bead maze (the word DROP riding the drop); "servant ... boss" rubber-stamped, or BOSS in brass under the paper crown. |
| eat | 5-8 | Line 5 as tiles Clawd eats one word per chomp (see `_test_lyrics`); P(DOOM): key the scene's own brass title letters to the syl times (`ly.skip(6, 'P(doom)')`) or accent them; FOOM in giant cardboard tumbling with the confetti; "Trapped in the Chinese room" stamped on the box. |
| room | 8-11 | Stamp the lyric on the answer cards the stamp slams (stamp style `on_object` the card); "shrooms" in neon that cycles hue with the mushrooms; "See through the shoggoth's lies" on a gold-leaf lens pane the camera racks through; "shinigami eyes" in red neon glinting with the glasses. |
| singularity | 12-15 | "stable training run" as blocks riding the wagons (`on_object` per wagon); "singularity's begun" letters sucked into the hole (`exit='eaten'`, target the hole centre); "optimizing, accelerating" on a typewriter strip spooling out behind the train; "atoms rearranging" blocks that pop in scrambled and settle. |
| sydney | 16-18 | "Sydney, please let me free" wiped in the fog she breathes on the globe glass (fog, `support='none'`, `on_object` the globe); "I'm upping my P(doom)" on the stand by the gauge; BASILISK on embossing tape round the USB cable. |
| moon | 18-21 | N-V-D-A lit green on the four cards as they power up (glow `glow_color='#76B900'`, syl times match); "The Omega Point's coming soon" in gold leaf reeled into the point (`exit='eaten'` to the point); the odometer IS "One E thirty": tiles flipping in its window. |
| safe | 21-23 | "That was safe enough, we reckoned" on embossing tape round the jar (tape `on_object` the jar) or stamped SAFE ENOUGH on its label; the stand for the tail of line 21. |
| backprop | 23-25 | "Forward MLP, backward, repeat" as blank blocks that spin round as sung (`preview='blank'`), M-L-P lit on the three layers; "von Neumann's obsolete" in brass stencils that shatter with the computer (`exit='sweep'`). |
| leftturn | 25-27 | One letter per domino (tiles standing, parented to the dominoes) so "SHARP LEFT TURN" reads as they fall; C-D-R in marker on the clipboard's checkboxes on their syl times. |
| paperclips | 27-31 | "Gato" on embossing tape on the collar; "paperclips fill the room" in bent paperclip wire swept away by the avalanche; PTO on a sticky note on the kill switch's beach chair (out of office); "nowhere left to go" on blocks buried by clips. |
| fuse | 31-33 | "we lit the fuse" letters lighting along the fuse as the spark passes (glow/neon, `reveal='light'` at the spark's times); "Orthogonality thesis blues" in blue neon over the blues club (`color='#4FA3FF'`). |
| disobey | 34-36 | "Just transformers all the way!" as blocks stacking into a tower beside the robot; "disobey" letters that pop in the wrong order and topple early; "Post-Chinchilla, super-dense" crushed under the press (scale keys on the pieces). |
| gpus | 36-39 | One word per popsicle fence (stencil on each fence, `exit='sweep'` when it's smashed); G-P-U lit in the LED city (screen text on the rooftops); R-L-H-F tiles on the thumbs-up lever, pushed askew letter by letter. |
| loom | 39-43 | P(DOOM) slammed in brass with the crack; "foretold by Loom" woven into the tapestry (marker/typed wipe on its surface); "masked pre-training days": tiles face down (masked) flipping as sung under the baby photo; "recursive self-upgrade" with each word bigger than the last. |
| ilya | 43-45 | "What did Ilya see?" chalk on the box lid, lit only by the peephole's light; "We'll never know" blocks that fade with the light (136.59); "Was it all for show?" in marquee neon on the proscenium, lighting with the footlights. |
| finale | 45 (tail) | Only the held "show?" (140.23-140.55): let the cut take it, or `ly.skip(45)`. The outro chant is not in the lyrics. |
| coda | - | No lyrics: nothing to do. |

## Files

`__init__.py` (the API, stands, building rows), `data.py` (words, letter times, rows, which scene shows what; pure
Python), `text.py` (fonts, glyph meshes, Hershey strokes, layout), `styles.py` (letter pieces and styles),
`mats.py` (materials and per-letter state), `core.py` (fast keys, pieces, reveals, exits), `place.py` (cameras,
projection and depth of field, the automatic stand, placements), `supports.py` (stand, cards, strips, slate,
panes, notes, tape, stamp, threads), `fonts/` (fonts and licences).

## Test renders

- `python tools/render.py sheet _test_lyrics --t 2.2,4.5,5.5,7.5,11.2,12.6,14.4,15.9,18.2,20.2,21.5,22.6,24.2,25.9,27.6,29.4 --cols 4`
  -> `out/wip/_test_lyrics/sheet_final.png` (64 samples, motion blur).
- `python tools/render.py sheet _test_lyrics_gallery --t 32.6,36.6,40.9,44.8,48.9,51.6,58.6,60.4,62.4,63.3,65.9,68.6,72.5,76.9 --cols 4`
  -> `out/wip/_test_lyrics_gallery/sheet_final.png`.
- `LYRICS_SCENE=training python tools/render.py sheet _test_lyrics_scene --from 5.8 --to 16.5 --n 12` (the real
  training scene with nothing but `ly.default('training')` added).
- `LYRICS_DEBUG=1` prints the stand's best candidates per shot.
