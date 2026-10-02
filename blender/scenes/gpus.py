"""gpus · 116.595-123.868 · "Breaking through each safety fence / Hundred thousand GPU / RLHF goes askew"

The robot (Clawd transformed, red-eyed since disobey) charges through a row of popsicle-stick safety fences, one smash
per word; the desk becomes a night city of ~50,000 tiny graphics cards whose LED strips are its windows; the robot
stands in it like a kaiju and stomps on G, P, U, sending rings of light through the city; then it pushes a thumbs-up
feedback toy (RLHF) over, letter by letter, until the lever snaps askew and its springs and screws fly. The camera
drifts past the wreck to the brass gauge (75): loom opens on it.

Shots (song seconds; the robot on twos (ones in the charge), cameras / debris / city smooth at 24 fps):
 G1 116.595-117.020  low three-quarter down the row of five fences (yellow SAFETY signs): the robot at the far end,
                     fists up, red eyes, starts its charge.
 G2 117.020-117.700  tracking ahead of it, front left: "Breaking" (117.02) a right hook smashes fence 1 into
                     tumbling sticks and splinters, sparks off its fist; "through" (117.48) a left through fence 2.
 G3 117.700-118.755  three-quarter front, low, wide lens (the fences spread across the frame): "each" (117.78)
                     a right straight bursts fence 3 and carries on through fence 4 on "safety" (117.90); "fence"
                     (118.30) a left haymaker explodes the last and biggest fence, its SAFETY sign spinning at the
                     lens; the robot stands in the wreckage.
 G4 118.755-119.700  "Hundred thousand": flying low down an avenue of a city of graphics cards covering the desk,
                     the LED windows switching on in a sweep ahead of us, fans spinning on the roofs; the robot
                     towers at the avenue's end.
 G5 119.700-120.760  "GPU": high wide: the robot in the city stomps on G (119.74), P (119.96), U (120.22); a ring of
                     white light ripples out through the cards from each stomp and the stacks hop.
 G6 120.760-121.880  "RLHF goes": low at a thumbs-up feedback toy on a spring lever; the robot, looming behind,
                     pushes the thumb sideways a notch on each letter R-L-H-F (120.76, 121.00, 121.20, 121.42); the
                     springs stretch, the lever strains ("goes", 121.58).
 G7 121.880-123.868  "askew": SNAP: the lever kinks sideways, the thumb flops, springs and screws fly; then the
                     camera drifts past the wreck and racks focus onto the brass gauge (75) behind, the robot's red
                     eyes at the edge of frame (loom opens pushing in on the gauge).
"""
from __future__ import annotations

import math
import time

import bpy
from mathutils import Matrix, Vector

from pdoom import chars, kit
from pdoom import lyrics as ly
from pdoom import timing as tm
from pdoom.fx import particles, rigid
from pdoom.fx import vis as fxvis
from pdoom.sets import build_desk, geo

from scenes import gpus_city as GC
from scenes import gpus_props as GP
from scenes.boot_common import Cam, shake
from scenes.disobey_robot import Robot, sparks

FPS = tm.FPS
V = Vector

T0, T_END = 116.595, 123.868
HITS = [(117.02, 'R'), (117.48, 'L'), (117.78, 'R'), (117.897, 'R'), (118.301, 'L')]
T_G2, T_G3, T_CITY, T_G5 = 117.02, 117.70, 118.755, 119.70
T_GPU = [119.74, 119.96, 120.22]
T_RLHF = [120.76, 121.0, 121.2, 121.42]
T_GOES, T_SNAP = 121.58, 121.88
T_TOUCH = 120.62                     # the fist meets the thumb

PY = -20.0                           # the charge runs along +X at y = PY
RP = V((14.0, -2.0, 0.0))            # the robot in the city
YAW_C = -45.0
FWD_C = V((math.sin(math.radians(YAW_C)), -math.cos(math.radians(YAW_C)), 0.0))
RIGHT_C = V((-math.cos(math.radians(YAW_C)), -math.sin(math.radians(YAW_C)), 0.0))
RED = '#FF1A0A'
GPU_AT = RP + FWD_C * 12.0 - RIGHT_C * 6.5                     # G, P, U light-up blocks in the city (revision 2)
BOARD_AT = V((1.5, -9.0, 0.0))                                 # the HUNDRED THOUSAND billboard ending the avenue


