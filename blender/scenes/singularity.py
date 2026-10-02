"""singularity · 38.418-52.962 · "We had a stable training run, / But now the singularity's begun / And you're
optimizing, accelerating, / I feel my atoms rearranging"

A tinplate clockwork train (the training run) circles an oval of tin track on the desk with Clawd riding in a blue tub
wagon, the researcher watching, proud. In the middle of the loop a black hole opens: a black sphere with a photon ring,
a lensed halo and an accretion disc of glowing gas, paper confetti, dust and embers; the desk behind it warps around
the shadow; the lamp cranes toward it. The train speeds up lap by lap, the track rips up behind it like a zipper and
spirals in, and the train runs off the gap, is captured into orbit and goes in car by car, stretched. The researcher's
hand then breaks into tiny cubes that swirl toward the hole and come back rearranged; the hole collapses and leaves a
snow globe on the desk (the next scene).

Shots (song s; cameras / train / effects smooth at 24 fps, characters on twos)                    hits
 S1  loco     38.418-39.781  38 mm tracking beside the train, low, on the tender and Clawd in his     puffs on the beats
                             tub with the loco's cab at the edge (revision 2: the blocks riding the
                             cars stay sharp); the researcher proud in the background.
 S2  stable   39.781-41.340  35 mm wide from the front: the oval, the researcher proud on the left, nods on the beats
                             the calm loss curve on the laptop, the gauge at 25. Slow push.
 S3  now      41.340-42.294  50 mm across the loop at the hole's height, the train passing behind:  pinprick on "now" 41.56
                             the lamp flickers and a black pinprick with a ring opens mid-air.      (lamp flicker)
 S4  sing.    42.294-44.080  28 mm hero wide, pushing in and craning down: the hole grows in three  steps on 42.508 42.963
                             beat-steps, the disc lights up and spins, the desk and rails behind    43.417
                             warp round the shadow, notes peel off the pad, the lamp cranes toward
                             it; Clawd turns to it, star eyes.
 S5  begun    44.080-45.060  65 mm on the researcher's face in the orange light, awe.               glint 44.55
 S6  and      45.060-46.160  on-ride: from the tender back at Clawd grinning in his tub, the world  speed-up from 45.06
                             whipping by, notes flying.
 S7  optim.   46.160-47.260  rail level outside the left curve, panning with the loco as it         laptop curve flips 46.16
                             thunders round past the lens, the hole beyond; the rails rattle.
 S8  accel.   47.260-47.963  high three-quarter (whip in): the disc face-on, the track rips up       zipper from 47.43
                             behind the caboose like a zipper and the pieces spiral into the disc.
 S10 leap     47.963-48.417  low from the front (whip in off the researcher): the loco runs off the  leap on 47.963
                             gap, banks up into orbit round the hole, the cars rush past the lens;
                             the laptop's curve is vertical.
 S11 orbit    48.417-48.872  riding outside the orbit (whip in): Clawd in the tub, star eyes, grin.
 S12 swallow  48.872-49.562  above the hole: the cars stretch and pour into the horizon car by car;  last car in on 49.326
                             flash as the caboose goes.                                              (flash)
 S13 feel     49.562-50.480  50 mm, the hole behind him: he turns his back on the glare and raises  voxels at 50.40
                             his right hand; it turns to cubes.
 S14 rearr.   50.480-52.962  58 mm: the cubes peel off from the fingertips up the arm and stream    peel from "atoms" 50.48,
                             into the hole's ring, come back on "rearranging" and land shuffled (a  back on 51.38, smooth
                             wood-and-white mosaic hand), the arm pops back; the hole winks out in  52.40, flash 52.508
                             a flash and the snow globe of `sydney` stands there, snow whirling;
                             he spins round, focus racks to the globe.
"""
from __future__ import annotations

import math
import os

import bpy
from mathutils import Matrix, Vector

from pdoom import chars, fx, kit
from pdoom import timing as tm
from pdoom.fx import clips
from pdoom.sets import build_desk, geo, phys_fstop

from scenes import singularity_atoms as AT
from scenes import singularity_hole as H
from scenes import singularity_props as PR
from scenes import singularity_sep as SEP
from scenes import singularity_train as TR

FPS = tm.FPS
T0, T1 = 38.418, 52.962
O = Vector((8.0, -16.0, 0.0))            # centre of the oval (desk)
C = Vector((8.0, -16.0, 6.2))            # the hole (at the cars' height: the train passes behind it)
RH = 2.3
ONLY = os.environ.get('SING_ONLY', '')   # iteration: 'nohole' skips the hole, etc.


def W(line, w):
    return tm.word(line, w)['start']


W_STABLE = W('stable training run', 'stable')              # 39.2
W_RUN = W('stable training run', 'run')                    # 40.9
W_BUT = W("singularity's begun", 'But')                    # 41.34
W_NOW = W("singularity's begun", 'now')                    # 41.56
W_SING = W("singularity's begun", "singularity's")         # 42.294
W_BEGUN = W("singularity's begun", 'begun')                # 44.08
W_AND = W('optimizing, accelerating', 'And')               # 45.06
W_OPT = W('optimizing, accelerating', 'optimizing')        # 46.16
W_ACC = W('optimizing, accelerating', 'accelerating')      # 47.26
W_I = W('atoms rearranging', 'I')                          # 49.562
W_ATOMS = W('atoms rearranging', 'atoms')                  # 50.48
W_REARR = W('atoms rearranging', 'rearranging')            # 51.38
BEATS = tm.beats_between(37.0, 54.0)

T_LEAVE = 47.963           # the loco runs off the gap (a beat)
T_SWALLOW = 49.326         # the last car goes in (downbeat)
T_HOLD = 50.2              # the raised hand is still from here (the voxels are measured on this pose)
T_VOX = 50.4               # hand and sleeve swap to cubes
T_POP = 52.4               # the smooth arm is back
T_COLLAPSE = 52.508        # the hole winks out (a beat): flash, and the snow globe stands there
GLOBE_O = Vector((O.x, O.y, 0.0))
GROW = (42.508, 42.963, 43.417)


def sm(t, a, b):
    return tm.smooth(t, a, b)


def frames_between(t0, t1):
    return list(range(int(math.floor(t0 * FPS)) - 1, int(math.ceil(t1 * FPS)) + 2))


def beat_pulse(t, hl=0.12):
    return tm.pulse(t, BEATS, half_life=hl)


# ------------------------------------------------------------------------------------------------ cameras


class Cam:
    """A shot: loc_fn / tgt_fn (song time -> world point) keyed every frame over the shot, cut in at t0.
    focus_fn: optional world point to focus on (else the target). lens_fn: optional zoom."""

    ALL: list = []

    def __init__(self, name, t0, t1, loc_fn, tgt_fn, lens=35.0, fstop=8.0, focus_fn=None, lens_fn=None,
                 fstop_fn=None, whip=0.0, whip_dur=0.11):
        self.name, self.t0, self.t1 = name, t0, t1
        if whip:
            # a whip pan into the shot: the aim swings in from `whip` radians to the side over the first frames
            base_tgt = tgt_fn

            def tgt_fn(t, base_tgt=base_tgt):
                g = Vector(base_tgt(t))
                u = min(1.0, max(0.0, (t - t0) / whip_dur))
                k = (1.0 - u) ** 2.2
                if k <= 0.0:
                    return g
                lo = Vector(loc_fn(t))
                d = g - lo
                right = d.cross(Vector((0.0, 0.0, 1.0))).normalized()
                return g + right * (math.tan(whip * k) * d.length)
        self.loc_fn, self.tgt_fn = loc_fn, tgt_fn
        cam, tgt = kit.camera('cam.' + name, lens=lens, loc=tuple(loc_fn(t0)), target=tuple(tgt_fn(t0)),
                              fstop=fstop, coll=kit.collection('cams'))
        cam.data.dof.aperture_fstop = phys_fstop(fstop)
        cam.data.dof.aperture_blades = 7
        cam.data.clip_start = 0.2
        self.cam, self.tgt = cam, tgt
        fr = frames_between(t0 - 0.05, t1 + 0.05)
        if tm.SMOOTH:            # 60 fps: sample every output frame (the whip-ins ease over only ~2.6 24 fps frames)
            fr = tm.out_frames(fr[0], fr[-1])
        ts = [f / FPS for f in fr]
        L = [Vector(loc_fn(t)) for t in ts]
        G = [Vector(tgt_fn(t)) for t in ts]
        for i in range(3):
            H.fast_keys(cam, 'location', [float(f) for f in fr], [v[i] for v in L], index=i)
            H.fast_keys(tgt, 'location', [float(f) for f in fr], [v[i] for v in G], index=i)
        if focus_fn is not None:
            dof = cam.data.dof
            dof.focus_object = None
            H.fast_keys(cam.data, 'dof.focus_distance', [float(f) for f in fr],
                        [(Vector(focus_fn(t)) - Vector(loc_fn(t))).length for t in ts])
        if lens_fn is not None:
            H.fast_keys(cam.data, 'lens', [float(f) for f in fr], [lens_fn(t) for t in ts])
        if fstop_fn is not None:
            H.fast_keys(cam.data, 'dof.aperture_fstop', [float(f) for f in fr], [phys_fstop(fstop_fn(t)) for t in ts])
        kit.cut_to(cam, t0)
        Cam.ALL.append(self)

    def at(self, t):
        return Vector(self.loc_fn(t))


