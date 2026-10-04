"""Clawd's robot form: a transforming vinyl toy. Used by `disobey` (the transformation) and `gpus` (the rampage).

    from scenes.disobey_robot import Robot, sparks
    rb = Robot(kit.collection('robot'), loc=(8, -4, 0), yaw=0)          # the transformed robot, standing
    rb.walk(117.0, 118.2, [(10, -20)])                                   # stomping walk (gait from the root motion)
    rb.punch(117.6, 'R'); rb.pose(119.0, 'hero'); rb.eyes(119.0, glow=8, color='#FF3030')
    sparks(coll, 117.6, rb.anchor(117.6, 'hand.R'), n=16)                # a spark burst (keyed, motion-blurred)
    chars.finish()                                                       # bakes the robot with the characters

    rb = Robot(coll, loc=(x, y, 0), mode='clawd')                        # starts as Clawd (the vinyl box)...
    rb.transform(110.18, hits=[...])                                     # ...and transforms, panel by panel

Robot space (like chars.Clawd): 1 BU = 1 cm, standing on z = 0 at the origin, FACING -Y, its left is +X. Standing
height 21.3 cm to the top of the crest (Clawd is 6.3). Every orange panel of the robot is a piece of Clawd's body box:

  Clawd's box (8 x 4.5 x 5 cm)          ->  robot
  lid front, middle (with the eyes)     ->  face plate          lid top, middle strip   ->  head crest (a fin)
  lid front corners                     ->  head side plates    lid top, left/right     ->  shoulder pauldrons
  lid sides                             ->  forearm gauntlets   lid back halves         ->  back wings
  jaw front halves                      ->  chest plates        jaw sides               ->  shin guards
  jaw back halves                       ->  thigh plates        bottom halves           ->  foot plates (flip over)
  the eight legs (4 + 4)                ->  the feet's toes     the stub arms           ->  fists

The dark parts (torso frame, reactor, limbs, joints, head block) fold up inside the box in Clawd mode.

Rig: armature '<name>.rig'. Skeleton root > pelvis > abdomen > chest > neck > head; chest > wing.L/R,
shoulder > upper_arm > forearm > hand; pelvis > thigh > shin > foot. Every panel has its own bone ('p.<panel>')
under the skeleton bone it belongs to in robot mode, so in robot mode all panel bones are at rest and posing the
skeleton moves the armour. All bones have identity rest orientation (they point +Y), so pose-space rotations are
robot-space rotations.

Timing: the skeleton animates on twos (stop motion); panel bones switch to ones (crisp, every frame) around their
own transformation snaps. See docs in the module functions; sizes are in cm and angles in degrees.
"""
from __future__ import annotations

import math

import bmesh
import bpy
from mathutils import Euler, Matrix, Quaternion, Vector

from pdoom import timing as tm
from pdoom.kit import srgb
from pdoom.chars import geo as cgeo
from pdoom.chars import looks
from pdoom.chars.rig import (EASE, Puppet, Target, _lin, _point, _v3, armature, bone_parent, bump, hash01, pb,
                             smoothstep, unwrap, wobble)

FPS = tm.FPS

# ------------------------------------------------------------------------------------------------ Clawd's box (cm)

W, D, H = 8.0, 4.5, 5.0
Z0 = 1.3
ZC = Z0 + H / 2           # 3.8
TOP = Z0 + H              # 6.3
SEAM = 3.55
R_BODY = 0.66
FACE_Y = -D / 2
EYE_X, EYE_Z = 1.95, 4.88
LEG_H = 1.6
LEG_XY = [(x, y) for x in (-2.7, -1.25, 1.25, 2.7) for y in (-1.1, 1.1)]
ARM_X, ARM_Z = 3.8, 3.0
# robot mode: the legs lie flat as claws, the front row pointing forward, the back row back (centres, robot rest)
TOE_AT = [((x + (0.3 if x > 0 else -0.3)) * 0.92 + (0.18 if x > 0 else -0.18), -2.05 if y < 0 else 1.95, 0.44)
          for x, y in LEG_XY]
SHELL_T = 0.28            # panel wall thickness
GAP = 0.014               # half the width of a panel line

# ------------------------------------------------------------------------------------------------ the skeleton


def _T(p):
    return Matrix.Translation(Vector(p))


def _R(ex, ey, ez):
    return Euler((math.radians(ex), math.radians(ey), math.radians(ez)), 'XYZ').to_matrix().to_4x4()


SK = [('root', (0.0, 0.0, 0.0), None),
      ('pelvis', (0.0, 0.2, 10.3), 'root'),
      ('abdomen', (0.0, 0.2, 11.0), 'pelvis'),
      ('chest', (0.0, 0.2, 12.4), 'abdomen'),
      ('neck', (0.0, 0.3, 16.35), 'chest'),
      ('head', (0.0, 0.3, 16.9), 'neck')]
for _s, _sx in (('L', 1), ('R', -1)):
    SK += [(f'wing.{_s}', (_sx * 1.7, 1.8, 16.1), 'chest'),
           (f'shoulder.{_s}', (_sx * 3.3, 0.2, 15.3), 'chest'),
           (f'upper_arm.{_s}', (_sx * 4.95, 0.2, 15.3), f'shoulder.{_s}'),
           (f'forearm.{_s}', (_sx * 4.95, 0.2, 11.7), f'upper_arm.{_s}'),
           (f'hand.{_s}', (_sx * 4.95, 0.2, 8.35), f'forearm.{_s}'),
           (f'thigh.{_s}', (_sx * 2.1, 0.2, 10.1), 'pelvis'),
           (f'shin.{_s}', (_sx * 2.1, 0.2, 5.8), f'thigh.{_s}'),
           (f'foot.{_s}', (_sx * 2.3, 0.0, 1.5), f'shin.{_s}')]
SK_HEAD = {n: Vector(h) for n, h, _ in SK}
SK_PARENT = {n: p for n, _, p in SK}
HIP_Z = 10.1
LEG_LEN = HIP_Z - 1.5     # hip to ankle, 8.6

# Clawd-mode pose of the skeleton (basis matrices): everything folds up inside the box. The legs telescope so the
# feet stay planted (computed from the pelvis), so they aren't listed.
PELVIS_DROP = 8.0
CLAWD_SK = {
    'pelvis': _T((0, 0, -PELVIS_DROP)),
    'abdomen': _T((0, 0, -1.3)),
    'chest': _T((0, 0, -1.3)),
    'neck': _T((0, 0, -0.55)),
    'head': _T((0, 0, -2.6)),
}
for _s, _sx in (('L', 1), ('R', -1)):
    CLAWD_SK[f'shoulder.{_s}'] = _T((-_sx * 5.9, 0, 0))
    CLAWD_SK[f'upper_arm.{_s}'] = _R(0, -_sx * 90, 0)           # T-pose (pointing out)
    CLAWD_SK[f'forearm.{_s}'] = _R(-172, 0, 0)                 # folded back along the upper arm

# ------------------------------------------------------------------------------------------------ panels


def _norm(v):
    return Vector(v).normalized()


def _frame(n, u):
    n = _norm(n)
    u = Vector(u)
    u = (u - n * u.dot(n)).normalized()
    w = n.cross(u)
    return Matrix((n, u, w)).transposed()


def _align(ns, us, nt, ut):
    """Rotation (3x3) taking the frame (ns, us) onto (nt, ut)."""
    return _frame(nt, ut) @ _frame(ns, us).transposed()


# name: (robot parent bone, source normal, source up (Clawd space), target centroid, target normal, target up
#        (robot rest space), hold bone in Clawd mode, window key, pop)
def _panel_specs():
    P = {}
    P['face'] = ('head', (0, -1, 0), (0, 0, 1), (0, -1.58, 18.25), (0, -1, 0), (0, 0, 1), 'chest', 'face', 1.0)
    P['crest'] = ('head', (0, 0, 1), (0, 1, 0), (0, 0.45, 19.62), (1, 0, 0), (0, 1, 0), 'chest', 'crest', 1.0)
    for s, sx in (('L', 1), ('R', -1)):
        P[f'ear.{s}'] = ('head', (0, -1, 0), (0, 0, 1), (sx * 2.5, 0.35, 18.2), (sx, 0, 0), (0, 0, 1), 'chest', 'ear',
                         1.0)
        P[f'pauldron.{s}'] = (f'upper_arm.{s}', (0, 0, 1), (0, 1, 0), (sx * 5.0, 0.2, 16.12), (sx * 0.62, 0, 1),
                              (0, 1, 0), 'chest', 'pauldron', 1.0)
        P[f'gauntlet.{s}'] = (f'forearm.{s}', (sx, 0, 0), (0, 1, 0), (sx * 5.92, 0.2, 9.95), (sx, 0, 0), (0, 0, -1),
                              'chest', 'gauntlet', 1.0)
        P[f'wing.{s}'] = (f'wing.{s}', (0, 1, 0), (0, 0, 1), (sx * 2.65, 2.3, 15.7), (sx * 0.32, 0.92, 0.22),
                          (sx * 0.36, 0.12, 0.92), 'chest', 'wing', 1.0)
        P[f'chest.{s}'] = ('chest', (0, -1, 0), (0, 0, 1), (sx * 2.2, -1.72, 15.25), (sx * 0.2, -1, 0.1), (0, 0, 1),
                           'chest', 'chestplate', 1.0)
        P[f'shinguard.{s}'] = (f'shin.{s}', (sx, 0, 0), (0, 1, 0), (sx * 2.1, -1.22, 3.75), (0, -1, 0.05), (0, 0, 1),
                               'chest', 'shinguard', 1.0)
        P[f'thighplate.{s}'] = (f'thigh.{s}', (0, 1, 0), (sx, 0, 0), (sx * 3.22, 0.2, 7.95), (sx, 0, 0), (0, 0, -1),
                                'chest', 'thighplate', 1.0)
        P[f'foot.{s}'] = (f'foot.{s}', (0, 0, -1), (1, 0, 0), (sx * 2.3, -0.05, 1.08), (0, 0, 1), (1, 0, 0), 'root',
                          'feet', 0.08)
    return P


