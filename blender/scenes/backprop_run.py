"""The `backprop` scene's marble run: a three-layer MLP built of plywood, turned wooden funnel cups, cardboard chutes,
wooden flip-flop rockers, brass-socketed bulbs and a string-art "fully connected" net behind it all; plus the glass
cat's-eye marbles and their keyed motion.

Board-local coordinates (cm): x right, z up from the desk, y toward the back (the board's front face is y = 0, parts
stand out in front at negative y). Nodes (cup centres), 3-4-3:
    input  z 26:  x -16, 0, 16
    hidden z 17:  x -24, -8, 8, 24
    output z 8:   x -16, 0, 16
Cup axis at y = -2.6. Each node connects to the two nearest nodes below by a cardboard chute (a lattice); the full
bipartite net is strung in cotton thread between brass pins on the board face.

Marbles are keyed, not simulated: each route is a path function of "nominal time" u (seconds of a normal forward run;
u = 0 when it drops into its input cup), and a per-marble map t -> u plays it forward, backward (an exact rewind, spin
reversed) and faster. Rockers and bulbs are functions of the same u, so a rewind un-flips them.
"""
from __future__ import annotations

import math

import bmesh
import bpy
from mathutils import Matrix, Vector

from pdoom import kit
from pdoom.fx import materials as FXM
from pdoom.sets import geo
from pdoom.sets import materials as M
from pdoom.timing import FPS

LAYERS = [(26.0, [-16.0, 0.0, 16.0]), (17.0, [-24.0, -8.0, 8.0, 24.0]), (8.0, [-16.0, 0.0, 16.0])]
CUP_Y = -2.6
R_MARBLE = 0.78
BOARD_W, BOARD_H = 62.0, 33.5
HOPPER_Z = 30.2
TRAY_Z = 2.2              # tray floor
G = 981.0
# The flip-flop rockers hang ROCK_Z below their cup's centre, low enough that a marble resting on the paddle (it drops
# straight through the cup's hole onto it) has rolled clear of the cup's base before it moves sideways onto its
# chute. Rockers tilt +-TILT about the board normal.
ROCK_Z = 2.45
PAD_T = 0.22
TILT = math.radians(22)
CHUTE_DROP = 2.85         # a chute's floor starts this far below its upper cup's centre (just under the paddle end)
SEAT_Z = -0.23            # a centred marble's lowest rest in a cup's cone (relative to the cup centre)


def cup_inner_r(dz: float) -> float:
    """The cup's inner (cone) wall radius at height dz above the cup centre (valid for -0.42 <= dz <= 0.8)."""
    return 0.82 + 0.656 * (dz + 0.42)


# a marble touching the 33 deg cone wall has its centre this far (horizontally) inside the wall
CONE_CLEAR = R_MARBLE / math.cos(math.atan(0.656)) + 0.02

# lattice: each node to its two nearest nodes in the next layer
EDGES = [(0, 0, 0), (0, 0, 1), (0, 1, 1), (0, 1, 2), (0, 2, 2), (0, 2, 3),
         (1, 0, 0), (1, 1, 0), (1, 1, 1), (1, 2, 1), (1, 2, 2), (1, 3, 2)]


def node(layer: int, i: int) -> Vector:
    z, xs = LAYERS[layer]
    return Vector((xs[i], CUP_Y, z))


# ------------------------------------------------------------------------------------------------ materials


def ply():
    return M.solid('bp.ply', '#2C3A33', rough=0.7, coat=0.08, micro=(3.0, 0.06))


def wood_light():
    return M.solid('bp.beech', '#D9B98C', rough=0.45, coat=0.35, coat_rough=0.2, micro=(5.0, 0.04))


def cardboard():
    return M.cardboard('bp.cardboard')


def thread_mat():
    return M.solid('bp.thread', '#EFE3CC', rough=0.85, sheen=0.5)


