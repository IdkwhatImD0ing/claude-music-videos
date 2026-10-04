"""The basilisk: a snake made of USB cables (scene-local, shared by `sydney` and `moon`).

The body is three USB cables (black, charcoal, white) twisted into one braid and bound every few cm by black zip ties
whose tails stick up like dorsal spines. Its tail is plugged into the laptop's right-hand port; its head is a chunky
USB-A plug: the metal shell is the snout and splits into jaws, two red LEDs are the eyes, a forked copper wire is the
tongue. At rest it lies on the desk like any cable.

The spine is a POLY curve whose points are keyed on the chars library's stop-motion grid (twos by default); a
geometry-nodes modifier sweeps the braid and places the ties. The head follows the spine's tip (keyed on the same
grid). Pose = rest path, lifted into a cobra S-curve by `rear` (0..1), aimed by `aim` (heading in degrees), swayed by
`sway`, and blended toward an optional `strike` curve (a list of points) by `strike_w`.
"""
from __future__ import annotations

import math

import bpy
import numpy as np
from mathutils import Matrix, Vector

from pdoom import kit
from pdoom.fx import _nodes as N
from pdoom.sets import geo
from pdoom.sets import materials as M
from pdoom.timing import FPS

# the rest path on the desk (world cm): from the laptop's right port, round the left of the researcher, to the
# front-left where the head lies pointing at the snow globe
PORT = Vector((-1.8, 17.6, 0.75))
REST = [(-1.8, 17.6, 0.75), (0.4, 17.4, 0.62), (2.6, 15.2, 0.6), (1.0, 11.4, 0.6), (-5.0, 9.0, 0.6),
        (-13.0, 6.2, 0.6), (-18.6, 0.6, 0.6), (-20.0, -7.0, 0.6), (-18.6, -13.0, 0.6), (-15.4, -16.2, 0.6),
        (-12.2, -15.0, 0.6), (-9.6, -15.6, 0.6), (-8.0, -17.6, 0.6), (-7.4, -19.6, 0.6)]
BODY_R = 0.6          # the braid's radius (the spine's height off the desk at rest)
STRAND_R = 0.27
TIE_EVERY = 2.4


def _resample(pts, n):
    P = [Vector(p) for p in pts]
    dense = geo.catmull(P, 16)
    L = [0.0]
    for i in range(1, len(dense)):
        L.append(L[-1] + (dense[i] - dense[i - 1]).length)
    out = []
    j = 1
    for k in range(n):
        s = L[-1] * k / (n - 1)
        while j < len(L) - 1 and L[j] < s:
            j += 1
        a = (s - L[j - 1]) / max(1e-9, L[j] - L[j - 1])
        out.append(dense[j - 1].lerp(dense[j], a))
    return out, L[-1]


def _heading(v):
    return math.atan2(v.y, v.x)


def write_keys(idb, path, index, keys, interp='CONSTANT'):
    """Write an F-curve in bulk: keys = [(frame, value)]."""
    ad = idb.animation_data or idb.animation_data_create()
    if ad.action is None:
        ad.action = bpy.data.actions.new(f'{idb.name}.act')
    fc = ad.action.fcurve_ensure_for_datablock(idb, path, index=index)
    kp = fc.keyframe_points
    kp.clear()
    kp.add(len(keys))
    kp.foreach_set('co', [c for f, v in keys for c in (f, v)])
    ip = {'CONSTANT': 0, 'LINEAR': 1, 'BEZIER': 2}[interp]
    kp.foreach_set('interpolation', [ip] * len(keys))
    fc.update()
    return fc


