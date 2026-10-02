"""The desk's props, each built at real size around a root Empty you can move, key or hide.

Laptop (screen you can drive), mug, books, pencil cup + pencils, sticky notes, pen, drawer unit (openable drawers),
kill switch (pressable), the paperclip, and the USB cable. desk.py places them; scenes get them through the Desk handle.
"""
from __future__ import annotations

import math
import os

import bpy
import bmesh
from mathutils import Matrix, Vector

from .. import kit
from ..timing import FPS
from . import geo
from . import materials as M


class Prop:
    """A prop: .root (Empty, move/key it), .objects (every object under it), plus prop-specific handles."""

    def __init__(self, root):
        self.root = root

    @property
    def objects(self):
        return geo.descendants(self.root)

    def visible(self, t_on: float | None = None, t_off: float | None = None):
        """Show the whole prop only from t_on to t_off (kit.visible on every object under the root)."""
        for o in self.objects:
            kit.visible(o, t_on, t_off)
        return self

    def hide(self):
        """Hide the whole prop for the entire scene (renders and viewport)."""
        for o in self.objects:
            o.hide_render = o.hide_viewport = True
        return self


# ------------------------------------------------------------------------------------------------ screen images


def _np():
    import numpy as np
    return np


def _hex(h):
    h = h.lstrip('#')
    return [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]


def screen_image(kind: str = 'code', w: int = 1280, h: int = 800):
    """A generated screen picture (packed into the .blend): 'code', 'loss', 'boot', 'black'. Deterministic."""
    name = f'screen.{kind}'
    if name in bpy.data.images:
        return bpy.data.images[name]
    np = _np()
    a = np.zeros((h, w, 4), dtype=np.float32)
    a[..., 3] = 1.0

    def rect(x0, y0, x1, y1, c, alpha=1.0):   # y from the top
        x0, x1 = max(0, int(x0)), min(w, int(x1))
        y0, y1 = max(0, int(y0)), min(h, int(y1))
        if x1 > x0 and y1 > y0:
            a[y0:y1, x0:x1, :3] = a[y0:y1, x0:x1, :3] * (1 - alpha) + np.array(_hex(c)) * alpha

    r = geo.rng(kind)
    if kind == 'code':
        rect(0, 0, w, h, '#0E141B')
        rect(0, 0, w, 34, '#18212B')
        for i, c in enumerate(('#FF5F57', '#FEBC2E', '#28C840')):
            rect(16 + i * 22, 11, 28 + i * 22, 23, c)
        rect(0, 34, 230, h, '#111922')               # file tree
        for i in range(18):
            rect(24 + 14 * (r() < 0.3), 56 + i * 26, 60 + r() * 130, 66 + i * 26, '#4B5B6B')
        rect(230, 34, 290, h, '#0F161E')              # gutter
        palette = ['#C792EA', '#82AAFF', '#C3E88D', '#D6DEEB', '#D6DEEB', '#F78C6C', '#89DDFF', '#FFCB6B']
        y = 50
        line = 0
        indent = 0
        while y < h - 170:
            rect(248, y + 3, 272, y + 11, '#3A4654')
            if line == 9:
                rect(290, y - 5, w, y + 18, '#1B2733')
            if r() < 0.12:
                y += 22
                line += 1
                continue
            indent = max(0, min(4, indent + (1 if r() < 0.3 else (-1 if r() < 0.3 else 0))))
            x = 310 + indent * 34
            if r() < 0.12:
                rect(x, y + 1, x + 120 + r() * 400, y + 12, '#546E7A')   # comment
            else:
                for _ in range(1 + int(r() * 6)):
                    wd = 24 + r() * 110
                    rect(x, y, x + wd, y + 13, palette[int(r() * len(palette))])
                    x += wd + 12
                    if x > w - 60:
                        break
            y += 22
            line += 1
        rect(290, h - 160, w, h, '#0A0F14')           # terminal: a training log
        rect(290, h - 160, w, h - 150, '#18212B')
        for i in range(5):
            rect(310, h - 138 + i * 26, 380, h - 126 + i * 26, '#82AAFF')
            rect(392, h - 138 + i * 26, 480 + r() * 300, h - 126 + i * 26, '#C3E88D' if i < 4 else '#D97757')
        rect(310, h - 138 + 5 * 26, 324, h - 122 + 5 * 26, '#D6DEEB')
    elif kind == 'loss':
        rect(0, 0, w, h, '#0D1117')
        x0, x1, y0, y1 = 120, w - 80, 90, h - 110
        for i in range(6):
            yy = y0 + (y1 - y0) * i / 5
            rect(x0, yy, x1, yy + 2, '#1F2A36')
        for i in range(9):
            xx = x0 + (x1 - x0) * i / 8
            rect(xx, y0, xx + 2, y1, '#1F2A36')
        rect(x0 - 3, y0, x0, y1 + 3, '#8B98A8')
        rect(x0 - 3, y1, x1, y1 + 3, '#8B98A8')
        rect(x0, 30, x0 + 260, 56, '#D6DEEB')
        xs = np.arange(x0, x1)
        u = (xs - x0) / (x1 - x0)
        drop = 1 / (1 + np.exp(-(u - 0.68) * 90))
        noise = np.array([geo.hash01('loss', int(i)) - 0.5 for i in range(len(xs))])
        val = 0.12 + 0.62 * np.exp(-u * 3.2) * (1 - 0.8 * drop) + 0.18 * (1 - drop) * np.exp(-u) + noise * 0.02 * (1 - 0.6 * drop)
        ys = y0 + (y1 - y0) * (1 - val)
        for dx in range(-2, 3):
            for dy in range(-3, 4):
                xi = np.clip(xs + dx, 0, w - 1).astype(int)
                yi = np.clip(ys + dy, 0, h - 1).astype(int)
                a[yi, xi, :3] = _hex('#D97757')
    elif kind == 'boot':
        rect(0, 0, w, h, '#050608')
        cx, cy = w // 2, h // 2 - 40
        rect(cx - 80, cy - 45, cx + 80, cy + 45, '#D97757')
        rect(cx - 45, cy - 18, cx - 25, cy + 12, '#1A1614')
        rect(cx + 25, cy - 18, cx + 45, cy + 12, '#1A1614')
        rect(cx - 150, cy + 110, cx + 150, cy + 116, '#2A2F36')
        rect(cx - 150, cy + 110, cx - 40, cy + 116, '#D6DEEB')
    else:
        rect(0, 0, w, h, '#000000')
    a = a[::-1].copy()
    img = bpy.data.images.new(name, w, h, alpha=False)
    img.pixels.foreach_set(a.ravel())
    try:
        img.pack()
    except Exception:
        d = os.path.join(kit.OUT, 'cache', 'sets')
        os.makedirs(d, exist_ok=True)
        p = os.path.join(d, f'{name}.png')
        img.filepath_raw = p
        img.file_format = 'PNG'
        img.save()
    return img


