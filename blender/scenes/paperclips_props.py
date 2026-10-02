"""paperclips: the scene's own props (not library code).

- collar(c): a red leather cat collar with a gold bell and a D-ring, riding Clawd's body bone.
- leash(): a sagging red cord between two Empties (geometry nodes: a parabola whose sag follows the slack), so it
  follows both puppets exactly on every frame without keys.
- The kill switch guy's empty vacation spot: a striped deck chair, a beach umbrella on a weighted base, sunglasses,
  a cocktail with a paper umbrella and a pair of flip-flops.
- tip(): keys a prop tipping over an edge (gravity-like, a small bounce) so knocked-over props hit their words.
"""
from __future__ import annotations

import math

import bmesh
import bpy
from mathutils import Matrix, Vector

from pdoom import kit
from pdoom.fx import _nodes as N
from pdoom.sets import geo
from pdoom.sets import materials as M
from pdoom.timing import FPS

V = Vector


# ------------------------------------------------------------------------------------------------ small builders


def rod(name, p0, p1, r, m, coll, verts=12):
    """A cylinder from p0 to p1 (world or parent-local cm)."""
    p0, p1 = V(p0), V(p1)
    d = p1 - p0
    o = kit.cylinder(name, r, d.length, (0, 0, 0), verts=verts, m=m, coll=coll)
    o.matrix_world = Matrix.Translation((p0 + p1) / 2) @ d.to_track_quat('Z', 'Y').to_matrix().to_4x4()
    return o


def _apply(o):
    """Bake the object's transform into its mesh (so joins keep placement)."""
    me = o.data
    me.transform(o.matrix_basis)
    o.matrix_basis = Matrix.Identity(4)
    return o


def _obj(name, bm, coll, mats, smooth=True):
    me = bpy.data.meshes.new(name)
    bm.normal_update()
    bm.to_mesh(me)
    bm.free()
    o = bpy.data.objects.new(name, me)
    coll.objects.link(o)
    for m in mats:
        me.materials.append(m)
    if smooth:
        for p in me.polygons:
            p.use_smooth = True
        kit.smooth(o, 40)
    return o


def _stripes(name, a, b, *, axis='X', freq=1.0, rough=0.55, sheen=0.4, angular=0):
    """Canvas with bold stripes: along an object axis (freq stripes per cm), or `angular` sectors around Z."""
    m, fresh = M.new_mat(name)
    if not fresh:
        return m
    nt = m.node_tree
    bs = M.principled(m)
    M.setin(bs, 'Roughness', rough)
    M.setin(bs, 'Sheen Weight', sheen)
    tc = M.node(nt, 'ShaderNodeTexCoord', (-900, 0))
    sep = M.node(nt, 'ShaderNodeSeparateXYZ', (-750, 0))
    M.link(nt, M.sout(tc, 'Object'), M.sin(sep, 'Vector'))
    if angular:
        at = M.node(nt, 'ShaderNodeMath', (-600, 0), operation='ARCTAN2')
        M.link(nt, M.sout(sep, 'Y'), at.inputs[0])
        M.link(nt, M.sout(sep, 'X'), at.inputs[1])
        mul = M.node(nt, 'ShaderNodeMath', (-450, 0), operation='MULTIPLY')
        M.link(nt, at.outputs[0], mul.inputs[0])
        mul.inputs[1].default_value = angular / (2 * math.pi)
        src = mul.outputs[0]
    else:
        mul = M.node(nt, 'ShaderNodeMath', (-450, 0), operation='MULTIPLY')
        M.link(nt, M.sout(sep, axis), mul.inputs[0])
        mul.inputs[1].default_value = freq
        src = mul.outputs[0]
    fr = M.node(nt, 'ShaderNodeMath', (-300, 0), operation='FRACT')
    M.link(nt, src, fr.inputs[0])
    gt = M.node(nt, 'ShaderNodeMath', (-150, 0), operation='GREATER_THAN')
    M.link(nt, fr.outputs[0], gt.inputs[0])
    gt.inputs[1].default_value = 0.5
    mx = M.node(nt, 'ShaderNodeMix', (0, 0), data_type='RGBA', blend_type='MIX')
    M.link(nt, gt.outputs[0], M.sin(mx, 'Factor', 'VALUE'))
    M.setin(mx, 'A', kit.srgb(a), 'RGBA')
    M.setin(mx, 'B', kit.srgb(b), 'RGBA')
    M.link(nt, M.sout(mx, 'Result', 'RGBA'), M.sin(bs, 'Base Color'))
    M.link(nt, M.micro_bump(nt, 30.0, 0.04, loc=(0, -400)), M.sin(bs, 'Normal'))
    m.diffuse_color = kit.srgb(a)
    return m


