"""Particles as pure functions of song time: Python draws every particle's birth, launch point, velocity, drag and
landing time from a fixed seed; a geometry-nodes tree evaluates the closed-form motion (gravity + linear drag,
resting on a floor) at the frame's song time. Nothing is simulated or baked, so any frame renders on its own and
motion blur samples the exact path.

    from pdoom.fx import particles as P
    P.sparks_along('agi', points=d.cable.pts, starts=[3.68, 4.06, 4.36], travel=0.4)   # sparks run along a cable
    P.burst('pop', center=(8, -4, 6), t0=25.58, count=300)                              # a spark burst
    P.confetti('foom.confetti', center=(8, -4, 8), t0=25.6, count=600)                  # paper confetti
    P.fuse('fuse', points=path, t0=102.2, t1=104.5)                                     # a burning fuse
    P.motes('motes', box=((-20, -20, 0), (20, 20, 40)), count=800)                      # dust in a light cone

Motion: v' = g - k v  =>  p(a) = p0 + v0 F + (g/k)(a - F),  F = (1 - e^(-k a)) / k, frozen at the landing age.
Units: cm, s; g = 981 cm/s^2 (gravity=1). Sparks render as emissive capsules stretched along their velocity (a
streak, independent of motion blur); colour cools from white-yellow to red over each spark's life.
"""
from __future__ import annotations

import math

import bpy
from mathutils import Vector

from .. import kit
from . import _nodes as N
from . import log

G = 981.0


# ------------------------------------------------------------------------------------------------ helpers


def _cloud(name: str, attrs: dict, coll=None) -> bpy.types.Object:
    """A mesh of loose vertices (positions from attrs['p0']) carrying float / vector point attributes."""
    import numpy as np
    p0 = np.asarray(attrs['p0'], dtype=np.float32).reshape(-1, 3)
    me = bpy.data.meshes.new(name)
    me.vertices.add(len(p0))
    me.vertices.foreach_set('co', p0.ravel())
    for nm, arr in attrs.items():
        arr = np.asarray(arr, dtype=np.float32)
        vec = arr.ndim == 2
        a = me.attributes.new(nm, 'FLOAT_VECTOR' if vec else 'FLOAT', 'POINT')
        a.data.foreach_set('vector' if vec else 'value', arr.ravel())
    me.update()
    ob = bpy.data.objects.new(name, me)
    (coll or kit.collection('fx.particles')).objects.link(ob)
    return ob


def _land_age(p0z, v0z, k, g, floor, life):
    """Age at which z(a) reaches floor (vectorised Newton on the drag trajectory); life if never."""
    import numpy as np
    a = np.clip(life, 1e-3, None).astype(np.float64)

    def z(a):
        F = (1 - np.exp(-k * a)) / k
        return p0z + v0z * F - (g / k) * (a - F)

    ok = z(a) < floor
    # bisection on [0, life] for the ones that do land
    lo = np.zeros_like(a)
    hi = a.copy()
    for _ in range(40):
        mid = 0.5 * (lo + hi)
        below = z(mid) < floor
        hi = np.where(below, mid, hi)
        lo = np.where(below, lo, mid)
    return np.where(ok, hi, life)


def _attr(g, name, kind='FLOAT'):
    nd = g.node('GeometryNodeInputNamedAttribute', data_type=kind, inputs={'Name': name})
    return g.out(nd, 'Attribute')


def _motion(g, gscale: float):
    """Shared maths: returns (alive, age01, position, velocity) S sockets from the point attributes."""
    t = g.time()
    birth, life, k, aland = _attr(g, 'birth'), _attr(g, 'life'), _attr(g, 'k'), _attr(g, 'aland')
    p0, v0 = _attr(g, 'p0', 'FLOAT_VECTOR'), _attr(g, 'v0', 'FLOAT_VECTOR')
    a = t - birth
    alive = g.bool_and(a >= 0.0, a < life)
    ae = g.max(g.min(a, aland), 0.0)
    E = g.exp(-1.0 * k * ae)
    F = (1.0 - E) / k
    gk = g.vec(0.0, 0.0, -G * gscale) / k
    pos = p0 + v0 * F + gk * (ae - F)
    landed = a > aland
    vel = g.switch(landed, gk + (v0 - gk) * E, (0.0, 0.0, 0.0), kind='VECTOR')
    age01 = g.clamp(a / life)
    return alive, age01, pos, vel, landed