# ------------------------------------------------------------------------------------------------ laptop


class Laptop(Prop):
    """Laptop: .hinge (lid pivot), .screen_obj, .fill (area light), screen(t, glow=, color=, mix=), set_image()."""

    def __init__(self, root):
        super().__init__(root)
        self.hinge = self.lid = self.screen_obj = self.fill = None
        self.glow_socket = self.tint_socket = self.mix_socket = None
        self.img_a = self.img_b = None
        self.fill_power = 1.0   # set by lighting(): watts at glow 1
        self.glow = 1.0

    def set_image(self, img, slot: str = 'A'):
        """img: a bpy image, a file path, or a built-in name ('code', 'loss', 'boot', 'black')."""
        if isinstance(img, str):
            img = screen_image(img) if img in ('code', 'loss', 'boot', 'black') else bpy.data.images.load(img, check_existing=True)
        (self.img_a if slot == 'A' else self.img_b).image = img
        return self

    def screen(self, t: float | None = None, *, glow: float | None = None, color=None, mix: float | None = None,
               interp: str = 'LINEAR'):
        """Screen state: glow (emission; 1 = normal), color (tint multiplied over the picture), mix (0 = image A,
        1 = image B). Keys at t if given. The cool fill light follows glow and colour."""
        if glow is not None:
            self.glow = glow
            self.glow_socket.default_value = 3.2 * glow
            self.fill.data.energy = self.fill_power * glow
            if t is not None:
                geo.keyp(self.glow_socket, 'default_value', t, interp=interp)
                geo.keyp(self.fill.data, 'energy', t, interp=interp)
        if color is not None:
            c = M.col(color)
            self.tint_socket.default_value = c
            self.fill.data.color = [min(1.0, 0.35 + 0.65 * x) for x in c[:3]]
            if t is not None:
                geo.keyp(self.tint_socket, 'default_value', t, interp=interp)
                geo.keyp(self.fill.data, 'color', t, interp=interp)
        if mix is not None:
            self.mix_socket.default_value = mix
            if t is not None:
                geo.keyp(self.mix_socket, 'default_value', t, interp=interp)
        return self

    def open(self, t: float, angle: float = 110.0, interp='BEZIER'):
        """Lid angle in degrees (0 closed, 90 upright, 110 normal), keyed at t."""
        self.hinge.rotation_euler[0] = math.radians(90 - angle)
        geo.keyp(self.hinge, 'rotation_euler', t, index=0, interp=interp)
        return self

    def screen_point(self, u=0.5, v=0.5) -> Vector:
        """World point on the screen (u, v in 0..1 from bottom left)."""
        o = self.screen_obj
        return o.matrix_world @ Vector(((u - 0.5) * self.sw, 0.0, (v - 0.5) * self.sh))


def _screen_material():
    m, fresh = M.new_mat('laptop.screen')
    nt = m.node_tree
    b = M.principled(m)
    M.setin(b, 'Base Color', (0.002, 0.002, 0.003, 1))
    M.setin(b, 'Roughness', 0.22)
    M.setin(b, 'Specular IOR Level', 0.22)
    uv = M.node(nt, 'ShaderNodeTexCoord', (-900, 0))
    ia = M.node(nt, 'ShaderNodeTexImage', (-650, 150))
    ib = M.node(nt, 'ShaderNodeTexImage', (-650, -150))
    ia.name = ia.label = 'screen.A'
    ib.name = ib.label = 'screen.B'
    M.link(nt, M.sout(uv, 'UV'), M.sin(ia, 'Vector'))
    M.link(nt, M.sout(uv, 'UV'), M.sin(ib, 'Vector'))
    mx = M.node(nt, 'ShaderNodeMix', (-350, 0), data_type='RGBA', blend_type='MIX')
    mx.name = mx.label = 'screen.mix'
    M.setin(mx, 'Factor', 0.0, 'VALUE')
    M.link(nt, M.sout(ia, 'Color'), M.sin(mx, 'A', 'RGBA'))
    M.link(nt, M.sout(ib, 'Color'), M.sin(mx, 'B', 'RGBA'))
    tn = M.node(nt, 'ShaderNodeMix', (-150, 0), data_type='RGBA', blend_type='MULTIPLY')
    tn.name = tn.label = 'screen.tint'
    M.setin(tn, 'Factor', 1.0, 'VALUE')
    M.link(nt, M.sout(mx, 'Result', 'RGBA'), M.sin(tn, 'A', 'RGBA'))
    M.setin(tn, 'B', (1, 1, 1, 1), 'RGBA')
    M.link(nt, M.sout(tn, 'Result', 'RGBA'), M.sin(b, 'Emission Color'))
    M.setin(b, 'Emission Strength', 3.2)
    return m, ia, ib, M.sin(mx, 'Factor', 'VALUE'), M.sin(tn, 'B', 'RGBA'), M.sin(b, 'Emission Strength')


