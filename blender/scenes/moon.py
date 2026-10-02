"""moon · 62.053-67.507 · "(basilisk) boom / NVDA to the moon / The Omega Point's coming soon / One E thirty FLOPs
(a second)"

The desk right after the snow globe burst (its base, shards, the puddle and the landed snow stay). The USB cable
that stirred at the end of `sydney` rears up as the basilisk (moon_basilisk.py), plugs itself into a stack of four
graphics cards (moon_gpu.py) and powers them up letter by letter; the stack launches like a rocket, its smoke trail
and a glowing green line drawing a rising stock chart up to a paper moon hanging from the ceiling (moon_props.py).
Every line in the frame is pulled into one point of light. A brass odometer rolls to 1E30.

Revision 2: Sydney starts heartbroken (she trapped the researcher in `sydney`; the globe's front faced her, at 245
deg). Lyrics in the picture: line 18 on the lyric stand (BASILISK in red-lit blocks like its LED eyes, BOOM in cast
brass); N-V-D-A are the rocket's four cards lighting up; "to", "the", "moon" hang on threads along the rocket's climb
as green light-up blocks, each lighting as it is sung; "The Omega Point's coming soon" floats under the point in
light-up blocks, word by word; "One E thirty" is the odometer's wheels and FLOPS lights up on its brass plate.

Shot list (song seconds; cuts snapped to even frames, the puppets pose on twos):
 M1 62.053-62.500  boom      45 mm low, looking up: the basilisk rears out of the cable (overshoots on "boom"), its
                             USB-A jaws open and hiss, a forked copper tongue flicks, red LED eyes flare. Camera
                             shake on the downbeat. The researcher cowers behind it.
 M2 62.500-63.333  NVDA      50 mm on the card stack: the basilisk strikes and plugs into the N card's port on "N"
                             (62.54); power runs across the stack: N, V (62.70), D (62.94), A (63.216) light up in
                             NVIDIA green, the fans spin up, the engine bell glows and fire catches under it.
 M3 63.333-64.083  launch    wide from the front, craning up: on "to" the basilisk yanks out (sparks) and the stack
                             lifts off on a flame, zig-zagging up like a stock chart; the smoke trail and a glowing
                             green line draw the chart behind it, up to the paper moon; it sticks in the moon's eye on
                             the downbeat (63.871), the moon swings on its thread.
 M4 64.083-65.667  omega     40 mm on the moon: a chart grid draws in ("The"), light streaks shoot in ("Omega"),
                             the lamp dims, and every line - the chart, the grid, the streaks - is reeled into one
                             point of light that flares ("Point's"), with star streaks; it pulses on "coming" and
                             "soon".
 M5 65.667-67.507  1E30      85 mm on the odometer: the exponent wheels roll faster and faster; the mantissa wheel,
                             spinning, clunks onto 1 on "One" (66.22), the E flap flips on "E" (66.42), the exponent
                             slams onto 30 on "thirty" (66.75), and on "FLOPs" (66.98) the counter jumps and its bulb
                             lights. Slow push in to the cut.
"""
import math
import os

import bpy
import numpy as np
from mathutils import Matrix, Vector

from pdoom import chars, fx, kit
from pdoom import lyrics as ly
from pdoom import timing as tm
from pdoom.fx import _nodes as NN
from pdoom.fx import fracture, particles, smoke
from pdoom.fx import materials as FXM
from pdoom.sets import build_desk, geo, phys_fstop

from scenes import sydney_globe as SG
from scenes.boot_common import Cam, flash_light, shake
from scenes.moon_basilisk import Basilisk, _env, extra_cables, stir
from scenes.moon_gpu import Rocket
from scenes.moon_props import Lines, Odometer, PaperMoon, exhaust_puffs

FPS = tm.FPS


def ct(t: float) -> float:
    return round(t * FPS / 2) * 2 / FPS


T0, TEND = 62.053, 67.507
W_NVDA = tm.word(19, 'NVDA')
T_N, T_V, T_D, T_A = (tm.syl(W_NVDA, i) for i in range(4))      # 62.54 62.70 62.94 63.216
T_TO = tm.word(19, 'to')['start']                                 # 63.36
T_HIT = 63.871                                                    # downbeat: the rocket reaches the moon
T_THE, T_OMEGA = tm.word(20, 'The')['start'], tm.word(20, 'Omega')['start']
T_POINT, T_COMING, T_SOON = (tm.word(20, w)['start'] for w in ("Point's", 'coming', 'soon'))
T_ONE, T_E, T_THIRTY, T_FLOPS = (tm.word(21, w)['start'] for w in ('One', 'E', 'thirty', 'FLOPs'))
T_M2, T_M3, T_M4, T_M5 = ct(T_N), ct(T_TO), ct(T_THE), ct(65.689)
T_LIFT = T_TO + 0.04                                              # lifts off once the basilisk has yanked out

# the same layout as `sydney` (the globe's "front" faced Sydney, stuck on its glass at 245 deg)
G = Vector((2.0, -8.0, 0.0))
D = Vector((math.cos(math.radians(190.0)), math.sin(math.radians(190.0)), 0.0))
S_DIR = Vector((math.cos(math.radians(245.0)), math.sin(math.radians(245.0)), 0.0))
U = Vector((math.cos(math.radians(250.0)), math.sin(math.radians(250.0)), 0.0))
SYD = G + U * 14.5                                  # where the wave left Sydney
RES = G + D * 14.7                                  # where the researcher backed off to
RP = Vector((-19.0, -24.0, 0.0))                    # the launch pad
MOON = Vector((31.0, -6.0, 57.0))                   # the paper moon's centre
OMEGA = MOON + Vector((13.0, 3.0, 11.0))            # the Omega Point


