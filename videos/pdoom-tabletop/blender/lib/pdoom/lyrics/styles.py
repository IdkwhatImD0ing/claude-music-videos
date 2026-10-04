"""Letter styles: what one letter is made of, how it is laid out, and its default reveal and exit.

Every piece is built in units with its base at z = 0, its back on the row plane (y = 0) and its face toward -Y
(the viewer), so the same row can stand on the desk, lie flat on a page, sit on the laptop screen or ride the lens.

| style     | letter                                           | reveal (default) | exit     |
|-----------|--------------------------------------------------|------------------|----------|
| blocks    | painted wooden ABC block, raised cream letter     | pop              | drop     |
| glow      | smoked acrylic block, letter lit from inside      | light (preview)  | fade     |
| tiles     | ivory letter tile with its score (lies flat)      | flip (preview)   | sweep    |
| brass     | cast brass letter (slab serif)                    | slam             | topple   |
| cardboard | letter cut from corrugated cardboard              | tumble           | topple   |
| stencil   | brass stencil plate with the letter cut out       | slide            | sweep    |
| stamp     | rubber-stamped ink on paper                      | stamp            | none     |
| typed     | typewriter ink on a paper strip                   | type             | none     |
| screen    | glowing monospace text (laptop screen)            | type (dim preview) | fade   |
| marker    | felt-tip handwriting on sticky notes              | draw             | none     |
| chalk     | chalk script on a slate (single-stroke font)      | draw             | fade     |
| wire      | bent steel wire (paperclip wire, single stroke)   | grow             | topple   |
| neon      | neon tube script, unlit glass until sung          | light (preview)  | fade     |
| tape      | embossed label tape, raised white letters         | type             | none     |
| fog       | letters wiped in a fogged pane                    | draw             | fade     |
| goldleaf  | gilded sign-writing on glass (lens panes)         | draw             | fade     |
"""
from __future__ import annotations

import bpy
import bmesh
from mathutils import Matrix, Vector

from .. import kit
from . import mats as LM
from . import text as T

SCORES = {c: s for s, cs in ((1, 'AEILNORSTU'), (2, 'DG'), (3, 'BCMP'), (4, 'FHVWY'), (5, 'K'), (8, 'JX'), (10, 'QZ'))
          for c in cs}

_MESHES: dict[tuple, bpy.types.Mesh] = {}


def _cached(key):
    me = _MESHES.get(key)
    if T.alive(me, bpy.data.meshes):
        return me
    return None


def _add_mesh(bm, me, M=Matrix.Identity(4), mat_index=0):
    """Append a mesh's geometry to a bmesh, transformed, with a material index."""
    if me is None:
        return
    old = set(bm.faces)            # (bmesh reuses freed slots: new faces are not simply appended)
    tmp = me.copy()
    tmp.transform(M)
    bm.from_mesh(tmp)
    bpy.data.meshes.remove(tmp)
    for f in bm.faces:
        if f not in old:
            f.material_index = mat_index
            f.smooth = False


def _rounded_box(bm, size, center, bevel, segments=3, mat_index=0):
    old = set(bm.faces)
    res = bmesh.ops.create_cube(bm, size=1.0)
    vs = res['verts']
    for v in vs:
        v.co = Vector((v.co.x * size[0] + center[0], v.co.y * size[1] + center[1], v.co.z * size[2] + center[2]))
    edges = list({e for v in vs for e in v.link_edges})
    if bevel > 0:
        bmesh.ops.bevel(bm, geom=edges, offset=bevel, offset_type='OFFSET', segments=segments, profile=0.5,
                        affect='EDGES', clamp_overlap=True)
    for f in bm.faces:
        if f not in old:
            f.material_index = mat_index
            f.smooth = True


def _finish(bm, name, mats):
    me = bpy.data.meshes.new(name)
    bm.normal_update()
    bm.to_mesh(me)
    bm.free()
    for m in mats:
        me.materials.append(m)
    return me


def _center_glyph(font, ch, cap, zc):
    """Matrix that scales a glyph to cap height `cap` and centres its ink box at x = 0, z = zc."""
    x0, x1, z0, z1 = T.glyph_box(font, ch)
    s = cap
    return Matrix.Translation((-(x0 + x1) * 0.5 * s, 0, zc - (z0 + z1) * 0.5 * s)) @ Matrix.Scale(s, 4)


