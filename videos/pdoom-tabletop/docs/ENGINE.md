# Engine guide (Blender pipeline)

Read this whole page before writing code. The design is `docs/TREATMENT.md`.

This is the brief the scene agents worked from while the video was made (one agent per scene, a lead agent owning
the shared libraries). Paths are relative to this video's folder (`videos/pdoom-tabletop/`).

**Blender** 5.2.2 LTS (on Windows the tools look for `C:/Program Files/Blender Foundation/Blender 5.2/blender.exe`; set
`BLENDER` to override), always run in the background (`-b --factory-startup`) by the tools below.

## How it works

- A scene is one Python file `blender/scenes/<id>.py` with a `build()` function. It builds everything from scratch in
  an empty file (`kit.new_scene(id)`), keys all animation by **song time**, bakes its simulations, and the tool saves it
  as `out/blend/<id>.blend`.
- **Every frame is a pure function of song time.** Global frame f shows song time f / 24; each scene's .blend spans
  exactly its window's global frames (`timeline.py`). Keyframes, drivers of the frame number, and baked caches only:
  no `random` without a fixed seed, no handlers that keep state.
- Frames render in parallel background processes from the saved .blend; `tools/render.py assemble` joins every scene's
  frames with the song and the lyric subtitles (ffmpeg, NVENC).

## Commands (run from `videos/pdoom-tabletop/` with the system `python`)

```bash
python tools/render.py sheet  <id> --from 38.4 --to 42 --n 12 --cols 4        # build + a contact sheet (50 % size)
python tools/render.py sheet  <id> --t 23.873,23.95,24.1 --cols 3            # exact times (hits)
python tools/render.py stills <id> --t 25.6 [--scale 100]                    # full-size PNGs -> out/wip/<id>/stills
python tools/render.py strip  <id> --from 10.1 --to 10.7                      # every frame of a moment
python tools/render.py build  <id>                                            # build + save only
python tools/render.py range  <id> --workers 3                                # all frames -> out/frames/<id>/
python tools/render.py assemble                                               # the whole video
```

Add `--reuse` to render from the saved .blend without rebuilding, `--samples 16 --nomb` for fast looks. **LOOK at every
sheet with the Read tool.** Test scenes are named `_<name>.py` and pass `window=(t0, t1)` to `kit.new_scene`.

## The library (`blender/lib/pdoom/`)

- `timing.py`: `FPS` (24), `t2f`, `line(q)`, `word(line, w)`, `syl(word, i)`, `beats()`, `downbeats()`, `bar(k)`,
  `beat_after(t, n)`, `beats_between`, `kicks(t0, t1)`, `snares`, `envelope(name, t)`, `smooth`, `pulse`.
- `timeline.py`: `EDIT`, `window(id)`, `frames(id)`.
- `kit.py`: `new_scene`, `collection`, `key(obj, path, t, value, interp=, easing=)`, `keys`, `fcurves`, `set_interp`,
  `cycles_modifier`, `visible(obj, t_on, t_off)`, `mat(...)`, `emission_mat`, `box`/`cylinder`/`sphere`/`empty`,
  `parent`, `camera(...)` (+ Empty target, DOF), `cut_to(cam, t)` (camera switches by marker), `shake`, `area`/`spot`/
  `point`/`sun`, `world_color`/`world_hdri`, `post(bloom=, vignette=)`, `bake_all`, `cache_dir`, `PAL`, `srgb`.
- `chars/`, `sets/`, `fx/`: the shared characters, the desk world and the simulation kit (see their docs in
  `docs/lib/`).

## Rules

1. **World scale: 1 BU = 1 cm.** `new_scene` sets unit scale 0.01 and gravity 981 cm/s². Clawd is 8 cm long, the
   researcher 12 cm tall, a paperclip 3 cm, the desk 160 × 80 cm. Two EEVEE quirks at this scale (measured):
   - **Light falloff ignores the unit scale**, so lights need 10^4-10^5 W: the desk lamp key is 260 kW at 38 cm.
     Copy the desk's lighting presets (`sets.desk.lighting`) or tune by eye from there.
   - **DOF ignores the unit scale**: `kit.camera(fstop=2.8)` already multiplies by 0.01 so f/2.8 looks like a real
     f/2.8 macro lens; for a camera you make yourself use `sets.phys_fstop(f)`.
   `new_scene` also sets the volume range to 1-450 cm and a large bokeh size. For keying node sockets and light
   data (colour, energy) use `sets.geo.keyp`.
