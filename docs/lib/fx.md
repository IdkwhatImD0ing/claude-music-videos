# fx: simulations and effects

`blender/lib/pdoom/fx/` is the kit for the parts of the video that show off what Blender can do:
- thousands of rigid-body paperclips
- Voronoi fracture with cracks
- Mantaflow smoke, fire and water
- a domino run
- sparks, confetti and a burning fuse
- objects that break into cubes and reassemble

Every effect was tested at 1 BU = 1 cm in `blender/scenes/_test_fx_*.py`.

Everything is keyed by **song time** and seeded, and every simulation is **baked in `build()`**. Render workers
only read caches:
- Rigid bodies bake into the .blend.
- Mantaflow bakes to `out/cache/<scene>/<name>/`.
- Particles, seas, fields, cubes, cracks and haze are geometry nodes that compute each frame from song time, so
  there is nothing to bake.

Saved-and-reloaded .blends render identically to the build process (measured below).

## Quick start

```python
from pdoom import fx, kit
from pdoom.fx import clips, rigid, fracture, smoke, liquid, dominoes, particles, cubes, materials

def build():
    sc = kit.new_scene('sydney')
    d = build_desk(kit.collection('desk'))
    rigid.desk(d)                                   # desk top, drawers, props become colliders
    pieces = fracture.fracture(glass, 48, impact=front, swap_at=60.235)
    fracture.shatter(pieces, 60.235, impact=centre, speed=(25, 70))
    liquid.spill('globe.water', body=water, t0=60.235, box=((-36, -36, 0), (36, 36, 20)), res=144)
    fx.bake()                                       # LAST: rigid bodies, then every fluid domain
```

`fx.bake()` bakes every point cache (Bullet) and then every Mantaflow domain the kit made, in that order, so fluids
can collide with baked rigid bodies. Call it once, at the end of `build()`.

### The paperclips showcase on the desk (from `_test_fx_clips.py`)

```python
d = build_desk(kit.collection('desk'), mood='night')
rigid.world(substeps=30, iterations=12)
rigid.desk(d)
d.drawer.burst(t)                                   # the top drawer shoots open
out = d.drawer.root.matrix_world.to_quaternion() @ Vector((0, -1, 0))
src = d.drawer.inside(0, 1.0) + out * 3.8 + Vector((0, 0, 5.6))      # over the open tray
closed, size = d.drawer.inside(0, 0.0), d.drawer.inside_size(0)
fill_box = ((closed.x - size.x / 2 + 1.5, closed.y - size.y / 2 + 1.5, closed.z + 0.2),
            (closed.x + size.x / 2 - 1.5, closed.y + size.y / 2 - 1.5, closed.z + size.z - 0.8))
clips.avalanche('flood', count=8000, t0=t + 0.1, duration=3.0, source=(tuple(src), (18, 12)),
                direction=tuple(out * 0.75 + Vector((0, 0, 1))), speed=(40, 95), spread=15,
                friction=0.9, fill=350, fill_box=fill_box)
fx.bake()
```

The lamp can't reach the drawer unit (its arm reaches about 65 cm), so light the drawer yourself. The test uses a
600 kW warm spot 70 cm away.

## Scale notes (1 BU = 1 cm, gravity 981 cm/s²), all measured

**Light and optics**
- Light falloff and depth of field ignore the unit scale (see ENGINE.md and sets.md). Point lights riding on
  effects need 3-8 kW. Emission strengths are 6-15 for fire and sparks.

**Bullet (rigid bodies)**
- Bullet tunnels at this scale. A 1 cm cube dropped from 50 cm went through a 2 cm floor at the default 10
  substeps. Clips (0.16 cm collision boxes) need 30 substeps. Keep colliders thick. The desk's 0.15-0.3 cm drawer
  trays held at 30 substeps.
- A rigid-body cache that starts at a negative frame reads garbage at subframes, and motion blur samples subframes.
  `rigid.world()` clamps the pre-roll so the cache never starts before frame 0. So the `boot` scene (frame 0) gets
  no settling pre-roll.
- An animated (kinematic) body keeps its last animated velocity when it turns dynamic. The kit uses this to throw
  clips from a source, push the first domino and fling shards. Switches happen on whole frames.
- Collision layers can be keyed mid-bake. Parked clips wait in layer 19 and travel to the source without hitting
  anything.