# ------------------------------------------------------------------------------------------------ piece meshes


def block_mesh(ch: str, *, font='slab', width=1.0, cap=0.68, relief=0.045, bevel=0.075, letter_mat=None,
               body_mat=None):
    """A painted wooden block (1 tall, `width` wide, 1 deep; back at y = 0) with the letter raised on its face."""
    key = ('block', ch, font, round(width, 3), round(cap, 3), letter_mat.name if letter_mat else '',
           body_mat.name if body_mat else '')
    me = _cached(key)
    if me:
        return me
    bm = bmesh.new()
    _rounded_box(bm, (width, 1.0, 1.0), (0, -0.5, 0.5), bevel, 3, 0)
    g = T.glyph_mesh(font, ch, extrude=relief / cap / 2, bevel=0.0)
    if g is not None:
        # glyph solid spans y +-relief/2 (at scale cap): sink its back into the face
        c = cap if ch.isalnum() else cap * 0.9
        M = Matrix.Translation((0, -1.0 - relief * 0.5 + 0.01, 0)) @ _center_glyph(font, ch, c, 0.5)
        _add_mesh(bm, g, M, 1)
    me = _finish(bm, f'ly.block.{ord(ch)}.{font}', [body_mat or LM.paint_body(), letter_mat or LM.paint(LM.CREAM)])
    _MESHES[key] = me
    return me


def tile_mesh(ch: str, *, font='sans', width=1.0, height=1.08, thick=0.22, cap=0.5):
    """An ivory letter tile (standing: face toward -Y, back at y = 0) with the letter and its score engraved."""
    key = ('tile', ch, font, width, height, thick, cap)
    me = _cached(key)
    if me:
        return me
    bm = bmesh.new()
    _rounded_box(bm, (width, thick, height), (0, -thick / 2, height / 2), 0.05, 2, 0)
    g = T.glyph_mesh(font, ch)
    if g is not None:
        M = Matrix.Translation((0, -thick - 0.004, 0)) @ _center_glyph(font, ch, cap, height * 0.54)
        _add_mesh(bm, g, M, 1)
    sc = SCORES.get(ch.upper())
    if sc:
        for k, d in enumerate(str(sc)[::-1]):
            gd = T.glyph_mesh(font, d)
            if gd is not None:
                M = Matrix.Translation((0, -thick - 0.004, 0)) @ \
                    Matrix.Translation((width * 0.36 - k * 0.1, 0, 0)) @ _center_glyph(font, d, 0.16, height * 0.16)
                _add_mesh(bm, gd, M, 1)
    me = _finish(bm, f'ly.tile.{ord(ch)}', [LM.ivory(), LM.engrave()])
    _MESHES[key] = me
    return me


def glyph_piece_mesh(ch: str, *, font='slab', depth=0.25, bevel=0.03, name='glyph', mats=()):
    """A solid letter (cap height 1, `depth` thick), centred on x, base at z = 0, back at y = 0."""
    key = ('glyph', ch, font, round(depth, 3), round(bevel, 3), tuple(m.name for m in mats))
    me = _cached(key)
    if me:
        return me
    g = T.glyph_mesh(font, ch, extrude=max(depth / 2 - bevel, 0.001), bevel=bevel, bevel_res=2)
    if g is None:
        return None
    bm = bmesh.new()
    x0, x1, z0, z1 = T.glyph_box(font, ch)
    M = Matrix.Translation((-(x0 + x1) * 0.5, -depth / 2, 0))
    _add_mesh(bm, g, M, 0)
    for f in bm.faces:
        f.smooth = False
    me = _finish(bm, f'ly.{name}.{ord(ch)}', list(mats))
    T.ensure_uv_box(me, 1.0)
    _MESHES[key] = me
    return me


def decal_mesh(ch: str, *, font='slab', lift=0.004, name='decal', mats=()):
    """A flat letter (cap height 1) just in front of the row plane: ink, chalk, screen text, fog windows."""
    key = ('decal', ch, font, lift, tuple(m.name for m in mats))
    me = _cached(key)
    if me:
        return me
    g = T.glyph_mesh(font, ch)
    if g is None:
        return None
    bm = bmesh.new()
    x0, x1, z0, z1 = T.glyph_box(font, ch)
    _add_mesh(bm, g, Matrix.Translation((-(x0 + x1) * 0.5, -lift, 0)), 0)
    me = _finish(bm, f'ly.{name}.{ord(ch)}', list(mats))
    _MESHES[key] = me
    return me


