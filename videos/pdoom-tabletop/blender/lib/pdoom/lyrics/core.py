"""The machinery under the lyrics API: fast keyframes, letter pieces laid out in rows, and the reveal / exit
animations keyed by song time (on twos by default, like the puppets).

A piece is one letter's object, parented to its row's root Empty. Pieces are built in units (a block ~1 tall); the
root carries the placement (world matrix) and the size (cm per unit) as its scale. Every piece has a rest pose in
row space; animations are lists of events (t, pose) where a pose gives the offset from rest: loc, rot (radians),
scl, and the material states on / wipe / fade (custom properties ly_on, ly_wipe, ly_fade), hide, and for stroke
letters the curve's draw-on (bevel factor).
"""
from __future__ import annotations

import math
from collections import defaultdict

import bpy
from mathutils import Euler, Matrix, Vector

from ..sets.geo import hash01
from ..timing import FPS

HALF = 0.5          # on-twos keys sit half a frame before the frame they show (like the chars library)


# ------------------------------------------------------------------------------------------------ keys


class Keys:
    """Collects keyframes and writes them in one go (much faster than keyframe_insert for thousands of keys)."""

    def __init__(self):
        self.k = defaultdict(list)
        self.ids = {}

    def add(self, idb, path: str, index: int, frame: float, value: float, interp: str = 'CONSTANT'):
        key = (idb.as_pointer(), path, index)
        self.ids[key] = idb
        self.k[key].append((frame, float(value), interp))

    def flush(self):
        for key, ks in self.k.items():
            idb = self.ids[key]
            _, path, index = key
            ad = idb.animation_data or idb.animation_data_create()
            if ad.action is None:
                ad.action = bpy.data.actions.new(f'{idb.name}.ly')
            fc = ad.action.fcurve_ensure_for_datablock(idb, path, index=max(index, 0))
            ks.sort(key=lambda x: x[0])
            merged = []
            for f, v, ip in ks:
                if merged and abs(merged[-1][0] - f) < 1e-4:
                    merged[-1] = (f, v, ip)
                else:
                    merged.append((f, v, ip))
            base = len(fc.keyframe_points)
            fc.keyframe_points.add(len(merged))
            for i, (f, v, ip) in enumerate(merged):
                kp = fc.keyframe_points[base + i]
                kp.co = (f, v)
                kp.interpolation = ip
                kp.handle_left_type = kp.handle_right_type = 'AUTO_CLAMPED'
            if base:
                fc.keyframe_points.sort()
            fc.update()
        self.k.clear()
        self.ids.clear()


def frame_of(t: float) -> int:
    """The frame that shows song time t."""
    return int(round(t * FPS))


# ------------------------------------------------------------------------------------------------ pieces


class Piece:
    """One letter: its object, where it rests in the row, and its animation events."""

    def __init__(self, obj, ch, word, letter, x, w, h, d, *, row=0, curve=None, extra=None):
        self.obj = obj
        self.ch = ch
        self.word = word            # data.Word
        self.letter = letter        # data.Letter
        self.x, self.w, self.h, self.d = x, w, h, d
        self.row = row
        self.rest = Vector((x, 0.0, 0.0))
        self.rest_rot = Euler((0.0, 0.0, 0.0))
        self.curve = curve          # curve data for draw-on (stroke letters)
        self.extra = extra or []    # other objects of this letter (lights, strings)
        self.ev: list = []          # (t, pose, mode)
        self.t_on = letter.t if letter is not None else 0.0
        self.k_index = 0            # position in its row (exit ripples)

    def at(self, t: float, mode: str = 'twos', **pose):
        self.ev.append((float(t), pose, mode))
        return self

    def frames(self, t0: float, poses: list, *, step: int = 2, mode: str = 'twos'):
        """Poses on consecutive frames from the frame that shows t0, `step` frames apart."""
        F0 = frame_of(t0)
        for k, p in enumerate(poses):
            self.at((F0 + k * step) / FPS, mode, **p)
        return (F0 + (len(poses) - 1) * step) / FPS


DEFAULT = {'loc': (0.0, 0.0, 0.0), 'rot': (0.0, 0.0, 0.0), 'scl': (1.0, 1.0, 1.0)}