def _spark_mat(name: str, hot: str = '#FFF3C4', mid: str = '#FFB24A', cool: str = '#D2382E',
               strength: float = 40.0):
    """Emission from the instancer attribute 'heat' (0 hot .. 1 dead): white-yellow -> orange -> red -> dark."""
    if name in bpy.data.materials:
        return bpy.data.materials[name]
    m = bpy.data.materials.new(name)
    nt = m.node_tree
    nt.nodes.clear()
    out = nt.nodes.new('ShaderNodeOutputMaterial')
    em = nt.nodes.new('ShaderNodeEmission')
    at = nt.nodes.new('ShaderNodeAttribute')
    at.attribute_type = 'INSTANCER'
    at.attribute_name = 'heat'
    ramp = nt.nodes.new('ShaderNodeValToRGB')
    cr = ramp.color_ramp
    cr.elements[0].position, cr.elements[0].color = 0.0, kit.srgb(hot)
    cr.elements[1].position, cr.elements[1].color = 1.0, (0.05, 0.0, 0.0, 1.0)
    e = cr.elements.new(0.3)
    e.color = kit.srgb(mid)
    e = cr.elements.new(0.7)
    e.color = kit.srgb(cool)
    nt.links.new(at.outputs['Fac'], ramp.inputs['Fac'])
    nt.links.new(ramp.outputs['Color'], em.inputs['Color'])
    # strength falls as it cools
    inv = nt.nodes.new('ShaderNodeMath')
    inv.operation = 'SUBTRACT'
    inv.inputs[0].default_value = 1.0
    nt.links.new(at.outputs['Fac'], inv.inputs[1])
    pw = nt.nodes.new('ShaderNodeMath')
    pw.operation = 'POWER'
    pw.inputs[1].default_value = 2.0
    nt.links.new(inv.outputs[0], pw.inputs[0])
    mul = nt.nodes.new('ShaderNodeMath')
    mul.operation = 'MULTIPLY'
    mul.inputs[1].default_value = strength
    nt.links.new(pw.outputs[0], mul.inputs[0])
    nt.links.new(mul.outputs[0], em.inputs['Strength'])
    nt.links.new(em.outputs['Emission'], out.inputs['Surface'])
    m.diffuse_color = kit.srgb(mid)
    return m


def _unit_sphere(name='fx.spark.unit', subdiv=1):
    ob = bpy.data.objects.get(name)
    if ob is not None:
        return ob
    bpy.ops.mesh.primitive_ico_sphere_add(radius=1.0, subdivisions=subdiv, location=(0, 0, -10000))
    ob = bpy.context.object
    ob.name = name
    kit.link(ob, kit.collection('fx.protos'))
    ob.hide_render = True
    return ob


def _spark_tree(name: str, mat, *, gscale: float, streak: float, size: float):
    """Ballistic sparks as emissive capsules: radius size*(1-age)^0.5, stretched along velocity by streak (s)."""
    g = N.Tree(name)
    geo = g.input_geometry()
    alive, age01, pos, vel, landed = _motion(g, gscale)
    geo = g.out(g.node('GeometryNodeSetID', inputs={'Geometry': geo, 'ID': g.index()}))  # stable ids for motion blur
    geo = g.delete(geo, g.bool_not(alive))
    geo = g.set_position(geo, position=pos)
    geo = g.store(geo, 'heat', age01)
    r = _attr(g, 'size') * g.sqrt(1.0 - age01)
    speed = g.length(vel)
    half = speed * (0.5 * streak)
    rot = g.align(g.vop('ADD', vel, (0.0, 0.0, 1e-4)), 'Z')
    sc = g.vec(r, r, r + half)
    inst = g.instance(geo, g.object_geo(_unit_sphere(), as_instance=True, relative=False), rotation=rot, scale=sc)
    # pull the capsule back so its head sits at the particle
    inst = g.out(g.node('GeometryNodeTranslateInstances', inputs={'Instances': inst,
                                                                  'Translation': vel * (-0.5 * streak),
                                                                  'Local Space': False}))
    inst = g.set_material(inst, mat)
    g.output(inst)
    return g


# ------------------------------------------------------------------------------------------------ bursts


