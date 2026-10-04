"""singularity: "I feel my atoms rearranging". The researcher's right hand and sleeve break into tiny cubes.

At T_VOX the smooth hand and right sleeve are swapped for their voxels (wood cubes from the hand, white coat cubes
from the sleeve, measured from the posed, deformed meshes at the hold pose). The cubes peel off from the fingertips
up to the shoulder, stream out toward the hole spiralling round the pull axis, glowing, then come back in the other
order and land SHUFFLED (every atom in another atom's cell: a white hand speckled with wood, a sleeve speckled with
wood). At T_POP the smooth arm is back. A geometry-nodes point cloud evaluates it all from song time.

The library's fx.cubes.dissolve does one static object with one material and a vertical swirl; this needs a
deformed sleeve plus a rigid hand, two materials mixed by the shuffle, and a stream toward a point, so it's local.
The arm must hold still between T_VOX and T_POP (key the head with T['head'], not look(): look() twists the spine).
"""
from __future__ import annotations

import math

import bmesh
import bpy
import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree

from pdoom import fx, kit
from pdoom import timing as tm
from pdoom.fx import _nodes as N

from scenes.singularity_hole import ShTree, new_material

FPS = tm.FPS


def _components(bm):
    """Split a bmesh's faces into connected components -> list of face lists."""
    seen = set()
    comps = []
    for f in bm.faces:
        if f.index in seen:
            continue
        stack = [f]
        comp = []
        seen.add(f.index)
        while stack:
            g = stack.pop()
            comp.append(g)
            for e in g.edges:
                for h in e.link_faces:
                    if h.index not in seen:
                        seen.add(h.index)
                        stack.append(h)
        comps.append(comp)
    return comps


def _bvh_parts(verts_world, faces):
    """BVH trees of the closed parts of a triangle soup (world coords)."""
    bm = bmesh.new()
    vs = [bm.verts.new(v) for v in verts_world]
    for f in faces:
        try:
            bm.faces.new([vs[i] for i in f])
        except ValueError:
            pass
    bm.verts.index_update()
    bm.faces.ensure_lookup_table()
    bm.faces.index_update()
    out = []
    for comp in _components(bm):
        tris = []
        pts = []
        idx = {}
        for f in comp:
            ids = []
            for v in f.verts:
                if v.index not in idx:
                    idx[v.index] = len(pts)
                    pts.append(v.co.copy())
                ids.append(idx[v.index])
            for k in range(1, len(ids) - 1):
                tris.append((ids[0], ids[k], ids[k + 1]))
        lo = Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts)))
        hi = Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)))
        out.append((BVHTree.FromPolygons(pts, tris), lo, hi))
    bm.free()
    return out


def _inside(parts, p):
    d = Vector((0.5774, 0.5832, 0.5714)).normalized()
    for bvh, lo, hi in parts:
        if not (lo.x <= p.x <= hi.x and lo.y <= p.y <= hi.y and lo.z <= p.z <= hi.z):
            continue
        hits, q = 0, p.copy()
        for _ in range(40):
            loc, nrm, i, dist = bvh.ray_cast(q, d)
            if loc is None:
                break
            hits += 1
            q = loc + d * 1e-4
        if hits % 2 == 1:
            return True
    return False


def _voxelize(parts, cube):
    lo = Vector((min(p[1].x for p in parts), min(p[1].y for p in parts), min(p[1].z for p in parts)))
    hi = Vector((max(p[2].x for p in parts), max(p[2].y for p in parts), max(p[2].z for p in parts)))
    n = [max(1, int(math.ceil((hi[i] - lo[i]) / cube))) for i in range(3)]
    out = []
    for i in range(n[0]):
        for j in range(n[1]):
            for k in range(n[2]):
                p = lo + Vector(((i + 0.5) * cube, (j + 0.5) * cube, (k + 0.5) * cube))
                if _inside(parts, p):
                    out.append(tuple(p))
    return out


def arm_meshes(r, t_hold):
    """World triangles of the researcher's posed right hand and right sleeve at song time t_hold (after bake)."""
    sc = bpy.context.scene
    f = int(round(t_hold * FPS))
    sc.frame_set(f)
    dg = bpy.context.evaluated_depsgraph_get()
    hand = bpy.data.objects[f'{r.name}.hand.R']
    sl = r.o_sleeves
    res = {}
    for key, ob in (('hand', hand), ('sleeve', sl)):
        oe = ob.evaluated_get(dg)
        me = oe.to_mesh()
        mw = oe.matrix_world.copy()
        verts = [mw @ v.co for v in me.vertices]
        faces = [tuple(p.vertices) for p in me.polygons]
        oe.to_mesh_clear()
        if key == 'sleeve':
            # the right sleeve: vertices weighted to the right arm's bones (same indices as the original mesh)
            g = {vg.name: vg.index for vg in ob.vertex_groups}
            gi = {g.get('upper_arm.R'), g.get('forearm.R')}
            right = set()
            for v in ob.data.vertices:
                w = sum(e.weight for e in v.groups if e.group in gi)
                if w > 0.5:
                    right.add(v.index)
            faces = [fc for fc in faces if all(i in right for i in fc)]
        res[key] = (verts, faces)
    return res


