"""The `leftturn` domino run: classic black lacquered dominoes with white pips (the same look as backprop's last
domino), real Bullet rigid bodies standing along a snaking path that takes a SHARP LEFT TURN, timed by tuning the
spacing of each leg so the corner falls on the beat and the last domino strikes the broken jar on "there".

The run continues exactly from backprop's domino: it stands at world (44, -27, 0), yaw -60, tapped at 81.87 and
falling toward (+0.87, +0.5) about its back-bottom edge (backprop_fall.py integrates th'' = 3g/2h sin th). Here that
same domino is keyed with the same integration until the scene starts, then released as a rigid body, so it carries
its angular velocity into the chain. The second domino stands FIRST_GAP cm on: backprop's last frame (82.0) shows
the first domino at 20 deg, just short of touching it.

The path is a turtle walk from the second domino (heading 30 deg): leg A snakes right, then left, along the front of
the desk; the SHARP LEFT TURN (TURN deg on radius R_TURN); leg B runs up toward the window to the broken jar lying on
its side (its axis JAR_GAP cm past the last domino). Tight spacing (~1.1-1.5 cm for 0.8 cm thick dominoes) makes a
dense ripple; the fallen dominoes lean on each other at 50-60 deg.
"""
from __future__ import annotations

import math
import random

import bmesh
import bpy
from mathutils import Matrix, Vector

from pdoom import kit
from pdoom.fx import log, rigid
from pdoom.sets import materials as M
from pdoom.timing import FPS

SIZE = (2.4, 0.8, 4.8)                      # width, thickness, height (cm): backprop's domino
BP_DOMINO = Vector((44.0, -27.0, 0.0))
BP_YAW = -60.0
BP_TAP = 81.87
FALL_DIR = Vector((math.sin(math.radians(60.0)), math.cos(math.radians(60.0)), 0.0))   # (+0.866, +0.5)
PIP_R, PIP_D, PIP_Y = 0.17, 0.06, -0.41      # backprop's pips: radius, depth, centre y (proud of the -y face)
PIP_OFF = 0.54

FIRST_GAP = 2.8                              # backprop's domino -> the second one (centre to centre, cm)
R_TURN = 4.0
TURN = 115.0
# ('arc', r, +left/-right deg) | ('line', L): up and to the left, a U-turn right, down, left onto heading 0
LEG_A = [('arc', 6.0, 60.0), ('line', 4.0), ('arc', 5.5, -180.0), ('line', 4.0), ('arc', 6.0, 90.0), ('line', 4.0)]
LEG_B = 31.0
JAR_GAP = 0.4 + 8.2                          # last domino centre -> the jar's axis (horizontal, cm)
MASS, FRICTION = 0.02, 0.45


# ------------------------------------------------------------------------------------------------ backprop's domino


def bp_angle():
    """backprop's domino fall: theta(t) (radians) about its back-bottom edge, the same integration as
    backprop_fall.py (th0 0.02, w0 0.9, th'' = 306 sin th, capped at 84 deg)."""
    th, w, t, dt = 0.02, 0.9, BP_TAP, 1.0 / (FPS * 16)
    samples = []
    while t < BP_TAP + 1.5:
        samples.append((t, th))
        w += 306.0 * math.sin(th) * dt
        th = min(math.radians(84), th + w * dt)
        t += dt

    def a(tt):
        if tt <= BP_TAP:
            return 0.0
        return min(samples, key=lambda s: abs(s[0] - tt))[1]
    return a


def bp_matrix(a: float) -> Matrix:
    """World matrix of backprop's domino at fall angle a, origin at its CENTRE (for the rigid body)."""
    piv = Vector((0.0, 0.4, 0.0))
    return (Matrix.Translation(BP_DOMINO) @ Matrix.Rotation(math.radians(BP_YAW), 4, 'Z') @ Matrix.Translation(piv)
            @ Matrix.Rotation(-a, 4, 'X') @ Matrix.Translation(-piv) @ Matrix.Translation((0, 0, SIZE[2] / 2)))


