"""A domino run: real rigid bodies standing along a path with rounded corners (the sharp left turn), pushed over at
a song time, falling in a chain.

    from pdoom.fx import dominoes, rigid
    run = dominoes.run('run', points=[(-60, -20), (10, -20), (10, 15)], t0=82.1, spacing=2.3)
    dominoes.land(run, index=-1, t=82.72)    # retime the push so the LAST domino lands on 82.72 (bakes twice)
    rigid.bake()                             # (land() leaves the world baked; fx.bake() at the end re-bakes it all)
    times = run['fall_times']                # song time each domino passes 60 degrees (after land / measure)

Toy wooden dominoes 4.8 x 2.4 x 0.75 cm, lacquered in a cycling palette. They start asleep (Bullet deactivation),
so they stand perfectly still until hit. Chain speed is set by spacing: measured at 1 BU = 1 cm with 4.8 cm
dominoes (docs/lib/fx.md has the table): the wave runs ~22-30 dominoes/s. On a beat grid that is ~10-14 dominoes
per beat at 132 BPM; to put a hit on a beat, retime the push with land(), or break the run into segments.
"""
from __future__ import annotations

import math
import random

import bpy
from mathutils import Matrix, Vector

from .. import kit
from ..timing import FPS
from . import log

SIZE = (2.4, 0.75, 4.8)          # width, thickness, height (cm)
PALETTE = ('#D2382E', '#F2C230', '#2F6FD0', '#3AA35B', '#F2EBDD', '#E07B39')


def path(points, radius: float = 3.0, step: float = 0.05):
    """Dense samples (pos, tangent) along a polyline in the XY plane with corners rounded to `radius` cm."""
    P = [Vector((p[0], p[1], 0.0)) for p in points]
    segs = []
    cur = P[0]
    for i in range(1, len(P) - 1):
        a, b, c = P[i - 1], P[i], P[i + 1]
        d1, d2 = (b - a).normalized(), (c - b).normalized()
        ang = math.acos(max(-1.0, min(1.0, d1.dot(d2))))
        if ang < 1e-3:
            continue
        cut = min(radius * math.tan(ang / 2), (b - a).length * 0.49, (c - b).length * 0.49)
        r = cut / math.tan(ang / 2)
        p1, p2 = b - d1 * cut, b + d2 * cut
        segs.append(('L', cur, p1))
        # arc centre: to the inside of the turn
        side = 1.0 if d1.cross(d2).z > 0 else -1.0
        n1 = Vector((-d1.y, d1.x, 0.0)) * side
        ctr = p1 + n1 * r
        segs.append(('A', ctr, r, p1, p2, side))
        cur = p2
    segs.append(('L', cur, P[-1]))
    out = []
    for sg in segs:
        if sg[0] == 'L':
            a, b = sg[1], sg[2]
            L = (b - a).length
            n = max(1, int(L / step))
            t = (b - a).normalized() if L > 1e-9 else Vector((1, 0, 0))
            for k in range(n):
                out.append((a.lerp(b, k / n), t))
        else:
            _, ctr, r, p1, p2, side = sg
            a0 = math.atan2(p1.y - ctr.y, p1.x - ctr.x)
            a1 = math.atan2(p2.y - ctr.y, p2.x - ctr.x)
            da = (a1 - a0 + math.pi) % (2 * math.pi) - math.pi
            n = max(2, int(abs(da) * r / step))
            for k in range(n):
                a = a0 + da * k / n
                pos = Vector((ctr.x + r * math.cos(a), ctr.y + r * math.sin(a), 0.0))
                t = Vector((-math.sin(a), math.cos(a), 0.0)) * (1 if da > 0 else -1)
                out.append((pos, t))
    out.append((P[-1], (P[-1] - P[-2]).normalized()))
    return out


def _domino_mesh(size, bevel=0.12):
    name = f'domino.{size[0]}x{size[1]}x{size[2]}'
    if name in bpy.data.meshes:
        return bpy.data.meshes[name]
    import bmesh
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    bmesh.ops.scale(bm, vec=Vector(size), verts=bm.verts)
    bmesh.ops.bevel(bm, geom=list(bm.edges), offset=bevel, segments=3, affect='EDGES', profile=0.5)
    for f in bm.faces:
        f.smooth = True
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    me.materials.append(_mat(PALETTE[0]))
    return me


def _mat(color: str):
    return kit.mat(f'domino.{color}', color, rough=0.28, coat=0.6, coat_rough=0.12, spec=0.5)


