"""The `safe` scene's props: a wide-mouth glass jar (thick base, threaded neck), its gold screw lid, hazard-stripe tape
(the wrapped band, the free span and the roll) and the crack. Reusable: `leftturn` can import build_jar() for the
broken jar (same size and look).

Jar (local, base centre at the origin): outer radius 5.9, glass wall 0.3, a solid 2 cm glass base (the floor inside is
at z = 2.0), shoulder at 9.2 into a 5.65 neck, rim at 10.4; the screwed-on lid's top is at 10.7. Clawd (8 x 4.5, arms
+-5.25) fits inside facing any way.

Tape: the band sits at z 4.25-5.75 (below Clawd's eyes, which are at 6.2-7.6 when he stands on the glass floor). The
reveal of the wrapped band and the stripes on the free span are driven by one keyed value L (cm of tape laid), so
the stripes flow continuously from the roll, along the span, onto the jar.
"""
from __future__ import annotations

import math

import bmesh
import bpy
from mathutils import Vector

from pdoom import kit
from pdoom.fx import materials as FXM
from pdoom.sets import geo
from pdoom.sets import materials as M

R_OUT = 5.9          # outer radius of the body
R_IN = 5.6           # inner radius of the body
FLOOR = 2.0          # top of the solid glass base (Clawd stands here)
SHOULDER = 9.2
NECK = 5.65          # outer radius of the neck
NECK_IN = 5.38
RIM = 10.4
LID_TOP = 10.72
TAPE_W = 1.5
TAPE_Z0 = 4.25       # band bottom
TAPE_R = R_OUT + 0.035
STRIPE = 2 * math.pi * 1.3 / 7   # hazard stripe pitch along the tape (cm): 7 per turn of the roll (no seam)

# ------------------------------------------------------------------------------------------------ materials


def glass():
    return FXM.glass('safe.glass', tint='#F1FAF6', rough=0.015, ior=1.5, thin=True)


def lid_mat():
    """A jam-jar lid: red-and-white gingham printed on glossy enamelled tin (the checks show it turning)."""
    m, fresh = M.new_mat('safe.lid')
    if not fresh:
        return m
    nt = m.node_tree
    b = M.principled(m)
    b.location = (400, 0)
    tc = M.node(nt, 'ShaderNodeTexCoord', (-1200, 0))
    sep = M.node(nt, 'ShaderNodeSeparateXYZ', (-1000, 0))
    M.link(nt, M.sout(tc, 'Object'), M.sin(sep, 'Vector'))
    acc = []
    for i, ax in enumerate(('X', 'Y')):
        d = M.node(nt, 'ShaderNodeMath', (-800, 200 - 200 * i), operation='DIVIDE')
        M.link(nt, sep.outputs[ax], d.inputs[0])
        d.inputs[1].default_value = 1.1
        f = M.node(nt, 'ShaderNodeMath', (-650, 200 - 200 * i), operation='FRACT')
        M.link(nt, d.outputs[0], f.inputs[0])
        st = M.node(nt, 'ShaderNodeMath', (-500, 200 - 200 * i), operation='LESS_THAN')
        M.link(nt, f.outputs[0], st.inputs[0])
        st.inputs[1].default_value = 0.5
        acc.append(st)
    add = M.node(nt, 'ShaderNodeMath', (-350, 100), operation='ADD')
    M.link(nt, acc[0].outputs[0], add.inputs[0])
    M.link(nt, acc[1].outputs[0], add.inputs[1])
    half = M.node(nt, 'ShaderNodeMath', (-200, 100), operation='MULTIPLY')
    M.link(nt, add.outputs[0], half.inputs[0])
    half.inputs[1].default_value = 0.5
    mix = M.node(nt, 'ShaderNodeMix', (0, 100), data_type='RGBA', blend_type='MIX')
    M.link(nt, half.outputs[0], M.sin(mix, 'Factor', 'VALUE'))
    M.setin(mix, 'A', kit.srgb('#F2EBDD'), 'RGBA')
    M.setin(mix, 'B', kit.srgb('#B3261E'), 'RGBA')
    M.link(nt, M.sout(mix, 'Result', 'RGBA'), M.sin(b, 'Base Color'))
    M.setin(b, 'Roughness', 0.3)
    M.setin(b, 'Coat Weight', 0.8)
    M.setin(b, 'Coat Roughness', 0.08)
    m.diffuse_color = kit.srgb('#B3261E')
    return m