# ------------------------------------------------------------------------------------------------ Clawd's collar


def _rrect_ring(cx, cy, hw, hd, r, n=18):
    """Outline points of a rounded rectangle (half sizes hw, hd, corner radius r), counter-clockwise."""
    pts = []
    for k, (sx, sy, a0) in enumerate(((1, 1, 0), (-1, 1, 90), (-1, -1, 180), (1, -1, 270))):
        ccx, ccy = cx + sx * (hw - r), cy + sy * (hd - r)
        for i in range(n + 1):
            a = math.radians(a0 + 90 * i / n)
            pts.append((ccx + r * math.cos(a), ccy + r * math.sin(a)))
    return pts


def collar(c, coll):
    """A red leather collar round Clawd's lower body, a gold bell at the front and a D-ring beside it for the leash.
    Returns (collar object, ring point in Clawd's character space)."""
    from pdoom.chars.clawd import D as CD, R_BODY, W as CW
    from pdoom.chars.rig import bone_parent
    leather = M.solid('pc.collar', '#B0182A', rough=0.42, coat=0.35, coat_rough=0.2, sheen=0.2, micro=(18.0, 0.03))
    gold = M.solid('pc.bell', '#E3B44A', rough=0.14, metal=1.0)
    z0, z1, th = 2.02, 2.46, 0.11
    hw, hd, r = CW / 2 + 0.02, CD / 2 + 0.02, R_BODY + 0.02
    bm = bmesh.new()
    inner = _rrect_ring(0, 0, hw, hd, r)
    outer = _rrect_ring(0, 0, hw + th, hd + th, r + th)
    n = len(inner)
    rings = []
    for (pts, z) in ((inner, z0), (outer, z0), (outer, z1), (inner, z1)):
        rings.append([bm.verts.new((x, y, z)) for x, y in pts])
    for a in range(4):
        A, B = rings[a], rings[(a + 1) % 4]
        for i in range(n):
            j = (i + 1) % n
            bm.faces.new((A[i], A[j], B[j], B[i]))
    band = _obj('clawd.collar', bm, coll, [leather])
    # the bell: a sphere with a slit band, hanging from a small loop under the collar at the front
    bm = bmesh.new()
    bc = V((0.0, -hd - th - 0.3, z0 - 0.28))
    bmesh.ops.create_uvsphere(bm, u_segments=24, v_segments=14, radius=0.3,
                              matrix=Matrix.Translation(bc))
    bell = _obj('clawd.bell', bm, coll, [gold])
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=True, segments=16, radius1=0.035, radius2=0.035, depth=0.62,
                          matrix=Matrix.Translation(bc + V((0, 0, -0.02))) @ Matrix.Rotation(math.pi / 2, 4, 'X'))
    slit = _obj('clawd.bell.slit', bm, coll, [M.solid('pc.bell.slit', '#1A1208', rough=0.6)])
    loop = rod('clawd.bell.loop', bc + V((0, 0.02, 0.22)), bc + V((0, 0.04, 0.46)), 0.05, gold, coll, 8)
    _apply(loop)
    # D-ring on the front, off to his right, where the leash clips on
    ring_c = V((-1.25, -hd - th - 0.12, (z0 + z1) / 2))
    ring = rod('clawd.dring', ring_c + V((-0.22, 0, 0)), ring_c + V((0.22, 0, 0)), 0.045, gold, coll, 8)
    _apply(ring)
    ob = geo.join([band, bell, slit, loop, ring], 'clawd.collar')
    ob.matrix_world = c.rig.matrix_world
    bone_parent(ob, c.rig, 'body')
    return ob, ring_c + V((0, -0.12, -0.05))


# ------------------------------------------------------------------------------------------------ the leash