# ------------------------------------------------------------------------------------------------ the look

DICE = {0: [], 1: [(0, 0)], 2: [(-1, 1), (1, -1)], 3: [(-1, 1), (0, 0), (1, -1)],
        4: [(-1, 1), (1, 1), (-1, -1), (1, -1)], 5: [(-1, 1), (1, 1), (0, 0), (-1, -1), (1, -1)],
        6: [(-1, 1), (1, 1), (-1, 0), (1, 0), (-1, -1), (1, -1)]}


def mats():
    blk = M.solid('bp.domino', '#121212', rough=0.2, coat=0.8, coat_rough=0.05)
    pip = M.solid('bp.pip', '#F2EEE6', rough=0.3)
    return blk, pip


def domino_mesh(top: int, bottom: int):
    """One domino [top|bottom] as a single mesh (origin at its centre): a bevelled black body and raised white pips
    and centre bar on the -y face. Shared by every domino with that face."""
    name = f'lt.domino.{top}{bottom}'
    if name in bpy.data.meshes:
        return bpy.data.meshes[name]
    blk, pip = mats()
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    bmesh.ops.scale(bm, vec=Vector(SIZE), verts=bm.verts)
    bmesh.ops.bevel(bm, geom=list(bm.edges), offset=0.12, segments=3, affect='EDGES', profile=0.5)
    for f in bm.faces:
        f.material_index = 0
        f.smooth = True

    def paint(res):
        for v in res['verts']:
            for f in v.link_faces:
                f.material_index = 1
                f.smooth = False

    for half, n in ((1, top), (-1, bottom)):
        for px, pz in DICE[n]:
            M4 = Matrix.Translation((px * PIP_OFF, PIP_Y, half * 1.2 + pz * PIP_OFF)) @ \
                Matrix.Rotation(math.radians(90), 4, 'X')
            paint(bmesh.ops.create_cone(bm, cap_ends=True, segments=12, radius1=PIP_R, radius2=PIP_R, depth=PIP_D,
                                        matrix=M4))
    paint(bmesh.ops.create_cube(bm, size=1.0, matrix=Matrix.Translation((0, -0.41, 0)) @
                                Matrix.Diagonal((1.9, 0.05, 0.08, 1))))
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    me.materials.append(blk)
    me.materials.append(pip)
    return me


# ------------------------------------------------------------------------------------------------ layout


def turtle(p0: Vector, heading_deg: float, moves, step: float = 0.05):
    """Dense samples [(pos, tangent, move index)] along turtle moves from p0 (XY)."""
    out = []
    p = Vector((p0.x, p0.y, 0.0))
    h = math.radians(heading_deg)
    for mi, mv in enumerate(moves):
        if mv[0] == 'line':
            L = mv[1]
            n = max(1, int(L / step))
            d = Vector((math.cos(h), math.sin(h), 0.0))
            for k in range(n):
                out.append((p + d * (L * k / n), d.copy(), mi))
            p = p + d * L
        else:
            r, deg = mv[1], mv[2]
            sgn = 1.0 if deg > 0 else -1.0
            ctr = p + Vector((math.cos(h + sgn * math.pi / 2), math.sin(h + sgn * math.pi / 2), 0.0)) * r
            a0 = math.atan2(p.y - ctr.y, p.x - ctr.x)
            da = math.radians(deg)
            n = max(2, int(abs(da) * r / step))
            for k in range(n):
                a = a0 + da * k / n
                pos = Vector((ctr.x + r * math.cos(a), ctr.y + r * math.sin(a), 0.0))
                hh = h + da * k / n
                out.append((pos, Vector((math.cos(hh), math.sin(hh), 0.0)), mi))
            h += da
            p = Vector((ctr.x + r * math.cos(a0 + da), ctr.y + r * math.sin(a0 + da), 0.0))
    out.append((p, Vector((math.cos(h), math.sin(h), 0.0)), len(moves)))
    return out


