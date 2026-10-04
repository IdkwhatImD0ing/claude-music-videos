"""Scene-local pieces for eat.py (not library code).

- Bites: a 'bite' cutter (a disc with scalloped tooth marks, extruded) keyed into place on the frame a chomp closes;
  a Boolean (DIFFERENCE, EXACT) modifier on each target takes the bite out (the mug's rim, the book).
- Breakables: pencils and the pen built in pieces with the desk's own materials: the middle vanishes into the mouth
  and the ends fly.
- Debris: crumbs, chips, paper bits and ink thrown from a bite (stateless fx.particles streams and confetti).
- fly(): keys a thrown piece every frame (ballistic, tumbling, bouncing and sliding to rest on the desk).
- The brass title P(DOOM) as separate 3D letters, each with its origin at its base.

Every animation here is keyed by song time (pure functions of t, seeded hashes, no global random state).
"""
from __future__ import annotations

import math

import bmesh
import bpy
from mathutils import Euler, Matrix, Quaternion, Vector

from pdoom import kit
from pdoom import timing as tm
from pdoom.fx import particles as P
from pdoom.sets import geo
from pdoom.sets import materials as M

FPS = tm.FPS
PARK = Vector((0.0, 0.0, -3000.0))


# ------------------------------------------------------------------------------------------------ timing helpers


def pose_key(t: float, lead: float = 0.02) -> float:
    """The key frame (f - 0.5) of the first on-twos pose that shows song time >= t - lead: a prop that must change
    together with a puppet's pose (an item vanishing as the lid slams) switches there. In a smooth build
    (timing.SMOOTH: the puppets move on every output frame) there are no twos poses: the switch goes on the first
    whole frame at or after t - lead (key f - 0.5; run.py moves the step to f - 0.1, between two exposures)."""
    if tm.SMOOTH:
        return math.ceil((t - lead) * FPS - 1e-6) - 0.5
    f = math.ceil((t - lead) * FPS - 1 - 1e-6)
    if f % 2:
        f += 1
    return f - 0.5


def frame_times(t0: float, t1: float):
    """Song times to key a per-frame animation at: every 24 fps frame, or every output frame in a smooth build."""
    f0, f1 = int(math.floor(t0 * FPS)), int(math.ceil(t1 * FPS))
    if tm.SMOOTH:
        return [f / FPS for f in tm.out_frames(f0, f1)]
    return [f / FPS for f in range(f0, f1 + 1)]


def hide_from(objs, kf: float):
    """Render-hide objects from key frame kf on (kf is a frame number, e.g. from pose_key)."""
    for o in objs:
        kit.visible(o, None, kf / FPS)


def show_from(objs, kf: float, kf_off: float | None = None):
    for o in objs:
        kit.visible(o, kf / FPS, None if kf_off is None else kf_off / FPS)


def key_const(obj, path, kf, value, index=-1):
    """A CONSTANT key on obj.path at frame kf."""
    if index >= 0:
        getattr(obj, path)[index] = value
    else:
        setattr(obj, path, value)
    obj.keyframe_insert(path, frame=kf, index=index)
    for fc in kit.fcurves(obj):
        if fc.data_path == path:
            for kp in fc.keyframe_points:
                if abs(kp.co.x - kf) < 1e-4:
                    kp.interpolation = 'CONSTANT'


def no_rays(o):
    """Invisible to every ray but still evaluated (boolean cutters, helpers)."""
    for a in ('visible_camera', 'visible_shadow', 'visible_diffuse', 'visible_glossy', 'visible_transmission',
              'visible_volume_scatter'):
        try:
            setattr(o, a, False)
        except Exception:
            pass
    o.display_type = 'WIRE'
    return o


# ------------------------------------------------------------------------------------------------ bites


