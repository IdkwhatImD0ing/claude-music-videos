"""Model-maker's pieces for the finale's miniature sets (scene-local): walls with window holes, gable roofs, model
houses, foam trees, picket fences, street lamps, a toy car, and the materials of a model shop (clapboard, roof
tiles, brick, flock, asphalt, wallpaper, a cutting mat, facades with lit window grids). Everything in cm.
"""
from __future__ import annotations

import math
import random

import bmesh
import bpy
from mathutils import Matrix, Vector

from pdoom import kit
from pdoom.chars import geo as cgeo
from pdoom.sets import geo
from pdoom.sets import materials as M

V = Vector


def _T(p):
    return Matrix.Translation(V(p))


def _Rz(deg):
    return Matrix.Rotation(math.radians(deg), 4, 'Z')


# ------------------------------------------------------------------------------------------------ materials


def _get(name):
    return bpy.data.materials.get(name)


def _bump(nt, b, height_socket, strength=0.4, distance=0.05):
    bp = M.node(nt, 'ShaderNodeBump', (-150, -500))
    M.setin(bp, 'Strength', strength)
    M.setin(bp, 'Distance', distance)
    M.link(nt, height_socket, M.sin(bp, 'Height'))
    M.link(nt, M.sout(bp, 'Normal'), M.sin(b, 'Normal'))


def clapboard(name, color, board=1.2, rough=0.62):
    """Painted clapboard siding: horizontal boards (object Z) with a shadow line under each."""
    m = _get(name)
    if m:
        return m
    m, _ = M.new_mat(name)
    nt = m.node_tree
    b = M.principled(m)
    M.setin(b, 'Base Color', kit.srgb(color))
    M.setin(b, 'Roughness', rough)
    tc = M.node(nt, 'ShaderNodeTexCoord', (-900, 0))
    sep = M.node(nt, 'ShaderNodeSeparateXYZ', (-700, 0))
    M.link(nt, M.sout(tc, 'Object'), M.sin(sep, 'Vector'))
    dv = M.node(nt, 'ShaderNodeMath', (-500, 0), operation='DIVIDE')
    M.link(nt, M.sout(sep, 'Z'), dv.inputs[0])
    dv.inputs[1].default_value = board
    fr = M.node(nt, 'ShaderNodeMath', (-350, 0), operation='FRACT')
    M.link(nt, dv.outputs[0], fr.inputs[0])
    _bump(nt, b, fr.outputs[0], 0.5, 0.06)
    m.diffuse_color = kit.srgb(color)
    return m


def brickish(name, c1, c2, mortar='#2A2624', size=(0.9, 0.35), msize=0.06, rough=0.8, scale=1.0, offset=0.5,
             bump=0.3):
    """Brick / roof-tile pattern (Brick Texture in object space). size = (brick width, row height) in cm."""
    m = _get(name)
    if m:
        return m
    m, _ = M.new_mat(name)
    nt = m.node_tree
    b = M.principled(m)
    M.setin(b, 'Roughness', rough)
    tc = M.node(nt, 'ShaderNodeTexCoord', (-900, 0))
    br = M.node(nt, 'ShaderNodeTexBrick', (-600, 0))
    br.offset = offset
    M.setin(br, 'Color1', kit.srgb(c1))
    M.setin(br, 'Color2', kit.srgb(c2))
    M.setin(br, 'Mortar', kit.srgb(mortar))
    M.setin(br, 'Scale', scale)
    M.setin(br, 'Mortar Size', msize)
    M.setin(br, 'Brick Width', size[0])
    M.setin(br, 'Row Height', size[1])
    M.link(nt, M.sout(tc, 'Object'), M.sin(br, 'Vector'))
    M.link(nt, M.sout(br, 'Color'), M.sin(b, 'Base Color'))
    inv = M.node(nt, 'ShaderNodeMath', (-350, -300), operation='SUBTRACT')
    inv.inputs[0].default_value = 1.0
    M.link(nt, M.sout(br, 'Factor'), inv.inputs[1])
    _bump(nt, b, inv.outputs[0], bump, 0.04)
    m.diffuse_color = kit.srgb(c1)
    return m