def moves():
    return LEG_A + [('arc', R_TURN, TURN), ('line', LEG_B)]


def heading_b() -> Vector:
    a = math.radians(30.0 + sum(m[2] for m in LEG_A if m[0] == 'arc') + TURN)
    return Vector((math.cos(a), math.sin(a), 0.0))


def path_samples():
    return turtle(BP_DOMINO + FALL_DIR * FIRST_GAP, 30.0, moves())


def corner_points():
    """Key points (XY, z 0): the second domino, the start and the end of the sharp turn, the end of leg B."""
    smp = path_samples()
    ti = len(LEG_A)
    c0 = next(p for p, t, mi in smp if mi == ti)
    c1 = next(p for p, t, mi in smp if mi == ti + 1)
    return [smp[0][0], c0, c1, smp[-1][0]]


def jar_center() -> Vector:
    """The broken jar's axis centre on the desk (z 0): JAR_GAP past the end of leg B."""
    return corner_points()[-1] + heading_b() * JAR_GAP


def layout(spacing_a: float, spacing_b: float):
    """Stations (pos, tangent, leg) along the path: leg A every spacing_a, the corner 'C' (kept wide enough that the
    inner edges clear), leg B every spacing_b. The first station is the second domino."""
    samples = path_samples()
    ti = len(LEG_A)
    c_min = (SIZE[1] + 0.16) * R_TURN / (R_TURN - SIZE[0] / 2)
    # arc length of every sample, and of the leg boundaries
    s = [0.0]
    for (p0, _, _), (p1, _, _) in zip(samples, samples[1:]):
        s.append(s[-1] + (p1 - p0).length)
    s_c0 = next(s[i] for i, smp in enumerate(samples) if smp[2] == ti)
    s_c1 = next(s[i] for i, smp in enumerate(samples) if smp[2] == ti + 1)
    s_end = s[-1]
    # each leg gets a whole number of steps, so the corner starts and ends on a domino and the last one stands
    # exactly at the path's end (the jar is placed from it)
    marks = []
    for a, b, sp in ((0.0, s_c0, spacing_a), (s_c0, s_c1, max(spacing_a, c_min)), (s_c1, s_end, spacing_b)):
        n = max(1, round((b - a) / sp))
        marks += [a + (b - a) * k / n for k in range(n)]
    marks.append(s_end)
    out = []
    j = 0
    for m in marks:
        while j < len(s) - 2 and s[j + 1] < m:
            j += 1
        u = 0.0 if s[j + 1] <= s[j] else (m - s[j]) / (s[j + 1] - s[j])
        u = min(1.0, max(0.0, u))
        pos = samples[j][0].lerp(samples[j + 1][0], u)
        tan = samples[j][1].lerp(samples[j + 1][1], u).normalized()
        leg = 'A' if m < s_c0 - 1e-6 else ('C' if m < s_c1 - 1e-6 else 'B')
        out.append((pos, tan, leg))
    return out


# ------------------------------------------------------------------------------------------------ build


def _body(ob):
    rb = rigid.active(ob, mass=MASS, shape='BOX', friction=FRICTION, bounce=0.02, damping=(0.04, 0.1), margin=0.02)
    rb.use_start_deactivated = True
    rb.deactivate_linear_velocity = 0.3
    rb.deactivate_angular_velocity = 0.3
    return rb


