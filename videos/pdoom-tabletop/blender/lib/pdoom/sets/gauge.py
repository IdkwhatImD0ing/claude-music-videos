"""The P(doom) gauge: a brass analog dial (0-100) on a small walnut plinth, red needle, glass that can crack.

  g = build_gauge(coll, loc=(24, 14, 0), yaw_deg=-18)
  g.set(t, value)          # needle swings to value with a mechanical overshoot-and-settle (keys every frame)
  g.crack(t)               # the glass cracks from the needle's 100 end (radial + ring cracks spread in ~0.3 s)
  g.jolt(t, amp_deg=3)     # the whole instrument jumps (a knock)
  g.tremble(t0, t1, amp)   # the needle quivers around its value (anticipation)
  g.value_at(t)            # what the needle reads at song time t (from the events keyed so far)
  g.history()              # key the song's four DOOM jumps and the crack (build_desk does this by default)

The needle is re-keyed from the whole event list after every call, so calls can come in any order.
"""
from __future__ import annotations

import math

import bpy
from mathutils import Vector

from .. import kit
from ..timing import FPS
from . import geo
from . import materials as M

# the song's DOOM jumps (treatment §4): time -> value; the glass cracks on the last one
DOOMS = [(23.873, 25.0), (60.235, 50.0), (96.596, 75.0), (125.686, 100.0)]
CRACK_T = 125.686

SWEEP = 270.0          # degrees of dial arc
R_CASE = 6.0           # cm: case radius
R_FACE = 5.25
DIAL_H = 8.6           # cm: dial centre height above the desk (on its plinth)
TILT = 9.0             # degrees the dial leans back


def dial_angle(v: float) -> float:
    """Clockwise angle from 12 o'clock (radians) for a dial value (0 at lower left, 100 at lower right)."""
    return math.radians(-SWEEP / 2 + SWEEP * v / 100.0)


