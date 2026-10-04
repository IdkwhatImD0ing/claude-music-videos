"""The GPU city for `gpus` (scene-local): tens of thousands of tiny graphics cards stacked into skyscrapers over the
whole desk, a night skyline whose windows are the cards' LED strips.

- A card is 1.6 x 0.64 x 0.22 cm lying flat: green PCB with gold fingers, a black shroud with a silver accent, LED
  strips on both long sides, an I/O bracket with a status LED. Stacks of 1-34 cards (0.27 cm a floor) make the
  buildings on a street grid; the roof card of every stack carries two fans (spinning, with RGB rings).
- Everything is geometry-node instancing of one points mesh per kind (cards, fans), so the city is cheap to build and
  every frame is a pure function of song time:
    * blink: some cards' LEDs blink at their own rate and phase; the others glow steady;
    * power-on: the city lights come on in a sweep along +X from `on0` over `on_dur` s;
    * waves: shock rings from a point (the robot's stomps) at the given times: the LEDs flash white as a ring passes
      and the stacks hop.
  The LED materials read the instance attributes 'glow', 'wave', 'ledcol', 'blink'.
"""
from __future__ import annotations

import math

import bmesh
import bpy
from mathutils import Matrix, Vector

from pdoom import kit
from pdoom.chars import geo as cgeo
from pdoom.fx import _nodes as N
from pdoom.sets import materials as M

V = Vector

CARD_L, CARD_W, CARD_H = 1.6, 0.64, 0.22
FLOOR = 0.27
PALETTE = [((0.18, 1.0, 0.22), 0.55), ((1.0, 1.0, 1.0), 0.14), ((0.15, 0.75, 1.0), 0.16), ((1.0, 0.25, 0.55), 0.08),
           ((1.0, 0.55, 0.1), 0.07)]


# ------------------------------------------------------------------------------------------------ materials


def _inst_attr(nt, name, loc, kind='INSTANCER'):
    a = nt.nodes.new('ShaderNodeAttribute')
    a.attribute_type = kind
    a.attribute_name = name
    a.location = loc
    return a


def led_material(name='gpu.led', *, gain=1.0):
    """Emission: colour 'ledcol' pushed toward white by 'wave', strength 'glow' * gain (instance attributes)."""
    if name in bpy.data.materials:
        return bpy.data.materials[name]
    m = bpy.data.materials.new(name)
    nt = m.node_tree
    nt.nodes.clear()
    out = nt.nodes.new('ShaderNodeOutputMaterial')
    col = _inst_attr(nt, 'ledcol', (-600, 200))
    wav = _inst_attr(nt, 'wave', (-600, 0))
    glo = _inst_attr(nt, 'glow', (-600, -200))
    mix = nt.nodes.new('ShaderNodeMix')
    mix.data_type = 'RGBA'
    socks = {s.identifier: s for s in mix.inputs}
    nt.links.new(wav.outputs['Fac'], socks['Factor_Float'])
    nt.links.new(col.outputs['Vector'], socks['A_Color'])
    socks['B_Color'].default_value = (1.0, 0.97, 0.9, 1.0)
    em = nt.nodes.new('ShaderNodeEmission')
    nt.links.new(next(o for o in mix.outputs if o.identifier == 'Result_Color'), em.inputs['Color'])
    mul = nt.nodes.new('ShaderNodeMath')
    mul.operation = 'MULTIPLY'
    mul.inputs[1].default_value = gain
    nt.links.new(glo.outputs['Fac'], mul.inputs[0])
    nt.links.new(mul.outputs[0], em.inputs['Strength'])
    nt.links.new(em.outputs[0], out.inputs['Surface'])
    m.diffuse_color = (0.2, 1.0, 0.25, 1.0)
    return m


