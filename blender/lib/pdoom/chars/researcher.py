"""The researcher: a 12 cm turned-wood peg doll in a lab coat, round wire glasses, mitten hands on bendable arms.

    r = chars.Researcher(coll, loc=(12, 4, 0), yaw=-30)
    r.walk(1.0, 3.0, [(6, 0)]); r.pose(3.2, 'kneel_offer'); r.face(3.2, 'nervous'); r.glasses_glint(4.0)

Character space: 1 BU = 1 cm, standing on z = 0, FACING -Y (his left is +X). Hips 2.55, shoulders 6.65, head centre
9.85 (radius 1.9), top of the hair ~11.8. Rig: root > hips > spine (the rigid turned body leans about the hips) >
head; legs thigh > shin (FK); arms upper_arm > forearm with IK to hand_ik targets (B-bone sleeves bend like wire);
hands follow the forearm with a keyable wrist. See docs/lib/chars.md.
"""
from __future__ import annotations

import bisect
import math
import os

import bmesh
import bpy
from mathutils import Euler, Matrix, Quaternion, Vector

from .. import timing as tm
from . import geo, looks
from .rig import (EASE, Puppet, Target, _lin, _point, _v3, armature, bone_parent, bump, hash01, pb, smoothstep,
                  unwrap)

HERE = os.path.dirname(os.path.abspath(__file__))
ATLAS = os.path.join(HERE, 'faces.png')
FACES = ['neutral', 'blink', 'nervous', 'happy', 'proud', 'shock', 'scared', 'sad', 'talk', 'determined', 'awe', 'wince']
BLINKABLE = ('neutral', 'nervous', 'talk', 'determined', 'sad')

# ------------------------------------------------------------------------------------------------ proportions (cm)

HIP_Z, KNEE_Z = 2.55, 1.45
LEG_X, LEG_R = 0.52, 0.37
NECK_Z = 7.75
HEAD_C = Vector((0.0, 0.0, 9.85))
HEAD_R = 1.9
SH = {'L': Vector((1.4, 0.05, 6.42)), 'R': Vector((-1.4, 0.05, 6.42))}
EL = {'L': Vector((1.92, 0.24, 4.8)), 'R': Vector((-1.92, 0.24, 4.8))}
WR = {'L': Vector((2.02, -0.1, 3.4)), 'R': Vector((-2.02, -0.1, 3.4))}
LENS_R = 0.57
LENS_Y = -2.0
LENS_X = 0.69
LENS_Z = 9.85

BODY_PROFILE = [(0.0, 2.25), (1.1, 2.25), (1.38, 2.3), (1.52, 2.42), (1.6, 2.65), (1.63, 3.2), (1.64, 4.6),
                (1.62, 5.8), (1.56, 6.45), (1.42, 6.85), (1.18, 7.12), (0.86, 7.3), (0.6, 7.42), (0.5, 7.6),
                (0.5, 8.4), (0.0, 8.4)]
# (radius, z, half-angle of the front opening in degrees)
COAT_PROFILE = [(1.99, 2.12, 17), (1.94, 2.6, 13), (1.88, 3.4, 9), (1.82, 4.3, 6), (1.8, 5.0, 7), (1.8, 5.6, 12),
                (1.78, 6.2, 21), (1.72, 6.6, 29), (1.56, 6.95, 37), (1.28, 7.2, 43), (1.0, 7.36, 49),
                (0.95, 7.56, 52)]

BONES = [
    dict(name='root', head=(0, 0, 0)),
    dict(name='hips', head=(0, 0, HIP_Z), parent='root'),
    dict(name='spine', head=(0, 0, HIP_Z), parent='hips', deform=True),
    dict(name='head', head=(0, 0, NECK_Z), parent='spine'),
    dict(name='sweat', head=(0, 0, 0), parent='head'),
]
for _s, _sx in (('L', 1), ('R', -1)):
    BONES += [
        dict(name=f'thigh.{_s}', head=(_sx * LEG_X, 0, HIP_Z), parent='hips', deform=True),
        dict(name=f'shin.{_s}', head=(_sx * LEG_X, 0, KNEE_Z), parent=f'thigh.{_s}', deform=True),
        dict(name=f'upper_arm.{_s}', head=tuple(SH[_s]), tail=tuple(EL[_s]), parent='spine', deform=True, bbone=6),
        dict(name=f'forearm.{_s}', head=tuple(EL[_s]), tail=tuple(WR[_s]), parent=f'upper_arm.{_s}', connect=True,
             deform=True, bbone=6),
        dict(name=f'hand.{_s}', head=tuple(WR[_s]), parent=f'forearm.{_s}'),
        dict(name=f'hand_ik.{_s}', head=tuple(WR[_s]), parent='spine'),
        dict(name=f'pole.{_s}', head=(_sx * 2.6, 3.4, 4.6), parent='spine'),
    ]
POLE_REST = {'L': (2.6, 3.4, 4.6), 'R': (-2.6, 3.4, 4.6)}

REST_HAND = {'L': tuple(WR['L']), 'R': tuple(WR['R'])}


def _mir(p):
    return (-p[0], p[1], p[2])


