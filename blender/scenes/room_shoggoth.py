"""The shoggoth for the room scene: orange vinyl tentacles covered in blinking toy eyes, a lumpy eyed mass behind the
box, and the one eye that peeks out of the mail slot at the end.

Each tentacle is a geometry-nodes object built from nothing: a 40-point line whose bend angle is a function of the
point's parameter s and song time (a travelling sway wave plus a curl that tightens toward the tip and unfurls as the
tentacle rises); Accumulate Field integrates the unit steps into a kinematic chain, so it coils like a real tentacle.
Curve to Mesh skins it (tapering radius); eyes and suckers are instanced at fixed (s, angle) spots sampled along the
curve, so they ride the surface exactly. Eyes blink on their own seeded clocks, open on a keyed 'Open' and swivel to an
object on 'Stare'. Time is quantised to twos inside the tree (the stop-motion convention for characters).
"""
from __future__ import annotations

import math

import bmesh
import bpy
from mathutils import Vector

from pdoom import kit
from pdoom.chars import geo as cg
from pdoom.chars import looks
from pdoom.sets import geo
from pdoom import timing as tm
from pdoom.timing import FPS

from .room_nodes import Tree, modifier, set_input

N_PTS = 40
TAU = 2 * math.pi
BOX = (-12.0, 16.0, -20.0, 0.0, 16.9)       # the cardboard box's footprint x0, x1, y0, y1 and its lid top


# ------------------------------------------------------------------------------------------------ materials + protos


def mats():
    return dict(
        vinyl=looks.vinyl('room.shog.vinyl', '#E8621C', rough=0.4, sss=0.1, coat=0.3),
        vinyl_dark=looks.vinyl('room.shog.vinylDark', '#A8431E', rough=0.45, sss=0.05),
        sucker=looks.satin('room.shog.sucker', '#F7C2A8', rough=0.35, sss=0.3, coat=0.4),
        sclera=looks.gloss('room.eye.sclera', '#F6F1E8', rough=0.12, sss=0.15),
        iris=looks.gloss('room.eye.iris', '#E8C21E', rough=0.1),
        pupil=looks.gloss('room.eye.pupil', '#080606', rough=0.05),
    )


def build_protos(coll, M):
    """Eyeball (radius 1, looking +Z), socket ring (radius 1, in the XY plane) and sucker (radius 1, facing +Z)."""
    bm = bmesh.new()
    cg.uv_sphere(bm, 1.0, segs=28, rings=16)
    for f in bm.faces:
        z = f.calc_center_median().z
        f.material_index = 2 if z > 0.93 else (1 if z > 0.74 else 0)
    eye = cg.to_object(bm, 'shog.proto.eye', coll, [M['sclera'], M['iris'], M['pupil']], sharp=None)
    bm = bmesh.new()
    ring_prof = [(1.0, -0.2), (1.24, -0.1), (1.3, 0.05), (1.16, 0.2), (1.0, 0.14)]
    cg.lathe(bm, ring_prof + [ring_prof[0]], segs=28)
    ring = cg.to_object(bm, 'shog.proto.ring', coll, [M['vinyl_dark']], sharp=None)
    bm = bmesh.new()
    cg.lathe(bm, [(0.0, 0.0), (0.7, 0.0), (1.0, 0.12), (0.95, 0.32), (0.62, 0.35), (0.45, 0.18), (0.0, 0.16)], segs=18)
    sucker = cg.to_object(bm, 'shog.proto.sucker', coll, [M['sucker']], sharp=None)
    return eye, ring, sucker


# ------------------------------------------------------------------------------------------------ node pieces


def _tq(g):
    """Song time inside a tree: on twos at 24 fps; unquantised (every output frame) in a smooth 60 fps build."""
    frame = g.out(g.node('GeometryNodeInputSceneTime'), 'Frame')
    if tm.SMOOTH:
        return frame / 24.0
    return (g.floor((frame + 0.5) / 2.0) * 2.0 + 1.0) / 24.0


