"""The `leftturn` props: the broken, empty jar Clawd escaped from (safe_jar's jar lying on its side, a jagged hole
punched out of its flank, cracks, the hazard tape torn with its ends curling off, the gingham lid off on the desk,
glass shards around), and the clipboard of empty checkboxes (with a pencil) that the researcher waves at Clawd.

Jar frame: the jar lies on the desk with its axis horizontal along `u` (base -> mouth), its lowest line on the desk.
Jar-local coordinates are safe_jar's (base centre at the origin, axis +Z); local +X points straight up in the world
and local +Y points at the camera side (-dB, where the dominoes come from).
"""
from __future__ import annotations

import math
import random

import bmesh
import bpy
from mathutils import Matrix, Vector

from pdoom import kit
from pdoom.fx import fracture
from pdoom.sets import geo
from pdoom.sets import materials as M

from scenes import safe_jar as SJ

HOLE_ANGLE = 58.0            # the hole's centre, degrees from the top of the lying jar toward the camera side
HOLE_Z = 4.6                 # jar-local height (along the axis) of the hole's centre
TAPE_Z = 8.1                 # the tape band's centre (toward the mouth, clear of Clawd's feet)
HOLE_R = 3.3                 # cm


def jar_matrix(J: Vector, u: Vector) -> Matrix:
    """World matrix of the lying jar: its axis midpoint above J (on the desk), axis along u (base -> mouth)."""
    z = Vector((u.x, u.y, 0.0)).normalized()
    x = Vector((0.0, 0.0, 1.0))
    y = z.cross(x)
    R = Matrix((x, y, z)).transposed().to_4x4()
    return Matrix.Translation(Vector((J.x, J.y, SJ.R_OUT))) @ R @ Matrix.Translation((0, 0, -SJ.RIM / 2))


def local_dir(angle_deg: float) -> Vector:
    """A radial direction in jar-local XY, angle measured from the top (+X, world up) toward the camera (+Y)."""
    a = math.radians(angle_deg)
    return Vector((math.cos(a), math.sin(a), 0.0))


def surface_point(Mj: Matrix, angle_deg: float, z: float, lift: float = 0.0) -> Vector:
    d = local_dir(angle_deg)
    r = SJ.surface_r(z) + lift
    return Mj @ Vector((d.x * r, d.y * r, z))


# ------------------------------------------------------------------------------------------------ the broken jar


def broken_jar(coll, J: Vector, u: Vector, cam_side: Vector, *, seed: int = 5):
    """The lying jar (axis along u, base -> mouth), fractured, with the pieces around the hole removed; the hole
    faces up and toward cam_side. Returns a dict: 'M' (jar matrix), 'pieces' (kept, shown), 'loose' (removed
    pieces: shards to scatter), 'thread', 'hole' (world centre), 'hole_n' (world outward normal), 'hole_angle'
    (jar-local degrees from the top, signed)."""
    Mj = jar_matrix(J, u)
    y_world = Mj.to_3x3() @ Vector((0, 1, 0))
    ang = HOLE_ANGLE if y_world.dot(cam_side) > 0 else -HOLE_ANGLE
    jar, thread = SJ.build_jar(coll, 'lt.jar')
    jar.matrix_world = Mj
    thread.matrix_world = Mj
    thread.visible_shadow = False
    hole = surface_point(Mj, ang, HOLE_Z)
    hole_n = (Mj.to_3x3() @ local_dir(ang)).normalized()
    bpy.context.view_layer.update()
    pieces = fracture.fracture(jar, 64, seed=seed, impact=tuple(hole), cluster=0.78, mode='surface',
                               inner=SJ.glass(), coll=kit.collection('lt.jar.shards', coll))
    kept, loose = [], []
    for p in pieces:
        c = Vector(p['fx_seed'])
        # jagged: the hole's edge wanders with a seeded wobble around HOLE_R
        d = (c - hole) - hole_n * (c - hole).dot(hole_n)
        wob = 0.55 * math.sin(3.0 * math.atan2(d.y, d.x) + seed) + 0.35 * math.sin(7.0 * math.atan2(d.z, d.x))
        if (c - hole).length < HOLE_R + wob:
            loose.append(p)
        else:
            kept.append(p)
    for p in kept:
        p.visible_shadow = False
    return {'M': Mj, 'pieces': kept, 'loose': loose, 'thread': thread, 'hole': hole, 'hole_n': hole_n,
            'jar': jar, 'hole_angle': ang}