def build(coll, *, spacing_a: float, spacing_b: float, t_start: float, seed: int = 3):
    """The run: backprop's domino (keyed, released at t_start) + the stations as sleeping rigid bodies.
    Returns a dict: 'first', 'objects' (all made; active(r) = the ones in use), 'legs', 'points', 'stations'."""
    rigid.world(substeps=24, iterations=20, preroll=0.25)
    first = bpy.data.objects.new('lt.domino.000', domino_mesh(5, 2))
    coll.objects.link(first)
    a = bp_angle()
    f_rel = int(math.floor(t_start * FPS + 1e-6))
    for f in range(f_rel - 8, f_rel + 1):
        first.matrix_world = bp_matrix(a(f / FPS))
        first.keyframe_insert('location', frame=f)
        first.keyframe_insert('rotation_euler', frame=f)
    for fc in kit.fcurves(first):
        for kp in fc.keyframe_points:
            kp.interpolation = 'LINEAR'
    rigid.active(first, mass=MASS, shape='BOX', friction=FRICTION, bounce=0.02, damping=(0.04, 0.1), margin=0.02)
    rigid.release(first, t_start)
    first.rigid_body.use_start_deactivated = False
    r = {'first': first, 'objects': [first], 'legs': ['bp'], 'points': corner_points(), 'coll': coll,
         'seed': seed, 'spacing': (spacing_a, spacing_b)}
    place(r, layout(spacing_a, spacing_b))
    lg = r['legs']
    log(f'leftturn run: {r["n"]} dominoes (A {lg.count("A")}, corner {lg.count("C")}, B {lg.count("B")})')
    return r


def place(r, st):
    """Stand the run's dominoes (all but backprop's) on the stations st. Extra objects are parked far below the
    desk (hidden, disabled), missing ones are made (so the tuner can change the count)."""
    objs = r['objects']
    need = len(st) + 1
    faces = [(t, b) for t in range(7) for b in range(t + 1)]
    rnd = random.Random(r['seed'])
    while len(objs) < need:
        tb = faces[rnd.randrange(len(faces))]
        if rnd.random() < 0.5:
            tb = (tb[1], tb[0])
        ob = bpy.data.objects.new(f'lt.domino.{len(objs):03d}', domino_mesh(*tb))
        r['coll'].objects.link(ob)
        _body(ob)
        objs.append(ob)
    r['legs'] = ['bp'] + [leg for _, _, leg in st]
    for i, ob in enumerate(objs[1:], start=1):
        if i < need:
            pos, tan, leg = st[i - 1]
            yaw = math.atan2(tan.y, tan.x) - math.pi / 2
            ob.location = (pos.x, pos.y, SIZE[2] / 2)
            ob.rotation_euler = (0.0, 0.0, yaw)
            ob.hide_render = False
            ob.rigid_body.enabled = True
        else:
            ob.location = (0.0, 0.0, -3000.0 - 10 * i)
            ob.hide_render = True
            ob.rigid_body.enabled = False
    r['stations'] = st
    r['n'] = need


def active(r):
    return r['objects'][:r['n']]


def tilt(o) -> float:
    return math.degrees(math.acos(max(-1.0, min(1.0, (o.matrix_world.to_3x3() @ Vector((0, 0, 1))).z))))


def measure(objs, f0: int, f1: int, angle: float = 20.0):
    """After a bake: the song time each domino first tilts past `angle` (interpolated), None if it never does."""
    sc = bpy.context.scene
    lim = math.cos(math.radians(angle))
    times = [None] * len(objs)
    prev = [1.0] * len(objs)
    for f in range(f0, f1 + 1):
        sc.frame_set(f)
        for i, o in enumerate(objs):
            up = (o.matrix_world.to_3x3() @ Vector((0, 0, 1))).z
            if times[i] is None and up < lim:
                u = (prev[i] - lim) / max(1e-6, prev[i] - up)
                times[i] = (f - 1 + u) / FPS
            prev[i] = up
        if all(t is not None for t in times):
            break
    return times


def strike_time(o, f0: int, f1: int):
    """When domino o comes to rest against something: the first frame its tilt is within 2 deg of its tilt at f1
    (None if it barely moved)."""
    sc = bpy.context.scene
    sc.frame_set(f1)
    fin = tilt(o)
    if fin < 10.0:
        return None
    for f in range(f0, f1 + 1):
        sc.frame_set(f)
        if tilt(o) > fin - 2.0:
            return f / FPS
    return None