def bite_mesh(name: str, coll, r: float = 2.4, depth: float = 6.0, teeth: int = 14, lobe: float = 0.09,
              seg: int = 84, m=None):
    """A prism along local Z (-depth/2..depth/2) whose outline is a circle of radius r made of rounded lobes (the
    marks of `teeth` teeth around the full circle): the shape a bite leaves."""
    bm = bmesh.new()
    bot, top = [], []
    for i in range(seg):
        a = 2 * math.pi * i / seg
        k = abs(math.cos(teeth * a / 2.0))
        rr = r * (1.0 + lobe * (k ** 0.45) - lobe * 0.5)
        x, y = rr * math.cos(a), rr * math.sin(a)
        bot.append(bm.verts.new((x, y, -depth / 2)))
        top.append(bm.verts.new((x, y, depth / 2)))
    for i in range(seg):
        j = (i + 1) % seg
        bm.faces.new((bot[i], bot[j], top[j], top[i]))
    bm.faces.new(list(reversed(bot)))
    bm.faces.new(top)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    o = bpy.data.objects.new(name, me)
    coll.objects.link(o)
    if m is not None:
        me.materials.append(m)
    no_rays(o)
    return o


class Biteable:
    """Targets that take bites: each gets a Boolean modifier whose operand is this collection of cutters. bake()
    then replaces the live Booleans by one baked mesh per bite state, swapped on the bite frames (a live EXACT
    Boolean cost ~0.7 s per scene evaluation, and motion blur evaluates the scene several times per frame)."""

    def __init__(self, name: str, objs, *, material=None, parent_coll=None, parent=None):
        self.name = name
        self.parent = parent
        self.coll = kit.collection(f'{name}.cutters', parent_coll)
        self.material = material
        self.n = 0
        self.targets = list(objs)
        self.cutters = []            # (object, key frame, placed location)
        for o in objs:
            mod = o.modifiers.new('bite', 'BOOLEAN')
            mod.operation = 'DIFFERENCE'
            mod.solver = 'EXACT'
            mod.operand_type = 'COLLECTION'
            mod.collection = self.coll
            mod.material_mode = 'TRANSFER' if material is not None else 'INDEX'
            # before the smoothing (Smooth by Angle) so the cut edges come out sharp
            idx = next((i for i, m in enumerate(o.modifiers) if m.type == 'NODES'), None)
            if idx is not None:
                o.modifiers.move(len(o.modifiers) - 1, idx)

    def bite(self, kf: float, M_world: Matrix, *, r: float = 2.4, depth: float = 6.0, teeth: int = 14):
        """A bite shaped like the cutter placed at M_world (its local Z is the bite's axis) from key frame kf."""
        self.n += 1
        c = bite_mesh(f'{self.name}.bite{self.n}', self.coll, r=r, depth=depth, teeth=teeth, m=self.material)
        if self.parent is not None:
            # cutters ride with the target (it may be thrown later): key them in its local space
            c.parent = self.parent
            c.matrix_parent_inverse = Matrix.Identity(4)
            M_world = self.parent.matrix_basis.inverted() @ M_world
        loc, rot, _ = M_world.decompose()
        c.rotation_mode = 'QUATERNION'
        c.rotation_quaternion = rot
        c.location = PARK
        self.cutters.append((c, kf, loc))
        return c

    def bake(self):
        """One mesh per state (0..n bites) for every target, each shown from its bite's key frame to the next."""
        cut = sorted(self.cutters, key=lambda x: x[1])
        kfs = [kf for _, kf, _ in cut]
        vl = bpy.context.view_layer
        for o in self.targets:
            for k in range(len(cut) + 1):
                for i, (c, kf, loc) in enumerate(cut):
                    c.location = loc if i < k else PARK
                vl.update()
                dg = bpy.context.evaluated_depsgraph_get()
                me = bpy.data.meshes.new_from_object(o.evaluated_get(dg))
                ob = bpy.data.objects.new(f'{o.name}.b{k}', me)
                for cl in o.users_collection:
                    cl.objects.link(ob)
                ob.parent = o.parent
                ob.parent_type = o.parent_type
                ob.matrix_parent_inverse = o.matrix_parent_inverse.copy()
                ob.matrix_basis = o.matrix_basis.copy()
                t_on = None if k == 0 else kfs[k - 1] / FPS
                t_off = kfs[k] / FPS if k < len(kfs) else None
                kit.visible(ob, t_on, t_off)
            o.modifiers.clear()
            o.hide_render = o.hide_viewport = True
        for c, _, _ in cut:
            bpy.data.objects.remove(c, do_unlink=True)
        self.cutters = []


# ------------------------------------------------------------------------------------------------ pencils and the pen


def _lathe(name, prof, coll, m, segs, smooth=True):
    return geo.lathe(name, prof, segs=segs, coll=coll, m=m, smooth=smooth)


