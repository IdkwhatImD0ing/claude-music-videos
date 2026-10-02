"""The room around the desk: the desk itself (top, legs), the wall with its window, the night city seen through it,
the floor, and the atmosphere (dust motes and a faint haze that makes the lamp's cone visible).

Coordinates: the desktop's surface is z = 0, the desk spans x -80..80, y -40..40 (front edge at y = -40, towards the
default camera). The wall's inner face is at y = 42; the window opening spans x -60..60, z 10..112.
"""
from __future__ import annotations

import math

import bpy
import bmesh
from mathutils import Matrix, Vector

from .. import kit
from . import geo
from . import materials as M

DESK = (160.0, 80.0, 3.2)
DESK_H = 74.0             # floor at z = -74
WALL_Y = 42.0
WALL_T = 18.0
WIN = (-60.0, 60.0, 10.0, 112.0)   # x0, x1, z0, z1 of the window opening
GLASS_Y = WALL_Y + 9.0


class Room:
    def __init__(self):
        self.desk = None
        self.wall = []
        self.window = {}
        self.glass = None
        self.moon = None           # the cool light coming in through the window (area light)
        self.bounce = None         # dim warm fill from above (the lamp's light off the ceiling)
        self.city_sockets = []     # emission strength sockets of the city (scaled by lighting presets)
        self.city_base = []
        self.sky_nodes = None      # (bottom, horizon, top) colour sockets of the sky gradient
        self.sky_strength = None
        self.haze_density = None
        self.motes = None
        self.haze = None


# ------------------------------------------------------------------------------------------------ desk + room


def build_desk_body(coll, room: Room):
    wood = M.desk_wood()
    W, D, T = DESK
    top = geo.box('desk.top', (W, D, T), (0, 0, -T / 2), bev=0.35, segments=5, m=wood, coll=coll)
    room.desk = top
    legm = M.tex_mat('desk.legwood', 'desk_wood', 120, hue=0.49, sat=0.85, val=0.6, rough=(0.35, 0.6), normal=0.6,
                     coat=0.3, fallback='#3A2418', rot_deg=90)
    for sx in (-1, 1):
        for sy in (-1, 1):
            geo.box(f'desk.leg{sx}{sy}', (5.0, 5.0, DESK_H - T), (sx * (W / 2 - 6), sy * (D / 2 - 6), -T - (DESK_H - T) / 2),
                    bev=0.3, m=legm, coll=coll)
    for sy in (-1, 1):
        geo.box(f'desk.apron.y{sy}', (W - 14, 2.2, 9.0), (0, sy * (D / 2 - 6), -T - 4.5), bev=0.2, m=legm, coll=coll)
    for sx in (-1, 1):
        geo.box(f'desk.apron.x{sx}', (2.2, D - 14, 9.0), (sx * (W / 2 - 6), 0, -T - 4.5), bev=0.2, m=legm, coll=coll)
    return top


def build_wall(coll, room: Room, *, paint='#6F767C'):
    pl = M.plaster(paint)
    x0, x1, z0, z1 = WIN
    zf, zc = -DESK_H, 200.0
    y = WALL_Y + WALL_T / 2
    parts = [
        ((260 - (-x0), WALL_T, zc - zf), ((-260 + x0) / 2, y, (zc + zf) / 2)),
        ((260 - x1, WALL_T, zc - zf), ((260 + x1) / 2, y, (zc + zf) / 2)),
        ((x1 - x0, WALL_T, z0 - zf), ((x0 + x1) / 2, y, (z0 + zf) / 2)),
        ((x1 - x0, WALL_T, zc - z1), ((x0 + x1) / 2, y, (zc + z1) / 2)),
    ]
    for i, (sz, lc) in enumerate(parts):
        o = geo.box(f'room.wall{i}', sz, lc, m=pl, coll=coll)
        room.wall.append(o)
    # skirting board
    sk = M.enamel('room.skirting', '#D9D2C4', rough=0.45, coat=0.1)
    geo.box('room.skirting', (520, 1.6, 10), (0, WALL_Y - 0.8, zf + 5), bev=0.2, m=sk, coll=coll)
    # floor
    fl = M.floor_wood()
    geo.box('room.floor', (520, 400, 2), (0, -150, zf - 1), m=fl, coll=coll)
    return room.wall