- Parented, animated passive colliders work. The desk's drawer trays follow their keyed drawer Empty and push clips.

**Mantaflow**
- Liquid falls about 1.4× too fast with the scene's gravity. `liquid.spill` sets the domain's gravity weight to
  0.7, and a blob then falls 13 cm in 1/6 s, as in life.
- Gas buoyancy is right at weight 1: a hot plume rises about 13 cm/s.
- Initial velocities are capped at 100. `smoke.burst` grows its emitter while it emits, because the moving surface
  pushes the smoke. Without that, a FOOM stays a small puff.
- A GEOMETRY liquid flow keeps refilling its volume every frame it is on, and only fills on the domain's first
  frame. `spill` keys it on for the first two frames only.
- "Fractions" plus a floor obstacle deleted the water within 0.2 s, so `spill` leaves fractions off.

**EEVEE**
- Water must use the SLAB thickness model. SPHERE (with or without a thickness), probe-only and BLENDED refraction
  all render water black in the dark room. `materials.water()` and `materials.glass()` do this.

**Blender 5.2 and pipeline gotchas**
- Geometry-node modifier inputs moved to `mod.properties.inputs.<Socket_N>.value`. The old `mod['Socket_N'] = x`
  raises an error. Use `fx._nodes.set_input` and `key_input`.
- Object Info in RELATIVE mode carries the object's transform. A proto parked at z = -10000 put every instance
  100 m underground. The kit instances with ORIGINAL.
- A new object's `matrix_world` stays stale until the depsgraph updates. Use `matrix_basis` right after creating
  objects.
- Blender resolves relative output paths from the drive root (`C:\out\...`). Pass absolute `--out` paths to
  `tools/render.py`.

## Paperclips (`clips`)

A Gem clip is 3.3 × 0.85 cm, made of 0.9 mm wire bent into three U-turns (two nested loops). The mesh is a tube
swept along that centreline in the XY plane, long axis X.

| LOD | Tube sides × segments per bend | Use |
|---|---|---|
| 0 | 12 × 20 | Hero clip, macro close-ups. `sets` uses it for the desk's clip. |
| 1 | 6 × 9 | Rigid bodies, piles |
| 2 | 4 × 5 | Seas, pours, the clip Earth |
| 3 | 3 × 3 | Fields of millions |

`clips.material(coloured=0)` is brushed steel. Roughness is streaked along the wire (UV u) and varies per clip,
with a faint warm or cool tint. `coloured=0.05` makes 5 % of clips vinyl-coated (red, blue, yellow, green).

### `clip(name, loc, *, rz=0, rot=None, lod=0)`
One clip lying flat on `loc` (rz in degrees), or with a full Euler `rot`.

### `avalanche(name, *, count, t0, duration=1.5, source, direction, speed=(80, 140), spread=18, spin=12, profile='flood', fill=0, fill_box=None, preroll=1.0, lod=1, mass=0.002, friction=0.45, substeps=30)`: the showcase

`count` real Bullet rigid bodies pour out of `source = (centre, (width, height))`, facing `direction`, from `t0`.
Each is its own object with a BOX collision shape 3.3 × 0.85 × 0.16 cm.

- Clips leave the mouth at `speed` cm/s inside a cone of `spread` degrees, tumbling at about `spin` rad/s.
- `profile`: `'flood'` (a burst, then a steady pour), `'burst'`, `'steady'`, `'swell'`, or `f(x) -> weight`.
- Each clip waits parked in collision layer 19, jumps behind the mouth, slides out over 2 frames at its launch
  velocity, then turns dynamic in layer 0.
- The mouth passes at most one clip per 3.6 × 1 × 1 cm cell per frame. Any excess carries over to later frames,
  and the log says so.
- `fill` clips lie in `fill_box` at the first frame. They drop and settle during a `preroll` before it.
- `friction=0.9` gives steeper, more clip-like heaps than 0.45.
- Returns `{'objects', 'emitted', 'filled', 'collection', 'release_frames'}`.

| Measured | Bodies | Bake | .blend | Render |
|---|---|---|---|---|
| Stand-in cabinet (30 substeps, 7 s window) | 10,618 | 313 s | 139 MB | 1.3 s/frame at 50 %, 16 samples |
| On the desk world (`_test_fx_clips`, 93 desk colliders, 7 s + 1 s pre-roll) | 8,444 | 218-227 s | 119 MB | **4.7 s/frame at 1080p, 64 samples, motion blur** |