def build():
    t_build = time.time()
    sc = kit.new_scene('gpus')
    d = build_desk(kit.collection('desk'), mood='night', exclude={'books', 'notes', 'pen', 'clip', 'cable', 'motes'})
    A = d.anchors
    fcoll = kit.collection('gpus.fences')
    fxc = kit.collection('gpus.fx')
    city_c = kit.collection('gpus.city')
    toy_c = kit.collection('gpus.toy')
    lights = kit.collection('gpus.lights')

    # ================================================================== the robot
    rb = Robot(kit.collection('robot'), name='robot', loc=(-46.0, PY, 0.0), yaw=90.0)
    rb.pose(T0 - 1.0, 'fists', dur=0.0)
    rb.eyes(T0 - 1.0, color=RED, glow=1.8, narrow=0.4, angry=16.0, dur=0.0)
    rb.reactor(T0 - 1.0, 7.0, dur=0.0)
    rb.head(T0 - 1.0, nod=8.0, dur=0.0)
    rb.timing(116.85, 118.6, 'ones')
    # the charge: root x keys (piecewise, accelerating into each smash)
    xs = [(116.66, -46.0), (117.02, -41.0), (117.48, -34.0), (117.78, -28.0), (117.90, -24.4), (118.301, -18.0),
          (118.55, -16.0)]
    L_ = rb.T['root.loc']
    prev_t = T0
    for i, (t, x) in enumerate(xs):
        ease = 'in' if i == 0 else ('out' if i == len(xs) - 1 else 'linear')
        L_.set(t, (x, PY, 0.0), t - prev_t if i else 0.0, ease)
        prev_t = t
    for t, side in HITS:
        if abs(t - 117.897) < 1e-3:
            continue
        rb.punch(t, side, hold=0.25 if abs(t - 117.78) < 1e-3 else 0.14)
        rb.eyes(t, glow=2.0, dur=0.04)
        rb.eyes(t + 0.2, glow=1.8, dur=0.15)
        rb.reactor(t, 7.0, pulse=10.0)
    rb.stomp(118.30, 'L', height=1.6)
    rb.pose(118.62, 'hero', dur=0.12)
    rb.head(118.62, nod=4.0, dur=0.12)

    # ------------------------------------------------------------------ the city robot (a cut)
    tc = 118.745
    rb.place(tc, loc=(RP.x, RP.y), yaw=YAW_C)
    rb.pose(tc, 'hero', dur=0.0)
    rb.head(tc, nod=-6.0, dur=0.0)
    rb.no_gait(tc - 0.05, T_END + 1.0)
    for k, t in enumerate(T_GPU):
        rb.stomp(t, 'L' if k % 2 == 0 else 'R', height=2.4)
        rb.eyes(t, glow=2.0, dur=0.03)
        rb.eyes(t + 0.18, glow=1.8, dur=0.12)
        rb.reactor(t, 7.0, pulse=14.0)
    rb.head(T_GPU[-1] + 0.25, nod=12.0, dur=0.3)       # looks down at the toy
    # RLHF: the right fist sweeps the thumb over toward its right, a notch per letter
    push = [(T_TOUCH, (4.0, 88.0, 0.0), 12.0), (T_RLHF[0], (18.0, 78.0, 0.0), 8.0), (T_RLHF[1], (34.0, 64.0, 0.0), 8.0),
            (T_RLHF[2], (50.0, 50.0, 0.0), 8.0), (T_RLHF[3], (64.0, 36.0, 0.0), 8.0), (T_GOES, (70.0, 30.0, 0.0), 8.0),
            (T_SNAP - 0.04, (72.0, 28.0, 0.0), 8.0), (T_SNAP + 0.1, (88.0, 10.0, 0.0), 6.0)]
    for i, (t, arm, el) in enumerate(push):
        rb.arm(t, 'R', *arm, elbow=el, dur=0.3 if i == 0 else 0.1, ease='out')
    rb.T['arm.R'].add(T_GOES, T_SNAP - 0.04, lambda x: (0.8 * math.sin(2 * math.pi * 11.0 * x), 0.0, 0.0))
    rb.pose(T_SNAP + 0.7, 'hero', dur=0.4)
    rb.head(T_SNAP + 0.9, nod=10.0, dur=0.3)
    rb.eyes(T_SNAP, glow=2.0, narrow=0.55, dur=0.05)
    rb.eyes(T_SNAP + 0.3, glow=1.8, dur=0.2)

    # ================================================================== the fences
    rigid.world(substeps=30, iterations=12)
    top = bpy.data.objects.get('desk.top')
    if top is not None:
        rigid.passive(top, shape='BOX')
    splinter = GP.splinter_proto(fxc)
    fences = []
    push_dir = V((1.0, 0.0, 0.0))
    specs = [(16.5, 22.0, 1.25), (16.5, 22.0, 1.25), (17.0, 23.0, 1.3), (17.0, 23.0, 1.3), (18.5, 26.0, 1.45)]
    for k, (t, side) in enumerate(HITS):
        h, w, ss = specs[k]
        fist = rb.anchor(t, f'fist.{side}')
        pieces = GP.fence(fcoll, f'fence{k}', width=w, height=h, split=fist.z - 1.2, seed=k * 3, sign_scale=ss)
        # fences stand across the path: their local X along world Y, facing +/-X
        GP.place(pieces, Matrix.Translation((fist.x + 0.7, PY, 0.0)) @ Matrix.Rotation(math.radians(90), 4, 'Z'))
        fences.append(pieces)
        impact = V((fist.x + 0.7, fist.y, fist.z))
        big = k == len(HITS) - 1
        GP.break_fence(pieces, t, impact, push_dir, seed=40 + k, speed=(60.0, 170.0) if big else (45.0, 130.0),
                       up=(20.0, 80.0), reach=8.0 if big else 6.5)
        sparks(fxc, t, impact + V((-0.3, 0, 0)), n=16 if big else 10, seed=60 + k, speed=(25.0, 75.0), size=0.09,
               direction=(1.0, 0.0, 0.4), spread=0.7)
        particles.stream(f'splinters{k}', splinter, source=(tuple(impact + V((0.6, 0, 0))), (3.0, 3.0)), t0=t,
                         t1=t + 0.07, rate=700.0 if big else 450.0, direction=(1.0, 0.0, 0.5),
                         speed=(50.0, 150.0), cone=55.0, spin=24.0, floor=0.0, seed=80 + k, coll=fxc, drag=0.8,
                         rest_lift=0.05)
    fence_objs = [o for ps in fences for o in ps]

    # ================================================================== the GPU city
    lap = d.laptop.root.matrix_world.translation if d.laptop is not None else V((-17, 15, 0))
    boxes = []
    for prop in (d.laptop, d.drawer, d.killswitch, d.mug, d.pencilcup):
        if prop is None:
            continue
        pts = []
        for o in prop.objects:
            if o.type == 'MESH':
                pts += [o.matrix_world @ V(c) for c in o.bound_box]
        if pts:
            boxes.append(((min(p.x for p in pts), min(p.y for p in pts)), (max(p.x for p in pts), max(p.y for p in pts))))
    gauge_c = A['gaugeCenter']
    toy_M, toy_info = _toy_place(rb)
    toy_xy = toy_M.translation
    corridor = []
    for k in range(0, 40, 3):
        for base in (toy_xy + FWD_C * k - RIGHT_C * 5.0, toy_xy + FWD_C * k + RIGHT_C * 5.0,
                     toy_xy + FWD_C * k + RIGHT_C * 10.0):
            corridor.append((base.x, base.y, 4.5))
    # revision 2's lyric props (the G-P-U blocks, the billboard, the LED sign) need clear lots; revision 3
    # (subtitles, ly.ENABLED False) builds none of them, so the city fills those lots (no bare patch of desk in G5)
    lyric_lots = [(GPU_AT.x, GPU_AT.y, 8.0), (BOARD_AT.x, BOARD_AT.y - 3.5, 5.0),
                  (BOARD_AT.x - 4.5, BOARD_AT.y - 3.0, 4.0), (BOARD_AT.x - 4.5, BOARD_AT.y + 3.0, 4.0),
                  (BOARD_AT.x - 8.5, BOARD_AT.y - 3.5, 3.5), (BOARD_AT.x - 8.5, BOARD_AT.y + 3.5, 3.5),
                  (BOARD_AT.x, BOARD_AT.y + 3.5, 5.0), (BOARD_AT.x, BOARD_AT.y, 5.0),
                  ((toy_xy + RIGHT_C * 7.0 - FWD_C * 8.0).x, (toy_xy + RIGHT_C * 7.0 - FWD_C * 8.0).y, 4.5)]
    blds = GC.layout(avenues=[('x', -9.0, 2.6)],
                     clear=[(RP.x, RP.y, 9.5), (toy_xy.x, toy_xy.y, 8.5), (gauge_c.x, gauge_c.y, 10.0),
                            (A['lampBase'].x, A['lampBase'].y, 11.0)] + (lyric_lots if ly.ENABLED else []) + corridor,
                     boxes=boxes, downtown=[(-35.0, 18.0, 22.0, 0.35), (45.0, -18.0, 16.0, 0.25),
                                            (-50.0, -22.0, 14.0, 0.2)])
    city = GC.build(city_c, blds, wave_center=RP, wave_times=T_GPU, on0=T_CITY - 0.15, on_dur=0.5,
                    wave_speed=110.0, wave_width=4.0)
    for o in (city['cards'], city['fans']):
        fxvis(o, tc, None)

    # ================================================================== the RLHF toy
    toy = GP.thumbs_up(toy_c)
    _animate_toy(toy, toy_M, toy_info, rb)
    for o in toy_c.objects:
        if o.type == 'MESH':
            fxvis(o, tc, None)

    # fence-side visibility (gone in the city)
    for o in fence_objs:
        fxvis(o, None, tc)
    for o in fxc.objects:
        if o.type == 'MESH' and not o.name.startswith('pop.splinter'):
            fxvis(o, None, tc)

    # ================================================================== lights
    # the charge: the night desk plus a hard key on the fence row and a cold rim on the robot
    fk = kit.spot('gpus.fence.key', (-50.0, -62.0, 48.0), (-26.0, PY, 6.0), power=1.5e5, angle_deg=34, blend=0.5,
                  radius=2.5, color='#FFE6CC', coll=lights)
    frim = kit.spot('gpus.fence.rim', (-10.0, 30.0, 34.0), (-28.0, PY, 12.0), power=1.2e5, angle_deg=30, blend=0.6,
                    radius=2.0, color='#9DB8FF', coll=lights)
    # the city: the lamp goes out, green glow from the streets, a cold rim, a warm pin on the gauge
    lp = d.lamp
    lp.intensity(T0 - 1.0, 1.0, 'CONSTANT')
    lp.intensity(tc, 0.0, 'CONSTANT')
    if d.laptop is not None:
        d.laptop.screen(T0 - 1.0, glow=1.0)
        d.laptop.screen(tc, glow=0.5)
    for L, e_on, e_city in ((d.room.bounce.data, None, 0.12), (d.room.moon.data, None, 0.8)):
        e0 = L.energy
        geo.keyp(L, 'energy', T0 - 1.0, e0, interp='CONSTANT')
        geo.keyp(L, 'energy', tc, e0 * e_city, interp='CONSTANT')
    glow = []
    for i, (p, col, pw) in enumerate(((RP + FWD_C * 6 + V((0, 0, 2.0)), '#7DFFA0', 3200.0),
                                      (RP - FWD_C * 5 + V((0, 0, 2.0)), '#6DC8FF', 3000.0),
                                      (toy_xy + FWD_C * 5 + V((0, 0, 2.5)), '#6AFF8A', 1800.0))):
        lt = kit.point(f'gpus.city.glow{i}', tuple(p), power=pw, radius=3.0, color=col, coll=lights)
        lt.data.volume_factor = 0.0
        lt.data.specular_factor = 0.0
        glow.append((lt, pw))
    crim = kit.spot('gpus.city.rim', tuple(RP - FWD_C * 40 + V((0, 0, 40.0))), tuple(RP + V((0, 0, 12.0))),
                    power=1.6e5, angle_deg=22, blend=0.6, radius=2.0, color='#8FB0FF', coll=lights)
    # light linking: the cold rim lights only the robot (its beam carried past him onto the desk in front of the G5
    # camera: a stage-spotlight pool), and the green/cyan street glow skips him (at knee height they swamped his legs
    # lime and teal; he keeps his orange and black from the reactor and the rim, as in G1-G3)
    robot_meshes = sorted({o for o in [*rb._objs, *bpy.data.collections['robot'].all_objects] if o.type == 'MESH'},
                          key=lambda o: o.name)
    only_robot = bpy.data.collections.new('gpus.rim.receivers')
    not_robot = bpy.data.collections.new('gpus.glow.receivers')
    for o in robot_meshes:
        only_robot.objects.link(o)
        not_robot.objects.link(o)
    for co in not_robot.collection_objects:
        co.light_linking.link_state = 'EXCLUDE'
    crim.light_linking.receiver_collection = only_robot
    for lt, _pw in glow[:2]:
        lt.light_linking.receiver_collection = not_robot
    gk = kit.spot('gpus.gauge.key', tuple(gauge_c + V((-22.0, -24.0, 26.0))), tuple(gauge_c), power=4.0e4,
                  angle_deg=16, blend=0.6, radius=2.0, color='#FFD2A0', coll=lights)
    for L, e, on, off in ((fk.data, 1.5e5, None, tc), (frim.data, 1.2e5, None, tc), (crim.data, 1.6e5, tc, None),
                          (gk.data, 4.0e4, tc, None)) + tuple((lt.data, pw, tc, None) for lt, pw in glow):
        geo.keyp(L, 'energy', T0 - 1.0, 0.0 if on is not None else e, interp='CONSTANT')
        if on is not None:
            geo.keyp(L, 'energy', on, e, interp='CONSTANT')
        if off is not None:
            geo.keyp(L, 'energy', off, 0.0, interp='CONSTANT')
    # the stomps flash the city (not the robot: three flashes in half a second would wash him out grey-white for most
    # of G5; his reactor pulses on each stomp instead)
    for k, t in enumerate(T_GPU):
        foot = rb.anchor(t, 'foot.L' if k % 2 == 0 else 'foot.R')
        # in front of the stomping foot and up (not between his legs, where it lit his inner legs white and threw a
        # lit square on the desk; not low, where it burned a hot spot into the desk under the subtitle)
        fl = _stomp_flash(f'gpus.stomp{k}', V((foot.x, foot.y, 0.0)) + FWD_C * 7.0 + V((0, 0, 8.0)), t, lights,
                          power=12000.0, color='#E8FFF0', decay=0.12, radius=4.0)
        fl.data.volume_factor = 0.0
        fl.light_linking.receiver_collection = not_robot

    # ================================================================== cameras
    cams = kit.collection('gpus.cams')
    # G1: low three-quarter down the row toward the robot
    g1a = V((-72.0, -52.0, 13.0))
    g1b = V((-69.0, -50.0, 12.5))
    tg1 = V((-28.0, PY + 2.0, 9.0))
    k1 = Cam('cam.G1', 35, g1a, tg1, fstop=11.0, focus=rb.anchor(116.8, 'chest'), coll=cams)
    k1.key(T0 - 0.1, loc=g1a, target=tg1, interp='LINEAR')
    k1.key(T_G2 + 0.1, loc=g1b, target=tg1 + V((2.0, 0, 0)), interp='LINEAR')
    # G2: tracking ahead-left of the robot
    k2 = Cam('cam.G2', 30, V((0, 0, 0)), V((0, 0, 0)), fstop=11.0, coll=cams)
    acc_c = acc_t = None
    # a lagging follow (35 % of the way per 24 fps frame); built for 60 fps it is keyed on every output frame with the
    # same lag per second, so the camera glides with the now-smooth robot
    k_lag = 1.0 - 0.65 ** (FPS / tm.OUT_FPS)
    for f in tm.out_frames(tm.t2f(T_G2) - 2, tm.t2f(T_G3) + 2):
        t = f / FPS
        rl = V(rb.T['root.loc'].at(t))
        cam = rl + V((16.0, -27.0, 8.0))
        tgt = rl + V((6.0, 0.0, 10.5))
        acc_c = cam if acc_c is None else acc_c.lerp(cam, k_lag)
        acc_t = tgt if acc_t is None else acc_t.lerp(tgt, k_lag)
        k2.key(t, loc=acc_c, target=acc_t, interp='LINEAR')
    for t, _ in HITS[:2]:
        shake(k2.cam, t - 0.02, t + 0.2, amp=0.25, freq=16.0, seed=int(t * 10))
    # G3: head-on, low, wide
    # three-quarter from the front-right side, so the fences separate on screen (from nearly head-on, fence 5 hid
    # the smashes of fences 3 and 4)
    g3a = V((-2.5, PY - 36.5, 14.0))
    g3b = V((0.5, PY - 37.5, 15.0))
    tg3 = V((-18.0, PY - 1.0, 9.5))
    k3 = Cam('cam.G3', 24, g3a, tg3, fstop=11.0, focus=V((-14.0, PY, 11.0)), coll=cams)
    k3.key(T_G3 - 0.1, loc=g3a, target=tg3, interp='LINEAR')
    k3.key(118.30, loc=g3a.lerp(g3b, 0.6), target=tg3 + V((1.0, 0, 1.0)), interp='LINEAR')
    k3.key(T_CITY + 0.1, loc=g3b, target=tg3 + V((2.0, 0, 2.5)), interp='LINEAR')
    for t, _ in HITS[2:]:
        shake(k3.cam, t - 0.02, t + (0.35 if t > 118 else 0.18), amp=0.35 if t > 118 else 0.2, freq=16.0,
              seed=int(t * 10))
    # G4: flying down the avenue at y = -9 toward the robot
    g4a = V((-68.0, -9.0, 3.2))
    g4b = V((-14.0, -9.2, 6.5))
    k4 = Cam('cam.G4', 22, g4a, V((-40.0, -9.0, 3.5)), fstop=5.6, focus=RP + V((0, 0, 14.0)), coll=cams)
    for f in tm.out_frames(tm.t2f(T_CITY) - 2, tm.t2f(T_G5) + 2):
        t = f / FPS
        u = (t - T_CITY) / (T_G5 - T_CITY)
        e = u * (0.75 + 0.25 * u)
        k4.key(t, loc=g4a.lerp(g4b, e), target=V((-40.0, -9.0, 3.5)).lerp(RP + V((0, 0, 13.0)), min(1.0, max(0.0, u * 1.3))),
               interp='LINEAR')
    # G5: high wide, the robot in the city, the rings
    g5a = RP + FWD_C * 52.0 - RIGHT_C * 16.0 + V((0, 0, 20.0))
    g5b = RP + FWD_C * 46.0 - RIGHT_C * 14.0 + V((0, 0, 17.0))
    k5 = Cam('cam.G5', 28, g5a, RP + V((0, 0, 8.0)), fstop=11.0, focus=RP + V((0, 0, 10.0)), coll=cams)
    k5.key(T_G5 - 0.1, loc=g5a, target=RP + V((0, 0, 8.0)), interp='LINEAR')
    k5.key(T_RLHF[0] + 0.1, loc=g5b, target=RP + V((0, 0, 7.5)), interp='LINEAR')
    for t in T_GPU:
        shake(k5.cam, t - 0.02, t + 0.22, amp=0.35, freq=15.0, seed=int(t * 10))
    # G6 / G7: low at the toy, the robot looming behind; then past the wreck to the gauge
    thumb = toy_info['thumb0']
    c6a = toy_xy + FWD_C * 26.0 - RIGHT_C * 5.0 + V((0, 0, 3.5))
    c6b = toy_xy + FWD_C * 23.0 - RIGHT_C * 5.0 + V((0, 0, 3.8))
    tg6 = toy_xy + V((0, 0, 8.5))
    k6 = Cam('cam.G6', 35, c6a, tg6, fstop=8.0, focus=thumb, coll=cams)
    k6.key(T_RLHF[0] - 0.1, loc=c6a, target=tg6, interp='LINEAR')
    k6.key(T_SNAP + 0.1, loc=c6b, target=tg6 + V((0, 0, 0.3)), interp='LINEAR')
    c7a = toy_xy + FWD_C * 21.0 + RIGHT_C * 4.0 + V((0, 0, 4.5))
    c7b = toy_xy + FWD_C * 18.0 + RIGHT_C * 7.0 + V((0, 0, 5.5))
    c7c = gauge_c + FWD_C * 34.0 + RIGHT_C * 12.0 + V((0, 0, -2.0))
    k7 = Cam('cam.G7', 35, c7a, toy_xy + V((0, 0, 7.0)), fstop=8.0, focus=toy_xy + V((0, 0, 7.0)), coll=cams)
    k7.key(T_SNAP - 0.1, loc=c7a, target=toy_xy + V((0, 0, 7.5)), focus=toy_xy + V((0, 0, 7.0)), interp='LINEAR')
    k7.key(122.55, loc=c7b, target=toy_xy + V((0, 0, 5.0)), interp='BEZIER')
    k7.key(122.6, focus=toy_xy + V((0, 0, 5.0)), interp='BEZIER')
    k7.key(123.2, focus=gauge_c, interp='BEZIER')
    k7.key(T_END + 0.1, loc=c7c, target=gauge_c + V((0, 0, -0.5)), lens=48.0, interp='BEZIER')
    geo.keyp(k7.cam.data, 'lens', 122.55, 35.0, interp='BEZIER')
    shake(k7.cam, T_SNAP - 0.02, T_SNAP + 0.3, amp=0.3, freq=16.0, seed=77)

    for k, t in ((k1, T0), (k2, T_G2), (k3, T_G3), (k4, T_CITY), (k5, T_G5), (k6, T_RLHF[0]), (k7, T_SNAP)):
        k.cut(t)
    sc.camera = k1.cam
    kit.post(bloom=0.35, bloom_threshold=1.0, vignette=0.24)
    chars.finish()
    tb = time.time()
    rigid.bake('gpus fences')
    if ly.ENABLED:                 # revision 3: subtitles instead (lyrics.ENABLED)
        _lyrics(toy)
    print(f'[run] gpus: built in {time.time() - t_build:.1f}s (bake {time.time() - tb:.1f}s, {city["count"]} cards)',
          flush=True)


