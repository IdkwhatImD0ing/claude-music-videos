"""Props and effects for `fuse` (scene-local, not library code).

The race: a landscape of paperclips over the buried desk (a height field with a clip field on it and the mound under
Clawd), a burning fuse cord laid over it with a speed profile (ignites slowly, then races), a kitchen match with a
flickering flame, a matchbox, and a big red firecracker.
The club: two wooden rulers crossed at right angles (the axes), a thread-spool stool, a tiny cherry-red blues guitar,
a squat pencil cup (the bar), a whisky glass and a tealight.

Everything is keyed by song time and seeded (pure functions of time).
"""
from __future__ import annotations

import math

import bmesh
import bpy
from mathutils import Matrix, Vector

from pdoom import kit
from pdoom.chars import geo as cgeo
from pdoom.fx import _nodes as N
from pdoom.fx import clips, particles
from pdoom.sets import geo
from pdoom.sets import materials as M
from pdoom import timing as _tm
from pdoom.timing import FPS

V = Vector

# ------------------------------------------------------------------------------------------------ the clip landscape

SEA = 10.0                       # the sea of clips over the desk (paperclips ends at ~10 cm)
C0 = V((-1.2, -5.6, 0.0))        # the mound under Clawd (paperclips' C0)
PEAK = 27.9                      # mound surface at its top (clips on it reach ~28.4, where Clawd sits)
SLOPE = 0.95
RFLAT = 8.5                      # the flat top: the researcher and Clawd stand on it side by side


def _softplus(x, k):
    z = x / k
    return x if z > 30 else k * math.log1p(math.exp(z))


def _smax(a, b, k):
    h = max(k - abs(a - b), 0.0) / k
    return max(a, b) + h * h * k * 0.25


def dunes(x, y):
    return (0.9 * math.sin(0.11 * x + 0.7) * math.cos(0.09 * y - 0.3) + 0.55 * math.sin(0.23 * x - 0.17 * y + 1.3)
            + 0.3 * math.sin(0.41 * x + 0.37 * y + 2.1) + 0.16 * math.sin(0.83 * x - 0.61 * y + 0.4))


def height(x, y):
    """Surface height (cm) of the clip landscape's core at (x, y)."""
    base = SEA + dunes(x, y)
    r = math.hypot(x - C0.x, y - C0.y)
    mound = PEAK - SLOPE * _softplus(r - RFLAT, 1.2) + 0.35 * math.sin(0.9 * (x - y)) * min(1.0, r / 6.0)
    h = _smax(base, mound, 2.5)
    if y < -40.0:
        h -= (-40.0 - y) * 3.0
    return h


def normal(x, y, e=0.3):
    dx = (height(x + e, y) - height(x - e, y)) / (2 * e)
    dy = (height(x, y + e) - height(x, y - e)) / (2 * e)
    return V((-dx, -dy, 1.0)).normalized()


TOP = 0.55                        # the clip layers' top above the core surface


def build_land(coll, *, x0=-84.0, x1=84.0, y0=-46.0, y1=40.5, step=1.0, density=0.62, layers=3, lod=2):
    """The core surface (a dark steel height field) + a clip field on it. Returns (surface, field dict)."""
    nx = int(round((x1 - x0) / step)) + 1
    ny = int(round((y1 - y0) / step)) + 1
    verts, faces = [], []
    for j in range(ny):
        y = y0 + j * step
        for i in range(nx):
            x = x0 + i * step
            verts.append((x, y, height(x, y)))
    for j in range(ny - 1):
        for i in range(nx - 1):
            a = j * nx + i
            faces.append((a, a + 1, a + nx + 1, a + nx))
    core_m = kit.mat('fuse.land.core', '#2E3136', rough=0.42, metal=0.85)
    surf = geo.mesh_obj('fuse.land', verts, faces, coll, core_m, smooth=True)
    fld = clips.field('fuse.clips', surface=surf, density=density, layers=layers, lod=lod, seed=21, coll=coll,
                      tilt=0.42)
    return surf, fld


def lay_path(points2d, *, clear=1.15, samples=10, end=None):
    """A dense 3D polyline over the landscape through (x, y) waypoints (Catmull-Rom), `clear` cm above the core.
    end: an optional final 3D point (the firecracker's fuse hole) the cord climbs to."""
    pts = geo.catmull([V((p[0], p[1], 0.0)) for p in points2d], samples)
    out = [V((p.x, p.y, height(p.x, p.y) + clear)) for p in pts]
    # smooth the heights a little (the cord drapes over the clips instead of following every dune)
    for _ in range(3):
        sm = [out[0]]
        for i in range(1, len(out) - 1):
            z = (out[i - 1].z + 2 * out[i].z + out[i + 1].z) / 4
            sm.append(V((out[i].x, out[i].y, max(z, height(out[i].x, out[i].y) + clear * 0.8))))
        sm.append(out[-1])
        out = sm
    if end is not None:
        e = V(end)
        last = out[-1]
        n = 6
        for k in range(1, n + 1):
            u = k / n
            q = last.lerp(e, u)
            q.z = last.z + (e.z - last.z) * (u * u * (3 - 2 * u))
            out.append(q)
    return out


# ------------------------------------------------------------------------------------------------ the burning fuse


def _profile(t_ign, t_end, total, *, v0=3.0, v1=32.0, v2=58.0, creep=0.26):
    """s(t): arc length burnt at song time t. Creeps at v0 for `creep` s after ignition, then speeds up to v1 and
    accelerates to v2 at the end; normalised so s(t_end) = total."""
    n = 2000
    dt = (t_end - t_ign) / n
    S = [0.0]
    for k in range(n):
        t = t_ign + (k + 0.5) * dt
        a = _ss(t_ign + creep * 0.6, t_ign + creep + 0.18, t)
        b = _ss(t_ign + creep + 0.18, t_end, t)
        v = v0 + (v1 - v0) * a + (v2 - v1) * b
        S.append(S[-1] + v * dt)
    k = total / S[-1]

    def s_of(t):
        if t <= t_ign:
            return 0.0
        if t >= t_end:
            return total
        x = (t - t_ign) / dt
        i = min(int(x), n - 1)
        return k * (S[i] + (S[i + 1] - S[i]) * (x - i))
    return s_of


def _ss(a, b, x):
    if b <= a:
        return float(x >= b)
    u = min(max((x - a) / (b - a), 0.0), 1.0)
    return u * u * (3 - 2 * u)