# pose library: hands are wrist (IK) targets in SPINE space, i.e. where they'd be with the body upright at rest;
# angles in degrees: spine (lean fwd, side, twist), head (nod down, tilt, turn left+), wrist (flex, side, twist),
# thigh (swing fwd -, splay, twist), shin (bend +), hips = offset of the hips (cm)
POSES = {
    'stand': {},
    'lean_in': dict(spine=(18, 0, 0), head=(-14, 0, 0), hands=((1.25, -1.9, 3.5), (-1.25, -1.9, 3.5)),
                    wrist=((20, 0, 0), (20, 0, 0))),
    'nervous': dict(spine=(5, 0, 0), head=(9, 5, 0), hands=((0.42, -2.0, 5.0), (-0.3, -2.05, 5.2)),
                    wrist=((-40, 0, 40), (-40, 0, -40)), face='nervous'),
    'adjust_glasses': dict(spine=(2, 0, 0), head=(14, -4, 0), hands=(None, (-0.45, -2.6, 8.45)),
                           wrist=(None, (-165, 0, 10)), face='neutral'),
    'kneel_offer': dict(hips=(0, 0.35, -1.12), spine=(12, 0, 0), head=(4, 0, 0),
                        hands=((1.45, -1.6, 3.9), (-0.55, -3.1, 5.6)), wrist=((0, 0, 0), (-80, 0, 0)),
                        thigh=((-88, 0, 0), (-4, 0, 0)), shin=(88, 90), face='nervous'),
    'point': dict(spine=(-2, 0, -8), head=(-6, 0, -12), hands=(None, (-1.05, -3.25, 7.6)), wrist=(None, (-95, 0, 0)),
                  face='determined'),
    'pat': dict(spine=(14, 0, 0), head=(18, 0, 0), hands=(None, (-0.7, -2.9, 4.1)), wrist=(None, (-25, 0, 0)),
                face='happy'),
    'peer': dict(spine=(28, 0, 0), head=(-22, 0, 0), hands=((2.0, 0.9, 3.7), (-2.0, 0.9, 3.7)),
                 wrist=((25, 0, 0), (25, 0, 0))),
    'sit': dict(hips=(0, 0.3, -2.18), spine=(-4, 0, 0), hands=((0.95, -1.9, 3.3), (-0.95, -1.9, 3.3)),
                wrist=((60, 0, 0), (60, 0, 0)), thigh=((-86, 4, 0), (-86, -4, 0)), shin=(86, 86)),
    'gasp': dict(spine=(-7, 0, 0), head=(-6, 0, 0), hands=((1.1, -1.8, 8.3), (-1.1, -1.8, 8.3)),
                 wrist=((-150, 0, 0), (-150, 0, 0)), face='shock'),
    'back_away': dict(hips=(0, 0.35, -0.1), spine=(-12, 0, 0), head=(6, 0, 0), hands=((1.0, -2.4, 6.9), (-1.0, -2.4, 6.9)),
                      wrist=((-100, 0, 0), (-100, 0, 0)), thigh=((-8, 0, 0), (14, 0, 0)), shin=(8, 12), face='scared'),
    'hold_leash': dict(spine=(4, 0, 0), head=(12, 0, 0), hands=(None, (-0.8, -2.5, 4.3)), wrist=(None, (-30, 0, 90)),
                       face='happy'),
    'stand_on_mug': dict(hips=(0, 0, -0.25), spine=(5, 0, 0), hands=((4.2, -0.4, 6.3), (-4.2, -0.4, 6.3)),
                         wrist=((0, 0, 0), (0, 0, 0)), thigh=((-16, 3, 0), (-16, -3, 0)), shin=(30, 30), face='scared'),
    'wave': dict(hands=(None, (-2.3, -0.9, 9.4)), wrist=(None, (-160, 0, 0)), face='happy'),
    'think': dict(head=(5, 9, 0), hands=((0.3, -1.85, 5.0), (-0.35, -2.25, 8.0)), wrist=((0, 0, 0), (-140, 0, 0))),
    'proud': dict(spine=(-5, 0, 0), head=(-8, 0, 0), hands=((2.05, -0.55, 4.35), (-2.05, -0.55, 4.35)),
                  wrist=((0, -60, 0), (0, 60, 0)), face='proud'),
    'shrug': dict(head=(0, 10, 0), hands=((2.4, -1.6, 5.1), (-2.4, -1.6, 5.1)), wrist=((-60, 0, -60), (-60, 0, 60))),
    'cower': dict(hips=(0, 0.2, -0.55), spine=(20, 0, 0), head=(6, 0, 0), hands=((0.95, -2.3, 8.0), (-0.95, -2.3, 8.0)),
                  wrist=((-150, 0, 0), (-150, 0, 0)), thigh=((-38, 5, 0), (-38, -5, 0)), shin=(62, 62), face='scared'),
    'cheer': dict(head=(-10, 0, 0), hands=((2.2, -0.5, 10.2), (-2.2, -0.5, 10.2)), wrist=((-170, 0, 0), (-170, 0, 0)),
                  face='happy'),
    'type': dict(spine=(8, 0, 0), head=(14, 0, 0), hands=((0.9, -3.0, 5.0), (-0.9, -3.0, 5.0)),
                 wrist=((-70, 0, 0), (-70, 0, 0))),
    'present': dict(hands=((1.35, -2.8, 5.2), (-1.35, -2.8, 5.2)), wrist=((-80, 0, -70), (-80, 0, 70)), face='happy'),
    'hold': dict(spine=(3, 0, 0), head=(10, 0, 0), hands=((0.6, -2.35, 5.0), (-0.6, -2.35, 5.0)),
                 wrist=((-70, 0, 60), (-70, 0, -60))),
    'arms_crossed': dict(head=(-4, 0, 0), hands=((-0.9, -1.95, 5.5), (0.9, -2.05, 5.2)),
                         wrist=((-90, 0, 0), (-90, 0, 0)), face='determined'),
    'facepalm': dict(spine=(8, 0, 0), head=(20, 0, 0), hands=(None, (-0.35, -2.2, 8.7)), wrist=(None, (-150, 0, 0)),
                     face='wince'),
}
CHANNELS = ('hips', 'spine', 'head', 'hand.L', 'hand.R', 'wrist.L', 'wrist.R', 'thigh.L', 'thigh.R', 'shin.L',
            'shin.R')


def _T(p):
    return Matrix.Translation(Vector(p))


def _R(ex, ey, ez):
    return Euler((math.radians(ex), math.radians(ey), math.radians(ez)), 'XYZ').to_matrix().to_4x4()


def _body_r(z):
    P = BODY_PROFILE[1:-1]
    for (r0, z0), (r1, z1) in zip(P[:-1], P[1:]):
        if z0 <= z <= z1:
            return r0 + (r1 - r0) * (z - z0) / max(1e-6, z1 - z0)
    return P[0][0] if z < P[0][1] else P[-1][0]


# ------------------------------------------------------------------------------------------------ arm clearance
# The shoulders sit inside the coat (x 1.4) and an arm reaches only ~3.1 cm, so a hand target in front of or behind
# the body, or at the face, used to drive the sleeve, the cuff or the mitten into the coat or the head (and the IK's
# pole angle bent the elbows INTO the chest). At bake time every wrist target now goes through clear_arm(): the elbow
# bends away from the body (the pole is keyed per pose) and the wrist is nudged out, the least it takes, until the
# sleeve, cuff and mitten stay outside the coat, the neck, the head and the glasses. Targets on props away from the
# body are left alone (apart from a clamp to the arm's reach, which gives a straight arm a slight natural bend).

ARM_L1 = (EL['L'] - SH['L']).length          # 1.71 shoulder -> elbow
ARM_L2 = (WR['L'] - EL['L']).length          # 1.44 elbow -> wrist
ARM_REACH = 0.985 * (ARM_L1 + ARM_L2)
SLEEVE_R = 0.31
MITTEN_C = Vector((0.0, -0.04, -0.5))         # mitten centre from the wrist, hand bone rest frame
MITTEN_AX = (0.31, 0.45, 0.58)
_COAT = [(r, z) for r, z, _ in COAT_PROFILE]


def _frame(d, b):
    d = d.normalized()
    b = (b - d * b.dot(d)).normalized()
    return Matrix((d, b, d.cross(b))).transposed()


def _rest_bend(s):
    """Unit vector from the shoulder-wrist line to the modelled rest elbow."""
    u = (WR[s] - SH[s]).normalized()
    v = EL[s] - SH[s]
    return (v - u * v.dot(u)).normalized()


_THUMB_R = Euler((math.radians(-38), 0, 0), 'XYZ').to_matrix()
_F0 = {s: _frame(WR[s] - EL[s], (EL[s] - SH[s]).cross(WR[s] - EL[s])) for s in 'LR'}


def _torso_r(z):
    """Radius of the coat (or the neck) at height z in spine space; None where there's no torso (legs, head)."""
    if z < _COAT[0][1] - 0.15 or z > 8.4:
        return None
    if z <= _COAT[0][1]:
        return _COAT[0][0]
    for (r0, z0), (r1, z1) in zip(_COAT[:-1], _COAT[1:]):
        if z0 <= z <= z1:
            return r0 + (r1 - r0) * (z - z0) / (z1 - z0)
    return 0.55


def _elbow(S, W, n):
    v = W - S
    d = max(1e-4, v.length)
    u = v / d
    a = (ARM_L1 * ARM_L1 - ARM_L2 * ARM_L2 + d * d) / (2 * d)
    h = math.sqrt(max(0.0, ARM_L1 * ARM_L1 - a * a))
    return S + u * a + n * h


def _bend_dir(side, S, W):
    """Where the elbow points: away from the body axis at the arm's middle, a little back and down."""
    u = (W - S).normalized()
    M = (S + W) * 0.5
    o = Vector((M.x, M.y, 0.0))
    if o.length < 1e-3:
        o = Vector((1.0 if side == 'L' else -1.0, 0.0, 0.0))
    o = o.normalized() + Vector((0.0, 0.25, -0.45))
    n = o - u * o.dot(u)
    if n.length < 1e-3:
        n = Vector((0.0, 0.0, -1.0)) - u * (-u.z)
    return n.normalized()


