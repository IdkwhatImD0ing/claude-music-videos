"""The bead-maze toy for `training`: a maple block with a blue enamel wire bent into a loss curve (quick decay, a long
plateau, a SUDDEN DROP, a long low tail), a big red bead Clawd rides, a cluster of small beads resting at the end of
the tail, and two decorative wires behind (a yellow wave with a loop, a short green hump) with their own beads.

    mz = build_maze(coll, origin=(7, -26, 0), yaw=0)
    mz.point(s)          # world point at arc length s (cm) along the ride wire
    mz.frame(s)          # 4x4 world matrix of the seat on the bead at s (X along the wire, Z the wire's normal)
    mz.s_of_u(u)         # arc length at the local x position u (cm from the left end)

All sizes are cm (1 BU = 1 cm). Local frame: x along the sculpture (the curve's time axis), z up, y toward the wall.
"""
from __future__ import annotations

import math

import bmesh
import bpy
from mathutils import Matrix, Vector

from pdoom import kit
from pdoom.chars.rig import Path
from pdoom.sets import geo
from pdoom.sets import materials as M

BASE_W, BASE_D, BASE_H = 47.0, 9.0, 1.8
WIRE_R = 0.34
BEAD_R = 2.0            # the ride bead (a barrel bead, long along the wire)
BEAD_L = 5.2

# the loss curve (u, z), local cm; u = 0 at the left end of the base
LOSS = [
    (0.8, 1.2), (0.8, 21.5), (1.1, 25.0), (2.3, 26.8), (4.0, 25.2), (6.0, 22.9), (8.5, 21.4), (11.5, 20.6),
    (14.0, 20.25), (16.2, 19.95), (17.5, 19.0), (18.25, 15.5), (18.7, 10.5), (19.3, 7.0), (20.6, 5.2), (23.0, 4.7),
    (28.0, 4.55), (34.0, 4.45), (40.0, 4.4), (43.3, 4.45), (44.4, 3.6), (44.5, 1.2),
]
YELLOW = [(3.0, 1.2), (3.0, 7.5), (4.5, 10.5), (7.0, 11.2), (9.5, 9.0), (10.4, 6.8), (9.2, 5.0), (7.6, 6.2),
          (8.2, 8.6), (11.0, 10.4), (13.5, 9.6), (15.2, 7.0), (15.4, 1.2)]
GREEN = [(23.5, 1.2), (23.5, 6.0), (25.5, 8.4), (29.0, 9.0), (32.5, 7.8), (35.0, 6.3), (38.0, 7.0), (40.2, 8.2),
         (41.5, 6.4), (41.5, 1.2)]


class Maze:
    def __init__(self):
        self.root = None
        self.path = None        # chars.rig.Path over the ride wire (local)
        self.M = Matrix()       # local -> world
        self.objects = []
        self.bead = None        # the ride bead's root Empty (keyed by the scene)
        self.cluster = []       # the resting beads (Empties), from the post end back
        self.cluster_s = []     # their rest arc lengths

    # geometry queries -------------------------------------------------------------------------------------------
    def local(self, s):
        return Vector(self.path.at(max(0.0, min(1.0, s / self.path.length))))

    def point(self, s):
        return self.M @ self.local(s)

    def tangent(self, s, eps=0.25):
        a, b = self.local(s - eps), self.local(s + eps)
        v = (b - a)
        return (self.M.to_3x3() @ v).normalized()

    def frame(self, s, lift=0.0):
        """World matrix of the ride bead at s: X along the wire (travel), Z the in-plane normal (up side)."""
        T = self.tangent(s)
        side = (self.M.to_3x3() @ Vector((0, 1, 0))).normalized()     # the sculpture's y (toward the wall)
        N = T.cross(side).normalized()                                  # in-plane normal, up side
        Y = N.cross(T).normalized()
        R = Matrix((T, Y, N)).transposed()
        p = self.point(s) + N * lift
        return Matrix.Translation(p) @ R.to_4x4()

    def s_of_u(self, u):
        """Arc length where the wire first reaches local x = u (on the part after the first rise)."""
        n = 800
        best = None
        for i in range(n + 1):
            s = self.path.length * i / n
            p = self.local(s)
            if p.z < 26.0 and i > 20 and p.x >= u:
                best = s
                break
        return best if best is not None else self.path.length


def _mat_wood():
    try:
        from pdoom.chars import looks
        return looks.wood('maze.maple', light='#E9D2A8', dark='#D2B07E')
    except Exception:  # noqa: BLE001
        return M.solid('maze.maple', '#E2C597', rough=0.45, coat=0.3)


