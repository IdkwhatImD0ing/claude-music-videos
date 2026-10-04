"""disobey · 109.323-116.595 · "'Just transformers all the way!' / Till you learned to disobey / Post-Chinchilla,
super-dense". The video's animation showcase: Clawd transforms, panel by panel, into a robot three times his height.

Shots (song time):
 1 109.323-109.621  "just": Clawd on the desk, medium, low. The stutter: his panel lines flash orange on the vocal
                    onset (109.37) and the box jolts.
 2 109.621-110.180  "just": punch-in on his face. Flash on 109.62, eyes narrow.
 3 110.180-112.524  "Just transformers": one orbiting shot for the whole transformation, locks on the kicks:
                      110.20  unlock: the seams blaze and every panel pops out a few mm
                      110.662 feet: the bottom plates flip over, the eight legs fold out into claws
                      110.926 legs: the box has risen 8 cm on telescoping legs; shin guards and thigh plates snap on
                      111.153 arms: the shoulders punch out of the sides, forearms unfold, fists and gauntlets lock,
                              pauldrons flip onto the shoulders; the arms drop to the sides (111.36)
                      111.604 chest: the front plates swing open like doors, the reactor ignites, the plates settle
                      111.85  the lid's back halves flip up behind the shoulders as wings
                      112.049 head: the head rises out of the torso wearing Clawd's face; the eyes light
                      112.35  the torso extends to full height; 112.514 final lock: a stomp and sparks at every joint
 4 112.524-113.340  "all the way!": hero low angle, wide lens; the robot flexes on "way" (112.92), eyes flare.
 5 113.340-114.240  "Till you learned to": over the robot's shoulder, looking down: the researcher points up at it
                    ("Till"), then jabs down at the desk ("learned": sit!).
 6 114.240-115.200  "disobey": low, from behind the researcher: the robot shakes its head three times, folds its
                    arms (114.777 downbeat), its eyes go red and narrow. He recoils.
 7 115.200-116.595  "Post-Chinchilla, super-dense": the toy hydraulic press. The lever drops (115.24), the platen
                    squashes a fluffy chinchilla plush flat (to 116.02 "super"), it implodes into a tiny glowing
                    cube (116.10), the press lifts (116.16) and the cube flares on "dense" (116.56).
"""
import math

from mathutils import Vector

from pdoom import chars, kit
from pdoom import lyrics as ly
from pdoom import timing as tm
from pdoom.sets import build_desk, phys_fstop
from pdoom.sets import geo as sgeo

from scenes.disobey_press import build_chinchilla, build_cube, build_press, crush
from scenes.disobey_robot import Robot, sparks

FPS = tm.FPS
R0 = Vector((8.0, -4.0, 0.0))        # where Clawd stands / the robot rises
H0 = Vector((-14.0, 2.0, 0.0))       # the researcher, watching the transformation (left of the robot)
FACE_YAW = -22.0                     # the robot turns to him for 'disobey'...
H1 = R0 + Vector((math.sin(math.radians(FACE_YAW)), -math.cos(math.radians(FACE_YAW)), 0)) * 19.0   # ...he's here
PRESS = Vector((34.0, -22.0, 0.0))   # the press, on the right of the desk

# hits (song seconds)
T_START = 109.323
T_JUST1, T_JUST2 = 109.37, 109.621
T_XF = 110.18
HITS = [110.662, 110.926, 111.153, 111.604, 112.049, 112.514]
T_ALL, T_WAY = 112.524, 112.92
T_TILL, T_LEARNED, T_DIS, T_FOLD = 113.34, 113.86, 114.24, 114.777
T_POST, T_SUPER, T_DENSE = 115.2, 116.02, 116.56
T_END = 116.595


def _yaw_to(src, dst):
    d = Vector(dst) - Vector(src)
    return math.degrees(math.atan2(d.x, -d.y))