def thread_red():
    return M.solid('bp.thread.red', '#B8322A', rough=0.8, sheen=0.5)


def bulb_mat(i: int):
    """One material per bulb (its glow is keyed): warm glass with an emissive core driven by 'glow' and 'col'."""
    m, fresh = M.new_mat(f'bp.bulb.{i}')
    if not fresh:
        return m
    b = M.principled(m)
    M.setin(b, 'Base Color', kit.srgb('#FFF1D8'))
    M.setin(b, 'Roughness', 0.08)
    M.setin(b, 'Transmission Weight', 0.55)
    M.setin(b, 'Coat Weight', 1.0)
    M.setin(b, 'Emission Color', kit.srgb('#FFB24A'))
    M.setin(b, 'Emission Strength', 0.0)
    m.diffuse_color = kit.srgb('#FFF1D8')
    return m


# ------------------------------------------------------------------------------------------------ geometry


def _cup(coll, name):
    """A turned funnel cup: rim radius 1.9, hole 0.75, origin at the node centre."""
    prof = [(0.8, -0.95), (1.0, -0.95), (1.05, -0.55), (1.9, 0.72), (1.95, 0.85), (1.88, 0.95), (1.72, 0.95),
            (1.62, 0.8), (0.82, -0.42), (0.78, -0.95)]
    prof = [(r, z) for r, z in prof] + [(0.8, -0.95)]
    o = geo.lathe(name, prof, segs=48, coll=coll, m=wood_light(), smooth_angle=40)
    return o


def _u_channel(bm, a: Vector, b: Vector, *, inner=1.8, wall=0.6, t=0.09, lip=0.1):
    """A cardboard U-channel whose floor runs from a to b (points on the floor's centre line, xz-plane slope),
    open at both ends. Adds to bm."""
    d = (b - a)
    ln = d.length
    dn = d.normalized()
    up = Vector((0, 0, 1))
    n = (up - dn * up.dot(dn)).normalized()          # floor normal, in the vertical plane of the chute
    side = dn.cross(n).normalized()
    # cross-section (side offset, normal offset), outer then inner, as a closed loop
    w = inner / 2
    sec = [(-w - t, wall), (-w - t, -t), (w + t, -t), (w + t, wall), (w, wall), (w, 0.0), (-w, 0.0), (-w, wall)]
    rings = []
    for p in (a - dn * 0.05, b + dn * 0.05):
        rings.append([bm.verts.new(p + side * sx + n * sy) for sx, sy in sec])
    k = len(sec)
    for i in range(k):
        j = (i + 1) % k
        bm.faces.new((rings[0][i], rings[0][j], rings[1][j], rings[1][i]))
    for r in rings:
        bm.faces.new(r)
    return n