def grid(t0, t1, mode='twos', spans=()):
    """The chars library's stop-motion grid: [(key frame, sample time, interp)]. Smooth on the output grid when built
    for 60 fps (timing.SMOOTH)."""
    from pdoom import timing as _tm
    if _tm.SMOOTH:
        return [(fk, fk / FPS, 'LINEAR') for fk in _tm.out_frames(math.floor(t0 * FPS) - 2, math.ceil(t1 * FPS) + 2)]
    def mode_at(t):
        m = mode
        for a, b, mm in spans:
            if a <= t < b:
                m = mm
        return m
    f = int(math.floor(t0 * FPS)) - 2
    f -= f % 2
    f1 = int(math.ceil(t1 * FPS)) + 2
    out = []
    while f <= f1:
        m = mode_at(f / FPS)
        if m == 'ones':
            out.append((f - 0.5, f / FPS, 'CONSTANT'))
            f += 1
        elif m == 'smooth':
            out.append((float(f), f / FPS, 'LINEAR'))
            f += 1
        else:
            if f % 2:
                out.append((f - 0.5, f / FPS, 'CONSTANT'))
                f += 1
                continue
            out.append((f - 0.5, (f + 1) / FPS, 'CONSTANT'))
            f += 2
    return out


# ------------------------------------------------------------------------------------------------ materials


def _mats():
    return [M.solid('basilisk.black', '#17181A', rough=0.42, spec=0.45, micro=(12.0, 0.02)),
            M.solid('basilisk.char', '#3A3D42', rough=0.45, spec=0.45, micro=(12.0, 0.02)),
            M.solid('basilisk.white', '#E6E4DE', rough=0.4, spec=0.45, micro=(12.0, 0.02))]


def led_mat(name='basilisk.led', color='#FF2A18'):
    m, fresh = M.new_mat(name)
    if fresh:
        b = M.principled(m)
        M.setin(b, 'Base Color', M.col('#3A0604'))
        M.setin(b, 'Roughness', 0.08)
        M.setin(b, 'Coat Weight', 1.0)
        M.setin(b, 'Coat Roughness', 0.02)
        M.setin(b, 'Emission Color', M.col(color))
        M.setin(b, 'Emission Strength', 0.0)
    return m


# ------------------------------------------------------------------------------------------------ the snake