def scatter_shards(shards, J: Vector, dB: Vector, u: Vector, *, seed: int = 11, avoid_halfwidth: float = 2.2,
                   keep: int = 14, avoid=()):
    """Lay the knocked-out pieces flat on the desk in front of the hole (toward -dB), clear of the domino line
    (which comes in along dB through J). Extra pieces are removed. Returns the laid shards."""
    rnd = random.Random(seed)
    shards = sorted(shards, key=lambda p: -len(p.data.polygons))[:keep]
    extra = [p for p in shards[keep:]]
    out = []
    for i, p in enumerate(shards):
        # a spot in a fan in front of the jar, avoiding the dominoes' corridor
        for _ in range(80):
            along = rnd.uniform(6.8, 15.0)
            side = rnd.uniform(-11.0, 9.0)
            pos = J - dB * along + u * side
            if abs(side) > avoid_halfwidth + 0.6 and all((pos - Vector(a)).length > rr for a, rr in avoid):
                break
        # lay it flat: the shard's outward normal (from the jar axis) points up
        me = p.data
        nrm = Vector()
        for poly in me.polygons:
            if poly.material_index == 0:
                nrm += poly.normal * poly.area
        nrm = nrm.normalized() if nrm.length > 1e-6 else Vector((0, 0, 1))
        rot = nrm.rotation_difference(Vector((0, 0, 1))).to_matrix().to_4x4()
        yaw = Matrix.Rotation(rnd.uniform(0, 2 * math.pi), 4, 'Z')
        tilt = Matrix.Rotation(math.radians(rnd.uniform(-8, 8)), 4, 'X')
        R = yaw @ tilt @ rot
        zmin = min((R @ v.co).z for v in me.vertices)
        p.matrix_world = Matrix.Translation((pos.x, pos.y, -zmin + 0.01)) @ R
        p.visible_shadow = True
        out.append(p)
    for p in extra:
        bpy.data.objects.remove(p, do_unlink=True)
    return out


def ribbon(name, pts, across, coll, m, *, width: float = SJ.TAPE_W, u0: float = 0.0, torn_end: bool = False,
           seed: int = 3):
    """A tape ribbon along centre points pts (world), its width along the per-point `across` vectors. UV u = cm
    along, v = cm across (the hazard stripes). torn_end: the last row is ragged (a torn edge)."""
    rnd = random.Random(seed)
    n = len(pts)
    ss = [u0]
    for i in range(1, n):
        ss.append(ss[-1] + (pts[i] - pts[i - 1]).length)
    verts, faces, uvs = [], [], []
    k = 4 if torn_end else 1                    # verts across (k + 1)
    for i, p in enumerate(pts):
        a = across[i].normalized()
        t = (pts[min(i + 1, n - 1)] - pts[max(i - 1, 0)]).normalized()
        for j in range(k + 1):
            f = j / k
            q = p + a * ((f - 0.5) * width)
            if torn_end and i == n - 1:
                q = q + t * rnd.uniform(-0.45, 0.3)
            verts.append(tuple(q))
    for i in range(n - 1):
        for j in range(k):
            a0 = i * (k + 1) + j
            faces.append((a0, a0 + k + 1, a0 + k + 2, a0 + 1))
            v0, v1 = width * j / k, width * (j + 1) / k
            uvs += [(ss[i], v0), (ss[i + 1], v0), (ss[i + 1], v1), (ss[i], v1)]
    o = geo.mesh_obj(name, verts, faces, coll, m, smooth=True, uvs=uvs)
    sol = o.modifiers.new('solid', 'SOLIDIFY')
    sol.thickness = 0.02
    return o


def torn_tape(coll, Mj: Matrix, hole_angle: float = HOLE_ANGLE):
    """The hazard-tape band around the lying jar, torn open at the hole: the band runs around the back of the jar;
    its two ends peel off the glass and curl in the air. Returns the objects."""
    m = SJ.tape_mat('lt.tape', reveal=False, offset=False)
    zc = TAPE_Z
    r = SJ.TAPE_R + 0.02
    a_hole = math.radians(hole_angle)
    gap0, gap1 = a_hole - math.radians(28), a_hole + math.radians(40)      # the tear (flapA peels off below his feet)
    ax = Mj.to_3x3() @ Vector((0, 0, 1))
    objs = []
    pts, acr = [], []
    n = 90
    for i in range(n + 1):
        a = gap1 + (gap0 + 2 * math.pi - gap1) * i / n
        pts.append(Mj @ Vector((r * math.cos(a), r * math.sin(a), zc)))
        acr.append(ax)
    objs.append(ribbon('lt.tape.band', pts, acr, coll, m))
    # the two torn ends lift off the glass and curl outward
    for name, a_end, sgn, L, curl, seed in (('lt.tape.flapA', gap0, 1.0, 3.2, 2.2, 3),
                                            ('lt.tape.flapB', gap1, -1.0, 2.4, 2.8, 8)):
        p = Vector((r * math.cos(a_end), r * math.sin(a_end), zc))
        tan = Vector((-math.sin(a_end), math.cos(a_end), 0.0)) * sgn          # continuing round, over the hole
        nrm = Vector((math.cos(a_end), math.sin(a_end), 0.0))
        loc = [p]
        k = 16
        for i in range(1, k + 1):
            s = i / k
            ang = curl * s ** 1.3
            d = tan * math.cos(ang) + nrm * math.sin(ang)
            loc.append(loc[-1] + d * (L / k))
        objs.append(ribbon(name, [Mj @ q for q in loc], [ax] * len(loc), coll, m, torn_end=True, seed=seed))
    return objs