def leash(name, a, b, coll, *, length=9.0, radius=0.055, color='#C8242E'):
    """A braided cord from Empty a to Empty b that sags by its slack: sag = sqrt(3 d (L - d) / 8) (a parabola of arc
    length L over span d). Pure function of the two Empties' world positions (geometry nodes)."""
    m = M.solid(f'{name}.mat', color, rough=0.5, sheen=0.5, micro=(40.0, 0.02))
    me = bpy.data.meshes.new(name)
    ob = bpy.data.objects.new(name, me)
    coll.objects.link(ob)
    g = N.Tree(f'{name}.gn')
    g.input_geometry()
    ia = g.node('GeometryNodeObjectInfo', transform_space='ORIGINAL', inputs={'Object': a})
    ib = g.node('GeometryNodeObjectInfo', transform_space='ORIGINAL', inputs={'Object': b})
    pa, pb = g.out(ia, 'Location'), g.out(ib, 'Location')
    line = g.node('GeometryNodeCurvePrimitiveLine', mode='POINTS', inputs={'Start': pa, 'End': pb})
    res = g.node('GeometryNodeResampleCurve', inputs={'Curve': g.out(line), 'Count': 28})
    cur = g.out(res)
    u = g.out(g.node('GeometryNodeSplineParameter'), 'Factor')
    d = g.length(pb - pa)
    slack = g.max(length - d, 0.0)
    sag = g.sqrt(g.max(d * slack * 0.375, 0.0))
    dz = sag * u * (1.0 - u) * -4.0
    cur = g.set_position(cur, offset=g.vec(0.0, 0.0, dz))
    prof = g.node('GeometryNodeCurvePrimitiveCircle', mode='RADIUS', inputs={'Resolution': 8, 'Radius': radius})
    c2m = g.node('GeometryNodeCurveToMesh', inputs={'Curve': cur, 'Profile Curve': g.out(prof), 'Fill Caps': True})
    mesh = g.out(c2m)
    mesh = g.out(g.node('GeometryNodeSetShadeSmooth', inputs={'Geometry': mesh}))
    mesh = g.set_material(mesh, m)
    g.output(mesh)
    N.modifier(ob, g, 'leash')
    return ob


# ------------------------------------------------------------------------------------------------ vacation spot


def beach_chair(coll, name='pc.chair'):
    """A low striped deck chair for a 12 cm peg doll, facing local -Y, origin on the ground at its centre."""
    wood = M.solid('pc.chair.wood', '#C9A171', rough=0.55, coat=0.3, micro=(10.0, 0.05))
    canvas = _stripes('pc.chair.canvas', '#E7412F', '#F4EEDF', axis='X', freq=1.35)
    parts = []
    W2 = 2.25
    for s in (-1, 1):
        x = s * W2
        parts.append(rod(f'{name}.rail{s}', (x, -2.6, 1.35), (x, 0.9, 0.85), 0.14, wood, coll))
        parts.append(rod(f'{name}.back{s}', (x, 0.9, 0.85), (x, 3.3, 6.3), 0.14, wood, coll))
        parts.append(rod(f'{name}.legf{s}', (x, -2.3, 0.0), (x, -2.3, 1.35), 0.13, wood, coll))
        parts.append(rod(f'{name}.legb{s}', (x, 1.9, 0.0), (x, 1.1, 1.2), 0.13, wood, coll))
        parts.append(rod(f'{name}.arm{s}', (x * 1.02, -1.6, 2.7), (x * 1.02, 1.6, 3.2), 0.12, wood, coll))
        parts.append(rod(f'{name}.armpost{s}', (x * 1.02, -1.5, 1.3), (x * 1.02, -1.5, 2.7), 0.11, wood, coll))
    parts.append(rod(f'{name}.bar0', (-W2, -2.6, 1.35), (W2, -2.6, 1.35), 0.13, wood, coll))
    parts.append(rod(f'{name}.bar1', (-W2, 3.3, 6.3), (W2, 3.3, 6.3), 0.13, wood, coll))
    parts.append(rod(f'{name}.bar2', (-W2, 1.6, 0.35), (W2, 1.6, 0.35), 0.11, wood, coll))
    for o in parts:
        _apply(o)
    # the sling: from the front bar, sagging into the seat, up the back
    path = [(-2.6, 1.3), (-1.6, 0.85), (-0.5, 0.62), (0.6, 0.72), (1.3, 1.5), (2.1, 3.3), (2.8, 5.0), (3.25, 6.25)]
    bm = bmesh.new()
    nx = 14
    rows = []
    for (y, z) in path:
        rows.append([bm.verts.new((-W2 + 0.12 + (2 * W2 - 0.24) * i / nx, y, z)) for i in range(nx + 1)])
    for j in range(len(rows) - 1):
        for i in range(nx):
            bm.faces.new((rows[j][i], rows[j][i + 1], rows[j + 1][i + 1], rows[j + 1][i]))
    sling = _obj(f'{name}.sling', bm, coll, [canvas])
    sol = sling.modifiers.new('thick', 'SOLIDIFY')
    sol.thickness = 0.06
    geo.apply_mods(sling)
    ob = geo.join(parts + [sling], name)
    return ob


