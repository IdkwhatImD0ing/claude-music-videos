"""Mesh builders for the character library. Pure bmesh (no operators), so a whole character builds in well under a
second. Everything is built in CHARACTER SPACE (cm, the character standing at the origin facing -Y); parts are then
bone-parented with an identity basis (rig.bone_parent), so their vertices stay where they were modelled.
"""
from __future__ import annotations

import math

import bmesh
import bpy
from mathutils import Matrix, Vector

# ------------------------------------------------------------------------------------------------ objects


def to_object(bm, name: str, coll, mats=(), *, sharp: float | None = 38.0, smooth: bool = True):
    """bmesh -> a new mesh object in coll. Smooth shading with edges sharper than `sharp` degrees split."""
    if smooth:
        for f in bm.faces:
            f.smooth = True
        if sharp is not None:
            lim = math.radians(sharp)
            for e in bm.edges:
                if len(e.link_faces) == 2 and e.calc_face_angle(0.0) > lim:
                    e.smooth = False
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    for m in mats:
        me.materials.append(m)
    ob = bpy.data.objects.new(name, me)
    coll.objects.link(ob)
    return ob


def xform_verts(verts, M: Matrix):
    for v in verts:
        v.co = M @ v.co


# ------------------------------------------------------------------------------------------------ rounded box


def _axis_coords(h: float, r: float, seg: int, flat: int, extra=()) -> list[float]:
    """Grid positions along one axis of a cube of half-size h whose corners get rounded with radius r.
    Corner-zone samples are spaced so the projected arc is sampled at equal angles."""
    cs = []
    for i in range(seg + 1):
        th = (math.pi / 4) * (1 - i / seg)
        cs.append(-h + r - r * math.tan(th))
        cs.append(h - r + r * math.tan(th))
    a, b = -h + r, h - r
    for k in range(1, flat + 1):
        cs.append(a + (b - a) * k / (flat + 1))
    cs.extend(extra)
    out = []
    for c in sorted(cs):
        if not out or c - out[-1] > 1e-4:
            out.append(c)
    return out


def rounded_box(bm, size, r: float, center=(0, 0, 0), *, seg: int = 4, flat=(2, 2, 2), extra=((), (), ()),
                mat: int = 0, M: Matrix | None = None, taper: float = 0.0):
    """A box with every edge rounded to radius r (a perfect rounded box, not a bevel approximation).

    size: full extents; extra: extra grid cuts per axis (pre-projection coords, e.g. a seam height relative to the
    centre) so faces can be split cleanly later; taper: shrink x/y linearly toward +z (0.1 = top 10 % smaller).
    Returns the new faces."""
    h = [s / 2 for s in size]
    r = min(r, *h)
    L = [_axis_coords(h[a], r, seg, flat[a], extra[a]) for a in range(3)]
    verts: dict = {}
    faces = []

    def V(p):
        k = (round(p[0], 5), round(p[1], 5), round(p[2], 5))
        v = verts.get(k)
        if v is None:
            v = bm.verts.new(p)
            verts[k] = v
        return v

    for a in range(3):
        b, c = (a + 1) % 3, (a + 2) % 3
        for s in (-1, 1):
            grid = []
            for xb in L[b]:
                row = []
                for xc in L[c]:
                    p = [0.0, 0.0, 0.0]
                    p[a], p[b], p[c] = s * h[a], xb, xc
                    row.append(V(p))
                grid.append(row)
            for i in range(len(L[b]) - 1):
                for j in range(len(L[c]) - 1):
                    q = [grid[i][j], grid[i + 1][j], grid[i + 1][j + 1], grid[i][j + 1]]
                    if s < 0:
                        q.reverse()
                    f = bm.faces.new(q)
                    f.material_index = mat
                    faces.append(f)
    cen = Vector(center)
    lim = [hh - r for hh in h]
    for v in verts.values():
        p = v.co
        inner = Vector((max(-lim[0], min(lim[0], p.x)), max(-lim[1], min(lim[1], p.y)),
                        max(-lim[2], min(lim[2], p.z))))
        d = p - inner
        q = inner + d.normalized() * r if d.length > 1e-9 else p.copy()
        if taper:
            k = 1.0 - taper * (q.z + h[2]) / (2 * h[2])
            q.x *= k
            q.y *= k
        v.co = q + cen
    if M is not None:
        xform_verts(verts.values(), M)
    return faces


# ------------------------------------------------------------------------------------------------ lathe