def build_window(coll, room: Room):
    x0, x1, z0, z1 = WIN
    frame_m = M.enamel('window.frame', '#E2DCD0', rough=0.42, coat=0.15)
    sill_m = M.enamel('window.sill', '#E7E1D6', rough=0.35, coat=0.25)
    sill = geo.box('window.sill', (x1 - x0 + 8, 20, 2.6), ((x0 + x1) / 2, WALL_Y + 5, z0 - 1.3 + 0.4), bev=0.4,
                   m=sill_m, coll=coll)
    fw, fd = 5.0, 6.0
    fy = GLASS_Y
    parts = [
        ('window.stileL', (fw, fd, z1 - z0), (x0 + fw / 2, fy, (z0 + z1) / 2)),
        ('window.stileR', (fw, fd, z1 - z0), (x1 - fw / 2, fy, (z0 + z1) / 2)),
        ('window.head', (x1 - x0, fd, fw), ((x0 + x1) / 2, fy, z1 - fw / 2)),
        ('window.bottom', (x1 - x0, fd, fw + 1.5), ((x0 + x1) / 2, fy, z0 + 0.4 + (fw + 1.5) / 2)),
        ('window.mullion', (3.6, fd - 1, z1 - z0 - 2 * fw), ((x0 + x1) / 2, fy, (z0 + z1) / 2)),
        ('window.transom', (x1 - x0 - 2 * fw, fd - 1, 3.6), ((x0 + x1) / 2, fy, z0 + (z1 - z0) * 0.66)),
    ]
    for nm, sz, lc in parts:
        room.window[nm] = geo.box(nm, sz, lc, bev=0.35, segments=3, m=frame_m, coll=coll)
    room.window['window.sill'] = sill
    # glass: thin, slightly reflective (it picks up the lamp and the room)
    gm, fresh = M.new_mat('window.glass')
    if fresh:
        b = M.principled(gm)
        M.setin(b, 'Base Color', (0.9, 0.95, 1.0, 1))
        M.setin(b, 'Roughness', 0.03)
        M.setin(b, 'Transmission Weight', 1.0)
        M.setin(b, 'IOR', 1.45)
        M.setin(b, 'Thin Wall', True)
        # faint smudges
        nt = gm.node_tree
        tc = M.node(nt, 'ShaderNodeTexCoord', (-700, -200))
        nz = M.node(nt, 'ShaderNodeTexNoise', (-500, -200))
        M.setin(nz, 'Scale', 0.05)
        M.setin(nz, 'Detail', 5)
        M.link(nt, M.sout(tc, 'Object'), M.sin(nz, 'Vector'))
        mr = M.node(nt, 'ShaderNodeMapRange', (-300, -200))
        M.setin(mr, 'From Min', 0.45, 'VALUE')
        M.setin(mr, 'From Max', 0.8, 'VALUE')
        M.setin(mr, 'To Min', 0.02, 'VALUE')
        M.setin(mr, 'To Max', 0.12, 'VALUE')
        M.link(nt, M.sout(nz, 'Factor'), M.sin(mr, 'Value', 'VALUE'))
        M.link(nt, M.sout(mr, 'Result', 'VALUE'), M.sin(b, 'Roughness'))
        M.glassify(gm)
    verts = [(x0, 0, z0), (x1, 0, z0), (x1, 0, z1), (x0, 0, z1)]
    g = geo.mesh_obj('window.glass', verts, [(0, 1, 2, 3)], coll, gm, uvs=[(0, 0), (1, 0), (1, 1), (0, 1)])
    g.location = (0, GLASS_Y + 0.5, 0)
    g.visible_shadow = False
    room.glass = g
    return room.window


# ------------------------------------------------------------------------------------------------ the city