def live_cam(t):
    """The camera that renders song time t: the cut markers sit on whole frames (tm.t2f(t0)), so a shot whose t0 falls
    early in a frame is live from that frame on (comparing t with t0 had the billboard face the old camera there)."""
    order = sorted(Cam.ALL, key=lambda c: c.t0)
    cur = order[0]
    f = t * FPS
    for c in order:
        if f >= tm.t2f(c.t0) - 1e-6:
            cur = c
    return cur


# ------------------------------------------------------------------------------------------------ build


def build():
    sc = kit.new_scene('singularity')
    sc.eevee.shadow_pool_size = '1024'
    Cam.ALL = []
    d = build_desk(kit.collection('desk'), mood='night', exclude={'mug', 'cable', 'clip', 'pen', 'notes'})
    S = type('S', (), {})()
    S.d = d
    world_and_desk(S)
    train(S)
    if ONLY != 'nohole':
        hole(S)
    else:
        key_fly(S)
    characters(S)
    globe(S)
    cameras(S)
    if ONLY != 'nohole':
        hole_follow(S)
    kit.post(bloom=0.32, bloom_threshold=1.0, vignette=0.24)
    chars.finish()
    if ONLY != 'noatoms':
        AT.dissolve(S.researcher, pull=S.pull, t_hold=T_HOLD, t_vox=T_VOX, t_pop=T_POP, cube=0.1,
                    t_in=(W_REARR, 51.95))
    from pdoom import lyrics as ly
    if ly.ENABLED:                 # revision 3: subtitles instead (lyrics.ENABLED)
        lyrics(S)
    sc.frame_set(sc.frame_start)


def lyrics(S):
    """Revision 2: every sung word in the picture (docs/lib/lyrics.md).

    S1-S2      "We had a stable training run" rides the train as painted blocks on the cars (WE HAD A on the
               tender, STABLE on the tub's rim beside Clawd, TRAINING RUN on the caboose roof), popping up on their
               words; the lyric stand in the wide S2 carries the whole line
    S3-S4      "But now the singularity's" on the stand; the black hole sucks the letters in on its growth beats
               (BUT NOW THE on 42.963, SINGULARITY'S letter by letter from 43.55)
    S5         what's left: "begun" on the stand under the researcher's awed face
    S6         "and you're" on blocks standing on the tub's front rim, riding with Clawd toward the lens
    S7-S12     line 14 on the stand (S11, the orbit: ACCELERATING rides the tub's rim instead)
    S13-S14    line 15 on the stand; REARRANGING pops up scrambled and sorts itself as his cubes land (51.8-52.1)
    """
    from pdoom import lyrics as ly
    st = ly._state()
    tr = S.train
    F = 1.0 / FPS

    def unclaim(line, js):
        for j in js:
            st['claimed'].discard((line, j))

    # ---- S1-S2: blocks riding the cars, on the side the tracking camera sees
    # (placements on a car read its current scale: evaluate the cars at a time they're toy-sized, not spaghetti)
    bpy.context.scene.frame_set(int(39.0 * FPS))
    cam1 = next(c for c in Cam.ALL if c.name == 'loco')
    Mt = S.car_M(tr.tub, 39.1)
    lat = Vector(Mt.col[1][:3]).normalized()
    sgn = 1.0 if lat.dot(cam1.at(39.1) - Mt.translation) > 0 else -1.0
    riders = [(tr.tender, (0, 3), (0.0, sgn * 2.2, 6.0), 0.84),
              (tr.tub, (3, 4), (0.0, sgn * 3.9, 6.0), 0.95),
              (tr.caboose, (4, 6), (0.0, sgn * 2.62, 6.55), 0.6)]
    for car, words, org, size in riders:
        ly.line(12, words=words, style='blocks', place=ly.on_object(car.root, org, (0.0, sgn, 0.0), (0, 0, 1),
                                                                     size=size, lift=0.0),
                t_show=T0, t_end=W_BUT - 0.5 * F, exit='none', max_chars=30)
    unclaim(12, range(6))
    ly.line(12, place='auto', t_show=39.781, spec=ly.StageSpec(cells=16.0, rows=2))   # the wide S2: the whole line
    # ---- S3-S4: into the hole
    def eat_t(pc):
        if pc.word.index < 3:
            return GROW[1] + 0.042 * pc.k_index
        return 43.5 + 0.042 * pc.letter.k
    ly.line(13, words=(0, 4), place='auto', t_end=W_BEGUN, exit='eaten',
            exit_opts=dict(target=lambda t: Vector(C), t=eat_t, frames=7, stagger=0),
            spec=ly.StageSpec(cells=15.0, rows=2))
    # ---- S6: "and you're" on the tub's front rim (facing the tender, where the on-ride camera sits)
    ly.line(14, words=(0, 2), style='blocks', place=ly.on_object(tr.tub.root, (4.4, 0.0, 6.0), (1, 0, 0), (0, 0, 1),
                                                                  size=0.62, lift=0.0),
            t_show=W_AND - 0.1, t_end=W_OPT - 0.5 * F, exit='none')
    unclaim(14, range(4))
    # ---- S11 (the orbit): ACCELERATING on the tub's rim, facing the orbiting camera
    orbit = next(c for c in Cam.ALL if c.name == 'orbit')
    Mo = S.car_M(tr.tub, 48.64)
    dl = Mo.inverted().to_3x3() @ (orbit.at(48.64) - Mo.translation)
    dl.z = 0.0
    dl.normalize()
    ly.line(14, words='accelerating', style='blocks',
            place=ly.on_object(tr.tub.root, dl * 4.1 + Vector((0.0, 0.0, 6.0)), dl, (0, 0, 1), size=0.6, lift=0.0),
            t_show=48.417 - 0.5 * F, t_end=48.872 - 0.5 * F, exit='none')
    unclaim(14, range(4))
    # ---- S7-S10 and S12: the stand
    sp14 = ly.StageSpec(cells=22.0, rows=2)
    ly.line(14, place='auto', window=(W_OPT, 48.417), spec=sp14)
    unclaim(14, range(4))
    ly.line(14, place='auto', window=(48.872, W_I), spec=sp14)
    # ---- everything else (begun, line 15) on the stand
    out = ly.default('singularity')
    # REARRANGING: its letters pop up in a jumble and sort themselves as the cubes land
    import random
    for lyr in out:
        if lyr.line != 15:
            continue
        for cp in lyr.copies:
            pcs = [pc for pc in cp.pieces if pc.word.index == 4]
            if not pcs:
                continue
            xs = [pc.rest.x for pc in pcs]
            order = list(range(len(pcs)))
            rnd = random.Random(15)
            while any(i == j for i, j in enumerate(order)):
                rnd.shuffle(order)
            for k, pc in enumerate(pcs):
                sh = bpy.data.objects.new(pc.obj.name + '.shuffle', None)
                cp.root.users_collection[0].objects.link(sh)
                sh.parent = cp.root
                pc.obj.parent = sh
                dx = xs[order[k]] - xs[k]
                f_go = int(round(51.8 * FPS)) + (k % 3)
                poses = [(f_go - 30, dx, 0.0), (f_go, dx, 0.0), (f_go + 2, dx * 0.66, 0.55), (f_go + 4, dx * 0.25, 0.7),
                         (f_go + 6, 0.0, 0.15), (f_go + 8, 0.0, 0.0)]
                for f, x, z in poses:
                    sh.location = (x, 0.0, z)
                    sh.keyframe_insert('location', frame=f - 0.5)
                for fc in kit.fcurves(sh):
                    for kp in fc.keyframe_points:
                        kp.interpolation = 'CONSTANT'