def write(pieces: list[Piece], keys: Keys, *, t_start: float, t_end: float, vis=None):
    """Turn every piece's events into keys. vis: (t_show, t_hide) visibility window for the whole row copy."""
    for pc in pieces:
        o = pc.obj
        for nm in ('ly_on', 'ly_wipe', 'ly_fade'):
            if nm not in o:
                o[nm] = 1.0
        ev = sorted(pc.ev, key=lambda e: e[0])
        state = {'loc': DEFAULT['loc'], 'rot': DEFAULT['rot'], 'scl': DEFAULT['scl'], 'on': o['ly_on'],
                 'wipe': o['ly_wipe'], 'fade': o['ly_fade'], 'hide': False, 'bevel': 1.0}
        o.location = pc.rest
        o.rotation_euler = pc.rest_rot
        channels = defaultdict(list)
        for t, pose, mode in ev:
            f = t * FPS
            if mode in ('twos', 'ones'):
                fk, ip = round(f) - HALF, 'CONSTANT'
            elif mode == 'linear':
                fk, ip = f, 'LINEAR'
            else:
                fk, ip = f, 'BEZIER'
            for k, v in pose.items():
                state[k] = v
                channels[k].append((fk, v, ip))
        # transforms
        for (fk, v, ip) in channels.get('loc', []):
            p = pc.rest + Vector(v)
            for i in range(3):
                keys.add(o, 'location', i, fk, p[i], ip)
        for (fk, v, ip) in channels.get('rot', []):
            for i in range(3):
                keys.add(o, 'rotation_euler', i, fk, pc.rest_rot[i] + v[i], ip)
        for (fk, v, ip) in channels.get('scl', []):
            for i in range(3):
                keys.add(o, 'scale', i, fk, v[i], ip)
        for nm, prop in (('on', 'ly_on'), ('wipe', 'ly_wipe'), ('fade', 'ly_fade')):
            for (fk, v, ip) in channels.get(nm, []):
                keys.add(o, f'["{prop}"]', -1, fk, v, ip)
                for x in pc.extra:
                    if prop in x:
                        keys.add(x, f'["{prop}"]', -1, fk, v, ip)
        for (fk, v, ip) in channels.get('bevel', []):
            if pc.curve is not None:
                keys.add(pc.curve, 'bevel_factor_end', -1, fk, v, ip)
        # visibility: the piece's own show/hide events, clipped to the copy's window
        own = sorted(((fk, bool(v)) for fk, v, _ in channels.get('hide', [])), key=lambda x: x[0])
        if own or vis is not None:
            pts = sorted({fk for fk, _ in own} | ({vis[0] * FPS - HALF, vis[1] * FPS - HALF} if vis else set()))
            lo = vis[0] * FPS - HALF if vis else -1e9
            hi = vis[1] * FPS - HALF if vis else 1e9

            def hidden(f):
                if not own:
                    h = False
                else:
                    h = True
                    for fk, v in own:
                        if fk <= f + 1e-6:
                            h = v
                return h or f < lo - 1e-6 or f >= hi - 1e-6
            for ob in [o] + [x for x in pc.extra if isinstance(x, bpy.types.Object)]:
                keys.add(ob, 'hide_render', -1, pts[0] - 1.0, True, 'CONSTANT')
                keys.add(ob, 'hide_viewport', -1, pts[0] - 1.0, True, 'CONSTANT')
                for f in pts:
                    keys.add(ob, 'hide_render', -1, f, hidden(f), 'CONSTANT')
                    keys.add(ob, 'hide_viewport', -1, f, hidden(f), 'CONSTANT')
                ob.hide_render = ob.hide_viewport = True


# ------------------------------------------------------------------------------------------------ reveals


def _jit(pc, k, amp):
    return (2 * hash01(pc.obj.name, k) - 1) * amp


def reveal_pop(pc: Piece, t: float, *, hop=0.45, flat=False):
    """Pop up on twos with a squash: tiny and squashed, stretched in the air, squash on landing, settle."""
    up = (0.0, -1.0, 0.0) if flat else (0.0, 0.0, 1.0)
    j = lambda k: _jit(pc, k, 0.06)
    seq = [
        dict(hide=False, scl=(0.55, 0.55, 0.32) if not flat else (0.55, 0.32, 0.55), loc=(0, 0, 0), rot=(0, 0, j(1))),
        dict(scl=(0.84, 0.84, 1.26) if not flat else (0.84, 1.26, 0.84), loc=tuple(hop * c for c in up),
             rot=(j(2), 0, j(3))),
        dict(scl=(1.16, 1.16, 0.8) if not flat else (1.16, 0.8, 1.16), loc=(0, 0, 0), rot=(0, 0, j(4) * 0.5)),
        dict(scl=(0.97, 0.97, 1.05) if not flat else (0.97, 1.05, 0.97)),
        dict(scl=(1.0, 1.0, 1.0), rot=(0, 0, 0)),
    ]
    pc.at(t - 3.0, 'twos', hide=True, scl=(0.0, 0.0, 0.0))
    return pc.frames(t, seq)


