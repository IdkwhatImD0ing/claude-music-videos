# chars: Clawd, Sydney and the researcher

`blender/lib/pdoom/chars/` builds the video's rigged characters and animates them by song time, on twos. Test
scenes: `blender/scenes/_test_chars.py` (both characters acting on the real desk, 0-24 s) and
`_test_chars_sheet.py` (a model sheet: every researcher pose front and profile, Clawd's expressions and props).

## Quick start

```python
from pdoom import chars, kit, timing as tm
from pdoom.sets import build_desk

def build():
    kit.new_scene('training')
    d = build_desk(kit.collection('desk'))
    c = chars.Clawd(kit.collection('clawd'), loc=d.anchors['clawdSpot'], yaw=0)
    r = chars.Researcher(kit.collection('researcher'), loc=d.anchors['researcherSpot'], yaw=120)
    c.eyes(5.8, 'open', glow=4)                       # wakes up
    c.blink(6.3); c.look(6.8, r)                      # blinks, looks at him
    r.pose(7.0, 'nervous'); r.fidget(7.0, 9.0); r.sweat(7.2, 9.0)
    r.pose(9.2, 'adjust_glasses'); r.glasses_glint(9.6)
    c.move(10.0, 11.5, [(14, -6), (20, -2)])          # scuttles off along a curve
    c.chomp(tm.word('boss', 'boss')['start'])         # hits on words / beats from timing
    chars.finish()                                    # bake (see "Baking")
```

Every API call takes song seconds and returns the character, so calls can be chained. Call order doesn't matter much:
keys are sorted by time. Angles are degrees. Positions are world cm.

## How it animates

- **On twos.** Bake samples every track once per 2 frames (even global frames) and writes CONSTANT keys half a frame
  early (f - 0.5), so a pose covers the whole shutter: characters never motion-blur, like a real puppet. Frames f
  and f+1 show the pose at time (f+1)/24, so a hit lands within one frame of its time. Moving poses get a tiny
  seeded jitter (about 0.02 cm, 0.4-1.4 deg); holds stay clean.
- **`c.timing(t0, t1, mode)`** switches a span to `'ones'` (a pose every frame, still crisp) or `'smooth'` (LINEAR
  keys every frame, motion-blurred, no jitter). The constructor's `timing=` sets the default.
- **Tracks.** Persistent state (position, lid, arms, eye shape, props) is keyed with "arrive at t" semantics: the
  channel tweens over `dur` and reaches the value exactly at t, then holds. Actions (hop, chomp, take, blink, dance,
  wave) are additive overlays on top, so they combine.
- **Legs walk by themselves.** Any root motion (move, turn, look, hop `to=`) drives a gait phase integrated from
  the actual speed: legs scuttle, the body bobs and the arms swing, faster when he moves faster, settling when he
  stops. `move(..., gait=False)` or `c.no_gait(t0, t1)` slides without stepping (riding a bead, a train).
- **Auto-blinks** every 2.3-5 s (seeded), skipped within 0.35 s of any API event. `blink=False` turns them off.

## Baking

`chars.finish()` at the end of `build()` bakes every character. As a safety net the library also bakes on
`save_pre` and `render_init`, so a forgotten `finish()` still renders correctly, but call it anyway: bake reads the
scene's frame range, and anything you read back from the pose before baking is the rest pose. Re-calling the API
after a bake marks the character dirty; `finish()` re-bakes it.

## Clawd

`chars.Clawd(coll, name='clawd', loc=(0,0,0), yaw=0, scale=1, *, variant='vinyl', seed=None, timing='twos',
blink=True, glow_light=True)`

`chars.sydney(coll, name='sydney', loc, yaw, scale, **kw)` is the same rig in translucent blue jelly (raytraced
refraction; a jelly core instead of the dark mouth; she glows faintly).

| Call | What it does |
|---|---|
| `place(t, loc=None, yaw=None)` | Snap to a position (x, y[, z]) and/or yaw at t (a cut). |
| `turn(t, yaw, dur=0.3)` | Turn in place to yaw by t (the legs shuffle). |
| `move(t0, t1, points, face='forward', ease='inout', smooth=True, gait=True)` | Travel from the current spot through `points` (Catmull-Rom) arriving at t1, at constant speed with ease in/out. `face`: `'forward'`, `'back'`, `'keep'` (crab walk) or a yaw. `walk` is an alias. |
| `hop(t, height=2, dur=None, to=None, at='takeoff', spin=0)` | Anticipation squash, arc, stretch, landing squash. `at` says which moment lands on t: `'takeoff'`, `'apex'`, `'land'`. `to` hops to a new spot, `spin` adds yaw in the air. |
| `squash(t, amount=0.25)`, `stretch(t, amount=0.2)` | A squash (or stretch) arriving at t, springing back. |
| `lid(t, open01, dur=0.14)` | Open the lid/mouth: 0 closed, 1 = 72 deg, up to 1.3. |
| `chomp(t, wide=0.9, n=1, every=beat)` | The lid opens before t and slams shut ON t (and t + k*every), with a lunge. |
| `eyes(t, shape=None, glow=None, color=None, side=None)` | Swap the eye shape at t (replacement animation) and/or key the glow. `side='L'` or `'R'` for one eye. |
| `glow(t, strength=5, color=None, side=None)` | Eye emission (0 off, 3-8 lit) and colour. A wide spot light just in front of his eyes, aimed where he faces, follows it: it lights the desk and whoever he looks at, not his own face (`glow_light=False` to skip). |
| `blink(t, side=None)` | One blink starting at t. |
| `look(t, target=None, turn=0.6, dur=0.25)` | Look at a point, an object or another character: the body turns `turn` of the way (not while moving), the eyes slide and the body tilts for the rest. `None` recentres. |
| `arms(t, pose='rest', side=None, dur=0.16)` | Named pose or `(raise, swing, twist)` degrees. |
| `wave(t0, t1, side='R')` | Raises an arm, waves on the beat, puts it back. |
| `take(t, hold=0.8, mark=False, jump=1.3)` | The cartoon's surprise take: squash, pop up, stretch, arms fly up, eyes 'surprised', lid gasps; returns to the previous eyes after `hold` unless you set them in between. `mark=True` pops a yellow '!' above him. |
| `dance(t0, t1, style='bounce', beats=None, amount=1)` | On the song's beats in [t0, t1) (or your list): `'bounce'`, `'sway'`, `'spin'` (a quarter turn per beat, finishes the full turn), `'shimmy'`, `'hop'` (lands on each beat), `'chomp'` (lid bop), `'wave'` (arms up swaying). |
| `wear(t, prop, on=True)` | Put on/take off `'crown'` (paper crown), `'cat_ears'`, `'mask'` (yellow smiley over the face), `'party_hat'`, `'bowtie'`. Head props ride the lid. |
| `scale_to(t, s, dur=0.35, ease='back')` | Uniform size (FOOM). The eye light scales too. |
| `visible(t_on=None, t_off=None)` | Show the whole character only between the times (add more calls for more switches). |
| `timing(t0, t1, mode)`, `no_gait(t0, t1)` | See above. |
| `attach(obj, socket, offset=(0,0,0), rot=(0,0,0))` | Parent a scene object to a socket bone, placed at the socket's rest spot + offset (character axes). |
| `anchor(t, name='face')` | World position of a socket at song time t (from the tracks; within ~0.1 cm of the render). |

**Eye shapes** (`chars.EYE_SHAPES`): `open`, `happy` (^^), `angry`, `narrow` (half-lidded, for "boss"), `surprised`
(big, with a catchlight), `shut` (closed arcs), `heart` (pink), `sad`, `small` (scared), `x` (KO), `star` (yellow),
`dizzy` (spirals). Shapes are built on first use.

**Arm poses** (`chars.ARM_POSES`): `rest`, `down`, `out`, `up`, `high`, `cheer`, `forward`, `hold`, `hug`, `back`,
`shrug`, `fold`, `akimbo`, and one-sided `point`, `wave`, `think` (right arm).

**Sizes and anchors** (character space: standing on z = 0 at the origin, facing -Y, his left is +X):

| | |
|---|---|
| Body | 8 x 4.5 x 5 cm bevelled box (edge radius 0.66), underside at z 1.3, top at 6.3; legs 1.6 tall (8, two rows) |
| Lid | the top 2.75 cm (z 3.55-6.3), hinged at the back (y 2.05, z 3.55); cavities 1.3 cm deep below, 1.45 above; 6 + 5 front teeth, 4 + 4 side teeth, a tongue |
| Eyes | 0.64 x 1.36 cm glossy pills at (+-1.95, -2.25, 4.88), 0.15 proud of the face; they slide up to 0.36 sideways when looking |
| Sockets (bones) | `face` (0, -2.25, 4.88) and `hat` (0, 0, 6.3) ride the lid; `mouth` (0, -0.2, 2.25) is the jaw floor; `back` (-2.6, 2.25, 2.2) is the USB-C port on his back-left, where the desk's cable plugs in (`clawdPort` = `clawdSpot` + this); `hand.L/R` at the arm tips (+-5.25, 0, 3.0); also `body`, `lid`, `hips`, `root`, `eye.L/R` |
| Rig | armature `<name>.rig`: root > hips > body (squash) > lid > eyes/face/hat; body > arms > hands; hips > 8 legs. All parts are rigid meshes bone-parented (no deformation) |

Parts for scenes that need to take him apart (the robot transformation): `c.rig`, `c.o_body`, `c.o_lid`, `c.o_legs`
(8), `c.o_arms['L'/'R']`, `c._eye_objs[(shape, side)]`, `c.m_body` (the shared vinyl material).

## The researcher

`chars.Researcher(coll, name='researcher', loc=(0,0,0), yaw=0, scale=1, *, seed=None, timing='twos', blink=True,
face='neutral')`

A 12 cm turned-wood peg doll: varnished maple head with a painted hair cap and a painted face (12 expressions from an
atlas), round brass wire glasses with lenses, a painted blue shirt and red tie, a modelled lab coat (lapels, pockets,
buttons, pen, ID badge; its skirt follows the thighs), bendable sleeve arms (B-bones + IK) with wooden mitten hands,
trousers and glossy shoes.

| Call | What it does |
|---|---|
| `place`, `turn`, `move`/`walk`, `visible`, `timing`, `no_gait` | As for Clawd. Walking waddles: hip sway, bob, knees, arm swing. |
| `pose(t, name, dur=0.3, face=True)` | Arrive at a pose from `chars.POSES` by t (and its face, if the pose names one). |
| `face(t, expr)` | Painted expression from t: `neutral`, `blink`, `nervous` (sweat drop painted), `happy`, `proud`, `shock`, `scared`, `sad`, `talk`, `determined`, `awe`, `wince`. |
| `look(t, target=None, turn=None)` | Head (and a little spine) toward a point/object/character. Beyond ~65 deg the body turns the excess (or `turn=` a fraction). |
| `hand(t, side, target, wrist=None, reach=0.55)` | Put the mitten (side `'L'`/`'R'`) on a world point by t. Keeps its place relative to his body afterwards. |
| `wave(t0, t1, side='R')`, `pat(t0, t1, target=None)`, `fidget(t0, t1)`, `nod(t, n=2)`, `shake_head(t, n=3)`, `jump(t)` | Small actions (overlays). |
| `glasses_glint(t, color='#FFFFFF', dur=0.4, strength=14, hold=0)` | A bright band sweeps across both lenses. `hold > 0`: the lenses then glow solid in `color` (the red "shinigami" glint). |
| `glasses_reflect(t0, t1, color='#FFA030', strength=3)` | Two small glowing tall eyes reflected in each lens (the boot scene: Clawd's eyes lighting). |
| `sweat(t0, t1)` | A glossy bead appears on the temple and slides down. |
| `attach(obj, socket='hand.R', offset, rot)` | Parent a prop to `hand.L/R` (the mitten palm), `head`, `spine`, `hips`, `root`. |
| `anchor(t, name='eyes')` | `eyes` (between the lenses), `head`, `hand.L/R` (wrist targets), `chest`, `hips`, `root`. |

**Poses** (`chars.POSES`): `stand`, `lean_in`, `nervous`, `adjust_glasses`, `kneel_offer` (right knee down, right hand
offering), `point`, `pat`, `peer`, `sit` (on the surface under his root; legs forward), `gasp`, `back_away`,
`hold_leash`, `stand_on_mug` (arms out for balance), `wave`, `think`, `proud` (hands on hips), `shrug`, `cower`,
`cheer`, `type`, `present`, `hold` (both hands together in front), `arms_crossed`, `facepalm`. A pose is a dict of
channels (hips offset, spine, head, hand targets in body space, wrists, thighs, shins, face); add your own by writing
into `POSES` before calling `pose()`.

**Sizes**: height ~11.8 cm (hair top); hips 2.55; shoulders (+-1.4, 0, 6.42); head centre 9.85, radius 1.9; lens
centres (+-0.69, -2.0, 9.85), radius 0.57. **Reach**: about 3.1 cm from shoulder to wrist plus the mitten; targets
further away leave the arm fully extended toward them (no stretch), so stand him close to what he touches.

**Rig**: `<name>.rig`: root > hips > spine (the rigid turned body leans about the hips) > head; hips > thigh > shin
(FK); spine > upper_arm > forearm (IK to `hand_ik.L/R`, pole `pole.L/R`) > hand. The sleeves, trousers and coat
deform with an Armature modifier; everything else is rigid.

## Props for scenes

`chars.props.make(prop, coll, name, M=Matrix)` builds a free-standing copy of `'crown'`, `'cat_ears'`, `'mask'`
(smiley, 3.6 cm; scale it for the shoggoth), `'party_hat'`, `'bowtie'` or `'mark'` ('!') with its anchor at `M`.

## Costs (measured, RTX 5080)

- Build: Clawd 0.03 s, Sydney 0.03 s, researcher 0.1 s. Bake: about
  1 ms per character per second of scene.
- Geometry: Clawd 21 objects, ~9k faces (more as eye shapes and props are used); researcher 14 objects, ~8k faces.
- Render: a full-frame close-up on the desk at 64 samples, 1080p, motion blur: ~1.2 s (2.5 s for the first,
  shader-compiling frame). `--samples 16 --nomb --scale 50`: ~0.3 s.

## Limits

- `look()`, `hand()` and `pat(target=)` read a moving target where it is at the call time (object) or at t (character).
  They don't track a target that moves afterwards; call again.
- Base keys that overlap in time: the one arriving later wins while both are in progress. `look()` doesn't turn the
  body while `move()` is carrying him (only eyes and head).
- The researcher's legs are FK: in `walk` the feet slide a little over long strides; `kneel_offer` and `sit` put the
  knee/seat at his root height, so place his root on the surface he kneels or sits on.
- The coat is rigid above the hips: extreme spine twists show the body under the lapels.
- Sydney's refraction is screen-space (EEVEE): she refracts what's on screen; a snow globe's glass adds another
  layer, so check those shots.
- Faces are painted textures: expressions switch instantly (replacement animation), with no in-betweens.
- Everything is keyed for the scene's frame range; changing `frame_start/end` after `finish()` needs another
  `finish()` (or `c.bake()`).

## Files

`__init__.py` (exports), `rig.py` (tracks, bake on twos, gait, locomotion, handlers), `geo.py` (rounded boxes, lathes,
raised decals, tubes), `looks.py` (materials), `clawd.py`, `props.py`, `researcher.py`, `faces.png` (the face atlas)
and `make_faces.py` (paints it; run with the system Python after editing a face).

## Keeping limbs out of bodies (added after the user saw arms inside bodies)

- **Researcher:** every hand target goes through `clear_arm()` at bake time: it clamps the target to the arm's reach,
  bends the elbow away from the body (elbow direction keyed per pose), and pushes the wrist out by the least amount so
  the sleeve, cuff, mitten and thumb clear the coat, neck, head and glasses. The mitten keeps each pose's angle.
  `anchor('hand.L/R')` returns the adjusted wrist.
- **Clawd:** `arm_clear()` slides each stub arm out along its shoulder until it clears the box; swings are capped at
  90°. His stubs are too short to fold across the body: "fold" poses show the arms forward at his sides.
- Check a scene with a per-frame test of hand/forearm positions against the bodies (see out/wip/clip/ scripts of the
  fix, git-ignored) and look at close-ups of hands near bodies.
