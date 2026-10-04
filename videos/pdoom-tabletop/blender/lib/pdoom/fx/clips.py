"""Paperclips: the mesh, the brushed-steel material, static piles, the rigid-body avalanche, and instanced seas.

    from pdoom.fx import clips
    ob = clips.clip('clip.hero', loc=(10, 0, 0.05), rz=30)          # one hero clip (lod 0)
    clips.pile('pile', center=(0, 0, 0), radius=12, height=4, count=2500)   # static heap (GN instances)
    av = clips.avalanche('drawer', count=4000, box=((-15, -10, 2), (15, 10, 12)), t0=96.84, ...)
    clips.sea('sea', size=(160, 80), level=[(96.84, 0), (100.7, 25)], ...)  # rising flood of instanced clips

A Gem clip: 3.3 cm long, 0.85 cm wide, 0.9 mm steel wire bent into three U-turns (two nested loops). The mesh is a
tube swept along that centreline, in the XY plane, centred on the origin, long axis X.
"""
from __future__ import annotations

import math
import random
import time

import bmesh
import bpy
from mathutils import Euler, Matrix, Vector

from .. import kit
from . import log
from ..timing import FPS
from . import _nodes as N

WIRE_R = 0.045          # 0.9 mm wire
LENGTH = 3.3            # outer length, cm
HALF = LENGTH / 2 - WIRE_R
COLLIDE_T = 0.16        # rigid-body box thickness (the pile's loose "fluff"; the wire is 0.09)

# LOD: (tube sides, segments per 180-degree bend)
LODS = {0: (12, 20), 1: (6, 9), 2: (4, 5), 3: (3, 3)}


def centreline(half: float = HALF) -> list[tuple[float, float, float]]:
    """The Gem clip's wire path (cm), from the inner free end to the outer free end."""
    R = 0.38                                  # outer bend (right end)
    y1, y2, y3, y4 = -0.13, 0.17, -R, R       # inner leg, middle leg, outer bottom, outer top
    rA = (y2 - y1) / 2                        # inner bend (right, nested)
    rB = (y2 - y3) / 2                        # left bend
    xC = half - R
    xA = half - 0.25 - rA
    xB = -half + rB
    pieces = [
        ('L', (-0.55, y1), (xA, y1)),
        ('A', (xA, (y1 + y2) / 2), rA, -90, 90),
        ('L', (xA, y2), (xB, y2)),
        ('A', (xB, (y2 + y3) / 2), rB, 90, 270),
        ('L', (xB, y3), (xC, y3)),
        ('A', (xC, 0.0), R, -90, 90),
        ('L', (xC, y4), (-1.05, y4)),
    ]
    return pieces


def _path(segs_per_bend: int) -> list[Vector]:
    pts: list[Vector] = []
    for p in centreline():
        if p[0] == 'L':
            a, b = Vector((*p[1], 0)), Vector((*p[2], 0))
            n = max(1, int((b - a).length / 0.6))
            for i in range(n + 1):
                pts.append(a.lerp(b, i / n))
        else:
            c, r, a0, a1 = p[1], p[2], p[3], p[4]
            for i in range(segs_per_bend + 1):
                a = math.radians(a0 + (a1 - a0) * i / segs_per_bend)
                pts.append(Vector((c[0] + r * math.cos(a), c[1] + r * math.sin(a), 0)))
    out = [pts[0]]
    for q in pts[1:]:
        if (q - out[-1]).length > 1e-5:
            out.append(q)
    # a real clip is not perfectly flat: the free ends lift a hair
    n = len(out)
    for i, q in enumerate(out):
        u = i / (n - 1)
        q.z = 0.035 * (max(0, 0.12 - u) / 0.12) ** 2 + 0.025 * (max(0, u - 0.9) / 0.1) ** 2
    return out


