"""Scene-local helpers shared by boot.py and training.py (not library code).

- Cam: a motion-control camera (target Empty for aim, optional separate focus Empty for rack focus, physical f-stop).
- grid(): the chars library's stop-motion grid (twos / ones), so scene props (the bead, the falling crown, the sugar
  cube) pose on the same frames as the puppets.
- key_mats(): keys an object's world placement on that grid from a function of song time.
- Spark / embers: electric sparks running along a path (smooth, 24 fps, motion-blurred) and ballistic ember bursts,
  all keyed per frame from seeded hashes (pure functions of song time).
"""
from __future__ import annotations

import math

import bpy
from mathutils import Matrix, Vector

from pdoom import kit
from pdoom.sets import geo, phys_fstop
from pdoom.sets import materials as M
from pdoom import timing as tm
from pdoom.timing import FPS


# ------------------------------------------------------------------------------------------------ cameras


class Cam:
    """A camera aimed at a target Empty. focus: an optional point for a separate focus Empty (rack focus); without it
    the camera focuses on the target. f-stops are real-lens values (phys_fstop applied)."""

    def __init__(self, name, lens, loc, target, fstop=8.0, focus=None, coll=None):
        cam, tgt = kit.camera(name, lens=lens, loc=tuple(loc), target=tuple(target), fstop=fstop, coll=coll)
        cam.data.dof.aperture_fstop = phys_fstop(fstop)
        cam.data.dof.aperture_blades = 7
        cam.data.dof.aperture_rotation = math.radians(12)
        cam.data.clip_start = 0.3
        self.cam, self.tgt, self.foc = cam, tgt, None
        self.name = name
        if focus is not None:
            self.foc = kit.empty(name + '.focus', tuple(focus), coll)
            cam.data.dof.focus_object = self.foc

    def key(self, t, *, loc=None, target=None, focus=None, lens=None, fstop=None, interp='BEZIER'):
        """Key any of the camera's channels at song time t."""
        if loc is not None:
            kit.key(self.cam, 'location', t, tuple(loc), interp=interp)
        if target is not None:
            kit.key(self.tgt, 'location', t, tuple(target), interp=interp)
        if focus is not None and self.foc is not None:
            kit.key(self.foc, 'location', t, tuple(focus), interp=interp)
        if lens is not None:
            geo.keyp(self.cam.data, 'lens', t, lens, interp=interp)
        if fstop is not None:
            geo.keyp(self.cam.data.dof, 'aperture_fstop', t, phys_fstop(fstop), interp=interp)
        return self

    def cut(self, t):
        kit.cut_to(self.cam, t)
        return self


def shake(obj, t0, t1, amp=0.1, freq=12.0, seed=1, path='location'):
    """Camera shake: a restricted-range noise modifier on obj's already-keyed channel (adds no keys, unlike
    kit.shake which inserts a key from the object's current, un-evaluated value)."""
    for fc in kit.fcurves(obj):
        if fc.data_path != path:
            continue
        n = fc.modifiers.new('NOISE')
        n.scale, n.strength, n.phase = FPS / freq, amp * 2, seed * 7.3 + fc.array_index * 3.1
        n.use_restricted_range = True
        n.frame_start, n.frame_end = t0 * FPS, t1 * FPS
        n.blend_in = min(1.5, (t1 - t0) * FPS / 6)
        n.blend_out = min(4.0, (t1 - t0) * FPS / 3)
    return obj


def lerp3(a, b, u):
    return tuple(float(x) + (float(y) - float(x)) * u for x, y in zip(a, b))


def along(p0, p1, k):
    """p0 + (p1 - p0) * k (a point part of the way along)."""
    return Vector(p0).lerp(Vector(p1), k)


# ------------------------------------------------------------------------------------------------ stop-motion grid


def grid(t0, t1, spans=(), default='twos'):
    """[(key frame, sample time)] on the chars library's grid: twos = one pose per 2 frames on even frames, keyed at
    f - 0.5 and showing the pose at (f + 1) / 24; ones = every frame, showing f / 24. spans: [(ta, tb, mode)].
    Built for 60 fps (timing.SMOOTH, the production render) every mode samples every output frame (keys at the sample
    times; run.py turns the callers' CONSTANT keys on that grid into LINEAR)."""
    if tm.SMOOTH:
        return [(fk, fk / FPS) for fk in tm.out_frames(math.floor(t0 * FPS) - 2, math.ceil(t1 * FPS) + 2)]
    def mode_at(t):
        m = default
        for a, b, mm in spans:
            if a <= t < b:
                m = mm
        return m
    f0 = int(math.floor(t0 * FPS)) - 2
    f1 = int(math.ceil(t1 * FPS)) + 2
    out = []
    f = f0 - (f0 % 2)
    while f <= f1:
        m = mode_at(f / FPS)
        if m == 'ones':
            out.append((f - 0.5, f / FPS))
            f += 1
        elif m == 'smooth':
            out.append((float(f), f / FPS))
            f += 1
        else:
            if f % 2:
                out.append((f - 0.5, f / FPS))
                f += 1
                continue
            out.append((f - 0.5, (f + 1) / FPS))
            f += 2
    return out