# ------------------------------------------------------------------------------------------------ desk


def world_and_desk(S):
    d = S.d
    # the laptop: a calm training curve; on "optimizing" it goes vertical
    d.laptop.set_image(PR.stable_image(), 'A')
    d.laptop.set_image(PR.takeoff_image(), 'B')
    d.laptop.screen(T0 - 0.5, glow=1.25, mix=0.0)
    d.laptop.screen(W_NOW - 0.02, glow=1.25)
    for k, g in enumerate((0.3, 1.6, 0.5, 1.4, 1.25)):
        d.laptop.screen(W_NOW + 0.04 * (k + 1), glow=g, interp='CONSTANT')
    d.laptop.screen(W_OPT - 0.08, mix=0.0, interp='CONSTANT')
    d.laptop.screen(W_OPT - 0.04, mix=1.0, glow=1.9, interp='CONSTANT')
    d.laptop.screen(W_OPT, mix=0.0, glow=0.6, interp='CONSTANT')
    d.laptop.screen(W_OPT + 0.04, mix=1.0, glow=1.5, interp='CONSTANT')
    # the hole's lens is clear glass (transmission 1, roughness 0): EEVEE draws any light behind it as a sharp image
    # of the light's shape, so the screen-sized fill showed as a pale-cyan slab over the screen, and the lamp as white
    # crescents. They still light everything; they just don't show through the lens (like the hole's own lights).
    # (Every desk light: the fill, the lamp, the room bounce; the window light already has it.)
    d.laptop.fill.data.transmission_factor = 0.0
    d.lamp.light.data.transmission_factor = 0.0
    for o in bpy.context.scene.objects:
        if o.type == 'LIGHT':
            o.data.transmission_factor = 0.0
    # the gauge quivers while the hole is open
    d.gauge.tremble(42.3, 45.0, amp=1.2, rate=11.0, seed=3)
    d.gauge.tremble(45.02, 49.4, amp=3.5, rate=15.0, seed=4)
    d.gauge.tremble(49.42, 52.9, amp=2.0, rate=12.0, seed=5)
    # the haze leaves when the hole opens (EEVEE's refraction can't carry the in-scattered glow)
    if d.room.haze_density is not None:
        hz = d.room.haze_density
        v0 = hz.default_value
        geo.keyp(hz, 'default_value', T0 - 0.5, v0, interp='CONSTANT')
        geo.keyp(hz, 'default_value', W_BUT - 0.5 / FPS, v0, interp='CONSTANT')
        geo.keyp(hz, 'default_value', W_BUT, 0.0, interp='CONSTANT')
    if d.room.motes is not None:
        fx.vis(d.room.motes, None, W_BUT)
    # the lamp: flickers on "now", then cranes toward the hole on the growth beats, dimming as it's pulled
    lp = d.lamp
    lp.flicker(W_NOW - 0.03, W_NOW + 0.36, depth=0.85, rate=16, seed=9, dropouts=0.35, end=1.0)
    pool = O + Vector((-3.0, -4.0, 0.0))
    lp.aim(T0 - 0.5, pool, reach=38.0, height=44.0, interp='BEZIER')
    lp.aim(W_SING, pool, reach=38.0, height=44.0, interp='BEZIER')
    for k, (tb, reach, hgt) in enumerate(((GROW[0], 37.0, 38.0), (GROW[1], 40.0, 35.0), (GROW[2], 43.0, 33.0),
                                          (43.872, 44.0, 32.0), (45.69, 46.0, 31.0), (47.508, 47.5, 30.0))):
        tgt = C + Vector((0, 0, -2.0 + k * 0.3))
        lp.aim(tb - 0.1, tgt if k else pool.lerp(tgt, 0.5), reach=reach - 3.0, height=hgt + 1.0,
               interp='BEZIER')
        lp.aim(tb + 0.06, tgt, reach=reach, height=hgt, interp='BEZIER')
    lp.intensity(W_NOW + 0.36, 1.0)
    # a soft warm key from the front left (the tabletop softbox) so the toys read; it dims as the hole takes over
    key = kit.area('sing.key', (-40.0, -70.0, 50.0), (6.0, -18.0, 3.0), power=70000.0, size=40.0, color='#FFE2C4',
                   coll=kit.collection('sing.lights'))
    key.data.specular_factor = 0.6
    H.key_value(key.data, 'energy', lambda t: 70000.0 * (1.0 - 0.55 * sm(t, W_SING, 43.6) - 0.2 * sm(t, 47.0, 49.3)),
                T0, T1)
    lp.intensity(43.0, 0.85)
    lp.intensity(44.0, 0.45)
    lp.intensity(45.5, 0.3)
    lp.intensity(47.5, 0.2)
    lp.intensity(49.2, 0.15)
    lp.intensity(49.45, 0.03)
    lp.aim(W_I - 0.5 / FPS, C + Vector((0, 0, -1.0)), reach=30.0, height=48.0, interp='CONSTANT')
    lp.aim(W_I, C + Vector((0, 0, -1.0)), reach=30.0, height=48.0, interp='BEZIER')
    lp.intensity(T1 + 0.2, 0.03)


# ------------------------------------------------------------------------------------------------ train