def facade(name, wall, *, cell=(1.6, 2.2), win=(0.55, 0.5), lit=0.45, strength=5.0, warm='#FFC27A',
           cool='#CFE3FF', dark='#16181C', seed=0.0, rough=0.7):
    """A painted wall with a grid of windows, a fraction `lit` of them lit (warm, a few cool), the rest dark glass.
    Brick Texture in object space: its 'bricks' are the windows, its mortar the wall; each brick's random grey
    decides lit or not. cell: window pitch (along the wall, up); win: window size as a fraction of the cell."""
    m = _get(name)
    if m:
        return m
    m, _ = M.new_mat(name)
    nt = m.node_tree
    b = M.principled(m)
    M.setin(b, 'Roughness', rough)
    tc = M.node(nt, 'ShaderNodeTexCoord', (-1300, 0))
    sep = M.node(nt, 'ShaderNodeSeparateXYZ', (-1100, 0))
    M.link(nt, M.sout(tc, 'Object'), M.sin(sep, 'Vector'))
    along = M.node(nt, 'ShaderNodeMath', (-900, 100), operation='ADD')
    M.link(nt, M.sout(sep, 'X'), along.inputs[0])
    M.link(nt, M.sout(sep, 'Y'), along.inputs[1])
    cmb = M.node(nt, 'ShaderNodeCombineXYZ', (-700, 0))
    M.link(nt, along.outputs[0], M.sin(cmb, 'X'))
    M.link(nt, M.sout(sep, 'Z'), M.sin(cmb, 'Y'))
    cmb.inputs['Z'].default_value = seed
    br = M.node(nt, 'ShaderNodeTexBrick', (-450, 0))
    br.offset = 0.0
    M.setin(br, 'Color1', (1.0, 1.0, 1.0, 1.0))
    M.setin(br, 'Color2', (0.0, 0.0, 0.0, 1.0))
    M.setin(br, 'Mortar', (0.0, 0.0, 0.0, 1.0))
    M.setin(br, 'Scale', 1.0)
    M.setin(br, 'Mortar Size', min(cell[0] * (1 - win[0]), cell[1] * (1 - win[1])) / 2)
    M.setin(br, 'Brick Width', cell[0])
    M.setin(br, 'Row Height', cell[1])
    M.setin(br, 'Bias', 0.0)
    M.link(nt, M.sout(cmb, 'Vector'), M.sin(br, 'Vector'))
    wallmask = M.sout(br, 'Factor')                                   # 1 on the wall, 0 in a window
    sepc = M.node(nt, 'ShaderNodeSeparateColor', (-250, 250))
    M.link(nt, M.sout(br, 'Color'), sepc.inputs[0])
    on = M.node(nt, 'ShaderNodeMath', (-100, 250), operation='GREATER_THAN')
    M.link(nt, sepc.outputs[0], on.inputs[0])
    on.inputs[1].default_value = 1.0 - lit
    cold = M.node(nt, 'ShaderNodeMath', (-100, 400), operation='GREATER_THAN')
    M.link(nt, sepc.outputs[0], cold.inputs[0])
    cold.inputs[1].default_value = 1.0 - lit * 0.2
    glassm = M.node(nt, 'ShaderNodeMath', (-200, -200), operation='SUBTRACT')
    glassm.inputs[0].default_value = 1.0
    M.link(nt, wallmask, glassm.inputs[1])
    mix = M.node(nt, 'ShaderNodeMix', (-200, 100), data_type='RGBA', blend_type='MIX')
    M.link(nt, wallmask, M.sin(mix, 'Factor', 'VALUE'))
    M.setin(mix, 'A', kit.srgb(dark), 'RGBA')
    M.setin(mix, 'B', kit.srgb(wall), 'RGBA')
    M.link(nt, M.sout(mix, 'Result', 'RGBA'), M.sin(b, 'Base Color'))
    wc = M.node(nt, 'ShaderNodeMix', (100, 400), data_type='RGBA', blend_type='MIX')
    M.link(nt, cold.outputs[0], M.sin(wc, 'Factor', 'VALUE'))
    M.setin(wc, 'A', kit.srgb(warm), 'RGBA')
    M.setin(wc, 'B', kit.srgb(cool), 'RGBA')
    M.link(nt, M.sout(wc, 'Result', 'RGBA'), M.sin(b, 'Emission Color'))
    st = M.node(nt, 'ShaderNodeMath', (100, -200), operation='MULTIPLY')
    M.link(nt, glassm.outputs[0], st.inputs[0])
    M.link(nt, on.outputs[0], st.inputs[1])
    st2 = M.node(nt, 'ShaderNodeMath', (250, -200), operation='MULTIPLY')
    M.link(nt, st.outputs[0], st2.inputs[0])
    st2.inputs[1].default_value = strength
    M.link(nt, st2.outputs[0], M.sin(b, 'Emission Strength'))
    # dark glass is glossy
    rg = M.node(nt, 'ShaderNodeMapRange', (100, -400))
    M.setin(rg, 'To Min', 0.12, 'VALUE')
    M.setin(rg, 'To Max', rough, 'VALUE')
    M.link(nt, wallmask, M.sin(rg, 'Value', 'VALUE'))
    M.link(nt, M.sout(rg, 'Result', 'VALUE'), M.sin(b, 'Roughness'))
    m.diffuse_color = kit.srgb(wall)
    return m