In a tight bin, Bullet cost was:
- 5,000 BOX clips: 0.48 s/frame at 10 substeps
- 10,000 BOX clips: 1.6 s/frame
- CONVEX_HULL: 6× slower than BOX, so it isn't used for clips

Budget about 1.2-1.9 s of bake per frame for 8-10k clips at 30 substeps; a 12 s window takes 6-10 minutes. The
cache costs about 12 KB per clip-second in the .blend.

### `pile(name, *, center, radius=10, height=4, count=None, lod=1, core=True, shape=1.6)`
A static heap. Instances hug a `z = h(1 - (r/R)^shape)` mound, tilted with its slope, over a dark steel core.
Nothing is simulated, and it builds in under 1 s.

### `sea(name, *, area, base=0, depth=30, level=[(t, h)...], density=0.9, band=1.6, drop=3, settle=0.35, origin=None, slope=0, exclude=(), lod=2)`
A rising flood of clips, built from instances:
- Clips fill `area` up to the keyed `level` and drop into place over `settle` s as it passes them. A lagged copy of
  the level (the `Lag` input) tells falling clips from resting ones.
- `origin` and `slope` make a mound that spreads from a source.
- `exclude` keeps props' footprints clear.
- Only a `band` under the surface is instanced, about 20-40k instances on a desk.
- Use it for "clips up to the lamp", the fuse's sea and the finale's desk.

### `field(name, *, surface, density=0.3, scale=1, layers=1, lod=3)`
Clips scattered on any mesh by geometry nodes. `density` is clips per cm² per layer at scale 1. Use `scale` > 1
in far shots. Measured: 4 million clips (20 × 20 m, 2 layers, lod 3) render at 1080p/64 samples in **25.6 s**,
fine for a shot or two. The cost scales linearly.

### `pour(name, *, source, t0, t1, rate=400, direction, speed, scale=1, lod=2, floor=0)`
A stateless stream of tumbling clips that land flat and stay, for the clips pouring from the house's windows.
Clips don't pile, so put a `sea()` under it.

### `ball(name, *, center, radius=30, scale=1, layers=3, density=1.0, lod=2, progress=[(t, 0..1)], grain=0.15, core_mat=None)`
The paperclip Earth: clips cover a sphere over a dark core. `progress` keys the conversion in growing noise
patches. Give the core an Earth material (`core_mat`) for "the Earth turning into clips".

## Rigid-body plumbing (`rigid`)

- `world(substeps=20, iterations=12, preroll=0)`: one world per scene. Later calls only raise the settings.
- `desk(d)`: makes `build_desk` solid. The desk top and drawer panels become boxes, the trays and fronts follow
  their drawers, and every prop mesh over 2 cm becomes a convex hull that follows its prop's keys.
- `passive(obj, shape='BOX'|'CONVEX_HULL'|'MESH', animated=False)`, `active(obj, mass, shape)`. Masses are
  relative: a clip 0.002, a domino 0.02, glass by volume (0.0025/cm³), a light prop 0.05-0.25.
- `release(obj, t)`: held by its keys until t, then free, keeping its velocity.
- `launch(obj, t, pos, vel, spin=, rot=)`: the park-and-throw emitter.
- `blast(loc, t, strength, radius, dur)`: a keyed force field.
- `settle(objs, seconds)`: a throwaway bake that makes resting poses the start poses.
- `bake(label)`: bakes everything and logs the time.

## Fracture (`fracture`)

The cell-fracture add-on isn't bundled, so the kit does it in bmesh:
- Each piece is the source clipped by the perpendicular-bisector planes to its 26 nearest seeds.
- Every cut is capped by a triangle fill that handles holes, so hollow walls get annulus caps.
- Caps are tagged (`fx_cap`) and normals recalculated. Pieces are closed and convex, so CONVEX_HULL collision fits.

The functions:
- `fracture(obj, pieces=40, *, seed, impact=None, cluster=0.5, mode='auto', inner=None, gap=0, swap_at=None)`:
  - Modifiers are applied first, so give a jar a Solidify.
  - `mode`: `'surface'` seeds on the surface (thin glass), `'volume'` seeds inside (solids), `'auto'` picks one.
  - `impact` makes pieces cluster smaller there.
  - `inner` is the fracture-face material (`materials.ceramic_break()`, `materials.glass()`).
  - The original shows until `swap_at` and the pieces after it, because coplanar internal faces would show in glass.
  - Speed: 48-60 pieces of a 64-segment glass globe or jar in 0.2-0.7 s.
