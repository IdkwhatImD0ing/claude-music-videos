"""The Chinese room set: a corrugated cardboard box on the desk with a brass mail slot in its left wall and a
knife-cut window in its front, and what's inside (a hanging bulb, the rulebook, a matchbox table, an ink pad, the
rubber stamp, the paper bag), the notes with Chinese on them, and Clawd's smiley mask on a stick.

World cm, desktop at z = 0. The box spans x -12..16, y -20..0, z 0..16.4 (lid flaps closed and taped); its floor is at
z = FLOOR. Everything is plain bmesh/objects, built once; room.py animates it.
"""
from __future__ import annotations

import math
import os

import bmesh
import bpy
from mathutils import Euler, Matrix, Vector

from pdoom import kit
from pdoom.chars import geo as cg
from pdoom.chars import looks
from pdoom.sets import geo
from pdoom.sets import materials as M

# ------------------------------------------------------------------------------------------------ layout (world cm)

X0, X1, Y0, Y1 = -12.0, 16.0, -20.0, 0.0      # outer walls
H = 16.0                                       # wall height (flaps on top)
T = 0.4                                        # corrugated board thickness
FLOOR = 0.4                                    # inside floor (the box bottom)
WIN = (-9.0, 12.0, 1.0, 12.0)                  # front-wall window (a low 'garage' cut): x0, x1, z0, z1
SLOT = (-12.4, -6.6, 2.6, 3.6)                 # left-wall mail slot: y0, y1, z0, z1
SLOT_C = Vector((X0, (SLOT[0] + SLOT[1]) / 2, (SLOT[2] + SLOT[3]) / 2))
BULB = Vector((1.5, -9.0, 12.2))
BAG = Vector((12.0, -3.5, FLOOR))              # paper bag (back-right corner inside)
BOOK = Vector((-0.8, -14.0, FLOOR))            # the open rulebook (in front of Clawd)
CLAWD = Vector((-1.8, -7.0, FLOOR))
MATCH = Vector((-8.75, -8.2, FLOOR))           # matchbox table (Clawd's right, by the slot)

FONT_HAND = 'C:/Windows/Fonts/simkai.ttf'      # KaiTi: brush handwriting
FONT_BOOK = 'C:/Windows/Fonts/simfang.ttf'     # FangSong: printed rulebook
FONT_SEAL = 'C:/Windows/Fonts/simhei.ttf'

QUESTION = ('你懂中文', '吗？')                    # "Do you understand Chinese?"
ANSWER = ('当然懂！',)                           # "Of course I understand!"
SEAL = '懂'                                     # the red chop: "understand"
RULES_L = ['你 → 我', '懂 → 懂', '吗 → ！', '中 → 当', '文 → 然', '？ → 。', '好 → 好', '谁 → 我']
RULES_R = ['是 → 是', '爱 → 爱', '人 → 机', '想 → 算', '知 → 道', '心 → 零', '梦 → 电', '怕 → 不']


class Box:
    """Handles to the set pieces (objects are None until built)."""


# ------------------------------------------------------------------------------------------------ materials


def cardboard():
    return M.cardboard('room.cardboard', tint=None)


