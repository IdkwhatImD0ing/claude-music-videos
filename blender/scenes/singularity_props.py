"""singularity: small props. The laptop pictures (a calm training curve; the same run going vertical), cotton-wool
steam puffs from the chimney, and the hero debris the hole swallows (sticky notes peeling off a pad, paper clips, the
pen). All keyed per frame as pure functions of song time."""
from __future__ import annotations

import math

import bmesh
import bpy
from mathutils import Matrix, Vector

from pdoom import timing as tm
from pdoom.sets import geo
from pdoom.sets import materials as M

from scenes.singularity_hole import key_matrices

FPS = tm.FPS


# ------------------------------------------------------------------------------------------------ screen images


def _canvas(w, h):
    import numpy as np
    a = np.zeros((h, w, 4), dtype=np.float32)
    a[..., 3] = 1.0
    return a


def _hexc(s):
    import numpy as np
    s = s.lstrip('#')
    return np.array([int(s[i:i + 2], 16) / 255 for i in (0, 2, 4)], dtype=np.float32)


def _to_image(name, a):
    h, w = a.shape[:2]
    img = bpy.data.images.new(name, w, h, alpha=False)
    img.pixels.foreach_set(a[::-1].ravel())
    img.pack()
    return img


def chart_image(name, curve, color, *, w=1280, h=800, label='#D6DEEB', glow=False):
    """A dark chart with a grid and one thick curve y = curve(u) (u, y in 0..1)."""
    import numpy as np
    if name in bpy.data.images:
        return bpy.data.images[name]
    a = _canvas(w, h)
    a[..., :3] = _hexc('#0D1117')
    x0, x1, y0, y1 = 120, w - 80, 110, h - 110
    for i in range(6):
        yy = int(y0 + (y1 - y0) * i / 5)
        a[yy:yy + 2, x0:x1, :3] = _hexc('#1F2A36')
    for i in range(9):
        xx = int(x0 + (x1 - x0) * i / 8)
        a[y0:y1, xx:xx + 2, :3] = _hexc('#1F2A36')
    a[y0:y1 + 3, x0 - 3:x0, :3] = _hexc('#8B98A8')
    a[y1:y1 + 3, x0:x1, :3] = _hexc('#8B98A8')
    a[40:64, x0:x0 + 300, :3] = _hexc(label)
    a[40:64, x0 + 320:x0 + 420, :3] = _hexc('#5B6B7B')
    col = _hexc(color)
    n = 1600
    yy_, xx_ = np.mgrid[0:h, 0:w]
    for i in range(n + 1):
        u = i / n
        v = min(1.08, max(-0.05, curve(u)))
        x = x0 + u * (x1 - x0)
        y = y1 - v * (y1 - y0)
        if y < 30:
            break
        r = 7 if not glow else 9
        xa, xb = int(max(0, x - r - 1)), int(min(w, x + r + 2))
        ya, yb = int(max(0, y - r - 1)), int(min(h, y + r + 2))
        d = np.sqrt((xx_[ya:yb, xa:xb] - x) ** 2 + (yy_[ya:yb, xa:xb] - y) ** 2)
        k = np.clip(r - d, 0, 1)[..., None]
        a[ya:yb, xa:xb, :3] = a[ya:yb, xa:xb, :3] * (1 - k) + col * k
    return _to_image(name, a)


def stable_image():
    """A calm, well-behaved training run: loss falls smoothly and settles (blue)."""
    return chart_image('screen.sing.stable', lambda u: 0.12 + 0.72 * math.exp(-u * 4.2) +
                       0.012 * math.sin(u * 60) * math.exp(-u * 2), '#4A8CFF')


def takeoff_image():
    """The same axes, a capability curve going vertical (orange-red)."""
    return chart_image('screen.sing.takeoff', lambda u: 0.1 + 0.05 * u + 0.9 * max(0.0, (u - 0.55) / 0.45) ** 3.2 * 1.3,
                       '#FF5A2A', label='#FFB08A')


# ------------------------------------------------------------------------------------------------ steam


