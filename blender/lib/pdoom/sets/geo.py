"""Mesh helpers for the sets: lathes, tubes, text, true-scale UVs, and keying any property by song time.

Everything is in centimetres (1 BU = 1 cm). UVs are written at 1 UV unit = 1 cm, so a texture material maps a tile of
N cm by scaling UVs by 1/N (materials.py does this), and every prop shows its textures at true size.
"""
from __future__ import annotations

import math
import os

import bpy
import bmesh
from mathutils import Matrix, Vector

from .. import kit
from ..timing import FPS

# ------------------------------------------------------------------------------------------------ objects


def link(obj, coll):
    return kit.link(obj, coll)


def mesh_obj(name: str, verts, faces, coll=None, m=None, *, smooth: bool = False, uvs=None, loc=(0, 0, 0)):
    """An object from raw verts/faces. uvs: per-loop (u, v) list in face order (optional)."""
    me = bpy.data.meshes.new(name)
    me.from_pydata([tuple(v) for v in verts], [], [tuple(f) for f in faces])
    if uvs is not None:
        uvl = me.uv_layers.new(name='UVMap')
        for i, uv in enumerate(uvs):
            uvl.data[i].uv = uv
    me.update()
    if smooth:
        for p in me.polygons:
            p.use_smooth = True
    o = bpy.data.objects.new(name, me)
    (coll or bpy.context.scene.collection).objects.link(o)
    o.location = loc
    if m is not None:
        me.materials.append(m)
    return o


def empty(name, loc=(0, 0, 0), coll=None, size=1.0, kind='PLAIN_AXES', parent=None, rot=(0, 0, 0)):
    o = kit.empty(name, loc, coll, kind, size)
    o.rotation_euler = rot
    if parent is not None:
        o.parent = parent
    return o


def attach(child, par, loc=None, rot=None):
    """Parent child to par with child's transform expressed in par's local space (no inverse matrix)."""
    child.parent = par
    child.matrix_parent_inverse = Matrix.Identity(4)
    if loc is not None:
        child.location = loc
    if rot is not None:
        child.rotation_euler = rot
    return child


def descendants(o) -> list:
    out = [o]
    for c in o.children:
        out += descendants(c)
    return out


def set_smooth(o, angle_deg: float = 35.0):
    return kit.smooth(o, angle_deg)


def bevel(o, width: float, segments: int = 3, angle_deg: float = 40.0, harden=False):
    mod = o.modifiers.new('bevel', 'BEVEL')
    mod.width, mod.segments, mod.limit_method = width, segments, 'ANGLE'
    mod.angle_limit = math.radians(angle_deg)
    mod.harden_normals = harden
    return mod


# ------------------------------------------------------------------------------------------------ UVs


def box_uv(o, scale: float = 1.0):
    """Planar UVs per face by its dominant normal axis, in cm (object local coords) * scale."""
    me = o.data
    if not me.uv_layers:
        me.uv_layers.new(name='UVMap')
    uvl = me.uv_layers.active.data
    for p in me.polygons:
        n = p.normal
        ax = max(range(3), key=lambda i: abs(n[i]))
        for li in p.loop_indices:
            co = me.vertices[me.loops[li].vertex_index].co
            if ax == 2:
                u, v = co.x, co.y
            elif ax == 1:
                u, v = co.x, co.z
            else:
                u, v = co.y, co.z
            uvl[li].uv = (u * scale, v * scale)
    return o


def box(name, size=(1, 1, 1), loc=(0, 0, 0), *, bev: float = 0.0, segments: int = 3, m=None, coll=None, uv=True):
    """kit.box plus true-scale UVs (cm)."""
    o = kit.box(name, size, loc, bevel=bev, segments=segments, m=m, coll=coll)
    if uv:
        box_uv(o)
    return o


# ------------------------------------------------------------------------------------------------ lathe (turned shapes)