def _sky_material():
    m, fresh = M.new_mat('city.sky')
    nt = m.node_tree
    for n in list(nt.nodes):
        if n.bl_idname != 'ShaderNodeOutputMaterial':
            nt.nodes.remove(n)
    out = nt.nodes.get('Material Output')
    tc = M.node(nt, 'ShaderNodeTexCoord', (-900, 0))
    sep = M.node(nt, 'ShaderNodeSeparateXYZ', (-700, 0))
    M.link(nt, M.sout(tc, 'Object'), M.sin(sep, 'Vector'))
    mr = M.node(nt, 'ShaderNodeMapRange', (-500, 0))
    M.setin(mr, 'From Min', -3000.0, 'VALUE')
    M.setin(mr, 'From Max', 12000.0, 'VALUE')
    M.link(nt, M.sout(sep, 'Z'), M.sin(mr, 'Value', 'VALUE'))
    ramp = M.node(nt, 'ShaderNodeValToRGB', (-300, 0))
    cr = ramp.color_ramp
    cr.elements[0].position, cr.elements[0].color = 0.0, kit.srgb('#3B2A3A')
    cr.elements[1].position, cr.elements[1].color = 1.0, kit.srgb('#04070F')
    mid = cr.elements.new(0.22)
    mid.color = kit.srgb('#1B2438')
    M.link(nt, M.sout(mr, 'Result', 'VALUE'), M.sin(ramp, 'Factor'))
    em = M.node(nt, 'ShaderNodeEmission', (0, 0))
    M.link(nt, M.sout(ramp, 'Color'), M.sin(em, 'Color'))
    M.setin(em, 'Strength', 1.0)
    M.link(nt, M.sout(em, 'Emission'), out.inputs['Surface'])
    return m, cr, M.sin(em, 'Strength')


def _facade_material(name, seed, lit=0.35, warm='#FFC98A', cool='#BFD8FF', strength=3.0):
    """Dark facade with a grid of lit windows (one random on/off and warm/cool per cell): pure shader, no textures."""
    m, fresh = M.new_mat(name)
    nt = m.node_tree
    b = M.principled(m)
    M.setin(b, 'Base Color', kit.srgb('#0A0D12'))
    M.setin(b, 'Roughness', 0.5)
    N, S, L = M.node, M.sin, M.sout
    tc = N(nt, 'ShaderNodeTexCoord', (-1400, 0))
    sep = N(nt, 'ShaderNodeSeparateXYZ', (-1200, 0))
    M.link(nt, L(tc, 'Object'), S(sep, 'Vector'))
    # use x+y along the facade (boxes are axis-aligned; either x or y varies on a face) and z up
    along = N(nt, 'ShaderNodeMath', (-1000, 100), operation='ADD')
    M.link(nt, L(sep, 'X'), along.inputs[0])
    M.link(nt, L(sep, 'Y'), along.inputs[1])
    cw, chh = 110.0, 290.0
    cu = N(nt, 'ShaderNodeMath', (-800, 100), operation='DIVIDE')
    M.link(nt, along.outputs[0], cu.inputs[0])
    cu.inputs[1].default_value = cw
    cv = N(nt, 'ShaderNodeMath', (-800, -100), operation='DIVIDE')
    M.link(nt, L(sep, 'Z'), cv.inputs[0])
    cv.inputs[1].default_value = chh
    fu = N(nt, 'ShaderNodeMath', (-600, 150), operation='FLOOR')
    M.link(nt, cu.outputs[0], fu.inputs[0])
    fv = N(nt, 'ShaderNodeMath', (-600, -150), operation='FLOOR')
    M.link(nt, cv.outputs[0], fv.inputs[0])
    cell = N(nt, 'ShaderNodeCombineXYZ', (-400, 0))
    M.link(nt, fu.outputs[0], S(cell, 'X'))
    M.link(nt, fv.outputs[0], S(cell, 'Y'))
    cell.inputs['Z'].default_value = seed
    wn = N(nt, 'ShaderNodeTexWhiteNoise', (-200, 0))
    wn.noise_dimensions = '3D'
    M.link(nt, L(cell, 'Vector'), S(wn, 'Vector'))
    on = N(nt, 'ShaderNodeMath', (0, 100), operation='LESS_THAN')
    M.link(nt, L(wn, 'Value'), on.inputs[0])
    on.inputs[1].default_value = lit
    # window rectangle inside the cell
    ru = N(nt, 'ShaderNodeMath', (-400, 300), operation='FRACT')
    M.link(nt, cu.outputs[0], ru.inputs[0])
    rv = N(nt, 'ShaderNodeMath', (-400, -300), operation='FRACT')
    M.link(nt, cv.outputs[0], rv.inputs[0])

    def band(src, lo, hi, y):
        a = N(nt, 'ShaderNodeMath', (-200, y), operation='GREATER_THAN')
        M.link(nt, src, a.inputs[0])
        a.inputs[1].default_value = lo
        c = N(nt, 'ShaderNodeMath', (-200, y - 60), operation='LESS_THAN')
        M.link(nt, src, c.inputs[0])
        c.inputs[1].default_value = hi
        d = N(nt, 'ShaderNodeMath', (0, y), operation='MULTIPLY')
        M.link(nt, a.outputs[0], d.inputs[0])
        M.link(nt, c.outputs[0], d.inputs[1])
        return d.outputs[0]

    bu = band(ru.outputs[0], 0.18, 0.82, 400)
    bv = band(rv.outputs[0], 0.25, 0.8, -400)
    w1 = N(nt, 'ShaderNodeMath', (200, 0), operation='MULTIPLY')
    M.link(nt, bu, w1.inputs[0])
    M.link(nt, bv, w1.inputs[1])
    w2 = N(nt, 'ShaderNodeMath', (400, 0), operation='MULTIPLY')
    M.link(nt, w1.outputs[0], w2.inputs[0])
    M.link(nt, on.outputs[0], w2.inputs[1])
    # colour: warm or cool by a second hash (the noise's colour output)
    sepc = N(nt, 'ShaderNodeSeparateXYZ', (0, -250))
    M.link(nt, L(wn, 'Color'), S(sepc, 'Vector'))
    mx = N(nt, 'ShaderNodeMix', (200, -250), data_type='RGBA', blend_type='MIX')
    M.link(nt, L(sepc, 'X'), S(mx, 'Factor', 'VALUE'))
    M.setin(mx, 'A', kit.srgb(warm), 'RGBA')
    M.setin(mx, 'B', kit.srgb(cool), 'RGBA')
    M.link(nt, L(mx, 'Result', 'RGBA'), S(b, 'Emission Color'))
    st = N(nt, 'ShaderNodeMath', (600, 0), operation='MULTIPLY')
    M.link(nt, w2.outputs[0], st.inputs[0])
    st.inputs[1].default_value = strength
    # brightness varies per window a little
    st2 = N(nt, 'ShaderNodeMath', (800, 0), operation='MULTIPLY_ADD')
    M.link(nt, st.outputs[0], st2.inputs[0])
    M.link(nt, L(sepc, 'Y'), st2.inputs[1])
    st2.inputs[2].default_value = 0.0
    M.link(nt, st2.outputs[0], S(b, 'Emission Strength'))
    return m, st.inputs[1]