def train(S):
    coll = kit.collection('train')
    Mt = TR.mats()
    oval = TR.Oval(O, rc=15.0, a=9.0)
    S.oval = oval
    tr = TR.Train(coll, Mt)
    S.train = tr
    # the run: pick s0 so the loco's front reaches a piece joint (the start of the left curve's 4th piece) exactly
    # at T_LEAVE
    kw = dict(v0=24.0, t_acc=W_AND, t_leave=T_LEAVE, v1=165.0, t_end=T1 + 0.3, v2=240.0, p=2.0)
    probe = TR.Run(0.0, T0, **kw)
    D = probe.s(T_LEAVE)
    pieces = oval.pieces()
    j0 = 15
    gap = pieces[j0][0]
    k = round((-5.4 + D + tr.front - gap) / oval.L)
    s_gap = gap + k * oval.L
    s0 = s_gap - tr.front - D
    run = TR.Run(s0, T0, **kw)
    S.run = run
    S.s_gap = s_gap
    path = TR.Path(oval, C, s_leave=s_gap)
    S.path = path
    fx.log(f'singularity: s0={s0:.2f} gap={s_gap:.2f} (piece {j0}) spiral {path.sp_s[-1]:.0f} cm')

    def car_M(car, t):
        s = run.s(t)
        sc_ = s + car.offset
        v = run.v(t)
        # bank outward on the curves when fast (from the heading change over +-2 cm)
        _, ta = path.at(sc_ - 2.0)
        _, tb = path.at(sc_ + 2.0)
        a2, b2 = ta.to_2d(), tb.to_2d()
        turn = a2.angle_signed(b2, 0.0) if a2.length > 1e-6 and b2.length > 1e-6 else 0.0
        kappa = -turn / 4.0
        bank = max(-0.3, min(0.3, 0.00035 * v * v * kappa * (1 if sc_ <= s_gap else 0.4)))
        if sc_ <= s_gap:
            bank += 0.012 * math.sin(t * 23.0 + car.offset) * min(1.0, v / 120.0)
        stretch = None
        if sc_ > s_gap:
            r = path.radius(sc_)
            u = min(1.0, max(0.0, (7.0 - r) / (7.0 - RH * 0.8)))
            stretch = ((1.0 + 2.6 * u ** 1.4) * (1.0 - u ** 3), (1.0 - u) ** 1.5)
        return tr.car_matrix(car, s, path, bank=bank, stretch=stretch)
    S.car_M = car_M
    # when each car goes in (its centre crosses the horizon on the spiral)
    S.t_in = {}
    for car in tr.cars:
        t_in = None
        f = int(T_LEAVE * FPS)
        while f < int((T1 + 0.5) * FPS):
            t = f / FPS
            sc_ = run.s(t) + car.offset
            if sc_ > s_gap and path.radius(sc_) < RH * 1.05:
                t_in = t
                break
            f += 1
        S.t_in[car.name] = t_in
    fx.log('singularity: in ' + ', '.join(f'{k} {v and round(v, 3)}' for k, v in S.t_in.items()) +
           f' | s(T_LEAVE)={run.s(T_LEAVE):.1f}')
    fr = frames_between(T0 - 0.2, T1 + 0.2)
    if tm.SMOOTH:
        # 60 fps: key every output frame. On the spiral a car turns up to ~2 rad per 24 fps frame, and LINEAR keys
        # that far apart cut the chord (the in-between frames would jerk inward and back)
        fr = tm.out_frames(fr[0], fr[-1])
    ts = [f / FPS for f in fr]
    frf = [float(f) for f in fr]
    for car in tr.cars:
        H.key_matrices(car.root, ts, [car_M(car, t) for t in ts], frames=frf)
        for w, r, crank in car.wheels:
            H.fast_keys(w, 'rotation_euler', frf, [(run.s(t) + car.offset) / r for t in ts], index=1)
        t_in = S.t_in[car.name]
        if t_in is not None:
            for o in [car.root] + car.parts:
                fx.vis(o, None, t_in)
    # rods on the loco
    lo = tr.loco
    x1, x2 = lo.rod_x
    rc, za = lo.rod_r, lo.rod_z
    for side, cr, cn, xh in lo.rods:
        ys = side * 2.98
        alpha = 0.0 if side > 0 else math.pi / 2
        cl, cnl, cnr, xhl = [], [], [], []
        for t in ts:
            ph = run.s(t) / 1.45
            a = alpha - ph
            px, pz = rc * math.cos(a), rc * math.sin(a)
            cl.append(((x1 + x2) / 2 + px, ys, za + pz))
            P = Vector((x1 + px, ys + side * 0.05, za + pz))
            zc = 1.5
            dz = zc - P.z
            X = P.x + math.sqrt(max(0.0, 2.0 ** 2 - dz * dz))
            cnl.append(tuple(P))
            cnr.append(-math.atan2(dz, X - P.x))
            xhl.append((X, ys, zc))
        for i in range(3):
            H.fast_keys(cr, 'location', frf, [v[i] for v in cl], index=i)
            H.fast_keys(cn, 'location', frf, [v[i] for v in cnl], index=i)
            H.fast_keys(xh, 'location', frf, [v[i] for v in xhl], index=i)
        H.fast_keys(cn, 'rotation_euler', frf, cnr, index=1)
    H.fast_keys(lo.key, 'rotation_euler', frf, [-run.s(t) * 0.035 for t in ts], index=1)
    # the track: rattles from "optimizing", then rips up behind the caboose (a zipper) and spirals into the disc
    tcoll = kit.collection('track')
    S.pieces = TR.build_track(tcoll, oval, Mt)
    zipper(S)
    # steam: a puff on every beat, then every half beat, then every quarter as it races
    births = [b for b in BEATS if T0 - 0.6 <= b < W_AND]
    hb = tm.beat_period() / 2
    t = W_AND
    while t < 46.6:
        births.append(t)
        t += hb
    while t < T_LEAVE - 0.05:
        births.append(t)
        t += hb / 2
    chim = lambda t: car_M(tr.loco, t) @ tr.loco.chimney
    vel = lambda t: (chim(t + 0.02) - chim(t - 0.02)) / 0.04

    def pull(t, p):
        k = sm(t, 42.3, 44.0)
        d_ = C - p
        return d_.normalized() * (6.0 * k) if d_.length > 1e-3 else Vector()
    PR.puffs(kit.collection('steam'), births, chim, vel, pull=pull)


def zipper(S):
    """Track pieces: rest -> rattle (46.16 on) -> rip up behind the tail -> orbit in the disc."""
    run, oval, tr = S.run, S.oval, S.train
    L = oval.L
    j0 = 15
    n = len(S.pieces)
    S.peel = {}
    base = S.s_gap - S.pieces[j0]['sa'] - L          # unwrap offset of the zipper lap (the lap before the gap)
    for m in range(n):
        j = (j0 + m) % n
        sb = S.pieces[j]['sb'] + base + (L if j < j0 else 0.0)
        S.peel[j] = run.t_at(sb - tr.back) + 0.03     # the caboose's rear clears the piece's far end
    fx.log('singularity: zipper ' + ' '.join(f'{j}:{S.peel[j]:.2f}' for j in sorted(S.peel, key=S.peel.get)))
    S.fly = []        # everything that gets pulled into orbit: keyed in key_fly() once they're kept apart
    fr = frames_between(T0 - 0.2, T1 + 0.2)
    ts = [f / FPS for f in fr]
    frf = [float(f) for f in fr]
    for j, pc in enumerate(S.pieces):
        ob = pc['obj']
        Mr = pc['M']
        tp = S.peel[j]
        sa_p, _ = oval.at(pc['sa'])
        h = lambda *k, j=j: geo.hash01('piece', j, *k)
        head = pc['head']
        lat = Vector((-math.sin(head), math.cos(head), 0.0))
        lift_dur = 0.09

        def rest_M(t, Mr=Mr, h=h, tp=tp):
            # rattle: little hops and twists, stronger as the train gets faster
            k = sm(t, W_OPT - 0.3, W_OPT + 0.4) * (0.4 + 0.6 * sm(t, W_OPT, tp))
            if k <= 0:
                return Mr
            z = 0.22 * k * abs(math.sin(t * 31.0 + 7 * h('a'))) * (0.5 + 0.5 * math.sin(t * 7.3 + h('b') * 6))
            rx = 0.05 * k * math.sin(t * 27.0 + h('c') * 6)
            rz = 0.03 * k * math.sin(t * 19.0 + h('d') * 6)
            return Matrix.Translation((0, 0, z)) @ Mr @ Matrix.Rotation(rx, 4, 'X') @ Matrix.Rotation(rz, 4, 'Z')

        def lifted(t, Mr=Mr, tp=tp, sa_p=sa_p, lat=lat):
            u = sm(t, tp, tp + lift_dur)
            piv = Vector((sa_p.x, sa_p.y, 0.0))
            ang = math.radians(35) * u
            R = Matrix.Translation(piv) @ Matrix.Rotation(ang, 4, lat) @ Matrix.Translation(-piv)
            return Matrix.Translation((0, 0, 0.6 * u)) @ R @ Mr
        M_l = lifted(tp + lift_dur)
        rel = M_l.translation - C
        m = (j - j0) % n                    # peel order: neighbours get different heights, so they part as they rise
        orb = H.Orbit(rs=rel.xy.length, a_s=math.atan2(rel.y, rel.x), zs=rel.z, ts=tp + lift_dur,
                      dc=0.5 + 0.3 * h('dc'), r=11.5 + 3.0 * (m % 2) + 1.0 * h('r'), z=(m % 4) * 1.1 - 1.65 + (h('z') - 0.5) * 0.5,
                      K=1.2 + 1.2 * h('K'),
                      lift=2.0 + 2.0 * h('l'), collapse=lambda t: sm(t, 52.25, 52.52) ** 1.2,
                      fall=(tp + 0.45 + 0.35 * h('f'), tp + 0.95 + 0.35 * h('f')))
        ax = Vector((h('x') - 0.5, h('y') - 0.5, h('w') - 0.5)).normalized()
        spin = 2.5 + 3.0 * h('s')
        R_l = M_l.to_quaternion().to_matrix().to_4x4()
        mats = []
        for t in ts:
            if t < tp:
                mats.append(rest_M(t))
            elif t < tp + lift_dur:
                mats.append(lifted(t))
            else:
                p, R_, A_, u = orb.pos(t, C)
                tau = t - (tp + lift_dur)
                q = Matrix.Rotation(spin * tau * sm(tau, 0.0, 0.4), 4, ax) @ R_l
                s = max(1e-3, 1.0 - sm(t, 52.35, 52.5))
                if R_ < RH * 3.0:
                    s = min(s, max(1e-3, (R_ - RH * 0.8) / (RH * 2.2)))
                mats.append(Matrix.Translation(p) @ q @ Matrix.Scale(s, 4))
        S.fly.append(dict(ob=ob, frames=frf, mats=mats, free=tp, bins=3))
        fx.vis(ob, None, 52.5)


# ------------------------------------------------------------------------------------------------ the hole