class Gauge:
    def __init__(self):
        self.root = None      # Empty on the desk (move/rotate this)
        self.jolt_empty = None
        self.dial = None      # Empty at the dial centre: X right, Y up, Z out of the face
        self.needle = None
        self.glass = None
        self.glass_mat = None
        self.crack_amount = None   # Value sockets (keyed)
        self.crack_radius = None
        self.initial = 0.0
        self.events: list[tuple[float, float, dict]] = []   # (t, value, params)
        self.cracks: list[float] = []
        self.objects = []

    # -------------------------------------------------------------------------------------------- needle
    def _response(self, a: float, b: float, tau: float, freq: float, zeta: float) -> float:
        """Step response of a damped needle from a to b, tau seconds after the kick (zero initial velocity)."""
        if tau <= 0:
            return a
        w = 2 * math.pi * freq
        wd = w * math.sqrt(1 - zeta * zeta)
        e = math.exp(-zeta * w * tau)
        x = b - (b - a) * e * (math.cos(wd * tau) + zeta / math.sqrt(1 - zeta * zeta) * math.sin(wd * tau))
        # the stop pins just past 0 and 100: bounce off them
        hi, lo = 101.8, -1.8
        if x > hi:
            x = hi - (x - hi) * 0.35
        if x < lo:
            x = lo + (lo - x) * 0.35
        return x

    def value_at(self, t: float) -> float:
        """The needle's reading at song time t (each event starts from wherever the previous swing had got to)."""
        cur = None   # (t_event, from, to, params)
        for te, ve, p in sorted(self.events, key=lambda e: e[0]):
            if te > t + 1e-9:
                break
            a = self.initial if cur is None else self._response(cur[1], cur[2], te - cur[0], cur[3]['freq'], cur[3]['zeta'])
            cur = (te, a, ve, p)
        if cur is None:
            return self.initial
        return self._response(cur[1], cur[2], t - cur[0], cur[3]['freq'], cur[3]['zeta'])

    def set(self, t: float, value: float, *, freq: float = 3.0, zeta: float = 0.3, settle: float = 1.6):
        """Needle to value at song time t: a hard swing (31 % of the way in one frame), overshoot, damped settle."""
        self.events.append((t, float(value), {'freq': freq, 'zeta': zeta, 'settle': settle}))
        self._rekey()
        return self

    def clear(self, initial: float | None = None):
        """Drop every needle event (and the crack) so a scene can key its own story."""
        if initial is not None:
            self.initial = initial
        self.events = []
        self._rekey()
        return self

    def _rekey(self):
        n = self.needle
        geo.clear_keys(n, 'rotation_euler')
        n.rotation_euler = (0, 0, -dial_angle(self.initial))
        sc = bpy.context.scene
        evs = sorted(self.events, key=lambda e: e[0])
        # the resting value, keyed just before the first event (or at the scene start if there are none); constant
        # extrapolation holds it before that
        t_init = evs[0][0] - 1e-3 if evs else sc.frame_start / FPS - 1.0
        geo.keyp(n, 'rotation_euler', t_init, index=2, interp='LINEAR')
        for i, (te, ve, p) in enumerate(evs):
            t_end = evs[i + 1][0] if i + 1 < len(evs) else te + p['settle'] + 1.0
            t_stop = min(te + p['settle'], t_end)
            k = 0
            while True:
                tt = te + k / FPS
                if tt > t_stop - 1e-6:
                    break
                n.rotation_euler[2] = -dial_angle(self.value_at(tt))
                geo.keyp(n, 'rotation_euler', tt, index=2, interp='LINEAR')
                k += 1
            # hold until the next event (key just before it so the next swing starts from rest)
            tt = t_stop
            n.rotation_euler[2] = -dial_angle(self.value_at(tt))
            geo.keyp(n, 'rotation_euler', tt, index=2, interp='LINEAR')
            if i + 1 < len(evs):
                geo.keyp(n, 'rotation_euler', evs[i + 1][0] - 1e-3, index=2, interp='LINEAR')
        self._tremble_keys()

    # -------------------------------------------------------------------------------------------- extras
    _trembles: list = None

    def tremble(self, t0: float, t1: float, amp: float = 0.6, rate: float = 14.0, seed: int = 1):
        """Needle quivers around its value between t0 and t1 (value units). Keys every frame; don't overlap a set()."""
        if self._trembles is None:
            self._trembles = []
        self._trembles.append((t0, t1, amp, rate, seed))
        self._rekey()
        return self

    def _tremble_keys(self):
        n = self.needle
        for (t0, t1, amp, rate, seed) in (self._trembles or []):
            k = 0
            while t0 + k / FPS <= t1:
                tt = t0 + k / FPS
                env = math.sin(math.pi * (tt - t0) / max(t1 - t0, 1e-3))
                wob = math.sin(2 * math.pi * rate * tt + seed) * 0.6 + math.sin(2 * math.pi * rate * 1.73 * tt + seed * 2) * 0.4
                n.rotation_euler[2] = -dial_angle(self.value_at(tt) + amp * env * wob)
                geo.keyp(n, 'rotation_euler', tt, index=2, interp='LINEAR')
                k += 1

    def jolt(self, t: float, amp_deg: float = 3.0, dur: float = 0.35):
        """The instrument jumps on its plinth: a quick damped rock about its base."""
        j = self.jolt_empty
        geo.keyp(j, 'rotation_euler', t - 1 / FPS, (0, 0, 0), interp='LINEAR')
        k = 0
        while k / FPS <= dur:
            tau = k / FPS
            e = math.exp(-tau * 9.0)
            a = math.radians(amp_deg) * e * math.sin(2 * math.pi * 7.0 * tau + 0.9)
            b = math.radians(amp_deg * 0.5) * e * math.sin(2 * math.pi * 9.0 * tau + 0.2)
            geo.keyp(j, 'rotation_euler', t + tau, (a, b, 0), interp='LINEAR')
            k += 1
        geo.keyp(j, 'rotation_euler', t + dur + 1 / FPS, (0, 0, 0), interp='LINEAR')
        return self

    def crack(self, t: float, *, spread: float = 0.3, jolt: bool = True):
        """The glass cracks at t from the lower right (where the needle slams into its 100 pin)."""
        self.cracks.append(t)
        amt, rad = self.crack_amount, self.crack_radius
        geo.keyp(amt, 'default_value', t - 1 / FPS, 0.0, interp='CONSTANT')
        geo.keyp(amt, 'default_value', t, 1.0, interp='CONSTANT')
        geo.keyp(rad, 'default_value', t - 1 / FPS, 0.0, interp='LINEAR')
        geo.keyp(rad, 'default_value', t, 2.2, interp='LINEAR')
        geo.keyp(rad, 'default_value', t + 2 / FPS, 6.0, interp='BEZIER')
        geo.keyp(rad, 'default_value', t + spread, 8.5, interp='BEZIER')
        if jolt:
            self.jolt(t, 2.5)
        return self

    def history(self):
        """The song's canonical gauge: 0 until DOOM 1, then 25, 50, 75, 100 and the crack."""
        for t, v in DOOMS:
            self.events.append((t, v, {'freq': 3.0, 'zeta': 0.3, 'settle': 1.6}))
        self._rekey()
        self.crack(CRACK_T)
        return self

    def front(self, dist: float = 25.0) -> Vector:
        """A world point `dist` cm in front of the dial centre along its face normal (for cameras)."""
        mw = self.dial.matrix_world
        return mw @ Vector((0, 0, dist))

    def center(self) -> Vector:
        return self.dial.matrix_world.translation.copy()