CITY_COLORS = ['#FFB25C', '#FFB25C', '#FFD9A8', '#FFD9A8', '#FFE7C4', '#CFE3FF', '#9FD8FF', '#FF6B4A', '#FF6FAE',
               '#FFC46B']


def build_city(coll, room: Room, *, seed: int = 11, n_buildings: int = 44, n_lights: int = 700):
    """The skyline beyond the window: a gradient sky, dark towers with lit windows, and bright point lights (which
    the macro lenses turn into bokeh). Everything is emissive (no lights), so it costs almost nothing."""
    r = geo.rng(seed)
    sky_m, ramp, sky_strength = _sky_material()
    sky = geo.mesh_obj('city.sky', [(-60000, 0, -20000), (60000, 0, -20000), (60000, 0, 30000), (-60000, 0, 30000)],
                       [(0, 1, 2, 3)], coll, sky_m)
    sky.location = (0, 14000, 0)
    sky.visible_shadow = False
    room.sky_nodes = ramp
    room.sky_strength = sky_strength
    ground = -3200.0
    fac_mats = []
    for k in range(3):
        m, sock = _facade_material(f'city.facade{k}', seed * 10 + k, lit=[0.16, 0.24, 0.1][k], strength=1.1)
        fac_mats.append(m)
        room.city_sockets.append(sock)
        room.city_base.append(sock.default_value)
    bld = []
    for i in range(n_buildings):
        x = (r() * 2 - 1) * 14000
        y = 5000 + r() ** 0.8 * 16000
        w = 700 + r() * 1800
        d = 600 + r() * 1200
        top = -800 + r() ** 1.5 * 7000 * (0.45 + 0.55 * (y / 21000))
        h = top - ground
        o = geo.box(f'city.b{i}', (w, d, h), (x, y, ground + h / 2), m=fac_mats[i % 3], coll=coll, uv=False)
        o.visible_shadow = False
        bld.append((x, y, w, d, top))
    # point lights: facade lamps, rooftop beacons, a far band of street/highway lights
    bm = bmesh.new()
    colattr = bm.verts.layers.float_color.new('city.col')

    def light(p, rad, colr):
        res = bmesh.ops.create_icosphere(bm, subdivisions=1, radius=rad, matrix=Matrix.Translation(p))
        c = kit.srgb(colr)
        for v in res['verts']:
            v[colattr] = c
    for i in range(n_lights):
        kind = r()
        if kind < 0.55 and bld:
            x, y, w, d, top = bld[int(r() * len(bld))]
            p = Vector((x + (r() - 0.5) * w, y - d / 2 - 30, ground + 200 + r() * (top - ground - 200)))
            light(p, 14 + r() * 30, CITY_COLORS[int(r() * len(CITY_COLORS))])
        elif kind < 0.62 and bld:
            x, y, w, d, top = bld[int(r() * len(bld))]
            light(Vector((x + (r() - 0.5) * w * 0.8, y, top + 40)), 24 + r() * 14, '#FF3B2E')
        else:
            t = r()
            p = Vector(((t * 2 - 1) * 16000, 5000 + r() * 16000, -900 + r() * 900 + (r() ** 3) * 3500))
            light(p, 20 + r() * 34, CITY_COLORS[int(r() * len(CITY_COLORS))])
    me = bpy.data.meshes.new('city.lights')
    bm.to_mesh(me)
    bm.free()
    lo = bpy.data.objects.new('city.lights', me)
    coll.objects.link(lo)
    lo.visible_shadow = False
    lm, fresh = M.new_mat('city.lightmat')
    nt = lm.node_tree
    b = M.principled(lm)
    M.setin(b, 'Base Color', (0, 0, 0, 1))
    at = M.node(nt, 'ShaderNodeAttribute', (-400, 0))
    at.attribute_name = 'city.col'
    M.link(nt, M.sout(at, 'Color'), M.sin(b, 'Emission Color'))
    M.setin(b, 'Emission Strength', 45.0)
    me.materials.append(lm)
    s = M.sin(b, 'Emission Strength')
    room.city_sockets.append(s)
    room.city_base.append(s.default_value)
    return sky, lo