def clip_mesh(lod: int = 1, *, name: str | None = None, collide_pad: bool = True) -> bpy.types.Mesh:
    """The paperclip mesh (cached per lod). collide_pad adds two loose vertices at z = +-COLLIDE_T/2 so a BOX
    rigid-body shape gets the pile's effective thickness (loose vertices never render)."""
    name = name or f'paperclip.lod{lod}'
    if name in bpy.data.meshes:
        return bpy.data.meshes[name]
    sides, segs = LODS[lod]
    path = _path(segs)
    bm = bmesh.new()
    uv = bm.loops.layers.uv.new('UVMap')
    rings = []
    total = sum((path[i + 1] - path[i]).length for i in range(len(path) - 1))
    s_acc = [0.0]
    for i in range(len(path) - 1):
        s_acc.append(s_acc[-1] + (path[i + 1] - path[i]).length)
    Z = Vector((0, 0, 1))
    for i, p in enumerate(path):
        if i == 0:
            t = path[1] - path[0]
        elif i == len(path) - 1:
            t = path[-1] - path[-2]
        else:
            t = (path[i + 1] - path[i - 1])
        t.normalize()
        b = t.cross(Z).normalized()
        n = b.cross(t).normalized()
        ring = []
        for k in range(sides):
            a = 2 * math.pi * (k + 0.5) / sides
            ring.append(bm.verts.new(p + WIRE_R * (math.cos(a) * b + math.sin(a) * n)))
        rings.append(ring)
    for i in range(len(rings) - 1):
        for k in range(sides):
            k2 = (k + 1) % sides
            f = bm.faces.new((rings[i][k], rings[i + 1][k], rings[i + 1][k2], rings[i][k2]))
            f.smooth = True
            u0, u1 = s_acc[i] / total, s_acc[i + 1] / total
            for loop, (uu, vv) in zip(f.loops, ((u0, k / sides), (u1, k / sides), (u1, (k + 1) / sides),
                                                 (u0, (k + 1) / sides))):
                loop[uv].uv = (uu, vv)
    for ring in (rings[0], rings[-1]):
        f = bm.faces.new(list(reversed(ring)) if ring is rings[0] else ring)
        f.smooth = False
    if collide_pad:
        bm.verts.new((0, 0, COLLIDE_T / 2))
        bm.verts.new((0, 0, -COLLIDE_T / 2))
    bm.normal_update()
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    me.materials.append(material())
    return me


# ------------------------------------------------------------------------------------------------ material

def material(name: str = 'clip.steel', *, tint='#C9CED6', rough=(0.16, 0.32), coloured: float = 0.0):
    """Brushed steel: metallic, roughness streaked ALONG the wire (UV u) and varied per clip (Object/instance
    random), a faint per-clip tint. coloured: fraction of clips that are vinyl-coated (red/blue/yellow/green)."""
    if name in bpy.data.materials:
        return bpy.data.materials[name]
    m = bpy.data.materials.new(name)
    nt = m.node_tree
    b = nt.nodes.get('Principled BSDF')
    L = nt.links
    info = nt.nodes.new('ShaderNodeObjectInfo')
    uvn = nt.nodes.new('ShaderNodeUVMap')
    # streaks along the wire: noise stretched in u
    mapn = nt.nodes.new('ShaderNodeMapping')
    mapn.inputs['Scale'].default_value = (220.0, 3.0, 1.0)
    L.new(uvn.outputs['UV'], mapn.inputs['Vector'])
    noi = nt.nodes.new('ShaderNodeTexNoise')
    noi.inputs['Scale'].default_value = 1.0
    noi.inputs['Detail'].default_value = 6.0
    noi.inputs['Roughness'].default_value = 0.7
    L.new(mapn.outputs['Vector'], noi.inputs['Vector'])
    # per-clip random offset of the streak pattern and roughness
    rr = nt.nodes.new('ShaderNodeMapRange')
    rr.inputs['To Min'].default_value = rough[0]
    rr.inputs['To Max'].default_value = rough[1]
    mixr = nt.nodes.new('ShaderNodeMath')
    mixr.operation = 'MULTIPLY_ADD'
    L.new(noi.outputs['Fac'], mixr.inputs[0])
    mixr.inputs[1].default_value = 0.6
    L.new(info.outputs['Random'], mixr.inputs[2])
    L.new(mixr.outputs[0], rr.inputs['Value'])
    rr.inputs['From Min'].default_value = 0.2
    rr.inputs['From Max'].default_value = 1.4
    L.new(rr.outputs['Result'], b.inputs['Roughness'])
    # colour: steel with a faint warm/cool per-clip tint
    ramp = nt.nodes.new('ShaderNodeValToRGB')
    cr = ramp.color_ramp
    cr.elements[0].position, cr.elements[0].color = 0.0, kit.srgb('#BFC4CC')
    cr.elements[1].position, cr.elements[1].color = 1.0, kit.srgb('#D4D2CC')
    L.new(info.outputs['Random'], ramp.inputs['Fac'])
    col_out = ramp.outputs['Color']
    metal_out = None
    if coloured > 0:
        # vinyl-coated clips: pick by a second hash of Random
        h = nt.nodes.new('ShaderNodeMath')
        h.operation = 'FRACT'
        hm = nt.nodes.new('ShaderNodeMath')
        hm.operation = 'MULTIPLY'
        hm.inputs[1].default_value = 97.13
        L.new(info.outputs['Random'], hm.inputs[0])
        L.new(hm.outputs[0], h.inputs[0])
        vinyl = nt.nodes.new('ShaderNodeValToRGB')
        vr = vinyl.color_ramp
        vr.interpolation = 'CONSTANT'
        vr.elements[0].color = kit.srgb('#D2382E')
        vr.elements[1].position, vr.elements[1].color = 0.25, kit.srgb('#2F6FD0')
        e = vr.elements.new(0.5)
        e.color = kit.srgb('#F2C230')
        e = vr.elements.new(0.75)
        e.color = kit.srgb('#3AA35B')
        L.new(h.outputs[0], vinyl.inputs['Fac'])
        is_c = nt.nodes.new('ShaderNodeMath')
        is_c.operation = 'LESS_THAN'
        is_c.inputs[1].default_value = coloured
        h2 = nt.nodes.new('ShaderNodeMath')
        h2.operation = 'FRACT'
        hm2 = nt.nodes.new('ShaderNodeMath')
        hm2.operation = 'MULTIPLY'
        hm2.inputs[1].default_value = 13.71
        L.new(info.outputs['Random'], hm2.inputs[0])
        L.new(hm2.outputs[0], h2.inputs[0])
        L.new(h2.outputs[0], is_c.inputs[0])
        mixc = nt.nodes.new('ShaderNodeMix')
        mixc.data_type = 'RGBA'
        sk = {s.identifier: s for s in mixc.inputs}
        L.new(is_c.outputs[0], sk['Factor_Float'])
        L.new(ramp.outputs['Color'], sk['A_Color'])
        L.new(vinyl.outputs['Color'], sk['B_Color'])
        col_out = next(s for s in mixc.outputs if s.identifier == 'Result_Color')
        inv = nt.nodes.new('ShaderNodeMath')
        inv.operation = 'SUBTRACT'
        inv.inputs[0].default_value = 1.0
        L.new(is_c.outputs[0], inv.inputs[1])
        metal_out = inv.outputs[0]
        coat = nt.nodes.new('ShaderNodeMath')
        coat.operation = 'MULTIPLY'
        coat.inputs[1].default_value = 0.8
        L.new(is_c.outputs[0], coat.inputs[0])
        L.new(coat.outputs[0], b.inputs['Coat Weight'])
    L.new(col_out, b.inputs['Base Color'])
    if metal_out is not None:
        L.new(metal_out, b.inputs['Metallic'])
    else:
        b.inputs['Metallic'].default_value = 1.0
    m.diffuse_color = kit.srgb(tint)
    m.metallic = 1.0
    m.roughness = 0.25
    return m