def sunglasses(coll, name='pc.shades'):
    frame = M.plastic('pc.shades.frame', '#15120F', rough=0.25, coat=0.6)
    lens = M.solid('pc.shades.lens', '#1B2A30', rough=0.04, coat=1.0, coat_rough=0.02, metal=0.4)
    parts = []
    for s in (-1, 1):
        bm = bmesh.new()
        bmesh.ops.create_cone(bm, cap_ends=True, segments=20, radius1=0.42, radius2=0.42, depth=0.06,
                              matrix=Matrix.Translation((s * 0.52, 0, 0)) @ Matrix.Rotation(math.pi / 2, 4, 'X'))
        o = _obj(f'{name}.lens{s}', bm, coll, [lens])
        parts.append(o)
        bm = bmesh.new()
        bmesh.ops.create_cone(bm, cap_ends=True, segments=20, radius1=0.48, radius2=0.48, depth=0.05,
                              matrix=Matrix.Translation((s * 0.52, 0.035, 0)) @ Matrix.Rotation(math.pi / 2, 4, 'X'))
        parts.append(_obj(f'{name}.rim{s}', bm, coll, [frame]))
        arm = rod(f'{name}.arm{s}', (s * 0.98, 0.05, 0.1), (s * 1.0, 1.9, 0.05), 0.045, frame, coll, 6)
        parts.append(_apply(arm))
    parts.append(_apply(rod(f'{name}.bridge', (-0.12, 0.02, 0.18), (0.12, 0.02, 0.18), 0.05, frame, coll, 6)))
    return geo.join(parts, name)


def umbrella(coll, name='pc.umbrella', h=12.5, r=6.2):
    """A beach umbrella on a weighted base, origin at the base's centre on the ground, pole along +Z."""
    pole_m = M.solid('pc.umb.pole', '#EDE7DA', rough=0.35, coat=0.4)
    base_m = M.plastic('pc.umb.base', '#2A5C88', rough=0.4, coat=0.3)
    cloth = _stripes('pc.umb.cloth', '#F2C230', '#E24E3A', angular=8, rough=0.6, sheen=0.3)
    parts = [geo.lathe(f'{name}.base', geo.rounded_profile([(0.0, 0.0), (1.35, 0.0), (1.35, 0.35), (0.5, 0.6),
                                                             (0.0, 0.6)], 0.12), segs=32, coll=coll, m=base_m)]
    parts.append(_apply(rod(f'{name}.pole', (0, 0, 0.3), (0, 0, h + 0.3), 0.12, pole_m, coll)))
    # canopy: 8 panels, scalloped rim
    bm = bmesh.new()
    seg, rings = 64, 8
    apex = bm.verts.new((0, 0, h + 0.05))
    rows = []
    for k in range(1, rings + 1):
        rr = r * k / rings
        row = []
        for j in range(seg):
            a = 2 * math.pi * j / seg
            sc = 1.0 - 0.06 * (k / rings) ** 3 * (1 - math.cos(8 * a)) * 0.5
            z = h + 0.05 - 1.9 * (k / rings) ** 1.3 + 0.12 * math.sin(math.pi * k / rings)
            row.append(bm.verts.new((rr * sc * math.cos(a), rr * sc * math.sin(a), z)))
        rows.append(row)
    for j in range(seg):
        bm.faces.new((apex, rows[0][j], rows[0][(j + 1) % seg]))
    for k in range(rings - 1):
        for j in range(seg):
            j2 = (j + 1) % seg
            bm.faces.new((rows[k][j], rows[k + 1][j], rows[k + 1][j2], rows[k][j2]))
    can = _obj(f'{name}.canopy', bm, coll, [cloth])
    sol = can.modifiers.new('thick', 'SOLIDIFY')
    sol.thickness = 0.05
    geo.apply_mods(can)
    parts.append(can)
    fin = kit.sphere(f'{name}.finial', 0.28, (0, 0, h + 0.3), m=pole_m, coll=coll, subdiv=2)
    parts.append(_apply(fin))
    for j in range(8):
        a = 2 * math.pi * (j + 0.5) / 8
        p1 = V((r * 0.62 * math.cos(a), r * 0.62 * math.sin(a), h - 0.9))
        parts.append(_apply(rod(f'{name}.rib{j}', (0, 0, h - 2.6), p1, 0.04, pole_m, coll, 5)))
    return geo.join(parts, name)


