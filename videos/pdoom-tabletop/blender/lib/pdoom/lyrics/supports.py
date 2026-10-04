"""Things the letters stand or lie on: the lyric stand (shelves on legs), a paper card, a typewriter strip, a
terminal panel, sticky notes, a slate, a frosted pane, a glass pane, a neon backing board, embossing tape, and
threads to hang letters from. All built in row units, parented to the row root (or the stage root)."""
from __future__ import annotations

import math

import bpy
import bmesh
from mathutils import Matrix, Vector

from . import mats as LM


def _box(name, coll, size, center, mat, bevel=0.0, seg=2, parent=None):
    bm = bmesh.new()
    res = bmesh.ops.create_cube(bm, size=1.0)
    for v in res['verts']:
        v.co = Vector((v.co.x * size[0] + center[0], v.co.y * size[1] + center[1], v.co.z * size[2] + center[2]))
    if bevel > 0:
        bmesh.ops.bevel(bm, geom=list(bm.edges), offset=bevel, offset_type='OFFSET', segments=seg, profile=0.5,
                        affect='EDGES', clamp_overlap=True)
    for f in bm.faces:
        f.smooth = bevel > 0
    uv = bm.loops.layers.uv.new('UVMap')
    for f in bm.faces:
        n = f.normal
        ax = max(range(3), key=lambda i: abs(n[i]))
        for lp in f.loops:
            co = lp.vert.co
            lp[uv].uv = (co.y, co.z) if ax == 0 else ((co.x, co.z) if ax == 1 else (co.x, co.y))
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    me.materials.append(mat)
    o = bpy.data.objects.new(name, me)
    coll.objects.link(o)
    if parent is not None:
        o.parent = parent
    return o


def stand(name, coll, root, rows: list[tuple[float, float]], *, depth=1.0, legs=0.0, plank=0.1, margin=0.28,
          lowest_plank=True):
    """The lyric stand: a shelf per row (rows = [(z of the shelf top, width)]), side posts joining them and legs
    down `legs` units to whatever it stands on. Pale varnished beech."""
    wood = LM.beech()
    out = []
    W = max(w for _, w in rows) + 2 * margin
    zs = sorted(z for z, _ in rows)
    for k, (z, w) in enumerate(rows):
        if z == zs[0] and not lowest_plank:
            continue
        # flush with the blocks' faces, so an upper shelf never hides the row below it
        out.append(_box(f'{name}.shelf{k}', coll, (W, depth + 0.25, plank), (0, -depth / 2 + 0.125, z - plank / 2),
                        wood, bevel=0.03, parent=root))
    z_lo = zs[0] - (plank if lowest_plank else 0.0) - legs
    z_hi = zs[-1] - 0.0
    if legs > 0.02 or len(rows) > 1:
        post = 0.13
        for s in (-1, 1):
            x = s * (W / 2 - post / 2 - 0.04)
            h = z_hi - z_lo
            out.append(_box(f'{name}.post{s:+d}', coll, (post, post, h), (x, 0.08, z_lo + h / 2), wood,
                            bevel=0.02, parent=root))
            if legs > 0.02:
                out.append(_box(f'{name}.foot{s:+d}', coll, (post * 3.2, depth * 0.9, post * 0.7),
                                (x, -depth / 2 + 0.05, z_lo + post * 0.35), wood, bevel=0.02, parent=root))
    return out


def card(name, coll, root, x0, x1, z0, z1, *, tint='#F4EFE4', thick=0.03, lift=0.0):
    """A paper card under flat text (its face on the row plane; it lies behind the letters)."""
    w, h = x1 - x0, z1 - z0
    return [_box(name, coll, (w, thick, h), ((x0 + x1) / 2, -thick / 2 - lift, (z0 + z1) / 2), LM.paper(tint),
                 parent=root)]


def panel(name, coll, root, x0, x1, z0, z1, *, color='#0B1016'):
    return [_box(name, coll, (x1 - x0, 0.01, z1 - z0), ((x0 + x1) / 2, -0.005, (z0 + z1) / 2),
                 LM.screen_panel(color), parent=root)]


def slate(name, coll, root, x0, x1, z0, z1):
    """A school slate: dark board in a pale wooden frame."""
    out = [_box(name + '.board', coll, (x1 - x0, 0.1, z1 - z0), ((x0 + x1) / 2, 0.05, (z0 + z1) / 2), LM.slate(),
                parent=root)]
    fw = 0.28
    wood = LM.beech()
    for k, (sx, sz, cx, cz) in enumerate((((x1 - x0) + 2 * fw, fw, (x0 + x1) / 2, z1 + fw / 2),
                                          ((x1 - x0) + 2 * fw, fw, (x0 + x1) / 2, z0 - fw / 2),
                                          (fw, z1 - z0, x0 - fw / 2, (z0 + z1) / 2),
                                          (fw, z1 - z0, x1 + fw / 2, (z0 + z1) / 2))):
        out.append(_box(f'{name}.frame{k}', coll, (sx, 0.22, sz), (cx, 0.0, cz), wood, bevel=0.04, parent=root))
    return out