def burst(name: str = 'sparks', *, center, t0: float, count: int = 300, speed=(60.0, 220.0), direction=(0, 0, 1),
          cone: float = 180.0, gravity: float = 1.0, drag: float = 1.5, life=(0.3, 0.9), size: float = 0.06,
          emit: float = 0.04, floor: float | None = 0.0, streak: float = 0.018, seed: int = 1, coll=None,
          colors=('#FFF3C4', '#FFB24A', '#D2382E'), strength: float = 6.0) -> bpy.types.Object:
    """A burst of sparks from center at song time t0 (births spread over `emit` s): speeds in cm/s inside a cone of
    `cone` degrees around direction (180 = all round), linear drag `drag` (1/s), life range (s), radius `size` cm.
    They fall under gravity, stop on the floor (z) and cool out. Returns the particle object."""
    import numpy as np
    rng = np.random.default_rng(seed)
    n = count
    d = Vector(direction).normalized()
    ref = Vector((1, 0, 0)) if abs(d.x) < 0.9 else Vector((0, 1, 0))
    u = d.cross(ref).normalized()
    w = d.cross(u)
    cz = rng.uniform(math.cos(math.radians(min(cone, 180.0))), 1.0, n)
    phi = rng.uniform(0, 2 * math.pi, n)
    sz = np.sqrt(1 - cz ** 2)
    D = np.array(d)[None] * cz[:, None] + (np.array(u)[None] * np.cos(phi)[:, None] +
                                            np.array(w)[None] * np.sin(phi)[:, None]) * sz[:, None]
    v0 = D * rng.uniform(speed[0], speed[1], n)[:, None]
    p0 = np.array(center)[None].repeat(n, 0) + rng.normal(0, 0.15, (n, 3))
    birth = t0 + rng.uniform(0, emit, n)
    lf = rng.uniform(life[0], life[1], n)
    k = np.full(n, drag) * rng.uniform(0.8, 1.25, n)
    aland = _land_age(p0[:, 2], v0[:, 2], k, G * gravity, floor + size, lf) if floor is not None else lf
    ob = _cloud(name, {'p0': p0, 'v0': v0, 'birth': birth, 'life': lf, 'k': k, 'aland': aland,
                       'size': size * rng.uniform(0.6, 1.3, n)}, coll)
    mat = _spark_mat(f'{name}.mat', *colors, strength=strength)
    N.modifier(ob, _spark_tree(f'{name}.gn', mat, gscale=gravity, streak=streak, size=size), 'sparks')
    log(f'burst {name}: {n} sparks at t={t0:.3f}')
    return ob


# ------------------------------------------------------------------------------------------------ confetti


def _confetti_mat(name, colors):
    if name in bpy.data.materials:
        return bpy.data.materials[name]
    m = bpy.data.materials.new(name)
    nt = m.node_tree
    b = nt.nodes.get('Principled BSDF')
    at = nt.nodes.new('ShaderNodeAttribute')
    at.attribute_type = 'INSTANCER'
    at.attribute_name = 'cid'
    ramp = nt.nodes.new('ShaderNodeValToRGB')
    cr = ramp.color_ramp
    cr.interpolation = 'CONSTANT'
    n = len(colors)
    cr.elements[0].color = kit.srgb(colors[0])
    cr.elements[1].position, cr.elements[1].color = (n - 1) / n, kit.srgb(colors[-1])
    for i in range(1, n - 1):
        e = cr.elements.new(i / n)
        e.color = kit.srgb(colors[i])
    nt.links.new(at.outputs['Fac'], ramp.inputs['Fac'])
    nt.links.new(ramp.outputs['Color'], b.inputs['Base Color'])
    b.inputs['Roughness'].default_value = 0.45
    b.inputs['Sheen Weight'].default_value = 0.3
    b.inputs['Subsurface Weight'].default_value = 0.2
    m.use_backface_culling = False
    m.diffuse_color = kit.srgb(colors[0])
    return m


def _quad(name='fx.confetti.quad', w=1.0, h=0.6):
    ob = bpy.data.objects.get(name)
    if ob is not None:
        return ob
    me = bpy.data.meshes.new(name)
    me.from_pydata([(-w / 2, -h / 2, 0), (w / 2, -h / 2, 0), (w / 2, h / 2, 0), (-w / 2, h / 2, 0)], [],
                   [(0, 1, 2, 3)])
    ob = bpy.data.objects.new(name, me)
    kit.collection('fx.protos').objects.link(ob)
    ob.location = (0, 0, -10000)
    ob.hide_render = True
    return ob