def cocktail(coll, name='pc.drink'):
    """A tiny tumbler of orange juice with a striped straw, a lemon slice and a paper cocktail umbrella."""
    glass = M.glass('pc.drink.glass', tint='#F4FBFF', rough=0.03)
    juice = M.solid('pc.drink.juice', '#F28A1E', rough=0.1, sss=0.6, sss_radius=(1.0, 0.5, 0.2))
    straw = _stripes('pc.drink.straw', '#F4EEDF', '#D83A56', axis='Z', freq=2.5, rough=0.3, sheen=0.0)
    lemon = M.solid('pc.drink.lemon', '#F5D44A', rough=0.4, sss=0.4)
    paper = _stripes('pc.drink.paper', '#2EA7C8', '#F4EEDF', angular=6, rough=0.6, sheen=0.1)
    parts = [geo.lathe(f'{name}.glass', [(0.0, 0.0), (0.62, 0.0), (0.66, 0.1), (0.72, 1.9), (0.66, 1.9), (0.6, 0.18),
                                          (0.0, 0.18)], segs=32, coll=coll, m=glass)]
    parts.append(geo.lathe(f'{name}.juice', [(0.0, 0.2), (0.6, 0.2), (0.665, 1.55), (0.0, 1.55)], segs=32, coll=coll,
                           m=juice))
    parts.append(_apply(rod(f'{name}.straw', (0.2, 0.1, 0.3), (0.55, 0.3, 2.9), 0.06, straw, coll, 8)))
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=True, segments=24, radius1=0.42, radius2=0.42, depth=0.1,
                          matrix=Matrix.Translation((-0.62, 0.0, 1.8)) @ Matrix.Rotation(math.pi / 2, 4, 'Y'))
    parts.append(_obj(f'{name}.lemon', bm, coll, [lemon]))
    parts.append(_apply(rod(f'{name}.pick', (-0.2, -0.2, 0.6), (-0.5, -0.55, 3.4), 0.025, M.solid(
        'pc.drink.pick', '#D9B48A', rough=0.6), coll, 5)))
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=False, segments=24, radius1=0.75, radius2=0.02, depth=0.35,
                          matrix=Matrix.Translation((-0.5, -0.55, 3.35)))
    parts.append(_obj(f'{name}.parasol', bm, coll, [paper]))
    return geo.join(parts, name)


def flipflops(coll, name='pc.flipflops'):
    sole = M.solid('pc.ff.sole', '#34B3A0', rough=0.6, micro=(12.0, 0.03))
    strap = M.solid('pc.ff.strap', '#F4EEDF', rough=0.5)
    parts = []
    for s, (dx, dy, yaw) in enumerate(((-0.75, 0.0, 8.0), (0.8, 0.35, -14.0))):
        bm = bmesh.new()
        pts = []
        for i in range(24):
            a = 2 * math.pi * i / 24
            w = 0.42 + 0.08 * math.cos(a)
            pts.append((w * math.cos(a) * 0.95, 1.15 * math.sin(a)))
        Rz = Matrix.Rotation(math.radians(yaw), 4, 'Z')
        vs = [bm.verts.new(Rz @ V((x, y, 0.0)) + V((dx, dy, 0))) for x, y in pts]
        f = bm.faces.new(vs)
        ext = bmesh.ops.extrude_face_region(bm, geom=[f])
        top = [e for e in ext['geom'] if isinstance(e, bmesh.types.BMVert)]
        bmesh.ops.translate(bm, verts=top, vec=(0, 0, 0.14))
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
        parts.append(_obj(f'{name}.sole{s}', bm, coll, [sole], smooth=False))
        toe = Rz @ V((0.0, -0.55, 0.14)) + V((dx, dy, 0))
        for sx in (-1, 1):
            side = Rz @ V((sx * 0.4, 0.15, 0.14)) + V((dx, dy, 0))
            parts.append(_apply(rod(f'{name}.strap{s}{sx}', toe, side + V((0, 0, 0.12)), 0.04, strap, coll, 6)))
    return geo.join(parts, name)