def _bead_mesh(name, coll, m, r, length, holes=True):
    """A lacquered barrel bead along local X (the wire's direction), centre at the origin."""
    bm = bmesh.new()
    segs, rings = 28, 14
    verts = []
    for i in range(rings + 1):
        a = -math.pi / 2 + math.pi * i / rings
        x = math.sin(a) * length / 2
        rr = max(0.001, math.cos(a))
        # a barrel: flatter ends, round belly
        rr = r * (rr ** 0.55)
        if holes and i in (0, rings):
            rr = WIRE_R * 1.25
        ring = []
        for k in range(segs):
            b = 2 * math.pi * k / segs
            ring.append(bm.verts.new((x, rr * math.cos(b), rr * math.sin(b))))
        verts.append(ring)
    for i in range(rings):
        for k in range(segs):
            a, b = verts[i][k], verts[i][(k + 1) % segs]
            c, d = verts[i + 1][(k + 1) % segs], verts[i + 1][k]
            bm.faces.new((a, b, c, d))
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    for p in me.polygons:
        p.use_smooth = True
    o = bpy.data.objects.new(name, me)
    coll.objects.link(o)
    me.materials.append(m)
    return o


def _round_bead(name, coll, m, r):
    o = kit.sphere(name, r, (0, 0, 0), m=m, coll=coll, subdiv=4)
    o.scale = (0.82, 1.0, 1.0)      # a little squashed along the wire, like a real wooden bead
    return o


def build_maze(coll, origin=(7.0, -26.0, 0.0), yaw=0.0) -> Maze:
    mz = Maze()
    mz.M = Matrix.Translation(Vector(origin)) @ Matrix.Rotation(math.radians(yaw), 4, 'Z') @ \
        Matrix.Translation((-BASE_W / 2, 0, 0))
    root = geo.empty('maze', (0, 0, 0), coll, 2.0)
    root.matrix_world = mz.M
    mz.root = root
    wood = _mat_wood()
    blue = M.solid('maze.wire.blue', '#3F8BFF', rough=0.16, coat=1.0, coat_rough=0.05)
    yellow = M.solid('maze.wire.yellow', '#F2BE2A', rough=0.2, coat=1.0, coat_rough=0.06)
    green = M.solid('maze.wire.green', '#2FA05C', rough=0.2, coat=1.0, coat_rough=0.06)
    red = M.solid('maze.bead.red', '#D8392C', rough=0.22, coat=1.0, coat_rough=0.04, sss=0.05)
    bead_cols = ['#F4C430', '#34A853', '#F4F0E6', '#2F7FE0', '#E8742C', '#B04AC8']
    bead_mats = [M.solid(f'maze.bead.{i}', c, rough=0.25, coat=1.0, coat_rough=0.05) for i, c in enumerate(bead_cols)]
    felt = M.solid('maze.felt', '#2E2A26', rough=0.9)

    # the maple block, with rounded edges, on four felt feet
    base = geo.box('maze.base', (BASE_W, BASE_D, BASE_H), (0, 0, 0), bev=0.5, segments=4, m=wood, coll=coll)
    geo.attach(base, root, (BASE_W / 2, 0, BASE_H / 2 + 0.12))
    for i, (x, y) in enumerate(((2.5, -3.2), (2.5, 3.2), (BASE_W - 2.5, -3.2), (BASE_W - 2.5, 3.2))):
        f = kit.cylinder(f'maze.foot{i}', 0.9, 0.14, (0, 0, 0), verts=20, m=felt, coll=coll)
        geo.attach(f, root, (x, y, 0.07))
    mz.objects.append(base)

    # the ride wire (the loss curve), dense points from the same Path the ride uses
    pts = [(u, 0.0, z) for u, z in LOSS]
    mz.path = Path(pts, smooth=True, per_seg=16)
    dense = [tuple(p) for p in mz.path.P]
    w = geo.curve_tube('maze.wire', dense, WIRE_R, coll=coll, m=blue, kind='POLY', bevel_res=4)
    geo.attach(w, root)
    mz.objects.append(w)
    # decorative wires behind (y + 2.6, + 1.4)
    for nm, P, m, yy in (('maze.wire.y', YELLOW, yellow, 3.0), ('maze.wire.g', GREEN, green, 3.4)):
        pp = Path([(u, yy, z) for u, z in P], smooth=True, per_seg=14)
        o = geo.curve_tube(nm, [tuple(p) for p in pp.P], WIRE_R * 0.9, coll=coll, m=m, kind='POLY', bevel_res=4)
        geo.attach(o, root)
        mz.objects.append(o)
        # beads on them, resting at low points
        n = 5 if nm == 'maze.wire.y' else 3
        for k in range(n):
            s = pp.length * (0.15 + 0.7 * k / max(1, n - 1)) if nm == 'maze.wire.y' else pp.length * (0.3 + 0.2 * k)
            p = Vector(pp.at(s / pp.length))
            a = Vector(pp.at(max(0, s - 0.3) / pp.length))
            b = Vector(pp.at(min(pp.length, s + 0.3) / pp.length))
            t = (b - a).normalized()
            bd = _round_bead(f'{nm}.bead{k}', coll, bead_mats[(k * 2 + len(nm)) % len(bead_mats)], 1.05)
            q = t.to_track_quat('X', 'Z')
            geo.attach(bd, root, p, q.to_euler())
            mz.objects.append(bd)

    # the ride bead: a red barrel bead under a root Empty the scene keys
    br = geo.empty('maze.ridebead', (0, 0, 0), coll, 1.5)
    bead = _bead_mesh('maze.ridebead.mesh', coll, red, BEAD_R, BEAD_L)
    bead.parent = br
    mz.bead = br
    mz.objects.append(bead)

    # the resting cluster at the end of the tail: three round beads against the stop
    L = mz.path.length
    s_stop = mz.s_of_u(43.0)
    rs = [1.25, 1.25, 1.25]
    s = s_stop
    for k, r in enumerate(rs):
        s -= r * 0.82
        e = geo.empty(f'maze.cluster{k}', (0, 0, 0), coll, 0.8)
        e.matrix_world = mz.frame(s)
        bd = _round_bead(f'maze.cluster{k}.mesh', coll, bead_mats[k], r)
        bd.parent = e
        mz.cluster.append(e)
        mz.cluster_s.append(s)
        mz.objects.append(bd)
        s -= r * 0.82
    mz.s_hit = s - BEAD_L / 2          # where the ride bead's leading end meets the cluster
    return mz