def key_mats(obj, fn, t0, t1, spans=(), default='twos', scale=False):
    """Key obj's placement from fn(t) -> 4x4 world Matrix on the stop-motion grid (CONSTANT keys). obj must have no
    parent (or a static one: fn returns the matrix in the parent's space)."""
    prev = None
    fcs = []
    for fk, t in grid(t0, t1, spans, default):
        Mt = fn(t)
        loc, rot, sca = Mt.decompose()
        eul = rot.to_euler('XYZ', prev) if prev is not None else rot.to_euler('XYZ')
        prev = eul
        obj.location = loc
        obj.rotation_euler = eul
        obj.keyframe_insert('location', frame=fk)
        obj.keyframe_insert('rotation_euler', frame=fk)
        if scale:
            obj.scale = sca
            obj.keyframe_insert('scale', frame=fk)
    for fc in kit.fcurves(obj):
        if fc.data_path in ('location', 'rotation_euler', 'scale'):
            for kp in fc.keyframe_points:
                kp.interpolation = 'CONSTANT'
    return obj


def key_value_grid(owner, prop, fn, t0, t1, spans=(), default='twos', index=-1):
    """Key owner.prop from fn(t) on the stop-motion grid (CONSTANT)."""
    for fk, t in grid(t0, t1, spans, default):
        v = fn(t)
        if index >= 0:
            getattr(owner, prop)[index] = v
        else:
            setattr(owner, prop, v)
        owner.keyframe_insert(prop, frame=fk, index=index)
    idb = owner.id_data
    try:
        full = owner.path_from_id(prop)
    except Exception:
        full = prop
    for fc in kit.fcurves(idb):
        if fc.data_path == full:
            for kp in fc.keyframe_points:
                kp.interpolation = 'CONSTANT'


def vis(obj, t_on=None, t_off=None):
    """Render + viewport visibility only between t_on and t_off (keyed, constant)."""
    kit.visible(obj, t_on, t_off)
    return obj


def frame_loop(t0, t1):
    """Song times of every frame in [t0, t1] (inclusive, 24 fps)."""
    f0, f1 = int(math.floor(t0 * FPS)), int(math.ceil(t1 * FPS))
    return [f / FPS for f in range(f0, f1 + 1)]


# ------------------------------------------------------------------------------------------------ sparks


def hot_mat(name, color, strength):
    """An emissive material for sparks (bright core colour, blooms)."""
    m = M.emissive(name, color, strength)
    return m


def _ball(name, r, coll, m, subdiv=2):
    o = kit.sphere(name, r, (0, 0, 0), m=m, coll=coll, subdiv=subdiv)
    o.visible_shadow = False
    try:
        o.visible_diffuse = o.visible_glossy = True
    except Exception:
        pass
    return o


