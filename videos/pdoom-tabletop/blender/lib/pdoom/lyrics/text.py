"""Fonts and glyph geometry for the in-picture lyrics.

Outline fonts (bundled in lyrics/fonts/, OFL or Apache) become per-character meshes; Hershey single-stroke fonts
become per-character polylines (for bent wire, neon tubes and chalk that draw on in pen order).

Conventions (every piece in the library): 1 unit = the font's CAP HEIGHT (an 'H' is 1 tall), baseline at z = 0,
the pen origin at x = 0, the glyph standing in the XZ plane and reading from -Y (its face points at -Y). Meshes are
cached by (font, char, extrude, bevel) and shared between every letter that uses them.
"""
from __future__ import annotations

import math
import os

import bpy
import bmesh
from mathutils import Matrix, Vector

HERE = os.path.dirname(os.path.abspath(__file__))
FONT_DIR = os.path.join(HERE, 'fonts')

# outline fonts: key -> file (licences in fonts/, see docs/lib/lyrics.md)
FONTS = {
    'slab': 'AlfaSlabOne-Regular.ttf',        # chunky slab serif: wooden blocks, brass, cardboard (OFL)
    'sans': 'Archivo-Bold.ttf',               # bold grotesk: tiles, labels (OFL)
    'cond': 'Archivo-CondensedBold.ttf',      # condensed: embossed tape (OFL)
    'type': 'CourierPrime-Bold.ttf',          # typewriter (OFL)
    'mono': 'IBMPlexMono-Medium.ttf',         # screen text (OFL)
    'marker': 'PermanentMarker-Regular.ttf',  # felt-tip marker handwriting (Apache 2.0)
    'stencil': 'StardosStencil-Bold.ttf',     # stencil serif: brass stencils (OFL)
}
# single-stroke (Hershey) fonts: key -> file
STROKES = {
    'line': 'hershey-futural.jhf',            # clean monoline sans: bent wire
    'roman': 'hershey-rowmans.jhf',           # monoline roman
    'script': 'hershey-scripts.jhf',          # joined script: neon signs, chalk
    'cursive': 'hershey-cursive.jhf',
}

_FONT_CACHE: dict[str, bpy.types.VectorFont] = {}


def alive(idb, coll) -> bool:
    """A cached datablock is still in this file (kit.new_scene starts a new file: old references die)."""
    try:
        return idb is not None and coll.get(idb.name) == idb
    except ReferenceError:
        return False
_METRICS: dict[str, dict] = {}
_ADV: dict[tuple, float] = {}
_MESH: dict[tuple, bpy.types.Mesh | None] = {}
_BOX: dict[tuple, tuple] = {}
_HERSHEY: dict[str, list] = {}


def font(key: str) -> bpy.types.VectorFont:
    f = _FONT_CACHE.get(key)
    if alive(f, bpy.data.fonts):
        return f
    path = os.path.join(FONT_DIR, FONTS.get(key, key))
    f = bpy.data.fonts.load(path, check_existing=True)
    _FONT_CACHE[key] = f
    return f


WORK = 'ly.work'


def work_scene():
    """A tiny scene for evaluating temporary text objects (fast: the real scene's depsgraph is never touched)."""
    ws = bpy.data.scenes.get(WORK)
    if ws is None:
        ws = bpy.data.scenes.new(WORK)
    return ws


def drop_work_scene():
    ws = bpy.data.scenes.get(WORK)
    if ws is not None:
        for o in list(ws.collection.objects):
            bpy.data.objects.remove(o, do_unlink=True)
        bpy.data.scenes.remove(ws)


def _eval(o):
    """(depsgraph, evaluated object) of a temp object in the work scene."""
    ws = work_scene()
    with bpy.context.temp_override(scene=ws, view_layer=ws.view_layers[0]):
        dg = bpy.context.evaluated_depsgraph_get()
    return dg, o.evaluated_get(dg)


def _tmp_text(body: str, key: str, *, extrude=0.0, bevel=0.0, bevel_res=2, res=5):
    cd = bpy.data.curves.new('ly.tmp', 'FONT')
    cd.body = body
    cd.font = font(key)
    cd.size = 1.0
    cd.align_x = 'LEFT'
    cd.align_y = 'TOP_BASELINE'
    cd.extrude = extrude
    cd.bevel_depth = bevel
    cd.bevel_resolution = bevel_res
    cd.resolution_u = res
    cd.fill_mode = 'BOTH'
    o = bpy.data.objects.new('ly.tmp', cd)
    work_scene().collection.objects.link(o)
    return o


def _drop(o):
    cd = o.data
    bpy.data.objects.remove(o, do_unlink=True)
    if cd.users == 0:
        bpy.data.curves.remove(cd)