def stencil_mesh(ch: str, *, font='stencil', thick=0.05, pad=0.12, height=1.5):
    """A brass stencil plate with the letter cut out (curve fill with the glyph outlines as holes)."""
    key = ('stencil', ch, font, thick, pad, height)
    me = _cached(key)
    if me:
        return me
    polys = T.outline_splines(font, ch) if not ch.isspace() else []
    x0, x1, z0, z1 = T.glyph_box(font, ch) if polys else (0, T.advance(font, ch), 0, 1)
    cx = (x0 + x1) * 0.5
    w = max(x1 - x0, 0.3) + 2 * pad
    cd = bpy.data.curves.new('ly.tmp.stencil', 'CURVE')
    cd.dimensions = '2D'
    cd.fill_mode = 'BOTH'
    try:
        cd.fill_rule = 'EVEN_ODD'
    except Exception:
        pass
    cd.extrude = thick / 2
    zb = -0.25
    rect = [(-w / 2, zb), (w / 2, zb), (w / 2, zb + height), (-w / 2, zb + height)]
    for poly in [rect] + [[(x - cx, y) for x, y in p] for p in polys]:
        sp = cd.splines.new('POLY')
        sp.points.add(len(poly) - 1)
        for i, (x, y) in enumerate(poly):
            sp.points[i].co = (x, y, 0, 1)
        sp.use_cyclic_u = True
    o = bpy.data.objects.new('ly.tmp.stencil', cd)
    T.work_scene().collection.objects.link(o)
    dg, oe = T._eval(o)
    me = bpy.data.meshes.new_from_object(oe)
    bpy.data.objects.remove(o, do_unlink=True)
    bpy.data.curves.remove(cd)
    me.transform(Matrix.Translation((0, -thick / 2, 0)) @ T.STAND)
    me.name = f'ly.stencil.{ord(ch)}'
    me.materials.append(LM.brass())
    _MESHES[key] = me
    return me


def stroke_curve(name: str, ch: str, *, font='line', radius=0.04, res=3, flat=False, mat=None, smooth=True):
    """A single-stroke letter as a curve object (its own data: the draw-on keys its bevel factor). Returns
    (object, curve data, advance). The tube's centre line is at y = -radius (it rests on the row plane)."""
    polys, adv = T.strokes(font, ch)
    cd = bpy.data.curves.new(name, 'CURVE')
    cd.dimensions = '3D'
    cd.bevel_mode = 'ROUND'
    cd.bevel_depth = radius
    cd.bevel_resolution = res
    cd.resolution_u = 4
    cd.use_fill_caps = True
    cd.bevel_factor_mapping_start = 'SPLINE'
    cd.bevel_factor_mapping_end = 'SPLINE'
    for p in polys:
        pts = T.smooth_polyline(p) if smooth else p
        if len(pts) < 2:
            continue
        sp = cd.splines.new('POLY')
        sp.points.add(len(pts) - 1)
        for i, (x, y) in enumerate(pts):
            sp.points[i].co = (x, -radius, y, 1.0)
    o = bpy.data.objects.new(name, cd)
    if mat is not None:
        cd.materials.append(mat)
    return o, cd, adv, polys


# ------------------------------------------------------------------------------------------------ styles


class Style:
    """Base style. Subclasses set the class attributes and implement piece()."""
    name = 'base'
    font = 'slab'
    case = 'upper'
    punct = 'minimal'
    mono = None             # fixed cell width (units) or None for the font's advances
    gap = 0.0               # extra space between letters (units)
    space = 0.5             # word gap (units)
    height = 1.0            # a letter's height in units (row spacing uses it)
    depth = 1.0             # how far a piece sticks out toward the viewer (units)
    reveal = 'pop'
    exit = 'drop'
    flat = False            # lies flat by default (tiles on the desk, ink on a page)
    preview = None          # unsung state: None (hidden) | 'blank' (face down) | 'dim' (unlit)
    size = 1.2              # default cm per unit for explicit placements
    support = None          # default support: None | 'stand' | 'paper' | 'strip' | 'slate' | 'panel' | 'notes' ...
    descent = 0.0           # how far descenders reach below the baseline (units): rows sit this much higher
    leading = 0.45          # extra space between rows (units)
    stack = False           # solid standing pieces: several rows get a little shelf unit to stand on
    tex = ''

    def __init__(self, **opts):
        self.opts = opts
        for k, v in opts.items():
            if hasattr(self, k) and not callable(getattr(self, k)):
                setattr(self, k, v)

    def cell(self, ch):
        if self.mono is not None:
            return self.mono if (ch.isalnum() or ch == ' ') else self.mono * 0.5
        return T.advance(self.font, ch)

    def piece(self, ch, name, coll, word):
        """-> (object or None, dict(w=, h=, d=, curve=, extra=[]))"""
        raise NotImplementedError

    def link(self, o, coll):
        coll.objects.link(o)
        return o