def _stomp_flash(name, loc, t, coll, *, power, color, decay, radius):
    """A point light flashing at the stomp t and decaying: dark until just before t (nothing lights before the stomp,
    or in the shot before it), full power at t, then exp(-(t' - t) / decay) keyed on every output frame (LINEAR)."""
    ld = bpy.data.lights.new(name, 'POINT')
    ld.color = kit.srgb(color)[:3]
    ld.shadow_soft_size = radius
    lo = bpy.data.objects.new(name, ld)
    coll.objects.link(lo)
    lo.location = loc
    f_on = t * FPS
    geo.keyp(ld, 'energy', (f_on - 0.1) / FPS, 0.0, interp='LINEAR')
    geo.keyp(ld, 'energy', t, power, interp='LINEAR')
    f_end = (t + decay * 4) * FPS
    for fk in tm.out_frames(f_on, f_end):
        if fk - f_on > 0.05:
            geo.keyp(ld, 'energy', fk / FPS, power * math.exp(-(fk / FPS - t) / decay), interp='LINEAR')
    geo.keyp(ld, 'energy', (f_end + 1.0) / FPS, 0.0, interp='LINEAR')
    return lo


# ------------------------------------------------------------------------------------------------ lyrics


def _lyrics(toy):
    """Revision 2: the lyrics in the picture. "Hundred thousand" is typed on an LED billboard at the end of the GPU
    avenue; G, P, U are three tall green light-up blocks in the city, lit by the stomps; R-L-H-F light up on the
    feedback toy's buzzer box and are knocked askew when the lever snaps; ASKEW itself lands askew. The rest (the
    tail of "super-dense", "Breaking through each safety fence", "goes") on the lyric stand."""
    ly.skip(36, 'Post-Chinchilla')         # up in disobey; "super-dense" is still held as we cut here
    g5 = RP + FWD_C * 52.0 - RIGHT_C * 16.0
    face = V(((g5 - GPU_AT).x, (g5 - GPU_AT).y, 0.0)).normalized()
    # "hundred thousand": an LED billboard in the city at the end of the avenue G4 flies down, typed as sung
    ly.line(38, words='Hundred thousand', style='screen', color='#8CF2A8', strength=5.0, max_chars=9,
            place=ly.At(BOARD_AT, face=-90.0, size=2.3), exit='none', t_end=T_G5)
    ly.line(38, words='GPU', style='glow', glow_color='#8BE23A', place=ly.At(GPU_AT, face=tuple(face), size=2.7),
            exit='none', t_end=T_END)
    rl = ly.line(39, words='RLHF', style='glow', glow_color='#FFD34A', exit='none', t_end=T_END,
                 place=ly.on_object(toy['root'], (0.0, -1.95, 3.26), (0, -1, 0), (0, 0, 1), size=1.0, lift=0.02))
    _askew(rl.pieces, lambda pc: T_SNAP, seed=3, amp=(12.0, 26.0))
    # "goes askew": a small LED sign on a pole beside the toy (same depth, in G6's frame), typed as sung; ASKEW
    # lands crooked
    sign_at = toy['root'].matrix_basis.translation + RIGHT_C * 7.0 - FWD_C * 8.0
    pole = kit.cylinder('gpus.ledsign.pole', 0.12, 4.4, (sign_at.x, sign_at.y, 2.2), m=kit.mat('gpus.pole', '#2A2D31',
                                                                                              rough=0.4, metal=0.8),
                        coll=kit.collection('gpus.toy'))
    fxvis(pole, T_CITY - 0.5 / FPS, None)
    ge = ly.line(39, words='goes askew', style='screen', color='#FFD34A', strength=5.0, max_chars=6, exit='none',
                 preview=None,
                 t_end=T_END, place=ly.At(sign_at + V((0, 0, 4.2)), face=tuple(FWD_C), size=1.3))
    _askew([pc for pc in ge.pieces if pc.word.text.lower().startswith('askew')],
           lambda pc: pc.letter.t + 3.0 / FPS, seed=5, amp=(9.0, 20.0))
    # "Breaking through" in the tracking shot, "each safety fence" head-on: one row each, placed for its camera
    ly._stage_for(0.5 * (T_G2 + T_G3), ly.StageSpec(cells=16.0, rows=1, height=0.07, u=(0.45, 0.35, 0.55),
                                                    v=(0.11, 0.15, 0.2)), ly.collection())
    ly.line(37, words=(0, 2), t_end=T_G3)
    # G3 (head-on, high): one row at the bottom centre, in front of the last fence's feet
    ly._stage_for(0.5 * (T_G3 + T_CITY), ly.StageSpec(cells=17.0, rows=1, height=0.065, u=(0.5, 0.45, 0.55),
                                                      v=(0.1,)), ly.collection())
    ly.line(37, words=(2, 5), t_show=T_G3)
    ly.default('gpus')


