"""singularity: the tinplate clockwork train and its oval of tin track.

Models (car space: x forward, y to the train's left, z up, z = 0 on the rail tops):
  loco      lithographed tin 4-4-0: green boiler with brass bands, black smokebox and chimney, red footplate, cab and
            buffer beam, brass dome and buffers, spoked red driving wheels with steel tyres, coupling and connecting
            rods that really crank, and a brass wind-up key on the right side of the cab
  tender    green with a heap of coal
  tub       Clawd's open wagon: a wide blue tin tub with a yellow rim on a red frame (Clawd is 8 cm wide)
  caboose   red with a cupola, cream window frames and a glowing red tail lamp
  track     O-ish gauge tinplate track (5 cm): hollow steel rails on black pressed-tin ties, 18 pieces (3 per straight,
            6 per half-circle) that can peel off one by one

Motion: `Run` holds the unwrapped arc length s(t) of the loco's centre; `Path` maps s to a point on the oval, and past
s_leave onto a spiral that climbs into the accretion disc and winds down to the horizon. Cars follow the path on two
bogie points each (chords on the curves), bank on fast curves, and stretch (spaghettify) near the hole.
"""
from __future__ import annotations

import bisect
import math

import bmesh
import bpy
from mathutils import Matrix, Vector

from pdoom import timing as tm
from pdoom.chars import geo as cg
from pdoom.sets import geo
from pdoom.sets import materials as M


FPS = tm.FPS
RAIL_Z = 0.82          # rail top above the desk
GAUGE = 5.0
TIE_L, TIE_W, TIE_T = 7.2, 1.0, 0.22


def _T(x, y=0.0, z=0.0):
    return Matrix.Translation((x, y, z))


RX = Matrix.Rotation(math.radians(-90), 4, 'X')      # lathe axis Z -> +Y (axles)
RY = Matrix.Rotation(math.radians(90), 4, 'Y')       # lathe axis Z -> +X (boilers)


# ------------------------------------------------------------------------------------------------ materials


def mats():
    return {
        'green': M.enamel('train.green', '#1E5B3C', rough=0.28, coat=0.5),
        'red': M.enamel('train.red', '#B52E27', rough=0.3, coat=0.5),
        'black': M.enamel('train.black', '#17171A', rough=0.35, coat=0.4),
        'blue': M.enamel('train.blue', '#2D6CB8', rough=0.28, coat=0.5),
        'yellow': M.enamel('train.yellow', '#E6B42C', rough=0.3, coat=0.4),
        'cream': M.enamel('train.cream', '#EEE3C8', rough=0.35, coat=0.3),
        'brass': M.brass('train.brass', '#D2A650', rough=0.22),
        'steel': M.solid('train.steel', '#B9C0C8', rough=0.22, metal=1.0, micro=(40.0, 0.02)),
        'rail': M.solid('train.rail', '#C4CAD2', rough=0.18, metal=1.0, micro=(30.0, 0.015)),
        'tie': M.enamel('train.tie', '#22201F', rough=0.45, coat=0.2),
        'coal': M.solid('train.coal', '#101012', rough=0.35, spec=0.6, micro=(6.0, 0.25)),
        'glass': M.solid('train.window', '#0B0F14', rough=0.08, spec=0.7),
        'lamp': M.emissive('train.taillamp', '#FF2A1A', 2.0),
        'head': M.emissive('train.headlamp', '#FFE2A0', 6.0),
    }


# ------------------------------------------------------------------------------------------------ mesh helpers


def cyl_x(bm, r, x0, x1, *, y=0.0, z=0.0, segs=32, mat=0, r1=None):
    """Closed cylinder along X from x0 to x1 (radius r, or tapering to r1)."""
    r1 = r if r1 is None else r1
    prof = [(0.0, 0.0), (r, 0.0), (r1, x1 - x0), (0.0, x1 - x0)]
    cg.lathe(bm, prof, segs=segs, mat=mat, M=_T(x0, y, z) @ RY)


def cyl_z(bm, r, z0, z1, *, x=0.0, y=0.0, segs=24, mat=0, r1=None):
    r1 = r if r1 is None else r1
    cg.lathe(bm, [(0.0, z0), (r, z0), (r1, z1), (0.0, z1)], segs=segs, mat=mat, M=_T(x, y, 0.0))


def cyl_y(bm, r, y0, y1, *, x=0.0, z=0.0, segs=24, mat=0):
    cg.lathe(bm, [(0.0, 0.0), (r, 0.0), (r, y1 - y0), (0.0, y1 - y0)], segs=segs, mat=mat, M=_T(x, y0, z) @ RX)


def rbox(bm, size, center, r=0.12, mat=0, seg=2):
    cg.rounded_box(bm, size, min(r, min(size) / 2 - 1e-3), center, seg=seg, flat=(1, 1, 1), mat=mat)


def obj(bm, name, coll, mlist, sharp=40.0):
    cg.recalc_normals(bm)
    return cg.to_object(bm, name, coll, mlist, sharp=sharp)