def lid_skirt_mat():
    """The knurled skirt: the lid's gold with vertical ribs (a bump from the angle around the axis)."""
    m, fresh = M.new_mat('safe.lid.skirt')
    if not fresh:
        return m
    nt = m.node_tree
    b = M.principled(m)
    M.setin(b, 'Base Color', kit.srgb('#A8221B'))
    M.setin(b, 'Metallic', 0.0)
    M.setin(b, 'Roughness', 0.3)
    M.setin(b, 'Coat Weight', 0.7)
    M.setin(b, 'Coat Roughness', 0.1)
    tc = M.node(nt, 'ShaderNodeTexCoord', (-900, 0))
    sep = M.node(nt, 'ShaderNodeSeparateXYZ', (-700, 0))
    M.link(nt, M.sout(tc, 'Object'), M.sin(sep, 'Vector'))
    at = M.node(nt, 'ShaderNodeMath', (-500, 0), operation='ARCTAN2')
    M.link(nt, sep.outputs['Y'], at.inputs[0])
    M.link(nt, sep.outputs['X'], at.inputs[1])
    mul = M.node(nt, 'ShaderNodeMath', (-320, 0), operation='MULTIPLY')
    M.link(nt, at.outputs[0], mul.inputs[0])
    mul.inputs[1].default_value = 90.0            # 90 ribs * 2 pi / 2 pi
    sn = M.node(nt, 'ShaderNodeMath', (-150, 0), operation='SINE')
    M.link(nt, mul.outputs[0], sn.inputs[0])
    bump = M.node(nt, 'ShaderNodeBump', (100, -200))
    M.setin(bump, 'Strength', 0.6)
    M.setin(bump, 'Distance', 0.02)
    M.link(nt, sn.outputs[0], M.sin(bump, 'Height'))
    M.link(nt, M.sout(bump, 'Normal'), M.sin(b, 'Normal'))
    return m


def _stripes(nt, s_sock, v_sock, loc=(-300, 300)):
    """Hazard stripes: yellow / black diagonal bands from tape coords s (along) and v (across), in cm."""
    add = M.node(nt, 'ShaderNodeMath', (loc[0] - 400, loc[1]), operation='ADD')
    nt.links.new(s_sock, add.inputs[0])
    nt.links.new(v_sock, add.inputs[1])
    div = M.node(nt, 'ShaderNodeMath', (loc[0] - 250, loc[1]), operation='DIVIDE')
    M.link(nt, add.outputs[0], div.inputs[0])
    div.inputs[1].default_value = STRIPE
    fr = M.node(nt, 'ShaderNodeMath', (loc[0] - 100, loc[1]), operation='FRACT')
    M.link(nt, div.outputs[0], fr.inputs[0])
    # a soft edge (printing is crisp but the macro lens isn't): smoothstep across 0.5
    mr = M.node(nt, 'ShaderNodeMapRange', (loc[0] + 60, loc[1]))
    mr.interpolation_type = 'SMOOTHSTEP'
    M.setin(mr, 'From Min', 0.47, 'VALUE')
    M.setin(mr, 'From Max', 0.53, 'VALUE')
    M.link(nt, fr.outputs[0], M.sin(mr, 'Value', 'VALUE'))
    mix = M.node(nt, 'ShaderNodeMix', (loc[0] + 240, loc[1]), data_type='RGBA', blend_type='MIX')
    M.link(nt, M.sout(mr, 'Result', 'VALUE'), M.sin(mix, 'Factor', 'VALUE'))
    M.setin(mix, 'A', kit.srgb('#F3C21C'), 'RGBA')
    M.setin(mix, 'B', kit.srgb('#141210'), 'RGBA')
    return M.sout(mix, 'Result', 'RGBA')