# ------------------------------------------------------------------------------------------------ build


def _glass_material(name='gauge.glass', impact=(3.2, -3.0)):
    """Clear glass with a keyed crack: polar Voronoi edges (radial + ring cracks) masked by a growing radius."""
    m, fresh = M.new_mat(name)
    nt = m.node_tree
    b = M.principled(m)
    M.setin(b, 'Base Color', (1, 1, 1, 1))
    M.setin(b, 'Roughness', 0.03)
    M.setin(b, 'Transmission Weight', 1.0)
    M.setin(b, 'IOR', 1.5)
    M.setin(b, 'Thin Wall', True)
    M.glassify(m)
    out = nt.nodes.get('Material Output')
    N, S, L = M.node, M.sin, M.sout
    tc = N(nt, 'ShaderNodeTexCoord', (-1800, 0))
    sep = N(nt, 'ShaderNodeSeparateXYZ', (-1600, 0))
    M.link(nt, L(tc, 'Object'), S(sep, 'Vector'))
    dx = N(nt, 'ShaderNodeMath', (-1400, 100), operation='SUBTRACT')
    M.link(nt, L(sep, 'X'), dx.inputs[0])
    dx.inputs[1].default_value = impact[0]
    dy = N(nt, 'ShaderNodeMath', (-1400, -100), operation='SUBTRACT')
    M.link(nt, L(sep, 'Y'), dy.inputs[0])
    dy.inputs[1].default_value = impact[1]
    cmb = N(nt, 'ShaderNodeCombineXYZ', (-1200, 0))
    M.link(nt, dx.outputs[0], S(cmb, 'X'))
    M.link(nt, dy.outputs[0], S(cmb, 'Y'))
    rlen = N(nt, 'ShaderNodeVectorMath', (-1000, 0), operation='LENGTH')
    M.link(nt, L(cmb, 'Vector'), rlen.inputs[0])
    r = L(rlen, 'Value')
    ang = N(nt, 'ShaderNodeMath', (-1000, 200), operation='ARCTAN2')
    M.link(nt, dy.outputs[0], ang.inputs[0])
    M.link(nt, dx.outputs[0], ang.inputs[1])
    # polar coordinates: (angle * k, log(r) * k2) -> Voronoi cells become radial shards and rings
    rr = N(nt, 'ShaderNodeMath', (-800, -100), operation='ADD')
    M.link(nt, r, rr.inputs[0])
    rr.inputs[1].default_value = 0.12
    lg = N(nt, 'ShaderNodeMath', (-600, -100), operation='LOGARITHM')
    M.link(nt, rr.outputs[0], lg.inputs[0])
    lg.inputs[1].default_value = 2.718281828
    ka = N(nt, 'ShaderNodeMath', (-600, 200), operation='MULTIPLY')
    M.link(nt, ang.outputs[0], ka.inputs[0])
    ka.inputs[1].default_value = 4.6
    kr = N(nt, 'ShaderNodeMath', (-400, -100), operation='MULTIPLY')
    M.link(nt, lg.outputs[0], kr.inputs[0])
    kr.inputs[1].default_value = 1.15
    pol = N(nt, 'ShaderNodeCombineXYZ', (-200, 0))
    M.link(nt, ka.outputs[0], S(pol, 'X'))
    M.link(nt, kr.outputs[0], S(pol, 'Y'))
    vor = N(nt, 'ShaderNodeTexVoronoi', (0, 0))
    vor.feature = 'DISTANCE_TO_EDGE'
    M.setin(vor, 'Scale', 1.0)
    M.setin(vor, 'Randomness', 0.85)
    M.link(nt, L(pol, 'Vector'), S(vor, 'Vector'))
    line = N(nt, 'ShaderNodeMapRange', (200, 0))
    M.setin(line, 'From Min', 0.0, 'VALUE')
    M.setin(line, 'From Max', 0.035, 'VALUE')
    M.setin(line, 'To Min', 1.0, 'VALUE')
    M.setin(line, 'To Max', 0.0, 'VALUE')
    M.link(nt, L(vor, 'Distance'), S(line, 'Value', 'VALUE'))
    # growth mask: r < radius (keyed)
    radv = N(nt, 'ShaderNodeValue', (0, -400))
    radv.label = radv.name = 'crack.radius'
    radv.outputs[0].default_value = 0.0
    lo = N(nt, 'ShaderNodeMath', (200, -400), operation='MULTIPLY')
    M.link(nt, radv.outputs[0], lo.inputs[0])
    lo.inputs[1].default_value = 0.75
    grow = N(nt, 'ShaderNodeMapRange', (400, -300))
    M.link(nt, r, S(grow, 'Value', 'VALUE'))
    M.link(nt, lo.outputs[0], S(grow, 'From Min', 'VALUE'))
    M.link(nt, radv.outputs[0], S(grow, 'From Max', 'VALUE'))
    M.setin(grow, 'To Min', 1.0, 'VALUE')
    M.setin(grow, 'To Max', 0.0, 'VALUE')
    amt = N(nt, 'ShaderNodeValue', (400, -500))
    amt.label = amt.name = 'crack.amount'
    amt.outputs[0].default_value = 0.0
    m1 = N(nt, 'ShaderNodeMath', (600, -100), operation='MULTIPLY')
    M.link(nt, L(line, 'Result', 'VALUE'), m1.inputs[0])
    M.link(nt, L(grow, 'Result', 'VALUE'), m1.inputs[1])
    m2 = N(nt, 'ShaderNodeMath', (800, -100), operation='MULTIPLY')
    M.link(nt, m1.outputs[0], m2.inputs[0])
    M.link(nt, amt.outputs[0], m2.inputs[1])
    crackv = m2.outputs[0]
    # cracked glass: a white, rough, partly opaque fracture surface; the clear glass is bumped along the cracks
    b2 = N(nt, 'ShaderNodeBsdfPrincipled', (800, 300))
    M.setin(b2, 'Base Color', (0.95, 0.97, 1.0, 1))
    M.setin(b2, 'Roughness', 0.25)
    M.setin(b2, 'Transmission Weight', 0.35)
    M.setin(b2, 'Coat Weight', 0.0)
    M.setin(b2, 'Emission Color', (1, 1, 1, 1))
    M.setin(b2, 'Emission Strength', 0.0)
    bump = N(nt, 'ShaderNodeBump', (800, -300))
    M.setin(bump, 'Strength', 0.6)
    M.setin(bump, 'Distance', 0.05)
    M.link(nt, crackv, S(bump, 'Height'))
    M.link(nt, L(bump, 'Normal'), S(b, 'Normal'))
    M.link(nt, L(bump, 'Normal'), S(b2, 'Normal'))
    # a faint film of dust / fingerprints so the glass reads as glass when light rakes across it
    dn = N(nt, 'ShaderNodeTexNoise', (400, 500))
    M.setin(dn, 'Scale', 1.3)
    M.setin(dn, 'Detail', 8.0)
    M.link(nt, L(tc, 'Object'), S(dn, 'Vector'))
    dm = N(nt, 'ShaderNodeMapRange', (600, 500))
    M.setin(dm, 'From Min', 0.45, 'VALUE')
    M.setin(dm, 'From Max', 0.75, 'VALUE')
    M.setin(dm, 'To Min', 0.0, 'VALUE')
    M.setin(dm, 'To Max', 0.07, 'VALUE')
    M.link(nt, L(dn, 'Factor'), S(dm, 'Value', 'VALUE'))
    tot = N(nt, 'ShaderNodeMath', (900, 200), operation='ADD')
    M.link(nt, crackv, tot.inputs[0])
    M.link(nt, L(dm, 'Result', 'VALUE'), tot.inputs[1])
    tot.use_clamp = True
    crackv_mix = tot.outputs[0]
    mix = N(nt, 'ShaderNodeMixShader', (1100, 0))
    M.link(nt, crackv_mix, mix.inputs[0])
    M.link(nt, L(b, 'BSDF'), mix.inputs[1])
    M.link(nt, L(b2, 'BSDF'), mix.inputs[2])
    M.link(nt, mix.outputs[0], out.inputs['Surface'])
    out.location = (1300, 0)
    return m, amt.outputs[0], radv.outputs[0]


