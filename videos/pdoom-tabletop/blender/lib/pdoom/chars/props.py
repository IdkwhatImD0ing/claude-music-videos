"""Small props Clawd wears (and scenes can reuse): paper crown, cat-ear headband, smiley mask, party hat, bow tie and
the take's '!' mark. Each is modelled around its own anchor (origin) in cm, facing -Y:

    obj = props.make('mask', coll, 'shoggoth.mask', M=Matrix.Translation((10, 0, 20)) @ Matrix.Scale(3, 4))
"""
from __future__ import annotations

import math

import bmesh
from mathutils import Matrix, Vector

from . import geo, looks


def _T(p):
    return Matrix.Translation(Vector(p))


def _Ry(deg):
    return Matrix.Rotation(math.radians(deg), 4, 'Y')


def _Rx(deg):
    return Matrix.Rotation(math.radians(deg), 4, 'X')


def _Rz(deg):
    return Matrix.Rotation(math.radians(deg), 4, 'Z')


# ------------------------------------------------------------------------------------------------ geometry


def _crown(bm, M, rx=1.75, ry=1.32, h=1.35, points=7):
    """A cracker-style paper crown: a zig-zag band around a squircle, base at z = 0."""
    n = points * 8
    rows = 4
    ring = []
    for i in range(n):
        a = 2 * math.pi * i / n
        c, s = math.cos(a), math.sin(a)
        x = rx * math.copysign(abs(c) ** 0.55, c)
        y = ry * math.copysign(abs(s) ** 0.55, s)
        f = (i % 8) / 8.0
        top = h * (0.58 + 0.42 * (1 - 2 * abs(f - 0.5)))   # valleys at f = 0, points at f = 0.5
        col = []
        for r in range(rows + 1):
            z = top * r / rows
            v = bm.verts.new((x * (1 + 0.04 * r / rows), y * (1 + 0.04 * r / rows), z))
            col.append(v)
        ring.append(col)
    faces = []
    for i in range(n):
        A, B = ring[i], ring[(i + 1) % n]
        for r in range(rows):
            faces.append(bm.faces.new((A[r], B[r], B[r + 1], A[r + 1])))
    bmesh.ops.recalc_face_normals(bm, faces=faces)
    ret = bmesh.ops.solidify(bm, geom=faces, thickness=0.04)
    vs = list({v for f in faces for v in f.verts} | {g for g in ret['geom'] if isinstance(g, bmesh.types.BMVert)})
    geo.xform_verts(vs, M)
    # three paper 'jewels' printed on the front
    for k, (a_deg, mat) in enumerate(((-90, 1), (-55, 2), (-125, 3))):
        a = math.radians(a_deg)
        c, s = math.cos(a), math.sin(a)
        x = rx * 1.02 * math.copysign(abs(c) ** 0.55, c)
        y = ry * 1.02 * math.copysign(abs(s) ** 0.55, s)
        yaw = math.degrees(math.atan2(c * ry, -s * rx))   # face along the outward normal
        geo.decal(bm, geo.ellipse(0.32, 0.32, 20), depth=0.05, back=0.03, bevel=0.03, rings=2, mat=mat,
                  M=M @ _T((x, y, h * 0.3)) @ _Rz(yaw))