def reveal_appear(pc: Piece, t: float, **_):
    """Just there on the frame (stamps, typewriter keys, screen text)."""
    pc.at(t - 3.0, 'twos', hide=True)
    pc.at(t, 'ones', hide=False, scl=(1.0, 1.0, 1.0), wipe=1.0, on=1.0)
    return t


def reveal_type(pc: Piece, t: float, *, bump=0.08, **_):
    """A key strike: the letter lands a touch big (the key's impact), then settles on the next frame."""
    pc.at(t - 3.0, 'twos', hide=True, loc=(0, 0, 0), scl=(1.0, 1.0, 1.0))
    b = 1.0 + bump
    pc.frames(t, [dict(hide=False, scl=(b, 1.0, b), on=1.0, wipe=1.0),
                  dict(scl=(1.0, 1.0, 1.0))], step=1, mode='ones')
    return t + 1 / FPS


def reveal_draw(pc: Piece, t: float, *, dur=None, **_):
    """Draw on: the wipe (or the stroke's bevel factor) runs across the letter, smooth at 24 fps."""
    d = dur if dur is not None else 0.14
    pc.at(t - 3.0, 'twos', hide=True, wipe=0.0, bevel=0.0)
    pc.at(t - 0.5 / FPS, 'ones', hide=False)
    pc.at(t, 'linear', wipe=0.0, bevel=0.0)
    pc.at(t + d, 'linear', wipe=1.0, bevel=1.0)
    return t + d


def reveal_light(pc: Piece, t: float, *, preview=True, flicker=True, **_):
    """A lamp / tube lights: unlit (visible if preview) until t, then a flicker on ones and full."""
    if not preview:
        pc.at(t - 3.0, 'twos', hide=True)
        pc.at(t, 'ones', hide=False)
    seq = [0.7, 0.12, 1.0, 0.45, 1.0] if flicker else [1.0]
    pc.at(t - 1.0 / FPS, 'ones', on=0.0)
    for k, v in enumerate(seq):
        pc.at(t + k / FPS, 'ones', on=v)
    return t + len(seq) / FPS


def reveal_flip(pc: Piece, t: float, *, flat=True, axis='Z', **_):
    """Face down (the blank back showing) until t, then it flips over with a hop and lands face up (tiles, blocks)."""
    hop_dir = Vector((0, -1, 0)) if flat else Vector((0, 0, 1))
    ax = {'X': 0, 'Y': 1, 'Z': 2}[axis]

    def rot(a):
        r = [0.0, 0.0, 0.0]
        r[ax] = a
        return tuple(r)
    lift = 0.6 * max(pc.w, pc.h) if flat else 0.35
    seq = [dict(rot=rot(math.pi * 0.62), loc=tuple(hop_dir * lift)),
           dict(rot=rot(math.pi * 0.2), loc=tuple(hop_dir * lift * 0.6)),
           dict(rot=rot(0.0), loc=(0, 0, 0), scl=(1.06, 1.06, 0.94) if not flat else (1.06, 0.9, 1.06)),
           dict(scl=(1.0, 1.0, 1.0))]
    pc.at(t - 1.0 / FPS, 'twos', rot=rot(math.pi))
    return pc.frames(t, seq)


def reveal_blank(pc: Piece, t: float, *, flat=True, axis='Z', how='pop'):
    """The unsung state for flips: the piece arrives face down at t (popping in)."""
    ax = {'X': 0, 'Y': 1, 'Z': 2}[axis]
    r = [0.0, 0.0, 0.0]
    r[ax] = math.pi
    pc.at(t - 3.0, 'twos', hide=True, scl=(0.0, 0.0, 0.0), rot=tuple(r))
    if how == 'pop':
        pc.frames(t, [dict(hide=False, scl=(0.6, 0.6, 0.6), rot=tuple(r)), dict(scl=(1.08, 1.08, 1.08)),
                      dict(scl=(1.0, 1.0, 1.0))])
    else:
        pc.at(t, 'twos', hide=False, scl=(1.0, 1.0, 1.0), rot=tuple(r))