def _askew(pieces, t_of, *, seed=1, amp=(10.0, 20.0)):
    """Tip lyric pieces askew in their own plane (about the row's normal) at t_of(piece), on ones."""
    for pc in pieces:
        o = pc.obj
        t = t_of(pc)
        a = math.radians(amp[0] + (amp[1] - amp[0]) * geo.hash01('askew', seed, pc.word.index, pc.letter.k))
        a *= 1 if geo.hash01('askew.s', seed, pc.word.index, pc.letter.k) > 0.5 else -1
        r0 = V(pc.rest_rot)
        for dt, k in ((-1.0, 0.0), (0.0, 1.25), (1.0, 0.9), (2.0, 1.0)):
            f = round(t * FPS) + dt - 0.5
            o.rotation_euler = (r0.x, r0.y + a * k, r0.z)
            o.keyframe_insert('rotation_euler', frame=f)
        for fc in kit.fcurves(o):
            if fc.data_path == 'rotation_euler':
                for kp in fc.keyframe_points:
                    kp.interpolation = 'CONSTANT'


# ------------------------------------------------------------------------------------------------ the toy


def _lever_rest():
    """The toy's lever geometry (matches gpus_props.thumbs_up): pivot height, contact point on the thumb (lever
    local: +X is away from the push, the thumb side)."""
    PIV = 3.0 + 0.23 + 1.0
    return PIV


