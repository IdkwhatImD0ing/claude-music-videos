"""The puppet engine shared by the characters.

A character is a set of TRACKS (named channels: root location, lid angle, arm pose...). API calls add keys and
overlays to tracks by SONG TIME; nothing touches Blender until bake(), which samples every track on the stop-motion
grid and writes the F-curves in bulk:

- twos (default): one pose per 2 global frames (even frames), CONSTANT keys placed half a frame early (f - 0.5) so a
  pose covers the whole shutter interval: characters never motion-blur, like a real stop-motion puppet. The pose shown
  on frames f, f+1 is the pose at time (f + 1) / 24, so hits land within +-1 frame.
- ones: one pose per frame, still CONSTANT (crisp).
- smooth: LINEAR keys on every frame (24 fps, motion-blurred) for shots that need it.

Built with PDOOM_FPS=60 (timing.OUT_FPS, the production render) every mode bakes smooth on the 60 fps output grid: LINEAR
keys every 0.4 frames, no jitter. Stepped channels (visibility, the researcher's face texture) stay CONSTANT, keyed at
timing.switch_frame (between exposures, cut-aligned). Snaps (zero-duration Track keys: place(), cut poses) are not
interpolated: the pose holds, then jumps between two exposures at the snap's switch_frame, so a teleport at a cut never
smears or leaks into the outgoing shot.

Moving poses get a tiny per-pose jitter (a seeded hash of the frame), holds stay clean. Tracks:

  Track.set(t, value, dur, ease, fn)   the channel ARRIVES at value at t (tween from t - dur); holds after
  Track.add(t0, t1, fn)                an additive overlay fn(t) on [t0, t1) (hops, chomps, blinks, dances)
  Discrete.set(t, value, origin)       stepped values (eye shape, prop on/off); origin makes a 'soft' event that is
                                       dropped if any other event happens between origin and t (auto-returns)
"""
from __future__ import annotations

import bisect
import math

import bpy
from mathutils import Matrix, Vector

from .. import timing as _tm
from ..timing import FPS

# ------------------------------------------------------------------------------------------------ easing / values


def _back(u):
    c1 = 1.70158
    c3 = c1 + 1
    return 1 + c3 * (u - 1) ** 3 + c1 * (u - 1) ** 2


def _elastic(u):
    if u <= 0 or u >= 1:
        return float(u >= 1)
    return 2 ** (-10 * u) * math.sin((u * 10 - 0.75) * (2 * math.pi / 3)) + 1


EASE = {
    'linear': lambda u: u,
    'inout': lambda u: u * u * (3 - 2 * u),
    'in': lambda u: u * u * u,
    'out': lambda u: 1 - (1 - u) ** 3,
    'back': _back,
    'elastic': _elastic,
    'snap': lambda u: 0.0,
}


def lerp(a, b, u):
    if isinstance(a, tuple):
        return tuple(x + (y - x) * u for x, y in zip(a, b))
    return a + (b - a) * u


def vadd(a, b):
    if isinstance(a, tuple):
        return tuple(x + y for x, y in zip(a, b))
    return a + b


def vscale(a, k):
    if isinstance(a, tuple):
        return tuple(x * k for x in a)
    return a * k


def smoothstep(e0, e1, x):
    if e1 == e0:
        return float(x >= e1)
    u = min(max((x - e0) / (e1 - e0), 0.0), 1.0)
    return u * u * (3 - 2 * u)


def bump(t, t0, tp, t1):
    """0 at t0, 1 at tp, 0 at t1 (smooth)."""
    if t <= t0 or t >= t1:
        return 0.0
    if t < tp:
        return smoothstep(t0, tp, t)
    return 1.0 - smoothstep(tp, t1, t)


def wobble(t, t0, freq=3.2, damp=7.0):
    """Damped spring after t0: 1 at t0, oscillating to 0 (squash recoveries)."""
    if t < t0:
        return 0.0
    x = t - t0
    return math.exp(-damp * x) * math.cos(2 * math.pi * freq * x)