def puff_mesh(name, seed):
    """A cotton-wool puff: overlapping lumpy balls, about 1 cm across at scale 1."""
    if name in bpy.data.meshes:
        return bpy.data.meshes[name]
    bm = bmesh.new()
    r = geo.rng(seed)
    for k in range(7):
        c = Vector(((r() - 0.5) * 0.7, (r() - 0.5) * 0.7, (r() - 0.5) * 0.45 + 0.1))
        rad = 0.28 + 0.2 * r()
        ret = bmesh.ops.create_icosphere(bm, subdivisions=2, radius=rad)
        for v in ret['verts']:
            n = v.co.normalized()
            bump = 1 + 0.12 * math.sin(n.x * 9 + k) * math.sin(n.y * 7 - k) * math.sin(n.z * 8 + 2 * k)
            v.co = c + v.co * bump
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    for p in me.polygons:
        p.use_smooth = True
    return me


def steam_material():
    return M.solid('sing.steam', '#F3F1EE', rough=0.95, sss=0.55, sss_radius=(0.8, 0.8, 0.8), sheen=0.6)


def puffs(coll, births, chimney_fn, vel_fn, *, life=1.15, size=1.4, pull=None):
    """One puff per birth time: pops out of the chimney (chimney_fn(t) -> world point), rises and swells, is left
    behind by the train (keeps a little of vel_fn(t)), then shrinks away. pull(t, p) -> offset for the hole's
    tug. Keyed per frame."""
    m = steam_material()
    out = []
    for i, tb in enumerate(births):
        me = puff_mesh(f'sing.puff{i % 5}', 11 + i % 5)
        ob = bpy.data.objects.new(f'puff.{i:03d}', me)
        if not me.materials:
            me.materials.append(m)
        coll.objects.link(ob)
        ob.visible_shadow = True
        p0 = chimney_fn(tb)
        v0 = vel_fn(tb) * 0.12
        h = lambda *k: geo.hash01('puff', i, *k)
        drift = Vector(((h('dx') - 0.5) * 1.2, (h('dy') - 0.5) * 1.2, 0.0))
        spin = (h('s') - 0.5) * 3.0
        s_max = size * (0.8 + 0.5 * h('sz'))
        L = life * (0.85 + 0.3 * h('l'))
        f0, f1 = int(math.floor(tb * FPS)) - 1, int(math.ceil((tb + L) * FPS)) + 1
        frames, mats = [], []
        for f in range(f0, f1 + 1):
            t = f / FPS
            tau = max(0.0, t - tb)
            rise = 0.6 + 4.2 * (1 - math.exp(-tau / 0.9)) + 1.2 * tau
            p = p0 + v0 * (1 - math.exp(-tau / 0.25)) + drift * tau + Vector((0, 0, rise * min(1.0, tau / 0.06)))
            if pull is not None:
                p = p + pull(t, p) * tau
            grow = tm.smooth(tau, 0.0, 0.14)
            fade = 1 - tm.smooth(tau, L * 0.45, L)
            s = max(1e-3, s_max * (0.35 + 0.65 * grow) * fade * (1 + 0.6 * tau)) if tau > 0 else 1e-3
            Mt = Matrix.Translation(p) @ Matrix.Rotation(spin * tau + h('r0') * 6.3, 4, 'Z') @ Matrix.Scale(s, 4)
            frames.append(float(f))
            mats.append(Mt)
        key_matrices(ob, None, mats, frames=frames)
        _vis(ob, tb - 0.5 / FPS, tb + L)
        out.append(ob)
    return out


def _vis(ob, t_on, t_off):
    from pdoom import fx
    fx.vis(ob, t_on, t_off)


# ------------------------------------------------------------------------------------------------ sticky notes


def note_mesh(name, size=7.6, curl=0.3):
    if name in bpy.data.meshes:
        return bpy.data.meshes[name]
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
    me = bpy.data.meshes.new(name)
    me.from_pydata(verts, [], faces)
    uvl = me.uv_layers.new(name='UVMap')
    for i, uv in enumerate(uvs):
        uvl.data[i].uv = uv
    me.update()
    for p in me.polygons:
        p.use_smooth = True
    return me


def note_obj(coll, name, color, size=7.6, curl=0.3):
    me = note_mesh(f'sing.note.{size:.1f}.{curl:.2f}', size, curl)
    ob = bpy.data.objects.new(name, me)
    coll.objects.link(ob)
    mat = M.paper(f'note.{color}', color, tile=25)
    if not me.materials:
        me.materials.append(mat)
    ob.material_slots[0].link = 'OBJECT'
    ob.material_slots[0].material = mat
    sol = ob.modifiers.new('thick', 'SOLIDIFY')
    sol.thickness = 0.02
    return ob