def cardboard_edge():
    """The cut edge of corrugated board: two liners and a wavy flute between them, in object space. Walls are built
    with their thickness along local Y, so the same material reads right on every wall."""
    m, fresh = M.new_mat('room.cardboard.edge')
    if not fresh:
        return m
    nt = m.node_tree
    b = M.principled(m)
    tc = M.node(nt, 'ShaderNodeTexCoord', (-1200, 0))
    sep = M.node(nt, 'ShaderNodeSeparateXYZ', (-1000, 0))
    M.link(nt, M.sout(tc, 'Object'), M.sin(sep, 'Vector'))

    def math_(op, a, b_=None, loc=(-800, 0)):
        n = M.node(nt, 'ShaderNodeMath', loc, operation=op)
        for i, v in enumerate((a, b_)):
            if v is None:
                continue
            if isinstance(v, (int, float)):
                n.inputs[i].default_value = v
            else:
                M.link(nt, v, n.inputs[i])
        return n.outputs[0]
    u = math_('ADD', M.sout(sep, 'X'), M.sout(sep, 'Z'))
    wave = math_('SINE', math_('MULTIPLY', u, 2 * math.pi / 0.42))
    y = M.sout(sep, 'Y')
    liner = math_('GREATER_THAN', math_('ABSOLUTE', y), T / 2 - 0.055)
    flute = math_('LESS_THAN', math_('ABSOLUTE', math_('SUBTRACT', y, math_('MULTIPLY', wave, T / 2 - 0.09))), 0.035)
    paper = math_('MAXIMUM', liner, flute)
    mix = M.node(nt, 'ShaderNodeMix', (-300, 0), data_type='RGBA')
    M.setin(mix, 'A', kit.srgb('#2E2014'), 'RGBA')
    M.setin(mix, 'B', kit.srgb('#B98A58'), 'RGBA')
    M.link(nt, paper, M.sin(mix, 'Factor', 'VALUE'))
    M.link(nt, M.sout(mix, 'Result', 'RGBA'), M.sin(b, 'Base Color'))
    M.setin(b, 'Roughness', 0.92)
    M.setin(b, 'Specular IOR Level', 0.25)
    m.diffuse_color = kit.srgb('#8A6440')
    return m


def kraft(name='room.kraft', tint='#A87A4C'):
    return M.solid(name, tint, rough=0.85, sheen=0.3, micro=(9.0, 0.08))


def card_paper(name='room.card', tint='#F3ECDC'):
    return M.paper(name, tint=tint, tile=18)


def ink(name='room.ink', color='#141110'):
    return M.solid(name, color, rough=0.55, spec=0.3)


def red_ink():
    return M.solid('room.redink', '#C8231E', rough=0.6, spec=0.3)


# ------------------------------------------------------------------------------------------------ helpers


def _cells(bm, xs, zs, t, holes, *, mat_face=0, mat_edge=1):
    """A slab in local XZ (thickness along Y, centred) made of axis-aligned cells, skipping cells inside holes.
    Faces facing +-Y get mat_face, the thin edges mat_edge (the corrugation shows on every cut)."""
    xs, zs = sorted(set(xs)), sorted(set(zs))
    for i in range(len(xs) - 1):
        for k in range(len(zs) - 1):
            cx, cz = (xs[i] + xs[i + 1]) / 2, (zs[k] + zs[k + 1]) / 2
            if any(h[0] < cx < h[1] and h[2] < cz < h[3] for h in holes):
                continue
            a, b_, c, d = xs[i], xs[i + 1], zs[k], zs[k + 1]
            v = [bm.verts.new((x, y, z)) for x in (a, b_) for y in (-t / 2, t / 2) for z in (c, d)]
            # vertex index = xi*4 + yi*2 + zi
            faces = [((0, 4, 5, 1), mat_face), ((2, 3, 7, 6), mat_face), ((0, 1, 3, 2), mat_edge),
                     ((4, 6, 7, 5), mat_edge), ((0, 2, 6, 4), mat_edge), ((1, 5, 7, 3), mat_edge)]
            for idx, mi in faces:
                f = bm.faces.new([v[j] for j in idx])
                f.material_index = mi
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])


def _obj(bm, name, coll, mats, *, smooth=False):
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    for m in mats:
        me.materials.append(m)
    if smooth:
        for p in me.polygons:
            p.use_smooth = True
    o = bpy.data.objects.new(name, me)
    coll.objects.link(o)
    return o


def wall(name, coll, length, height, holes=(), *, extra_x=(), extra_z=()):
    """A corrugated wall in local coords: x 0..length, z 0..height, thickness along Y. holes: (x0, x1, z0, z1)."""
    bm = bmesh.new()
    xs = [0.0, length, *extra_x] + [v for h in holes for v in h[:2]]
    zs = [0.0, height, *extra_z] + [v for h in holes for v in h[2:]]
    _cells(bm, xs, zs, T, holes)
    o = _obj(bm, name, coll, [cardboard(), cardboard_edge()])
    geo.box_uv(o)
    return o