def pane(name, coll, root, x0, x1, z0, z1, *, frosted=True, thick=0.08, frame=True):
    """A standing glass pane behind the letters (frosted for fog writing, clear for gold leaf), in a thin frame."""
    mat = LM.frost() if frosted else LM.clear_glass()
    out = [_box(name + '.glass', coll, (x1 - x0, thick, z1 - z0), ((x0 + x1) / 2, thick / 2 + 0.01, (z0 + z1) / 2),
                mat, parent=root)]
    if frame:
        fw = 0.18
        wood = LM.beech()
        for k, (sx, sz, cx, cz) in enumerate((((x1 - x0) + 2 * fw, fw, (x0 + x1) / 2, z1 + fw / 2),
                                              ((x1 - x0) + 2 * fw, fw, (x0 + x1) / 2, z0 - fw / 2),
                                              (fw, z1 - z0, x0 - fw / 2, (z0 + z1) / 2),
                                              (fw, z1 - z0, x1 + fw / 2, (z0 + z1) / 2))):
            out.append(_box(f'{name}.frame{k}', coll, (sx, 0.24, sz), (cx, thick / 2, cz), wood, bevel=0.03,
                            parent=root))
    return out


def backing(name, coll, root, x0, x1, z0, z1):
    """Neon signs hang on a black acrylic board."""
    m = LM.M.solid('ly.backing', '#0C0C0E', rough=0.2, coat=0.8, coat_rough=0.05)
    return [_box(name, coll, (x1 - x0, 0.1, z1 - z0), ((x0 + x1) / 2, 0.08, (z0 + z1) / 2), m, bevel=0.04,
                 parent=root)]


def note(name, coll, root, x0, x1, z0, z1, *, color='#F6E27A'):
    """A sticky note (square-ish paper) behind a word."""
    return [_box(name, coll, (x1 - x0, 0.015, z1 - z0), ((x0 + x1) / 2, -0.0075, (z0 + z1) / 2), LM.sticky(color),
                 parent=root)]


def tape(name, coll, root, x0, x1, z0, z1, *, color='#1F1F24'):
    """A strip of embossing tape behind a word (glossy plastic)."""
    return [_box(name, coll, (x1 - x0, 0.04, z1 - z0), ((x0 + x1) / 2, -0.02, (z0 + z1) / 2), LM.tape(color),
                 bevel=0.012, parent=root)]


def _mesh_obj(name, coll, bm, mat, parent=None, smooth=True):
    for f in bm.faces:
        f.smooth = smooth
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    me.materials.append(mat)
    o = bpy.data.objects.new(name, me)
    coll.objects.link(o)
    if parent is not None:
        o.parent = parent
    return o


def thread(name, coll, parent, top_z, length=60.0, radius=0.012):
    """A cotton thread from a letter's top straight up (hanging letters)."""
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=True, segments=6, radius1=radius, radius2=radius, depth=length,
                          matrix=Matrix.Translation((0, -0.5, top_z + length / 2)))
    return _mesh_obj(name, coll, bm, LM.M.solid('ly.thread', '#E8E2D4', rough=0.9, sheen=0.5), parent)


def stamp_tool(name, coll, root, w, h):
    """A rubber stamp for flat rows: its red rubber face at y = 0 facing +Y (down onto the page), the wooden block
    and knob handle rising toward -Y (up, toward the viewer). Returns its objects (parented to root)."""
    out = []
    rub = LM.rubber()
    wood = LM.beech()
    out.append(_box(name + '.rubber', coll, (w, 0.12, h), (0, -0.06, h / 2), rub, bevel=0.02, parent=root))
    out.append(_box(name + '.block', coll, (w + 0.2, 0.45, h + 0.2), (0, -0.345, h / 2), wood, bevel=0.06,
                    parent=root))
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=True, segments=24, radius1=0.28, radius2=0.28, depth=0.9,
                          matrix=Matrix.Translation((0, -1.0, h / 2)) @ Matrix.Rotation(math.radians(90), 4, 'X'))
    out.append(_mesh_obj(name + '.handle', coll, bm, wood, root))
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=20, v_segments=10, radius=0.45,
                              matrix=Matrix.Translation((0, -1.6, h / 2)))
    out.append(_mesh_obj(name + '.knob', coll, bm, wood, root))
    return out
