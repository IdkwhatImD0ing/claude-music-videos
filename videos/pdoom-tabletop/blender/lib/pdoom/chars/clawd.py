"""Clawd: the orange soft-touch vinyl toy (and Sydney, his blue jelly twin).

    from pdoom import chars
    c = chars.Clawd(coll, name='clawd', loc=(0, 0, 0), yaw=0)
    c.move(1.0, 2.5, [(10, 0), (14, 6)])      # scuttles along a smooth path, turning to face where it goes
    c.hop(3.0, 2.5); c.chomp(4.1); c.eyes(5.0, 'happy'); c.take(6.2)
    chars.finish()                            # bake (also runs automatically on save / render)

Character space: 1 BU = 1 cm, standing on z = 0 at the origin, FACING -Y (his left is +X). Body 8 x 4.5 x 5 cm on
1.45 cm legs; the top 2.75 cm of the body is the LID (mouth) hinged at the back. All angles in the API are degrees.
See docs/lib/chars.md for the full API.
"""
from __future__ import annotations

import bisect
import math

import bmesh
import bpy
from mathutils import Matrix, Vector

from .. import timing as tm
from ..kit import srgb
from . import geo, looks
from .rig import (EASE, Path, Puppet, Target, _lin, _point, _v3, armature, bone_parent, bump, hash01, pb,
                  smoothstep, unwrap, wobble)

# ------------------------------------------------------------------------------------------------ proportions (cm)