# ------------------------------------------------------------------------------------------------ single clips


def clip(name: str = 'clip', loc=(0, 0, 0), *, rz: float = 0.0, rot=None, lod: int = 0, coll=None,
         m=None) -> bpy.types.Object:
    """One paperclip object lying flat (rz: degrees about Z) or with a full rotation (radians Euler) rot."""
    me = clip_mesh(lod)
    ob = bpy.data.objects.new(name, me)
    (coll or bpy.context.scene.collection).objects.link(ob)
    z = WIRE_R + 0.0 if rot is None else 0.0
    ob.location = (loc[0], loc[1], loc[2] + z)
    ob.rotation_euler = rot if rot is not None else (0, 0, math.radians(rz))
    if m is not None:
        ob.material_slots[0].link = 'OBJECT'
        ob.material_slots[0].material = m
    return ob


# ------------------------------------------------------------------------------------------------ rigid bodies


def _proto(name: str, lod: int, coll, *, mass, friction, bounce, m=None):
    from . import rigid
    me = clip_mesh(lod)
    ob = bpy.data.objects.new(name, me)
    coll.objects.link(ob)
    if m is not None:
        ob.material_slots[0].link = 'OBJECT'
        ob.material_slots[0].material = m
    rb = rigid.active(ob, mass=mass, shape='BOX', friction=friction, bounce=bounce, damping=(0.1, 0.25),
                      margin=0.02)
    rb.deactivate_linear_velocity = 0.6
    rb.deactivate_angular_velocity = 0.8
    return ob


def _frame(direction):
    """Orthonormal emission frame: d (out of the source), u (across, horizontal if possible), w = d x u."""
    d = Vector(direction).normalized()
    ref = Vector((0, 0, 1)) if abs(d.z) < 0.9 else Vector((1, 0, 0))
    u = ref.cross(d).normalized()
    w = d.cross(u).normalized()
    return d, u, w


def _profile(kind, n_frames: int) -> list[float]:
    xs = [(i + 0.5) / n_frames for i in range(n_frames)]
    if kind == 'burst':
        ws = [math.exp(-x / 0.3) + 0.15 for x in xs]
    elif kind == 'flood':
        ws = [1.0 + 1.5 * math.exp(-x / 0.12) - 0.6 * max(0.0, x - 0.8) / 0.2 for x in xs]
    elif kind == 'steady':
        ws = [1.0 for _ in xs]
    elif kind == 'swell':
        ws = [math.sin(math.pi * x) ** 0.7 + 0.05 for x in xs]
    elif callable(kind):
        ws = [max(0.0, float(kind(x))) for x in xs]
    else:
        raise ValueError(kind)
    s = sum(ws)
    return [w / s for w in ws]