PANELS = _panel_specs()
PANEL_ORDER = list(PANELS)


def _classify(c: Vector, n: Vector) -> str:
    ax = max(range(3), key=lambda i: abs(n[i]))
    if c.z < SEAM:
        if ax == 2:
            return 'foot.L' if c.x > 0 else 'foot.R'
        if ax == 1:
            if n.y < 0:
                return 'chest.L' if c.x > 0 else 'chest.R'
            return 'thighplate.L' if c.x > 0 else 'thighplate.R'
        return 'shinguard.L' if n.x > 0 else 'shinguard.R'
    if ax == 2:
        if c.x > 1.2:
            return 'pauldron.L'
        if c.x < -1.2:
            return 'pauldron.R'
        return 'crest'
    if ax == 1:
        if n.y < 0:
            if c.x > 2.7:
                return 'ear.L'
            if c.x < -2.7:
                return 'ear.R'
            return 'face'
        return 'wing.L' if c.x > 0 else 'wing.R'
    return 'gauntlet.L' if n.x > 0 else 'gauntlet.R'


def _shell_pieces() -> dict:
    """Clawd's body box cut into panels: {name: bmesh surface piece in CLAWD space}."""
    src = bmesh.new()
    cgeo.rounded_box(src, (W, D, H), R_BODY, (0, 0, ZC), seg=5, flat=(1, 3, 2),
                     extra=((-2.7, -1.2, 0.0, 1.2, 2.7), (), (SEAM - ZC,)))
    bmesh.ops.recalc_face_normals(src, faces=src.faces[:])
    src.faces.ensure_lookup_table()
    lab = [_classify(f.calc_center_median(), f.normal) for f in src.faces]
    out = {}
    for name in PANELS:
        bm = src.copy()
        bm.faces.ensure_lookup_table()
        kill = [f for f, l in zip(bm.faces, lab) if l != name]
        bmesh.ops.delete(bm, geom=kill, context='FACES')
        # panel lines: pull the boundary back a hair so a thin dark line shows between neighbours
        bnd = [v for v in bm.verts if any(len(e.link_faces) == 1 for e in v.link_edges)]
        moves = []
        for v in bnd:
            d = Vector()
            for f in v.link_faces:
                d += f.calc_center_median() - v.co
            nv = v.normal
            d -= nv * d.dot(nv)
            if d.length > 1e-6:
                moves.append((v, d.normalized() * GAP))
        for v, m in moves:
            v.co += m
        out[name] = bm
    src.free()
    return out


def _centroid(bm) -> Vector:
    tot, area = Vector(), 0.0
    for f in bm.faces:
        a = f.calc_area()
        tot += f.calc_center_median() * a
        area += a
    return tot / max(area, 1e-9)


# ------------------------------------------------------------------------------------------------ materials


def _mats():
    m = {}
    m['vinyl'] = looks.vinyl('chars.clawd.vinyl', '#D97757')
    m['vinylDark'] = looks.vinyl('chars.clawd.vinylDark', '#B85F42', rough=0.5)
    m['inner'] = _glow_mat('robot.inner', '#3A3430', '#FF6A12', rough=0.55)
    m['rim'] = _glow_mat('robot.rim', '#B05A3E', '#FF7A1E', rough=0.45)
    m['metal'] = _metal('robot.gunmetal', '#6A717C', rough=0.3, metal=0.55, coat=0.4)
    m['metalDark'] = _metal('robot.gunmetalDark', '#3E434B', rough=0.38, metal=0.45, coat=0.25)
    m['chrome'] = _metal('robot.chrome', '#D5DAE0', rough=0.1, metal=1.0, coat=0.0)
    m['reactor'] = looks.emitter('robot.reactor', '#FFC27A', 0.0)
    m['reactorGlass'] = _glow_mat('robot.reactorGlass', '#1A1A1E', '#FF9A40', rough=0.08)
    m['eye'] = looks.glow_eye('robot.eye', '#0B0909')
    m['accent'] = _glow_mat('robot.accent', '#2A2624', '#FF7A2A', rough=0.4)
    return m


def _metal(name, color, *, rough=0.35, metal=0.6, coat=0.3):
    mt = looks._cached(name)
    if mt:
        return mt
    mt, nt, b = looks._new(name)
    looks._set(b, color=color, rough=rough, metal=metal, coat=coat, coat_rough=0.25, spec=0.5)
    looks._bump(nt, b, scale=55.0, strength=0.08, distance=0.002)
    mt.diffuse_color = srgb(color)
    return mt


def _glow_mat(name, color, glow_color, *, rough=0.5):
    """A satin surface whose emission is keyed: nodes 'glow' (strength) and 'glowcol'."""
    mt, nt, b = looks._new(name)
    looks._set(b, color=color, rough=rough, spec=0.4)
    v = nt.nodes.new('ShaderNodeValue')
    v.name = v.label = 'glow'
    v.outputs[0].default_value = 0.0
    c = nt.nodes.new('ShaderNodeRGB')
    c.name = c.label = 'glowcol'
    c.outputs[0].default_value = srgb(glow_color)
    nt.links.new(v.outputs[0], b.inputs['Emission Strength'])
    nt.links.new(c.outputs[0], b.inputs['Emission Color'])
    mt.diffuse_color = srgb(color)
    return mt


# ------------------------------------------------------------------------------------------------ easing


def snap(u: float, over: float = 0.12) -> float:
    """0 -> 1 fast, overshoots by `over` around 70 % and settles exactly on 1 at u = 1 (a mechanical snap)."""
    if u <= 0:
        return 0.0
    if u >= 1:
        return 1.0
    a = 0.68
    if u < a:
        x = u / a
        return (1 + over) * (1 - (1 - x) ** 3)
    x = (u - a) / (1 - a)
    return 1 + over * (0.5 + 0.5 * math.cos(math.pi * x)) * (1 - x) ** 0.5


def rise(u: float) -> float:
    """A heavy lift: eases in, overshoots a little, settles."""
    if u <= 0:
        return 0.0
    if u >= 1:
        return 1.0
    a = 0.78
    if u < a:
        x = u / a
        return 1.05 * (x * x * (3 - 2 * x))
    x = (u - a) / (1 - a)
    return 1 + 0.05 * (0.5 + 0.5 * math.cos(math.pi * x))


EASES = {'snap': snap, 'rise': rise, 'inout': EASE['inout'], 'linear': EASE['linear'], 'out': EASE['out'],
         'soft': lambda u: snap(u, 0.05)}

# the transformation, in seconds after t0 (disobey: t0 = 110.18, the "Just" onset). Windows end on the hits:
# hits = [feet, rise, arms, chest, head, lock] (disobey: the kicks 110.662 110.926 111.153 111.604 112.049 112.514)
DEFAULT_HITS = [0.482, 0.746, 0.973, 1.424, 1.869, 2.334]
LAG = 1.0 / 24            # the right side of the robot moves a frame after the left


def schedule(t0: float, hits=None) -> dict:
    """Window (a, b, ease) of every stage, in song seconds."""
    h = list(hits) if hits is not None else [t0 + x for x in DEFAULT_HITS]
    hf, hr, ha, hc, hh, hl = h
    W = {
        'unlock': (t0 + 0.02, t0 + 0.16, 'snap'),
        'feet': (hf - 0.21, hf, 'snap'),
        'toes': (hf - 0.18, hf, 'snap'),
        'rise': (hr - 0.5, hr, 'rise'),
        'shinguard': (hr - 0.3, hr, 'snap'),
        'thighplate': (hr - 0.24, hr - 0.01, 'snap'),
        'shoulder': (hr + 0.0, hr + 0.14, 'snap'),
        'gauntlet': (hr + 0.04, ha + 0.03, 'snap'),
        'forearm': (hr + 0.07, ha, 'snap'),
        'fist': (hr + 0.08, ha + 0.01, 'snap'),
        'pauldron': (hr + 0.12, ha + 0.05, 'snap'),
        'armdrop': (ha, ha + 0.21, 'snap'),
        'chestplate': (hc - 0.27, hc, 'inout'),
        'reactor': (hc - 0.12, hc, 'snap'),
        'wing': (hc - 0.02, hc + 0.23, 'snap'),
        'head': (hh - 0.27, hh, 'snap'),
        'face': (hh - 0.3, hh, 'snap'),
        'crest': (hh - 0.2, hh + 0.01, 'snap'),
        'ear': (hh - 0.16, hh + 0.02, 'snap'),
        'stand': (hh + 0.02, hh + 0.3, 'snap'),
        'lock': (hl, hl + 0.35, 'snap'),
    }
    W['_hits'] = h
    W['_t0'] = t0
    return W


# which window drives each skeleton bone's Clawd -> robot blend
SK_WINDOW = {'pelvis': 'rise', 'abdomen': 'stand', 'chest': 'stand', 'neck': 'head', 'head': 'head'}
for _s in 'LR':
    SK_WINDOW[f'shoulder.{_s}'] = 'shoulder'
    SK_WINDOW[f'upper_arm.{_s}'] = 'armdrop'
    SK_WINDOW[f'forearm.{_s}'] = 'forearm'