def build_laptop(coll, loc=(-16, 14, 0), yaw_deg=4.0, angle=108.0) -> Laptop:
    root = geo.empty('laptop', loc, coll, 4.0, 'ARROWS', rot=(0, 0, math.radians(yaw_deg)))
    lp = Laptop(root)
    alu = M.brushed('laptop.alu', '#8E9296', rough=(0.25, 0.4), tile=30, val=0.9)
    keys_m = M.plastic('laptop.keys', '#15171A', rough=0.45)
    glass_black = M.solid('laptop.bezel', '#060708', rough=0.08, coat=0.0, spec=0.6)
    pad_m = M.solid('laptop.pad', '#7E8286', rough=0.22, metal=0.6)
    W, D, T = 30.4, 21.2, 1.5
    base = geo.box('laptop.base', (W, D, T), (0, 0, T / 2), bev=0.45, segments=4, m=alu, coll=coll)
    geo.attach(base, root, (0, 0, T / 2))
    # keyboard (one mesh of key caps) in a shallow well
    well = geo.box('laptop.well', (W - 3.2, 10.6, 0.06), (0, 0, 0), m=keys_m, coll=coll)
    geo.attach(well, root, (0, 3.9, T + 0.005))
    bm = bmesh.new()
    pitch, cap = 1.9, 1.6

    def keycap(x, y, wu=1.0, hu=1.0):
        mtx = Matrix.Translation((x, y, T + 0.07)) @ Matrix.Diagonal((cap + (wu - 1) * pitch, cap * hu, 0.12, 1.0))
        bmesh.ops.create_cube(bm, size=1.0, matrix=mtx)

    x_left = -(13 * pitch) / 2 + pitch / 2
    for row in range(4):
        y = 7.6 - row * pitch
        for c in range(13):
            keycap(x_left + c * pitch, y)
    for c in range(14):   # function row (half height)
        keycap(x_left - pitch * 0.5 + c * pitch * 13 / 13.5 + 0.4, 9.25, 0.95, 0.5)
    y = 7.6 - 4 * pitch
    xs = [(-5.5, 1.0), (-4.5, 1.0), (-3.5, 1.0), (-2.4, 1.2), (0.0, 5.0), (2.4, 1.2), (3.5, 1.0), (4.5, 1.0), (5.5, 1.0)]
    for cx, wu in xs:
        keycap(cx * pitch, y, wu)
    km = bpy.data.meshes.new('laptop.keys')
    bm.to_mesh(km)
    bm.free()
    kobj = bpy.data.objects.new('laptop.keys', km)
    coll.objects.link(kobj)
    km.materials.append(keys_m)
    geo.bevel(kobj, 0.08, 2)
    geo.attach(kobj, root)
    pad = geo.box('laptop.trackpad', (11.5, 7.2, 0.04), (0, 0, 0), bev=0.02, m=pad_m, coll=coll)
    geo.attach(pad, root, (0, -5.8, T + 0.005))
    # lid on a hinge at the back edge
    hinge = geo.empty('laptop.hinge', (0, 0, 0), coll, 2.0)
    geo.attach(hinge, root, (0, D / 2 - 0.3, T))
    lp.hinge = hinge
    lid = geo.box('laptop.lid', (W, 0.5, D - 0.4), (0, 0, 0), m=alu, coll=coll)
    # front face -> bezel material (before the bevel is evaluated, material per face)
    lid.data.materials.append(glass_black)
    for p in lid.data.polygons:
        if p.normal.y < -0.9:
            p.material_index = 1
    geo.bevel(lid, 0.3, 3)
    geo.attach(lid, hinge, (0, -0.25, (D - 0.4) / 2 + 0.05))
    lp.lid = lid
    scr_m, ia, ib, mixs, tints, glows = _screen_material()
    sw, sh = 28.2, 17.6
    lp.sw, lp.sh = sw, sh
    verts = [(-sw / 2, 0, -sh / 2), (sw / 2, 0, -sh / 2), (sw / 2, 0, sh / 2), (-sw / 2, 0, sh / 2)]
    scr = geo.mesh_obj('laptop.screen', verts, [(0, 1, 2, 3)], coll, scr_m, uvs=[(0, 0), (1, 0), (1, 1), (0, 1)])
    geo.attach(scr, hinge, (0, -0.51, 1.25 + sh / 2 + 0.3))
    lp.screen_obj = scr
    lp.img_a, lp.img_b = ia, ib
    lp.mix_socket, lp.tint_socket, lp.glow_socket = mixs, tints, glows
    lp.set_image('code', 'A')
    lp.set_image('loss', 'B')
    # the cool fill: a rectangle light over the screen, facing the user
    ld = bpy.data.lights.new('laptop.fill', 'AREA')
    ld.shape, ld.size, ld.size_y = 'RECTANGLE', sw, sh
    ld.color = kit.srgb(kit.PAL['screen'])[:3]
    ld.energy = 1.0
    ld.spread = math.radians(150)
    ld.specular_factor = 0.2     # the screen's own emission already reflects in glossy things
    fill = bpy.data.objects.new('laptop.fill', ld)
    coll.objects.link(fill)
    geo.attach(fill, hinge, (0, -0.9, 1.25 + sh / 2 + 0.3), (math.radians(-90), 0, 0))
    lp.fill = fill
    # rubber feet
    for sx in (-1, 1):
        for sy in (-1, 1):
            ft = kit.cylinder(f'laptop.foot{sx}{sy}', 0.5, 0.12, (0, 0, 0), verts=16, m=M.rubber(), coll=coll)
            geo.attach(ft, root, (sx * (W / 2 - 2.5), sy * (D / 2 - 2.5), 0.02))
    hinge.rotation_euler[0] = math.radians(90 - angle)
    return lp


# ------------------------------------------------------------------------------------------------ mug


def build_mug(coll, loc=(36, -8, 0), yaw_deg=-140.0, glaze='#4E7087'):
    root = geo.empty('mug', loc, coll, 3.0, 'ARROWS', rot=(0, 0, math.radians(yaw_deg)))
    p = Prop(root)
    glz = M.ceramic('mug.glaze', glaze, rough=0.06)
    inner = M.ceramic('mug.inner', '#EDE6D6', rough=0.06)
    clay = M.solid('mug.clay', '#B79C7E', rough=0.8, micro=(6.0, 0.08))
    outer = [(0.0, 0.3), (3.3, 0.3), (3.5, 0.02), (3.85, 0.0), (4.15, 0.45), (4.25, 1.2), (4.32, 9.1), (4.22, 9.5),
             (3.98, 9.52), (3.86, 9.2)]
    innerp = [(3.82, 1.4), (3.5, 0.98), (0.0, 0.92)]
    prof = outer + innerp
    # segments: foot underside/clay (0-2), glazed outside (3-8), inner glaze (9..)
    idx = [2, 2, 2, 2, 0, 0, 0, 0, 0, 1, 1, 1]
    body = geo.lathe('mug.body', prof, segs=72, coll=coll, mats=[glz, inner, clay], mat_idx=idx[:len(prof) - 1])
    geo.attach(body, root)
    # handle: a D-shaped loop
    hp = [(3.9, 0, 7.9), (5.6, 0, 8.0), (6.6, 0, 6.8), (6.5, 0, 4.2), (5.5, 0, 3.0), (3.9, 0, 2.9)]
    hd = geo.curve_tube('mug.handle', hp, 0.5, coll=coll, m=glz, kind='BEZIER', res=10, bevel_res=5, to_mesh=True)
    hd.scale = (1.0, 1.35, 1.0)
    geo.attach(hd, root)
    geo.set_smooth(hd, 60)
    # coffee
    cof = M.solid('mug.coffee', '#1E0F07', rough=0.06, spec=0.6)
    cf = geo.lathe('mug.coffee', [(0.0, 7.4), (3.8, 7.4)], segs=48, coll=coll, m=cof)
    geo.attach(cf, root)
    crema = M.solid('mug.crema', '#6B4226', rough=0.3)
    cr = geo.lathe('mug.crema', [(3.35, 7.41), (3.8, 7.41)], segs=48, coll=coll, m=crema)
    geo.attach(cr, root)
    p.top = Vector((0, 0, 9.52))
    p.radius = 4.3
    return p