def cube_material(name, color, *, rough=0.5, coat=0.0, glow='#FFB060'):
    m, nt, out = new_material(name)
    g = ShTree(nt)
    b = g.node('ShaderNodeBsdfPrincipled')
    b.inputs['Base Color'].default_value = kit.srgb(color)
    b.inputs['Roughness'].default_value = rough
    if coat:
        b.inputs['Coat Weight'].default_value = coat
    b.inputs['Emission Color'].default_value = kit.srgb(glow)
    gl = g.attribute('glow')
    g.feed(b.inputs['Emission Strength'], gl * gl * 2.6)
    nt.links.new(b.outputs[0], out.inputs['Surface'])
    m.diffuse_color = kit.srgb(color)
    return m


def dissolve(r, *, pull, t_hold, t_vox, t_out=(50.48, 51.12), t_in=(51.38, 52.1), t_pop=52.34, cube=0.1,
             seed=3, coll=None, reach=(1.5, 6.5)):
    """Build the cube cloud for the researcher's right arm. Returns (object, count)."""
    coll = coll or kit.collection('atoms')
    mesh = arm_meshes(r, t_hold)
    parts_h = _bvh_parts(*mesh['hand'])
    parts_s = _bvh_parts(*mesh['sleeve'])
    ph = _voxelize(parts_h, cube)
    ps = _voxelize(parts_s, cube)
    ps = [p for p in ps if not _inside(parts_h, Vector(p))]
    P = np.array(ph + ps, dtype=np.float64).reshape(-1, 3)
    kind = np.array([0] * len(ph) + [1] * len(ps), dtype=np.float32)
    n = len(P)
    fx.log(f'atoms: {len(ph)} hand + {len(ps)} sleeve cubes of {cube} cm')
    rng = np.random.default_rng(seed)
    # arm coordinate: 0 at the shoulder end, 1 at the fingertips
    hc = P[:len(ph)].mean(axis=0) if len(ph) else P.mean(axis=0)
    # the shoulder end = the sleeve point farthest from the hand's centre
    sh = P[len(ph):][np.argmax(np.linalg.norm(P[len(ph):] - hc, axis=1))] if len(ps) else P.mean(axis=0)
    dist = np.linalg.norm(P - sh, axis=1)
    f = dist / max(1e-6, dist.max())
    perm = rng.permutation(n)
    Q = P[perm]
    fq = f[perm]
    t0 = t_out[0] + (t_out[1] - t_out[0]) * (1 - f) ** 1.1 + rng.uniform(0, 0.06, n)
    t1 = t_in[0] + (t_in[1] - t_in[0]) * fq ** 0.9 + rng.uniform(0, 0.06, n)
    t1 = np.maximum(t1, t0 + 0.35)
    # the pull axis (unit): the stream flows along it, spiralling round it
    A = np.array(tuple(pull), dtype=np.float64)
    A /= np.linalg.norm(A)
    rnd = rng.normal(0, 1, (n, 3))
    o = rnd - (rnd @ A)[:, None] * A[None]
    o /= np.maximum(np.linalg.norm(o, axis=1, keepdims=True), 1e-6)
    rch = reach[0] + (reach[1] - reach[0]) * rng.power(1.6, n) * (0.55 + 0.45 * f)
    rad = rng.uniform(0.3, 1.0, n) * (0.4 + 0.25 * rch)
    turns = rng.uniform(0.8, 2.0, n)
    ax = rng.normal(0, 1, (n, 3))
    ax /= np.linalg.norm(ax, axis=1, keepdims=True)
    spin = rng.uniform(1.0, 3.0, n)
    ph0 = rng.uniform(0, 2 * math.pi, n)
    attrs = {'p1': Q, 'o': o, 'ax': ax, 'kind': kind, 't0': t0, 't1': t1, 'rch': rch, 'rad': rad, 'turns': turns,
             'spin': spin, 'ph0': ph0}
    me = bpy.data.meshes.new('atoms')
    me.vertices.add(n)
    me.vertices.foreach_set('co', P.astype(np.float32).ravel())
    for nm, arr in attrs.items():
        arr = np.asarray(arr, dtype=np.float32)
        vec = arr.ndim == 2
        a = me.attributes.new(nm, 'FLOAT_VECTOR' if vec else 'FLOAT', 'POINT')
        a.data.foreach_set('vector' if vec else 'value', arr.ravel())
    me.update()
    ob = bpy.data.objects.new('atoms', me)
    coll.objects.link(ob)
    # prototypes: a bevelled unit cube in wood and in coat white
    pc = kit.collection('atoms.protos', coll)
    for i, (nm, col, rough, coat) in enumerate((('wood', '#D8A870', 0.42, 0.35), ('coat', '#EEEBE3', 0.65, 0.0))):
        bm = bmesh.new()
        bmesh.ops.create_cube(bm, size=1.0)
        bmesh.ops.bevel(bm, geom=list(bm.edges), offset=0.1, segments=2, affect='EDGES')
        pm = bpy.data.meshes.new(f'atom.p{i}.{nm}')
        bm.to_mesh(pm)
        bm.free()
        pm.materials.append(cube_material(f'atom.{nm}', col, rough=rough, coat=coat))
        po = bpy.data.objects.new(f'atom.p{i}.{nm}', pm)
        pc.objects.link(po)
        po.location = (0, 0, -10000)
    pc.hide_render = True
    tree = _tree('atoms.gn', pc, A, cube, t_vox, t_pop)
    N.modifier(ob, tree, 'atoms')
    fx.vis(ob, t_vox - 0.5 / FPS, t_pop - 0.5 / FPS)
    # the originals: the hand hides, the right sleeve is deleted by a node modifier, for the same span
    hand = bpy.data.objects[f'{r.name}.hand.R']
    fx.vis(hand, None, t_vox - 0.5 / FPS)
    hand.hide_render = False
    hand.keyframe_insert('hide_render', frame=(t_pop - 0.5 / FPS) * FPS)
    for fc in kit.fcurves(hand):
        if fc.data_path == 'hide_render':
            for kp in fc.keyframe_points:
                kp.interpolation = 'CONSTANT'
    hide_right_sleeve(r, t_vox - 0.5 / FPS, t_pop - 0.5 / FPS)
    return ob, n