def status_material(name='gpu.status'):
    """A tiny status LED: green when 'blink' is on, dim red otherwise; flashes white with the wave."""
    if name in bpy.data.materials:
        return bpy.data.materials[name]
    m = bpy.data.materials.new(name)
    nt = m.node_tree
    nt.nodes.clear()
    out = nt.nodes.new('ShaderNodeOutputMaterial')
    bl = _inst_attr(nt, 'blink', (-600, 200))
    wav = _inst_attr(nt, 'wave', (-600, 0))
    on = _inst_attr(nt, 'on', (-600, -200))
    mix = nt.nodes.new('ShaderNodeMix')
    mix.data_type = 'RGBA'
    socks = {s.identifier: s for s in mix.inputs}
    nt.links.new(bl.outputs['Fac'], socks['Factor_Float'])
    socks['A_Color'].default_value = kit.srgb('#FF2A10')
    socks['B_Color'].default_value = kit.srgb('#4DFF5A')
    em = nt.nodes.new('ShaderNodeEmission')
    nt.links.new(next(o for o in mix.outputs if o.identifier == 'Result_Color'), em.inputs['Color'])
    add = nt.nodes.new('ShaderNodeMath')
    add.operation = 'MULTIPLY_ADD'
    add.inputs[1].default_value = 10.0
    add.inputs[2].default_value = 1.6
    nt.links.new(wav.outputs['Fac'], add.inputs[0])
    mul = nt.nodes.new('ShaderNodeMath')
    mul.operation = 'MULTIPLY'
    nt.links.new(add.outputs[0], mul.inputs[0])
    nt.links.new(on.outputs['Fac'], mul.inputs[1])
    nt.links.new(mul.outputs[0], em.inputs['Strength'])
    nt.links.new(em.outputs[0], out.inputs['Surface'])
    return m


def _mats():
    return {
        'pcb': M.solid('gpu.pcb', '#1F6A34', rough=0.45, coat=0.4, coat_rough=0.2),
        'gold': M.solid('gpu.gold', '#E2B04A', rough=0.25, metal=1.0),
        'shroud': M.solid('gpu.shroud', '#17191D', rough=0.35, metal=0.4, coat=0.3),
        'accent': M.solid('gpu.accent', '#B9BEC6', rough=0.22, metal=1.0),
        'bracket': M.solid('gpu.bracket', '#C4C8CE', rough=0.3, metal=1.0),
        'led': led_material(),
        'status': status_material(),
        'fan': M.solid('gpu.fan', '#0E0F11', rough=0.5),
        'ring': led_material('gpu.ring', gain=1.3),
    }


# ------------------------------------------------------------------------------------------------ the models


def _box(bm, lo, hi, mat):
    (x0, y0, z0), (x1, y1, z1) = lo, hi
    vs = [bm.verts.new(p) for p in ((x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0),
                                     (x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1))]
    for f in ((0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)):
        bm.faces.new([vs[i] for i in f]).material_index = mat


def card_proto(coll):
    """The card mesh (origin at its bottom centre, length X, fans side up)."""
    ob = bpy.data.objects.get('gpu.card.proto')
    if ob is not None:
        return ob
    mats = _mats()
    order = ['pcb', 'gold', 'shroud', 'accent', 'bracket', 'led', 'status']
    mi = {k: i for i, k in enumerate(order)}
    L, W = CARD_L / 2, CARD_W / 2
    bm = bmesh.new()
    _box(bm, (-L, -W, 0.0), (L - 0.02, W - 0.03, 0.035), mi['pcb'])
    _box(bm, (-0.46, W - 0.03, 0.0), (0.34, W + 0.02, 0.03), mi['gold'])
    _box(bm, (-L + 0.05, -W + 0.03, 0.035), (L - 0.09, W - 0.06, 0.205), mi['shroud'])
    _box(bm, (-L + 0.05, -W + 0.015, 0.1), (L - 0.09, -W + 0.03, 0.125), mi['accent'])
    _box(bm, (-L + 0.25, -W + 0.012, 0.145), (L - 0.3, -W + 0.03, 0.185), mi['led'])
    _box(bm, (-L + 0.25, W - 0.06, 0.145), (L - 0.3, W - 0.045, 0.185), mi['led'])
    _box(bm, (L - 0.02, -W - 0.01, 0.0), (L + 0.01, W - 0.03, CARD_H + 0.01), mi['bracket'])
    _box(bm, (L + 0.01, -W + 0.08, 0.15), (L + 0.025, -W + 0.14, 0.19), mi['status'])
    me = bpy.data.meshes.new('gpu.card')
    bm.to_mesh(me)
    bm.free()
    for k in order:
        me.materials.append(mats[k])
    ob = bpy.data.objects.new('gpu.card.proto', me)
    coll.objects.link(ob)
    ob.location = (0, 0, -5000)
    ob.hide_render = True
    return ob