def pencil_mats(paint='#E9B820'):
    """The desk's pencil materials (cached by name in the sets library)."""
    return dict(paint=M.enamel(f'pencil.paint.{paint}', paint, rough=0.35, coat=0.6),
                wood=M.solid('pencil.wood', '#D9B48A', rough=0.7, micro=(12.0, 0.1)),
                lead=M.solid('pencil.lead', '#2B2B2D', rough=0.35, metal=0.3),
                ferrule=M.brushed('pencil.ferrule', '#C8CACC', rough=(0.2, 0.35), tile=5),
                eraser=M.solid('pencil.eraser', '#E38C8C', rough=0.75, micro=(8.0, 0.05)))


def _cut_face(name, z, coll, mt, flip=False, r=0.395):
    """The broken end of a pencil: raw wood with the lead in the middle (just proud of the cut)."""
    dz = -0.004 if flip else 0.004
    w = _lathe(name + '.w', [(0.0, z + dz), (r, z + dz)] if not flip else [(r, z + dz), (0.0, z + dz)], coll,
               mt['wood'], 6, smooth=False)
    ld = _lathe(name + '.l', [(0.0, z + 2 * dz), (0.11, z + 2 * dz)] if not flip else [(0.11, z + 2 * dz),
                (0.0, z + 2 * dz)], coll, mt['lead'], 12, smooth=False)
    return [w, ld]


def pencil_pieces(coll, name, paint='#E9B820', length=17.6, cut=(6.2, 12.0)):
    """A hexagonal pencil along local +Z from its eraser end (like the desk's), in three pieces: the eraser end
    [0, a], the middle [a, b] and the sharpened end [b, length]. Returns (end_a, middle, end_b)."""
    mt = pencil_mats(paint)
    a, b = cut
    body_end = length - 1.9
    R = 0.405
    ea = [_lathe(f'{name}.eraser', [(0.0, 0.0), (0.3, 0.02), (0.33, 0.12), (0.33, 0.8), (0.0, 0.8)], coll,
                 mt['eraser'], 16),
          _lathe(f'{name}.ferrule', [(0.36, 0.7), (0.38, 0.8), (0.38, 1.0), (0.36, 1.05), (0.38, 1.1), (0.38, 1.5),
                                     (0.36, 1.55), (0.38, 1.6), (0.38, 1.75), (0.36, 1.8)], coll, mt['ferrule'], 24),
          _lathe(f'{name}.bodyA', [(0.0, 1.7), (R, 1.7), (R, a), (0.0, a)], coll, mt['paint'], 6, smooth=False)]
    ea += _cut_face(f'{name}.cutA', a, coll, mt)
    mid = [_lathe(f'{name}.bodyM', [(0.0, a), (R, a), (R, b), (0.0, b)], coll, mt['paint'], 6, smooth=False)]
    eb = [_lathe(f'{name}.bodyB', [(0.0, b), (R, b), (R, body_end), (0.0, body_end)], coll, mt['paint'], 6,
                 smooth=False),
          _lathe(f'{name}.cone', [(0.39, body_end), (0.1, length - 0.35), (0.0, length - 0.33)], coll, mt['wood'], 24),
          _lathe(f'{name}.lead', [(0.105, length - 0.37), (0.03, length - 0.02), (0.0, length)], coll, mt['lead'], 16)]
    eb += _cut_face(f'{name}.cutB', b, coll, mt, flip=True)
    A = geo.join(ea, f'{name}.A')
    Mi = geo.join(mid, f'{name}.M')
    B = geo.join(eb, f'{name}.B')
    return A, Mi, B


def pen_mats():
    return dict(body=M.plastic('pen.body', '#101218', rough=0.25, coat=0.5), chrome=M.chrome('pen.chrome'),
                refill=M.solid('eat.pen.refill', '#E8E4DA', rough=0.4), ink=M.solid('eat.ink', '#16244F', rough=0.12,
                                                                                 coat=1.0, spec=0.7))