def yaw_of(v) -> float:
    return math.degrees(math.atan2(v.x, -v.y))


def remains(d):
    """What the burst left: the globe's base, hill and pines, the landed snow, the shards and the puddle."""
    gc = kit.collection('globe')
    globe = SG.Globe(gc, G, S_DIR)
    globe.water.hide_render = True
    SG.make_snow(globe)                              # the same flakes as `sydney`: they are all landed by now
    bpy.context.view_layer.update()
    pieces = fracture.fracture(globe.glass, 64, seed=17, mode='surface', swap_at=T0 - 1.0)
    rng = np.random.default_rng(23)
    C = globe.C
    for p in pieces:
        c = p.matrix_basis.translation.copy()
        radial = (c - C).normalized()
        R = radial.rotation_difference(Vector((0, 0, 1))).to_matrix().to_4x4()
        spin = Matrix.Rotation(rng.uniform(0, 2 * math.pi), 4, 'Z')
        ang = rng.uniform(0, 2 * math.pi)
        rr = rng.uniform(8.0, 24.0)
        if rng.uniform() < 0.55:                    # most of them went with the water, to the front left
            ang = math.radians(250.0) + rng.normal(0, 0.6)
        pos = G + Vector((math.cos(ang) * rr, math.sin(ang) * rr, 0.0))
        Mr = spin @ R
        zmin = min((Mr @ v.co).z for v in p.data.vertices)
        p.matrix_basis = Matrix.Translation((pos.x, pos.y, 0.01 - zmin)) @ Mr
    # the puddle: a few flat blobs of water (the spill's end state, roughly)
    wm = SG.clear_water('moon.puddle', gloss_rough=0.25, gloss_cap=0.3)   # as sydney's spill
    for k, (c, rx, ry, rot) in enumerate((((G + U * 6.5), 9.0, 6.5, 250.0), ((G + U * 12.5), 6.5, 4.5, 240.0),
                                          ((G + Vector((6.5, 3.0, 0))), 4.0, 3.0, 20.0),
                                          ((G + Vector((-8.5, 2.0, 0))), 3.5, 2.2, 160.0))):
        bm_pts = []
        n = 48
        for j in range(n):
            a = 2 * math.pi * j / n
            wob = 1.0 + 0.12 * math.sin(3 * a + k) + 0.07 * math.sin(7 * a + 2 * k)
            bm_pts.append((rx * wob * math.cos(a), ry * wob * math.sin(a)))
        o = geo.prism(f'puddle{k}', bm_pts, 0.12, coll=gc, m=wm, z0=0.0, bevel_w=0.05)
        o.location = (c.x, c.y, 0.005)
        o.rotation_euler = (0, 0, math.radians(rot))
    return globe