def _eyes(g, pos, out_dir, up_hint, eye_r, eid, seed, open_, stare, look_pos, tq, eye_ob, ring_ob, count,
          ring_pos=None):
    """Instance eyeballs (and their vinyl socket rings) on `count` points at field positions. Returns geometry."""
    pts = g.points(count)
    pts = g.set_position(pts, pos)
    to_look = g.normalize(look_pos - pos)
    look_dir = g.normalize(out_dir + to_look * (stare * 1.8))
    rot = g.out(g.node('FunctionNodeAxesToRotation', primary_axis='Z', secondary_axis='Y',
                       inputs={'Primary Axis': look_dir, 'Secondary Axis': up_hint}))
    period = g.rand(2.4, 5.2, eid, seed + 31)
    off = g.rand(0.0, 5.2, eid, seed + 32)
    ph = g.mod(tq + off, period)
    closed = g.clamp(1.0 - g.abs(ph - 0.08) / 0.08)
    delay = g.rand(0.0, 0.55, eid, seed + 33)
    op = g.smooth(open_, delay, delay + 0.3)
    sy0 = (1.0 - closed) * op
    sy = g.max(sy0, 0.06)
    scale = g.vec(eye_r, eye_r * sy, eye_r * g.max(sy, 0.35))
    eye_geo = g.object_geo(eye_ob, relative=False)
    eyes = g.instance(pts, eye_geo, rotation=rot, scale=scale)
    # socket rings sit on the surface, facing out. A shut eye's ring sinks into the surface and shrinks a little, so on
    # a curved tentacle it reads as a closed lid rather than a flat coin standing off the vinyl
    shut = g.clamp(1.0 - sy0)
    rp = ring_pos if ring_pos is not None else pos
    rpts = g.points(count)
    rpts = g.set_position(rpts, rp - out_dir * (eye_r * (shut * 0.24)))
    rrot = g.out(g.node('FunctionNodeAxesToRotation', primary_axis='Z', secondary_axis='Y',
                        inputs={'Primary Axis': out_dir, 'Secondary Axis': up_hint}))
    rs_ = eye_r * (1.0 - shut * 0.12)
    rings = g.instance(rpts, g.object_geo(ring_ob, relative=False), rotation=rrot, scale=g.vec(rs_, rs_, rs_))
    return g.join(eyes, rings)


