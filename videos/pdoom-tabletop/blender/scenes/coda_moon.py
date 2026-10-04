"""The paper moon: a crescent cut from layered card (corrugated cardboard edges showing), faced with pale yellow
watercolour paper with painted craters, hung on a cotton string like a stage prop. Also the paperclip Earth in
space (the clip ball over the painted globe) and the gauge on its own thread, for coda.py and finale K8.

    moon = build_moon(coll, loc=(0, 0, 0), yaw=0, scale=1)
    moon.seat(u)              # a world point on the lower inner edge (u 0..1 along the seat) and the seat's frame

Crescent geometry (in the moon's local XZ plane, card thickness along Y, the painted face toward -Y):
outer circle r 40 at (0, 0), inner circle r 34 at (13, 9); the horns are at (37.1, -15.0) and (-1.0, 40.0). The
inner edge's lowest stretch (x 4..24, z -24..-25) is nearly level: that's where Clawd and the researcher sit, legs
dangling over the face.
"""
from __future__ import annotations

import math

import bmesh
import bpy
from mathutils import Matrix, Vector

from pdoom import kit
from pdoom.fx import clips as C
from pdoom.sets import geo
from pdoom.sets import materials as M

V = Vector
RO, RI = 40.0, 34.0
CI = V((13.0, 9.0))
DEPTH = 6.0                   # card thickness (y)


class Moon:
    pass


def _crescent_outline(n_out=120, n_in=110):
    """Outline points (x, z) of the crescent, counter-clockwise: the outer arc from the lower horn round the
    left to the upper horn, then the inner arc back."""
    # intersections
    a_lo = math.atan2(-15.0, 37.08)          # lower horn on the outer circle
    a_hi = math.atan2(40.0, -0.99)
    pts = []
    # outer arc from the lower horn clockwise? go from a_lo down/around through the bottom and left to a_hi
    # (angles decreasing from a_lo through -pi/2, -pi ... to a_hi - 2 pi)
    a0, a1 = a_lo, a_hi - 2 * math.pi
    for i in range(n_out + 1):
        a = a0 + (a1 - a0) * i / n_out
        pts.append((RO * math.cos(a), RO * math.sin(a)))
    # inner arc from the upper horn back to the lower horn (the concave side)
    b_hi = math.atan2(40.0 - CI.y, -0.99 - CI.x)
    b_lo = math.atan2(-15.0 - CI.y, 37.08 - CI.x)
    if b_lo > b_hi:
        b_lo -= 2 * math.pi
    # the inner arc goes from the upper horn round the left and bottom to the lower horn: angles increasing
    b0, b1 = b_hi, b_lo + 2 * math.pi if b_lo < b_hi else b_lo
    for i in range(1, n_in):
        a = b0 + (b1 - b0) * i / n_in
        pts.append((CI.x + RI * math.cos(a), CI.y + RI * math.sin(a)))
    return pts


