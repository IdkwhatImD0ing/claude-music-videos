"""singularity: the black hole on the desk and its accretion disc.

Parts (all children of `Hole.root`, which scales the whole thing open and shut):
  horizon   a pure black sphere (radius RH)
  lens      a camera-facing refracting annulus behind the photon ring (screen-space raytraced refraction with a
            bent shading normal): the desk and the train behind the hole warp around the shadow
  disc      a flared annulus with an emissive swirl shader: white-hot inside, orange, deep red outside; the pattern
            turns with Keplerian speed (inner faster), so streaks wind up into orbits
  halo      a camera-facing billboard: the thin photon ring plus the lensed image of the disc's far side, which
            arches over and under the shadow when the disc is seen edge-on (Interstellar)
  light     a warm point light at the centre (the disc's glow on the desk)

`debris()` makes the accretion debris as one geometry-nodes point cloud (paper confetti, dust, embers, bits): every
particle lies on the desk (or waits unseen) until its capture time, spirals up into a circular orbit and heats up
near the inner edge; `Collapse` sucks everything into the centre. `orbit()` is the same maths in Python for hero
objects (sticky notes, clips, track pieces) that are keyed per frame. Everything is a pure function of song time.
"""
from __future__ import annotations

import math

import bmesh
import bpy
import numpy as np
from mathutils import Vector

from pdoom import kit
from pdoom import timing as tm
from pdoom.fx import _nodes as N
from pdoom.sets import geo

FPS = tm.FPS
TREF = 42.3            # reference time of the orbit phases


# ------------------------------------------------------------------------------------------------ keying


def fast_keys(idb, path, frames, values, *, index=0, interp='LINEAR', owner_name='sing'):
    """Write an F-curve in one go (much faster than keyframe_insert per frame). interp: CONSTANT | LINEAR."""
    ad = idb.animation_data or idb.animation_data_create()
    if ad.action is None:
        ad.action = bpy.data.actions.new(f'{owner_name}:{idb.name}')
    fc = ad.action.fcurve_ensure_for_datablock(idb, path, index=index)
    kp = fc.keyframe_points
    kp.clear()
    kp.add(len(frames))
    kp.foreach_set('co', [c for f, v in zip(frames, values) for c in (f, v)])
    kp.foreach_set('interpolation', [0 if interp == 'CONSTANT' else 1] * len(frames))
    fc.update()
    return fc


def key_matrices(obj, times, mats, *, interp='LINEAR', scale=True, frames=None):
    """Key obj's location / rotation (Euler, unwrapped) / scale from world-ish matrices (in obj's parent space)."""
    frames = frames if frames is not None else [t * FPS for t in times]
    L, R, S = [], [], []
    prev = None
    for Mt in mats:
        loc, rot, sca = Mt.decompose()
        e = rot.to_euler('XYZ', prev) if prev is not None else rot.to_euler('XYZ')
        prev = e
        L.append(loc)
        R.append(e)
        S.append(sca)
    obj.rotation_mode = 'XYZ'
    for i in range(3):
        fast_keys(obj, 'location', frames, [v[i] for v in L], index=i, interp=interp)
        fast_keys(obj, 'rotation_euler', frames, [v[i] for v in R], index=i, interp=interp)
        if scale:
            fast_keys(obj, 'scale', frames, [v[i] for v in S], index=i, interp=interp)


def key_value(owner, prop, fn, t0, t1, *, index=-1, interp='LINEAR', step=1):
    """owner.prop = fn(t) on every frame of [t0, t1] (fast writer; owner may be a socket, a light, an object)."""
    f0, f1 = int(math.floor(t0 * FPS)) - 1, int(math.ceil(t1 * FPS)) + 1
    frames = list(range(f0, f1 + 1, step))
    vals = [fn(f / FPS) for f in frames]
    idb = owner.id_data
    try:
        full = owner.path_from_id(prop)
    except Exception:
        full = prop
    if index >= 0:
        getattr(owner, prop)[index] = vals[0]
    else:
        setattr(owner, prop, vals[0])
    return fast_keys(idb, full, [float(f) for f in frames], vals, index=max(index, 0), interp=interp)


def key_vec(owner, prop, fn, t0, t1, n=3, **kw):
    for i in range(n):
        key_value(owner, prop, lambda t, i=i: fn(t)[i], t0, t1, index=i, **kw)


