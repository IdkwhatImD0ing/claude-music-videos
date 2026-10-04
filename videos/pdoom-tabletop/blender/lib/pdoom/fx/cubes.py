"""Atoms rearranging: an object dissolves into small cubes that swirl out and reassemble (geometry nodes, a pure
function of song time; nothing baked).

    from pdoom.fx import cubes
    c = cubes.dissolve('hand', hand_obj, t0=49.56, t1=51.2, cube=0.35, shuffle=True)

The object is voxelised in Python (cube centres on a grid inside the mesh, by ray parity), each cube takes its
colour from the object's material, and flies from its own cell to a target cell: its own (shuffle=False: the
object comes back as it was) or another cube's (shuffle=True: the same shape, every atom somewhere new). The
original hides for the flight. Timing per cube is staggered by height (bottom first) and a little noise.
"""
from __future__ import annotations

import math

import bpy
from mathutils import Vector
from mathutils.bvhtree import BVHTree

from .. import kit
from ..timing import FPS
from . import _nodes as N
from . import log, vis


def _voxels(obj, cube: float, limit: int):
    import bmesh
    import numpy as np
    dg = bpy.context.evaluated_depsgraph_get()
    oe = obj.evaluated_get(dg)
    me = oe.to_mesh()
    bm = bmesh.new()
    bm.from_mesh(me)
    oe.to_mesh_clear()
    bm.transform(obj.matrix_world)
    bvh = BVHTree.FromBMesh(bm)
    xs = [v.co for v in bm.verts]
    lo = Vector((min(v.x for v in xs), min(v.y for v in xs), min(v.z for v in xs)))
    hi = Vector((max(v.x for v in xs), max(v.y for v in xs), max(v.z for v in xs)))
    bm.free()
    while True:
        n = [max(1, int((hi[i] - lo[i]) / cube)) for i in range(3)]
        if n[0] * n[1] * n[2] <= limit * 4:
            break
        cube *= 1.15
    pts = []
    d = Vector((0.577, 0.577, 0.577))
    for i in range(n[0]):
        for j in range(n[1]):
            for k in range(n[2]):
                p = lo + Vector(((i + 0.5) * cube, (j + 0.5) * cube, (k + 0.5) * cube))
                # parity: count hits along +d
                hits, q = 0, p.copy()
                for _ in range(64):
                    loc, nrm, idx, dist = bvh.ray_cast(q, d)
                    if loc is None:
                        break
                    hits += 1
                    q = loc + d * 1e-4
                if hits % 2 == 1:
                    pts.append(tuple(p))
    return np.array(pts, dtype=np.float32).reshape(-1, 3), cube, lo, hi