def loss_image(name='screen.loss_true', w=1280, h=800):
    """The laptop picture for this scene: the same curve as the wire (a real loss curve: high on the left, the
    sudden drop, low on the right), drawn in the wire's blue on a dark chart, plus a red dot the scene can't move
    (static) at the drop."""
    import numpy as np
    if name in bpy.data.images:
        return bpy.data.images[name]
    a = np.zeros((h, w, 4), dtype=np.float32)
    a[..., 3] = 1.0

    def hexc(s):
        s = s.lstrip('#')
        return np.array([int(s[i:i + 2], 16) / 255 for i in (0, 2, 4)], dtype=np.float32)

    def rect(x0, y0, x1, y1, c):
        x0, x1 = max(0, int(x0)), min(w, int(x1))
        y0, y1 = max(0, int(y0)), min(h, int(y1))
        if x1 > x0 and y1 > y0:
            a[y0:y1, x0:x1, :3] = hexc(c)
    rect(0, 0, w, h, '#0D1117')
    x0, x1, y0, y1 = 120, w - 80, 110, h - 110
    for i in range(6):
        yy = y0 + (y1 - y0) * i / 5
        rect(x0, yy, x1, yy + 2, '#1F2A36')
    for i in range(9):
        xx = x0 + (x1 - x0) * i / 8
        rect(xx, y0, xx + 2, y1, '#1F2A36')
    rect(x0 - 3, y0, x0, y1 + 3, '#8B98A8')
    rect(x0 - 3, y1, x1, y1 + 3, '#8B98A8')
    rect(x0, 40, x0 + 300, 64, '#D6DEEB')
    rect(x0 + 320, 40, x0 + 420, 64, '#5B6B7B')
    pth = Path([(u, 0.0, z) for u, z in LOSS[2:-2]], smooth=True, per_seg=40)
    us = [p.x for p in pth.P]
    umin, umax = min(us), max(us)
    zs = [p.z for p in pth.P]
    zmin, zmax = min(zs), max(zs)
    col = hexc('#4A8CFF')
    for p in pth.P:
        x = x0 + (p.x - umin) / (umax - umin) * (x1 - x0)
        y = y1 - (p.z - zmin) / (zmax - zmin) * (y1 - y0) * 0.9 - (y1 - y0) * 0.03
        n = geo.hash01('lossimg', round(p.x, 2)) - 0.5
        y += n * 6 * (1.0 if p.z > 10 else 0.4)
        xi, yi = int(x), int(y)
        a[max(0, yi - 3):yi + 4, max(0, xi - 3):xi + 4, :3] = col
    a = a[::-1].copy()
    img = bpy.data.images.new(name, w, h, alpha=False)
    img.pixels.foreach_set(a.ravel())
    try:
        img.pack()
    except Exception:  # noqa: BLE001
        pass
    return img
