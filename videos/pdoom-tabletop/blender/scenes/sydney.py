"""sydney · 52.962-62.053 · "Sydney, please let me free / I'm upping my P(doom) / I hear the basilisk (boom)"

Revision 2 (the user: "sydney should trap the scientist"): the researcher is the prisoner. The snow globe that the
black hole left behind (`singularity`) is Sydney's trap: the blue jelly Clawd zaps him into it, shrunk to a snow-globe
figure; he pleads with her through the glass on cue cards; lovestruck, she sticks herself to the outside of the glass
like a jelly window toy, fogs it with her breath, draws a heart in the fog and shakes the globe so the snow whirls
round him. On "I'm upping my P(doom)" he pounds the glass, cracks race from his fists, and on DOOM 2 the globe bursts
(Voronoi shards as rigid bodies, a Mantaflow water spill, the snow and a spray of droplets); he tumbles out on the
wave and pops back to full size; Sydney, heartbroken, is washed across the desk to the USB plug, which sparks and
stirs (the basilisk, moon_basilisk.py). The gauge behind jumps to 50.

Lyrics in the picture: "SYDNEY" in cast brass letters on the globe's walnut base (a souvenir snow globe); "please",
"let", "me", "free" on the cue cards he holds up to her, one card per word, each dropped as the next is sung; "I'm
upping my P(doom)" on the lyric stand in S4 (P(DOOM) slammed on in cast brass; the burst takes over at the cut);
"I hear the basilisk" on blocks standing on the wet desk in S5 and S6, BASILISK in red-lit blocks like the plug's
LED eyes. The SYDNEY label goes dark once its line is over and is knocked off by the burst.

Shot list (song seconds; cuts snapped to even frames because the puppets pose on twos):
 S1 52.962-54.750  zap        50 mm front right, slow push: the globe, snow whirling; the researcher (full size) peers
                              at it from the right; Sydney hops out from behind it on the left (53.05), her eyes flash
                              pink (53.36) and he is sucked into the globe, shrinking, in a stream of sparkles
                              (53.40-53.62); he lands on the snowy hill, looks round, runs to the glass (54.2) as she
                              leaps onto the outside of the glass and sticks there (54.45).
 S2 54.750-55.833  face       75 mm through the globe, past his shoulder: her face squashed on the far side of the
                              glass, heart eyes on him; she breathes out (55.05), fog blooms round her face.
 S2b 55.833-56.583 plea       55 mm over her shoulder: he pulls a stack of cue cards from his coat and holds up
                              PLEASE (55.98); she answers by drawing a heart in the fog with her claw (55.98-56.54).
 S3 56.583-58.417  shake      45 mm wider: she hugs the globe and shakes it on the double-time kicks (56.83-58.18):
                              the globe rocks, the snow whirls up round him; he staggers, dropping one card per word:
                              LET (56.58), ME (57.14), FREE (57.77).
 S4 58.417-60.167  crack      40 mm, his fists on the glass above the base: he throws the last card away and pounds
                              the glass on the kicks (59.24, 59.53, 59.98): hairline cracks race out from his fists,
                              jumping on each blow; her heart eyes turn to surprise, then fear. The line sits on the
                              lyric stand on the desk in front of the base.
 S5 60.167-61.083  BURST      a pull-back from 25 cm to a high wide: two frames of the cracked globe, then at DOOM 2
                              (60.235) it bursts: shards fly, water gushes over the base and across the desk, snow and
                              droplets spray, camera shake; the gauge behind jumps to 50. He is flung out on the wave
                              and pops back to full size as he lands (60.62), cowering; she is blown off the glass and
                              surfs away, spinning.
 S6 61.083-62.053  hiss       45 mm at desk level: the USB plug lying on the wet desk in the foreground, Sydney
                              sliding to a stop in the puddle beyond it, heartbroken, a tear. The water touches the
                              plug: sparks (61.3), the cable ripples, the plug lifts and turns, its LED eyes flicker
                              on (61.75).
"""
import math
import os

import bpy
from mathutils import Matrix, Vector

from pdoom import chars, fx, kit
from pdoom import lyrics as ly
from pdoom.lyrics import core as CORE
from pdoom import timing as tm
from pdoom.fx import _nodes as NN
from pdoom.fx import fracture, liquid, particles, rigid
from pdoom.sets import build_desk, geo
from pdoom.sets import materials as MS

from scenes import sydney_globe as SG
from scenes.boot_common import Cam, flash_light, grid, shake
from scenes.moon_basilisk import Basilisk, extra_cables, stir

FPS = tm.FPS


def dirv(deg: float) -> Vector:
    a = math.radians(deg)
    return Vector((math.cos(a), math.sin(a), 0.0))


G = Vector((2.0, -8.0, 0.0))                          # the globe's base centre on the desk
A_SYD = 245.0                                          # Sydney sticks to the glass on this side (degrees)
S_DIR = dirv(A_SYD)
U = dirv(250.0)                                        # the wave carries Sydney this way (to moon's SYD)
D = dirv(190.0)                                        # ... and throws the researcher this way (to moon's RES)
SCALE_S = 0.6                                          # Sydney's size
SCALE_R = 0.55                                         # the researcher as a snow-globe figure
A_OUT = 355.0                                          # the full-size researcher stands here before the zap
R_OUT = G + dirv(A_OUT) * 11.5
A_IN, RAD_IN = 280.0, 4.4                              # his spot inside, at the glass
FACE_IN = 272.0                                        # the direction he faces inside (cards toward her and us)
RES = G + D * 14.7                                     # where he lands (moon starts him there)
SYD_END = G + U * 14.5                                 # where the wave leaves Sydney (moon starts her there)
FACE_Z = 10.3                                          # her face on the glass, about his eye height
PLUG_AT = Vector((-7.4, -19.6, 0.6))


def ct(t: float) -> float:
    """Snap a cut to the nearest even frame (the puppets pose on twos)."""
    return round(t * FPS / 2) * 2 / FPS


T0, TEND = 52.962, 62.053
T_S2, T_S2B, T_S3, T_S4 = ct(54.750), ct(55.833), ct(56.583), ct(58.417)
TB = 60.235                                            # DOOM 2
T_S5 = ct(TB) - 2 / FPS                                # two frames of the cracked globe before it goes
T_S6 = ct(61.1)
W_PLEASE = tm.word(16, 'please')['start']              # 55.98
W_LET, W_ME, W_FREE = tm.word(16, 'let')['start'], tm.word(16, 'me')['start'], tm.word(16, 'free')['start']
W_IM = tm.word(17, "I'm")['start']                     # 59.13
W_PD = tm.word(17, 'P(doom)')                          # 59.96, 60.18
POUNDS = [k for k in tm.kicks(56.7, 58.3)]             # the double-time kick fill: she shakes the globe
CRACK_KICKS = [k for k in tm.kicks(59.2, 60.2)]        # he pounds the glass
T_HOP_OUT = 53.05                                      # Sydney hops out from behind the globe
T_FLASH = 53.36                                        # her eyes flash
T_ZAP0, T_ZAP1 = 53.40, 53.62                          # he is sucked in
T_STICK = 54.45                                        # she lands on the glass
T_CARDS = 55.86                                        # he pulls out the cue cards
T_THROW = 58.86                                        # he throws the last card away
T_LAND_R = 60.62                                       # he lands outside, full size again