def smooth(x, a, b):
    return tm.smooth(x, a, b)


# ------------------------------------------------------------------------------------------------ shader maths


class ShTree(N.Tree):
    """The geometry-node expression builder reused on a material's node tree (Math, Vector Math, Map Range, Noise,
    Combine/Separate XYZ are shared node types). time() is a Value node keyed to song seconds."""

    def __init__(self, nt):
        self.ng = nt
        self.n = 0
        self._time = None
        self._sep_cache = {}

    def time(self):
        if self._time is None:
            nd = self.node('ShaderNodeValue')
            nd.label = 'song time'
            s = nd.outputs[0]
            geo.keyp(s, 'default_value', 0.0, 0.0, interp='LINEAR')
            geo.keyp(s, 'default_value', 200.0, 200.0, interp='LINEAR')
            self._time = self.out(nd)
        return self._time

    def value(self, v, label=''):
        nd = self.node('ShaderNodeValue')
        nd.outputs[0].default_value = v
        nd.label = nd.name = label or nd.name
        return self.out(nd), nd.outputs[0]

    def atan2(self, y, x):
        return self.op('ARCTAN2', y, x)

    def ramp(self, fac, stops):
        nd = self.node('ShaderNodeValToRGB')
        cr = nd.color_ramp
        cr.interpolation = 'B_SPLINE'
        while len(cr.elements) > 2:
            cr.elements.remove(cr.elements[-1])
        for i, (p, c) in enumerate(stops):
            e = cr.elements[i] if i < 2 else cr.elements.new(p)
            e.position = p
            e.color = kit.srgb(c) if isinstance(c, str) else c
        self.feed(nd.inputs['Fac'], fac)
        return self.out(nd, 'Color')

    def attribute(self, name, kind='INSTANCER', out='Fac'):
        nd = self.node('ShaderNodeAttribute', attribute_type=kind, attribute_name=name)
        return self.out(nd, out)


def new_material(name):
    m = bpy.data.materials.new(name)
    try:
        m.use_nodes = True
    except Exception:
        pass
    nt = m.node_tree
    for nd in list(nt.nodes):
        nt.nodes.remove(nd)
    out = nt.nodes.new('ShaderNodeOutputMaterial')
    out.location = (1600, 0)
    return m, nt, out


def glow_output(g: ShTree, out, color, strength, alpha):
    """Emission with alpha (Mix of Transparent and Emission) into the material output."""
    em = g.node('ShaderNodeEmission')
    g.feed(em.inputs['Color'], color)
    g.feed(em.inputs['Strength'], strength)
    tr = g.node('ShaderNodeBsdfTransparent')
    mx = g.node('ShaderNodeMixShader')
    g.feed(mx.inputs[0], alpha)
    g.ng.links.new(tr.outputs[0], mx.inputs[1])
    g.ng.links.new(em.outputs[0], mx.inputs[2])
    g.ng.links.new(mx.outputs[0], out.inputs['Surface'])


# ------------------------------------------------------------------------------------------------ the hole