def build(coll, origin: Vector):
    """Build the run at world `origin` (the board's front face, bottom centre). Returns a dict of handles."""
    O = Vector(origin)
    H = {'origin': O, 'bulbs': {}, 'rockers': {}, 'cups': {}}
    root = kit.empty('run', tuple(O), coll, 'ARROWS', 4.0)
    H['root'] = root

    def put(o, loc=(0, 0, 0), rot=None):
        geo.attach(o, root, Vector(loc), rot)
        return o
    # the board, its feet and a top rail
    board = geo.box('run.board', (BOARD_W, 1.2, BOARD_H), (0, 0, 0), bev=0.12, m=ply(), coll=coll)
    put(board, (0, 0.6, BOARD_H / 2 + 0.6))
    for sx in (-1, 1):
        foot = geo.box(f'run.foot{sx}', (2.2, 14.0, 1.4), (0, 0, 0), bev=0.15, m=wood_light(), coll=coll)
        put(foot, (sx * (BOARD_W / 2 - 4), 3.0, 0.7))
        brace = geo.prism(f'run.brace{sx}', [(0, 0), (9.0, 0), (0, 11.0)], 1.6, coll=coll, m=wood_light())
        put(brace, (sx * (BOARD_W / 2 - 4) - 0.8, 1.2, 1.4), (math.radians(90), 0, math.radians(90)))
    # string-art net: pins at every node on the board face, the full bipartite graph in cotton thread
    pins = {}
    for li, (z, xs) in enumerate(LAYERS):
        for i, x in enumerate(xs):
            p = Vector((x, -0.12, z))
            pins[(li, i)] = p
            pin = kit.cylinder(f'run.pin.{li}{i}', 0.16, 0.5, (0, 0, 0), verts=12, m=M.brass('bp.brass'), coll=coll,
                               rot=(math.radians(90), 0, 0))
            put(pin, p)
    k = 0
    for li in (0, 1):
        for i in range(len(LAYERS[li][1])):
            for j in range(len(LAYERS[li + 1][1])):
                a, b = pins[(li, i)] + Vector((0, -0.05 - 0.01 * (k % 3), 0)), pins[(li + 1, j)] + Vector((0, -0.05, 0))
                th = geo.curve_tube(f'run.thread.{k}', [tuple(a), tuple(b)], 0.028, coll=coll,
                                    m=thread_red() if (k % 5 == 2) else thread_mat(), kind='POLY', res=2, bevel_res=1)
                put(th)
                k += 1
    # cups (on little shelf brackets), rockers (flip-flops on brass pins) and bulbs (in brass sockets)
    for li, (z, xs) in enumerate(LAYERS):
        for i, x in enumerate(xs):
            c = _cup(coll, f'run.cup.{li}{i}')
            put(c, (x, CUP_Y, z))
            H['cups'][(li, i)] = c
            # the bracket holds the cup's back rim only, so the marbles drop past it through the hole
            br = geo.box(f'run.bracket.{li}{i}', (0.9, 1.5, 0.5), (0, 0, 0), bev=0.08, m=wood_light(), coll=coll)
            put(br, (x, -0.95, z - 0.95))
            # rocker: a thin paddle on a pin, ROCK_Z below the cup's centre (none under the output cups)
            if li < 2:
                rk = kit.empty(f'run.rocker.{li}{i}', (0, 0, 0), coll, 'PLAIN_AXES', 0.5)
                put(rk, (x, CUP_Y, z - ROCK_Z))
                pad = geo.box(f'run.rocker.{li}{i}.pad', (2.6, 1.7, PAD_T), (0, 0, 0), bev=0.07, m=M.enamel(
                    'bp.rocker', '#D97757', rough=0.35, coat=0.4), coll=coll)
                geo.attach(pad, rk, Vector((0, 0, 0.0)))
                fin = geo.box(f'run.rocker.{li}{i}.fin', (0.22, 1.7, 0.9), (0, 0, 0), bev=0.05, m=M.enamel(
                    'bp.rocker', '#D97757'), coll=coll)
                geo.attach(fin, rk, Vector((0, 0, -0.5)))
                axle = kit.cylinder(f'run.rocker.{li}{i}.axle', 0.12, 2.9, (0, 0, 0), verts=10, m=M.brass('bp.brass'),
                                    coll=coll, rot=(math.radians(90), 0, 0))
                put(axle, (x, CUP_Y / 2 + 0.2, z - ROCK_Z))
                H['rockers'][(li, i)] = rk
            # bulb above-left of the cup on the board face
            bm_ = bulb_mat(len(H['bulbs']))
            sock = kit.cylinder(f'run.socket.{li}{i}', 0.42, 0.9, (0, 0, 0), verts=20, m=M.brass('bp.brass'),
                                coll=coll, rot=(math.radians(90), 0, 0))
            put(sock, (x - 2.9, -0.45, z + 1.3))
            bulb = kit.sphere(f'run.bulb.{li}{i}', 0.5, (0, 0, 0), m=bm_, coll=coll, subdiv=3)
            put(bulb, (x - 2.9, -1.15, z + 1.3))
            bulb.visible_shadow = False
            lt = kit.point(f'run.bulblight.{li}{i}', (0, 0, 0), power=0.0, radius=0.4, color='#FFB24A', coll=coll)
            put(lt, (x - 2.9, -1.9, z + 1.3))
            lt.data.specular_factor = 0.4
            H['bulbs'][(li, i)] = (bulb, bm_, lt)
    # chutes (one mesh), with dowel struts to the board
    bm = bmesh.new()
    for li, i, j in EDGES:
        a, b = chute_ends(li, i, j)
        _u_channel(bm, a, b)
    me = bpy.data.meshes.new('run.chutes')
    bm.to_mesh(me)
    bm.free()
    ch = bpy.data.objects.new('run.chutes', me)
    coll.objects.link(ch)
    me.materials.append(cardboard())
    geo.box_uv(ch)
    put(ch)
    for li, i, j in EDGES:
        a, b = chute_ends(li, i, j)
        mid = (a + b) / 2 - Vector((0, 0, 0.2))
        st = kit.cylinder(f'run.strut.{li}{i}{j}', 0.16, abs(mid.y) + 0.2, (0, 0, 0), verts=10, m=wood_light(),
                          coll=coll, rot=(math.radians(90), 0, 0))
        put(st, (mid.x, mid.y / 2 - 0.1, mid.z))
    # hopper (top trough with three holes over the inputs) and the tray at the bottom
    hop = geo.box('run.hopper', (40.0, 3.2, 0.25), (0, 0, 0), bev=0.05, m=cardboard(), coll=coll)
    put(hop, (0, CUP_Y, HOPPER_Z - 0.12))
    for sx in (-1, 1):
        wall = geo.box(f'run.hopper.wall{sx}', (40.0, 0.12, 1.2), (0, 0, 0), m=cardboard(), coll=coll)
        put(wall, (0, CUP_Y + sx * 1.6, HOPPER_Z + 0.5))
    for x in LAYERS[0][1]:
        ring = geo.lathe(f'run.hopper.hole{x:+.0f}', [(0.72, -0.14), (0.95, -0.14), (0.95, 0.02), (0.72, 0.02)],
                         segs=24, coll=coll, m=M.brass('bp.brass'))
        put(ring, (x, CUP_Y, HOPPER_Z + 0.02))
    tray = geo.box('run.tray', (44.0, 3.4, 0.2), (0, 0, 0), bev=0.04, m=cardboard(), coll=coll)
    put(tray, (0, CUP_Y, TRAY_Z - 0.1))
    for sx in (-1, 1):
        wall = geo.box(f'run.tray.wall{sx}', (44.0, 0.12, 1.3), (0, 0, 0), m=cardboard(), coll=coll)
        put(wall, (0, CUP_Y + sx * 1.7, TRAY_Z + 0.55))
    for sx in (-1, 1):
        end = geo.box(f'run.tray.end{sx}', (0.12, 3.4, 1.3), (0, 0, 0), m=cardboard(), coll=coll)
        put(end, (sx * 22.0, CUP_Y, TRAY_Z + 0.55))
        leg = geo.box(f'run.tray.leg{sx}', (1.0, 1.0, TRAY_Z), (0, 0, 0), m=wood_light(), coll=coll)
        put(leg, (sx * 18.0, CUP_Y, TRAY_Z / 2 - 0.1))
    return H


