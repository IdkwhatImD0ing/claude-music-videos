"""ilya's box: a small closed walnut box with brass corners and a peephole. Something inside glows: coloured light
leaks from the lid seam and pours out of the peephole onto whoever looks in. We never see inside.

    bx = build_box(coll, loc=(8, 8, 0), peep_z=8.6)
    bx.light(t0, t1, level=lambda t: ...)          # keyed every frame: colour cycle + flicker (deterministic)
"""
from __future__ import annotations

import math

import bmesh
import bpy
from mathutils import Matrix, Vector

from pdoom import kit
from pdoom import timing as tm
from pdoom.chars import geo as cgeo
from pdoom.chars import looks
from pdoom.chars.rig import hash01
from pdoom.sets import geo as sgeo
from pdoom.sets import materials as SM

FPS = tm.FPS
W_BOX, H_BOX = 6.4, 5.0
LID_H = 1.05
GAP = 0.08
PEEP_LOCAL = 3.3          # peephole height above the box's base

# the light inside: a slow drift through these colours (linear RGB from sRGB hex)
PALETTE = ['#9FD8FF', '#7B61FF', '#FF4FA0', '#FFC24A', '#FF3A2A', '#E8F4FF', '#58FFD0']


def _T(p):
    return Matrix.Translation(Vector(p))


def _R(ex, ey, ez):
    from mathutils import Euler
    return Euler((math.radians(ex), math.radians(ey), math.radians(ez)), 'XYZ').to_matrix().to_4x4()


class Box:
    pass