def tape_mat(name: str, *, reveal: bool, offset: bool):
    """Tape material. UV u = cm along the tape, v = cm across. A Value node 'L' (cm of tape laid, keyed by the
    scene) either cuts the band off beyond u = L (reveal, the wrapped band) or shifts the stripes by L (offset,
    the free span: its u runs from the jar end)."""
    m, fresh = M.new_mat(name)
    if not fresh:
        return m
    nt = m.node_tree
    b = M.principled(m)
    b.location = (500, 0)
    uv = M.node(nt, 'ShaderNodeUVMap', (-1200, 200))
    uv.uv_map = 'UVMap'
    sep = M.node(nt, 'ShaderNodeSeparateXYZ', (-1000, 200))
    M.link(nt, uv.outputs[0], M.sin(sep, 'Vector'))
    L = M.node(nt, 'ShaderNodeValue', (-1200, -100))
    L.name = L.label = 'L'
    L.outputs[0].default_value = 0.0
    s = sep.outputs['X']
    if offset:
        a = M.node(nt, 'ShaderNodeMath', (-800, 300), operation='ADD')
        M.link(nt, sep.outputs['X'], a.inputs[0])
        M.link(nt, L.outputs[0], a.inputs[1])
        s = a.outputs[0]
    col = _stripes(nt, s, sep.outputs['Y'])
    M.link(nt, col, M.sin(b, 'Base Color'))
    M.setin(b, 'Roughness', 0.32)
    M.setin(b, 'Coat Weight', 0.35)
    M.setin(b, 'Coat Roughness', 0.18)
    M.setin(b, 'Specular IOR Level', 0.5)
    if reveal:
        lt = M.node(nt, 'ShaderNodeMath', (-700, -100), operation='LESS_THAN')
        M.link(nt, sep.outputs['X'], lt.inputs[0])
        M.link(nt, L.outputs[0], lt.inputs[1])
        M.link(nt, lt.outputs[0], M.sin(b, 'Alpha'))
        m.surface_render_method = 'DITHERED'
        try:
            m.use_transparent_shadow = True
        except Exception:
            pass
    m.use_backface_culling = False
    m.diffuse_color = kit.srgb('#F3C21C')
    return m


def roll_mat():
    """The outside of the roll: the same stripes, from the angle around the roll (they turn with it)."""
    m, fresh = M.new_mat('safe.tape.roll')
    if not fresh:
        return m
    nt = m.node_tree
    b = M.principled(m)
    b.location = (500, 0)
    tc = M.node(nt, 'ShaderNodeTexCoord', (-1400, 200))
    sep = M.node(nt, 'ShaderNodeSeparateXYZ', (-1200, 200))
    M.link(nt, M.sout(tc, 'Object'), M.sin(sep, 'Vector'))
    at = M.node(nt, 'ShaderNodeMath', (-1000, 300), operation='ARCTAN2')
    M.link(nt, sep.outputs['Y'], at.inputs[0])
    M.link(nt, sep.outputs['X'], at.inputs[1])
    mul = M.node(nt, 'ShaderNodeMath', (-850, 300), operation='MULTIPLY')
    M.link(nt, at.outputs[0], mul.inputs[0])
    mul.inputs[1].default_value = ROLL_R       # arc length: material deeper in the roll sits at larger angles
    col = _stripes(nt, mul.outputs[0], sep.outputs['Z'])
    M.link(nt, col, M.sin(b, 'Base Color'))
    M.setin(b, 'Roughness', 0.3)
    M.setin(b, 'Coat Weight', 0.35)
    M.setin(b, 'Coat Roughness', 0.15)
    m.diffuse_color = kit.srgb('#F3C21C')
    return m


def crack_mat():
    """The crack: a hair-thin bright line (the fracture face catching the light), revealed along its length by the
    keyed value 'C' (cm from the origin); UV u = cm from the origin along the branch, v = 0..1 across."""
    m, fresh = M.new_mat('safe.crack')
    if not fresh:
        return m
    nt = m.node_tree
    b = M.principled(m)
    b.location = (500, 0)
    M.setin(b, 'Base Color', kit.srgb('#F4F8FF'))
    M.setin(b, 'Roughness', 0.08)
    M.setin(b, 'Metallic', 0.6)
    M.setin(b, 'Emission Color', kit.srgb('#E8F0FF'))
    M.setin(b, 'Emission Strength', 0.9)
    uv = M.node(nt, 'ShaderNodeUVMap', (-1000, 0))
    uv.uv_map = 'UVMap'
    sep = M.node(nt, 'ShaderNodeSeparateXYZ', (-800, 0))
    M.link(nt, uv.outputs[0], M.sin(sep, 'Vector'))
    C = M.node(nt, 'ShaderNodeValue', (-1000, -200))
    C.name = C.label = 'C'
    lt = M.node(nt, 'ShaderNodeMath', (-600, -100), operation='LESS_THAN')
    M.link(nt, sep.outputs['X'], lt.inputs[0])
    M.link(nt, C.outputs[0], lt.inputs[1])
    M.link(nt, lt.outputs[0], M.sin(b, 'Alpha'))
    m.surface_render_method = 'DITHERED'
    m.use_backface_culling = False
    m.diffuse_color = kit.srgb('#F4F8FF')
    return m