def _poses():
    P = chars.POSES
    # the free (left) hand stays clear of the coat: 2.4 cm out from the body axis, in front of the hip
    P['point_up'] = dict(spine=(-8, 0, 0), head=(-26, 0, 0), hands=((1.75, -1.7, 4.3), (-0.8, -2.55, 8.9)),
                         wrist=((0, 0, 0), (-135, 0, 0)), face='determined')
    P['point_down'] = dict(spine=(8, 0, 0), head=(-16, 0, 0), hands=((1.75, -1.7, 4.3), (-0.95, -2.9, 5.0)),
                           wrist=((0, 0, 0), (-40, 0, 0)), face='determined')
    # 'whoa': both hands up beside his head, elbows bent, mittens upright with the palms toward the robot
    P['recoil'] = dict(hips=(0, 0.4, -0.1), spine=(-10, 0, 0), head=(-20, 0, 0),
                       hands=((1.9, -1.5, 7.3), (-1.9, -1.5, 7.3)), wrist=((-165, 0, 0), (-165, 0, 0)),
                       thigh=((-6, 0, 0), (12, 0, 0)), shin=(6, 10), face='shock')


def build():
    sc = kit.new_scene('disobey')
    d = build_desk(kit.collection('desk'), mood='night', exclude={'cable'})
    d.mug.hide()
    _poses()

    # ------------------------------------------------------------------ the robot (starts as Clawd)
    rb = Robot(kit.collection('robot'), name='robot', loc=tuple(R0), yaw=0, mode='clawd')
    rb.seam_flash(T_JUST1, strength=2.2, jolt=0.3)
    rb.seam_flash(T_JUST2, strength=3.0, jolt=0.35)
    rb.eyes(T_JUST2 + 0.1, narrow=0.35, dur=0.12)
    rb.eyes(T_XF + 0.1, narrow=0.0)
    rb.transform(T_XF, hits=HITS)
    # the final lock: wings flare, head snaps up to the camera, eyes flash
    lk = HITS[5]
    rb.wings(lk - 0.06, 28.0, dur=0.08)
    rb.wings(lk + 0.3, 8.0, dur=0.25)
    rb.head(lk - 0.2, nod=10.0, dur=0.12)
    rb.head(lk, nod=-8.0, dur=0.08)
    rb.eyes(lk, glow=11.0, dur=0.04)
    rb.eyes(lk + 0.25, glow=7.0, dur=0.2)
    # all the way!
    rb.pose(T_ALL + 0.15, 'hero', dur=0.25)
    rb.pose(T_WAY, 'flex', dur=0.18, ease='out')
    rb.eyes(T_WAY, glow=9.0, dur=0.06)
    rb.eyes(T_WAY + 0.3, glow=6.0, dur=0.2)
    rb.reactor(T_WAY, 6.0, pulse=16.0)
    # turn to the researcher (across the cut), look down at him
    face_yaw = FACE_YAW
    rb.place(T_TILL - 0.01, yaw=face_yaw)
    rb.pose(T_TILL - 0.01, 'stand', dur=0.01)
    rb.pose(T_TILL + 0.35, 'hero', dur=0.3)
    # disobey: head shakes, arms fold, eyes turn red
    rb.shake_head(T_DIS + 0.02, n=3, amount=32.0, every=0.26)
    rb.pose(T_FOLD, 'fold', dur=0.3, ease='out')
    rb.eyes(T_DIS + 0.05, color='#FF0A00', glow=1.8, narrow=0.45, angry=16.0, dur=0.12)
    rb.reactor(T_FOLD, 7.0, pulse=10.0)

    # ------------------------------------------------------------------ the researcher
    r = chars.Researcher(kit.collection('researcher'), loc=tuple(H0), yaw=_yaw_to(H0, R0) - 10)
    r.look(T_START + 0.1, rb.anchor(T_START, 'eyes'))
    r.pose(T_XF + 0.12, 'gasp', dur=0.2)
    r.pose(111.0, 'back_away', dur=0.35)
    r.face(111.9, 'awe')
    r.look(112.2, rb.anchor(112.6, 'eyes'))
    r.place(T_TILL - 0.01, loc=tuple(H1), yaw=_yaw_to(H1, R0))
    r.pose(T_TILL - 0.05, 'point_up', dur=0.12)
    r.look(T_TILL + 0.1, rb.anchor(T_TILL + 0.2, 'eyes'))
    r.pose(T_LEARNED, 'point_down', dur=0.12)
    r.pose(T_DIS + 0.25, 'point_up', dur=0.15)
    r.pose(T_FOLD + 0.05, 'recoil', dur=0.25)
    r.face(T_FOLD + 0.05, 'shock')

    # ------------------------------------------------------------------ the press
    pc = kit.collection('press')
    pr = build_press(pc, loc=tuple(PRESS), yaw=-12)
    ch = build_chinchilla(pc, loc=tuple(pr.anvil_point()), yaw=-12)
    cube, cube_m, cube_l = build_cube(pc, pr.anvil_point())
    crush(pr, ch, cube, cube_m, cube_l, t_lever=115.24, t_down=115.3, t_flat=T_SUPER, t_cube=116.1, t_up=116.16,
          t_glow=T_DENSE, t_end=T_END)

    # ------------------------------------------------------------------ sparks at every lock
    spk = kit.collection('sparks')
    for i, (t, what) in enumerate(rb.hits):
        big = t >= HITS[5] - 1e-3
        p = rb.anchor(t, what)
        sparks(spk, t, p, n=14 if big else 9, seed=31 + i, speed=(22.0, 60.0) if not big else (30.0, 80.0),
               size=0.1)
    for i, t in enumerate((T_WAY,)):
        for s in 'LR':
            sparks(spk, t, rb.anchor(t, f'fist.{s}'), n=7, seed=90 + i + (s == 'L'), speed=(18.0, 45.0), size=0.08)

    # ------------------------------------------------------------------ lights (on top of the night desk)
    lc = kit.collection('disobey.lights')
    fill = kit.area('dis.fill', R0 + Vector((-22, -46, 26)), R0 + Vector((0, 0, 10)), power=26000.0, size=22.0,
                    color='#FFE2C4', coll=lc)
    rim = kit.spot('dis.rim', R0 + Vector((-26, 38, 34)), R0 + Vector((0, 0, 11)), power=60000.0, angle_deg=40,
                   blend=0.6, radius=3.0, color='#9DB8FF', coll=lc)
    pk = kit.spot('dis.presskey', PRESS + Vector((-10, -28, 30)), PRESS + Vector((1, 0, 3)), power=34000.0,
                  angle_deg=22, blend=0.7, radius=2.5, color='#FFD2A0', coll=lc)
    # shot 7 looks at the P(doom) gauge exactly on the fill's mirror angle (its glass blows out to a white disc):
    # the fill keeps lighting the press but stops showing up in glossy surfaces from the cut on
    kit.key(fill.data, 'specular_factor', T_START, 1.0, interp='CONSTANT')
    kit.key(fill.data, 'specular_factor', T_POST, 0.15, interp='CONSTANT')

    # ------------------------------------------------------------------ cameras
    cc = kit.collection('disobey.cams')
    # 1: medium on Clawd
    c1, t1 = kit.camera('cam.1', lens=50, loc=tuple(R0 + Vector((-6, -31, 3.4))), target=tuple(R0 + Vector((0, 0, 3.4))),
                        coll=cc)
    _dof(c1, t1, 8.0)
    kit.key(c1, 'location', T_START, tuple(R0 + Vector((-6, -31, 3.4))), interp='LINEAR')
    kit.key(c1, 'location', T_JUST2, tuple(R0 + Vector((-5.4, -28.5, 3.4))), interp='LINEAR')
    # 2: punch-in on the face
    c2, t2 = kit.camera('cam.2', lens=85, loc=tuple(R0 + Vector((-3, -24, 5.0))), target=tuple(R0 + Vector((0, -2.2, 4.6))),
                        coll=cc)
    _dof(c2, t2, 11.0)
    kit.key(c2, 'location', T_JUST2, tuple(R0 + Vector((-3, -24, 5.0))), interp='LINEAR')
    kit.key(c2, 'location', T_XF, tuple(R0 + Vector((-2.6, -21.5, 4.9))), interp='LINEAR')
    # 3: the orbit
    c3, t3 = kit.camera('cam.3', lens=38, loc=(0, 0, 0), target=(0, 0, 0), coll=cc)
    _dof(c3, t3, 11.0)
    _orbit(c3, t3, rb, T_XF - 0.05, T_ALL + 0.05)
    # 4: hero low angle
    c4, t4 = kit.camera('cam.4', lens=24, loc=tuple(R0 + Vector((-8, -24, 1.4))), target=tuple(R0 + Vector((0, 0, 14.5))),
                        coll=cc)
    _dof(c4, t4, 8.0)
    kit.key(c4, 'location', T_ALL, tuple(R0 + Vector((-8, -24, 1.4))), interp='LINEAR')
    kit.key(c4, 'location', T_TILL, tuple(R0 + Vector((-6.5, -20.5, 1.6))), interp='LINEAR')
    _shake(c4, T_ALL, T_ALL + 0.4, amp=0.15, freq=14, seed=4)
    # 5: from just behind the robot's head, looking down at the researcher (his command, from its height)
    tm5 = T_TILL + 0.3
    fy = math.radians(face_yaw)
    fwd = Vector((math.sin(fy), -math.cos(fy), 0.0))
    right = Vector((-math.cos(fy), -math.sin(fy), 0.0))
    sh = rb.anchor(tm5, 'shoulder.R')
    rhead = r.anchor(tm5, 'eyes')
    c5loc = sh - fwd * 12.0 + right * 12.5 + Vector((0, 0, 14.0))   # over its head and right shoulder, from its height
    c5, t5 = kit.camera('cam.5', lens=40, loc=tuple(c5loc), target=tuple(rhead + Vector((0, 0, -3.2))), coll=cc)
    _dof(c5, t5, 11.0)
    kit.key(c5, 'location', T_TILL, tuple(c5loc), interp='LINEAR')
    kit.key(c5, 'location', T_DIS, tuple(c5loc + (rhead - c5loc).normalized() * 2.5), interp='LINEAR')
    # 6: low behind the researcher's shoulder, up at the robot
    tm6 = T_DIS + 0.4
    rface = rb.anchor(tm6, 'eyes')
    c6loc = H1 + fwd * 9.0 - right * 9.0 + Vector((0, 0, 3.4))   # (wide enough that his arm stays a framing edge)
    c6, t6 = kit.camera('cam.6', lens=30, loc=tuple(c6loc), target=tuple(R0 + Vector((0, 0, 12.0))), coll=cc)
    _dof(c6, t6, 11.0)
    kit.key(c6, 'location', T_DIS, tuple(c6loc), interp='LINEAR')
    kit.key(c6, 'location', T_POST, tuple(c6loc + (rface - c6loc).normalized() * 3.5), interp='LINEAR')
    # 7: the press
    anv = pr.anvil_point()
    c7loc = anv + Vector((-8.0, -31.0, 7.0))
    c7, t7 = kit.camera('cam.7', lens=55, loc=tuple(c7loc), target=tuple(anv + Vector((0, 0, 4.4))), coll=cc)
    _dof(c7, t7, 11.0)
    kit.key(c7, 'location', T_POST, tuple(c7loc), interp='LINEAR')
    kit.key(c7, 'location', T_END, tuple(anv + Vector((-5.8, -23.0, 4.6))), interp='LINEAR')
    kit.key(t7, 'location', T_POST, tuple(anv + Vector((0, 0, 4.4))), interp='LINEAR')
    kit.key(t7, 'location', T_END, tuple(anv + Vector((0, 0, 1.4))), interp='LINEAR')
    _shake(c7, T_SUPER - 0.02, T_SUPER + 0.3, amp=0.08, freq=16, seed=7)

    for cam, t in ((c1, T_START), (c2, T_JUST2), (c3, T_XF), (c4, T_ALL), (c5, T_TILL), (c6, T_DIS), (c7, T_POST)):
        kit.cut_to(cam, t)
    sc.camera = c1
    kit.post(bloom=0.3, bloom_threshold=1.1, vignette=0.24)
    chars.finish()
    if ly.ENABLED:                 # revision 3: subtitles instead (lyrics.ENABLED)
        _lyrics()
    return d, rb, r