def cord_material(name='fuse.cord'):
    """A green visco fuse: waxed cotton wrap with a tight twist (rings along the cord from the 'u' attribute)."""
    if name in bpy.data.materials:
        return bpy.data.materials[name]
    m, _ = M.new_mat(name)
    nt = m.node_tree
    b = M.principled(m)
    at = M.node(nt, 'ShaderNodeAttribute', (-900, 200), attribute_name='u')
    mul = M.node(nt, 'ShaderNodeMath', (-700, 200), operation='MULTIPLY')
    mul.inputs[1].default_value = 5.5
    M.link(nt, at.outputs['Fac'], mul.inputs[0])
    sn = M.node(nt, 'ShaderNodeMath', (-500, 200), operation='SINE')
    M.link(nt, mul.outputs[0], sn.inputs[0])
    mr = M.node(nt, 'ShaderNodeMapRange', (-300, 200))
    M.setin(mr, 'From Min', -1.0, 'VALUE')
    M.setin(mr, 'To Min', 0.55, 'VALUE')
    M.link(nt, sn.outputs[0], M.sin(mr, 'Value', 'VALUE'))
    mx = M.node(nt, 'ShaderNodeMix', (-100, 300), data_type='RGBA', blend_type='MULTIPLY')
    M.setin(mx, 'Factor', 1.0, 'VALUE')
    M.setin(mx, 'A', M.col('#5FA848'), 'RGBA')
    M.link(nt, M.sout(mr, 'Result', 'VALUE'), M.sin(mx, 'B', 'RGBA'))
    M.link(nt, M.sout(mx, 'Result', 'RGBA'), b.inputs['Base Color'])
    M.setin(b, 'Roughness', 0.45)
    M.setin(b, 'Coat Weight', 0.4)
    M.setin(b, 'Coat Roughness', 0.25)
    bp = M.node(nt, 'ShaderNodeBump', (0, -200))
    M.setin(bp, 'Strength', 0.35)
    M.setin(bp, 'Distance', 0.02)
    M.link(nt, sn.outputs[0], M.sin(bp, 'Height'))
    M.link(nt, M.sout(bp, 'Normal'), b.inputs['Normal'])
    m.diffuse_color = M.col('#3E7A3A')
    return m


def burn(name, pts, *, t_ign, t_end, coll, radius=0.24, rate=560.0, light=7500.0, seed=4, s_of=None,
         glow_len=4.0, **prof):
    """A fuse cord along pts that ignites at t_ign and burns (creep, then race) to its end at t_end. The burning
    point throws sparks, carries a flickering light and an incandescent bead; the burnt part is ash that glows for
    a few cm behind the burn point. Returns a dict with 's' (s(t)), 'at' (point at arc length), objects."""
    import numpy as np
    rng = np.random.default_rng(seed)
    P, L = particles._polyline(pts)
    total = L[-1]
    if s_of is None:
        s_of = _profile(t_ign, t_end, total, **prof)

    def at(s):
        return particles._at(P, L, s)

    # the path curve (hidden) the tubes are built from
    cd = bpy.data.curves.new(f'{name}.path', 'CURVE')
    cd.dimensions = '3D'
    sp = cd.splines.new('POLY')
    sp.points.add(len(P) - 1)
    for i, p in enumerate(P):
        sp.points[i].co = (p.x, p.y, p.z, 1.0)
    path = bpy.data.objects.new(f'{name}.path', cd)
    coll.objects.link(path)
    path.hide_render = True
    cord_m = cord_material()
    ash_m = kit.mat(f'{name}.ash', '#121010', rough=0.95, emit='#FF5A1A', emit_strength=0.0)
    b = ash_m.node_tree.nodes.get('Principled BSDF')
    atn = ash_m.node_tree.nodes.new('ShaderNodeAttribute')
    atn.attribute_name = 'glow'
    mul = ash_m.node_tree.nodes.new('ShaderNodeMath')
    mul.operation = 'MULTIPLY'
    mul.inputs[1].default_value = 30.0
    ash_m.node_tree.links.new(atn.outputs['Fac'], mul.inputs[0])
    ash_m.node_tree.links.new(mul.outputs[0], b.inputs['Emission Strength'])

    def tube(nm, mat, keep_before, r):
        g = N.Tree(f'{nm}.gn')
        g.input_geometry()
        prog = g.param('Burn', 'FLOAT', 0.0)
        crv = g.object_geo(path, relative=True)
        crv = g.out(g.node('GeometryNodeResampleCurve', inputs={'Curve': crv, 'Count': 900}))
        ln = g.out(g.node('GeometryNodeSplineParameter'), 'Length')
        crv = g.store(crv, 'u', ln)
        tr = g.node('GeometryNodeTrimCurve', mode='FACTOR', inputs={'Curve': crv})
        if keep_before:
            g.feed(g.inp(tr, 'Start'), 0.0)
            g.feed(g.inp(tr, 'End'), prog)
        else:
            g.feed(g.inp(tr, 'Start'), prog)
            g.feed(g.inp(tr, 'End'), 1.0)
        crv = g.out(tr)
        if keep_before:
            # glow within glow_len cm behind the burn point
            u = g.out(g.node('GeometryNodeInputNamedAttribute', data_type='FLOAT', inputs={'Name': 'u'}),
                      'Attribute')
            crv = g.store(crv, 'glow', g.smooth(u, prog * total - glow_len, prog * total))
        circ = g.out(g.node('GeometryNodeCurvePrimitiveCircle', inputs={'Resolution': 10, 'Radius': r}))
        mesh = g.out(g.node('GeometryNodeCurveToMesh', inputs={'Curve': crv, 'Profile Curve': circ,
                                                               'Fill Caps': True}))
        mesh = g.set_material(mesh, mat)
        g.output(mesh)
        me = bpy.data.meshes.new(nm)
        ob = bpy.data.objects.new(nm, me)
        coll.objects.link(ob)
        mod = N.modifier(ob, g, 'tube')
        f0, f1 = int(math.floor(t_ign * FPS)) - 1, int(math.ceil(t_end * FPS)) + 1
        for f in range(f0, f1 + 1):
            N.key_input(ob, mod, 'Burn', f / FPS, s_of(f / FPS) / total, interp='LINEAR')
        return ob

    cord = tube(f'{name}.cord', cord_m, False, radius)
    ash = tube(f'{name}.ash', ash_m, True, radius * 0.75)

    # sparks from the burn point (more while racing: births follow the burn with a floor rate)
    n = int(rate * (t_end - t_ign))
    tb = np.sort(rng.uniform(t_ign, t_end, n))
    p0, v0, fl = [], [], []
    for bt in tb:
        s = s_of(bt)
        p, tan = at(s)
        d = rng.normal(0, 1, 3)
        d /= np.linalg.norm(d)
        d[2] = abs(d[2]) * 1.2 + 0.5
        d = d - np.array(tan) * 0.35          # spit a little backward (the burn front races ahead)
        d /= np.linalg.norm(d)
        p0.append((p.x, p.y, p.z + radius))
        v0.append(tuple(d * rng.uniform(30, 120)))
        fl.append(height(p.x, p.y) + TOP)
    p0a, v0a, fla = np.array(p0), np.array(v0), np.array(fl)
    lf = rng.uniform(0.1, 0.42, n)
    k = np.full(n, 2.2)
    aland = particles._land_age(p0a[:, 2], v0a[:, 2], k, particles.G, fla, lf)
    sparks = particles._cloud(f'{name}.sparks', {'p0': p0a, 'v0': v0a, 'birth': tb, 'life': lf, 'k': k,
                                                 'aland': aland, 'size': np.full(n, 0.032) * rng.uniform(0.6, 1.5, n)},
                              coll)
    N.modifier(sparks, particles._spark_tree(f'{name}.sparks.gn', particles._spark_mat(f'{name}.spark.mat',
                                                                                        strength=45.0),
                                             gscale=1.0, streak=0.022, size=0.032), 'sparks')
    # the incandescent bead and the flickering light riding the burn point
    bead_m = kit.emission_mat(f'{name}.bead', '#FFE9B0', 70.0)
    bead = kit.sphere(f'{name}.bead', radius * 1.25, (0, 0, 0), m=bead_m, coll=coll, subdiv=2)
    bead.visible_shadow = False
    from pdoom.fx import vis as fxvis
    fxvis(bead, t_ign - 0.5 / FPS, t_end + 1.0 / FPS)
    fxvis(ash, t_ign - 0.5 / FPS, None)          # its glowing end cap would show before it burns
    lt = kit.point(f'{name}.light', P[0], power=light, radius=0.9, color='#FF9A3A', coll=coll)
    f0, f1 = int(math.floor(t_ign * FPS)), int(math.ceil(t_end * FPS))
    for f in range(f0 - 1, f1 + 2):
        t = f / FPS
        p, _ = at(s_of(t))
        j = V(((geo.hash01(name, 'jx', f) - 0.5) * 0.12, (geo.hash01(name, 'jy', f) - 0.5) * 0.12, 0.0))
        kit.key(bead, 'location', t, tuple(p + V((0, 0, radius * 0.6)) + j), interp='LINEAR')
        kit.key(lt, 'location', t, tuple(p + V((0, 0, 0.9))), interp='LINEAR')
        e = light * (0.7 + 0.6 * geo.hash01(name, 'fl', f)) if t_ign - 0.5 / FPS <= t <= t_end + 0.5 / FPS else 0.0
        geo.keyp(lt.data, 'energy', t, e, interp='LINEAR')
    return {'s': s_of, 'at': at, 'total': total, 'cord': cord, 'ash': ash, 'sparks': sparks, 'bead': bead,
            'light': lt, 'path': path}