# ------------------------------------------------------------------------------------------------ atmosphere


def build_motes(coll, room: Room, box_min=(-20.0, -26.0, 0.5), box_max=(46.0, 26.0, 44.0), *, count: int = 1400,
                seed: int = 5, radius: float = 0.026, drift: float = 0.35, cone=None):
    """Dust motes drifting in the lamp's cone: geometry nodes, a pure function of scene time (no bake).

    cone: (apex, axis, inner_deg, outer_deg) world-space; motes shrink to nothing outside it (so unlit motes never
    show as dark specks against lit surfaces)."""
    me = bpy.data.meshes.new('desk.motes')
    o = bpy.data.objects.new('desk.motes', me)
    coll.objects.link(o)
    o.visible_shadow = False
    ng = bpy.data.node_groups.new('desk.motes', 'GeometryNodeTree')
    ng.interface.new_socket('Geometry', in_out='INPUT', socket_type='NodeSocketGeometry')
    ng.interface.new_socket('Geometry', in_out='OUTPUT', socket_type='NodeSocketGeometry')
    N, S, L = M.node, M.sin, M.sout
    gi = N(ng, 'NodeGroupInput', (-1400, 0))
    go = N(ng, 'NodeGroupOutput', (800, 0))
    pts = N(ng, 'GeometryNodePoints', (-1000, 0))
    S(pts, 'Count').default_value = count
    rnd = N(ng, 'FunctionNodeRandomValue', (-1200, -200))
    rnd.data_type = 'FLOAT_VECTOR'
    S(rnd, 'Min', 'VECTOR').default_value = (0, 0, 0)
    S(rnd, 'Max', 'VECTOR').default_value = (1, 1, 1)
    S(rnd, 'Seed').default_value = seed
    vel = N(ng, 'FunctionNodeRandomValue', (-1200, -450))
    vel.data_type = 'FLOAT_VECTOR'
    S(vel, 'Min', 'VECTOR').default_value = (-0.012, -0.012, -0.02)
    S(vel, 'Max', 'VECTOR').default_value = (0.012, 0.012, 0.008)
    S(vel, 'Seed').default_value = seed + 1
    tm = N(ng, 'GeometryNodeInputSceneTime', (-1200, -650))
    # p = wrap(rand + vel * t, 0, 1) -> box
    sc = N(ng, 'ShaderNodeVectorMath', (-1000, -450), operation='SCALE')
    M.link(ng, L(vel, 'Value', 'VECTOR'), sc.inputs[0])
    M.link(ng, L(tm, 'Seconds'), S(sc, 'Scale'))
    add = N(ng, 'ShaderNodeVectorMath', (-800, -300), operation='ADD')
    M.link(ng, L(rnd, 'Value', 'VECTOR'), add.inputs[0])
    M.link(ng, L(sc, 'Vector'), add.inputs[1])
    wr = N(ng, 'ShaderNodeVectorMath', (-600, -300), operation='WRAP')
    M.link(ng, L(add, 'Vector'), wr.inputs[0])
    wr.inputs[1].default_value = (1, 1, 1)
    wr.inputs[2].default_value = (0, 0, 0)
    size = Vector(box_max) - Vector(box_min)
    mul = N(ng, 'ShaderNodeVectorMath', (-400, -300), operation='MULTIPLY')
    M.link(ng, L(wr, 'Vector'), mul.inputs[0])
    mul.inputs[1].default_value = size
    off = N(ng, 'ShaderNodeVectorMath', (-200, -300), operation='ADD')
    M.link(ng, L(mul, 'Vector'), off.inputs[0])
    off.inputs[1].default_value = box_min
    # wobble: 4D noise of (position, time)
    nz = N(ng, 'ShaderNodeTexNoise', (-200, -600))
    nz.noise_dimensions = '4D'
    S(nz, 'Scale').default_value = 0.08
    M.link(ng, L(off, 'Vector'), S(nz, 'Vector'))
    tw = N(ng, 'ShaderNodeMath', (-400, -700), operation='MULTIPLY')
    M.link(ng, L(tm, 'Seconds'), tw.inputs[0])
    tw.inputs[1].default_value = drift
    M.link(ng, tw.outputs[0], S(nz, 'W'))
    ctr = N(ng, 'ShaderNodeVectorMath', (0, -600), operation='SUBTRACT')
    M.link(ng, L(nz, 'Color'), ctr.inputs[0])
    ctr.inputs[1].default_value = (0.5, 0.5, 0.5)
    amp = N(ng, 'ShaderNodeVectorMath', (200, -600), operation='SCALE')
    M.link(ng, L(ctr, 'Vector'), amp.inputs[0])
    S(amp, 'Scale').default_value = 3.0
    pos = N(ng, 'ShaderNodeVectorMath', (200, -300), operation='ADD')
    M.link(ng, L(off, 'Vector'), pos.inputs[0])
    M.link(ng, L(amp, 'Vector'), pos.inputs[1])
    M.link(ng, L(pos, 'Vector'), S(pts, 'Position'))
    ico = N(ng, 'GeometryNodeMeshIcoSphere', (-200, 200))
    S(ico, 'Radius').default_value = radius
    S(ico, 'Subdivisions').default_value = 2
    rs = N(ng, 'FunctionNodeRandomValue', (-200, 400))
    rs.data_type = 'FLOAT'
    S(rs, 'Min', 'VALUE').default_value = 0.35
    S(rs, 'Max', 'VALUE').default_value = 1.15
    S(rs, 'Seed').default_value = seed + 2
    inst = N(ng, 'GeometryNodeInstanceOnPoints', (200, 0))
    M.link(ng, L(pts, 'Points'), S(inst, 'Points'))
    M.link(ng, L(ico, 'Mesh'), S(inst, 'Instance'))
    scale_out = L(rs, 'Value', 'VALUE')
    if cone is not None:
        apex, axis, inner, outer = cone
        rel = N(ng, 'ShaderNodeVectorMath', (0, 700), operation='SUBTRACT')
        M.link(ng, L(pos, 'Vector'), rel.inputs[0])
        rel.inputs[1].default_value = tuple(apex)
        nrm = N(ng, 'ShaderNodeVectorMath', (150, 700), operation='NORMALIZE')
        M.link(ng, L(rel, 'Vector'), nrm.inputs[0])
        dot = N(ng, 'ShaderNodeVectorMath', (300, 700), operation='DOT_PRODUCT')
        M.link(ng, L(nrm, 'Vector'), dot.inputs[0])
        dot.inputs[1].default_value = tuple(Vector(axis).normalized())
        mr = N(ng, 'ShaderNodeMapRange', (450, 700))
        M.link(ng, L(dot, 'Value'), S(mr, 'Value', 'VALUE'))
        S(mr, 'From Min', 'VALUE').default_value = math.cos(math.radians(outer))
        S(mr, 'From Max', 'VALUE').default_value = math.cos(math.radians(inner))
        mul2 = N(ng, 'ShaderNodeMath', (600, 600), operation='MULTIPLY')
        M.link(ng, L(mr, 'Result', 'VALUE'), mul2.inputs[0])
        M.link(ng, scale_out, mul2.inputs[1])
        scale_out = mul2.outputs[0]
    M.link(ng, scale_out, S(inst, 'Scale'))
    real = N(ng, 'GeometryNodeRealizeInstances', (400, 0))
    M.link(ng, L(inst, 'Instances'), S(real, 'Geometry'))
    sm = N(ng, 'GeometryNodeSetMaterial', (600, 0))
    M.link(ng, L(real, 'Geometry'), S(sm, 'Geometry'))
    mote_m = M.solid('desk.mote', '#FFF6E8', rough=0.5, sss=0.4, sss_radius=(1, 1, 1), spec=0.3)
    S(sm, 'Material').default_value = mote_m
    M.link(ng, L(sm, 'Geometry'), go.inputs[0])
    mod = o.modifiers.new('motes', 'NODES')
    mod.node_group = ng
    room.motes = o
    return o