def moon_face_mat(name='moon.face'):
    """Pale yellow watercolour paper, painted craters (darker rings), soft pencil-grey shading."""
    m = bpy.data.materials.get(name)
    if m:
        return m
    m = M.tex_mat(name, 'paper', 24, tint='#F3E3A8', sat=0.25, rough=(0.72, 0.92), normal=0.9, fallback='#F3E3A8',
                  sheen=0.15, sss=0.04)
    nt = m.node_tree
    b = M.principled(m)
    # craters: voronoi cells, a darker ring at their rims
    base_link = b.inputs['Base Color'].links[0].from_socket if b.inputs['Base Color'].links else None
    tc = M.node(nt, 'ShaderNodeTexCoord', (-1400, -900))
    vo = M.node(nt, 'ShaderNodeTexVoronoi', (-1200, -900))
    M.setin(vo, 'Scale', 0.11)
    M.setin(vo, 'Randomness', 0.9)
    M.link(nt, M.sout(tc, 'Object'), M.sin(vo, 'Vector'))
    ring = M.node(nt, 'ShaderNodeMapRange', (-1000, -900))
    M.setin(ring, 'From Min', 0.25, 'VALUE')
    M.setin(ring, 'From Max', 0.55, 'VALUE')
    M.setin(ring, 'To Min', 0.0, 'VALUE')
    M.setin(ring, 'To Max', 1.0, 'VALUE')
    M.link(nt, M.sout(vo, 'Distance'), M.sin(ring, 'Value', 'VALUE'))
    nz = M.node(nt, 'ShaderNodeTexNoise', (-1200, -1150))
    M.setin(nz, 'Scale', 0.06)
    M.setin(nz, 'Detail', 4.0)
    M.link(nt, M.sout(tc, 'Object'), M.sin(nz, 'Vector'))
    blot = M.node(nt, 'ShaderNodeMapRange', (-1000, -1150))
    M.setin(blot, 'From Min', 0.45, 'VALUE')
    M.setin(blot, 'From Max', 0.7, 'VALUE')
    M.setin(blot, 'To Min', 0.0, 'VALUE')
    M.setin(blot, 'To Max', 0.35, 'VALUE')
    M.link(nt, M.sout(nz, 'Factor'), M.sin(blot, 'Value', 'VALUE'))
    crat = M.node(nt, 'ShaderNodeMath', (-800, -900), operation='SUBTRACT')
    crat.inputs[0].default_value = 1.0
    M.link(nt, M.sout(ring, 'Result', 'VALUE'), crat.inputs[1])
    cm = M.node(nt, 'ShaderNodeMath', (-650, -900), operation='MULTIPLY')
    M.link(nt, crat.outputs[0], cm.inputs[0])
    cm.inputs[1].default_value = 0.35
    tot = M.node(nt, 'ShaderNodeMath', (-500, -900), operation='ADD')
    M.link(nt, cm.outputs[0], tot.inputs[0])
    M.link(nt, M.sout(blot, 'Result', 'VALUE'), tot.inputs[1])
    tot.use_clamp = True
    mix = M.node(nt, 'ShaderNodeMix', (200, 300), data_type='RGBA', blend_type='MULTIPLY')
    M.link(nt, tot.outputs[0], M.sin(mix, 'Factor', 'VALUE'))
    if base_link is not None:
        M.link(nt, base_link, M.sin(mix, 'A', 'RGBA'))
    else:
        M.setin(mix, 'A', kit.srgb('#F3E3A8'), 'RGBA')
    M.setin(mix, 'B', kit.srgb('#B89A5C'), 'RGBA')
    M.link(nt, M.sout(mix, 'Result', 'RGBA'), M.sin(b, 'Base Color'))
    return m


def card_edge_mat(name='moon.edge'):
    """The cut edge: layers of corrugated card (the flutes show as fine stripes along the edge)."""
    m = bpy.data.materials.get(name)
    if m:
        return m
    m, _ = M.new_mat(name)
    nt = m.node_tree
    b = M.principled(m)
    M.setin(b, 'Roughness', 0.9)
    tc = M.node(nt, 'ShaderNodeTexCoord', (-900, 0))
    sep = M.node(nt, 'ShaderNodeSeparateXYZ', (-700, 0))
    M.link(nt, M.sout(tc, 'Object'), M.sin(sep, 'Vector'))
    wave = M.node(nt, 'ShaderNodeTexWave', (-500, 0))
    wave.wave_type = 'BANDS'
    wave.bands_direction = 'Y'
    M.setin(wave, 'Scale', 0.9)
    M.setin(wave, 'Distortion', 0.5)
    M.link(nt, M.sout(tc, 'Object'), M.sin(wave, 'Vector'))
    ramp = M.node(nt, 'ShaderNodeValToRGB', (-300, 0))
    ramp.color_ramp.elements[0].color = kit.srgb('#8C6A3E')
    ramp.color_ramp.elements[1].color = kit.srgb('#C9A36A')
    M.link(nt, M.sout(wave, 'Factor'), M.sin(ramp, 'Factor'))
    M.link(nt, M.sout(ramp, 'Color'), M.sin(b, 'Base Color'))
    bp = M.node(nt, 'ShaderNodeBump', (-100, -300))
    M.setin(bp, 'Strength', 0.6)
    M.setin(bp, 'Distance', 0.08)
    M.link(nt, M.sout(wave, 'Factor'), M.sin(bp, 'Height'))
    M.link(nt, M.sout(bp, 'Normal'), M.sin(b, 'Normal'))
    m.diffuse_color = kit.srgb('#B08A55')
    return m