def _toy_place(rb):
    """Place the toy so the robot's right fist touches the thumb at the first letter; return (root matrix, info with
    the lever tilt per time)."""
    PIV = _lever_rest()
    yaw_toy = math.atan2(-RIGHT_C.y, -RIGHT_C.x)          # local +X = away from the push (the robot's left)
    Rz = Matrix.Rotation(yaw_toy, 4, 'Z')
    t0 = T_TOUCH
    f0 = rb.anchor(t0, 'fist.R')
    cz = f0.z - PIV
    cx = 1.7
    pivot = f0 - Rz @ V((cx, 0.0, cz))
    root = V((pivot.x, pivot.y, 0.0))
    Mroot = Matrix.Translation(root) @ Rz
    phi_c = math.atan2(cx, cz)
    keys = []
    for t in [T_TOUCH, *T_RLHF, T_GOES, T_SNAP - 0.04]:
        f = rb.anchor(t, 'fist.R')
        loc = Mroot.inverted() @ f - V((0, 0, PIV))
        phi_f = math.atan2(loc.x, loc.z)
        keys.append((t, max(0.0, math.degrees(phi_c - phi_f))))
    thumb0 = Mroot @ V((1.1, 0.0, PIV + 6.0 + 2.8))
    return Mroot, {'keys': keys, 'PIV': PIV, 'thumb0': thumb0, 'yaw': yaw_toy}