def spark_run(name, path, t0, t1, coll, *, core='#E8FBFF', halo='#7FD6FF', r=0.22, light_power=2600.0,
              ease=lambda u: u, tail=3, seed=1, crackle=6, ember_color='#BFEFFF'):
    """A spark running along path(u) (u 0..1 -> world Vector) from t0 to t1 (u = ease((t - t0) / (t1 - t0))),
    keyed on every frame so motion blur streaks it. A point light rides with it. `tail` smaller glowing beads
    trail behind; `crackle` embers break off along the way. Returns the core object."""
    mc = hot_mat(f'{name}.core', core, 120.0)
    mh = hot_mat(f'{name}.halo', halo, 30.0)
    o = _ball(f'{name}', r, coll, mc)
    tails = []
    for k in range(tail):
        tails.append(_ball(f'{name}.tail{k}', r * (0.75 - 0.18 * k), coll, mh, 1))
    ld = bpy.data.lights.new(f'{name}.light', 'POINT')
    ld.color = kit.srgb(halo)[:3]
    ld.shadow_soft_size = 0.3
    ld.energy = 0.0
    lo = bpy.data.objects.new(f'{name}.light', ld)
    coll.objects.link(lo)
    dur = t1 - t0

    def pos(t):
        u = min(1.0, max(0.0, (t - t0) / dur))
        return Vector(path(ease(u)))
    ts = frame_loop(t0 - 2 / FPS, t1 + 2 / FPS)
    for t in ts:
        p = pos(t)
        o.location = p
        kit.key(o, 'location', t, tuple(p), interp='LINEAR')
        lo.location = p + Vector((0, 0, 0.5))
        kit.key(lo, 'location', t, tuple(lo.location), interp='LINEAR')
        for k, tb in enumerate(tails):
            pt = pos(t - (k + 1) * 0.022)
            tb.location = pt
            kit.key(tb, 'location', t, tuple(pt), interp='LINEAR')
        # flicker of the light (seeded)
        live = t0 - 0.5 / FPS <= t <= t1 + 0.5 / FPS
        e = light_power * (0.75 + 0.5 * geo.hash01(name, 'fl', int(round(t * FPS)))) if live else 0.0
        geo.keyp(ld, 'energy', t, e, interp='CONSTANT')
    for ob in [o] + tails:
        vis(ob, t0 - 0.5 / FPS, t1 + 0.5 / FPS)
    # crackle: embers thrown off along the run
    for k in range(crackle):
        tk = t0 + dur * (0.1 + 0.8 * geo.hash01(name, 'ck', k, seed))
        embers(f'{name}.ck{k}', pos(tk), tk, coll, n=3, seed=seed * 31 + k, speed=(18, 45), life=(0.12, 0.3),
               color=ember_color, up=0.6, r=0.05)
    return o


def embers(name, origin, t, coll, *, n=12, seed=1, speed=(20.0, 60.0), life=(0.15, 0.4), color='#FFD27A', up=0.8,
           r=0.06, gravity=981.0, spread=None, floor=0.02, strength=60.0):
    """A burst of n tiny glowing embers from origin at time t: ballistic (gravity, bounce off the desk), each shrinking
    to nothing over its life. spread: optional main direction (Vector) the burst favours."""
    m = hot_mat(f'embers.{color}', color, strength)
    origin = Vector(origin)
    objs = []
    for i in range(n):
        h = lambda *k: geo.hash01(name, seed, i, *k)
        az = 2 * math.pi * h('az')
        el = math.asin(max(-1.0, min(1.0, (2 * h('el') - 1) * 0.6 + up * 0.4)))
        v = speed[0] + (speed[1] - speed[0]) * h('v')
        d = Vector((math.cos(az) * math.cos(el), math.sin(az) * math.cos(el), math.sin(el)))
        if spread is not None:
            d = (d + Vector(spread).normalized() * 1.2).normalized()
        vel = d * v
        L = life[0] + (life[1] - life[0]) * h('life')
        o = _ball(f'{name}.{i}', r * (0.6 + 0.8 * h('r')), coll, m, 1)
        ts = frame_loop(t - 1 / FPS, t + L + 1 / FPS)
        for tt in ts:
            dt = max(0.0, tt - t)
            p = origin + vel * dt + Vector((0, 0, -0.5 * gravity * dt * dt))
            if p.z < floor:
                p.z = floor + (floor - p.z) * 0.25
            o.location = p
            kit.key(o, 'location', tt, tuple(p), interp='LINEAR')
            s = max(0.0, 1.0 - dt / L) ** 0.7 if tt >= t else 0.0
            o.scale = (s, s, s)
            kit.key(o, 'scale', tt, (s, s, s), interp='LINEAR')
        vis(o, t - 0.5 / FPS, t + L)
        objs.append(o)
    return objs


def flash_light(name, loc, t, coll, *, power=8000.0, color='#FFD9A0', decay=0.18, radius=0.5):
    """A point light that flashes at t and decays (keyed per frame)."""
    ld = bpy.data.lights.new(name, 'POINT')
    ld.color = kit.srgb(color)[:3]
    ld.shadow_soft_size = radius
    lo = bpy.data.objects.new(name, ld)
    coll.objects.link(lo)
    lo.location = loc
    geo.keyp(ld, 'energy', t - 1.5 / FPS, 0.0, interp='LINEAR')
    for tt in frame_loop(t, t + decay * 4):
        e = power * math.exp(-(tt - t) / decay)
        geo.keyp(ld, 'energy', tt, e, interp='LINEAR')
    geo.keyp(ld, 'energy', t + decay * 4 + 1 / FPS, 0.0, interp='LINEAR')
    return lo