def build_moon(coll, loc=(0, 0, 0), yaw=0.0, roll=0.0, scale=1.0, *, string_top=900.0, name='moon') -> Moon:
    """The crescent prop. Returns a Moon with .root (Empty: move / key it), .objects, .seat(u) (a world point on the
    sitting edge at song-independent rest), .local(p) (local -> world)."""
    mn = Moon()
    root = kit.empty(f'{name}.root', tuple(loc), coll)
    root.rotation_euler = (0.0, math.radians(roll), math.radians(yaw))
    root.scale = (scale, scale, scale)
    bm = bmesh.new()
    uvl = bm.loops.layers.uv.new('UVMap')
    Nn = 96
    a_lo, a_hi = math.atan2(-15.0, 37.08), math.atan2(40.0, -0.99) - 2 * math.pi
    b_lo = math.atan2(-15.0 - CI.y, 37.08 - CI.x) + 2 * math.pi
    b_hi = math.atan2(40.0 - CI.y, -0.99 - CI.x)
    outer = [(RO * math.cos(a_lo + (a_hi - a_lo) * i / Nn), RO * math.sin(a_lo + (a_hi - a_lo) * i / Nn))
             for i in range(Nn + 1)]
    inner = [(CI.x + RI * math.cos(b_lo + (b_hi - b_lo) * i / Nn), CI.y + RI * math.sin(b_lo + (b_hi - b_lo) * i / Nn))
             for i in range(Nn + 1)]
    inner[0], inner[-1] = outer[0], outer[-1]
    rows = {}
    for side, y in (('f', -DEPTH / 2), ('b', DEPTH / 2)):
        o = [bm.verts.new((x, y, z)) for x, z in outer]
        n = [o[0]] + [bm.verts.new((x, y, z)) for x, z in inner[1:-1]] + [o[-1]]
        rows[side] = (o, n)

    def face(vs, uvs, mat):
        vs2, uv2 = [], []
        for v, u in zip(vs, uvs):
            if not vs2 or v is not vs2[-1]:
                vs2.append(v)
                uv2.append(u)
        if vs2[0] is vs2[-1]:
            vs2.pop()
            uv2.pop()
        if len(vs2) < 3:
            return
        f = bm.faces.new(vs2)
        f.material_index = mat
        for lp, u in zip(f.loops, uv2):
            lp[uvl].uv = u

    def cuv(v):
        return (v.co.x / 90.0 + 0.5, v.co.z / 90.0 + 0.5)
    for side in ('f', 'b'):
        o, n = rows[side]
        for i in range(Nn):
            q = [o[i], o[i + 1], n[i + 1], n[i]]
            if side == 'b':
                q = q[::-1]
            face(q, [cuv(v) for v in q], 0)
    for (o_f, o_b) in ((rows['f'][0], rows['b'][0]), (rows['f'][1], rows['b'][1])):
        for i in range(Nn):
            q = [o_f[i], o_b[i], o_b[i + 1], o_f[i + 1]]
            face(q, [(i / Nn, 0.0), (i / Nn, 1.0), ((i + 1) / Nn, 1.0), ((i + 1) / Nn, 0.0)], 1)
    bmesh.ops.remove_doubles(bm, verts=bm.verts[:], dist=1e-4)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    me = bpy.data.meshes.new(f'{name}.card')
    bm.to_mesh(me)
    bm.free()
    me.materials.append(moon_face_mat())
    me.materials.append(card_edge_mat())
    card = bpy.data.objects.new(f'{name}.card', me)
    coll.objects.link(card)
    card.parent = root
    bv = card.modifiers.new('bevel', 'BEVEL')
    bv.width, bv.segments, bv.limit_method = 0.35, 2, 'ANGLE'
    # the string: from a little brass eyelet at the upper horn up out of every frame
    eye = V((-1.5, 0.0, 38.2))
    bm = bmesh.new()
    from pdoom.chars import geo as cgeo
    cgeo.tube(bm, [eye, eye + V((0.0, 0.0, string_top))], [0.06, 0.06], segs=6)
    st = cgeo.to_object(bm, f'{name}.string', coll, [M.solid('moon.cotton', '#E8E2D2', rough=0.8)], sharp=None)
    st.parent = root
    bm = bmesh.new()
    cgeo.lathe(bm, [(0.35, -0.12), (0.35, 0.12), (0.2, 0.12), (0.2, -0.12)], segs=16,
               M=Matrix.Translation(eye) @ Matrix.Rotation(math.radians(90), 4, 'X'))
    ey = cgeo.to_object(bm, f'{name}.eyelet', coll, [M.brass('moon.brass', '#C8A15A', 0.3)], sharp=None)
    ey.parent = root
    mn.root, mn.card, mn.objects = root, card, [root, card, st, ey]

    def local(p):
        return root.matrix_basis @ V(p)
    mn.local = local

    def seat(u, front=-DEPTH / 2):
        """(world point on the sitting edge, local x) for u in 0..1 along x 4..24 (the level stretch)."""
        x = 4.0 + 20.0 * u
        z = CI.y - math.sqrt(max(0.0, RI * RI - (x - CI.x) ** 2))
        return local((x, 0.0, z)), z
    mn.seat = seat
    return mn