def _dial_face_mat():
    """Aged cream card with a faint darkening towards the rim."""
    m, fresh = M.new_mat('gauge.face')
    if not fresh:
        return m
    nt = m.node_tree
    b = M.principled(m)
    M.setin(b, 'Roughness', 0.55)
    M.setin(b, 'Specular IOR Level', 0.35)
    tc = M.node(nt, 'ShaderNodeTexCoord', (-900, 0))
    ln = M.node(nt, 'ShaderNodeVectorMath', (-700, 0), operation='LENGTH')
    M.link(nt, M.sout(tc, 'Object'), ln.inputs[0])
    mr = M.node(nt, 'ShaderNodeMapRange', (-500, 0))
    M.setin(mr, 'From Min', 2.5, 'VALUE')
    M.setin(mr, 'From Max', R_FACE, 'VALUE')
    M.link(nt, M.sout(ln, 'Value'), M.sin(mr, 'Value', 'VALUE'))
    nz = M.node(nt, 'ShaderNodeTexNoise', (-500, 250))
    M.setin(nz, 'Scale', 1.2)
    M.setin(nz, 'Detail', 6)
    M.link(nt, M.sout(tc, 'Object'), M.sin(nz, 'Vector'))
    mx = M.node(nt, 'ShaderNodeMix', (-250, 100), data_type='RGBA', blend_type='MIX')
    M.link(nt, M.sout(mr, 'Result', 'VALUE'), M.sin(mx, 'Factor', 'VALUE'))
    M.setin(mx, 'A', kit.srgb('#F1E8D2'), 'RGBA')
    M.setin(mx, 'B', kit.srgb('#CDBB93'), 'RGBA')
    mx2 = M.node(nt, 'ShaderNodeMix', (-50, 100), data_type='RGBA', blend_type='MULTIPLY')
    M.setin(mx2, 'Factor', 0.12, 'VALUE')
    M.link(nt, M.sout(mx, 'Result', 'RGBA'), M.sin(mx2, 'A', 'RGBA'))
    M.link(nt, M.sout(nz, 'Color'), M.sin(mx2, 'B', 'RGBA'))
    M.link(nt, M.sout(mx2, 'Result', 'RGBA'), M.sin(b, 'Base Color'))
    m.diffuse_color = kit.srgb('#F1E8D2')
    return m