def _xbox(body: str, key: str):
    o = _tmp_text(body, key)
    dg, oe = _eval(o)
    xs = [v[0] for v in oe.bound_box]
    ys = [v[1] for v in oe.bound_box]
    _drop(o)
    return min(xs), max(xs), min(ys), max(ys)


def metrics(key: str) -> dict:
    """{'cap': cap height, 'xh': x-height} in Blender text units at size 1 (the library divides by 'cap')."""
    m = _METRICS.get(key)
    if m is None:
        H = _xbox('H', key)
        x = _xbox('x', key)
        m = {'cap': H[3] - H[2], 'xh': x[3] - x[2]}
        _METRICS[key] = m
    return m


def advance(key: str, ch: str) -> float:
    """Pen advance of a character in cap units (measured from Blender's own layout: 'cI' minus 'I')."""
    k = (key, ch)
    if k not in _ADV:
        cap = metrics(key)['cap']
        _ADV[k] = (_xbox(ch + 'I', key)[1] - _xbox('I', key)[1]) / cap
    return _ADV[k]


STAND = Matrix.Rotation(math.radians(90), 4, 'X')   # glyph plane XY (faces +Z) -> XZ (faces -Y)


def glyph_mesh(key: str, ch: str, *, extrude: float = 0.0, bevel: float = 0.0, bevel_res: int = 2,
               res: int = 5) -> bpy.types.Mesh | None:
    """A character as a mesh in cap units, standing in XZ and facing -Y (extrude and bevel in cap units too; the
    solid spans y = -extrude-bevel .. +extrude+bevel). None for a blank character."""
    k = (key, ch, round(extrude, 4), round(bevel, 4), bevel_res, res)
    if k in _MESH:
        me = _MESH[k]
        if me is None or alive(me, bpy.data.meshes):
            return me
    if ch.isspace():
        _MESH[k] = None
        return None
    cap = metrics(key)['cap']
    o = _tmp_text(ch, key, extrude=extrude * cap, bevel=bevel * cap, bevel_res=bevel_res, res=res)
    dg, oe = _eval(o)
    me = bpy.data.meshes.new_from_object(oe)
    _drop(o)
    if len(me.vertices) == 0:
        bpy.data.meshes.remove(me)
        _MESH[k] = None
        return None
    me.transform(STAND @ Matrix.Scale(1.0 / cap, 4))
    me.name = f'ly.g.{key}.{ord(ch)}.{k[2]}.{k[3]}'
    me.materials.clear()
    _MESH[k] = me
    return me


def glyph_box(key: str, ch: str) -> tuple[float, float, float, float]:
    """Ink box (x0, x1, z0, z1) of a character in cap units (from its flat mesh)."""
    k = (key, ch)
    if k not in _BOX:
        me = glyph_mesh(key, ch)
        if me is None:
            _BOX[k] = (0.0, advance(key, ch), 0.0, 0.0)
        else:
            xs = [v.co.x for v in me.vertices]
            zs = [v.co.z for v in me.vertices]
            _BOX[k] = (min(xs), max(xs), min(zs), max(zs))
    return _BOX[k]


def outline_splines(key: str, ch: str) -> list[list[tuple[float, float]]]:
    """A character's outlines as closed polygons in cap units (x right, y up; pen origin, baseline 0), for stencil
    plates (a rectangle with the letter cut out)."""
    cap = metrics(key)['cap']
    o = _tmp_text(ch, key, res=6)
    dg, oe = _eval(o)
    cu = oe.to_curve(dg)
    polys = []
    for sp in cu.splines:
        pts = []
        if sp.type == 'BEZIER':
            bps = list(sp.bezier_points)
            n = len(bps)
            for i in range(n):
                a, b = bps[i], bps[(i + 1) % n]
                p0, p1, p2, p3 = a.co, a.handle_right, b.handle_left, b.co
                for s in range(8):
                    t = s / 8
                    q = ((1 - t) ** 3) * p0 + 3 * ((1 - t) ** 2) * t * p1 + 3 * (1 - t) * t * t * p2 + t ** 3 * p3
                    pts.append((q.x / cap, q.y / cap))
        else:
            pts = [(p.co.x / cap, p.co.y / cap) for p in sp.points]
        if len(pts) >= 3:
            polys.append(pts)
    oe.to_curve_clear()
    _drop(o)
    return polys


# ------------------------------------------------------------------------------------------------ Hershey strokes


def _parse_jhf(path: str) -> list:
    s = open(path, encoding='ascii').read().replace('\r', '').replace('\n', '')
    i = 0
    glyphs = []
    while i + 8 <= len(s):
        n = int(s[i + 5:i + 8])
        i += 8
        data = s[i:i + 2 * n]
        i += 2 * n
        left, right = ord(data[0]) - 82, ord(data[1]) - 82
        strokes, cur = [], []
        for k in range(1, n):
            a, b = data[2 * k], data[2 * k + 1]
            if a == ' ' and b == 'R':
                if cur:
                    strokes.append(cur)
                cur = []
                continue
            cur.append((ord(a) - 82, ord(b) - 82))
        if cur:
            strokes.append(cur)
        glyphs.append((left, right, strokes))
    return glyphs