def confetti(name: str = 'confetti', *, center, t0: float, count: int = 500, speed=(1000.0, 2200.0),
             direction=(0, 0, 1), cone: float = 55.0, drag: float = 45.0, sway: float = 2.5, spin: float = 9.0,
             size=(1.0, 0.6), emit: float = 0.06, life: float = 30.0, floor: float | None = 0.0, seed: int = 2,
             colors=('#D2382E', '#F2C230', '#2F6FD0', '#3AA35B', '#F2EBDD', '#E07B39', '#C86DD7'),
             coll=None) -> bpy.types.Object:
    """Paper confetti fired from center at song time t0 (a cone around direction) that flutters down: air drag
    `drag` 1/s (rise ~speed/drag cm; terminal fall g/drag ~ 22 cm/s at 45, like real confetti: fired fast,
    stopped by the air at once, then drifting down for a second or two), a sideways sway
    of `sway` cm, tumbling at ~`spin` rad/s; each piece lies flat where it lands and stays (life s).
    Returns the particle object."""
    import numpy as np
    rng = np.random.default_rng(seed)
    n = count
    d = Vector(direction).normalized()
    ref = Vector((1, 0, 0)) if abs(d.x) < 0.9 else Vector((0, 1, 0))
    u = d.cross(ref).normalized()
    w = d.cross(u)
    cz = rng.uniform(math.cos(math.radians(cone)), 1.0, n)
    phi = rng.uniform(0, 2 * math.pi, n)
    sz = np.sqrt(1 - cz ** 2)
    D = np.array(d)[None] * cz[:, None] + (np.array(u)[None] * np.cos(phi)[:, None] +
                                            np.array(w)[None] * np.sin(phi)[:, None]) * sz[:, None]
    v0 = D * rng.uniform(speed[0], speed[1], n)[:, None]
    p0 = np.array(center)[None].repeat(n, 0) + rng.normal(0, 0.4, (n, 3))
    birth = t0 + rng.uniform(0, emit, n)
    k = drag * rng.uniform(0.7, 1.4, n)
    lf = np.full(n, life)
    aland = _land_age(p0[:, 2], v0[:, 2], k, G, floor + 0.02, lf) if floor is not None else lf
    axis = rng.normal(0, 1, (n, 3))
    axis /= np.linalg.norm(axis, axis=1, keepdims=True)
    ob = _cloud(name, {'p0': p0, 'v0': v0, 'birth': birth, 'life': lf, 'k': k, 'aland': aland, 'axis': axis,
                       'w': rng.uniform(0.5, 1.0, n) * spin * np.where(rng.random(n) < 0.5, -1, 1),
                       'phase': rng.uniform(0, 2 * math.pi, n), 'fq': rng.uniform(1.5, 3.0, n),
                       'yaw': rng.uniform(0, 2 * math.pi, n), 'cid': rng.integers(0, len(colors), n) / len(colors)
                       + 0.5 / len(colors)}, coll)
    g = N.Tree(f'{name}.gn')
    geo = g.input_geometry()
    alive, age01, pos, vel, landed = _motion(g, 1.0)
    t = g.time()
    a = t - _attr(g, 'birth')
    aland = _attr(g, 'aland')
    ae = g.max(g.min(a, aland), 0.0)
    # sway grows as the piece slows down (after the launch), frozen on landing
    ph = _attr(g, 'phase') + ae * _attr(g, 'fq') * 6.2832
    grow = g.clamp(ae * 1.5)
    swayv = g.vec(g.sin(ph), g.cos(ph * 0.83), 0.0) * (sway * 1.0) * grow
    geo = g.out(g.node('GeometryNodeSetID', inputs={'Geometry': geo, 'ID': g.index()}))  # stable ids for motion blur
    geo = g.delete(geo, g.bool_not(alive))
    geo = g.set_position(geo, position=pos + swayv)
    geo = g.store(geo, 'cid', _attr(g, 'cid'))
    # tumbling in the air, lying flat (random yaw) once landed
    tumble = g.axis_angle(_attr(g, 'axis', 'FLOAT_VECTOR'), _attr(g, 'w') * ae)
    flat = g.euler(g.vec(0.0, 0.0, _attr(g, 'yaw')))
    rot = g.switch(landed, tumble, flat, kind='ROTATION')
    inst = g.instance(geo, g.object_geo(_quad(name=f'fx.confetti.quad.{size[0]:g}x{size[1]:g}', w=size[0], h=size[1]), as_instance=True, relative=False), rotation=rot)
    inst = g.set_material(inst, _confetti_mat(f'{name}.mat', colors))
    g.output(inst)
    N.modifier(ob, g, 'confetti')
    log(f'confetti {name}: {n} pieces at t={t0:.3f}')
    return ob