def wheelset(bm, r, *, spokes=0, crank=0.0, phase=0.0, mat_web=0, mat_tyre=1, mat_hub=2, half=GAUGE / 2):
    """An axle with two wheels (at y = +-half), centred on the origin (axle along Y). spokes > 0 makes a spoked
    driving wheel; crank > 0 adds a crank pin at that radius (left side leads the right by 90 degrees)."""
    for side in (-1, 1):
        yc = side * half
        # tyre + flange (the flange on the inside)
        yi, yo = yc - side * 0.2, yc + side * 0.14
        a, b = (yi, yo) if side > 0 else (yo, yi)
        prof = [(r * 0.84, 0.0), (r, 0.0), (r, 0.03), (r, b - a - 0.03), (r, b - a), (r * 0.84, b - a)]
        cg.lathe(bm, prof, segs=40, mat=mat_tyre, M=_T(0, a, 0) @ RX)
        fl = (yi - side * 0.07)
        a2, b2 = (fl, yi) if side > 0 else (yi, fl)
        cg.lathe(bm, [(r * 0.84, 0.0), (r + 0.16, 0.0), (r + 0.16, b2 - a2), (r * 0.84, b2 - a2)], segs=40,
                 mat=mat_tyre, M=_T(0, a2, 0) @ RX)
        # web (recessed disc) and hub
        cyl_y(bm, r * 0.86, yc - 0.06, yc + 0.06, mat=mat_web, segs=32)
        hub_o = yc + side * 0.22
        cyl_y(bm, r * 0.2, min(yc, hub_o), max(yc, hub_o), mat=mat_hub, segs=16)
        if spokes:
            for k in range(spokes):
                ang = 2 * math.pi * k / spokes
                c, s_ = math.cos(ang), math.sin(ang)
                ln = r * 0.66
                ctr = Vector((c * (r * 0.2 + ln / 2), yc + side * 0.07, s_ * (r * 0.2 + ln / 2)))
                vs = bmesh.ops.create_cube(bm, size=1.0)['verts']
                Ms = Matrix.Translation(ctr) @ Matrix.Rotation(-ang, 4, 'Y') @ Matrix.Diagonal((ln, 0.12, 0.16, 1))
                for v in vs:
                    v.co = Ms @ v.co
                for f in {f for v in vs for f in v.link_faces}:
                    f.material_index = mat_web
            # counterweight
            cg.lathe(bm, [(0.0, 0.0), (r * 0.55, 0.0), (r * 0.55, 0.12), (0.0, 0.12)], segs=16, mat=mat_web,
                     M=_T(0, yc + side * 0.02, 0) @ Matrix.Rotation(phase + (0 if side > 0 else math.pi / 2) + math.pi,
                                                                     4, 'Y') @ _T(r * 0.45, 0, 0) @ RX)
        if crank:
            ph = phase + (0.0 if side > 0 else math.pi / 2)
            px, pz = crank * math.cos(ph), crank * math.sin(ph)
            y0, y1 = (yc + side * 0.1, yc + side * 0.55)
            cyl_y(bm, 0.13, min(y0, y1), max(y0, y1), x=px, z=pz, mat=mat_hub, segs=12)
    cyl_y(bm, 0.12, -half, half, mat=mat_tyre, segs=10)          # axle


# ------------------------------------------------------------------------------------------------ cars


class Car:
    def __init__(self, name, length, wheelbase, offset, root):
        self.name, self.length, self.wb, self.offset, self.root = name, length, wheelbase, offset, root
        self.wheels = []       # (object, radius)
        self.parts = []        # every object under the root
        self.rods = []         # loco only


def _car_root(name, coll):
    r = geo.empty(name, (0, 0, 0), coll, 2.0, 'ARROWS')
    r.rotation_mode = 'XYZ'
    return r