def lathe(bm, profile, *, segs: int = 48, mat=0, M: Matrix | None = None, a0: float = 0.0, a1: float = 2 * math.pi,
          closed: bool = True):
    """Surface of revolution about Z. profile: [(r, z), ...] bottom to top; r == 0 makes a pole.
    mat: an int or a function (z_mid) -> material index. Angles start at -Y (the front) and run toward +X.
    closed=False with a0/a1 makes an open sheet (a coat with a front opening). Returns (faces, rings)."""
    n = segs if closed else segs + 1
    rings = []
    for (r, z) in profile:
        if r < 1e-6:
            rings.append([bm.verts.new((0.0, 0.0, z))])
            continue
        ring = []
        for i in range(n):
            a = a0 + (a1 - a0) * i / segs
            ring.append(bm.verts.new((r * math.sin(a), -r * math.cos(a), z)))
        rings.append(ring)
    faces = []
    for k in range(len(rings) - 1):
        A, B = rings[k], rings[k + 1]
        zm = (profile[k][1] + profile[k + 1][1]) / 2
        mi = mat(zm) if callable(mat) else mat
        cnt = segs
        for i in range(cnt):
            j = (i + 1) % n if closed else i + 1
            if len(A) == 1 and len(B) == 1:
                continue
            if len(A) == 1:
                q = [A[0], B[j], B[i]]
            elif len(B) == 1:
                q = [A[i], A[j], B[0]]
            else:
                q = [A[i], A[j], B[j], B[i]]
            try:
                f = bm.faces.new(q)
            except ValueError:
                continue
            f.material_index = mi
            faces.append(f)
    if M is not None:
        xform_verts([v for r in rings for v in r], M)
    return faces, rings


# ------------------------------------------------------------------------------------------------ 2D outlines


def rrect(w: float, h: float, rr: float | None = None, n: int = 10, cx=0.0, cz=0.0):
    """Rounded rectangle outline (CCW seen from the front, -Y). rr defaults to a pill."""
    rr = min(w, h) / 2 * 0.999 if rr is None else min(rr, w / 2, h / 2)
    pts = []
    corners = [(w / 2 - rr, h / 2 - rr, 0), (-w / 2 + rr, h / 2 - rr, 90), (-w / 2 + rr, -h / 2 + rr, 180),
               (w / 2 - rr, -h / 2 + rr, 270)]
    for (x, z, a0) in corners:
        for i in range(n + 1):
            a = math.radians(a0 + 90 * i / n)
            pts.append((cx + x + rr * math.cos(a), cz + z + rr * math.sin(a)))
    return _dedupe(pts)


def ellipse(w: float, h: float, n: int = 40, cx=0.0, cz=0.0):
    return [(cx + w / 2 * math.cos(2 * math.pi * i / n), cz + h / 2 * math.sin(2 * math.pi * i / n)) for i in range(n)]


def heart(w: float, h: float, n: int = 64, cx=0.0, cz=0.0):
    pts = []
    for i in range(n):
        t = 2 * math.pi * i / n
        x = 16 * math.sin(t) ** 3
        z = 13 * math.cos(t) - 5 * math.cos(2 * t) - 2 * math.cos(3 * t) - math.cos(4 * t)
        pts.append((cx + x / 32 * w, cz + (z + 2.5) / 30 * h))
    pts.reverse()  # make CCW
    return pts


def star(r_out: float, r_in: float, n: int = 5, cx=0.0, cz=0.0, round_: int = 3):
    pts = []
    for i in range(2 * n):
        a = math.pi / 2 + math.pi * i / n
        r = r_out if i % 2 == 0 else r_in
        pts.append((cx + r * math.cos(a), cz + r * math.sin(a)))
    return pts


def arc(cx, cz, rx, rz, a0_deg, a1_deg, n=16):
    return [(cx + rx * math.cos(math.radians(a0_deg + (a1_deg - a0_deg) * i / n)),
             cz + rz * math.sin(math.radians(a0_deg + (a1_deg - a0_deg) * i / n))) for i in range(n + 1)]


def stroke(center, width: float, cap: int = 8):
    """Outline of a thick smooth polyline with round caps (for ^^ eyes, lines, spirals)."""
    P = [Vector(p) for p in center]
    n = len(P)
    hw = width / 2

    def nrm(i):
        if i == 0:
            d = P[1] - P[0]
        elif i == n - 1:
            d = P[-1] - P[-2]
        else:
            d = (P[i + 1] - P[i]).normalized() + (P[i] - P[i - 1]).normalized()
        d = d.normalized()
        return Vector((-d.y, d.x))

    left = [P[i] + nrm(i) * hw for i in range(n)]
    right = [P[i] - nrm(i) * hw for i in range(n)]
    out = list(left)
    d_end = (P[-1] - P[-2]).normalized()
    a_end = math.atan2(nrm(n - 1).y, nrm(n - 1).x)
    for k in range(1, cap):
        a = a_end - math.pi * k / cap
        out.append(P[-1] + Vector((math.cos(a), math.sin(a))) * hw)
    out.extend(reversed(right))
    a_st = math.atan2(-nrm(0).y, -nrm(0).x)
    for k in range(1, cap):
        a = a_st - math.pi * k / cap
        out.append(P[0] + Vector((math.cos(a), math.sin(a))) * hw)
    pts = [(p.x, p.y) for p in out]
    if _area(pts) < 0:
        pts.reverse()
    return pts