def lathe(name, profile, *, segs: int = 64, coll=None, m=None, smooth: bool = True, cap_top=False, cap_bottom=False,
          loc=(0, 0, 0), mat_idx=None, mats=None, smooth_angle: float = 50.0):
    """Revolve a profile [(r, z), ...] around local Z. UV: u = arc length at the ring (cm), v = profile length (cm).

    r = 0 points close the shape (poles). mat_idx: a material index per profile segment (len(profile) - 1), with
    mats the material list (m is ignored then).
    """
    verts, faces, uvs = [], [], []
    n = len(profile)
    # cumulative profile length for v
    vcum = [0.0]
    for i in range(1, n):
        (r0, z0), (r1, z1) = profile[i - 1], profile[i]
        vcum.append(vcum[-1] + math.hypot(r1 - r0, z1 - z0))
    rmax = max(r for r, _ in profile) or 1.0
    for j in range(segs):
        a = 2 * math.pi * j / segs
        ca, sa = math.cos(a), math.sin(a)
        for r, z in profile:
            verts.append((r * ca, r * sa, z))
    for j in range(segs):
        j2 = (j + 1) % segs
        for i in range(n - 1):
            a0, a1 = j * n + i, j * n + i + 1
            b0, b1 = j2 * n + i, j2 * n + i + 1
            faces.append((a0, b0, b1, a1))
            u0 = 2 * math.pi * rmax * j / segs
            u1 = 2 * math.pi * rmax * (j + 1) / segs
            uvs += [(u0, vcum[i]), (u1, vcum[i]), (u1, vcum[i + 1]), (u0, vcum[i + 1])]
    if cap_bottom:
        faces.append(tuple(j * n for j in reversed(range(segs))))
        uvs += [(profile[0][0] * math.cos(2 * math.pi * j / segs), profile[0][0] * math.sin(2 * math.pi * j / segs))
                for j in reversed(range(segs))]
    if cap_top:
        faces.append(tuple(j * n + n - 1 for j in range(segs)))
        uvs += [(profile[-1][0] * math.cos(2 * math.pi * j / segs), profile[-1][0] * math.sin(2 * math.pi * j / segs))
                for j in range(segs)]
    o = mesh_obj(name, verts, faces, coll, None if mats else m, smooth=smooth, uvs=uvs, loc=loc)
    if mats:
        for mm in mats:
            o.data.materials.append(mm)
        if mat_idx:
            nseg = n - 1
            for fi, p in enumerate(o.data.polygons):
                if fi < segs * nseg:
                    p.material_index = mat_idx[fi % nseg]
    # weld poles (r = 0) so shading is clean
    bm = bmesh.new()
    bm.from_mesh(o.data)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-5)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(o.data)
    bm.free()
    if smooth:
        kit.smooth(o, smooth_angle)
    return o


def rounded_profile(pts, radius: float, steps: int = 4):
    """Round the interior corners of a polyline profile [(r, z)] with arcs of `radius` (a quick fillet)."""
    out = [pts[0]]
    for i in range(1, len(pts) - 1):
        p0, p1, p2 = Vector(pts[i - 1]), Vector(pts[i]), Vector(pts[i + 1])
        d0, d1 = (p0 - p1), (p2 - p1)
        l0, l1 = d0.length, d1.length
        if l0 < 1e-6 or l1 < 1e-6:
            out.append(pts[i])
            continue
        rr = min(radius, l0 * 0.45, l1 * 0.45)
        a = p1 + d0.normalized() * rr
        b = p1 + d1.normalized() * rr
        for k in range(steps + 1):
            s = k / steps
            # quadratic bezier a -> p1 -> b
            q = (1 - s) ** 2 * a + 2 * (1 - s) * s * p1 + s * s * b
            out.append((q.x, q.y))
    out.append(pts[-1])
    return out


def prism(name, poly, thickness: float, *, coll=None, m=None, z0: float = 0.0, bevel_w: float = 0.0):
    """Extrude a 2D polygon [(x, y), ...] (counter-clockwise) from z0 to z0 + thickness (local XY plane)."""
    bm = bmesh.new()
    vs = [bm.verts.new((x, y, z0)) for x, y in poly]
    f = bm.faces.new(vs)
    ext = bmesh.ops.extrude_face_region(bm, geom=[f])
    top = [e for e in ext['geom'] if isinstance(e, bmesh.types.BMVert)]
    bmesh.ops.translate(bm, verts=top, vec=(0, 0, thickness))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    o = bpy.data.objects.new(name, me)
    (coll or bpy.context.scene.collection).objects.link(o)
    if m is not None:
        me.materials.append(m)
    if bevel_w:
        bevel(o, bevel_w, 2)
    box_uv(o)
    return o