def asphalt(name='model.asphalt', color='#2B2C2E'):
    m = _get(name)
    if m:
        return m
    return M.solid(name, color, rough=0.85, micro=(4.0, 0.15), spec=0.3)


def gravel(name='model.gravel', color='#9A958C'):
    m = _get(name)
    if m:
        return m
    return M.solid(name, color, rough=0.9, micro=(9.0, 0.5), spec=0.3)


def wallpaper(name='model.wallpaper', a='#A9B79A', b_='#C8CFB5', stripe=1.4):
    m = _get(name)
    if m:
        return m
    m, _ = M.new_mat(name)
    nt = m.node_tree
    b = M.principled(m)
    M.setin(b, 'Roughness', 0.8)
    tc = M.node(nt, 'ShaderNodeTexCoord', (-900, 0))
    sep = M.node(nt, 'ShaderNodeSeparateXYZ', (-700, 0))
    M.link(nt, M.sout(tc, 'Object'), M.sin(sep, 'Vector'))
    add = M.node(nt, 'ShaderNodeMath', (-550, 0), operation='ADD')
    M.link(nt, M.sout(sep, 'X'), add.inputs[0])
    M.link(nt, M.sout(sep, 'Y'), add.inputs[1])
    dv = M.node(nt, 'ShaderNodeMath', (-400, 0), operation='DIVIDE')
    M.link(nt, add.outputs[0], dv.inputs[0])
    dv.inputs[1].default_value = stripe
    fr = M.node(nt, 'ShaderNodeMath', (-250, 0), operation='FRACT')
    M.link(nt, dv.outputs[0], fr.inputs[0])
    st = M.node(nt, 'ShaderNodeMath', (-100, 0), operation='GREATER_THAN')
    M.link(nt, fr.outputs[0], st.inputs[0])
    st.inputs[1].default_value = 0.55
    mix = M.node(nt, 'ShaderNodeMix', (100, 0), data_type='RGBA', blend_type='MIX')
    M.link(nt, st.outputs[0], M.sin(mix, 'Factor', 'VALUE'))
    M.setin(mix, 'A', kit.srgb(a), 'RGBA')
    M.setin(mix, 'B', kit.srgb(b_), 'RGBA')
    M.link(nt, M.sout(mix, 'Result', 'RGBA'), M.sin(b, 'Base Color'))
    m.diffuse_color = kit.srgb(a)
    return m


def cutting_mat(name='model.mat', color='#1F4A3C', line='#CFE3D6', grid=1.0):
    """A modeller's self-healing cutting mat: dark green with a fine white grid (every `grid` cm)."""
    m = _get(name)
    if m:
        return m
    m, _ = M.new_mat(name)
    nt = m.node_tree
    b = M.principled(m)
    M.setin(b, 'Roughness', 0.7)
    tc = M.node(nt, 'ShaderNodeTexCoord', (-900, 0))
    br = M.node(nt, 'ShaderNodeTexBrick', (-500, 0))
    br.offset = 0.0
    M.setin(br, 'Color1', kit.srgb(color))
    M.setin(br, 'Color2', kit.srgb(color))
    M.setin(br, 'Mortar', kit.srgb(line))
    M.setin(br, 'Scale', 1.0)
    M.setin(br, 'Mortar Size', 0.02 * grid)
    M.setin(br, 'Brick Width', grid)
    M.setin(br, 'Row Height', grid)
    M.link(nt, M.sout(tc, 'Object'), M.sin(br, 'Vector'))
    M.link(nt, M.sout(br, 'Color'), M.sin(b, 'Base Color'))
    m.diffuse_color = kit.srgb(color)
    return m


