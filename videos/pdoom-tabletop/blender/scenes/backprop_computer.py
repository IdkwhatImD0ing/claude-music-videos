"""The `backprop` scene's model vacuum-tube computer (a desk model of von Neumann's IAS machine), the little shelf it
stands on, its shatter (fx.fracture + fx.rigid) and the keyed pieces that must land where the camera wants them
(the brass plaque, the hero tube that rolls into the domino), the sparks and the domino.

Model-local frame: origin at the bottom centre of the plinth, x right, y back, z up; front face at y = -3.4.
Sizes (cm): plinth 13 x 6.8 x 0.9; cabinet 12 x 6 x 8.6 (painted balsa, grey-green); on its front a brass plaque
"VON NEUMANN", a black panel with 8 x 4 blinking lamps and two tape reels; on top six glass vacuum tubes with
glowing filaments in black bakelite bases. Total height ~12.4.
"""
from __future__ import annotations

import math

import bmesh
import bpy
from mathutils import Matrix, Vector

from pdoom import kit
from pdoom.fx import fracture, rigid, vis
from pdoom.fx import materials as FXM
from pdoom.sets import geo
from pdoom.sets import materials as M
from pdoom.timing import FPS

FRONT = -3.4
TUBE_X = [-4.6, -2.76, -0.92, 0.92, 2.76, 4.6]
TOP = 9.5
HERO_TUBE = 4          # this tube survives whole and rolls into the domino


# ------------------------------------------------------------------------------------------------ materials


def lamp_mat():
    """The panel lamps: each lamp object has a 'seed' property; they blink from a hash of (seed, clock); the keyed
    Value nodes 'clock' (ticks) and 'power' (0..1) run them."""
    m, fresh = M.new_mat('bp.vn.lamp')
    if not fresh:
        return m
    nt = m.node_tree
    b = M.principled(m)
    b.location = (600, 0)
    M.setin(b, 'Base Color', kit.srgb('#FFF2DA'))
    M.setin(b, 'Roughness', 0.15)
    M.setin(b, 'Coat Weight', 1.0)
    at = M.node(nt, 'ShaderNodeAttribute', (-1200, 0))
    at.attribute_type = 'OBJECT'
    at.attribute_name = 'seed'
    clk = M.node(nt, 'ShaderNodeValue', (-1200, -200))
    clk.name = clk.label = 'clock'
    pw = M.node(nt, 'ShaderNodeValue', (-1200, -400))
    pw.name = pw.label = 'power'
    pw.outputs[0].default_value = 1.0
    # tick = floor(clock + seed * 3)
    ms = M.node(nt, 'ShaderNodeMath', (-1000, -100), operation='MULTIPLY_ADD')
    M.link(nt, at.outputs['Fac'], ms.inputs[0])
    ms.inputs[1].default_value = 3.0
    M.link(nt, clk.outputs[0], ms.inputs[2])
    fl = M.node(nt, 'ShaderNodeMath', (-850, -100), operation='FLOOR')
    M.link(nt, ms.outputs[0], fl.inputs[0])
    cmb = M.node(nt, 'ShaderNodeCombineXYZ', (-700, -100))
    M.link(nt, at.outputs['Fac'], cmb.inputs['X'])
    M.link(nt, fl.outputs[0], cmb.inputs['Y'])
    wn = M.node(nt, 'ShaderNodeTexWhiteNoise', (-550, -100))
    wn.noise_dimensions = '2D'
    M.link(nt, cmb.outputs[0], M.sin(wn, 'Vector'))
    gt = M.node(nt, 'ShaderNodeMath', (-380, -100), operation='GREATER_THAN')
    M.link(nt, wn.outputs['Value'], gt.inputs[0])
    gt.inputs[1].default_value = 0.42
    mul = M.node(nt, 'ShaderNodeMath', (-220, -100), operation='MULTIPLY')
    M.link(nt, gt.outputs[0], mul.inputs[0])
    M.link(nt, pw.outputs[0], mul.inputs[1])
    st = M.node(nt, 'ShaderNodeMath', (-60, -100), operation='MULTIPLY')
    M.link(nt, mul.outputs[0], st.inputs[0])
    st.inputs[1].default_value = 7.0
    M.link(nt, st.outputs[0], M.sin(b, 'Emission Strength'))
    # colour: mostly warm white, one in five red
    cr = M.node(nt, 'ShaderNodeMath', (-700, 200), operation='GREATER_THAN')
    M.link(nt, at.outputs['Fac'], cr.inputs[0])
    cr.inputs[1].default_value = 0.8
    mix = M.node(nt, 'ShaderNodeMix', (-400, 200), data_type='RGBA', blend_type='MIX')
    M.link(nt, cr.outputs[0], M.sin(mix, 'Factor', 'VALUE'))
    M.setin(mix, 'A', kit.srgb('#FFC870'), 'RGBA')
    M.setin(mix, 'B', kit.srgb('#FF4A30'), 'RGBA')
    M.link(nt, M.sout(mix, 'Result', 'RGBA'), M.sin(b, 'Emission Color'))
    m.diffuse_color = kit.srgb('#FFF2DA')
    return m


