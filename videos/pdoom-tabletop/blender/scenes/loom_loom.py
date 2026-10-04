"""The `loom` scene's tiny table loom: maple side frames with a castle, breast and back beams, a warp beam wound with
cream yarn, 56 warp threads through two heddle shafts that swap the shed each pick, a swinging beater with a steel
reed, a boat shuttle (orange weft on its bobbin) flying through the shed, and the woven tapestry that grows from the
front beam: a picture of the future, a giant Clawd towering over a tiny night city, whose eyes glow when it's done.

Loom-local frame: origin on the desk under the middle of the loom, the weaver's side (front) is -Y, X across.
The warp lies at z = WARP_Z; the cloth runs from the breast beam (y = Y_FRONT) back to the fell (y_fell).

    L = build_loom(coll, loc, yaw)
    L.weave(picks=[...], fell=[(t, v)...], glow_t=127.54)
"""
from __future__ import annotations

import math
import random

import bmesh
import bpy
from mathutils import Matrix, Vector

from pdoom import kit
from pdoom import timing as tm
from pdoom.sets import geo
from pdoom.sets import materials as M
from pdoom.timing import FPS

N_WARP = 56
HALF_W = 7.7                     # warp from -HALF_W to +HALF_W
WARP_Z = 8.35
Y_FRONT, Y_BACK = -10.5, 10.5    # breast beam, back beam
Y_HEDDLE = 4.0
FELL_MAX = 1.5                   # the fell when the picture is finished
SHED = 0.75                      # half the shed opening at the heddles (cm)
PIX_W, PIX_H = 96, 72            # the tapestry's weave cells
PIVOT = Vector((0.0, -3.0, 1.0))  # the beater's hinge (loom-local)
SIDE_IN, SIDE_TOP = 8.5, 8.9     # the side frames' inner face (|x|) and top (z) in front of the castle (y < 1.4)
SHUTTLE_HALF = (2.4, 0.52, 0.39)  # the boat shuttle's half length (x), half width (y), half height (z)


# ------------------------------------------------------------------------------------------------ the picture


