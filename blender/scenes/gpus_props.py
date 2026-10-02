"""Props for `gpus` (scene-local): popsicle-stick safety fences that break into rigid bodies, wood splinters, and the
RLHF thumbs-up feedback toy (a spring-loaded lever with a foam thumbs-up, springs and screws that fly off).

Fences stand across the robot's path (local X across the path, facing +Y/-Y). Each picket is two halves split at the
impact height, so the sticks snap. break_fence() holds every piece still (kinematic) until the hit, gives it a
velocity and spin away from the impact over the last frame, and releases it to Bullet (baked in build()).
"""
from __future__ import annotations

import math

import bmesh
import bpy
from mathutils import Euler, Matrix, Quaternion, Vector

from pdoom import kit
from pdoom.chars import geo as cgeo
from pdoom.fx import rigid
from pdoom.sets import geo
from pdoom.sets import materials as M
from pdoom import timing as tm
from pdoom.timing import FPS

V = Vector


# ------------------------------------------------------------------------------------------------ materials


def wood():
    return M.solid('pop.wood', '#E3C38E', rough=0.72, micro=(9.0, 0.08))


def _stick_bm(length, width=0.95, thick=0.2, round_=True):
    """A popsicle stick along local Z from 0 to length (rounded ends), width along X, thickness along Y."""
    bm = bmesh.new()
    n = 8
    hw = width / 2
    pts = []
    if round_:
        for k in range(n + 1):
            a = math.pi + math.pi * k / n
            pts.append((hw * math.cos(a), hw + hw * math.sin(a) * 0.9))
        for k in range(n + 1):
            a = math.pi * k / n
            pts.append((hw * math.cos(a), length - hw + hw * math.sin(a) * 0.9))
    else:
        pts = [(-hw, 0.0), (hw, 0.0), (hw, length), (-hw, length)]
    # counter-clockwise outline in (x, z); extrude along Y
    front = [bm.verts.new((x, -thick / 2, z)) for x, z in pts]
    back = [bm.verts.new((x, thick / 2, z)) for x, z in pts]
    m = len(pts)
    bm.faces.new(front)
    bm.faces.new(list(reversed(back)))
    for i in range(m):
        j = (i + 1) % m
        bm.faces.new((front[j], front[i], back[i], back[j]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return bm


def _snapped_pair(length, split, width=1.4, thick=0.2, seed=0):
    """Two halves of a stick snapped at `split` with a jagged break (lower from 0, upper to length)."""
    hw = width / 2
    n = 8
    lo_pts, hi_pts = [], []
    for k in range(n + 1):
        a = math.pi + math.pi * k / n
        lo_pts.append((hw * math.cos(a), hw + hw * math.sin(a) * 0.9))
    teeth = [(hw - width * i / 5, split + (0.18 if (i + seed) % 2 else -0.12)) for i in range(6)]
    lo = lo_pts + teeth
    # upper piece: along the teeth (left to right), then round the top (right to left)
    upper = [(x, z) for x, z in reversed(teeth)] + \
        [(hw * math.cos(math.pi * k / n), length - hw + hw * math.sin(math.pi * k / n) * 0.9) for k in range(n + 1)]
    out = []
    for poly in (lo, upper):
        bm = bmesh.new()
        f = [bm.verts.new((x, -thick / 2, z)) for x, z in poly]
        b = [bm.verts.new((x, thick / 2, z)) for x, z in poly]
        mm = len(poly)
        try:
            bm.faces.new(f)
            bm.faces.new(list(reversed(b)))
        except ValueError:
            pass
        for i in range(mm):
            j = (i + 1) % mm
            try:
                bm.faces.new((f[j], f[i], b[i], b[j]))
            except ValueError:
                pass
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
        out.append(bm)
    return out


# ------------------------------------------------------------------------------------------------ fences


def sign_material(name, color):
    return M.solid(name, color, rough=0.55, micro=(15.0, 0.02))


def fence(coll, name, *, width=18.0, height=9.0, gap=1.25, split=None, seed=0, sign_scale=1.0):
    """A popsicle-stick fence across local X centred on the origin, standing on z = 0, facing +/-Y: pickets (each
    pre-snapped in two at `split`), two rails on the +Y face, two on the -Y face, and a yellow SAFETY sign on each
    face. Returns a list of piece objects (each its own mesh, origin at its centroid, world placement in its
    matrix)."""
    wm = wood()
    pieces = []
    pw = 1.4
    n = int((width + gap) // (pw + gap))
    x0 = -((n - 1) * (pw + gap)) / 2
    split = split if split is not None else height * 0.55
    for i in range(n):
        x = x0 + i * (pw + gap)
        h = height + (0.35 if i % 2 else 0.0)
        s = split + 0.6 * math.sin(i * 1.7 + seed)
        lo, hi = _snapped_pair(h, s, seed=i + seed)
        for k, bm in enumerate((lo, hi)):
            ob = cgeo.to_object(bm, f'{name}.p{i}{"ab"[k]}', coll, [wm], sharp=30.0)
            ob.matrix_world = Matrix.Translation((x, 0.0, 0.0))
            pieces.append(ob)
    # rails (horizontal sticks) in front of and behind the pickets
    for side in (-1, 1):
        for z in (height * 0.28, height * 0.72):
            L = width + 0.8
            bm = _stick_bm(L, width=1.3, thick=0.2)
            ob = cgeo.to_object(bm, f'{name}.rail{side}{z:.0f}', coll, [wm], sharp=30.0)
            ob.matrix_world = (Matrix.Translation((-L / 2, side * 0.21, z)) @ Matrix.Rotation(math.radians(90), 4, 'Y'))
            pieces.append(ob)
    # the SAFETY sign: a yellow card with a black border and black letters, on each face, hung on the upper rail
    for side in (-1, 1):
        sw, sh = 6.2 * sign_scale, 2.1 * sign_scale
        card = geo.box(f'{name}.sign{side}', (sw, 0.06, sh), (0, 0, 0), m=sign_material('sign.yellow', '#F4C51F'),
                       coll=coll)
        border = geo.box(f'{name}.sign{side}.border', (sw - 0.25, 0.01, sh - 0.25), (0, 0, 0),
                         m=sign_material('sign.black', '#141414'), coll=coll)
        inner = geo.box(f'{name}.sign{side}.inner', (sw - 0.45, 0.012, sh - 0.45), (0, 0, 0),
                        m=sign_material('sign.yellow', '#F4C51F'), coll=coll)
        txt = geo.text_mesh(f'{name}.sign{side}.text', 'SAFETY', 1.15 * sign_scale, coll=coll,
                            m=sign_material('sign.black', '#141414'))
        zc = height * 0.72 - 0.3
        yc = side * (0.34 + 0.03)
        card.matrix_world = Matrix.Translation((0.0, yc, zc))
        border.matrix_world = Matrix.Translation((0.0, yc + side * 0.035, zc))
        inner.matrix_world = Matrix.Translation((0.0, yc + side * 0.041, zc))
        # text: local XY plane reading from +Z -> stand it up facing +/-Y
        rx = Matrix.Rotation(math.radians(90), 4, 'X')
        rz = Matrix.Rotation(math.radians(0 if side < 0 else 180), 4, 'Z')
        txt.matrix_world = Matrix.Translation((0.0, yc + side * 0.05, zc - 0.05 * sign_scale)) @ rz @ rx
        sg = geo.join([card, border, inner, txt], f'{name}.sign{side}')
        pieces.append(sg)
    # origins at the centroids (rigid bodies spin about them)
    for ob in pieces:
        _origin_to_centroid(ob)
    return pieces


def _origin_to_centroid(ob):
    me = ob.data
    if not me.vertices:
        return
    mw = ob.matrix_world.copy()
    c = sum((v.co for v in me.vertices), V()) / len(me.vertices)
    me.transform(Matrix.Translation(-c))
    ob.matrix_world = mw @ Matrix.Translation(c)


def place(pieces, M_):
    """Move a fence built at the origin to the world placement M_ (a Matrix)."""
    for ob in pieces:
        ob.matrix_world = M_ @ ob.matrix_world


def break_fence(pieces, t, impact, push, *, seed=0, speed=(40.0, 130.0), up=(15.0, 70.0), reach=7.0, spin=16.0,
                min_speed=0.12, mass=0.004):
    """Rigid bodies: every piece held still until the hit at t, then released with a velocity away from the impact
    (along `push`, spreading sideways and up, falling off with distance: exp(-d / reach), never below min_speed of
    it) and a tumbling spin. Returns the release frame."""
    import numpy as np
    rng = np.random.default_rng(seed)
    F = int(math.floor(t * FPS + 1e-6))
    p = V(impact)
    push = V(push).normalized()
    for ob in pieces:
        rigid.active(ob, mass=mass, shape='CONVEX_HULL', friction=0.6, bounce=0.2, damping=(0.1, 0.25), sleep=False)
        ob.rigid_body.collision_margin = 0.02
        ob.rigid_body.use_margin = True
        M0 = ob.matrix_world.copy()
        c = M0.translation
        d = (c - p).length
        k = max(min_speed, math.exp(-d / reach))
        lat = V((c.x - p.x, c.y - p.y, 0.0))
        lat = lat - push * lat.dot(push)
        vel = push * rng.uniform(*speed) * k + lat.normalized() * rng.uniform(5, 40) * k * (1 if lat.length > 1e-3
                                                                                          else 0) + \
            V((0, 0, rng.uniform(*up) * k))
        w = V(rng.normal(0, 1, 3)).normalized() * spin * k * rng.uniform(0.5, 1.2)
        loc0, rot0 = M0.translation.copy(), M0.to_euler('XYZ')
        dt = 1.0 / FPS
        loc1 = loc0 + vel * dt
        q1 = Quaternion(w.normalized(), w.length * dt) @ M0.to_quaternion() if w.length > 1e-6 else M0.to_quaternion()
        rot1 = q1.to_euler('XYZ', rot0)
        ob.location, ob.rotation_euler = loc0, rot0
        rw = rigid.world()
        if tm.SMOOTH:
            # built for 60 fps: the piece starts moving at the hit itself (frame h, fractional), not at the whole frame
            # before it (which showed the pickets breaking 1-3 output frames before the fist landed). It keeps the
            # kick velocity, kinematic, through the next two whole frames (the last held step, Fh -> Fh + 1, is one
            # full frame of motion, so Bullet takes over at that velocity), and a key at Fh + 2 carries it on to the
            # release so no exposure sees it parked.
            h = t * FPS
            Fh = int(math.floor(h + 1e-6)) + 1

            def at(f):
                u = (f - h) / FPS
                q = Quaternion(w.normalized(), w.length * u) @ M0.to_quaternion() if w.length > 1e-6 \
                    else M0.to_quaternion()
                return loc0 + vel * u, q.to_euler('XYZ', rot0)
            keys = [(rw.point_cache.frame_start, (loc0, rot0)), (h, (loc0, rot0)), (Fh, at(Fh)), (Fh + 1, at(Fh + 1)),
                    (Fh + 2, at(Fh + 2))]
            t_rel, F_ret = (Fh + 1.5) / FPS, Fh + 2
        else:
            keys = [(rw.point_cache.frame_start, (loc0, rot0)), (F - 1, (loc0, rot0)), (F, (loc1, rot1))]
            t_rel, F_ret = (F + 0.5) / FPS, F + 1
        for f, (L_, R_) in keys:
            ob.location, ob.rotation_euler = L_, R_
            ob.keyframe_insert('location', frame=f)
            ob.keyframe_insert('rotation_euler', frame=f)
        for fc in kit.fcurves(ob):
            if fc.data_path in ('location', 'rotation_euler'):
                for kp in fc.keyframe_points:
                    kp.interpolation = 'LINEAR'
        rigid.release(ob, t_rel)
    return F_ret


def splinter_proto(coll):
    """A wood splinter (a thin sliver) for particles.stream."""
    ob = bpy.data.objects.get('pop.splinter')
    if ob is not None:
        return ob
    bm = bmesh.new()
    vs = [bm.verts.new(p) for p in ((-0.35, -0.05, 0.0), (0.35, -0.02, 0.0), (0.4, 0.03, 0.0), (-0.3, 0.06, 0.0),
                                     (-0.33, -0.04, 0.05), (0.3, -0.01, 0.04), (0.36, 0.02, 0.03), (-0.28, 0.05, 0.05))]
    for f in ((0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)):
        bm.faces.new([vs[i] for i in f])
    ob = cgeo.to_object(bm, 'pop.splinter', coll, [wood()], sharp=20.0)
    ob.location = (0, 0, -5000)
    ob.hide_render = True
    return ob


# ------------------------------------------------------------------------------------------------ the thumbs-up toy


def thumbs_up(coll, name='rlhf'):
    """The feedback toy: a glossy red/white base (a game-show buzzer box) with a chrome hinge bracket and four
    screws; a chrome lever standing on the hinge; a yellow foam thumbs-up on top. Local frame: base on z = 0,
    hinge pivot at (0, 0, PIV), the lever tilts about local Y. Returns a dict of parts (objects/empties) and the
    geometry numbers."""
    red = M.solid('rlhf.red', '#D2382E', rough=0.22, coat=0.8, coat_rough=0.08)
    white = M.solid('rlhf.white', '#F0ECE4', rough=0.3, coat=0.5)
    chrome = M.chrome('rlhf.chrome')
    foam = M.solid('rlhf.foam', '#F6C43A', rough=0.8, sheen=0.4, micro=(12.0, 0.08))
    cuff = M.solid('rlhf.cuff', '#3A6FC8', rough=0.5)
    root = kit.empty(f'{name}', (0, 0, 0), coll, size=2.0)
    bw, bh = 5.2, 3.0
    bm = bmesh.new()
    cgeo.rounded_box(bm, (bw, bw, bh), 0.45, (0, 0, bh / 2), seg=4)
    base = cgeo.to_object(bm, f'{name}.base', coll, [red], sharp=None)
    geo.attach(base, root)
    bm = bmesh.new()
    cgeo.rounded_box(bm, (bw - 0.5, bw - 0.5, 0.25), 0.1, (0, 0, bh + 0.1), seg=3)
    top = cgeo.to_object(bm, f'{name}.top', coll, [white], sharp=None)
    geo.attach(top, root)
    # hinge bracket (a chrome U) with the pivot pin, as its own piece so it can tear off
    brk = kit.empty(f'{name}.bracket', (0, 0, 0), coll, size=0.5)
    geo.attach(brk, root, (0.0, 0.0, bh + 0.23))
    parts = []
    plate = geo.box(f'{name}.plate', (2.4, 1.6, 0.14), (0, 0, 0), bev=0.03, m=chrome, coll=coll)
    geo.attach(plate, brk, (0, 0, 0.07))
    parts.append(plate)
    for sx in (-1, 1):
        ear = geo.box(f'{name}.ear{sx}', (0.14, 1.2, 1.2), (0, 0, 0), bev=0.04, m=chrome, coll=coll)
        geo.attach(ear, brk, (sx * 0.55, 0.0, 0.7))
        parts.append(ear)
    screws = []
    for i, (sx, sy) in enumerate(((-1, -1), (1, -1), (1, 1), (-1, 1))):
        sc = geo.lathe(f'{name}.screw{i}', [(0.0, -0.9), (0.05, -0.9), (0.07, -0.8), (0.07, 0.0), (0.2, 0.0),
                                            (0.2, 0.06), (0.14, 0.12), (0.0, 0.13)], segs=16, coll=coll, m=chrome)
        geo.attach(sc, brk, (sx * 0.95, sy * 0.58, 0.14))
        screws.append(sc)
    PIV = bh + 0.23 + 1.0
    lever = kit.empty(f'{name}.lever', (0, 0, 0), coll, size=0.5)
    geo.attach(lever, root, (0.0, 0.0, PIV))
    pin = geo.lathe(f'{name}.pin', [(0.0, -0.7), (0.12, -0.7), (0.12, 0.7), (0.0, 0.7)], segs=16, coll=coll, m=chrome)
    geo.attach(pin, lever, (0, 0, 0), (math.radians(90), 0, math.radians(90)))
    L = 6.0
    rod = geo.lathe(f'{name}.rod', [(0.0, 0.0), (0.2, 0.0), (0.2, L), (0.0, L)], segs=20, coll=coll, m=chrome)
    geo.attach(rod, lever, (0, 0, 0))
    # the hand: a foam fist with curled fingers facing -Y, the thumb straight up
    hand = kit.empty(f'{name}.hand', (0, 0, 0), coll, size=0.5)
    geo.attach(hand, lever, (0.0, 0.0, L))
    bm = bmesh.new()
    cgeo.rounded_box(bm, (2.3, 1.9, 2.2), 0.6, (0, 0, 1.25), seg=4)
    for k in range(4):
        cgeo.uv_sphere(bm, 1.0, segs=16, rings=10, scale=(0.3, 0.42, 0.26),
                       M=Matrix.Translation((0.72 - k * 0.48, -0.95, 1.9 - k * 0.04)))
    for k in range(4):
        cgeo.uv_sphere(bm, 1.0, segs=16, rings=10, scale=(0.26, 0.35, 0.24),
                       M=Matrix.Translation((0.72 - k * 0.48, -0.9, 1.25 - k * 0.03)))
    fist = cgeo.to_object(bm, f'{name}.fist', coll, [foam], sharp=None)
    geo.attach(fist, hand)
    bm = bmesh.new()
    cgeo.tube(bm, [V((1.0, 0.0, 1.6)), V((1.25, 0.0, 2.6)), V((1.22, 0.0, 3.5)), V((1.1, 0.0, 3.95))],
              [0.42, 0.44, 0.4, 0.3], segs=18)
    thumb = cgeo.to_object(bm, f'{name}.thumb', coll, [foam], sharp=None)
    geo.attach(thumb, hand)
    bm = bmesh.new()
    cgeo.lathe(bm, [(0.0, -0.1), (0.95, -0.1), (1.05, 0.1), (1.05, 0.4), (0.95, 0.55), (0.0, 0.55)], segs=28)
    cf = cgeo.to_object(bm, f'{name}.cuff', coll, [cuff], sharp=None)
    geo.attach(cf, hand, (0, 0, -0.2))
    # springs: unit-length helices along +Z (scaled to span their anchors every frame)
    springs = []
    for i in range(2):
        pts = [V(p) for p in geo.helix(9, 0.28, 1.0, 14)]
        sp = geo.curve_tube(f'{name}.spring{i}', [tuple(p) for p in pts], 0.045, coll=coll, m=chrome, res=2,
                            bevel_res=2, to_mesh=True)
        springs.append(sp)
    return {'root': root, 'base': base, 'top': top, 'bracket': brk, 'bracket_parts': parts, 'screws': screws,
            'lever': lever, 'hand': hand, 'thumb': thumb, 'springs': springs, 'PIV': PIV, 'L': L, 'bw': bw,
            'bh': bh}


def span(A, B):
    """World matrix of a unit +Z spring spanning A -> B."""
    A, B = V(A), V(B)
    d = B - A
    q = V((0, 0, 1)).rotation_difference(d.normalized())
    return Matrix.Translation(A) @ q.to_matrix().to_4x4() @ Matrix.Diagonal((1.0, 1.0, max(d.length, 0.05), 1.0))


def flight(t0, M0, v0, w, *, floor=0.0, rest_h=0.08, t1=None, g=981.0, bounce=0.35, drag=0.4):
    """A free flight from t0: world placement M0 moving with v0 (cm/s) and spin w (rad/s, a vector); ballistic with
    gravity and a little drag; bounces off `floor` (+rest_h), then slides to rest. Returns f(t) -> world Matrix
    (a pure function, simulated once on a fine step)."""
    t1 = t1 if t1 is not None else t0 + 2.5
    p0 = M0.translation.copy()
    q0 = M0.to_quaternion()
    sc = M0.to_scale()
    # simulate on a fine step (a pure function of the inputs)
    dt = 1.0 / 240
    p, v = p0.copy(), V(v0)
    wv = V(w)
    ang = 0.0
    states = []
    t = t0
    bounced = 0
    while t <= t1 + 1e-6:
        states.append((t, p.copy(), ang))
        v = v * (1 - drag * dt) + V((0, 0, -g * dt))
        p = p + v * dt
        ang += wv.length * dt
        if p.z < floor + rest_h:
            p.z = floor + rest_h
            if v.z < -30 and bounced < 2:
                v = V((v.x * 0.55, v.y * 0.55, -v.z * bounce))
                wv = wv * 0.5
                bounced += 1
            else:
                v = V((v.x * 0.8, v.y * 0.8, 0.0))
                wv = wv * 0.85
        t += dt
    axis = V(w).normalized() if V(w).length > 1e-6 else V((0, 0, 1))

    def at(tt):
        i = min(max(int(round((tt - t0) / dt)), 0), len(states) - 1)
        _, pp, aa = states[i]
        q = Quaternion(axis, aa) @ q0
        return Matrix.LocRotScale(pp, q, sc)
    return at


def key_world(ob, fn, t0, t1, *, spans=(), default='ones'):
    """Key an unparented object's world placement from fn(t) on the stop-motion grid (boot_common.grid: 'twos',
    'ones' (CONSTANT) or 'smooth' (LINEAR, every frame)) over [t0, t1]."""
    from scenes.boot_common import grid
    prev = None
    g = grid(t0, t1, spans, default)
    for fk, t in g:
        Mt = fn(t)
        loc, rot, sca = Mt.decompose()
        e = rot.to_euler('XYZ', prev) if prev is not None else rot.to_euler('XYZ')
        prev = e
        ob.location, ob.rotation_euler, ob.scale = loc, e, sca
        for pth in ('location', 'rotation_euler', 'scale'):
            ob.keyframe_insert(pth, frame=fk)
    smooth = {fk for fk, _ in g if float(fk).is_integer()}
    for fc in kit.fcurves(ob):
        if fc.data_path in ('location', 'rotation_euler', 'scale'):
            for kp in fc.keyframe_points:
                # built for 60 fps the grid samples every output frame: all keys move (LINEAR)
                kp.interpolation = 'LINEAR' if (tm.SMOOTH or kp.co.x in smooth) else 'CONSTANT'
    return ob
