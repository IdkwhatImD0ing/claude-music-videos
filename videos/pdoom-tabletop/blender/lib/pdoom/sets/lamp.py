"""The articulated desk lamp (an Anglepoise-style enamel lamp with springs): the warm key light of the desk.

  lamp = build_lamp(coll, base=(50, 26, 0), aim=(6, -4, 0))
  lamp.aim(t, target, reach=34, height=40)   # IK pose: head joint at (reach, height) from the base, shade on target
  lamp.pose(t, shoulder=5, elbow=84, head=65, yaw=None)   # or key the joint angles directly (degrees)
  lamp.click(t, on=True)                      # the base button clicks; the bulb snaps on (or off) over 2 frames
  lamp.flicker(t0, t1, depth=0.7, rate=12)    # a failing-contact flicker (deterministic)
  lamp.intensity(t, v, interp='LINEAR')       # key the brightness 0..1 (light, bulb and shade glow together)

Joints (Empties you can also key yourself): lamp.root (yaw about Z), lamp.shoulder, lamp.elbow, lamp.head (pitch about
their local Y; + tips forward). The spot light (lamp.light) sits in the shade and follows the head.
"""
from __future__ import annotations

import math

import bpy
from mathutils import Vector

from .. import kit
from ..timing import FPS
from . import geo
from . import materials as M

L1, L2 = 34.0, 31.0      # arm lengths (cm)
SHOULDER_Z = 5.4
KEY_COLOR = kit.PAL['glow']