def tapestry_pixels(seed: int = 7):
    """The woven picture (PIX_W x PIX_H cells, row 0 at the bottom = the front of the cloth): a night sky with
    stars and a moon, a giant Clawd standing behind a tiny city skyline, red eyes. Returns (rgb float array
    [H, W, 3] linear, glow mask [H, W])."""
    import numpy as np
    rnd = random.Random(seed)
    W, H = PIX_W, PIX_H

    def lin(h):
        return np.array(kit.srgb(h)[:3], dtype=np.float32)
    img = np.zeros((H, W, 3), np.float32)
    glow = np.zeros((H, W), np.float32)
    top, hor = lin('#121833'), lin('#3B2B4F')
    for y in range(H):
        k = min(1.0, max(0.0, (y - 18) / (H - 22)))
        img[y, :] = hor * (1 - k) + top * k
    for _ in range(34):
        x, y = rnd.randrange(3, W - 3), rnd.randrange(30, H - 4)
        img[y, x] = lin('#CFCFE6')
    # the moon
    mx, my = 82, 60
    for y in range(H):
        for x in range(W):
            d = math.hypot(x - mx, y - my)
            if d < 5.2:
                img[y, x] = lin('#F2E6C0') if d < 4.2 else lin('#B8AE92')
    # giant Clawd (drawn before the city, so the buildings stand in front of his legs)
    body, dark, ink = lin('#D97757'), lin('#A8533A'), lin('#0B0909')
    x0, x1, y0, y1 = 25, 71, 25, 54
    for y in range(y0, y1):
        for x in range(x0, x1):
            corner = (x in (x0, x1 - 1)) and (y in (y0, y1 - 1))
            if not corner:
                img[y, x] = body if y > y0 + 2 else dark
    for x in range(x0 + 1, x1 - 1):          # the lid seam
        img[39, x] = dark
    for sx in (-1, 1):                       # stub arms
        ax = x0 - 4 if sx < 0 else x1
        for y in range(34, 38):
            for x in range(ax, ax + 4):
                img[y, x] = body
    for lx in (29, 37, 57, 65):              # legs
        for y in range(14, y0):
            for x in range(lx, lx + 3):
                img[y, x] = dark
    for ex in (34, 57):                      # eyes: tall black pills with a glowing red core
        for y in range(42, 53):
            for x in range(ex, ex + 5):
                if (y in (42, 52)) and x in (ex, ex + 4):
                    continue
                img[y, x] = ink
                if 44 <= y <= 50 and ex + 1 <= x <= ex + 3:
                    img[y, x] = lin('#FF3A1E')
                    glow[y, x] = 1.0 if x == ex + 2 else 0.6
    # the city: a skyline of blocks with lit windows
    x = 0
    while x < W:
        w = rnd.randrange(4, 10)
        h = rnd.randrange(9, 25) if not (30 < x < 64) else rnd.randrange(9, 17)
        col = lin('#1C2130') if rnd.random() < 0.5 else lin('#262C3F')
        for yy in range(2, 2 + h):
            for xx in range(x, min(W, x + w)):
                img[yy, xx] = col
                if (xx - x) % 2 == 1 and (yy % 3 == 1) and yy < 2 + h - 1 and rnd.random() < 0.55:
                    img[yy, xx] = lin('#FFC96A')
        x += w + rnd.randrange(0, 2)
    # revision 2: the loom weaves its own name into the sky above his head (the last rows it weaves, as "Loom" is
    # sung); the letters glow with his eyes (the glow mask)
    gold = lin('#FFC96A')
    font5x7 = {
        'L': ['X....', 'X....', 'X....', 'X....', 'X....', 'X....', 'XXXXX'],
        'O': ['.XXX.', 'X...X', 'X...X', 'X...X', 'X...X', 'X...X', '.XXX.'],
        'M': ['X...X', 'XX.XX', 'X.X.X', 'X.X.X', 'X...X', 'X...X', 'X...X'],
    }
    from pdoom import lyrics as ly
    word, x_left, y_top = ('LOOM' if ly.ENABLED else ''), 36, 64          # revision 3: no lyrics in the picture
    for i, ch in enumerate(word):
        rows = font5x7[ch]
        for r, row in enumerate(rows):
            for c, px in enumerate(row):
                if px == 'X':
                    x, y = x_left + i * 6 + c, y_top - r
                    img[y, x] = gold
                    glow[y, x] = 0.55
    # a woven border: cream with a red stripe
    cream, red = lin('#E9DDC2'), lin('#B7372C')
    for y in range(H):
        for x in range(W):
            e = min(x, y, W - 1 - x, H - 1 - y)
            if e < 2:
                img[y, x] = cream
            elif e == 2:
                img[y, x] = red
    return img, glow


def tapestry_images(name='loom.tapestry'):
    """The picture and its glow mask as packed Blender images (Closest-sampled in the material)."""
    import numpy as np
    rgb, glow = tapestry_pixels()
    H, W = glow.shape
    out = []
    for nm, arr in ((name, rgb), (name + '.glow', np.repeat(glow[:, :, None], 3, axis=2))):
        im = bpy.data.images.new(nm, W, H, alpha=True, float_buffer=True)
        rgba = np.concatenate([arr, np.ones((H, W, 1), np.float32)], axis=2)
        im.pixels.foreach_set(rgba.ravel())
        if nm.endswith('.glow'):
            im.colorspace_settings.name = 'Non-Color'
        im.pack()
        out.append(im)
    return out