# ------------------------------------------------------------------------------------------------ books


BOOKS = [  # (length along spine, width, thickness, cover colour)
    (24.0, 17.0, 3.4, '#7A2E2A'),
    (22.5, 15.5, 2.3, '#253C5A'),
    (21.0, 14.5, 4.1, '#B08A3C'),
    (19.0, 13.0, 1.9, '#2F4B38'),
]


def _pages_mat():
    m, fresh = M.new_mat('book.pages')
    if not fresh:
        return m
    nt = m.node_tree
    b = M.principled(m)
    M.setin(b, 'Roughness', 0.85)
    tc = M.node(nt, 'ShaderNodeTexCoord', (-700, 0))
    wv = M.node(nt, 'ShaderNodeTexWave', (-500, 0))
    wv.wave_type = 'BANDS'
    wv.bands_direction = 'Z'
    M.setin(wv, 'Scale', 14.0)
    M.setin(wv, 'Distortion', 1.5)
    M.setin(wv, 'Detail', 2.0)
    M.link(nt, M.sout(tc, 'Object'), M.sin(wv, 'Vector'))
    mx = M.node(nt, 'ShaderNodeMix', (-250, 0), data_type='RGBA', blend_type='MIX')
    M.link(nt, M.sout(wv, 'Factor'), M.sin(mx, 'Factor', 'VALUE'))
    M.setin(mx, 'A', kit.srgb('#E9DDC2'), 'RGBA')
    M.setin(mx, 'B', kit.srgb('#CDBE9E'), 'RGBA')
    M.link(nt, M.sout(mx, 'Result', 'RGBA'), M.sin(b, 'Base Color'))
    bp = M.node(nt, 'ShaderNodeBump', (-250, -250))
    M.setin(bp, 'Strength', 0.25)
    M.link(nt, M.sout(wv, 'Factor'), M.sin(bp, 'Height'))
    M.link(nt, M.sout(bp, 'Normal'), M.sin(b, 'Normal'))
    m.diffuse_color = kit.srgb('#E9DDC2')
    return m


def build_book(coll, name, L, W, T, color, parent=None, loc=(0, 0, 0), yaw_deg=0.0):
    """A hardback lying flat, spine facing -Y, at its own root (origin bottom centre)."""
    root = geo.empty(name, loc, coll, 2.0, rot=(0, 0, math.radians(yaw_deg)))
    if parent is not None:
        geo.attach(root, parent, loc, (0, 0, math.radians(yaw_deg)))
    cover = M.tex_mat(f'{name}.cloth', 'linen', 30, tint=color, sat=0.0, val=1.0, rough=(0.65, 0.85), normal=0.8,
                      sheen=0.3, fallback=color)
    foil = M.brass('book.foil', '#D4AF62', 0.3)
    b = 0.24
    parts = [
        geo.box(f'{name}.bottom', (L, W, b), (0, 0, b / 2), bev=0.06, segments=2, m=cover, coll=coll),
        geo.box(f'{name}.top', (L, W, b), (0, 0, T - b / 2), bev=0.06, segments=2, m=cover, coll=coll),
    ]
    sp = geo.box(f'{name}.spine', (L, 0.34, T), (0, -W / 2 + 0.17, T / 2), bev=0.14, segments=4, m=cover, coll=coll)
    parts.append(sp)
    pg = geo.box(f'{name}.pages', (L - 0.6, W - 0.55, T - 2 * b + 0.02), (0, 0.05, T / 2), bev=0.05, segments=2,
                 m=_pages_mat(), coll=coll)
    parts.append(pg)
    for k, zz in enumerate((0.28, 0.72)):
        fb = geo.box(f'{name}.foil{k}', (L * 0.06 if k else L * 0.5, 0.02, T * 0.12), (-(L * 0.2) if k else 0,
                     -W / 2 - 0.005, T * zz), m=foil, coll=coll)
        parts.append(fb)
    for o in parts:
        geo.attach(o, root, o.location.copy())
    return root


def build_books(coll, loc=(-42, -16, 0), yaw_deg=-8.0):
    root = geo.empty('books', loc, coll, 3.0, 'ARROWS', rot=(0, 0, math.radians(yaw_deg)))
    p = Prop(root)
    z = 0.0
    p.books = []
    for i, (L, W, T, c) in enumerate(BOOKS):
        yaw = [0.0, 6.0, -4.0, 9.0][i]
        off = [(0, 0), (0.6, -0.5), (-0.4, 0.3), (0.8, 0.2)][i]
        br = build_book(coll, f'book{i}', L, W, T, c, parent=root, loc=(off[0], off[1], z), yaw_deg=yaw)
        p.books.append(Prop(br))
        z += T
    p.top = Vector((0, 0, z))
    return p


# ------------------------------------------------------------------------------------------------ pencil cup, pencils, pen


PENCILS = [  # (paint colour, tilt deg, azimuth deg, spin, sharpened end up?)
    ('#E9B820', 11, 20, 0, True),
    ('#E9B820', 14, 140, 20, True),
    ('#2F6B4F', 9, 250, 5, False),
    ('#C23A2E', 16, 300, 40, True),
    ('#E9B820', 7, 200, 12, False),
    ('#1F3A66', 13, 75, 33, True),
]


def build_pencil(coll, name, paint='#E9B820', length=17.6):
    """A hexagonal pencil along +Z from its base (eraser end) at the origin: eraser, ferrule, body, cone, lead."""
    paint_m = M.enamel(f'pencil.paint.{paint}', paint, rough=0.35, coat=0.6)
    wood = M.solid('pencil.wood', '#D9B48A', rough=0.7, micro=(12.0, 0.1))
    lead = M.solid('pencil.lead', '#2B2B2D', rough=0.35, metal=0.3)
    ferrule = M.brushed('pencil.ferrule', '#C8CACC', rough=(0.2, 0.35), tile=5)
    eraser = M.solid('pencil.eraser', '#E38C8C', rough=0.75, micro=(8.0, 0.05))
    body_end = length - 1.9
    objs = [
        geo.lathe(f'{name}.eraser', [(0.0, 0.0), (0.3, 0.02), (0.33, 0.12), (0.33, 0.8), (0.0, 0.8)], segs=16, coll=coll, m=eraser),
        geo.lathe(f'{name}.ferrule', [(0.36, 0.7), (0.38, 0.8), (0.38, 1.0), (0.36, 1.05), (0.38, 1.1), (0.38, 1.5),
                                      (0.36, 1.55), (0.38, 1.6), (0.38, 1.75), (0.36, 1.8)], segs=24, coll=coll, m=ferrule,
                  smooth_angle=30),
        geo.lathe(f'{name}.body', [(0.0, 1.7), (0.405, 1.7), (0.405, body_end), (0.0, body_end)], segs=6, coll=coll,
                  m=paint_m, smooth=False),
        geo.lathe(f'{name}.cone', [(0.39, body_end), (0.1, length - 0.35), (0.0, length - 0.33)], segs=24, coll=coll, m=wood),
        geo.lathe(f'{name}.lead', [(0.105, length - 0.37), (0.03, length - 0.02), (0.0, length)], segs=16, coll=coll, m=lead),
    ]
    o = geo.join(objs, name)
    return o