def _tree(name, protos, A, cube, t_vox, t_pop):
    g = N.Tree(name)
    geo_in = g.input_geometry()
    T = g.time()

    def at(nm, kind='FLOAT'):
        return g.out(g.node('GeometryNodeInputNamedAttribute', data_type=kind, inputs={'Name': nm}), 'Attribute')
    t0, t1 = at('t0'), at('t1')
    u = g.clamp((T - t0) / (t1 - t0))
    e = g.smooth(u, 0.0, 1.0)
    b = g.op('POWER', g.sin(u * math.pi), 0.45)                    # out fast, hover, back fast
    p0 = g.position()
    p1 = at('p1', 'FLOAT_VECTOR')
    base = p0 + (p1 - p0) * e
    Av = tuple(float(x) for x in A)
    ang = at('ph0') + at('turns') * u * 6.2832
    rot = g.node('ShaderNodeVectorRotate', rotation_type='AXIS_ANGLE',
                 inputs={'Vector': at('o', 'FLOAT_VECTOR'), 'Axis': Av, 'Angle': ang})
    swirl = g.out(rot, 'Vector')
    exc = g.vec(*Av) * (at('rch') * b) + swirl * (at('rad') * b)
    pos = base + exc
    pts = g.set_position(geo_in, position=pos)
    fl = g.exp(-g.max(T - t_vox, 0.0) / 0.09) + g.exp(-g.max(T - (t_pop - 0.12), 0.0) / 0.06) * (T > (t_pop - 0.13))
    glow = g.clamp(b * 0.9 + fl * 0.8)
    pts = g.store(pts, 'glow', glow)
    tumble = g.axis_angle(at('ax', 'FLOAT_VECTOR'), b * at('spin') * 6.2832)
    k = cube * 0.9
    src = g.collection_geo(protos, separate=True, reset=True)
    inst = g.instance(pts, src, rotation=tumble, scale=g.vec(k, k, k), pick=True, instance_index=at('kind'))
    g.output(inst)
    return g


def hide_right_sleeve(r, t_off, t_on):
    """A node modifier after the armature deletes the right sleeve (its bones' weights) while Hide = 1."""
    ob = r.o_sleeves
    g = N.Tree('atoms.sleevehide')
    geo_in = g.input_geometry()
    hide = g.param('Hide', 'FLOAT', 0.0)

    def at(nm):
        return g.out(g.node('GeometryNodeInputNamedAttribute', data_type='FLOAT', inputs={'Name': nm}), 'Attribute')
    w = at('upper_arm.R') + at('forearm.R')
    sel = g.bool_and(w > 0.5, hide > 0.5)
    g.output(g.delete(geo_in, sel, domain='POINT'))
    mod = N.modifier(ob, g, 'atoms.hide')
    sc = bpy.context.scene
    N.key_input(ob, mod, 'Hide', sc.frame_start / FPS - 1, 0.0, interp='CONSTANT')
    N.key_input(ob, mod, 'Hide', t_off, 1.0, interp='CONSTANT')
    N.key_input(ob, mod, 'Hide', t_on, 0.0, interp='CONSTANT')
    return mod