# ------------------------------------------------------------------------------------------------ flames


def flame_material(name='fuse.flame', *, strength=9.0, height_cm=2.2):
    """A candle/match flame: emission ramp from a blue base through white-yellow to orange at the tip, fading at
    the silhouette (Layer Weight facing), blended."""
    if name in bpy.data.materials:
        return bpy.data.materials[name]
    m = bpy.data.materials.new(name)
    nt = m.node_tree
    nt.nodes.clear()
    out = nt.nodes.new('ShaderNodeOutputMaterial')
    tc = nt.nodes.new('ShaderNodeTexCoord')
    sep = nt.nodes.new('ShaderNodeSeparateXYZ')
    nt.links.new(tc.outputs['Object'], sep.inputs['Vector'])
    mr = nt.nodes.new('ShaderNodeMapRange')
    mr.inputs['From Min'].default_value = 0.0
    mr.inputs['From Max'].default_value = height_cm
    nt.links.new(sep.outputs['Z'], mr.inputs['Value'])
    ramp = nt.nodes.new('ShaderNodeValToRGB')
    cr = ramp.color_ramp
    cr.elements[0].position, cr.elements[0].color = 0.0, kit.srgb('#3A6BFF')
    cr.elements[1].position, cr.elements[1].color = 1.0, kit.srgb('#FF4A10')
    for pos, c in ((0.12, '#FFD89A'), (0.35, '#FFF6D8'), (0.7, '#FFB040')):
        e = cr.elements.new(pos)
        e.color = kit.srgb(c)
    nt.links.new(mr.outputs['Result'], ramp.inputs['Fac'])
    em = nt.nodes.new('ShaderNodeEmission')
    nt.links.new(ramp.outputs['Color'], em.inputs['Color'])
    # brighter in the core
    lw = nt.nodes.new('ShaderNodeLayerWeight')
    lw.inputs['Blend'].default_value = 0.35
    inv = nt.nodes.new('ShaderNodeMath')
    inv.operation = 'SUBTRACT'
    inv.inputs[0].default_value = 1.0
    nt.links.new(lw.outputs['Facing'], inv.inputs[1])
    pw = nt.nodes.new('ShaderNodeMath')
    pw.operation = 'POWER'
    pw.inputs[1].default_value = 1.6
    nt.links.new(inv.outputs[0], pw.inputs[0])
    st = nt.nodes.new('ShaderNodeMath')
    st.operation = 'MULTIPLY'
    st.inputs[1].default_value = strength
    nt.links.new(pw.outputs[0], st.inputs[0])
    nt.links.new(st.outputs[0], em.inputs['Strength'])
    tr = nt.nodes.new('ShaderNodeBsdfTransparent')
    mix = nt.nodes.new('ShaderNodeMixShader')
    nt.links.new(pw.outputs[0], mix.inputs['Fac'])
    nt.links.new(tr.outputs[0], mix.inputs[1])
    nt.links.new(em.outputs[0], mix.inputs[2])
    nt.links.new(mix.outputs[0], out.inputs['Surface'])
    for attr, v in (('surface_render_method', 'BLENDED'), ('use_transparent_shadow', True)):
        try:
            setattr(m, attr, v)
        except Exception:
            pass
    m.diffuse_color = kit.srgb('#FFB040')
    return m


def flame_mesh(name, coll, *, h=2.2, r=0.42, m=None):
    """A teardrop flame standing on its origin (local +Z up), h tall."""
    prof = [(0.0, 0.0), (r * 0.45, h * 0.03), (r * 0.85, h * 0.14), (r, h * 0.3), (r * 0.88, h * 0.5),
            (r * 0.55, h * 0.72), (r * 0.22, h * 0.9), (0.0, h)]
    o = geo.lathe(name, prof, segs=24, coll=coll, m=m or flame_material(height_cm=h))
    o.visible_shadow = False
    return o


