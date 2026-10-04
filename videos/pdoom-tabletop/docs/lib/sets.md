# sets: the desk world

`blender/lib/pdoom/sets/` builds the researcher's desk at night at real size (1 BU = 1 cm): the desk, the room, the
window and city, every prop the treatment names, the P(doom) gauge, three lighting moods and camera marks. Test scenes:
`blender/scenes/_test_desk.py` (every mark and event) and `_test_desk_moods.py` (the three moods).

## Quick start

```python
from pdoom import kit
from pdoom.sets import build_desk

def build():
    sc = kit.new_scene('boot')
    d = build_desk(kit.collection('desk'), mood='night')   # ~5 s, 317 objects, ~210k triangles
    cam, tgt = d.camera('hero_low')                        # a camera on a named mark (physical depth of field)
    d.move(cam, tgt, 'two_shot', 4.0)                      # key a dolly to another mark at 4.0 s
    d.lamp.click(2.056)                                    # dark until 2.056, then the bulb snaps on
    d.laptop.screen(3.0, glow=1.4, color='#FFB070')        # screen brighter and warmer from 3.0 s
    here = d.anchors['clawdSpot']                          # where Clawd stands (world cm)
    kit.post(bloom=0.25, bloom_threshold=1.2, vignette=0.22)
```

The gauge's whole song history (0 until 23.873, then 25, 50, 75, 100 and the crack at 125.686) is keyed by default,
so any scene that shows the gauge reads the right value without doing anything.

## Coordinates and layout

The desktop surface is **z = 0**. The desk spans x -80..80 and y -40..40. The front edge is y = -40, facing the
default camera; +y goes back towards the wall and window. The wall's inner face is at y = 42. The window opening spans
x -60..60 and z 10..112. The floor is at z = -74.

Top view (x right, y up the page):

```
 y=40  +--------------------------------------------------------------+   wall and window behind
       | drawers    pencils                        lamp base          |
       | (-63,18)   (-40,31)   laptop (-17,15)     (50,27)            |
       |                                   gauge (25,13)              |
       |          clip (-3,-4)   Clawd (8,-4)                         |
       | books (-45,-17)  notes (-22,-17)  researcher (-6,-12)        |
       |                  pen (-16,-27)      mug (29,-13)  kill (59,-15)
 y=-40 +--------------------------------------------------------------+   default camera side
      x=-80                                                         x=80
```

The front half of the desk between x -10 and 30 is left clear for scene toys (see the `open*` anchors). Hide props a
scene doesn't want with `d.<prop>.hide()`, or skip them with `build_desk(..., exclude={'books', 'pen'})`.

## `build_desk(coll=None, mood='night', *, parts=None, exclude=(), gauge_history=True, clawd_spot=None, researcher_spot=None)`

- `parts` / `exclude`: any of `room window city lamp laptop mug books pencils notes pen drawers killswitch clip cable
  gauge motes haze` (`ALL_PARTS`).
- `clawd_spot`, `researcher_spot`: move the characters' spots. The cable, anchors and marks follow.
- The objects go in sub-collections of `coll`: `desk.room`, `desk.city`, `desk.props`, `desk.lights`,
  `desk.atmos`, `desk.cams`. Exclude a whole group in the view layer if a scene doesn't need it.
- Also sets the scene's EEVEE depth-of-field and volume settings for centimetre scale (see Limits).

It returns a `Desk` with `.lamp .laptop .gauge .drawer .killswitch .cable .clip .mug .books .pencilcup .pencils
.notes .pen .room`, plus `.anchors`, `.facing`, `.marks`, `.colls`, `camera()`, `move()`, `mark()` and `lighting()`.

Every prop is a `Prop` with a `.root` Empty. You can move or key the root, and `.objects` lists everything under it.
`.visible(t_on, t_off)` shows the prop only between those times (keyed). `.hide()` hides it for the whole scene.

## The props

