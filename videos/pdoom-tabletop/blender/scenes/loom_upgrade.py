"""The `loom` scene's recursive self-upgrade: Clawd conducts the panels of a Clawd 1.6x his size out of thin air;
they fly in and snap together (legs, then the jaw, the lid, the arms, the eyes last); the new one's eyes light,
it raises its arms and builds the next, 1.6x again, faster each time.

assemble(c, t0, t1) keys every part of Clawd c (bone-parented meshes) flying in from around him: each starts as a
speck (scale 0), arcs in tumbling, grows to full size and snaps into its rest place with a small overshoot. The
offsets are in character space, so they scale with the character (a 4x Clawd's panels come from 4x further).
Keys every frame (every output frame when built for 60 fps; smooth, motion-blurred: the panels move like an effect).
"""
from __future__ import annotations

import math
import random

from mathutils import Euler, Matrix, Vector

from pdoom import kit
from pdoom import timing as tm
from pdoom.timing import FPS


def parts(c):
    """Every mesh Clawd is made of, in assembly order: (object, group) with group 0 legs, 1 body, 2 lid (and what
    rides on it), 3 arms, 4 eyes."""
    out = [(o, 0) for o in c.o_legs] + [(c.o_body, 1), (c.o_lid, 2)] + [(c.o_arms[s], 3) for s in 'LR']
    seen = {o for o, _ in out}
    for (shape, side), o in c._eye_objs.items():
        out.append((o, 4))
        seen.add(o)
    # anything else parented to the rig (teeth, tongue, port...) rides with the lid or the body
    for o in c.rig.children:
        if o.type == 'MESH' and o not in seen:
            out.append((o, 2 if o.parent_bone == 'lid' else 1))
    return out


def _ease_out(u):
    u = min(max(u, 0.0), 1.0)
    return 1 - (1 - u) ** 3


def assemble(c, t0: float, t1: float, *, seed: int = 1, spread: float = 9.0):
    """Key c's parts flying in between t0 and t1 (hidden, as scale 0, before their start)."""
    rnd = random.Random(seed)
    ps = parts(c)
    span = t1 - t0
    # stagger: group g starts at a fraction of the span
    start = {0: 0.0, 1: 0.22, 2: 0.4, 3: 0.55, 4: 0.7}
    fly = 0.3 * span + 0.02
    for i, (o, g) in enumerate(ps):
        rest = o.matrix_basis.copy()
        loc0, rot0, sc0 = rest.decompose()
        c_rest = loc0
        ts = t0 + span * start[g] + rnd.uniform(0.0, 0.08) * span
        ta = min(t1, ts + fly)
        # where it comes from: outward from his middle, up, and a little toward the camera side (-y)
        out = Vector((c_rest.x, c_rest.y - 1.5, 0.0))
        if out.length < 1e-3:
            out = Vector((rnd.uniform(-1, 1), -1.0, 0.0))
        out.normalize()
        ang = rnd.uniform(-0.9, 0.9)
        out = Matrix.Rotation(ang, 3, 'Z') @ out
        p_from = c_rest + out * spread * rnd.uniform(0.8, 1.3) + Vector((0, 0, rnd.uniform(3.0, 8.0)))
        spin = Vector((rnd.uniform(-1, 1), rnd.uniform(-1, 1), rnd.uniform(-1, 1))) * math.pi * rnd.uniform(0.8, 1.6)
        f0 = int(math.floor(ts * FPS)) - 1
        f1 = int(math.ceil(ta * FPS)) + 2
        prev = None
        # every output frame when built for 60 fps (a panel flies in over ~2.5 scene frames)
        for f in (tm.out_frames(f0, f1) if tm.SMOOTH else range(f0, f1 + 1)):
            t = f / FPS
            if t <= ts:
                s, p, r = 0.0, p_from, spin
            else:
                u = (t - ts) / max(1e-4, ta - ts)
                e = _ease_out(u)
                p = p_from.lerp(c_rest, e) + Vector((0, 0, 2.0 * math.sin(math.pi * min(u, 1.0)) * (1 - e)))
                r = spin * (1 - e)
                s = min(1.0, 0.25 + 0.75 * _ease_out(u * 1.4)) * (1.0 + 0.12 * math.sin(math.pi * min(1.0, max(0.0, (u - 0.85) / 0.3))))
                if u >= 1.0:
                    s, p, r = 1.0, c_rest, Vector((0, 0, 0))
            R = rot0.to_matrix() @ Euler(r, 'XYZ').to_matrix()
            eul = R.to_euler('XYZ', prev) if prev is not None else R.to_euler('XYZ')
            prev = eul
            o.location = p
            o.rotation_euler = eul
            o.scale = sc0 * max(s, 1e-4)
            o.keyframe_insert('location', frame=f)
            o.keyframe_insert('rotation_euler', frame=f)
            o.keyframe_insert('scale', frame=f)
        o.matrix_basis = rest
        for fc in kit.fcurves(o):
            if fc.data_path in ('location', 'rotation_euler', 'scale'):
                for kp in fc.keyframe_points:
                    kp.interpolation = 'LINEAR'
    return ps