def build_box(coll, loc=(0, 0, 0), peep_z: float = 9.0, yaw: float = 0.0) -> Box:
    """The box on a stack of old books (so its peephole is at world height peep_z), its peephole on the -X face,
    a glowing lid seam, and the lights."""
    bx = Box()
    base = max(0.0, peep_z - PEEP_LOCAL)
    books = kit.empty('ilya.books', loc, coll)
    bx.books = _books(coll, books, base)
    loc = (loc[0], loc[1], loc[2] + base)
    bx.base = base
    walnut = looks.wood('ilya.walnut', light='#7A4E2E', dark='#3A2012')
    brass = SM.brass('ilya.brass', '#C49A48', 0.3)
    dark = looks.satin('ilya.hole', '#050404', rough=0.9)
    glow = looks.emitter('ilya.glow', '#9FD8FF', 0.0)
    root = kit.empty('ilya.box', loc, coll)
    root.rotation_euler.z = math.radians(yaw)
    bx.root = root
    h = W_BOX / 2

    def part(bm, name, mats, sharp=40.0):
        ob = cgeo.to_object(bm, f'ilya.box.{name}', coll, mats, sharp=sharp)
        ob.parent = root
        return ob

    bm = bmesh.new()
    cgeo.rounded_box(bm, (W_BOX, W_BOX, H_BOX), 0.18, (0, 0, H_BOX / 2), seg=2, flat=(3, 3, 3))
    # a band moulding under the lid and a plinth
    cgeo.rounded_box(bm, (W_BOX + 0.3, W_BOX + 0.3, 0.6), 0.12, (0, 0, 0.3), seg=2, flat=(3, 3, 0))
    part(bm, 'body', [walnut])
    bm = bmesh.new()
    cgeo.rounded_box(bm, (W_BOX + 0.35, W_BOX + 0.35, LID_H), 0.3, (0, 0, H_BOX + GAP + LID_H / 2), seg=3,
                     flat=(3, 3, 1))
    cgeo.rounded_box(bm, (3.0, 0.5, 0.35), 0.12, (0, 0, H_BOX + GAP + LID_H + 0.12), seg=2, flat=(1, 0, 0), mat=1)
    part(bm, 'lid', [walnut, brass])
    # brass corners, hasp, hinges
    bm = bmesh.new()
    for sx in (-1, 1):
        for sy in (-1, 1):
            for z in (0.45, H_BOX - 0.45):
                cgeo.rounded_box(bm, (0.9, 0.9, 0.9), 0.2, (sx * (h - 0.3), sy * (h - 0.3), z), seg=2,
                                 flat=(0, 0, 0))
            cgeo.rounded_box(bm, (1.0, 1.0, 0.75), 0.24,
                             (sx * (h - 0.3), sy * (h - 0.3), H_BOX + GAP + LID_H / 2), seg=2, flat=(0, 0, 0))
    cgeo.rounded_box(bm, (1.0, 0.2, 1.5), 0.08, (0, -h - 0.05, H_BOX - 0.3), seg=1, flat=(0, 0, 1))
    part(bm, 'brass', [brass])
    # the peephole on the -X face: a brass ring (a door viewer), a dark tunnel, the glowing lens in the ring's mouth
    # (the body is closed, so the lens sits just proud of the wall, inside the ring)
    pz = PEEP_LOCAL
    bm = bmesh.new()
    cgeo.lathe(bm, [(0.2, 0.0), (0.52, 0.0), (0.6, 0.12), (0.52, 0.3), (0.3, 0.32), (0.2, 0.3)], segs=36,
               M=_T((-h, 0, pz)) @ _R(0, -90, 0))
    part(bm, 'peep', [brass], sharp=None)
    bm = bmesh.new()
    cgeo.lathe(bm, [(0.2, 0.3), (0.2, -0.6)], segs=24, M=_T((-h, 0, pz)) @ _R(0, -90, 0))
    part(bm, 'tunnel', [dark], sharp=None)
    bm = bmesh.new()
    cgeo.lathe(bm, [(0.0, 0.05), (0.21, 0.05)], segs=24, M=_T((-h, 0, pz)) @ _R(0, -90, 0))
    part(bm, 'lens', [glow], sharp=None)
    # the lid seam: a glowing band in the gap
    bm = bmesh.new()
    cgeo.rounded_box(bm, (W_BOX - 0.04, W_BOX - 0.04, GAP + 0.04), 0.1, (0, 0, H_BOX + GAP / 2), seg=2, flat=(3, 3, 0))
    part(bm, 'seam', [glow])
    bx.glow = glow
    bx.peep_local = Vector((-h - 0.35, 0, pz))
    # lights: a wide soft spot out of the peephole (it lights the face that looks in), a faint glow from the seam
    ld = bpy.data.lights.new('ilya.peeplight', 'SPOT')
    ld.energy = 0.0
    ld.spot_size = math.radians(110)
    ld.spot_blend = 1.0
    ld.shadow_soft_size = 0.25
    lo = bpy.data.objects.new('ilya.peeplight', ld)
    coll.objects.link(lo)
    lo.parent = root
    lo.location = (-h + 1.2, 0, pz + 0.2)     # inside the box, unshadowed: it pours out over the face
    lo.rotation_euler = (0, math.radians(90), 0)
    try:
        ld.use_shadow = False
    except Exception:
        pass
    bx.spot = ld
    ld = bpy.data.lights.new('ilya.beam', 'SPOT')
    ld.energy = 0.0
    ld.spot_size = math.radians(16)
    ld.spot_blend = 0.6
    ld.shadow_soft_size = 0.05
    ld.volume_factor = 4.0          # a thin shaft is narrower than a volume cell: scatter more so it reads in the haze
    lo = bpy.data.objects.new('ilya.beam', ld)
    coll.objects.link(lo)
    lo.parent = root
    # inside the box (its apex hidden behind the wall, which would block a shadowed light: the body has no hole)
    lo.location = (-h + 0.6, 0, pz)
    lo.rotation_euler = (0, math.radians(90), 0)
    try:
        ld.use_shadow = False
    except Exception:
        pass
    bx.beam = ld
    ld = bpy.data.lights.new('ilya.seamlight', 'POINT')
    ld.energy = 0.0
    ld.shadow_soft_size = 3.0
    try:
        ld.use_shadow = False
    except Exception:
        pass
    lo = bpy.data.objects.new('ilya.seamlight', ld)
    coll.objects.link(lo)
    lo.parent = root
    lo.location = (0, 0, H_BOX + 1.6)
    bx.seam = ld
    return bx