def pen_pieces(coll, name, cut=6.4, L=13.8):
    """The desk's black click pen along local +Z (tip at 0, button at L) in two pieces: the front [0, cut] (tip and
    barrel) and the back [cut, L] (barrel, button, clip). The broken ends show the white refill. Returns (front,
    back)."""
    mt = pen_mats()
    fr = [_lathe(f'{name}.tip', [(0.0, 0.0), (0.12, 0.0), (0.2, 0.4), (0.25, 0.9), (0.0, 0.9)], coll, mt['chrome'], 24),
          _lathe(f'{name}.bodyF', [(0.0, 0.85), (0.36, 0.85), (0.46, 1.6), (0.47, cut), (0.0, cut)], coll, mt['body'],
                 32),
          _lathe(f'{name}.refF', [(0.0, cut + 0.004), (0.16, cut + 0.004)], coll, mt['refill'], 16)]
    bk = [_lathe(f'{name}.bodyB', [(0.0, cut), (0.47, cut), (0.47, L - 1.2), (0.42, L - 0.9), (0.0, L - 0.9)], coll,
                 mt['body'], 32),
          _lathe(f'{name}.button', [(0.25, L - 1.0), (0.3, L - 0.95), (0.3, L - 0.2), (0.2, L), (0.0, L)], coll,
                 mt['chrome'], 24),
          _lathe(f'{name}.refB', [(0.16, cut - 0.004), (0.0, cut - 0.004)], coll, mt['refill'], 16)]
    clip = geo.box(f'{name}.clip', (0.12, 0.26, 5.0), (-0.55, 0.0, L - 3.6), bev=0.04, m=mt['chrome'], coll=coll)
    bk.append(clip)
    return geo.join(fr, f'{name}.front'), geo.join(bk, f'{name}.back')


# ------------------------------------------------------------------------------------------------ flight


def fly(obj, t0: float, M0: Matrix, v0, w0, *, t_end: float, floor: float = 0.0, half: float = 0.4,
        bounce: float = 0.35, slide: float = 5.0, spin_damp: float = 3.0, keep_flat: bool = False, t_pre=None,
        drag: float = 0.0, desk=(80.0, 40.0), low_floor: float = -74.0):
    """Key obj's world placement every frame from t0 to t_end: it starts at M0 (a 4x4 world matrix) with velocity v0
    (cm/s) and angular velocity w0 (rad/s, world axes), falls under gravity, bounces off the desk (z = floor + half
    at its centre) and slides to rest with friction. keep_flat: spin only about world Z (a pencil stub skittering
    flat). Beyond the desk's edges (half-extents `desk`) it falls to low_floor. Returns the list of (t, Matrix)."""
    g = 981.0
    dt = 1.0 / 480.0
    p = M0.to_translation()
    q = M0.to_quaternion()
    v = Vector(v0)
    w = Vector(w0)
    if keep_flat:
        w = Vector((0.0, 0.0, w.z))
    out = []
    t = t0
    ts = frame_times(t0, t_end)
    i = 0
    resting = False
    while i < len(ts):
        while t < ts[i] - 1e-9:
            if not resting:
                on_desk = abs(p.x) < desk[0] and abs(p.y) < desk[1]
                fz = (floor if on_desk else low_floor) + half
                v.z -= g * dt
                if drag:
                    v *= math.exp(-drag * dt)
                p += v * dt
                if p.z < fz:
                    p.z = fz
                    if abs(v.z) > 30.0:
                        v.z = -v.z * bounce
                        v.x *= 0.7
                        v.y *= 0.7
                        w *= 0.6
                    else:
                        v.z = 0.0
                if p.z <= fz + 1e-4 and v.z == 0.0:
                    sp = v.xy.length
                    if sp > 0:
                        dec = min(sp, slide * 100.0 * dt)
                        v.x -= v.x / sp * dec
                        v.y -= v.y / sp * dec
                    w *= math.exp(-spin_damp * dt * 4.0)
                    if sp < 0.5 and w.length < 0.2:
                        resting = True
                ang = w.length * dt
                if ang > 0:
                    q = Quaternion(w.normalized(), ang) @ q
            t += dt
        out.append((ts[i], Matrix.Translation(p) @ q.to_matrix().to_4x4()))
        i += 1
    obj.rotation_mode = 'QUATERNION'
    if t_pre is not None:
        obj.location = M0.to_translation()
        obj.rotation_quaternion = M0.to_quaternion()
        obj.keyframe_insert('location', frame=t_pre * FPS)
        obj.keyframe_insert('rotation_quaternion', frame=t_pre * FPS)
    prev = None
    for tt, Mt in out:
        loc, rot, _ = Mt.decompose()
        if prev is not None and prev.dot(rot) < 0:
            rot = -rot
        prev = rot
        obj.location = loc
        obj.rotation_quaternion = rot
        obj.keyframe_insert('location', frame=tt * FPS)
        obj.keyframe_insert('rotation_quaternion', frame=tt * FPS)
    for fc in kit.fcurves(obj):
        if fc.data_path in ('location', 'rotation_quaternion'):
            for kp in fc.keyframe_points:
                kp.interpolation = 'LINEAR'
    return out