- `crack(pieces, t, *, origin, speed=60, width=0.009, reach=None)`: hairline crack tubes grow over the still-intact
  object along the real fracture seams, from `origin` at `speed` cm/s. The later `shatter()` breaks exactly along
  them. Keep the original visible (`swap_at` = the shatter time) and hide the lines then:
  `fx.vis(cracks, t, t_shatter)`. Use it for the crack up the jar and the gauge glass.
- `shatter(pieces, t, *, impact=None, speed=(20, 80), spin=10, follow=None, falloff=0, direction=None, mass_density=0.0025)`:
  the pieces are held until t, then fly apart as rigid bodies away from `impact`. With `follow=obj` they ride a
  keyed object until t and inherit its velocity.
- `topple(obj, t0, t_hit, *, direction=(0, -1, 0), floor=0)`: keys a box-like object tipping over its bottom edge,
  falling and landing flat exactly at `t_hit`. It returns the contact point. Use it for the vacuum-tube computer:
  `hit = topple(model, 77.3, 77.72)`, then `shatter(pieces, 77.72, follow=model, impact=hit, speed=(40, 110))`.

## Smoke and fire (`smoke`, Mantaflow gas)

| Recipe | What | Measured bake / cache | Render |
|---|---|---|---|
| `burst(name, *, center, t0, radius=6, emit=0.2, size=(70, 70, 60), res=112, grow=0.25, density=1.5, dissolve=2.5)` | The FOOM: the cloud engulfs a Clawd-sized object in about 0.2 s, then billows up and thins | 10.5 s / 80 MB (3.5 s) | 1.6 s/frame at 1080p, 64 samples |
| `burst(..., fire=True)` | A fireball: flash, rolling flames, then a smoke column | 19.3 s / 110 MB | Use `volume_quality('4')` |
| `trail(name, *, emitter, t0, t1, box, res=128, fire=False)` | A smoke trail behind a keyed object (the rocket), subframed so it stays continuous | 13.2 s / 60 MB (res 112) | |
| `haze(name, *, box, density=0.03, scale=10, drift, contrast=3)` | Procedural drifting haze for a club or a light shaft | None | About 2 s for the first frame, then fast |

Also available:
- `volume_quality(tile='4')`: finer EEVEE volumes for fire. The default 8 px froxels step visibly in flames.
- Lower level: `domain(name, box, t0, t1, res, kind)`, `flow(obj, kind, t_on, t_off, ...)`, `collider(obj)`,
  `material(...)`, `bake(dom)`, `bake_all()`.

## Liquid (`liquid`, Mantaflow FLIP)

`spill(name, *, body, t0, box, res=128, burst=0, obstacles=(), floor=0.0, viscosity=0.025, ...)`
- `body` is a closed mesh, the water's shape at t0 (the globe's water). It shows as still water until t0 and turns
  into liquid then.
- The domain floor is sunk 3 cells under `floor` (the desk top) and filled by a hidden obstacle, so the water rests
  on the desk. A guard modifier hides the domain's placeholder box on frames with no liquid.

Measured on the 776 cm³ globe, res 144 in a 72 cm box, 3 s:

| viscosity | Look | Bake | Cache |
|---|---|---|---|
| 0 | Sprays into a thin film of droplets that runs to the domain walls | 70-114 s | 111-680 MB |
| **0.025 (default)** | Slumps out of the broken globe into one coherent puddle about 30 cm across | **415 s** | 151 MB |
| 0.08 | Slow and gloopy | 365 s | 117 MB |
| 0.6 and up | Jelly: the ball of water holds its shape | 333 s | 90 MB |

`still(name, obj)` puts the water material on a mesh.

## Dominoes (`dominoes`)

- `run(name, *, points, t0, spacing=2.3, size=(2.4, 0.75, 4.8), radius=3, turn_spacing=0.8, push_deg=14)`:
  lacquered toy dominoes stand along a polyline whose corners are rounded to `radius` cm (the sharp left turn),
  spaced tighter in turns. They start asleep, so they stand dead still until hit. At t0 the first one is tipped and
  released.