def filament_mat(name='bp.vn.filament'):
    """Glowing filament: keyed 'glow' Value (0..~3) times an orange emission."""
    m, fresh = M.new_mat(name)
    if not fresh:
        return m
    nt = m.node_tree
    b = M.principled(m)
    M.setin(b, 'Base Color', kit.srgb('#3A2A20'))
    M.setin(b, 'Emission Color', kit.srgb('#FF8A2A'))
    g = M.node(nt, 'ShaderNodeValue', (-600, -200))
    g.name = g.label = 'glow'
    g.outputs[0].default_value = 1.0
    mul = M.node(nt, 'ShaderNodeMath', (-400, -200), operation='MULTIPLY')
    M.link(nt, g.outputs[0], mul.inputs[0])
    mul.inputs[1].default_value = 14.0
    M.link(nt, mul.outputs[0], M.sin(b, 'Emission Strength'))
    m.diffuse_color = kit.srgb('#FF8A2A')
    return m


def tube_glass():
    return FXM.glass('bp.vn.tubeglass', tint='#EAF2F0', rough=0.03, thin=True)


def paint():
    return M.enamel('bp.vn.paint', '#6A7B6C', rough=0.42, coat=0.25)


def balsa():
    return M.solid('bp.vn.balsa', '#B58C5C', rough=0.85, micro=(10.0, 0.12))


def spark_mat():
    return M.emissive('bp.spark', '#FFC56A', 60.0)


# ------------------------------------------------------------------------------------------------ the model


def hollow_box(coll, name, size, wall, mats):
    """A closed hollow box (a painted balsa cabinet): outer shell with material 0, the inside with material 1, as
    one closed mesh so fx.fracture can break it into wall panels. A bevel softens the outer edges."""
    bm = bmesh.new()
    sx, sy, sz = size
    for k, (ex, ey, ez, flip, mi) in enumerate(((sx, sy, sz, False, 0),
                                                 (sx - 2 * wall, sy - 2 * wall, sz - 2 * wall, True, 1))):
        r = bmesh.ops.create_cube(bm, size=1.0)
        vs = r['verts']
        bmesh.ops.scale(bm, vec=(ex, ey, ez), verts=vs)
        fs = list({f for v in vs for f in v.link_faces})
        for f in fs:
            f.material_index = mi
        if flip:
            bmesh.ops.reverse_faces(bm, faces=fs)
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    o = bpy.data.objects.new(name, me)
    coll.objects.link(o)
    for m in mats:
        me.materials.append(m)
    mod = o.modifiers.new('bevel', 'BEVEL')
    mod.width, mod.segments, mod.limit_method = 0.18, 3, 'ANGLE'
    geo.box_uv(o)
    kit.smooth(o, 40)
    return o


def _tube(coll, name, *, filament_m):
    """One vacuum tube, origin at its base's bottom centre: bakelite base (r 0.46, h 0.5), glass envelope (a closed
    capsule, r 0.42, 2.5 tall with a tip), a grey anode plate and a glowing filament inside. Returns
    (base, glass, inner parts)."""
    base = geo.lathe(f'{name}.base', [(0.0, 0.0), (0.46, 0.0), (0.48, 0.08), (0.48, 0.42), (0.42, 0.5), (0.0, 0.5)],
                     segs=24, coll=coll, m=M.plastic('bp.vn.bakelite', '#171311', rough=0.3, coat=0.4))
    for k in range(4):
        a = math.radians(45 + 90 * k)
        pin = kit.cylinder(f'{name}.pin{k}', 0.05, 0.45, (0.25 * math.cos(a), 0.25 * math.sin(a), -0.2), verts=8,
                           m=M.chrome('bp.chrome'), coll=coll)
        geo.attach(pin, base, Vector((0.25 * math.cos(a), 0.25 * math.sin(a), -0.2)))
    prof = [(0.0, 0.48), (0.4, 0.48), (0.42, 0.62), (0.42, 2.45), (0.36, 2.75), (0.18, 2.9), (0.07, 2.95),
            (0.05, 3.08), (0.0, 3.1)]
    glass = geo.lathe(f'{name}.glass', prof, segs=32, coll=coll, m=tube_glass(), smooth_angle=60)
    plate = geo.box(f'{name}.plate', (0.5, 0.12, 1.1), (0, 0, 0), m=M.solid('bp.vn.plate', '#6E6E6A', rough=0.4,
                                                                               metal=0.8), coll=coll)
    geo.attach(plate, base, Vector((0, 0.12, 1.45)))
    fil = kit.cylinder(f'{name}.filament', 0.05, 1.0, (0, 0, 0), verts=8, m=filament_m, coll=coll)
    geo.attach(fil, base, Vector((0, -0.08, 1.45)))
    fil.visible_shadow = False
    getter = kit.cylinder(f'{name}.getter', 0.3, 0.05, (0, 0, 0), verts=16, m=M.chrome('bp.chrome'), coll=coll)
    geo.attach(getter, base, Vector((0, 0, 2.3)))
    return base, glass, [plate, fil, getter]