# ------------------------------------------------------------------------------------------------ streams of objects


def stream(name: str, instance, *, source, t0: float, t1: float, rate: float = 400.0, direction=(0, -1, 0),
           speed=(40.0, 90.0), cone: float = 20.0, drag: float = 0.3, spin: float = 12.0, scale: float = 1.0,
           floor: float | None = 0.0, life: float = 60.0, seed: int = 8, coll=None, flat_axis: str = 'Z',
           rest_lift: float = 0.05) -> bpy.types.Object:
    """A pour of tumbling objects (clips from a window, sugar cubes, bolts): `rate` per second from t0 to t1 out of
    source = (centre, (width, height)) facing `direction`, ballistic with light drag, tumbling at ~`spin` rad/s;
    each lands flat (its local flat_axis up, random yaw) on the floor and stays. Stateless: pair it with
    clips.sea() for the pile that grows under it. Returns the particle object."""
    import numpy as np
    rng = np.random.default_rng(seed)
    n = int(rate * (t1 - t0))
    (c, (W, H)) = source
    d = Vector(direction).normalized()
    ref = Vector((0, 0, 1)) if abs(d.z) < 0.9 else Vector((1, 0, 0))
    u = ref.cross(d).normalized()
    w = d.cross(u)
    birth = np.sort(rng.uniform(t0, t1, n))
    p0 = (np.array(c)[None] + np.array(u)[None] * rng.uniform(-W / 2, W / 2, n)[:, None] +
          np.array(w)[None] * rng.uniform(-H / 2, H / 2, n)[:, None])
    cz = rng.uniform(math.cos(math.radians(cone)), 1.0, n)
    phi = rng.uniform(0, 2 * math.pi, n)
    sz = np.sqrt(1 - cz ** 2)
    D = np.array(d)[None] * cz[:, None] + (np.array(u)[None] * np.cos(phi)[:, None] +
                                            np.array(w)[None] * np.sin(phi)[:, None]) * sz[:, None]
    v0 = D * rng.uniform(speed[0], speed[1], n)[:, None]
    k = np.full(n, max(drag, 1e-3))
    lf = np.full(n, life)
    aland = _land_age(p0[:, 2], v0[:, 2], k, G, floor + rest_lift, lf) if floor is not None else lf
    axis = rng.normal(0, 1, (n, 3))
    axis /= np.linalg.norm(axis, axis=1, keepdims=True)
    ob = _cloud(name, {'p0': p0, 'v0': v0, 'birth': birth, 'life': lf, 'k': k, 'aland': aland, 'axis': axis,
                       'w': rng.uniform(0.4, 1.0, n) * spin, 'yaw': rng.uniform(0, 2 * math.pi, n),
                       'r0': rng.uniform(0, 2 * math.pi, (n, 3))}, coll)
    g = N.Tree(f'{name}.gn')
    geo = g.input_geometry()
    alive, age01, pos, vel, landed = _motion(g, 1.0)
    a = g.time() - _attr(g, 'birth')
    ae = g.max(g.min(a, _attr(g, 'aland')), 0.0)
    geo = g.out(g.node('GeometryNodeSetID', inputs={'Geometry': geo, 'ID': g.index()}))  # stable ids for motion blur
    geo = g.delete(geo, g.bool_not(alive))
    geo = g.set_position(geo, position=pos)
    tumble = g.rotate(g.euler(_attr(g, 'r0', 'FLOAT_VECTOR')),
                      g.axis_angle(_attr(g, 'axis', 'FLOAT_VECTOR'), _attr(g, 'w') * ae), space='GLOBAL')
    flat = g.euler(g.vec(0.0, 0.0, _attr(g, 'yaw')))
    rot = g.switch(landed, tumble, flat, kind='ROTATION')
    inst = g.instance(geo, g.object_geo(instance, as_instance=True, relative=False), rotation=rot,
                      scale=g.vec(scale, scale, scale))
    g.output(inst)
    N.modifier(ob, g, 'stream')
    log(f'stream {name}: {n} x {instance.name} from t={t0:.3f} to {t1:.3f}')
    return ob


# ------------------------------------------------------------------------------------------------ along a path