def build_pencil_cup(coll, loc=(-40, 30, 0)):
    root = geo.empty('pencilcup', loc, coll, 3.0, 'ARROWS')
    p = Prop(root)
    cupm = M.brushed('pencilcup.metal', '#3A3D40', rough=(0.3, 0.5), tile=20, val=0.7)
    prof = geo.rounded_profile([(0.0, 0.0), (3.9, 0.0), (4.0, 0.2), (4.0, 10.4), (4.1, 10.55), (3.95, 10.7), (3.8, 10.4),
                                (3.8, 0.5), (0.0, 0.5)], 0.08, 2)
    cup = geo.lathe('pencilcup.cup', prof, segs=64, coll=coll, m=cupm)
    geo.attach(cup, root)
    p.pencils = []
    for i, (paint, tilt, az, spin, up) in enumerate(PENCILS):
        pc = build_pencil(coll, f'pencil{i}', paint)
        piv = geo.empty(f'pencil{i}.root', (0, 0, 0), coll, 1.0)
        a = math.radians(az)
        # lean away from the cup centre, resting on the rim
        rx, ry = 2.0 * math.cos(a + math.pi), 2.0 * math.sin(a + math.pi)
        geo.attach(piv, root, (rx, ry, 0.5))
        piv.rotation_euler = (math.radians(tilt) * math.sin(a) * -1, math.radians(tilt) * math.cos(a), math.radians(spin))
        if up:
            geo.attach(pc, piv, (0, 0, 0))
        else:
            geo.attach(pc, piv, (0, 0, 17.6), (math.pi, 0, 0))
        p.pencils.append(Prop(piv))
    p.top = Vector((0, 0, 10.7))
    return p


def build_pen(coll, loc=(-19, -26, 0), yaw_deg=28.0):
    root = geo.empty('pen', loc, coll, 2.0, 'ARROWS', rot=(0, 0, math.radians(yaw_deg)))
    p = Prop(root)
    bodym = M.plastic('pen.body', '#101218', rough=0.25, coat=0.5)
    chrome = M.chrome('pen.chrome')
    L = 13.8
    prof = [(0.0, 0.0), (0.12, 0.0), (0.2, 0.4), (0.25, 0.9)]
    tip = geo.lathe('pen.tip', prof + [(0.0, 0.9)], segs=24, coll=coll, m=chrome)
    body = geo.lathe('pen.body', [(0.36, 0.85), (0.46, 1.6), (0.47, L - 1.2), (0.42, L - 0.9), (0.0, L - 0.9)], segs=32,
                     coll=coll, m=bodym)
    btn = geo.lathe('pen.button', [(0.25, L - 1.0), (0.3, L - 0.95), (0.3, L - 0.2), (0.2, L), (0.0, L)], segs=24, coll=coll,
                    m=chrome)
    clip = geo.box('pen.clip', (0.12, 0.26, 5.0), (0, 0, 0), bev=0.04, m=chrome, coll=coll)
    piv = geo.empty('pen.axis', (0, 0, 0), coll, 1.0)
    geo.attach(piv, root, (-L / 2, 0, 0.47), (0, math.radians(90), 0))
    for o in (tip, body, btn):
        geo.attach(o, piv)
    geo.attach(clip, piv, (-0.55, 0, L - 3.6))
    return p


# ------------------------------------------------------------------------------------------------ sticky notes


def build_notes(coll, pad_loc=(-20, -15, 0), pad_yaw=12.0):
    root = geo.empty('notes', pad_loc, coll, 2.0, 'ARROWS', rot=(0, 0, math.radians(pad_yaw)))
    p = Prop(root)
    yel = M.paper('note.yellow', '#F2D54B', tile=25)
    pink = M.paper('note.pink', '#F2A0B8', tile=25)
    mint = M.paper('note.mint', '#A6E3C8', tile=25)
    pad = geo.box('notes.pad', (7.6, 7.6, 0.9), (0, 0, 0), bev=0.03, segments=1, m=_pad_side_mat(), coll=coll)
    geo.attach(pad, root, (0, 0, 0.45))
    top = _note(coll, 'notes.top', yel, curl=0.22)
    geo.attach(top, root, (0.05, 0.05, 0.91), (0, 0, math.radians(1.5)))
    p.pad = pad
    p.loose = []
    return p


def _pad_side_mat():
    m, fresh = M.new_mat('note.padside')
    if not fresh:
        return m
    nt = m.node_tree
    b = M.principled(m)
    M.setin(b, 'Roughness', 0.85)
    tc = M.node(nt, 'ShaderNodeTexCoord', (-700, 0))
    wv = M.node(nt, 'ShaderNodeTexWave', (-500, 0))
    wv.wave_type = 'BANDS'
    wv.bands_direction = 'Z'
    M.setin(wv, 'Scale', 9.0)
    M.setin(wv, 'Distortion', 0.6)
    M.link(nt, M.sout(tc, 'Object'), M.sin(wv, 'Vector'))
    mx = M.node(nt, 'ShaderNodeMix', (-250, 0), data_type='RGBA', blend_type='MIX')
    M.link(nt, M.sout(wv, 'Factor'), M.sin(mx, 'Factor', 'VALUE'))
    M.setin(mx, 'A', kit.srgb('#F2D54B'), 'RGBA')
    M.setin(mx, 'B', kit.srgb('#D9B936'), 'RGBA')
    M.link(nt, M.sout(mx, 'Result', 'RGBA'), M.sin(b, 'Base Color'))
    m.diffuse_color = kit.srgb('#F2D54B')
    return m