def paint(name, color, rough=0.55):
    m = _get(name)
    if m:
        return m
    return M.solid(name, color, rough=rough, micro=(6.0, 0.03), spec=0.4)


def foam(name='model.foam', color='#355A2C'):
    """Model-railway foam foliage: rough, speckled green."""
    m = _get(name)
    if m:
        return m
    m, _ = M.new_mat(name)
    nt = m.node_tree
    b = M.principled(m)
    M.setin(b, 'Roughness', 0.95)
    M.setin(b, 'Sheen Weight', 0.4)
    tc = M.node(nt, 'ShaderNodeTexCoord', (-800, 0))
    vo = M.node(nt, 'ShaderNodeTexVoronoi', (-600, 0))
    M.setin(vo, 'Scale', 3.0)
    M.link(nt, M.sout(tc, 'Object'), M.sin(vo, 'Vector'))
    ramp = M.node(nt, 'ShaderNodeValToRGB', (-400, 0))
    ramp.color_ramp.elements[0].color = kit.srgb('#1E3A1C')
    ramp.color_ramp.elements[1].color = kit.srgb(color)
    M.link(nt, M.sout(vo, 'Distance'), M.sin(ramp, 'Factor'))
    M.link(nt, M.sout(ramp, 'Color'), M.sin(b, 'Base Color'))
    _bump(nt, b, M.sout(vo, 'Distance'), 0.8, 0.1)
    m.diffuse_color = kit.srgb(color)
    return m


# ------------------------------------------------------------------------------------------------ meshes


def _box_bm(bm, x0, x1, y0, y1, z0, z1, mat=0):
    vs = [bm.verts.new(c) for c in ((x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0),
                                    (x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1))]
    for f in ((0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)):
        face = bm.faces.new([vs[i] for i in f])
        face.material_index = mat
    return vs


def wall(bm, length, height, thick, holes=(), *, M=Matrix(), mat=0):
    """A wall slab in local coords: x along [0, length], y through [0, thick] (outer face y=0), z up, with
    rectangular holes (x0, x1, z0, z1). One watertight mesh on the rectilinear grid of the holes' edges (front,
    back, the openings' reveals and the slab's ends share vertices: no internal faces). M places it."""
    xs = sorted({0.0, length} | {h[0] for h in holes} | {h[1] for h in holes})
    zs = sorted({0.0, height} | {min(max(h[2], 0.0), height) for h in holes} |
                {min(max(h[3], 0.0), height) for h in holes})
    nx, nz = len(xs), len(zs)
    F_ = [[bm.verts.new(M @ V((x, 0.0, z))) for z in zs] for x in xs]
    B_ = [[bm.verts.new(M @ V((x, thick, z))) for z in zs] for x in xs]

    def solid(i, j):
        """cell (i, j) = [xs[i], xs[i+1]] x [zs[j], zs[j+1]] is wall (not in a hole, inside the slab)."""
        if i < 0 or j < 0 or i >= nx - 1 or j >= nz - 1:
            return False
        cx, cz = (xs[i] + xs[i + 1]) / 2, (zs[j] + zs[j + 1]) / 2
        return not any(h[0] < cx < h[1] and h[2] < cz < h[3] for h in holes)

    made = []

    def face(vs):
        f = bm.faces.new(vs)
        f.material_index = mat
        made.append(f)
    for i in range(nx - 1):
        for j in range(nz - 1):
            if not solid(i, j):
                continue
            face((F_[i][j], F_[i][j + 1], F_[i + 1][j + 1], F_[i + 1][j]))          # front
            face((B_[i][j], B_[i + 1][j], B_[i + 1][j + 1], B_[i][j + 1]))          # back
            # sides where the neighbouring cell is empty (a reveal or the slab's end)
            if not solid(i - 1, j):
                face((F_[i][j], B_[i][j], B_[i][j + 1], F_[i][j + 1]))
            if not solid(i + 1, j):
                face((F_[i + 1][j], F_[i + 1][j + 1], B_[i + 1][j + 1], B_[i + 1][j]))
            if not solid(i, j - 1):
                face((F_[i][j], F_[i + 1][j], B_[i + 1][j], B_[i][j]))
            if not solid(i, j + 1):
                face((F_[i][j + 1], B_[i][j + 1], B_[i + 1][j + 1], F_[i + 1][j + 1]))
    for col in F_ + B_:
        for v in col:
            if not v.link_faces:
                bm.verts.remove(v)
    bmesh.ops.recalc_face_normals(bm, faces=made)      # watertight slab: outward normals