def build_gauge(coll, loc=(24, 14, 0), yaw_deg: float = -18.0, *, initial: float = 0.0) -> Gauge:
    g = Gauge()
    g.initial = initial
    brass = M.brass('gauge.brass')
    dark_brass = M.brass('gauge.brassdark', '#8E6B35', 0.35)
    ink = M.ink('gauge.ink', '#1C1712', 0.5)
    red_ink = M.solid('gauge.redink', '#B8322A', rough=0.5)
    needle_m = M.enamel('gauge.needle', kit.PAL['red'], rough=0.25, coat=0.6)
    plinth_m = M.tex_mat('gauge.plinth', 'desk_wood', 60, hue=0.5, sat=0.8, val=0.55, rough=(0.25, 0.45), normal=0.5,
                         coat=0.8, coat_rough=0.05, fallback='#3A2418')
    felt_m = M.felt('gauge.felt', '#243A2E')

    root = geo.empty('gauge', loc, coll, 4.0, 'ARROWS', rot=(0, 0, math.radians(yaw_deg)))
    g.root = root
    # plinth: a lacquered block with a felt pad under it
    pl = geo.box('gauge.plinth', (14.0, 7.5, 2.2), (0, 0, 1.2), bev=0.35, segments=4, m=plinth_m, coll=coll)
    geo.attach(pl, root, (0, 0, 1.2))
    pad = geo.box('gauge.felt', (13.4, 7.0, 0.2), (0, 0, 0.1), m=felt_m, coll=coll)
    geo.attach(pad, root, (0, 0, 0.1))
    # the jolt pivot at the plinth top, then the dial frame (tilted back)
    jolt = geo.empty('gauge.jolt', (0, 0, 2.3), coll, 1.0)
    geo.attach(jolt, root, (0, 0, 2.3))
    g.jolt_empty = jolt
    dial = geo.empty('gauge.dial', (0, 0, 0), coll, 3.0, 'ARROWS')
    geo.attach(dial, jolt, (0, 0.6, DIAL_H - 2.3), (math.radians(90 - TILT), 0, 0))
    g.dial = dial
    # feet: two brass brackets from the plinth to the case
    for s in (-1, 1):
        ft = geo.lathe(f'gauge.foot{s}', [(0, 0), (0.9, 0), (0.9, 0.25), (0.35, 0.5), (0.35, 3.2), (0.0, 3.2)], segs=24,
                       coll=coll, m=brass)
        geo.attach(ft, jolt, (s * 3.4, 0.9, 0.0))
    # case: back, wall, bezel lip (lathe along the dial's Z = out of the face)
    prof = geo.rounded_profile([(0.0, -1.6), (R_CASE - 0.6, -1.6), (R_CASE, -1.1), (R_CASE, 0.55), (R_CASE + 0.15, 0.75),
                                (R_CASE - 0.1, 1.0), (R_FACE + 0.05, 0.95), (R_FACE, 0.2), (0.0, 0.2)], 0.25, 3)
    case = geo.lathe('gauge.case', prof, segs=96, coll=coll, m=brass)
    geo.attach(case, dial)
    ring = geo.lathe('gauge.ring', [(R_FACE - 0.02, 0.21), (R_FACE - 0.45, 0.21), (R_FACE - 0.45, 0.26),
                                    (R_FACE - 0.02, 0.26)], segs=96, coll=coll, m=dark_brass, smooth=False)
    geo.attach(ring, dial)
    # face
    face = geo.lathe('gauge.face', [(0.0, 0.215), (R_FACE - 0.4, 0.215)], segs=96, coll=coll, m=_dial_face_mat())
    geo.attach(face, dial)
    z_ink = 0.222
    marks = []
    # ticks: major every 10, minor every 2; red band 75-100
    tick_verts, tick_faces = [], []

    def quad(cx, cy, ang, length, width, r_out, z):
        # a tick of `length` ending at radius r_out along angle ang (clockwise from up)
        s, c = math.sin(ang), math.cos(ang)
        ux, uy = s, c            # radial
        vx, vy = c, -s           # tangential
        r0, r1 = r_out - length, r_out
        base = len(tick_verts)
        for rr, ww in ((r0, -width / 2), (r1, -width / 2), (r1, width / 2), (r0, width / 2)):
            tick_verts.append((cx + ux * rr + vx * ww, cy + uy * rr + vy * ww, z))
        tick_faces.append((base, base + 3, base + 2, base + 1))

    for i in range(51):
        v = i * 2
        a = dial_angle(v)
        major = v % 10 == 0
        quad(0, 0, a, 0.62 if major else 0.32, 0.085 if major else 0.04, 4.72, z_ink)
    ticks = geo.mesh_obj('gauge.ticks', tick_verts, tick_faces, coll, ink)
    geo.attach(ticks, dial)
    # red zone arc (75-100) just inside the tick ring
    band_v, band_f = [], []
    steps = 40
    for k in range(steps + 1):
        a = dial_angle(75 + 25 * k / steps)
        s, c = math.sin(a), math.cos(a)
        band_v += [(s * 3.88, c * 3.88, z_ink - 0.002), (s * 4.06, c * 4.06, z_ink - 0.002)]
        if k:
            j = 2 * k
            band_f.append((j - 2, j - 1, j + 1, j))
    band = geo.mesh_obj('gauge.redzone', band_v, band_f, coll, red_ink)
    geo.attach(band, dial)
    # numerals
    for v in range(0, 101, 10):
        a = dial_angle(v)
        tx = geo.text_mesh(f'gauge.n{v}', str(v), 0.66, coll=coll, m=ink)
        geo.attach(tx, dial, (math.sin(a) * 3.45, math.cos(a) * 3.45 - 0.02, z_ink))
        marks.append(tx)
    lab = geo.text_mesh('gauge.label', 'P(doom)', 0.95, coll=coll, m=ink)
    geo.attach(lab, dial, (0, -1.85, z_ink))
    pct = geo.text_mesh('gauge.pct', '%', 0.5, coll=coll, m=red_ink)
    geo.attach(pct, dial, (0, -2.75, z_ink))
    # needle: a pivot at the centre; tip up (+Y) at rotation 0
    npiv = geo.empty('gauge.needle', (0, 0, 0), coll, 1.0)
    geo.attach(npiv, dial, (0, 0, 0.42))
    poly = [(-0.16, -1.25), (0.16, -1.25), (0.12, 0.0), (0.035, 4.35), (0.0, 4.55), (-0.035, 4.35), (-0.12, 0.0)]
    nd = geo.prism('gauge.needle.blade', poly, 0.05, coll=coll, m=needle_m)
    geo.attach(nd, npiv)
    tail = geo.lathe('gauge.needle.tail', [(0.0, -0.02), (0.38, -0.02), (0.38, 0.08), (0.0, 0.08)], segs=24, coll=coll,
                     m=needle_m)
    geo.attach(tail, npiv, (0, -1.2, 0))
    hub = geo.lathe('gauge.hub', [(0.0, -0.25), (0.42, -0.25), (0.42, 0.1), (0.3, 0.22), (0.0, 0.26)], segs=32,
                    coll=coll, m=brass)
    geo.attach(hub, npiv, (0, 0, 0.02))
    g.needle = npiv
    # stop pins at 0 and 100
    for v in (-2.5, 102.5):
        a = dial_angle(v)
        pin = geo.lathe(f'gauge.pin{v:g}', [(0, 0), (0.09, 0), (0.09, 0.26), (0.06, 0.3), (0, 0.3)], segs=12, coll=coll, m=brass)
        geo.attach(pin, dial, (math.sin(a) * 4.0, math.cos(a) * 4.0, 0.22))
    # glass: a very slight dome under the bezel lip
    gm, amt, rad = _glass_material()
    gprof = [(0.0, 0.93), (R_FACE * 0.5, 0.91), (R_FACE * 0.85, 0.86), (R_FACE + 0.08, 0.8)]
    gl = geo.lathe('gauge.glass', gprof, segs=96, coll=coll, m=gm)
    geo.attach(gl, dial)
    gl.visible_shadow = False
    g.glass, g.glass_mat, g.crack_amount, g.crack_radius = gl, gm, amt, rad
    g.needle.rotation_euler = (0, 0, -dial_angle(initial))
    g.objects = geo.descendants(root)
    return g
