"""Voronoi fracture (the cell-fracture add-on isn't bundled in 5.2) and rigid-body breaking.

    from pdoom.fx import fracture, rigid, materials
    pieces = fracture.fracture(jar, 60, seed=3, impact=(0, 0, 6), inner=materials.glass())  # objects, jar hidden
    fracture.crack(pieces, t=74.3, origin=(0, -5, 0.5), speed=40)     # a crack runs up from the base (no break)
    fracture.shatter(pieces, t=74.6, impact=(0, 0, 6), speed=(30, 110))   # bursts from inside at t
    rigid.bake()

    # a keyed object that breaks at a song time (the toppling vacuum-tube computer):
    pieces = fracture.fracture(model, 40, inner=materials.ceramic_break())
    fracture.shatter(pieces, t=77.72, follow=model, impact=None, speed=(10, 40))  # follows model's keys until t

fracture(): each piece is the source mesh clipped by the perpendicular-bisector planes to its neighbouring seeds;
every cut is capped (triangle fill, holes handled, so hollow walls get annulus caps) with the `inner` material.
The source must be a closed mesh (modifiers are applied first: give a jar a Solidify). Pieces are convex cells of
the source, so CONVEX_HULL collision is exact for convex sources and close for hollow ones. Until swap time the
original object is shown and the pieces are hidden (coplanar internal faces would show in glass).
"""
from __future__ import annotations

import math
import random
import time

import bmesh
import bpy
from mathutils import Matrix, Vector
from mathutils.bvhtree import BVHTree

from .. import kit
from ..timing import FPS
from . import log, vis


def _eval_bmesh(obj) -> bmesh.types.BMesh:
    dg = bpy.context.evaluated_depsgraph_get()
    oe = obj.evaluated_get(dg)
    me = oe.to_mesh()
    bm = bmesh.new()
    bm.from_mesh(me)
    oe.to_mesh_clear()
    bm.transform(obj.matrix_world)
    bmesh.ops.triangulate(bm, faces=[f for f in bm.faces if len(f.verts) > 4])
    return bm


def _seeds(bm, n: int, rng: random.Random, impact, cluster: float, mode: str):
    bvh = BVHTree.FromBMesh(bm)
    xs = [v.co for v in bm.verts]
    lo = Vector((min(v.x for v in xs), min(v.y for v in xs), min(v.z for v in xs)))
    hi = Vector((max(v.x for v in xs), max(v.y for v in xs), max(v.z for v in xs)))
    size = (hi - lo).length

    def inside(p):
        hit = bvh.find_nearest(p)
        return hit[0] is not None and (hit[0] - p).dot(hit[1]) > 0

    # surface sampling (thin shells): area-weighted points on faces
    faces = list(bm.faces)
    areas = [f.calc_area() for f in faces]
    tot = sum(areas)

    def on_surface():
        r = rng.random() * tot
        acc = 0.0
        for f, a in zip(faces, areas):
            acc += a
            if acc >= r:
                break
        vs = [v.co for v in f.verts]
        a, b = rng.random(), rng.random()
        if a + b > 1:
            a, b = 1 - a, 1 - b
        return vs[0] + (vs[1] - vs[0]) * a + (vs[2] - vs[0]) * b

    if mode == 'auto':
        hits = sum(inside(Vector((rng.uniform(lo.x, hi.x), rng.uniform(lo.y, hi.y), rng.uniform(lo.z, hi.z))))
                   for _ in range(200))
        mode = 'volume' if hits > 30 else 'surface'
    pts = []
    tries = 0
    while len(pts) < n and tries < n * 400:
        tries += 1
        near = impact is not None and rng.random() < cluster
        if mode == 'surface':
            p = on_surface()
            if near:
                # re-sample until close to the impact (rejection with a gaussian falloff)
                d = (p - Vector(impact)).length
                if rng.random() > math.exp(-(d / (0.25 * size)) ** 2):
                    continue
        else:
            if near:
                p = Vector(impact) + Vector((rng.gauss(0, 0.15), rng.gauss(0, 0.15), rng.gauss(0, 0.15))) * size
            else:
                p = Vector((rng.uniform(lo.x, hi.x), rng.uniform(lo.y, hi.y), rng.uniform(lo.z, hi.z)))
            if not inside(p):
                continue
        if all((p - q).length > 0.02 * size for q in pts):
            pts.append(p)
    return pts, mode