def rounded_poly(pts, rr: float, n: int = 6):
    """A polygon (CCW) with every corner rounded by radius rr (clamped to the edges)."""
    P = [Vector(p) for p in pts]
    m = len(P)
    out = []
    for i in range(m):
        p0, p1, p2 = P[i - 1], P[i], P[(i + 1) % m]
        a, b = (p0 - p1), (p2 - p1)
        la, lb = a.length, b.length
        a.normalize()
        b.normalize()
        ang = math.acos(max(-1.0, min(1.0, a.dot(b))))
        d = min(rr / max(1e-6, math.tan(ang / 2)), la * 0.49, lb * 0.49)
        r = d * math.tan(ang / 2)
        s0, s1 = p1 + a * d, p1 + b * d
        bis = (a + b).normalized()
        c = p1 + bis * (r / max(1e-6, math.sin(ang / 2)))
        a0 = math.atan2(s0.y - c.y, s0.x - c.x)
        a1 = math.atan2(s1.y - c.y, s1.x - c.x)
        da = (a1 - a0 + math.pi) % (2 * math.pi) - math.pi
        for k in range(n + 1):
            q = a0 + da * k / n
            out.append((c.x + r * math.cos(q), c.y + r * math.sin(q)))
    return _dedupe(out)


def clip(outline, a: float, b: float, c: float):
    """Keep the part of a convex-ish outline where a*x + b*z + c >= 0 (Sutherland-Hodgman, one half-plane)."""
    out = []
    n = len(outline)
    for i in range(n):
        p, q = outline[i], outline[(i + 1) % n]
        fp, fq = a * p[0] + b * p[1] + c, a * q[0] + b * q[1] + c
        if fp >= 0:
            out.append(p)
        if (fp >= 0) != (fq >= 0):
            u = fp / (fp - fq)
            out.append((p[0] + (q[0] - p[0]) * u, p[1] + (q[1] - p[1]) * u))
    return out


def mirror_x(outline):
    return [(-x, z) for x, z in reversed(outline)]


def _area(pts):
    s = 0.0
    for i in range(len(pts)):
        x0, z0 = pts[i]
        x1, z1 = pts[(i + 1) % len(pts)]
        s += x0 * z1 - x1 * z0
    return s / 2


def _dedupe(pts, eps=1e-5):
    out = []
    for p in pts:
        if not out or abs(p[0] - out[-1][0]) + abs(p[1] - out[-1][1]) > eps:
            out.append(p)
    if len(out) > 2 and abs(out[0][0] - out[-1][0]) + abs(out[0][1] - out[-1][1]) < eps:
        out.pop()
    return out


def _inset(pts, d):
    """Offset a CCW outline inward by d (miter, clamped)."""
    n = len(pts)
    out = []
    for i in range(n):
        p0, p1, p2 = Vector(pts[i - 1]), Vector(pts[i]), Vector(pts[(i + 1) % n])
        e0 = (p1 - p0)
        e1 = (p2 - p1)
        if e0.length < 1e-9 or e1.length < 1e-9:
            out.append(tuple(p1))
            continue
        e0.normalize()
        e1.normalize()
        n0 = Vector((-e0.y, e0.x))  # CCW: inward is the left normal
        n1 = Vector((-e1.y, e1.x))
        m = (n0 + n1)
        if m.length < 1e-6:
            m = n0
        m.normalize()
        k = 1.0 / max(0.35, m.dot(n0))
        q = p1 + m * d * k
        out.append((q.x, q.y))
    return out


# ------------------------------------------------------------------------------------------------ raised decals


def decal(bm, outline, *, depth: float = 0.12, back: float = 0.1, bevel: float = 0.05, rings: int = 3, mat: int = 0,
          M: Matrix | None = None):
    """A raised glossy shape (an eye, a heart...) from a 2D outline in the XZ plane, facing -Y.

    The back sits at y = +back (buried in the surface), the front at y = -depth, with a rounded front edge of radius
    `bevel` (rings steps). Closed and manifold. Returns the new verts."""
    pts = _dedupe(outline)
    if _area(pts) < 0:
        pts.reverse()
    made = []

    def ring(ps, y):
        r = [bm.verts.new((x, y, z)) for x, z in ps]
        made.extend(r)
        return r

    R = [ring(pts, back), ring(pts, -depth + bevel)]
    for k in range(1, rings + 1):
        th = (math.pi / 2) * k / rings
        R.append(ring(_inset(pts, bevel * (1 - math.cos(th))), -depth + bevel - bevel * math.sin(th)))
    n = len(pts)
    for A, B in zip(R[:-1], R[1:]):
        for i in range(n):
            j = (i + 1) % n
            f = bm.faces.new((A[i], A[j], B[j], B[i]))
            f.material_index = mat
    f = bm.faces.new(R[-1])
    f.material_index = mat
    f = bm.faces.new(list(reversed(R[0])))
    f.material_index = mat
    if M is not None:
        xform_verts(made, M)
    return made


