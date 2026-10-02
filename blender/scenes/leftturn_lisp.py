"""The `leftturn` Lisp list (revision 2: "Without a single CDR" is Lisp): a toy linked list built like an SICP
box-and-pointer diagram. Wooden cons cells stand on the desk, each a little tray with two compartments, the car
(left, the word of the lyric sits in it as painted letter blocks) and the cdr (right, a black bead with a bent-wire
arrow rising out of it, arching over and pointing down into the next cell's car); the last cdr has the nil slash.
A pair of big wooden parentheses stands at the two ends: '(WITHOUT A SINGLE CDR).

Local frames: a cell's origin is its bottom centre, +X along the list (reading direction), -Y the open front, +Z up.
An arrow's origin is its bead (the cdr's centre), +X toward the next cell.
"""
from __future__ import annotations

import math

import bmesh
import bpy
from mathutils import Matrix, Vector

from pdoom import kit
from pdoom.sets import geo
from pdoom.sets import materials as M

CELL_W, CELL_D, CELL_H, WALL = 6.8, 2.1, 2.0, 0.22
CAR_W = 5.4                                   # the car compartment's outer width (the cdr gets the rest)
GAP = 1.6                                     # between cells
PITCH = CELL_W + GAP
CDR_X = -CELL_W / 2 + CAR_W + (CELL_W - CAR_W) / 2          # the cdr's centre (cell-local x)
BEAD_Z = 1.0
ARCH_Z = 3.35                                 # the arrow's top run (Clawd's mouth height)
ARROW_L = PITCH - CDR_X + (-CELL_W / 2 + WALL + 0.75)       # bead -> into the next car


def _cube(bm, size, center):
    bmesh.ops.create_cube(bm, size=1.0, matrix=Matrix.Translation(center) @ Matrix.Diagonal((*size, 1.0)))


def mats():
    return {
        'wood': M.solid('lt.cons.wood', '#D8B887', rough=0.48, coat=0.25, coat_rough=0.15, micro=(14.0, 0.03)),
        'car': M.solid('lt.cons.car', '#F3E7CF', rough=0.6),
        'cdr': M.solid('lt.cons.cdr', '#BFD6E6', rough=0.6),
        'ink': M.solid('lt.cons.ink', '#1C1A18', rough=0.35, coat=0.6),
        'wire': M.solid('lt.cons.wire', '#B9BEC6', rough=0.22, metal=1.0),
        'paren': M.solid('lt.cons.paren', '#7A4A2A', rough=0.4, coat=0.5, coat_rough=0.1, micro=(10.0, 0.04)),
    }


def cell(coll, name, *, last=False):
    """One cons cell (one mesh, three materials: wood frame, cream car back, pale blue cdr back; plus the bead or
    the nil slash in black)."""
    mt = mats()
    bm = bmesh.new()
    W, D, H, T = CELL_W, CELL_D, CELL_H, WALL
    x0, x1 = -W / 2, W / 2
    xp = x0 + CAR_W
    # frame: bottom, left, right, partition, a lip on top of the back
    _cube(bm, (W, D, T), (0, 0, T / 2))
    _cube(bm, (T, D, H), (x0 + T / 2, 0, H / 2))
    _cube(bm, (T, D, H), (x1 - T / 2, 0, H / 2))
    _cube(bm, (T, D, H), (xp, 0, H / 2))
    _cube(bm, (W, T * 1.2, T), (0, D / 2 - T * 0.6, H - T / 2))
    nf = len(bm.faces)
    # painted back panels (the compartments read as two boxes)
    _cube(bm, (xp - x0 - T * 1.5, T * 0.8, H - T * 1.5), ((x0 + xp) / 2, D / 2 - T * 0.4, H / 2))
    n_car = len(bm.faces)
    _cube(bm, (x1 - xp - T * 1.5, T * 0.8, H - T * 1.5), ((xp + x1) / 2, D / 2 - T * 0.4, H / 2))
    n_cdr = len(bm.faces)
    for i, f in enumerate(bm.faces):
        f.material_index = 0 if i < nf else (1 if i < n_car else 2)
    if last:                                   # nil: the slash across the cdr's front
        cx = (xp + x1) / 2
        L = math.hypot(x1 - xp - T, H - T)
        ang = math.atan2(H - T, x1 - xp - T)
        bmesh.ops.create_cube(bm, size=1.0, matrix=Matrix.Translation((cx, -D / 2 + 0.25, H / 2 + T / 4))
                              @ Matrix.Rotation(-ang, 4, 'Y') @ Matrix.Diagonal((L * 0.95, 0.12, 0.16, 1.0)))
        for f in bm.faces[n_cdr:]:
            f.material_index = 3
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    o = bpy.data.objects.new(name, me)
    coll.objects.link(o)
    for m in (mt['wood'], mt['car'], mt['cdr'], mt['ink']):
        me.materials.append(m)
    bev = o.modifiers.new('bevel', 'BEVEL')
    bev.width, bev.segments, bev.limit_method = 0.05, 2, 'ANGLE'
    kit.smooth(o, 35)
    if not last:                               # the bead the pointer leaves from
        b = kit.sphere(name + '.bead', 0.26, (CDR_X, 0.1, BEAD_Z), m=mt['ink'], coll=coll, subdiv=2)
        b.parent = o
    return o


def arrow(coll, name):
    """A bent steel-wire pointer from the cdr's bead: up out of the tray, over the gap, down into the next car, with
    an arrowhead. Origin at the bead."""
    mt = mats()
    L = ARROW_L
    up = ARCH_Z - BEAD_Z
    r = 0.35
    pts = [(0, 0, 0), (0, 0, up - r), (r * 0.3, 0, up - r * 0.3), (r, 0, up), (L - r, 0, up),
           (L - r * 0.3, 0, up - r * 0.3), (L, 0, up - r), (L, 0, up - 1.35)]
    o = geo.curve_tube(name, pts, 0.075, coll=coll, m=mt['wire'], kind='POLY', to_mesh=True)
    # the arrowhead: a cone pointing down (-Z) at the wire's end
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=True, segments=16, radius1=0.24, radius2=0.0, depth=0.55,
                          matrix=Matrix.Translation((L, 0, up - 1.35 - 0.22)) @ Matrix.Rotation(math.pi, 4, 'X'))
    me = bpy.data.meshes.new(name + '.head')
    bm.to_mesh(me)
    bm.free()
    head = bpy.data.objects.new(name + '.head', me)
    coll.objects.link(head)
    me.materials.append(mt['wire'])
    for p in me.polygons:
        p.use_smooth = True
    head.parent = o
    return o


def paren(coll, name, side):
    """A big wooden parenthesis standing on the desk: side -1 is '(' (it bulges to -X), +1 is ')'."""
    mt = mats()
    R, h = 5.2, 7.6
    half = math.asin(min(0.999, (h / 2) / R))
    pts = []
    n = 16
    for k in range(n + 1):
        a = -half + 2 * half * k / n
        x = side * (R * math.cos(a) - R * math.cos(half))        # the middle bulges outward ('(' to -X)
        pts.append((x, 0.0, h / 2 + R * math.sin(a) + 0.45))
    o = geo.curve_tube(name, pts, 0.5, coll=coll, m=mt['paren'], kind='BEZIER', to_mesh=True,
                       radii=[0.75 + 0.35 * math.cos(math.pi * (k / n - 0.5)) for k in range(n + 1)])
    foot = kit.box(name + '.foot', (1.8, 1.8, 0.35), (0, 0, 0.175), bevel=0.08, segments=2, m=mt['paren'],
                   coll=coll)
    foot.parent = o
    return o