def gable(bm, x0, x1, y0, y1, z_eave, z_ridge, over=1.0, thick=0.35, mat=0, gable_mat=1):
    """A gable roof along x (ridge at y centre) with overhangs, as two slabs; plus the two triangular gable ends."""
    yc = (y0 + y1) / 2
    for s in (-1, 1):
        ye = y0 - over if s < 0 else y1 + over
        k = (z_ridge - z_eave) / (yc - (y0 if s < 0 else y1))
        ze = z_eave - abs(ye - (y0 if s < 0 else y1)) * abs(k)
        a = [V((x0 - over, yc, z_ridge)), V((x1 + over, yc, z_ridge)), V((x1 + over, ye, ze)), V((x0 - over, ye, ze))]
        b = [p + V((0, 0, thick)) for p in a]
        va = [bm.verts.new(p) for p in a]
        vb = [bm.verts.new(p) for p in b]
        faces = [va[::-1], vb, (va[0], va[1], vb[1], vb[0]), (va[1], va[2], vb[2], vb[1]),
                 (va[2], va[3], vb[3], vb[2]), (va[3], va[0], vb[0], vb[3])]
        for f in faces:
            ff = bm.faces.new(f if s > 0 else list(reversed(f)))
            ff.material_index = mat
    for x in (x0, x1):
        vs = [bm.verts.new((x, y0, z_eave)), bm.verts.new((x, y1, z_eave)), bm.verts.new((x, yc, z_ridge))]
        f = bm.faces.new(vs if x == x1 else list(reversed(vs)))
        f.material_index = gable_mat


def obj(bm, name, coll, mats, sharp=30.0):
    return cgeo.to_object(bm, name, coll, mats, sharp=sharp)


class House:
    pass