def key_flame(fl, light, pos_of, t0, t1, *, seed=1, size_of=None, base_power=2200.0, lean_k=0.004):
    """Key a flame (and its light) every frame from t0 to t1: position pos_of(t) (world), flicker in scale, a lean
    against its motion. size_of(t) scales it (0 = out)."""
    f0, f1 = int(math.floor(t0 * FPS)) - 1, int(math.ceil(t1 * FPS)) + 1
    # every output frame (the 60 fps grid when timing.SMOOTH, so the flame follows the smoothly baked match on
    # every frame; whole 24 fps frames otherwise); the flicker hashes stay per 24 fps frame, blended in between
    frames = _tm.out_frames(f0, f1) if _tm.SMOOTH else list(range(f0, f1 + 1))

    def hv(tag, fr):
        a = math.floor(fr + 1e-6)
        u = fr - a
        h0 = geo.hash01(seed, tag, int(a))
        return h0 if u < 1e-6 else h0 + (geo.hash01(seed, tag, int(a) + 1) - h0) * u

    prev = prev_t = None
    prev_s = 0.0
    for fr in frames:
        t = fr / FPS
        p = V(pos_of(t))
        s = size_of(t) if size_of else 1.0
        if _tm.SMOOTH and prev_s <= 0.0 < s and prev_t is not None:
            # it lights between two output frames: hold it out until just before the frame it shows on (between
            # exposures), so the previous frame's exposure stays dark
            tz = t - 0.5 * (FPS / _tm.OUT_FPS) / FPS
            kit.key(fl, 'scale', tz, (0.0, 0.0, 0.0), interp='LINEAR')
            if light is not None:
                geo.keyp(light.data, 'energy', tz, 0.0, interp='LINEAR')
        prev_s = s
        fx = 1.0 + 0.1 * (hv('fx', fr) - 0.5)
        fz = 1.0 + 0.28 * (hv('fz', fr) - 0.5)
        vel = (p - prev) / (t - prev_t) if prev is not None else V((0, 0, 0))
        prev, prev_t = p, t
        lean = V((-vel.x * lean_k + 0.05 * (hv('lx', fr) - 0.5),
                  -vel.y * lean_k + 0.05 * (hv('ly', fr) - 0.5), 1.0))
        rot = V((0, 0, 1)).rotation_difference(lean.normalized()).to_euler()
        kit.key(fl, 'location', t, tuple(p), interp='LINEAR')
        kit.key(fl, 'rotation_euler', t, tuple(rot), interp='LINEAR')
        kit.key(fl, 'scale', t, (s * fx, s * fx, s * fz), interp='LINEAR')
        if light is not None:
            kit.key(light, 'location', t, tuple(p + V((0, 0, 0.8 * s))), interp='LINEAR')
            geo.keyp(light.data, 'energy', t, base_power * s * (0.8 + 0.4 * hv('le', fr)),
                     interp='LINEAR')


# ------------------------------------------------------------------------------------------------ match, box


def match(coll, name='match'):
    """A big kitchen match (6.4 cm) along local +Z from its origin (the end he holds). Returns (root, head, charred).
    The head is red with a white tip; `charred` (hidden until struck) is the burnt head."""
    root = kit.empty(name, (0, 0, 0), coll, size=0.5)
    wood = M.solid('match.wood', '#E8CFA0', rough=0.7, micro=(30.0, 0.04))
    stick = geo.box(f'{name}.stick', (0.3, 0.3, 5.9), (0, 0, 2.95), bev=0.03, m=wood, coll=coll)
    geo.attach(stick, root)
    bm = bmesh.new()
    cgeo.uv_sphere(bm, 1.0, segs=20, rings=12, scale=(0.3, 0.3, 0.46), M=Matrix.Translation((0, 0, 6.05)))
    head_m = M.solid('match.head', '#B8261C', rough=0.85, micro=(40.0, 0.2))
    head = cgeo.to_object(bm, f'{name}.head', coll, [head_m], sharp=None)
    geo.attach(head, root)
    bm = bmesh.new()
    cgeo.uv_sphere(bm, 1.0, segs=16, rings=10, scale=(0.14, 0.14, 0.14), M=Matrix.Translation((0, 0, 6.42)))
    tip = cgeo.to_object(bm, f'{name}.tip', coll, [M.solid('match.tip', '#F2EEDC', rough=0.8)], sharp=None)
    geo.attach(tip, root)
    bm = bmesh.new()
    cgeo.uv_sphere(bm, 1.0, segs=20, rings=12, scale=(0.27, 0.27, 0.4), M=Matrix.Translation((0, 0, 6.05)))
    char_m = M.solid('match.char', '#1B1512', rough=0.9, emit='#FF5A10', emit_strength=0.6)
    charred = cgeo.to_object(bm, f'{name}.char', coll, [char_m], sharp=None)
    geo.attach(charred, root)
    return root, (head, tip), charred


def matchbox(coll, name='matchbox'):
    """A kitchen matchbox 5.6 x 3.6 x 1.7 cm lying flat (origin at its bottom centre, long side along X). The long
    sides carry brown striker strips; the top a simple printed label (no text)."""
    root = kit.empty(name, (0, 0, 0), coll, size=0.5)
    card = M.solid('mbox.card', '#E9DDBF', rough=0.75, micro=(12.0, 0.03))
    red = M.solid('mbox.red', '#C23A26', rough=0.6)
    blue = M.solid('mbox.blue', '#23407A', rough=0.6)
    strike = M.solid('mbox.strike', '#5A3322', rough=0.95, micro=(60.0, 0.6))
    L, W, H = 5.6, 3.6, 1.7
    body = geo.box(f'{name}.body', (L, W, H), (0, 0, H / 2), bev=0.06, m=card, coll=coll)
    geo.attach(body, root)
    lab = geo.box(f'{name}.label', (L - 0.6, W - 0.6, 0.02), (0, 0, H + 0.005), m=red, coll=coll)
    geo.attach(lab, root)
    band = geo.box(f'{name}.band', (L - 0.6, 0.55, 0.025), (0, -0.4, H + 0.012), m=blue, coll=coll)
    geo.attach(band, root)
    star = cgeo.star(0.55, 0.24, 5, 1.4, 0.55)
    bm = bmesh.new()
    vs = [bm.verts.new((x, z, 0.0)) for x, z in star]
    bm.faces.new(vs)
    so = cgeo.to_object(bm, f'{name}.star', coll, [M.solid('mbox.gold', '#F2C64A', rough=0.4)], sharp=None)
    so.location = (0, 0, H + 0.03)
    geo.attach(so, root, (0.0, 0.0, H + 0.03))
    for sy in (-1, 1):
        st = geo.box(f'{name}.strike{sy}', (L - 0.5, 0.03, H - 0.4), (0, sy * (W / 2 + 0.01), H / 2), m=strike,
                     coll=coll)
        geo.attach(st, root)
    return root


# ------------------------------------------------------------------------------------------------ the firecracker