class Hole:
    """The black hole at `center` (world cm). rh: horizon radius. All parts hang off .root (scale it with open()).

    Handles: .root, .horizon, .shell, .disc, .halo, .light, .sock (keyable shader sockets: 'disc', 'halo', 'edge',
    'ring', 'spin'), .face(follower) points the billboard at a camera-following Empty."""

    def __init__(self, coll, center, rh=2.3, *, shell=3.6, disc=(1.55, 4.1), ior=1.6, light=True):
        self.C = Vector(center)
        self.RH = rh
        self.coll = coll
        self.sock = {}
        self.root = geo.empty('hole', tuple(self.C), coll, 2.0, 'SPHERE')
        self._horizon()
        self._disc(rh * disc[0], rh * disc[1])
        self._halo()
        self._lens(rh * shell, ior)
        self.light = None
        if light:
            self.light = kit.point('hole.light', tuple(self.C), power=0.0, radius=2.5, color='#FF9A48', coll=coll)
            geo.attach(self.light, self.root, (0, 0, 0))
            # under-light: the disc's glow on the desk beneath (no shadow, so the hole doesn't block it)
            self.under = kit.point('hole.under', tuple(self.C), power=0.0, radius=4.0, color='#FF8A3A', coll=coll)
            self.under.data.use_shadow = False
            geo.attach(self.under, self.root, (0, 0, -1.2))
            for lo in (self.light, self.under):      # no highlight of the light inside the lensing shell
                for attr in ('transmission_factor', 'specular_factor'):
                    try:
                        setattr(lo.data, attr, 0.0)
                    except Exception:
                        pass

    # -------------------------------------------------------------------------------------------- parts
    def _horizon(self):
        m, nt, out = new_material('hole.horizon')
        em = nt.nodes.new('ShaderNodeEmission')
        em.inputs['Color'].default_value = (0, 0, 0, 1)
        em.inputs['Strength'].default_value = 0.0
        nt.links.new(em.outputs[0], out.inputs['Surface'])
        bm = bmesh.new()
        bmesh.ops.create_uvsphere(bm, u_segments=64, v_segments=32, radius=self.RH)
        for f in bm.faces:
            f.smooth = True
        me = bpy.data.meshes.new('hole.horizon')
        bm.to_mesh(me)
        bm.free()
        me.materials.append(m)
        ob = bpy.data.objects.new('hole.horizon', me)
        self.coll.objects.link(ob)
        geo.attach(ob, self.root)
        ob.visible_shadow = False
        self.horizon = ob

    def _lens(self, rs, ior):
        """The gravitational lens: a camera-facing annulus (a child of the halo billboard, just behind it) that
        refracts what lies behind the hole. Its shading normal tilts outward by an angle that is largest just
        outside the halo and fades to zero at the rim, so rays bend toward the hole there and not at all at the
        edge: the desk and window behind wrap around the shadow with no visible outline."""
        self.RS = rs
        r_in = self.R2 * 0.92
        m, nt, out = new_material('hole.lens')
        g = ShTree(nt)
        b = g.node('ShaderNodeBsdfPrincipled')
        b.inputs['Base Color'].default_value = (1, 1, 1, 1)
        b.inputs['Roughness'].default_value = 0.0
        b.inputs['Transmission Weight'].default_value = 1.0
        b.inputs['IOR'].default_value = ior
        b.inputs['Specular IOR Level'].default_value = 0.0
        tc = g.node('ShaderNodeTexCoord')
        p = g.out(tc, 'Object')
        rho = g.length(g.vec(p.x, p.y, 0.0)) / rs
        vt = g.node('ShaderNodeVectorTransform', vector_type='VECTOR', convert_from='OBJECT', convert_to='WORLD')
        g.feed(vt.inputs['Vector'], g.vec(p.x, p.y, 0.0))
        radial = g.normalize(g.out(vt, 'Vector'))
        gm = g.node('ShaderNodeNewGeometry')
        I = g.out(gm, 'Incoming')
        k, self.sock['lens'] = g.value(1.0, 'lens')
        r0 = r_in / rs
        # the disc crosses this plane along its horizontal axis: no lens in a band there (refracted rays would start
        # inside the disc and trace black); the bend eases in above and below
        ay = g.abs(p.y)
        tilt = (g.smooth(rho, r0, r0 + 0.1) * g.op('POWER', g.clamp((1.0 - rho) / (1.0 - r0)), 1.6) * k * 1.9 *
                g.smooth(ay, 0.95, 2.4))
        g.feed(b.inputs['Normal'], g.normalize(I + radial * tilt))
        tr = g.node('ShaderNodeBsdfTransparent')
        mx = g.node('ShaderNodeMixShader')
        g.feed(mx.inputs[0], g.smooth(ay, 0.75, 1.1) * (1.0 - g.smooth(rho, 0.72, 0.97)))
        nt.links.new(tr.outputs[0], mx.inputs[1])
        nt.links.new(b.outputs[0], mx.inputs[2])
        nt.links.new(mx.outputs[0], out.inputs['Surface'])
        out.inputs['Thickness'].default_value = 0.0
        for attr, v in (('use_raytrace_refraction', True), ('thickness_mode', 'SLAB'),
                        ('surface_render_method', 'DITHERED'), ('use_backface_culling', True)):
            try:
                setattr(m, attr, v)
            except Exception:
                pass
        self.sock['ior'] = b.inputs['IOR']
        me = bpy.data.meshes.new('hole.lens')
        n, nr = 128, 6
        verts, faces = [], []
        for j in range(nr + 1):
            r = r_in + (rs - r_in) * j / nr
            for i in range(n):
                a = 2 * math.pi * i / n
                verts.append((r * math.cos(a), r * math.sin(a), 0.0))
        for j in range(nr):
            for i in range(n):
                i2 = (i + 1) % n
                faces.append((j * n + i, (j + 1) * n + i, (j + 1) * n + i2, j * n + i2))
        me.from_pydata(verts, [], faces)
        me.update()
        me.materials.append(m)
        ob = bpy.data.objects.new('hole.lens', me)
        self.coll.objects.link(ob)
        geo.attach(ob, self.halo, (0.0, 0.0, -0.12))
        ob.visible_shadow = False
        self.lens = ob

    def _disc(self, r_in, r_out):
        self.r_in, self.r_out = r_in, r_out
        # a flared annulus: thin at the hot inner edge, thicker outside (seen edge-on it's a sliver with some body)
        bm = bmesh.new()
        na, nr = 160, 18
        rings_top, rings_bot = [], []
        for j in range(nr + 1):
            u = j / nr
            r = r_in + (r_out - r_in) * (u ** 1.2)
            h = 0.03 + 0.22 * u * u
            top, bot = [], []
            for i in range(na):
                a = 2 * math.pi * i / na
                top.append(bm.verts.new((r * math.cos(a), r * math.sin(a), h)))
                bot.append(bm.verts.new((r * math.cos(a), r * math.sin(a), -h)))
            rings_top.append(top)
            rings_bot.append(bot)
        for j in range(nr):
            for i in range(na):
                k = (i + 1) % na
                A, B = rings_top[j], rings_top[j + 1]
                bm.faces.new((A[i], A[k], B[k], B[i]))
                A, B = rings_bot[j], rings_bot[j + 1]
                bm.faces.new((A[i], B[i], B[k], A[k]))
        for i in range(na):     # inner lip
            k = (i + 1) % na
            bm.faces.new((rings_top[0][i], rings_bot[0][i], rings_bot[0][k], rings_top[0][k]))
        for f in bm.faces:
            f.smooth = True
        me = bpy.data.meshes.new('hole.disc')
        bm.to_mesh(me)
        bm.free()
        m = self._disc_material(r_in, r_out)
        me.materials.append(m)
        ob = bpy.data.objects.new('hole.disc', me)
        self.coll.objects.link(ob)
        geo.attach(ob, self.root)
        ob.visible_shadow = False
        self.disc = ob

    def _disc_material(self, r_in, r_out):
        m, nt, out = new_material('hole.disc')
        g = ShTree(nt)
        tc = g.node('ShaderNodeTexCoord')
        p = g.out(tc, 'Object')
        x, y = p.x, p.y
        r = g.length(g.vec(x, y, 0.0))
        th = g.atan2(y, x)
        rho = g.clamp((r - r_in) / (r_out - r_in))
        T = g.time() - TREF
        spin, self.sock['spin'] = g.value(1.0, 'spin')
        om = (g.op('POWER', g.max(r, r_in * 0.9) / r_in, -1.5)) * 5.2 * spin        # rad/s, inner edge ~5.2
        ph = th - om * T
        # streaks along the orbit: coarse radial bands x fine angular structure
        q = g.vec(r * 1.7, g.cos(ph) * 2.4, g.sin(ph) * 2.4)
        n1 = g.noise(q, 1.6, 6.0)
        q2 = g.vec(r * 5.5, g.cos(ph) * 1.2, g.sin(ph) * 1.2)
        n2 = g.noise(q2, 2.2, 3.0)
        pat = g.clamp(g.remap(n1, 0.32, 0.72, 0.0, 1.0) * 0.75 + g.remap(n2, 0.35, 0.7, 0.0, 0.6))
        col = g.ramp(rho, [(0.0, '#FFF6E0'), (0.12, '#FFD08A'), (0.35, '#FF8A2E'), (0.7, '#C23A0C'),
                           (1.0, '#4A0A03')])
        bright, self.sock['disc'] = g.value(0.0, 'disc')
        hot = g.op('POWER', 1.0 - rho, 2.4)
        stren = (hot * 26.0 + 1.2) * (pat * 0.85 + 0.25) * bright
        edge_in = g.smooth(rho, 0.0, 0.05)
        edge_out = 1.0 - g.smooth(rho, 0.55, 1.0)
        alpha = g.clamp(edge_in * edge_out * (pat * 0.9 + 0.35) * g.clamp(bright * 3.0))
        glow_output(g, out, col, stren, alpha)
        m.surface_render_method = 'DITHERED'
        m.use_transparent_shadow = True
        return m

    def _halo(self):
        """Camera-facing billboard: the photon ring and the lensed far side of the disc."""
        R1 = self.RH * 1.2
        R2 = self.RH * 2.05
        s = R2 * 1.25
        me = bpy.data.meshes.new('hole.halo')
        n = 96
        verts = [(0.0, 0.0, 0.0)]
        for i in range(n):
            a = 2 * math.pi * i / n
            verts.append((s * math.cos(a), s * math.sin(a), 0.0))
        faces = [(0, 1 + i, 1 + (i + 1) % n) for i in range(n)]
        me.from_pydata(verts, [], faces)
        me.update()
        m, nt, out = new_material('hole.halo')
        g = ShTree(nt)
        tc = g.node('ShaderNodeTexCoord')
        p = g.out(tc, 'Object')
        x, y = p.x, p.y
        r = g.length(g.vec(x, y, 0.0))
        up = g.abs(y) / g.max(r, 1e-3)                    # 1 at top/bottom, 0 at the sides
        T = g.time() - TREF
        th = g.atan2(y, x)
        ph = th - T * 1.6
        n1 = g.noise(g.vec(r * 3.0, g.cos(ph) * 1.8, g.sin(ph) * 1.8), 1.8, 4.0)
        ring_w = 0.09
        ring = g.exp(-((r - R1) / ring_w) * ((r - R1) / ring_w))
        band = g.smooth(r, R1 * 0.98, R1 * 1.12) * (1.0 - g.smooth(r, R1 * 1.25, R2))
        edge, self.sock['edge'] = g.value(1.0, 'edge')
        arch = g.mix(0.45, g.op('POWER', up, 1.6) * 1.25, edge)
        dop, self.sock['dop'] = g.value(0.0, 'dop')          # -1..1: which side is brighter (approaching)
        side = 1.0 + dop * (x / g.max(r, 1e-3)) * 0.55
        halo = band * arch * (g.remap(n1, 0.3, 0.75, 0.25, 1.1)) * side
        hb, self.sock['halo'] = g.value(0.0, 'halo')
        rb, self.sock['ring'] = g.value(0.0, 'ring')
        col = g.mix(g.vec(1.0, 0.42, 0.1), g.vec(1.0, 0.86, 0.6), g.clamp(ring * 1.2 + band * 0.25))
        stren = ring * 42.0 * rb + halo * 14.0 * hb
        alpha = g.clamp(ring * 1.4 * g.clamp(rb * 4.0) + halo * 1.1 * g.clamp(hb * 3.0))
        glow_output(g, out, col, stren, alpha)
        m.surface_render_method = 'DITHERED'
        me.materials.append(m)
        ob = bpy.data.objects.new('hole.halo', me)
        self.coll.objects.link(ob)
        geo.attach(ob, self.root)
        ob.visible_shadow = False
        self.halo = ob
        self.R1, self.R2 = R1, R2

    # -------------------------------------------------------------------------------------------- animation
    def face(self, follower):
        """Point the billboard at an Empty that rides with the live camera."""
        c = self.halo.constraints.new('TRACK_TO')
        c.target = follower
        c.track_axis, c.up_axis = 'TRACK_Z', 'UP_Y'
        return c

    def open(self, size_fn, t0, t1):
        """Key the root's scale (0 = gone) per frame; hide everything while it's ~0."""
        key_vec(self.root, 'scale', lambda t: (max(1e-4, size_fn(t)),) * 3, t0, t1)
        return self