def cloth_mat(img, mask):
    """Woven cloth: the picture sampled per weave cell, a basket-weave bump, soft sheen. Value nodes: 'fell'
    (0..1: how much of the picture is woven, from UV v = 0 at the front) and 'eyes' (glow strength)."""
    m, fresh = M.new_mat('loom.cloth')
    if not fresh:
        return m
    nt = m.node_tree
    b = M.principled(m)
    b.location = (700, 0)
    uv = M.node(nt, 'ShaderNodeUVMap', (-1500, 0))
    uv.uv_map = 'UVMap'
    tex = M.node(nt, 'ShaderNodeTexImage', (-600, 250))
    tex.image, tex.interpolation = img, 'Closest'
    M.link(nt, uv.outputs[0], tex.inputs['Vector'])
    gtex = M.node(nt, 'ShaderNodeTexImage', (-600, -150))
    gtex.image, gtex.interpolation = mask, 'Closest'
    M.link(nt, uv.outputs[0], gtex.inputs['Vector'])
    # weave: cell coordinates, a sine ridge along alternating directions per cell (over / under)
    sep = M.node(nt, 'ShaderNodeSeparateXYZ', (-1300, -400))
    M.link(nt, uv.outputs[0], M.sin(sep, 'Vector'))
    mx = M.node(nt, 'ShaderNodeMath', (-1100, -350), operation='MULTIPLY')
    M.link(nt, sep.outputs['X'], mx.inputs[0])
    mx.inputs[1].default_value = PIX_W
    my = M.node(nt, 'ShaderNodeMath', (-1100, -500), operation='MULTIPLY')
    M.link(nt, sep.outputs['Y'], my.inputs[0])
    my.inputs[1].default_value = PIX_H
    fx_ = M.node(nt, 'ShaderNodeMath', (-900, -350), operation='FRACT')
    M.link(nt, mx.outputs[0], fx_.inputs[0])
    fy_ = M.node(nt, 'ShaderNodeMath', (-900, -500), operation='FRACT')
    M.link(nt, my.outputs[0], fy_.inputs[0])
    sx = M.node(nt, 'ShaderNodeMath', (-700, -350), operation='MULTIPLY')
    M.link(nt, fx_.outputs[0], sx.inputs[0])
    sx.inputs[1].default_value = math.pi
    sy = M.node(nt, 'ShaderNodeMath', (-700, -500), operation='MULTIPLY')
    M.link(nt, fy_.outputs[0], sy.inputs[0])
    sy.inputs[1].default_value = math.pi
    snx = M.node(nt, 'ShaderNodeMath', (-550, -350), operation='SINE')
    M.link(nt, sx.outputs[0], snx.inputs[0])
    sny = M.node(nt, 'ShaderNodeMath', (-550, -500), operation='SINE')
    M.link(nt, sy.outputs[0], sny.inputs[0])
    hmul = M.node(nt, 'ShaderNodeMath', (-400, -420), operation='MULTIPLY')
    M.link(nt, snx.outputs[0], hmul.inputs[0])
    M.link(nt, sny.outputs[0], hmul.inputs[1])
    pw = M.node(nt, 'ShaderNodeMath', (-250, -420), operation='POWER')
    M.link(nt, hmul.outputs[0], pw.inputs[0])
    pw.inputs[1].default_value = 0.5
    bump = M.node(nt, 'ShaderNodeBump', (300, -400))
    M.setin(bump, 'Strength', 0.55)
    M.setin(bump, 'Distance', 0.03)
    M.link(nt, pw.outputs[0], M.sin(bump, 'Height'))
    M.link(nt, M.sout(bump, 'Normal'), M.sin(b, 'Normal'))
    # darken the gaps between threads a little
    shade = M.node(nt, 'ShaderNodeMapRange', (-100, -300))
    M.setin(shade, 'To Min', 0.62, 'VALUE')
    M.setin(shade, 'To Max', 1.0, 'VALUE')
    M.link(nt, pw.outputs[0], M.sin(shade, 'Value', 'VALUE'))
    col = M.node(nt, 'ShaderNodeMix', (300, 200), data_type='RGBA', blend_type='MULTIPLY')
    M.setin(col, 'Factor', 1.0, 'VALUE')
    M.link(nt, tex.outputs['Color'], M.sin(col, 'A', 'RGBA'))
    M.link(nt, M.sout(shade, 'Result', 'VALUE'), M.sin(col, 'B', 'RGBA'))
    M.link(nt, M.sout(col, 'Result', 'RGBA'), M.sin(b, 'Base Color'))
    M.setin(b, 'Roughness', 0.86)
    M.setin(b, 'Sheen Weight', 0.5)
    M.setin(b, 'Sheen Roughness', 0.4)
    # the eyes' glow
    ev = M.node(nt, 'ShaderNodeValue', (-600, -700))
    ev.name = ev.label = 'eyes'
    ev.outputs[0].default_value = 0.0
    em = M.node(nt, 'ShaderNodeMath', (100, -150), operation='MULTIPLY')
    M.link(nt, gtex.outputs['Color'], em.inputs[0])
    M.link(nt, ev.outputs[0], em.inputs[1])
    M.setin(b, 'Emission Color', kit.srgb('#FF6A24'))
    M.link(nt, em.outputs[0], M.sin(b, 'Emission Strength'))
    # the fell: woven only where v <= fell
    fv = M.node(nt, 'ShaderNodeValue', (-600, -850))
    fv.name = fv.label = 'fell'
    lt = M.node(nt, 'ShaderNodeMath', (100, -800), operation='LESS_THAN')
    M.link(nt, sep.outputs['Y'], lt.inputs[0])
    M.link(nt, fv.outputs[0], lt.inputs[1])
    M.link(nt, lt.outputs[0], M.sin(b, 'Alpha'))
    m.surface_render_method = 'DITHERED'
    m.use_backface_culling = False
    m.diffuse_color = kit.srgb('#D97757')
    return m