2. **Stop-motion feel:** character animation on twos: key poses on even frames with CONSTANT interpolation (the chars
   library has helpers). Cameras, lights, simulations and effects are smooth at 24 fps.
3. **Hits land exactly.** Key by song time from `timing` (words, beats, kicks), not by guessed frame numbers.
4. **Simulations are baked in build()** (rigid bodies, cloth, particles: point caches; Mantaflow: `kit.cache_dir`).
   A render worker must never simulate.
5. **Blender 5.2 API traps:** no `action.fcurves` (use `kit.fcurves`); engine `BLENDER_EEVEE`; compositor via
   `scene.compositing_node_group`; `CompositorNodeMixRGB` is gone (use `ShaderNodeMix`, `data_type='RGBA'`); many
   node settings are input sockets now (set by socket name); geometry-node socket identifiers changed in 5.2 (use
   names); the cell-fracture add-on isn't bundled (use `fx.fracture`). Check signatures with the Blender MCP's
   `search_api_docs` / `get_python_api_docs` tools, or grep the RST docs bundled with that MCP server. Don't guess.
6. **Budget:** a final frame (64 samples, motion blur, 1080p) should render in about 1-5 s. Heavy volumetrics or
   100k instances are fine for a shot or two. Keep baked caches under a few GB per scene.
7. **Look at your frames.** Sheets of every shot, first and last frames, hits, strips across motion. Iterate until it
   reads like a real tabletop shoot.
8. **Files:** only your own. Scene agents: `blender/scenes/<id>.py` and `blender/scenes/<id>_*.py`. Library agents:
   their folder under `blender/lib/pdoom/`, their `_test_*` scenes, their doc in `docs/lib/`.
9. **On-twos traps** (found in boot/training): a character that must change at a cut on an ODD frame still shows its
   old pose there (frames f and f+1 share one pose): key the change a quarter-frame early and switch that span to
   `timing(..., 'ones')`. Stills at FRACTIONAL frames show double images of characters (the shutter spans a twos
   key); check characters on integer frames. `boot_common.py` has reusable helpers (a motion-control camera with
   separate aim and focus targets, sparks along a path, ember bursts, flash lights).