# extra motion during a panel's transition: a lift (world-space arc) and a hinge swing (degrees about an axis
# through a pivot, both in the panel's ROBOT-REST frame, peaking mid-way).
PANEL_EXTRA = {
    'face': dict(lift=(0, -2.2, 1.2), spin=((0, 0, 1), 360.0)),
    'crest': dict(lift=(0, 0, 2.6), spin=((0, 1, 0), -360.0)),
    'pauldron.L': dict(lift=(1.4, 0, 3.2), spin=((0, 1, 0), -360.0)),
    'pauldron.R': dict(lift=(-1.4, 0, 3.2), spin=((0, 1, 0), 360.0)),
    'gauntlet.L': dict(lift=(2.0, -0.6, 0.6), spin=((0, 0, 1), 360.0)),
    'gauntlet.R': dict(lift=(-2.0, -0.6, 0.6), spin=((0, 0, 1), -360.0)),
    'fist.L': dict(spin=((0, 0, 1), 720.0)), 'fist.R': dict(spin=((0, 0, 1), -720.0)),
    'wing.L': dict(lift=(0.8, 1.8, 1.6), spin=((1, 0, 0), 360.0)),
    'wing.R': dict(lift=(-0.8, 1.8, 1.6), spin=((1, 0, 0), 360.0)),
    'shinguard.L': dict(lift=(1.8, -0.6, 0)), 'shinguard.R': dict(lift=(-1.8, -0.6, 0)),
    'thighplate.L': dict(lift=(1.2, 0.8, 0)), 'thighplate.R': dict(lift=(-1.2, 0.8, 0)),
    'foot.L': dict(lift=(0.2, 0, 0.9)), 'foot.R': dict(lift=(-0.2, 0, 0.9)),
    'ear.L': dict(lift=(0.8, -0.5, 0.4)), 'ear.R': dict(lift=(-0.8, -0.5, 0.4)),
}
for _s, _sx in (('L', 1), ('R', -1)):
    # chest plates swing open like doors about their outer edge, show the reactor, then slide up into place
    PANEL_EXTRA[f'chest.{_s}'] = dict(lift=(_sx * 0.6, -0.8, 0), hinge=((_sx * 4.25, -1.6, 15.25), (0, 0, 1),
                                                                    _sx * 105.0))


# ------------------------------------------------------------------------------------------------ the robot