def size_fn(t):
    """The hole's scale: a pinprick on "now", three beat-steps to full size, a breathing pulse, the collapse."""
    if t < W_NOW + 0.05:
        return 0.0
    s = 0.2 * sm(t, W_NOW + 0.05, W_NOW + 0.25)
    for k, tb in enumerate(GROW):
        target = (0.42, 0.72, 1.0)[k]
        prev = (0.2, 0.42, 0.72)[k]
        if t >= tb - 0.04:
            u = min(1.0, (t - tb + 0.04) / 0.2)
            back = 1 + 2.2 * (u - 1) ** 3 + 1.2 * (u - 1) ** 2     # ease-out-back
            s = prev + (target - prev) * back
    s *= 1.0 + 0.035 * beat_pulse(t, 0.1) * sm(t, 43.5, 44.0)
    s *= 1.0 - sm(t, 52.28, 52.5) ** 1.3
    return s


def flash(t):
    """The swallow flash: a sharp spike when the caboose goes in, decaying."""
    x = t - T_SWALLOW
    if x < -1.0 / FPS:
        return 0.0
    if x < 0:
        return 0.5
    return math.exp(-x / 0.12)


def hole(S):
    hc = kit.collection('hole')
    h = H.Hole(hc, C, rh=RH)
    S.hole = h
    h.open(size_fn, T0 - 0.1, T1 + 0.1)
    for o in (h.horizon, h.disc, h.halo, h.lens):
        fx.vis(o, W_NOW + 0.04, 52.5)
    H.key_value(h.sock['ring'], 'default_value', lambda t: sm(t, W_NOW + 0.05, W_NOW + 0.2) *
                (1.0 + 1.5 * beat_pulse(t, 0.08) * sm(t, 42.2, 43.6)) + 3.0 * flash(t), T0, T1)
    H.key_value(h.sock['halo'], 'default_value', lambda t: sm(t, GROW[0] - 0.05, GROW[2] + 0.3) *
                (1.0 + 0.3 * beat_pulse(t, 0.1)) + 2.0 * flash(t), T0, T1)
    H.key_value(h.sock['disc'], 'default_value', lambda t: sm(t, GROW[0], GROW[2] + 0.6) *
                (0.9 + 0.25 * beat_pulse(t, 0.12)) * (1 + 0.5 * sm(t, 45.5, 48.5)) + 2.5 * flash(t), T0, T1)
    H.key_value(h.sock['lens'], 'default_value', lambda t: 0.6 + 0.4 * sm(t, GROW[0], GROW[2]), T0, T1)
    H.key_value(h.sock['spin'], 'default_value', lambda t: 1.0 + 0.8 * sm(t, 45.5, 49.0), T0, T1)
    h.sock['dop'].default_value = -0.9
    for o, e in ((h.light, 42000.0), (h.under, 16000.0)):
        H.key_value(o.data, 'energy', lambda t, e=e: e * (sm(t, W_NOW + 0.05, W_NOW + 0.3) * 0.06 +
                                                          0.94 * sm(t, GROW[0], GROW[2] + 0.5)) *
                    (0.9 + 0.25 * beat_pulse(t, 0.12)) * (1 + 0.4 * sm(t, 45.5, 48.5)) * (1 - sm(t, 52.3, 52.5)) +
                    e * 6.0 * flash(t), T0, T1)
    # debris: dust and paper bits off the desk inside and around the loop, embers and dust born in the disc
    groups = [
        (0.28, (3,), (8.0, 30.0), (42.45, 47.8), True),
        (0.03, (6,), (6.0, 22.0), (43.0, 48.5), True),
        (0.30, (4,), (0.0, 0.0), (42.55, 45.5), False),
        (0.12, (0, 1, 2), (0.0, 0.0), (42.6, 45.0), False),
        (0.15, (3, 5), (0.0, 0.0), (42.45, 44.5), False),
    ]
    ob, mod, _ = H.debris('hole.debris', C, n=2400, spawn=groups, rh=RH, r_in=RH * 1.55, r_out=RH * 4.1)
    H.N.key_input(ob, mod, 'Collapse', 52.2, 0.0, interp='LINEAR')
    H.N.key_input(ob, mod, 'Collapse', 52.5, 1.0, interp='LINEAR')
    fx.vis(ob, None, 52.55)
    hero_debris(S)


def hero_debris(S):
    """Sticky notes peeling one by one off a pad inside the loop, paper clips and the pen: pulled up into orbit."""
    from pdoom.sets import props as SP
    coll = kit.collection('hole.hero')
    pad_c = Vector((16.5, -12.0, 0.0))
    SP.build_notes(coll, (pad_c.x, pad_c.y, 0.0), pad_yaw=-18.0)
    items = []
    cols = ['#F2D54B', '#F2D54B', '#F2A0B8', '#F2D54B', '#A6E3C8', '#F2D54B', '#F2A0B8']
    for i, col in enumerate(cols):
        n = PR.note_obj(coll, f'note.fly{i}', col, size=7.6, curl=0.25 + 0.1 * (i % 3))
        z = 0.93 + 0.02 * i
        yaw = math.radians(-18.0 + (geo.hash01('n', i) - 0.5) * 6)
        M0 = Matrix.Translation((pad_c.x, pad_c.y, z)) @ Matrix.Rotation(yaw, 4, 'Z')
        # the notes and the pen share one ring (one radius, so one angular speed: they never overtake each other),
        # in evenly spaced slots, heights alternating above / below the disc
        zl = (0.9 + 0.3 * (i % 3)) * (1 if i % 2 == 0 else -1)
        items.append((n, M0, 42.7 + i * 0.42, 0.9, 9.5, zl, (8, i)))
    for i in range(6):
        a = 2 * math.pi * geo.hash01('clip', i)
        rr = 5.5 + 5.0 * geo.hash01('clipr', i)
        p = O + Vector((math.cos(a) * rr, math.sin(a) * rr * 0.6, 0.05))
        cl = clips.clip(f'clip.fly{i}', loc=tuple(p), rz=geo.hash01('rz', i) * 360, lod=0, coll=coll)
        # the clips: an inner ring of their own, evenly spaced
        items.append((cl, cl.matrix_basis.copy(), 43.2 + 0.55 * i, 0.7, 5.6, 0.45 * (1 if i % 2 else -1), (6, i)))
    pen = SP.build_pen(coll, (1.0, -21.0, 0.0), yaw_deg=24.0)
    bpy.context.view_layer.update()
    items.append((pen.root, pen.root.matrix_basis.copy(), 45.3, 1.0, 9.5, -1.3, (8, 7)))   # the pen: the ring's last slot
    fr = frames_between(T0 - 0.2, T1 + 0.2)
    ts = [f / FPS for f in fr]
    base = {}
    for k, (ob, M0, t_cap, dc, r_orb, z_orb, slot) in enumerate(items):
        rel = M0.translation - C
        h = lambda *q, k=k: geo.hash01('hero', k, *q)
        # the extra unwind angle K puts the item in its slot: phase th0 = a_s - om (t_cap - TREF) + K
        a_s = math.atan2(rel.y, rel.x)
        ph = a_s - H.omega(r_orb) * (t_cap - H.TREF)
        K = 1.5 + h('K')
        nsl, isl = slot
        if nsl not in base:
            base[nsl] = ph + K
        K = 1.0 + (base[nsl] + 2 * math.pi * isl / nsl - ph - 1.0) % (2 * math.pi)
        orb = H.Orbit(rs=rel.xy.length, a_s=a_s, zs=rel.z, ts=t_cap, dc=dc, r=r_orb,
                      z=z_orb, K=K, lift=1.5 + 1.5 * h('l'),
                      collapse=lambda t: sm(t, 52.22, 52.5) ** 1.2,
                      fall=None if k in (1, 4, 9, 13) else (max(t_cap + dc + 0.3, 48.0 + 1.3 * h('f')),
                                                             max(t_cap + dc + 0.3, 48.0 + 1.3 * h('f')) + 0.55))
        ax = Vector((h('x') - 0.5, h('y') - 0.5, h('w') - 0.5)).normalized()
        spin = 3.0 + 4.0 * h('s')
        R0 = M0.to_quaternion().to_matrix().to_4x4()
        mats = []
        for t in ts:
            if t <= t_cap:
                wob = sm(t, t_cap - 0.5, t_cap) * 0.08 * math.sin(t * 40 + k)
                mats.append(M0 @ Matrix.Rotation(wob, 4, 'X'))
                continue
            p, R_, A_, u = orb.pos(t, C)
            tau = t - t_cap
            q = Matrix.Rotation(spin * tau * sm(tau, 0.0, 0.5), 4, ax) @ R0
            s = 1.0
            if R_ < RH * 2.2:
                s = max(1e-3, (R_ - RH * 0.9) / (RH * 1.3))
            mats.append(Matrix.Translation(p) @ q @ Matrix.Scale(max(1e-3, s), 4))
        S.fly.append(dict(ob=ob, frames=[float(f) for f in fr], mats=mats, free=t_cap, bins=1))
        for o in geo.descendants(ob):
            fx.vis(o, None, 52.5)
    SEP.separate(S.fly, C, label='orbiters', iters=16, max_push=5.0, max_total=6.0)
    key_fly(S)