def build_loco(coll, Mt):
    root = _car_root('loco', coll)
    car = Car('loco', 14.0, 8.4, 0.0, root)
    ml = [Mt['red'], Mt['green'], Mt['black'], Mt['brass'], Mt['cream'], Mt['glass'], Mt['steel'], Mt['head']]
    RED, GREEN, BLACK, BRASS, CREAM, GLASS, STEEL, HEAD = range(8)
    bm = bmesh.new()
    fz = 2.9
    rbox(bm, (14.0, 6.2, 0.32), (0.0, 0.0, fz), 0.1, RED)                         # footplate
    rbox(bm, (13.2, 5.0, 0.9), (-0.2, 0.0, fz - 0.55), 0.08, BLACK)              # frames
    rbox(bm, (0.45, 6.4, 1.3), (6.95, 0.0, fz - 0.35), 0.08, RED)                # buffer beam
    rbox(bm, (0.4, 6.0, 1.0), (-7.0, 0.0, fz - 0.3), 0.08, RED)                  # drag beam
    for yb in (-2.05, 2.05):
        cyl_x(bm, 0.2, 7.1, 7.7, y=yb, z=fz - 0.35, mat=STEEL, segs=12)
        cyl_x(bm, 0.42, 7.7, 7.85, y=yb, z=fz - 0.35, mat=BRASS, segs=20)       # buffer heads
    # boiler, bands, smokebox
    bz = fz + 0.16 + 2.0
    cyl_x(bm, 2.0, -1.4, 5.5, z=bz, mat=GREEN, segs=48)
    for xb in (-1.2, 0.9, 3.0, 5.2):
        cyl_x(bm, 2.06, xb, xb + 0.16, z=bz, mat=BRASS, segs=48)
    cyl_x(bm, 2.12, 5.5, 6.95, z=bz, mat=BLACK, segs=48)
    cg.lathe(bm, [(0.0, 0.3), (1.2, 0.26), (1.75, 0.12), (1.85, 0.0)], segs=40, mat=BLACK,
             M=_T(6.95, 0, bz) @ RY)                                            # smokebox door
    cyl_x(bm, 0.12, 7.2, 7.35, z=bz, mat=BRASS, segs=12)
    rbox(bm, (0.1, 1.0, 0.12), (7.25, 0.0, bz), 0.03, BRASS)                     # door handle
    # headlamp on the smokebox top front
    rbox(bm, (0.7, 0.7, 0.8), (6.6, 0.0, bz + 2.4), 0.12, BLACK)
    cyl_x(bm, 0.26, 6.95, 7.05, z=bz + 2.4, mat=HEAD, segs=16)
    # chimney (flared) and dome, safety valves
    cg.lathe(bm, [(0.0, 0.0), (0.72, 0.0), (0.62, 0.4), (0.58, 1.9), (0.7, 2.2), (0.82, 2.35), (0.8, 2.5),
                  (0.5, 2.5), (0.5, 2.0), (0.0, 2.0)], segs=32, mat=BLACK, M=_T(6.2, 0, bz + 1.75))
    cg.lathe(bm, [(0.0, 0.0), (0.95, 0.0), (0.9, 0.35), (0.75, 0.8), (0.45, 1.05), (0.0, 1.12)], segs=32,
             mat=BRASS, M=_T(2.6, 0, bz + 1.8))
    cg.lathe(bm, [(0.0, 0.0), (0.35, 0.0), (0.3, 0.5), (0.18, 0.7), (0.0, 0.72)], segs=16, mat=BRASS,
             M=_T(0.2, 0, bz + 1.85))
    # handrails along the boiler
    for side in (-1, 1):
        cg.tube(bm, [(-1.2, side * 2.2, bz + 0.6), (5.4, side * 2.2, bz + 0.6)], 0.05, segs=6, mat=BRASS)
    # cab
    cx0, cx1 = -6.9, -1.3
    ch = 4.4
    rbox(bm, (cx1 - cx0, 6.2, ch), ((cx0 + cx1) / 2, 0.0, fz + 0.16 + ch / 2), 0.15, RED)
    for side in (-1, 1):       # side windows (dark insets with cream frames)
        rbox(bm, (2.1, 0.1, 1.7), (-3.7, side * 3.08, fz + 3.1), 0.2, CREAM)
        rbox(bm, (1.7, 0.1, 1.3), (-3.7, side * 3.12, fz + 3.1), 0.18, GLASS)
        cg.lathe(bm, [(0.0, 0.0), (0.62, 0.0), (0.62, 0.1), (0.0, 0.1)], segs=24, mat=CREAM,
                 M=_T(cx1 + 0.02, side * 1.6, fz + 3.3) @ RY)
        cg.lathe(bm, [(0.0, 0.0), (0.5, 0.0), (0.5, 0.12), (0.0, 0.12)], segs=24, mat=GLASS,
                 M=_T(cx1 + 0.03, side * 1.6, fz + 3.3) @ RY)
        rbox(bm, (5.8, 0.12, 0.14), ((cx0 + cx1) / 2, side * 3.12, fz + 0.5), 0.04, BRASS)   # lining
    # arched roof
    bm2 = bmesh.new()
    cg.lathe(bm2, [(0.0, 0.0), (3.6, 0.0), (3.6, 0.28), (0.0, 0.28)], segs=48, mat=0)
    roof = bmesh.new()
    rw, rl = 7.0, 6.4
    n = 12
    for i in range(n + 1):
        u = i / n
        y = -rw / 2 + rw * u
        zz = 0.55 * (1 - (2 * u - 1) ** 2)
        roof.verts.new((-rl / 2, y, zz))
        roof.verts.new((rl / 2, y, zz))
    roof.verts.ensure_lookup_table()
    fs = []
    for i in range(n):
        a, b, c, d = roof.verts[2 * i], roof.verts[2 * i + 1], roof.verts[2 * i + 3], roof.verts[2 * i + 2]
        fs.append(roof.faces.new((a, b, c, d)))
    bmesh.ops.solidify(roof, geom=fs, thickness=0.2)
    for v in roof.verts:
        v.co = Vector(((cx0 + cx1) / 2 - 0.2 + v.co.x, v.co.y, fz + 0.16 + ch + 0.02 + v.co.z))
    bm2.free()
    me_r = bpy.data.meshes.new('tmp.roof')
    roof.to_mesh(me_r)
    roof.free()
    bm.from_mesh(me_r)
    bpy.data.meshes.remove(me_r)
    for f in bm.faces:
        if f.material_index == 0 and f.calc_center_median().z > fz + ch + 0.1 and f.calc_center_median().x < cx1 + 0.2:
            f.material_index = CREAM
    # cylinders (steam chests) at the front, both sides
    for side in (-1, 1):
        cyl_x(bm, 0.62, 4.1, 5.9, y=side * 2.85, z=1.5, mat=GREEN, segs=24)
        cyl_x(bm, 0.68, 4.05, 4.2, y=side * 2.85, z=1.5, mat=BRASS, segs=24)
        cyl_x(bm, 0.68, 5.8, 5.95, y=side * 2.85, z=1.5, mat=BRASS, segs=24)
        rbox(bm, (2.0, 0.12, 0.12), (3.1, side * 2.98, 1.5 + 0.28), 0.03, STEEL)     # slide bars
        rbox(bm, (2.0, 0.12, 0.12), (3.1, side * 2.98, 1.5 - 0.28), 0.03, STEEL)
    # running-board valances
    for side in (-1, 1):
        rbox(bm, (14.0, 0.08, 0.5), (0.0, side * 3.08, fz - 0.2), 0.03, RED)
    body = obj(bm, 'loco.body', coll, ml)
    geo.attach(body, root)
    car.parts.append(body)
    # wheels: leading pony axle and two coupled driving axles
    for nm, x, r, spokes, crank in (('pony', 5.6, 0.72, 0, 0.0), ('drv1', 1.2, 1.45, 10, 0.62),
                                    ('drv2', -2.7, 1.45, 10, 0.62), ('trail', -5.6, 0.72, 0, 0.0)):
        bm = bmesh.new()
        wheelset(bm, r, spokes=spokes, crank=crank, mat_web=0, mat_tyre=1, mat_hub=2)
        w = obj(bm, f'loco.{nm}', coll, [Mt['red'], Mt['steel'], Mt['brass']], sharp=50)
        geo.attach(w, root, (x, 0.0, r))
        w.rotation_mode = 'XYZ'
        car.wheels.append((w, r, crank))
        car.parts.append(w)
    # rods (keyed per frame from the crank angle)
    car.rod_x = (1.2, -2.7)
    car.rod_r = 0.62
    car.rod_z = 1.45
    for side in (-1, 1):
        bm = bmesh.new()
        L = car.rod_x[0] - car.rod_x[1]
        rbox(bm, (L + 0.5, 0.1, 0.24), (0.0, 0.0, 0.0), 0.08, 0)
        for xe in (-L / 2, L / 2):
            cyl_y(bm, 0.2, -0.06, 0.06, x=xe, mat=0, segs=12)
        cr = obj(bm, f'loco.coupling.{side}', coll, [Mt['steel']])
        geo.attach(cr, root)
        bm = bmesh.new()
        rbox(bm, (2.0, 0.1, 0.2), (1.0, 0.0, 0.0), 0.07, 0)
        cyl_y(bm, 0.18, -0.06, 0.06, x=0.0, mat=0, segs=12)
        cyl_y(bm, 0.15, -0.06, 0.06, x=2.0, mat=0, segs=12)
        cn = obj(bm, f'loco.conrod.{side}', coll, [Mt['steel']])
        geo.attach(cn, root)
        bm = bmesh.new()
        rbox(bm, (0.5, 0.26, 0.44), (0.0, 0.0, 0.0), 0.06, 0)
        cyl_x(bm, 0.09, 0.0, 1.9, mat=0, segs=10)
        xh = obj(bm, f'loco.crosshead.{side}', coll, [Mt['steel']])
        geo.attach(xh, root)
        for o in (cr, cn, xh):
            o.rotation_mode = 'XYZ'
            car.parts.append(o)
        car.rods.append((side, cr, cn, xh))
    # the clockwork key on the right (-y) side of the cab
    bm = bmesh.new()
    cyl_y(bm, 0.12, -0.9, 0.0, mat=0, segs=12)
    for sgn in (-1, 1):
        cg.lathe(bm, [(0.0, 0.0), (0.55, 0.0), (0.55, 0.1), (0.0, 0.1)], segs=24, mat=0,
                 M=_T(0, -0.9, sgn * 0.62) @ RX)
    rbox(bm, (0.3, 0.1, 1.4), (0.0, -0.95, 0.0), 0.05, 0)
    key = obj(bm, 'loco.key', coll, [Mt['brass']])
    geo.attach(key, root, (-4.4, -3.1, fz + 1.4))
    key.rotation_mode = 'XYZ'
    car.key = key
    car.parts.append(key)
    car.chimney = Vector((6.2, 0.0, bz + 1.75 + 2.5))
    car.headlamp = Vector((7.1, 0.0, bz + 2.4))
    return car