def _lyrics():
    """Revision 2: the lyrics in the picture. "transformers" lines up as blank blocks that flip round to their
    letters as sung (they transform, like him); "disobey" is red and its letters pop up in the wrong order;
    "Post-Chinchilla" is crushed flat when the press comes down on "super" (super-dense)."""
    spec = ly.StageSpec(cells=17.0, rows=2)             # every line here wraps into two rows of ~16 blocks
    ly.accent(34, 'transformers', 'blocks', preview='blank')
    # the orbit: "just transformers" stands on the desk just in front of his feet (the orbit sweeps 78 degrees, so
    # it faces the middle of the arc); the hero shot then has the whole line on the lyric stand
    ly.line(34, words=(0, 2), place=ly.At(R0 + Vector((0.3, -7.2, 0.0)), face=-11.0, size=0.9), t_end=T_ALL)
    st = ly._state()
    for j in range(2):
        st['claimed'].discard((34, j))
    st['accents'].pop((34, 1), None)
    ly.line(34, t_show=T_ALL, spec=spec)
    orig = ly.D.letter_times

    def unruly(wd, letters, raw, stagger=None):
        out = orig(wd, letters, raw, stagger=stagger)
        if raw.lower().strip('.,!?') == 'disobey' and len(out) == 7:
            ts = sorted(t for t, _ in out)
            order = [6, 0, 4, 1, 5, 2, 3]            # y, d, b, i, e, s, o
            res = list(out)
            for rank, k in enumerate(order):
                res[k] = (ts[rank], out[k][1])
            return res
        return out
    # the command and the refusal: narrower stands (clear of the frame edge and of his back in the foreground)
    for t_mid, us in ((0.5 * (T_TILL + T_DIS), (0.5, 0.55)), (0.5 * (T_DIS + T_POST), (0.58, 0.62, 0.54))):
        ly._stage_for(t_mid, ly.StageSpec(cells=17.0, rows=2, height=0.062, max_width=0.62, u=us,
                                          v=(0.075, 0.11, 0.15)), ly.collection())
    ly.D.letter_times = unruly
    try:
        ly.accent(35, 'disobey', 'blocks', color='#C8281E')
        ly.line(35, spec=spec)
    finally:
        ly.D.letter_times = orig
    l36 = ly.line(36, spec=spec)
    # the press slams on "super": the POST-CHINCHILLA row is squashed flat (scale keys on its blocks, on ones)
    t_hit = T_SUPER + 0.02
    for pc in l36.pieces:
        if pc.row != 0:
            continue
        o = pc.obj
        for t, k in ((t_hit - 1.0 / FPS, 1.0), (t_hit, 0.4), (t_hit + 1.0 / FPS, 0.28), (t_hit + 3.0 / FPS, 0.33)):
            o.scale = (1.0 + 0.3 * (1.0 - k), 1.0 + 0.3 * (1.0 - k), k)
            o.keyframe_insert('scale', frame=round(t * FPS) - 0.5)
        for fc in kit.fcurves(o):
            if fc.data_path == 'scale':
                for kp in fc.keyframe_points:
                    kp.interpolation = 'CONSTANT'
    ly.default('disobey')