class Basilisk:
    def __init__(self, coll, *, name='basilisk', rest=REST, n=110, rear_len=19.0, seed=3):
        self.coll = coll
        self.name = name
        self.n = n
        self.rest, self.length = _resample(rest, n)
        self.ds = self.length / (n - 1)
        self.rear_len = rear_len
        self.s0 = max(1, n - 1 - int(round(rear_len / self.ds)))     # first point of the rearing neck
        # rest headings (radians, horizontal) and elevations along the path
        self.rest_head = []
        for i in range(n - 1):
            self.rest_head.append(_heading(self.rest[i + 1] - self.rest[i]))
        self.rest_head.append(self.rest_head[-1])
        for i in range(1, n):
            while self.rest_head[i] - self.rest_head[i - 1] > math.pi:
                self.rest_head[i] -= 2 * math.pi
            while self.rest_head[i] - self.rest_head[i - 1] < -math.pi:
                self.rest_head[i] += 2 * math.pi
        # animation controls (functions of song time); scenes replace them
        self.rear = lambda t: 0.0
        self.aim = lambda t: math.degrees(self.rest_head[-1])
        self.sway = lambda t: 0.0
        self.ripple = lambda t: 0.0          # a slither wave along the lying body (cm)
        self.lift = lambda t: 0.0            # the head alone lifts off the desk (cm): stirring
        self.strike = None                   # a list of n - s0 points (world)
        self.strike_w = lambda t: 0.0
        self.jaw = lambda t: 0.0             # 0 shut .. 1 wide
        self.tongue = lambda t: 0.0          # 0 in .. 1 out
        self.eyes = lambda t: 0.0            # LED emission strength
        self.bow = lambda t: 0.0             # extra degrees the head tips down (a cobra looking down at you)
        self.twist = 7.0                     # braid turns over the whole cable
        self._build()

    # ------------------------------------------------------------------------------------------------ pose
    def spine(self, t):
        """The spine's points (world Vectors) at song time t."""
        n, s0 = self.n, self.s0
        R = self.rear(t)
        rip = self.ripple(t)
        pts = []
        # the lying part: the rest path plus a travelling slither wave (sideways) that dies out toward the port
        for i in range(s0 + 1):
            p = self.rest[i].copy()
            if rip:
                h = self.rest_head[i]
                side = Vector((-math.sin(h), math.cos(h), 0.0))
                w = min(1.0, i / (0.35 * n))
                p += side * (rip * w * math.sin(0.55 * i * self.ds * 0.5 - 7.0 * t))
            pts.append(p)
        base = pts[-1].copy()
        h0 = self.rest_head[s0]
        aim = math.radians(self.aim(t))
        while aim - h0 > math.pi:
            aim -= 2 * math.pi
        while aim - h0 < -math.pi:
            aim += 2 * math.pi
        sw = self.sway(t)
        lift = self.lift(t)
        bow = self.bow(t)
        m = n - 1 - s0
        cur = base.copy()
        for j in range(1, m + 1):
            u = j / m
            i = s0 + j
            # heading: rest heading blended toward the aim, plus a sway wave
            hr = self.rest_head[i - 1]
            w = min(1.0, R) * (0.35 + 0.65 * u)
            h = hr + (aim - hr) * w + math.radians(sw) * math.sin(math.pi * u * 1.6 - 1.0) * min(1.0, R + 0.2)
            # elevation: a cobra S (up, hold, the head levels off)
            e_up = 92.0 * _sm(0.0, 0.42, u) - 86.0 * _sm(0.7, 1.0, u)
            el = math.radians(e_up * R - bow * _sm(0.72, 1.0, u))
            d = Vector((math.cos(h) * math.cos(el), math.sin(h) * math.cos(el), math.sin(el)))
            cur = cur + d * self.ds
            q = cur.copy()
            if lift:
                q.z += lift * _sm(0.55, 1.0, u)
            q.z = max(q.z, BODY_R * 0.95)
            pts.append(q)
        sw_ = self.strike_w(t) if self.strike else 0.0
        if sw_ > 0:
            for j in range(1, m + 1):
                pts[s0 + j] = pts[s0 + j].lerp(Vector(self.strike[j - 1]), sw_ * _sm(0.0, 0.5, j / m) ** 0.5)
        return pts

    def head_matrix(self, pts):
        tip = pts[-1]
        fwd = (pts[-1] - pts[-3]).normalized()
        up = Vector((0, 0, 1))
        right = fwd.cross(up)
        if right.length < 1e-4:
            right = Vector((1, 0, 0))
        right.normalize()
        up = right.cross(fwd).normalized()
        R3 = Matrix((right, fwd, up)).transposed()
        return Matrix.Translation(tip) @ R3.to_4x4()

    def make_strike(self, target, direction, t):
        """Precompute a strike curve: from the neck's base at time t to `target` (world), arriving along
        `direction` (the head's forward), arc length matched to the neck."""
        pts = self.spine(t)
        base = pts[self.s0]
        m = self.n - 1 - self.s0
        tgt = Vector(target)
        dv = Vector(direction).normalized()
        p1 = base + Vector((0, 0, 9.0))
        p2 = tgt - dv * 6.0 + Vector((0, 0, 2.0))
        ctrl = [base, p1, p2, tgt - dv * 1.2, tgt]
        dense = geo.catmull(ctrl, 30)
        L = [0.0]
        for i in range(1, len(dense)):
            L.append(L[-1] + (dense[i] - dense[i - 1]).length)
        out = []
        j = 1
        for k in range(1, m + 1):
            s = L[-1] * k / m
            while j < len(L) - 1 and L[j] < s:
                j += 1
            a = (s - L[j - 1]) / max(1e-9, L[j] - L[j - 1])
            out.append(dense[j - 1].lerp(dense[j], a))
        self.strike = out
        return out

    # ------------------------------------------------------------------------------------------------ build
    def _build(self):
        cd = bpy.data.curves.new(f'{self.name}.spine', 'CURVE')
        cd.dimensions = '3D'
        sp = cd.splines.new('POLY')
        sp.points.add(self.n - 1)
        for i, p in enumerate(self.rest):
            sp.points[i].co = (p.x, p.y, p.z, 1.0)
        cd.twist_mode = 'MINIMUM'
        self.spine_obj = bpy.data.objects.new(f'{self.name}.spine', cd)
        self.coll.objects.link(self.spine_obj)
        self.mats = _mats()
        for m in self.mats:
            cd.materials.append(m)
        cd.materials.append(M.solid('basilisk.tie', '#101010', rough=0.55, spec=0.35))
        self.mod = N.modifier(self.spine_obj, _braid_tree(self.name, self.twist, self.length), 'braid')
        self._build_head()

    def _build_head(self):
        c = self.coll
        nm = self.name
        blk = M.plastic('basilisk.plug', '#141416', rough=0.38)
        metal = M.solid('basilisk.shell', '#C9CDD2', rough=0.16, metal=1.0, micro=(40.0, 0.01))
        blue = M.plastic('basilisk.tongue3', '#1F4FD8', rough=0.3)
        gold = M.solid('basilisk.gold', '#E2B550', rough=0.18, metal=1.0)
        self.head = kit.empty(f'{nm}.head', (0, 0, 0), c, 'ARROWS', 1.5)
        parts = []
        # strain relief (tapers into the braid) and the housing
        boot = kit.cylinder(f'{nm}.boot', 0.62, 2.2, (0, -2.6, 0), verts=24, m=blk, coll=c,
                            rot=(math.radians(90), 0, 0))
        bm_taper = boot.modifiers.new('taper', 'SIMPLE_DEFORM')
        bm_taper.deform_method, bm_taper.factor, bm_taper.deform_axis = 'TAPER', -0.35, 'Z'
        parts.append(boot)
        hs = geo.box(f'{nm}.housing', (2.3, 3.1, 1.25), (0, 0.0, 0), bev=0.32, segments=4, m=blk, coll=c)
        parts.append(hs)
        # grip ridges on the housing
        for k in range(5):
            r = geo.box(f'{nm}.ridge{k}', (2.34, 0.12, 1.29), (0, -1.1 + k * 0.28, 0), bev=0.05, segments=2,
                        m=blk, coll=c)
            parts.append(r)
        self.head_parts = parts
        # jaws: the USB-A shell split in two (upper and lower), hinged at the housing's front
        self.jaw_up = kit.empty(f'{nm}.jaw.up', (0, 1.55, 0.05), c, 'PLAIN_AXES', 0.4)
        self.jaw_lo = kit.empty(f'{nm}.jaw.lo', (0, 1.55, -0.05), c, 'PLAIN_AXES', 0.4)
        up = geo.box(f'{nm}.shell.up', (1.92, 1.9, 0.08), (0, 2.5, 0.38), bev=0.02, segments=2, m=metal, coll=c)
        up_s = [geo.box(f'{nm}.shell.upside{k}', (0.08, 1.9, 0.38), (sx * 0.92, 2.5, 0.2), bev=0.02, segments=2,
                        m=metal, coll=c) for k, sx in enumerate((-1, 1))]
        lo = geo.box(f'{nm}.shell.lo', (1.92, 1.9, 0.08), (0, 2.5, -0.38), bev=0.02, segments=2, m=metal, coll=c)
        lo_s = [geo.box(f'{nm}.shell.loside{k}', (0.08, 1.9, 0.38), (sx * 0.92, 2.5, -0.2), bev=0.02, segments=2,
                        m=metal, coll=c) for k, sx in enumerate((-1, 1))]
        # the square latch windows on the shell (dark holes read as nostrils)
        for k, sx in enumerate((-0.45, 0.45)):
            hole = geo.box(f'{nm}.nostril{k}', (0.32, 0.32, 0.1), (sx, 3.05, 0.4), bev=0.02, m=blk, coll=c)
            up_s.append(hole)
        # the plastic tongue inside (USB 3 blue) with gold contacts: rides on the lower jaw
        tg = geo.box(f'{nm}.pcb', (1.5, 1.75, 0.2), (0, 2.45, -0.18), bev=0.03, m=blue, coll=c)
        lo_s.append(tg)
        for k in range(4):
            gc = geo.box(f'{nm}.pin{k}', (0.16, 0.9, 0.03), (-0.5 + k * 0.333, 2.95, -0.07), m=gold, coll=c)
            lo_s.append(gc)
        self.jaw_up_parts = [up] + up_s
        self.jaw_lo_parts = [lo] + lo_s
        # LED eyes on the housing's front shoulders
        self.led = led_mat()
        self.eye_objs = []
        for k, sx in enumerate((-0.78, 0.78)):
            e = kit.sphere(f'{nm}.eye{k}', 0.2, (sx, 1.25, 0.6), m=self.led, coll=c, subdiv=3)
            e.scale = (1.0, 0.8, 0.75)
            self.eye_objs.append(e)
            rim = kit.cylinder(f'{nm}.eyerim{k}', 0.26, 0.1, (sx, 1.25, 0.58), verts=20, m=metal, coll=c)
            self.head_parts.append(rim)
        self.head_parts += self.eye_objs
        # the forked tongue: two thin copper wires
        copper = M.solid('basilisk.copper', '#D07A45', rough=0.25, metal=1.0)
        self.tongue_root = kit.empty(f'{nm}.tongue', (0, 2.2, -0.02), c, 'PLAIN_AXES', 0.3)
        tpts = [(0, 0, 0), (0, 1.2, 0.02), (0, 2.0, 0.0)]
        fork = []
        stem = geo.curve_tube(f'{nm}.tongue.stem', tpts, 0.045, coll=c, m=copper, kind='BEZIER', to_mesh=True)
        fork.append(stem)
        for k, sx in enumerate((-1, 1)):
            f = geo.curve_tube(f'{nm}.tongue.f{k}', [(0, 2.0, 0), (sx * 0.25, 2.5, 0.05), (sx * 0.42, 2.8, 0.1)],
                               0.035, coll=c, m=copper, kind='BEZIER', to_mesh=True)
            fork.append(f)
        self.tongue_parts = fork
        # a light in each eye
        self.eye_light = kit.point(f'{nm}.eyelight', (0, 1.8, 0.9), power=0.0, radius=0.3, color='#FF3A20', coll=c)
        # parenting (everything modelled in head space at the origin, forward +Y)
        bpy.context.view_layer.update()
        for o in self.head_parts:
            kit.parent(o, self.head, keep_transform=False)
        kit.parent(self.jaw_up, self.head, keep_transform=False)
        kit.parent(self.jaw_lo, self.head, keep_transform=False)
        for o in self.jaw_up_parts:
            o.parent = self.jaw_up
            o.matrix_parent_inverse = Matrix.Translation(-self.jaw_up.location)
        for o in self.jaw_lo_parts:
            o.parent = self.jaw_lo
            o.matrix_parent_inverse = Matrix.Translation(-self.jaw_lo.location)
        kit.parent(self.tongue_root, self.jaw_lo, keep_transform=False)
        self.tongue_root.location = (0, 2.2 - 1.55, 0.03)
        for o in self.tongue_parts:
            o.parent = self.tongue_root
        kit.parent(self.eye_light, self.head, keep_transform=False)

    # ------------------------------------------------------------------------------------------------ bake
    def bake(self, t0, t1, mode='twos', spans=()):
        """Key the spine points, the head, jaws, tongue and eyes over [t0, t1] on the stop-motion grid."""
        cd = self.spine_obj.data
        sp = cd.splines[0]
        g = grid(t0, t1, mode, spans)
        cols = [[[], [], []] for _ in range(self.n)]
        head_keys = {k: [] for k in ('lx', 'ly', 'lz', 'rx', 'ry', 'rz')}
        jaw_keys, tng_keys, eye_keys = [], [], []
        prev_e = None
        for fk, t, ip in g:
            pts = self.spine(t)
            for i, p in enumerate(pts):
                for a in range(3):
                    cols[i][a].append((fk, p[a]))
            Mh = self.head_matrix(pts)
            loc, rot, _ = Mh.decompose()
            eul = rot.to_euler('XYZ', prev_e) if prev_e is not None else rot.to_euler('XYZ')
            prev_e = eul
            for k, v in zip(('lx', 'ly', 'lz'), loc):
                head_keys[k].append((fk, v))
            for k, v in zip(('rx', 'ry', 'rz'), eul):
                head_keys[k].append((fk, v))
            jaw_keys.append((fk, self.jaw(t)))
            tng_keys.append((fk, self.tongue(t)))
            eye_keys.append((fk, self.eyes(t)))
        from pdoom import timing as _tm
        ip = 'LINEAR' if mode == 'smooth' or _tm.SMOOTH else 'CONSTANT'     # (60 fps builds: smooth on the output grid)
        for i in range(self.n):
            for a in range(3):
                write_keys(cd, f'splines[0].points[{i}].co', a, cols[i][a], ip)
        for a, k in enumerate(('lx', 'ly', 'lz')):
            write_keys(self.head, 'location', a, head_keys[k], ip)
        for a, k in enumerate(('rx', 'ry', 'rz')):
            write_keys(self.head, 'rotation_euler', a, head_keys[k], ip)
        write_keys(self.jaw_up, 'rotation_euler', 0, [(f, math.radians(-28.0) * v) for f, v in jaw_keys], ip)
        write_keys(self.jaw_lo, 'rotation_euler', 0, [(f, math.radians(22.0) * v) for f, v in jaw_keys], ip)
        write_keys(self.tongue_root, 'scale', 1, [(f, max(0.001, v)) for f, v in tng_keys], ip)
        write_keys(self.tongue_root, 'scale', 0, [(f, 0.6 + 0.4 * v) for f, v in tng_keys], ip)
        b = M.principled(self.led)
        sock = b.inputs['Emission Strength']
        for f, v in eye_keys:
            geo.keyp(sock, 'default_value', f / FPS, v, interp=ip)
        for f, v in eye_keys:
            geo.keyp(self.eye_light.data, 'energy', f / FPS, 260.0 * v, interp=ip)
        # tongue parts hide when retracted
        for o in self.tongue_parts:
            o.hide_render = True
            o.keyframe_insert('hide_render', frame=g[0][0] - 1)
            last = None
            for f, v in tng_keys:
                h = v < 0.05
                if h != last:
                    o.hide_render = h
                    o.keyframe_insert('hide_render', frame=f)
                    last = h
            for fc in kit.fcurves(o):
                for kp in fc.keyframe_points:
                    kp.interpolation = 'CONSTANT'