def house(name, coll, *, loc=(0, 0, 0), yaw=0.0, size=(32.0, 20.0, 21.0), ridge=10.0, wall_mat=None, roof_mat=None,
          trim_mat=None, windows=None, door=None, glow=None, chimney=True, over=1.2, thick=0.8, recess=0.5,
          frames=True):
    """A two-storey model house. windows: list of (face, u, z0, w, h) with face in 'front' (y = -D/2), 'back',
    'left' (x = -W/2), 'right' and u the position along the face (from its centre). door: (u, w, h) on the front.
    Returns a House with .objects, .openings [(world centre, world outward normal, (w, h), kind)]."""
    W, D, H = size
    hs = House()
    hs.objects, hs.openings = [], []
    wall_mat = wall_mat or clapboard('model.clap.cream', '#E9DFC6')
    roof_mat = roof_mat or brickish('model.roof.slate', '#3B4048', '#2E3239', size=(0.9, 0.55), msize=0.05)
    trim_mat = trim_mat or paint('model.trim', '#F4F1EA', 0.45)
    glow = glow or kit.mat('model.glow.dummy', '#FFC27A')
    Mb = _T(loc) @ _Rz(yaw)
    faces = {
        'front': (_T((-W / 2, -D / 2, 0)), W, V((0, -1, 0))),
        'right': (_T((W / 2, -D / 2, 0)) @ _Rz(90), D, V((1, 0, 0))),
        'back': (_T((W / 2, D / 2, 0)) @ _Rz(180), W, V((0, 1, 0))),
        'left': (_T((-W / 2, D / 2, 0)) @ _Rz(270), D, V((-1, 0, 0))),
    }
    holes = {k: [] for k in faces}
    for (f, u, z0, w, h) in (windows or []):
        L = faces[f][1]
        holes[f].append((L / 2 + u - w / 2, L / 2 + u + w / 2, z0, z0 + h, 'win'))
    if door is not None:
        u, w, h = door
        holes['front'].append((W / 2 + u - w / 2, W / 2 + u + w / 2, 0.0, h, 'door'))
    bm = bmesh.new()
    bm_trim = bmesh.new()
    bm_glow = bmesh.new()
    for f, (Mf, L, nrm) in faces.items():
        hh = [(a, b, c, d) for a, b, c, d, _ in holes[f]]
        wall(bm, L, H, thick, hh, M=Mf)
        for a, b, c, d, kind in holes[f]:
            # the lit room behind the opening
            gv = [bm_glow.verts.new(Mf @ V(p)) for p in ((a, thick + recess, c), (b, thick + recess, c),
                                                        (b, thick + recess, d), (a, thick + recess, d))]
            bm_glow.faces.new(gv)
            if frames:
                t = min(0.22, (b - a) * 0.08)
                sl = min(0.3, (b - a) * 0.1)
                pr = min(0.25, t * 1.2)
                for (x0, x1, z0, z1) in ((a - t, a, c - t, d + t), (b, b + t, c - t, d + t), (a, b, d, d + t),
                                         (a - sl, b + sl, c - sl, c)):
                    if kind == 'door' and z0 < 0:
                        continue
                    vs = _box_bm(bm_trim, x0, x1, -pr, 0.15, max(0.0, z0), z1)
                    for v in vs:
                        v.co = Mf @ v.co
            cw = Mf @ V(((a + b) / 2, 0.0, (c + d) / 2))
            hs.openings.append((Mb @ cw, (Mb.to_3x3() @ nrm).normalized(), (b - a, d - c), kind))
    # a plinth
    pz = min(0.9, H * 0.045)
    po = min(0.3, W * 0.012)
    _box_bm(bm_trim, -W / 2 - po, W / 2 + po, -D / 2 - po, D / 2 + po, 0.0, pz)
    for v in bm.verts:
        v.co = Mb @ v.co
    for v in bm_trim.verts:
        v.co = Mb @ v.co
    for v in bm_glow.verts:
        v.co = Mb @ v.co
    hs.objects.append(obj(bm, f'{name}.walls', coll, [wall_mat]))
    hs.objects.append(obj(bm_trim, f'{name}.trim', coll, [trim_mat]))
    g = obj(bm_glow, f'{name}.glow', coll, [glow], sharp=None)
    g.visible_shadow = False
    hs.objects.append(g)
    bm = bmesh.new()
    gable(bm, -W / 2, W / 2, -D / 2, D / 2, H, H + ridge, over=over, mat=0, gable_mat=1)
    if chimney:
        cw = max(0.4, W * 0.094)
        cx1 = W / 2 - W * 0.094
        cy0 = D * 0.025
        ch = ridge * 0.35
        _box_bm(bm, cx1 - cw, cx1, cy0, cy0 + cw, H + ridge * 0.3, H + ridge + ch, mat=2)
        e = cw * 0.12
        _box_bm(bm, cx1 - cw - e, cx1 + e, cy0 - e, cy0 + cw + e, H + ridge + ch, H + ridge + ch + cw * 0.2, mat=2)
    for v in bm.verts:
        v.co = Mb @ v.co
    brick = brickish('model.brick', '#8C3B2A', '#A4533A', mortar='#6E625A', size=(0.8, 0.3), msize=0.05)
    hs.objects.append(obj(bm, f'{name}.roof', coll, [roof_mat, wall_mat, brick]))
    hs.M = Mb
    return hs


def tree(name, coll, loc, height=14.0, radius=5.0, seed=1, color='#3E6231'):
    """A model-railway tree: a twisted brown trunk and clumps of foam foliage."""
    rng = random.Random(seed)
    bm = bmesh.new()
    x, y, z = loc
    cgeo.tube(bm, [V((x, y, z)), V((x + 0.2, y - 0.1, z + height * 0.35)), V((x - 0.1, y + 0.2, z + height * 0.6))],
              [height * 0.045, height * 0.032, height * 0.02], segs=8)
    trunk = obj(bm, f'{name}.trunk', coll, [paint('model.bark', '#4A3526', 0.9)])
    bm = bmesh.new()
    for k in range(9):
        a = rng.uniform(0, 2 * math.pi)
        rr = radius * rng.uniform(0.0, 0.6)
        zz = z + height * rng.uniform(0.45, 0.9)
        s = radius * rng.uniform(0.45, 0.7) * (1.0 - 0.4 * (zz - z) / height)
        bmesh.ops.create_icosphere(bm, subdivisions=2, radius=s,
                                   matrix=_T((x + rr * math.cos(a), y + rr * math.sin(a), zz)))
    fol = obj(bm, f'{name}.foliage', coll, [foam(f'model.foam.{color}', color)], sharp=None)
    tex = bpy.data.textures.get('model.foamtex') or bpy.data.textures.new('model.foamtex', 'VORONOI')
    tex.noise_scale = radius * 0.18
    dm = fol.modifiers.new('lumps', 'DISPLACE')
    dm.texture = tex
    dm.strength = radius * 0.18
    dm.texture_coords = 'OBJECT'
    return [trunk, fol]