def tentacle_tree(eye_ob, ring_ob, sucker_ob, vinyl):
    g = Tree('room.tentacle')
    g.input_geometry()
    base = g.param('Base', 'VECTOR', (0.0, 0.0, 0.0))
    yaw = g.param('Yaw', 'FLOAT', -math.pi / 2)
    lean = g.param('Lean', 'FLOAT', 0.15)
    length = g.param('Length', 'FLOAT', 30.0)
    rise = g.param('Rise', 'FLOAT', 1.0)
    r0 = g.param('R0', 'FLOAT', 3.0)
    curl = g.param('Curl', 'FLOAT', 2.0)
    sway = g.param('Sway', 'FLOAT', 0.35)
    freq = g.param('Freq', 'FLOAT', 2.2)
    phase = g.param('Phase', 'FLOAT', 0.0)
    twist = g.param('Twist', 'FLOAT', 0.4)
    n_eyes = g.param('Eyes', 'INT', 14)
    seed = g.param('Seed', 'INT', 0)
    open_ = g.param('Open', 'FLOAT', 0.0)
    stare = g.param('Stare', 'FLOAT', 0.0)
    look = g.param('Look', 'OBJECT')
    n_suck = g.param('Suckers', 'INT', 16)
    unfurl = g.param('Unfurl', 'FLOAT', 2.4)          # extra curl while short (unfurls as it rises)
    curl_grow = g.param('CurlGrow', 'FLOAT', 0.0)     # >0: the curl itself grows with the rise (rise ** k)
    tq = _tq(g)
    look_pos = g.out(g.node('GeometryNodeObjectInfo', transform_space='RELATIVE', inputs={'Object': look}), 'Location')

    def theta(s):
        curl_eff = curl * g.op('POWER', g.max(rise, 0.0), curl_grow) + (1.0 - rise) * unfurl
        wave = g.sin(freq * tq + phase - s * 5.0)
        return lean + curl_eff * s * s + sway * wave * s

    def phi(s):
        return yaw + twist * g.sin(freq * 0.63 * tq + phase * 1.7 - s * 3.0) * s

    def radius(s):
        return r0 * (1.0 - 0.86 * s ** 1.1) * (g.sin(s * 17.0 + phase) * 0.05 + 1.0)

    def skin(s):
        """The tube's radius: radius(s), closing to a rounded tip over the last 10% (a dome, not a cut hose)."""
        return radius(s) * g.max(g.sqrt(g.clamp((1.0 - s) / 0.1)), 0.12)

    line = g.out(g.node('GeometryNodeCurvePrimitiveLine', inputs={'Start': (0, 0, 0), 'End': (0, 0, 1)}))
    line = g.out(g.node('GeometryNodeResampleCurve', inputs={'Curve': line, 'Count': N_PTS}))
    s = g.out(g.node('GeometryNodeSplineParameter'), 'Factor')
    th, ph = theta(s), phi(s)
    d = g.vec(g.sin(th) * g.cos(ph), g.sin(th) * g.sin(ph), g.cos(th))
    step = d * (length * rise / (N_PTS - 1))
    acc = g.node('GeometryNodeAccumulateField', data_type='FLOAT_VECTOR', domain='POINT', inputs={'Value': step})
    trail = g.out(acc, 'Trailing')
    # the box is solid: any point over its footprint (grown by the local radius) is lifted to lie on the lid
    raw = base + trail
    rs = radius(s)
    bx0, bx1, by0, by1, lid = BOX
    inside = g.bool_and(g.bool_and(raw.x > rs * -1.0 + bx0, raw.x < rs + bx1),
                        g.bool_and(raw.y > rs * -1.0 + by0, raw.y < rs + by1))
    low = raw.z < rs * 0.85 + lid
    near_back = raw.y > by1 - 5.0
    hit = g.bool_and(inside, low)
    push_back = g.bool_and(hit, near_back)                 # squashed against the back wall, behind the box
    lift = g.bool_and(hit, g.bool_not(near_back))          # further in: lying on the lid
    ny = g.switch(push_back, raw.y, rs * 1.15 + (by1 + 0.3))
    nz = g.switch(lift, raw.z, rs * 0.85 + lid)
    curve = g.set_position(line, g.vec(raw.x, ny, nz))
    prof = g.out(g.node('GeometryNodeCurvePrimitiveCircle', inputs={'Resolution': 20, 'Radius': 1.0}))
    tube = g.out(g.node('GeometryNodeCurveToMesh', inputs={'Curve': curve, 'Profile Curve': prof,
                                                          'Scale': skin(s), 'Fill Caps': True}))
    tube = g.out(g.node('GeometryNodeSetShadeSmooth', inputs={'Mesh': tube}))
    tube = g.set_material(tube, vinyl)

    # --- eyes at fixed (s, angle) spots
    idx = g.index()
    se = g.rand(0.14, 0.9, idx, seed)
    ae = g.rand(0.0, TAU, idx, seed + 1)
    ez = g.rand(0.6, 1.0, idx, seed + 2)
    sc = g.node('GeometryNodeSampleCurve', mode='FACTOR', use_all_curves=False,
                inputs={'Curves': curve, 'Factor': se})
    P, Tn, Nn = g.out(sc, 'Position'), g.out(sc, 'Tangent'), g.out(sc, 'Normal')
    Bn = g.cross(Tn, Nn)
    out_dir = g.normalize(Nn * g.cos(ae) + Bn * g.sin(ae))
    r_e = radius(se)
    eye_r = ez * r_e * 0.56
    pos = P + out_dir * (r_e - eye_r * 0.3)
    up = g.vec(0.0, 0.0, 1.0)
    eyes = _eyes(g, pos, out_dir, up, eye_r, idx, seed, open_, stare, look_pos, tq, eye_ob, ring_ob, n_eyes,
                 ring_pos=P + out_dir * (r_e - eye_r * 0.12))

    # --- suckers: two rows along the inner side of the curl
    idx2 = g.index()
    k = g.op('FLOORED_MODULO', idx2, 2.0)
    ss = (g.floor(idx2 / 2.0) + 0.5) / (n_suck / 2.0) * 0.8 + 0.08
    sc2 = g.node('GeometryNodeSampleCurve', mode='FACTOR', use_all_curves=False,
                 inputs={'Curves': curve, 'Factor': ss})
    P2 = g.out(sc2, 'Position')
    T2 = g.out(sc2, 'Tangent')
    th2, ph2 = theta(ss), phi(ss)
    inner = g.vec(g.cos(th2) * g.cos(ph2), g.cos(th2) * g.sin(ph2), g.sin(th2) * -1.0)
    side = g.cross(T2, inner)
    ang = (k - 0.5) * 0.9
    sdir = g.normalize(inner * g.cos(ang) + side * g.sin(ang))
    r2 = radius(ss)
    sr = r2 * 0.2
    spts = g.set_position(g.points(n_suck), P2 + sdir * (r2 * 0.97))
    srot = g.out(g.node('FunctionNodeAxesToRotation', primary_axis='Z', secondary_axis='Y',
                        inputs={'Primary Axis': sdir, 'Secondary Axis': T2}))
    suckers = g.instance(spts, g.object_geo(sucker_ob, relative=False), rotation=srot, scale=g.vec(sr, sr, sr))
    g.output(g.join(tube, eyes, suckers))
    return g