def lid(coll, loc: Vector, yaw_deg: float, tilt_deg: float = 4.0):
    """The gingham screw lid lying on the desk, right side up (a slight tilt)."""
    o = SJ.build_lid(coll, 'lt.jar.lid')
    o.matrix_world = (Matrix.Translation((loc.x, loc.y, 1.04 + 0.2)) @ Matrix.Rotation(math.radians(yaw_deg), 4, 'Z')
                      @ Matrix.Rotation(math.radians(tilt_deg), 4, 'X'))
    return o


def jar_collider(coll, J: Vector, u: Vector):
    """An invisible cylinder where the jar lies (the dominoes and the clipboard bounce off it)."""
    bpy.ops.mesh.primitive_cylinder_add(radius=SJ.R_OUT, depth=SJ.RIM, vertices=40, location=(J.x, J.y, SJ.R_OUT))
    o = bpy.context.object
    o.name = 'lt.jar.collider'
    kit.link(o, coll)
    o.rotation_euler = Vector((u.x, u.y, 0.0)).to_track_quat('Z', 'Y').to_euler()
    o.hide_render = True
    o.display_type = 'WIRE'
    return o


# ------------------------------------------------------------------------------------------------ the clipboard

CB_W, CB_H, CB_T = 5.0, 6.6, 0.22           # board: width (local x), height (local y), thickness (local z)


def _box(bm, size, center, mat):
    res = bmesh.ops.create_cube(bm, size=1.0, matrix=Matrix.Translation(center) @ Matrix.Diagonal((*size, 1.0)))
    for v in res['verts']:
        for f in v.link_faces:
            f.material_index = mat
    return res