| Handle | What it is | API |
|---|---|---|
| `d.lamp` | Anglepoise-style enamel lamp with springs, cream shade interior, bulb and spot light (the warm key). | `click(t, on=True)` switches it on or off with a 2-frame filament snap and presses the base button. `flicker(t0, t1, depth=0.7, rate=12, seed=7, dropouts=0.25, end=1.0)` is a bad-contact flicker. `intensity(t, v, interp)` keys brightness 0..1. `aim(t, target, reach=34, height=40)` is IK: the shade points at `target`. `pose(t, shoulder=, elbow=, head=, yaw=)` takes degrees. Joints are the Empties `root, shoulder, elbow, head`; the light is `light`. `set_level(v)` sets it without keys. |
| `d.laptop` | 30 × 21 cm aluminium laptop: key caps, trackpad, hinged lid, emissive screen, and a cool area light over the screen. | `screen(t, glow=, color=, mix=)` keys the screen. `glow` 1 is normal, `color` tints the picture, `mix` blends image A (0) to image B (1). The fill light follows glow and colour. `set_image(img, 'A' or 'B')` takes a bpy image, a file path, or a built-in: `'code'`, `'loss'`, `'boot'`, `'black'`. Defaults: A = code, B = loss curve. `open(t, angle)` keys the lid (0 closed, 108 default). `screen_point(u, v)` gives a world point on the screen. |
| `d.gauge` | Brass dial (0-100, numerals, red zone 75-100, "P(doom)"), red needle with counterweight, walnut plinth, domed glass. | `set(t, value, freq=3, zeta=0.3)` swings the needle hard, overshoots and settles (keys every frame). `crack(t)`: radial and ring cracks spread from the 100 end in about 0.3 s, with a jolt. `jolt(t, amp_deg)` knocks the instrument. `tremble(t0, t1, amp)` makes the needle quiver. `value_at(t)`, `clear(initial=None)`, `history()`, `front(dist)`, `center()`. Events re-key from the whole list, so call order doesn't matter. Module constants: `DOOMS`, `CRACK_T`, `dial_angle(v)`. |
| `d.drawer` | Sage steel card cabinet, 22 × 26 × 18 cm, three real drawers (hollow trays with brass pulls and label cards). | `open(t0, t1, amount=1, k=0)` slides drawer k (0 = top) out by up to 17 cm. `burst(t, amount=1, k=0)` shoots it open in 2 frames and bounces off the stop. `inside(k, amount)` is the world point on the tray floor; `inside_size(k)` is its interior (20.3 × 23.9 × 4.5 cm). `drawers[k]` are the Empties. |
| `d.killswitch` | Yellow enamel box, 8.6 cm, with a hazard-stripe plate, a red mushroom e-stop and a cable off the desk edge. | `press(t, latch=True, depth=0.55)`. `button` is the Empty. |
| `d.cable` | White USB-C cable lying on the desk from the laptop's right port to Clawd's back-left port (`clawdPort`), with plugs. | `at(u)` and `tangent(u)` give the point and direction by arc length (u 0 = laptop end, 1 = Clawd). `pts`, `length` (30.5 cm). Use it for sparks running along the cable. |
| `d.clip` | The single paperclip by the laptop. It is the fx library's hero clip (`fx.clips.clip`, lod 0), so it matches the avalanche. If `pdoom.fx.clips` is missing it falls back to its own 3.1 cm mesh (`d.clip.source` says which). | `root`, `mesh`. |
| `d.mug` | Glazed stoneware mug, 8.5 × 9.5 cm: slate-blue outside, cream inside, bare clay foot, coffee with crema. | `top` (local), `radius`. The `mugTop` anchor is the rim centre. |
| `d.books` | Four cloth hardbacks stacked (spines face -y), pages with a paper edge and gilt bands. | `books[i]` are Props. `top` is the stack height (11.7 cm). |
| `d.pencilcup`, `d.pencils` | Brushed dark steel cup with six hexagonal pencils (eraser, ferrule, painted body, sharpened cone, lead). Some point up, some down. | Each pencil is a Prop: eat them one by one with `.visible(None, t)`. |
| `d.notes` | Sticky-note pad (yellow, 7.6 cm) with a curling top sheet, two loose notes, and one mint note on the laptop bezel. | `pad`, `loose` (list of objects). |
| `d.pen` | Black click ballpoint with a chrome clip. | Prop. |
| `d.room` | Desk top and legs, wall and skirting, window frame, sill and glass, floor, city, the window light (`moon`), the overhead fill (`bounce`), haze and motes. | `moon`, `bounce` (area lights), `haze_density` (socket), `city_sockets`, `sky_nodes`, `motes`, `haze`, `glass`. |

To key a node socket or a light setting yourself, use `pdoom.sets.geo.keyp(owner, prop, t, value, interp=)`.
`kit.key` only sets interpolation on ID-level paths; `keyp` also works on sockets and embedded data.

## Anchors (`d.anchors`, world cm)

