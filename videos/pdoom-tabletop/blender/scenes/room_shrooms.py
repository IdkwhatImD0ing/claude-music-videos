"""Glowing mushrooms for the room scene: four hand-sculpted-looking prototypes (a spotted toadstool, a pointy liberty
cap, a tall parasol and a little cluster) instanced by geometry nodes on a point cloud whose per-point birth times are
computed here in Python (a growth wave from the tipped bag, across the box floor, out of the window and the mail slot,
over the desk). The node tree only evaluates the time, so every frame is a pure function of song time.

Growth is on twos (the stop-motion convention for anything an animator would move by hand); the glow colour and the
beat pulse are material values keyed smoothly at 24 fps.
"""
from __future__ import annotations

import math

import bmesh
import bpy
from mathutils import Matrix

from pdoom import kit
from pdoom.chars import geo as cg
from pdoom.sets import geo

from . import room_box as RB
from .room_nodes import Tree, modifier

GROW = 0.42          # seconds from sprout to full size (with an overshoot)


# ------------------------------------------------------------------------------------------------ material


def glow_mat(name='room.shroom', *, sat=0.95, spots=True):
    """Emissive cap/gill/stem material. Hue per instance (instancer attribute 'hue') + a global keyed shift
    (node 'hueshift'); brightness keyed on node 'glow'. Material slots: 0 cap, 1 gills, 2 stem."""
    mats = []
    for part in ('cap', 'gill', 'stem'):
        m = bpy.data.materials.new(f'{name}.{part}')
        nt = m.node_tree
        b = nt.nodes.get('Principled BSDF')
        at = nt.nodes.new('ShaderNodeAttribute')
        at.attribute_type = 'INSTANCER'
        at.attribute_name = 'hue'
        hs = nt.nodes.new('ShaderNodeValue')
        hs.name = hs.label = 'hueshift'
        gl = nt.nodes.new('ShaderNodeValue')
        gl.name = gl.label = 'glow'
        gl.outputs[0].default_value = 1.0
        add = nt.nodes.new('ShaderNodeMath')
        add.operation = 'ADD'
        nt.links.new(at.outputs['Fac'], add.inputs[0])
        nt.links.new(hs.outputs[0], add.inputs[1])
        fr = nt.nodes.new('ShaderNodeMath')
        fr.operation = 'FRACT'
        nt.links.new(add.outputs[0], fr.inputs[0])
        cc = nt.nodes.new('ShaderNodeCombineColor')
        cc.mode = 'HSV'
        nt.links.new(fr.outputs[0], cc.inputs[0])
        cc.inputs[1].default_value = sat if part != 'stem' else 0.3
        cc.inputs[2].default_value = 1.0
        col = cc.outputs[0]
        strength = {'cap': 0.38, 'gill': 1.1, 'stem': 0.1}[part]
        mul = nt.nodes.new('ShaderNodeMath')
        mul.operation = 'MULTIPLY'
        mul.inputs[1].default_value = strength
        nt.links.new(gl.outputs[0], mul.inputs[0])
        if part == 'cap' and spots:
            # pale spots (object-space Voronoi on the prototype): white, not glowing
            tc = nt.nodes.new('ShaderNodeTexCoord')
            vo = nt.nodes.new('ShaderNodeTexVoronoi')
            vo.inputs['Scale'].default_value = 3.2
            vo.inputs['Randomness'].default_value = 0.8
            nt.links.new(tc.outputs['Object'], vo.inputs['Vector'])
            lt = nt.nodes.new('ShaderNodeMath')
            lt.operation = 'LESS_THAN'
            lt.inputs[1].default_value = 0.11
            nt.links.new(vo.outputs['Distance'], lt.inputs[0])
            mx = nt.nodes.new('ShaderNodeMix')
            mx.data_type = 'RGBA'
            si = {x.identifier: x for x in mx.inputs}
            so = {x.identifier: x for x in mx.outputs}
            nt.links.new(lt.outputs[0], si['Factor_Float'])
            nt.links.new(col, si['A_Color'])
            si['B_Color'].default_value = (0.95, 0.92, 0.85, 1.0)
            nt.links.new(so['Result_Color'], b.inputs['Base Color'])
            inv = nt.nodes.new('ShaderNodeMath')
            inv.operation = 'SUBTRACT'
            inv.inputs[0].default_value = 1.0
            nt.links.new(lt.outputs[0], inv.inputs[1])
            mul2 = nt.nodes.new('ShaderNodeMath')
            mul2.operation = 'MULTIPLY'
            nt.links.new(mul.outputs[0], mul2.inputs[0])
            nt.links.new(inv.outputs[0], mul2.inputs[1])
            nt.links.new(mul2.outputs[0], b.inputs['Emission Strength'])
        else:
            if part == 'stem':
                b.inputs['Base Color'].default_value = kit.srgb('#EFE6D6')
            else:
                nt.links.new(col, b.inputs['Base Color'])
            nt.links.new(mul.outputs[0], b.inputs['Emission Strength'])
        nt.links.new(col, b.inputs['Emission Color'])
        b.inputs['Roughness'].default_value = 0.35 if part == 'cap' else 0.6
        b.inputs['Coat Weight'].default_value = 0.4 if part == 'cap' else 0.0
        b.inputs['Subsurface Weight'].default_value = 0.25
        b.inputs['Subsurface Radius'].default_value = (1.0, 0.8, 0.6)
        b.inputs['Subsurface Scale'].default_value = 0.1
        m.diffuse_color = (1.0, 0.4, 0.8, 1.0)
        mats.append(m)
    return mats