# ------------------------------------------------------------------------------------------------ the loom


class Loom:
    def __init__(self):
        self.weft = None
        self.root = None
        self.warp = None
        self.shafts = []
        self.beater = None
        self.shuttle = None
        self.cloth = None
        self.cloth_m = None
        self.objects = []

    def local(self, p) -> Vector:
        return self.root.matrix_world @ Vector(p)

    def fell_y(self, v: float) -> float:
        return Y_FRONT + (FELL_MAX - Y_FRONT) * v


def _prism_yz(name, poly, x0, thick, coll, m):
    """A board: a polygon in the (y, z) plane extruded along x from x0 by thick."""
    bm = bmesh.new()
    vs = [bm.verts.new((x0, y, z)) for y, z in poly]
    f = bm.faces.new(vs)
    ext = bmesh.ops.extrude_face_region(bm, geom=[f])
    top = [e for e in ext['geom'] if isinstance(e, bmesh.types.BMVert)]
    bmesh.ops.translate(bm, verts=top, vec=(thick, 0, 0))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    o = bpy.data.objects.new(name, me)
    coll.objects.link(o)
    me.materials.append(m)
    geo.bevel(o, 0.12, 2)
    geo.box_uv(o)
    return o


def build_loom(coll, loc=(0, 0, 0), yaw_deg: float = 0.0) -> Loom:
    L = Loom()
    maple = M.solid('loom.maple', '#C49A6C', rough=0.45, coat=0.35, coat_rough=0.15, micro=(6.0, 0.04))
    walnut = M.solid('loom.walnut', '#6B4428', rough=0.4, coat=0.5, coat_rough=0.1, micro=(8.0, 0.03))
    yarn = M.solid('loom.yarn', '#EFE6D2', rough=0.9, sheen=0.6, micro=(40.0, 0.05))
    weft = M.solid('loom.weft', '#D97757', rough=0.85, sheen=0.6, micro=(40.0, 0.05))
    steel = M.steel('loom.steel', 0.25)
    root = kit.empty('loom', tuple(loc), coll, 'ARROWS', 4.0)
    root.rotation_euler = (0, 0, math.radians(yaw_deg))
    L.root = root

    def put(o, p=(0, 0, 0), r=None):
        geo.attach(o, root, Vector(p), r)
        L.objects.append(o)
        return o
    # side frames with the castle
    prof = [(-11.2, 0.0), (11.2, 0.0), (11.2, 8.9), (6.6, 8.9), (5.4, 17.2), (2.6, 17.2), (1.4, 8.9), (-11.2, 8.9)]
    for sx in (-1, 1):
        put(_prism_yz(f'loom.side{sx}', prof, 0.0, 0.9, coll, maple), (sx * 9.4 - (0.9 if sx > 0 else 0.0), 0, 0))
    # beams: breast and back (square), the warp beam (a roller wound with yarn) and the cloth beam
    for nm, y, z, sz in (('breast', Y_FRONT, WARP_Z - 0.55, 1.1), ('backbeam', Y_BACK, WARP_Z - 0.55, 1.1),
                         ('castle', 4.0, 16.6, 1.0)):
        put(geo.box(f'loom.{nm}', (19.6, sz, sz), (0, 0, 0), bev=0.12, m=maple, coll=coll), (0, y, z))
    for nm, y, z, r, m in (('warpbeam', 8.6, 3.6, 1.35, yarn), ('clothbeam', -8.8, 3.4, 1.1, weft)):
        o = kit.cylinder(f'loom.{nm}', r, 18.4, (0, 0, 0), verts=40, m=m, coll=coll, rot=(0, math.radians(90), 0))
        put(o, (0, y, z), (0, math.radians(90), 0))
        for sx in (-1, 1):
            cap = kit.cylinder(f'loom.{nm}.end{sx}', r * 0.45, 0.8, (0, 0, 0), verts=24, m=walnut, coll=coll)
            put(cap, (sx * 9.2, y, z), (0, math.radians(90), 0))
    # the warp: one mesh of thin square tubes, 4 stations per thread (back beam, heddle, fell, breast beam),
    # shape keys for the two sheds and the fell
    verts, faces = [], []
    r = 0.035
    stations = [(Y_BACK, WARP_Z + 0.02), (Y_HEDDLE, WARP_Z), (Y_FRONT, WARP_Z), (Y_FRONT - 0.3, WARP_Z - 0.02)]
    xs = [-HALF_W + 2 * HALF_W * i / (N_WARP - 1) for i in range(N_WARP)]
    for x in xs:
        base = len(verts)
        for y, z in stations:
            verts += [(x - r, y, z - r), (x + r, y, z - r), (x + r, y, z + r), (x - r, y, z + r)]
        for s in range(len(stations) - 1):
            a0, b0 = base + 4 * s, base + 4 * (s + 1)
            for k in range(4):
                faces.append((a0 + k, a0 + (k + 1) % 4, b0 + (k + 1) % 4, b0 + k))
    warp = geo.mesh_obj('loom.warp', verts, faces, coll, yarn)
    put(warp)
    warp.shape_key_add(name='Basis')
    for nm, sgn in (('shedA', 1.0), ('shedB', -1.0)):
        sk = warp.shape_key_add(name=nm, from_mix=False)
        for i, x in enumerate(xs):
            d = SHED * (sgn if i % 2 else -sgn)
            for k in range(4):
                vi = i * 16 + 4 * 1 + k
                sk.data[vi].co.z += d
    sk = warp.shape_key_add(name='fell', from_mix=False)
    for i in range(N_WARP):
        for k in range(4):
            sk.data[i * 16 + 4 * 2 + k].co.y = FELL_MAX
    L.warp = warp
    # heddle shafts: a frame of two bars each and a steel heddle wire per thread
    for si, (yy, sgn) in enumerate(((Y_HEDDLE - 0.35, -1.0), (Y_HEDDLE + 0.35, 1.0))):
        sh = kit.empty(f'loom.shaft{si}', (0, 0, 0), coll, 'PLAIN_AXES', 1.0)
        put(sh, (0, yy, 0))
        for zb in (WARP_Z + 3.4, WARP_Z - 3.4):
            bar = geo.box(f'loom.shaft{si}.bar', (16.8, 0.3, 0.45), (0, 0, 0), bev=0.05, m=walnut, coll=coll)
            geo.attach(bar, sh, Vector((0, 0, zb)))
        wv, wf = [], []
        for i, x in enumerate(xs):
            if (i % 2) != si:
                continue
            b0 = len(wv)
            for z in (WARP_Z - 3.3, WARP_Z + 3.3):
                wv += [(x - 0.018, -0.018, z), (x + 0.018, -0.018, z), (x + 0.018, 0.018, z), (x - 0.018, 0.018, z)]
            for k in range(4):
                wf.append((b0 + k, b0 + (k + 1) % 4, b0 + 4 + (k + 1) % 4, b0 + 4 + k))
        wires = geo.mesh_obj(f'loom.shaft{si}.heddles', wv, wf, coll, steel)
        geo.attach(wires, sh)
        L.shafts.append((sh, sgn))
    # the beater: two arms from the hinge, a reed (steel dents) at the warp, a handle bar on top
    bt = kit.empty('loom.beater', (0, 0, 0), coll, 'PLAIN_AXES', 1.0)
    put(bt, tuple(PIVOT))
    L.beater = bt
    arm_h = WARP_Z + 2.4 - PIVOT.z
    for sx in (-1, 1):
        a = geo.box(f'loom.beater.arm{sx}', (0.6, 0.6, arm_h), (0, 0, 0), bev=0.08, m=maple, coll=coll)
        geo.attach(a, bt, Vector((sx * 8.4, 0, arm_h / 2)))
    for zb, hgt in ((WARP_Z - 1.3 - PIVOT.z, 0.5), (WARP_Z + 1.4 - PIVOT.z, 0.5), (arm_h + 0.3, 0.8)):
        bar = geo.box('loom.beater.bar', (17.4, 0.7, hgt), (0, 0, 0), bev=0.1, m=maple, coll=coll)
        geo.attach(bar, bt, Vector((0, 0, zb)))
    rv, rf = [], []
    for i in range(N_WARP + 1):
        x = -HALF_W - 0.14 + 2 * (HALF_W + 0.14) * i / N_WARP
        b0 = len(rv)
        for z in (WARP_Z - 1.1 - PIVOT.z, WARP_Z + 1.2 - PIVOT.z):
            rv += [(x - 0.02, -0.12, z), (x + 0.02, -0.12, z), (x + 0.02, 0.12, z), (x - 0.02, 0.12, z)]
        for k in range(4):
            rf.append((b0 + k, b0 + (k + 1) % 4, b0 + 4 + (k + 1) % 4, b0 + 4 + k))
    reed = geo.mesh_obj('loom.reed', rv, rf, coll, steel)
    geo.attach(reed, bt)
    # the boat shuttle: a pointed hull (lathe along X, flattened) with an open slot and an orange bobbin
    prof = [(0.0, -2.4), (0.22, -2.1), (0.45, -1.3), (0.52, 0.0), (0.45, 1.3), (0.22, 2.1), (0.0, 2.4)]
    boxwood = M.solid('loom.boxwood', '#E3C38E', rough=0.35, coat=0.6, coat_rough=0.08, micro=(10.0, 0.03))
    hull = geo.lathe('loom.shuttle', prof, segs=24, coll=coll, m=boxwood)
    for v in hull.data.vertices:
        x, y, z = v.co
        v.co = (z, y, x * 0.75)
    bm = bmesh.new()
    bm.from_mesh(hull.data)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(hull.data)
    bm.free()
    hull.data.update()
    sh = kit.empty('loom.shuttle.root', (0, 0, 0), coll, 'PLAIN_AXES', 1.0)
    put(sh, (0, 0, 0))
    geo.attach(hull, sh)
    bob = kit.cylinder('loom.shuttle.bobbin', 0.3, 2.0, (0, 0, 0), verts=16, m=weft, coll=coll,
                       rot=(0, math.radians(90), 0))
    geo.attach(bob, sh, Vector((0, 0, 0.3)), (0, math.radians(90), 0))
    L.shuttle = sh
    # the weft being laid: an orange thread from the edge of the warp to the flying shuttle
    wf = kit.cylinder('loom.weft', 0.07, 1.0, (0, 0, 0), verts=8, m=weft, coll=coll)
    wf.data.transform(Matrix.Rotation(math.radians(90), 4, 'Y'))       # its length along X
    wf.rotation_euler = (0, 0, 0)
    put(wf, (0, 0, WARP_Z + 0.03))
    L.weft = wf
    # the cloth: a plane on top of the warp from the breast beam back to FELL_MAX, over the breast beam and down
    img, mask = tapestry_images()
    L.cloth_m = cloth_mat(img, mask)
    W2 = HALF_W + 0.06
    cv = [(-W2, Y_FRONT, WARP_Z + 0.05), (W2, Y_FRONT, WARP_Z + 0.05), (W2, FELL_MAX, WARP_Z + 0.05),
          (-W2, FELL_MAX, WARP_Z + 0.05)]
    cloth = geo.mesh_obj('loom.cloth', cv, [(0, 1, 2, 3)], coll, L.cloth_m,
                         uvs=[(0, 0), (1, 0), (1, 1), (0, 1)])
    put(cloth)
    L.cloth = cloth
    # the already-woven cloth rolling over the breast beam onto the cloth beam (the picture's bottom border)
    rest = geo.mesh_obj('loom.cloth.roll', [(-W2, Y_FRONT, WARP_Z + 0.05), (W2, Y_FRONT, WARP_Z + 0.05),
                                             (W2, Y_FRONT - 0.2, WARP_Z - 1.1), (-W2, Y_FRONT - 0.2, WARP_Z - 1.1),
                                             (W2, -9.0, 4.5), (-W2, -9.0, 4.5)],
                        [(0, 1, 2, 3), (3, 2, 4, 5)], coll, M.solid('loom.cloth.old', '#E9DDC2', rough=0.9,
                                                                       sheen=0.5, micro=(30.0, 0.08)))
    put(rest)
    return L