def fan_proto(coll):
    """A fan (origin at its hub, blades in XY): a housing disc, 7 blades, a hub, an RGB ring."""
    ob = bpy.data.objects.get('gpu.fan.proto')
    if ob is not None:
        return ob
    mats = _mats()
    bm = bmesh.new()
    R = 0.25
    # housing disc (flat, dark)
    ring = [bm.verts.new((R * math.cos(2 * math.pi * k / 24), R * math.sin(2 * math.pi * k / 24), 0.0))
            for k in range(24)]
    bm.faces.new(ring).material_index = 0
    # blades: twisted quads
    for b in range(7):
        a0 = 2 * math.pi * b / 7
        pts = []
        for r_, da, z in ((0.07, 0.0, 0.03), (0.22, 0.45, 0.012), (0.22, 0.75, 0.035), (0.07, 0.5, 0.045)):
            a = a0 + da
            pts.append(bm.verts.new((r_ * math.cos(a), r_ * math.sin(a), z)))
        bm.faces.new(pts).material_index = 0
    # hub
    hub = [bm.verts.new((0.07 * math.cos(2 * math.pi * k / 12), 0.07 * math.sin(2 * math.pi * k / 12), 0.05))
           for k in range(12)]
    bm.faces.new(hub).material_index = 0
    # RGB ring (annulus, slightly raised)
    outer = [bm.verts.new((R * math.cos(2 * math.pi * k / 32), R * math.sin(2 * math.pi * k / 32), 0.02))
             for k in range(32)]
    inner = [bm.verts.new((0.225 * math.cos(2 * math.pi * k / 32), 0.225 * math.sin(2 * math.pi * k / 32), 0.02))
             for k in range(32)]
    for k in range(32):
        k2 = (k + 1) % 32
        bm.faces.new((inner[k], outer[k], outer[k2], inner[k2])).material_index = 1
    me = bpy.data.meshes.new('gpu.fan')
    bm.to_mesh(me)
    bm.free()
    me.materials.append(mats['fan'])
    me.materials.append(mats['ring'])
    ob = bpy.data.objects.new('gpu.fan.proto', me)
    coll.objects.link(ob)
    ob.location = (0, 0, -5000)
    ob.hide_render = True
    return ob


# ------------------------------------------------------------------------------------------------ layout


def _noise2(x, y):
    return (0.5 + 0.22 * math.sin(0.083 * x + 1.3) * math.cos(0.11 * y - 0.4) + 0.17 * math.sin(0.19 * x - 0.13 * y + 2.2)
            + 0.11 * math.sin(0.37 * x + 0.29 * y + 0.7))