def _polyline(points):
    P = [Vector(p) if len(p) == 3 else Vector((p[0], p[1], 0.0)) for p in points]
    L = [0.0]
    for i in range(1, len(P)):
        L.append(L[-1] + (P[i] - P[i - 1]).length)
    return P, L


def _at(P, L, s):
    """Point and unit tangent at arc length s along the polyline."""
    import bisect
    s = min(max(s, 0.0), L[-1])
    i = min(max(bisect.bisect_right(L, s) - 1, 0), len(P) - 2)
    seg = L[i + 1] - L[i]
    u = (s - L[i]) / seg if seg > 1e-9 else 0.0
    t = (P[i + 1] - P[i])
    return P[i].lerp(P[i + 1], u), (t.normalized() if t.length > 1e-9 else Vector((1, 0, 0)))


def sparks_along(name: str = 'run', *, points, starts, travel: float = 0.4, rate: float = 500.0,
                 life=(0.08, 0.35), speed=(8.0, 45.0), size: float = 0.035, head: float = 0.22,
                 light: float = 8000.0, color: str = '#9FE8FF', hot: str = '#FFFFFF', gravity: float = 0.6,
                 ease: bool = True, seed: int = 3, coll=None, streak: float = 0.02) -> dict:
    """Bright sparks racing along a path (the USB cable) from its start to its end: one per song time in `starts`,
    each taking `travel` s, shedding `rate` embers per second that spray off and fall (life, speed cm/s). Each
    head is an emissive bead with a point light (`light` W) riding it. Returns {'embers', 'heads', 'lights'}."""
    import numpy as np
    rng = np.random.default_rng(seed)
    P, L = _polyline(points)
    total = L[-1]
    coll = coll or kit.collection(f'{name}')
    rows = {k: [] for k in ('p0', 'v0', 'birth', 'life', 'k', 'size')}
    heads, lights = [], []
    hm = kit.emission_mat(f'{name}.head', hot, 60.0)

    def u_of(x):
        return x * x * (3 - 2 * x) if ease else x

    for j, ts in enumerate(starts):
        nb = int(rate * travel)
        tb = ts + np.sort(rng.uniform(0, travel, nb))
        for b in tb:
            s = u_of((b - ts) / travel) * total
            p, tan = _at(P, L, s)
            vdir = rng.normal(0, 1, 3)
            vdir /= np.linalg.norm(vdir)
            vdir = vdir * 0.8 + np.array(tan) * 0.4
            rows['p0'].append(tuple(p))
            rows['v0'].append(tuple(vdir * rng.uniform(*speed)))
            rows['birth'].append(b)
            rows['life'].append(rng.uniform(*life))
            rows['k'].append(3.0)
            rows['size'].append(size * rng.uniform(0.6, 1.4))
        # the head bead + its light, keyed every frame of its run
        hb = kit.sphere(f'{name}.head{j}', head, (0, 0, 0), m=hm, coll=coll, subdiv=2)
        lt = kit.point(f'{name}.light{j}', (0, 0, 0), power=light, radius=0.3, color=color, coll=coll)
        f0, f1 = int(math.floor(ts * 24)), int(math.ceil((ts + travel) * 24))
        for f in range(f0, f1 + 1):
            x = min(max((f / 24 - ts) / travel, 0.0), 1.0)
            p, _ = _at(P, L, u_of(x) * total)
            for ob in (hb, lt):
                ob.location = p
                ob.keyframe_insert('location', frame=f)
        for ob in (hb, lt):
            for fc in kit.fcurves(ob):
                for kp in fc.keyframe_points:
                    kp.interpolation = 'LINEAR'
        from . import vis
        vis(hb, ts, ts + travel + 1 / 24)
        lt.data.energy = 0.0
        kit.key(lt.data, 'energy', ts - 1 / 24, 0.0)
        kit.key(lt.data, 'energy', ts, light)
        kit.key(lt.data, 'energy', ts + travel, light)
        kit.key(lt.data, 'energy', ts + travel + 2 / 24, 0.0)
        heads.append(hb)
        lights.append(lt)
    arr = {k: np.array(v, dtype=np.float32) for k, v in rows.items()}
    n = len(arr['birth'])
    arr['aland'] = arr['life'].copy()
    ob = _cloud(f'{name}.embers', arr, coll)
    mat = _spark_mat(f'{name}.mat', hot, color, '#2F6FD0', strength=30.0)
    N.modifier(ob, _spark_tree(f'{ob.name}.gn', mat, gscale=gravity, streak=streak, size=size), 'sparks')
    log(f'sparks_along {name}: {len(starts)} runs over {total:.1f} cm, {n} embers')
    return {'embers': ob, 'heads': heads, 'lights': lights}