def reveal_slam(pc: Piece, t: float, *, height=7.0, frames=4, flat=False, **_):
    """Dropped from high above: falls fast on ones and lands ON t with a heavy squash (brass, the title)."""
    up = Vector((0, -1, 0)) if flat else Vector((0, 0, 1))
    F = frame_of(t)
    pc.at((F - frames - 3) / FPS, 'ones', hide=True)
    for k in range(frames):
        a = (frames - k) / frames
        h = height * a * a
        pc.at((F - frames + k) / FPS, 'ones', hide=False, loc=tuple(up * h),
              rot=(_jit(pc, k, 0.12) * a, _jit(pc, k + 9, 0.1) * a, _jit(pc, k + 5, 0.25) * a),
              scl=(0.94, 0.94, 1.1) if not flat else (0.94, 1.1, 0.94))
    squash = (1.12, 1.12, 0.8) if not flat else (1.12, 0.8, 1.12)
    pc.frames(t, [dict(loc=(0, 0, 0), rot=(0, 0, 0), scl=squash),
                  dict(loc=tuple(up * 0.12), scl=(0.97, 0.97, 1.05) if not flat else (0.97, 1.05, 0.97)),
                  dict(loc=(0, 0, 0), scl=(1.0, 1.0, 1.0))], step=2, mode='twos')
    return t


def reveal_tumble(pc: Piece, t: float, *, frames=8, side=1.0, flat=False, **_):
    """Tumbles in along an arc (a toss from the side and above) and lands on t with a small bounce."""
    up = Vector((0, -1, 0)) if flat else Vector((0, 0, 1))
    F = frame_of(t)
    s = side if side else (1.0 if hash01(pc.obj.name, 'side') > 0.5 else -1.0)
    start = Vector((s * (3.0 + 2 * hash01(pc.obj.name, 'dx')), 0.0, 0.0)) + up * 2.5
    spin = (2 * hash01(pc.obj.name, 'sp') - 1) * math.pi * 1.5
    pc.at((F - frames - 3) / FPS, 'ones', hide=True)
    for k in range(frames):
        a = k / frames
        p = start * (1 - a) + up * (4.0 * a * (1 - a))
        pc.at((F - frames + k) / FPS, 'ones', hide=False, loc=tuple(p),
              rot=(spin * (1 - a), 0.5 * spin * (1 - a), -s * (1 - a) * 1.2))
    pc.frames(t, [dict(loc=(0, 0, 0), rot=(0, 0, 0), scl=(1.1, 1.1, 0.86) if not flat else (1.1, 0.86, 1.1)),
                  dict(loc=tuple(up * 0.3), rot=(0, 0, _jit(pc, 3, 0.08)), scl=(1, 1, 1)),
                  dict(loc=(0, 0, 0), rot=(0, 0, 0))])
    return t


def reveal_slide(pc: Piece, t: float, *, dist=6.0, frames=6, side=-1.0, **_):
    """Slides in along the row from one side and stops on t (a little overshoot)."""
    F = frame_of(t)
    pc.at((F - frames - 3) / FPS, 'ones', hide=True)
    for k in range(frames):
        a = 1 - (k / frames)
        pc.at((F - frames + k) / FPS, 'ones', hide=False, loc=(side * dist * a * a, 0, 0))
    pc.frames(t, [dict(loc=(-side * 0.12, 0, 0)), dict(loc=(0, 0, 0))])
    return t


def reveal_grow(pc: Piece, t: float, *, dur=0.35, **_):
    """Bent wire grows along its strokes (smooth)."""
    return reveal_draw(pc, t, dur=dur)


REVEALS = {'pop': reveal_pop, 'appear': reveal_appear, 'type': reveal_type, 'draw': reveal_draw,
           'light': reveal_light, 'flip': reveal_flip, 'slam': reveal_slam, 'tumble': reveal_tumble,
           'slide': reveal_slide, 'grow': reveal_grow, 'stamp': reveal_appear}


# ------------------------------------------------------------------------------------------------ exits


def _pivot(pc, axis_vec, angle, pivot):
    """(loc offset, rot euler) that rotate the piece by angle about axis_vec through pivot (piece space)."""
    R = Matrix.Rotation(angle, 3, Vector(axis_vec))
    pv = Vector(pivot)
    off = pv - R @ pv
    return tuple(off), tuple(R.to_euler('XYZ'))