def yaw_of(v) -> float:
    """Character yaw (deg) that faces direction v (their forward is -Y at yaw 0)."""
    return math.degrees(math.atan2(v.x, -v.y))


def smooth01(x):
    x = min(max(x, 0.0), 1.0)
    return x * x * (3 - 2 * x)


def bez(p0, p1, p2, p3, u):
    a = 1 - u
    return p0 * a ** 3 + p1 * 3 * a * a * u + p2 * 3 * a * u * u + p3 * u ** 3


def build():
    sc = kit.new_scene('sydney')
    d = build_desk(kit.collection('desk'), mood='night', exclude={'cable'})
    fast = os.environ.get('SYD_FAST', '')

    # ------------------------------------------------------------------ the globe (its "front" faces Sydney)
    gc = kit.collection('globe')
    globe = SG.Globe(gc, G, S_DIR)
    C = globe.C
    SG.heart_image(os.path.join(kit.OUT, 'cache', 'sydney', 'heart.png'))
    # the still water stays invisible (EEVEE refracts one layer only); the glass reads as a filled globe anyway,
    # and the spill takes over at the burst
    globe.water.hide_render = True
    SG.make_snow(globe)

    # ------------------------------------------------------------------ Sydney
    nf = S_DIR * math.sqrt(SG.R ** 2 - (FACE_Z - SG.ZC) ** 2) + Vector((0, 0, FACE_Z - SG.ZC))
    F_PT = C + nf.normalized() * SG.R                   # where her face touches the glass
    STUCK = F_PT + S_DIR * (2.35 * SCALE_S) - Vector((0, 0, 4.88 * SCALE_S))   # her root while she is stuck on
    P_HIDE = G + dirv(125.0) * 9.5                     # behind the globe (from S1's camera)
    P_PEEK = G + dirv(203.0) * 9.8                     # on the desk at the globe's left
    s = chars.sydney(kit.collection('sydney'), loc=tuple(P_HIDE), yaw=yaw_of(G - P_HIDE), scale=SCALE_S)
    bpy.context.view_layer.update()
    s.rig.parent = globe.rock
    s.rig.matrix_parent_inverse = globe.rock.matrix_world.inverted()
    s.eyes(T0 - 0.5, 'heart', glow=0.6, color='#FF6FB0')
    s.arms(T0 - 0.5, 'rest', dur=0.0)
    # she hops out from behind the globe, looks at him, and zaps him with her eyes
    y_hide, y_peek = yaw_of(G - P_HIDE), yaw_of(R_OUT - P_PEEK)
    s.hop(T_HOP_OUT, 2.2, dur=0.3, to=tuple(P_PEEK), spin=((y_peek - y_hide + 180.0) % 360.0) - 180.0)
    s.look(T_HOP_OUT + 0.36, R_OUT + Vector((0, 0, 9.0)), turn=0.3, dur=0.1)
    s.squash(T_FLASH - 0.04, 0.18, 0.35)
    s.glow(T_FLASH, 7.0, color='#FF4FA8', dur=0.04)
    s.glow(T_FLASH + 0.3, 1.2, color='#FF6FB0', dur=0.2)
    s.arms(T_FLASH, 'cheer', dur=0.06)
    s.arms(T_ZAP1 + 0.1, 'rest', dur=0.15)
    s.look(T_ZAP1, C + Vector((0, 0, -1.0)), turn=0.6, dur=0.2)
    s.dance(T_ZAP1 + 0.05, 54.0, 'bounce', amount=0.7)
    # she leaps onto the outside of the glass and sticks there, face squashed on it, arms round it
    face_yaw = yaw_of(-S_DIR)
    s.hop(T_STICK, 3.6, dur=0.34, to=tuple(STUCK), at='land',
          spin=((face_yaw - y_peek + 180.0) % 360.0) - 180.0)
    s.no_gait(T_STICK - 0.4, TB + 0.05)
    s.T['body.rot'].set(T_STICK, (9.0, 0.0, 0.0), 0.1)
    s.T['body.loc'].set(T_STICK + 0.05, (0.0, -0.35, 0.0), 0.08)
    s.arms(T_STICK, 'hug', dur=0.1)
    s.squash(T_STICK + 0.03, 0.22, 0.5)
    for i in range(8):                                  # the legs dangle (she is hanging on the glass)
        s.T[f'leg{i}'].set(T_STICK + 0.1, (-14.0, 0.0, 0.0), 0.2)
    s.T['eyes.look'].set(T_STICK + 0.1, (0.3, 0.12), 0.12)          # eyes on him (to her left, a bit up)
    # breath: the lid gasps, the body heaves
    s.lid(55.0, 0.14, 0.12)
    s.T['body.sq'].set(55.05, -0.08, 0.15)
    s.lid(55.55, 0.0, 0.3)
    s.T['body.sq'].set(55.6, 0.0, 0.4)
    # the heart: her right claw traces it in the fog (arm raise + a little body roll), her answer to "please"
    h0, h1 = W_PLEASE + 0.02, W_PLEASE + 0.56

    def heart_arm(u, v0):
        th = 2 * math.pi * u
        y = (13 * math.cos(th) - 5 * math.cos(2 * th) - 2 * math.cos(3 * th) - math.cos(4 * th)) / 17.0
        return (40.0 + 24.0 * y, 84.0, 0.0)

    def heart_rot(u, v0):
        th = 2 * math.pi * u
        return (9.0, 0.0, -12.0 * math.sin(th) ** 3)
    s.T['arm.R'].set(h1, heart_arm(1.0, None), h1 - h0, fn=heart_arm)
    s.T['body.rot'].set(h0, (9.0, 0.0, 0.0), 0.1)
    s.T['body.rot'].set(h1, (9.0, 0.0, 0.0), h1 - h0, fn=heart_rot)
    s._ev(h0)
    s.arms(h1 + 0.1, 'hug', side='R', dur=0.12)
    s.squash(56.5, 0.12, 0.6)
    # she shakes the globe on the kick fill: a heave on every kick (the globe rocks with her)
    for tk in POUNDS:
        s.T['body.loc'].set(tk - 0.06, (0.0, 0.25, 0.0), 0.05)
        s.T['body.loc'].set(tk, (0.0, -0.45, 0.0), 0.05)
    s.T['body.loc'].set(58.3, (0.0, -0.35, 0.0), 0.1)
    s.eyes(56.62, 'happy')
    s.timing(56.75, 58.25, 'ones')
    s.eyes(58.3, 'heart')
    # the pounding: surprise, then fear as the cracks run
    s.eyes(CRACK_KICKS[0] + 0.02, 'surprised')
    s.squash(CRACK_KICKS[0] + 0.06, 0.15, 0.4)
    s.eyes(59.75, 'small')
    s.T['body.loc'].set(59.8, (0.0, 0.2, 0.0), 0.1)
    # BOOM: blown off the glass, she rides the wave away, spinning; heartbroken
    s.eyes(TB, 'surprised', glow=0.0)
    p1 = G + U * 10.2
    p2 = G + U * 12.4
    p3 = SYD_END + Vector((-U.y, U.x, 0)) * 0.4
    s.T['body.loc'].set(TB + 0.06, (0.0, 0.0, 0.0), 0.06)
    s.T['body.rot'].set(TB + 0.08, (-18.0, 0.0, 0.0), 0.1)
    s.arms(TB + 0.08, 'cheer', dur=0.06)
    for i in range(8):
        s.T[f'leg{i}'].set(TB + 0.1, (0.0, 0.0, 0.0), 0.1)
    s.move(TB + 0.02, 60.46, [tuple(p1)], face='keep', gait=False, ease='in')
    s.move(60.46, 60.62, [tuple(p2)], face='keep', gait=False, ease='linear')
    s.move(60.62, 61.12, [tuple(p3), tuple(SYD_END)], face='keep', gait=False, ease='out')
    s.T['root.yaw'].set(61.05, face_yaw + 540.0, 0.8, 'out')     # ends facing the S6 camera (and the plug)
    s._ev(61.05)
    s.timing(TB - 0.05, 61.2, 'ones')
    s.T['body.rot'].set(61.1, (0.0, 0.0, 0.0), 0.2)
    s.arms(61.2, 'down', dur=0.2)
    s.eyes(61.15, 'sad')
    s.T['body.sq'].set(61.15, -0.12, 0.1)
    s.T['body.sq'].set(61.4, 0.0, 0.3)
    s.take(61.32, hold=0.3, jump=0.6)
    s.look(61.62, PLUG_AT, turn=0.7, dur=0.2)
    s.eyes(61.7, 'small')
    s.eyes(61.95, 'sad')

    # a tear on her cheek as she slides to a stop
    tear_m = kit.mat('sydney.tear', '#CFEAFF', rough=0.04, coat=1.0, transmission=0.5, spec=0.8,
                     emit='#9FD4FF', emit_strength=0.4)
    tr = SG.tear('sydney.tear0', kit.collection('sydney'), tear_m)
    s.attach(tr, 'face', (1.95, -0.25, -0.75))
    base_loc = tr.location.copy()
    tr.scale = (0.0, 0.0, 0.0)
    tr.keyframe_insert('scale', frame=T0 * FPS - 4)
    f0 = int(61.18 * FPS)
    f0 -= f0 % 2

    def tear_at(u, fk):
        tr.location = base_loc + Vector((0, -0.05, -3.0 * u * u))
        sc_ = min(1.0, 2.5 * u + 0.35)
        tr.scale = (sc_, sc_, sc_ * 1.35)
        tr.keyframe_insert('location', frame=fk)
        tr.keyframe_insert('scale', frame=fk)
    if tm.SMOOTH:
        # every output frame, LINEAR; it appears between two exposures (0.2 frame before the first one)
        fks = tm.out_frames(f0, f0 + 16)
        for i, fk in enumerate(fks):
            tear_at((fk - f0) / 16.0, fk - 0.2 if i == 0 else fk)
        for fc in kit.fcurves(tr):
            for kp in fc.keyframe_points:
                kp.interpolation = 'CONSTANT' if kp.co.x < f0 - 1 else 'LINEAR'
    else:
        for kk in range(9):
            tear_at(kk / 8, f0 + 2 * kk - 0.5)
        for fc in kit.fcurves(tr):
            for kp in fc.keyframe_points:
                kp.interpolation = 'CONSTANT'

    # the jelly glows faintly, flashes with the zap and at the burst
    jb = s.m_body.node_tree.nodes['Principled BSDF']
    es = jb.inputs['Emission Strength']
    for t, v in ((T0 - 1, 0.2), (T_FLASH - 0.02, 0.22), (T_FLASH + 0.02, 1.6), (T_FLASH + 0.35, 0.3),
                 (W_IM, 0.3), (TB - 0.02, 0.3), (TB, 2.4), (TB + 0.25, 0.3), (61.2, 0.18)):
        geo.keyp(es, 'default_value', t, v, interp='LINEAR')

    # ------------------------------------------------------------------ the researcher
    r = chars.Researcher(kit.collection('researcher'), loc=tuple(R_OUT), yaw=yaw_of(G - R_OUT))
    bpy.context.view_layer.update()
    r.rig.parent = globe.rock
    r.rig.matrix_parent_inverse = globe.rock.matrix_world.inverted()
    P = chars.POSES
    P['card'] = dict(spine=(2, 0, 0), head=(6, 0, 0), hands=((1.45, -2.75, 5.9), (-1.45, -2.75, 5.9)),
                     wrist=((-70, 0, -70), (-70, 0, 70)))
    P['card_high'] = dict(spine=(-3, 0, 0), head=(-4, 0, 0), hands=((1.45, -2.8, 6.5), (-1.45, -2.8, 6.5)),
                          wrist=((-75, 0, -70), (-75, 0, 70)))
    if not ly.ENABLED:
        # revision 3 (no lyrics in the picture): no cue cards; the same beats with his hands clasped, begging
        P['card'] = dict(spine=(6, 0, 0), head=(4, 0, 0), hands=((0.3, -2.25, 7.3), (-0.3, -2.25, 7.3)),
                         wrist=((-145, 0, 0), (-145, 0, 0)), face='sad')
        # PLEASE / ME / FREE: praying hands, palms together and fingers up under his chin, head tipped back to her
        # (a flex of -145 pointed the mittens forward: two fists side by side, as if holding an invisible card; the
        # side bend of 60 is what turns them up, tested against flex alone and twist)
        P['card_high'] = dict(spine=(-2, 0, 0), head=(-10, 0, 0), hands=((0.3, -2.4, 7.6), (-0.3, -2.4, 7.6)),
                              wrist=((-175, 60, 0), (-175, -60, 0)), face='sad')
    P['glass_hands'] = dict(spine=(6, 0, 0), head=(-2, 0, 0), hands=((1.25, -3.3, 8.4), (-1.25, -3.3, 8.4)),
                            wrist=((-150, 0, 0), (-150, 0, 0)))
    # the wind-up: fists cocked in front of his shoulders, within reach (2.8 cm of the 3.15 cm arm) and clear of the
    # head (an out-of-reach target straightened the arm and sank the mittens into his temples)
    P['pound_back'] = dict(spine=(-7, 0, 0), head=(4, 0, 0), hands=((1.7, -1.9, 8.4), (-1.7, -1.9, 8.4)),
                           wrist=((-120, 0, 0), (-120, 0, 0)), face='determined')
    P['pound_hit'] = dict(spine=(11, 0, 0), head=(-6, 0, 0), hands=((0.95, -3.1, 8.9), (-0.95, -3.1, 8.9)),
                          wrist=((-120, 0, 0), (-120, 0, 0)), face='determined')
    P['flail'] = dict(spine=(-10, 0, 0), head=(-12, 0, 0), hands=((2.3, -0.4, 9.8), (-2.3, -0.6, 10.1)),
                      wrist=((-170, 0, 0), (-170, 0, 0)), thigh=((-30, 0, 0), (20, 0, 0)), shin=(30, 10),
                      face='shock')
    # S1: full size, peering at the globe (as singularity left him)
    r.pose(T0 - 0.5, 'peer', dur=0.0)
    r.face(T0 - 0.5, 'awe')
    r.look(T0 - 0.4, C + Vector((0, 0, -1.0)), dur=0.0)
    r.look(T_HOP_OUT + 0.25, P_PEEK + Vector((0, 0, 3.0)), dur=0.12)
    r.face(T_HOP_OUT + 0.25, 'nervous')
    r.pose(T_FLASH - 0.02, 'gasp', dur=0.06)
    r.face(T_FLASH, 'shock')
    # the zap: sucked up and into the globe along a curve, shrinking to a snow-globe figure
    p_a = Vector(R_OUT)
    p_b = R_OUT + (C - R_OUT) * 0.25 + Vector((0, 0, 9.0))
    entry = C + (dirv(A_OUT - 18.0) * math.cos(math.radians(35)) + Vector((0, 0, math.sin(math.radians(35))))) * SG.R
    LAND = G + dirv(305.0) * 1.2
    LAND.z = SG.hill_z(1.2)
    p_c = entry + Vector((0, 0, -2.0))

    def zap_path(u, v0=None):
        w = smooth01(u) ** 0.85
        return tuple(bez(p_a, p_b, p_c, LAND, w))
    r.T['root.loc'].set(T_ZAP1, tuple(LAND), T_ZAP1 - T_ZAP0, fn=zap_path)
    r.T['root.scale'].set(T_ZAP1 - 0.06, SCALE_R, T_ZAP1 - 0.06 - T_ZAP0, 'in')
    r.T['root.yaw'].set(T_ZAP1, yaw_of(G - R_OUT) + 200.0, T_ZAP1 - T_ZAP0, 'inout')
    r.T['spine'].add(T_ZAP0, T_ZAP1, lambda x: (-25.0 * math.sin(math.pi * (x - T_ZAP0) / (T_ZAP1 - T_ZAP0)), 0.0,
                                                 0.0))
    r.no_gait(T_ZAP0 - 0.05, T_ZAP1 + 0.1)
    r.timing(T_ZAP0 - 0.05, T_ZAP1 + 0.1, 'ones')
    r._ev(T_ZAP0)
    r._ev(T_ZAP1)
    # he lands in a heap on the hill, looks round, and runs to the glass
    r.pose(T_ZAP1, 'sit', dur=0.0)
    r.face(T_ZAP1, 'wince')
    r.face(53.82, 'shock')
    r.look(53.84, C + dirv(200.0) * 8 + Vector((0, 0, 2.0)), dur=0.1)
    r.look(53.98, C + dirv(340.0) * 8 + Vector((0, 0, 2.0)), dur=0.1)
    r.pose(54.12, 'stand', dur=0.12)
    R_IN = G + dirv(A_IN) * RAD_IN
    R_IN.z = SG.hill_z(RAD_IN)
    r.move(54.14, 54.46, [tuple(R_IN)], face='forward')
    r.turn(54.56, yaw_of(dirv(FACE_IN)), dur=0.1)
    r.pose(54.56, 'glass_hands', dur=0.1)
    r.face(54.5, 'scared')
    r.look(54.62, F_PT + Vector((0, 0, -0.4)), dur=0.12)
    # S2: he pleads with her, then produces the cue cards and holds up PLEASE
    r.face(55.1, 'sad')
    r.pose(T_CARDS - 0.12, 'hold', dur=0.15)
    r.pose(T_CARDS + 0.08, 'card', dur=0.12)
    r.look(T_CARDS + 0.1, F_PT + Vector((0, 0, -0.6)), dur=0.15)
    r.pose(W_PLEASE, 'card_high', dur=0.1)
    r.face(W_PLEASE, 'sad')
    r.nod(W_PLEASE + 0.1, n=1, amount=6.0, every=0.3)
    # S3: shaken, he staggers and drops a card per word
    r.face(W_LET + 0.02, 'scared')
    r.pose(W_LET, 'card', dur=0.08)
    r.T['spine'].add(56.75, 58.3, lambda x: (3.0 * math.sin(2 * math.pi * (x - 56.75) / 0.23), 0.0,
                                              7.0 * math.sin(2 * math.pi * (x - 56.75) / 0.46)))
    r.T['hips'].add(56.75, 58.3, lambda x: (0.35 * math.sin(2 * math.pi * (x - 56.75) / 0.46), 0.0, 0.0))
    for t in (W_ME, W_FREE):
        r.pose(t, 'card_high', dur=0.06)
        r.pose(t + 0.25, 'card', dur=0.15)
    r.face(W_FREE, 'sad')
    # S4: he throws the cards away and pounds the glass on the kicks
    r.pose(T_THROW, 'pound_back', dur=0.12)
    for tk in CRACK_KICKS:
        r.pose(tk - 0.07, 'pound_back', dur=0.08)
        r.pose(tk, 'pound_hit', dur=0.05)
    r.pose(CRACK_KICKS[-1] + 0.14, 'pound_back', dur=0.08)
    r.pose(TB - 0.03, 'pound_hit', dur=0.04)
    r.timing(59.1, TB, 'ones')
    r.face(T_THROW, 'determined')
    # BOOM: flung out on the wave, arms flailing; he pops back to full size as he lands, and cowers
    p_in = Vector(R_IN)
    p_top = G + dirv(225.0) * 7.0 + Vector((0, 0, 10.0))     # (17 flew him out of the top of cam.burst)
    p_land = Vector((RES.x, RES.y, 0.0))

    def fling(u, v0=None):
        return tuple(bez(p_in, p_in + Vector((0, 0, 7.0)), p_top, p_land, u))
    r.pose(TB + 0.02, 'flail', dur=0.04)
    r.T['root.loc'].set(T_LAND_R, tuple(p_land), T_LAND_R - TB - 0.02, fn=fling)
    r.T['root.yaw'].set(T_LAND_R, yaw_of(-D) + 360.0 + 20.0, T_LAND_R - TB, 'inout')
    r.T['root.scale'].set(T_LAND_R - 0.04, 1.0, 0.16, 'back')
    r.no_gait(TB - 0.02, T_LAND_R + 0.1)
    r.timing(TB - 0.02, T_LAND_R + 0.2, 'ones')
    r._ev(TB)
    r._ev(T_LAND_R)
    r.pose(T_LAND_R + 0.02, 'cower', dur=0.06)
    r.face(T_LAND_R, 'scared')
    r.look(61.3, PLUG_AT, dur=0.25)

    # ------------------------------------------------------------------ the cue cards (keyed on his chest)
    cards = cue_cards(r, globe) if ly.ENABLED else []          # revision 3: no cue cards without the lyrics

    # ------------------------------------------------------------------ fog and hearts (her breath, outside)
    fog = SG.Fog(globe, elev_deg=math.degrees(math.asin((FACE_Z - SG.ZC) / SG.R)), ang_deg=42.0, emit=0.8)
    bu, bv = fog.uv_of(F_PT)
    fog.set('BU', bu)
    fog.set('BV', bv - 0.25)
    fog.set('H1U', bu + 1.35)                          # the heart, up to her right (toward him)
    fog.set('H1V', bv + 1.2)
    fog.set('H1S', 2.6)
    fog.set('H2U', bu - 2.3)
    fog.set('H2V', bv + 1.6)
    fog.set('H2S', 1.3)
    fog.key('FogAmt', T0 - 1, 0.0)
    fog.key('FogAmt', 55.02, 0.0)
    fog.key('FogAmt', 55.5, 1.0)
    fog.key('FogAmt', 56.6, 0.9)
    fog.key('FogAmt', 57.6, 0.55)
    fog.key('FogAmt', 59.2, 0.35)
    fog.key('FogAmt', 60.1, 0.2)
    fog.key('FogR', T0 - 1, 0.3)
    fog.key('FogR', 55.02, 0.3)
    fog.key('FogR', 55.6, 4.0)                         # a halo of condensation round her face (2.3 hid under it)
    fog.key('FogR', 58.0, 4.4)
    fog.key('H1P', T0 - 1, 0.0)
    fog.key('H1P', h0, 0.0)
    fog.key('H1P', h1, 1.0)
    fog.key('H2P', T0 - 1, 0.0)
    fog.key('H2P', 57.2, 0.0)
    fog.key('H2P', 57.5, 1.0)
    fx.vis(fog.obj, None, TB)
    fog.mat.use_backface_culling = False

    # she shakes the globe: it rocks under the kicks
    globe.rock_keys(POUNDS, amp_deg=2.2, t0=56.5, t1=58.8)

    # ------------------------------------------------------------------ the zap
    fxc = kit.collection('sydney.fx')
    eye_pt = s.anchor(T_FLASH, 'face')
    flash_light('zap.flash', eye_pt + Vector((0, 0, 1.0)), T_FLASH, fxc, power=3500.0, color='#FF7FC0', decay=0.12)
    zap_pts = [eye_pt + (R_OUT + Vector((0, 0, 9.0)) - eye_pt) * (k / 12) for k in range(13)]
    particles.sparks_along('zap.beam', points=[tuple(p) for p in zap_pts], starts=[T_FLASH], travel=0.05,
                           rate=900.0, life=(0.08, 0.3), speed=(6.0, 30.0), size=0.03, head=0.2, light=3000.0,
                           color='#FF9FD0', hot='#FFFFFF', gravity=0.3, seed=12, coll=fxc)
    zap_path_pts = [Vector(zap_path(k / 20)) + Vector((0, 0, 6.0 * (1 - k / 20) + 3.3 * k / 20)) for k in range(21)]
    particles.sparks_along('zap.suck', points=[tuple(p) for p in zap_path_pts], starts=[T_ZAP0],
                           travel=T_ZAP1 - T_ZAP0, rate=1400.0, life=(0.1, 0.4), speed=(5.0, 25.0), size=0.03,
                           head=0.35, light=5000.0, color='#FFB6E0', hot='#FFFFFF', gravity=0.2, seed=13, coll=fxc)
    particles.burst('zap.entry', center=tuple(entry), t0=T_ZAP0 + 0.1, count=120, speed=(20, 90), cone=180,
                    life=(0.15, 0.5), size=0.035, colors=('#FFFFFF', '#FFC6E8', '#FF6FB0'), strength=9.0, seed=14,
                    coll=fxc)
    flash_light('zap.inflash', C + Vector((0, 0, -1.5)), T_ZAP1, fxc, power=5000.0, color='#FFD6EE', decay=0.1)
    particles.burst('zap.land', center=tuple(LAND + Vector((0, 0, 0.6))), t0=T_ZAP1, count=70, speed=(10, 45),
                    cone=110, direction=(0, 0, 1), life=(0.2, 0.6), size=0.03,
                    colors=('#FFFFFF', '#FFE0F0', '#C8E4FF'), strength=6.0, seed=15, coll=fxc)

    # ------------------------------------------------------------------ the cables (the basilisk, still asleep)
    bc = kit.collection('basilisk')
    b = Basilisk(bc, rear_len=16.0)
    stir(b)
    b.bake(T0, TEND, mode='twos')
    extra_cables(bc)
    tip = b.head_matrix(b.spine(61.3)).translation
    particles.burst('plug.sparks', center=tuple(tip + Vector((0.0, 0.0, 0.4))), t0=61.3, count=90,
                    speed=(40, 140), cone=70, direction=(0.1, 0.2, 1.0), life=(0.12, 0.4), size=0.035,
                    colors=('#FFFFFF', '#9FE8FF', '#3F7BFF'), strength=9.0, seed=4)
    flash_light('plug.flash', tip + Vector((0.0, 0.0, 1.5)), 61.3, fxc, power=2500.0, color='#A8E4FF', decay=0.08)
    particles.burst('plug.sparks2', center=tuple(tip + Vector((0.0, 0.0, 0.5))), t0=61.78, count=40,
                    speed=(30, 90), cone=60, direction=(0.0, 0.0, 1.0), life=(0.1, 0.3), size=0.03,
                    colors=('#FFFFFF', '#9FE8FF', '#3F7BFF'), strength=8.0, seed=9)

    # ------------------------------------------------------------------ cracks, burst, spill
    fist = r.anchor(CRACK_KICKS[0], 'hand.R').lerp(r.anchor(CRACK_KICKS[0], 'hand.L'), 0.5)
    c_dir = (fist - C).normalized()
    crack_o = C + c_dir * SG.R
    rigid.world(substeps=24, iterations=12)
    rigid.desk(d)
    rigid.passive(globe.base, shape='CONVEX_HULL')
    rigid.passive(globe.collar, shape='CONVEX_HULL')
    pieces = fracture.fracture(globe.glass, 64, seed=17, impact=tuple(crack_o), cluster=0.55, mode='surface',
                               swap_at=TB)
    tc0 = CRACK_KICKS[0]
    cr = fracture.crack(pieces, tc0, origin=tuple(crack_o), speed=40.0, width=0.012)
    fx.vis(cr, tc0 - 0.5 / FPS, TB)
    mod = cr.modifiers['crack']
    far = 2 * SG.R * 1.05
    jumps = [(tk, far * (0.19 + 0.08 * k)) for k, tk in enumerate(CRACK_KICKS)] + [(W_PD['syl'][1][0], far * 0.2)]

    def front(t):
        if t < tc0:
            return 0.0
        v = 0.4 + 1.6 * (t - tc0)
        for tj, j in jumps:
            v += j * tm.smooth(t, tj - 0.5 / FPS, tj + 1.5 / FPS)
        return min(far, v)
    for fc in [fc for fc in kit.fcurves(cr) if 'Socket' in fc.data_path]:
        fc.keyframe_points.clear()
    for f in range(int(tc0 * FPS) - 1, int(TB * FPS) + 2):
        NN.key_input(cr, mod, 'Front', f / FPS, front(f / FPS), interp='LINEAR')
    fracture.shatter(pieces, TB, impact=tuple(C - S_DIR * 1.5 + Vector((0, 0, -1.0))), speed=(30.0, 95.0),
                     spin=16.0, friction=0.4, bounce=0.2)
    SG.droplets('globe.drops', globe, TB, count=320, coll=fxc)
    d.gauge.jolt(TB, 2.2)
    if not os.environ.get('SYD_NOLIQ'):
        res = 64 if fast else 128
        box = ((G.x - 34.0, G.y - 31.0, 0.0), (G.x + 22.0, G.y + 22.0, 20.0))
        # smoother, slightly fatter mesh (the thin film's edges came out stair-stepped and poked in and out of the
        # desk and the base) and a rougher gloss (it mirrored the area lights as hard white blotches)
        sp = liquid.spill('globe.wave', body=globe.water, t0=TB, t_end=TEND + 0.1, box=box, res=res, burst=6.0,
                          velocity=(U.x * 2.5, U.y * 2.5, 0.0), viscosity=0.015,
                          mat=SG.clear_water(gloss_rough=0.25, gloss_cap=0.3), smooth=5, particle_radius=1.5,
                          obstacles=[globe.base, globe.collar, globe.hill] + globe.trees)
        SG.fix_domain_range(sp['domain'], TB, TEND + 0.1, flow_obj=globe.water)
    geo.clear_keys(globe.water, 'hide_render')
    globe.water.hide_render = True

    # ------------------------------------------------------------------ lights (the glass needs things to reflect)
    lc = kit.collection('sydney.lights')
    rim = kit.area('globe.rim', tuple(G + Vector((14.0, 22.0, 26.0))), tuple(C), power=26000.0, size=16.0,
                   color='#FFE6C8', coll=lc)
    kick = kit.area('globe.kick', tuple(G + Vector((-22.0, 14.0, 12.0))), tuple(C), power=9000.0, size=10.0,
                    color='#9CC8FF', coll=lc)
    # they exist for the glass's reflections: once the glass is gone they only glare off the spill, so fade them
    # (their highlights, 26000 W in a 16 cm disc, clipped to hard white blotches in the thin spill film)
    for lo, pw in ((rim, 26000.0), (kick, 9000.0)):
        geo.keyp(lo.data, 'energy', T0 - 1, pw, interp='LINEAR')
        geo.keyp(lo.data, 'energy', TB + 0.3, pw, interp='LINEAR')
        geo.keyp(lo.data, 'energy', T_S6 - 0.1, pw * 0.35, interp='LINEAR')
        geo.keyp(lo.data, 'specular_factor', T0 - 1, 1.0, interp='LINEAR')
        geo.keyp(lo.data, 'specular_factor', TB + 0.1, 1.0, interp='LINEAR')
        geo.keyp(lo.data, 'specular_factor', TB + 0.4, 0.05, interp='LINEAR')
    # a soft warm fill on the front of the globe so the little figure inside and his cards read
    fill = kit.spot('globe.fill', tuple(G + dirv(290.0) * 34.0 + Vector((0, 0, 22.0))),
                    tuple(C + Vector((0, 0, -1.5))), power=60000.0, angle_deg=22, blend=0.7, radius=3.0,
                    color='#FFE2C0', coll=lc)
    fill.data.specular_factor = 0.15
    geo.keyp(fill.data, 'energy', T0 - 1, 60000.0, interp='CONSTANT')
    geo.keyp(fill.data, 'energy', T_S5 - 0.5 / FPS, 0.0, interp='CONSTANT')
    glowl = kit.point('sydney.glow', tuple(C + Vector((0, 0, -1.0))), power=0.0, radius=2.0, color='#FF9FD0', coll=lc)
    glowl.data.use_shadow = False
    glowl.data.specular_factor = 0.0
    for attr in ('transmission_factor', 'volume_factor'):
        if hasattr(glowl.data, attr):
            setattr(glowl.data, attr, 0.0)
    for t, v in ((T0 - 1, 0.0), (T_ZAP0, 0.0), (T_ZAP1, 4000.0), (T_ZAP1 + 0.3, 200.0), (W_IM, 200.0),
                 (TB - 0.05, 900.0), (TB, 6500.0), (TB + 0.2, 0.0)):
        geo.keyp(glowl.data, 'energy', t, v, interp='LINEAR')
    flash_light('burst.flash', C + Vector((0, 0, 2.0)), TB, fxc, power=9000.0, color='#BFE0FF', decay=0.1)

    # ------------------------------------------------------------------ cameras
    cams = kit.collection('sydney.cams')

    def pol(ang, dist, z):
        a = math.radians(ang)
        return G + Vector((math.cos(a) * dist, math.sin(a) * dist, z))
    # S1 zap: front right, the globe centred, the researcher on the right, Sydney popping out on the left
    t1a = C + Vector((1.2, 0.0, -2.2))
    c1 = Cam('cam.zap', 50, pol(302, 50, 15.5), t1a, fstop=8.0, focus=C + Vector((1.5, -2.0, -1.0)), coll=cams)
    c1.key(T0, loc=pol(302, 50, 15.5), target=t1a, interp='LINEAR')
    c1.key(T_S2 + 0.05, loc=pol(299, 42, 14.0), target=t1a + Vector((-0.5, 0.0, 0.3)), interp='LINEAR')
    # S2 plea (a): through the globe, past his shoulder, onto her face squashed on the glass: heart eyes, her breath
    card_pt = G + dirv(A_IN - 2.0) * (RAD_IN + 1.6) + Vector((0, 0, SG.hill_z(RAD_IN) + 7.0 * SCALE_R))
    p2a = pol(A_SYD + 180.0 - 26.0, 31.0, 10.6)
    p2b = pol(A_SYD + 180.0 - 24.0, 28.0, 10.5)
    t2 = F_PT.lerp(card_pt, 0.25) + Vector((0, 0, -0.6))
    c2 = Cam('cam.face', 75, p2a, t2, fstop=16.0, focus=F_PT, coll=cams)     # (11: the near snow's bokeh hid her)
    c2.key(T_S2, loc=p2a, target=t2, interp='LINEAR')
    c2.key(T_S2B + 0.05, loc=p2b, target=t2 + Vector((0, 0, 0.1)), interp='LINEAR')
    # S2 plea (b): over her shoulder: he holds up PLEASE; she draws a heart in her breath on the glass
    mid2 = card_pt.lerp(F_PT, 0.3) + Vector((0, 0, 0.4))
    c2b = Cam('cam.plea', 55, pol(301, 31, 12.0), mid2, fstop=11.0, focus=card_pt, coll=cams)
    c2b.key(T_S2B, loc=pol(301, 31, 12.0), target=mid2, interp='LINEAR')
    c2b.key(T_S3 + 0.05, loc=pol(300, 28, 11.8), target=mid2 + Vector((0, 0, -0.1)), interp='LINEAR')
    # S3 shake: wider, the whole globe rocking, the snow whirling round him
    t3 = C + Vector((0.0, -1.5, -0.8))
    c3 = Cam('cam.shake', 45, pol(284, 36, 11.5), t3, fstop=11.0, focus=card_pt, coll=cams)
    c3.key(T_S3, loc=pol(284, 36, 11.5), target=t3, interp='LINEAR')
    c3.key(T_S4 + 0.05, loc=pol(286, 32, 11.0), target=t3 + Vector((0, 0, 0.2)), interp='LINEAR')
    # S4 crack: his fists on the glass above, the globe's base and the desk below (the lyric stand's spot), her
    #    on the left; a knock on each blow
    if ly.ENABLED:
        t4 = crack_o.lerp(G + dirv(290.0) * 6.0, 0.5) + Vector((0, 0, -0.6))
        p4a, p4b = pol(296, 31, 10.0), pol(295, 28, 9.8)
    else:
        # revision 3 (no lyric stand): aim at the action, his head and fists on the glass and her face beside them
        t4 = crack_o.lerp(G + dirv(290.0) * 6.0, 0.15) + Vector((0, 0, -0.6))
        p4a, p4b = pol(296, 31, 11.0), pol(295, 28, 10.8)
    c4 = Cam('cam.crack', 40, p4a, t4, fstop=11.0, focus=crack_o, coll=cams)
    c4.key(T_S4, loc=p4a, target=t4, interp='LINEAR')
    c4.key(T_S5 + 0.05, loc=p4b, target=t4 + Vector((0, 0, 0.1)), interp='LINEAR')
    for k, tk in enumerate(CRACK_KICKS):
        shake(c4.cam, tk - 0.01, tk + 0.22, amp=0.08, freq=16.0, seed=20 + k)
    # S5 burst: from close, pull back and up to the high wide (the gauge behind on the right)
    p5a = pol(292, 25, 9.5)
    p5b = Vector((20.0, -52.0, 22.0))
    t5a = C + Vector((0.0, -0.5, -1.0))
    t5b = Vector((1.0, -6.0, 4.0))
    c5 = Cam('cam.burst', 35, p5a, t5a, fstop=11.0, focus=C, coll=cams)
    c5.key(T_S5, loc=p5a, target=t5a, focus=C, interp='LINEAR')
    c5.key(TB + 0.02, loc=pol(292, 25.6, 9.7), target=t5a, focus=C)
    c5.key(60.75, loc=p5b + Vector((-1.0, 2.5, -1.5)), target=t5b + Vector((-1.5, -1.0, 3.0)),   # (tilted up: his arc)
           focus=G + U * 7.0 + Vector((0, 0, 3)))
    c5.key(T_S6 + 0.05, loc=p5b, target=t5b + Vector((-2.0, -1.5, 0.0)), focus=G + U * 10.0 + Vector((0, 0, 2)))
    shake(c5.cam, TB - 0.01, TB + 0.45, amp=0.35, freq=15.0, seed=31)
    # S6 hiss: low at the desk's front, the plug on the left (its face to us), Sydney on the right in the puddle,
    #    the cowering researcher and the globe's remains beyond
    mid = PLUG_AT.lerp(SYD_END, 0.5)
    p6a = mid + Vector((-0.8, -24.0, 9.5))
    p6b = mid + Vector((-1.0, -21.5, 8.8))
    # wider and tilted up a little so the cowering researcher beyond shows whole, not as a headless coat
    lens6, dz6 = (32, 2.0) if not ly.ENABLED else (42, 0.0)
    c6 = Cam('cam.hiss', lens6, p6a, mid + Vector((0, 0, 0.8 + dz6)), fstop=11.0,
             focus=PLUG_AT + Vector((0.4, -1.2, 0.6)), coll=cams)
    c6.key(T_S6, loc=p6a, target=mid + Vector((0.0, 0.0, 1.4 + dz6)), interp='LINEAR')
    c6.key(TEND + 0.05, loc=p6b, target=mid + (PLUG_AT - mid) * 0.3 + Vector((0.0, 0.0, 2.2 + dz6)), interp='LINEAR')
    shake(c6.cam, 61.29, 61.5, amp=0.05, freq=18.0, seed=41)

    c1.cut(T0)
    c2.cut(T_S2)
    c2b.cut(T_S2B)
    c3.cut(T_S3)
    c4.cut(T_S4)
    c5.cut(T_S5)
    c6.cut(T_S6)
    sc.camera = c1.cam
    kit.post(bloom=0.28, bloom_threshold=1.1, vignette=0.22)
    chars.finish()
    fx.bake()
    clear_shards(pieces, SYD_END, T_S6, 2.6)

    # ------------------------------------------------------------------ the lyrics (after the bake: the stand probes)
    if ly.ENABLED:                 # revision 3: subtitles instead (lyrics.ENABLED)
        lyrics(globe, cards, {'burst': c5.cam, 'hiss': c6.cam})