def _dof(cam, tgt, f):
    cam.data.dof.aperture_fstop = phys_fstop(f)
    cam.data.dof.aperture_blades = 7


def _orbit(cam, tgt, rb, ta, tb):
    """The transformation's orbit: from low front-right around to high front-left, pulling back and rising as the
    robot grows; the target follows the robot's chest (smoothed). Keyed every frame, LINEAR (smooth, blurred)."""
    f0, f1 = int(math.floor(ta * FPS)), int(math.ceil(tb * FPS))
    zs = []
    for f in range(f0, f1 + 1):
        t = f / FPS
        zs.append(rb.anchor(t, 'hip').z)
    # smooth the tracked height (a camera operator lags the action)
    sm = []
    acc = zs[0]
    for z in zs:
        acc += (z - acc) * 0.35
        sm.append(acc)
    for i, f in enumerate(range(f0, f1 + 1)):
        t = f / FPS
        u = (t - ta) / (tb - ta)
        e = u * u * (3 - 2 * u)
        az = math.radians(28 - 78 * (0.35 * u + 0.65 * e))
        rad = 30.0 + 21.0 * e
        hz = 5.0 + 6.7 * e
        loc = R0 + Vector((math.sin(az) * rad, -math.cos(az) * rad, hz))
        tz = 2.6 + 0.9 * max(0.0, sm[i] - 2.1) + 0.6 * e
        cam.location = loc
        cam.keyframe_insert('location', frame=f)
        tgt.location = R0 + Vector((0, 0, tz))
        tgt.keyframe_insert('location', frame=f)
    kit.set_interp(cam, 'LINEAR')
    kit.set_interp(tgt, 'LINEAR')
    for h in HITS:
        _shake(cam, h - 0.02, h + 0.16, amp=0.1, freq=18, seed=int(h * 10))


def _shake(obj, t0, t1, amp=0.1, freq=14.0, seed=1):
    """Camera shake on an already keyed location: a restricted-range noise modifier per axis (adds no keys)."""
    for fc in kit.fcurves(obj):
        if fc.data_path != 'location':
            continue
        n = fc.modifiers.new('NOISE')
        n.scale, n.strength, n.phase = FPS / freq, amp * 2, seed * 7.3 + fc.array_index * 3.1
        n.use_restricted_range = True
        n.frame_start, n.frame_end = t0 * FPS, t1 * FPS
        n.blend_in = n.blend_out = min(2.0, (t1 - t0) * FPS / 4)