def place(o, loc, rot_deg=(0, 0, 0)):
    o.location = loc
    o.rotation_euler = tuple(math.radians(a) for a in rot_deg)
    return o


def text(name, lines, size, font_path, coll, m, *, spacing=1.0, line_gap=1.15, align='CENTER'):
    """Flat CJK text as a mesh in the local XY plane (reads from +Z), centred on the origin."""
    cd = bpy.data.curves.new(name, 'FONT')
    cd.body = '\n'.join(lines) if isinstance(lines, (list, tuple)) else lines
    font_path = geo.sysfont(font_path)
    if os.path.exists(font_path):
        cd.font = bpy.data.fonts.load(font_path, check_existing=True)
    cd.size = size
    cd.align_x = align
    cd.align_y = 'CENTER'
    cd.space_character = spacing
    cd.space_line = line_gap
    cd.resolution_u = 3
    cd.fill_mode = 'BOTH'
    o = bpy.data.objects.new(name, cd)
    coll.objects.link(o)
    o = geo.convert_to_mesh(o)
    o.data.materials.clear()
    o.data.materials.append(m)
    return o


def attach_rigid(child, par):
    """Parent keeping the child's world transform."""
    bpy.context.view_layer.update()
    mw = child.matrix_world.copy()
    child.parent = par
    child.matrix_parent_inverse = par.matrix_world.inverted()
    child.matrix_world = mw
    return child


# ------------------------------------------------------------------------------------------------ the box


def build_box(coll) -> Box:
    b = Box()
    L = X1 - X0
    D = Y1 - Y0
    # front wall (y = Y0) with the window; local x runs +X, local y = thickness (-> world y)
    wx0, wx1, wz0, wz1 = WIN
    b.front = place(wall('box.front', coll, L, H, [(wx0 - X0, wx1 - X0, wz0, wz1)]), (X0, Y0 + T / 2, 0))
    b.back = place(wall('box.back', coll, L, H), (X0, Y1 - T / 2, 0))
    # side walls fit between front and back; local x runs +Y (rotate 90 about Z: local x -> world y)
    sy0, sy1, sz0, sz1 = SLOT
    inner = D - 2 * T
    b.left = place(wall('box.left', coll, inner, H, [(sy0 - (Y0 + T), sy1 - (Y0 + T), sz0, sz1)]),
                   (X0 + T / 2, Y0 + T, 0), (0, 0, 90))
    b.right = place(wall('box.right', coll, inner, H), (X1 - T / 2, Y0 + T, 0), (0, 0, 90))
    # the window's cut-out, hinged along the sill and folded out and down onto the desk (a ramp)
    fw, fh = wx1 - wx0 - 0.1, wz1 - wz0 - 0.05
    flap = wall('box.windowflap', coll, fw, fh)
    for v in flap.data.vertices:          # hinge at local z = 0, flap along +z
        v.co.x -= fw / 2
    fold = 90 + math.degrees(math.asin(min(1.0, (wz0 - 0.2) / fh)))
    place(flap, ((wx0 + wx1) / 2, Y0 + T * 0.1, wz0), (fold, 0, 0))
    b.flap = flap
    b.flap_size = (fw, fh)
    # floor
    fl = geo.box('box.floor', (L - 2 * T, D - 2 * T, FLOOR), ((X0 + X1) / 2, (Y0 + Y1) / 2, FLOOR / 2), m=cardboard(),
                 coll=coll)
    b.floor = fl
    # lid: two long flaps meeting along y = centre, bowed a little; packing tape along the seam
    yc = (Y0 + Y1) / 2
    b.lid = []
    for side, (ya, yb) in (('f', (Y0, yc)), ('b', (yc, Y1))):
        fl2 = wall(f'box.lid.{side}', coll, L + 0.05, (yb - ya) - 0.08)
        # lay flat: local z -> world y (rotate +90 about X), thickness -> world z
        for v in fl2.data.vertices:
            x, y, z = v.co
            v.co = Vector((x, z, y))
        hinge_y = ya if side == 'f' else yb
        o = place(fl2, (X0 - 0.025, ya + 0.04, H + T / 2), (0, 0, 0))
        # bow: tilt each flap up ~1.5 deg about its outer (hinge) edge
        o.rotation_euler = (math.radians(1.6 if side == 'f' else -1.6), 0, 0)
        if side == 'b':
            o.location.y = ya + 0.04
            # rotate about the far edge: shift so the hinge stays put
            o.location.z = H + T / 2 + (yb - ya) * math.sin(math.radians(1.6))
        b.lid.append(o)
    tape_m = M.solid('room.tape', '#C79A5A', rough=0.22, coat=0.6, coat_rough=0.08, spec=0.6)
    tape = geo.box('box.tape', (L + 0.3, 4.8, 0.03), ((X0 + X1) / 2, yc, H + T + 0.3), m=tape_m, coll=coll)
    for sx in (X0 - 0.17, X1 + 0.17):
        geo.box('box.tape.side', (0.03, 4.8, 4.5), (sx, yc, H + T - 2.0), m=tape_m, coll=coll)
    b.tape = tape
    return b