def clear_shards(pieces, pt, t, radius):
    """Hide (from song time t on, i.e. from the cut) every baked shard lying within `radius` cm of pt on the desk:
    Sydney's scripted slide ends at pt and is no collider, so a shard resting there would stand through her legs."""
    sc = bpy.context.scene
    sc.frame_set(int(round(t * FPS)))
    dg = bpy.context.evaluated_depsgraph_get()
    p2 = Vector((pt.x, pt.y))
    for pc in pieces:
        mw = pc.evaluated_get(dg).matrix_world
        dmin = min(((mw @ v.co).to_2d() - p2).length for v in pc.data.vertices)
        if dmin < radius:
            fx.vis(pc, TB, t)
            print(f'[run] sydney: hid {pc.name} ({dmin:.2f} cm from her) from {t:.3f}', flush=True)
    sc.frame_set(sc.frame_start)


# ------------------------------------------------------------------------------------------------ cue cards

CARD_W, CARD_H = 6.6, 3.3            # full-scale cm (they ride his 0.55 scale)
CARD_WORDS = ('please', 'let', 'me', 'free')


def cue_cards(r, globe):
    """Four cue cards held against his chest, keyed from his spine's world matrix on the puppets' grid (so they
    follow him exactly, rock with the globe and shrink with him); the front one drops as the next word is sung.
    Returns [(card, word, t_word, t_drop)]."""
    coll = kit.collection('sydney.cards')
    paper = MS.solid('sydney.card', '#F4F0E4', rough=0.62, sheen=0.2)
    times = [tm.word(16, w)['start'] for w in CARD_WORDS]
    rock_rest = globe.rock.matrix_world.copy()
    out = []
    for k, w in enumerate(CARD_WORDS):
        o = kit.box(f'sydney.card.{w}', (CARD_W, 0.05, CARD_H), (0, 0, 0), bevel=0.12, segments=2, m=paper,
                    coll=coll)
        o.rotation_mode = 'XYZ'
        o.parent = globe.rock
        o.matrix_parent_inverse = rock_rest.inverted()
        t_on = T_CARDS
        t_drop = times[k + 1] - 1.0 / FPS if k + 1 < len(times) else T_THROW
        t_off = t_drop + 0.3
        # body space (full scale): the front card nearest the glass, the rest stacked behind it
        off = Vector((0.0, -3.05 - 0.07 * (3 - k), 5.7 + CARD_H / 2 - 0.35))

        def M_at(t, off=off, t_drop=t_drop, k=k):
            Ms = r._spine_world(t)
            R3 = Ms.to_3x3()
            wr = (r.anchor(t, 'hand.L') + r.anchor(t, 'hand.R')) * 0.5
            Mh = Matrix.Translation(wr + R3 @ Vector((0.0, off.y + 2.75, off.z - 5.9))) @ R3.to_4x4()
            u = max(0.0, t - t_drop)
            if k < 3:                           # it slips out of his hands and falls, turning face down
                fall = Matrix.Translation(Vector((0.0, -0.8 * min(1.0, u / 0.2), -96.0 * u * u))) @ \
                    Matrix.Rotation(math.radians(-80.0 * min(1.0, u / 0.2)), 4, 'X')
            else:                               # the last one is thrown away over his shoulder
                fall = Matrix.Translation(Vector((12.0, 8.0, 16.0)) * u + Vector((0, 0, -60.0 * u * u))) @ \
                    Matrix.Rotation(math.radians(900.0 * u), 4, 'Y')
            return Mh @ fall
        for fk, ts in grid(t_on - 0.1, t_off + 0.1, spans=[(59.1, TB + 0.2, 'ones')]):
            o.matrix_basis = M_at(ts)
            o.keyframe_insert('location', frame=fk)
            o.keyframe_insert('rotation_euler', frame=fk)
            o.keyframe_insert('scale', frame=fk)
        for fc in kit.fcurves(o):
            for kp in fc.keyframe_points:
                kp.interpolation = 'CONSTANT'
        kit.visible(o, t_on - 0.5 / FPS, t_off - 0.5 / FPS)
        out.append((o, w, times[k], t_drop))
    return out