def value_node(m, name: str):
    return m.node_tree.nodes[name]


# ------------------------------------------------------------------------------------------------ the jar


def outer_profile():
    """(r, z) of the outer surface, bottom centre to rim (with the rim's rounded top)."""
    return [(0.0, 0.0), (5.25, 0.0), (5.62, 0.06), (5.84, 0.25), (5.9, 0.55), (5.9, SHOULDER - 0.25),
            (5.86, SHOULDER + 0.05), (5.72, SHOULDER + 0.28), (NECK, SHOULDER + 0.45), (NECK, RIM - 0.12),
            (5.6, RIM - 0.02), (5.52, RIM)]


def surface_r(z: float) -> float:
    """Outer radius at height z (for placing things on the glass)."""
    pr = outer_profile()[3:]
    for (r0, z0), (r1, z1) in zip(pr, pr[1:]):
        if z0 <= z <= z1 and z1 > z0:
            return r0 + (r1 - r0) * (z - z0) / (z1 - z0)
    return R_OUT if z < SHOULDER else NECK


def build_jar(coll, name='jar'):
    """The glass jar as one closed solid (outer wall, rim, inner wall, floor) + the neck's thread. Returns
    (jar, thread). Local origin = base centre."""
    prof = outer_profile() + [(5.45, RIM), (NECK_IN, RIM - 0.1), (NECK_IN, SHOULDER + 0.4), (R_IN, SHOULDER - 0.05),
                              (R_IN, FLOOR + 0.35), (R_IN - 0.12, FLOOR + 0.1), (R_IN - 0.4, FLOOR), (0.0, FLOOR)]
    jar = geo.lathe(name, prof, segs=112, coll=coll, m=glass(), smooth_angle=60)
    # the thread: 1.4 turns of a round ridge on the neck
    pts = []
    n = 90
    for i in range(n + 1):
        u = i / n
        a = math.radians(40) + u * 1.4 * 2 * math.pi
        z = SHOULDER + 0.62 + 0.62 * u
        pts.append((math.cos(a) * (NECK + 0.02), math.sin(a) * (NECK + 0.02), z))
    th = geo.curve_tube(f'{name}.thread', pts, 0.075, coll=coll, m=glass(), kind='POLY', to_mesh=True,
                        radii=[min(1.0, 8 * min(i / n, 1 - i / n)) for i in range(n + 1)])
    return jar, th


def lid_inside_mat():
    """The inside of the lid (lip, inner skirt, underside): plain red lacquered tin."""
    return M.solid('safe.lid.inside', '#8E1D17', rough=0.35, coat=0.5, coat_rough=0.12)


def build_lid(coll, name='jar.lid', *, plain_inside: bool = False):
    """The screw lid, origin at the jar's rim centre when fully tightened. plain_inside: the lip, inner skirt and
    underside get a plain lacquer (the gingham, projected from object X/Y, smears into vertical bars on the inner
    wall, which shows through the glass at eye level)."""
    prof = [(0.0, 0.3), (4.4, 0.28), (4.55, 0.33), (4.75, 0.33), (4.9, 0.27), (5.6, 0.26), (5.8, 0.2), (5.9, 0.07),
            (5.92, -0.02), (5.92, -0.98), (5.86, -1.04), (5.76, -0.98), (5.76, 0.1), (0.0, 0.1)]
    # material per profile segment: top parts gold, the skirt (outer vertical) knurled
    idx = [0] * (len(prof) - 1)
    idx[8] = 1
    mats = [lid_mat(), lid_skirt_mat()]
    if plain_inside:
        mats.append(lid_inside_mat())
        for i in (9, 10, 11, 12):
            idx[i] = 2
    lid = geo.lathe(name, prof, segs=112, coll=coll, mats=mats, mat_idx=idx, smooth_angle=50)
    return lid


# ------------------------------------------------------------------------------------------------ tape

ROLL_R = 1.3         # outer radius of the tape roll
CORE_R = 0.78