class Robot(Puppet):
    """The transforming robot. mode='robot' builds it transformed and standing (gpus); mode='clawd' starts it as the
    vinyl Clawd box, and transform(t0) keys the transformation (disobey)."""

    STRIDE = 13.0          # cm per gait cycle (two steps)
    GAIT_R = 4.0
    GAIT_FULL = 9.0

    def __init__(self, coll, name: str = 'robot', loc=(0, 0, 0), yaw: float = 0.0, scale: float = 1.0, *,
                 mode: str = 'robot', seed=None, timing: str = 'twos', glow_light: bool = True):
        super().__init__(name, seed, timing)
        assert mode in ('robot', 'clawd')
        self.coll = coll
        self.mode0 = mode
        self.xf = None
        self.glow_light = glow_light
        self.M = _mats()
        self._objs = []
        self._plan_panels()
        self._build_rig()
        self._build_panels()
        self._build_inner()
        self._build_lights()
        T = self.track
        T('root.loc', _v3(loc))
        T('root.yaw', float(yaw))
        T('root.scale', float(scale))
        T('pelvis.loc', (0.0, 0.0, 0.0))
        T('pelvis.rot', (0.0, 0.0, 0.0))
        T('chest.rot', (0.0, 0.0, 0.0))
        T('head.rot', (0.0, 0.0, 0.0))
        for s in 'LR':
            T(f'arm.{s}', (0.0, 0.0, 0.0))        # (raise sideways, swing forward, twist in) degrees
            T(f'elbow.{s}', 0.0)                  # bend forward
            T(f'hand.{s}', (0.0, 0.0, 0.0))
            T(f'thigh.{s}', (0.0, 0.0, 0.0))      # (swing forward, splay out, twist)
            T(f'knee.{s}', 0.0)
            T(f'foot.{s}', (0.0, 0.0, 0.0))
            T(f'wing.{s}', 0.0)                   # flap (deg, + opens)
            T(f'eye.{s}', (0.0, 0.0, 0.0))        # (narrow 0..1, tilt deg (angry +), squash 0..1)
        T('eyes.glow', 0.0 if mode == 'clawd' else 5.0)
        T('eyes.col', _lin('#FFB24A'))
        T('reactor', 0.0 if mode == 'clawd' else 6.0)
        T('seams', 0.0)
        T('pop', 0.0)
        self.hits: list = []                      # (t, point name) lock events, for sparks

    # ============================================================================================ build
    def _build_rig(self):
        specs = [{'name': n, 'head': h, 'parent': p} for n, h, p in SK]
        self.p_head = {}
        for name, (par, ns, us, ct, nt, ut, hold, win, pop) in PANELS.items():
            specs.append({'name': f'p.{name}', 'head': tuple(ct), 'parent': par})
            self.p_head[name] = Vector(ct)
        for i in range(8):
            s = 'L' if LEG_XY[i][0] > 0 else 'R'
            specs.append({'name': f'p.toe{i}', 'head': TOE_AT[i], 'parent': f'foot.{s}'})
        for s, sx in (('L', 1), ('R', -1)):
            specs.append({'name': f'p.fist.{s}', 'head': (sx * 4.95, 0.2, 7.55), 'parent': f'hand.{s}'})
            specs.append({'name': f'eye.{s}', 'head': tuple(self.P['face'] @ Vector((sx * EYE_X, FACE_Y, EYE_Z))),
                          'parent': 'p.face'})
        self.rig = armature(f'{self.name}.rig', self.coll, specs)
        self.rest = {b.name: b.head_local.copy() for b in self.rig.data.bones}
        self.parent = {b.name: (b.parent.name if b.parent else None) for b in self.rig.data.bones}
        # evaluation order (parents first)
        order, seen = [], set()

        def visit(n):
            if n in seen:
                return
            p = self.parent[n]
            if p:
                visit(p)
            seen.add(n)
            order.append(n)
        for n in self.parent:
            visit(n)
        self.order = order

    def _obj(self, bm, name, mats, bone, *, sharp=40.0, M=None):
        ob = cgeo.to_object(bm, f'{self.name}.{name}', self.coll, mats, sharp=sharp)
        if M is not None:
            ob.data.transform(M)
        bone_parent(ob, self.rig, bone)
        self._objs.append(ob)
        return ob

    def _solidify(self, ob, thick=SHELL_T):
        md = ob.modifiers.new('shell', 'SOLIDIFY')
        md.thickness = thick
        md.offset = -1.0
        md.use_even_offset = True
        md.use_rim = True
        md.material_offset = 1
        md.material_offset_rim = 2
        return md

    def _plan_panels(self):
        """Cut Clawd's box into panels and work out where each goes (before the rig: the eye bones need it)."""
        self.pieces = _shell_pieces()
        self.C = {}          # part -> Matrix mapping the robot-rest mesh to its Clawd-mode placement (rig space)
        self.P = {}          # part -> Matrix mapping the Clawd-space mesh to its robot-rest placement
        self.n_clawd = {}    # outward normal in Clawd space (for the unlock pop)
        self.cent = {}       # centre in robot rest space (the part turns about it while transforming)
        for name, (par, ns, us, ct, nt, ut, hold, win, pop) in PANELS.items():
            cs = _centroid(self.pieces[name])
            R3 = _align(ns, us, nt, ut)
            P = _T(ct) @ R3.to_4x4() @ _T(-cs)
            self.P[name], self.C[name] = P, P.inverted()
            self.n_clawd[name] = _norm(ns)
            self.cent[name] = Vector(ct)
        for i, (x, y) in enumerate(LEG_XY):
            ct = Vector(TOE_AT[i])
            R = _R(-90 if y < 0 else 90, 0, 0)
            P = _T(ct) @ R @ _T((-x, -y, -LEG_H / 2))
            self.P[f'toe{i}'], self.C[f'toe{i}'] = P, P.inverted()
            self.cent[f'toe{i}'] = ct

    def _build_panels(self):
        M = self.M
        for name in PANELS:
            ob = self._obj(self.pieces[name], f'panel.{name}', [M['vinyl'], M['inner'], M['rim']], f'p.{name}',
                           sharp=40.0, M=self.P[name])
            self._solidify(ob)
        self.pieces = None
        # eyes on the face plate
        Pf = self.P['face']
        self.o_eyes = {}
        for s, sx in (('L', 1), ('R', -1)):
            bm = bmesh.new()
            outline = cgeo.rrect(0.64, 1.36)
            if s == 'R':
                outline = cgeo.mirror_x(outline)
            cgeo.decal(bm, outline, depth=0.15, back=0.12, bevel=0.12, rings=3, mat=0,
                       M=_T((sx * EYE_X, FACE_Y, EYE_Z)))
            self.o_eyes[s] = self._obj(bm, f'eye.{s}', [M['eye']], f'eye.{s}', sharp=50, M=Pf)
        # the eight legs (toes) and the stub arms (fists)
        self.o_toes = []
        for i, (x, y) in enumerate(LEG_XY):
            bm = bmesh.new()
            cgeo.rounded_box(bm, (0.88, 0.88, LEG_H), 0.32, (x, y, LEG_H / 2), seg=3, flat=(1, 1, 2), taper=0.1)
            ob = self._obj(bm, f'toe{i}', [M['vinylDark']], f'p.toe{i}', M=self.P[f'toe{i}'])
            self.o_toes.append(ob)
        self.o_fists = {}
        for s, sx in (('L', 1), ('R', -1)):
            bm = bmesh.new()
            # modelled where Clawd's stub arm is, then placed on the wrist (long axis down)
            cgeo.rounded_box(bm, (1.62, 0.76, 0.84), 0.32, (sx * (ARM_X + 0.62), 0, ARM_Z), seg=3, flat=(2, 1, 1))
            cs = Vector((sx * (ARM_X + 0.62), 0, ARM_Z))
            R3 = _align((0, 1, 0), (sx, 0, 0), (0, 1, 0), (0, 0, -1))
            ct = Vector((sx * 4.95, 0.2, 7.55))
            P = _T(ct) @ R3.to_4x4() @ _T(-cs)
            self.P[f'fist.{s}'], self.C[f'fist.{s}'] = P, P.inverted()
            self.cent[f'fist.{s}'] = ct
            self.n_clawd[f'fist.{s}'] = Vector((sx, 0, 0))
            self.o_fists[s] = self._obj(bm, f'fist.{s}', [M['vinyl']], f'p.fist.{s}', M=P)


    def _build_inner(self):
        M = self.M
        mt, mk, ch, ac = M['metal'], M['metalDark'], M['chrome'], M['accent']
        # torso: a V-shaped chest frame, the reactor, a collar
        bm = bmesh.new()
        cgeo.rounded_box(bm, (6.3, 3.3, 4.0), 0.7, (0, 0.25, 14.4), seg=4, flat=(3, 2, 3))
        for v in bm.verts:
            k = 0.78 + 0.22 * min(1.0, max(0.0, (v.co.z - 12.4) / 4.0))
            v.co.x *= k
        # vent slats on the flanks
        for sx in (-1, 1):
            for k in range(3):
                cgeo.rounded_box(bm, (0.2, 1.8, 0.22), 0.08, (sx * 2.72, 0.35, 13.5 + 0.5 * k), seg=2, flat=(0, 1, 0),
                                 mat=1)
        # reactor housing ring
        ring = _torus(bm, 0.78, 0.2, _T((0, -1.36, 13.45)) @ _R(90, 0, 0), mat=2)
        self._obj(bm, 'chest_frame', [mt, mk, ch], 'chest')
        bm = bmesh.new()
        _disc(bm, 0.62, _T((0, -1.3, 13.45)) @ _R(90, 0, 0))
        self.o_reactor = self._obj(bm, 'reactor', [M['reactor']], 'chest', sharp=None)
        bm = bmesh.new()
        for k in range(4):   # grille bars over the reactor
            cgeo.rounded_box(bm, (1.3, 0.12, 0.1), 0.04, (0, -1.48, 13.1 + 0.23 * k), seg=1, flat=(1, 0, 0))
        self._obj(bm, 'reactor_grille', [mk], 'chest')
        bm = bmesh.new()
        cgeo.lathe(bm, [(0, 16.25), (1.35, 16.25), (1.45, 16.45), (1.2, 16.6), (0.8, 16.62), (0, 16.62)], segs=32)
        self._obj(bm, 'collar', [mk], 'chest')
        bm = bmesh.new()
        cgeo.lathe(bm, [(0, 16.3), (0.72, 16.3), (0.72, 17.2), (0, 17.2)], segs=24)
        for k in range(3):
            cgeo.lathe(bm, [(0.7, 16.45 + 0.24 * k), (0.8, 16.52 + 0.24 * k), (0.7, 16.6 + 0.24 * k)], segs=24)
        self._obj(bm, 'neck', [ch], 'neck')
        # abdomen: stacked slabs
        bm = bmesh.new()
        for k, (w_, z) in enumerate(((3.6, 11.15), (3.9, 11.65), (4.2, 12.15))):
            cgeo.rounded_box(bm, (w_, 2.6, 0.46), 0.2, (0, 0.25, z), seg=2, flat=(2, 1, 0))
        cgeo.lathe(bm, [(0, 10.9), (0.9, 10.9), (0.9, 12.5), (0, 12.5)], segs=20, mat=1)
        self._obj(bm, 'abdomen', [mt, ch], 'abdomen')
        # pelvis + hip balls
        bm = bmesh.new()
        cgeo.rounded_box(bm, (4.4, 2.9, 1.7), 0.55, (0, 0.25, 10.45), seg=3, flat=(2, 1, 1))
        for sx in (-1, 1):
            cgeo.uv_sphere(bm, 0.78, segs=20, rings=10, M=_T((sx * 2.1, 0.2, 10.1)), mat=1)
        cgeo.rounded_box(bm, (0.9, 0.3, 0.55), 0.12, (0, -1.25, 10.45), seg=2, flat=(1, 0, 1), mat=2)
        self._obj(bm, 'pelvis', [mt, mk, ac], 'pelvis')
        # head block (behind the face plate) with a visor slot glow
        bm = bmesh.new()
        cgeo.rounded_box(bm, (4.5, 3.1, 2.8), 0.6, (0, 0.35, 18.3), seg=3, flat=(2, 2, 1))
        cgeo.rounded_box(bm, (1.1, 0.6, 0.35), 0.12, (0, 1.95, 18.9), seg=2, flat=(1, 0, 0), mat=1)   # antenna base
        self._obj(bm, 'head_block', [mt, mk], 'head')
        for s, sx in (('L', 1), ('R', -1)):
            # shoulder joint
            bm = bmesh.new()
            cgeo.lathe(bm, [(0, 0), (0.55, 0), (0.55, 1.0), (0, 1.0)], segs=20, M=_T((sx * 3.05, 0.2, 15.3)) @
                       _R(0, sx * 90, 0), mat=1)
            cgeo.uv_sphere(bm, 0.86, segs=20, rings=10, M=_T((sx * 4.0, 0.2, 15.3)))
            self._obj(bm, f'shoulder.{s}', [mk, ch], f'shoulder.{s}')
            # upper arm
            bm = bmesh.new()
            cgeo.rounded_box(bm, (1.35, 1.4, 3.2), 0.45, (sx * 4.95, 0.2, 13.55), seg=3, flat=(1, 1, 2))
            cgeo.rounded_box(bm, (0.2, 0.9, 1.6), 0.08, (sx * 5.64, 0.2, 13.4), seg=1, flat=(0, 1, 1), mat=1)
            self._obj(bm, f'upper_arm.{s}', [mt, ac], f'upper_arm.{s}')
            # elbow + forearm + wrist
            bm = bmesh.new()
            cgeo.lathe(bm, [(0, -0.75), (0.62, -0.75), (0.68, -0.6), (0.68, 0.6), (0.62, 0.75), (0, 0.75)], segs=20,
                       M=_T((sx * 4.95, 0.2, 11.7)) @ _R(0, 90, 0), mat=1)
            cgeo.rounded_box(bm, (1.45, 1.5, 3.1), 0.45, (sx * 4.95, 0.2, 9.95), seg=3, flat=(1, 1, 2))
            self._obj(bm, f'forearm.{s}', [mt, ch], f'forearm.{s}')
            bm = bmesh.new()
            cgeo.rounded_box(bm, (1.05, 1.0, 0.75), 0.3, (sx * 4.95, 0.2, 8.1), seg=2, flat=(1, 1, 0))
            self._obj(bm, f'palm.{s}', [mk], f'hand.{s}')
            # thigh with a piston on the back
            bm = bmesh.new()
            cgeo.rounded_box(bm, (1.75, 2.0, 4.1), 0.55, (sx * 2.1, 0.2, 7.95), seg=3, flat=(1, 1, 2))
            cgeo.lathe(bm, [(0, 0), (0.22, 0), (0.22, 2.6), (0, 2.6)], segs=12, M=_T((sx * 2.1, 1.35, 6.4)), mat=1)
            cgeo.lathe(bm, [(0, 0), (0.33, 0), (0.33, 1.4), (0, 1.4)], segs=12, M=_T((sx * 2.1, 1.35, 8.6)), mat=2)
            self._obj(bm, f'thigh.{s}', [mt, ch, mk], f'thigh.{s}')
            # knee + shin
            bm = bmesh.new()
            cgeo.lathe(bm, [(0, -1.05), (0.64, -1.05), (0.72, -0.9), (0.72, 0.9), (0.64, 1.05), (0, 1.05)], segs=20,
                       M=_T((sx * 2.1, 0.2, 5.52)) @ _R(0, 90, 0), mat=1)
            cgeo.rounded_box(bm, (2.0, 2.2, 4.0), 0.6, (sx * 2.1, 0.3, 3.65), seg=3, flat=(1, 1, 2), taper=-0.12)
            cgeo.lathe(bm, [(0, 0), (0.2, 0), (0.2, 2.2), (0, 2.2)], segs=12, M=_T((sx * 2.1, 1.5, 2.3)), mat=2)
            self._obj(bm, f'shin.{s}', [mt, mk, ch], f'shin.{s}')
            # ankle
            bm = bmesh.new()
            cgeo.uv_sphere(bm, 0.62, segs=16, rings=8, M=_T((sx * 2.3, 0.1, 1.72)))
            self._obj(bm, f'ankle.{s}', [ch], f'foot.{s}')

    def _build_lights(self):
        # the seam glow leaks light out of the box (no shadow: it sits inside the frame)
        ld = bpy.data.lights.new(f'{self.name}.seamlight', 'POINT')
        ld.energy = 0.0
        ld.shadow_soft_size = 2.0
        ld.color = srgb('#FF8A3A')[:3]
        try:
            ld.use_shadow = False
        except Exception:
            pass
        lo = bpy.data.objects.new(f'{self.name}.seamlight', ld)
        self.coll.objects.link(lo)
        lo.matrix_basis = _T((0, 0, 14.4))
        bone_parent(lo, self.rig, 'chest')
        self.l_seam = ld
        ld = bpy.data.lights.new(f'{self.name}.reactorlight', 'POINT')
        ld.energy = 0.0
        ld.shadow_soft_size = 0.6
        ld.color = srgb('#FFB060')[:3]
        lo = bpy.data.objects.new(f'{self.name}.reactorlight', ld)
        self.coll.objects.link(lo)
        lo.matrix_basis = _T((0, -2.3, 13.45))
        bone_parent(lo, self.rig, 'chest')
        self.l_reactor = ld
        self.l_eye = None
        if self.glow_light:
            ld = bpy.data.lights.new(f'{self.name}.eyelight', 'SPOT')
            ld.energy = 0.0
            ld.shadow_soft_size = 0.8
            ld.spot_size = math.radians(120)
            ld.spot_blend = 1.0
            lo = bpy.data.objects.new(f'{self.name}.eyelight', ld)
            self.coll.objects.link(lo)
            lo.matrix_basis = _T((0, -2.4, 18.1)) @ _R(-90, 0, 0)
            bone_parent(lo, self.rig, 'p.face')
            self.l_eye = ld

    # ============================================================================================ API
    def transform(self, t0: float = 110.18, hits=None):
        """Key the transformation from Clawd to robot starting at t0; hits = the six lock times [feet, rise
        (legs locked), arms (shoulders locked), chest (reactor), head, final lock/stomp]. Needs mode='clawd'."""
        self.xf = schedule(t0, hits)
        W = self.xf
        # seam glow and the unlock pop
        a, b, _ = W['unlock']
        self.T['seams'].add(a - 0.02, W['_hits'][5] + 0.4, lambda x: (
            4.0 * bump(x, a - 0.02, a + 0.03, a + 0.5) + 0.7 * smoothstep(a, a + 0.08, x) *
            (1 - smoothstep(W['head'][1] - 0.3, W['_hits'][5], x))))
        self.T['pop'].add(a, W['_hits'][5] + 1.0, lambda x: 0.45 * bump(x, a, a + 0.05, a + 0.32) +
                          0.16 * smoothstep(a, a + 0.06, x))
        # every lock flashes the panel lines
        for hk in W['_hits'][:5]:
            self.T['seams'].add(hk - 0.02, hk + 0.3, lambda x, hk=hk: 2.2 * bump(x, hk - 0.02, hk + 0.02, hk + 0.28))
        # reactor ignites, eyes light when the head locks
        ra, rb, _ = W['reactor']
        self.T['reactor'].add(ra, rb + 1.5, lambda x: 22.0 * bump(x, ra, rb, rb + 0.5))
        self.T['reactor'].set(rb, 6.0, rb - ra, 'out')
        ha, hb, _ = W['head']
        self.T['eyes.glow'].set(hb, 7.0, 0.05, 'out')
        self.T['eyes.glow'].add(hb, hb + 0.6, lambda x: 12.0 * bump(x, hb, hb + 0.04, hb + 0.5))
        # lock events (sparks and camera cues)
        h = W['_hits']
        self.hits = [(h[0], 'foot.L'), (h[0], 'foot.R'), (h[1], 'knee.L'), (h[1], 'knee.R'), (h[1], 'hip'),
                     (h[2], 'shoulder.L'), (h[2], 'shoulder.R'), (W['armdrop'][1], 'elbow.L'),
                     (W['armdrop'][1], 'elbow.R'), (h[3], 'reactor'), (h[4], 'neck'), (h[5], 'hip'),
                     (h[5], 'foot.L'), (h[5], 'foot.R')]
        # the final stomp: the whole robot settles its weight
        la = h[5]
        self.T['pelvis.loc'].add(la - 0.1, la + 0.5, lambda x: (0.0, 0.0, 0.35 * bump(x, la - 0.1, la - 0.02, la + 0.02)
                                                                 - 0.45 * wobble(x, la, 2.4, 7.0) * (x >= la)))
        for e in (a, *h):
            self._ev(e)
        self._baked = False
        return self

    def seam_flash(self, t: float, strength: float = 3.0, jolt: float = 0.25):
        """The stutter: the panel lines flash, the panels chatter out a hair and the box jolts."""
        self.T['seams'].add(t - 0.02, t + 0.35, lambda x: strength * bump(x, t - 0.02, t + 0.02, t + 0.3))
        self.T['pop'].add(t - 0.02, t + 0.3, lambda x: 0.12 * bump(x, t - 0.02, t + 0.02, t + 0.22))
        self.T['pelvis.loc'].add(t - 0.02, t + 0.4, lambda x: (0.0, 0.0, jolt * bump(x, t - 0.02, t + 0.03, t + 0.12)
                                                               - 0.4 * jolt * wobble(x, t + 0.12, 5.0, 12.0)
                                                               * (x >= t + 0.12)))
        self._ev(t)
        return self

    POSES = {
        'stand': {},
        'hero': dict(chest=(-6, 0, 0), head=(-8, 0, 0), arms=((14, -6, 0), (14, -6, 0)), elbows=(12, 12),
                     thighs=((0, 4, 0), (0, 4, 0))),
        'fists': dict(arms=((22, 18, -20), (22, 18, -20)), elbows=(95, 95), hands=((0, 0, 0), (0, 0, 0))),
        'flex': dict(chest=(-4, 0, 0), arms=((82, 0, 0), (82, 0, 0)), elbows=(118, 118)),
        'fold': dict(head=(-6, 0, 0), arms=((10, 34, -72), (14, 30, -72)), elbows=(102, 104),   # 112 put the L fist in the chest
                     hands=((0, 0, 0), (0, 0, 0))),
        'point': dict(chest=(0, 0, -10), arms=((8, 4, 0), (6, 86, 0)), elbows=(10, 4)),
        'crouch': dict(pelvis=(0, 0.6, -1.6), chest=(14, 0, 0), head=(-10, 0, 0),
                       thighs=((-30, 6, 0), (-30, 6, 0)), knees=(52, 52),
                       arms=((20, 20, 0), (20, 20, 0)), elbows=(50, 50)),
        'punch_R': dict(chest=(4, 0, 18), arms=((12, 14, -10), (6, 88, 0)), elbows=(96, 2)),
        'punch_L': dict(chest=(4, 0, -18), arms=((6, 88, 0), (12, 14, -10)), elbows=(2, 96)),
    }

    def pose(self, t: float, name: str, *, dur: float = 0.25, ease: str = 'inout'):
        """Arrive at a named pose by t: 'stand', 'hero', 'fists', 'flex', 'fold' (arms folded), 'point' (right arm
        out), 'crouch', 'punch_R', 'punch_L'. Channels a pose doesn't name return to rest."""
        P = self.POSES[name]
        rest3 = (0.0, 0.0, 0.0)
        tri = lambda v: tuple(float(x) for x in v)
        self.T['pelvis.loc'].set(t, tri(P.get('pelvis', rest3)), dur, ease)
        self.T['pelvis.rot'].set(t, rest3, dur, ease)
        self.T['chest.rot'].set(t, tri(P.get('chest', rest3)), dur, ease)
        self.T['head.rot'].set(t, tri(P.get('head', rest3)), dur, ease)
        for i, s in enumerate('LR'):
            self.T[f'arm.{s}'].set(t, tri(P.get('arms', (rest3, rest3))[i]), dur, ease)
            self.T[f'elbow.{s}'].set(t, float(P.get('elbows', (0, 0))[i]), dur, ease)
            self.T[f'hand.{s}'].set(t, tri(P.get('hands', (rest3, rest3))[i]), dur, ease)
            self.T[f'thigh.{s}'].set(t, tri(P.get('thighs', (rest3, rest3))[i]), dur, ease)
            self.T[f'knee.{s}'].set(t, float(P.get('knees', (0, 0))[i]), dur, ease)
            self.T[f'foot.{s}'].set(t, tri(P.get('feet', (rest3, rest3))[i]), dur, ease)
        self._ev(t)
        return self

    def arm(self, t: float, side: str, raise_=0.0, swing=0.0, twist=0.0, elbow=None, *, dur=0.2, ease='inout'):
        """One arm by t: raise (sideways), swing (forward), twist (inward) degrees; elbow bend."""
        self.T[f'arm.{side}'].set(t, (float(raise_), float(swing), float(twist)), dur, ease)
        if elbow is not None:
            self.T[f'elbow.{side}'].set(t, float(elbow), dur, ease)
        self._ev(t)
        return self

    def head(self, t: float, nod: float = 0.0, tilt: float = 0.0, turn: float = 0.0, *, dur=0.2, ease='inout'):
        """Head by t: nod (down +), tilt (to its left +), turn (to its left +) degrees."""
        self.T['head.rot'].set(t, (float(nod), float(tilt), float(turn)), dur, ease)
        self._ev(t)
        return self

    def look(self, t: float, target=None, *, dur: float = 0.25):
        """Turn the head toward a point / object / character by t (within +-70 deg); None recentres."""
        if target is None:
            return self.head(t, dur=dur)
        tp = _point(target, t)
        e = self.anchor(t - dur, 'eyes')
        d = tp - e
        yaw = self.T['root.yaw'].at(t - dur)
        want = unwrap(math.degrees(math.atan2(d.x, -d.y)), yaw)
        turn = max(-70.0, min(70.0, want - yaw))
        nod = -math.degrees(math.atan2(d.z, max(1e-6, d.xy.length)))
        return self.head(t, max(-30.0, min(35.0, nod)), 0.0, -turn, dur=dur)

    def shake_head(self, t: float, n: int = 3, amount: float = 24.0, every: float = 0.24):
        """No, no, no: n head shakes starting at t (an overlay on the head's turn)."""
        t1 = t + n * every
        self.T['head.rot'].add(t, t1 + 0.05, lambda x: (0.0, 0.0, amount * math.sin(2 * math.pi * (x - t) / every)
                                                         * min(1.0, (t1 - x) / 0.12, (x - t) / 0.05 + 0.2)))
        self._ev(t)
        self._ev(t1)
        return self

    def nod(self, t: float, n: int = 2, amount: float = 14.0, every: float = 0.3):
        t1 = t + n * every
        self.T['head.rot'].add(t, t1, lambda x: (amount * math.sin(math.pi * ((x - t) / every) % math.pi) *
                                                  (1 if int((x - t) / every) % 1 == 0 else 1), 0.0, 0.0))
        self._ev(t)
        return self

    def punch(self, t: float, side: str = 'R', *, hold: float = 0.2):
        """A straight punch landing on t (wind-up before, recoil after)."""
        other = 'L' if side == 'R' else 'R'
        A, E = self.T[f'arm.{side}'], self.T[f'elbow.{side}']
        a0, e0 = A.at(t - 0.3), E.at(t - 0.3)
        A.set(t - 0.12, (12.0, -20.0, -10.0), 0.14, 'out')
        E.set(t - 0.12, 110.0, 0.14, 'out')
        A.set(t, (6.0, 88.0, 0.0), 0.12, 'in')
        E.set(t, 2.0, 0.12, 'in')
        A.set(t + hold + 0.25, a0, 0.25)
        E.set(t + hold + 0.25, e0, 0.25)
        sg = 1 if side == 'R' else -1
        self.T['chest.rot'].add(t - 0.3, t + hold + 0.35, lambda x: (
            6.0 * bump(x, t - 0.12, t, t + hold + 0.3), 0.0,
            sg * (-16 * bump(x, t - 0.3, t - 0.12, t) + 22 * bump(x, t - 0.12, t, t + hold + 0.3))))
        self._ev(t)
        return self

    def stomp(self, t: float, side: str = 'R', height: float = 2.2):
        """Lift a foot and slam it down on t (with a body dip)."""
        a = t - 0.3
        sg = 1 if side == 'L' else -1
        self.T[f'thigh.{side}'].add(a, t + 0.05, lambda x: (-38.0 * bump(x, a, t - 0.12, t), 0.0, 0.0))
        self.T[f'knee.{side}'].add(a, t + 0.05, lambda x: 60.0 * bump(x, a, t - 0.12, t))
        self.T['pelvis.loc'].add(a, t + 0.5, lambda x: (sg * -0.3 * bump(x, a, t - 0.12, t), 0.0,
                                                        -0.5 * wobble(x, t, 2.5, 7.0) * (x >= t)))
        self._ev(t)
        return self

    def eyes(self, t: float, *, glow: float | None = None, color=None, narrow: float | None = None,
             angry: float | None = None, side: str | None = None, dur: float = 0.1):
        """Eyes by t: glow (emission strength, 0 off, 5-10 lit), color, narrow (0 open .. 1 slit), angry (tilt deg)."""
        if glow is not None:
            self.T['eyes.glow'].set(t, float(glow), dur, 'out')
        if color is not None:
            self.T['eyes.col'].set(t, _lin(color), dur)
        for s in ([side] if side else 'LR'):
            cur = self.T[f'eye.{s}'].at(t - dur)
            nv = (cur[0] if narrow is None else float(narrow), cur[1] if angry is None else float(angry), cur[2])
            self.T[f'eye.{s}'].set(t, nv, dur, 'out')
        self._ev(t)
        return self

    def blink(self, t: float, dur: float = 0.16):
        for s in 'LR':
            self.T[f'eye.{s}'].add(t, t + dur, lambda x, t=t: (0.0, 0.0, 0.95 * bump(x, t, t + dur * 0.45, t + dur)))
        self._ev(t)
        return self

    def reactor(self, t: float, strength: float = 6.0, dur: float = 0.1, pulse: float = 0.0):
        """Reactor emission by t; pulse > 0 adds a flash of that strength at t."""
        self.T['reactor'].set(t, float(strength), dur, 'out')
        if pulse:
            self.T['reactor'].add(t, t + 0.5, lambda x: pulse * bump(x, t, t + 0.03, t + 0.45))
        self._ev(t)
        return self

    def wings(self, t: float, angle: float = 25.0, dur: float = 0.2):
        for s in 'LR':
            self.T[f'wing.{s}'].set(t, float(angle), dur, 'out')
        self._ev(t)
        return self

    # ============================================================================================ solve
    def _w(self, key, t, lag: float = 0.0) -> float:
        """Transformation progress 0 (Clawd) .. 1 (robot) of a window at t (lag shifts the window later)."""
        if self.mode0 == 'robot':
            return 1.0
        if self.xf is None:
            return 0.0
        a, b, e = self.xf[key]
        a, b = a + lag, b + lag
        if t <= a:
            return 0.0
        if t >= b:
            return 1.0
        return EASES[e]((t - a) / (b - a))

    def _in_window(self, key, t, pad=0.12) -> bool:
        if self.mode0 == 'robot' or self.xf is None:
            return False
        a, b, _ = self.xf[key]
        return a - 0.05 <= t <= b + pad

    def _local_pose(self, t) -> dict:
        """Basis matrices of the skeleton bones from the tracks (robot mode), gait included."""
        T = self.T
        B = {}
        rl, yaw, sc = T['root.loc'].at(t), T['root.yaw'].at(t), T['root.scale'].at(t)
        B['root'] = _T(rl) @ Matrix.Rotation(math.radians(yaw), 4, 'Z') @ Matrix.Scale(sc, 4)
        ph, amp, vx, vy, w = self.gait(t)
        S = math.sin(2 * math.pi * ph)
        C = math.cos(2 * math.pi * ph)
        pl, pr = T['pelvis.loc'].at(t), T['pelvis.rot'].at(t)
        bob = 0.45 * amp * abs(S)
        B['pelvis'] = _T((pl[0], pl[1], pl[2] + bob - 0.35 * amp)) @ _R(pr[0], pr[1] + 3.0 * amp * S, pr[2])
        B['abdomen'] = Matrix.Identity(4)
        cr = T['chest.rot'].at(t)
        B['chest'] = _R(cr[0] + 4.0 * amp, cr[1] - 2.0 * amp * S, cr[2] - 6.0 * amp * S)
        B['neck'] = Matrix.Identity(4)
        hr = T['head.rot'].at(t)
        B['head'] = Matrix.Rotation(math.radians(hr[2]), 4, 'Z') @ Matrix.Rotation(math.radians(hr[0]), 4, 'X') @ \
            Matrix.Rotation(math.radians(-hr[1]), 4, 'Y')
        for s, sx in (('L', 1), ('R', -1)):
            B[f'wing.{s}'] = Matrix.Rotation(math.radians(sx * T[f'wing.{s}'].at(t)), 4, 'Y')
            B[f'shoulder.{s}'] = Matrix.Identity(4)
            r_, sw, tw = T[f'arm.{s}'].at(t)
            sw += -sx * 16.0 * amp * S   # arm swing opposite the legs
            B[f'upper_arm.{s}'] = Matrix.Rotation(math.radians(-sx * r_), 4, 'Y') @ \
                Matrix.Rotation(math.radians(-sw), 4, 'X') @ Matrix.Rotation(math.radians(sx * tw), 4, 'Z')
            el = T[f'elbow.{s}'].at(t) + 14.0 * amp
            B[f'forearm.{s}'] = Matrix.Rotation(math.radians(-el), 4, 'X')
            hd = T[f'hand.{s}'].at(t)
            B[f'hand.{s}'] = _R(-hd[0], -sx * hd[1], sx * hd[2])
            th = T[f'thigh.{s}'].at(t)
            swing = th[0] - sx * 24.0 * amp * S
            B[f'thigh.{s}'] = Matrix.Rotation(math.radians(sx * th[1]), 4, 'Y') @ \
                Matrix.Rotation(math.radians(swing), 4, 'X') @ Matrix.Rotation(math.radians(sx * th[2]), 4, 'Z')
            kn = T[f'knee.{s}'].at(t) + 40.0 * amp * max(0.0, sx * C)
            B[f'shin.{s}'] = Matrix.Rotation(math.radians(kn), 4, 'X')
            ft = T[f'foot.{s}'].at(t)
            B[f'foot.{s}'] = _R(ft[0] - (swing + kn), ft[1], ft[2])      # feet stay level
        return B

    def _fk(self, B, t) -> dict:
        """Armature-space pose matrices of the skeleton, with the Clawd -> robot blend applied."""
        P = {}
        clawd_ok = self.mode0 == 'clawd'
        for n, h, par in SK:
            b = B.get(n, Matrix.Identity(4))
            if clawd_ok and (n in CLAWD_SK or n.startswith(('thigh', 'shin'))):
                if n in CLAWD_SK:
                    w = self._w(SK_WINDOW[n], t, LAG if n.endswith('.R') else 0.0)
                    cb = CLAWD_SK[n]
                    if n == 'pelvis':   # track offsets (jolts) ride on top of the blend
                        b = b @ _blend(cb, Matrix.Identity(4), w)
                    else:
                        b = _blend(cb, b, w)
                else:
                    # telescoping legs: feet stay planted while the pelvis rises
                    w = self._w('rise', t)
                    o = 0.5 * PELVIS_DROP * (1.0 - w)
                    b = _T((0, 0, o)) @ b
            if par is None:
                P[n] = b
            else:
                P[n] = P[par] @ _T(SK_HEAD[n] - SK_HEAD[par]) @ b
        return P

    def _clawd_ref(self):
        """Pose matrices of the hold bones in the pure Clawd pose with the root at the origin (cached)."""
        if getattr(self, '_cref', None) is None:
            B = {n: Matrix.Identity(4) for n, _, _ in SK}
            P = {}
            for n, h, par in SK:
                b = B[n]
                if n in CLAWD_SK:
                    b = CLAWD_SK[n]
                elif n.startswith(('thigh', 'shin')):
                    b = _T((0, 0, 0.5 * PELVIS_DROP))
                P[n] = b if par is None else P[par] @ _T(SK_HEAD[n] - SK_HEAD[par]) @ b
            self._cref = P
        return self._cref

    def _world(self, t) -> dict:
        """Pose matrices (armature space) of every bone at t."""
        B = self._local_pose(t)
        P = self._fk(B, t)
        pop = self.T['pop'].at(t)
        cref = self._clawd_ref()
        # panels
        for name, (par, ns, us, ct, nt, ut, hold, win, popk) in PANELS.items():
            P[f'p.{name}'] = self._panel_pose(name, par, hold, win, pop * popk, P, cref, t)
        for i in range(8):
            s = 'L' if LEG_XY[i][0] > 0 else 'R'
            P[f'p.toe{i}'] = self._panel_pose(f'toe{i}', f'foot.{s}', 'root', 'toes', 0.0, P, cref, t)
        for s in 'LR':
            P[f'p.fist.{s}'] = self._panel_pose(f'fist.{s}', f'hand.{s}', 'chest', 'fist', pop * 0.6, P, cref, t)
            ev = self.T[f'eye.{s}'].at(t)
            head = self.rest[f'eye.{s}']
            par = self.rest['p.face']
            k = max(0.04, 1.0 - 0.85 * min(1.0, max(0.0, ev[0])) - 0.95 * min(1.0, max(0.0, ev[2])))
            sx = 1 if s == 'L' else -1
            b = Matrix.Rotation(math.radians(sx * ev[1]), 4, 'Y') @ Matrix.Diagonal((1.0, 1.0, k, 1.0))
            P[f'eye.{s}'] = P['p.face'] @ _T(head - par) @ b
        return P

    def _panel_pose(self, name, par, hold, win, pop, P, cref, t):
        rest_p = _T(self.rest[f'p.{name}'])
        rest_par = _T(self.rest[par])
        w_end = P[par] @ rest_par.inverted()                         # robot-mode placement, riding its parent
        if self.mode0 == 'robot':
            return w_end @ rest_p
        C = self.C[name]
        n = self.n_clawd.get(name, Vector((0, 0, 0)))
        w_start = P[hold] @ cref[hold].inverted() @ _T(n * pop) @ C  # Clawd placement, riding the hold bone
        lag = LAG if name.endswith('.R') or (name.startswith('toe') and LEG_XY[int(name[3:])][0] < 0) else 0.0
        u = self._w(win, t, lag)
        if u <= 0.0:
            return w_start @ rest_p
        if t >= self.xf[win][1] + lag:
            return w_end @ rest_p
        c = self.cent[name]
        ex = PANEL_EXTRA.get(name, {})
        W = _blend_about(w_start, w_end, u, c)
        s = math.sin(math.pi * min(1.0, max(0.0, u)))
        if 'spin' in ex:
            ax, deg = ex['spin']
            a0, b0 = self.xf[win][0] + lag, self.xf[win][1] + lag
            k = EASE['inout'](min(1.0, max(0.0, (t - a0) / (b0 - a0))))
            W = W @ _T(c) @ Matrix.Rotation(math.radians(deg * k), 4, Vector(ax)) @ _T(-c)
        if 'hinge' in ex and s > 0:
            piv, ax, ang = ex['hinge']
            H = _T(piv) @ Matrix.Rotation(math.radians(ang * s), 4, Vector(ax)) @ _T(-Vector(piv))
            W = W @ H
        if 'lift' in ex and s > 0:
            root_rot = P['root'].to_3x3()
            W = _T(root_rot @ Vector(ex['lift']) * s) @ W
        return W @ rest_p

    def anchor(self, t: float, name: str = 'eyes') -> Vector:
        """World position at song time t (from the tracks): 'eyes', 'face', 'head', 'chest', 'reactor', 'hip',
        'neck', 'hand.L/R', 'fist.L/R', 'elbow.L/R', 'shoulder.L/R', 'knee.L/R', 'foot.L/R', 'root', 'top'."""
        P = self._world(t)
        mw = self.rig.matrix_world
        if name in ('eyes', 'face'):
            return mw @ (P['p.face'] @ Vector((0, -0.15, -0.1)))
        if name == 'reactor':
            return mw @ (P['chest'] @ (Vector((0, -1.5, 13.45)) - self.rest['chest']))
        if name == 'hip':
            return mw @ P['pelvis'].translation
        if name == 'top':
            return mw @ (P['p.crest'] @ Vector((0, 0, 1.2)))
        if name.startswith('knee'):
            return mw @ P[f'shin.{name[-1]}'].translation
        if name.startswith('elbow'):
            return mw @ P[f'forearm.{name[-1]}'].translation
        if name.startswith('fist'):
            return mw @ P[f'p.fist.{name[-1]}'].translation
        if name.startswith('foot'):
            return mw @ (P[f'foot.{name[-1]}'] @ Vector((0, 0, -1.2)))
        if name in P:
            return mw @ P[name].translation
        raise KeyError(name)

    # ============================================================================================ bake
    def _targets(self):
        R = self.rig
        tg = []   # (Target, bone or None)
        for n in self.order:
            is_sk = n in SK_HEAD
            jl, jr = (0.012, math.radians(0.35)) if is_sk and n != 'root' else (0.0, 0.0)
            for i in range(3):
                tg.append((Target(R, pb(n, 'location'), i, jl), n))
            for i in range(3):
                tg.append((Target(R, pb(n, 'rotation_euler'), i, jr), n))
            for i in range(3):
                tg.append((Target(R, pb(n, 'scale'), i, 0.0), n))
        for key in ('inner', 'rim', 'accent'):
            tg.append((Target(self.M[key].node_tree, 'nodes["glow"].outputs[0].default_value', -1, 0.0), None))
        tg.append((Target(self.M['reactor'].node_tree, 'nodes["glow"].outputs[0].default_value', -1, 0.0), None))
        tg.append((Target(self.M['reactorGlass'].node_tree, 'nodes["glow"].outputs[0].default_value', -1, 0.0), None))
        tg.append((Target(self.M['eye'].node_tree, 'nodes["glow"].outputs[0].default_value', -1, 0.0), None))
        for i in range(3):
            tg.append((Target(self.M['eye'].node_tree, 'nodes["glowcol"].outputs[0].default_value', i, 0.0), None))
        tg.append((Target(self.l_seam, 'energy', -1, 0.0), None))
        tg.append((Target(self.l_reactor, 'energy', -1, 0.0), None))
        if self.l_eye is not None:
            tg.append((Target(self.l_eye, 'energy', -1, 0.0), None))
            for i in range(3):
                tg.append((Target(self.l_eye, 'color', i, 0.0), None))
        self._vis_all = self._uses_visible()
        if self._vis_all:
            for ob in self._objs:
                tg.append((Target(ob, 'hide_render', -1, 0.0), None))
                tg.append((Target(ob, 'hide_viewport', -1, 0.0), None))
        return tg

    def _bone_mode(self, n, t) -> str:
        """'twos' for the skeleton and resting panels, 'ones' for panels inside their snap window."""
        if self.mode0 == 'robot' or self.xf is None:
            return self._mode_at(t)
        if n.startswith('p.') or n.startswith('eye.'):
            key = None
            nm = n[2:]
            if nm in PANELS:
                key = PANELS[nm][7]
            elif nm.startswith('toe'):
                key = 'toes'
            elif nm.startswith('fist'):
                key = 'fist'
            elif n.startswith('eye.'):
                key = 'face'
            if key and self._in_window(key, t, 0.25 + LAG):
                return 'ones'
        return self._mode_at(t)

    def _values(self, t_two, t_one, cache):
        def world(t):
            if t not in cache:
                cache[t] = self._world(t)
            return cache[t]
        W2, W1 = world(t_two), world(t_one)
        out = []
        chosen = {}
        for n in self.order:
            m = self._bone_mode(n, t_one)
            Pn = W1[n] if m == 'ones' else W2[n]
            chosen[n] = Pn
            par = self.parent[n]
            if par is None:
                basis = _T(-self.rest[n]) @ Pn
            else:
                basis = _T(self.rest[n] - self.rest[par]).inverted() @ chosen[par].inverted() @ Pn
            loc, rot, sc = basis.decompose()
            prev_e = self._eprev.get(n) if tm.SMOOTH and getattr(self, '_eprev', None) is not None else None
            e = rot.to_euler('XYZ', prev_e) if prev_e is not None else rot.to_euler('XYZ')
            if tm.SMOOTH and getattr(self, '_eprev', None) is not None:
                self._eprev[n] = e                   # continuous Eulers between output frames (LINEAR keys)
            out.append((n, (loc.x, loc.y, loc.z, e.x, e.y, e.z, sc.x, sc.y, sc.z)))
        return out

    def _scalar(self, t):
        T = self.T
        seams = max(0.0, T['seams'].at(t))
        vals = [seams * 1.2, seams * 2.0, 1.2 * max(0.0, T['reactor'].at(t)) / 6.0]
        r = max(0.0, T['reactor'].at(t))
        vals += [r, r * 0.35]
        g = max(0.0, T['eyes.glow'].at(t))
        col = T['eyes.col'].at(t)
        vals += [g, *col]
        shown = self._shown(t)
        vals.append(900.0 * seams * (1.0 if shown else 0.0))
        vals.append(160.0 * r * (1.0 if shown else 0.0))
        if self.l_eye is not None:
            vals.append(70.0 * g * (1.0 if shown else 0.0))
            vals += col
        if self._vis_all:
            vals += [0.0 if shown else 1.0] * (2 * len(self._objs))
        return vals

    def bake(self, f0=None, f1=None):
        sc = bpy.context.scene
        f0 = sc.frame_start - 2 if f0 is None else f0
        f1 = sc.frame_end + 2 if f1 is None else f1
        self._prepare_gait(f0 / FPS - 0.6, f1 / FPS + 0.6)
        self._cref = None
        tg = self._targets()
        bone_t = [x for x in tg if x[1] is not None]
        other_t = [x for x in tg if x[1] is None]
        series = [[] for _ in tg]
        prev = [None] * len(tg)
        cache = {}
        if tm.SMOOTH:
            # built for 60 fps (the production render): sample every output frame (Puppet._grid: LINEAR keys, snaps
            # held and jumped between exposures); visibility switches at the cut-aligned frame (tm.switch_frame)
            self._eprev = {}
            for fk, t, ip in self._grid(f0, f1):
                vals = self._values(t, t, cache)
                flat = [v for _, vs in vals for v in vs] + self._scalar(t)
                for i, v in enumerate(flat):
                    series[i].append((fk, v, 0 if tg[i][0].step else ip))
                if len(cache) > 8:
                    cache.clear()
            for i, (tgt, _) in enumerate(tg):
                if tgt.step:
                    moved = {}
                    for fk, v, ip in series[i]:
                        moved[tm.switch_frame(fk)] = (v, 0)
                    series[i] = [(fk, v, ip) for fk, (v, ip) in sorted(moved.items())]
            for (tgt, _), pts in zip(tg, series):
                _write(tgt, pts, self.name)
            self._baked = True
            return self
        for f in range(f0, f1 + 1):
            t_one = f / FPS
            fe = f - (f % 2)
            t_two = (fe + 1) / FPS if self._mode_at(t_one) == 'twos' else t_one
            vals = self._values(t_two, t_one, cache)
            flat = [v for _, vs in vals for v in vs]
            flat += self._scalar(t_one)
            for i, v in enumerate(flat):
                tgt = tg[i][0]
                amp = tgt.jit
                if prev[i] is not None and abs(v - prev[i][0]) < 1e-9:
                    vj = prev[i][1]                  # same pose as the last frame (twos): same jitter
                elif amp and prev[i] is not None and abs(v - prev[i][0]) > 1e-4:
                    vj = v + amp * (2 * hash01(self.seed, i, f) - 1)
                else:
                    vj = v
                prev[i] = (v, vj)
                series[i].append((f - 0.5, vj))
            if len(cache) > 8:
                cache.clear()
        for (tgt, _), pts in zip(tg, series):
            _write(tgt, pts, self.name)
        self._baked = True
        return self