def firecracker(coll, name='firecracker', *, r=3.1, h=15.5):
    """A big red paper firecracker standing on its origin: red paper tube, gold bands, a crimped paper top with a
    gold cap, a gold star on its front (-Y), and a fuse hole on its front side at z = 3.2. Returns (root, hole
    local point)."""
    root = kit.empty(name, (0, 0, 0), coll, size=2.0)
    paper = M.paper('fc.paper', tint='#D2261C', tile=24)
    gold = M.solid('fc.gold', '#E0B04A', rough=0.28, metal=1.0, micro=(20.0, 0.03))
    tube = geo.lathe(f'{name}.tube', [(r - 0.02, 0.0), (r, 0.12), (r, h - 0.3), (r - 0.05, h)], segs=64, coll=coll,
                     m=paper)
    geo.attach(tube, root)
    for z0, z1 in ((0.9, 1.9), (h - 2.4, h - 1.4)):
        band = geo.lathe(f'{name}.band{z0:.0f}', [(r + 0.035, z0), (r + 0.05, z0 + 0.05), (r + 0.05, z1 - 0.05),
                                                   (r + 0.035, z1)], segs=64, coll=coll, m=gold)
        geo.attach(band, root)
    # crimped paper top: a low cone with folds (a wobbly profile around), and a gold disc cap
    bm = bmesh.new()
    segs, rings = 48, 6
    rows = []
    for k in range(rings + 1):
        u = k / rings
        rr = r * (1 - u * 0.92)
        row = []
        for j in range(segs):
            a = 2 * math.pi * j / segs
            fold = 1.0 + 0.06 * math.sin(12 * a) * (1 - u) * u * 4
            row.append(bm.verts.new((rr * fold * math.cos(a), rr * fold * math.sin(a), h - 0.05 + 1.3 * u ** 0.8)))
        rows.append(row)
    for k in range(rings):
        for j in range(segs):
            j2 = (j + 1) % segs
            bm.faces.new((rows[k][j], rows[k][j2], rows[k + 1][j2], rows[k + 1][j]))
    bm.faces.new(rows[-1])
    top = cgeo.to_object(bm, f'{name}.top', coll, [paper], sharp=None)
    geo.attach(top, root)
    cap = geo.lathe(f'{name}.cap', [(0.0, h + 1.28), (0.34, h + 1.28), (0.36, h + 1.4), (0.0, h + 1.45)], segs=32,
                    coll=coll, m=gold)
    geo.attach(cap, root)
    # a gold star on the front
    star = cgeo.star(1.35, 0.58, 5, 0.0, 0.0)
    bm = bmesh.new()
    vs = [bm.verts.new((x, 0.0, z)) for x, z in star]
    f = bm.faces.new(list(reversed(vs)))
    bmesh.ops.solidify(bm, geom=[f], thickness=0.03)
    star_m = M.solid('fc.gold.star', '#E0B04A', rough=0.5, metal=0.6, emit='#FFB84A', emit_strength=0.15)
    so = cgeo.to_object(bm, f'{name}.star', coll, [star_m], sharp=None)     # less mirror-like: reads gold in the dark
    # wrap it onto the tube: place it on the front at mid height, slightly proud
    geo.attach(so, root, (0.0, -r - 0.03, h * 0.55), (0, 0, 0))
    # the fuse hole: a dark ring on the front side, low
    hz = 3.2
    ring = geo.lathe(f'{name}.hole', [(0.0, 0.0), (0.26, 0.0), (0.33, 0.06), (0.26, 0.08), (0.0, 0.08)], segs=20,
                     coll=coll, m=M.solid('fc.hole', '#1A0C0A', rough=0.9))
    geo.attach(ring, root, (0.0, -r + 0.02, hz), (math.radians(90), 0, 0))
    return root, V((0.0, -r - 0.05, hz))


# ------------------------------------------------------------------------------------------------ the club


def ruler_material(name, wood='#D9B77A', ink='#1E1812'):
    """A wooden ruler: maple with grain, black ticks every 0.5 cm (long every 1 cm, longest every 5 cm) along its
    local X, printed on the top face near the front edge (local -Y). No numbers."""
    if name in bpy.data.materials:
        return bpy.data.materials[name]
    m, _ = M.new_mat(name)
    nt = m.node_tree
    b = M.principled(m)
    tc = M.node(nt, 'ShaderNodeTexCoord', (-1400, 0))
    sep = M.node(nt, 'ShaderNodeSeparateXYZ', (-1200, 0))
    M.link(nt, M.sout(tc, 'Object'), M.sin(sep, 'Vector'))
    # grain: stretched noise along X
    mp = M.node(nt, 'ShaderNodeMapping', (-1200, 300))
    M.setin(mp, 'Scale', (0.25, 6.0, 6.0))
    M.link(nt, M.sout(tc, 'Object'), M.sin(mp, 'Vector'))
    nz = M.node(nt, 'ShaderNodeTexNoise', (-1000, 300))
    M.setin(nz, 'Scale', 2.5)
    M.setin(nz, 'Detail', 6.0)
    M.link(nt, M.sout(mp, 'Vector'), M.sin(nz, 'Vector'))
    gr = M.node(nt, 'ShaderNodeMix', (-800, 300), data_type='RGBA', blend_type='MIX')
    M.link(nt, M.sout(nz, 'Factor'), M.sin(gr, 'Factor', 'VALUE'))
    M.setin(gr, 'A', M.col(wood), 'RGBA')
    M.setin(gr, 'B', M.col('#B8925A'), 'RGBA')

    def math_node(op, a=None, bv=None, loc=(0, 0)):
        n = M.node(nt, 'ShaderNodeMath', loc, operation=op)
        for i, v in enumerate((a, bv)):
            if v is None:
                continue
            if isinstance(v, (int, float)):
                n.inputs[i].default_value = v
            else:
                M.link(nt, v, n.inputs[i])
        return n.outputs[0]
    x = sep.outputs['X']
    y = sep.outputs['Y']
    # distance to the nearest half-cm tick: |fract(x*2 + 0.5) - 0.5| / 2
    fr = math_node('FRACT', math_node('ADD', math_node('MULTIPLY', x, 2.0, (-1000, -100)), 0.5, (-900, -100)),
                   None, (-800, -100))
    dist = math_node('ABSOLUTE', math_node('SUBTRACT', fr, 0.5, (-700, -100)), None, (-600, -100))
    line = math_node('LESS_THAN', dist, 0.022, (-500, -100))
    # tick length: 0.35 (half), 0.6 (cm), 0.9 (5 cm): from the front edge (y = -w/2)
    cmf = math_node('FRACT', math_node('ADD', x, 0.25, (-1000, -300)), None, (-900, -300))
    is_cm = math_node('LESS_THAN', math_node('ABSOLUTE', math_node('SUBTRACT', cmf, 0.25, (-800, -300)), None,
                                            (-700, -300)), 0.1, (-600, -300))
    f5 = math_node('FRACT', math_node('ADD', math_node('DIVIDE', x, 5.0, (-1000, -450)), 0.05, (-900, -450)), None,
                   (-800, -450))
    is5 = math_node('LESS_THAN', f5, 0.1, (-700, -450))
    ln = math_node('ADD', math_node('ADD', 0.35, math_node('MULTIPLY', is_cm, 0.3, (-500, -300)), (-400, -300)),
                   math_node('MULTIPLY', is5, 0.35, (-500, -450)), (-300, -350))
    edge = M.node(nt, 'ShaderNodeValue', (-1000, -600))
    edge.outputs[0].default_value = -1.35
    from_edge = math_node('SUBTRACT', y, edge.outputs[0], (-800, -600))
    in_len = math_node('LESS_THAN', from_edge, ln, (-200, -400))
    tick = math_node('MULTIPLY', line, in_len, (-100, -200))
    # only on the top face
    nrm = M.node(nt, 'ShaderNodeNewGeometry', (-1000, -800))
    sepn = M.node(nt, 'ShaderNodeSeparateXYZ', (-800, -800))
    M.link(nt, M.sout(nrm, 'Normal'), M.sin(sepn, 'Vector'))
    up = math_node('GREATER_THAN', sepn.outputs['Z'], 0.9, (-600, -800))
    tick = math_node('MULTIPLY', tick, up, (0, -300))
    fin = M.node(nt, 'ShaderNodeMix', (200, 200), data_type='RGBA', blend_type='MIX')
    M.link(nt, tick, M.sin(fin, 'Factor', 'VALUE'))
    M.link(nt, M.sout(gr, 'Result', 'RGBA'), M.sin(fin, 'A', 'RGBA'))
    M.setin(fin, 'B', M.col(ink), 'RGBA')
    M.link(nt, M.sout(fin, 'Result', 'RGBA'), b.inputs['Base Color'])
    M.setin(b, 'Roughness', 0.42)
    M.setin(b, 'Coat Weight', 0.5)
    M.setin(b, 'Coat Roughness', 0.18)
    m.diffuse_color = M.col(wood)
    return m