# ------------------------------------------------------------------------------------------------ mail slot


def build_slot(coll, b: Box):
    """A small brass letterbox plate on the outside of the left wall, with a flap hinged along the top of the
    opening. b.slot_flap is an Empty at the hinge: key rotation_euler.y (+ swings the flap out, - into the box)."""
    brass = M.solid('room.brass', '#D2AE62', rough=0.38, metal=0.75, coat=0.3, coat_rough=0.1)
    sy0, sy1, sz0, sz1 = SLOT
    cy, cz = (sy0 + sy1) / 2, (sz0 + sz1) / 2
    x = X0 - 0.06
    bm = bmesh.new()
    pw, ph, pt = (sy1 - sy0) + 1.8, (sz1 - sz0) + 1.3, 0.12
    xs = [0, pw, 0.9, pw - 0.9]
    zs = [0, ph, 0.65, ph - 0.65]
    _cells(bm, xs, zs, pt, [(0.9, pw - 0.9, 0.65, ph - 0.65)], mat_face=0, mat_edge=0)
    plate = _obj(bm, 'slot.plate', coll, [brass])
    for v in plate.data.vertices:
        v.co.x -= pw / 2
        v.co.z -= ph / 2
    mod = plate.modifiers.new('bevel', 'BEVEL')
    mod.width, mod.segments, mod.limit_method = 0.04, 2, 'ANGLE'
    place(plate, (x, cy, cz), (0, 0, 90))
    kit.smooth(plate, 40)
    # two screws
    for dy in (-pw / 2 + 0.45, pw / 2 - 0.45):
        s = kit.cylinder('slot.screw', 0.13, 0.08, (x - 0.07, cy + dy, cz), verts=16, m=brass, coll=coll,
                         rot=(0, math.radians(90), 0))
    hinge = geo.empty('slot.hinge', (x - 0.12, cy, sz1 + 0.05), coll, 0.5)
    fw, fh = (sy1 - sy0) + 0.3, (sz1 - sz0) + 0.35
    flap = geo.box('slot.flap', (0.1, fw, fh), (0, 0, -fh / 2), m=brass, coll=coll, uv=False)
    flap.modifiers.new('bevel', 'BEVEL').width = 0.03
    geo.attach(flap, hinge, (0, 0, -fh / 2))
    # a little knob on the flap
    knob = kit.cylinder('slot.knob', 0.16, 0.18, (0, 0, 0), verts=16, m=brass, coll=coll, rot=(0, math.radians(90), 0))
    geo.attach(knob, hinge, (-0.12, 0, -fh + 0.3), (0, math.radians(90), 0))
    b.slot_flap = hinge
    b.slot_plate = plate