def _note(coll, name, mat, size=7.6, curl=0.5):
    """A single sticky note, its free (bottom) edge curling up slightly."""
    n = 10
    verts, faces, uvs = [], [], []
    for j in range(n + 1):
        v = j / n
        y = -size / 2 + size * v
        lift = curl * max(0.0, (0.35 - v) / 0.35) ** 2
        for i in range(2):
            verts.append((-size / 2 + size * i, y, lift))
    for j in range(n):
        a = 2 * j
        faces.append((a, a + 1, a + 3, a + 2))
        uvs += [(0, j * size / n), (size, j * size / n), (size, (j + 1) * size / n), (0, (j + 1) * size / n)]
    o = geo.mesh_obj(name, verts, faces, coll, mat, smooth=True, uvs=uvs)
    sol = o.modifiers.new('thick', 'SOLIDIFY')
    sol.thickness = 0.02
    return o


def add_note(coll, parent, name, color='#F2D54B', loc=(0, 0, 0.02), rot=(0, 0, 0), curl=0.5):
    mat = M.paper(f'note.{color}', color, tile=25)
    o = _note(coll, name, mat, curl=curl)
    geo.attach(o, parent, loc, rot)
    return o


# ------------------------------------------------------------------------------------------------ drawer unit


class DrawerUnit(Prop):
    """A small painted-steel drawer cabinet. .drawers[k] (Empty, 0 = top) slide along -Y (towards the viewer)."""
    MAX_OUT = 17.0

    def __init__(self, root):
        super().__init__(root)
        self.drawers = []
        self.inner = []   # per drawer: (centre local, size) of the tray's interior

    def open(self, t0: float, t1: float, amount: float = 1.0, k: int = 0, interp='BEZIER'):
        """Slide drawer k from its current keyed position (at t0) to `amount` open (0..1) at t1."""
        d = self.drawers[k]
        geo.keyp(d, 'location', t0, index=1, interp=interp)
        d.location[1] = d['y0'] - self.MAX_OUT * amount
        geo.keyp(d, 'location', t1, index=1, interp=interp)
        return self

    def burst(self, t: float, amount: float = 1.0, k: int = 0):
        """Drawer k shoots open at t (2 frames), hits its stop and bounces."""
        d = self.drawers[k]
        y0 = d['y0']
        f = 1 / FPS
        for dt, a in ((-f, 0.0), (0.0, 0.0), (f, 0.55), (2 * f, 1.0), (3 * f, 0.9), (4 * f, 1.0), (6 * f, 0.97), (8 * f, 1.0)):
            geo.keyp(d, 'location', t + dt, y0 - self.MAX_OUT * a * amount, index=1, interp='LINEAR')
        return self

    def inside(self, k: int = 0, amount: float = 1.0) -> Vector:
        """World point at the middle of drawer k's tray floor when it is `amount` open (0 = closed)."""
        c, _ = self.inner[k]
        d = self.drawers[k]
        return self.root.matrix_world @ (Vector((0, d['y0'] - self.MAX_OUT * amount, d.location[2])) + c)

    def inside_size(self, k: int = 0) -> Vector:
        """Interior (width, depth, height) of drawer k's tray, cm."""
        return self.inner[k][1].copy()


def build_drawer_unit(coll, loc=(-60, 18, 0), yaw_deg=6.0, color='#6E8B7F', n=3):
    root = geo.empty('drawers', loc, coll, 3.0, 'ARROWS', rot=(0, 0, math.radians(yaw_deg)))
    du = DrawerUnit(root)
    en = M.enamel('drawers.enamel', color, rough=0.4, coat=0.25)
    inside_m = M.enamel('drawers.inside', '#4E6359', rough=0.55, coat=0.0)
    brass = M.brass('drawers.brass', '#C29A52', 0.3)
    card = M.paper('drawers.card', '#EFE7D2', tile=20)
    W, D, H, th = 22.0, 26.0, 18.0, 0.3
    panels = [
        ((W, D, th), (0, 0, th / 2)),
        ((W, D, th), (0, 0, H - th / 2)),
        ((th, D, H), (-W / 2 + th / 2, 0, H / 2)),
        ((th, D, H), (W / 2 - th / 2, 0, H / 2)),
        ((W, th, H), (0, D / 2 - th / 2, H / 2)),
    ]
    slot_h = (H - 2 * th - (n - 1) * 0.2) / n
    for k in range(1, n):
        z = th + k * slot_h + (k - 0.5) * 0.2
        panels.append(((W - 2 * th, D - th, 0.2), (0, th / 2, z)))
    body = []
    for i, (sz, lc) in enumerate(panels):
        o = geo.box(f'drawers.panel{i}', sz, lc, bev=0.08 if i < 5 else 0.0, segments=2, m=en, coll=coll)
        body.append(o)
    for o in body:
        geo.attach(o, root, o.location.copy())
    # feet
    for sx in (-1, 1):
        for sy in (-1, 1):
            ft = kit.cylinder(f'drawers.foot{sx}{sy}', 0.7, 0.3, (0, 0, 0), verts=16, m=M.rubber(), coll=coll)
            geo.attach(ft, root, (sx * (W / 2 - 1.8), sy * (D / 2 - 1.8), -0.15))
    root.location.z = loc[2] + 0.3
    for k in range(n):
        z_bot = H - th - (k + 1) * slot_h - k * 0.2
        dr = geo.empty(f'drawers.drawer{k}', (0, 0, 0), coll, 1.5)
        geo.attach(dr, root, (0, 0, z_bot))
        dr['y0'] = 0.0
        fw, fh = W - 2 * th - 0.25, slot_h - 0.2
        front = geo.box(f'drawers.front{k}', (fw, 0.45, fh), (0, 0, 0), bev=0.1, segments=3, m=en, coll=coll)
        geo.attach(front, dr, (0, -D / 2 + 0.2, fh / 2 + 0.1))
        tw, td, tdep = fw - 0.6, D - 1.8, fh - 1.0
        tray = []
        tray.append(geo.box(f'drawers.tray{k}.floor', (tw, td, 0.15), (0, 0, 0), m=inside_m, coll=coll))
        tray[-1].location = (0, -D / 2 + 0.45 + td / 2, 0.25)
        for s in (-1, 1):
            sd = geo.box(f'drawers.tray{k}.side{s}', (0.15, td, tdep), (0, 0, 0), m=inside_m, coll=coll)
            sd.location = (s * (tw / 2 - 0.075), -D / 2 + 0.45 + td / 2, 0.25 + tdep / 2)
            tray.append(sd)
        bk = geo.box(f'drawers.tray{k}.back', (tw, 0.15, tdep), (0, 0, 0), m=inside_m, coll=coll)
        bk.location = (0, -D / 2 + 0.45 + td, 0.25 + tdep / 2)
        tray.append(bk)
        for o in tray:
            geo.attach(o, dr, o.location.copy())
        du.inner.append((Vector((0, -D / 2 + 0.45 + td / 2, 0.33)), Vector((tw - 0.3, td - 0.3, tdep))))
        # label holder + card, and a cup pull
        holder = geo.box(f'drawers.holder{k}', (4.4, 0.08, 1.9), (0, 0, 0), bev=0.03, segments=1, m=brass, coll=coll)
        geo.attach(holder, dr, (0, -D / 2 - 0.06, fh * 0.68))
        cd = geo.box(f'drawers.card{k}', (3.9, 0.04, 1.45), (0, 0, 0), m=card, coll=coll)
        geo.attach(cd, dr, (0, -D / 2 - 0.1, fh * 0.68))
        pull = geo.lathe(f'drawers.pull{k}', geo.rounded_profile([(1.6, 0.0), (1.6, 0.35), (1.45, 0.4), (1.2, 0.2),
                                                                 (0.0, 0.2)], 0.1), segs=40, coll=coll, m=brass)
        geo.attach(pull, dr, (0, -D / 2 - 0.02, fh * 0.3), (math.radians(90), 0, 0))
        pull.scale = (1.0, 0.55, 1.0)
        du.drawers.append(dr)
    du.size = (W, D, H)
    du.front_local = Vector((0, -D / 2 - 0.1, 0))
    return du