W, D, H = 8.0, 4.5, 5.0
Z0 = 1.3                  # underside of the body
ZC = Z0 + H / 2
TOP = Z0 + H              # 6.3
SEAM = 3.55               # lid / jaw split
R_BODY = 0.66
WALL = 0.42
CAV_LO, CAV_HI = 1.3, 1.45
FACE_Y = -D / 2
EYE_X, EYE_Z = 1.95, 4.88
HINGE = (0.0, D / 2 - 0.2, SEAM)
ARM_X, ARM_Z = 3.8, 3.0
LEG_H = 1.6
LEG_XY = [(x, y) for x in (-2.7, -1.25, 1.25, 2.7) for y in (-1.1, 1.1)]
LEG_GROUP = [(i // 2 + i % 2) % 2 for i in range(8)]   # alternating tetrapod gait
LID_MAX = 72.0            # degrees at lid(1)
PORT = (-2.6, D / 2, 2.2)  # USB-C port on his back-left, where the desk's cable plugs in (sets: clawdPort)

BONES = {
    'root': (0, 0, 0), 'hips': (0, 0, Z0), 'body': (0, 0, Z0), 'lid': HINGE,
    'eye.L': (EYE_X, FACE_Y, EYE_Z), 'eye.R': (-EYE_X, FACE_Y, EYE_Z), 'face': (0, FACE_Y, EYE_Z),
    'hat': (0, 0, TOP), 'mouth': (0, -0.2, SEAM - CAV_LO), 'back': PORT,
    'arm.L': (ARM_X, 0, ARM_Z), 'arm.R': (-ARM_X, 0, ARM_Z),
    'hand.L': (ARM_X + 1.45, 0, ARM_Z), 'hand.R': (-ARM_X - 1.45, 0, ARM_Z),
}
PARENT = {'hips': 'root', 'body': 'hips', 'lid': 'body', 'eye.L': 'lid', 'eye.R': 'lid', 'face': 'lid', 'hat': 'lid',
          'mouth': 'body', 'back': 'body', 'arm.L': 'body', 'arm.R': 'body', 'hand.L': 'arm.L', 'hand.R': 'arm.R'}
for _i, (_x, _y) in enumerate(LEG_XY):
    BONES[f'leg{_i}'] = (_x, _y, Z0 + 0.15)
    PARENT[f'leg{_i}'] = 'hips'

# arm poses: (raise, swing forward, twist) in degrees, per side or one for both
ARM_POSES = {
    'rest': (-14, 4, 0), 'down': (-48, 0, 0), 'out': (0, 0, 0), 'up': (62, 6, 0), 'high': (82, 0, 0),
    'cheer': (70, 22, 0), 'forward': (-4, 74, 0), 'hold': (10, 62, 0), 'hug': (4, 88, 0), 'back': (-24, -42, 0),
    'shrug': (30, -14, 40), 'fold': (-6, 96, 0), 'akimbo': (-38, -30, 0),
    'point': {'L': (-14, 4, 0), 'R': (22, 82, 0)}, 'wave': {'L': (-14, 4, 0), 'R': (72, 12, 0)},
    'think': {'L': (-14, 4, 0), 'R': (38, 70, 0)},
}

EYE_SHAPES = ('open', 'happy', 'angry', 'narrow', 'surprised', 'shut', 'heart', 'sad', 'small', 'x', 'star', 'dizzy')
BLINKABLE = ('open', 'angry', 'narrow', 'surprised', 'sad', 'small')
PROPS = ('crown', 'cat_ears', 'mask', 'party_hat', 'bowtie')

VARIANTS = {
    'vinyl': dict(body='#D97757', legs='#B85F42', mouth='#4A1519', teeth='#F4EEE2', tongue='#D65A6A', eye='#0B0909'),
    'sydney': dict(body='#5AA8FF', legs='#5AA8FF', mouth='#2F6FE0', teeth='#E8F3FF', tongue='#FF7FB0', eye='#0E1C45'),
}


def _T(p):
    return Matrix.Translation(Vector(p))


def _R(ex, ey, ez):
    from mathutils import Euler
    return Euler((math.radians(ex), math.radians(ey), math.radians(ez)), 'XYZ').to_matrix().to_4x4()


# ------------------------------------------------------------------------------------------------ arm clearance
# The stub arms pivot 0.2 cm inside the body's side (x 3.8, the side is at 4.0), so an arm swung forward ('forward',
# 'hold', 'hug', 'fold', 'think', 'point') or raised high ('high', 'cheer') used to sink into the body, up to its whole
# thickness. At bake time the arm now slides out along its shoulder axis, the least it takes, until its outer part
# clears the body; the root stays tucked against the side. Swings/raises past 90 deg (pointing back into the body)
# are capped at 90.

ARM_LEN = (-0.19, 1.43)          # extent of the stub along the arm, from the pivot
ARM_HALF = (0.38, 0.42)          # half thickness (y, z) of the stub
_ARM_SECTION = [(math.cos(a), math.sin(a)) for a in (i * math.pi / 4 for i in range(8))]


def _box_depth(q):
    """How deep a point (character space, lid closed) is inside Clawd's rounded body box (< 0: outside)."""
    hx, hy, hz = W / 2 - R_BODY, D / 2 - R_BODY, H / 2 - R_BODY
    dx, dy, dz = abs(q.x) - hx, abs(q.y) - hy, abs(q.z - ZC) - hz
    outside = math.sqrt(max(dx, 0) ** 2 + max(dy, 0) ** 2 + max(dz, 0) ** 2)
    inside = min(max(dx, dy, dz), 0.0)
    return R_BODY - outside - inside


def arm_clear(side, raise_, swing, twist):
    """(raise, swing, twist, outward offset cm) for an arm pose that keeps the stub out of the body."""
    raise_ = max(-90.0, min(90.0, raise_))
    swing = max(-90.0, min(90.0, swing))
    sx = 1 if side == 'L' else -1
    ex = (math.radians(twist), math.radians(-raise_), math.radians(-swing)) if side == 'L' else         (math.radians(-twist), math.radians(raise_), math.radians(swing))
    from mathutils import Euler
    R = Euler(ex, 'XYZ').to_matrix()
    piv = Vector(BONES[f'arm.{side}'])
    pts = [R @ Vector((sx * s, ARM_HALF[0] * cy, ARM_HALF[1] * cz)) for s in (0.7, 0.95, 1.2, 1.43)
           for cy, cz in _ARM_SECTION]
    dx = 0.0
    for _ in range(8):
        dep = max(_box_depth(piv + Vector((sx * dx, 0.0, 0.0)) + p) for p in pts) - 0.03
        if dep <= 1e-3:
            break
        dx = min(0.9, dx + dep)
    return raise_, swing, twist, dx


class Clawd(Puppet):
    """The vinyl Clawd toy, rigged. See the module doc and docs/lib/chars.md."""

    STRIDE = 2.6
    GAIT_R = 2.9
    GAIT_FULL = 2.2
    LEG_SWING = 26.0
    LEG_LIFT = 0.38

    def __init__(self, coll, name: str = 'clawd', loc=(0, 0, 0), yaw: float = 0.0, scale: float = 1.0, *,
                 variant: str = 'vinyl', seed=None, timing: str = 'twos', blink: bool = True,
                 glow_light: bool = True):
        super().__init__(name, seed, timing)
        self.coll = coll
        self.variant = variant
        self.auto_blink = blink
        self.glow_light = glow_light
        self._eye_objs: dict = {}     # (shape, side) -> object
        self._props: dict = {}        # prop -> [objects]
        self._light = None
        self._mark = None
        self._mats()
        self.rig = self._build_rig()
        self._build_body()
        self._eye_obj('open', 'L')
        self._eye_obj('open', 'R')
        # tracks and their rest values
        self.track('root.loc', _v3(loc))
        self.track('root.yaw', float(yaw))
        self.track('root.scale', float(scale))
        self.track('hips.loc', (0.0, 0.0, 0.0))
        self.track('hips.rot', (0.0, 0.0, 0.0))
        self.track('body.loc', (0.0, 0.0, 0.0))
        self.track('body.rot', (0.0, 0.0, 0.0))
        self.track('body.sq', 0.0)
        self.track('lid', 0.0)
        self.track('eyes.look', (0.0, 0.0))
        for s in 'LR':
            self.track(f'eye.{s}.s', (0.0, 0.0, 0.0))
            self.track(f'arm.{s}', tuple(float(x) for x in ARM_POSES['rest']))
            self.track(f'glow.{s}', 0.0)
            self.disc(f'eyes.{s}', 'open')
        self.track('glow.col', _lin('#FFB24A'))
        for i in range(8):
            self.track(f'leg{i}', (0.0, 0.0, 0.0))
        self.disc('mark', False)
        self._auto_blinks: list = []

    # ============================================================================================ build
    def _mats(self):
        v = VARIANTS[self.variant]
        if self.variant == 'sydney':
            self.m_body = looks.jelly('chars.sydney.jelly', v['body'])
            self.m_legs = self.m_body
            self.m_mouth = looks.jelly('chars.sydney.core', v['mouth'])
            self.m_teeth = looks.gloss('chars.sydney.teeth', v['teeth'], rough=0.15)
            self.m_tongue = looks.satin('chars.sydney.tongue', v['tongue'], rough=0.3)
        else:
            self.m_body = looks.vinyl('chars.clawd.vinyl', v['body'])
            self.m_legs = looks.vinyl('chars.clawd.vinylDark', v['legs'], rough=0.5)
            self.m_mouth = looks.satin('chars.clawd.mouth', v['mouth'], rough=0.5, sss=0.15)
            self.m_teeth = looks.gloss('chars.clawd.teeth', v['teeth'], rough=0.28, coat=0.5, coat_rough=0.1)
            self.m_tongue = looks.satin('chars.clawd.tongue', v['tongue'], rough=0.42, sss=0.3, coat=0.3)
        self.m_eye = {s: looks.glow_eye(f'{self.name}.eye.{s}', v['eye']) for s in 'LR'}
        self.m_white = looks.gloss('chars.white', '#FBFAF6', rough=0.15)
        self.m_heart = looks.gloss('chars.heart', '#FF3D6E', rough=0.12, sss=0.2)
        self.m_gold = looks.gloss('chars.star', '#FFC928', rough=0.15, coat=0.8)
        self.m_port = looks.satin('chars.clawd.port', '#1B1715', rough=0.6)

    def _build_rig(self):
        specs = []
        for n, h in BONES.items():
            s = {'name': n, 'head': h, 'parent': PARENT.get(n)}
            if n.startswith('arm'):
                s['inherit_scale'] = 'AVERAGE'
            specs.append(s)
        return armature(f'{self.name}.rig', self.coll, specs)

    def _part(self, bm, name, mats, bone, *, sharp=36.0, M=None):
        ob = geo.to_object(bm, f'{self.name}.{name}', self.coll, mats, sharp=sharp)
        if M is not None:
            ob.matrix_basis = M
        bone_parent(ob, self.rig, bone)
        return ob

    def _half(self, upper: bool):
        bm = bmesh.new()
        geo.rounded_box(bm, (W, D, H), R_BODY, (0, 0, ZC), seg=5, flat=(4, 3, 3), extra=((), (), (SEAM - ZC,)))
        kill = [f for f in bm.faces if (f.calc_center_median().z > SEAM) != upper]
        bmesh.ops.delete(bm, geom=kill, context='FACES')
        edges = [e for e in bm.edges if len(e.link_faces) == 1]
        # the parting line: the outer wall stops 0.05 short of the seam and a 45-degree chamfer climbs to a rim that
        # meets the other half exactly at SEAM (a V-groove outside, no gap to see the teeth through)
        for v in {v for e in edges for v in e.verts}:
            v.co.z += 0.05 if upper else -0.05
        cap = bmesh.ops.holes_fill(bm, edges=edges, sides=0)['faces'][0]
        geo.recalc_normals(bm)
        bmesh.ops.inset_region(bm, faces=[cap], thickness=0.05, depth=0.05, use_even_offset=True)
        bmesh.ops.inset_region(bm, faces=[cap], thickness=WALL - 0.05, depth=0.0, use_even_offset=True)
        ret = bmesh.ops.extrude_face_region(bm, geom=[cap])
        bmesh.ops.delete(bm, geom=[cap], context='FACES_ONLY')   # the op keeps the original face
        nv = [g for g in ret['geom'] if isinstance(g, bmesh.types.BMVert)]
        depth = CAV_HI if upper else CAV_LO
        bmesh.ops.translate(bm, verts=nv, vec=(0, 0, depth if upper else -depth))
        inner_z = SEAM
        for f in bm.faces:
            c = f.calc_center_median()
            inside = abs(c.x) < W / 2 - WALL + 0.01 and abs(c.y) < D / 2 - WALL + 0.01
            deep = (inner_z + 0.01 < c.z < TOP - 0.3) if upper else (Z0 + 0.3 < c.z < inner_z - 0.01)
            if inside and deep:
                f.material_index = 1
        # mouth interior darkening is in the material; teeth
        yT = FACE_Y + WALL + 0.2
        if upper:
            xs = [-2.2 + 1.1 * i for i in range(5)]
            for x in xs:
                geo.cone(bm, 0.25, 0.03, 0.62, segs=8, squash=0.62, mat=2,
                         M=_T((x, yT, SEAM + 0.3)) @ _R(180, 0, 0))
            for sx in (-1, 1):
                for y in (-0.35, 0.8):
                    geo.cone(bm, 0.22, 0.03, 0.52, segs=8, squash=0.62, mat=2,
                             M=_T((sx * (W / 2 - WALL - 0.18), y, SEAM + 0.3)) @ _R(180, 0, 90))
        else:
            xs = [-2.75 + 1.1 * i for i in range(6)]
            for x in xs:
                geo.cone(bm, 0.25, 0.03, 0.66, segs=8, squash=0.62, mat=2, M=_T((x, yT, SEAM - 0.3)))
            for sx in (-1, 1):
                for y in (-0.9, 0.25):
                    geo.cone(bm, 0.22, 0.03, 0.55, segs=8, squash=0.62, mat=2,
                             M=_T((sx * (W / 2 - WALL - 0.18), y, SEAM - 0.3)) @ _R(0, 0, 90))
            # tongue
            geo.rounded_box(bm, (2.9, 2.2, 0.62), 0.3, (0, 0.2, SEAM - CAV_LO + 0.1), seg=4, flat=(2, 2, 0), mat=3)
            # a USB-C port on the back (for the boot scene's cable)
            geo.decal(bm, geo.rrect(0.95, 0.34), depth=0.02, back=0.05, bevel=0.015, rings=1, mat=4,
                      M=_T(PORT) @ _R(0, 0, 180))
        return bm

    def _build_body(self):
        mats = [self.m_body, self.m_mouth, self.m_teeth, self.m_tongue, self.m_port]
        self.o_body = self._part(self._half(False), 'body', mats, 'body')
        self.o_lid = self._part(self._half(True), 'lid', mats[:3], 'lid')
        # legs (one mesh, 8 objects)
        bm = bmesh.new()
        geo.rounded_box(bm, (0.88, 0.88, LEG_H), 0.32, (0, 0, LEG_H / 2), seg=3, flat=(1, 1, 2), taper=0.1)
        me = None
        self.o_legs = []
        for i, (x, y) in enumerate(LEG_XY):
            if me is None:
                ob = geo.to_object(bm, f'{self.name}.leg{i}', self.coll, [self.m_legs])
                me = ob.data
            else:
                ob = bpy.data.objects.new(f'{self.name}.leg{i}', me)
                self.coll.objects.link(ob)
            ob.matrix_basis = _T((x, y, 0))
            bone_parent(ob, self.rig, f'leg{i}')
            self.o_legs.append(ob)
        # arms
        self.o_arms = {}
        for s, sx in (('L', 1), ('R', -1)):
            bm = bmesh.new()
            geo.rounded_box(bm, (1.62, 0.76, 0.84), 0.32, (sx * 0.62, 0, 0), seg=3, flat=(2, 1, 1))
            self.o_arms[s] = self._part(bm, f'arm.{s}', [self.m_body], f'arm.{s}', M=_T((sx * ARM_X, 0, ARM_Z)))

    # eye shapes --------------------------------------------------------------------------------------------------
    @staticmethod
    def _eye_outlines(shape):
        """[(outline, material slot, depth, bevel)] for the LEFT eye (+X); inner side is -x. Slots: 0 eye, 1 white,
        2 heart, 3 gold."""
        pill = geo.rrect(0.64, 1.36)
        if shape == 'open':
            return [(pill, 0, 0.15, 0.12)]
        if shape == 'small':
            return [(geo.rrect(0.44, 0.78), 0, 0.14, 0.1)]
        if shape == 'surprised':
            return [(geo.ellipse(0.92, 1.56, 48), 0, 0.15, 0.14),
                    (geo.ellipse(0.22, 0.3, 20, cx=-0.14, cz=0.4), 1, 0.2, 0.05)]
        if shape == 'happy':
            return [(geo.stroke(geo.arc(0, -0.3, 0.4, 0.58, 12, 168, 18), 0.27), 0, 0.14, 0.09)]
        if shape == 'shut':
            return [(geo.stroke(geo.arc(0, 0.08, 0.42, 0.2, 196, 344, 16), 0.22), 0, 0.13, 0.08)]
        if shape == 'angry':
            return [(geo.clip(geo.rrect(0.7, 1.3), 0.8, -1.0, 0.1), 0, 0.15, 0.1)]
        if shape == 'narrow':
            return [(geo.clip(geo.rrect(0.74, 1.36), 0.25, -1.0, 0.1), 0, 0.15, 0.1)]
        if shape == 'sad':
            return [(geo.clip(geo.rrect(0.66, 1.3), -0.7, -1.0, 0.12), 0, 0.15, 0.1)]
        if shape == 'heart':
            return [(geo.heart(1.2, 1.1, 64), 2, 0.17, 0.12)]
        if shape == 'star':
            return [(geo.star(0.66, 0.3), 3, 0.16, 0.06)]
        if shape == 'x':
            return [(geo.stroke([(-0.36, -0.42), (0.36, 0.42)], 0.2), 0, 0.14, 0.07),
                    (geo.stroke([(-0.36, 0.42), (0.36, -0.42)], 0.2), 0, 0.16, 0.07)]
        if shape == 'dizzy':
            pts = []
            for k in range(60):
                a = k / 59 * 2.6 * 2 * math.pi
                r = 0.05 + 0.4 * k / 59
                pts.append((r * math.cos(a), r * math.sin(a) * 1.25))
            return [(geo.stroke(pts, 0.13, cap=6), 0, 0.13, 0.05)]
        raise KeyError(f'unknown eye shape {shape!r}; one of {EYE_SHAPES}')

    def _eye_obj(self, shape, side):
        key = (shape, side)
        if key in self._eye_objs:
            return self._eye_objs[key]
        bm = bmesh.new()
        sx = 1 if side == 'L' else -1
        for outline, slot, depth, bev in self._eye_outlines(shape):
            if side == 'R':
                outline = geo.mirror_x(outline)
            geo.decal(bm, outline, depth=depth, back=0.12, bevel=bev, rings=3, mat=slot,
                      M=_T((sx * EYE_X, FACE_Y, EYE_Z)))
        ob = geo.to_object(bm, f'{self.name}.eye.{side}.{shape}', self.coll,
                           [self.m_eye[side], self.m_white, self.m_heart, self.m_gold], sharp=50)
        bone_parent(ob, self.rig, f'eye.{side}')
        self._eye_objs[key] = ob
        self._baked = False
        return ob

    # props -------------------------------------------------------------------------------------------------------
    def _prop(self, prop):
        if prop in self._props:
            return self._props[prop]
        from . import props as P
        objs = P.build(prop, self)
        self._props[prop] = objs
        self._baked = False
        return objs

    # ============================================================================================ API
    def hop(self, t: float, height: float = 2.0, dur: float | None = None, *, to=None, at: str = 'takeoff',
            spin: float = 0.0):
        """A hop. at: which moment lands on t ('takeoff' | 'apex' | 'land'). to: (x, y[, z]) to hop to a new
        spot; spin: degrees of yaw turned in the air."""
        dur = dur or (0.26 + 0.07 * height)
        t_off = {'takeoff': t, 'apex': t - dur / 2, 'land': t - dur}[at]
        t_land = t_off + dur
        HL, S = self.T['hips.loc'], self.T['body.sq']

        def arc(x, t_off=t_off, dur=dur, h=height):
            u = (x - t_off) / dur
            return (0.0, 0.0, 4 * h * u * (1 - u))
        HL.add(t_off, t_land, arc)
        S.add(t_off - 0.16, t_off, lambda x: -0.2 * smoothstep(t_off - 0.16, t_off - 0.03, x))
        S.add(t_off, t_off + dur * 0.55, lambda x: 0.22 * (1 - smoothstep(t_off, t_off + dur * 0.55, x)))
        S.add(t_land, t_land + 0.7, lambda x: -0.24 * wobble(x, t_land, 3.0, 6.0))
        HL.add(t_off - 0.16, t_off, lambda x: (0.0, 0.0, -0.25 * smoothstep(t_off - 0.16, t_off - 0.03, x)))
        for i, (lx, ly) in enumerate(LEG_XY):
            d = Vector((lx, ly * 2.0)).normalized()
            self.T[f'leg{i}'].add(t_off, t_land, lambda x, d=d: tuple(
                v * bump(x, t_off, t_off + dur * 0.3, t_land) for v in (d.y * 22, -d.x * 22, 0.25)))
        for s in 'LR':
            self.T[f'arm.{s}'].add(t_off - 0.1, t_land + 0.25, lambda x: (
                38 * bump(x, t_off - 0.05, t_off + dur * 0.4, t_land + 0.2), 0.0, 0.0))
        if to is not None:
            p0 = self.T['root.loc'].at(t_off)
            self.T['root.loc'].set(t_land, _v3(to, p0[2]), dur, 'linear')
            self.no_gait(t_off, t_land + 0.05)
        if spin:
            y0 = self.T['root.yaw'].at(t_off)
            self.T['root.yaw'].set(t_land, y0 + spin, dur, 'inout')
            self.no_gait(t_off, t_land + 0.05)
        self._ev(t_off)
        self._ev(t_land)
        return self

    def squash(self, t: float, amount: float = 0.25, dur: float = 0.7):
        """Squash (amount > 0) or stretch (< 0) arriving at t, then spring back."""
        S = self.T['body.sq']
        S.add(t - 0.1, t, lambda x: -amount * smoothstep(t - 0.1, t, x))
        S.add(t, t + dur, lambda x: -amount * wobble(x, t, 3.0, 6.5))
        self._ev(t)
        return self

    def stretch(self, t: float, amount: float = 0.2, dur: float = 0.7):
        return self.squash(t, -amount, dur)

    def lid(self, t: float, open01: float, dur: float = 0.14, ease: str = 'out'):
        """Open the lid/mouth: 0 closed, 1 wide open (72 deg), up to ~1.25."""
        self.T['lid'].set(t, float(open01), dur, ease)
        self._ev(t)
        return self

    def chomp(self, t: float, wide: float = 0.9, n: int = 1, every: float | None = None):
        """Bite(s): the lid opens before t and SLAMS shut on t (and on t + k*every). Lunges a little."""
        every = every or tm.beat_period()
        Lid = self.T['lid']
        for k in range(n):
            tk = t + k * every
            a0 = tk - min(0.34, every * 0.75)
            a1 = tk - 0.15

            def env(x, tk=tk, a0=a0, a1=a1):
                if x < a1:
                    return EASE['out'](smoothstep(a0, a1, x))
                if x < tk - 0.07:
                    return 1.0
                if x < tk:
                    return 1.0 - smoothstep(tk - 0.07, tk, x)
                return -0.35 * bump(x, tk, tk + 0.04, tk + 0.12)
            Lid.add(a0, tk + 0.12, lambda x, env=env: env(x) * (wide - Lid.base(x)) if env(x) >= 0 else env(x) * 0.1)
            self.T['body.sq'].add(tk - 0.02, tk + 0.5, lambda x, tk=tk: -0.12 * wobble(x, tk, 3.4, 7.0))
            self.T['body.rot'].add(a0, tk + 0.3, lambda x, a0=a0, tk=tk: (
                5.0 * bump(x, a0, tk - 0.1, tk + 0.25) - 4.0 * bump(x, tk - 0.08, tk, tk + 0.25), 0.0, 0.0))
            self.T['body.loc'].add(a0, tk + 0.3, lambda x, a0=a0, tk=tk: (
                0.0, -0.45 * bump(x, tk - 0.12, tk, tk + 0.28), 0.0))
            self._ev(tk)
        return self

    def eyes(self, t: float, shape: str | None = None, *, glow: float | None = None, color=None,
             side: str | None = None, dur: float = 0.12):
        """Eye expression at t: shape in EYE_SHAPES ('open', 'happy', 'angry', 'narrow', 'surprised', 'shut',
        'heart', 'sad', 'small', 'x', 'star', 'dizzy', or 'blink'); glow: emission strength (0 = off, ~3-8 = lit);
        color: glow colour; side: 'L' | 'R' for one eye (a wink, eyes lighting one by one)."""
        sides = [side] if side else ['L', 'R']
        if shape == 'blink':
            return self.blink(t)
        if shape:
            if shape not in EYE_SHAPES:
                raise KeyError(f'unknown eye shape {shape!r}; one of {EYE_SHAPES}')
            for s in sides:
                self._eye_obj(shape, s)
                self.D[f'eyes.{s}'].set(t, shape)
        if glow is not None:
            for s in sides:
                self.T[f'glow.{s}'].set(t, float(glow), dur, 'out')
        if color is not None:
            self.T['glow.col'].set(t, _lin(color), dur)
        self._ev(t)
        return self

    def glow(self, t: float, strength: float = 5.0, color=None, side: str | None = None, dur: float = 0.12):
        return self.eyes(t, glow=strength, color=color, side=side, dur=dur)

    def blink(self, t: float, dur: float = 0.2, side: str | None = None):
        for s in ([side] if side else 'LR'):
            self.T[f'eye.{s}.s'].add(t, t + dur, lambda x, t=t: (0.08 * bump(x, t, t + dur * 0.45, t + dur), 0.0,
                                                                -0.9 * bump(x, t, t + dur * 0.45, t + dur)))
        self._ev(t)
        return self

    def look(self, t: float, target=None, *, turn: float = 0.6, dur: float = 0.25):
        """Look at target (a point, an object, or another character) by t: the body turns `turn` of the way
        (0 = eyes only), the eyes and a small body tilt do the rest. target=None recentres the eyes."""
        E = self.T['eyes.look']
        if target is None:
            E.set(t, (0.0, 0.0), dur * 0.6)
            self.T['body.rot'].set(t, (0.0, 0.0, 0.0), dur)
            self._ev(t)
            return self
        tp = _point(target, t)
        face = self.anchor(t - dur, 'face')
        d = tp - face
        Y = self.T['root.yaw']
        y0 = Y.at(t - dur)
        want = unwrap(math.degrees(math.atan2(d.x, -d.y)), y0)
        new = y0
        if turn > 0 and not self._moving(t - dur, t):
            new = y0 + (want - y0) * turn
            Y.set(t, new, dur, 'inout')
        rem = math.radians(want - new)
        elev = math.atan2(d.z, max(1e-6, d.xy.length))
        ex = max(-0.36, min(0.36, math.sin(rem) * 0.6))
        ez = max(-0.24, min(0.26, math.sin(elev) * 0.5))
        E.set(t, (ex, ez), dur * 0.7)
        pitch = max(-10.0, min(12.0, math.degrees(elev) * 0.35))
        self.T['body.rot'].set(t, (-pitch, 0.0, 0.0), dur)
        self._ev(t)
        return self

    def arms(self, t: float, pose='rest', *, side: str | None = None, dur: float = 0.16, ease: str = 'out'):
        """Arm pose by t: a name from ARM_POSES ('rest', 'up', 'high', 'cheer', 'forward', 'hold', 'hug', 'down',
        'out', 'back', 'shrug', 'fold', 'akimbo', 'point', 'wave', 'think') or (raise, swing, twist) degrees."""
        if isinstance(pose, str):
            p = ARM_POSES[pose]
        else:
            p = tuple(pose)
        lr = p if isinstance(p, dict) else {'L': p, 'R': p}
        for s in ([side] if side else 'LR'):
            self.T[f'arm.{s}'].set(t, tuple(float(x) for x in lr[s]), dur, ease)
        self._ev(t)
        return self

    def wave(self, t0: float, t1: float, side: str = 'R', rate: float | None = None):
        """Wave one arm from t0 to t1 (raises it, waves, puts it back)."""
        A = self.T[f'arm.{side}']
        prev = A.at(t0 - 0.2)
        A.set(t0, tuple(float(x) for x in ARM_POSES['wave']['R']), 0.18, 'out')
        A.set(t1 + 0.2, prev, 0.2)
        per = rate or tm.beat_period()
        A.add(t0, t1, lambda x: (14 * math.sin(2 * math.pi * (x - t0) / per), 18 * math.sin(2 * math.pi * (x - t0) / per), 0.0))
        self._ev(t0)
        self._ev(t1)
        return self

    def take(self, t: float, *, hold: float = 0.8, mark: bool = False, jump: float = 1.3):
        """The cartoon's surprise take: anticipation squash, pop up and stretch, arms fly up, eyes go wide, the lid
        gasps open; holds `hold` seconds and settles. mark=True pops a yellow '!' above his head."""
        S, HL = self.T['body.sq'], self.T['hips.loc']
        S.add(t - 0.14, t, lambda x: -0.18 * smoothstep(t - 0.14, t - 0.02, x))
        S.add(t, t + 0.9, lambda x: 0.3 * wobble(x, t, 2.6, 5.0))
        HL.add(t - 0.02, t + 0.36, lambda x: (0.0, 0.0, jump * 4 * ((x - t + 0.02) / 0.38) * (1 - (x - t + 0.02) / 0.38)))
        env = lambda x: smoothstep(t - 0.04, t + 0.02, x) * (1 - smoothstep(t + hold, t + hold + 0.3, x))
        for s in 'LR':
            A = self.T[f'arm.{s}']
            A.add(t - 0.05, t + hold + 0.35, lambda x, A=A: (env(x) * (74.0 - A.base(x)[0]), 8 * env(x), 0.0))
        self.T['lid'].add(t - 0.05, t + hold + 0.35, lambda x: 0.22 * env(x))
        self.T['body.rot'].add(t - 0.05, t + hold + 0.35, lambda x: (-7.0 * env(x), 0.0, 0.0))
        for s in 'LR':
            prev = self.D[f'eyes.{s}'].at(t - 1e-3)
            self._eye_obj('surprised', s)
            self.D[f'eyes.{s}'].set(t, 'surprised')
            self.D[f'eyes.{s}'].set(t + hold, prev, origin=t)
        if mark:
            self._mark_obj()
            self.D['mark'].set(t, True)
            self.D['mark'].set(t + hold, False)
        self._ev(t)
        return self

    def dance(self, t0: float, t1: float, style: str = 'bounce', beats=None, amount: float = 1.0):
        """Dance on the beat from t0 to t1. style: 'bounce' | 'sway' | 'spin' | 'shimmy' | 'hop' | 'chomp' |
        'wave'. beats defaults to the song's beats in [t0, t1)."""
        bs = list(beats) if beats is not None else tm.beats_between(t0, t1)
        if not bs:
            return self
        per = tm.beat_period()
        a = amount

        def phase(x):
            i = bisect.bisect_right(bs, x) - 1
            if i < 0:
                return 0, (x - bs[0]) / per
            nxt = bs[i + 1] if i + 1 < len(bs) else bs[i] + per
            return i, (x - bs[i]) / (nxt - bs[i])
        win = lambda x: smoothstep(t0, t0 + 0.12, x) * (1 - smoothstep(t1 - 0.12, t1, x))
        if style in ('bounce', 'chomp', 'wave'):
            for b in bs:
                self.T['body.sq'].add(b - 0.08, b + per, lambda x, b=b: -0.13 * a * (
                    smoothstep(b - 0.08, b, x) if x < b else wobble(x, b, 2.4, 6.0)))
            self.T['hips.loc'].add(t0, t1, lambda x: (0.0, 0.0, 0.55 * a * win(x) * math.sin(math.pi * phase(x)[1]) ** 2))
            if style == 'bounce':
                for s, sg in (('L', 1), ('R', -1)):
                    self.T[f'arm.{s}'].add(t0, t1, lambda x, sg=sg: (
                        28 * a * win(x) * sg * (1 if phase(x)[0] % 2 else -1) * math.sin(math.pi * phase(x)[1]), 0.0, 0.0))
        if style == 'chomp':
            self.chomp(bs[0], wide=0.55 * a + 0.2, n=len(bs), every=per)
        if style in ('sway', 'wave'):
            self.T['body.rot'].add(t0, t1, lambda x: (0.0, 10 * a * win(x) * math.sin(math.pi * (phase(x)[0] + phase(x)[1])), 0.0))
            self.T['hips.loc'].add(t0, t1, lambda x: (0.4 * a * win(x) * math.sin(math.pi * (phase(x)[0] + phase(x)[1])), 0.0, 0.0))
            for s, sg in (('L', 1), ('R', -1)):
                base_up = 55 if style == 'wave' else 0
                self.T[f'arm.{s}'].add(t0, t1, lambda x, sg=sg, base_up=base_up: (
                    win(x) * (base_up + 30 * a * sg * math.sin(math.pi * (phase(x)[0] + phase(x)[1]))),
                    win(x) * 10 * math.cos(math.pi * (phase(x)[0] + phase(x)[1])), 0.0))
        if style == 'shimmy':
            self.T['body.rot'].add(t0, t1, lambda x: (0.0, 6 * a * win(x) * math.sin(2 * math.pi * (phase(x)[0] + phase(x)[1])), 0.0))
            self.T['body.loc'].add(t0, t1, lambda x: (0.22 * a * win(x) * math.sin(2 * math.pi * (phase(x)[0] + phase(x)[1])), 0.0, 0.0))
            for s, sg in (('L', 1), ('R', -1)):
                self.T[f'arm.{s}'].add(t0, t1, lambda x, sg=sg: (
                    win(x) * (20 + 32 * a * sg * math.sin(2 * math.pi * (phase(x)[0] + phase(x)[1]))), 0.0, 0.0))
            for i in range(8):
                g = LEG_GROUP[i]
                self.T[f'leg{i}'].add(t0, t1, lambda x, g=g: (0.0, 0.0, 0.3 * a * win(x) * max(0.0, math.sin(
                    2 * math.pi * (phase(x)[0] + phase(x)[1]) + math.pi * g))))
        if style == 'spin':
            Y = self.T['root.yaw']
            y0 = Y.at(bs[0] - 0.2)
            for k, b in enumerate(bs):
                Y.set(b, y0 + 90.0 * (k + 1), min(0.22, per * 0.6), 'out')
                self.T['hips.loc'].add(b - 0.22, b + 0.05, lambda x, b=b: (0.0, 0.0, 0.8 * a * bump(x, b - 0.22, b - 0.1, b + 0.03)))
            n_extra = (-len(bs)) % 4
            for k in range(n_extra):
                Y.set(bs[-1] + per * (k + 1), y0 + 90.0 * (len(bs) + k + 1), min(0.22, per * 0.6), 'out')
            self.no_gait(bs[0] - 0.3, bs[-1] + per * (n_extra + 1))
        if style == 'hop':
            for b in bs:
                self.hop(b, height=1.3 * a, dur=per * 0.7, at='land')
        for b in bs:
            self._ev(b)
        return self

    def wear(self, t: float, prop: str, on: bool = True):
        """Put on (on=True) or take off a prop at t: 'crown' (paper crown), 'cat_ears', 'mask' (smiley mask over the
        face), 'party_hat', 'bowtie'. Props ride the lid (they tip back when he opens his mouth)."""
        if prop not in PROPS:
            raise KeyError(f'unknown prop {prop!r}; one of {PROPS}')
        self._prop(prop)
        self.disc(f'prop.{prop}', False).set(t, bool(on))
        self._ev(t)
        return self

    def scale_to(self, t: float, s: float, dur: float = 0.35, ease: str = 'back'):
        """Uniform size by t (FOOM). The legs keep stepping at scale."""
        self.T['root.scale'].set(t, float(s), dur, ease)
        self._ev(t)
        return self

    # ---------------------------------------------------------------------------------------------- helpers
    def attach(self, obj, socket: str, offset=(0, 0, 0), rot=(0, 0, 0)):
        """Parent a scene object to a socket bone ('hat', 'face', 'mouth', 'back', 'hand.L', 'hand.R', 'eye.L',
        'eye.R', 'body', 'lid', 'hips', 'root'). The object is placed at the socket's rest position + offset
        (socket axes = character axes: -Y forward), rotated by rot (deg)."""
        head = Vector(BONES[socket])
        obj.matrix_world = self.rig.matrix_world @ _T(head + Vector(offset)) @ _R(*rot)
        bone_parent(obj, self.rig, socket)
        return obj

    def anchor(self, t: float, name: str = 'face') -> Vector:
        """World position of a socket at song time t (from the tracks, without jitter): 'face', 'eye.L', 'eye.R',
        'hat', 'mouth', 'back', 'hand.L', 'hand.R', 'hinge', 'center', 'root'."""
        M = self._fk(t)
        if name == 'center':
            return self.rig.matrix_world @ (M['body'] @ Vector((0, 0, H / 2)))
        if name == 'hinge':
            name = 'lid'
        head = M[name] @ Vector((0, 0, 0))
        return self.rig.matrix_world @ head

    def _fk(self, t):
        T = self.T
        rl, yaw, s = T['root.loc'].at(t), T['root.yaw'].at(t), T['root.scale'].at(t)
        Mr = _T(rl) @ Matrix.Rotation(math.radians(yaw), 4, 'Z') @ Matrix.Scale(s, 4)
        Mh = Mr @ _T(BONES['hips']) @ _T(T['hips.loc'].at(t)) @ _R(*T['hips.rot'].at(t))
        sq = max(-0.6, T['body.sq'].at(t))
        k = 1 / math.sqrt(1 + sq)
        Sq = Matrix.Diagonal((k, k, 1 + sq, 1.0))
        Mb = Mh @ _T(T['body.loc'].at(t)) @ _R(*T['body.rot'].at(t)) @ Sq
        Ml = Mb @ _T(Vector(BONES['lid']) - Vector(BONES['body'])) @ _R(-LID_MAX * T['lid'].at(t), 0, 0)
        ex, ez = T['eyes.look'].at(t)
        M = {'root': Mr, 'hips': Mh, 'body': Mb, 'lid': Ml}
        for n in ('eye.L', 'eye.R'):
            M[n] = Ml @ _T(Vector(BONES[n]) - Vector(BONES['lid'])) @ _T((ex, 0, ez))
        for n in ('face', 'hat'):
            M[n] = Ml @ _T(Vector(BONES[n]) - Vector(BONES['lid']))
        for n in ('mouth', 'back'):
            M[n] = Mb @ _T(Vector(BONES[n]) - Vector(BONES['body']))
        for sd in 'LR':
            r, sw, tw, dx = arm_clear(sd, *T[f'arm.{sd}'].at(t))
            M[f'arm.{sd}'] = Mb @ _T(Vector(BONES[f'arm.{sd}']) - Vector(BONES['body'])) @                 _T(((dx if sd == 'L' else -dx), 0, 0)) @ self._arm_R(sd, r, sw, tw)
            M[f'hand.{sd}'] = M[f'arm.{sd}'] @ _T(Vector(BONES[f'hand.{sd}']) - Vector(BONES[f'arm.{sd}']))
        return M

    @staticmethod
    def _arm_euler(side, raise_, swing, twist):
        if side == 'L':
            return (math.radians(twist), math.radians(-raise_), math.radians(-swing))
        return (math.radians(-twist), math.radians(raise_), math.radians(swing))

    def _arm_R(self, side, r, sw, tw):
        from mathutils import Euler
        return Euler(self._arm_euler(side, r, sw, tw), 'XYZ').to_matrix().to_4x4()

    def _mark_obj(self):
        if self._mark is None:
            from . import props as P
            self._mark = P.build('mark', self)
            self._baked = False
        return self._mark

    # ============================================================================================ bake
    def _plan_blinks(self, ta, tb):
        self._auto_blinks = []
        if not self.auto_blink:
            return
        ev = sorted(self.events)
        t = ta + 0.6 + 2.0 * hash01(self.seed, 1)
        k = 0
        while t < tb:
            near = False
            i = bisect.bisect_left(ev, t - 0.35)
            if i < len(ev) and ev[i] < t + 0.35:
                near = True
            if not near and self.D['eyes.L'].at(t) in BLINKABLE and self.D['eyes.R'].at(t) in BLINKABLE:
                self._auto_blinks.append(t)
            k += 1
            t += 2.3 + 2.9 * hash01(self.seed, 7, k)

    def bake(self, f0=None, f1=None):
        sc = bpy.context.scene
        a = (sc.frame_start if f0 is None else f0) / tm.FPS
        b = (sc.frame_end if f1 is None else f1) / tm.FPS
        self._plan_blinks(a, b)
        return super().bake(f0, f1)

    def _targets(self):
        R = self.rig
        tg = []
        J_LOC, J_ROT, J_SC = 0.018, math.radians(0.45), 0.004

        def bone(b, prop, n, jit):
            for i in range(n):
                tg.append(Target(R, pb(b, prop), i, jit))
        bone('root', 'location', 3, J_LOC)
        bone('root', 'rotation_euler', 3, J_ROT)
        bone('root', 'scale', 3, 0.0)
        bone('hips', 'location', 3, J_LOC)
        bone('hips', 'rotation_euler', 3, J_ROT)
        bone('body', 'location', 3, J_LOC)
        bone('body', 'rotation_euler', 3, J_ROT)
        bone('body', 'scale', 3, J_SC)
        bone('lid', 'rotation_euler', 1, math.radians(0.8))
        for s in 'LR':
            bone(f'eye.{s}', 'location', 3, 0.004)
            bone(f'eye.{s}', 'scale', 3, 0.0)
            bone(f'arm.{s}', 'rotation_euler', 3, math.radians(1.4))
            bone(f'arm.{s}', 'location', 3, 0.0)
        for i in range(8):
            bone(f'leg{i}', 'location', 3, 0.01)
            bone(f'leg{i}', 'rotation_euler', 3, math.radians(1.2))
        # visibility of eye shapes / props (hide_render + hide_viewport)
        self._vis = []
        for (shape, side), ob in self._eye_objs.items():
            self._vis.append((ob, ('eye', side, shape)))
        for prop, objs in self._props.items():
            for ob in objs:
                self._vis.append((ob, ('prop', prop)))
        if self._mark:
            for ob in self._mark:
                self._vis.append((ob, ('mark',)))
        if self._uses_visible():
            for ob in [self.o_body, self.o_lid, *self.o_legs, *self.o_arms.values()]:
                self._vis.append((ob, ('all',)))
        for ob, _ in self._vis:
            tg.append(Target(ob, 'hide_render', -1, 0.0))
            tg.append(Target(ob, 'hide_viewport', -1, 0.0))
        # glow
        self._use_glow = any(tr.keys or tr.over for n, tr in self.T.items() if n.startswith('glow.'))
        if self._use_glow:
            for s in 'LR':
                nt = self.m_eye[s].node_tree
                tg.append(Target(nt, 'nodes["glow"].outputs[0].default_value', -1, 0.0))
                for i in range(3):
                    tg.append(Target(nt, 'nodes["glowcol"].outputs[0].default_value', i, 0.0))
            if self.glow_light and self._light is None:
                # a wide spot just in front of the eyes, aimed forward: it lights what he faces, not his own face
                ld = bpy.data.lights.new(f'{self.name}.eyelight', 'SPOT')
                ld.shadow_soft_size = 0.8
                ld.spot_size = math.radians(150)
                ld.spot_blend = 1.0
                ld.energy = 0.0
                lo = bpy.data.objects.new(f'{self.name}.eyelight', ld)
                self.coll.objects.link(lo)
                lo.matrix_basis = _T((0, FACE_Y - 0.45, EYE_Z)) @ _R(-90, 0, 0)
                bone_parent(lo, self.rig, 'face')
                self._light = ld
            if self._light is not None:
                tg.append(Target(self._light, 'energy', -1, 0.0))
                for i in range(3):
                    tg.append(Target(self._light, 'color', i, 0.0))
        return tg

    def _solve(self, t):
        T = self.T
        out = []
        rl = T['root.loc'].at(t)
        out += rl
        out += (0.0, 0.0, math.radians(T['root.yaw'].at(t)))
        s = T['root.scale'].at(t)
        out += (s, s, s)
        ph, amp, vx, vy, w = self.gait(t)
        hl = T['hips.loc'].at(t)
        out += hl
        out += [math.radians(x) for x in T['hips.rot'].at(t)]
        c2 = math.sin(2 * math.pi * ph)
        bl = T['body.loc'].at(t)
        out += (bl[0], bl[1], bl[2] + 0.12 * amp * abs(c2))
        br = T['body.rot'].at(t)
        out += (math.radians(br[0]), math.radians(br[1] + 2.4 * amp * c2), math.radians(br[2]))
        sq = max(-0.6, T['body.sq'].at(t))
        k = 1 / math.sqrt(1 + sq)
        out += (k, k, 1 + sq)
        out.append(math.radians(-LID_MAX * max(-0.04, min(1.3, T['lid'].at(t)))))
        ex, ez = T['eyes.look'].at(t)
        blink = 0.0
        for tb in self._auto_blinks:
            if tb <= t < tb + 0.2:
                blink = bump(t, tb, tb + 0.09, tb + 0.2)
        for sd in 'LR':
            out += (ex, 0.0, ez)
            es = T[f'eye.{sd}.s'].at(t)
            out += (1 + es[0] + 0.08 * blink, 1 + es[1], max(0.05, 1 + es[2] - 0.9 * blink))
            r, sw, tw = T[f'arm.{sd}'].at(t)
            sw += (12 if sd == 'L' else -12) * amp * c2
            r, sw, tw, dx = arm_clear(sd, r, sw, tw)
            out += self._arm_euler(sd, r, sw, tw)
            out += ((dx if sd == 'L' else -dx), 0.0, 0.0)
        wr = w
        for i, (lx, ly) in enumerate(LEG_XY):
            fx, fy = vx - wr * ly, vy + wr * lx
            n = math.hypot(fx, fy)
            dx, dy = (fx / n, fy / n) if n > 1e-4 else (0.0, -1.0)
            phi = 2 * math.pi * (ph + 0.5 * LEG_GROUP[i])
            th = self.LEG_SWING * amp * math.sin(phi)
            lift = self.LEG_LIFT * amp * max(0.0, math.cos(phi))
            ov = T[f'leg{i}'].at(t)
            out += (0.0, 0.0, lift + ov[2])
            out += (math.radians(dy * th + ov[0]), math.radians(-dx * th + ov[1]), 0.0)
        shown = self._shown(t)
        for ob, what in self._vis:
            if what[0] == 'eye':
                on = self.D[f'eyes.{what[1]}'].at(t) == what[2]
            elif what[0] == 'prop':
                on = bool(self.D[f'prop.{what[1]}'].at(t))
            elif what[0] == 'mark':
                on = bool(self.D['mark'].at(t))
            else:
                on = True
            on = on and shown
            out += (0.0 if on else 1.0, 0.0 if on else 1.0)
        if self._use_glow:
            col = T['glow.col'].at(t)
            gs = []
            for sd in 'LR':
                g = max(0.0, T[f'glow.{sd}'].at(t))
                gs.append(g)
                out.append(g)
                out += col
            if self._light is not None:
                out.append(90.0 * (gs[0] + gs[1]) * s * s * (1.0 if shown else 0.0))
                out += col
        return out


def sydney(coll, name: str = 'sydney', loc=(0, 0, 0), yaw: float = 0.0, scale: float = 1.0, **kw) -> Clawd:
    """Sydney: a translucent blue jelly Clawd (same rig and API). Glows faintly from inside."""
    return Clawd(coll, name=name, loc=loc, yaw=yaw, scale=scale, variant='sydney', **kw)