# ------------------------------------------------------------------------------------------------ bulb


def build_bulb(coll, b: Box):
    cord_m = M.rubber('room.cord', '#161412')
    top = Vector((BULB.x, BULB.y, H))
    cord = geo.curve_tube('bulb.cord', [top, BULB + Vector((0, 0, 1.25))], 0.06, coll=coll, m=cord_m, to_mesh=True)
    sock = kit.cylinder('bulb.socket', 0.42, 1.0, BULB + Vector((0, 0, 0.9)), verts=24, m=M.solid(
        'room.bakelite', '#1B1714', rough=0.35, coat=0.4), coll=coll)
    glass_m = M.emissive('room.bulb.glow', '#FFC77A', 6.0)
    bm = bmesh.new()
    cg.lathe(bm, [(0.0, -0.95), (0.45, -0.85), (0.7, -0.45), (0.72, 0.0), (0.55, 0.35), (0.34, 0.5), (0.32, 0.62),
                  (0.0, 0.62)], segs=32)
    bulb = cg.to_object(bm, 'bulb.glass', coll, [glass_m], sharp=None)
    bulb.location = BULB
    light = kit.point('bulb.light', BULB + Vector((0, 0, -0.1)), power=35000.0, radius=0.5, color='#FFC27A', coll=coll)
    b.bulb_light = light
    b.bulb_mat = glass_m
    b.bulb_parts = [cord, sock, bulb]
    piv = geo.empty('bulb.pivot', top, coll, 0.5)
    for o in (cord, sock, bulb, light):
        attach_rigid(o, piv)
    b.bulb_pivot = piv


# ------------------------------------------------------------------------------------------------ inside props


def build_book(coll, b: Box):
    """The rulebook: a thick cloth-bound tome lying open, pages of character-to-character rules."""
    cloth = M.solid('room.bookcloth', '#7A1F24', rough=0.8, sheen=0.4)
    page_m = card_paper('room.pages', '#E2D3B4')
    ink_m = ink('room.bookink', '#221A16')
    root = geo.empty('book', BOOK, coll, 1.0, rot=(0, 0, math.radians(6)))
    pw, ph, pt = 5.4, 8.0, 0.9
    cover = geo.box('book.cover', (2 * pw + 0.5, ph + 0.5, 0.16), (0, 0, 0.08), m=cloth, coll=coll)
    geo.attach(cover, root, (0, 0, 0.08))
    b.book_pages = []
    for side, rules in ((-1, RULES_L), (1, RULES_R)):
        pg = geo.box(f'book.pages{side}', (pw, ph, pt), (0, 0, 0), m=page_m, coll=coll)
        geo.attach(pg, root, (side * (pw / 2 + 0.05), 0, 0.16 + pt / 2), (0, math.radians(-side * 3.5), 0))
        tx = text(f'book.text{side}', rules, 0.58, FONT_BOOK, coll, ink_m, line_gap=1.12)
        geo.attach(tx, pg, (0, -0.1, pt / 2 + 0.006))
        b.book_pages.append(pg)
    # a ribbon bookmark
    rib = geo.box('book.ribbon', (0.3, 3.6, 0.02), (0, 0, 0), m=M.solid('room.ribbon', '#D8B23A', rough=0.4, sheen=0.5),
                  coll=coll)
    geo.attach(rib, root, (0.4, -ph / 2 - 1.4, 0.2))
    b.book = root