def fuse(name: str = 'fuse', *, points, t0: float, t1: float, radius: float = 0.25, rate: float = 900.0,
         light: float = 6000.0, ember_life: float = 1.2, seed: int = 4, coll=None) -> dict:
    """A burning fuse along points: the cord (a braided tube) burns from its start (t0) to its end (t1); the burn
    point sprays sparks (`rate` per second) and carries a flickering light; the burnt part behind it is a black,
    glowing-then-cooling ash line. Returns {'cord', 'ash', 'sparks', 'light'}."""
    import numpy as np
    rng = np.random.default_rng(seed)
    P, L = _polyline(points)
    total = L[-1]
    coll = coll or kit.collection(name)
    # the cord and the ash: one tube each; geometry nodes trim them to the burn point (keyed factor)
    cd = bpy.data.curves.new(f'{name}.path', 'CURVE')
    cd.dimensions = '3D'
    sp = cd.splines.new('POLY')
    sp.points.add(len(P) - 1)
    for i, p in enumerate(P):
        sp.points[i].co = (p.x, p.y, p.z + radius, 1.0)
    path = bpy.data.objects.new(f'{name}.path', cd)
    coll.objects.link(path)
    path.hide_render = True
    cord_m = kit.mat(f'{name}.cord', '#D8C39A', rough=0.75, sheen=0.5)
    ash_m = kit.mat(f'{name}.ash', '#141210', rough=0.9, emit='#FF5A1A', emit_strength=0.0)
    # ash glows near the burn point: emission from the 'glow' attribute (1 at the burn point, 0 a few cm behind)
    b = ash_m.node_tree.nodes.get('Principled BSDF')
    at = ash_m.node_tree.nodes.new('ShaderNodeAttribute')
    at.attribute_name = 'glow'
    mul = ash_m.node_tree.nodes.new('ShaderNodeMath')
    mul.operation = 'MULTIPLY'
    mul.inputs[1].default_value = 25.0
    ash_m.node_tree.links.new(at.outputs['Fac'], mul.inputs[0])
    ash_m.node_tree.links.new(mul.outputs[0], b.inputs['Emission Strength'])

    def tube(nm, mat, keep_before: bool, r):
        g = N.Tree(f'{nm}.gn')
        g.input_geometry()
        prog = g.param('Burn', 'FLOAT', 0.0)
        curve = g.object_geo(path, relative=True)
        rs = g.node('GeometryNodeResampleCurve', inputs={'Curve': curve, 'Count': 400})
        crv = g.out(rs)
        # trim: cord keeps [burn, 1], ash keeps [0, burn]
        tr = g.node('GeometryNodeTrimCurve', mode='FACTOR', inputs={'Curve': crv})
        if keep_before:
            g.feed(g.inp(tr, 'Start'), 0.0)
            g.feed(g.inp(tr, 'End'), prog)
        else:
            g.feed(g.inp(tr, 'Start'), prog)
            g.feed(g.inp(tr, 'End'), 1.0)
        crv = g.out(tr)
        par = g.out(g.node('GeometryNodeSplineParameter'), 'Factor')
        crv = g.store(crv, 'glow', g.smooth(par, 0.85, 1.0) if keep_before else g.f(0.0))
        circ = g.out(g.node('GeometryNodeCurvePrimitiveCircle', inputs={'Resolution': 8, 'Radius': r}))
        mesh = g.out(g.node('GeometryNodeCurveToMesh', inputs={'Curve': crv, 'Profile Curve': circ,
                                                               'Fill Caps': True}))
        mesh = g.set_material(mesh, mat)
        g.output(mesh)
        me = bpy.data.meshes.new(nm)
        ob = bpy.data.objects.new(nm, me)
        coll.objects.link(ob)
        mod = N.modifier(ob, g, 'tube')
        N.key_input(ob, mod, 'Burn', t0, 0.0, interp='LINEAR')
        N.key_input(ob, mod, 'Burn', t1, 1.0, interp='LINEAR')
        return ob

    cord = tube(f'{name}.cord', cord_m, False, radius)
    ash = tube(f'{name}.ash', ash_m, True, radius * 0.8)
    # sparks spraying from the burn point
    nb = int(rate * (t1 - t0))
    tb = t0 + np.sort(rng.uniform(0, t1 - t0, nb))
    p0, v0 = [], []
    for b in tb:
        p, tan = _at(P, L, (b - t0) / (t1 - t0) * total)
        dirv = rng.normal(0, 1, 3)
        dirv /= np.linalg.norm(dirv)
        dirv[2] = abs(dirv[2]) + 0.6
        p0.append((p.x, p.y, p.z + radius * 1.5))
        v0.append(tuple(dirv * rng.uniform(40, 160)))
    lf = rng.uniform(0.15, 0.6, nb)
    k = np.full(nb, 2.0)
    p0a, v0a = np.array(p0), np.array(v0)
    aland = _land_age(p0a[:, 2], v0a[:, 2], k, G, P[0].z + 0.04, lf)
    sparks = _cloud(f'{name}.sparks', {'p0': p0a, 'v0': v0a, 'birth': tb, 'life': lf, 'k': k, 'aland': aland,
                                       'size': np.full(nb, 0.035) * rng.uniform(0.6, 1.4, nb)}, coll)
    N.modifier(sparks, _spark_tree(f'{name}.sparks.gn', _spark_mat(f'{name}.spark.mat'), gscale=1.0, streak=0.02,
                                   size=0.035), 'sparks')
    # the flickering light at the burn point
    lt = kit.point(f'{name}.light', P[0], power=light, radius=0.4, color='#FF9A3A', coll=coll)
    for f in range(int(math.floor(t0 * 24)), int(math.ceil(t1 * 24)) + 1):
        x = min(max((f / 24 - t0) / (t1 - t0), 0.0), 1.0)
        p, _ = _at(P, L, x * total)
        lt.location = (p.x, p.y, p.z + 1.0)
        lt.keyframe_insert('location', frame=f)
        lt.data.energy = light * (0.75 + 0.5 * rng.random())
        lt.data.keyframe_insert('energy', frame=f)
    lt.data.energy = 0.0
    lt.data.keyframe_insert('energy', frame=int(math.floor(t0 * 24)) - 1)
    lt.data.keyframe_insert('energy', frame=int(math.ceil(t1 * 24)) + 2)
    log(f'fuse {name}: {total:.1f} cm from t={t0:.3f} to {t1:.3f}, {nb} sparks')
    return {'cord': cord, 'ash': ash, 'sparks': sparks, 'light': lt}