def chute_ends(li, i, j):
    """Floor centre-line ends of the chute from node (li, i) to node (li + 1, j) (board-local)."""
    a = node(li, i)
    b = node(li + 1, j)
    s = 1.0 if b.x > a.x else -1.0
    return (Vector((a.x + s * 1.45, CUP_Y, a.z - CHUTE_DROP)), Vector((b.x - s * 1.35, CUP_Y, b.z + 1.75)))


# ------------------------------------------------------------------------------------------------ marbles


def marble_material(name: str, core: str):
    """A glossy swirl marble ('onyx' style): a saturated base with a cream band swirled through it by a distorted
    wave, under a thick clear coat. Opaque on purpose: clear glass vanished against the dark board."""
    m, fresh = M.new_mat(f'bp.marble.{name}')
    if not fresh:
        return m
    nt = m.node_tree
    b = M.principled(m)
    b.location = (400, 0)
    tc = M.node(nt, 'ShaderNodeTexCoord', (-900, 0))
    wv = M.node(nt, 'ShaderNodeTexWave', (-700, 0))
    wv.wave_type = 'BANDS'
    M.setin(wv, 'Scale', 1.1)
    M.setin(wv, 'Distortion', 6.0)
    M.setin(wv, 'Detail', 2.0)
    M.link(nt, M.sout(tc, 'Object'), M.sin(wv, 'Vector'))
    mr = M.node(nt, 'ShaderNodeMapRange', (-500, 0))
    M.setin(mr, 'From Min', 0.55, 'VALUE')
    M.setin(mr, 'From Max', 0.7, 'VALUE')
    M.link(nt, wv.outputs[1], M.sin(mr, 'Value', 'VALUE'))
    mix = M.node(nt, 'ShaderNodeMix', (-250, 0), data_type='RGBA', blend_type='MIX')
    M.link(nt, M.sout(mr, 'Result', 'VALUE'), M.sin(mix, 'Factor', 'VALUE'))
    M.setin(mix, 'A', kit.srgb(core), 'RGBA')
    M.setin(mix, 'B', kit.srgb('#F6EEDC'), 'RGBA')
    M.link(nt, M.sout(mix, 'Result', 'RGBA'), M.sin(b, 'Base Color'))
    M.setin(b, 'Roughness', 0.18)
    M.setin(b, 'Subsurface Weight', 0.25)
    M.setin(b, 'Subsurface Radius', (0.4, 0.4, 0.4))
    M.setin(b, 'Subsurface Scale', 0.2)
    M.setin(b, 'Coat Weight', 1.0)
    M.setin(b, 'Coat Roughness', 0.02)
    m.diffuse_color = kit.srgb(core)
    return m