# ------------------------------------------------------------------------------------------------ kill switch


class KillSwitch(Prop):
    def __init__(self, root):
        super().__init__(root)
        self.button = None

    def press(self, t: float, *, latch: bool = True, depth: float = 0.55, hold: float = 0.3):
        b = self.button
        z0 = b['z0']
        f = 1 / FPS
        geo.keyp(b, 'location', t - f, z0, index=2, interp='LINEAR')
        geo.keyp(b, 'location', t + f, z0 - depth, index=2, interp='LINEAR')
        if not latch:
            geo.keyp(b, 'location', t + hold, z0 - depth, index=2, interp='BEZIER')
            geo.keyp(b, 'location', t + hold + 4 * f, z0, index=2, interp='BEZIER')
        return self


def _hazard_mat():
    m, fresh = M.new_mat('killswitch.hazard')
    if not fresh:
        return m
    nt = m.node_tree
    b = M.principled(m)
    M.setin(b, 'Roughness', 0.4)
    tc = M.node(nt, 'ShaderNodeTexCoord', (-800, 0))
    sep = M.node(nt, 'ShaderNodeSeparateXYZ', (-650, 0))
    M.link(nt, M.sout(tc, 'Object'), M.sin(sep, 'Vector'))
    add = M.node(nt, 'ShaderNodeMath', (-500, 0), operation='ADD')
    M.link(nt, M.sout(sep, 'X'), add.inputs[0])
    M.link(nt, M.sout(sep, 'Z'), add.inputs[1])
    mul = M.node(nt, 'ShaderNodeMath', (-350, 0), operation='MULTIPLY')
    M.link(nt, add.outputs[0], mul.inputs[0])
    mul.inputs[1].default_value = 1.4
    fr = M.node(nt, 'ShaderNodeMath', (-200, 0), operation='FRACT')
    M.link(nt, mul.outputs[0], fr.inputs[0])
    gt = M.node(nt, 'ShaderNodeMath', (-50, 0), operation='GREATER_THAN')
    M.link(nt, fr.outputs[0], gt.inputs[0])
    gt.inputs[1].default_value = 0.5
    mx = M.node(nt, 'ShaderNodeMix', (150, 0), data_type='RGBA', blend_type='MIX')
    M.link(nt, gt.outputs[0], M.sin(mx, 'Factor', 'VALUE'))
    M.setin(mx, 'A', kit.srgb('#E8B923'), 'RGBA')
    M.setin(mx, 'B', kit.srgb('#141414'), 'RGBA')
    M.link(nt, M.sout(mx, 'Result', 'RGBA'), M.sin(b, 'Base Color'))
    return m


def build_killswitch(coll, loc=(58, -14, 0), yaw_deg=-20.0):
    root = geo.empty('killswitch', loc, coll, 3.0, 'ARROWS', rot=(0, 0, math.radians(yaw_deg)))
    ks = KillSwitch(root)
    yellow = M.enamel('killswitch.yellow', '#E3B21F', rough=0.35, coat=0.3)
    black = M.plastic('killswitch.black', '#18181A', rough=0.4)
    red = M.solid('killswitch.red', '#C8231C', rough=0.18, coat=0.8, coat_rough=0.04, sss=0.08,
                  sss_radius=(1.0, 0.2, 0.1))
    bx = geo.box('killswitch.box', (8.6, 8.6, 6.6), (0, 0, 0), bev=0.6, segments=4, m=yellow, coll=coll)
    geo.attach(bx, root, (0, 0, 3.3))
    hz = geo.box('killswitch.stripes', (7.0, 0.06, 1.3), (0, 0, 0), bev=0.02, segments=1, m=_hazard_mat(), coll=coll)
    geo.attach(hz, root, (0, -4.32, 1.3))
    for sx in (-1, 1):
        for sy in (-1, 1):
            scr = kit.cylinder(f'killswitch.screw{sx}{sy}', 0.28, 0.1, (0, 0, 0), verts=16, m=M.chrome(), coll=coll)
            geo.attach(scr, root, (sx * 3.4, sy * 3.4, 6.62))
    collar = geo.lathe('killswitch.collar', geo.rounded_profile([(2.2, 6.55), (3.2, 6.55), (3.2, 7.0), (2.9, 7.35),
                                                                (2.2, 7.35)], 0.12), segs=64, coll=coll, m=black)
    geo.attach(collar, root)
    btn = geo.empty('killswitch.button', (0, 0, 0), coll, 1.0)
    geo.attach(btn, root, (0, 0, 7.0))
    btn['z0'] = 7.0
    stem = geo.lathe('killswitch.stem', [(0.0, -0.8), (1.8, -0.8), (1.8, 0.5), (0.0, 0.5)], segs=32, coll=coll, m=black)
    geo.attach(stem, btn)
    mush = geo.lathe('killswitch.mushroom', geo.rounded_profile(
        [(0.0, 0.35), (3.3, 0.35), (3.45, 0.8), (3.2, 1.45), (2.2, 1.95), (0.0, 2.1)], 0.3, 4), segs=72, coll=coll, m=red)
    geo.attach(mush, btn)
    ks.button = btn
    # its cable runs off the back of the desk
    cpts = [(4.3, 1.0, 1.2), (6.5, 1.8, 0.3), (12, 3.5, 0.3), (19, 2.0, 0.3), (24.5, 1.0, 0.3), (26, 1.0, -3), (26.5, 1.0, -40)]
    cab = geo.curve_tube('killswitch.cable', cpts, 0.3, coll=coll, m=M.rubber('killswitch.rubber', '#1A1A1A'), kind='BEZIER',
                         res=10)
    geo.attach(cab, root)
    ks.top = Vector((0, 0, 9.1))
    return ks