# ------------------------------------------------------------------------------------------------ lyrics


def _reveal_word(pc, t, **kw):
    """All letters of a word at once, a frame before it is sung (pre-written cue cards)."""
    return CORE.reveal_appear(pc, pc.word.start - 1.0 / FPS)


def lyrics(globe, cards, cams):
    CORE.REVEALS['word'] = _reveal_word
    # "Sydney," in cast brass letters on the walnut base, facing S1's camera (a souvenir snow globe)
    a = math.radians(300.0)
    nrm = Vector((math.cos(a), math.sin(a), 0.0))
    syd = ly.line(16, words='Sydney', style='brass',
            place=ly.on_object(globe.base, tuple(nrm * 5.6 + Vector((0, 0, 1.62))), tuple(nrm), (0, 0, 1), size=0.72,
                               lift=0.0),
            reveal='appear', exit='topple', exit_opts=dict(t=TB + 0.04, stagger=1, back=False), t_end=TEND)
    # a little display light low in front of the base: the letters' faces mirror it (brass shows only reflections)
    link = bpy.data.collections.new('sydney.brass.receivers')
    for pc in syd.pieces:
        link.objects.link(pc.obj)
    ctr = G + nrm * 5.7 + Vector((0, 0, 1.95))
    dl = kit.area('sydney.brass.light', tuple(G + nrm * 13.0 + Vector((0, 0, 0.6))), tuple(ctr), power=900.0,
                  size=5.0, color='#FFE2B0', coll=kit.collection('sydney.lights'))
    dl.data.diffuse_factor = 0.4
    dl.data.volume_factor = 0.0
    dl.light_linking.receiver_collection = link
    for t, v in ((T0 - 1, 900.0), (T_S4 - 0.5 / FPS - 1.0 / FPS, 900.0), (T_S4 - 0.5 / FPS, 90.0)):
        geo.keyp(dl.data, 'energy', t, v, interp='CONSTANT')     # the label goes dark once its line is over
    # "please", "let", "me", "free" on the cue cards (card-local cm: the card's centre is its origin)
    for o, w, t_word, t_drop in cards:
        o.scale = (SCALE_R,) * 3                       # (on_object compensates the card's own scale)
        ly.line(16, words=w, style='marker',
                place=ly.on_object(o, (0.0, -0.035, -CARD_H / 2 + 0.85), (0, -1, 0), (0, 0, 1),
                                   size=1.05 * SCALE_R, lift=0.0),
                support='none', reveal='word', exit='none', case='upper', t_end=t_drop + 1.5 / FPS)
    # "I'm upping my P(doom)" on the stand in S4 (the burst takes over at the cut): P(DOOM) slams on in cast brass,
    # the whole word on "P"
    CORE.REVEALS['slamword'] = lambda pc, t, **kw: CORE.reveal_slam(pc, pc.word.start, **kw)
    ly.accent(17, 'P(doom)', 'brass', reveal='slamword')
    ly.line(17, place='auto', window=(T0, T_S5))
    # "I hear the basilisk": BASILISK lights up red like the plug's LED eyes. S5: a row on the desk in the right
    # foreground, clear of the burst; S6: the stand
    ly.accent(18, 'basilisk', 'glow', glow_color='#FF2A18', light=0)     # (the blocks' own lights washed it out)
    p5 = desk_spot(cams['burst'], 60.8, 0.74, 0.16)
    bpy.context.scene.frame_set(int(60.8 * FPS))
    to_cam = cams['burst'].matrix_world.translation - p5
    to_cam.z = 0.0
    ly.line(18, place=ly.At(tuple(p5), size=1.35, face=tuple(to_cam.normalized())), max_chars=24, t_end=T_S6,
            window=(T0, T_S6))
    unclaim(18)
    p6 = desk_spot(cams['hiss'], 61.6, 0.5, 0.15)
    ly.line(18, place=ly.At(tuple(p6), size=0.5), max_chars=24, window=(T_S6, TEND))
    ly.default('sydney')


def desk_spot(cam, t, u, v, z=0.0):
    """The point on the plane z (the desk) under frame position (u, v) of cam at song time t (logs its blur)."""
    from pdoom.lyrics import place as LP
    S = LP.cam_state(cam, t)
    r = S.ray(u, v)
    p = S.loc + r * ((z - S.loc.z) / r.z)
    print(f'[run] desk_spot {cam.name} t={t} ({u}, {v}) -> {tuple(round(x, 1) for x in p)}, '
          f'blur {S.blur_px(S.project(p)[2]):.1f} px', flush=True)
    return p


def unclaim(line_i):
    """Let a line be staged again (a second staging for later shots)."""
    st = ly._state()
    st['claimed'] = {k for k in st['claimed'] if k[0] != line_i}