def fence(name, coll, a, b, *, height=2.2, pitch=0.9, picket=0.45):
    """A white picket fence from a to b (z = 0 plane of a)."""
    a, b = V(a), V(b)
    d = b - a
    L = d.length
    ang = math.degrees(math.atan2(d.y, d.x))
    M0 = _T(a) @ _Rz(ang)
    bm = bmesh.new()
    n = max(2, int(L / pitch))
    for i in range(n + 1):
        x = L * i / n
        _box_bm(bm, x - picket / 2, x + picket / 2, -0.08, 0.08, 0.0, height)
    for z in (height * 0.3, height * 0.72):
        _box_bm(bm, 0.0, L, 0.08, 0.28, z - 0.15, z + 0.15)
    for v in bm.verts:
        v.co = M0 @ v.co
    return obj(bm, name, coll, [paint('model.fence', '#F2EFE6', 0.5)])


def street_lamp(name, coll, loc, *, height=16.0, arm=3.0, yaw=0.0, color='#FFC77A', glow=12.0):
    """A cast-iron street lamp: pole, arm, a glowing lantern head. Returns (objects, head world position)."""
    x, y, z = loc
    Mz = _T(loc) @ _Rz(yaw)
    bm = bmesh.new()
    cgeo.tube(bm, [V((0, 0, 0)), V((0, 0, height)), V((0, -arm * 0.7, height + 0.6)), V((0, -arm, height))],
              [height * 0.018, height * 0.012, height * 0.01, height * 0.01], segs=8)
    _box_bm(bm, -height * 0.035, height * 0.035, -height * 0.035, height * 0.035, 0.0, height * 0.06)
    for v in bm.verts:
        v.co = Mz @ v.co
    pole = obj(bm, f'{name}.pole', coll, [paint('model.iron', '#1E2422', 0.45)])
    bm = bmesh.new()
    s = height * 0.06
    bmesh.ops.create_cone(bm, cap_ends=True, segments=10, radius1=s * 0.9, radius2=s * 0.35, depth=s * 1.3,
                          matrix=Mz @ _T((0, -arm, height - s * 0.8)))
    head = obj(bm, f'{name}.head', coll, [kit.emission_mat(f'model.lamp.{color}', color, glow)], sharp=None)
    head.visible_shadow = False
    return [pole, head], Mz @ V((0, -arm, height - s * 1.2))


def toy_car(name, coll, loc, yaw=0.0, color='#C8322A', size=1.0):
    """A little painted die-cast car: body, cabin, four black wheels."""
    s = size
    Mz = _T(loc) @ _Rz(yaw)
    bm = bmesh.new()
    cgeo.rounded_box(bm, (4.2 * s, 1.9 * s, 1.0 * s), 0.3 * s, (0, 0, 0.9 * s), seg=2, flat=(2, 1, 0))
    cgeo.rounded_box(bm, (2.3 * s, 1.7 * s, 0.9 * s), 0.35 * s, (-0.2 * s, 0, 1.75 * s), seg=2, flat=(1, 1, 0))
    for v in bm.verts:
        v.co = Mz @ v.co
    body = obj(bm, f'{name}.body', coll, [M.solid(f'model.car.{color}', color, rough=0.25, coat=0.9,
                                                  coat_rough=0.05)])
    bm = bmesh.new()
    for sx in (-1.3, 1.3):
        for sy in (-0.95, 0.95):
            cgeo.lathe(bm, [(0.0, -0.22 * s), (0.45 * s, -0.22 * s), (0.45 * s, 0.22 * s), (0.0, 0.22 * s)], segs=14,
                       M=Mz @ _T((sx * s, sy * s, 0.45 * s)) @ Matrix.Rotation(math.radians(90), 4, 'X'))
    wheels = obj(bm, f'{name}.wheels', coll, [M.solid('model.tyre', '#141414', rough=0.7)])
    return [body, wheels]