def build_table(coll, b: Box):
    """A matchbox (Clawd's desk) with the ink pad."""
    root = geo.empty('matchbox', MATCH, coll, 1.0, rot=(0, 0, math.radians(-8)))
    mw, md, mh = 5.3, 3.6, 1.6
    tray = geo.box('matchbox.body', (mw, md, mh), (0, 0, 0), bev=0.04, m=M.solid('room.matchbox', '#E4C24A', rough=0.6),
                   coll=coll)
    geo.attach(tray, root, (0, 0, mh / 2))
    band = geo.box('matchbox.band', (mw + 0.02, md * 0.42, mh + 0.02), (0, 0, 0), m=M.solid('room.matchband', '#B7302A',
                                                                                          rough=0.6), coll=coll)
    geo.attach(band, root, (0, 0, mh / 2))
    for sy in (-1, 1):
        st = geo.box('matchbox.striker', (mw * 0.9, 0.02, mh * 0.7), (0, 0, 0), m=M.solid('room.striker', '#4A3226',
                                                                                          rough=0.95), coll=coll)
        geo.attach(st, root, (0, sy * (md / 2 + 0.01), mh / 2))
    b.table = root
    b.table_top = mh
    # ink pad (a tin with red felt) on the matchbox's far end
    tin = kit.cylinder('inkpad.tin', 0.95, 0.45, (0, 0, 0), verts=32, m=M.brushed('room.tin', '#9FA6AE'), coll=coll)
    geo.attach(tin, root, (-1.7, 0.55, mh + 0.225))
    felt = kit.cylinder('inkpad.felt', 0.82, 0.05, (0, 0, 0), verts=32, m=M.felt('room.felt.red', '#A01818'), coll=coll)
    geo.attach(felt, root, (-1.7, 0.55, mh + 0.46))
    b.pad = tin


def note(coll, name, lines, *, font=FONT_HAND, size=0.62, w=3.6, d=2.6, paper='#F4EDDD', ink_col='#1A1614'):
    """A small paper card (w x d, 0.03 thick) with Chinese handwriting on top; its origin at the card's centre."""
    card = geo.box(name, (w, d, 0.03), (0, 0, 0), m=card_paper(f'room.card.{paper}', paper), coll=coll)
    tx = text(name + '.text', lines, size, font, coll, ink(f'room.ink.{ink_col}', ink_col), line_gap=1.05)
    geo.attach(tx, card, (0, 0, 0.018))
    return card


def seal(coll, name, size=0.95):
    """A red square chop (the stamp's print): a bordered square with 懂 in it, flat, reads from +Z."""
    red = red_ink()
    bm = bmesh.new()
    s = size / 2
    xs, zs = [-s, s, -s + 0.12, s - 0.12], [-s, s, -s + 0.12, s - 0.12]
    _cells(bm, xs, zs, 0.004, [(-s + 0.12, s - 0.12, -s + 0.12, s - 0.12)], mat_face=0, mat_edge=0)
    frame = _obj(bm, name, coll, [red])
    for v in frame.data.vertices:
        x, y, z = v.co
        v.co = Vector((x, z, y))
    ch = text(name + '.ch', SEAL, size * 0.72, FONT_SEAL, coll, red)
    geo.attach(ch, frame, (0, 0, 0.0))
    return frame


def build_stamp(coll, name='stamp'):
    """A small rubber stamp standing upright, rubber face at z = 0, knob on top (2.6 cm tall)."""
    wood = looks.wood('room.stampwood', '#D9B98C', '#B8905E')
    rub = M.solid('room.rubber.red', '#9E1C18', rough=0.7)
    bm = bmesh.new()
    cg.rounded_box(bm, (1.5, 1.5, 0.28), 0.04, (0, 0, 0.14), seg=2, mat=1)          # rubber
    cg.rounded_box(bm, (1.6, 1.6, 0.55), 0.12, (0, 0, 0.28 + 0.275), seg=3, mat=0)  # block
    cg.lathe(bm, [(0.0, 0.82), (0.32, 0.82), (0.26, 1.2), (0.22, 1.7), (0.42, 2.05), (0.5, 2.3), (0.38, 2.55),
                  (0.0, 2.62)], segs=24, mat=0)
    return cg.to_object(bm, name, coll, [wood, rub], sharp=50)