class Lamp:
    def __init__(self):
        self.root = self.shoulder = self.elbow = self.head = None
        self.light = None
        self.bulb_socket = None      # emission strength sockets (keyed with intensity)
        self.inner_socket = None
        self.button = None
        self.full_power = 1.0        # set by lighting(): watts at intensity 1
        self.bulb_full = 60.0
        self.inner_full = 1.2
        self.level = 1.0
        self.objects = []

    # -------------------------------------------------------------------------------------------- brightness
    def _apply(self, v: float):
        self.light.data.energy = self.full_power * v
        self.bulb_socket.default_value = self.bulb_full * v
        self.inner_socket.default_value = self.inner_full * v

    def set_level(self, v: float):
        """Static brightness (no keys): 1 on, 0 off. lighting() uses this."""
        self.level = v
        self._apply(v)

    def intensity(self, t: float, v: float, interp: str = 'LINEAR'):
        self._apply(v)
        geo.keyp(self.light.data, 'energy', t, interp=interp)
        geo.keyp(self.bulb_socket, 'default_value', t, interp=interp)
        geo.keyp(self.inner_socket, 'default_value', t, interp=interp)
        return self

    def click(self, t: float, on: bool = True, *, button: bool = True):
        """Switch on (or off) at song time t: dark until t, then a two-frame filament snap. Also presses the button."""
        f = 1.0 / FPS
        if on:
            self.intensity(t - f * 0.5, 0.0, 'CONSTANT')
            self.intensity(t, 0.55, 'LINEAR')
            self.intensity(t + f, 1.08, 'LINEAR')
            self.intensity(t + 2 * f, 0.97, 'LINEAR')
            self.intensity(t + 3 * f, 1.0, 'LINEAR')
        else:
            self.intensity(t - f * 0.5, 1.0, 'CONSTANT')
            self.intensity(t, 0.35, 'LINEAR')
            self.intensity(t + f, 0.08, 'LINEAR')
            self.intensity(t + 2 * f, 0.0, 'LINEAR')
        if button and self.button is not None:
            b = self.button
            z0 = b['z0']
            geo.keyp(b, 'location', t - 3 * f, z0, index=2, interp='LINEAR')
            geo.keyp(b, 'location', t, z0 - 0.28, index=2, interp='LINEAR')
            geo.keyp(b, 'location', t + 3 * f, z0, index=2, interp='LINEAR')
        return self

    def flicker(self, t0: float, t1: float, *, depth: float = 0.7, rate: float = 12.0, seed: int = 7, dropouts=0.25,
                end: float = 1.0):
        """A bad-contact flicker from t0 to t1 (keys every frame): dips of up to `depth`, some full dropouts."""
        k = 0
        n = max(1, int((t1 - t0) * FPS))
        while k <= n:
            t = t0 + k / FPS
            h = geo.hash01('flicker', seed, k // max(1, int(FPS / rate)))
            v = 1.0 - depth * h
            if geo.hash01('drop', seed, k) < dropouts * (1 - k / (n + 1)):
                v = 0.04
            if k == n:
                v = end
            self.intensity(t, v, 'CONSTANT')
            k += 1
        return self

    # -------------------------------------------------------------------------------------------- pose
    def pose(self, t: float | None = None, *, shoulder=None, elbow=None, head=None, yaw=None, interp='BEZIER'):
        """Joint angles in degrees (keyed at t if given)."""
        for obj, val, idx in ((self.shoulder, shoulder, 1), (self.elbow, elbow, 1), (self.head, head, 1),
                              (self.root, yaw, 2)):
            if val is None:
                continue
            obj.rotation_euler[idx] = math.radians(val)
            if t is not None:
                geo.keyp(obj, 'rotation_euler', t, index=idx, interp=interp)
        return self

    def solve(self, target, reach: float = 34.0, height: float = 40.0):
        """IK: angles (yaw, shoulder, elbow, head) in degrees that put the head joint `reach` cm out from the base
        towards target (horizontally) at `height` above the base, with the shade pointing at target."""
        base = Vector(self.base_loc)
        T = Vector(target)
        d = T - base
        yaw = math.atan2(d.y, d.x)
        tx = math.hypot(d.x, d.y)
        tz = d.z
        hx, hz = reach, height
        sx, sz = 0.0, SHOULDER_Z
        vx, vz = hx - sx, hz - sz
        D = min(math.hypot(vx, vz), L1 + L2 - 1e-3)
        phi = math.atan2(vx, vz)
        alpha = math.acos(max(-1, min(1, (L1 * L1 + D * D - L2 * L2) / (2 * L1 * D))))
        beta = math.acos(max(-1, min(1, (L1 * L1 + L2 * L2 - D * D) / (2 * L1 * L2))))
        s = phi - alpha
        e = math.pi - beta
        psi = math.atan2(tx - hx, tz - hz)
        h = psi - (s + e)
        return tuple(math.degrees(a) for a in (yaw, s, e, h))

    def aim(self, t: float | None, target, *, reach: float = 34.0, height: float = 40.0, interp='BEZIER'):
        yaw, s, e, h = self.solve(target, reach, height)
        return self.pose(t, shoulder=s, elbow=e, head=h, yaw=yaw, interp=interp)

    def head_point(self) -> Vector:
        return self.light.matrix_world.translation.copy()


def build_lamp(coll, base=(50.0, 26.0, 0.0), aim=(6.0, -4.0, 0.0), *, reach=34.0, height=40.0,
               enamel_color='#2B3530') -> Lamp:
    lp = Lamp()
    lp.base_loc = tuple(base)
    enamel = M.enamel('lamp.enamel', enamel_color, rough=0.3, coat=0.5)
    brass = M.brass('lamp.brass', '#C9A45C', 0.25)
    chrome = M.chrome('lamp.chrome')
    inner, fresh = M.new_mat('lamp.inner')
    bi = M.principled(inner)
    M.setin(bi, 'Base Color', kit.srgb('#EFE6D2'))
    M.setin(bi, 'Roughness', 0.45)
    M.setin(bi, 'Emission Color', kit.srgb('#FFC47A'))
    M.setin(bi, 'Emission Strength', 1.0)
    bulb = M.emissive('lamp.bulb', '#FFD7A0', 60.0)
    button_m = M.plastic('lamp.button', '#E9E1CF', rough=0.3, coat=0.4)

    root = geo.empty('lamp', base, coll, 5.0, 'ARROWS')
    lp.root = root
    # weighted base (turned), with a push button
    bprof = geo.rounded_profile([(0.0, 0.0), (7.6, 0.0), (7.6, 0.9), (7.0, 1.5), (5.2, 2.1), (1.8, 2.35), (0.0, 2.35)], 0.3, 3)
    b = geo.lathe('lamp.base', bprof, segs=72, coll=coll, m=enamel)
    geo.attach(b, root)
    felt = geo.lathe('lamp.basefelt', [(0.0, -0.001), (7.3, -0.001), (7.3, 0.05), (0.0, 0.05)], segs=48, coll=coll,
                     m=M.felt('lamp.felt', '#1C1C1C'))
    geo.attach(felt, root)
    btn = geo.lathe('lamp.button', [(0.0, 0.0), (0.75, 0.0), (0.75, 0.45), (0.6, 0.6), (0.0, 0.62)], segs=32, coll=coll,
                    m=button_m)
    a = math.radians(125)
    geo.attach(btn, root, (4.3 * math.cos(a), 4.3 * math.sin(a), 1.62))
    btn['z0'] = 1.62
    ring = geo.lathe('lamp.buttonring', [(0.78, 1.6), (1.05, 1.6), (1.05, 1.95), (0.78, 1.95)], segs=32, coll=coll,
                     m=chrome, smooth=False)
    geo.attach(ring, root, (4.3 * math.cos(a), 4.3 * math.sin(a), 0.0))
    lp.button = btn
    col = geo.lathe('lamp.turret', geo.rounded_profile([(0.0, 2.3), (1.5, 2.3), (1.5, 4.6), (1.1, 5.0), (0.0, 5.0)], 0.2),
                    segs=40, coll=coll, m=enamel)
    geo.attach(col, root)
    # shoulder
    sh = geo.empty('lamp.shoulder', (0, 0, SHOULDER_Z), coll, 2.0)
    geo.attach(sh, root, (0, 0, SHOULDER_Z))
    lp.shoulder = sh
    knuck = kit.cylinder('lamp.knuckle.s', 0.95, 3.4, (0, 0, 0), verts=32, m=enamel, coll=coll, rot=(math.pi / 2, 0, 0))
    geo.attach(knuck, sh, (0, 0, 0), (math.pi / 2, 0, 0))
    for s in (-1, 1):
        cap = kit.cylinder(f'lamp.cap.s{s}', 0.6, 0.25, (0, 0, 0), verts=24, m=brass, coll=coll)
        geo.attach(cap, sh, (0, s * 1.82, 0), (math.pi / 2, 0, 0))
    for s in (-1, 1):
        rod = kit.cylinder(f'lamp.rod1.{s}', 0.32, L1, (0, 0, 0), verts=16, m=enamel, coll=coll)
        geo.attach(rod, sh, (0, s * 1.15, L1 / 2))
        sp = geo.curve_tube(f'lamp.spring{s}', geo.helix(22, 0.42, 11.0, 14), 0.07, coll=coll, m=chrome, res=2,
                            bevel_res=2)
        geo.attach(sp, sh, (-1.25, s * 0.65, 1.2))
        hook = kit.cylinder(f'lamp.springrod{s}', 0.07, 6.0, (0, 0, 0), verts=8, m=chrome, coll=coll)
        geo.attach(hook, sh, (-1.25, s * 0.65, 15.0))
    # elbow
    el = geo.empty('lamp.elbow', (0, 0, L1), coll, 2.0)
    geo.attach(el, sh, (0, 0, L1))
    lp.elbow = el
    k2 = kit.cylinder('lamp.knuckle.e', 0.8, 3.0, (0, 0, 0), verts=32, m=enamel, coll=coll)
    geo.attach(k2, el, (0, 0, 0), (math.pi / 2, 0, 0))
    for s in (-1, 1):
        cap = kit.cylinder(f'lamp.cap.e{s}', 0.5, 0.22, (0, 0, 0), verts=24, m=brass, coll=coll)
        geo.attach(cap, el, (0, s * 1.6, 0), (math.pi / 2, 0, 0))
        rod = kit.cylinder(f'lamp.rod2.{s}', 0.28, L2, (0, 0, 0), verts=16, m=enamel, coll=coll)
        geo.attach(rod, el, (0, s * 0.85, L2 / 2))
    # head: knuckle, shade (outer enamel, inner cream), bulb, spot light
    hd = geo.empty('lamp.head', (0, 0, L2), coll, 2.0)
    geo.attach(hd, el, (0, 0, L2))
    lp.head = hd
    k3 = kit.cylinder('lamp.knuckle.h', 0.7, 2.6, (0, 0, 0), verts=32, m=enamel, coll=coll)
    geo.attach(k3, hd, (0, 0, 0), (math.pi / 2, 0, 0))
    outer = [(0.0, 1.0), (1.3, 1.0), (1.3, 3.2), (2.2, 3.8), (4.4, 5.6), (6.1, 9.6), (7.0, 12.6), (7.25, 13.0)]
    outer = geo.rounded_profile(outer, 0.5, 3)
    innerp = [(7.05, 13.0), (6.8, 12.6), (5.9, 9.6), (4.25, 5.75), (2.1, 4.0), (0.0, 3.9)]
    innerp = geo.rounded_profile(innerp, 0.5, 3)
    prof = outer + innerp
    nseg = len(prof) - 1
    idx = [0] * (len(outer) - 1) + [0] + [1] * (len(innerp) - 1)
    shade = geo.lathe('lamp.shade', prof, segs=72, coll=coll, mats=[enamel, inner], mat_idx=idx[:nseg])
    geo.attach(shade, hd)
    socket = kit.cylinder('lamp.socket', 1.0, 2.2, (0, 0, 0), verts=24, m=brass, coll=coll)
    geo.attach(socket, hd, (0, 0, 4.6))
    bl = kit.sphere('lamp.bulb', 2.4, (0, 0, 0), m=bulb, coll=coll, subdiv=3)
    geo.attach(bl, hd, (0, 0, 7.4))
    bl.scale = (1.0, 1.0, 1.15)
    bl.visible_shadow = False
    lt = kit.spot('lamp.light', (0, 0, 0), power=1.0, angle_deg=88, blend=0.55, radius=2.6, color=KEY_COLOR, coll=coll)
    geo.attach(lt, hd, (0, 0, 6.6), (math.pi, 0, 0))
    lt.data.use_soft_falloff = True
    lt.data.shadow_buffer_clip_start = 0.5
    lp.light = lt
    lp.bulb_socket = M.principled(bulb).inputs['Emission Strength']
    lp.inner_socket = M.principled(inner).inputs['Emission Strength']
    # a switch toggle on the shade's back (decoration)
    tog = kit.box('lamp.toggle', (0.3, 0.3, 1.2), (0, 0, 0), bevel=0.08, m=brass, coll=coll)
    geo.attach(tog, hd, (-2.6, 0, 4.2), (0, math.radians(-35), 0))
    lp.aim(None, aim, reach=reach, height=height)
    lp.objects = geo.descendants(root)
    return lp