def key_fly(S):
    for it in S.fly:
        H.key_matrices(it['ob'], None, it['mats'], frames=it['frames'])
    S.fly = []


# ------------------------------------------------------------------------------------------------ characters


R0 = Vector((-26.5, -27.5, 0.0))
R1 = Vector((-29.5, -31.5, 0.0))


def yaw_to(p, q):
    dv = Vector(q) - Vector(p)
    return math.degrees(math.atan2(dv.x, -dv.y))


def wrist_for(r, side, W, *, fingers, palm, compat=(0.0, 0.0, 0.0)):
    """The researcher's wrist angles (deg) that point the mitten's fingers along `fingers` with its inner face (the
    palm: toward the thigh at rest) toward `palm`, both in spine space, for the wrist target W. The rig turns the
    mitten by the wrist angles in the forearm's frame of the old IK chain (researcher.clear_arm), so solve that."""
    from pdoom.chars import researcher as RS
    f = Vector(fingers).normalized()
    n = Vector(palm)
    n = (n - f * n.dot(f)).normalized()
    inner = Vector((-1.0 if side == 'L' else 1.0, 0.0, 0.0))     # rest: fingers down (-z), palm toward the body
    down = Vector((0.0, 0.0, -1.0))
    rest = Matrix((inner, down.cross(inner), down)).transposed()
    want = Matrix((n, f.cross(n), f)).transposed()
    R_hand = want @ rest.transposed()
    Eo, Wo, no = RS._old_chain(side, Vector(W), r._pole_a[side])
    F = RS._forearm_rot(side, RS.SH[side], Eo, Wo, no)
    from mathutils import Euler
    e = (F.transposed() @ R_hand).to_euler('XYZ', Euler(tuple(math.radians(a) for a in compat), 'XYZ'))
    return tuple(math.degrees(a) for a in e)


def characters(S):
    tr = S.train
    # Clawd in the tub (his rig rides the tub's seat Empty), facing forward (+x of the car)
    c = chars.Clawd(kit.collection('clawd'), name='clawd', loc=(0, 0, 0), yaw=90.0, glow_light=False)
    c.rig.parent = tr.tub.seat
    c.rig.matrix_parent_inverse = Matrix.Identity(4)
    c.rig.location = (0, 0, 0)
    c.no_gait(0.0, 999.0)
    for i in range(8):
        c.T[f'leg{i}'].set(0.0, (-30.0 if i % 2 == 0 else 30.0, 0.0, 0.0), 0.0)
    c.T['hips.loc'].set(0.0, (0.0, 0.0, -0.5), 0.0)
    S.clawd = c
    if S.t_in.get('tub'):
        c.visible(None, S.t_in['tub'])
    c.eyes(T0 - 0.3, 'happy')
    c.arms(T0 - 0.3, (35, 30, 0), dur=0.0)                        # elbows on the rim
    c.dance(T0, W_NOW - 0.05, 'bounce', amount=0.55)
    c.look(38.9, None)
    c.wave(39.1, 40.2, side='R')
    c.eyes(40.5, 'open')
    # "now": he sees it (the hole is on the train's left)
    c.T['eyes.look'].set(W_NOW + 0.1, (-0.36, 0.05), 0.08)
    c.eyes(W_NOW + 0.08, 'surprised')
    c.T['body.rot'].set(W_NOW + 0.25, (0.0, 0.0, 28.0), 0.2)
    c.eyes(GROW[1], 'star')
    c.lid(GROW[1] + 0.05, 0.35, dur=0.12)
    c.arms(GROW[2], 'cheer', dur=0.18)
    c.dance(43.5, W_AND, 'bounce', amount=0.8)
    # accelerating: the roller coaster
    c.T['body.rot'].set(W_AND + 0.1, (0.0, 0.0, 0.0), 0.25)
    c.T['eyes.look'].set(W_AND + 0.1, (0.0, 0.0), 0.1)
    c.eyes(W_AND + 0.05, 'happy')
    c.arms(W_AND + 0.1, 'high', dur=0.2)
    c.lid(W_AND + 0.2, 0.22, dur=0.2)
    c.eyes(W_OPT, 'star')
    c.T['body.rot'].set(W_OPT + 0.2, (-10.0, 0.0, 0.0), 0.3)
    c.lid(W_ACC, 0.3, dur=0.12)
    c.lid(T_LEAVE + 0.1, 0.12, dur=0.1)
    c.eyes(T_LEAVE - 0.02, 'surprised')
    c.arms(T_LEAVE + 0.05, 'cheer', dur=0.08)
    c.eyes(T_LEAVE + 0.3, 'star')
    c.T['body.rot'].set(T_LEAVE + 0.3, (-6.0, 0.0, 8.0), 0.2)
    c.timing(W_AND, T1, 'ones')
    # the researcher: proud of his stable run, then the hole
    r = chars.Researcher(kit.collection('researcher'), name='researcher', loc=tuple(R0), yaw=yaw_to(R0, O))
    S.researcher = r
    r.pose(T0 - 0.3, 'proud', dur=0.0)
    r.face(T0 - 0.3, 'proud')
    for k, t in enumerate(tm.beats_between(T0, W_BUT)):
        if k % 2 == 0:
            r.nod(t, n=1, amount=7.0, every=0.3)
    for t in (T0 - 0.2, 38.9, 39.5, 40.1, 40.7, 41.2):
        r.look(t, S.car_M(tr.loco, t + 0.2).translation + Vector((0, 0, 3.0)), dur=0.3, turn=0.0)
    r.face(W_NOW + 0.05, 'nervous')
    r.look(W_NOW + 0.2, C, dur=0.2, turn=0.0)
    r.pose(W_SING + 0.15, 'gasp', dur=0.2)
    r.face(W_SING + 0.1, 'shock')
    r.pose(43.3, 'back_away', dur=0.3)
    r.walk(43.35, 43.95, [(R1.x, R1.y)], face='back')
    r.turn(44.05, yaw_to(R1, C), dur=0.2)
    r.face(44.05, 'awe')
    r.pose(44.1, 'stand', dur=0.3, face=False)
    r.look(44.15, C, dur=0.2, turn=0.0)
    r.glasses_glint(44.55, '#FFB070', dur=0.4, strength=10.0)
    r.pose(45.3, 'nervous', dur=0.25)
    r.face(45.3, 'nervous')
    r.fidget(45.4, 46.1, 1.0)
    r.pose(46.25, 'cower', dur=0.25)
    r.face(46.25, 'scared')
    r.look(46.3, C, dur=0.2, turn=0.0)
    r.face(T_LEAVE + 0.05, 'shock')
    r.jump(T_LEAVE + 0.02, height=1.2, dur=0.36)
    r.look(48.3, C + Vector((0, 0, 1)), dur=0.2, turn=0.0)
    r.face(T_SWALLOW + 0.02, 'wince')
    r.pose(T_SWALLOW + 0.05, 'back_away', dur=0.15)
    # "I feel my atoms rearranging": he turns his back on the glare and raises his right hand to look at it
    away = yaw_to(R1, C) + 180.0
    S.yaw_away = away
    r.turn(49.8, away, dur=0.35)
    r.pose(49.75, 'stand', dur=0.3, face=False)
    r.face(W_I + 0.05, 'nervous')
    # the hand comes up out to his right at chin height, fingers up, the palm turned to his face, and he turns his
    # head to look at it. (The old target sat beyond the arm's reach in front of his chin, with the -150 deg
    # hand-to-face wrist fold: a fist jammed against his chin.) It swings out and forward first (a waypoint), so the
    # mitten never sweeps across the coat front, and the wrist turns up on the way.
    W_LOOK = (-2.8, -1.8, 7.75)
    W_WAY = (-2.45, -2.5, 5.9)
    wr_way = wrist_for(r, 'R', W_WAY, fingers=(-0.35, -1.0, 0.55), palm=(1.0, 0.0, 0.4), compat=(0.0, 0.0, 0.0))
    wr_look = wrist_for(r, 'R', W_LOOK, fingers=(-0.15, -0.25, 1.0), palm=(1.0, 0.1, 0.5), compat=wr_way)
    fx.log(f'singularity: look_hand wrist way {tuple(round(a) for a in wr_way)} look {tuple(round(a) for a in wr_look)}')
    r.T['hand.R'].set(49.97, W_WAY, 0.22)
    r.T['wrist.R'].set(49.97, wr_way, 0.22)
    r._ev(49.97)
    chars.POSES['look_hand'] = dict(spine=(3, 0, 0), head=(14, 2, -40), hands=(None, W_LOOK),
                                    wrist=(None, wr_look), face='awe')
    r.pose(T_HOLD - 0.05, 'look_hand', dur=0.18)
    r.face(T_VOX + 0.02, 'shock')
    r.T['head'].set(50.9, (6.0, 8.0, -26.0), 0.25)           # follows the stream a little (head only)
    r.face(W_REARR + 0.05, 'awe')
    r.T['head'].set(51.7, (4.0, 3.0, -16.0), 0.3)
    r.face(52.0, 'nervous')
    r.T['head'].set(52.05, (8.0, -6.0, -10.0), 0.12)
    # released: the hole winks out behind him; he spins round to it
    r.timing(52.3, T1 + 0.2, 'ones')
    r.face(T_COLLAPSE + 0.02, 'shock')
    r.pose(T_COLLAPSE + 0.1, 'gasp', dur=0.15, face=False)
    r.T['head'].set(T_COLLAPSE + 0.2, (-4.0, 0.0, -50.0), 0.18)
    r.T['spine'].set(T_COLLAPSE + 0.24, (0.0, 0.0, -24.0), 0.2)