def hash01(*k) -> float:
    """Deterministic hash -> [0, 1)."""
    h = 2166136261
    for x in k:
        h ^= int(x) & 0xFFFFFFFF
        h = (h * 16777619) & 0xFFFFFFFF
        h ^= h >> 13
        h = (h * 1274126177) & 0xFFFFFFFF
    return (h & 0xFFFFFF) / float(0x1000000)


def name_seed(s: str) -> int:
    h = 7
    for ch in s:
        h = (h * 131 + ord(ch)) & 0x7FFFFFFF
    return h


def unwrap(a, ref):
    """Angle a (deg) shifted by 360s to be closest to ref."""
    return a + 360.0 * round((ref - a) / 360.0)


# ------------------------------------------------------------------------------------------------ tracks


class Track:
    __slots__ = ('default', 'keys', 'over', '_dirty', '_maxdur')

    def __init__(self, default):
        self.default = default
        self.keys = []      # (t_arrive, t_start, value, ease, fn)
        self.over = []      # (t0, t1, fn)
        self._dirty = False
        self._maxdur = 0.0

    def set(self, t, value, dur=0.0, ease='inout', fn=None):
        dur = max(0.0, float(dur))
        self.keys.append((float(t), float(t) - dur, value, ease, fn))
        self._dirty = True
        self._maxdur = max(self._maxdur, dur)

    def add(self, t0, t1, fn):
        self.over.append((float(t0), float(t1), fn))

    def base(self, t):
        ks = self.keys
        if self._dirty:
            ks.sort(key=lambda k: k[0])
            self._dirty = False
        lo, hi = 0, len(ks)
        while lo < hi:
            mid = (lo + hi) // 2
            if ks[mid][0] <= t:
                lo = mid + 1
            else:
                hi = mid
        v = ks[lo - 1][2] if lo > 0 else self.default
        j = lo
        lim = t + self._maxdur + 1e-9
        while j < len(ks) and ks[j][0] <= lim:
            ta, ts, val, ease, fn = ks[j]
            if ts <= t < ta:
                u = (t - ts) / (ta - ts)
                v = fn(u, v) if fn else lerp(v, val, EASE[ease](u))
            j += 1
        return v

    def at(self, t):
        v = self.base(t)
        for t0, t1, fn in self.over:
            if t0 <= t < t1:
                v = vadd(v, fn(t))
        return v


class Discrete:
    __slots__ = ('default', 'ev', '_dirty', '_valid')

    def __init__(self, default):
        self.default = default
        self.ev = []        # (t, value, origin or None)
        self._dirty = False
        self._valid = []

    def set(self, t, value, origin=None):
        self.ev.append((float(t), value, origin))
        self._dirty = True

    def _prep(self):
        self.ev.sort(key=lambda e: e[0])
        ts = [e[0] for e in self.ev]
        self._valid = []
        for i, (t, v, o) in enumerate(self.ev):
            ok = True
            if o is not None:
                ok = not any(o + 1e-6 < ts[j] < t - 1e-6 for j in range(len(ts)) if j != i)
            self._valid.append(ok)
        self._dirty = False

    def at(self, t):
        if self._dirty:
            self._prep()
        v = self.default
        for (te, val, _), ok in zip(self.ev, self._valid):
            if te > t + 1e-9:
                break
            if ok:
                v = val
        return v


def _v3(p, z=0.0):
    p = tuple(float(x) for x in p)
    return p if len(p) == 3 else (p[0], p[1], z)


def _lin(c):
    from ..kit import srgb
    if isinstance(c, str):
        return tuple(srgb(c)[:3])
    return tuple(c[:3])


# ------------------------------------------------------------------------------------------------ paths