def _simple_axles(car, coll, Mt, xs, r=0.8):
    for i, x in enumerate(xs):
        bm = bmesh.new()
        wheelset(bm, r, spokes=0, mat_web=0, mat_tyre=1, mat_hub=2)
        w = obj(bm, f'{car.name}.axle{i}', coll, [Mt['red'], Mt['steel'], Mt['brass']], sharp=50)
        geo.attach(w, car.root, (x, 0.0, r))
        w.rotation_mode = 'XYZ'
        car.wheels.append((w, r, 0.0))
        car.parts.append(w)


def _frame(bm, L, W, z, mat_red, mat_black):
    rbox(bm, (L, W, 0.3), (0.0, 0.0, z), 0.08, mat_red)
    rbox(bm, (L - 0.6, 4.6, 0.7), (0.0, 0.0, z - 0.45), 0.06, mat_black)
    for sx in (-1, 1):
        rbox(bm, (0.35, 0.9, 0.35), (sx * (L / 2 + 0.15), 0.0, z - 0.2), 0.06, mat_black)     # couplers


def build_tender(coll, Mt, offset):
    root = _car_root('tender', coll)
    car = Car('tender', 7.0, 4.4, offset, root)
    ml = [Mt['red'], Mt['green'], Mt['black'], Mt['brass'], Mt['coal']]
    bm = bmesh.new()
    _frame(bm, 7.0, 6.0, 2.5, 0, 2)
    rbox(bm, (6.8, 5.9, 3.0), (0.0, 0.0, 2.65 + 1.5), 0.2, 1)
    for side in (-1, 1):
        rbox(bm, (6.2, 0.1, 0.12), (0.0, side * 2.97, 3.1), 0.04, 3)
        rbox(bm, (6.2, 0.1, 0.12), (0.0, side * 2.97, 5.2), 0.04, 3)
    # coal heap
    heap = bmesh.new()
    bmesh.ops.create_grid(heap, x_segments=18, y_segments=16, size=1.0)
    for v in heap.verts:
        x, y = v.co.x * 3.2, v.co.y * 2.7
        h = 0.9 * max(0.0, 1 - (x / 3.4) ** 2) * max(0.0, 1 - (y / 2.9) ** 2)
        h += 0.12 * math.sin(x * 5.1 + y * 3.3) * math.cos(y * 4.7 - x * 1.9)
        v.co = Vector((x, y, 5.6 + h))
    for f in heap.faces:
        f.material_index = 4
    me = bpy.data.meshes.new('tmp.heap')
    heap.to_mesh(me)
    heap.free()
    bm.from_mesh(me)
    bpy.data.meshes.remove(me)
    body = obj(bm, 'tender.body', coll, ml, sharp=60)
    geo.attach(body, root)
    car.parts.append(body)
    _simple_axles(car, coll, Mt, (2.2, -2.2))
    return car