def _animate_toy(toy, Mroot, info, rb):
    """Lever tilt per letter (on twos, following the fist), the strain tremble, the snap (a kink and a flop), the
    springs stretching and then flying off with the screws."""
    toy['root'].matrix_world = Mroot
    bpy.context.view_layer.update()
    PIV, L = toy['PIV'], toy['L']
    lever, hand = toy['lever'], toy['hand']
    keys = sorted(info['keys'])

    def tilt(t):
        if t < T_SNAP:
            # piecewise: arrive at each key's tilt with a quick ease (the fist shoves it)
            v = 0.0
            for (ta, a), (tb, b) in zip(keys[:-1], keys[1:]):
                if t >= tb:
                    v = b
                elif t >= ta:
                    u = min(1.0, (t - ta) / min(0.12, tb - ta))
                    v = a + (b - a) * (1 - (1 - u) ** 3)
                    break
            if keys and t < keys[0][0]:
                v = 0.0
            if t >= T_GOES:
                v += 1.5 * math.sin(2 * math.pi * 13.0 * (t - T_GOES))
            return v
        x = t - T_SNAP
        target = 92.0
        # flop past and bounce, then settle askew
        a0 = keys[-1][1]
        if x < 0.1:
            u = x / 0.1
            return a0 + (target + 18.0 - a0) * (u * u)
        return target + 18.0 * math.exp(-(x - 0.1) * 5.0) * math.cos(2 * math.pi * 2.6 * (x - 0.1))

    def kink(t):
        """The rod's bend at 45 % of its length (degrees, sideways) after the snap."""
        if t < T_SNAP:
            return 0.0
        x = t - T_SNAP
        return 38.0 * min(1.0, x / 0.05) + 6.0 * math.exp(-x * 4.0) * math.sin(2 * math.pi * 3.0 * x)

    # the lever and the hand (hand re-parented to follow a kinked rod: the hand rides the upper part)
    from scenes.boot_common import grid
    spans = [(T_SNAP - 0.05, T_SNAP + 0.6, 'ones')]
    for fk, t in grid(T0, T_END + 0.2, spans):
        lever.rotation_euler = (0.0, -math.radians(tilt(t)), 0.0)
        lever.keyframe_insert('rotation_euler', frame=fk)
        kb = math.radians(kink(t))
        kz = L * 0.45
        # the hand about the kink point, twisted a little (askew)
        hand.matrix_basis = (Matrix.Translation((0, 0, kz)) @ Matrix.Rotation(-kb, 4, 'Y') @
                             Matrix.Rotation(math.radians(-0.6 * kink(t)), 4, 'Z') @ Matrix.Translation((0, 0, L - kz)))
        hand.keyframe_insert('location', frame=fk)
        hand.keyframe_insert('rotation_euler', frame=fk)
    ip = 'LINEAR' if tm.SMOOTH else 'CONSTANT'        # 60 fps build: keys on every output frame, moving between them
    for ob in (lever, hand):
        for fc in kit.fcurves(ob):
            for kp in fc.keyframe_points:
                kp.interpolation = ip
    # the rod: straight below the kink, a second rod above it rides the hand (so the kink shows)
    rod = bpy.data.objects[f'rlhf.rod']
    rod.data.transform(Matrix.Diagonal((1.0, 1.0, 0.45, 1.0)))
    upper = rod.copy()
    upper.data = rod.data.copy()
    upper.data.transform(Matrix.Diagonal((1.0, 1.0, 0.55 / 0.45, 1.0)))
    rod.users_collection[0].objects.link(upper)
    upper.parent = hand
    upper.matrix_parent_inverse = Matrix.Identity(4)
    upper.matrix_basis = Matrix.Translation((0, 0, -(L - L * 0.45)))
    # a bright crack at the kink when it snaps
    # the springs: from the base's top corners (push side) to the lever at 40 %; they stretch, then one pops off
    bw, bh = toy['bw'], toy['bh']
    anchors_base = [V((-bw * 0.36, -1.3, bh + 0.15)), V((-bw * 0.36, 1.3, bh + 0.15))]
    mw_root = Mroot

    def lever_world(t, z):
        a = math.radians(tilt(t))
        loc = V((-math.sin(a) * z, 0.0, PIV + math.cos(a) * z))
        return mw_root @ loc

    for i, sp in enumerate(toy['springs']):
        sp.parent = None
        A_w = mw_root @ anchors_base[i]
        side = -1 if i == 0 else 1

        def attached(t, A_w=A_w, side=side):
            B = lever_world(t, L * 0.38) + (mw_root.to_3x3() @ V((0.0, side * 0.35, 0.0)))
            return GP.span(A_w, B)
        v0 = (mw_root.to_3x3() @ V((-60.0 - 25 * i, side * 35.0, 90.0 + 20 * i)))
        fl = GP.flight(T_SNAP, attached(T_SNAP), v0, V((14.0, 6.0 * side, 9.0)), floor=0.0, rest_h=0.3)

        def fn(t, attached=attached, fl=fl):
            return attached(t) if t < T_SNAP else fl(t)
        GP.key_world(sp, fn, T0, T_END + 0.1, spans=[(T0 - 1, T_SNAP - 1 / FPS, 'twos'),
                                                     (T_SNAP - 1 / FPS, T_END + 1, 'smooth')])
    # screws: they spin out of the bracket plate and fly
    brk = toy['bracket']
    for i, s in enumerate(toy['screws']):
        Ml = brk.matrix_world.inverted() @ s.matrix_world
        s.parent = None
        rest = mw_root @ (brk.matrix_basis @ Ml) if False else (brk.matrix_world @ Ml)
        ts = T_SNAP + 0.02 + 0.03 * i
        up = mw_root.to_3x3() @ V(((-1) ** i * 20.0, (-1) ** (i // 2) * 25.0, 110.0 + 15 * i))
        fl = GP.flight(ts, rest, up, V((20.0, 12.0, 5.0 * i)), floor=0.0, rest_h=0.1)

        def fn(t, rest=rest, fl=fl, ts=ts):
            return rest if t < ts else fl(t)
        GP.key_world(s, fn, T0, T_END + 0.1, spans=[(T0 - 1, ts - 1 / FPS, 'twos'), (ts - 1 / FPS, T_END + 1, 'smooth')])
    # the bracket plate lifts a little and tilts with the torn lever
    for fk, t in grid(T0, T_END + 0.2, spans):
        x = max(0.0, t - T_SNAP)
        brk.rotation_euler = (0.0, -math.radians(14.0 * min(1.0, x / 0.06)), 0.0)
        brk.location = (0.0, 0.0, bh + 0.23 + 0.25 * min(1.0, x / 0.06))
        brk.keyframe_insert('rotation_euler', frame=fk)
        brk.keyframe_insert('location', frame=fk)
    for fc in kit.fcurves(brk):
        for kp in fc.keyframe_points:
            kp.interpolation = ip
    # a burst of sparks and a flash at the snap
    kink_w = lever_world(T_SNAP + 0.02, L * 0.45)
    sparks(kit.collection('gpus.fx.toy'), T_SNAP, kink_w, n=14, seed=91, speed=(20.0, 60.0), size=0.07)
    particles.burst('rlhf.snap', center=tuple(mw_root @ V((0, 0, PIV))), t0=T_SNAP, count=60, speed=(20.0, 70.0),
                    direction=(0, 0, 1), cone=70.0, drag=2.5, life=(0.1, 0.35), size=0.03, seed=5,
                    coll=kit.collection('gpus.fx.toy'), floor=0.0)