def blob_tree(eye_ob, ring_ob):
    """Eyes on a point cloud (attributes nrm, esz) in the object's local space: the mass's eye field."""
    g = Tree('room.blob.eyes')
    pts_in = g.input_geometry()
    open_ = g.param('Open', 'FLOAT', 0.0)
    stare = g.param('Stare', 'FLOAT', 0.0)
    look = g.param('Look', 'OBJECT')
    n = g.param('Count', 'INT', 60)
    seed = g.param('Seed', 'INT', 5)
    tq = _tq(g)
    look_pos = g.out(g.node('GeometryNodeObjectInfo', transform_space='RELATIVE', inputs={'Object': look}), 'Location')
    idx = g.index()

    def sample(name, kind='FLOAT_VECTOR'):
        nd = g.node('GeometryNodeSampleIndex', data_type=kind, domain='POINT',
                    inputs={'Geometry': pts_in, 'Index': idx})
        at = g.out(g.node('GeometryNodeInputNamedAttribute', data_type=kind, inputs={'Name': name}), 0)
        g.feed(g.inp(nd, 'Value'), at)
        return g.out(nd, 0)
    P = sample('position')
    nrm = sample('nrm')
    esz = sample('esz', 'FLOAT')
    eye_r = esz
    pos = P + nrm * (eye_r * 0.25)
    eyes = _eyes(g, pos, nrm, g.vec(0.0, 0.0, 1.0), eye_r, idx, seed, open_, stare, look_pos, tq, eye_ob, ring_ob, n,
                 ring_pos=P + nrm * (eye_r * 0.05))
    g.output(eyes)
    return g


# ------------------------------------------------------------------------------------------------ objects


def carrier(name, coll):
    me = bpy.data.meshes.new(name)
    ob = bpy.data.objects.new(name, me)
    coll.objects.link(ob)
    return ob


def tentacle(coll, tree, name, look, **inputs):
    ob = carrier(name, coll)
    mod = modifier(ob, tree, 'tentacle')
    set_input(mod, 'Look', look)
    for k, v in inputs.items():
        set_input(mod, k, v)
    return ob, mod


def blob(coll, name, M, *, radius=9.0, squash=(1.45, 0.9, 1.05), n_eyes=60, seed=5, look=None, eyes_tree=None):
    """A lumpy vinyl mass (subdivided icosphere with a baked seeded displacement) and its eye field."""
    bm = bmesh.new()
    bmesh.ops.create_icosphere(bm, subdivisions=5, radius=radius)
    for v in bm.verts:
        p = v.co.normalized()
        n1 = math.sin(p.x * 3.1 + 1.3) * math.sin(p.y * 2.7 + 0.4) * math.sin(p.z * 3.3 + 2.1)
        n2 = math.sin(p.x * 7.0 + 2.2) * math.sin(p.y * 6.1 + 1.7) * math.sin(p.z * 6.7 + 0.3)
        v.co = p * radius * (1.0 + 0.16 * n1 + 0.05 * n2)
        v.co.x *= squash[0]
        v.co.y *= squash[1]
        v.co.z *= squash[2]
    body = cg.to_object(bm, name, coll, [M['vinyl']], sharp=None)
    # eye spots: seeded points over the front/upper surface, pushed onto the displaced surface by ray cast
    bpy.context.view_layer.update()
    rng = geo.rng(seed)
    co, nr, sz = [], [], []
    tries = 0
    while len(co) < n_eyes and tries < 5000:
        tries += 1
        u, w = rng(), rng()
        th = math.acos(1 - 2 * u)
        ph = TAU * w
        dvec = Vector((math.sin(th) * math.cos(ph), math.sin(th) * math.sin(ph), math.cos(th)))
        if dvec.y > 0.35 or dvec.z < -0.25:      # the front (-y) and top only
            continue
        ok, loc, n, _ = body.ray_cast(Vector((0, 0, 0)), dvec, distance=radius * 3)
        if not ok:
            continue
        # outward: the cast from inside hits back-faces; flip if needed
        n = n if n.dot(dvec) > 0 else -n
        s_eye = 0.55 + 1.1 * rng() ** 2
        if any((loc - Vector(c)).length < (s_eye + sz[i]) * 1.15 for i, c in enumerate(co)):
            continue
        co.append(tuple(loc))
        nr.append(tuple(n))
        sz.append(s_eye)
    # one big eye front and centre
    ok, loc, n, _ = body.ray_cast(Vector((0, 0, 0)), Vector((0.0, -0.94, 0.34)).normalized(), distance=radius * 3)
    if ok:
        n = n if n.y < 0 else -n
        keep = [i for i, c in enumerate(co) if (Vector(c) - loc).length > 4.2]
        co = [co[i] for i in keep] + [tuple(loc)]
        nr = [nr[i] for i in keep] + [tuple(n)]
        sz = [sz[i] for i in keep] + [2.6]
    me = bpy.data.meshes.new(name + '.eyes')
    me.from_pydata(co, [], [])
    a = me.attributes.new('nrm', 'FLOAT_VECTOR', 'POINT')
    a.data.foreach_set('vector', [c for v in nr for c in v])
    a = me.attributes.new('esz', 'FLOAT', 'POINT')
    a.data.foreach_set('value', sz)
    eo = bpy.data.objects.new(name + '.eyes', me)
    coll.objects.link(eo)
    eo.parent = body
    mod = modifier(eo, eyes_tree, 'eyes')
    set_input(mod, 'Count', len(co))
    set_input(mod, 'Seed', seed)
    if look is not None:
        set_input(mod, 'Look', look)
    return body, eo, mod