def _cell(src: bmesh.types.BMesh, i: int, pts, k_near: int, gap: float, inner_index: int):
    bm = src.copy()
    cap = bm.faces.layers.int.get('fx_cap') or bm.faces.layers.int.new('fx_cap')
    p = pts[i]
    others = sorted((q for j, q in enumerate(pts) if j != i), key=lambda q: (q - p).length_squared)[:k_near]
    for q in others:
        n = (q - p).normalized()
        mid = (p + q) * 0.5 - n * (gap * 0.5)
        geom = list(bm.verts) + list(bm.edges) + list(bm.faces)
        if not geom:
            break
        res = bmesh.ops.bisect_plane(bm, geom=geom, dist=1e-5, plane_co=mid, plane_no=n, clear_outer=True)
        bnd = [e for e in bm.edges if e.is_boundary]
        if bnd:
            out = bmesh.ops.triangle_fill(bm, use_beauty=True, use_dissolve=False, edges=bnd, normal=n)
            for f in out['geom']:
                if isinstance(f, bmesh.types.BMFace):
                    f.material_index = inner_index
                    f.smooth = False
                    f[cap] = 1
    # drop degenerate leftovers, make every normal point out of the piece
    loose = [v for v in bm.verts if not v.link_faces]
    if loose:
        bmesh.ops.delete(bm, geom=loose, context='VERTS')
    if bm.faces:
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return bm


def fracture(obj, pieces: int = 40, *, seed: int = 1, impact=None, cluster: float = 0.5, mode: str = 'auto',
             inner=None, gap: float = 0.0, k_near: int = 26, coll=None, swap_at: float | None = None,
             min_volume: float = 0.0) -> list:
    """Split obj into ~`pieces` Voronoi cells. impact: a world point where pieces cluster smaller (a fraction
    `cluster` of the seeds sits near it). mode 'volume' (seeds inside; solids), 'surface' (seeds on the surface;
    thin shells like a glass jar) or 'auto'. inner: material for the fracture faces (default: the object's own).
    gap: cm shaved off every face (visible cracks). swap_at: song time the pieces replace the original (default:
    the scene start, i.e. pieces from the start and the original hidden). Returns the piece objects (origins at
    their centres, named <obj>.shard.NN), in a collection <obj>.shards."""
    t0 = time.time()
    rng = random.Random(seed)
    src = _eval_bmesh(obj)
    mats = list(obj.data.materials)
    inner_index = len(mats) if inner is not None else 0
    pts, used = _seeds(src, pieces, rng, impact, cluster, mode)
    coll = coll or kit.collection(f'{obj.name}.shards')
    out = []
    for i in range(len(pts)):
        bm = _cell(src, i, pts, k_near, gap, inner_index)
        if not bm.faces:
            bm.free()
            continue
        c = Vector()
        for v in bm.verts:
            c += v.co
        c /= len(bm.verts)
        vol = bm.calc_volume()
        if vol < min_volume:
            bm.free()
            continue
        bmesh.ops.translate(bm, verts=bm.verts, vec=-c)
        me = bpy.data.meshes.new(f'{obj.name}.shard.{i:02d}')
        bm.to_mesh(me)
        bm.free()
        for m in mats:
            me.materials.append(m)
        if inner is not None:
            me.materials.append(inner)
        for poly in me.polygons:
            if poly.material_index != inner_index or inner is None:
                poly.use_smooth = True
        piece = bpy.data.objects.new(me.name, me)
        coll.objects.link(piece)
        piece.location = c
        piece['fx_seed'] = tuple(pts[i])
        out.append(piece)
    src.free()
    # show the original until swap time, the pieces after
    sc = bpy.context.scene
    ts = swap_at if swap_at is not None else sc.frame_start / FPS
    vis(obj, None, ts)
    for p in out:
        vis(p, ts, None)
    log(f'fracture {obj.name}: {len(out)} pieces ({used} seeds) in {time.time() - t0:.1f}s')
    return out