def build_tub(coll, Mt, offset):
    root = _car_root('tub', coll)
    car = Car('tub', 10.4, 6.0, offset, root)
    ml = [Mt['red'], Mt['blue'], Mt['black'], Mt['yellow']]
    bm = bmesh.new()
    _frame(bm, 8.4, 6.0, 2.2, 0, 2)
    # the tub: a rounded box, open at the top, walls 0.22
    tub = bmesh.new()
    H = 3.5
    cg.rounded_box(tub, (10.4, 9.4, H), 0.5, (0.0, 0.0, 2.35 + H / 2), seg=4, flat=(3, 3, 2), mat=1)
    tub.normal_update()
    top = [f for f in tub.faces if f.calc_center_median().z > 2.35 + H - 0.05 and f.normal.z > 0.9]
    bmesh.ops.delete(tub, geom=top, context='FACES')
    bmesh.ops.solidify(tub, geom=tub.faces[:], thickness=0.22)
    me = bpy.data.meshes.new('tmp.tub')
    tub.to_mesh(me)
    tub.free()
    bm.from_mesh(me)
    bpy.data.meshes.remove(me)
    # yellow rim and a band
    zr = 2.35 + H
    loop = []
    for i in range(65):
        a = 2 * math.pi * i / 64
        # superellipse around the tub's top outline
        cx, cy = 4.72, 4.22
        c, s_ = math.cos(a), math.sin(a)
        k = 6.0
        x = cx * math.copysign(abs(c) ** (2 / k), c)
        y = cy * math.copysign(abs(s_) ** (2 / k), s_)
        loop.append((x, y, zr))
    cg.tube(bm, loop, 0.2, segs=8, mat=3, cap0=False, cap1=False)
    for side in (-1, 1):
        rbox(bm, (8.0, 0.1, 0.35), (0.0, side * 4.72, 2.35 + 1.2), 0.08, 3)
    body = obj(bm, 'tub.body', coll, ml, sharp=50)
    geo.attach(body, root)
    car.parts.append(body)
    _simple_axles(car, coll, Mt, (3.0, -3.0))
    car.seat = geo.empty('tub.seat', (0, 0, 0), coll, 1.0)
    geo.attach(car.seat, root, (0.0, 0.0, 2.35 + 0.22))
    return car