# ------------------------------------------------------------------------------------------------ orbits


def omega(r, k=5.2, r0=3.6):
    """Angular speed (rad/s) of a circular orbit at radius r (Keplerian, matching the disc shader's inner edge)."""
    return k * (max(r, 0.5) / r0) ** -1.5


class Orbit:
    """One captured object's path: rest at (rs, as_, zs) (polar about the hole centre) until ts, spiralling into
    a circular orbit (r, z) over dc seconds (K = extra unwind angle), then orbiting; collapse(t) 0..1 sucks it into
    the centre. Pure function of time."""

    def __init__(self, rs, a_s, zs, ts, dc, r, z, K=2.5, lift=1.5, k=5.2, r0=3.6, collapse=None, fall=None):
        self.rs, self.zs, self.ts, self.dc, self.r, self.z, self.K, self.lift = rs, zs, ts, dc, r, z, K, lift
        self.om = omega(r, k, r0)
        # phase so the spawn angle is a_s at ts
        self.th0 = a_s - self.om * (ts - TREF) + K
        self.collapse = collapse
        self.fall = fall          # optional (t_start, t_end): a slow spiral into the horizon

    def polar(self, t):
        u = min(1.0, max(0.0, (t - self.ts) / self.dc))
        e = u * u * (3 - 2 * u)
        R = self.rs + (self.r - self.rs) * e
        A = self.th0 + self.om * (t - TREF) - self.K * (1 - u) ** 2
        Z = self.zs + (self.z - self.zs) * e + self.lift * math.sin(math.pi * u)
        if self.fall is not None:
            f = smooth(t, *self.fall)
            if f > 0:
                R = R * (1 - f) + 0.0 * f
                A += 7.0 * f * f
                Z = Z * (1 - f)
        if self.collapse is not None:
            c = self.collapse(t)
            if c > 0:
                R *= (1 - c) ** 1.5
                A += 9.0 * c * c
                Z *= (1 - c)
        return R, A, Z, u

    def pos(self, t, C):
        R, A, Z, u = self.polar(t)
        return Vector((C.x + R * math.cos(A), C.y + R * math.sin(A), C.z + Z)), R, A, u