def _env(t, pts):
    if t <= pts[0][0]:
        return pts[0][1]
    for (a, va), (b, vb) in zip(pts, pts[1:]):
        if t <= b:
            u = (t - a) / (b - a)
            u = u * u * (3 - 2 * u)
            return va + (vb - va) * u
    return pts[-1][1]


def stir(b):
    """The end of `sydney` (the water reaches the plug at 61.3): the cable ripples, the plug lifts and turns, its
    LED eyes flicker on. `moon` calls this first and extends the controls after 62.053."""
    h_end = math.degrees(b.rest_head[-1])
    b.ripple = lambda t: 0.0 if t < 61.35 else 0.35 * math.sin(math.pi * min(1.0, (t - 61.35) / 0.7)) + \
        (0.25 * min(1.0, (t - 62.0) / 0.1) if t > 62.0 else 0.0)
    b.lift = lambda t: _env(t, [(61.3, 0.0), (61.42, 0.7), (61.55, 0.35), (61.85, 1.6), (62.1, 2.2)])
    b.aim = lambda t: _env(t, [(61.5, h_end), (62.0, h_end - 35.0)])
    b.rear = lambda t: _env(t, [(61.7, 0.0), (62.1, 0.08)])
    b.eyes = lambda t: 0.0 if t < 61.72 else ((1.5 if int(t * FPS) % 3 else 0.2) if t < 61.95 else 1.8)
    return b