def rulers(coll, center, *, length=30.0, width=2.7, thick=0.3, rot_deg=0.0):
    """Two rulers crossed at right angles at center (the axes): one along X (on the desk), one along Y on top of
    it. Their zero ends meet near the crossing so they read as x and y axes. Returns (rx, ry, top z)."""
    c = V(center)
    m = ruler_material('club.ruler')
    rx = geo.box('club.ruler.x', (length, width, thick), (0, 0, 0), bev=0.04, m=m, coll=coll)
    ry = geo.box('club.ruler.y', (length, width, thick), (0, 0, 0), bev=0.04, m=m, coll=coll)
    a = math.radians(rot_deg)
    off = length / 2 - 3.0
    rx.location = c + V((math.cos(a) * off, math.sin(a) * off, thick / 2))
    rx.rotation_euler = (0, 0, a)
    ry.location = c + V((-math.sin(a) * off, math.cos(a) * off, thick * 1.5))
    ry.rotation_euler = (0, 0, a + math.pi / 2)
    # the upright ruler bridges over the flat one: tilt it a hair so its far end rests on the desk
    return rx, ry, thick * 2


def spool(coll, loc, *, r=1.75, core=1.2, h=3.2, thread='#2B4FB8'):
    """A wooden thread spool (the stool): two flanges and a core wound with thread. Origin at its bottom."""
    root = kit.empty('club.spool', tuple(loc), coll, size=1.0)
    wood = M.solid('club.spool.wood', '#C9A36B', rough=0.5, coat=0.3, micro=(10.0, 0.03))
    fl = 0.32
    for z0 in (0.0, h - fl):
        f = geo.lathe(f'club.spool.flange{z0:.1f}', [(0.0, z0), (r - 0.08, z0), (r, z0 + 0.08), (r, z0 + fl - 0.08),
                                                     (r - 0.08, z0 + fl), (0.0, z0 + fl)], segs=48, coll=coll, m=wood)
        geo.attach(f, root)
    # thread: a wave texture of fine grooves around the core
    tm, fresh = M.new_mat('club.spool.thread')
    if fresh:
        nt = tm.node_tree
        b = M.principled(tm)
        tc = M.node(nt, 'ShaderNodeTexCoord', (-800, 0))
        wv = M.node(nt, 'ShaderNodeTexWave', (-600, 0), wave_type='BANDS', bands_direction='Z')
        M.setin(wv, 'Scale', 22.0)
        M.setin(wv, 'Distortion', 0.6)
        M.link(nt, M.sout(tc, 'Object'), M.sin(wv, 'Vector'))
        bp = M.node(nt, 'ShaderNodeBump', (-300, -100))
        M.setin(bp, 'Strength', 0.5)
        M.setin(bp, 'Distance', 0.02)
        M.link(nt, M.sout(wv, 'Color'), M.sin(bp, 'Height'))
        M.link(nt, M.sout(bp, 'Normal'), b.inputs['Normal'])
        M.setin(b, 'Base Color', M.col(thread))
        M.setin(b, 'Roughness', 0.55)
        M.setin(b, 'Sheen Weight', 0.8)
        tm.diffuse_color = M.col(thread)
    th = geo.lathe('club.spool.thread', [(core, fl), (core + 0.28, fl + 0.05), (core + 0.32, h / 2),
                                         (core + 0.28, h - fl - 0.05), (core, h - fl)], segs=48, coll=coll, m=tm)
    geo.attach(th, root)
    return root, h