# ------------------------------------------------------------------------------------------------ misc solids


def cone(bm, r0: float, r1: float, h: float, *, segs: int = 10, M: Matrix | None = None, mat: int = 0,
         squash: float = 1.0):
    """A capped cone along +Z from z=0 (radius r0) to z=h (radius r1). squash scales y (flat teeth)."""
    ret = bmesh.ops.create_cone(bm, cap_ends=True, cap_tris=True, segments=segs, radius1=r0, radius2=r1, depth=h,
                                matrix=Matrix.Translation((0, 0, h / 2)))
    vs = ret['verts']
    for v in vs:
        v.co.y *= squash
    for f in {f for v in vs for f in v.link_faces}:
        f.material_index = mat
    if M is not None:
        xform_verts(vs, M)
    return vs


def uv_sphere(bm, r, *, segs=24, rings=12, M: Matrix | None = None, mat: int = 0, scale=(1, 1, 1)):
    ret = bmesh.ops.create_uvsphere(bm, u_segments=segs, v_segments=rings, radius=r)
    vs = ret['verts']
    for v in vs:
        v.co.x *= scale[0]
        v.co.y *= scale[1]
        v.co.z *= scale[2]
    for f in {f for v in vs for f in v.link_faces}:
        f.material_index = mat
    if M is not None:
        xform_verts(vs, M)
    return vs


def tube(bm, path, radii, *, segs: int = 16, mat: int = 0, cap0: bool = True, cap1: bool = True, up=(0, 0, 1)):
    """A tube along a 3D polyline with per-point radius (sleeves, legs, cables). Rounded (domed) caps.
    Returns (verts, per-vertex path parameter s in [0, total length])."""
    P = [Vector(p) for p in path]
    n = len(P)
    upv = Vector(up)
    made, params = [], []
    L = [0.0]
    for i in range(1, n):
        L.append(L[-1] + (P[i] - P[i - 1]).length)
    rings = []
    prev_x = None
    for i in range(n):
        if i == 0:
            d = P[1] - P[0]
        elif i == n - 1:
            d = P[-1] - P[-2]
        else:
            d = (P[i + 1] - P[i - 1])
        d.normalize()
        x = (upv.cross(d) if prev_x is None else prev_x - d * prev_x.dot(d))
        if x.length < 1e-6:
            x = Vector((1, 0, 0)).cross(d)
        x.normalize()
        prev_x = x
        y = d.cross(x)
        r = radii[i] if isinstance(radii, (list, tuple)) else radii
        ring = []
        for k in range(segs):
            a = 2 * math.pi * k / segs
            v = bm.verts.new(P[i] + (x * math.cos(a) + y * math.sin(a)) * r)
            ring.append(v)
            made.append(v)
            params.append(L[i])
        rings.append((ring, P[i], d, x, y, r))
    for (A, *_), (B, *_) in zip(rings[:-1], rings[1:]):
        for k in range(segs):
            j = (k + 1) % segs
            f = bm.faces.new((A[k], A[j], B[j], B[k]))
            f.material_index = mat
    for end, cap in ((0, cap0), (n - 1, cap1)):
        if not cap:
            continue
        ring, c, d, x, y, r = rings[end]
        sgn = -1 if end == 0 else 1
        prev = ring
        steps = 3
        for s in range(1, steps + 1):
            th = (math.pi / 2) * s / steps
            if s == steps:
                tip = bm.verts.new(c + d * sgn * r * 0.85)
                made.append(tip)
                params.append(L[end])
                for k in range(segs):
                    j = (k + 1) % segs
                    q = (prev[k], prev[j], tip) if sgn > 0 else (prev[j], prev[k], tip)
                    f = bm.faces.new(q)
                    f.material_index = mat
            else:
                rr = r * math.cos(th)
                cc = c + d * sgn * r * 0.85 * math.sin(th)
                nr = []
                for k in range(segs):
                    a = 2 * math.pi * k / segs
                    v = bm.verts.new(cc + (x * math.cos(a) + y * math.sin(a)) * rr)
                    nr.append(v)
                    made.append(v)
                    params.append(L[end])
                for k in range(segs):
                    j = (k + 1) % segs
                    q = (prev[k], prev[j], nr[j], nr[k]) if sgn > 0 else (prev[j], prev[k], nr[k], nr[j])
                    f = bm.faces.new(q)
                    f.material_index = mat
                prev = nr
    return made, params, L[-1]


def recalc_normals(bm):
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