def build_caboose(coll, Mt, offset):
    root = _car_root('caboose', coll)
    car = Car('caboose', 8.5, 5.4, offset, root)
    ml = [Mt['red'], Mt['black'], Mt['cream'], Mt['glass'], Mt['lamp'], Mt['yellow']]
    bm = bmesh.new()
    _frame(bm, 8.5, 6.2, 2.3, 0, 1)
    z0 = 2.45
    rbox(bm, (7.0, 5.6, 3.8), (0.0, 0.0, z0 + 1.9), 0.15, 0)
    for side in (-1, 1):
        for xw in (-1.8, 1.8):
            rbox(bm, (1.3, 0.1, 1.3), (xw, side * 2.82, z0 + 2.3), 0.12, 2)
            rbox(bm, (1.0, 0.1, 1.0), (xw, side * 2.86, z0 + 2.3), 0.1, 3)
        rbox(bm, (6.6, 0.1, 0.14), (0.0, side * 2.85, z0 + 0.6), 0.04, 5)
    # end platforms with railings
    for sx in (-1, 1):
        rbox(bm, (0.9, 6.0, 0.18), (sx * 4.0, 0.0, z0 + 0.05), 0.05, 1)
        for yy in (-2.6, 0.0, 2.6):
            cg.tube(bm, [(sx * 4.3, yy, z0 + 0.1), (sx * 4.3, yy, z0 + 1.6)], 0.05, segs=6, mat=5)
        cg.tube(bm, [(sx * 4.3, -2.7, z0 + 1.55), (sx * 4.3, 2.7, z0 + 1.55)], 0.05, segs=6, mat=5)
    # roof and cupola
    rbox(bm, (8.0, 6.3, 0.3), (0.0, 0.0, z0 + 3.95), 0.12, 1)
    rbox(bm, (3.0, 4.2, 1.6), (0.0, 0.0, z0 + 4.85), 0.12, 0)
    for side in (-1, 1):
        rbox(bm, (0.8, 0.1, 0.7), (-0.7, side * 2.12, z0 + 4.9), 0.08, 3)
        rbox(bm, (0.8, 0.1, 0.7), (0.7, side * 2.12, z0 + 4.9), 0.08, 3)
    rbox(bm, (3.5, 4.7, 0.25), (0.0, 0.0, z0 + 5.72), 0.1, 1)
    cyl_z(bm, 0.18, z0 + 5.8, z0 + 6.6, x=1.1, mat=1, segs=12)       # stove pipe
    # tail lamp
    rbox(bm, (0.5, 0.5, 0.6), (-4.35, 1.8, z0 + 2.2), 0.08, 1)
    cyl_x(bm, 0.2, -4.7, -4.6, y=1.8, z=z0 + 2.2, mat=4, segs=16)
    body = obj(bm, 'caboose.body', coll, ml, sharp=50)
    geo.attach(body, root)
    car.parts.append(body)
    _simple_axles(car, coll, Mt, (2.7, -2.7))
    return car


# ------------------------------------------------------------------------------------------------ track


class Oval:
    """The track's centre line: two straights along x and two half circles, counter-clockwise from the start of
    the front (-y) straight. s is arc length (cm); wraps every L."""

    def __init__(self, O, rc=15.0, a=9.0):
        self.O = Vector((O[0], O[1], 0.0))
        self.rc, self.a = rc, a
        self.seg = [2 * a, math.pi * rc, 2 * a, math.pi * rc]
        self.L = sum(self.seg)

    def at(self, s):
        """(point on the rail tops, heading angle in radians)."""
        O, rc, a = self.O, self.rc, self.a
        s = s % self.L
        if s < 2 * a:
            return Vector((O.x - a + s, O.y - rc, RAIL_Z)), 0.0
        s -= 2 * a
        if s < math.pi * rc:
            ang = -math.pi / 2 + s / rc
            return Vector((O.x + a + rc * math.cos(ang), O.y + rc * math.sin(ang), RAIL_Z)), ang + math.pi / 2
        s -= math.pi * rc
        if s < 2 * a:
            return Vector((O.x + a - s, O.y + rc, RAIL_Z)), math.pi
        s -= 2 * a
        ang = math.pi / 2 + s / rc
        return Vector((O.x - a + rc * math.cos(ang), O.y + rc * math.sin(ang), RAIL_Z)), ang + math.pi / 2

    def pieces(self):
        """[(s_a, s_b)] for 18 pieces: 3 per straight, 6 per half circle."""
        out = []
        s = 0.0
        for k, ln in enumerate(self.seg):
            n = 3 if k % 2 == 0 else 6
            for i in range(n):
                out.append((s + ln * i / n, s + ln * (i + 1) / n))
            s += ln
        return out