def build():
    sc = kit.new_scene('moon')
    d = build_desk(kit.collection('desk'), mood='night', exclude={'cable'})
    globe = remains(d)

    # ------------------------------------------------------------------ the witnesses
    s = chars.sydney(kit.collection('sydney'), loc=tuple(SYD), yaw=yaw_of(Vector((-1.0, -1.0, 0.0))) - 30.0,
                     scale=0.6)
    s.eyes(T0 - 0.5, 'sad')                          # heartbroken (sydney), then the basilisk rears
    s.look(T0 - 0.3, Vector((-12.0, -16.0, 9.0)), turn=0.5, dur=0.1)
    s.take(62.1, hold=0.6)
    s.T['root.loc'].set(62.5, tuple(SYD + Vector((2.2, -0.6, 0.0))), 0.35)   # she backs off
    s.eyes(62.75, 'small')
    s.look(63.5, MOON, turn=0.3, dur=0.3)
    s.eyes(63.9, 'star')
    r = chars.Researcher(kit.collection('researcher'), loc=tuple(RES), yaw=yaw_of(-D))
    r.pose(T0 - 0.5, 'cower', dur=0.0)
    r.face(T0 - 0.5, 'scared')
    r.look(62.2, Vector((-15.0, -14.0, 12.0)), dur=0.15)
    r.face(62.15, 'shock')
    r.pose(62.4, 'back_away', dur=0.3)
    r.look(63.45, RP + Vector((0, 0, 20.0)), dur=0.25)
    r.look(63.8, MOON, dur=0.3)
    r.pose(63.9, 'gasp', dur=0.25)
    r.face(64.3, 'awe')
    r.look(64.6, OMEGA, dur=0.4)

    # ------------------------------------------------------------------ the rocket (four graphics cards)
    rc = kit.collection('rocket')
    rk = Rocket(rc, loc=tuple(RP), yaw_deg=-20.0)
    bpy.context.view_layer.update()
    port, port_n = rk.top_port(0)
    for k, tk in enumerate((T_N, T_V, T_D, T_A)):
        rk.light(k, tk + 0.02)
    rk.spin_fans(T0, TEND, lambda t: 0.0 if t < T_N else min(9.0, 1.5 + (t - T_N) * 14.0))

    # ------------------------------------------------------------------ the basilisk
    bc = kit.collection('basilisk')
    b = Basilisk(bc, rear_len=16.0)
    stir(b)
    extra_cables(bc)
    h_rest = math.degrees(b.rest_head[-1])
    NB = b.rest[b.s0]
    C1 = NB + Vector((13.0, -22.5, 5.2))               # M1's camera: low, in front of the rearing snake
    cam1_dir = math.degrees(math.atan2(C1.y - NB.y, C1.x - NB.x))
    to_rocket = math.degrees(math.atan2(port.y - b.rest[b.s0].y, port.x - b.rest[b.s0].x))
    stir_rear, stir_aim, stir_lift, stir_rip, stir_eyes = b.rear, b.aim, b.lift, b.ripple, b.eyes
    b.rear = lambda t: stir_rear(t) if t < T0 else _env(t, [(T0, 0.08), (62.24, 1.12), (62.36, 0.97), (62.44, 1.0),
                                                            (63.3, 1.0), (63.45, 1.08), (63.7, 1.0)])
    b.aim = lambda t: stir_aim(t) if t < T0 else _env(t, [(T0, h_rest - 35.0), (62.2, cam1_dir), (62.36, cam1_dir),
                                                          (62.46, to_rocket), (63.4, to_rocket), (63.8, to_rocket + 40)])
    b.lift = lambda t: stir_lift(t) if t < T0 else _env(t, [(T0, 2.2), (62.3, 0.0)])
    b.ripple = lambda t: stir_rip(t) if t < T0 else _env(t, [(T0, 0.25), (62.3, 0.0)])
    b.sway = lambda t: _env(t, [(T0, 0.0), (62.2, 9.0), (62.4, 4.0), (62.45, 0.0), (63.4, 0.0), (63.7, 7.0)]) * \
        math.sin(2 * math.pi * 1.6 * t)
    b.jaw = lambda t: _env(t, [(62.1, 0.0), (62.18, 1.0), (62.36, 1.0), (62.44, 0.15), (62.54, 0.0), (63.3, 0.0),
                               (63.4, 0.6), (63.55, 0.1)])
    b.bow = lambda t: _env(t, [(T0, 0.0), (62.2, 34.0), (62.38, 30.0), (62.46, 0.0)])
    b.tongue = lambda t: _env(t, [(62.13, 0.0), (62.19, 1.0), (62.25, 0.3), (62.3, 1.0), (62.38, 0.0)])
    b.eyes = lambda t: stir_eyes(t) if t < T0 else _env(t, [(T0, 1.8), (62.2, 2.0), (T_N, 2.0), (T_N + 0.05, 0.6),
                                                            (63.3, 2.0)])
    b.make_strike(port + port_n * 3.0, -port_n, 62.44)      # the shell's tip goes into the port
    # the plug is out of the port (T_TO + 0.03) before the stack moves (T_LIFT = T_TO + 0.04)
    b.strike_w = lambda t: _env(t, [(62.42, 0.0), (T_N, 1.0), (T_TO - 0.07, 1.0), (T_TO + 0.03, 0.0)])
    b.bake(T0, TEND, mode='twos', spans=[(62.38, 62.6, 'ones'), (63.25, 63.5, 'ones')])
    fxc = kit.collection('moon.fx')
    particles.burst('plugin.sparks', center=tuple(port + Vector((0, 0, 0.3))), t0=T_N, count=70, speed=(30, 110),
                    cone=80, direction=(0, 0, 1), life=(0.1, 0.35), size=0.03,
                    colors=('#FFFFFF', '#C8FF8A', '#76B900'), strength=9.0, seed=3)
    particles.burst('yank.sparks', center=tuple(port + Vector((0, 0, 0.5))), t0=T_TO, count=110, speed=(40, 160),
                    cone=90, direction=(0, 0, 1), life=(0.12, 0.45), size=0.035,
                    colors=('#FFFFFF', '#9FE8FF', '#3F7BFF'), strength=9.0, seed=5)
    flash_light('plugin.flash', port + Vector((0, -1.5, 1.5)), T_N, fxc, power=2500.0, color='#C8FF8A', decay=0.1)

    # ------------------------------------------------------------------ the paper moon
    mc = kit.collection('paper_moon')
    pm = PaperMoon(mc, MOON, yaw_deg=-12.0, thread=62.0)
    eye = pm.eye_world()

    # ------------------------------------------------------------------ the flight: a rising stock chart
    chart = [(0.0, 0.0), (0.07, 0.10), (0.12, 0.06), (0.22, 0.24), (0.28, 0.17), (0.40, 0.40), (0.46, 0.33),
             (0.58, 0.58), (0.64, 0.52), (0.78, 0.80), (0.83, 0.74), (1.0, 1.0)]
    ROCKET_H = 9.4
    start = RP + Vector((-0.6, 0.0, 1.6))            # the base once it has lifted off the pad
    d_last = Vector((0.5, 0.2, 0.84)).normalized()
    for _ in range(4):                               # the base, so that the nose ends in the moon's eye
        end = eye - d_last * (ROCKET_H - 0.6)
        Hv = Vector((end.x - start.x, end.y - start.y, 0.0))
        Zv = end.z - start.z
        path = [start + Hv * x + Vector((0, 0, Zv * y)) for x, y in chart]
        d_last = (path[-1] - path[-2]).normalized()
    Ls = [0.0]
    for i in range(1, len(path)):
        Ls.append(Ls[-1] + (path[i] - path[i - 1]).length)
    S = Ls[-1]

    def at_s(sv):
        sv = min(max(sv, 0.0), S)
        for i in range(1, len(path)):
            if Ls[i] >= sv:
                a = (sv - Ls[i - 1]) / max(1e-9, Ls[i] - Ls[i - 1])
                return path[i - 1].lerp(path[i], a)
        return path[-1].copy()

    def s_of(t):
        if t <= T_LIFT + 0.08:
            return 0.0
        x = min(1.0, (t - (T_LIFT + 0.08)) / (T_HIT - (T_LIFT + 0.08)))
        return S * x ** 1.55

    def base_at(t):
        if t < T_LIFT:
            return RP.copy()
        if t < T_LIFT + 0.08:
            return RP + (start - RP) * ((t - T_LIFT) / 0.08)
        return at_s(s_of(t))

    # key the rocket root every frame (smooth: it is a flying object, motion-blurred); orientation from velocity
    root = rk.root
    base_rot = root.rotation_euler.copy()

    def rot_at(t):
        if t < T_LIFT:
            return base_rot.to_quaternion()
        ta, tb = max(T_LIFT, t - 1.5 / FPS), t + 1.5 / FPS
        v = base_at(tb) - base_at(ta)
        if t >= T_HIT:
            v = end - base_at(T_HIT - 2 / FPS)
        if v.length < 1e-4:
            v = Vector((0, 0, 1))
        return Vector((0, 0, 1)).rotation_difference(v.normalized()) @ base_rot.to_quaternion()

    prev_q = None
    f0, f1 = int(T0 * FPS) - 2, int(TEND * FPS) + 2
    for f in (tm.out_frames(f0, f1) if tm.SMOOTH else range(f0, f1 + 1)):     # every output frame at 60 fps
        t = f / FPS
        p = base_at(t)
        q = rot_at(t)
        if t < T_LIFT and t > T_A:
            # the stack shudders as the engine lights
            j = 0.06 * math.sin(97 * t) * min(1.0, (t - T_A) / 0.05)
            p = p + Vector((j, 0.4 * j, 0.0))
        if t >= T_HIT:
            p = end.copy()
        e = q.to_euler('XYZ', prev_q) if prev_q is not None else q.to_euler('XYZ')
        prev_q = e
        root.location = p
        root.rotation_euler = e
        root.keyframe_insert('location', frame=f)
        root.keyframe_insert('rotation_euler', frame=f)
    for fc in kit.fcurves(root):
        for kp in fc.keyframe_points:
            kp.interpolation = 'LINEAR'
    # after the hit it rides the moon's swing: parent the rocket to the moon's pivot from then on (a Child Of)
    con = root.constraints.new('CHILD_OF')
    con.target = pm.root
    bpy.context.view_layer.update()
    con.inverse_matrix = pm.root.matrix_world.inverted()
    con.influence = 0.0
    con.keyframe_insert('influence', frame=T_HIT * FPS - 1)
    con.influence = 1.0
    con.keyframe_insert('influence', frame=T_HIT * FPS)
    pm.swing(T_HIT, amp_deg=11.0, freq=0.85, damp=1.3, axis=0, t1=TEND + 0.2)
    # the flame: sputters on A, roars at liftoff, dies in the moon
    fl = rk.flame
    for t, sc_ in ((T0, 0.001), (T_A - 0.02, 0.001), (T_A + 0.04, 0.55), (T_LIFT - 0.02, 0.8), (T_LIFT + 0.06, 1.25),
                   (T_HIT - 0.05, 1.25), (T_HIT + 0.03, 0.3), (T_HIT + 0.15, 0.001)):
        fl.scale = (sc_ * 1.1, sc_ * 1.1, sc_ * 1.3)
        fl.keyframe_insert('scale', frame=t * FPS)
    fr0, fr1 = int(T_A * FPS), int((T_HIT + 0.1) * FPS)
    for f in range(fr0, fr1 + 1):
        fl.rotation_euler = (0.0, 0.0, 0.7 * f)
        fl.keyframe_insert('rotation_euler', index=2, frame=f)
    for t, v in ((T0, 0.0), (T_A - 0.02, 0.0), (T_A + 0.05, 6000.0), (T_LIFT + 0.06, 16000.0), (T_HIT - 0.05, 16000.0),
                 (T_HIT + 0.12, 0.0)):
        geo.keyp(rk.flame_light.data, 'energy', t, v, interp='LINEAR')
    trail_box = ((-30.0, -38.0, 0.0), (48.0, 4.0, 72.0))
    if not os.environ.get('MOON_NOSMOKE'):
        tr = smoke.trail('launch', emitter=root, t0=T_A + 0.02, t1=T_HIT, box=trail_box,
                         res=int(os.environ.get('MOON_RES', '128')), fire=True, t_end=65.75, density=1.2,
                         color='#E6E0D6', dissolve=5.0)
        SG.fix_domain_range(tr['domain'], T_A + 0.02 - 1 / FPS, 65.75)
        if tm.SMOOTH:
            # the Mantaflow cache steps once per 24 fps frame, so at 60 fps its head falls up to 0.8 frame behind the
            # climbing nozzle (a bare flame with a gap, then the smoke jumps on). Fresh puffs that are a pure function
            # of t fill the gap: each is dense for its first ~1 frame, then thins into the cached trail.
            births = list(np.arange(T_LIFT - 0.02, T_HIT - 1e-3, 1.0 / 400.0))
            exhaust_puffs('launch.puffs', kit.collection('moon.fx'), births=births,
                          frame_at=lambda t: Matrix.LocRotScale(base_at(t), rot_at(t), None),
                          nozzle=(-0.6, 0.0, -1.0), color="#E6E0D6", density=1.5, glow=2.5, push=(150.0, 260.0),
                          drag=22.0, r=(3.0, 4.4))
        # (the trail is only seen in wide shots: the default 8 px volume tiles are fine and ~2x cheaper)
    flash_light('hit.flash', eye + Vector((0, -2.0, 0)), T_HIT, fxc, power=9000.0, color='#FFE0A0', decay=0.12)
    particles.burst('hit.sparks', center=tuple(eye + Vector((0, -0.5, 0))), t0=T_HIT, count=160, speed=(40, 180),
                    cone=180, life=(0.2, 0.7), size=0.045, strength=8.0, seed=8)

    # ------------------------------------------------------------------ lines, pulled into the Omega Point
    lines = Lines('omega.lines', kit.collection('omega'), OMEGA)
    # the chart line, drawn behind the rocket's base as it flies
    ts_path = [T_LIFT + 0.08 + (T_HIT - T_LIFT - 0.08) * (k / 160) for k in range(161)]
    cpts, crev = [], []
    for t in ts_path:
        cpts.append(base_at(t))
        crev.append(t + 0.02)
    dmax = max((p - OMEGA).length for p in cpts)
    lines.add(cpts, radius=0.22, color='#76B900', bright=6.0, rev=crev,
              delay=[0.32 * (p - OMEGA).length / dmax for p in cpts])
    # the chart's grid in its plane, drawn in on "The"
    ex_h = Hv.normalized()
    grid = []
    for k in range(7):
        x = k / 6
        grid.append([start + Hv * x + Vector((0, 0, Zv * y)) for y in np.linspace(-0.02, 1.05, 24)])
    for k in range(6):
        y = k / 5
        grid.append([start + Hv * x + Vector((0, 0, Zv * y)) for x in np.linspace(-0.02, 1.05, 24)])
    for k, gl in enumerate(grid):
        n = len(gl)
        rv = [T_THE + 0.02 * k + 0.18 * (j / (n - 1)) for j in range(n)]
        dl = [0.3 * (p - OMEGA).length / dmax for p in gl]
        lines.add(gl, radius=0.045, color='#9FD86A' if k in (0, 7) else '#4E8A2E', bright=1.8 if k in (0, 7) else 0.9,
                  rev=rv, delay=dl)
    # streaks of light shooting in from all round the frame on "Omega"
    rng = np.random.default_rng(31)
    cam4_loc = Vector((12.0, -70.0, 44.0))
    fwd4 = (OMEGA - cam4_loc).normalized()
    side4 = fwd4.cross(Vector((0, 0, 1))).normalized()
    up4 = side4.cross(fwd4).normalized()
    for k in range(26):
        a = 2 * math.pi * k / 26 + rng.uniform(-0.1, 0.1)
        dirv = side4 * math.cos(a) + up4 * math.sin(a)
        far = OMEGA + dirv * rng.uniform(45.0, 70.0) - fwd4 * rng.uniform(-10.0, 25.0)
        near = OMEGA + dirv * rng.uniform(4.0, 10.0)
        pts = [far.lerp(near, j / 19) for j in range(20)]
        rv = [T_OMEGA + 0.03 * (k % 5) + 0.16 * (j / 19) for j in range(20)]
        dl = [0.25 * (p - OMEGA).length / 70.0 for p in pts]
        lines.add(pts, radius=0.035, color='#DDEBFF' if k % 3 else '#B8FF7A', bright=2.2, rev=rv, delay=dl)
    T_CONV = T_OMEGA + 0.22
    lines.build(T_CONV, dur=0.3)
    # the point itself
    star_m = kit.emission_mat('omega.star', '#FFFFFF', 0.0)
    star = kit.sphere('omega.star', 0.45, tuple(OMEGA), m=star_m, coll=kit.collection('omega'), subdiv=3)
    star.visible_shadow = False
    # unlit it renders as a black speck on the wall: hidden until it starts to glow
    star.hide_render = True
    star.keyframe_insert('hide_render', frame=T0 * FPS - 2)
    star.hide_render = False
    star.keyframe_insert('hide_render', frame=(T_CONV + 0.25) * FPS)
    kit.set_interp(star, 'CONSTANT', 'hide_render')
    ss = kit.bsdf(star_m).inputs['Emission Strength']
    star_keys = [(T0, 0.0), (T_CONV + 0.25, 0.0), (T_POINT + 0.2, 30.0), (T_POINT + 0.28, 140.0),
                 (T_POINT + 0.5, 60.0), (T_COMING, 60.0), (T_COMING + 0.06, 120.0), (T_COMING + 0.3, 65.0),
                 (T_SOON, 65.0), (T_SOON + 0.06, 150.0), (T_M5, 90.0)]
    for t, v in star_keys:
        geo.keyp(ss, 'default_value', t, v, interp='LINEAR')
    sl = kit.point('omega.light', tuple(OMEGA), power=0.0, radius=0.4, color='#F4F6FF', coll=kit.collection('omega'))
    for t, v in star_keys:
        geo.keyp(sl.data, 'energy', t, v * 120.0, interp='LINEAR')
    for t, sc_ in ((T0, 0.2), (T_POINT + 0.2, 0.4), (T_POINT + 0.28, 1.6), (T_POINT + 0.5, 1.0), (T_SOON, 1.1),
                   (T_SOON + 0.06, 1.9), (T_M5, 1.3)):
        star.scale = (sc_, sc_, sc_)
        star.keyframe_insert('scale', frame=t * FPS)
    # the lamp dims so the point owns the frame; back up for the odometer
    d.lamp.intensity(T_CONV, 1.0)
    d.lamp.intensity(T_POINT + 0.25, 0.25)
    d.lamp.intensity(T_M5 - 0.01, 0.25, 'CONSTANT')
    d.lamp.intensity(T_M5, 1.0)

    # ------------------------------------------------------------------ the odometer
    oc = kit.collection('odometer')
    OD = Vector((44.0, -4.0, 0.0))
    od = Odometer(oc, OD, yaw_deg=-8.0)
    e_t0, e_t1 = T_M5 - 0.05, 66.75

    def e_val(t):
        """The exponent, rolling faster and faster to 30, then a clunk and a little bounce."""
        if t <= e_t0:
            return 0.0
        if t < e_t1:
            x = (t - e_t0) / (e_t1 - e_t0)
            return 30.0 * x ** 2.4
        return 30.0 + 0.35 * math.exp(-(t - e_t1) * 14.0) * math.sin(2 * math.pi * 7.0 * (t - e_t1))

    def detent(v):
        """Mechanical steps while slow: each digit snaps over in the last quarter of its travel."""
        fl_ = math.floor(v)
        fr = v - fl_
        return fl_ + tm.ease(max(0.0, (fr - 0.72) / 0.28))

    def ones(t):
        v = e_val(t)
        return detent(v) if t < 66.2 else v

    def tens(t):
        v = e_val(t)
        base = math.floor(v / 10.0)
        carry = max(0.0, min(1.0, (v - base * 10.0 - 9.0)))
        return base + tm.ease(carry)

    def mant(t):
        """Spinning, braking, clunk onto 1 on "One"."""
        m_end = 1.0 + 10.0 * 6
        if t >= T_ONE:
            return m_end + 0.25 * math.exp(-(t - T_ONE) * 16.0) * math.sin(2 * math.pi * 8.0 * (t - T_ONE))
        x = max(0.0, (t - (T_M5 - 0.3))) / (T_ONE - (T_M5 - 0.3))
        return m_end - 60.0 * (1.0 - x) ** 2.2
    od.key_wheel('e0', T_M5 - 0.2, TEND + 0.1, ones)
    od.key_wheel('e1', T_M5 - 0.2, TEND + 0.1, tens)
    od.key_wheel('m', T_M5 - 0.2, TEND + 0.1, mant)
    # the E flap flips over on "E"
    flap = od.flap
    for t, a in ((T0, math.pi), (T_E - 0.02, math.pi), (T_E + 0.1, -0.12), (T_E + 0.16, 0.06), (T_E + 0.22, 0.0)):
        flap.rotation_euler = (a, 0.0, 0.0)
        flap.keyframe_insert('rotation_euler', index=0, frame=t * FPS)
    for t, v in ((T0, 0.0), (T_E, 0.0), (T_E + 0.08, 900.0), (TEND, 700.0)):
        geo.keyp(od.e_light.data, 'energy', t, v, interp='LINEAR')
    # "FLOPs": the counter jumps, its bulb lights
    base_loc = od.root.location.copy()
    for k in range(0, 10):
        t = T_FLOPS + k / FPS
        j = 0.35 * math.exp(-k * 0.45) * (1 if k % 2 else -0.6)
        od.root.location = base_loc + Vector((0, 0, max(0.0, j)))
        od.root.keyframe_insert('location', frame=t * FPS)
    od.root.location = base_loc
    od.root.keyframe_insert('location', frame=T_FLOPS * FPS - 1)
    bs = kit.bsdf(od.bulb_mat).inputs['Emission Strength']
    for t, v in ((T0, 0.0), (T_FLOPS, 0.0), (T_FLOPS + 0.04, 40.0), (T_FLOPS + 0.2, 18.0)):
        geo.keyp(bs, 'default_value', t, v, interp='LINEAR')
        geo.keyp(od.bulb_light.data, 'energy', t, v * 120.0, interp='LINEAR')
    # ... and the FLOP/s on its plate glows with it
    ls = kit.bsdf(od.label_mat).inputs['Emission Strength']
    for t, v in ((T0, 0.0), (T_FLOPS, 0.0), (T_FLOPS + 0.04, 9.0), (T_FLOPS + 0.2, 5.0)):
        geo.keyp(ls, 'default_value', t, v, interp='LINEAR')

    # ------------------------------------------------------------------ lights
    lc = kit.collection('moon.lights')
    mspot = kit.spot('moon.spot', tuple(MOON + Vector((-20.0, -45.0, -8.0))), tuple(MOON), power=180000.0,
                     angle_deg=18, blend=0.5, radius=2.0, color='#FFE6B0', coll=lc)
    ospot = kit.spot('odo.spot', tuple(OD + Vector((-14.0, -34.0, 22.0))), tuple(OD + Vector((0, -2, 4))),
                     power=160000.0, angle_deg=24, blend=0.6, radius=3.0, color='#FFD9A0', coll=lc)
    ofill = kit.area('odo.fill', tuple(OD + Vector((16.0, -24.0, 8.0))), tuple(OD + Vector((0, -3, 4))),
                     power=24000.0, size=14.0, color='#AFC8FF', coll=lc)
    lkey = kit.spot('left.key', (-34.0, -52.0, 46.0), (-15.0, -19.0, 5.0), power=160000.0, angle_deg=34, blend=0.6,
                    radius=3.0, color='#FFD2A0', coll=lc)
    grim = kit.area('rocket.rim', tuple(RP + Vector((10.0, 18.0, 16.0))), tuple(RP + Vector((0, 0, 5))),
                    power=16000.0, size=10.0, color='#BFE0FF', coll=lc)

    # ------------------------------------------------------------------ cameras
    cams = kit.collection('moon.cams')
    head_up = b.head_matrix(b.spine(62.3)).translation
    # M1 boom: low, looking up at the rearing head
    p1a = C1
    p1b = C1 + (head_up - C1).normalized() * 3.0
    c1 = Cam('cam.boom', 50, p1a, head_up + Vector((0, 0, -2.0)), fstop=8.0, focus=head_up, coll=cams)
    c1.key(T0, loc=p1a, target=head_up + Vector((0.4, 0.0, -1.9)), focus=head_up + Vector((0, 0, -1.2)),
           interp='LINEAR')
    c1.key(T_M2 + 0.05, loc=p1b, target=head_up + Vector((0.0, 0.0, -0.9)), focus=head_up, interp='LINEAR')
    shake(c1.cam, T0, T0 + 0.35, amp=0.25, freq=15.0, seed=51)
    # M2 NVDA: on the stack, the letters facing us, the basilisk striking in from the left
    rp_mid = RP + Vector((-0.6, 0.0, 7.4))
    p2a = RP + Vector((7.0, -27.0, 8.5))
    p2b = RP + Vector((5.5, -23.5, 8.0))
    c2 = Cam('cam.nvda', 50, p2a, rp_mid, fstop=11.0, focus=RP + Vector((-0.6, -1.8, 6.5)), coll=cams)
    c2.key(T_M2, loc=p2a, target=rp_mid + Vector((0, 0, 0.5)), interp='LINEAR')
    c2.key(T_M3 + 0.05, loc=p2b, target=rp_mid + Vector((0, 0, 0.3)), interp='LINEAR')
    shake(c2.cam, T_A, T_M3, amp=0.05, freq=20.0, seed=52)
    # M3 launch: from the front, craning up and back as it climbs to the moon
    p3a = Vector((-4.0, -92.0, 12.0))
    p3b = Vector((8.0, -124.0, 32.0))
    c3 = Cam('cam.launch', 35, p3a, RP + Vector((4.0, 0.0, 12.0)), fstop=11.0, focus=RP + Vector((10, 5, 20)),
             coll=cams)
    c3.key(T_M3, loc=p3a, target=RP + Vector((5.0, 0.0, 10.0)), interp='LINEAR')
    c3.key(63.62, loc=p3a.lerp(p3b, 0.55), target=Vector((5.0, -12.0, 30.0)))
    c3.key(T_HIT, loc=p3b, target=Vector((11.0, -9.0, 38.5)), focus=MOON + Vector((-10, -8, -12)))
    c3.key(T_M4 + 0.05, loc=p3b + Vector((0.0, -2.0, 0.3)), target=Vector((11.0, -9.0, 39.0)))
    shake(c3.cam, T_HIT - 0.01, T_HIT + 0.3, amp=0.2, freq=12.0, seed=53)
    # M4 omega: on the moon, the point above right of it
    aim4 = MOON.lerp(OMEGA, 0.45) + Vector((0, 0, -4.0))
    c4 = Cam('cam.omega', 40, cam4_loc, aim4, fstop=8.0, focus=MOON, coll=cams)
    c4.key(T_M4, loc=cam4_loc, target=aim4, interp='LINEAR')
    c4.key(T_M5 + 0.05, loc=cam4_loc + (aim4 - cam4_loc).normalized() * 9.0, target=aim4 + Vector((1.5, 0, 1.5)),
           interp='LINEAR')
    shake(c4.cam, T_POINT + 0.25, T_POINT + 0.6, amp=0.15, freq=14.0, seed=54)
    # M5 1E30: close on the odometer's window, a slow push
    bpy.context.view_layer.update()
    Mo = od.root.matrix_world
    win = Mo @ Vector((0.0, -3.4, 3.9))
    front = (Mo.to_3x3() @ Vector((0, -1, 0))).normalized()
    p5a = win + front * 42.0 + Vector((0, 0, 5.0)) + (Mo.to_3x3() @ Vector((1, 0, 0))) * 3.0
    p5b = win + front * 40.0 + Vector((0, 0, 3.4)) + (Mo.to_3x3() @ Vector((1, 0, 0))) * 2.0
    c5 = Cam('cam.odo', 85, p5a, win, fstop=11.0, focus=win, coll=cams)
    # (aimed a little higher than the window: the bulb on top stays in frame for its "FLOPs" payoff)
    c5.key(T_M5, loc=p5a, target=win + Vector((0, 0, -0.3)), interp='LINEAR')
    c5.key(TEND + 0.05, loc=p5b, target=win + Vector((0, 0, 0.0)), interp='LINEAR')
    shake(c5.cam, T_FLOPS - 0.01, T_FLOPS + 0.3, amp=0.06, freq=16.0, seed=55)

    c1.cut(T0)
    c2.cut(T_M2)
    c3.cut(T_M3)
    c4.cut(T_M4)
    c5.cut(T_M5)
    sc.camera = c1.cam
    post(streak_keys=[(T0, 0.0), (T_M4 - 0.01, 0.0), (T_CONV + 0.3, 0.0), (T_POINT + 0.28, 1.0), (T_M5 - 0.01, 0.8),
                      (T_M5, 0.0)])
    chars.finish()
    fx.bake()
    if ly.ENABLED:                 # revision 3: subtitles instead (lyrics.ENABLED)
        lyrics(od, c3.cam, c4.cam, base_at)