# ------------------------------------------------------------------------------------------------ debris cloud


def _proto_objs(coll, heat_mats):
    """Hidden prototypes for the debris cloud, index order = name order (p0.., p1.., ...)."""
    protos = []

    def mk(i, name, bm, m):
        me = bpy.data.meshes.new(f'sing.p{i}.{name}')
        bm.to_mesh(me)
        bm.free()
        me.materials.append(m)
        ob = bpy.data.objects.new(f'sing.p{i}.{name}', me)
        coll.objects.link(ob)
        protos.append(ob)
    # 0-2 paper confetti (bent squares), 3 dust speck, 4 ember, 5 bit (tiny cube), 6 shaving curl
    for i, key in enumerate(('yellow', 'pink', 'mint')):
        bm = bmesh.new()
        s = 0.55
        vs = []
        for j in range(4):
            for k in range(2):
                x = -s / 2 + s * j / 3
                y = -s / 2 + s * k
                vs.append(bm.verts.new((x, y, 0.06 * math.sin(math.pi * j / 3))))
        for j in range(3):
            a, b, c, d = vs[2 * j], vs[2 * j + 2], vs[2 * j + 3], vs[2 * j + 1]
            bm.faces.new((a, b, c, d))
        mk(i, key, bm, heat_mats[key])
    bm = bmesh.new()
    bmesh.ops.create_icosphere(bm, subdivisions=1, radius=0.05)
    mk(3, 'dust', bm, heat_mats['dust'])
    bm = bmesh.new()
    bmesh.ops.create_icosphere(bm, subdivisions=1, radius=0.045)
    mk(4, 'ember', bm, heat_mats['ember'])
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=0.16)
    mk(5, 'bit', bm, heat_mats['bit'])
    from pdoom.chars import geo as cg
    bm = bmesh.new()
    pts = [(0.13 * math.cos(j / 9 * 4.5) * (1 + j * 0.09), 0.13 * math.sin(j / 9 * 4.5) * (1 + j * 0.09), 0.02 * j)
           for j in range(10)]
    cg.tube(bm, pts, [0.018] * 10, segs=5)
    mk(6, 'shaving', bm, heat_mats['shaving'])
    for ob in protos:
        ob.location = (0, 0, -10000)
    return protos