class Path:
    """A smooth path through points (Catmull-Rom), parametrised by arc length. at(s01) -> (x, y, z)."""

    def __init__(self, pts, smooth=True, per_seg=24):
        P = [Vector(_v3(p)) for p in pts]
        dense = [P[0]]
        for i in range(len(P) - 1):
            p0 = P[i - 1] if i > 0 else P[i] * 2 - P[i + 1]
            p1, p2 = P[i], P[i + 1]
            p3 = P[i + 2] if i + 2 < len(P) else P[i + 1] * 2 - P[i]
            for k in range(1, per_seg + 1):
                u = k / per_seg
                if smooth and len(P) > 2:
                    u2, u3 = u * u, u * u * u
                    q = 0.5 * ((2 * p1) + (-p0 + p2) * u + (2 * p0 - 5 * p1 + 4 * p2 - p3) * u2 +
                               (-p0 + 3 * p1 - 3 * p2 + p3) * u3)
                else:
                    q = p1.lerp(p2, u)
                dense.append(q)
        self.P = dense
        self.L = [0.0]
        for i in range(1, len(dense)):
            self.L.append(self.L[-1] + (dense[i] - dense[i - 1]).length)
        self.length = self.L[-1]
        hd = []
        for i in range(len(dense)):
            a, b = dense[max(i - 1, 0)], dense[min(i + 1, len(dense) - 1)]
            d = b - a
            hd.append(math.degrees(math.atan2(d.x, -d.y)) if d.xy.length > 1e-6 else None)
        # fill gaps, unwrap
        last = next((h for h in hd if h is not None), 0.0)
        out = []
        for h in hd:
            h = last if h is None else unwrap(h, last)
            out.append(h)
            last = h
        self.H = out

    def _find(self, s01):
        s = min(max(s01, 0.0), 1.0) * self.length
        i = max(1, bisect.bisect_left(self.L, s))
        i = min(i, len(self.L) - 1)
        l0, l1 = self.L[i - 1], self.L[i]
        return i, (s - l0) / (l1 - l0) if l1 > l0 else 0.0

    def at(self, s01):
        if self.length < 1e-9:
            return tuple(self.P[0])
        i, u = self._find(s01)
        return tuple(self.P[i - 1].lerp(self.P[i], u))

    def heading(self, s01):
        if self.length < 1e-9:
            return self.H[0]
        i, u = self._find(s01)
        return self.H[i - 1] + (self.H[i] - self.H[i - 1]) * u


# ------------------------------------------------------------------------------------------------ Blender helpers


def pb(bone: str, prop: str) -> str:
    return f'pose.bones["{bone}"].{prop}'


def armature(name: str, coll, bones: list[dict]):
    """Create an armature object from bone specs: {name, head, tail?, parent?, inherit_scale?, deform?, bbone?,
    roll?, connect?}. Tail defaults to head + (0, 0.8, 0): a bone pointing +Y with roll 0 has an IDENTITY rest
    orientation, so its pose-space rotations are character-space rotations (the rigs rely on this)."""
    ad = bpy.data.armatures.new(name)
    ad.display_type = 'STICK'
    ob = bpy.data.objects.new(name, ad)
    coll.objects.link(ob)
    vl = bpy.context.view_layer
    linked_tmp = False
    if ob.name not in vl.objects:
        bpy.context.scene.collection.objects.link(ob)
        linked_tmp = True
    prev = vl.objects.active
    vl.objects.active = ob
    bpy.ops.object.mode_set(mode='EDIT')
    ebs = {}
    for s in bones:
        eb = ad.edit_bones.new(s['name'])
        eb.head = s['head']
        eb.tail = s.get('tail') or (Vector(s['head']) + Vector((0, 0.8, 0)))
        eb.roll = s.get('roll', 0.0)
        eb.use_deform = s.get('deform', False)
        if s.get('bbone'):
            eb.bbone_segments = s['bbone']
        ebs[s['name']] = eb
    for s in bones:
        if s.get('parent'):
            ebs[s['name']].parent = ebs[s['parent']]
            ebs[s['name']].use_connect = s.get('connect', False)
        if s.get('inherit_scale'):
            ebs[s['name']].inherit_scale = s['inherit_scale']
    bpy.ops.object.mode_set(mode='OBJECT')
    vl.objects.active = prev
    if linked_tmp:
        bpy.context.scene.collection.objects.unlink(ob)
    for p in ob.pose.bones:
        p.rotation_mode = 'XYZ'
    return ob