def crack(pieces, t: float, *, origin, speed: float = 60.0, width: float = 0.009, color: str = '#F4F8FF',
          reach: float | None = None, name: str | None = None, coll=None, amount: float = 0.0, seed: int = 2):
    """A crack runs over the (still intact) object from `origin` at `speed` cm/s from song time t: bright hairline
    tubes (`width` cm) grow along the real fracture seams of `pieces` (where their caps meet the surface), so the
    later shatter() breaks exactly along the cracks. Keep the original visible until the shatter
    (fracture(..., swap_at=t_shatter)). reach: stop the crack at this distance (cm) from origin (None: everywhere).
    amount > 0 also shifts visible pieces by that much as the front passes (for pieces already swapped in).
    Returns the crack-lines object."""
    import bmesh as _bm
    o = Vector(origin)
    verts, edges, dist = [], [], []
    for pc in pieces:
        me = pc.data
        at = me.attributes.get('fx_cap')
        if at is None:
            continue
        capv = [x.value for x in at.data]
        mw = pc.matrix_basis                   # (matrix_world is stale until the depsgraph updates)
        bm = _bm.new()
        bm.from_mesh(me)
        bm.faces.ensure_lookup_table()
        for e in bm.edges:
            fs = e.link_faces
            if len(fs) != 2:
                continue
            a, b = capv[fs[0].index], capv[fs[1].index]
            if a == b:
                continue                      # a seam: one cap face and one surface face
            if (fs[0].normal.dot(fs[1].normal)) > 0.98:
                continue
            i0 = len(verts)
            for v in e.verts:
                w = mw @ v.co
                verts.append(tuple(w))
                dist.append((w - o).length)
            edges.append((i0, i0 + 1))
        bm.free()
    name = name or f'{pieces[0].name.split(".shard")[0]}.crack'
    me = bpy.data.meshes.new(name)
    me.from_pydata(verts, edges, [])
    a = me.attributes.new('d', 'FLOAT', 'POINT')
    a.data.foreach_set('value', dist)
    ob = bpy.data.objects.new(name, me)
    (coll or kit.collection(f'{name}')).objects.link(ob)
    from . import _nodes as N
    g = N.Tree(f'{name}.gn')
    geo = g.input_geometry()
    front = g.param('Front', 'FLOAT', 0.0)
    d = g.out(g.node('GeometryNodeInputNamedAttribute', data_type='FLOAT', inputs={'Name': 'd'}), 'Attribute')
    geo = g.delete(geo, d > front, domain='POINT')
    crv = g.out(g.node('GeometryNodeMeshToCurve', inputs={'Mesh': geo}))
    circ = g.out(g.node('GeometryNodeCurvePrimitiveCircle', inputs={'Resolution': 4, 'Radius': width}))
    mesh = g.out(g.node('GeometryNodeCurveToMesh', inputs={'Curve': crv, 'Profile Curve': circ}))
    m = kit.mat(f'{name}.mat', color, rough=0.15, spec=1.0, coat=1.0, emit=color, emit_strength=0.4)
    g.output(g.set_material(mesh, m))
    mod = N.modifier(ob, g, 'crack')
    far = max(dist) if dist else 0.0
    end = min(far, reach) if reach is not None else far
    N.key_input(ob, mod, 'Front', t, 0.0, interp='LINEAR')
    N.key_input(ob, mod, 'Front', t + end / max(speed, 1e-3), end, interp='LINEAR')
    if amount > 0:
        rng = random.Random(seed)
        for pc in pieces:
            c = pc.location.copy()
            tc = t + (c - o).length / max(speed, 1e-3)
            dd = (c - o).normalized() if (c - o).length > 1e-6 else Vector((0, 0, 1))
            shift = (dd + Vector((rng.gauss(0, .5), rng.gauss(0, .5), rng.gauss(0, .5)))).normalized() * amount
            kit.key(pc, 'location', tc - 1 / FPS, c)
            kit.key(pc, 'location', tc, c + shift, interp='CONSTANT')
    log(f'crack {name}: {len(edges)} seam segments, front {speed} cm/s from t={t:.3f}, reaches {end:.1f} cm')
    return ob