def build_gauge_hung(coll, loc, yaw=0.0, *, name='gauge.hung', string_top=900.0):
    """The P(doom) gauge (sets.gauge, its whole history keyed: 100 and the cracked glass) hanging on a thread."""
    from pdoom.sets.gauge import build_gauge
    g = build_gauge(coll, loc=tuple(loc), yaw_deg=yaw)
    g.history()
    # a thread tied round the case top
    top = g.dial.matrix_basis
    bm = bmesh.new()
    from pdoom.chars import geo as cgeo
    p = V(loc) + V((0.0, 0.6, 15.0))
    cgeo.tube(bm, [p, p + V((0.0, 0.0, string_top))], [0.05, 0.05], segs=6)
    th = cgeo.to_object(bm, f'{name}.thread', coll, [M.solid('moon.cotton', '#E8E2D2', rough=0.8)], sharp=None)
    th.parent = g.root
    th.matrix_parent_inverse = g.root.matrix_basis.inverted()
    return g, th


def clip_earth(coll, center, radius=30.0, *, progress=None, scale=0.3, layers=2, density=0.8, name='earth',
               clouds=True):
    """The globe that becomes a ball of paperclips (fx.clips.ball over the hand-painted Earth), parented to a spin
    Empty (key its rotation). progress: [(t, 0..1)] or None (all clips)."""
    from scenes import finale_common as F
    spin = kit.empty(f'{name}.spin', tuple(center), coll)
    em = F.earth_material()
    b = C.ball(f'{name}.clips', center=tuple(center), radius=radius, scale=scale, layers=layers, density=density,
               lod=2, progress=progress, grain=0.12, coll=coll, core_mat=em)
    objs = [b['object'], b['core']]
    shell = bpy.data.objects.get(f'{name}.clips.surface')
    if shell is not None:
        shell['never_render'] = True
        objs.append(shell)
    cl = None
    if clouds:
        cl = F.clouds(f'{name}.clouds', center, radius, coll)
        objs.append(cl)
    for ob in objs:
        mw = ob.matrix_basis.copy()
        ob.parent = spin
        ob.matrix_parent_inverse = spin.matrix_basis.inverted()
    return {'spin': spin, 'ball': b, 'clouds': cl, 'material': em, 'objects': objs + [spin]}