def clipboard(coll, name='lt.clipboard'):
    """A little clipboard: hardboard with rounded corners, a sheet of paper printed with 'CDR' and five EMPTY
    checkboxes with ruled lines, a chrome clip, and a yellow pencil under the clip. One mesh, origin at the board's
    centre; the board's face is +Z, its top edge +Y. 5 x 6.6 cm."""
    mats = [M.solid('lt.cb.board', '#7A4E2A', rough=0.55, coat=0.3, coat_rough=0.2, micro=(18.0, 0.06)),
            M.paper('lt.cb.paper', '#F6F2E8', tile=12),
            M.solid('lt.cb.ink', '#23201C', rough=0.6),
            M.chrome('lt.cb.clip'),
            M.solid('lt.cb.pencil', '#F2B51E', rough=0.35, coat=0.5),
            M.solid('lt.cb.wood', '#E3C49A', rough=0.7),
            M.solid('lt.cb.lead', '#2B2B2E', rough=0.35, metal=0.4),
            M.solid('lt.cb.eraser', '#E8828C', rough=0.7),
            M.brass('lt.cb.ferrule', '#C9B27A', 0.3),
            M.solid('lt.cb.grey', '#8C8781', rough=0.7)]
    bm = bmesh.new()
    # board: a rounded rectangle prism
    r = 0.45
    poly = []
    for cx, cy, a0 in ((CB_W / 2 - r, CB_H / 2 - r, 0), (-CB_W / 2 + r, CB_H / 2 - r, 90),
                       (-CB_W / 2 + r, -CB_H / 2 + r, 180), (CB_W / 2 - r, -CB_H / 2 + r, 270)):
        for k in range(7):
            a = math.radians(a0 + 90 * k / 6)
            poly.append((cx + r * math.cos(a), cy + r * math.sin(a)))
    vs = [bm.verts.new((x, y, -CB_T / 2)) for x, y in poly]
    f = bm.faces.new(vs)
    ext = bmesh.ops.extrude_face_region(bm, geom=[f])
    top = [e for e in ext['geom'] if isinstance(e, bmesh.types.BMVert)]
    bmesh.ops.translate(bm, verts=top, vec=(0, 0, CB_T))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    for fc in bm.faces:
        fc.material_index = 0
    z0 = CB_T / 2
    # paper
    _box(bm, (CB_W - 0.5, CB_H - 1.0, 0.02), (0, -0.25, z0 + 0.01), 1)
    zi = z0 + 0.025
    # header underline and the ruled rows with EMPTY checkboxes
    _box(bm, (3.2, 0.05, 0.004), (0.0, 1.55, zi), 2)
    for i in range(5):
        y = 0.95 - i * 0.88
        s, lw = 0.52, 0.055
        x0 = -1.75
        for (sx, sy, cx, cy) in ((s, lw, x0, y + s / 2), (s, lw, x0, y - s / 2), (lw, s, x0 - s / 2, y),
                                 (lw, s, x0 + s / 2, y)):
            _box(bm, (sx, sy, 0.004), (cx, cy, zi), 2)
        _box(bm, (2.9, 0.05, 0.004), (0.25, y - 0.18, zi), 9)
        _box(bm, (1.9 - 0.3 * (i % 2), 0.05, 0.004), (-0.25 + 0.15 * (i % 2), y + 0.1, zi), 9)
    # the clip: a bent plate and a lever
    _box(bm, (2.3, 0.9, 0.08), (0, CB_H / 2 - 0.55, z0 + 0.1), 3)
    _box(bm, (2.1, 0.12, 0.22), (0, CB_H / 2 - 0.1, z0 + 0.14), 3)
    res = bmesh.ops.create_cone(bm, cap_ends=True, segments=10, radius1=0.09, radius2=0.09, depth=2.0,
                                matrix=Matrix.Translation((0, CB_H / 2 - 0.1, z0 + 0.3)) @
                                Matrix.Rotation(math.radians(90), 4, 'Y'))
    for v in res['verts']:
        for fc in v.link_faces:
            fc.material_index = 3
    # the pencil, under the clip, diagonal across the top right
    P = Matrix.Translation((1.35, CB_H / 2 - 1.2, z0 + 0.22)) @ Matrix.Rotation(math.radians(-62), 4, 'Z') @ \
        Matrix.Rotation(math.radians(90), 4, 'Y')
    L = 4.2
    res = bmesh.ops.create_cone(bm, cap_ends=True, segments=6, radius1=0.17, radius2=0.17, depth=L - 0.9,
                                matrix=P @ Matrix.Translation((0, 0, -0.45)))
    for v in res['verts']:
        for fc in v.link_faces:
            fc.material_index = 4
    res = bmesh.ops.create_cone(bm, cap_ends=True, segments=6, radius1=0.17, radius2=0.03, depth=0.6,
                                matrix=P @ Matrix.Translation((0, 0, L / 2 - 0.6)))
    for v in res['verts']:
        for fc in v.link_faces:
            fc.material_index = 5
    res = bmesh.ops.create_cone(bm, cap_ends=True, segments=6, radius1=0.045, radius2=0.0, depth=0.15,
                                matrix=P @ Matrix.Translation((0, 0, L / 2 - 0.23)))
    for v in res['verts']:
        for fc in v.link_faces:
            fc.material_index = 6
    res = bmesh.ops.create_cone(bm, cap_ends=True, segments=12, radius1=0.18, radius2=0.18, depth=0.35,
                                matrix=P @ Matrix.Translation((0, 0, -L / 2 + 0.3)))
    for v in res['verts']:
        for fc in v.link_faces:
            fc.material_index = 8
    res = bmesh.ops.create_cone(bm, cap_ends=True, segments=12, radius1=0.16, radius2=0.15, depth=0.3,
                                matrix=P @ Matrix.Translation((0, 0, -L / 2 + 0.02)))
    for v in res['verts']:
        for fc in v.link_faces:
            fc.material_index = 7
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    for m in mats:
        me.materials.append(m)
    o = bpy.data.objects.new(name, me)
    coll.objects.link(o)
    geo.box_uv(o)
    # the header: CDR
    tx = geo.text_mesh(f'{name}.cdr', 'CDR', 0.62, coll=coll, m=mats[2])
    geo.apply_mods(tx)
    tx.location = (0.0, 2.0, zi + 0.002)
    bpy.context.view_layer.update()
    joined = geo.join([o, tx], name)
    return joined