def build_haze(coll, room: Room, lo=(-85.0, -45.0, 0.0), hi=(85.0, 45.0, 70.0), density: float = 0.0012):
    """A faint volume over the desk: the lamp's cone and the window light become visible shafts."""
    c = (Vector(lo) + Vector(hi)) / 2
    s = Vector(hi) - Vector(lo)
    o = kit.box('desk.haze', tuple(s), tuple(c), coll=coll)
    m, fresh = M.new_mat('desk.haze')
    nt = m.node_tree
    for n in list(nt.nodes):
        if n.bl_idname != 'ShaderNodeOutputMaterial':
            nt.nodes.remove(n)
    out = nt.nodes.get('Material Output')
    v = M.node(nt, 'ShaderNodeVolumePrincipled', (0, 0))
    M.setin(v, 'Density', density)
    M.setin(v, 'Anisotropy', 0.2)
    M.setin(v, 'Color', (1, 1, 1, 1))
    M.link(nt, M.sout(v, 'Volume'), out.inputs['Volume'])
    o.data.materials.clear()
    o.data.materials.append(m)
    o.visible_shadow = False
    room.haze = o
    room.haze_density = M.sin(v, 'Density')
    return o


def build_moonlight(coll, room: Room):
    """The cool light from outside, coming in through the window (a big soft area light behind the glass)."""
    x0, x1, z0, z1 = WIN
    ld = bpy.data.lights.new('window.light', 'AREA')
    ld.shape, ld.size, ld.size_y = 'RECTANGLE', (x1 - x0) * 0.9, (z1 - z0) * 0.9
    ld.color = kit.srgb('#7F9CCB')[:3]
    ld.energy = 1.0
    o = bpy.data.objects.new('window.light', ld)
    coll.objects.link(o)
    o.location = ((x0 + x1) / 2, WALL_Y + WALL_T + 30, (z0 + z1) / 2 + 20)
    kit.aim(o, (0, -10, 0))
    ld.transmission_factor = 0.0     # don't show the softbox through the glass
    ld.volume_factor = 0.6
    ld.specular_factor = 0.35        # a soft window reflection in the lacquer, not a white sheet
    room.moon = o
    return o


def build_bounce(coll, room: Room):
    """The lamp's light bouncing off the ceiling and walls: a big, dim, warm soft light from above the desk that
    keeps the desk's edges (drawer unit, books, kill switch) readable outside the lamp's pool."""
    ld = bpy.data.lights.new('room.bounce', 'AREA')
    ld.shape, ld.size, ld.size_y = 'RECTANGLE', 220.0, 140.0
    ld.color = kit.srgb('#FFD2A0')[:3]
    ld.energy = 1.0
    ld.volume_factor = 0.0
    ld.specular_factor = 0.0      # ambient only: no giant rectangle reflected in the lacquer
    ld.use_shadow = True
    o = bpy.data.objects.new('room.bounce', ld)
    coll.objects.link(o)
    o.location = (10, -30, 150)
    kit.aim(o, (0, 0, 0))
    room.bounce = o
    return o