def _ears(bm, M, width=8.0, top=0.0, r=0.66):
    """Cat-ear headband over a box head of `width`, whose top is at z = top (the anchor) with edge radius r."""
    th, wy = 0.12, 0.5
    path = []
    hw = width / 2
    for z in (-1.35, -0.9, -0.5, -r):
        path.append((hw + th / 2 + 0.03, top + z))
    for k in range(1, 8):
        a = math.radians(90 * k / 8)
        path.append(((hw - r) + (r + th / 2 + 0.03) * math.cos(a), top - r + (r + th / 2 + 0.03) * math.sin(a)))
    path.append((0.0, top + th / 2 + 0.03))
    full = path + [(-x, z) for x, z in reversed(path[:-1])]
    # sweep a rectangle along the XZ path
    verts = []
    for i, (x, z) in enumerate(full):
        a, b = full[max(i - 1, 0)], full[min(i + 1, len(full) - 1)]
        d = Vector((b[0] - a[0], b[1] - a[1])).normalized()
        nrm = Vector((d.y, -d.x))      # outward for this winding
        if nrm.x * x + nrm.y * (z - (top - 1.5)) < 0:
            nrm = -nrm
        q = [(Vector((x, z)) + nrm * o) for o in (-th / 2, th / 2)]
        verts.append([bm.verts.new((p.x, y, p.y)) for p in q for y in (-wy / 2, wy / 2)])
    faces = []
    for A, B in zip(verts[:-1], verts[1:]):
        for (i, j) in ((0, 2), (2, 3), (3, 1), (1, 0)):
            faces.append(bm.faces.new((A[i], A[j], B[j], B[i])))
    for cap in (verts[0], verts[-1]):
        faces.append(bm.faces.new((cap[0], cap[1], cap[3], cap[2])))
    for f in faces:
        f.material_index = 0
    bmesh.ops.recalc_face_normals(bm, faces=faces)
    geo.xform_verts({v for f in faces for v in f.verts}, M)
    tri = geo.rounded_poly([(-0.95, 0.0), (0.95, 0.0), (0.05, 1.95)], 0.28)
    inner = geo.rounded_poly([(-0.55, 0.25), (0.55, 0.25), (0.05, 1.45)], 0.2)
    for sx in (-1, 1):
        Me = M @ _T((sx * 2.3, 0.0, top - 0.05)) @ _Ry(sx * 13)
        o = tri if sx > 0 else geo.mirror_x(tri)
        oi = inner if sx > 0 else geo.mirror_x(inner)
        geo.decal(bm, o, depth=0.2, back=0.2, bevel=0.1, rings=2, mat=1, M=Me)
        geo.decal(bm, oi, depth=0.27, back=-0.1, bevel=0.05, rings=2, mat=2, M=Me)


def _mask(bm, M, d=3.6):
    """A yellow smiley mask (a glossy domed disc with a painted-on face), front at y ~ -0.3."""
    geo.decal(bm, geo.ellipse(d, d, 64), depth=0.3, back=0.0, bevel=0.24, rings=4, mat=0, M=M)
    k = d / 3.6
    F = M @ _T((0, -0.3 + 0.035, 0))
    for sx in (-1, 1):
        geo.decal(bm, geo.ellipse(0.42 * k, 0.78 * k, 28, cx=sx * 0.62 * k, cz=0.4 * k), depth=0.05, back=0.03,
                  bevel=0.03, rings=2, mat=1, M=F)
    geo.decal(bm, geo.stroke(geo.arc(0, 0.38 * k, 1.1 * k, 1.05 * k, 212, 328, 22), 0.24 * k), depth=0.05, back=0.03,
              bevel=0.03, rings=2, mat=1, M=F)


def _party(bm, M, r=0.95, h=2.5):
    geo.cone(bm, r, 0.04, h, segs=32, mat=0, M=M)
    geo.uv_sphere(bm, 0.3, segs=16, rings=8, mat=1, M=M @ _T((0, 0, h)))
    # a paper rim
    geo.cone(bm, r * 1.03, r * 0.98, 0.12, segs=32, mat=2, M=M @ _T((0, 0, -0.02)))


def _bowtie(bm, M):
    wing = geo.rounded_poly([(0.0, 0.14), (-1.0, 0.58), (-1.0, -0.58), (0.0, -0.14)], 0.16)
    geo.decal(bm, wing, depth=0.16, back=0.06, bevel=0.07, rings=2, mat=0, M=M)
    geo.decal(bm, geo.mirror_x(wing), depth=0.16, back=0.06, bevel=0.07, rings=2, mat=0, M=M)
    geo.decal(bm, geo.rrect(0.42, 0.46, 0.12), depth=0.22, back=0.06, bevel=0.08, rings=2, mat=0, M=M)