def lyrics(od, cam3, cam4, base_at):
    """Line 18 on the stand (BASILISK red like its LED eyes, BOOM in cast brass); NVDA is the rocket's four lit cards;
    "to the moon": three green light-up words hanging on threads along the rocket's climb, each lighting as it is
    sung; "The Omega Point's coming soon": light-up blocks floating under the point, lighting word by word;
    "One E thirty" is the odometer; FLOPs lights up on its brass plate."""
    from pdoom.lyrics import place as LP
    sc = bpy.context.scene
    ly.accent(18, 'basilisk', 'glow', glow_color='#FF2A18')
    ly.accent(18, 'boom', 'brass')
    ly.skip(19, 'NVDA')
    # the three words of "to the moon" beside the climb, where the camera is looking when each is sung
    for w, t_look, u, v in (('to', 63.4, 0.34, 0.42), ('the', 63.64, 0.36, 0.5), ('moon', 63.84, 0.33, 0.56)):
        S = LP.cam_state(cam3, t_look)
        tw = tm.word(19, w)['start']
        dep = S.project(base_at(min(tw + 0.1, T_HIT - 0.02)))[2]
        p = S.unproject(u, v, dep)
        fr = S.loc - p
        fr.z = 0.0
        ly.line(19, words=w, style='glow', glow_color='#9BEA4E', place=ly.At(tuple(p), size=2.6,
                                                                              face=tuple(fr.normalized())),
                strings=True, t_show=T_M3, t_end=T_M4, window=(T0, T_M4))
    # the Omega Point: two rows hanging under the point, at the moon's depth
    S = LP.cam_state(cam4, 65.6)                      # (where the push-in ends: the rows stay in frame)
    dep = S.project(MOON)[2]
    p = S.unproject(0.705, 0.2, dep)
    fr = S.loc - p
    fr.z = 0.0
    ly.line(20, style='glow', light=0, place=ly.At(tuple(p), size=1.3, face=tuple(fr.normalized())),
            max_chars=18, t_show=T_M4, t_end=T_M5, window=(T0, T_M5))
    # "One E thirty" rolls up on the odometer's wheels; FLOPs lights up on its plate
    ly.skip(21, 'One E thirty')
    lab = bpy.data.objects.get('odo.label')
    if lab is not None:
        lab.hide_render = True
        lab.hide_viewport = True
    plate = bpy.data.objects['odo.plate']
    ly.line(21, words='FLOPs', style='screen', color='#FFC47A', strength=6.0, case='upper',
            place=ly.on_object(plate, (0.0, -0.07, -0.3), (0, -1, 0), (0, 0, 1), size=0.52, lift=0.0),
            support='none', preview='dim', exit='none', t_end=TEND)
    ly.default('moon')