def _sm(a, b, x):
    if b <= a:
        return float(x >= b)
    u = min(max((x - a) / (b - a), 0.0), 1.0)
    return u * u * (3 - 2 * u)


def _braid_tree(name, turns, length):
    """Spine curve -> three twisted cable strands + zip ties every TIE_EVERY cm (tails up like spines)."""
    g = N.Tree(f'{name}.braid')
    geo_in = g.input_geometry()
    crv = g.out(g.node('GeometryNodeResampleCurve', inputs={'Curve': geo_in, 'Count': 420}))
    fac = g.out(g.node('GeometryNodeSplineParameter'), 'Factor')
    crv = g.out(g.node('GeometryNodeSetCurveTilt', inputs={'Curve': crv, 'Tilt': fac * (turns * 2 * math.pi)}))
    # the profile: three strands at 120 degrees
    prof = None
    for k in range(3):
        a = 2 * math.pi * k / 3
        circ = g.out(g.node('GeometryNodeCurvePrimitiveCircle', inputs={'Resolution': 12, 'Radius': STRAND_R}))
        circ = g.out(g.node('GeometryNodeTransform', inputs={'Geometry': circ,
                                                             'Translation': (0.33 * math.cos(a), 0.33 * math.sin(a),
                                                                             0.0)}))
        circ = g.store(circ, 'mi', float(k), domain='CURVE')
        prof = circ if prof is None else g.join(prof, circ)
    mesh = g.out(g.node('GeometryNodeCurveToMesh', inputs={'Curve': crv, 'Profile Curve': prof, 'Fill Caps': True}))
    mi = g.out(g.node('GeometryNodeInputNamedAttribute', data_type='FLOAT', inputs={'Name': 'mi'}), 'Attribute')
    mi_i = g.out(g.node('FunctionNodeFloatToInt', rounding_mode='ROUND', inputs={'Float': mi}))
    mesh = g.out(g.node('GeometryNodeSetMaterialIndex', inputs={'Geometry': mesh, 'Material Index': mi_i}))
    mesh = g.out(g.node('GeometryNodeSetShadeSmooth', inputs={'Geometry': mesh}))
    # zip ties
    n_ties = max(2, int(length / TIE_EVERY))
    tie_pts = g.out(g.node('GeometryNodeResampleCurve', inputs={'Curve': geo_in, 'Count': n_ties}))
    ctp = g.node('GeometryNodeCurveToPoints', mode='EVALUATED', inputs={'Curve': tie_pts})
    tie_pts, tan = g.out(ctp, 'Points'), g.out(ctp, 'Tangent')
    rot = g.align(tan, 'Y')
    rot = g.align(g.vec(0.0, 0.0, 1.0), 'Z', rotation=rot, pivot='Y')
    tie = _tie_proto(name)
    # skip the ties nearest the port and the head
    idx = g.index()
    sel = g.bool_and(idx > 0, idx < n_ties - 2)
    inst = g.instance(tie_pts, g.object_geo(tie, as_instance=True, relative=False), rotation=rot, selection=sel)
    real = g.realize(inst)
    real = g.out(g.node('GeometryNodeSetMaterialIndex', inputs={'Geometry': real, 'Material Index': 3}))
    g.output(g.join(mesh, real))
    return g