def _mark(bm, M):
    bar = geo.rounded_poly([(-0.19, 0.62), (0.19, 0.62), (0.31, 1.95), (-0.31, 1.95)], 0.16)
    geo.decal(bm, bar, depth=0.22, back=0.22, bevel=0.12, rings=3, mat=0, M=M)
    geo.decal(bm, geo.ellipse(0.44, 0.44, 24, cz=0.12), depth=0.22, back=0.22, bevel=0.12, rings=3, mat=0, M=M)


# ------------------------------------------------------------------------------------------------ materials


def _mats(prop):
    if prop == 'crown':
        return [looks.paper('chars.crown', '#F6C53D', rough=0.45), looks.gloss('chars.jewel.r', '#D8323E', rough=0.2),
                looks.gloss('chars.jewel.b', '#2F6FD6', rough=0.2), looks.gloss('chars.jewel.g', '#2E9E5B', rough=0.2)]
    if prop == 'cat_ears':
        return [looks.gloss('chars.band', '#1C1A1C', rough=0.25, coat=0.6), looks.felt('chars.felt.black', '#221D20'),
                looks.felt('chars.felt.pink', '#F49AB2')]
    if prop == 'mask':
        return [looks.gloss('chars.smiley', '#FFD23A', rough=0.18, coat=0.8), looks.gloss('chars.ink', '#15110F', rough=0.2)]
    if prop == 'party_hat':
        return [looks.paper('chars.partyhat', '#FF6FA8', rough=0.5), looks.felt('chars.felt.white', '#F7F3EC'),
                looks.paper('chars.partyrim', '#FFE066', rough=0.5)]
    if prop == 'bowtie':
        return [looks.satin('chars.bowtie', '#C8303C', rough=0.35, sheen=0.4, coat=0.3)]
    if prop == 'mark':
        return [looks.gloss('chars.mark', '#FFC21A', rough=0.15, coat=0.8)]
    raise KeyError(prop)


_GEO = {'crown': _crown, 'cat_ears': _ears, 'mask': _mask, 'party_hat': _party, 'bowtie': _bowtie, 'mark': _mark}


def make(prop: str, coll, name: str, M: Matrix | None = None):
    """A free-standing prop object (for scenes): its anchor at M."""
    bm = bmesh.new()
    _GEO[prop](bm, M or Matrix())
    return geo.to_object(bm, name, coll, _mats(prop), sharp=50)


# ------------------------------------------------------------------------------------------------ on Clawd


def build(prop: str, c) -> list:
    """Build a prop in Clawd's character space and bone-parent it. Returns its objects."""
    from .clawd import FACE_Y, EYE_Z, TOP, W, R_BODY, D
    from .rig import bone_parent
    if prop == 'crown':
        M, bone = _T((0.35, 0.15, TOP - 0.12)) @ _Ry(9), 'hat'
    elif prop == 'cat_ears':
        bm = bmesh.new()
        _ears(bm, _T((0, 0.35, 0)), width=W, top=TOP, r=R_BODY)
        ob = geo.to_object(bm, f'{c.name}.cat_ears', c.coll, _mats(prop), sharp=50)
        bone_parent(ob, c.rig, 'hat')
        return [ob]
    elif prop == 'mask':
        M, bone = _T((0, FACE_Y - 0.03, EYE_Z - 0.2)) @ _Rz(0) @ _Ry(-5), 'face'
    elif prop == 'party_hat':
        M, bone = _T((0.9, 0.1, TOP - 0.1)) @ _Ry(14), 'hat'
    elif prop == 'bowtie':
        M, bone = _T((0, FACE_Y, 2.45)), 'body'
    elif prop == 'mark':
        M, bone = _T((3.4, -0.4, TOP + 0.8)) @ _Ry(14), 'hat'
    else:
        raise KeyError(prop)
    ob = make(prop, c.coll, f'{c.name}.{prop}', M)
    bone_parent(ob, c.rig, bone)
    return [ob]