def join(objs, name=None):
    """Join mesh objects into the first one (keeps materials). Returns the joined object."""
    objs = [o for o in objs if o is not None]
    if len(objs) == 1:
        if name:
            objs[0].name = name
        return objs[0]
    with bpy.context.temp_override(active_object=objs[0], selected_editable_objects=objs, selected_objects=objs):
        bpy.ops.object.join()
    o = objs[0]
    if name:
        o.name = name
        o.data.name = name
    return o


def apply_mods(o):
    """Bake the modifier stack into the mesh (e.g. before joining)."""
    dg = bpy.context.evaluated_depsgraph_get()
    ev = o.evaluated_get(dg)
    me = bpy.data.meshes.new_from_object(ev)
    old = o.data
    o.modifiers.clear()
    o.data = me
    if old.users == 0:
        bpy.data.meshes.remove(old)
    return o


# ------------------------------------------------------------------------------------------------ curves and tubes


def curve_tube(name, pts, radius: float, *, coll=None, m=None, kind='POLY', closed=False, res: int = 12,
               bevel_res: int = 4, to_mesh: bool = False, radii=None, fill_caps=True):
    """A round tube along points (world/local cm). kind: 'POLY' (exact polyline) or 'BEZIER' (smooth, auto handles)."""
    cd = bpy.data.curves.new(name, 'CURVE')
    cd.dimensions = '3D'
    cd.bevel_mode = 'ROUND'
    cd.bevel_depth = radius
    cd.bevel_resolution = bevel_res
    cd.resolution_u = res
    cd.use_fill_caps = fill_caps
    if kind == 'BEZIER':
        sp = cd.splines.new('BEZIER')
        sp.bezier_points.add(len(pts) - 1)
        for i, p in enumerate(pts):
            bp = sp.bezier_points[i]
            bp.co = p
            bp.handle_left_type = bp.handle_right_type = 'AUTO'
            if radii:
                bp.radius = radii[i]
    else:
        sp = cd.splines.new('POLY')
        sp.points.add(len(pts) - 1)
        for i, p in enumerate(pts):
            sp.points[i].co = (p[0], p[1], p[2], 1.0)
            if radii:
                sp.points[i].radius = radii[i]
    sp.use_cyclic_u = closed
    o = bpy.data.objects.new(name, cd)
    (coll or bpy.context.scene.collection).objects.link(o)
    if m is not None:
        cd.materials.append(m)
    if to_mesh:
        o = convert_to_mesh(o)
    return o


def convert_to_mesh(o):
    """Replace a curve/text object by a mesh object with the same name, transform and materials."""
    dg = bpy.context.evaluated_depsgraph_get()
    ev = o.evaluated_get(dg)
    me = bpy.data.meshes.new_from_object(ev)
    name, mw, colls, par = o.name, o.matrix_world.copy(), list(o.users_collection), o.parent
    mats = [s.material for s in o.material_slots]
    bpy.data.objects.remove(o, do_unlink=True)
    n = bpy.data.objects.new(name, me)
    for c in colls:
        c.objects.link(n)
    n.matrix_world = mw
    if par is not None:
        n.parent = par
        n.matrix_world = mw
    if not me.materials:
        for mm in mats:
            me.materials.append(mm)
    return n


def helix(n_turns: float, radius: float, length: float, steps_per_turn: int = 16):
    pts = []
    N = int(n_turns * steps_per_turn)
    for i in range(N + 1):
        a = 2 * math.pi * i / steps_per_turn
        pts.append((radius * math.cos(a), radius * math.sin(a), length * i / N))
    return pts


def arc_pts(center, r, a0_deg, a1_deg, steps=12):
    out = []
    for k in range(steps + 1):
        a = math.radians(a0_deg + (a1_deg - a0_deg) * k / steps)
        out.append((center[0] + r * math.cos(a), center[1] + r * math.sin(a)))
    return out


def catmull(points, samples_per_seg: int = 8):
    """A Catmull-Rom polyline through points (Vectors/tuples, 3D)."""
    P = [Vector(p) for p in points]
    P = [P[0] + (P[0] - P[1])] + P + [P[-1] + (P[-1] - P[-2])]
    out = []
    for i in range(1, len(P) - 2):
        p0, p1, p2, p3 = P[i - 1], P[i], P[i + 1], P[i + 2]
        for k in range(samples_per_seg):
            t = k / samples_per_seg
            t2, t3 = t * t, t * t * t
            q = 0.5 * ((2 * p1) + (-p0 + p2) * t + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t2 + (-p0 + 3 * p1 - 3 * p2 + p3) * t3)
            out.append(q)
    out.append(P[-2])
    return out