# ------------------------------------------------------------------------------------------------ paperclip


def paperclip_points(length: float = 3.1):
    """Centre line of a Gem paperclip (x along its length, y across), scaled to `length` cm overall."""
    pts = []
    pts += [(0.9, -0.15), (2.2, -0.15)]
    pts += geo.arc_pts((2.2, 0.0), 0.15, -90, 90, 10)[1:]
    pts += [(0.45, 0.15)]
    pts += geo.arc_pts((0.45, -0.1), 0.25, 90, 270, 14)[1:]
    pts += [(2.65, -0.35)]
    pts += geo.arc_pts((2.65, 0.0), 0.35, -90, 90, 16)[1:]
    pts += [(1.0, 0.35)]
    xs = [p[0] for p in pts]
    s = length / ((max(xs) + 0.05) - (min(xs) - 0.05))
    x0 = (max(xs) + min(xs)) / 2
    return [((x - x0) * s, y * s, 0.0) for x, y in pts]


def build_paperclip(coll, name='clip', loc=(-4, -2, 0), yaw_deg=24.0, wire: float = 0.045):
    """The single paperclip lying flat on the desk: the fx library's hero clip (fx.clips.clip, lod 0) so it matches
    the avalanche; falls back to an own 3.1 cm mesh if pdoom.fx.clips is unavailable."""
    root = geo.empty(name, loc, coll, 1.0, 'ARROWS', rot=(0, 0, math.radians(yaw_deg)))
    p = Prop(root)
    o = None
    try:
        from ..fx import clips as fxclips
        o = fxclips.clip(f'{name}.wire', (0, 0, 0), rz=0.0, lod=0, coll=coll)
        geo.attach(o, root, (0, 0, fxclips.WIRE_R), (0, 0, 0))
        p.source = 'fx.clips'
    except Exception as e:  # pragma: no cover - fallback
        print(f'[sets] fx.clips unavailable ({e}); using the sets paperclip mesh')
        o = geo.curve_tube(f'{name}.wire', paperclip_points(), wire, coll=coll, m=M.steel('clip.steel'), kind='POLY',
                           bevel_res=3, to_mesh=True)
        geo.set_smooth(o, 70)
        geo.attach(o, root, (0, 0, wire))
        p.source = 'sets'
    p.mesh = o
    return p


# ------------------------------------------------------------------------------------------------ USB cable


class Cable(Prop):
    """The USB cable from the laptop to Clawd's spot. .pts (world polyline), at(u) / tangent(u) by arc length."""

    def __init__(self, root):
        super().__init__(root)
        self.pts = []
        self.lengths = []

    def _prep(self):
        self.lengths = [0.0]
        for i in range(1, len(self.pts)):
            self.lengths.append(self.lengths[-1] + (self.pts[i] - self.pts[i - 1]).length)

    @property
    def length(self):
        return self.lengths[-1] if self.lengths else 0.0

    def at(self, u: float) -> Vector:
        """World point at fraction u (0 = laptop end, 1 = Clawd end) of the cable's length."""
        s = max(0.0, min(1.0, u)) * self.length
        for i in range(1, len(self.pts)):
            if self.lengths[i] >= s:
                a = (s - self.lengths[i - 1]) / max(1e-9, self.lengths[i] - self.lengths[i - 1])
                return self.pts[i - 1].lerp(self.pts[i], a)
        return self.pts[-1].copy()

    def tangent(self, u: float) -> Vector:
        a, b = self.at(max(0, u - 0.01)), self.at(min(1, u + 0.01))
        return (b - a).normalized()


def _usbc_plug(coll, name, housing):
    metal = M.chrome('usb.metal')
    h = geo.box(f'{name}.housing', (0.75, 2.0, 0.55), (0, 0, 0), bev=0.2, segments=3, m=housing, coll=coll)
    tip = geo.box(f'{name}.tip', (0.62, 0.8, 0.25), (0, 0, 0), bev=0.1, segments=3, m=metal, coll=coll)
    tip.location = (0, 1.35, 0)
    boot = kit.cylinder(f'{name}.boot', 0.24, 0.9, (0, 0, 0), verts=16, m=housing, coll=coll)
    boot.rotation_euler = (math.radians(90), 0, 0)
    boot.location = (0, -1.3, 0)
    root = geo.empty(name, (0, 0, 0), coll, 0.5)
    for o in (h, tip, boot):
        geo.attach(o, root, o.location.copy(), o.rotation_euler.copy())
    return root


def build_cable(coll, start: Vector, end: Vector, via=None, *, radius=0.2, color='#EDEDED'):
    """A USB-C cable lying on the desk from `start` (a port, world) to `end` (world). via: extra world points."""
    root = geo.empty('cable', (0, 0, 0), coll, 1.0, 'ARROWS')
    cb = Cable(root)
    rub = M.solid('cable.rubber', color, rough=0.45, spec=0.4, micro=(10.0, 0.02))
    start, end = Vector(start), Vector(end)
    d = end - start
    ctrl = [start, start + Vector((2.2, 0, 0)), start + Vector((4.5, -1.5, radius - start.z))]
    if via:
        ctrl += [Vector(v) for v in via]
    else:
        mid = start.lerp(end, 0.55) + Vector((6.0, -3.0, 0))
        mid.z = radius
        ctrl += [mid]
    dirv = Vector((-0.9, 0.8, 0.0)).normalized()
    ctrl += [end + Vector((-6.4, 5.6, radius - end.z)), end + dirv * 4.6 + Vector((0, 0, -0.3)), end + dirv * 2.6, end]
    pts = geo.catmull(ctrl, 10)
    # keep it on the desk except near the ports
    for i, p in enumerate(pts):
        if 2 < i < len(pts) - 3:
            p.z = max(radius, p.z)
    cb.pts = [Vector(p) for p in pts]
    cb._prep()
    tube = geo.curve_tube('cable.wire', [tuple(p) for p in pts], radius, coll=coll, m=rub, kind='POLY', bevel_res=3)
    geo.attach(tube, root)
    for nm, u, flip in (('cable.plugA', 0.0, True), ('cable.plugB', 1.0, False)):
        pl = _usbc_plug(coll, nm, rub)
        tng = cb.tangent(u) * (-1 if flip else 1)
        pl.location = cb.at(u) - tng * 1.0
        pl.rotation_euler = tng.to_track_quat('Y', 'Z').to_euler()
        geo.attach(pl, root, pl.location.copy(), pl.rotation_euler.copy())
    cb.tube = tube
    return cb