class Blocks(Style):
    name = 'blocks'
    stack = True
    font = 'slab'
    mono = 1.06
    space = 0.5
    reveal = 'pop'
    exit = 'drop'
    size = 1.2
    colors = LM.PAINT

    def piece(self, ch, name, coll, word):
        if ch == ' ':
            return None, {}
        w = 1.0 if ch.isalnum() else 0.5
        me = block_mesh(ch, font=self.font, width=w)
        o = self.link(bpy.data.objects.new(name, me), coll)
        cols = self.opts.get('color') or self.colors
        if isinstance(cols, str):
            cols = [cols]
        col = cols[(word.line * 3 + word.index) % len(cols)]
        o.color = kit.srgb(col)
        return o, dict(w=w, h=1.0, d=1.0)


class Glow(Blocks):
    """Light-up blocks: dark smoked acrylic with the letter glowing inside when sung (A-G-I)."""
    name = 'glow'
    reveal = 'light'
    exit = 'fade'
    preview = 'dim'
    glow_color = LM.GLOW
    light = 700.0           # W (per cm^2 of block) of a small point light in front of each lit block (0: none)

    def piece(self, ch, name, coll, word):
        if ch == ' ':
            return None, {}
        w = 1.0 if ch.isalnum() else 0.5
        col = self.opts.get('glow_color', self.glow_color)
        me = block_mesh(ch, font=self.font, width=w, relief=0.02, letter_mat=LM.glow_letter(col, 4.0),
                        body_mat=LM.acrylic())
        o = self.link(bpy.data.objects.new(name, me), coll)
        extra = []
        if self.opts.get('light', self.light):
            ld = bpy.data.lights.new(name + '.light', 'POINT')
            ld.energy = 0.0
            ld.color = kit.srgb(col)[:3]
            ld.shadow_soft_size = 0.3
            lo = bpy.data.objects.new(name + '.light', ld)
            coll.objects.link(lo)
            lo.parent = o
            lo.location = (0, -1.6, 0.5)
            lo['ly_on'] = 0.0
            extra.append(lo)
        return o, dict(w=w, h=1.0, d=1.0, extra=extra, light=self.opts.get('light', self.light))


class Tiles(Style):
    name = 'tiles'
    stack = True
    font = 'sans'
    mono = 1.08
    space = 0.55
    height = 1.08
    depth = 0.22
    reveal = 'flip'
    exit = 'sweep'
    flat = True
    preview = 'blank'
    size = 1.6

    def piece(self, ch, name, coll, word):
        if not ch.isalnum():
            return None, {}
        me = tile_mesh(ch.upper())
        o = self.link(bpy.data.objects.new(name, me), coll)
        return o, dict(w=1.0, h=1.08, d=0.22)

    def cell(self, ch):
        return self.mono if ch.isalnum() or ch == ' ' else 0.0


class Brass(Style):
    name = 'brass'
    stack = True
    font = 'slab'
    gap = 0.06
    space = 0.38
    depth = 0.3
    reveal = 'slam'
    exit = 'topple'
    size = 2.4

    def piece(self, ch, name, coll, word):
        me = glyph_piece_mesh(ch, font=self.font, depth=self.depth, bevel=0.035, name='brass', mats=(LM.brass(),))
        if me is None:
            return None, {}
        o = self.link(bpy.data.objects.new(name, me), coll)
        x0, x1, z0, z1 = T.glyph_box(self.font, ch)
        return o, dict(w=x1 - x0, h=1.0, d=self.depth)