def build_track(coll, oval: Oval, Mt):
    """One object per piece, its origin at the piece's middle on the desk, x along the track there."""
    pieces = []
    for i, (sa, sb) in enumerate(oval.pieces()):
        sm = (sa + sb) / 2
        pm, hm = oval.at(sm)
        Mm = Matrix.Translation((pm.x, pm.y, 0.0)) @ Matrix.Rotation(hm, 4, 'Z')
        Mi = Mm.inverted()
        bm = bmesh.new()
        n = max(4, int((sb - sa) / 0.6))
        # rails: a hollow tin profile swept along the piece (lateral offset +-GAUGE/2)
        prof = [(-0.24, 0.0), (0.24, 0.0), (0.2, 0.1), (0.1, RAIL_Z - TIE_T - 0.08), (0.07, RAIL_Z - TIE_T),
                (-0.07, RAIL_Z - TIE_T), (-0.1, RAIL_Z - TIE_T - 0.08), (-0.2, 0.1)]
        for side in (-1, 1):
            rings = []
            for j in range(n + 1):
                s = sa + (sb - sa) * j / n
                p, h = oval.at(s)
                t = Vector((math.cos(h), math.sin(h), 0.0))
                lat = Vector((-t.y, t.x, 0.0))
                c = Vector((p.x, p.y, TIE_T)) + lat * (side * GAUGE / 2)
                ring = [bm.verts.new(Mi @ (c + lat * px + Vector((0, 0, pz)))) for px, pz in prof]
                rings.append(ring)
            m = len(prof)
            for A, B in zip(rings[:-1], rings[1:]):
                for k in range(m):
                    k2 = (k + 1) % m
                    f = bm.faces.new((A[k], A[k2], B[k2], B[k]))
                    f.material_index = 0
            for R_, flip in ((rings[0], True), (rings[-1], False)):
                f = bm.faces.new(list(reversed(R_)) if flip else R_)
                f.material_index = 0
        # ties (pressed tin: the ends bend down a little), built in their own bmesh then merged
        nt = max(2, int(round((sb - sa) / 2.6)))
        bm_t = bmesh.new()
        for j in range(nt):
            s = sa + (sb - sa) * (j + 0.5) / nt
            p, h = oval.at(s)
            Mt_ = Mi @ Matrix.Translation((p.x, p.y, TIE_T / 2)) @ Matrix.Rotation(h, 4, 'Z')
            before = set(bm_t.verts)
            cg.rounded_box(bm_t, (TIE_W, TIE_L, TIE_T), 0.06, (0, 0, 0), seg=1, flat=(1, 3, 0), mat=1)
            for v in bm_t.verts:
                if v not in before:
                    v.co.z -= 0.08 * max(0.0, abs(v.co.y) - TIE_L / 2 + 0.6) / 0.6
                    v.co = Mt_ @ v.co
        me = bpy.data.meshes.new('tmp.ties')
        bm_t.to_mesh(me)
        bm_t.free()
        bm.from_mesh(me)
        bpy.data.meshes.remove(me)
        ob = obj(bm, f'track.{i:02d}', coll, [Mt['rail'], Mt['tie']], sharp=35)
        ob.matrix_basis = Mm
        ob.rotation_mode = 'XYZ'
        pieces.append(dict(obj=ob, sa=sa, sb=sb, M=Mm.copy(), mid=Vector((pm.x, pm.y, 0.0)), head=hm))
    return pieces


# ------------------------------------------------------------------------------------------------ path + run


class Path:
    """Oval until s_leave (unwrapped), then a spiral off the gap into the disc: it keeps going straight for a
    moment, then curls counter-clockwise around the hole, climbs to the disc plane and winds down to r_end."""

    def __init__(self, oval: Oval, C, *, s_leave=None, turns=3.9, r_orb=9.6, r_end=0.8, climb=0.12, fly=6.0):
        self.oval = oval
        self.C = Vector(C)
        self.s_leave = s_leave
        self.sp_s = [0.0]
        self.sp_p = []
        if s_leave is not None:
            p0, h0 = oval.at(s_leave)
            t0 = Vector((math.cos(h0), math.sin(h0), 0.0))
            d = p0 - Vector((self.C.x, self.C.y, p0.z))
            r0 = d.length
            a0 = math.atan2(d.y, d.x)
            n = 1600
            pts = []
            for i in range(n + 1):
                u = i / n
                a = a0 + 2 * math.pi * turns * u
                # captured into a wide orbit fast, a slow decay, then the plunge
                r = (r_end + (r_orb - r_end) * (1 - tm.smooth(u, 0.55, 1.0)) ** 0.8 * (1 - 0.18 * u) +
                     (r0 - r_orb) * math.exp(-u / 0.05))
                z = RAIL_Z + (self.C.z - RAIL_Z) * tm.smooth(u, 0.0, climb)
                sp = Vector((self.C.x + r * math.cos(a), self.C.y + r * math.sin(a), z))
                ln = Vector((p0.x, p0.y, z)) + t0 * (u * fly * 10.0)
                w = tm.smooth(u, 0.0, 0.06)
                pts.append(ln.lerp(sp, w))
            self.sp_p = pts
            for i in range(1, len(pts)):
                self.sp_s.append(self.sp_s[-1] + (pts[i] - pts[i - 1]).length)

    def at(self, s):
        """Point (3D) and unit tangent at unwrapped arc length s."""
        if self.s_leave is None or s <= self.s_leave:
            p, h = self.oval.at(s)
            return p, Vector((math.cos(h), math.sin(h), 0.0))
        x = s - self.s_leave
        S = self.sp_s
        if x >= S[-1]:
            p = self.sp_p[-1]
            return p.copy(), (self.sp_p[-1] - self.sp_p[-2]).normalized()
        i = max(0, bisect.bisect_right(S, x) - 1)
        u = (x - S[i]) / max(1e-9, S[i + 1] - S[i])
        a, b = self.sp_p[i], self.sp_p[i + 1]
        return a.lerp(b, u), (b - a).normalized()

    def radius(self, s):
        p, _ = self.at(s)
        return (p.xy - self.C.xy).length