def layout(*, area=((-77.0, -37.0), (77.0, 38.0)), pitch=(1.9, 1.0), block=(6, 5), street=(1.3, 1.1),
           avenues=(), clear=(), boxes=(), center=(0.0, 0.0), seed=7, max_floors=44, downtown=()):
    """Building footprints on a street grid. avenues: [(axis 'x'|'y', coord, half width)] kept clear; clear: [(x, y,
    r)] circles; boxes: [((x0, y0), (x1, y1))] rectangles kept clear. downtown: [(x, y, r, boost)] raise the skyline.
    Returns a list of (x, y, floors, yaw, colour, seed)."""
    import numpy as np
    rng = np.random.default_rng(seed)
    (x0, y0), (x1, y1) = area
    out = []
    xs = []
    x = x0
    i = 0
    while x < x1:
        xs.append(x)
        i += 1
        x += pitch[0] + (street[0] if i % block[0] == 0 else 0.0)
    ys = []
    y = y0
    j = 0
    while y < y1:
        ys.append(y)
        j += 1
        y += pitch[1] + (street[1] if j % block[1] == 0 else 0.0)
    cols = [c for c, _ in PALETTE]
    wts = np.array([w for _, w in PALETTE])
    wts = wts / wts.sum()
    for x in xs:
        for y in ys:
            skip = False
            for ax, c, hw in avenues:
                v = y if ax == 'x' else x
                if abs(v - c) < hw:
                    skip = True
            for cx, cy, r in clear:
                if (x - cx) ** 2 + (y - cy) ** 2 < r * r:
                    skip = True
            for (bx0, by0), (bx1, by1) in boxes:
                if bx0 - 0.9 < x < bx1 + 0.9 and by0 - 0.5 < y < by1 + 0.5:
                    skip = True
            if skip:
                continue
            n = _noise2(x, y)
            for dx, dy, r, boost in downtown:
                n += boost * math.exp(-((x - dx) ** 2 + (y - dy) ** 2) / (r * r))
            u = rng.random()
            floors = 1 + int((max_floors - 1) * min(1.0, max(0.0, n)) ** 1.7 * (0.3 + 0.7 * u ** 0.5))
            if rng.random() < 0.05:
                floors = min(max_floors, floors + int(rng.integers(6, 16)))
            col = cols[int(rng.choice(len(cols), p=wts))]
            out.append((x, y, floors, 0.0 if rng.random() < 0.5 else math.pi, col, int(rng.integers(0, 1 << 30))))
    return out


def build(coll, blds, *, wave_center, wave_times, wave_speed=75.0, wave_width=6.0, on0=118.76, on_dur=0.45,
          on_axis=(1.0, 0.0), extent=(-77.0, 77.0)):
    """The instanced city from layout() output. Returns {'cards', 'fans', 'count', 'fan_count'}."""
    import numpy as np
    rng = np.random.default_rng(11)
    card = card_proto(coll)
    fan = fan_proto(coll)
    P, A = [], {k: [] for k in ('d', 'ph', 'rate', 'blinky', 'bright', 'ton', 'yaw')}
    col = []
    FP_, FA = [], {k: [] for k in ('d', 'ph', 'ton', 'yaw', 'spin', 'bright')}
    fcol = []
    wc = V(wave_center)
    ax = V((on_axis[0], on_axis[1], 0.0)).normalized()
    e0, e1 = extent
    for (x, y, floors, yaw, c, s) in blds:
        d = math.hypot(x - wc.x, y - wc.y)
        proj = (x * ax.x + y * ax.y - e0) / (e1 - e0)
        ton = on0 + on_dur * min(1.0, max(0.0, proj)) + 0.06 * rng.random()
        bblink = rng.random() < 0.35
        for lv in range(floors):
            P.append((x, y, lv * FLOOR))
            A['d'].append(d)
            A['ph'].append(rng.random())
            A['rate'].append(rng.uniform(1.2, 4.5))
            A['blinky'].append(1.0 if (bblink and rng.random() < 0.7) else 0.0)
            A['bright'].append(rng.uniform(0.5, 1.6) * (0.6 if rng.random() < 0.25 else 1.0))
            A['ton'].append(ton + 0.02 * rng.random())
            A['yaw'].append(yaw)
            cc = c if rng.random() < 0.85 else PALETTE[int(rng.integers(0, len(PALETTE)))][0]
            col.append(cc)
        top = (floors - 1) * FLOOR + 0.205
        for fx in (-0.36, 0.36):
            ca, sa = math.cos(yaw), math.sin(yaw)
            FP_.append((x + fx * ca, y + fx * sa, top))
            FA['d'].append(d)
            FA['ph'].append(rng.uniform(0, 6.283))
            FA['ton'].append(ton)
            FA['yaw'].append(yaw)
            FA['spin'].append(rng.uniform(22.0, 34.0) * (1 if rng.random() < 0.5 else -1))
            FA['bright'].append(rng.uniform(0.8, 1.6))
            fcol.append(c)
    cards = _points('gpu.cards', P, A, col, coll)
    fans = _points('gpu.fans', FP_, FA, fcol, coll)
    N.modifier(cards, _tree('gpu.cards.gn', card, wave_times, wave_speed, wave_width, fans=False), 'city')
    N.modifier(fans, _tree('gpu.fans.gn', fan, wave_times, wave_speed, wave_width, fans=True), 'city')
    from pdoom.fx import log
    log(f'gpu city: {len(blds)} buildings, {len(P)} cards, {len(FP_)} fans')
    return {'cards': cards, 'fans': fans, 'count': len(P), 'fan_count': len(FP_)}