def place(obj, M: Matrix):
    obj.rotation_mode = 'QUATERNION'
    loc, rot, _ = M.decompose()
    obj.location = loc
    obj.rotation_quaternion = rot
    return obj


def recenter(obj) -> Vector:
    """Move obj's mesh so its origin is at its bounding-box centre; returns that centre in the old local space."""
    me = obj.data
    xs = [v.co for v in me.vertices]
    lo = Vector((min(v.x for v in xs), min(v.y for v in xs), min(v.z for v in xs)))
    hi = Vector((max(v.x for v in xs), max(v.y for v in xs), max(v.z for v in xs)))
    c = (lo + hi) / 2
    me.transform(Matrix.Translation(-c))
    me.update()
    return c


# ------------------------------------------------------------------------------------------------ debris


def _proto(name, bm, mats, coll):
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    for m in mats:
        me.materials.append(m)
    o = bpy.data.objects.new(name, me)
    coll.objects.link(o)
    o.location = (0, 0, -10000)
    o.hide_render = True
    return o


def proto_chip(name, coll, m, size=(0.35, 0.25, 0.08), seed=1):
    """A small irregular flat shard (ceramic, paint, cloth)."""
    ob = bpy.data.objects.get(name)
    if ob is not None:
        return ob
    bm = bmesh.new()
    n = 5
    top, bot = [], []
    for i in range(n):
        a = 2 * math.pi * i / n + 0.4 * geo.hash01(name, seed, i)
        rr = 0.6 + 0.5 * geo.hash01(name, seed, 'r', i)
        x, y = size[0] * 0.5 * rr * math.cos(a), size[1] * 0.5 * rr * math.sin(a)
        top.append(bm.verts.new((x, y, size[2] / 2)))
        bot.append(bm.verts.new((x, y, -size[2] / 2)))
    bm.faces.new(top)
    bm.faces.new(list(reversed(bot)))
    for i in range(n):
        j = (i + 1) % n
        bm.faces.new((bot[i], bot[j], top[j], top[i]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return _proto(name, bm, [m], coll)


def proto_cube(name, coll, m, s=0.16):
    ob = bpy.data.objects.get(name)
    if ob is not None:
        return ob
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=s)
    return _proto(name, bm, [m], coll)


def proto_drop(name, coll, m, r=0.12):
    ob = bpy.data.objects.get(name)
    if ob is not None:
        return ob
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=10, v_segments=6, radius=r)
    for v in bm.verts:
        v.co.z *= 0.75
    return _proto(name, bm, [m], coll)


def proto_shaving(name, coll, m_wood, m_paint, r=0.35):
    """A curled pencil shaving: a thin frilled cone ring, wood inside and a painted rim."""
    ob = bpy.data.objects.get(name)
    if ob is not None:
        return ob
    bm = bmesh.new()
    seg = 14
    inner, outer = [], []
    for i in range(seg + 1):
        a = 1.7 * math.pi * i / seg
        k = 1.0 - 0.35 * i / seg
        inner.append(bm.verts.new((0.35 * r * k * math.cos(a), 0.35 * r * k * math.sin(a), 0.05 * i / seg)))
        outer.append(bm.verts.new((r * k * math.cos(a), r * k * math.sin(a), 0.12 + 0.05 * i / seg)))
    for i in range(seg):
        f = bm.faces.new((inner[i], inner[i + 1], outer[i + 1], outer[i]))
        f.material_index = 0 if i % 3 else 1
    return _proto(name, bm, [m_wood, m_paint], coll)


def debris(name, proto, center, t0, *, count=40, direction=(0, 0, 1), speed=(40.0, 120.0), cone=60.0, drag=1.2,
           spin=18.0, scale=1.0, spread=(1.0, 1.0), emit=0.06, seed=3, coll=None, floor=0.0):
    """A burst of `count` copies of proto thrown from center at song time t0 (births over `emit` s): they tumble,
    fall, land flat on the desk and stay (fx.particles.stream, stateless)."""
    rate = count / max(emit, 1e-3)
    return P.stream(name, proto, source=(tuple(center), spread), t0=t0, t1=t0 + emit, rate=rate,
                    direction=tuple(direction), speed=speed, cone=cone, drag=drag, spin=spin, scale=scale,
                    floor=floor, seed=seed, coll=coll, rest_lift=0.02)