def build_bag(coll, b: Box):
    """An open kraft-paper lunch bag with a rolled rim, a few mushroom caps peeking out. Tips over about its
    front-left bottom edge: b.bag_pivot (Empty) at that edge; key its rotation."""
    kr = kraft()
    bw, bd, bh = 4.4, 3.0, 5.4
    bm = bmesh.new()
    # a crumpled open-top box: grid walls with a seeded jitter, thin
    N = 7

    def jit(*k):
        return (geo.hash01('bag', *k) - 0.5) * 0.22
    rings = []
    for iz in range(N + 1):
        z = bh * iz / N
        ring = []
        pts = []
        per = 2 * (bw + bd)
        for s in range(24):
            u = per * s / 24
            if u < bw:
                p = (-bw / 2 + u, -bd / 2)
            elif u < bw + bd:
                p = (bw / 2, -bd / 2 + (u - bw))
            elif u < 2 * bw + bd:
                p = (bw / 2 - (u - bw - bd), bd / 2)
            else:
                p = (-bw / 2, bd / 2 - (u - 2 * bw - bd))
            pts.append(p)
        for s, (x, y) in enumerate(pts):
            k = 1.0 + (0.06 if iz == N else 0.0)
            ring.append(bm.verts.new((x * k + jit(iz, s, 0) * (iz > 0), y * k + jit(iz, s, 1) * (iz > 0), z)))
        rings.append(ring)
    for A, B_ in zip(rings[:-1], rings[1:]):
        for s in range(24):
            j = (s + 1) % 24
            bm.faces.new((A[s], A[j], B_[j], B_[s]))
    bm.faces.new(list(reversed(rings[0])))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    o = _obj(bm, 'bag', coll, [kr], smooth=True)
    sol = o.modifiers.new('solid', 'SOLIDIFY')
    sol.thickness = 0.05
    geo.box_uv(o)
    # the rolled rim
    rim = geo.curve_tube('bag.rim', [(x * 1.08, y * 1.08, bh) for x, y in
                                     [(-bw / 2, -bd / 2), (bw / 2, -bd / 2), (bw / 2, bd / 2), (-bw / 2, bd / 2)]],
                         0.14, coll=coll, m=kr, closed=True, to_mesh=True)
    # pivot: the front-left bottom edge (the bag falls toward -x / -y, into the room)
    yaw = math.radians(35)
    off = Matrix.Rotation(yaw, 3, 'Z') @ Vector((bw / 2, 0, 0))
    piv = geo.empty('bag.pivot', BAG - off, coll, 1.0, rot=(0, 0, yaw))
    geo.attach(o, piv, (bw / 2, 0, 0))    # rotation_euler.y = -90 lays it on its side, mouth toward pivot -x
    geo.attach(rim, piv, (bw / 2, 0, 0))
    b.bag = o
    b.bag_pivot = piv
    b.bag_size = (bw, bd, bh)