class Cardboard(Brass):
    name = 'cardboard'
    font = 'slab'
    depth = 0.14
    gap = 0.1
    reveal = 'tumble'
    exit = 'topple'
    size = 2.0

    def piece(self, ch, name, coll, word):
        me = glyph_piece_mesh(ch, font=self.font, depth=self.depth, bevel=0.0, name='card', mats=(LM.cardboard(),))
        if me is None:
            return None, {}
        o = self.link(bpy.data.objects.new(name, me), coll)
        x0, x1, z0, z1 = T.glyph_box(self.font, ch)
        return o, dict(w=x1 - x0, h=1.0, d=self.depth, jitter=3.5)


class Stencil(Style):
    name = 'stencil'
    stack = True
    font = 'stencil'
    gap = -0.02
    space = 0.5
    depth = 0.05
    reveal = 'slide'
    exit = 'sweep'
    size = 1.6

    def cell(self, ch):
        if ch == ' ':
            return self.space
        x0, x1, _, _ = T.glyph_box(self.font, ch)
        return max(x1 - x0, 0.3) + 0.24

    def piece(self, ch, name, coll, word):
        if ch == ' ':
            return None, {}
        me = stencil_mesh(ch, font=self.font)
        o = self.link(bpy.data.objects.new(name, me), coll)
        return o, dict(w=self.cell(ch), h=1.5, d=0.05)


class Decal(Style):
    """Flat letters on a surface (ink, marker, chalk, screen text, fog windows, gold leaf)."""
    name = 'decal'
    font = 'slab'
    case = None
    depth = 0.0
    flat = True
    descent = 0.3
    material = None

    def mat(self):
        return LM.ink()

    def piece(self, ch, name, coll, word):
        me = decal_mesh(ch, font=self.font, name=self.name, mats=(self.mat(),))
        if me is None:
            return None, {}
        o = self.link(bpy.data.objects.new(name, me), coll)
        x0, x1, z0, z1 = T.glyph_box(self.font, ch)
        return o, dict(w=x1 - x0, h=1.0, d=0.0)


class Stamp(Decal):
    name = 'stamp'
    font = 'slab'
    case = 'upper'
    descent = 0.0
    gap = 0.04
    space = 0.45
    reveal = 'stamp'
    exit = 'none'
    size = 0.9
    support = 'paper'
    ink = '#B3261E'

    def mat(self):
        return LM.ink(self.opts.get('ink', self.ink))


class Typed(Decal):
    name = 'typed'
    font = 'type'
    case = None
    punct = 'keep'
    reveal = 'type'
    exit = 'none'
    size = 0.55
    support = 'strip'

    def mat(self):
        return LM.ink('#23201C', name='ly.typeink', speckle=0.22)


class Screen(Decal):
    name = 'screen'
    font = 'mono'
    case = None
    punct = 'keep'
    reveal = 'type'
    exit = 'fade'
    preview = 'dim'
    size = 0.9
    support = 'panel'
    color = '#9CF0B0'

    def mat(self):
        return LM.screen_text(self.opts.get('color', self.color), self.opts.get('strength', 4.0))


class Marker(Decal):
    name = 'marker'
    font = 'marker'
    case = None
    gap = 0.02
    space = 1.05            # one sticky note per word, with a gap between notes
    reveal = 'draw'
    exit = 'none'
    size = 0.7
    support = 'notes'
    ink = LM.INK

    def mat(self):
        return LM.marker(self.opts.get('ink', self.ink))


class Fog(Decal):
    """Letters wiped in a fogged pane: clear-glass letters over a frosted pane (EEVEE refraction shows the world
    sharp through them). Put them on real glass (the snow globe, the jar, the window) or on the style's pane."""
    name = 'fog'
    font = 'marker'
    case = None
    reveal = 'draw'
    exit = 'fade'
    size = 1.2
    support = 'pane'

    def mat(self):
        return fog_letter()


class GoldLeaf(Decal):
    name = 'goldleaf'
    font = 'slab'
    case = None
    gap = 0.04
    reveal = 'draw'
    exit = 'fade'
    size = 0.8
    support = 'glass'

    def mat(self):
        return goldleaf()