def key_mats(mats, fn_shift, fn_glow, t0, t1, step=1):
    """Key the hue shift and glow of every mushroom material at each frame from t0 to t1."""
    from pdoom.timing import FPS
    f0, f1 = int(math.floor(t0 * FPS)), int(math.ceil(t1 * FPS))
    for m in mats:
        nt = m.node_tree
        hs = nt.nodes['hueshift'].outputs[0]
        gl = nt.nodes['glow'].outputs[0]
        for f in range(f0, f1 + 1, step):
            t = f / FPS
            hs.default_value = fn_shift(t)
            hs.keyframe_insert('default_value', frame=f)
            gl.default_value = fn_glow(t)
            gl.keyframe_insert('default_value', frame=f)


# ------------------------------------------------------------------------------------------------ prototypes


def _bend(verts, k):
    for v in verts:
        v.co.x += k * v.co.z * v.co.z


def proto_toadstool(bm, M=None):
    stem = [(0.0, 0.0), (0.3, 0.0), (0.32, 0.12), (0.25, 0.55), (0.21, 1.1), (0.24, 1.42), (0.0, 1.42)]
    cg.lathe(bm, stem, segs=20, mat=2, M=M)
    cap = [(0.0, 1.38), (0.3, 1.36), (0.78, 1.33), (0.99, 1.4), (1.02, 1.55), (0.93, 1.8), (0.66, 2.02), (0.33, 2.12),
           (0.0, 2.15)]
    cg.lathe(bm, cap, segs=28, mat=lambda z: 1 if z < 1.38 else 0, M=M)


def proto_liberty(bm, M=None):
    """Psilocybe-style liberty cap: a thin wavy stem and a pointy conical cap with a nipple."""
    stem = [(0.0, 0.0), (0.12, 0.0), (0.1, 0.5), (0.085, 1.3), (0.08, 2.0), (0.0, 2.0)]
    _, rings = cg.lathe(bm, stem, segs=12, mat=2)
    vs = [v for r in rings for v in r]
    _bend(vs, 0.06)
    cap = [(0.0, 1.86), (0.28, 1.84), (0.44, 1.88), (0.4, 2.1), (0.3, 2.38), (0.17, 2.6), (0.09, 2.72), (0.05, 2.8),
           (0.0, 2.82)]
    _, rings2 = cg.lathe(bm, cap, segs=20, mat=lambda z: 1 if z < 1.86 else 0)
    for v in [v for r in rings2 for v in r]:
        v.co.x += 0.06 * 2.0 * 2.0
    if M is not None:
        cg.xform_verts(vs + [v for r in rings2 for v in r], M)


def proto_parasol(bm, M=None):
    stem = [(0.0, 0.0), (0.2, 0.0), (0.16, 0.2), (0.12, 1.2), (0.11, 2.3), (0.0, 2.3)]
    _, rings = cg.lathe(bm, stem, segs=14, mat=2)
    vs = [v for r in rings for v in r]
    _bend(vs, -0.035)
    # a ring (annulus) on the stem
    _, rr = cg.lathe(bm, [(0.11, 1.75), (0.26, 1.7), (0.24, 1.66), (0.11, 1.68)], segs=14, mat=2)
    cap = [(0.0, 2.24), (0.5, 2.22), (1.1, 2.2), (1.24, 2.26), (1.1, 2.4), (0.7, 2.56), (0.3, 2.66), (0.0, 2.7)]
    _, rings2 = cg.lathe(bm, cap, segs=30, mat=lambda z: 1 if z < 2.23 else 0)
    off = -0.035 * 2.3 * 2.3
    for v in [v for r in rings2 for v in r] + [v for r in rr for v in r]:
        v.co.x += off if v.co.z > 2.0 else -0.035 * v.co.z * v.co.z
    if M is not None:
        cg.xform_verts(vs + [v for r in rings2 for v in r] + [v for r in rr for v in r], M)