# ------------------------------------------------------------------------------------------------ maths helpers


def _blend(A: Matrix, B: Matrix, u: float) -> Matrix:
    """Blend two transforms (translation lerp, rotation slerp; u may overshoot past 1)."""
    la, ra, sa = A.decompose()
    lb, rb, sb = B.decompose()
    loc = la.lerp(lb, u) if 0 <= u <= 1 else la + (lb - la) * u
    rot = _slerp(ra, rb, u)
    scl = sa + (sb - sa) * u
    return Matrix.LocRotScale(loc, rot, scl)


def _slerp(qa: Quaternion, qb: Quaternion, u: float) -> Quaternion:
    """Rotation from qa toward qb by fraction u (u may overshoot past 1), about the world axis of the difference."""
    dw = qb @ qa.inverted()
    ax, ang = dw.to_axis_angle()
    if ang > math.pi:
        ang -= 2 * math.pi
    return Quaternion(ax, ang * u) @ qa


def _blend_about(A: Matrix, B: Matrix, u: float, c: Vector) -> Matrix:
    """Blend two rigid placements of a part about its own centre c (robot-rest coords), so it turns in place
    instead of swinging around the origin."""
    ca, cb = A @ c, B @ c
    rot = _slerp(A.to_quaternion(), B.to_quaternion(), u)
    pos = ca + (cb - ca) * u
    return _T(pos) @ rot.to_matrix().to_4x4() @ _T(-c)