def heat_material(name, color, *, rough=0.6, emit='#FF7A28', emit_k=9.0, base_emit=0.0, sss=0.0):
    """A small-debris material that glows orange with the instancer attribute 'heat' (0..1)."""
    m, nt, out = new_material(name)
    g = ShTree(nt)
    b = g.node('ShaderNodeBsdfPrincipled')
    b.inputs['Base Color'].default_value = kit.srgb(color)
    b.inputs['Roughness'].default_value = rough
    if sss:
        b.inputs['Subsurface Weight'].default_value = sss
        b.inputs['Subsurface Scale'].default_value = 0.05
    h = g.attribute('heat')
    b.inputs['Emission Color'].default_value = kit.srgb(emit)
    g.feed(b.inputs['Emission Strength'], h * h * emit_k + base_emit)
    nt.links.new(b.outputs[0], out.inputs['Surface'])
    m.diffuse_color = kit.srgb(color)
    return m


def debris(name, C, *, n=2600, seed=5, coll=None, rh=2.3, r_in=3.6, r_out=9.4, t_open=42.3, t_full=45.0,
           spawn=None, collapse_key=None):
    """The accretion debris cloud about C. spawn: list of (weight, kind, rmin, rmax, t_a, t_b, on_desk): groups of
    particles with a capture-time window; on_desk groups lie on the desk until captured (z = -C.z)."""
    rng = np.random.default_rng(seed)
    coll = coll or kit.collection('hole.debris')
    pc = kit.collection('hole.protos', coll)
    mats = {
        'yellow': heat_material('deb.yellow', '#F2D54B', rough=0.8, sss=0.1),
        'pink': heat_material('deb.pink', '#F2A0B8', rough=0.8, sss=0.1),
        'mint': heat_material('deb.mint', '#A6E3C8', rough=0.8, sss=0.1),
        'dust': heat_material('deb.dust', '#8C7B69', rough=0.9, emit_k=14.0),
        'ember': heat_material('deb.ember', '#3A1508', rough=0.5, emit='#FF9A40', emit_k=16.0, base_emit=5.0),
        'bit': heat_material('deb.bit', '#D9D2C6', rough=0.4, emit_k=10.0),
        'shaving': heat_material('deb.shaving', '#D8A868', rough=0.7),
    }
    _proto_objs(pc, mats)
    pc.hide_render = True
    groups = spawn or [
        # weight, kinds, rest radius range, capture window, on desk
        (0.30, (3,), (10.0, 34.0), (42.4, 47.5), True),     # dust off the desk
        (0.16, (0, 1, 2), (6.0, 20.0), (42.6, 47.0), True),  # paper bits
        (0.12, (5, 6), (8.0, 26.0), (43.0, 48.5), True),     # bits and shavings
        (0.22, (4,), (0.0, 0.0), (42.5, 45.5), False),       # embers born in the disc
        (0.20, (3, 5), (0.0, 0.0), (42.4, 44.5), False),     # dust born in the disc
    ]
    wsum = sum(gp[0] for gp in groups)
    rows = []
    for w, kinds, (ra, rb), (ta, tb), desk in groups:
        k = int(round(n * w / wsum))
        kind = rng.choice(kinds, k)
        r = r_in + (r_out - r_in) * rng.power(0.8, k) * 0.95 + 0.1
        z = rng.normal(0, 0.18, k) * (0.4 + (r - r_in) / (r_out - r_in))
        ts = rng.uniform(ta, tb, k)
        if desk:
            rs = rng.uniform(ra, rb, k)
            a_s = rng.uniform(0, 2 * math.pi, k)
            zs = np.full(k, -C.z + 0.04)
            dc = rng.uniform(0.7, 1.6, k) * (0.6 + rs / 34.0)
            show0 = np.ones(k)
        else:
            rs = r * rng.uniform(1.0, 1.25, k)
            a_s = rng.uniform(0, 2 * math.pi, k)
            zs = z + rng.normal(0, 0.4, k)
            dc = rng.uniform(0.3, 0.8, k)
            show0 = np.zeros(k)
        K = rng.uniform(1.2, 3.5, k)
        om = np.array([omega(x) for x in r])
        th0 = a_s - om * (ts - TREF) + K
        sz = np.where(kind <= 2, rng.uniform(0.5, 1.2, k), rng.uniform(0.6, 1.5, k))
        ax = rng.normal(0, 1, (k, 3))
        ax /= np.linalg.norm(ax, axis=1, keepdims=True)
        spin = rng.uniform(4, 14, k)
        if desk:
            rot0 = np.stack([np.zeros(k), np.zeros(k), rng.uniform(0, 6.3, k)], 1)
        else:
            rot0 = rng.uniform(0, 6.3, (k, 3))
        lift = rng.uniform(0.5, 2.5, k) if desk else np.zeros(k)
        for i in range(k):
            rows.append((kind[i], r[i], z[i], ts[i], dc[i], rs[i], zs[i], K[i], om[i], th0[i], sz[i], ax[i],
                         spin[i], rot0[i], lift[i], show0[i]))
    cnt = len(rows)
    col = lambda j: np.array([row[j] for row in rows], dtype=np.float32)
    attrs = {
        'kind': col(0), 'rr': col(1), 'zz': col(2), 'ts': col(3), 'dc': col(4), 'rs': col(5), 'zs': col(6),
        'K': col(7), 'om': col(8), 'th0': col(9), 'sz': col(10), 'ax': np.stack([row[11] for row in rows]),
        'spin': col(12), 'rot0': np.stack([row[13] for row in rows]), 'lift': col(14), 'show0': col(15),
    }
    me = bpy.data.meshes.new(name)
    me.vertices.add(cnt)
    me.vertices.foreach_set('co', np.zeros(cnt * 3, dtype=np.float32))
    for nm, arr in attrs.items():
        arr = np.asarray(arr, dtype=np.float32)
        vec = arr.ndim == 2
        a = me.attributes.new(nm, 'FLOAT_VECTOR' if vec else 'FLOAT', 'POINT')
        a.data.foreach_set('vector' if vec else 'value', arr.ravel())
    me.update()
    ob = bpy.data.objects.new(name, me)
    coll.objects.link(ob)
    ob.location = C
    tree = _debris_tree(name + '.gn', pc, rh, r_in, r_out)
    mod = N.modifier(ob, tree, 'debris')
    return ob, mod, attrs