# ------------------------------------------------------------------------------------------------ weaving


def smoothstep_(x):
    x = min(max(x, 0.0), 1.0)
    return x * x * (3 - 2 * x)


def weave(L: Loom, picks, fell_keys, t0: float, t1: float, glow_t: float, glow=5.0):
    """Animate the weaving: picks = [(t, direction +1 / -1)] the shuttle crossing times (it arrives at the far side
    at t); fell_keys = [(t, v)] how much picture is woven; the beater swings in after each pick, the shafts swap the
    shed; the eyes glow from glow_t. After the last pick the shuttle lifts out, comes forward over the side frame and
    is laid on the woven cloth by the selvedge (shuttle_rest). Keys every frame (every output frame when built for
    60 fps: a flurry pick crosses in 1.4 scene frames)."""
    fell_node = L.cloth_m.node_tree.nodes['fell'].outputs[0]
    eyes_node = L.cloth_m.node_tree.nodes['eyes'].outputs[0]

    def fell_at(t):
        k = fell_keys
        if t <= k[0][0]:
            return k[0][1]
        for (ta, va), (tb, vb) in zip(k, k[1:]):
            if t <= tb:
                u = (t - ta) / (tb - ta)
                u = u * u * (3 - 2 * u)
                return va + (vb - va) * u
        return k[-1][1]

    picks = sorted(picks)

    def pick_state(t):
        """(shuttle x, shed 0/1 blend, beater y offset from the fell, weft span (x0, x1) or None)."""
        side = -picks[0][1]
        x = side * 11.8
        shed = 0.0
        beat = 2.6
        span = None
        for i, (tp, dirn) in enumerate(picks):
            dur = 0.11 if i < 3 else 0.06
            ts = tp - dur
            if t >= tp:
                x = dirn * 11.8
                shed = float((i + 1) % 2)
                span = (-HALF_W, HALF_W) if t < tp + (0.1 if i < 3 else 0.04) else None
            elif t > ts:
                u = (t - ts) / dur
                x = -dirn * 11.8 + dirn * 23.6 * u
                shed = float(i % 2)
                xe = -dirn * HALF_W
                xs = max(-HALF_W, min(HALF_W, x))
                span = (min(xe, xs), max(xe, xs)) if (xs - xe) * dirn > 0.05 else None
            else:
                break
        # beater: after each pick it swings in to the fell and back
        for i, (tp, dirn) in enumerate(picks):
            d = 0.07 if i < 3 else 0.035
            if tp <= t < tp + 2 * d:
                u = (t - tp) / d
                k = u if u < 1 else 2 - u
                beat = 2.6 - 2.4 * math.sin(k * math.pi / 2)
        return x, shed, beat, span

    t_rest = picks[-1][0] + 0.05              # the weft is laid and beaten in; the shuttle is put away

    def shuttle_rest(t, p):
        """The parked shuttle (p, outside the frame on the last pick's far side) put away on the cloth: up and
        forward clear of the side frame and the castle (A), in over the frame top (B), down onto the cloth (C)."""
        if t <= t_rest:
            return p
        hx, hy, hz = SHUTTLE_HALF
        side = picks[-1][1]
        y_rest = FELL_MAX - 4.8                 # on the woven sky, clear of the fell, the moon and the giant
        x_rest = side * (SIDE_IN - hx - 0.1)    # its tip just inside the side frame
        z_hop = SIDE_TOP + hz + 0.15            # its keel clears the frame top
        z_rest = WARP_Z + 0.05 + hz + 0.005     # lying on the cloth
        ua = smoothstep_((t - t_rest) / 0.08)
        ub = smoothstep_((t - t_rest - 0.07) / 0.12)
        uc = smoothstep_((t - t_rest - 0.19) / 0.06)
        x = p[0] + (x_rest - p[0]) * ub
        y = p[1] + (y_rest - p[1]) * ua
        z = p[2] + (z_hop - p[2]) * ua
        z = z + (z_rest - z) * uc
        return (x, y, z)

    f0, f1 = int(math.floor(t0 * FPS)) - 1, int(math.ceil(t1 * FPS)) + 1
    kb = L.warp.data.shape_keys.key_blocks
    for f in (tm.out_frames(f0, f1) if tm.SMOOTH else range(f0, f1 + 1)):
        t = f / FPS
        v = fell_at(t)
        yf = L.fell_y(v)
        x, shed, beat, span = pick_state(t)
        geo.keyp(fell_node, 'default_value', t, v + 0.004, interp='LINEAR')
        geo.keyp(kb['fell'], 'value', t, v, interp='LINEAR')
        # the shed swaps quickly (over 2 frames) when it changes
        geo.keyp(kb['shedA'], 'value', t, 1.0 - shed, interp='LINEAR')
        geo.keyp(kb['shedB'], 'value', t, shed, interp='LINEAR')
        for sh, sgn in L.shafts:
            geo.keyp(sh, 'location', t, (0.0, sh.location.y, SHED * sgn * ((1.0 - shed) - shed) * 0.8),
                     interp='LINEAR')
        # the shuttle in the shed just behind the fell; the beater's reed at fell + beat
        L.shuttle.location = shuttle_rest(t, (x, yf + 1.3, WARP_Z + 0.05))
        L.shuttle.keyframe_insert('location', frame=f)
        if L.weft is not None:
            if span is None:
                L.weft.scale = (1e-3, 1e-3, 1e-3)
                L.weft.location = (0.0, yf + 0.9, WARP_Z + 0.03)
            else:
                L.weft.scale = (max(1e-3, span[1] - span[0]), 1.0, 1.0)
                L.weft.location = ((span[0] + span[1]) / 2, yf + 0.9 - 0.7 * min(1.0, max(0.0, (2.6 - beat) / 2.4)),
                                   WARP_Z + 0.03)
            L.weft.keyframe_insert('location', frame=f)
            L.weft.keyframe_insert('scale', frame=f)
        yr = yf + beat - PIVOT.y
        ang = math.asin(max(-0.95, min(0.95, yr / (WARP_Z - PIVOT.z))))
        L.beater.rotation_euler = (-ang, 0.0, 0.0)
        L.beater.keyframe_insert('rotation_euler', frame=f)
        geo.keyp(eyes_node, 'default_value', t, 0.0 if t < glow_t else glow * min(1.0, (t - glow_t) / 0.12),
                 interp='LINEAR')
    for o in (L.shuttle, L.beater, L.weft):
        if o is not None:
            kit.set_interp(o, 'LINEAR')