# ------------------------------------------------------------------------------------------------ text

_FONT = None
FONT_PATHS = ['C:/Windows/Fonts/bahnschrift.ttf', 'C:/Windows/Fonts/segoeui.ttf']


def sysfont(path: str) -> str:
    """A system font given by its Windows path; elsewhere (the Linux cloud render machines) the file of the same name
    in $PDOOM_FONT_DIR, if it is there."""
    if os.path.exists(path):
        return path
    d = os.environ.get('PDOOM_FONT_DIR')
    alt = os.path.join(d, os.path.basename(path)) if d else ''
    return alt if alt and os.path.exists(alt) else path


def font():
    """Bahnschrift (a DIN-style face, right for gauge dials) if the system has it, else Blender's built-in font."""
    global _FONT
    if _FONT is not None and _FONT.name in bpy.data.fonts:
        return _FONT
    for p in map(sysfont, FONT_PATHS):
        if os.path.exists(p):
            try:
                _FONT = bpy.data.fonts.load(p, check_existing=True)
                return _FONT
            except Exception:
                pass
    _FONT = None
    return None


def text_mesh(name, body: str, size: float, *, coll=None, m=None, align='CENTER', valign='CENTER', extrude=0.0,
              bevel_depth=0.0, spacing=1.0):
    """Flat text as a mesh object in the local XY plane (reads from +Z). Rotate it onto whatever surface."""
    cd = bpy.data.curves.new(name, 'FONT')
    cd.body = body
    f = font()
    if f is not None:
        cd.font = f
    cd.size = size
    cd.align_x = align
    cd.align_y = valign
    cd.extrude = extrude
    cd.bevel_depth = bevel_depth
    cd.space_character = spacing
    cd.resolution_u = 4
    o = bpy.data.objects.new(name, cd)
    (coll or bpy.context.scene.collection).objects.link(o)
    if m is not None:
        cd.materials.append(m)
    return convert_to_mesh(o)


# ------------------------------------------------------------------------------------------------ keys on anything


def keyp(owner, prop: str, t: float, value=None, *, interp: str | None = None, index: int = -1):
    """Keyframe owner.prop at song time t (owner: an object, a light, a node socket, a node...). Sets interp on the
    new key. Works for embedded data (node sockets key onto the node tree's action)."""
    if value is not None:
        if index >= 0:
            getattr(owner, prop)[index] = value
        else:
            setattr(owner, prop, value)
    f = t * FPS
    owner.keyframe_insert(prop, frame=f, index=index)
    if interp:
        idb = owner.id_data
        try:
            full = owner.path_from_id(prop)
        except Exception:
            full = prop
        for fc in kit.fcurves(idb):
            if fc.data_path != full or (index >= 0 and fc.array_index != index):
                continue
            for kp in fc.keyframe_points:
                if abs(kp.co.x - f) < 1e-4:
                    kp.interpolation = interp
    return owner


def clear_keys(owner, prop: str):
    """Remove the F-curves of owner.prop (e.g. to replace a canonical animation)."""
    idb = owner.id_data
    try:
        full = owner.path_from_id(prop)
    except Exception:
        full = prop
    ad = getattr(idb, 'animation_data', None)
    if not ad or not ad.action:
        return
    slot = ad.action_slot
    for layer in ad.action.layers:
        for strip in layer.strips:
            try:
                cb = strip.channelbag(slot)
            except Exception:
                cb = None
            if not cb:
                continue
            for fc in list(cb.fcurves):
                if fc.data_path == full:
                    cb.fcurves.remove(fc)


def hash01(*xs) -> float:
    """A deterministic hash in [0, 1) (no global random state)."""
    h = 2166136261
    for x in xs:
        for ch in repr(x):
            h = ((h ^ ord(ch)) * 16777619) & 0xFFFFFFFF
    h ^= h >> 13
    h = (h * 1274126177) & 0xFFFFFFFF
    return (h & 0xFFFFFF) / float(0x1000000)


def rng(seed):
    """A tiny seeded LCG generator: r = rng(3); r() -> [0, 1)."""
    state = [int(hash01('seed', seed) * 2 ** 31) or 1]

    def nxt():
        state[0] = (1103515245 * state[0] + 12345) & 0x7FFFFFFF
        return state[0] / float(0x80000000)
    return nxt