def bone_parent(obj, arm, bone: str):
    """Parent obj to a bone keeping its current (rest) world transform: the object then moves exactly with the bone
    about the bone's head. Objects are modelled in character space, so obj.matrix_basis is its rest placement."""
    b = arm.data.bones[bone]
    pm = arm.matrix_world @ b.matrix_local @ Matrix.Translation((0, b.length, 0))
    basis = obj.matrix_basis.copy()
    obj.parent = arm
    obj.parent_type = 'BONE'
    obj.parent_bone = bone
    obj.matrix_parent_inverse = pm.inverted()
    obj.matrix_basis = basis
    return obj


def _owner(idb, path: str):
    if '.' in path and not path.endswith(']'):
        head, attr = path.rsplit('.', 1)
        # a '.' inside ["..."] would break this; our paths never have one
        return idb.path_resolve(head), attr
    return idb, path


# ------------------------------------------------------------------------------------------------ puppet

REGISTRY: list = []


STEPPED_PATHS = ('hide_render', 'hide_viewport', 'nodes["face"]')     # discrete channels: never interpolated


class Target:
    __slots__ = ('idb', 'path', 'index', 'jit', 'step')

    def __init__(self, idb, path, index=-1, jit=0.0):
        self.idb, self.path, self.index, self.jit = idb, path, index, jit
        self.step = any(path.startswith(p) for p in STEPPED_PATHS)

    def key(self):
        return (self.idb.as_pointer(), self.path, self.index)