| Anchor | Value | Anchor | Value |
|---|---|---|---|
| `center` | (0, 0, 0) | `clawdSpot` | (8, -4, 0) |
| `clawdPort` | (5.4, -1.7, 2.2) | `researcherSpot` | (-6, -12, 0) |
| `lampPool` | (6, -4, 0) | `lampHead` | (19.8, 5.7, 34.1) |
| `lampBase` | (50, 27, 0) | `clipSpot` | (-3, -4, 0) |
| `laptopFront` | (-16.1, 1.5, 0) | `laptopKeys` | (-17.3, 18.9, 1.6) |
| `laptopScreen` | (-17.9, 28.0, 11.5) | `laptopTop` | (-18.1, 31.4, 21.9) |
| `cablePort` | (-1.8, 17.6, 0.75) | `mugTop` | (29, -13, 9.5) |
| `mugFront` | (29, -21, 0) | `gaugeCenter` | (25.2, 13.6, 8.6) |
| `gaugeFace` | (24.9, 12.7, 8.7) | `gaugeFront` | (22.5, 4.4, 0) |
| `drawerFront` | (-60.8, -2.9, 0) | `drawerFace` | (-61.6, 4.8, 15.3) |
| `drawerInside` | (-61.2, 0.7, 12.7) | `drawerTop` | (-63, 18, 18.3) |
| `killswitchTop` | (59, -15, 9.1) | `killswitchSide` | (48.6, -14.4, 0) |
| `booksTop` | (-45, -17, 11.7) | `pencilCup` | (-40, 31, 10.7) |
| `notesPad` | (-22, -17, 0.9) | `penSpot` | (-16, -27, 0) |
| `openCenter` | (6, -24, 0) | `openLeft` | (-24, -30, 0) |
| `openRight` | (28, -28, 0) | `windowCenter` | (0, 51, 61) |
| `windowSill` | (0, 40.5, 10.4) | `deskFront` | (0, -40, 0) |
| `deskFrontLeft` | (-80, -40, 0) | `deskFrontRight` | (80, -40, 0) |
| `deskBackLeft` | (-80, 40, 0) | `deskBackRight` | (80, 40, 0) |

The spots with a "Front" or "Side" name are on the desk where a character can stand. `killswitchSide` is where the
beach chair goes. `drawerInside` is on the top drawer's tray floor when it is fully open.

`d.facing` gives yaw in radians: 0 means local -y faces the camera side. `clawdSpot` is 0. `researcherSpot` is 119.7°,
which turns him towards Clawd.

## Marks (`d.marks`)

`d.camera(name)` makes a camera and target on a mark. `d.move(cam, tgt, name, t)` keys a camera onto a mark.
`d.mark(name, loc, target, lens, fstop)` adds a mark or overrides one. The f-numbers below are real-lens values;
the camera gets `phys_fstop()` of them (see Limits).

| Mark | Lens | f/ | Framing |
|---|---|---|---|
| `wide` | 35 | 8 | The whole desk, window and city (from 1.5 m, at eye height). |
| `establish` | 40 | 5.6 | Low three-quarter: laptop, researcher, Clawd, gauge, lamp, window. |
| `hero_low` | 65 | 8 | Desk level on Clawd; the gauge soft behind. |
| `over_researcher` | 55 | 8 | Over the researcher's shoulder onto Clawd. |
| `over_clawd` | 50 | 8 | Reverse: from beside Clawd up to the researcher's face. |
| `two_shot` | 50 | 8 | Researcher and Clawd with the laptop behind. |
| `gauge` | 70 | 11 | Insert: the whole dial and its feet. |
| `gauge_wide` | 45 | 11 | Clawd in front, the gauge behind. |
| `macro` | 100 | 16 | The paperclip, 10 cm away. |
| `laptop` | 45 | 8 | Over the keyboard onto the screen. |
| `lamp` | 32 | 5.6 | From desk level up at the lamp head against the window. |
| `drawer` | 50 | 8 | The drawer unit's front. |
| `killswitch` | 60 | 8 | The kill switch. |
| `mug` | 60 | 8 | The mug, with the gauge and city bokeh behind. |
| `books`, `pencils`, `notes` | 50 | 8 | Those props. |
| `cable` | 50 | 8 | Along the cable to Clawd's port. |
| `window` | 50 | 2.8 | Low, focused on the sill: city bokeh. |
| `top` | 32 | 11 | Straight down on the desk. |

## Lighting (`d.lighting(mood)` or `build_desk(mood=)`)

Presets set static values. Scenes key changes on top, for example `lamp.click`, `lamp.flicker`, `laptop.screen`, or
their own `geo.keyp` on `d.room.moon.data.energy`.