# ------------------------------------------------------------------------------------------------ knocked over


def tip(obj, t0, t_land, *, direction, pivot=None, angle=90.0, bounce=6.0, slide=0.0, drop=0.0, lift=None):
    """Key obj (no parent) tipping over the horizontal edge through `pivot` toward `direction` from song time t0,
    accelerating like a falling body, landing at t_land after turning `angle` degrees (+ a small bounce), sliding
    `slide` cm along direction and dropping `drop` cm while it falls. Keys every frame (LINEAR). Returns the final
    world matrix."""
    d = V(direction)
    d.z = 0.0
    d.normalize()
    axis = V((0, 0, 1)).cross(d).normalized()
    base = obj.matrix_basis.copy()
    if pivot is None:
        pivot = base.translation
    pivot = V(pivot)
    A = math.radians(angle)

    def pose(a, s, dz):
        R = Matrix.Rotation(a, 4, axis)
        return Matrix.Translation(d * s + V((0, 0, -dz))) @ Matrix.Translation(pivot) @ R @ \
            Matrix.Translation(-pivot) @ base

    f0, f1 = int(math.floor(t0 * FPS)), int(math.ceil(t_land * FPS))
    fb = f1 + int(0.35 * FPS)
    obj.rotation_mode = 'QUATERNION'
    prev = None
    for f in range(f0 - 1, fb + 1):
        t = f / FPS
        if t <= t0:
            Mx = base
        elif t <= t_land:
            u = (t - t0) / (t_land - t0)
            Mx = pose(A * u * u, slide * u, drop * u * u)
        else:
            x = t - t_land
            b = math.radians(bounce) * math.exp(-x * 12.0) * abs(math.sin(x * math.pi / 0.16))
            Mx = pose(A - b, slide, drop)
        loc, q, _ = Mx.decompose()
        if prev is not None and prev.dot(q) < 0:
            q.negate()
        prev = q
        obj.location = loc
        obj.rotation_quaternion = q
        obj.keyframe_insert('location', frame=f)
        obj.keyframe_insert('rotation_quaternion', frame=f)
    final = pose(A, slide, drop)
    loc, q, _ = base.decompose()
    obj.location = loc
    obj.rotation_quaternion = q
    for fc in kit.fcurves(obj):
        if fc.data_path in ('location', 'rotation_quaternion'):
            for kp in fc.keyframe_points:
                kp.interpolation = 'LINEAR'
    return final


# ------------------------------------------------------------------------------------------------ the cat's bowl

BOWL_R = 3.0          # outer radius of the bowl's straight wall (the GATO label sits on it)


def cat_bowl(coll, loc, yaw_deg, name='pc.bowl'):
    """A cream ceramic cat bowl with a blue rim and a few biscuits in it; origin at its bottom centre, local -Y
    toward the camera side (yaw_deg as a character yaw)."""
    cream = M.solid('pc.bowl.glaze', '#F1EADB', rough=0.18, coat=0.6, coat_rough=0.05)
    blue = M.solid('pc.bowl.rim', '#2C5AC8', rough=0.2, coat=0.6, coat_rough=0.05)
    R, H = BOWL_R, 1.7
    prof = [(0.0, 0.0), (R - 0.35, 0.0), (R - 0.05, 0.12), (R, 0.4), (R, H - 0.25), (R - 0.08, H),
            (R - 0.42, H - 0.05), (R - 0.5, 0.6), (0.0, 0.55)]
    idx = [0, 0, 0, 0, 1, 1, 0, 0]
    o = geo.lathe(name, prof, segs=64, coll=coll, mats=[cream, blue], mat_idx=idx, smooth_angle=45)
    brown = M.solid('pc.kibble', '#8A5A2E', rough=0.7)
    import random
    rng = random.Random(7)
    for k in range(9):
        a = rng.uniform(0, 2 * math.pi)
        rr = rng.uniform(0.0, R - 1.1)
        kb = kit.sphere(f'{name}.kibble{k}', 0.32, (rr * math.cos(a), rr * math.sin(a), 0.78 + rng.uniform(0, 0.12)),
                        m=brown, coll=coll, subdiv=2)
        kb.scale = (1.0, 0.8, 0.6)
        kb.parent = o
    o.location = loc
    o.rotation_euler = (0.0, 0.0, math.radians(yaw_deg))
    return o