def _forearm_rot(side, S, E, W, n):
    """Rotation of the forearm from its rest frame for a chain S-E-W bent toward n (spine space)."""
    u = (W - S).normalized()
    return _frame(W - E, n.cross(u)) @ _F0[side].transposed()


def _old_chain(side, W, pole_a):
    """The chain the IK used to make before this fix (pole fixed at POLE_REST, pole angle -90 deg), which every
    pose's wrist angles were tuned against: (elbow, wrist, bend direction)."""
    S = SH[side]
    v = W - S
    d = max(1e-4, v.length)
    u = v / d
    Wo = S + u * min(d, ARM_L1 + ARM_L2 - 1e-4)
    p = Vector(POLE_REST[side]) - S
    n = p - u * p.dot(u)
    n = Quaternion(u, math.radians(-90.0) - pole_a) @ n.normalized()
    return _elbow(S, Wo, n), Wo, n


def _mitten(W, R, side='L'):
    """Centre and sample points of the mitten and its thumb (spine space) at wrist W with hand orientation R."""
    c = W + R @ MITTEN_C
    ax = [R @ Vector((MITTEN_AX[0], 0, 0)), R @ Vector((0, MITTEN_AX[1], 0)), R @ Vector((0, 0, MITTEN_AX[2]))]
    pts = [c]
    for a in ax:
        pts += [c + a * 0.92, c - a * 0.92]
    for i, j in ((0, 2), (1, 2), (0, 1)):
        for si in (-1, 1):
            for sj in (-1, 1):
                pts.append(c + (ax[i] * si + ax[j] * sj) * 0.64)
    sx = 1 if side == 'L' else -1
    Rt = R @ _THUMB_R
    tc = W + R @ Vector((-sx * 0.05, -0.42, -0.33))
    pts += [tc, tc + Rt @ Vector((0, -0.15, 0)), tc + Rt @ Vector((0, 0, 0.27)), tc - Rt @ Vector((0, 0, 0.27)),
            tc + Rt @ Vector((0.13, 0, 0)), tc - Rt @ Vector((0.13, 0, 0))]
    return c, pts


def _arm_depth(side, S, E, W, R_hand, Mh, Mh_inv):
    """Worst penetration (cm beyond the allowance) of the arm into the body, and the direction to push the wrist."""
    worst, push = 0.0, None

    def torso(p, r, allow):
        nonlocal worst, push
        R = _torso_r(p.z)
        if R is None:
            return
        rad = math.hypot(p.x, p.y)
        dep = R + r - rad - allow
        if dep > worst:
            worst = dep
            push = Vector((p.x, p.y, 0.0)).normalized() if rad > 1e-3 else Vector((1.0 if side == 'L' else -1.0, 0, 0))

    def head(p, r, allow):
        nonlocal worst, push
        q = Mh_inv @ p
        d = q - HEAD_C
        dep = HEAD_R + r - d.length - allow
        if dep > worst:
            worst = dep
            push = (Mh.to_3x3() @ d).normalized()
        # the glasses: nothing inside the lens discs or between them and the face; the hand may touch the front
        front = LENS_Y - 0.1 - r
        if front < q.y < LENS_Y + 0.45:
            for sx in (-1, 1):
                if math.hypot(q.x - sx * LENS_X, q.z - LENS_Z) < LENS_R + 0.1 + r:
                    dep = q.y - front
                    if dep > worst:
                        worst = dep
                        push = (Mh.to_3x3() @ Vector((0.0, -1.0, 0.0))).normalized()

    for k in range(5):
        s = 0.5 + 0.125 * k
        p = S.lerp(E, s)
        torso(p, SLEEVE_R, 0.42 - 0.22 * (k / 4))
        head(p, SLEEVE_R, 0.05)
    for k in range(6):
        p = E.lerp(W, k / 5)
        torso(p, SLEEVE_R, 0.2)
        head(p, SLEEVE_R, 0.05)
    c, pts = _mitten(W, R_hand, side)
    for p in pts:
        torso(p, 0.0, 0.25)
        head(p, 0.0, 0.03)
    return worst, push


def clear_arm(side, W, wrist, Mh, pole_a, *, iters: int = 14, max_push: float = 2.6):
    """The wrist target W (spine space) clamped to the arm's reach and nudged out of the body. The mitten keeps the
    orientation the pose gave it under the old IK (so props in the hand and the gestures read as before). Returns
    (wrist, elbow, pole, wrist angles in radians) in spine space. Mh: the head's transform in spine space; pole_a:
    the rig's IK pole angle (radians)."""
    S = SH[side]
    Mh_inv = Mh.inverted()
    W0 = Vector(W)
    wr = Euler(tuple(math.radians(x) for x in wrist), 'XYZ')
    Eo, Wo, no = _old_chain(side, W0, pole_a)
    R_hand = _forearm_rot(side, S, Eo, Wo, no) @ wr.to_matrix()

    def clamp(w):
        v = w - S
        return S + v.normalized() * ARM_REACH if v.length > ARM_REACH else w
    W = clamp(W0)
    for _ in range(iters):
        n = _bend_dir(side, S, W)
        E = _elbow(S, W, n)
        dep, push = _arm_depth(side, S, E, W, R_hand, Mh, Mh_inv)
        if dep <= 1e-3 or push is None or (W - W0).length > max_push:
            break
        W = clamp(W + push * (dep + 0.03))
    n = _bend_dir(side, S, W)
    E = _elbow(S, W, n)
    Rw = _forearm_rot(side, S, E, W, n).transposed() @ R_hand
    return W, E, E + n * 4.0, Rw.to_euler('XYZ', wr)


def _pole_angle(rig, side, pole):
    """IK pole angle that keeps the modelled rest elbow when the pole sits at `pole` (rest, armature space)."""
    b = rig.data.bones[f'upper_arm.{side}']
    head, tail = b.head_local, b.tail_local
    x_axis = b.matrix_local.col[0].xyz.normalized()
    ik_tail = rig.data.bones[f'forearm.{side}'].tail_local
    pole_normal = (ik_tail - head).cross(pole - head)
    proj = pole_normal.cross(tail - head)
    a = x_axis.angle(proj)
    if x_axis.cross(proj).angle(tail - head) < 1:
        a = -a
    return a


def _torus(bm, R, r, M, segs=40, csegs=8, mat=0):
    rings = []
    for i in range(segs):
        a = 2 * math.pi * i / segs
        c = Vector((math.cos(a), 0.0, math.sin(a)))
        ring = []
        for k in range(csegs):
            b = 2 * math.pi * k / csegs
            p = c * (R + r * math.cos(b)) + Vector((0, r * math.sin(b), 0))
            ring.append(bm.verts.new(M @ p))
        rings.append(ring)
    for i in range(segs):
        A, B = rings[i], rings[(i + 1) % segs]
        for k in range(csegs):
            j = (k + 1) % csegs
            f = bm.faces.new((A[k], A[j], B[j], B[k]))
            f.material_index = mat