def exit_topple(pc: Piece, t: float, *, back=True, flat=False, stagger=1, **_):
    """Tips over (backwards) about its bottom edge like a domino, on twos, in a left-to-right ripple."""
    t = t + pc.k_index * stagger / FPS
    sgn = -1 if back else 1
    piv = (0.0, 0.0 if back else -pc.d, 0.0)
    seq = []
    for a in (0.3, 0.75, 1.62, 1.5708):
        off, rot = _pivot(pc, (1, 0, 0), sgn * a, piv)
        seq.append(dict(loc=off, rot=rot))
    end = pc.frames(t, seq)
    return end


def exit_drop(pc: Piece, t: float, *, stagger=None, flat=False, floor=None, **_):
    """Tips backwards off its shelf and drops out of sight, on ones, in a quick left-to-right ripple (~8 frames).
    floor: how far below its rest it may fall (units; the stand passes the height of the surface it stands on)."""
    n = max(getattr(pc, 'n_row', 8), 1)
    st = (3.0 / n) if stagger is None else stagger
    t = t + round(pc.k_index * st) / FPS
    fl = -abs(floor) if floor is not None else -1e9
    seq = []
    for k, (a, dz, dy) in enumerate(((0.45, 0.05, 0.1), (1.1, -0.2, 0.45), (1.8, -1.0, 0.9), (2.3, -2.4, 1.3),
                                     (2.6, -4.2, 1.6))):
        off, rot = _pivot(pc, (1, 0, 0), -a, (0.0, 0.0, 0.0))
        seq.append(dict(loc=(off[0], off[1] + dy, max(off[2] + dz, fl)), rot=rot))
    seq.append(dict(hide=True))
    return pc.frames(t, seq, step=1, mode='ones')


def exit_sweep(pc: Piece, t: float, *, side=1.0, stagger=0, **_):
    """Swept away sideways, spinning."""
    t = t + pc.k_index * stagger / FPS
    seq = []
    for k in range(1, 6):
        a = k / 5
        seq.append(dict(loc=(side * 9 * a * a, -0.5 * a, 0.8 * a * (1 - a)), rot=(0, 0, -side * 2.5 * a)))
    seq.append(dict(hide=True))
    return pc.frames(t, seq, step=1, mode='ones')


def exit_shrink(pc: Piece, t: float, *, stagger=1, **_):
    t = t + pc.k_index * stagger / FPS
    return pc.frames(t, [dict(scl=(1.1, 1.1, 1.1)), dict(scl=(0.6, 0.6, 0.6)), dict(scl=(0.2, 0.2, 0.2)),
                         dict(hide=True, scl=(0.0, 0.0, 0.0))])


def exit_fade(pc: Piece, t: float, *, dur=0.4, **_):
    """Fades with the light: lit things go dark (ly_on), paint fades out (ly_fade)."""
    pc.at(t, 'linear', fade=1.0, on=1.0)
    pc.at(t + dur, 'linear', fade=0.0, on=0.0)
    pc.at(t + dur + 1 / FPS, 'ones', hide=True)
    return t + dur


def exit_none(pc: Piece, t: float, **_):
    return t


def exit_eaten(pc: Piece, t: float, *, target=None, mouth=None, frames=6, stagger=1, **_):
    """Sucked into a mouth: flies along an arc to `target` (a point in the row's space, or a function of time
    returning one) and vanishes on arrival at t + frames (for Clawd: pass lyrics.mouth(clawd, row) as target)."""
    t = t + pc.k_index * stagger / FPS
    F = frame_of(t)
    for k in range(1, frames + 1):
        a = k / frames
        tt = (F + k) / FPS
        tgt = target(tt) if callable(target) else Vector(target)
        start = pc.rest
        p = start.lerp(tgt, a * a) + Vector((0, 0, 1.2 * math.sin(math.pi * a)))
        off = p - start
        s = max(0.05, 1 - 0.85 * a)
        pc.at(tt, 'ones', loc=tuple(off), rot=(a * 2.0, a * 1.3, a * 3.0), scl=(s, s, s))
    pc.at((F + frames + 1) / FPS, 'ones', hide=True)
    return (F + frames + 1) / FPS


EXITS = {'topple': exit_topple, 'drop': exit_drop, 'sweep': exit_sweep, 'shrink': exit_shrink, 'fade': exit_fade,
         'none': exit_none, 'eaten': exit_eaten}