def guitar(coll, name='guitar'):
    """A small cherry-red semi-hollow blues guitar (about 11.5 cm): body in local XZ (face toward -Y), neck along
    +X. Origin at the body's centre. Returns the root Empty."""
    root = kit.empty(name, (0, 0, 0), coll, size=1.0)
    cherry = M.solid('gtr.cherry', '#8E1414', rough=0.18, coat=1.0, coat_rough=0.04, sss=0.0)
    cream = M.solid('gtr.cream', '#EDE4C8', rough=0.35, coat=0.6)
    dark = M.solid('gtr.rosewood', '#2A1A12', rough=0.6)
    chrome = M.chrome('gtr.chrome')
    black = M.solid('gtr.black', '#0D0C0C', rough=0.35, coat=0.5)
    # body outline: two lobes (upper bout small, lower bout large) along X
    pts = []
    n = 72
    for k in range(n):
        a = 2 * math.pi * k / n
        x = math.cos(a)
        z = math.sin(a)
        # width varies along x: lower bout (x<0) wider, a waist near x=0.15
        w = 1.0 - 0.18 * math.exp(-((x - 0.12) / 0.28) ** 2) - 0.12 * max(0.0, x) ** 2
        pts.append((2.3 * x - 0.1, 1.75 * z * w))
    bm = bmesh.new()
    th = 0.75
    vs = [bm.verts.new((x, -th / 2, z)) for x, z in pts]
    f = bm.faces.new(list(reversed(vs)))
    ext = bmesh.ops.extrude_face_region(bm, geom=[f])
    top = [e for e in ext['geom'] if isinstance(e, bmesh.types.BMVert)]
    bmesh.ops.translate(bm, verts=top, vec=(0, th, 0))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    body = cgeo.to_object(bm, f'{name}.body', coll, [cherry], sharp=50.0)
    bv = body.modifiers.new('bevel', 'BEVEL')
    bv.width, bv.segments = 0.12, 3
    geo.attach(body, root)
    # binding: a thin cream lip around the front edge
    bpts = [(x * 1.005, -th / 2 - 0.01, z * 1.005) for x, z in pts] + [(pts[0][0] * 1.005, -th / 2 - 0.01,
                                                                        pts[0][1] * 1.005)]
    bo = geo.curve_tube(f'{name}.binding', bpts, 0.045, coll=coll, m=cream, res=2, bevel_res=2, to_mesh=True)
    geo.attach(bo, root)
    # f-holes (dark slots), pickups, bridge, knobs
    for sx in (-1, 1):
        fh = geo.box(f'{name}.fhole{sx}', (0.16, 0.02, 0.85), (0.2, -th / 2 - 0.005, sx * 0.85), m=black, coll=coll)
        fh.rotation_euler = (0, math.radians(12 * sx), 0)
        geo.attach(fh, root, (0.25, -th / 2 - 0.005, sx * 0.85), (0, math.radians(12 * sx), 0))   # inside the binding
    for i, px in enumerate((0.55, -0.35)):
        pk = geo.box(f'{name}.pickup{i}', (0.42, 0.14, 1.05), (0, 0, 0), bev=0.03, m=chrome, coll=coll)
        geo.attach(pk, root, (px, -th / 2 - 0.06, 0.0))
    br = geo.box(f'{name}.bridge', (0.16, 0.14, 1.0), (0, 0, 0), bev=0.02, m=chrome, coll=coll)
    geo.attach(br, root, (-1.05, -th / 2 - 0.06, 0.0))
    tp = geo.box(f'{name}.tail', (0.22, 0.1, 0.9), (0, 0, 0), bev=0.03, m=chrome, coll=coll)
    geo.attach(tp, root, (-1.6, -th / 2 - 0.04, 0.0))
    for i, (kx, kz) in enumerate(((-1.35, -1.1), (-0.95, -1.3), (-1.75, -0.7), (-1.5, -0.35))):
        kb = geo.lathe(f'{name}.knob{i}', [(0.0, 0.0), (0.13, 0.0), (0.12, 0.14), (0.0, 0.16)], segs=16, coll=coll,
                       m=M.solid('gtr.gold', '#D8B050', rough=0.3, metal=1.0))
        geo.attach(kb, root, (kx, -th / 2, kz), (math.radians(90), 0, 0))
    # neck, fretboard, frets, headstock, tuners
    nl = 5.0
    neck = geo.box(f'{name}.neck', (nl, 0.34, 0.5), (0, 0, 0), bev=0.08, m=cherry, coll=coll)
    geo.attach(neck, root, (2.0 + nl / 2, 0.02, 0.0))
    fb = geo.box(f'{name}.fret', (nl + 0.3, 0.08, 0.52), (0, 0, 0), bev=0.01, m=dark, coll=coll)
    geo.attach(fb, root, (1.85 + nl / 2, -0.19, 0.0))
    for k in range(12):
        x = 1.95 + nl * (1 - 2 ** (-k / 12 * 1.8)) * 1.05
        fr = geo.box(f'{name}.fret{k}', (0.02, 0.03, 0.5), (0, 0, 0), m=chrome, coll=coll)
        geo.attach(fr, root, (x, -0.24, 0.0))
    hs = geo.box(f'{name}.head', (1.35, 0.16, 0.78), (0, 0, 0), bev=0.1, m=black, coll=coll)
    geo.attach(hs, root, (2.05 + nl + 0.62, 0.0, 0.0), (0, math.radians(-6), 0))
    for i in range(3):
        for sz in (-1, 1):
            tu = geo.lathe(f'{name}.tuner{i}{sz}', [(0.0, 0.0), (0.06, 0.0), (0.06, 0.28), (0.1, 0.3), (0.1, 0.38),
                                                   (0.0, 0.4)], segs=12, coll=coll, m=chrome)
            geo.attach(tu, root, (2.05 + nl + 0.3 + i * 0.36, 0.0, sz * 0.36), (math.radians(-90 * sz), 0, 0))
    # strings: six thin lines from the tailpiece to the nut
    for k in range(6):
        z = -0.2 + 0.08 * k
        s = geo.curve_tube(f'{name}.string{k}', [(-1.6, -th / 2 - 0.1, z * 1.3), (2.05 + nl, -0.26, z)], 0.008,
                           coll=coll, m=chrome, res=1, bevel_res=1, to_mesh=True)
        geo.attach(s, root)
    return root


def bar_cup(coll, loc, *, r=3.0, h=6.6, away=None):
    """The bar: a squat brushed-steel pencil cup with a few pencils. Origin at its bottom centre. away: a world
    azimuth (deg) the pencils lean toward (spread 45 deg either side), e.g. away from someone standing at the cup."""
    from pdoom.sets import props as SP
    root = kit.empty('club.bar', tuple(loc), coll, size=1.0)
    cupm = M.brushed('club.bar.metal', '#44484C', rough=(0.25, 0.45), tile=18, val=0.8)
    prof = geo.rounded_profile([(0.0, 0.0), (r - 0.1, 0.0), (r, 0.2), (r, h - 0.2), (r + 0.08, h - 0.08),
                                (r - 0.1, h), (r - 0.2, h - 0.2), (r - 0.2, 0.45), (0.0, 0.45)], 0.07, 2)
    cup = geo.lathe('club.bar.cup', prof, segs=64, coll=coll, m=cupm)
    geo.attach(cup, root)
    azs = (130, 200, 250) if away is None else (away - 45.0, away, away + 45.0)
    for i, (paint, tilt, az) in enumerate(zip(('#F2C230', '#3A6FC8', '#D84A3A'), (11, 8, 14), azs)):
        pc = SP.build_pencil(coll, f'club.pencil{i}', paint, length=9.5)
        piv = kit.empty(f'club.pencil{i}.piv', (0, 0, 0), coll, size=0.5)
        a = math.radians(az)
        geo.attach(piv, root, (1.2 * math.cos(a), 1.2 * math.sin(a), 0.5),
                   (math.radians(tilt) * -math.sin(a), math.radians(tilt) * math.cos(a), math.radians(i * 47)))
        geo.attach(pc, piv, (0, 0, 0))
    return root, h


def whisky(coll, name='club.glass', *, r=0.42, h=0.78):
    """A tiny whisky tumbler with an amber finger of whisky. Origin at its bottom centre."""
    root = kit.empty(name, (0, 0, 0), coll, size=0.3)
    gl = M.glass('club.glass.mat', tint='#E8C9A0', rough=0.03)       # amber-tinted so it reads in the blue light
    g = geo.lathe(f'{name}.glass', [(0.0, 0.0), (r - 0.03, 0.0), (r, 0.03), (r * 1.04, h), (r * 1.04 - 0.035, h),
                                    (r - 0.04, 0.14), (0.0, 0.14)], segs=32, coll=coll, m=gl)
    geo.attach(g, root)
    liq = M.solid('club.whisky', '#B8641A', rough=0.05, sss=0.4, sss_radius=(1.0, 0.5, 0.2))
    lq = geo.lathe(f'{name}.whisky', [(0.0, 0.15), (r - 0.05, 0.15), (r - 0.04, 0.42), (0.0, 0.42)], segs=32,
                   coll=coll, m=liq)
    geo.attach(lq, root)
    return root