# ------------------------------------------------------------------------------------------------ the globe


def globe(S):
    """The hole winks out in a flash and leaves the snow globe of the next scene (sydney_globe's model, imported
    read-only; a plain stand-in if that module isn't there)."""
    gc = kit.collection('globe')
    tc = T_COLLAPSE
    try:
        from scenes import sydney_globe as SG
        D = Vector((math.cos(math.radians(190.0)), math.sin(math.radians(190.0)), 0.0))
        g = SG.Globe(gc, GLOBE_O, D)
        g.water.hide_render = True

        def swirl(t):
            return 0.55 + 3.2 * math.exp(-max(0.0, t - tc) / 0.3)

        def lift(t):
            return 0.8 + 0.2 * math.exp(-max(0.0, t - tc) / 0.35)
        SG.Snow(g, count=950, seed=5, swirl=swirl, lift=lift, t_range=(tc - 0.1, T1 + 0.3), t_burst=60.235)
        root = g.root
    except Exception as e:  # noqa: BLE001
        fx.log(f'singularity: sydney_globe unavailable ({e!r}); stand-in globe')
        root = geo.empty('globe.root', tuple(GLOBE_O), gc, 3.0)
        gl = kit.sphere('globe.glass', 7.0, (0, 0, 8.8), coll=gc, subdiv=5)
        gl.data.materials.append(kit.mat('globe.stand', '#DDE8F0', rough=0.02, transmission=1.0, ior=1.2))
        geo.attach(gl, root, (0, 0, 8.8))
    bpy.context.view_layer.update()

    def gscale(t):          # it forms inside the flash: a quick pop with a springy overshoot
        if t < tc - 0.5 / FPS:
            return 1e-3
        x = t - tc
        return 1.0 - 0.45 * math.exp(-x / 0.05) * math.cos(x * 38.0)
    H.key_vec(root, 'scale', lambda t: (gscale(t),) * 3, tc - 0.2, T1 + 0.2)
    for o in list(gc.all_objects):
        if o is None:                                         # (a stale entry: seen once on the review machine)
            continue
        if o.type != 'EMPTY' and not o.hide_render:          # (the still water stays hidden, as in sydney)
            fx.vis(o, tc - 0.5 / FPS, None)
    # a pink shimmer inside as it forms (Sydney's magic: revision 2 has her outside it, and sydney opens on the
    # empty globe), dying away by the cut, and the collapse flash
    lc = kit.collection('sing.lights')
    gl_l = kit.point('globe.glow', tuple(GLOBE_O + Vector((0, 0, 6.9))), power=0.0, radius=1.5, color='#FF9FD0',
                     coll=lc)
    gl_l.data.specular_factor = 0.0
    H.key_value(gl_l.data, 'energy', lambda t: 3500.0 * sm(t, tc + 0.02, tc + 0.15) * (1.0 - sm(t, tc + 0.18, T1 - 0.02)),
                tc - 0.2, T1 + 0.2)
    fl = kit.point('collapse.flash', tuple(C), power=0.0, radius=1.0, color='#FFE6C0', coll=lc)
    H.key_value(fl.data, 'energy', lambda t: 260000.0 * (math.exp(-max(0.0, t - tc) / 0.07) if t >= tc - 0.5 / FPS
                                                         else 0.0), tc - 0.3, T1)
    ball = kit.sphere('collapse.ball', 1.0, tuple(C), coll=lc, subdiv=3)
    ball.data.materials.append(H.heat_material('collapse.ball', '#FFFFFF', emit='#FFF1D8', emit_k=0.0,
                                               base_emit=60.0))
    ball.visible_shadow = False
    H.key_vec(ball, 'scale', lambda t: (max(1e-3, 2.6 * sm(t, tc - 0.5 / FPS, tc + 0.03) *
                                            math.exp(-max(0.0, t - tc - 0.03) / 0.05)),) * 3, tc - 0.2, tc + 0.4)
    fx.vis(ball, tc - 1.0 / FPS, tc + 0.3)
    # the lamp springs back to its pool, and comes back on full
    lp = S.d.lamp
    lp.aim(tc + 0.02, C + Vector((0, 0, -1.0)), reach=30.0, height=48.0, interp='BEZIER')
    lp.aim(tc + 0.2, S.d.anchors['lampPool'] + Vector((-4.0, -3.0, 0.0)), reach=31.0, height=43.0, interp='BEZIER')
    lp.aim(tc + 0.36, S.d.anchors['lampPool'], interp='BEZIER')
    lp.intensity(tc + 0.02, 0.03)
    lp.intensity(tc + 0.08, 1.1)
    lp.intensity(tc + 0.2, 1.0)


# ------------------------------------------------------------------------------------------------ cameras