def build_marble(coll, name: str, core: str):
    """A glossy swirl marble, radius R_MARBLE; its swirl shows it rolling."""
    o = kit.sphere(f'marble.{name}', R_MARBLE, (0, 0, 0), m=marble_material(name, core), coll=coll, subdiv=4)
    o.rotation_mode = 'XYZ'
    return o


class Route:
    """A marble's path through input i0, hidden h, output o (board-local), as a function of nominal time u.

    Events (nominal u): 0 enter the input cup, U_H enter the hidden cup, U_O enter the output cup, U_T land in the
    tray, U_END at rest. Negative u: falling from the hopper (u = U_HOP: at the hopper hole)."""
    SPIRAL, HOLE, ROCK, FLIGHT = 0.14, 0.05, 0.04, 0.05
    U_H, U_O = 0.404, 0.82
    U_T = U_O + 0.14 + 0.05 + 0.1
    U_END = U_T + 0.16

    def __init__(self, i0: int, h: int, o: int, spin_dir=1.0, roll_dir=1.0):
        self.nodes = [(0, i0), (1, h), (2, o)]
        self.roll_dir = roll_dir
        self.segs = []       # (u0, u1, fn(tau) -> Vector)
        hop = Vector((node(0, i0).x, CUP_Y, HOPPER_Z + R_MARBLE + 0.02))
        e0 = self._entry(0, i0, None)
        T0 = math.sqrt(2 * max(0.1, hop.z - e0.z) / G)
        self.U_HOP = -T0
        self.segs.append((-T0, 0.0, lambda s, a=hop, b=e0, T=T0: self._fall(a, b, T, s)))
        u = 0.0
        prev_dir = None
        for k in range(3):
            li, ni = self.nodes[k]
            nxt = self.nodes[k + 1] if k < 2 else None
            e = self._entry(li, ni, prev_dir)
            c = node(li, ni)
            sd = (1.0 if (nxt and node(*nxt).x > c.x) else -1.0) if nxt else roll_dir
            spin = spin_dir if prev_dir is None else prev_dir
            self.segs.append((u, u + self.SPIRAL, lambda s, e=e, c=c, sp=spin: self._spiral(e, c, sp, s)))
            u += self.SPIRAL
            hole = Vector((c.x, CUP_Y, c.z + SEAT_Z))
            if nxt is None:
                # drop through the output hole into the tray, bounce, roll a little
                land = Vector((c.x, CUP_Y, TRAY_Z + R_MARBLE))
                Tf = self.U_T - u
                self.segs.append((u, self.U_T, lambda s, a=hole, b=land, T=Tf: self._fall(a, b, T, s)))
                rest = land + Vector((roll_dir * 2.2, 0, 0))
                self.segs.append((self.U_T, self.U_END, lambda s, a=land, b=rest: self._settle(a, b, s)))
                break
            a, b = chute_ends(li, ni, nxt[1])
            nrm = self._n(a, b)
            # straight down through the hole onto the middle of the tilted paddle, along it and off its low end
            # onto the chute (the paddle slopes down toward the chute until the marble has left it)
            on_pad = (PAD_T / 2 + R_MARBLE) / math.cos(TILT)
            rock = Vector((c.x, CUP_Y, c.z - ROCK_Z + on_pad))
            pad_end = rock + Vector((sd * 1.15, 0.0, -1.15 * math.tan(TILT)))
            self.segs.append((u, u + self.HOLE, lambda s, p=hole, q=rock: p.lerp(q, s * s)))
            u += self.HOLE
            start = a + nrm * R_MARBLE
            self.segs.append((u, u + self.ROCK, lambda s, pts=(rock, pad_end, start): self._poly(pts, s)))
            u += self.ROCK
            end = b + nrm * R_MARBLE
            u_next = self.U_H if k == 0 else self.U_O
            Tc = u_next - self.FLIGHT - u
            self.segs.append((u, u + Tc, lambda s, p=start, q=end: p.lerp(q, 0.35 * s + 0.65 * s * s)))
            u += Tc
            e_next = self._entry(nxt[0], nxt[1], sd)
            v_end = (end - start) / Tc * (0.35 + 2 * 0.65)
            self.segs.append((u, u_next, lambda s, p=end, q=e_next, T=self.FLIGHT, v=v_end: self._arc(p, q, T, v, s)))
            u = u_next
            prev_dir = sd
        self._build_spin()

    @staticmethod
    def _n(a, b):
        d = (b - a).normalized()
        up = Vector((0, 0, 1))
        return (up - d * up.dot(d)).normalized()

    @staticmethod
    def _poly(pts, s):
        """A point a fraction s of the way along the polyline pts (by length)."""
        ls = [(q - p).length for p, q in zip(pts, pts[1:])]
        d = s * sum(ls)
        for i, ln in enumerate(ls):
            if d <= ln or i == len(ls) - 1:
                return pts[i].lerp(pts[i + 1], min(1.0, d / ln) if ln > 0 else 1.0)
            d -= ln
        return pts[-1].copy()

    @staticmethod
    def _entry(li, ni, from_dir):
        """Where a marble enters a cup: the first one drops in centred from the hopper; later ones land off-centre
        at the top of the cone, inside the wall clearance (cup_inner_r - CONE_CLEAR = 0.65 at dz 0.8)."""
        c = node(li, ni)
        if from_dir is None:
            return Vector((c.x, CUP_Y, c.z + 0.55))
        return Vector((c.x - from_dir * 0.56, CUP_Y - 0.14, c.z + 0.80))

    @staticmethod
    def _fall(a, b, T, s):
        """Free fall from a (at rest) to b over T (s in 0..1)."""
        p = a.lerp(b, s)
        p.z = a.z + (b.z - a.z) * s * s
        return p

    @staticmethod
    def _arc(p, q, T, v, s):
        """A short ballistic hop from p to q over T, leaving p with roughly velocity v."""
        t = s * T
        lin = p.lerp(q, s)
        lin.z = p.z + (q.z - p.z) * s + 0.5 * G * t * (T - t) * 0.6
        return lin

    @staticmethod
    def _spiral(e, c, sp, s):
        """Round the funnel 1.2 turns from the entry point e down to the seat above the hole, never closer to the
        cone wall than a marble's radius allows."""
        r0 = math.hypot(e.x - c.x, e.y - CUP_Y)
        a0 = math.atan2(e.y - CUP_Y, e.x - c.x)
        k = s ** 0.85
        z = e.z + (c.z + SEAT_Z - e.z) * k
        r = max(0.0, min(r0 * (1 - k) ** 0.8, cup_inner_r(z - c.z) - CONE_CLEAR))
        a = a0 + sp * 2 * math.pi * 1.2 * k
        return Vector((c.x + r * math.cos(a), CUP_Y + r * math.sin(a), z))

    @staticmethod
    def _settle(a, b, s):
        p = a.lerp(b, 1 - (1 - s) ** 2.5)
        p.z = a.z + 0.25 * max(0.0, math.sin(math.pi * min(1.0, s * 3.0))) * (1 - s)
        return p

    def pos(self, u: float) -> Vector:
        if u <= self.segs[0][0]:
            return self.segs[0][2](0.0)
        for u0, u1, fn in self.segs:
            if u <= u1:
                return fn((u - u0) / (u1 - u0) if u1 > u0 else 1.0)
        return self.segs[-1][2](1.0)

    def _build_spin(self):
        """Rolling angle about the board normal (Euler Y) as a function of u: signed path length / r."""
        n = 900
        u0, u1 = self.segs[0][0], self.U_END
        self._su = [u0 + (u1 - u0) * i / n for i in range(n + 1)]
        th = [0.0]
        prev = self.pos(self._su[0])
        for uu in self._su[1:]:
            p = self.pos(uu)
            d = p - prev
            th.append(th[-1] + (1.0 if d.x >= 0 else -1.0) * d.length / R_MARBLE)
            prev = p
        self._th = th

    def spin(self, u: float) -> float:
        su = self._su
        if u <= su[0]:
            return self._th[0]
        if u >= su[-1]:
            return self._th[-1]
        x = (u - su[0]) / (su[-1] - su[0]) * (len(su) - 1)
        i = int(x)
        f = x - i
        return self._th[i] + (self._th[i + 1] - self._th[i]) * f

    def node_u(self, k: int) -> float:
        return (0.0, self.U_H, self.U_O)[k]

    def rocker_u(self, k: int) -> float:
        """The rocker starts to flip as the marble rolls off its paddle onto the chute (not before: it would swing
        up through the marble)."""
        return self.node_u(k) + self.SPIRAL + self.HOLE + self.ROCK


def umap(keys):
    """Piecewise-linear t -> u through [(t, u)] (held flat outside)."""
    def f(t):
        if t <= keys[0][0]:
            return keys[0][1]
        for (ta, ua), (tb, ub) in zip(keys, keys[1:]):
            if t <= tb:
                return ua + (ub - ua) * (t - ta) / (tb - ta)
        return keys[-1][1]
    return f


def crossings(keys, u_mark: float):
    """Song times where the t -> u map passes u_mark, with the direction (+1 forward, -1 backward)."""
    out = []
    for (ta, ua), (tb, ub) in zip(keys, keys[1:]):
        if ua == ub:
            continue
        if min(ua, ub) <= u_mark < max(ua, ub) or (ub == u_mark and ua != ub):
            f = (u_mark - ua) / (ub - ua)
            out.append((ta + (tb - ta) * f, 1 if ub > ua else -1))
    return out