def dissolve(name: str, obj, *, t0: float, t1: float, cube: float = 0.35, shuffle: bool = True,
             spread: float = 6.0, swirl: float = 2.5, spin: float = 3.0, stagger: float = 0.45, gap: float = 0.08,
             mat=None, seed: int = 6, limit: int = 20000, hide_original: bool = True, floor: float | None = 0.0,
             coll=None) -> dict:
    """obj breaks into cubes of edge `cube` cm at song time t0 and is whole again at t1. Each cube lifts off,
    flies out up to `spread` cm on a swirl (`swirl` turns about the object's vertical axis), tumbles (`spin` turns),
    and lands in its target cell; `stagger` (0-0.8) spreads the start/finish of individual cubes over the window.
    gap: fraction of the edge left between cubes. mat: cube material (default: the object's first material).
    floor: height the cubes never dip below (the desk top; None = no limit).
    Returns {'object', 'modifier', 'count', 'cube'}; cubes show only during [t0, t1]."""
    import numpy as np
    rng = np.random.default_rng(seed)
    pts, cube, lo, hi = _voxels(obj, cube, limit)
    n = len(pts)
    if n == 0:
        raise ValueError(f'cubes.dissolve: no voxels inside {obj.name} (is it a closed mesh?)')
    tgt = pts[rng.permutation(n)] if shuffle else pts.copy()
    ctr = (np.array(lo) + np.array(hi)) / 2
    h = (pts[:, 2] - lo.z) / max(1e-6, hi.z - lo.z)
    delay = np.clip(h * stagger * 0.7 + rng.uniform(0, stagger * 0.3, n), 0, stagger)
    axis = rng.normal(0, 1, (n, 3))
    axis /= np.linalg.norm(axis, axis=1, keepdims=True)
    out = pts - ctr[None]
    out[:, 2] *= 0.3
    out /= np.maximum(np.linalg.norm(out, axis=1, keepdims=True), 1e-3)
    out = out * rng.uniform(0.4, 1.0, (n, 1)) * spread + rng.normal(0, spread * 0.15, (n, 3))
    if floor is not None:
        # never dip through the surface the object stands on (z offsets scale with the 0..1 flight bump)
        out[:, 2] = np.maximum(out[:, 2], floor + cube * 0.6 - np.minimum(pts[:, 2], tgt[:, 2]))
    me = bpy.data.meshes.new(name)
    me.vertices.add(n)
    me.vertices.foreach_set('co', pts.ravel())
    for nm, arr in (('tgt', tgt), ('out', out), ('axis', axis)):
        a = me.attributes.new(nm, 'FLOAT_VECTOR', 'POINT')
        a.data.foreach_set('vector', np.asarray(arr, dtype=np.float32).ravel())
    for nm, arr in (('delay', delay), ('seed', rng.uniform(0, 1, n))):
        a = me.attributes.new(nm, 'FLOAT', 'POINT')
        a.data.foreach_set('value', np.asarray(arr, dtype=np.float32).ravel())
    me.update()
    ob = bpy.data.objects.new(name, me)
    (coll or kit.collection('fx.cubes')).objects.link(ob)
    # the unit cube instance
    cname = f'{name}.cube'
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=(0, 0, -10000))
    cob = bpy.context.object
    cob.name = cname
    bev = cob.modifiers.new('bevel', 'BEVEL')
    bev.width, bev.segments = 0.08, 2
    kit.link(cob, kit.collection('fx.protos'))
    cob.hide_render = True
    m = mat or (obj.data.materials[0] if getattr(obj.data, 'materials', None) and len(obj.data.materials) else
                kit.mat('fx.cube', '#C9CED6', rough=0.4))
    cob.data.materials.append(m)
    # geometry nodes: progress 0..1 over [t0, t1]
    g = N.Tree(f'{name}.gn')
    geo = g.input_geometry()
    prog = g.param('Progress', 'FLOAT', 0.0)
    ctr_in = g.param('Centre', 'VECTOR', tuple(ctr))

    def attr(nm, kind='FLOAT'):
        return g.out(g.node('GeometryNodeInputNamedAttribute', data_type=kind, inputs={'Name': nm}), 'Attribute')

    d = attr('delay')
    s = g.clamp((prog - d) / (1.0 - stagger))
    e = g.smooth(s, 0.0, 1.0)                     # eased 0..1 per cube
    bump = g.sin(s * math.pi)                     # 0 -> 1 -> 0: out and back
    p = g.position()
    tgt_p = attr('tgt', 'FLOAT_VECTOR')
    base = p + (tgt_p - p) * e
    # swirl the outward offset about the vertical through the centre
    ang = (e * swirl) * 6.2832
    o = attr('out', 'FLOAT_VECTOR')
    ox, oy = o.x, o.y
    rot_o = g.vec(ox * g.cos(ang) - oy * g.sin(ang), ox * g.sin(ang) + oy * g.cos(ang), o.z + bump * 0.0)
    pos = base + rot_o * bump
    geo = g.set_position(geo, position=pos)
    rot = g.axis_angle(attr('axis', 'FLOAT_VECTOR'), bump * (spin * 6.2832) * attr('seed'))
    k = cube * (1.0 - gap)
    inst = g.instance(geo, g.object_geo(cob, as_instance=True, relative=False), rotation=rot,
                      scale=g.vec(k, k, k))
    g.output(inst)
    mod = N.modifier(ob, g, 'cubes')
    N.key_input(ob, mod, 'Progress', t0, 0.0, interp='LINEAR')
    N.key_input(ob, mod, 'Progress', t1, 1.0, interp='LINEAR')
    vis(ob, t0, t1)
    if hide_original:
        vis(obj, None, t0)
        # and back at t1: key it visible again
        obj.hide_render = False
        obj.keyframe_insert('hide_render', frame=t1 * FPS)
        for fc in kit.fcurves(obj):
            if fc.data_path == 'hide_render':
                for kp in fc.keyframe_points:
                    kp.interpolation = 'CONSTANT'
    log(f'cubes {name}: {n} cubes of {cube:.2f} cm from {obj.name}, t={t0:.3f}-{t1:.3f}')
    return {'object': ob, 'modifier': mod, 'count': n, 'cube': cube}