class Run:
    """s(t): the loco's unwrapped arc length. Steady v0 until t_acc, then v grows as a power of time to v1 at t_leave
    and keeps growing on the spiral (v2 at t_end). Integrated numerically (fine steps) once."""

    def __init__(self, s0, t0, *, v0=24.0, t_acc=45.06, t_leave=47.963, v1=165.0, t_end=49.6, v2=240.0, p=2.0):
        self.t0 = t0
        self.v0, self.t_acc, self.t_leave, self.v1, self.t_end, self.v2, self.p = v0, t_acc, t_leave, v1, t_end, v2, p
        self.dt = 1.0 / 480
        self.ts = []
        self.ss = []
        t, s = t0 - 1.0, s0 - v0 * 1.0
        while t < t_end + 1.0:
            self.ts.append(t)
            self.ss.append(s)
            s += self.v(t + self.dt / 2) * self.dt
            t += self.dt

    def v(self, t):
        if t < self.t_acc:
            return self.v0
        if t < self.t_leave:
            x = (t - self.t_acc) / (self.t_leave - self.t_acc)
            return self.v0 + (self.v1 - self.v0) * x ** self.p
        x = min(1.0, (t - self.t_leave) / (self.t_end - self.t_leave))
        return self.v1 + (self.v2 - self.v1) * x

    def s(self, t):
        i = int((t - self.ts[0]) / self.dt)
        i = max(0, min(len(self.ts) - 2, i))
        u = (t - self.ts[i]) / self.dt
        return self.ss[i] + (self.ss[i + 1] - self.ss[i]) * u

    def t_at(self, s):
        i = bisect.bisect_left(self.ss, s)
        i = max(1, min(len(self.ss) - 1, i))
        a, b = self.ss[i - 1], self.ss[i]
        return self.ts[i - 1] + self.dt * (s - a) / max(1e-9, b - a)


# ------------------------------------------------------------------------------------------------ the train


class Train:
    GAP = 1.2

    def __init__(self, coll, Mt):
        self.loco = build_loco(coll, Mt)
        off = -(14.0 / 2 + self.GAP + 7.0 / 2)
        self.tender = build_tender(coll, Mt, off)
        off -= 7.0 / 2 + self.GAP + 10.4 / 2
        self.tub = build_tub(coll, Mt, off)
        off -= 10.4 / 2 + self.GAP + 8.5 / 2
        self.caboose = build_caboose(coll, Mt, off)
        self.cars = [self.loco, self.tender, self.tub, self.caboose]
        self.front = 7.0
        self.back = off - 8.5 / 2          # the caboose's rear, relative to the loco centre

    def car_matrix(self, car, s_loco, path: Path, *, bank=0.0, stretch=None):
        """World matrix of a car whose centre is at s_loco + car.offset (two bogie points on the path)."""
        sc = s_loco + car.offset
        pf, _ = path.at(sc + car.wb / 2)
        pr, _ = path.at(sc - car.wb / 2)
        mid = (pf + pr) / 2
        fwd = (pf - pr)
        if fwd.length < 1e-6:
            _, fwd = path.at(sc)
        fwd.normalize()
        up0 = Vector((0.0, 0.0, 1.0))
        lat = up0.cross(fwd).normalized()
        up = fwd.cross(lat).normalized()
        R = Matrix((fwd, lat, up)).transposed().to_4x4()
        if bank:
            R = R @ Matrix.Rotation(bank, 4, 'X')
        Mw = Matrix.Translation(mid) @ R
        if stretch is not None:
            kl, kw = stretch
            Mw = Mw @ Matrix.Diagonal((max(1e-3, kl), max(1e-3, kw), max(1e-3, kw), 1.0))
        return Mw