def _tie_proto(name):
    """A black zip tie around the braid (axis Y): a flat band, the locking head on top, a short tail up and back."""
    ob = bpy.data.objects.get(f'{name}.tie.proto')
    if ob is not None:
        return ob
    verts, faces = [], []
    seg, w, r0, r1 = 20, 0.22, 0.64, 0.72
    for j in range(seg):
        a = 2 * math.pi * j / seg
        for (rr, yy) in ((r0, -w / 2), (r1, -w / 2), (r1, w / 2), (r0, w / 2)):
            verts.append((rr * math.cos(a), yy, rr * math.sin(a)))
    for j in range(seg):
        j2 = (j + 1) % seg
        for k in range(4):
            k2 = (k + 1) % 4
            faces.append((j * 4 + k, j2 * 4 + k, j2 * 4 + k2, j * 4 + k2))
    me = bpy.data.meshes.new(f'{name}.tie.proto')
    me.from_pydata(verts, [], faces)
    me.update()
    pc = kit.collection('basilisk.protos')
    band = bpy.data.objects.new(f'{name}.tie.proto', me)
    pc.objects.link(band)
    head = geo.box(f'{name}.tie.head', (0.42, 0.32, 0.3), (0, 0, 0.82), bev=0.04, coll=pc)
    tail = geo.box(f'{name}.tie.tail', (0.2, 0.06, 1.1), (0, -0.05, 1.42), bev=0.02, coll=pc)
    tail.rotation_euler = (math.radians(-28), 0, 0)
    bpy.context.view_layer.update()
    geo.apply_mods(head)
    geo.apply_mods(tail)
    tail.data.transform(tail.matrix_basis)
    tail.matrix_basis = Matrix.Identity(4)
    head.data.transform(head.matrix_basis)
    head.matrix_basis = Matrix.Identity(4)
    ob = geo.join([band, head, tail], f'{name}.tie.proto')
    for p in ob.data.polygons:
        p.use_smooth = False
    ob.location = (0, 0, 0)
    ob.hide_render = True
    ob.hide_viewport = True
    return ob