def _books(coll, parent, height):
    """A stack of old cloth-bound books (the box's pedestal), exactly `height` cm tall."""
    cols = ['#5B2A2A', '#23384F', '#3F4A2A', '#6A4A28']
    n = max(1, round(height / 1.9))
    hs = [height / n] * n
    objs = []
    z = 0.0
    for i, hh in enumerate(hs):
        cloth = looks.satin(f'ilya.book{i}', cols[i % len(cols)], rough=0.75, bump=0.3, bump_scale=120.0)
        paper = looks.paper('ilya.pages', '#E8DFC8')
        bm = bmesh.new()
        w, dd = 10.4 - 0.7 * i, 7.6 - 0.35 * i
        cgeo.rounded_box(bm, (w, dd, hh), 0.1, (0, 0, z + hh / 2), seg=2, flat=(2, 2, 0))
        cgeo.rounded_box(bm, (w - 0.5, dd - 0.35, hh - 0.26), 0.05, (0.2, -0.2, z + hh / 2), seg=1, flat=(2, 2, 0),
                         mat=1)
        ob = cgeo.to_object(bm, f'ilya.book{i}', coll, [cloth, paper])
        ob.parent = parent
        ob.rotation_euler.z = math.radians(9 * (hash01(i, 5) - 0.5))
        objs.append(ob)
        z += hh
    return objs


def colour_at(t: float, speed: float = 0.55):
    """The inner light's colour: a slow drift through PALETTE (linear RGB)."""
    x = (t * speed) % len(PALETTE)
    i = int(x)
    u = x - i
    u = u * u * (3 - 2 * u)
    a = kit.srgb(PALETTE[i])
    b = kit.srgb(PALETTE[(i + 1) % len(PALETTE)])
    return tuple(a[k] + (b[k] - a[k]) * u for k in range(3))


def flicker(t: float, seed: int = 5, rate: float = 18.0) -> float:
    """0.55..1.25: a restless, living flicker (smoothed hash noise) with rare spikes."""
    x = t * rate
    i = math.floor(x)
    u = x - i
    u = u * u * (3 - 2 * u)
    a, b = hash01(seed, i), hash01(seed, i + 1)
    n = a + (b - a) * u
    x2 = t * rate * 0.37
    j = math.floor(x2)
    v = x2 - j
    c, d = hash01(seed + 3, j), hash01(seed + 3, j + 1)
    n2 = c + (d - c) * (v * v * (3 - 2 * v))
    spike = 0.5 if hash01(seed + 9, i) > 0.93 else 0.0
    return 0.55 + 0.45 * n + 0.25 * n2 + spike * (1 - u)


def animate(bx: Box, t0: float, t1: float, level, *, flashes=(), white=()):
    """Key the box's light every frame from t0 to t1: level(t) (0 off .. ~1 normal .. more) x flicker, colours drifting.
    flashes: [(t, strength)] white-hot bursts; white: [(t0, t1)] spans forced toward white."""
    f0, f1 = int(math.floor(t0 * FPS)), int(math.ceil(t1 * FPS))
    em = bx.glow.node_tree.nodes['glow'].outputs[0]
    ec = bx.glow.node_tree.nodes['glowcol'].outputs[0]
    for f in range(f0, f1 + 1):
        t = f / FPS
        lv = max(0.0, level(t)) * flicker(t)
        col = colour_at(t)
        wf = 0.0
        for a, b in white:
            if a <= t <= b:
                wf = max(wf, min(1.0, (t - a) / 0.08, (b - t) / 0.12))
        for tf, s in flashes:
            if t >= tf - 0.02:
                k = math.exp(-max(0.0, t - tf) * 7.0) * (t >= tf - 0.02)
                lv += s * k
                wf = max(wf, k)
        col = tuple(c + (1.0 - c) * wf for c in col)
        _k(em, 'default_value', f, 14.0 * lv)
        for k in range(3):
            _k(ec, 'default_value', f, col[k], k)
        _k(bx.spot, 'energy', f, 2400.0 * lv)
        _k(bx.beam, 'energy', f, 9000.0 * lv)
        _k(bx.seam, 'energy', f, 160.0 * lv)
        for L in (bx.spot, bx.beam, bx.seam):
            for k in range(3):
                _k(L, 'color', f, col[k], k)
    for idb in (bx.glow.node_tree, bx.spot, bx.beam, bx.seam):
        kit.set_interp(idb, 'LINEAR')


def _k(owner, prop, f, v, index=-1):
    if index >= 0:
        getattr(owner, prop)[index] = v
    else:
        setattr(owner, prop, v)
    owner.keyframe_insert(prop, frame=f, index=index)