class Puppet:
    """Base class: tracks, timing spans, gait integration and the bake. Subclasses define _targets() / _solve(t)."""

    STRIDE = 2.4          # cm of travel per gait cycle
    GAIT_R = 2.9          # cm: lever arm that turns yaw rate into foot speed
    GAIT_FULL = 2.0       # cm/s of foot speed for full-amplitude steps

    def __init__(self, name: str, seed=None, timing: str = 'twos'):
        self.name = name
        self.seed = name_seed(name) if seed is None else int(seed)
        self.T: dict[str, Track] = {}
        self.D: dict[str, Discrete] = {}
        self.spans: list = []
        self.mode = timing
        self.nogait: list = []
        self.events: list[float] = []
        self._baked = False
        self._gait = None
        REGISTRY.append(self)
        _install_handlers()

    # tracks ------------------------------------------------------------------------------------------------------
    def track(self, name, default=0.0) -> Track:
        tr = self.T.get(name)
        if tr is None:
            tr = self.T[name] = Track(default)
        return tr

    def disc(self, name, default=None) -> Discrete:
        d = self.D.get(name)
        if d is None:
            d = self.D[name] = Discrete(default)
        return d

    def _ev(self, t):
        self.events.append(float(t))
        self._baked = False

    # timing ------------------------------------------------------------------------------------------------------
    def timing(self, t0: float, t1: float, mode: str = 'smooth'):
        """Animate [t0, t1) 'twos' | 'ones' | 'smooth' (24 fps with motion blur). The default comes from the
        constructor (timing='twos')."""
        assert mode in ('twos', 'ones', 'smooth')
        self.spans.append((float(t0), float(t1), mode))
        self._baked = False
        return self

    def _mode_at(self, t):
        m = self.mode
        for t0, t1, mode in self.spans:
            if t0 <= t < t1:
                m = mode
        return m

    def _grid(self, f0: int, f1: int):
        if _tm.SMOOTH:                    # production: every output frame gets its own pose, LINEAR in between
            pts = [(fk, fk / FPS, 1) for fk in _tm.out_frames(f0, f1)]
            snaps = sorted({_tm.switch_frame(ta * FPS) for tr in self.T.values()
                            for (ta, ts, *_r) in getattr(tr, 'keys', ()) if ta - ts < 1e-9 and f0 <= ta * FPS <= f1})
            if not snaps:
                return pts
            out, j = [], 0
            for i, p in enumerate(pts):
                nxt = pts[i + 1] if i + 1 < len(pts) else None
                while j < len(snaps) and snaps[j] <= p[0]:
                    j += 1
                if nxt is not None and j < len(snaps) and snaps[j] < nxt[0]:
                    s = snaps[j]          # hold this pose, then the post-snap pose from s (between exposures)
                    out.append((p[0], p[1], 0))
                    out.append((s, nxt[1], 1))
                else:
                    out.append(p)
            return out
        out = []
        f = f0 - (f0 % 2)
        while f <= f1:
            m = self._mode_at(f / FPS)
            if m == 'twos':
                if f % 2:
                    out.append((f - 0.5, f / FPS, 0))
                    f += 1
                    continue
                out.append((f - 0.5, (f + 1) / FPS, 0))
                f += 2
            elif m == 'ones':
                out.append((f - 0.5, f / FPS, 0))
                f += 1
            else:
                out.append((float(f), f / FPS, 1))
                f += 1
        return out

    # gait --------------------------------------------------------------------------------------------------------
    def visible(self, t_on: float | None = None, t_off: float | None = None):
        """Show the whole character only from t_on (hidden before) until t_off (hidden after); either may be None.
        Call again for more on/off switches (each call adds events)."""
        d = self.disc('visible', True)
        if t_on is not None:
            if not d.ev:
                d.default = False
            d.set(t_on, True)
        if t_off is not None:
            d.set(t_off, False)
        self._baked = False
        return self

    def _shown(self, t) -> bool:
        d = self.D.get('visible')
        return True if d is None else bool(d.at(t))

    def _uses_visible(self) -> bool:
        d = self.D.get('visible')
        return bool(d is not None and (d.ev or not d.default))

    def no_gait(self, t0, t1):
        """Root motion in [t0, t1) doesn't make the legs step (riding, sliding, flying)."""
        self.nogait.append((float(t0), float(t1)))
        self._baked = False

    def _prepare_gait(self, ta: float, tb: float):
        dt = 1.0 / 48
        n = int((tb - ta) / dt) + 3
        loc, yaw = self.T['root.loc'], self.T['root.yaw']
        ph, amp_t, vx, vy, w = [0.0] * n, [0.0] * n, [0.0] * n, [0.0] * n, [0.0] * n
        phase = 0.0
        # snaps (zero-duration root keys: place() at a cut) are teleports, not speed: samples whose window holds one
        # keep the previous sample's gait (they used to read as a burst of speed and swing the legs at every cut)
        snaps = sorted(k[0] for tr in (loc, yaw) for k in tr.keys if k[0] - k[1] < 1e-9)
        for i in range(n):
            t = ta + i * dt
            if any(a <= t < b for a, b in self.nogait):
                ph[i] = phase
                continue
            j = bisect.bisect_left(snaps, t - dt / 2 - 1e-9)
            if j < len(snaps) and snaps[j] <= t + dt / 2 + 1e-9:
                ph[i] = phase
                if i:
                    amp_t[i], vx[i], vy[i], w[i] = amp_t[i - 1], vx[i - 1], vy[i - 1], w[i - 1]
                continue
            p0, p1 = loc.at(t - dt / 2), loc.at(t + dt / 2)
            y0, y1 = yaw.at(t - dt / 2), yaw.at(t + dt / 2)
            sc = max(0.05, self.T['root.scale'].at(t))
            gx, gy = (p1[0] - p0[0]) / dt / sc, (p1[1] - p0[1]) / dt / sc
            om = (y1 - y0) / dt
            a = math.radians(yaw.at(t))
            lx = math.cos(a) * gx + math.sin(a) * gy
            ly = -math.sin(a) * gx + math.cos(a) * gy
            spd = math.hypot(lx, ly) + abs(math.radians(om)) * self.GAIT_R
            phase += spd * dt / self.STRIDE
            ph[i], vx[i], vy[i], w[i] = phase, lx, ly, math.radians(om)
            amp_t[i] = min(1.0, spd / self.GAIT_FULL)
        # symmetric smoothing of the amplitude (legs settle instead of snapping)
        k = 1 - math.exp(-dt / 0.07)
        f = amp_t[:]
        for i in range(1, n):
            f[i] = f[i - 1] + (amp_t[i] - f[i - 1]) * k
        b = amp_t[:]
        for i in range(n - 2, -1, -1):
            b[i] = b[i + 1] + (amp_t[i] - b[i + 1]) * k
        amp = [max(x, y) for x, y in zip(f, b)]
        self._gait = (ta, dt, ph, amp, vx, vy, w)

    def gait(self, t):
        """(phase, amplitude 0..1, local vx, local vy, yaw rate rad/s) at t, from the root's motion."""
        if self._gait is None:
            return 0.0, 0.0, 0.0, -1.0, 0.0
        ta, dt, ph, amp, vx, vy, w = self._gait
        i = min(max(int(round((t - ta) / dt)), 0), len(ph) - 1)
        return ph[i], amp[i], vx[i], vy[i], w[i]

    # locomotion --------------------------------------------------------------------------------------------------
    def place(self, t: float, loc=None, yaw: float | None = None):
        """Snap to loc (x, y[, z]) and/or yaw (deg) at t (a cut, or a pose between shots)."""
        if loc is not None:
            cur = self.T['root.loc'].at(t)
            self.T['root.loc'].set(t, _v3(loc, cur[2]))
        if yaw is not None:
            self.T['root.yaw'].set(t, float(yaw))
        self._ev(t)
        return self

    def turn(self, t: float, yaw: float, dur: float = 0.3, ease: str = 'inout'):
        """Turn in place to face yaw (deg) by t. The legs shuffle."""
        y0 = self.T['root.yaw'].at(t - dur)
        self.T['root.yaw'].set(t, unwrap(float(yaw), y0), dur, ease)
        self._ev(t)
        return self

    def move(self, t0: float, t1: float, points, *, face='forward', ease: str = 'inout', smooth: bool = True,
             gait: bool = True, turn_time: float = 0.25):
        """Travel from the current position (at t0) through points [(x, y[, z]), ...], arriving at t1.
        face: 'forward' (turn to face the direction of travel), 'back', 'keep' (crab-walk), or a yaw in degrees.
        gait=False slides without stepping (riding something)."""
        L, Y = self.T['root.loc'], self.T['root.yaw']
        p0 = L.at(t0)
        pts = [p0] + [_v3(p, p0[2]) for p in points]
        path = Path(pts, smooth=smooth)
        E = EASE[ease]
        dur = max(1e-3, t1 - t0)
        L.set(t1, tuple(pts[-1]) if path.length < 1e-9 else path.at(1.0), dur, fn=lambda u, v0: path.at(E(u)))
        y0 = Y.at(t0)
        if face in ('forward', 'back'):
            off = 0.0 if face == 'forward' else 180.0
            h0 = unwrap(path.heading(0.0) + off, y0)
            shift = h0 - (path.heading(0.0) + off)
            ut = min(0.45, turn_time / dur)

            def yawfn(u, v0, path=path, off=off, shift=shift, y0=y0, ut=ut):
                h = path.heading(E(u)) + off + shift
                w = smoothstep(0.0, ut, u) if ut > 0 else 1.0
                return y0 + (h - y0) * w
            Y.set(t1, path.heading(1.0) + off + shift, dur, fn=yawfn)
        elif isinstance(face, (int, float)):
            Y.set(t1, unwrap(float(face), y0), dur, ease)
        if not gait:
            self.no_gait(t0, t1)
        self._ev(t0)
        self._ev(t1)
        return self

    walk = move

    def _moving(self, t0, t1):
        a = self.T['root.loc'].at(t0)
        b = self.T['root.loc'].at(t1)
        c = self.T['root.loc'].at((t0 + t1) / 2)
        return (Vector(a) - Vector(b)).length > 1e-3 or (Vector(a) - Vector(c)).length > 1e-3

    def anchor(self, t: float, name: str = 'face') -> Vector:
        raise NotImplementedError

    # bake --------------------------------------------------------------------------------------------------------
    def _targets(self) -> list[Target]:
        raise NotImplementedError

    def _solve(self, t) -> list[float]:
        raise NotImplementedError

    def bake(self, f0: int | None = None, f1: int | None = None):
        """Sample every track on the stop-motion grid over the scene's frame range and write the F-curves."""
        sc = bpy.context.scene
        f0 = sc.frame_start - 2 if f0 is None else f0
        f1 = sc.frame_end + 2 if f1 is None else f1
        grid = self._grid(f0, f1)
        self._prepare_gait(grid[0][1] - 0.6, grid[-1][1] + 0.6)
        tg = self._targets()
        n = len(tg)
        series = [[] for _ in range(n)]
        prev = [None] * n
        for fk, t, ip in grid:
            vals = self._solve(t)
            fi = int(round(fk * 2))
            for i in range(n):
                v = vals[i]
                amp = tg[i].jit
                if amp and ip == 0 and prev[i] is not None and abs(v - prev[i]) > 1e-4:
                    vj = v + amp * (2 * hash01(self.seed, i, fi) - 1)
                else:
                    vj = v
                prev[i] = v
                series[i].append((fk, vj, 0 if tg[i].step else ip))
        if _tm.SMOOTH:                    # stepped channels switch at the cut-aligned frame, between exposures
            for i, tgt in enumerate(tg):
                if 'rotation_euler' in tgt.path and not tgt.step:
                    series[i] = _unwrap(series[i])          # LINEAR keys must not swing the long way round
                if tgt.step:
                    moved = {}
                    for fk, v, ip in series[i]:
                        moved[_tm.switch_frame(fk)] = (v, ip)       # a later sample at the same frame wins
                    series[i] = [(fk, v, ip) for fk, (v, ip) in sorted(moved.items())]
        for tgt, pts in zip(tg, series):
            _write(tgt, pts, self.name)
        self._baked = True
        return self