def proto_cluster(bm, M=None):
    for (x, y, s, rz) in ((0.0, 0.0, 0.62, 0), (0.62, 0.2, 0.45, 40), (-0.3, 0.55, 0.38, 80), (0.25, -0.5, 0.33, 10)):
        Mi = Matrix.Translation((x, y, 0)) @ Matrix.Rotation(math.radians(rz), 4, 'Z') @ Matrix.Diagonal((s, s, s * 1.1, 1))
        if M is not None:
            Mi = M @ Mi
        proto_toadstool(bm, Mi)


PROTOS = [proto_toadstool, proto_liberty, proto_parasol, proto_cluster]


def build_protos(coll, mats):
    """One object per prototype in `coll` (excluded from the view layer by the caller). Heights ~2.1-2.8 cm."""
    obs = []
    for i, fn in enumerate(PROTOS):
        bm = bmesh.new()
        fn(bm)
        o = cg.to_object(bm, f'shroom.proto{i}', coll, mats, sharp=None)
        obs.append(o)
    return obs


# ------------------------------------------------------------------------------------------------ the growth


def growth_tree(protos_coll, grow=GROW):
    g = Tree('room.shrooms')
    pts = g.input_geometry()
    beat = g.param('Beat', 'FLOAT', 0.0)
    frame = g.out(g.node('GeometryNodeInputSceneTime'), 'Frame')
    from pdoom import timing as tm
    if tm.SMOOTH:
        tq = frame / 24.0                                               # every output frame (smooth 60 fps build)
    else:
        tq = (g.floor((frame + 0.5) / 2.0) * 2.0 + 1.0) / 24.0      # on twos

    def attr(name, kind='FLOAT'):
        return g.out(g.node('GeometryNodeInputNamedAttribute', data_type=kind, inputs={'Name': name}), 0)
    birth, size, yaw = attr('birth'), attr('size'), attr('yaw')
    tilt = attr('tilt', 'FLOAT_VECTOR')
    var = g.out(g.node('GeometryNodeInputNamedAttribute', data_type='INT', inputs={'Name': 'var'}), 0)
    u = g.clamp((tq - birth) / grow)
    fc = g.node('ShaderNodeFloatCurve', inputs={'Value': u})
    cv = fc.mapping.curves[0]
    cv.points[0].location = (0.0, 0.0)
    cv.points[1].location = (1.0, 1.0)
    for x, y in ((0.45, 0.62), (0.7, 1.22), (0.86, 0.94)):
        cv.points.new(x, y)
    fc.mapping.use_clip = False
    fc.mapping.update()
    grow_s = g.out(fc, 'Value')
    # beat bob: squash on the beat, fading in with growth
    bob = beat * 0.16 * g.clamp(u * 2.0)
    sxy = size * grow_s * (bob * 0.5 + 1.0)
    sz = size * grow_s * (1.0 - bob)
    scale = g.vec(sxy, sxy, sz)
    rot = g.euler(g.vec(tilt.x, tilt.y, yaw))
    alive = u > 0.001
    inst = g.collection_geo(protos_coll, separate=True, reset=True)
    out = g.instance(pts, inst, rotation=rot, scale=scale, selection=alive, pick=True, instance_index=var)
    g.output(out)
    return g


def _poisson(rng, n_try, sampler, min_d, accept):
    pts = []
    cell = min_d / math.sqrt(2)
    grid = {}
    for _ in range(n_try):
        p = sampler()
        if not accept(p):
            continue
        gx, gy = int(math.floor(p[0] / cell)), int(math.floor(p[1] / cell))
        ok = True
        for dx in range(-2, 3):
            for dy in range(-2, 3):
                q = grid.get((gx + dx, gy + dy))
                if q is not None and (q[0] - p[0]) ** 2 + (q[1] - p[1]) ** 2 < min_d * min_d:
                    ok = False
                    break
            if not ok:
                break
        if ok:
            grid[(gx, gy)] = p
            pts.append(p)
    return pts