def topple(obj, t0: float, t_hit: float, *, direction=(0.0, -1.0, 0.0), floor: float = 0.0, tip_time: float = 0.35,
           slide: float = 3.0) -> Vector:
    """Key obj (unparented, standing on a ledge or the floor) tipping over its bottom edge toward `direction`
    (a horizontal axis: +-X or +-Y) from song time t0, falling with gravity-like timing and landing flat on that
    face on `floor` exactly at t_hit (keys every frame; `slide` cm of forward drift). Pair it with
    shatter(pieces, t_hit, follow=obj, impact=<returned point>) for a model that breaks on a beat.
    Returns the contact point under the object at t_hit."""
    from mathutils import Matrix
    d = Vector(direction)
    d.z = 0.0
    d.normalize()
    base = obj.matrix_basis.copy()
    corners = [base @ Vector(c) for c in obj.bound_box]
    zmin = min(c.z for c in corners)
    ext = max(c.dot(d) for c in corners)
    ctr = sum(corners, Vector()) / 8
    pivot = Vector((ctr.x, ctr.y, zmin)) + d * (ext - ctr.dot(d))
    axis = Vector((0, 0, 1)).cross(d).normalized()
    h_com = ctr.z - zmin
    half = ext - ctr.dot(d)
    tip = math.atan2(half, h_com) + math.radians(6)
    drop = zmin - floor
    t1 = min(t0 + tip_time, t_hit - 2 / FPS)

    def pose(ang, dz, fwd):
        R = Matrix.Rotation(ang, 4, axis)
        return Matrix.Translation(d * fwd + Vector((0, 0, -dz))) @ Matrix.Translation(pivot) @ R @ \
            Matrix.Translation(-pivot) @ base

    # after 90 degrees about the edge the object lies on that face at the ledge height; then it drops `drop`
    f0, fh = int(math.floor(t0 * FPS)), int(round(t_hit * FPS))
    for f in range(f0, fh + 1):
        t = f / FPS
        if t <= t1:
            u = (t - t0) / max(1e-6, t1 - t0)
            M = pose(tip * u * u, 0.0, 0.0)
        else:
            u = (t - t1) / max(1e-6, t_hit - t1)
            M = pose(tip + (math.pi / 2 - tip) * min(1.0, u * 1.2), drop * u * u, slide * u)
        obj.matrix_basis = M
        obj.keyframe_insert('location', frame=f)
        obj.keyframe_insert('rotation_euler', frame=f)
    obj.matrix_basis = base
    for fc in kit.fcurves(obj):
        if fc.data_path in ('location', 'rotation_euler'):
            for kp in fc.keyframe_points:
                kp.interpolation = 'LINEAR'
    land = pose(math.pi / 2, drop, slide)
    lc = [land @ Vector(c) for c in obj.bound_box]
    return Vector((sum(c.x for c in lc) / 8, sum(c.y for c in lc) / 8, floor))


def _pose_at(obj, frame: float):
    """(location, rotation_euler) of obj at frame from its own F-curves (current values where not animated)."""
    loc, rot = obj.location.copy(), obj.rotation_euler.copy()
    for fc in kit.fcurves(obj):
        if fc.data_path == 'location':
            loc[fc.array_index] = fc.evaluate(frame)
        elif fc.data_path == 'rotation_euler':
            rot[fc.array_index] = fc.evaluate(frame)
    return loc, rot