def wrap_band(coll, *, alpha1: float, turns: float = 2.3, pitch: float = 0.18, name='jar.tape'):
    """The wrapped band in the jar's local frame. Tape laid at s (cm) sits at local angle alpha1 - s / r (the jar
    turns counter-clockwise under a fixed tangent point at world angle alpha1). Returns (obj, material)."""
    m = tape_mat('safe.tape.band', reveal=True, offset=False)
    circ = 2 * math.pi * TAPE_R
    total = turns * circ
    n = int(total / 0.18) + 1
    verts, faces, uvs = [], [], []
    for i in range(n + 1):
        s = total * i / n
        r = TAPE_R + 0.022 * s / circ
        a = alpha1 - s / r
        z = TAPE_Z0 + pitch * s / circ
        c, sn = math.cos(a), math.sin(a)
        verts += [(r * c, r * sn, z), (r * c, r * sn, z + TAPE_W)]
    for i in range(n):
        faces.append((2 * i, 2 * i + 2, 2 * i + 3, 2 * i + 1))
        s0, s1 = total * i / n, total * (i + 1) / n
        uvs += [(s0, 0.0), (s1, 0.0), (s1, TAPE_W), (s0, TAPE_W)]
    o = geo.mesh_obj(name, verts, faces, coll, m, smooth=True, uvs=uvs)
    return o, m, total


def band_point(s: float, alpha1: float, pitch: float = 0.18) -> tuple[float, float, float]:
    """Local (jar) position of the band's centre line at tape length s."""
    circ = 2 * math.pi * TAPE_R
    r = TAPE_R + 0.022 * s / circ
    a = alpha1 - s / r
    return (r * math.cos(a), r * math.sin(a), TAPE_Z0 + pitch * s / circ + TAPE_W / 2)


def span(coll, p_jar: Vector, p_roll: Vector, name='jar.tape.span'):
    """The free span of tape between the roll's tangent point and the jar's (world points at the band's centre
    height). u runs from the jar end (0) to the roll; the stripes shift by L."""
    m = tape_mat('safe.tape.span', reveal=False, offset=True)
    d = p_roll - p_jar
    ln = d.length
    dh = Vector((d.x, d.y, 0)).normalized()
    up = Vector((0, 0, 1))
    verts = [p_jar - up * (TAPE_W / 2), p_roll - up * (TAPE_W / 2), p_roll + up * (TAPE_W / 2), p_jar + up * (TAPE_W / 2)]
    o = geo.mesh_obj(name, [tuple(v) for v in verts], [(0, 1, 2, 3)], coll, m, uvs=[(0, 0), (ln, 0), (ln, TAPE_W), (0, TAPE_W)])
    return o, m


def build_roll(coll, name='tape.roll'):
    """A small roll of hazard tape, axis +Z, origin at its centre (mid-height)."""
    w = TAPE_W
    body = geo.lathe(f'{name}', [(CORE_R + 0.06, -w / 2 + 0.02), (ROLL_R - 0.03, -w / 2 + 0.02), (ROLL_R, -w / 2 + 0.06),
                                 (ROLL_R, w / 2 - 0.06), (ROLL_R - 0.03, w / 2 - 0.02), (CORE_R + 0.06, w / 2 - 0.02)],
                     segs=64, coll=coll, mats=[M.solid('safe.tape.edge', '#B8922C', rough=0.35, coat=0.3),
                                               roll_mat()], mat_idx=[0, 0, 1, 0, 0], cap_top=False, cap_bottom=False)
    core = geo.lathe(f'{name}.core', [(CORE_R, -w / 2), (CORE_R + 0.07, -w / 2), (CORE_R + 0.07, w / 2),
                                      (CORE_R, w / 2), (CORE_R, -w / 2)], segs=48, coll=coll,
                     m=M.cardboard('safe.core'), smooth_angle=30)
    geo.attach(core, body)
    return body


# ------------------------------------------------------------------------------------------------ crack