def layout(*, t_start, mouth, exclude_in, exclude_out, flap_pts, seed=11):
    """The point cloud: list of dicts (co, birth, size, var, yaw, tilt, hue).

    mouth: where the wave starts (the tipped bag's mouth, world xy). exclude_in / exclude_out: lists of callables
    (x, y) -> True to reject. flap_pts: a function (u, v) -> world point on the window flap (u across, v from the
    sill 0 to its far edge 1)."""
    rng = geo.rng(seed)
    out = []
    X0, X1, Y0, Y1, T = RB.X0, RB.X1, RB.Y0, RB.Y1, RB.T
    sp_in, sp_ramp, sp_out = 24.0, 20.0, 15.0
    wx0, wx1 = RB.WIN[0], RB.WIN[1]
    # --- inside the box
    xi0, xi1, yi0, yi1 = X0 + T + 0.5, X1 - T - 0.5, Y0 + T + 0.5, Y1 - T - 0.5

    def acc_in(p):
        return not any(f(*p) for f in exclude_in)
    pin = _poisson(rng, 5000, lambda: (xi0 + (xi1 - xi0) * rng(), yi0 + (yi1 - yi0) * rng()), 1.05, acc_in)
    mx, my = mouth
    for (x, y) in pin:
        d = math.hypot(x - mx, y - my)
        b = t_start + d / sp_in + 0.12 * rng()
        big = math.exp(-d / 7.0)
        out.append(dict(co=(x, y, RB.FLOOR), birth=b, size=0.42 + 0.45 * rng() + 0.8 * big * rng(),
                        var=int(rng() * 4) % 4, yaw=rng() * 6.283, tilt=((rng() - 0.5) * 0.35, (rng() - 0.5) * 0.35, 0),
                        hue=(0.05 * x + 0.03 * y + 0.25 * rng()) % 1.0))
    # when the wave reaches the window sill (its nearest point) and the slot
    t_win = t_start + math.hypot(max(wx0, min(wx1, mx)) - mx, Y0 - my) / sp_in
    t_slot = t_start + math.hypot(X0 - mx, RB.SLOT_C.y - my) / sp_in + 0.2
    # --- on the window flap (the ramp)
    for k in range(70):
        u, v = rng(), rng()
        p = flap_pts(u, v)
        b = t_win + 0.05 + v * 10.5 / sp_ramp + 0.1 * rng()
        out.append(dict(co=tuple(p), birth=b, size=0.6 + 0.7 * rng(), var=int(rng() * 4) % 4, yaw=rng() * 6.283,
                        tilt=((rng() - 0.5) * 0.3, (rng() - 0.5) * 0.3, 0), hue=(0.05 * p[0] + 0.03 * p[1] + 0.25 * rng()) % 1.0))
    ramp_end = flap_pts(0.5, 1.0)
    t_ramp_end = t_win + 10.5 / sp_ramp
    # --- on the desk, spreading from the ramp's far edge and from the slot

    def acc_out(p):
        x, y = p
        if X0 - 0.4 < x < X1 + 0.4 and Y0 - 0.4 < y < Y1 + 0.4:
            return False
        if y > 3.0:
            return False
        if wx0 - 0.5 < x < wx1 + 0.5 and ramp_end.y - 0.3 < y < Y0:
            return False                  # under the flap
        return not any(f(x, y) for f in exclude_out)
    pout = _poisson(rng, 9000, lambda: (-55 + 95 * rng(), -48 + 51 * rng()), 1.3, acc_out)
    sx, sy = X0 - 0.2, RB.SLOT_C.y
    for (x, y) in pout:
        d_ramp = math.hypot(x - ramp_end.x, y - ramp_end.y)
        d_win = math.hypot(x - max(wx0, min(wx1, x)), y - (Y0 - 0.5)) if y < Y0 else 1e9
        d_slot = math.hypot(x - sx, y - sy)
        cands = [t_ramp_end + d_ramp / sp_out, t_win + 0.3 + d_win / sp_out, t_slot + d_slot / sp_out]
        b = min(cands)
        dmin = min(d_ramp, d_slot, d_win)
        keep = math.exp(-dmin / 12.0)
        if rng() > keep:
            continue
        out.append(dict(co=(x, y, 0.0), birth=b + 0.15 * rng(), size=0.5 + 0.65 * rng() + 0.5 * math.exp(-dmin / 6) * rng(),
                        var=int(rng() * 4) % 4, yaw=rng() * 6.283, tilt=((rng() - 0.5) * 0.3, (rng() - 0.5) * 0.3, 0),
                        hue=(0.05 * x + 0.03 * y + 0.25 * rng()) % 1.0))
    return out


def build_field(coll, pts, protos_coll, name='shrooms'):
    me = bpy.data.meshes.new(name)
    me.from_pydata([p['co'] for p in pts], [], [])
    for nm, kind, key in (('birth', 'FLOAT', 'birth'), ('size', 'FLOAT', 'size'), ('yaw', 'FLOAT', 'yaw'),
                          ('hue', 'FLOAT', 'hue'), ('var', 'INT', 'var'), ('tilt', 'FLOAT_VECTOR', 'tilt')):
        a = me.attributes.new(nm, kind, 'POINT')
        vals = [p[key] for p in pts]
        if kind == 'FLOAT_VECTOR':
            a.data.foreach_set('vector', [c for v in vals for c in v])
        elif kind == 'INT':
            a.data.foreach_set('value', vals)
        else:
            a.data.foreach_set('value', vals)
    ob = bpy.data.objects.new(name, me)
    coll.objects.link(ob)
    g = growth_tree(protos_coll)
    mod = modifier(ob, g, 'grow')
    return ob, mod