def build_model(coll, name='vn'):
    """Build the model with every part parented to a root Empty (origin at the plinth's bottom centre).
    Returns a dict of parts."""
    P = {'lamps': [], 'tubes': [], 'reels': []}
    root = kit.empty(f'{name}.root', (0, 0, 0), coll, 'ARROWS', 3.0)
    P['root'] = root

    def put(o, loc=(0, 0, 0), rot=None):
        geo.attach(o, root, Vector(loc), rot)
        return o
    plinth = geo.box(f'{name}.plinth', (13.0, 6.8, 0.9), (0, 0, 0), bev=0.15, m=M.solid(
        'bp.vn.walnut', '#3B261A', rough=0.35, coat=0.6, coat_rough=0.12, micro=(6.0, 0.03)), coll=coll)
    put(plinth, (0, 0, 0.45))
    P['plinth'] = plinth
    cab = hollow_box(coll, f'{name}.cabinet', (12.0, 6.0, 8.6), 0.25, [paint(), balsa()])
    put(cab, (0, 0, 0.9 + 4.3))
    P['cabinet'] = cab
    # vents on the sides: a few dark slots
    panel = geo.box(f'{name}.panel', (10.2, 0.2, 3.9), (0, 0, 0), bev=0.05, m=M.solid(
        'bp.vn.panel', '#141414', rough=0.6, coat=0.15), coll=coll)
    put(panel, (0, FRONT + 0.3, 4.15))
    P['panel'] = panel
    lm = lamp_mat()
    k = 0
    for row in range(4):
        for col in range(8):
            o = kit.sphere(f'{name}.lamp.{k:02d}', 0.2, (0, 0, 0), m=lm, coll=coll, subdiv=2)
            o['seed'] = geo.hash01('lamp', k)
            put(o, (-4.2 + col * 1.2, FRONT + 0.15, 2.65 + row * 1.0))
            P['lamps'].append(o)
            k += 1
    for sx in (-1, 1):
        reel = geo.lathe(f'{name}.reel{sx}', [(0.0, -0.18), (1.2, -0.18), (1.22, -0.12), (1.22, 0.12),
                                               (1.2, 0.18), (0.0, 0.18)], segs=40, coll=coll,
                         m=M.plastic('bp.vn.reel', '#1C1C1E', rough=0.25, coat=0.5))
        tape = geo.lathe(f'{name}.reel{sx}.tape', [(0.35, -0.13), (0.85, -0.13), (0.85, 0.13), (0.35, 0.13)],
                         segs=40, coll=coll, m=M.solid('bp.vn.tape', '#3A2418', rough=0.3, coat=0.4))
        hub = kit.cylinder(f'{name}.reel{sx}.hub', 0.3, 0.44, (0, 0, 0), verts=16, m=M.chrome('bp.chrome'),
                           coll=coll)
        put(reel, (sx * 2.7, FRONT - 0.1, 7.55), (math.radians(90), 0, 0))
        geo.attach(tape, reel)
        geo.attach(hub, reel)
        P['reels'].append(reel)
    # the plaque: brass, engraved VON NEUMANN
    plq = geo.box(f'{name}.plaque', (7.0, 0.14, 1.05), (0, 0, 0), bev=0.04, m=M.brass('bp.vn.brass', '#C9A45C',
                                                                                        0.22), coll=coll)
    put(plq, (0, FRONT - 0.06, 1.45))
    txt = geo.text_mesh(f'{name}.plaque.text', 'VON NEUMANN', 0.62, coll=coll,
                        m=M.solid('bp.vn.engrave', '#2A1E14', rough=0.5), extrude=0.02)
    geo.attach(txt, plq, Vector((0, -0.09, -0.02)), (math.radians(90), 0, 0))
    for sx in (-1, 1):
        sc = kit.cylinder(f'{name}.plaque.screw{sx}', 0.1, 0.06, (0, 0, 0), verts=12, m=M.chrome('bp.chrome'),
                          coll=coll, rot=(math.radians(90), 0, 0))
        geo.attach(sc, plq, Vector((sx * 3.15, -0.08, 0)))
    P['plaque'] = plq
    # tubes on top
    fm = filament_mat()
    fm_hero = filament_mat('bp.vn.filament.hero')
    for i, x in enumerate(TUBE_X):
        base, glass, inner = _tube(coll, f'{name}.tube{i}', filament_m=fm_hero if i == HERO_TUBE else fm)
        put(base, (x, 0.3, TOP))
        put(glass, (x, 0.3, TOP))
        P['tubes'].append((base, glass, inner))
    P['fm'], P['fm_hero'] = fm, fm_hero
    return P