- `measure(r)`: after a bake, the song time each domino passes 60°, interpolated between frames.
- `land(r, index, t)`: retimes the push so domino `index` (-1 is the last) lands at t. It bakes, measures, shifts
  by whole frames and repeats.

Measured: 47 dominoes over 107 cm with a 90° left turn. All fell, at 39 dominoes per second (spacing 2.3), which
is about 18 per beat at 132 BPM. Asked for the last one to land at 4.000 s, it landed at 3.989 s. The bake takes
0.2-0.3 s. To put hits on beats, split the run into segments or land one accent domino per beat.

## Particles (`particles`), stateless

Python draws each particle's birth, launch point, velocity, drag and landing age from a seed. Geometry nodes
evaluate `p(a) = p0 + v0·F + (g/k)(a − F)`, `F = (1 − e^(−ka))/k`, frozen at the landing age. Builds take 0.3 s.

- `burst(name, *, center, t0, count=300, speed=(60, 220), direction, cone=180, drag=1.5, life=(0.3, 0.9), size=0.06, streak=0.018, strength=6)`:
  sparks as emissive capsules stretched along their velocity, cooling from white-yellow to red. They stop on the
  floor.
- `sparks_along(name, *, points, starts=[t...], travel=0.4, rate=500, light=8000)`: one bright bead per start time
  runs along the path (the USB cable: `d.cable.pts`), with a point light riding it and shedding embers. Use it for
  A, G, I.
- `confetti(name, *, center, t0, count=500, speed=(1000, 2200), drag=45, cone=55, sway=2.5, spin=9)`: fired fast
  and stopped by the air, confetti rises 20-50 cm, flutters down for about 2 s, and lies flat where it lands.
- `fuse(name, *, points, t0, t1, rate=900, light=6000, radius=0.25)`: the cord burns from start to end. The tube
  shortens behind the burn point, the ash glows then cools, and sparks spray from a flickering light.
- `motes(name, *, box, count=800, drift=0.8)`: dust that shows only inside a light beam (not emissive). The desk
  set already has lamp-cone motes.
- `stream(name, instance, *, source, t0, t1, rate, ...)`: tumbling objects of any kind (`clips.pour` uses it).

## Atoms rearranging (`cubes`)

`dissolve(name, obj, *, t0, t1, cube=0.35, shuffle=True, spread=6, swirl=2.5, spin=3, stagger=0.45, floor=0)`
- obj is voxelised by ray parity, so it must be a closed mesh.
- Its cubes lift off bottom first, swirl out and land in their own cell. With `shuffle=True` they land in another
  cube's cell: the same shape, with every atom moved.
- The original hides during [t0, t1]. The effect is keyed by one `Progress` input.
- Measured: a mitten hand made 1,238 cubes of 0.3 cm, built in 0.3 s.

## Save and reload (measured)

`out/wip/_fx/probe/reload_check.sh` builds a scene, saves it and renders frames in that process. It then renders
the same frames from the saved .blend in a fresh process and compares them:

- Avalanche (8,444 clips): mean difference 0.012/255, 1 pixel over 24/255 in 518,400.
- Fireball (Mantaflow cache on disk): 0.000/255.
- Globe spill (liquid cache on disk, 407 s build): 0.000/255.

## Limits

- **Clip piles.** Clips can't hook each other (their collision shape is a box), so heaps are flatter than real
  tangles. A clip resting on the desk floats 0.35 mm, because its collision box (0.16 cm) is thicker than the wire
  (0.09 cm). That is invisible at normal framing.
- **Timing resolution.** Kinematic/dynamic switches, launches and domino retiming work on whole frames (1/24 s).
- **Water spread.** Mantaflow water has no contact angle, and surface tension had no visible effect. Viscosity sets
  how far the spill spreads, and its solver is the main bake cost.
- **Dark glass and water.** Glass shards and water on the desk read dark and glossy against the dark room. That is
  EEVEE refraction; give them a light to reflect.
- **Volume range.** Volumes must stay within 4.5 m of the camera (kit's EEVEE volume range).

## Requests to the lead (kit and tools)

- `tools/render.py` only shows output lines that start with `[run]`. The fx kit prints `[run] [fx] ...`, but
  Bullet's progress output sometimes shares a line with it and hides it. It would help to also keep lines that
  contain `[fx]`.