def _unwrap(pts):
    """Euler angle samples made continuous (each step within +-pi), so LINEAR keys between output frames never spin a
    part through a full turn (the same rotations, written the short way)."""
    out = []
    for fk, v, ip in pts:
        if out:
            v -= 2 * math.pi * round((v - out[-1][1]) / (2 * math.pi))
        out.append((fk, v, ip))
    return out


def _write(tgt: Target, pts, owner_name: str):
    out = []
    for fk, v, ip in pts:
        if out and ip == 0 and out[-1][2] == 0 and abs(out[-1][1] - v) < 1e-6:
            continue
        out.append((fk, v, ip))
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
        # static: just set the value, no F-curve
        owner, attr = _owner(idb, tgt.path)
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
    kp.foreach_set('interpolation', [0 if ip == 0 else 1 for _, _, ip in out])
    fc.update()


# ------------------------------------------------------------------------------------------------ finish / handlers


def finish_all():
    """Bake every character that changed since its last bake. Call at the end of a scene's build()."""
    for p in list(REGISTRY):
        try:
            if not p._baked:
                p.bake()
        except ReferenceError:
            REGISTRY.remove(p)


def _chars_autobake(*_args):
    try:
        finish_all()
    except Exception as e:  # never break a render
        print(f'[chars] auto-bake failed: {e!r}')


def _install_handlers():
    for lst in (bpy.app.handlers.save_pre, bpy.app.handlers.render_init):
        if not any(getattr(f, '__name__', '') == '_chars_autobake' for f in lst):
            lst.append(_chars_autobake)


def _point(target, t) -> Vector:
    if isinstance(target, Puppet):
        return target.anchor(t, 'face')
    if hasattr(target, 'matrix_world'):
        return target.matrix_world.translation.copy()
    return Vector(_v3(target))