# ------------------------------------------------------------------------------------------------ shelf, domino


def build_shelf(coll, loc: Vector, name='shelf'):
    """A small two-tier pine shelf, 16 x 11 x 13.5 cm (top surface at z 13.5), its front edge at loc.y, left side at
    loc.x. Returns (objects, top board)."""
    pine = M.solid('bp.pine', '#C79A63', rough=0.5, coat=0.25, micro=(4.0, 0.05))
    W, D, Hh, t = 16.0, 11.0, 13.5, 1.2
    x0, y0 = loc.x, loc.y
    objs = []
    top = geo.box(f'{name}.top', (W, D, t), (x0 + W / 2, y0 + D / 2, Hh - t / 2), bev=0.12, m=pine, coll=coll)
    objs.append(top)
    for sx in (0, 1):
        s = geo.box(f'{name}.side{sx}', (t, D, Hh - t), (x0 + t / 2 + sx * (W - t), y0 + D / 2, (Hh - t) / 2),
                    bev=0.1, m=pine, coll=coll)
        objs.append(s)
    mid = geo.box(f'{name}.mid', (W - 2 * t, D - 0.4, t * 0.8), (x0 + W / 2, y0 + D / 2 + 0.2, 6.3), bev=0.08,
                  m=pine, coll=coll)
    objs.append(mid)
    back = geo.box(f'{name}.back', (W - 2 * t, 0.5, Hh - t), (x0 + W / 2, y0 + D - 0.25, (Hh - t) / 2), m=pine,
                   coll=coll)
    objs.append(back)
    # a stack of punch cards on the lower tier and a small box on the floor tier
    cards = geo.box(f'{name}.cards', (8.3, 4.0, 1.6), (x0 + 5.8, y0 + 4.2, 6.3 + 0.48 + 0.8), bev=0.03,
                    m=M.solid('bp.cards', '#E8DDC4', rough=0.8, micro=(20.0, 0.1)), coll=coll)
    objs.append(cards)
    return objs, top


def build_domino(coll, loc, yaw_deg=0.0, name='domino'):
    """A classic domino (black lacquer, white pips) standing on end: 4.8 x 2.4 x 0.8 cm; origin at the bottom
    centre."""
    blk = M.solid('bp.domino', '#121212', rough=0.2, coat=0.8, coat_rough=0.05)
    pip = M.solid('bp.pip', '#F2EEE6', rough=0.3)
    root = kit.empty(name, tuple(loc), coll, 'PLAIN_AXES', 1.0)
    root.rotation_euler = (0, 0, math.radians(yaw_deg))
    body = geo.box(f'{name}.body', (2.4, 0.8, 4.8), (0, 0, 0), bev=0.12, segments=3, m=blk, coll=coll)
    geo.attach(body, root, Vector((0, 0, 2.4)))
    bar = geo.box(f'{name}.bar', (1.9, 0.05, 0.08), (0, 0, 0), m=pip, coll=coll)
    geo.attach(bar, root, Vector((0, -0.41, 2.4)))
    for half, pts in ((1, [(-0.6, 0.6), (0.6, -0.6), (0, 0), (-0.6, -0.6), (0.6, 0.6)]), (-1, [(-0.6, 0.6),
                                                                                              (0.6, -0.6)])):
        for px, pz in pts:
            d = kit.cylinder(f'{name}.pip', 0.17, 0.06, (0, 0, 0), verts=14, m=pip, coll=coll,
                             rot=(math.radians(90), 0, 0))
            geo.attach(d, root, Vector((px * 0.9, -0.41, 2.4 + half * 1.2 + pz)))
    return root


# ------------------------------------------------------------------------------------------------ helpers


def world_copy(o, coll, suffix='.rb'):
    """An unparented copy of o (sharing its mesh) at o's world transform, plus copies of its children parented to
    it. Returns the copy."""
    c = o.copy()
    c.animation_data_clear()
    coll.objects.link(c)
    c.parent = None
    c.matrix_world = o.matrix_world.copy()
    c.name = o.name + suffix
    for ch in o.children:
        cc = ch.copy()
        cc.animation_data_clear()
        coll.objects.link(cc)
        cc.parent = c
        cc.matrix_parent_inverse = ch.matrix_parent_inverse.copy()
        cc.matrix_basis = ch.matrix_basis.copy()
        cc.name = ch.name + suffix
    return c


def all_children(o):
    out = []
    for ch in o.children:
        out.append(ch)
        out += all_children(ch)
    return out