class Strokes(Style):
    """Single-stroke letters as tubes (wire, neon, chalk)."""
    name = 'strokes'
    font = 'line'
    case = None
    punct = 'minimal'
    radius = 0.045
    descent = 0.36
    reveal = 'grow'
    exit = 'topple'
    size = 2.0

    def cell(self, ch):
        return T.strokes(self.font, ch)[1] * self.opts.get('tracking', 1.0)

    def mat(self):
        return LM.steel()

    def piece(self, ch, name, coll, word):
        if ch == ' ':
            return None, {}
        o, cd, adv, polys = stroke_curve(name, ch, font=self.font, radius=self.opts.get('radius', self.radius),
                                         mat=self.mat())
        if not cd.splines:
            bpy.data.objects.remove(o)
            bpy.data.curves.remove(cd)
            return None, {}
        coll.objects.link(o)
        # centre the letter on its cell (curves have no mesh to re-centre: offset the points)
        for sp in cd.splines:
            for p in sp.points:
                p.co.x -= adv / 2
        return o, dict(w=adv, h=1.0, d=2 * self.radius, curve=cd)


class Wire(Strokes):
    name = 'wire'
    font = 'line'
    radius = 0.03
    reveal = 'grow'
    exit = 'topple'
    size = 3.0


class Neon(Strokes):
    name = 'neon'
    font = 'script'
    radius = 0.05
    descent = 0.58
    reveal = 'light'
    exit = 'fade'
    preview = 'dim'
    size = 2.4
    color = '#FF4F7A'
    support = 'backing'

    def mat(self):
        return LM.neon(self.opts.get('color', self.color), self.opts.get('strength', 9.0))


class Chalk(Strokes):
    name = 'chalk'
    font = 'script'
    radius = 0.045
    descent = 0.58
    reveal = 'draw'
    exit = 'fade'
    size = 1.4
    support = 'slate'

    def mat(self):
        return LM.chalk()


class Tape(Style):
    """Embossing tape: a glossy strip per word with raised white capitals punched one by one."""
    name = 'tape'
    font = 'cond'
    case = 'upper'
    gap = 0.12
    space = 0.9
    depth = 0.03
    reveal = 'type'
    exit = 'none'
    flat = True
    size = 0.5
    support = 'tape'
    color = '#1F1F24'

    def piece(self, ch, name, coll, word):
        me = glyph_piece_mesh(ch, font=self.font, depth=0.05, bevel=0.012, name='tapeletter',
                              mats=(LM.tape_letter(),))
        if me is None:
            return None, {}
        o = self.link(bpy.data.objects.new(name, me), coll)
        x0, x1, z0, z1 = T.glyph_box(self.font, ch)
        return o, dict(w=x1 - x0, h=1.0, d=0.05)


STYLES = {c.name: c for c in (Blocks, Glow, Tiles, Brass, Cardboard, Stencil, Stamp, Typed, Screen, Marker, Fog,
                              GoldLeaf, Wire, Neon, Chalk, Tape)}


def get(style, **opts) -> Style:
    if isinstance(style, Style):
        return style
    if isinstance(style, type) and issubclass(style, Style):
        return style(**opts)
    if style not in STYLES:
        raise KeyError(f'unknown lyric style {style!r}; one of {sorted(STYLES)}')
    return STYLES[style](**opts)


# ------------------------------------------------------------------------------------------------ special materials


def fog_letter():
    """Clear where wiped (ly_wipe runs across the letter), frosted like the pane where not yet."""
    m, fresh = LM._get('ly.fogletter')
    if not fresh:
        return m
    from ..sets import materials as M
    nt = m.node_tree
    b = M.principled(m)
    M.setin(b, 'Base Color', (1, 1, 1, 1))
    M.setin(b, 'Transmission Weight', 1.0)
    M.setin(b, 'IOR', 1.45)
    M.setin(b, 'Thin Wall', True)
    mask = LM.wipe_mask(nt, soft=0.12)
    rough = LM.math(nt, 'MULTIPLY_ADD', mask, -0.42, (-200, -300), c=0.42)
    nt.links.new(rough, b.inputs['Roughness'])
    M.glassify(m)
    return m


def goldleaf():
    m, fresh = LM._get('ly.goldleaf')
    if not fresh:
        return m
    from ..sets import materials as M
    nt = m.node_tree
    b = M.principled(m)
    M.setin(b, 'Base Color', kit.srgb('#E8BE62'))
    M.setin(b, 'Metallic', 1.0)
    M.setin(b, 'Roughness', 0.3)
    M.setin(b, 'Emission Color', kit.srgb('#FFC766'))
    M.setin(b, 'Emission Strength', 0.35)    # gilding catches the room: keep it legible against a bright blur
    LM._alpha(m, LM.wipe_mask(nt, soft=0.1), LM.attr(nt, 'ly_fade', (-900, -900)))
    return m