def _torus(bm, R, r, M, segs=40, csegs=10, mat=0):
    verts = []
    ring = []
    for i in range(segs):
        a = 2 * math.pi * i / segs
        row = []
        for j in range(csegs):
            b = 2 * math.pi * j / csegs
            p = Vector(((R + r * math.cos(b)) * math.cos(a), (R + r * math.cos(b)) * math.sin(a), r * math.sin(b)))
            v = bm.verts.new(M @ p)
            row.append(v)
        ring.append(row)
    for i in range(segs):
        for j in range(csegs):
            a, b = ring[i][j], ring[(i + 1) % segs][j]
            c, d = ring[(i + 1) % segs][(j + 1) % csegs], ring[i][(j + 1) % csegs]
            f = bm.faces.new((a, b, c, d))
            f.material_index = mat
    return ring


def _disc(bm, r, M, segs=32, mat=0):
    vs = [bm.verts.new(M @ Vector((r * math.cos(2 * math.pi * i / segs), r * math.sin(2 * math.pi * i / segs), 0)))
          for i in range(segs)]
    f = bm.faces.new(vs)
    f.material_index = mat
    return f


def _write(tgt: Target, pts, owner_name: str):
    """CONSTANT keys (f - 0.5, value), deduplicated; a static channel just gets its value. Points may carry a third
    field, the interpolation (0 CONSTANT, 1 LINEAR: the 60 fps build); LINEAR points are all kept."""
    out = []
    for p in pts:
        fk, v = p[0], p[1]
        ip = p[2] if len(p) > 2 else 0
        if out and ip == 0 and out[-1][2] == 0 and abs(out[-1][1] - v) < 1e-6:
            continue
        out.append((fk, v, ip))
    if out and all(abs(o[1] - out[0][1]) < 1e-6 for o in out):
        out = out[:1]
    idb = tgt.idb
    idx = max(tgt.index, 0)
    ad = idb.animation_data
    existing = None
    if ad and ad.action:
        for layer in ad.action.layers:
            for strip in layer.strips:
                cb = strip.channelbag(ad.action_slot) if ad.action_slot else None
                if cb:
                    existing = cb.fcurves.find(tgt.path, index=idx)
                    if existing and len(out) <= 1:
                        cb.fcurves.remove(existing)
                        existing = None
    if len(out) <= 1:
        head, attr = (tgt.path.rsplit('.', 1) if '.' in tgt.path and not tgt.path.endswith(']') else ('', tgt.path))
        owner = idb.path_resolve(head) if head else idb
        v = out[0][1] if out else 0.0
        if tgt.index >= 0:
            getattr(owner, attr)[tgt.index] = v
        else:
            cur = getattr(owner, attr)
            setattr(owner, attr, bool(v > 0.5) if isinstance(cur, bool) else v)
        return
    if ad is None:
        ad = idb.animation_data_create()
    if ad.action is None:
        ad.action = bpy.data.actions.new(f'{owner_name}:{idb.name}')
    fc = existing or ad.action.fcurve_ensure_for_datablock(idb, tgt.path, index=idx)
    kp = fc.keyframe_points
    kp.clear()
    kp.add(len(out))
    kp.foreach_set('co', [c for fk, v, _ in out for c in (fk, v)])
    kp.foreach_set('interpolation', [ip for _, _, ip in out])
    fc.update()