- **night**: warm lamp key (#FFB24A spot, 260 kW at about 38 cm). Cool laptop fill (4.5 kW area light over the
  screen). Blue window light from outside (90 kW; transmission 0 so it isn't seen through the glass). A dim neutral
  overhead fill (130 kW, diffuse only). City lights on. A faint haze (density 0.0006/cm) and dust motes in the lamp
  cone.
- **lamp_off**: lamp dark, laptop brighter, the window's cool light the main source, low fill. Cold and lonely.
- **dawn**: lamp off, the window a peach-to-blue sky with strong warm light through it, city lights at 12 %, a
  brighter world.

The world is the `office_night` HDRI at low strength, for reflections only. Camera rays see a plain dark colour.

## Assets (`python tools/fetch_assets.py`, 113 MB in `assets/`, git-ignored)

Everything is CC0 (public domain). Poly Haven lacks paper, cardboard, felt and brushed metal, so those come from
ambientCG, which is also CC0. `assets/README.md` and `assets/manifest.json` list them. Load them with
`kit.asset('tex', key, 'diff.jpg')` or through `sets.materials.tex_mat(name, key, tile_cm, ...)`, which maps a tile
at its real size in cm.

| Key | Source | Resolution | Used for |
|---|---|---|---|
| `tex/desk_wood` | Poly Haven `dark_wood` | 4k | The desktop, lacquered, 120 cm tile. |
| `tex/wall_plaster` | Poly Haven `painted_plaster_wall` | 2k | The wall. |
| `tex/floor_wood` | Poly Haven `wood_floor` | 2k | The floor. |
| `tex/linen` | Poly Haven `rough_linen` | 2k | Book cloth, lab coat. |
| `tex/paper` | ambientCG `Paper001` | 2K | Sticky notes, cards, the paper moon. |
| `tex/cardboard` | ambientCG `Cardboard004` | 2K | The Chinese-room box. |
| `tex/felt` | ambientCG `Fabric034` | 2K | Felt pads. |
| `tex/brushed_metal` | ambientCG `Metal011` | 2K | Laptop, pencil cup, ferrules. |
| `hdri/office_night.hdr` | Poly Haven `unfinished_office_night` | 2k | Reflections. |
| `hdri/city_night.hdr` | Poly Haven `shanghai_bund` | 2k | Spare night-city HDRI (not used by the desk). |

If `assets/` is missing, texture materials fall back to flat colours and print a warning, so builds never fail.

## Costs

- **Build:** about 5 s (the laptop screen pictures are generated and packed into the .blend).
- **Render, EEVEE, 1080p, 64 samples, motion blur:** about 1 s per frame for the full desk after the first
  (shader-compiling) frame, which takes about 2 s. Iteration renders at `--samples 16 --nomb --scale 50` take about
  0.3 s.
- **Scene size:** 317 objects, about 210k triangles, 24 images. The city is all emissive: no lights, almost free.
  The motes are geometry nodes (1400 points), a pure function of time with no bake.

## Limits and gotchas

- **Depth of field must use `phys_fstop()`.** EEVEE 5.2 ignores `unit_settings.scale_length` for depth of field. At
  1 BU = 1 cm, an `aperture_fstop` of 2.8 blurs about 100 times less than a real f/2.8 lens. I measured it: far points
  at 50 mm, f/2, focus 30 cm blurred 12 px when set naively, and 114 px (theory about 120) with f-stop × 0.01.
  `d.camera()` and `d.move()` apply this. Use `pdoom.sets.phys_fstop(2.8)` for any camera you make yourself. At real
  f-numbers the depth of field is very thin, so use f/8-f/16 to keep a character sharp, as a real tabletop shoot
  would.
- **Light power:** Blender's light falloff also ignores the unit scale. Wattages are about 10^4-10^5 W at desk
  distances (the lamp is 260 kW at 38 cm), not "a few watts".
- `build_desk` sets `eevee.bokeh_max_size = 320`, `use_volume_custom_range` (1 to 450 cm) and a few GI distances.
  A scene that adds volumes further than 4.5 m from the camera must widen `volumetric_end`.
- The drawer unit sits outside the lamp's pool, lit by the fill and the window. For the `paperclips` showcase, re-aim
  the lamp (`d.lamp.aim(t, d.anchors['drawerInside'])`) or add a light.
- The haze is a box over the desk (x ±85, y ±45, z 0-70). It isn't there for shots of the room beyond it.
- The dust motes fill a box around the lamp's default cone and fade outside it. If a scene moves the lamp a lot, the
  motes stay where the cone was: hide them (`d.room.motes.hide_render = True`) or rebuild with `parts`.
- The lamp's IK (`aim`) keeps the elbow up and assumes the target is reachable (arm reach about 65 cm).
- The gauge's needle keys come from its event list. `tremble` keys must not overlap a `set` swing.
- `lighting()` rebuilds the world node tree. To animate between moods inside a scene, key the individual values
  (see `_test_desk_moods.py`, `key_state`).
- The screen pictures are generated images (code editor, loss curve with a sudden drop, boot, black). For anything
  else, pass your own image or path to `set_image`.
- No in-world text except the gauge dial. The book spines, drawer cards and laptop are blank on purpose.

## Test renders

- `python tools/render.py sheet _test_desk --t 3.0,13,19,24.1,31,37,49,51,55,69,73,129 --cols 3` gives the marks at
  full quality: `out/wip/_test_desk/sheet_final.png`.
- `python tools/render.py strip _test_desk --from 23.8 --to 24.75` shows every frame of DOOM 1's needle swing.
- `python tools/render.py sheet _test_desk_moods --t 2,6,10,14,18,22 --cols 3` shows night, lamp_off and dawn.