# ------------------------------------------------------------------------------------------------ extra desk cables


def extra_cables(coll, *, wiggle=None):
    """Two more cables lying near the basilisk (dressing that stirs with it). Returns their spine objects."""
    specs = [
        ('cable.b', [(-8.0, 34.0, 0.3), (-12.0, 22.0, 0.3), (-22.0, 10.0, 0.3), (-26.0, -2.0, 0.3), (-27.0, -12.0, 0.3),
                     (-25.0, -20.0, 0.3), (-21.5, -23.0, 0.3)], '#1A1A1C', 0.26),
        ('cable.c', [(-31.0, 3.0, 0.24), (-34.0, -3.0, 0.24), (-31.5, -9.0, 0.24), (-26.5, -8.0, 0.24),
                     (-29.0, -2.5, 0.24), (-33.0, -6.0, 0.24)], '#DADAD4', 0.22),
    ]
    out = []
    for nm, pts, col, r in specs:
        rub = M.solid(f'{nm}.rubber', col, rough=0.45, spec=0.4, micro=(10.0, 0.02))
        dense = [tuple(p) for p in geo.catmull([Vector(p) for p in pts], 8)]
        tube = geo.curve_tube(nm, dense, r, coll=coll, m=rub, kind='POLY', bevel_res=3)
        # a USB-C plug on the free end
        end, prev = Vector(dense[-1]), Vector(dense[-3])
        d = (end - prev).normalized()
        plug = geo.box(f'{nm}.plug', (0.7, 2.0, 0.5), tuple(end + d * 1.0), bev=0.18, m=rub, coll=coll)
        plug.rotation_euler = d.to_track_quat('Y', 'Z').to_euler()
        tip = geo.box(f'{nm}.tip', (0.6, 0.75, 0.24), tuple(end + d * 2.35), bev=0.08,
                      m=M.chrome('usb.metal'), coll=coll)
        tip.rotation_euler = plug.rotation_euler
        out.append((tube, plug, tip))
    return out