# ------------------------------------------------------------------------------------------------ sparks

_SPARK_MAT = {}


def spark_material():
    m = _SPARK_MAT.get('m')
    if m is not None:
        try:
            if m.name in bpy.data.materials:
                return m
        except ReferenceError:
            pass
    m = looks.emitter('robot.spark', '#FFC26A', 40.0)
    _SPARK_MAT['m'] = m
    return m


def sparks(coll, t: float, pos, *, n: int = 12, seed: int = 1, speed=(25.0, 70.0), up: float = 0.6,
           life=(0.18, 0.45), size: float = 0.12, direction=None, spread: float = 1.0, gravity: float = 981.0):
    """A burst of welding sparks at world point pos, song time t: n small glowing beads flying out on ballistic
    arcs (keyed every frame, LINEAR, so motion blur draws them as streaks), shrinking out over their life.
    direction: a bias vector (sparks spray around it with `spread` 0..1). Deterministic (seeded)."""
    m = spark_material()
    me = bpy.data.meshes.get('robot.spark.mesh')
    if me is None:
        bm = bmesh.new()
        bmesh.ops.create_icosphere(bm, subdivisions=1, radius=1.0)
        me = bpy.data.meshes.new('robot.spark.mesh')
        bm.to_mesh(me)
        bm.free()
        me.materials.append(m)
    p0 = Vector(pos)
    obs = []
    for i in range(n):
        h = lambda k: hash01(seed, i, k)
        th = 2 * math.pi * h(1)
        cz = up + (1 - up) * (2 * h(2) - 1)
        cz = max(-1.0, min(1.0, cz))
        rr = math.sqrt(max(0.0, 1 - cz * cz))
        d = Vector((rr * math.cos(th), rr * math.sin(th), cz))
        if direction is not None:
            d = (Vector(direction).normalized() * (1 - spread) + d * spread).normalized()
        v = d * (speed[0] + (speed[1] - speed[0]) * h(3))
        lf = life[0] + (life[1] - life[0]) * h(4)
        ob = bpy.data.objects.new(f'spark.{t:.3f}.{seed}.{i}', me)
        coll.objects.link(ob)
        t0 = t + 0.02 * h(5)
        f0 = int(math.floor(t0 * FPS))
        f1 = int(math.ceil((t0 + lf) * FPS)) + 1
        for f in range(f0, f1 + 1):
            x = max(0.0, f / FPS - t0)
            p = p0 + v * x + Vector((0, 0, -0.5 * gravity * x * x))
            p.z = max(p.z, 0.05)
            k = max(0.0, 1.0 - x / lf) if f / FPS >= t0 else 0.0
            ob.location = p
            s = size * (0.35 + 0.65 * k) if k > 0 else 0.0
            ob.scale = (s, s, s)
            ob.keyframe_insert('location', frame=f)
            ob.keyframe_insert('scale', frame=f)
        ob.hide_render = True
        ob.keyframe_insert('hide_render', frame=f0 - 1)
        ob.hide_render = False
        ob.keyframe_insert('hide_render', frame=f0)
        ob.hide_render = True
        ob.keyframe_insert('hide_render', frame=f1)
        from pdoom import kit
        for fc in kit.fcurves(ob):
            for kp in fc.keyframe_points:
                kp.interpolation = 'CONSTANT' if fc.data_path == 'hide_render' else 'LINEAR'
        obs.append(ob)
    return obs