10. **Simulation and node traps** (found by the fx agent; details in docs/lib/fx.md):
   - A rigid-body cache that starts before frame 0 renders garbage at the subframes motion blur uses:
     `fx.rigid.world()` clamps the pre-roll.
   - Bullet tunnels at this scale: clips need ~30 substeps and colliders should be thick. A body switched from
     animated to dynamic keeps its animated velocity; collision layers can be keyed mid-bake.
   - Geometry-node modifier inputs are `mod.properties.inputs.Socket_N.value` in 5.2 (`mod['Socket_N'] = x` raises).
     Object Info in RELATIVE mode carries the object's transform (fx `_nodes.Tree.object_geo` defaults to RELATIVE:
     pass ORIGINAL when the modified object isn't at the origin). Right after creating an object `matrix_world` is
     stale: use `matrix_basis`.
   - Mantaflow at gravity 981: liquid falls ~1.4x too fast (fx sets gravity weight 0.7); initial velocity caps at
     100; a GEOMETRY flow refills every frame it's on. EEVEE water renders clear only with the SLAB thickness model.
   - `kit.visible` keys viewport visibility too, which blocks bake operators: use `fx.vis()` for objects that take
     part in a bake.
   - Glass and water read dark in the dark room: give them something bright to reflect. A large area light next to
     a closed box can light its inside through the walls at this scale.
   - Under AgX, saturated emissive reds wash out to pink above strength ~3: keep red glows at 2 or below.
   - Reusable scene pieces: `scenes/disobey_robot.py` (the transformed robot: `Robot(coll, loc=, yaw=)`, poses,
     punch, stomp, eyes, reactor; `sparks(...)` streak bursts), `scenes/boot_common.py` (motion-control camera,
     sparks along a path, embers, flash lights, noise-only shake).
   - `Collection.hide_render` can't be keyframed in 5.2: key visibility per object. A Subdivision Surface modifier
     on a big object whose visibility is keyed can cost seconds per frame (it re-evaluates): apply it or drop it.
   - Walls made of separate adjoining boxes shade in vertical bands in EEVEE: build one closed mesh. Brick Texture's
     output is `Factor` (not `Fac`). `bmesh.ops.triangulate` can fill the hollow of a concave outline: build such
     shapes from quads between their curves.
   - Curve to Mesh no longer scales the profile by the curve radius in 5.2: feed its `Scale` input.
   - Clear water and thin glass that let a refracting character show through: `sydney_globe.clear_water()` and
     `shell_glass()` (EEVEE refracts one layer only; `fx.materials.water` can render black in the dark room).
   - `render.use_motion_blur` can't be keyed, but `render.motion_blur_shutter` can (shorten it for fast shots).
     Geometry-node instances need stable ids (Set ID = Index before any Delete) or motion blur pairs the wrong
     instances between steps (fx now does this). A big rigid-body avalanche renders far faster once baked into one
     instancer: see `to_instances()` in `scenes/paperclips_flood.py`.
   - Changing a value exactly at a cut with CONSTANT keys: key the old value 1.5 frames and the new one 0.5 frames
     before the cut frame (keys at cut +/- 0.5 leave the cut frame on the old value, and motion blur samples it).
   - Refraction in EEVEE: it drops the volumetric haze's glow behind a refracting surface (a dark disc: turn the
     haze off for that shot); a light inside or behind glass shows as a big white highlight on it (set the light's
     `transmission_factor` and `specular_factor` to 0); an object crossing a refracting surface traces black where
     they meet.
   - Scene dependencies: `finale` calls `scenes.ilya.build()` to continue ilya's camera, so rebuild finale whenever
     ilya changes; `leftturn` copies backprop's last domino (position, yaw, tap time, fall maths): keep them in
     step; `singularity` imports the snow globe from `scenes/sydney_globe.py` (rebuild it when that
     changes).
   - Always pass absolute paths to Blender (the tool now absolutizes `--out`). Sheet/still times snap to whole
     frames unless `--exact`.
11. **Machine:** one render command at a time per agent; `--samples 16 --nomb` and `--scale 50` while iterating. The
   tool runs Blender at below-normal priority.
12. **More traps found later** (2026-09-30):
   - **Visibility:** `kit.visible` and `fx.vis` key from the scene start, so a second call on the same object wipes the
     first: give each object one call covering all its windows (an off-only `vis` is on the request list).
   - **Smoke caches:** set the cache end frame before the start frame, or the bake runs from frame 250 (fixed in
     `fx.smoke`; 447 s became 57 s). Confetti needs one particle shape per size (fixed in fx).
   - **Colour:** set the AgX view transform by name; its enum list is empty in background mode.
   - **Glass:** area lights draw their shapes in refractive glass (lower transmission and specular factors); turn
     glass shadows off. Light linking works in EEVEE 5.2.
   - **Cost:** hide or pre-bake fur and live booleans (they re-evaluate on every motion-blur step). Per-frame times
     vary about 2× when 5-7 Blenders share the GPU: time a scene on a quiet GPU before judging it.
   - **Lyrics library traps** (from the revision-2 agents): rows size from the parent's scale at `t_show` (one came out
     720× too big); words that start in a scene's last frames never show and rows are clipped to the scene window;
     slam reveals start 4 frames early; per-letter lights can wash out nearby faces; stands ignore camera push-ins
     (stage the line on something sharp instead); probes treat instancers as solid (slow builds).

## No ghost renders (tools/procguard.py)

Renders must never outlive whoever started them. `tools/render.py` ties every Blender it starts to itself (a Windows
job object: when render.py ends or is killed, its Blenders die) and exits if its launcher (your shell) exits.
- **Always render through `tools/render.py`.** Never run `blender.exe` directly or through your own wrapper script.
- **Background renders:** use the Bash tool's `run_in_background`, never a trailing `&` inside a foreground command
  (that shell exits at once, so the render stops).
- **Pause flag:** while the file named by `RENDER_STOP_FILE` (default `G:/video-renders/STOP`, the original machine's
  render drive) exists, every render stops within ~2 s (Blender at its next frame) and new ones refuse to start. The lead uses it to pause everything; don't remove it yourself.