def tealight(coll, loc, *, r=1.9, h=1.6):
    """A tealight in its aluminium cup; returns (root, flame base world point)."""
    root = kit.empty('club.tealight', tuple(loc), coll, size=0.5)
    alu = M.solid('club.alu', '#C8CCD0', rough=0.3, metal=1.0)
    wax = M.solid('club.wax', '#F4EEE0', rough=0.5, sss=0.6, sss_radius=(1.0, 0.8, 0.6))
    cup = geo.lathe('club.tealight.cup', [(0.0, 0.0), (r, 0.0), (r + 0.05, h), (r - 0.04, h), (r - 0.05, 0.08),
                                          (0.0, 0.08)], segs=40, coll=coll, m=alu)
    geo.attach(cup, root)
    wx = geo.lathe('club.tealight.wax', [(0.0, 0.08), (r - 0.06, 0.08), (r - 0.06, h - 0.25), (0.0, h - 0.35)],
                   segs=40, coll=coll, m=wax)
    geo.attach(wx, root)
    wick = geo.box('club.tealight.wick', (0.06, 0.06, 0.4), (0, 0, 0), m=M.solid('club.wick', '#141010', rough=0.9),
                   coll=coll)
    geo.attach(wick, root, (0.0, 0.0, h - 0.2))
    return root, V(loc) + V((0, 0, h + 0.05))


# ------------------------------------------------------------------------------------------------ the word "fuse"
# The fuse cord is laid across the mound's front slope in joined script so it reads "fuse" (revision 2: the lyrics in
# the picture); the spark writes the word in fire as it is sung. The script is one continuous pen stroke (units of
# x-height: baseline y = 0, x-height y = 1), entered from the upper right over the f's crook (the lead-in from the
# match comes down that way), and it leaves the e to the right.

CURSIVE_FUSE = [
    # f: over the crook, down the stem, round the descender loop and back up to the baseline
    (1.28, 2.66), (1.1, 2.56), (0.9, 2.46), (0.72, 2.36), (0.6, 2.12), (0.54, 1.5), (0.48, 0.7), (0.43, -0.1),
    (0.39, -0.75), (0.41, -1.12), (0.53, -1.2), (0.65, -1.0), (0.73, -0.55), (0.83, -0.08), (0.99, 0.2), (1.15, 0.38),
    # u
    (1.26, 0.7), (1.32, 1.0), (1.34, 0.55), (1.40, 0.15), (1.55, 0.0), (1.72, 0.1), (1.84, 0.45), (1.92, 1.0),
    (1.92, 0.55), (1.95, 0.15), (2.07, 0.0), (2.22, 0.14),
    # s
    (2.38, 0.55), (2.5, 1.02), (2.62, 0.72), (2.72, 0.42), (2.69, 0.14), (2.54, 0.0), (2.40, 0.04), (2.42, 0.14),
    (2.62, 0.08), (2.82, 0.22),
    # e, and away to the right
    (2.98, 0.42), (3.12, 0.72), (3.08, 0.94), (2.96, 0.9), (2.9, 0.62), (2.92, 0.26), (3.04, 0.04), (3.24, 0.04),
    (3.46, 0.2), (3.7, 0.3),
]
WORD_END = len(CURSIVE_FUSE) - 2          # the e's last point (after it the cord is just a cord)

# Revision 3 (no lyrics in the picture): the cord just snakes down the slope in loose S-bends over the same ground,
# with the same entry over the edge and the same exit to the right, so the lead-in, the burn timing and F4 still fit.
SNAKE = [(1.28, 2.66), (1.1, 2.52), (0.88, 2.3), (0.74, 1.98), (0.8, 1.66), (1.08, 1.44), (1.5, 1.34), (1.9, 1.24),
         (2.16, 1.0), (2.18, 0.68), (1.96, 0.42), (1.6, 0.26), (1.3, 0.04), (1.26, -0.3), (1.5, -0.56), (1.95, -0.62),
         (2.45, -0.44), (2.85, -0.14), (3.2, 0.12), (3.46, 0.22), (3.7, 0.3)]
SNAKE_END = len(SNAKE) - 2


def catmull2(pts, n=10):
    out = []
    for i in range(len(pts) - 1):
        p0 = pts[i - 1] if i > 0 else pts[i]
        p1, p2 = pts[i], pts[i + 1]
        p3 = pts[i + 2] if i + 2 < len(pts) else pts[i + 1]
        for k in range(n):
            t = k / n
            t2, t3 = t * t, t * t * t
            out.append(tuple(0.5 * (2 * p1[j] + (-p0[j] + p2[j]) * t + (2 * p0[j] - 5 * p1[j] + 4 * p2[j] - p3[j]) * t2
                                    + (-p0[j] + 3 * p1[j] - 3 * p2[j] + p3[j]) * t3) for j in range(2)))
    out.append(pts[-1])
    return out


def land_hit(origin, direction, *, clear=1.15, far=300.0, step=0.25):
    """First point where a ray from origin meets the clip landscape (core height + clear)."""
    o, d = V(origin), V(direction).normalized()
    prev_t = 0.0
    t = step
    while t < far:
        p = o + d * t
        f = p.z - (height(p.x, p.y) + clear)
        if f <= 0.0:
            a, b = prev_t, t
            for _ in range(30):
                m = 0.5 * (a + b)
                q = o + d * m
                if q.z - (height(q.x, q.y) + clear) > 0:
                    a = m
                else:
                    b = m
            return o + d * b
        prev_t = t
        t += step
    return None


def project_word(pts2d, cam_loc, base, right, up, k, *, clear=1.15):
    """Project 2D script points (x-height units) from a camera position onto the landscape: the point (u, v) sits at
    base + right * u * k + up * v * k on a plane through `base`, and is cast along the ray from the camera. Seen
    from that camera the cord reads as the designed script; from nearby it looks written on the slope."""
    out = []
    c = V(cam_loc)
    for u, v in pts2d:
        p = V(base) + V(right) * (u * k) + V(up) * (v * k)
        h = land_hit(c, p - c, clear=clear)
        out.append(h if h is not None else p)
    return out


def profile_keys(keys):
    """s(t) through (t, s) keys: monotone cubic (Fritsch-Carlson), flat before the first and after the last key."""
    ts = [k[0] for k in keys]
    ss = [k[1] for k in keys]
    n = len(keys)
    d = [(ss[i + 1] - ss[i]) / (ts[i + 1] - ts[i]) for i in range(n - 1)]
    m = [d[0]] + [0.5 * (d[i - 1] + d[i]) for i in range(1, n - 1)] + [d[-1]]
    for i in range(n - 1):
        if d[i] == 0:
            m[i] = m[i + 1] = 0.0
        else:
            a, b = m[i] / d[i], m[i + 1] / d[i]
            h = a * a + b * b
            if h > 9.0:
                tau = 3.0 / math.sqrt(h)
                m[i], m[i + 1] = tau * a * d[i], tau * b * d[i]

    def s_of(t):
        if t <= ts[0]:
            return ss[0]
        if t >= ts[-1]:
            return ss[-1]
        i = max(j for j in range(n - 1) if ts[j] <= t)
        hh = ts[i + 1] - ts[i]
        x = (t - ts[i]) / hh
        h00, h10 = 2 * x ** 3 - 3 * x ** 2 + 1, x ** 3 - 2 * x ** 2 + x
        h01, h11 = -2 * x ** 3 + 3 * x ** 2, x ** 3 - x ** 2
        return h00 * ss[i] + h10 * hh * m[i] + h01 * ss[i + 1] + h11 * hh * m[i + 1]
    return s_of


def polyline_length(pts):
    return sum((b - a).length for a, b in zip(pts, pts[1:]))