def cameras(S):
    tr = S.train
    LM = lambda t: S.car_M(tr.loco, t)
    TM = lambda t: S.car_M(tr.tub, t)
    V = Vector
    # S1 tracking beside the loco: a fixed world offset from the loco (front right, low)
    run, path = S.run, S.path

    def s1_s(t):              # which point of the train the shot looks at: the loco, easing back to the tub
        # (revision 2: tracks the tender and the tub, whose blocks carry "we had a" and "stable", with the loco's cab at
        # the edge, drifting back only a little: a camera that slides along the train blurs the blocks on it)
        return run.s(t) - 12.5 - 3.5 * sm(t, 38.4, 39.8)

    def s1_pt(t):
        p, _ = path.at(s1_s(t))
        return p
    Cam('loco', T0, 39.781, lambda t: s1_pt(t) + V((9.5, -25.0, 3.6)),
        lambda t: s1_pt(t) + V((-2.5, 0.0, 6.4)), lens=36, fstop=8,
        focus_fn=lambda t: s1_pt(t) + V((0.0, -3.5, 3.5)))
    # S2 wide establishing
    Cam('stable', 39.781, W_BUT, lambda t: V((-1.0, -86.0, 31.0)).lerp(V((-0.5, -78.0, 27.5)), sm(t, 39.7, 41.4)),
        lambda t: V((-1.0, -12.0, 5.0)), lens=35, fstop=8, focus_fn=lambda t: V((-5.0, -20.0, 4.0)))
    # S3 low across the loop at the pinprick
    Cam('now', W_BUT, W_SING, lambda t: V((4.0, -58.0, 6.8)).lerp(V((4.6, -53.0, 6.9)), sm(t, 41.3, 42.3)),
        lambda t: C + V((-0.5, 0.0, 0.2)), lens=50, fstop=8, focus_fn=lambda t: C)
    # S4 hero wide: push in and crane down
    Cam('sing', W_SING, W_BEGUN, lambda t: V((30.0, -58.0, 11.5)).lerp(V((21.0, -44.0, 7.0)), sm(t, 42.2, 44.2)),
        lambda t: C + V((-4.0, 0.0, -1.5)).lerp(V((-1.5, 0.0, 0.0)), sm(t, 42.2, 44.2)), lens=28, fstop=8,
        focus_fn=lambda t: C)
    # S5 the researcher's face
    r = S.researcher
    eyes = r.anchor(44.6, 'eyes')
    to_c = (C - eyes)
    to_c.z = 0
    to_c.normalize()
    side = V((-to_c.y, to_c.x, 0.0))
    p5a = eyes + to_c * 12.0 - side * 9.0 + V((0, 0, -1.0))
    p5b = eyes + to_c * 10.5 - side * 7.8 + V((0, 0, -0.8))
    Cam('begun', W_BEGUN, W_AND, lambda t: p5a.lerp(p5b, sm(t, 44.0, 45.1)), lambda t: eyes + V((0, 0, -0.4)),
        lens=65, fstop=5.6, focus_fn=lambda t: r.anchor(t, 'eyes'))
    # S6 on-ride: from the tender, looking back at Clawd
    TD = lambda t: S.car_M(tr.tender, t)
    Cam('chase', W_AND, W_OPT, lambda t: TD(t) @ V((1.0, -2.0, 10.5)), lambda t: TM(t) @ V((0.0, 0.0, 5.2)),
        lens=24, fstop=8, focus_fn=lambda t: TM(t) @ V((2.0, 0.0, 7.0)))
    # S7 rail level at the left curve, panning with the loco as it thunders past
    p7 = V((-27.0, -6.0, 2.6))
    Cam('optim', W_OPT, W_ACC, lambda t: p7, lambda t: LM(t + 0.03).translation + V((0, 0, 3.5)), lens=28, fstop=8,
        focus_fn=lambda t: LM(t).translation + V((0, 0, 3.0)))
    # S8 rear-facing chase just behind the caboose, low: the track rips up behind it like a zipper
    Cam('rip', W_ACC, T_LEAVE, lambda t: O + V((-14.0, -46.0, 56.0)) + V((2.0, 4.0, -5.0)) * sm(t, 47.2, 48.0),
        lambda t: O + V((0.0, -1.0, 0.0)), lens=30, fstop=11, focus_fn=lambda t: O + V((0, -4.0, 3.0)), whip=0.7)
    # S10 the leap: low near the researcher, looking up the track at the gap
    gp, _ = S.oval.at(S.s_gap)
    p10a, p10b = V((-9.0, -54.0, 4.2)), V((-7.0, -50.0, 4.6))
    Cam('leap', T_LEAVE, 48.417, lambda t: p10a.lerp(p10b, sm(t, 47.9, 48.5)),
        lambda t: (gp + V((0, 0, 4.5))).lerp(C, 0.35 + 0.35 * sm(t, 47.95, 48.4)), lens=26, fstop=8,
        focus_fn=lambda t: LM(t).translation.lerp(C, 0.5), whip=-0.8)

    # S11 orbiting with the tub: Clawd close
    def s11_loc(t):
        rel = TM(t).translation - C
        a = math.atan2(rel.y, rel.x) + 0.55
        rr = rel.xy.length + 15.0
        return V((C.x + rr * math.cos(a), C.y + rr * math.sin(a), C.z + 9.5))
    Cam('orbit', 48.417, 48.872, s11_loc, lambda t: TM(t) @ V((0.5, 0.0, 7.0)), lens=40, fstop=8, whip=0.75,
        focus_fn=lambda t: TM(t) @ V((0.0, -1.0, 6.0)))
    # S12 wide on the hole as the ring of cars goes in
    Cam('swallow', 48.872, W_I, lambda t: C + V((-4.0, -40.0, 16.0)).lerp(V((-3.0, -34.0, 13.0)), sm(t, 48.8, 49.6)),
        lambda t: C + V((0.0, 0.0, -1.0)), lens=40, fstop=8, focus_fn=lambda t: C)
    # S13 / S14: in front of him (his back to the hole), the hole just past his raised right hand
    eyes = r.anchor(50.6, 'eyes')
    hand = r.anchor(50.6, 'hand.R')
    tow = (C - R1)
    tow.z = 0
    tow.normalize()
    away = -tow
    left = V((tow.y, -tow.x, 0.0))              # his left (he faces away from the hole)
    mid = eyes.lerp(hand, 0.45)
    p13a = R1 + away * 23.0 - left * 6.0 + V((0, 0, 8.4))
    p13b = R1 + away * 20.5 - left * 5.4 + V((0, 0, 8.6))
    Cam('feel', W_I, W_ATOMS, lambda t: p13a.lerp(p13b, sm(t, 49.5, 50.6)), lambda t: mid + V((0, 0, -0.9)),
        lens=50, fstop=16, focus_fn=lambda t: hand.lerp(eyes, 0.3))
    p14a = R1 + away * 21.0 - left * 5.2 + V((0, 0, 8.4))
    p14b = R1 + away * 18.5 - left * 4.8 + V((0, 0, 8.6))
    g_c = GLOBE_O + V((0, 0, 8.8))

    def f14(t):
        k = sm(t, T_COLLAPSE + 0.03, T_COLLAPSE + 0.3)
        return (hand.lerp(eyes, 0.25) + (C - hand).normalized() * 0.8).lerp(g_c, k)
    Cam('rearr', W_ATOMS, T1, lambda t: p14a.lerp(p14b, sm(t, 50.4, 52.9)),
        lambda t: mid.lerp(mid.lerp(g_c, 0.42), sm(t, T_COLLAPSE + 0.05, T1)) + V((0, 0, -0.3)), lens=58,
        fstop=22, focus_fn=f14, fstop_fn=lambda t: 22.0 - 14.0 * sm(t, T_COLLAPSE - 0.1, T_COLLAPSE + 0.2))
    # the cubes stream across the frame toward the hole's side (and a little into depth), so they stay readable
    vd = (mid - p14b).normalized()
    to_h = C - hand
    lat = to_h - vd * to_h.dot(vd)
    S.pull = (lat.normalized() * 0.85 + vd * 0.35 + V((0, 0, 0.3))).normalized()
    bpy.context.scene.camera = Cam.ALL[0].cam
    sc = bpy.context.scene
    for c in Cam.ALL:
        sh = 0.2 if c.name in ('optim', 'rip', 'leap', 'swallow') else 0.5
        geo.keyp(sc.render, 'motion_blur_shutter', c.t0 - 0.5 / FPS, sh, interp='CONSTANT')


def hole_follow(S):
    """The billboard faces whichever camera is live; its edge-on arches fade as the camera rises above the disc."""
    h = S.hole
    fol = kit.empty('hole.camfollow', (0, 0, 0), kit.collection('hole'))
    fr = frames_between(T0 - 0.1, T1 + 0.1)

    def edge_of(p):
        dv = p - C
        el = abs(math.atan2(dv.z, max(1e-6, dv.xy.length)))
        return 1.0 - sm(el, 0.12, 0.9)
    # two keys per output frame, either side of it, from the camera that renders that frame: motion blur on a cut
    # frame never mixes the billboard's orientation (or its edge fade) for two cameras
    if tm.SMOOTH:
        # 60 fps: keys at x -+ 0.15 scene frames (the exposure is +-0.09), LINEAR, so the edge fade moves on every
        # output frame instead of stepping on the 24 fps grid; the gap between frames carries any cut
        xs = tm.out_frames(fr[0], fr[-1])
        dfs = (-0.15, 0.15)
    else:
        xs = [float(f) for f in fr]
        dfs = (-0.49, 0.49)
    kf, kp, ke = [], [], []
    for x in xs:
        cm = live_cam(x / FPS)
        for df in dfs:
            kf.append(x + df)
            p = cm.at((x + df) / FPS)
            kp.append(p)
            ke.append(edge_of(p))
    for i in range(3):
        H.fast_keys(fol, 'location', kf, [p[i] for p in kp], index=i, interp='LINEAR')
    h.face(fol)
    sock = h.sock['edge']
    if tm.SMOOTH:
        H.fast_keys(sock.id_data, sock.path_from_id('default_value'), kf, ke, interp='LINEAR')
    else:
        frf = [float(f) for f in fr]
        H.fast_keys(sock.id_data, sock.path_from_id('default_value'), frf,
                    [edge_of(live_cam(f / FPS).at(f / FPS)) for f in fr], interp='CONSTANT')