def avalanche(name: str = 'avalanche', *, count: int = 4000, t0: float, duration: float = 1.5,
              source=((0.0, 0.0, 5.0), (20.0, 4.0)), direction=(0.0, -1.0, 0.4), speed=(80.0, 140.0),
              spread: float = 18.0, spin: float = 12.0, profile='flood', fill: int = 0, fill_box=None,
              preroll: float = 1.0, seed: int = 1, lod: int = 1, coll=None, mass: float = 0.002,
              friction: float = 0.45, bounce: float = 0.08, substeps: int = 30, m=None) -> dict:
    """THE SHOWCASE. `count` real rigid-body clips pour out of a source from song time t0 for `duration` s.

    source = (centre, (width, height)): the opening (a drawer mouth, a hole in a wall, a point if the size is ~0),
    facing `direction` (clips leave along it at `speed` cm/s, within a cone of `spread` degrees, tumbling at
    ~`spin` rad/s). profile: 'flood' (a burst, then a sustained pour), 'burst' (a burst that tails off), 'steady',
    'swell', or f(x in 0..1) -> weight.
    fill/fill_box: clips already lying in a container (e.g. the open drawer) at the scene start; they drop into
    fill_box = ((x0, y0, z0), (x1, y1, z1)) during a `preroll` before the scene's first frame and are at rest by it.
    The scene provides the colliders (rigid.passive) and calls fx.bake() / rigid.bake() at the end of build().
    Returns {'objects', 'emitted', 'filled', 'collection', 'release_frames'}.
    """
    from . import rigid
    rng = random.Random(seed)
    rigid.world(substeps=substeps, iterations=12, preroll=preroll if fill else 0.0)
    coll = coll or kit.collection(name)
    t_build = time.time()
    proto = _proto(f'{name}.clip', lod, coll, mass=mass, friction=friction, bounce=bounce, m=m)
    objs = [proto] + rigid.copies(proto, count + fill - 1, coll)
    emitted, filled = objs[:count], objs[count:]
    # ---- fill: a jittered lattice above the container floor, dropped during the pre-roll
    if filled:
        (x0, y0, z0), (x1, y1, z1) = fill_box
        nx = max(1, int((x1 - x0) / 3.7))
        ny = max(1, int((y1 - y0) / 1.1))
        per = nx * ny
        for i, o in enumerate(filled):
            ix, iy, iz = i % nx, (i // nx) % ny, i // per
            o.location = (x0 + (ix + 0.5) * (x1 - x0) / nx + rng.uniform(-0.2, 0.2),
                          y0 + (iy + 0.5) * (y1 - y0) / ny, z0 + 0.3 + iz * 0.55)
            o.rotation_euler = (rng.uniform(-0.6, 0.6), rng.uniform(-0.25, 0.25), rng.uniform(-0.3, 0.3))
        top = z0 + 0.3 + ((len(filled) - 1) // per) * 0.55
        if top > z1:
            log(f'avalanche {name}: fill lattice reaches z={top:.1f} above fill_box top {z1:.1f}')
    # ---- emission schedule: clips per frame
    d, u, w = _frame(direction)
    (c, (W, H)) = source
    c = Vector(c)
    F0 = int(round(t0 * FPS))
    nF = max(1, int(round(duration * FPS)))
    weights = _profile(profile, nF)
    counts, acc, done = [], 0.0, 0
    for wt in weights:
        acc += wt * count
        k = int(round(acc)) - done
        counts.append(k)
        done += k
    counts[-1] += count - done
    v_mean = 0.5 * (speed[0] + speed[1])
    D = max(1.0, v_mean / FPS)                       # slab depth: how far a clip travels in one frame
    cu, cw, cd = 3.6, 1.0, 1.0
    nu, nw, nd = max(1, int(W / cu)), max(1, int(H / cw)), max(1, int(D / cd))
    cells = [(a, b, e) for a in range(nu) for b in range(nw) for e in range(nd)]
    # the mouth can pass at most one clip per cell per frame: carry any excess over to later frames
    cap, carry, sched = len(cells), 0, []
    for n in counts:
        n += carry
        sched.append(min(n, cap))
        carry = n - sched[-1]
    while carry > 0:
        sched.append(min(carry, cap))
        carry -= sched[-1]
    if len(sched) > len(counts):
        log(f'avalanche {name}: the {W:g} x {H:g} cm mouth passes {cap} clips/frame; the pour runs '
            f'{len(sched) / FPS:.2f}s instead of {duration}s')
    rel_frames = []
    i = 0
    for k, n in enumerate(sched):
        if n <= 0:
            continue
        F = F0 + k
        order = cells[:]
        rng.shuffle(order)
        for j in range(n):
            a, b, e = order[j]
            pu = (-W / 2 + (a + 0.5) * W / nu + rng.uniform(-0.15, 0.15)) if W > 0.5 else rng.uniform(-0.3, 0.3)
            pw = (-H / 2 + (b + 0.5) * H / nw + rng.uniform(-0.15, 0.15)) if H > 0.5 else rng.uniform(-0.3, 0.3)
            pd = (e + 0.5) * D / nd
            pos = c + u * pu + w * pw + d * pd
            # direction inside a cone
            th = math.radians(spread) * math.sqrt(rng.random())
            ph = rng.uniform(0, 2 * math.pi)
            dv = (d * math.cos(th) + (u * math.cos(ph) + w * math.sin(ph)) * math.sin(th)).normalized()
            vel = dv * rng.uniform(*speed)
            # orientation: long axis along u (the cell), random roll about it and some yaw
            rot_m = Matrix((u, w, d)).transposed()          # local x=u, y=w, z=d
            rot = (rot_m.to_quaternion() @ Euler((rng.uniform(0, math.pi), 0, rng.uniform(-0.45, 0.45)))
                   .to_quaternion()).to_euler()
            sp = Vector((rng.gauss(0, spin), rng.gauss(0, spin), rng.gauss(0, spin)))
            o = emitted[i]
            park = (-250 + (i % 100) * 5.0, -250 + ((i // 100) % 100) * 5.0, -3000 - (i // 10000) * 5.0)
            rel_frames.append(rigid.launch(o, F / FPS, pos, vel, spin=sp, rot=rot, park=park))
            i += 1
    log(f'avalanche {name}: {count} emitted over {len(sched) / FPS:.2f}s from t={t0}, {fill} filled; set up in '
        f'{time.time() - t_build:.1f}s')
    return {'objects': objs, 'emitted': emitted, 'filled': filled, 'collection': coll,
            'release_frames': rel_frames}


# ------------------------------------------------------------------------------------------------ instanced clips


def proto(lod: int = 2, m=None) -> bpy.types.Object:
    """The hidden clip object that geometry-node fields instance (one per lod/material). Hidden from render: its
    instances still render."""
    name = f'clip.proto.lod{lod}' + (f'.{m.name}' if m is not None else '')
    ob = bpy.data.objects.get(name)
    if ob is not None:
        return ob
    ob = bpy.data.objects.new(name, clip_mesh(lod, collide_pad=False, name=f'paperclip.lod{lod}.vis'))
    kit.collection('fx.protos').objects.link(ob)
    ob.location = (0, 0, -10000)
    ob.hide_render = True
    if m is not None:
        ob.material_slots[0].link = 'OBJECT'
        ob.material_slots[0].material = m
    return ob


def _points_object(name: str, co, attrs: dict, coll=None) -> bpy.types.Object:
    """A mesh of loose vertices at co (N x 3) carrying point attributes {name: ('FLOAT'|'FLOAT_VECTOR', array)}."""
    import numpy as np
    co = np.asarray(co, dtype=np.float32).reshape(-1, 3)
    me = bpy.data.meshes.new(name)
    me.vertices.add(len(co))
    me.vertices.foreach_set('co', co.ravel())
    for nm, (typ, arr) in attrs.items():
        a = me.attributes.new(nm, typ, 'POINT')
        a.data.foreach_set('vector' if typ == 'FLOAT_VECTOR' else 'value',
                           np.asarray(arr, dtype=np.float32).ravel())
    me.update()
    ob = bpy.data.objects.new(name, me)
    (coll or bpy.context.scene.collection).objects.link(ob)
    return ob


def _attr(g, name: str, kind: str = 'FLOAT'):
    nd = g.node('GeometryNodeInputNamedAttribute', data_type=kind, inputs={'Name': name})
    return g.out(nd, 'Attribute')


def _rand_rot(rng, n, tilt: float):
    """n Euler rotations: random yaw, tilt (radians, std) about X/Y, random 180-degree flips."""
    import numpy as np
    rx = rng.normal(0, tilt, n) + np.where(rng.random(n) < 0.5, 0.0, math.pi)
    ry = rng.normal(0, tilt, n)
    rz = rng.uniform(0, 2 * math.pi, n)
    return np.stack([rx, ry, rz], 1)


def _static_tree(name: str, clip_ob):
    """Instance the clip on every point, rotation from attribute 'rot' (Euler), scale from 'scale'."""
    g = N.Tree(name)
    geo = g.input_geometry()
    inst = g.object_geo(clip_ob, as_instance=True, relative=False)
    rot = g.euler(_attr(g, 'rot', 'FLOAT_VECTOR'))
    sc = _attr(g, 'scale')
    g.output(g.instance(geo, inst, rotation=rot, scale=sc))
    return g


def pile(name: str = 'pile', *, center=(0.0, 0.0, 0.0), radius: float = 10.0, height: float = 4.0,
         count: int | None = None, seed: int = 1, lod: int = 1, coll=None, core: bool = True, m=None,
         shape: float = 1.6) -> bpy.types.Object:
    """A static heap of clips (geometry-node instances; nothing simulated). The heap surface is
    z = height * (1 - (r/radius)^shape); clips hug it within ~0.5 cm, tilted with it. count defaults to ~2.2 clips
    per cm^2 of heap footprint (full cover). core: a dark steel mound under the clips so no gaps show through.
    Cheap: thousands of instances build in < 1 s."""
    import numpy as np
    rng = np.random.default_rng(seed)
    area = math.pi * radius ** 2
    n = count or int(area * 2.2)
    r = radius * np.sqrt(rng.random(n))
    th = rng.uniform(0, 2 * math.pi, n)
    x, y = r * np.cos(th), r * np.sin(th)
    surf = height * (1 - (r / radius) ** shape)
    depth = np.abs(rng.normal(0, 0.35, n))
    z = np.maximum(surf - depth, 0.0) + WIRE_R
    # tilt clips with the heap slope
    dz = -height * shape * (r / radius) ** (shape - 1) / radius
    slope = np.arctan(-dz)
    rot = _rand_rot(rng, n, 0.14)
    rot[:, 0] += slope * np.sin(rot[:, 2] - th)
    rot[:, 1] += slope * np.cos(rot[:, 2] - th)
    co = np.stack([x + center[0], y + center[1], z + center[2]], 1)
    coll = coll or kit.collection(name)
    ob = _points_object(name, co, {'rot': ('FLOAT_VECTOR', rot), 'scale': ('FLOAT', np.ones(n))}, coll)
    N.modifier(ob, _static_tree(f'{name}.gn', proto(lod, m)), 'clips')
    if core and height > 0.5:
        _core(f'{name}.core', center, radius * 0.97, max(0.0, height - 0.45), shape, coll)
    log(f'pile {name}: {n} clips, r={radius} h={height}')
    return ob


def _core(name, center, radius, height, shape, coll):
    """A dark brushed-steel mound (the heap's hidden inside)."""
    bm = bmesh.new()
    rings, seg = 16, 48
    verts = []
    for i in range(rings + 1):
        rr = radius * i / rings
        zz = height * (1 - (rr / radius) ** shape) if radius > 0 else 0
        if i == 0:
            verts.append([bm.verts.new((center[0], center[1], center[2] + height))])
            continue
        verts.append([bm.verts.new((center[0] + rr * math.cos(2 * math.pi * k / seg),
                                    center[1] + rr * math.sin(2 * math.pi * k / seg), center[2] + zz))
                      for k in range(seg)])
    for k in range(seg):
        bm.faces.new((verts[0][0], verts[1][k], verts[1][(k + 1) % seg]))
    for i in range(1, rings):
        for k in range(seg):
            bm.faces.new((verts[i][k], verts[i + 1][k], verts[i + 1][(k + 1) % seg], verts[i][(k + 1) % seg]))
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    for p in me.polygons:
        p.use_smooth = True
    ob = bpy.data.objects.new(name, me)
    coll.objects.link(ob)
    ob.data.materials.append(kit.mat('clip.core', '#3A3D42', rough=0.45, metal=0.8))
    return ob


def sea(name: str = 'sea', *, area=((-80.0, -40.0), (80.0, 40.0)), base: float = 0.0, depth: float = 30.0,
        level=((0.0, 0.0),), density: float = 0.9, band: float = 1.6, drop: float = 3.0, origin=None,
        slope: float = 0.0, exclude=(), lod: int = 2, seed: int = 3, coll=None, m=None,
        interp: str = 'BEZIER', settle: float = 0.35) -> dict:
    """A rising flood of clips (geometry-node instances, no simulation): clips fill `area` (x0,y0)-(x1,y1) from
    height `base` up to the keyed level [(song t, height above base)], dropping into place as the level passes
    them (each drop takes ~`settle` s). Only a `band` (cm) under the surface is instanced, so the cost stays
    ~(area x band x density) instances.
    origin/slope: the level falls off by `slope` cm per cm away from origin (a mound spreading from a source).
    exclude: objects whose XY bounding boxes stay clear (a mug the flood surrounds). density: clips per cm^3.
    Returns {'object', 'modifier'}; to add levels later, key _nodes.key_input on 'Level' (t, h) AND on 'Lag'
    (t + settle, h)."""
    import numpy as np
    rng = np.random.default_rng(seed)
    (x0, y0), (x1, y1) = area
    n = int((x1 - x0) * (y1 - y0) * depth * density)
    x = rng.uniform(x0, x1, n)
    y = rng.uniform(y0, y1, n)
    z0 = rng.uniform(0, depth, n)
    keep = np.ones(n, bool)
    for ob in exclude:
        bb = [ob.matrix_world @ Vector(c) for c in ob.bound_box]
        bx0, bx1 = min(v.x for v in bb) - 0.6, max(v.x for v in bb) + 0.6
        by0, by1 = min(v.y for v in bb) - 0.6, max(v.y for v in bb) + 0.6
        bz1 = max(v.z for v in bb) - base
        keep &= ~((x > bx0) & (x < bx1) & (y > by0) & (y < by1) & (z0 < bz1))
    x, y, z0 = x[keep], y[keep], z0[keep]
    n = len(x)
    rot = _rand_rot(rng, n, 0.16)
    coll = coll or kit.collection(name)
    ob = _points_object(name, np.stack([x, y, z0 + base], 1),
                        {'rot': ('FLOAT_VECTOR', rot), 'z0': ('FLOAT', z0), 'scale': ('FLOAT', np.ones(n))}, coll)
    g = N.Tree(f'{name}.gn')
    geo = g.input_geometry()
    lv = g.param('Level', 'FLOAT', 0.0)
    lg = g.param('Lag', 'FLOAT', 0.0)
    bd = g.param('Band', 'FLOAT', band)
    dr = g.param('Drop', 'FLOAT', drop)
    sl = g.param('Slope', 'FLOAT', slope)
    org = g.param('Origin', 'VECTOR', tuple(origin or (0, 0, 0)))
    zz = _attr(g, 'z0')
    p = g.position()
    dxy = g.vec(p.x - org.x, p.y - org.y, 0.0)
    fall = sl * g.length(dxy)
    lvl = lv - fall
    lag = lg - fall
    hidden = g.bool_or(zz > lvl, zz < lvl - bd)
    # stable ids BEFORE the delete: instances take their motion-blur identity from 'id', and without it the instance
    # order shifts as the level passes clips, EEVEE pairs the wrong clips between blur steps and a rising sea smears
    # into fur (found in paperclips)
    geo = g.out(g.node('GeometryNodeSetID', inputs={'Geometry': geo, 'ID': g.index()}))
    geo = g.delete(geo, hidden)
    # clips between the lagged level (settle s ago) and the level are still dropping in; below it they rest
    fill = g.clamp((lvl - zz) / g.max(lvl - lag, 0.05))
    un = 1.0 - fill
    geo = g.set_position(geo, offset=g.vec(0.0, 0.0, dr * un * un))
    wob = g.vec(un * 0.7, un * 0.45, 0.0)
    rot = g.euler(_attr(g, 'rot', 'FLOAT_VECTOR') + wob)
    inst = g.object_geo(proto(lod, m), as_instance=True, relative=False)
    g.output(g.instance(geo, inst, rotation=rot, scale=_attr(g, 'scale')))
    mod = N.modifier(ob, g, 'sea')
    for t, h in level:
        N.key_input(ob, mod, 'Level', t, h, interp=interp)
        N.key_input(ob, mod, 'Lag', t + settle, h, interp=interp)
    log(f'sea {name}: {n} candidate clips over {(x1 - x0):g} x {(y1 - y0):g} x {depth:g} cm')
    return {'object': ob, 'modifier': mod}


def field(name: str = 'field', *, surface, density: float = 0.3, scale: float = 1.0, layers: int = 1,
          lift: float = 0.0, lod: int = 3, seed: int = 5, coll=None, m=None, tilt: float = 0.35) -> dict:
    """Static dressing: clips scattered over any mesh `surface` (instances generated in geometry nodes, so millions
    are cheap to build). density: clips per cm^2 of surface PER LAYER at scale 1 (0.36 = edge-to-edge cover);
    scale: clip size (use > 1 in far shots where one clip must still read). Layers stack 0.2*scale cm apart.
    Returns {'object', 'modifier'}. Keyable inputs: 'Density', 'Scale'."""
    coll = coll or kit.collection(name)
    me = bpy.data.meshes.new(name)
    ob = bpy.data.objects.new(name, me)
    coll.objects.link(ob)
    g = N.Tree(f'{name}.gn')
    g.input_geometry()
    dens = g.param('Density', 'FLOAT', density)
    scl = g.param('Scale', 'FLOAT', scale)
    surf = g.object_geo(surface, relative=True)
    parts = []
    for L in range(layers):
        nd = g.node('GeometryNodeDistributePointsOnFaces', distribute_method='RANDOM',
                    inputs={'Mesh': surf, 'Density': dens / (scl * scl), 'Seed': seed + 17 * L})
        pts = g.out(nd, 'Points')
        nrm = g.out(nd, 'Normal')
        i = g.out(g.node('GeometryNodeInputID'))
        rot = g.rotate(g.align(nrm, 'Z'), g.euler(g.vec(g.rand(-tilt, tilt, i, seed + 2 + L),
                                                        g.rand(-tilt, tilt, i, seed + 3 + L),
                                                        g.rand(0.0, 6.2832, i, seed + 1 + L))))
        pts = g.set_position(pts, offset=nrm * (scl * (WIRE_R + 0.2 * L + lift)))
        inst = g.object_geo(proto(lod, m), as_instance=True, relative=False)
        parts.append(g.instance(pts, inst, rotation=rot, scale=scl))
    g.output(g.join(*parts) if len(parts) > 1 else parts[0])
    mod = N.modifier(ob, g, 'field')
    return {'object': ob, 'modifier': mod}


def pour(name: str = 'pour', *, source, t0: float, t1: float, rate: float = 400.0, direction=(0, -1, 0.2),
         speed=(40.0, 90.0), cone: float = 20.0, scale: float = 1.0, lod: int = 2, floor: float | None = 0.0,
         seed: int = 8, coll=None, m=None, spin: float = 14.0):
    """A stateless pour of tumbling clips (no rigid bodies: cheap at any count, e.g. clips spilling from the
    house's windows in the finale): `rate` clips/s from t0 to t1 out of source = (centre, (w, h)) facing
    direction; they land flat on the floor and stay (they don't pile: add a sea() under them). scale > 1 for far
    shots. Returns the particle object."""
    from . import particles
    return particles.stream(name, proto(lod, m), source=source, t0=t0, t1=t1, rate=rate, direction=direction,
                            speed=speed, cone=cone, scale=scale, floor=floor, seed=seed, coll=coll, spin=spin,
                            rest_lift=WIRE_R * scale)


def ball(name: str = 'clip.earth', *, center=(0.0, 0.0, 0.0), radius: float = 30.0, scale: float = 1.0,
         layers: int = 3, density: float = 1.0, lod: int = 2, progress=None, grain: float = 0.15,
         seed: int = 9, coll=None, m=None, core_mat=None) -> dict:
    """A planet of clips: a sphere of `radius` covered by `layers` of clips (size `scale`) over a dark core sphere.
    progress: [(song t, 0..1)] keys the conversion: clips appear in growing patches (noise of feature size
    ~1/grain cm) until the sphere is all clips; the core shows where there are none yet (give it an Earth material
    via core_mat for 'the Earth turning into paperclips'). Returns {'object', 'modifier', 'core'}."""
    coll = coll or kit.collection(name)
    bpy.ops.mesh.primitive_ico_sphere_add(radius=radius, subdivisions=5, location=center)
    shell = bpy.context.object
    shell.name = f'{name}.surface'
    kit.link(shell, coll)
    shell.hide_render = True
    core = kit.sphere(f'{name}.core', radius - 0.3 * scale, center, coll=coll, subdiv=5)
    core.data.materials.append(core_mat or kit.mat('clip.core', '#3A3D42', rough=0.45, metal=0.8))
    me = bpy.data.meshes.new(name)
    ob = bpy.data.objects.new(name, me)
    coll.objects.link(ob)
    g = N.Tree(f'{name}.gn')
    g.input_geometry()
    prog = g.param('Progress', 'FLOAT', 1.0 if progress is None else 0.0)
    surf = g.object_geo(shell, relative=True)
    parts = []
    for L in range(layers):
        nd = g.node('GeometryNodeDistributePointsOnFaces', distribute_method='RANDOM',
                    inputs={'Mesh': surf, 'Density': density / (scale * scale), 'Seed': seed + 31 * L})
        pts = g.out(nd, 'Points')
        nrm = g.out(nd, 'Normal')
        i = g.out(g.node('GeometryNodeInputID'))
        # conversion threshold: patchy noise + per-clip jitter; the outer layer converts last
        thr = g.noise(g.position() * grain, 1.0, 3.0) * 0.8 + g.rand(0.0, 0.2, i, seed + 5) + (0.08 * L - 0.1)
        pts = g.out(g.node('GeometryNodeSetID', inputs={'Geometry': pts, 'ID': g.index()}))  # stable ids for motion blur
        pts = g.delete(pts, thr > prog)
        rot = g.rotate(g.align(nrm, 'Z'), g.euler(g.vec(g.rand(-0.35, 0.35, i, seed + 2 + L),
                                                        g.rand(-0.35, 0.35, i, seed + 3 + L),
                                                        g.rand(0.0, 6.2832, i, seed + 1 + L))))
        pts = g.set_position(pts, offset=nrm * (scale * (WIRE_R + 0.18 * L)))
        inst = g.object_geo(proto(lod, m), as_instance=True, relative=False)
        parts.append(g.instance(pts, inst, rotation=rot, scale=scale))
    g.output(g.join(*parts) if len(parts) > 1 else parts[0])
    mod = N.modifier(ob, g, 'ball')
    for t, v in (progress or ()):
        N.key_input(ob, mod, 'Progress', t, v)
    return {'object': ob, 'modifier': mod, 'core': core}