def _points(name, P, A, col, coll):
    import numpy as np
    me = bpy.data.meshes.new(name)
    co = np.asarray(P, dtype=np.float32).reshape(-1, 3)
    me.vertices.add(len(co))
    me.vertices.foreach_set('co', co.ravel())
    for k, arr in A.items():
        a = me.attributes.new(k, 'FLOAT', 'POINT')
        a.data.foreach_set('value', np.asarray(arr, dtype=np.float32))
    a = me.attributes.new('col', 'FLOAT_VECTOR', 'POINT')
    a.data.foreach_set('vector', np.asarray(col, dtype=np.float32).ravel())
    me.update()
    ob = bpy.data.objects.new(name, me)
    coll.objects.link(ob)
    return ob


def _attr(g, name, kind='FLOAT'):
    nd = g.node('GeometryNodeInputNamedAttribute', data_type=kind, inputs={'Name': name})
    return g.out(nd, 'Attribute')


def _tree(name, proto, wave_times, v, w, *, fans):
    g = N.Tree(name)
    geo = g.input_geometry()
    t = g.time()
    d = _attr(g, 'd')
    # the shock rings
    wave = None
    for tk in wave_times:
        a = t - tk
        x = (d - a * v) / w
        term = g.exp(-(x * x)) * g.exp(-1.0 * g.max(a, 0.0) / 1.3) * (a > 0.0)
        wave = term if wave is None else wave + term
    wave = g.clamp(wave, 0.0, 1.0)
    on = g.smooth(t - _attr(g, 'ton'), 0.0, 0.08)
    bright = _attr(g, 'bright')
    if fans:
        glow = bright * on * 1.2 + wave * 30.0
        blink = g.f(1.0)
    else:
        blink = g.fract(t * _attr(g, 'rate') + _attr(g, 'ph')) < 0.55
        bl = _attr(g, 'blinky')
        base = bright * (1.0 - bl + bl * blink)
        glow = base * on + wave * 30.0
    geo = g.store(geo, 'glow', glow)
    geo = g.store(geo, 'wave', wave)
    geo = g.store(geo, 'on', on)
    geo = g.store(geo, 'blink', blink)
    geo = g.store(geo, 'ledcol', _attr(g, 'col', 'FLOAT_VECTOR'), kind='FLOAT_VECTOR')
    # the stacks hop as a ring passes
    geo = g.set_position(geo, offset=g.vec(0.0, 0.0, wave * 0.9))
    if fans:
        rz = _attr(g, 'yaw') + _attr(g, 'ph') + _attr(g, 'spin') * t
    else:
        rz = _attr(g, 'yaw')
    rot = g.euler(g.vec(0.0, 0.0, rz))
    inst = g.object_geo(proto, as_instance=True, relative=False)
    g.output(g.instance(geo, inst, rotation=rot))
    return g