def mask_on_stick(coll, c, pose, *, side='L', name='mask.stick'):
    """Clawd's smiley mask on a wooden stick, held in hand.<side>. `pose` is the arm pose (raise, swing, twist)
    at which the mask sits right in front of his face; the object is modelled for that pose and converted back
    to the arm's rest so the bone carries it there. Returns the object (bone-parented to hand.<side>)."""
    from pdoom.chars import props
    from pdoom.chars.clawd import BONES, FACE_Y, EYE_Z, arm_clear
    from pdoom.chars.rig import bone_parent
    r, sw, tw, dx = arm_clear(side, *pose)          # the bake slides the arm out by dx so it clears the body
    eul = c._arm_euler(side, r, sw, tw)
    R = Euler(eul, 'XYZ').to_matrix().to_4x4()
    A = Vector(BONES[f'arm.{side}'])
    Ad = A + Vector((math.copysign(dx, A.x), 0.0, 0.0))
    to_rest = Matrix.Translation(A) @ R.inverted() @ Matrix.Translation(-Ad)
    # posed character space: mask 0.55 in front of the face, a touch low so the tops of his eyes peek over
    mc = Vector((0.0, FACE_Y - 0.75, EYE_Z - 0.15))
    posed_hand = Matrix.Translation(Ad) @ R @ Matrix.Translation(Vector(BONES[f'hand.{side}']) - A)
    hand = posed_hand.translation
    mo = props.make('mask', coll, name, to_rest @ Matrix.Translation(mc) @ Matrix.Rotation(math.radians(-6), 4, 'X'))
    # stick: the hand is beside the body, behind the face, so the stick runs forward from the mitten past the body's
    # front corner, bends (a rounded elbow) and goes in behind the mask to its lower edge on the hand's side. A straight
    # stick from the hand to the mask cut through the body's corner.
    rim = mc + Vector((math.copysign(0.9, hand.x), 0.25, -1.45))
    bend = Vector((hand.x, FACE_Y - 0.5, hand.z))
    a_ = bend + (hand - bend).normalized() * 0.4
    b_ = bend + (rim - bend).normalized() * 0.4
    elbow = [a_ * (1 - u) ** 2 + bend * (2 * u * (1 - u)) + b_ * u * u for u in (0.0, 0.25, 0.5, 0.75, 1.0)]
    stick_m = looks.wood('room.stickwood', '#E3C79A', '#C9A574')
    bm = bmesh.new()
    cg.tube(bm, [hand + (hand - bend).normalized() * 0.35, hand] + elbow + [rim], 0.11, segs=10)
    st = cg.to_object(bm, name + '.wood', coll, [stick_m], sharp=None)
    for v in st.data.vertices:
        v.co = to_rest @ v.co
    ob = geo.join([mo, st], name)
    ob.matrix_world = c.rig.matrix_world.copy()
    bone_parent(ob, c.rig, f'hand.{side}')
    return ob


def stamp_in_hand(coll, c, *, side='R', off=(0.5, -0.1, -2.2), name='stamp.held'):
    """The rubber stamp held in hand.<side>: its knob in the mitten, the stamp hanging upright (rubber face down) in
    every arm pose. A Child Of constraint on the hand bone with rotation and scale off carries it, so it follows the
    hand without tilting with the arm. `off`: the rubber face's centre relative to the hand (x is mirrored outboard for
    either side). The mesh origin is the hand; returns (object, the face offset as a Vector)."""
    from pdoom.chars.clawd import BONES
    sx = math.copysign(1.0, BONES[f'hand.{side}'][0])
    off = Vector((sx * off[0], off[1], off[2]))
    st = build_stamp(coll, name)
    for v in st.data.vertices:
        v.co = v.co + off
    st.matrix_world = Matrix.Identity(4)
    con = st.constraints.new('CHILD_OF')
    con.target = c.rig
    con.subtarget = f'hand.{side}'
    for ax in 'xyz':
        setattr(con, f'use_rotation_{ax}', False)
        setattr(con, f'use_scale_{ax}', False)
    if hasattr(con, 'set_inverse_pending'):
        con.set_inverse_pending = False
    con.inverse_matrix = Matrix.Identity(4)
    return st, off


def clawd_hand(c, t, pose, side='R'):
    """World position of Clawd's hand.<side> at song time t if his arm were at `pose` (raise, swing, twist), with
    the rest of his body as keyed (squash, hop, tilt). The puppet's own FK (chars/clawd.py _fk) with the arm swapped."""
    from pdoom.chars.clawd import BONES, arm_clear
    M = c._fk(t)
    r, sw, tw, dx = arm_clear(side, *pose)
    A, Bd, Hd = Vector(BONES[f'arm.{side}']), Vector(BONES['body']), Vector(BONES[f'hand.{side}'])
    Ma = M['body'] @ Matrix.Translation(A - Bd) @ Matrix.Translation((math.copysign(dx, A.x), 0, 0)) @         c._arm_R(side, r, sw, tw)
    return c.rig.matrix_world @ (Ma @ Matrix.Translation(Hd - A)).translation