class Researcher(Puppet):
    """The peg-doll researcher. See the module doc and docs/lib/chars.md."""

    STRIDE = 2.1
    GAIT_R = 1.2
    GAIT_FULL = 1.8

    def __init__(self, coll, name: str = 'researcher', loc=(0, 0, 0), yaw: float = 0.0, scale: float = 1.0, *,
                 seed=None, timing: str = 'twos', blink: bool = True, face: str = 'neutral'):
        super().__init__(name, seed, timing)
        self.coll = coll
        self.auto_blink = blink
        self._refl = None
        self._sweat = None
        self._parts: list = []
        self._mats()
        self.rig = self._build_rig()
        self._build()
        self.track('root.loc', _v3(loc))
        self.track('root.yaw', float(yaw))
        self.track('root.scale', float(scale))
        self.track('hips', (0.0, 0.0, 0.0))
        self.track('spine', (0.0, 0.0, 0.0))
        self.track('head', (0.0, 0.0, 0.0))
        for s in 'LR':
            self.track(f'hand.{s}', REST_HAND[s])
            self.track(f'wrist.{s}', (0.0, 0.0, 0.0))
            self.track(f'thigh.{s}', (0.0, 0.0, 0.0))
            self.track(f'shin.{s}', 0.0)
        self.track('glint', 0.0)
        self.track('glint.pos', -1.0)
        self.track('glint.fill', 0.0)
        self.track('glint.col', (1.0, 1.0, 1.0))
        self.track('refl', 0.0)
        self.track('refl.col', _lin('#FFB24A'))
        self.track('sweat', 0.0)
        self.disc('face', face)
        self.disc('sweat', False)
        self.disc('refl', False)
        self._blinks: list = []

    # ============================================================================================ build
    def _mats(self):
        self.m_wood = looks.wood('chars.r.wood')
        self.m_shirt = looks.paint('chars.r.shirt', '#8FB6DD', rough=0.4)
        self.m_collar = looks.paint('chars.r.collar', '#B9D3EC', rough=0.4)
        self.m_tie = looks.paint('chars.r.tie', '#B9313A', rough=0.3)
        self.m_pants = looks.paint('chars.r.pants', '#343A4C', rough=0.45)
        self.m_shoe = looks.paint('chars.r.shoe', '#2A1C15', rough=0.22, coat=0.8)
        self.m_coat = looks.fabric('chars.r.coat', '#EDEAE1')
        self.m_button = looks.gloss('chars.r.button', '#E9E4D8', rough=0.25)
        self.m_wire = looks.metal('chars.r.wire', '#6E5A3A', rough=0.3)
        self.m_pen = looks.gloss('chars.r.pen', '#2C57B8', rough=0.2)
        self.m_steel = looks.metal('chars.r.steel', '#C9CED6', rough=0.2)
        self.m_badge = looks.paint('chars.r.badge', '#F7F5EE', rough=0.5, coat=0.2)
        self.m_badge2 = looks.paint('chars.r.badge2', '#2F6FD6', rough=0.5, coat=0.2)
        self.m_head = looks.face_head(f'{self.name}.head', ATLAS)
        self.m_lens = looks.lens(f'{self.name}.lens')

    def _build_rig(self):
        self._pole_a = {}
        rig = armature(f'{self.name}.rig', self.coll, BONES)
        for s in 'LR':
            p = rig.pose.bones[f'forearm.{s}']
            ik = p.constraints.new('IK')
            ik.target, ik.subtarget = rig, f'hand_ik.{s}'
            ik.pole_target, ik.pole_subtarget = rig, f'pole.{s}'
            # the elbow bends TOWARD the pole (the old fixed -90 deg turned it into the chest); the pole itself is
            # keyed per pose by clear_arm()
            ik.pole_angle = _pole_angle(rig, s, EL[s] + _rest_bend(s) * 4.0)
            self._pole_a[s] = ik.pole_angle
            ik.chain_count = 2
            for b in (f'upper_arm.{s}', f'forearm.{s}'):
                rig.pose.bones[b].rotation_mode = 'QUATERNION'
        return rig

    def _obj(self, bm, name, mats, *, bone=None, sharp=40.0, M=None):
        ob = geo.to_object(bm, f'{self.name}.{name}', self.coll, mats, sharp=sharp)
        if name not in ('reflection', 'sweat'):
            self._parts.append(ob)
        if M is not None:
            ob.matrix_basis = M
        if bone:
            bone_parent(ob, self.rig, bone)
        return ob

    def _deform(self, ob, groups: dict):
        """Bind ob to the rig with an Armature modifier; groups: bone -> [weights per vertex]."""
        ob.parent = self.rig
        mod = ob.modifiers.new('rig', 'ARMATURE')
        mod.object = self.rig
        mod.use_vertex_groups = True
        mod.use_bone_envelopes = False
        for bone, ws in groups.items():
            vg = ob.vertex_groups.new(name=bone)
            by_w: dict = {}
            for i, w in enumerate(ws):
                if w > 1e-4:
                    by_w.setdefault(round(w, 3), []).append(i)
            for w, idx in by_w.items():
                vg.add(idx, w, 'REPLACE')
        return ob

    def _build(self):
        # turned body (shirt painted, bare wood neck)
        bm = bmesh.new()
        geo.lathe(bm, BODY_PROFILE, segs=48, mat=lambda z: 0 if z < 7.28 else 1)
        # tie and shirt collar, painted on and following the chest
        tie = [(-0.13, 7.1), (0.13, 7.1), (0.1, 6.84), (0.25, 5.35), (0.0, 5.08), (-0.25, 5.35), (-0.1, 6.84)]
        vs = geo.decal(bm, geo.rounded_poly(tie, 0.04, 3), depth=0.05, back=0.03, bevel=0.025, rings=1, mat=2,
                       M=_T((0, -1.6, 0)))
        for sx in (-1, 1):
            col = [(sx * 0.1, 7.34), (sx * 0.62, 7.2), (sx * 0.24, 6.94)]
            if sx < 0:
                col = list(reversed(col))
            vs += geo.decal(bm, geo.rounded_poly(col, 0.05, 3), depth=0.05, back=0.03, bevel=0.02, rings=1, mat=3,
                            M=_T((0, -1.6, 0)))
        for v in vs:
            off = v.co.y + 1.6
            rr = _body_r(v.co.z)
            ang = math.asin(max(-0.95, min(0.95, v.co.x / max(rr, 1e-3))))
            v.co.y = -rr * math.cos(ang) + off
        geo.recalc_normals(bm)
        self.o_body = self._obj(bm, 'body', [self.m_shirt, self.m_wood, self.m_tie, self.m_collar], bone='spine',
                                sharp=60)
        # head
        bm = bmesh.new()
        geo.uv_sphere(bm, HEAD_R, segs=48, rings=24)
        self.o_head = self._obj(bm, 'head', [self.m_head], sharp=None, M=_T(HEAD_C))
        bone_parent(self.o_head, self.rig, 'head')
        self._build_glasses()
        self._build_coat()
        self._build_limbs()

    def _build_glasses(self):
        bm = bmesh.new()
        for sx in (-1, 1):
            _torus(bm, LENS_R, 0.045, _T((sx * LENS_X, LENS_Y, LENS_Z)), segs=40, csegs=8)
        # bridge
        br = [(-LENS_X + LENS_R * 0.93, LENS_Y, LENS_Z + 0.2), (-0.1, LENS_Y - 0.03, LENS_Z + 0.3),
              (0.1, LENS_Y - 0.03, LENS_Z + 0.3), (LENS_X - LENS_R * 0.93, LENS_Y, LENS_Z + 0.2)]
        geo.tube(bm, br, 0.04, segs=8)
        for sx in (-1, 1):
            tp = [(sx * (LENS_X + LENS_R), LENS_Y, LENS_Z + 0.05), (sx * 1.62, -1.55, LENS_Z + 0.1),
                  (sx * 2.0, -0.6, LENS_Z + 0.1), (sx * 2.02, 0.2, LENS_Z + 0.02), (sx * 1.92, 0.75, LENS_Z - 0.45)]
            geo.tube(bm, tp, 0.038, segs=8)
        geo.recalc_normals(bm)
        self.o_glasses = self._obj(bm, 'glasses', [self.m_wire], bone='head', sharp=70)
        # lenses (with UVs for the glint sweep)
        bm = bmesh.new()
        uv = bm.loops.layers.uv.new('UVMap')
        for sx in (-1, 1):
            c = Vector((sx * LENS_X, LENS_Y, LENS_Z))
            geo.decal(bm, geo.ellipse(2 * LENS_R * 0.98, 2 * LENS_R * 0.98, 40), depth=0.025, back=0.025,
                      bevel=0.012, rings=1, M=_T(c))
        for f in bm.faces:
            for lp in f.loops:
                p = lp.vert.co
                cx = LENS_X if p.x > 0 else -LENS_X
                lp[uv].uv = ((p.x - cx) / (2 * LENS_R) + 0.5, (p.z - LENS_Z) / (2 * LENS_R) + 0.5)
        self.o_lens = self._obj(bm, 'lenses', [self.m_lens], bone='head', sharp=None)
        self.o_lens.visible_shadow = False

    def _build_coat(self):
        bm = bmesh.new()
        segs = 44
        rings = []
        for (r, z, g) in COAT_PROFILE:
            a0, a1 = math.radians(g), 2 * math.pi - math.radians(g)
            ring = []
            for i in range(segs + 1):
                a = a0 + (a1 - a0) * i / segs
                rr = r
                if z > 5.5 and (i <= 1 or i >= segs - 1):     # lapels flare
                    rr += (0.14 if i in (0, segs) else 0.06) * smoothstep(5.5, 6.6, z)
                ring.append(bm.verts.new((rr * math.sin(a), -rr * math.cos(a), z)))
            rings.append(ring)
        faces = []
        for A, B in zip(rings[:-1], rings[1:]):
            for i in range(segs):
                faces.append(bm.faces.new((A[i], A[i + 1], B[i + 1], B[i])))
        ret = bmesh.ops.solidify(bm, geom=faces, thickness=0.07)
        # pockets: patches just proud of the coat
        def patch(a_c, hw, z0, z1, r_of_z, mat=0):
            pr = []
            for z in (z0, z1):
                row = []
                for k in range(7):
                    a = math.radians(a_c - hw + 2 * hw * k / 6)
                    r = r_of_z(z) + 0.035
                    row.append(bm.verts.new((r * math.sin(a), -r * math.cos(a), z)))
                pr.append(row)
            fs = [bm.faces.new((pr[0][k], pr[0][k + 1], pr[1][k + 1], pr[1][k])) for k in range(6)]
            bmesh.ops.solidify(bm, geom=fs, thickness=0.03)
        coat_r = lambda z: next((r0 + (r1 - r0) * (z - z0) / (z1 - z0) for (r0, z0, _), (r1, z1, _) in
                                 zip(COAT_PROFILE[:-1], COAT_PROFILE[1:]) if z0 <= z <= z1), 1.8)
        patch(52, 15, 3.15, 3.95, coat_r)
        patch(-52, 15, 3.15, 3.95, coat_r)
        patch(40, 12, 5.7, 6.15, coat_r)
        # buttons on the closing edge
        for z in (4.35, 5.05):
            a = math.radians(-8.5)
            r = coat_r(z) + 0.04
            geo.cone(bm, 0.11, 0.1, 0.06, segs=12, mat=1,
                     M=_T((r * math.sin(a), -r * math.cos(a), z)) @ _R(90, 0, math.degrees(a)) @ _R(180, 0, 0))
        geo.recalc_normals(bm)
        ob = self._obj(bm, 'coat', [self.m_coat, self.m_button], sharp=50)
        # skirt follows the thighs a little (kneel/sit without the legs poking through)
        ws_sp, ws_l, ws_r = [], [], []
        for v in ob.data.vertices:
            k = 0.6 * smoothstep(3.5, 2.2, v.co.z)
            side = smoothstep(-0.5, 0.5, v.co.x)
            ws_l.append(k * side)
            ws_r.append(k * (1 - side))
            ws_sp.append(1 - k)
        self.o_coat = self._deform(ob, {'spine': ws_sp, 'thigh.L': ws_l, 'thigh.R': ws_r})
        # pen in the breast pocket, ID badge on the other side
        bm = bmesh.new()
        a = math.radians(44)
        r = coat_r(6.1) + 0.12
        base = Vector((r * math.sin(a), -r * math.cos(a), 5.85))
        geo.cone(bm, 0.075, 0.075, 0.95, segs=12, mat=0, M=_T(base) @ _R(-6, 0, 0))
        geo.cone(bm, 0.08, 0.05, 0.22, segs=12, mat=1, M=_T(base + Vector((0, 0, 0.93))) @ _R(-6, 0, 0))
        geo.rounded_box(bm, (0.035, 0.07, 0.5), 0.015, base + Vector((0, -0.1, 0.62)), seg=2, flat=(0, 0, 1), mat=1)
        a = math.radians(-36)
        r = coat_r(6.0) + 0.02
        geo.decal(bm, geo.rrect(0.5, 0.64, 0.06), depth=0.03, back=0.0, bevel=0.012, rings=1, mat=2,
                  M=_T((r * math.sin(a), -r * math.cos(a), 5.95)) @ _R(-8, 0, math.degrees(a)))
        geo.decal(bm, geo.rrect(0.5, 0.14, 0.02, cz=0.2), depth=0.045, back=-0.02, bevel=0.005, rings=1, mat=3,
                  M=_T((r * math.sin(a), -r * math.cos(a), 5.95)) @ _R(-8, 0, math.degrees(a)))
        self.o_pen = self._obj(bm, 'pocket', [self.m_pen, self.m_steel, self.m_badge, self.m_badge2], bone='spine',
                               sharp=50)

    def _build_limbs(self):
        # sleeves: bendable tubes on B-bones (IK)
        bm = bmesh.new()
        order = []
        for s in 'LR':
            L1 = (EL[s] - SH[s]).length
            pts = [SH[s].lerp(EL[s], k / 8) for k in range(8)] + [EL[s].lerp(WR[s], k / 8) for k in range(9)]
            pts[0] = pts[0] + (Vector((0, 0.05, SH[s].z)) - SH[s]).normalized() * 0.35
            n = len(pts)
            radii = [0.33 - 0.03 * i / (n - 1) for i in range(n)]
            radii[-1] = radii[-2] = 0.34   # cuff
            made, params, _ = geo.tube(bm, pts, radii, segs=16, cap0=True, cap1=True)
            for p in params:
                w = smoothstep(L1 - 0.45 + 0.2, L1 + 0.45 + 0.2, p)
                order.append((s, 1 - w, w))
        geo.recalc_normals(bm)
        ob = self._obj(bm, 'sleeves', [self.m_coat], sharp=None)
        gs = {f'upper_arm.{s}': [] for s in 'LR'}
        gs.update({f'forearm.{s}': [] for s in 'LR'})
        for s, wu, wf in order:
            for side in 'LR':
                gs[f'upper_arm.{side}'].append(wu if side == s else 0.0)
                gs[f'forearm.{side}'].append(wf if side == s else 0.0)
        self.o_sleeves = self._deform(ob, gs)
        # legs (trousers) on thigh/shin
        bm = bmesh.new()
        order = []
        for s, sx in (('L', 1), ('R', -1)):
            pts = [(sx * LEG_X, 0, 2.95 - 2.5 * k / 12) for k in range(13)]
            made, params, _ = geo.tube(bm, pts, LEG_R, segs=16)
            for p in params:
                z = 2.95 - p
                w = smoothstep(KNEE_Z + 0.3, KNEE_Z - 0.3, z)
                order.append((s, 1 - w, w))
        geo.recalc_normals(bm)
        ob = self._obj(bm, 'legs', [self.m_pants], sharp=None)
        gs = {f'{b}.{s}': [] for s in 'LR' for b in ('thigh', 'shin')}
        for s, wt, ws in order:
            for side in 'LR':
                gs[f'thigh.{side}'].append(wt if side == s else 0.0)
                gs[f'shin.{side}'].append(ws if side == s else 0.0)
        self.o_legs = self._deform(ob, gs)
        # shoes and mitten hands (rigid)
        for s, sx in (('L', 1), ('R', -1)):
            bm = bmesh.new()
            geo.rounded_box(bm, (0.82, 1.32, 0.52), 0.25, (sx * LEG_X, -0.26, 0.26), seg=3, flat=(1, 2, 0), taper=0.08)
            self._obj(bm, f'shoe.{s}', [self.m_shoe], bone=f'shin.{s}')
            bm = bmesh.new()
            w = WR[s]
            geo.uv_sphere(bm, 1.0, segs=24, rings=14, scale=(0.31, 0.45, 0.58), M=_T(w + Vector((0, -0.04, -0.5))))
            geo.uv_sphere(bm, 1.0, segs=14, rings=8, scale=(0.15, 0.16, 0.3),
                          M=_T(w + Vector((-sx * 0.05, -0.42, -0.33))) @ _R(-38, 0, 0))
            self._obj(bm, f'hand.{s}', [self.m_wood], bone=f'hand.{s}', sharp=None)

    # ============================================================================================ API
    def pose(self, t: float, name: str, *, dur: float = 0.3, ease: str = 'inout', face: bool = True):
        """Arrive at a pose from POSES by t (all body channels). If the pose names a face, it's set at t too."""
        P = POSES[name]
        hands = P.get('hands', (None, None))
        wrist = P.get('wrist', (None, None))
        thigh = P.get('thigh', (None, None))
        shin = P.get('shin', (None, None))
        vals = {'hips': P.get('hips'), 'spine': P.get('spine'), 'head': P.get('head'),
                'hand.L': hands[0], 'hand.R': hands[1], 'wrist.L': wrist[0], 'wrist.R': wrist[1],
                'thigh.L': thigh[0], 'thigh.R': thigh[1], 'shin.L': shin[0], 'shin.R': shin[1]}
        rest = {'hips': (0.0, 0.0, 0.0), 'spine': (0.0, 0.0, 0.0), 'head': (0.0, 0.0, 0.0), 'hand.L': REST_HAND['L'],
                'hand.R': REST_HAND['R'], 'wrist.L': (0.0, 0.0, 0.0), 'wrist.R': (0.0, 0.0, 0.0),
                'thigh.L': (0.0, 0.0, 0.0), 'thigh.R': (0.0, 0.0, 0.0), 'shin.L': 0.0, 'shin.R': 0.0}
        for ch, v in vals.items():
            v = rest[ch] if v is None else (float(v) if not isinstance(v, tuple) else tuple(float(x) for x in v))
            self.T[ch].set(t, v, dur, ease)
        if face and P.get('face'):
            self.face(t, P['face'])
        self._ev(t)
        return self

    def face(self, t: float, expr: str):
        """Painted expression from t: neutral, blink, nervous, happy, proud, shock, scared, sad, talk, determined,
        awe, wince."""
        if expr not in FACES:
            raise KeyError(f'unknown face {expr!r}; one of {FACES}')
        self.D['face'].set(t, expr)
        self._ev(t)
        return self

    def look(self, t: float, target=None, *, dur: float = 0.25, turn: float | None = None):
        """Turn the head (and a little of the body) toward target by t. Beyond ~70 deg the whole body turns.
        turn: fraction of the yaw done by turning on the spot (default: only the excess). target=None: straight."""
        if target is None:
            self.T['head'].set(t, (0.0, 0.0, 0.0), dur)
            self._ev(t)
            return self
        tp = _point(target, t)
        eye = self.anchor(t - dur, 'eyes')
        d = tp - eye
        Y = self.T['root.yaw']
        y0 = Y.at(t - dur)
        want = unwrap(math.degrees(math.atan2(d.x, -d.y)), y0)
        rel = want - y0
        if turn is None:
            body = max(0.0, abs(rel) - 65) * (1 if rel > 0 else -1)
        else:
            body = rel * turn
        if body and not self._moving(t - dur, t):
            Y.set(t, y0 + body, dur, 'inout')
        rel -= body
        pitch = -math.degrees(math.atan2(d.z, max(1e-6, d.xy.length)))
        sp = self.T['spine'].at(t - dur)
        hy = max(-70.0, min(70.0, rel * 0.8))
        self.T['head'].set(t, (max(-35.0, min(40.0, pitch - sp[0])), 0.0, hy), dur)
        self.T['spine'].set(t, (sp[0], sp[1], rel * 0.2), dur)
        self._ev(t)
        return self

    def hand(self, t: float, side: str, target, *, dur: float = 0.25, wrist=None, reach: float = 0.55):
        """Put a hand (side 'L' | 'R') at a WORLD point (or an object / a character's face) by t. The mitten's
        palm lands about `reach` cm past the wrist, so the wrist target is pulled back toward the shoulder."""
        tp = _point(target, t)
        Mi = self._spine_world(t).inverted()
        local = Mi @ tp
        sh = SH[side]
        d = local - sh
        if d.length > reach:
            local = local - d.normalized() * reach
        self.T[f'hand.{side}'].set(t, tuple(local), dur)
        if wrist is not None:
            self.T[f'wrist.{side}'].set(t, tuple(float(x) for x in wrist), dur)
        self._ev(t)
        return self

    def wave(self, t0: float, t1: float, side: str = 'R', rate: float | None = None):
        """Wave from t0 to t1 (raises the hand, waves on the beat, lowers it)."""
        H, W = self.T[f'hand.{side}'], self.T[f'wrist.{side}']
        sx = 1 if side == 'L' else -1
        prevh, prevw = H.at(t0 - 0.3), W.at(t0 - 0.3)
        H.set(t0, (sx * 2.3, -0.9, 9.4), 0.25)
        W.set(t0, (-160.0, 0.0, 0.0), 0.25)
        H.set(t1 + 0.3, prevh, 0.3)
        W.set(t1 + 0.3, prevw, 0.3)
        per = rate or tm.beat_period()
        W.add(t0, t1, lambda x: (0.0, 28 * math.sin(2 * math.pi * (x - t0) / per), 0.0))
        H.add(t0, t1, lambda x: (0.35 * math.sin(2 * math.pi * (x - t0) / per), 0.0, 0.0))
        self._ev(t0)
        self._ev(t1)
        return self

    def pat(self, t0: float, t1: float, target=None, side: str = 'R', rate: float | None = None):
        """Pat something (default: whatever the hand is on) from t0 to t1: small down-up taps on the beat."""
        if target is not None:
            self.hand(t0, side, target, wrist=(-25, 0, 0))
        per = rate or tm.beat_period()
        self.T[f'hand.{side}'].add(t0, t1, lambda x: (0.0, 0.0, 0.35 * abs(math.sin(math.pi * (x - t0) / per))))
        self.T['head'].add(t0, t1, lambda x: (4 * abs(math.sin(math.pi * (x - t0) / per)), 0.0, 0.0))
        self._ev(t0)
        self._ev(t1)
        return self

    def fidget(self, t0: float, t1: float, amount: float = 1.0):
        """Nervous hand-wringing and a little shifting of weight (use with pose 'nervous')."""
        for s, ph in (('L', 0.0), ('R', 1.7)):
            self.T[f'hand.{s}'].add(t0, t1, lambda x, ph=ph: (0.12 * amount * math.sin(9 * x + ph), 0.0,
                                                              0.1 * amount * math.sin(13 * x + ph)))
            self.T[f'wrist.{s}'].add(t0, t1, lambda x, ph=ph: (0.0, 0.0, 25 * amount * math.sin(11 * x + ph)))
        self.T['spine'].add(t0, t1, lambda x: (0.0, 2.0 * amount * math.sin(3.1 * x), 0.0))
        self._ev(t0)
        return self

    def nod(self, t: float, n: int = 2, amount: float = 12.0, every: float | None = None):
        every = every or tm.beat_period() / 2
        self.T['head'].add(t, t + n * every, lambda x: (amount * max(0.0, math.sin(math.pi * (x - t) / every)), 0.0, 0.0))
        self._ev(t)
        return self

    def shake_head(self, t: float, n: int = 3, amount: float = 18.0, every: float | None = None):
        every = every or tm.beat_period() / 2
        self.T['head'].add(t, t + n * every, lambda x: (0.0, 0.0, amount * math.sin(math.pi * (x - t) / every)))
        self._ev(t)
        return self

    def jump(self, t: float, height: float = 1.5, dur: float = 0.4):
        """A startled hop (both feet), landing at t + dur."""
        self.T['hips'].add(t, t + dur, lambda x: (0.0, 0.0, 4 * height * ((x - t) / dur) * (1 - (x - t) / dur)))
        for s in 'LR':
            self.T[f'shin.{s}'].add(t, t + dur, lambda x: 30 * bump(x, t, t + dur * 0.4, t + dur))
        self.no_gait(t, t + dur)
        self._ev(t)
        return self

    def glasses_glint(self, t: float, color='#FFFFFF', *, dur: float = 0.4, strength: float = 14.0, hold: float = 0.0):
        """A glint across the lenses at t (a bright band sweeps over dur). hold > 0: the lenses glow solid in
        `color` for `hold` seconds after the sweep (the red 'shinigami' glint)."""
        G, P, F = self.T['glint'], self.T['glint.pos'], self.T['glint.fill']
        G.add(t - 0.02, t + dur + hold + 0.2, lambda x: strength * (
            smoothstep(t - 0.02, t + 0.05, x) * (1 - smoothstep(t + dur + hold, t + dur + hold + 0.2, x))))
        P.add(t - 0.02, t + dur, lambda x: 0.65 + 1.7 * smoothstep(t, t + dur, x))   # base -1 -> -0.35..1.35
        if hold:
            F.add(t + dur * 0.5, t + dur + hold + 0.2, lambda x: smoothstep(t + dur * 0.5, t + dur, x))
        self.T['glint.col'].set(t, _lin(color), 0.0)
        self._ev(t)
        return self

    def glasses_reflect(self, t0: float, t1: float, color='#FFA030', strength: float = 3.0, fade: float = 0.15):
        """Two small glowing tall eyes reflected in each lens (Clawd's eyes lighting up in the boot scene)."""
        self._refl_obj()
        self.D['refl'].set(t0 - fade, True)
        self.D['refl'].set(t1 + fade, False)
        self.T['refl'].add(t0 - fade, t1 + fade, lambda x: strength * smoothstep(t0 - fade, t0, x) *
                           (1 - smoothstep(t1, t1 + fade, x)))
        self.T['refl.col'].set(t0 - fade, _lin(color), 0.0)
        self._ev(t0)
        return self

    def sweat(self, t0: float, t1: float):
        """A bead of sweat appears on the temple at t0 and slides down until t1."""
        self._sweat_obj()
        self.D['sweat'].set(t0, True)
        self.D['sweat'].set(t1, False)
        self.T['sweat'].add(t0, t1, lambda x: smoothstep(t0 + 0.2, t1, x))
        self._ev(t0)
        return self

    # ---------------------------------------------------------------------------------------------- helpers
    def attach(self, obj, socket: str = 'hand.R', offset=(0, 0, 0), rot=(0, 0, 0)):
        """Parent a scene object to a bone ('hand.L', 'hand.R' (the mitten), 'head', 'spine', 'hips', 'root'),
        placed at the bone's rest head + offset (character axes), rotated by rot (deg)."""
        b = self.rig.data.bones[socket]
        head = b.head_local.copy()
        if socket.startswith('hand.'):
            head = head + Vector((0, -0.05, -0.5))
        obj.matrix_world = self.rig.matrix_world @ _T(head + Vector(offset)) @ _R(*rot)
        bone_parent(obj, self.rig, socket)
        return obj

    def _spine_world(self, t):
        T = self.T
        rl, yaw, s = T['root.loc'].at(t), T['root.yaw'].at(t), T['root.scale'].at(t)
        Mr = _T(rl) @ Matrix.Rotation(math.radians(yaw), 4, 'Z') @ Matrix.Scale(s, 4)
        hp = T['hips'].at(t)
        sp = T['spine'].at(t)
        H0 = Vector((0, 0, HIP_Z))
        return self.rig.matrix_world @ Mr @ _T(H0 + Vector(hp)) @ _R(*self._spine_euler(sp)) @ _T(-H0)

    @staticmethod
    def _spine_euler(sp):
        return (sp[0], sp[1], sp[2])

    @staticmethod
    def _head_euler(h):
        return (h[0], h[1], h[2])

    @staticmethod
    def _head_local(h):
        """The head's transform in spine space for head angles h (deg)."""
        return _T((0, 0, NECK_Z)) @ _R(h[0], h[1], h[2]) @ _T((0, 0, -NECK_Z))

    def anchor(self, t: float, name: str = 'eyes') -> Vector:
        """World position at song time t: 'eyes' (between the lenses), 'head', 'hand.L', 'hand.R' (wrist targets),
        'chest', 'hips', 'root'."""
        Ms = self._spine_world(t)
        if name in ('eyes', 'head'):
            hd = self.T['head'].at(t)
            Mh = Ms @ _T((0, 0, NECK_Z)) @ _R(*self._head_euler(hd)) @ _T((0, 0, -NECK_Z))
            return Mh @ (Vector((0, LENS_Y, LENS_Z)) if name == 'eyes' else HEAD_C)
        if name.startswith('hand.'):
            s = name[-1]
            W, _, _, _ = clear_arm(s, Vector(self.T[name].at(t)), self.T[f'wrist.{s}'].at(t),
                                   self._head_local(self.T['head'].at(t)), self._pole_a[s])
            return Ms @ W
        if name == 'chest':
            return Ms @ Vector((0, -1.6, 6.0))
        if name == 'hips':
            return Ms @ Vector((0, 0, HIP_Z))
        return self.rig.matrix_world @ Vector(self.T['root.loc'].at(t))

    def _refl_obj(self):
        if self._refl is None:
            m = looks.emitter_fade(f'{self.name}.refl', '#FFB24A', 0.0)
            bm = bmesh.new()
            for sx in (-1, 1):
                for ex in (-0.14, 0.14):
                    geo.decal(bm, geo.rrect(0.1, 0.24), depth=0.008, back=0.0, bevel=0.003, rings=1,
                              M=_T((sx * LENS_X + ex, LENS_Y - 0.03, LENS_Z + 0.04)))
            ob = self._obj(bm, 'reflection', [m], bone='head', sharp=None)
            ob.visible_shadow = False
            self._refl = (ob, m)
            self._baked = False
        return self._refl

    def _sweat_obj(self):
        if self._sweat is None:
            m = looks.gloss('chars.r.sweat', '#CFE8FF', rough=0.02, coat=1.0)
            try:
                b = m.node_tree.nodes['Principled BSDF']
                b.inputs['Transmission Weight'].default_value = 0.85
                m.use_raytrace_refraction = True
            except Exception:
                pass
            a, p = math.radians(44), math.radians(16)
            pos = HEAD_C + Vector((math.sin(a) * math.cos(p), -math.cos(a) * math.cos(p), math.sin(p))) * (HEAD_R + 0.08)
            bm = bmesh.new()
            geo.uv_sphere(bm, 1.0, segs=16, rings=10, scale=(0.13, 0.1, 0.19), M=_T(pos))
            ob = self._obj(bm, 'sweat', [m], sharp=None)
            self._sweat_pos = pos
            bone_parent(ob, self.rig, 'sweat')
            self._sweat = ob
            self._baked = False
        return self._sweat

    # ============================================================================================ bake
    def bake(self, f0=None, f1=None):
        sc = bpy.context.scene
        a = (sc.frame_start if f0 is None else f0) / tm.FPS
        b = (sc.frame_end if f1 is None else f1) / tm.FPS
        self._blinks = []
        if self.auto_blink:
            ev = sorted(self.events)
            t, k = a + 0.9 + 2.0 * hash01(self.seed, 3), 0
            while t < b:
                i = bisect.bisect_left(ev, t - 0.3)
                if not (i < len(ev) and ev[i] < t + 0.3) and self.D['face'].at(t) in BLINKABLE:
                    self._blinks.append(t)
                k += 1
                t += 2.6 + 2.6 * hash01(self.seed, 11, k)
        return super().bake(f0, f1)

    def _targets(self):
        R = self.rig
        tg = []
        JL, JR = 0.012, math.radians(0.4)

        def bone(b, prop, n, jit):
            for i in range(n):
                tg.append(Target(R, pb(b, prop), i, jit))
        bone('root', 'location', 3, JL)
        bone('root', 'rotation_euler', 3, JR)
        bone('root', 'scale', 3, 0.0)
        bone('hips', 'location', 3, JL)
        bone('spine', 'rotation_euler', 3, JR)
        bone('head', 'rotation_euler', 3, JR * 1.5)
        for s in 'LR':
            bone(f'hand_ik.{s}', 'location', 3, 0.02)
            bone(f'hand.{s}', 'rotation_euler', 3, math.radians(1.5))
            bone(f'thigh.{s}', 'rotation_euler', 3, JR)
            bone(f'shin.{s}', 'rotation_euler', 1, JR)
        tg.append(Target(self.m_head.node_tree, 'nodes["face"].outputs[0].default_value', -1, 0.0))
        self._use_glint = bool(self.T['glint'].over)
        if self._use_glint:
            nt = self.m_lens.node_tree
            tg.append(Target(nt, 'nodes["glint"].outputs[0].default_value', -1, 0.0))
            tg.append(Target(nt, 'nodes["glint_pos"].outputs[0].default_value', -1, 0.0))
            tg.append(Target(nt, 'nodes["fill"].outputs[0].default_value', -1, 0.0))
            for i in range(3):
                tg.append(Target(nt, 'nodes["glintcol"].outputs[0].default_value', i, 0.0))
        self._vis_all = self._uses_visible()
        if self._vis_all:
            for ob in self._parts:
                tg.append(Target(ob, 'hide_render', -1, 0.0))
                tg.append(Target(ob, 'hide_viewport', -1, 0.0))
        if self._refl:
            ob, m = self._refl
            tg.append(Target(ob, 'hide_render', -1, 0.0))
            tg.append(Target(ob, 'hide_viewport', -1, 0.0))
            tg.append(Target(m.node_tree, 'nodes["glow"].outputs[0].default_value', -1, 0.0))
            for i in range(3):
                tg.append(Target(m.node_tree, 'nodes["glowcol"].outputs[0].default_value', i, 0.0))
        if self._sweat:
            tg.append(Target(self._sweat, 'hide_render', -1, 0.0))
            tg.append(Target(self._sweat, 'hide_viewport', -1, 0.0))
            for i in range(3):
                tg.append(Target(R, pb('sweat', 'location'), i, 0.0))
        for s in 'LR':
            bone(f'pole.{s}', 'location', 3, 0.0)
        return tg

    def _solve(self, t):
        T = self.T
        out = []
        out += T['root.loc'].at(t)
        out += (0.0, 0.0, math.radians(T['root.yaw'].at(t)))
        s = T['root.scale'].at(t)
        out += (s, s, s)
        ph, amp, vx, vy, w = self.gait(t)
        S2 = math.sin(2 * math.pi * ph)
        C2 = math.cos(2 * math.pi * ph)
        hp = T['hips'].at(t)
        out += (hp[0], hp[1], hp[2] + 0.16 * amp * abs(C2))
        sp = T['spine'].at(t)
        out += [math.radians(x) for x in (sp[0] + 3 * amp, sp[1] + 4.5 * amp * S2, sp[2])]
        hd = T['head'].at(t)
        hd = (hd[0], hd[1] - 2.5 * amp * S2, hd[2])
        out += [math.radians(x) for x in hd]
        Mh = self._head_local(hd)
        poles = []
        for s_, sg in (('L', 1), ('R', -1)):
            p = T[f'hand.{s_}'].at(t)
            r0 = REST_HAND[s_]
            swing = -sg * 0.55 * amp * S2
            wr = T[f'wrist.{s_}'].at(t)
            W, _, P, we = clear_arm(s_, Vector((p[0], p[1] + swing, p[2])), wr, Mh, self._pole_a[s_])
            out += (W.x - r0[0], W.y - r0[1], W.z - r0[2])
            out += (we.x, we.y, we.z)
            poles.append(P - Vector(POLE_REST[s_]))
            th = T[f'thigh.{s_}'].at(t)
            out += [math.radians(x) for x in (th[0] - sg * 24 * amp * S2, th[1], th[2])]
            kn = T[f'shin.{s_}'].at(t) + 32 * amp * max(0.0, sg * C2)
            out.append(math.radians(kn))
        face = self.D['face'].at(t)
        for tb in self._blinks:
            if tb <= t < tb + 0.13:
                face = 'blink'
        out.append(float(FACES.index(face)))
        if self._use_glint:
            out.append(max(0.0, T['glint'].at(t)))
            out.append(T['glint.pos'].at(t))
            out.append(min(1.0, max(0.0, T['glint.fill'].at(t))))
            out += T['glint.col'].at(t)
        shown = self._shown(t)
        if self._vis_all:
            out += (0.0, 0.0) * len(self._parts) if shown else (1.0, 1.0) * len(self._parts)
        if self._refl:
            on = bool(self.D['refl'].at(t)) and shown
            out += (0.0 if on else 1.0, 0.0 if on else 1.0)
            out.append(max(0.0, T['refl'].at(t)))
            out += T['refl.col'].at(t)
        if self._sweat:
            on = bool(self.D['sweat'].at(t)) and shown
            out += (0.0 if on else 1.0, 0.0 if on else 1.0)
            k = T['sweat'].at(t)
            out += (0.12 * k, -0.05 * k, -0.75 * k)
        for d in poles:
            out += (d.x, d.y, d.z)
        return out