# ------------------------------------------------------------------------------------------------ keying on twos


def key_twos(ob, path, fn, t0, t1, *, index=-1, steps=()):
    """Sample fn(t) on the stop-motion grid (a pose per even global frame, held for two) from t0 to t1 and write
    CONSTANT keys half a frame early, like the characters library does.

    In a smooth 60 fps build (timing.SMOOTH) it samples every output frame instead and writes LINEAR keys, so the prop
    moves on every frame. `steps`: 24 fps frames where fn jumps (camera cuts); there the curve holds the old value and
    switches at timing.switch_frame (between two exposures), instead of sliding across the jump."""
    if tm.SMOOTH:
        _key_smooth(ob, path, fn, t0, t1, index, steps)
        return
    f0 = int(math.floor(t0 * FPS))
    f0 -= f0 % 2
    f1 = int(math.ceil(t1 * FPS)) + 2
    prev = None
    for f in range(f0, f1 + 1, 2):
        v = fn((f + 1) / FPS)
        if prev is not None and abs(v - prev) < 1e-6:
            continue
        _set_path(ob, path, v, index)
        ob.keyframe_insert(path, frame=f - 0.5, index=index)
        prev = v
    for fc in kit.fcurves(ob):
        if fc.data_path == path and (index < 0 or fc.array_index == index):
            for kp in fc.keyframe_points:
                kp.interpolation = 'CONSTANT'


def _key_smooth(ob, path, fn, t0, t1, index, steps):
    fr = tm.out_frames(math.floor(t0 * FPS) - 1, math.ceil(t1 * FPS) + 2)
    keys = [(f, fn(f / FPS)) for f in fr]
    hold = set()
    for sf in steps:
        before = [f for f, _ in keys if f < sf - 1e-6]
        if not before or not keys or sf > keys[-1][0]:
            continue
        hold.add(round(before[-1], 4))
        keys.append((tm.switch_frame(sf), fn(sf / FPS)))
    keys.sort()
    # drop samples inside flat runs (both neighbours equal): linear interpolation is unchanged
    out = []
    for i, (f, v) in enumerate(keys):
        if 0 < i < len(keys) - 1 and abs(v - keys[i - 1][1]) < 1e-7 and abs(v - keys[i + 1][1]) < 1e-7 and                 round(f, 4) not in hold:
            continue
        out.append((f, v))
    _set_path(ob, path, out[0][1], index)
    ob.keyframe_insert(path, frame=out[0][0], index=index)
    for fc in kit.fcurves(ob):
        if fc.data_path == path and (index < 0 or fc.array_index == index):
            kps = fc.keyframe_points
            kps.clear()
            kps.add(len(out))
            kps.foreach_set('co', [c for f, v in out for c in (f, v)])
            kps.foreach_set('interpolation', [0 if round(f, 4) in hold else 1 for f, _ in out])
            fc.update()


def _set_path(ob, path, v, index):
    target, attr = kit._resolve(ob, path)
    if index >= 0:
        getattr(target, attr)[index] = v
    else:
        setattr(target, attr, v)