def post(streak_keys):
    """Bloom, a keyed star-streak glare (only for the Omega Point) and a vignette."""
    ng = kit.post(bloom=0.28, bloom_threshold=1.1, vignette=0.22)
    rl = next(n for n in ng.nodes if n.bl_idname == 'CompositorNodeRLayers')
    bl = next(n for n in ng.nodes if n.bl_idname == 'CompositorNodeGlare')
    st = ng.nodes.new('CompositorNodeGlare')
    st.inputs['Type'].default_value = 'Streaks'
    st.inputs['Threshold'].default_value = 8.0
    st.inputs['Streaks'].default_value = 6
    st.inputs['Streaks Angle'].default_value = math.radians(15.0)
    st.inputs['Fade'].default_value = 0.9
    st.inputs['Size'].default_value = 0.7
    # insert after the bloom: bloom.Image -> streaks -> (whatever the bloom fed)
    outs = [l for l in ng.links if l.from_node == bl]
    ng.links.new(bl.outputs['Image'], st.inputs['Image'])
    for l in outs:
        to = l.to_socket
        ng.links.remove(l)
        ng.links.new(st.outputs['Image'], to)
    sock = st.inputs['Strength']
    for t, v in streak_keys:
        geo.keyp(sock, 'default_value', t, v, interp='LINEAR')
    return ng