# ------------------------------------------------------------------------------------------------ motes


def motes(name: str = 'motes', *, box, count: int = 800, size: float = 0.04, drift: float = 0.8,
          brightness: float = 0.0, seed: int = 5, coll=None, color: str = '#FFE6C0') -> bpy.types.Object:
    """Dust motes hanging in the air of box ((x0,y0,z0),(x1,y1,z1)), wandering `drift` cm/s on smooth noise paths
    (a pure function of time). Bright, rough and not emissive, so only the ones inside a light beam show: put them
    where a beam is (brightness > 0 makes them glow everywhere).
    Returns the object."""
    import numpy as np
    rng = np.random.default_rng(seed)
    (x0, y0, z0), (x1, y1, z1) = box
    p0 = np.stack([rng.uniform(x0, x1, count), rng.uniform(y0, y1, count), rng.uniform(z0, z1, count)], 1)
    ob = _cloud(name, {'p0': p0, 'ph': rng.uniform(0, 100, count), 'size': size * rng.uniform(0.5, 1.5, count)},
                coll)
    g = N.Tree(f'{name}.gn')
    geo = g.input_geometry()
    t = g.time()
    ph = _attr(g, 'ph')
    wv = g.noise(g.vec(ph, ph * 0.37, 0.0), 1.0, 1.0, w=t * (drift * 0.08), color=True)
    off = (wv - g.vec(0.5, 0.5, 0.5)) * (drift * 12.0)
    geo = g.set_position(geo, offset=off)
    r = _attr(g, 'size')
    inst = g.instance(geo, g.object_geo(_unit_sphere('fx.mote.unit', 1), as_instance=True, relative=False),
                      scale=g.vec(r, r, r))
    m = kit.mat(f'{name}.mat', color, rough=0.9, sheen=1.0, emit=color if brightness else None,
                emit_strength=brightness)
    inst = g.set_material(inst, m)
    g.output(inst)
    N.modifier(ob, g, 'motes')
    return ob