def shatter(pieces, t: float, *, impact=None, speed=(20.0, 80.0), spin: float = 10.0, follow=None,
            falloff: float = 0.0, direction=None, mass_density: float = 0.0025, friction: float = 0.5,
            bounce: float = 0.15, seed: int = 4, shape: str = 'CONVEX_HULL', margin: float = 0.01):
    """Break at song time t: the pieces are held (kinematic) until t, then fly apart as rigid bodies.

    impact: world point the pieces fly away from (None: no outward push; they just come apart and fall).
    speed: (min, max) cm/s outward; falloff > 0 slows pieces farther from the impact (1/cm, exponential).
    direction: an extra common velocity (cm/s). follow: an animated object the pieces ride on until t (they copy
    its keyed motion frame by frame, then keep its velocity: a toppling model that breaks on a beat).
    Masses scale with piece volume (mass_density per cm^3; glass ~0.0025). Adds the pieces to the rigid-body
    world; bake with rigid.bake() / fx.bake() after."""
    from . import rigid
    rbw = rigid.world()
    rng = random.Random(seed)
    sc = bpy.context.scene
    F = int(math.floor(t * FPS + 1e-6))
    f_start = rbw.point_cache.frame_start
    mats = {}
    if follow is not None:
        rbw.enabled = False                      # sample the keyed motion without stepping the simulation
        for f in range(f_start, F + 1):
            sc.frame_set(f)
            mats[f] = follow.matrix_world.copy()
        sc.frame_set(sc.frame_start)
        rbw.enabled = True
        base = follow.matrix_world.copy()
    imp = Vector(impact) if impact is not None else None
    extra = Vector(direction) if direction is not None else Vector()
    for p in pieces:
        bm = bmesh.new()
        bm.from_mesh(p.data)
        vol = abs(bm.calc_volume())
        bm.free()
        rigid.active(p, mass=max(1e-4, vol * mass_density), shape=shape, friction=friction, bounce=bounce,
                     margin=margin)
        c = p.matrix_basis.translation.copy()
        v = extra.copy()
        if imp is not None:
            d = c - imp
            dist = d.length
            d = d.normalized() if dist > 1e-6 else Vector((0, 0, 1))
            k = math.exp(-falloff * dist) if falloff > 0 else 1.0
            v += d * rng.uniform(*speed) * k
        w = Vector((rng.gauss(0, spin), rng.gauss(0, spin), rng.gauss(0, spin)))
        if follow is not None:
            local = base.inverted() @ p.matrix_basis
            for f in range(f_start, F):
                p.matrix_world = mats[f] @ local
                p.keyframe_insert('location', frame=f)
                p.keyframe_insert('rotation_euler', frame=f)
            p.matrix_world = mats[F] @ local
            p1, r1 = p.location.copy(), p.rotation_euler.copy()
        else:
            p0, r0 = _pose_at(p, F - 1)
            p.location, p.rotation_euler = p0, r0
            p.keyframe_insert('location', frame=F - 1)
            p.keyframe_insert('rotation_euler', frame=F - 1)
            p1, r1 = p0, r0
        # the break: over the step into frame F the piece picks up v and spin w (kinematic), then it is free
        p.location = p1 + v / FPS
        p.rotation_euler = (r1[0] + w.x / FPS, r1[1] + w.y / FPS, r1[2] + w.z / FPS)
        p.keyframe_insert('location', frame=F)
        p.keyframe_insert('rotation_euler', frame=F)
        for fc in kit.fcurves(p):
            if fc.data_path in ('location', 'rotation_euler'):
                for kp in fc.keyframe_points:
                    if kp.co.x >= F - 1 - 1e-4 or follow is not None:
                        kp.interpolation = 'LINEAR'
        rigid.release(p, F / FPS)
    log(f'shatter: {len(pieces)} pieces at t={t:.3f} (frame {F})')