HERSHEY_CAP = 21.0      # Hershey units from cap top (y -12) to baseline (y 9)
HERSHEY_BASE = 9.0


def strokes(key: str, ch: str) -> tuple[list[list[tuple[float, float]]], float]:
    """(polylines, advance) of a character of a single-stroke font, in cap units: x from the pen origin, y up from
    the baseline. Strokes come in the pen order of the original plotter font (draw-on animations follow it)."""
    g = _HERSHEY.get(key)
    if g is None:
        g = _parse_jhf(os.path.join(FONT_DIR, STROKES.get(key, key)))
        _HERSHEY[key] = g
    c = ord(ch) - 32
    if c < 0 or c >= len(g):
        c = ord('?') - 32
    left, right, st = g[c]
    out = [[((x - left) / HERSHEY_CAP, (HERSHEY_BASE - y) / HERSHEY_CAP) for x, y in s] for s in st]
    return out, (right - left) / HERSHEY_CAP


def stroke_length(polys) -> float:
    L = 0.0
    for p in polys:
        for a, b in zip(p, p[1:]):
            L += math.hypot(b[0] - a[0], b[1] - a[1])
    return L


def smooth_polyline(pts, *, corner_deg: float = 65.0, sub: int = 4):
    """Catmull-Rom smoothing of a Hershey polyline that keeps sharp corners (angle > corner_deg) sharp."""
    if len(pts) < 3:
        return pts
    # split at corners
    segs, cur = [], [pts[0]]
    for i in range(1, len(pts) - 1):
        cur.append(pts[i])
        a = Vector((pts[i][0] - pts[i - 1][0], pts[i][1] - pts[i - 1][1]))
        b = Vector((pts[i + 1][0] - pts[i][0], pts[i + 1][1] - pts[i][1]))
        if a.length > 1e-9 and b.length > 1e-9 and math.degrees(a.angle(b)) > corner_deg:
            segs.append(cur)
            cur = [pts[i]]
    cur.append(pts[-1])
    segs.append(cur)
    out = []
    for s in segs:
        if len(s) < 3:
            q = s
        else:
            P = [s[0]] + s + [s[-1]]
            q = []
            for i in range(1, len(P) - 2):
                p0, p1, p2, p3 = (Vector(P[i - 1]), Vector(P[i]), Vector(P[i + 1]), Vector(P[i + 2]))
                for k in range(sub):
                    t = k / sub
                    t2, t3 = t * t, t * t * t
                    v = 0.5 * ((2 * p1) + (-p0 + p2) * t + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t2
                               + (-p0 + 3 * p1 - 3 * p2 + p3) * t3)
                    q.append((v.x, v.y))
            q.append(s[-1])
        if out and q and (abs(out[-1][0] - q[0][0]) < 1e-9 and abs(out[-1][1] - q[0][1]) < 1e-9):
            q = q[1:]
        out += q
    return out


# ------------------------------------------------------------------------------------------------ layout


def layout(text: str, key: str, *, tracking: float = 0.0, mono: float | None = None, space: float | None = None,
           strokes_font: bool = False) -> tuple[list[tuple[str, float, float]], float]:
    """Pen layout of a string: ([(ch, x, width)], total width) in cap units.

    mono: a fixed cell width (blocks, tiles) instead of the font's advances. tracking: extra space per letter.
    space: the width of a space (default: the font's)."""
    out = []
    x = 0.0
    for ch in text:
        if mono is not None:
            w = mono
        elif strokes_font:
            w = strokes(key, ch)[1]
        else:
            w = advance(key, ch)
        if ch == ' ' and space is not None:
            w = space
        out.append((ch, x, w))
        x += w + tracking
    return out, max(0.0, x - tracking)


def ensure_uv_box(me: bpy.types.Mesh, scale: float = 1.0):
    """Box-projected UVs (1 UV unit = 1 mesh unit * scale) so texture materials read on glyph meshes."""
    if me.uv_layers:
        return me
    bm = bmesh.new()
    bm.from_mesh(me)
    uv = bm.loops.layers.uv.new('UVMap')
    for f in bm.faces:
        n = f.normal
        ax = max(range(3), key=lambda i: abs(n[i]))
        for lp in f.loops:
            co = lp.vert.co
            if ax == 0:
                lp[uv].uv = (co.y * scale, co.z * scale)
            elif ax == 1:
                lp[uv].uv = (co.x * scale, co.z * scale)
            else:
                lp[uv].uv = (co.x * scale, co.y * scale)
    bm.to_mesh(me)
    bm.free()
    return me