def build_crack(coll, jar_parent, origin_angle: float, origin_z: float, *, seed: int = 7, name='jar.crack'):
    """A crack on the outer glass from (angle, z) (jar-local), running up to the rim and down toward the base, with a
    small impact star and a few short side branches. One mesh; UV u = cm from the origin along each branch.
    Returns (obj, material, max_len)."""
    rnd = geo.rng(seed)
    m = crack_mat()

    def P(a, z, lift=0.012):
        r = surface_r(z) + lift
        return Vector((r * math.cos(a), r * math.sin(a), z))

    def walk(a0, z0, z1, step=0.16, wander=0.05, bias=0.0):
        """A jagged path from (a0, z0) to height z1 on the surface (angle wanders)."""
        out = [(a0, z0)]
        a, z = a0, z0
        sgn = 1 if z1 > z0 else -1
        drift = 0.0
        while (z1 - z) * sgn > 1e-3:
            dz = min(step * (0.6 + 0.8 * rnd()), abs(z1 - z)) * sgn
            drift = 0.6 * drift + (rnd() - 0.5) * 2 * wander + bias
            z += dz
            a += drift / surface_r(z)
            out.append((a, z))
        return out

    branches = []                 # (list of (a, z), u at start, width)
    up = walk(origin_angle, origin_z, RIM - 0.05, bias=0.004)
    down = walk(origin_angle, origin_z, 0.35, bias=-0.003)
    branches.append((up, 0.0, 0.05))
    branches.append((down, 0.0, 0.05))
    # impact star: short rays
    for k in range(6):
        ang = 2 * math.pi * (k + 0.3 * rnd()) / 6
        ln = 0.25 + 0.35 * rnd()
        pts = [(origin_angle + math.cos(ang) * ln * j / 4 / R_OUT, origin_z + math.sin(ang) * ln * j / 4) for j in range(5)]
        branches.append((pts, 0.0, 0.035))
    # side branches off the main runs
    for main in (up, down):
        for _ in range(2):
            i = int(len(main) * (0.25 + 0.5 * rnd()))
            a, z = main[i]
            u0 = sum((P(*main[j + 1]) - P(*main[j])).length for j in range(i))
            dirz = 1 if main is up else -1
            sb = walk(a, z, z + dirz * (0.6 + 0.9 * rnd()), step=0.12, wander=0.09, bias=(rnd() - 0.5) * 0.12)
            branches.append((sb, u0, 0.03))
    verts, faces, uvs = [], [], []
    maxlen = 0.0
    for pts2, u0, w in branches:
        pts = [P(a, z) for a, z in pts2]
        if len(pts) < 2:
            continue
        s = u0
        base = len(verts)
        n = len(pts)
        ss = [u0]
        for i in range(1, n):
            ss.append(ss[-1] + (pts[i] - pts[i - 1]).length)
        maxlen = max(maxlen, ss[-1])
        for i in range(n):
            p = pts[i]
            nrm = Vector((p.x, p.y, 0)).normalized()
            tng = (pts[min(i + 1, n - 1)] - pts[max(i - 1, 0)]).normalized()
            side = nrm.cross(tng).normalized()
            taper = min(1.0, (n - 1 - i) / 4 + 0.15)
            ww = w * taper * (0.7 + 0.6 * rnd())
            verts += [tuple(p - side * ww / 2), tuple(p + side * ww / 2)]
        for i in range(n - 1):
            a0 = base + 2 * i
            faces.append((a0, a0 + 2, a0 + 3, a0 + 1))
            uvs += [(ss[i], 0.0), (ss[i + 1], 0.0), (ss[i + 1], 1.0), (ss[i], 1.0)]
    o = geo.mesh_obj(name, verts, faces, coll, m, uvs=uvs)
    o.visible_shadow = False
    geo.attach(o, jar_parent)
    return o, m, maxlen


# ------------------------------------------------------------------------------------------------ small props


def build_sugar(coll, name='sugar'):
    m = M.solid('safe.sugar', '#F6F3EC', rough=0.62, sss=0.25, sss_radius=(0.6, 0.6, 0.6), micro=(40.0, 0.06))
    o = kit.box(name, (0.75, 0.75, 0.75), (0, 0, 0), bevel=0.06, segments=2, m=m, coll=coll)
    return o


def build_matchbox(coll, name='matchbox'):
    """The apple box: a matchbox the researcher stands on to reach the lid (5.4 x 3.6 x 1.6 cm)."""
    tray = M.solid('safe.matchbox', '#C0392B', rough=0.55, micro=(12.0, 0.03))
    side = M.solid('safe.matchbox.strike', '#4A2B1E', rough=0.9, micro=(30.0, 0.15))
    o = kit.box(name, (5.4, 3.6, 1.6), (0, 0, 0.8), bevel=0.05, segments=2, m=tray, coll=coll)
    s = kit.box(f'{name}.strike', (5.0, 0.04, 1.1), (0, -1.81, 0.8), m=side, coll=coll)
    geo.attach(s, o, (0, -1.81, 0.0))
    return o