# ------------------------------------------------------------------------------------------------ the title


def title_letters(coll, text='P(DOOM)', *, size=7.0, font='C:/Windows/Fonts/ariblk.ttf', extrude=0.65, bevel=0.14,
                  m=None, spacing=1.04):
    """The title as brass 3D letters standing upright, facing -Y, one object per glyph, each with its origin at the
    middle of its base (on z = 0) and x its offset from the word's centre. Returns [(char, obj)]."""
    cd = bpy.data.curves.new('eat.title', 'FONT')
    cd.body = text
    try:
        cd.font = bpy.data.fonts.load(geo.sysfont(font), check_existing=True)
    except Exception:
        pass
    cd.size = size
    cd.extrude = extrude
    cd.bevel_depth = bevel
    cd.bevel_resolution = 3
    cd.resolution_u = 10
    cd.align_x = 'CENTER'
    cd.space_character = spacing
    ob = bpy.data.objects.new('eat.title', cd)
    coll.objects.link(ob)
    if m is not None:
        cd.materials.append(m)
    bpy.context.view_layer.update()
    ob = geo.convert_to_mesh(ob)
    me = ob.data
    # split into connected islands (each glyph is one island: P, (, D, O, O, M, ))
    bm = bmesh.new()
    bm.from_mesh(me)
    bm.verts.ensure_lookup_table()
    seen = set()
    islands = []
    for v in bm.verts:
        if v.index in seen:
            continue
        stack = [v]
        comp = []
        seen.add(v.index)
        while stack:
            x = stack.pop()
            comp.append(x.index)
            for e in x.link_edges:
                y = e.other_vert(x)
                if y.index not in seen:
                    seen.add(y.index)
                    stack.append(y)
        islands.append(comp)
    # merge islands that overlap in x (a glyph's counter can be its own island: the hole in P, D, O)
    boxes = []
    for comp in islands:
        xs = [bm.verts[i].co.x for i in comp]
        boxes.append([min(xs), max(xs), set(comp)])
    boxes.sort(key=lambda b: b[0])
    merged = []
    for b in boxes:
        if merged and b[0] < merged[-1][1] - 0.05 and b[1] <= merged[-1][1] + 0.05:
            merged[-1][2] |= b[2]
        else:
            merged.append(b)
    out = []
    chars = [ch for ch in text if not ch.isspace()]
    for k, (x0, x1, ids) in enumerate(merged):
        bm2 = bmesh.new()
        vmap = {}
        for i in ids:
            vmap[i] = bm2.verts.new(bm.verts[i].co)
        for f in bm.faces:
            if f.verts[0].index in ids:
                try:
                    nf = bm2.faces.new([vmap[v.index] for v in f.verts])
                    nf.smooth = f.smooth
                    nf.material_index = f.material_index
                except Exception:
                    pass
        # stand it up: font XY plane -> world XZ (front face +Z -> -Y)
        R = Matrix.Rotation(math.radians(90), 4, 'X')
        bmesh.ops.transform(bm2, matrix=R, verts=bm2.verts)
        zs = [v.co.z for v in bm2.verts]
        xs = [v.co.x for v in bm2.verts]
        cx, z0 = (min(xs) + max(xs)) / 2, min(zs)
        bmesh.ops.translate(bm2, vec=(-cx, 0.0, -z0), verts=bm2.verts)
        ch = chars[k] if k < len(chars) else '?'
        m2 = bpy.data.meshes.new(f'eat.title.{k}')
        bm2.to_mesh(m2)
        bm2.free()
        for mm in me.materials:
            m2.materials.append(mm)
        o = bpy.data.objects.new(f'eat.title.{k}.{ch}', m2)
        coll.objects.link(o)
        o['x'] = cx
        o['h'] = max(zs) - z0
        o['w'] = max(xs) - min(xs)
        kit.smooth(o, 40)
        out.append((ch, o))
    bm.free()
    bpy.data.objects.remove(ob, do_unlink=True)
    return out