def run(name: str = 'dominoes', *, points, t0: float, spacing: float = 2.3, size=SIZE, radius: float = 3.0,
        turn_spacing: float = 0.8, colors=PALETTE, mass: float = 0.02, friction: float = 0.5,
        bounce: float = 0.02, push_deg: float = 14.0, push_time: float = 0.12, z: float = 0.0, coll=None,
        seed: int = 1) -> dict:
    """Stand dominoes along points (XY polyline at height z) every `spacing` cm (turn_spacing x that inside
    corners), facing along the path. At song time t0 the first one is pushed (tipped push_deg over push_time,
    then released spinning) and the chain runs. Returns {'objects', 'first', 't0', 'fall_times': None}."""
    from . import rigid
    rigid.world(substeps=20, iterations=15)
    coll = coll or kit.collection(name)
    samples = path(points, radius)
    me = _domino_mesh(tuple(size))
    objs = []
    s_acc, s_next = 0.0, 0.0
    prev = samples[0][0]
    k = 0
    for i, (pos, tan) in enumerate(samples):
        if i:
            s_acc += (pos - prev).length
        prev = pos
        if s_acc + 1e-6 < s_next:
            continue
        # tighter spacing where the path bends
        j = min(i + 20, len(samples) - 1)
        bend = 1.0 - max(0.0, tan.dot(samples[j][1]))
        step = spacing * (turn_spacing if bend > 0.02 else 1.0)
        s_next = s_acc + step
        ob = bpy.data.objects.new(f'{name}.{k:03d}', me)
        coll.objects.link(ob)
        yaw = math.atan2(tan.y, tan.x) - math.pi / 2       # local Y (thickness) along the path
        ob.location = (pos.x, pos.y, z + size[2] / 2)
        ob.rotation_euler = (0.0, 0.0, yaw)
        objs.append(ob)
        k += 1
    for i, ob in enumerate(objs):
        ob.material_slots[0].link = 'OBJECT'
        ob.material_slots[0].material = _mat(colors[i % len(colors)])
        rb = rigid.active(ob, mass=mass, shape='BOX', friction=friction, bounce=bounce, damping=(0.04, 0.1),
                          margin=0.02)
        rb.use_start_deactivated = i > 0
        rb.deactivate_linear_velocity = 0.3
        rb.deactivate_angular_velocity = 0.3
    first = objs[0]
    _push(first, t0, size, push_deg, push_time, z)
    length = sum((samples[i + 1][0] - samples[i][0]).length for i in range(len(samples) - 1))
    log(f'dominoes {name}: {len(objs)} along {length:.0f} cm, push at t={t0:.3f}')
    return {'objects': objs, 'first': first, 't0': t0, 'fall_times': None, 'size': size, 'z': z,
            'push': (push_deg, push_time)}


def _push(ob, t0: float, size, deg: float, dur: float, z: float):
    """Key the first domino tipping about its front bottom edge from t0 - dur to t0, then release it."""
    from . import rigid
    base = ob.matrix_world.copy()
    fwd = (base.to_3x3() @ Vector((0, 1, 0))).normalized()     # the path direction (its thin axis)
    pivot = base.translation + fwd * (size[1] / 2) - Vector((0, 0, size[2] / 2))
    axis = Vector((0, 0, 1)).cross(fwd).normalized()
    # remove earlier push keys
    if ob.animation_data:
        ob.animation_data_clear()
    fa = int(math.floor((t0 - dur) * FPS + 1e-6))
    fb = int(math.floor(t0 * FPS + 1e-6))
    for f in range(fa - 1, fb + 1):
        u = min(1.0, max(0.0, (f - fa) / max(1, fb - fa)))
        ang = math.radians(deg) * u * u
        R = Matrix.Rotation(ang, 4, axis)
        m = Matrix.Translation(pivot) @ R @ Matrix.Translation(-pivot) @ base
        ob.matrix_world = m
        ob.keyframe_insert('location', frame=f)
        ob.keyframe_insert('rotation_euler', frame=f)
    ob.matrix_world = base
    for fc in kit.fcurves(ob):
        for kp in fc.keyframe_points:
            kp.interpolation = 'LINEAR'
    rigid.release(ob, fb / FPS)
    ob.rigid_body.use_start_deactivated = False


def measure(r: dict, angle: float = 60.0) -> list:
    """After a bake: the song time each domino first tilts past `angle` degrees, interpolated between frames
    (None if it never falls). Stores it in r['fall_times']."""
    sc = bpy.context.scene
    objs = r['objects']
    lim = math.cos(math.radians(angle))
    times = [None] * len(objs)
    prev = [1.0] * len(objs)
    f0 = int(math.floor(r['t0'] * FPS)) - 1
    for f in range(max(sc.frame_start, f0), sc.frame_end + 1):
        sc.frame_set(f)
        for i, o in enumerate(objs):
            up = (o.matrix_world.to_3x3() @ Vector((0, 0, 1))).z
            if times[i] is None and up < lim:
                u = (prev[i] - lim) / max(1e-6, prev[i] - up)
                times[i] = (f - 1 + u) / FPS
            prev[i] = up
        if all(t is not None for t in times):
            break
    sc.frame_set(sc.frame_start)
    r['fall_times'] = times
    return times


def land(r: dict, index: int, t: float, *, angle: float = 60.0, tries: int = 3) -> float:
    """Retime the push so domino `index` (negative counts from the end) passes `angle` at song time t: bake,
    measure, shift the push by whole frames, repeat (up to `tries` bakes) until within half a frame. The push is
    keyed on whole frames, so that is the resolution. Other rigid bodies in the scene are baked too (cost).
    Returns the new t0."""
    from . import rigid
    for k in range(tries):
        rigid.bake(f'dominoes (timing {k + 1})')
        got = measure(r, angle)[index]
        if got is None:
            raise RuntimeError(f'domino {index} never fell: the chain broke (spacing too wide at a turn?)')
        err = t - got
        if abs(err) <= 0.5 / FPS or k == tries - 1:
            break
        r['t0'] += round(err * FPS) / FPS
        _push(r['first'], r['t0'], r['size'], *r['push'], r['z'])
    log(f'dominoes: domino {index} passes {angle:g} deg at {got:.3f} (asked {t:.3f}); push at {r["t0"]:.3f}')
    return r['t0']