def _debris_tree(name, protos_coll, rh, r_in, r_out):
    g = N.Tree(name)
    geo_in = g.input_geometry()
    col_in = g.param('Collapse', 'FLOAT', 0.0)
    T = g.time()

    def A(nm, kind='FLOAT'):
        return g.out(g.node('GeometryNodeInputNamedAttribute', data_type=kind, inputs={'Name': nm}), 'Attribute')
    ts, dc = A('ts'), A('dc')
    u = g.clamp((T - ts) / dc)
    e = u * u * (3.0 - u * 2.0)
    rr, rs, zz, zs = A('rr'), A('rs'), A('zz'), A('zs')
    R0 = rs + (rr - rs) * e
    omg, th0, K = A('om'), A('th0'), A('K')
    one_u = 1.0 - u
    ang0 = th0 + omg * (T - TREF) - K * one_u * one_u
    Z0 = zs + (zz - zs) * e + A('lift') * g.sin(u * math.pi)
    c = g.clamp(col_in)
    shrink = g.op('POWER', 1.0 - c, 1.5)
    R = R0 * shrink
    ang = ang0 + c * c * 9.0
    Z = Z0 * (1.0 - c)
    pos = g.vec(R * g.cos(ang), R * g.sin(ang), Z)
    pts = g.set_position(geo_in, position=pos)
    heat = g.clamp(g.remap(R, r_in * 1.9, r_in * 0.95, 0.0, 1.0)) * g.clamp(u * 3.0)
    pts = g.store(pts, 'heat', heat)
    shown = g.bool_or(T > (ts - 0.5 / FPS), A('show0') > 0.5)
    alive = R > (rh * 1.02)
    sel = g.bool_and(shown, alive)
    tumble = g.axis_angle(A('ax', 'FLOAT_VECTOR'), A('spin') * g.max(T - ts, 0.0))
    rot = g.rotate(g.euler(A('rot0', 'FLOAT_VECTOR')), tumble, space='GLOBAL')
    # stretched a little along the orbit near the hole (tidal), shrinks away in the collapse
    sc = A('sz') * (1.0 - g.smooth(c, 0.6, 1.0))
    inst_src = g.collection_geo(protos_coll, separate=True, reset=True)
    inst = g.instance(pts, inst_src, rotation=rot, scale=sc, selection=sel, pick=True, instance_index=A('kind'))
    g.output(inst)
    return g
