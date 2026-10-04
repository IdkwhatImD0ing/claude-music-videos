"""Time remapping: video time t -> clip source time s. This is where sync and velocity live.

A Remap is a chain of keys (t, s, v): at video time t the clip shows source time s moving at speed v (source seconds
per video second; 1 = real time, 0.25 = 4x slow-mo, 0 = freeze, negative = rewind). Between two keys the speed
follows a "velocity" profile: it eases from v0 up (or down) to a cruise speed, holds it, then eases into v1, and the
cruise speed is solved so the clip lands exactly on s1 at t1. So a kill keyed on a beat with a low v slows into the
hit, and the stretch between kills runs fast: that's a velocity edit.

    from engine.remap import Remap, K
    r = Remap([K(t_in, s_in, 1.0),                 # enter at real speed
               K(beat_a, kill_1, 0.3),             # kill 1 lands on beat_a, in slow-mo
               K(beat_a + 0.25, kill_1 + 0.075, 0.3),
               K(beat_b, kill_2, 0.25, ease=(0.15, 0.5)),   # ease = fraction of the segment spent speeding up / braking
               K(t_out, kill_2 + 1.2, 1.0)])
    r.s(t), r.speed(t)          # scalars or numpy arrays
    r.check()                   # list of warnings: cruise speeds outside 0.1..8x, reversals you didn't ask for

Shorthands:  Remap.linear(t0, s0, t1, s1)   Remap.hold(t0, t1, s)   Remap.constant(t0, s0, speed, t1)
"""
from dataclasses import dataclass

import numpy as np


@dataclass
class K:
    t: float
    s: float
    v: float = 1.0
    ease: tuple = (0.3, 0.3)   # (accelerate fraction after the previous key, brake fraction before this key)


def _ramp_int(x):
    """Integral of smoothstep from 0 to x (x in 0..1)."""
    return x ** 3 - 0.5 * x ** 4


class _Seg:
    def __init__(self, k0, k1):
        self.t0, self.t1, self.s0, self.s1 = k0.t, k1.t, k0.s, k1.s
        self.v0, self.v1 = k0.v, k1.v
        self.T = max(1e-9, k1.t - k0.t)
        a, b = k1.ease
        a, b = max(0.0, a), max(0.0, b)
        if a + b > 1:
            a, b = a / (a + b), b / (a + b)
        self.a, self.b = a, b
        mean = (k1.s - k0.s) / self.T
        denom = 1 - (a + b) / 2
        self.vc = (mean - (self.v0 * a + self.v1 * b) / 2) / denom if denom > 1e-9 else mean
        self.mean = mean

    def s(self, t):
        u = np.clip((t - self.t0) / self.T, 0.0, 1.0)
        a, b, v0, v1, vc, T = self.a, self.b, self.v0, self.v1, self.vc, self.T
        out = np.zeros_like(u, dtype=np.float64)
        # accelerate part
        if a > 0:
            x = np.clip(u / a, 0, 1)
            out += a * (v0 * x + (vc - v0) * _ramp_int(x))
        # cruise
        c0, c1 = a, 1 - b
        out += vc * np.clip(u - c0, 0, max(0.0, c1 - c0))
        # brake part
        if b > 0:
            x = np.clip((u - c1) / b, 0, 1)
            out += b * (vc * x + (v1 - vc) * _ramp_int(x))
        return self.s0 + out * T

    def speed(self, t):
        u = np.clip((t - self.t0) / self.T, 0.0, 1.0)
        a, b = self.a, self.b
        sm = lambda x: x * x * (3 - 2 * x)
        v = np.full_like(u, self.vc, dtype=np.float64)
        if a > 0:
            x = np.clip(u / a, 0, 1)
            v = np.where(u < a, self.v0 + (self.vc - self.v0) * sm(x), v)
        if b > 0:
            x = np.clip((u - (1 - b)) / b, 0, 1)
            v = np.where(u > 1 - b, self.vc + (self.v1 - self.vc) * sm(x), v)
        return v


class Remap:
    def __init__(self, keys):
        keys = sorted(keys, key=lambda k: k.t)
        if len(keys) < 2:
            raise ValueError('Remap needs at least two keys')
        self.keys = keys
        self.segs = [_Seg(a, b) for a, b in zip(keys, keys[1:])]
        self._t = np.array([k.t for k in keys])

    def _apply(self, t, fn):
        scalar = np.isscalar(t)
        t = np.atleast_1d(np.asarray(t, dtype=np.float64))
        out = np.empty_like(t)
        j = np.clip(np.searchsorted(self._t, t, side='right') - 1, 0, len(self.segs) - 1)
        for k, seg in enumerate(self.segs):
            m = j == k
            if m.any():
                tt = t[m]
                if fn == 's':
                    r = seg.s(tt)
                    # outside the key range: continue at the end speeds
                    if k == 0:
                        r = np.where(tt < seg.t0, seg.s0 + (tt - seg.t0) * seg.v0, r)
                    if k == len(self.segs) - 1:
                        r = np.where(tt > seg.t1, seg.s1 + (tt - seg.t1) * seg.v1, r)
                else:
                    r = seg.speed(tt)
                    if k == 0:
                        r = np.where(tt < seg.t0, seg.v0, r)
                    if k == len(self.segs) - 1:
                        r = np.where(tt > seg.t1, seg.v1, r)
                out[m] = r
        return float(out[0]) if scalar else out

    def s(self, t):
        return self._apply(t, 's')

    def speed(self, t):
        return self._apply(t, 'speed')

    def check(self, lo=0.1, hi=8.0):
        warn = []
        for g in self.segs:
            if g.mean != 0 and not (lo <= abs(g.vc) <= hi):
                warn.append(f'{g.t0:.2f}-{g.t1:.2f}s: cruise speed {g.vc:.2f}x (mean {g.mean:.2f}x)')
            if g.mean > 0 and g.vc < 0:
                warn.append(f'{g.t0:.2f}-{g.t1:.2f}s: runs backwards mid-segment; widen the segment or lower v')
        return warn

    # --- shorthands -----------------------------------------------------------------------------------------
    @staticmethod
    def linear(t0, s0, t1, s1):
        v = (s1 - s0) / (t1 - t0)
        return Remap([K(t0, s0, v, (0, 0)), K(t1, s1, v, (0, 0))])

    @staticmethod
    def constant(t0, s0, speed, t1):
        return Remap.linear(t0, s0, t1, s0 + speed * (t1 - t0))

    @staticmethod
    def hold(t0, t1, s):
        return Remap([K(t0, s, 0.0, (0, 0)), K(t1, s, 0.0, (0, 0))])
