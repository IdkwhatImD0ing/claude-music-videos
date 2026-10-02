"""The snow globe for `sydney` (scene-local, not library code).

A turned walnut base with a brass collar, a 2.5 mm glass dome (R 7 cm), a snowy hill inside with two tiny pines,
the water, swirling snow (geometry nodes: a pure function of song time, then a ballistic spray when the globe bursts),
breath fog with finger-drawn hearts (a shader on a shell just outside the glass, keyed by Value nodes), a spray of
water droplets for the burst, and Sydney's tears.

Local frame: the globe's axis is the Z axis through `origin` (the base's bottom centre on the desk).
"""
from __future__ import annotations

import math
import os

import bmesh
import bpy
import numpy as np
from mathutils import Matrix, Vector

from pdoom import kit
from pdoom.fx import _nodes as N
from pdoom.fx import materials as FXM
from pdoom.sets import geo
from pdoom.sets import materials as M
from pdoom.timing import FPS

R = 7.0              # glass outer radius
WALL = 0.25          # glass thickness
ZC = 8.8             # sphere centre height above the desk
R_IN = R - WALL
BASE_TOP = 3.7
COLLAR_TOP = 4.5
GLASS_CUT = 4.58     # the dome starts just above the collar (the collar hides the joint)
HILL_TOP = 6.25      # the snow hill's crown


def hill_z(r: float) -> float:
    """Height of the snow hill's surface at radius r (local)."""
    return HILL_TOP - 0.012 * r * r


def r_in(z: float) -> float:
    """Inner glass radius at height z (local)."""
    return math.sqrt(max(0.0, R_IN * R_IN - (z - ZC) ** 2))


# ------------------------------------------------------------------------------------------------ materials


def walnut():
    return M.tex_mat('sydney.walnut', 'desk_wood', 30, tint='#6B4226', tint_amount=0.55, val=0.9,
                     rough=(0.25, 0.45), coat=0.7, coat_rough=0.06, fallback='#5A3A24')


def snow_mat():
    m, fresh = M.new_mat('sydney.snow')
    if not fresh:
        return m
    nt = m.node_tree
    b = M.principled(m)
    M.setin(b, 'Base Color', M.col('#D9E1EB'))
    M.setin(b, 'Roughness', 0.55)
    M.setin(b, 'Subsurface Weight', 0.35)
    M.setin(b, 'Subsurface Radius', (1.0, 1.0, 1.1))
    M.setin(b, 'Subsurface Scale', 0.15)
    M.setin(b, 'Specular IOR Level', 0.6)
    # lumpy packed snow: a coarse and a fine bump
    tc = M.node(nt, 'ShaderNodeTexCoord', (-900, -200))
    nz = M.node(nt, 'ShaderNodeTexNoise', (-700, -200))
    M.setin(nz, 'Scale', 1.6)
    M.setin(nz, 'Detail', 8.0)
    M.setin(nz, 'Roughness', 0.62)
    M.link(nt, M.sout(tc, 'Object'), M.sin(nz, 'Vector'))
    bump = M.node(nt, 'ShaderNodeBump', (-300, -200))
    M.setin(bump, 'Strength', 0.55)
    M.setin(bump, 'Distance', 0.08)
    M.link(nt, M.sout(nz, 'Factor'), M.sin(bump, 'Height'))
    M.link(nt, M.sout(bump, 'Normal'), M.sin(b, 'Normal'))
    m.diffuse_color = M.col('#F3F6FB')
    return m


def flake_mat():
    """Snow-globe flakes: white plastic with a share of glitter (per-instance random from the instancer)."""
    if 'sydney.flake' in bpy.data.materials:
        return bpy.data.materials['sydney.flake']
    m = bpy.data.materials.new('sydney.flake')
    nt = m.node_tree
    b = nt.nodes.get('Principled BSDF')
    b.inputs['Base Color'].default_value = kit.srgb('#FFFFFF')
    b.inputs['Roughness'].default_value = 0.35
    b.inputs['Subsurface Weight'].default_value = 0.2
    b.inputs['Emission Color'].default_value = kit.srgb('#E8F0FF')
    b.inputs['Emission Strength'].default_value = 0.12
    at = nt.nodes.new('ShaderNodeAttribute')
    at.attribute_type = 'INSTANCER'
    at.attribute_name = 'glit'
    # glitter flakes: metallic, mirror-smooth (they flash in the lamp)
    nt.links.new(at.outputs['Fac'], b.inputs['Metallic'])
    inv = nt.nodes.new('ShaderNodeMath')
    inv.operation = 'MULTIPLY_ADD'
    inv.inputs[1].default_value = -0.3
    inv.inputs[2].default_value = 0.35
    nt.links.new(at.outputs['Fac'], inv.inputs[0])
    nt.links.new(inv.outputs[0], b.inputs['Roughness'])
    m.diffuse_color = (1, 1, 1, 1)
    return m


def shell_glass(name='sydney.glass'):
    """Thin glass without refraction: a fresnel mix of a clear see-through and a mirror-smooth gloss, blended.
    (Sydney's jelly already ray-traces its refraction; EEVEE refracts only one layer, so a refracting dome would
    hide her. A 2.5 mm shell barely bends light anyway.)"""
    if name in bpy.data.materials:
        return bpy.data.materials[name]
    m = bpy.data.materials.new(name)
    nt = m.node_tree
    nt.nodes.clear()
    out = nt.nodes.new('ShaderNodeOutputMaterial')
    fr = nt.nodes.new('ShaderNodeFresnel')
    fr.inputs['IOR'].default_value = 1.5
    boost = nt.nodes.new('ShaderNodeMath')
    boost.operation = 'MULTIPLY_ADD'
    boost.inputs[1].default_value = 0.9
    boost.inputs[2].default_value = 0.025
    nt.links.new(fr.outputs[0], boost.inputs[0])
    cap = nt.nodes.new('ShaderNodeMath')
    cap.operation = 'MINIMUM'
    cap.inputs[1].default_value = 0.34        # grazing edges stay partly see-through (no black rim)
    nt.links.new(boost.outputs[0], cap.inputs[0])
    boost = cap
    tr = nt.nodes.new('ShaderNodeBsdfTransparent')
    tr.inputs['Color'].default_value = kit.srgb('#F2F8FF')
    gl = nt.nodes.new('ShaderNodeBsdfGlossy')
    gl.inputs['Color'].default_value = (1, 1, 1, 1)
    gl.inputs['Roughness'].default_value = 0.015
    mix = nt.nodes.new('ShaderNodeMixShader')
    nt.links.new(boost.outputs[0], mix.inputs['Fac'])
    nt.links.new(tr.outputs[0], mix.inputs[1])
    nt.links.new(gl.outputs[0], mix.inputs[2])
    nt.links.new(mix.outputs[0], out.inputs['Surface'])
    m.surface_render_method = 'BLENDED'
    m.use_backface_culling = False
    try:
        m.use_transparency_overlap = True
    except Exception:
        pass
    m.use_transparent_shadow = True
    m.diffuse_color = (0.95, 0.97, 1.0, 0.15)
    return m


def clear_water(name='sydney.water', gloss_rough=0.03, gloss_cap=0.6):
    """Water that reads clear on the dark desk: a fresnel mix of a faintly blue see-through and a smooth gloss,
    blended (no screen-space refraction, which renders the spill black in this dark room). gloss_rough: a rougher
    gloss and a lower cap on the fresnel mix (gloss_cap) keep a thin film from mirroring the bright room as hard
    white blotches at grazing angles."""
    if name in bpy.data.materials:
        return bpy.data.materials[name]
    m = bpy.data.materials.new(name)
    nt = m.node_tree
    nt.nodes.clear()
    out = nt.nodes.new('ShaderNodeOutputMaterial')
    fr = nt.nodes.new('ShaderNodeFresnel')
    fr.inputs['IOR'].default_value = 1.33
    k = nt.nodes.new('ShaderNodeMath')
    k.operation = 'MULTIPLY_ADD'
    k.inputs[1].default_value = 1.4
    k.inputs[2].default_value = 0.06
    k.use_clamp = True
    nt.links.new(fr.outputs[0], k.inputs[0])
    cap = nt.nodes.new('ShaderNodeMath')
    cap.operation = 'MINIMUM'
    cap.inputs[1].default_value = gloss_cap
    nt.links.new(k.outputs[0], cap.inputs[0])
    tr = nt.nodes.new('ShaderNodeBsdfTransparent')
    tr.inputs['Color'].default_value = kit.srgb('#DDEEFF')
    gl = nt.nodes.new('ShaderNodeBsdfGlossy')
    gl.inputs['Roughness'].default_value = gloss_rough
    mix = nt.nodes.new('ShaderNodeMixShader')
    nt.links.new(cap.outputs[0], mix.inputs['Fac'])
    nt.links.new(tr.outputs[0], mix.inputs[1])
    nt.links.new(gl.outputs[0], mix.inputs[2])
    nt.links.new(mix.outputs[0], out.inputs['Surface'])
    m.surface_render_method = 'BLENDED'
    m.use_backface_culling = True
    m.use_transparent_shadow = True
    m.diffuse_color = (0.85, 0.92, 1.0, 0.2)
    return m


def pine_mat():
    return M.solid('sydney.pine', '#1F4A33', rough=0.6, sheen=0.3)


# ------------------------------------------------------------------------------------------------ build


class Globe:
    """Handles: root (Empty on the desk at the base centre; the rocking pivot is its parent `rock`), base, collar,
    hill, glass, water, snow, fog, trees. Local geometry is built around the globe axis."""

    def __init__(self, coll, origin, face_dir):
        self.coll = coll
        self.origin = Vector(origin)
        self.D = Vector((face_dir[0], face_dir[1], 0.0)).normalized()   # towards the researcher
        self.C = self.origin + Vector((0, 0, ZC))
        # the rocking pivot sits on the desk under the base's rim on the researcher's side
        piv = self.origin + self.D * 6.3
        self.rock = kit.empty('globe.rock', tuple(piv), coll, 'PLAIN_AXES', 2.0)
        self.rock.rotation_mode = 'AXIS_ANGLE'
        self.root = kit.empty('globe.root', tuple(self.origin), coll, 'ARROWS', 3.0)
        self.root.parent = self.rock
        self.root.matrix_parent_inverse = Matrix.Translation(-piv)
        self._build()

    # geometry ------------------------------------------------------------------------------------------------
    def _lathe(self, name, prof, m, **kw):
        o = geo.lathe(name, prof, segs=96, coll=self.coll, m=m, **kw)
        o.location = self.origin
        return o

    def _build(self):
        O = self.origin
        # the base: a turned walnut plinth
        prof = [(0.0, 0.0), (6.3, 0.0), (6.45, 0.12), (6.48, 0.7), (6.3, 0.95), (5.85, 1.35), (5.62, 1.95),
                (5.7, 2.55), (5.95, 2.95), (6.08, 3.25), (6.0, 3.55), (5.75, BASE_TOP), (0.0, BASE_TOP)]
        prof = geo.rounded_profile(prof, 0.12, 3)
        self.base = self._lathe('globe.base', prof, walnut(), smooth_angle=40)
        # the brass collar the dome sits in
        brass = M.brass('sydney.brass', '#C9A259', rough=0.22)
        cp = [(4.2, BASE_TOP - 0.1), (6.02, BASE_TOP - 0.1), (6.08, 4.05), (5.92, COLLAR_TOP), (4.95, COLLAR_TOP),
              (4.6, 4.1), (4.2, BASE_TOP - 0.1)]
        self.collar = self._lathe('globe.collar', geo.rounded_profile(cp, 0.08, 3), brass, smooth_angle=35)
        # the snow hill: a gentle crown down to the glass wall, filling the dome's bottom
        hp = [(0.0, HILL_TOP)]
        for k in range(1, 9):
            r = 6.0 * k / 8
            hp.append((min(r, r_in(hill_z(r)) - 0.03), hill_z(r)))
        zs = [hill_z(6.0) - 0.15 * k for k in range(1, 12)]
        for z in zs:
            if z < BASE_TOP:
                break
            hp.append((r_in(z) - 0.03, z))
        hp += [(r_in(BASE_TOP) - 0.03, BASE_TOP - 0.05), (0.0, BASE_TOP - 0.05)]
        self.hill = self._lathe('globe.hill', hp, snow_mat(), smooth_angle=60)
        # two tiny pines at the back of the hill (away from the researcher)
        self.trees = []
        side = Vector((-self.D.y, self.D.x, 0.0))
        for k, (back, lat, h) in enumerate(((-3.2, -1.9, 3.1), (-2.4, 2.3, 2.3))):
            p = O + self.D * back + side * lat
            rr = (p - O).length
            z0 = hill_z(rr) - 0.1
            parts = []
            for j, (r0, z_a, z_b) in enumerate(((0.95, 0.25, 1.6), (0.75, 0.95, 2.3), (0.5, 1.6, 3.0))):
                s = h / 3.0
                bpy.ops.mesh.primitive_cone_add(vertices=14, radius1=r0 * s, radius2=0.02, depth=(z_b - z_a) * s,
                                                location=(p.x, p.y, z0 + (z_a + z_b) / 2 * s))
                cone = bpy.context.object
                kit.link(cone, self.coll)
                cone.data.materials.append(pine_mat())
                parts.append(cone)
            trunk = kit.cylinder(f'globe.tree{k}.trunk', 0.12 * h / 3, 0.5 * h / 3, (p.x, p.y, z0 + 0.1),
                                 verts=10, m=M.solid('sydney.trunk', '#4A3020', rough=0.7), coll=self.coll)
            parts.append(trunk)
            t = geo.join(parts, f'globe.tree{k}')
            kit.smooth(t, 30)
            self.trees.append(t)
        # the glass dome: a sphere cut above the collar, 2.5 mm thick
        bm = bmesh.new()
        bmesh.ops.create_uvsphere(bm, u_segments=128, v_segments=64, radius=R)
        bmesh.ops.translate(bm, verts=bm.verts, vec=(0, 0, ZC))
        geom = list(bm.verts) + list(bm.edges) + list(bm.faces)
        bmesh.ops.bisect_plane(bm, geom=geom, dist=1e-5, plane_co=(0, 0, GLASS_CUT), plane_no=(0, 0, 1),
                               clear_inner=True)
        me = bpy.data.meshes.new('globe.glass')
        bm.to_mesh(me)
        bm.free()
        self.glass = bpy.data.objects.new('globe.glass', me)
        self.coll.objects.link(self.glass)
        self.glass.location = O
        for p in me.polygons:
            p.use_smooth = True
        sol = self.glass.modifiers.new('wall', 'SOLIDIFY')
        sol.thickness, sol.offset = WALL, -1.0
        self.glass_mat = shell_glass()
        me.materials.append(self.glass_mat)
        # the water: the dome's inside above the hill (closed)
        bm = bmesh.new()
        bmesh.ops.create_uvsphere(bm, u_segments=64, v_segments=32, radius=R_IN - 0.04)
        bmesh.ops.translate(bm, verts=bm.verts, vec=(0, 0, ZC))
        geom = list(bm.verts) + list(bm.edges) + list(bm.faces)
        res = bmesh.ops.bisect_plane(bm, geom=geom, dist=1e-5, plane_co=(0, 0, HILL_TOP + 0.05),
                                     plane_no=(0, 0, 1), clear_inner=True)
        bnd = [e for e in bm.edges if e.is_boundary]
        bmesh.ops.holes_fill(bm, edges=bnd, sides=0)
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
        me = bpy.data.meshes.new('globe.water')
        bm.to_mesh(me)
        bm.free()
        self.water = bpy.data.objects.new('globe.water', me)
        self.coll.objects.link(self.water)
        self.water.location = O
        for p in me.polygons:
            p.use_smooth = True
        bpy.context.view_layer.update()
        for o in [self.base, self.collar, self.hill, self.glass, self.water] + self.trees:
            self.adopt(o)

    def adopt(self, o):
        """Parent o to the globe (it rocks with it), keeping its world placement."""
        bpy.context.view_layer.update()
        mw = o.matrix_world.copy()
        o.parent = self.root
        o.matrix_parent_inverse = self.root.matrix_world.inverted()
        o.matrix_world = mw
        return o

    # rocking ------------------------------------------------------------------------------------------------
    def rock_keys(self, hits, amp_deg=1.3, t0=None, t1=None):
        """Rock the globe about its rim (towards the researcher) with a damped wobble after each hit time."""
        axis = Vector((-self.D.y, self.D.x, 0.0))    # tipping towards D
        ts = sorted(hits)
        ta = (t0 if t0 is not None else ts[0] - 0.1)
        tb = (t1 if t1 is not None else ts[-1] + 0.6)
        f0, f1 = int(math.floor(ta * FPS)), int(math.ceil(tb * FPS))
        for f in range(f0 - 1, f1 + 2):
            t = f / FPS
            a = 0.0
            for h in ts:
                if t >= h:
                    x = t - h
                    a += math.exp(-x * 11.0) * math.sin(2 * math.pi * 6.0 * x + 0.35)
            ang = math.radians(amp_deg) * max(-0.3, a)       # it can't tip backwards through the desk much
            self.rock.rotation_axis_angle = (ang, axis.x, axis.y, axis.z)
            self.rock.keyframe_insert('rotation_axis_angle', frame=f)
        for fc in kit.fcurves(self.rock):
            for kp in fc.keyframe_points:
                kp.interpolation = 'LINEAR'

    # points on the glass -----------------------------------------------------------------------------------
    def on_glass(self, yaw_off_deg=0.0, z=None, outer=True):
        """World point on the glass surface: yaw_off_deg around the axis from the researcher direction, height z."""
        z = ZC if z is None else z
        a = math.atan2(self.D.y, self.D.x) + math.radians(yaw_off_deg)
        rr = math.sqrt(max(0.0, (R if outer else R_IN) ** 2 - (z - ZC) ** 2))
        return self.origin + Vector((math.cos(a) * rr, math.sin(a) * rr, z))


# ------------------------------------------------------------------------------------------------ snow

T_SNOW0, T_SNOW1, T_BURST = 52.962, 62.053, 60.235      # sydney's window and DOOM 2 (moon reuses the landed flakes)


def _env(t, pts):
    if t <= pts[0][0]:
        return pts[0][1]
    for (a, va), (b, vb) in zip(pts, pts[1:]):
        if t <= b:
            u = (t - a) / (b - a)
            u = u * u * (3 - 2 * u)
            return va + (vb - va) * u
    return pts[-1][1]


def snow_swirl(t):
    """Swirl speed (rad/s): still whirling from the globe's arrival (singularity), a gust as the researcher is
    zapped in (53.62), calming; whipped up when Sydney shakes the globe, a storm under the cracks."""
    return _env(t, [(T_SNOW0 - 1, 2.4), (53.3, 1.1), (53.62, 3.2), (54.3, 1.2), (55.5, 0.5), (56.6, 0.45),
                    (57.0, 2.4), (58.3, 3.4), (59.1, 2.8), (60.2, 5.0)])


def snow_lift(t):
    return _env(t, [(T_SNOW0 - 1, 0.95), (53.3, 0.85), (53.7, 1.0), (54.6, 0.8), (56.6, 0.5), (57.2, 0.9),
                    (58.3, 1.0), (59.0, 0.9), (60.2, 1.0)])


def make_snow(globe):
    """The one snowfall both scenes share (the same seed and timing, so the flakes land in the same places)."""
    return Snow(globe, count=950, seed=5, swirl=snow_swirl, lift=snow_lift, t_range=(T_SNOW0, T_SNOW1),
                t_burst=T_BURST)



def _integrate(fn, t0, t1, dt=1.0 / 96):
    """[(t, integral of fn from t0)] sampled every frame (trapezoid on a finer step)."""
    out = []
    acc = 0.0
    f0, f1 = int(math.floor(t0 * FPS)), int(math.ceil(t1 * FPS))
    t = f0 / FPS
    out.append((t, 0.0))
    for f in range(f0 + 1, f1 + 1):
        tn = f / FPS
        n = 4
        h = (tn - t) / n
        for k in range(n):
            a, b = t + k * h, t + (k + 1) * h
            acc += 0.5 * (fn(a) + fn(b)) * h
        t = tn
        out.append((t, acc))
    return out


class Snow:
    """Snow flakes in the globe. Before `t_burst`: they swirl around the axis (Phase, keyed = the integral of the
    swirl speed) at a height set by Lift (0 settled on the hill .. 1 whirled up to the dome); after: each flake
    flies out ballistically (drag, weak gravity: they are in a gush of water) and lies flat where it lands."""

    def __init__(self, globe: Globe, *, count=1400, seed=7, swirl=None, lift=None, t_range=(0, 1), t_burst=1e9,
                 floor_fn=None):
        self.g = globe
        rng = np.random.default_rng(seed)
        n = count
        self.n = n
        self.h = rng.uniform(0.0, 1.0, n)
        self.k = rng.uniform(0.55, 2.6, n)
        self.r = np.sqrt(rng.uniform(0.0, 1.0, n))
        self.a = rng.uniform(0, 2 * math.pi, n)
        self.w = rng.uniform(0.55, 1.45, n) * np.where(rng.uniform(0, 1, n) < 0.12, -0.6, 1.0)
        self.s = rng.uniform(0, 1, n)
        self.size = rng.uniform(0.035, 0.085, n)
        self.glit = (rng.uniform(0, 1, n) < 0.22).astype(np.float32)
        self.spin = rng.uniform(2.0, 9.0, n)
        self.r0 = rng.uniform(0, 2 * math.pi, (n, 3))
        self.t_burst = t_burst
        ta, tb = t_range
        # keyed inputs: Lift directly, Phase as the integral of the swirl speed (rad/s)
        self.lift_fn = lift
        self.phase_keys = _integrate(swirl, ta - 0.2, tb + 0.2)
        self.lift_keys = [(f / FPS, lift(f / FPS)) for f in range(int(ta * FPS) - 5, int(tb * FPS) + 6)]
        self.floor_fn = floor_fn
        self._build(rng)

    def phase_at(self, t):
        ks = self.phase_keys
        if t <= ks[0][0]:
            return ks[0][1]
        for (t0, v0), (t1, v1) in zip(ks, ks[1:]):
            if t <= t1:
                return v0 + (v1 - v0) * (t - t0) / (t1 - t0)
        return ks[-1][1]

    def pre(self, t, phase=None, lift=None):
        """Flake positions (local, n x 3) at song time t before the burst (the same maths as the node tree)."""
        ph = self.phase_at(t) if phase is None else phase
        L = self.lift_fn(t) if lift is None else lift
        li = np.power(max(L, 1e-6), self.k)
        zmin = hill_z(0.0) + 0.18
        zmax = ZC + R_IN - 0.9
        z = zmin + (zmax - zmin) * self.h * li
        rmax = np.sqrt(np.maximum(0.0, (R_IN - 0.45) ** 2 - (z - ZC) ** 2))
        rho = self.r * rmax
        ang = self.a + ph * self.w
        x = rho * np.cos(ang) + 0.3 * li * np.sin(1.9 * t + 6.2832 * self.s)
        y = rho * np.sin(ang) + 0.3 * li * np.cos(1.4 * t + 8.17 * self.s)
        zz = z + 0.22 * li * np.sin(2.3 * t + 10.7 * self.s)
        # resting flakes sit on the hill's crown
        zz = np.maximum(zz, HILL_TOP - 0.012 * (x * x + y * y) + 0.05)
        return np.stack([x, y, zz], axis=1)

    def _build(self, rng):
        g = self.g
        n = self.n
        tb = self.t_burst
        p0 = self.pre(tb)
        # the burst: out and up, strongly damped (water), weak gravity
        radial = p0[:, :2] / np.maximum(np.linalg.norm(p0[:, :2], axis=1, keepdims=True), 1e-3)
        sp = rng.uniform(35.0, 115.0, n)
        v0 = np.zeros((n, 3))
        v0[:, :2] = radial * sp[:, None] + rng.normal(0, 12.0, (n, 2))
        v0[:, 2] = rng.uniform(-15.0, 70.0, n)
        kd = rng.uniform(4.5, 8.0, n)
        gs = 0.45 * 981.0
        # landing age: bisection on z(a) = floor(x, y) (the base top inside its rim, the desk outside)
        life = np.full(n, 30.0)

        def z_of(a):
            F = (1 - np.exp(-kd * a)) / kd
            return p0[:, 2] + v0[:, 2] * F - (gs / kd) * (a - F), F

        def floor_at(a):
            F = (1 - np.exp(-kd * a)) / kd
            xy = p0[:, :2] + v0[:, :2] * F[:, None]
            rr = np.linalg.norm(xy, axis=1)
            return np.where(rr < 6.0, BASE_TOP + 0.03, 0.03)
        lo, hi = np.zeros(n), np.full(n, 6.0)
        for _ in range(48):
            mid = 0.5 * (lo + hi)
            zm, _ = z_of(mid)
            below = zm < floor_at(mid)
            hi = np.where(below, mid, hi)
            lo = np.where(below, lo, mid)
        aland = hi
        # the point cloud (local to the globe), carrying every per-flake constant
        attrs = {'p0': p0, 'h': self.h, 'k': self.k, 'r': self.r, 'a': self.a, 'w': self.w, 's': self.s,
                 'size': self.size, 'glit': self.glit, 'spin': self.spin, 'r0': self.r0, 'v0': v0, 'kd': kd,
                 'aland': aland}
        me = bpy.data.meshes.new('globe.snow')
        me.vertices.add(n)
        me.vertices.foreach_set('co', np.asarray(p0, dtype=np.float32).ravel())
        for nm, arr in attrs.items():
            arr = np.asarray(arr, dtype=np.float32)
            vec = arr.ndim == 2
            at = me.attributes.new(nm, 'FLOAT_VECTOR' if vec else 'FLOAT', 'POINT')
            at.data.foreach_set('vector' if vec else 'value', arr.ravel())
        me.update()
        ob = bpy.data.objects.new('globe.snow', me)
        g.coll.objects.link(ob)
        ob.location = g.origin
        self.obj = ob
        self.tree = self._tree(gs)
        self.mod = N.modifier(ob, self.tree, 'snow')
        mod = self.mod
        path_ph = N.set_input(mod, 'Phase', 0.0)
        for t, v in self.phase_keys:
            N.set_input(mod, 'Phase', v)
            ob.keyframe_insert(path_ph, frame=t * FPS)
        path_l = N.set_input(mod, 'Lift', 0.0)
        for t, v in self.lift_keys:
            N.set_input(mod, 'Lift', v)
            ob.keyframe_insert(path_l, frame=t * FPS)
        for fc in kit.fcurves(ob):
            for kp in fc.keyframe_points:
                kp.interpolation = 'LINEAR'
        N.set_input(mod, 'Burst', tb)
        g.adopt(ob)

    def _tree(self, gs):
        g = N.Tree('globe.snow.gn')
        geo_in = g.input_geometry()
        phase = g.param('Phase', 'FLOAT', 0.0)
        lift = g.param('Lift', 'FLOAT', 0.5)
        tb = g.param('Burst', 'FLOAT', 1e9)
        t = g.time()

        def A(name, kind='FLOAT'):
            return g.out(g.node('GeometryNodeInputNamedAttribute', data_type=kind, inputs={'Name': name}), 'Attribute')
        h, k, r, a, w, s = A('h'), A('k'), A('r'), A('a'), A('w'), A('s')
        li = g.op('POWER', g.max(lift, 1e-6), k)
        zmin = hill_z(0.0) + 0.18
        zmax = ZC + R_IN - 0.9
        z = zmin + (zmax - zmin) * h * li
        dz = z - ZC
        rmax = g.sqrt(g.max((R_IN - 0.45) ** 2 - dz * dz, 0.0))
        rho = r * rmax
        ang = a + phase * w
        x = rho * g.cos(ang) + 0.3 * li * g.sin(1.9 * t + 6.2832 * s)
        y = rho * g.sin(ang) + 0.3 * li * g.cos(1.4 * t + 8.17 * s)
        zz = z + 0.22 * li * g.sin(2.3 * t + 10.7 * s)
        zz = g.max(zz, (HILL_TOP + 0.05) - 0.012 * (x * x + y * y))
        pre = g.vec(x, y, zz)
        # after the burst: p0 + v0 F + (g/k)(a - F), frozen at the landing age
        p0, v0 = A('p0', 'FLOAT_VECTOR'), A('v0', 'FLOAT_VECTOR')
        kd, aland = A('kd'), A('aland')
        age = t - tb
        ae = g.max(g.min(age, aland), 0.0)
        F = (1.0 - g.exp(-1.0 * kd * ae)) / kd
        gk = g.vec(0.0, 0.0, -gs) / kd
        post = p0 + v0 * F + gk * (ae - F)
        burst = age >= 0.0
        pos = g.switch(burst, pre, post, kind='VECTOR')
        landed = age > aland
        geo_s = g.set_position(geo_in, position=pos)
        tumble = g.euler(A('r0', 'FLOAT_VECTOR') + g.vec(1.0, 0.6, 0.3) * (A('spin') * t))
        flat = g.euler(g.vec(0.0, 0.0, a * 3.0))
        rot = g.switch(landed, tumble, flat, kind='ROTATION')
        sz = A('size')
        flake = _flake_proto()
        inst = g.instance(geo_s, g.object_geo(flake, as_instance=True, relative=False), rotation=rot,
                          scale=g.vec(sz, sz, sz))
        inst = g.store(inst, 'glit', A('glit'), domain='INSTANCE')
        inst = g.set_material(inst, flake_mat())
        g.output(inst)
        return g


def _flake_proto():
    ob = bpy.data.objects.get('globe.flake.proto')
    if ob is not None:
        return ob
    bm = bmesh.new()
    bmesh.ops.create_circle(bm, cap_ends=True, segments=6, radius=1.0)
    bmesh.ops.scale(bm, vec=(1.0, 0.8, 1.0), verts=bm.verts)
    me = bpy.data.meshes.new('globe.flake.proto')
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new('globe.flake.proto', me)
    kit.collection('sydney.protos').objects.link(ob)
    ob.location = (0, 0, -5000)
    ob.hide_render = True
    ob.hide_viewport = True
    return ob


# ------------------------------------------------------------------------------------------------ droplets


def droplets(name, globe: Globe, t0, *, count=260, seed=11, speed=(70.0, 190.0), coll=None):
    """A spray of water droplets thrown out of the dome when it bursts: ballistic with light drag, stretched along
    their velocity, gone when they hit the desk (they join the spill)."""
    rng = np.random.default_rng(seed)
    n = count
    # launch points on the dome, favouring the upper half
    th = rng.uniform(0, 2 * math.pi, n)
    cz = rng.uniform(-0.35, 1.0, n)
    sz = np.sqrt(1 - cz ** 2)
    d = np.stack([sz * np.cos(th), sz * np.sin(th), cz], axis=1)
    p0 = np.array(globe.C)[None] + d * R
    v0 = d * rng.uniform(*speed, n)[:, None] + np.array([0, 0, 40.0])[None] + rng.normal(0, 15, (n, 3))
    birth = t0 + rng.uniform(0, 0.05, n)
    k = rng.uniform(0.6, 1.6, n)
    size = rng.uniform(0.05, 0.2, n) * np.where(rng.uniform(0, 1, n) < 0.15, 1.8, 1.0)
    life = np.full(n, 3.0)
    # landing age on the desk (z = 0)
    G = 981.0

    def z_of(a):
        F = (1 - np.exp(-k * a)) / k
        return p0[:, 2] + v0[:, 2] * F - (G / k) * (a - F)
    lo, hi = np.zeros(n), np.full(n, 3.0)
    for _ in range(48):
        mid = 0.5 * (lo + hi)
        below = z_of(mid) < size
        hi = np.where(below, mid, hi)
        lo = np.where(below, lo, mid)
    aland = hi
    me = bpy.data.meshes.new(name)
    me.vertices.add(n)
    me.vertices.foreach_set('co', np.asarray(p0, dtype=np.float32).ravel())
    for nm, arr in {'p0': p0, 'v0': v0, 'birth': birth, 'k': k, 'size': size, 'aland': aland}.items():
        arr = np.asarray(arr, dtype=np.float32)
        vec = arr.ndim == 2
        at = me.attributes.new(nm, 'FLOAT_VECTOR' if vec else 'FLOAT', 'POINT')
        at.data.foreach_set('vector' if vec else 'value', arr.ravel())
    me.update()
    ob = bpy.data.objects.new(name, me)
    (coll or globe.coll).objects.link(ob)
    g = N.Tree(f'{name}.gn')
    geo_in = g.input_geometry()
    t = g.time()

    def A(nm, kind='FLOAT'):
        return g.out(g.node('GeometryNodeInputNamedAttribute', data_type=kind, inputs={'Name': nm}), 'Attribute')
    age = t - A('birth')
    alive = g.bool_and(age >= 0.0, age < A('aland'))
    kk = A('k')
    ae = g.max(age, 0.0)
    E = g.exp(-1.0 * kk * ae)
    F = (1.0 - E) / kk
    gk = g.vec(0.0, 0.0, -G) / kk
    pos = A('p0', 'FLOAT_VECTOR') + A('v0', 'FLOAT_VECTOR') * F + gk * (ae - F)
    vel = gk + (A('v0', 'FLOAT_VECTOR') - gk) * E
    geo_s = g.delete(geo_in, g.bool_not(alive))
    geo_s = g.set_position(geo_s, position=pos)
    r = A('size')
    half = g.length(vel) * 0.0035
    rot = g.align(g.vop('ADD', vel, (0.0, 0.0, 1e-4)), 'Z')
    sc = g.vec(r, r, r + half)
    unit = bpy.data.objects.get('sydney.drop.unit')
    if unit is None:
        bpy.ops.mesh.primitive_uv_sphere_add(radius=1.0, segments=16, ring_count=8, location=(0, 0, -5000))
        unit = bpy.context.object
        unit.name = 'sydney.drop.unit'
        kit.link(unit, kit.collection('sydney.protos'))
        for p in unit.data.polygons:
            p.use_smooth = True
        unit.hide_render = True
        unit.hide_viewport = True
    inst = g.instance(geo_s, g.object_geo(unit, as_instance=True, relative=False), rotation=rot, scale=sc)
    inst = g.set_material(inst, clear_water())
    g.output(inst)
    N.modifier(ob, g, 'drops')
    return ob


# ------------------------------------------------------------------------------------------------ breath fog and hearts


def heart_image(path: str, size: int = 384, width: float = 0.075):
    """The stroke-order image of a finger-drawn heart: R = the stroke's progress (0..1) along the outline starting
    at the top dip, G = coverage (anti-aliased). The heart fills the unit square with a margin."""
    th = np.linspace(0, 2 * math.pi, 2400)
    x = 16 * np.sin(th) ** 3
    y = 13 * np.cos(th) - 5 * np.cos(2 * th) - 2 * np.cos(3 * th) - np.cos(4 * th)
    x = x / 40.0 + 0.5
    y = (y + 2.5) / 40.0 + 0.5
    order = th / (2 * math.pi)
    yy, xx = np.mgrid[0:size, 0:size]
    u = (xx + 0.5) / size
    v = (yy + 0.5) / size
    img = np.zeros((size, size, 4), dtype=np.float32)
    best = np.full((size, size), 1e9)
    ordm = np.zeros((size, size))
    for i in range(0, len(th), 2):
        d = (u - x[i]) ** 2 + (v - y[i]) ** 2
        m = d < best
        best = np.where(m, d, best)
        ordm = np.where(m, order[i], ordm)
    dist = np.sqrt(best)
    cov = np.clip((width / 2 - dist) / (1.5 / size) + 0.5, 0, 1)
    img[..., 0] = np.where(cov > 0, ordm, 1.0)
    img[..., 1] = cov
    img[..., 3] = 1.0
    im = bpy.data.images.get('sydney.heart')
    if im is None:
        im = bpy.data.images.new('sydney.heart', size, size, alpha=True, float_buffer=False)
    im.colorspace_settings.name = 'Non-Color'
    im.pixels.foreach_set(img.ravel())
    im.update()
    try:
        im.pack()
    except Exception:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        im.filepath_raw = path
        im.file_format = 'PNG'
        im.save()
    return im


class Fog:
    """A thin shell just outside the glass facing the researcher. Its material shows breath fog (a soft blob that
    blooms and evaporates, keyed) and hearts wiped through it (stroke-order image, keyed progress per heart).
    UVs are the tangent-plane coordinates in cm around the shell's centre (u to the right seen from outside, v up)."""

    def __init__(self, globe: Globe, *, elev_deg=2.0, ang_deg=38.0, name='globe.fog', emit=0.0,
                 emit_color='#E8F0F8'):
        self.g = globe
        self.emit, self.emit_color = emit, emit_color
        D = globe.D
        up = Vector((0, 0, 1))
        c_dir = (D * math.cos(math.radians(elev_deg)) + up * math.sin(math.radians(elev_deg))).normalized()
        right = up.cross(c_dir).normalized()      # the viewer's right, seen from outside looking at -c_dir
        vv = c_dir.cross(right).normalized()      # up along the glass
        self.c_dir, self.right, self.up = c_dir, right, vv
        rad = R + 0.012
        verts, faces, uvs = [], [], []
        nr, na = 24, 64
        ang = math.radians(ang_deg)
        verts.append(tuple(c_dir * rad))
        for i in range(1, nr + 1):
            a = ang * i / nr
            for j in range(na):
                ph = 2 * math.pi * j / na
                d = (c_dir * math.cos(a) + (right * math.cos(ph) + vv * math.sin(ph)) * math.sin(a))
                verts.append(tuple(d * rad))
        for j in range(na):
            faces.append((0, 1 + j, 1 + (j + 1) % na))
        for i in range(nr - 1):
            for j in range(na):
                a0 = 1 + i * na + j
                a1 = 1 + i * na + (j + 1) % na
                b0 = a0 + na
                b1 = a1 + na
                faces.append((a0, b0, b1, a1))
        me = bpy.data.meshes.new(name)
        me.from_pydata([tuple(Vector(v) + Vector((0, 0, ZC))) for v in verts], [], faces)
        uvl = me.uv_layers.new(name='UVMap')
        for poly in me.polygons:
            for li in poly.loop_indices:
                vi = me.loops[li].vertex_index
                p = Vector(verts[vi])
                uvl.data[li].uv = (p.dot(right), p.dot(vv))
            poly.use_smooth = True
        me.update()
        ob = bpy.data.objects.new(name, me)
        globe.coll.objects.link(ob)
        ob.location = globe.origin
        self.obj = ob
        self.mat, self.vals = self._material(name + '.mat')
        me.materials.append(self.mat)
        ob.visible_shadow = False
        globe.adopt(ob)

    def uv_of(self, world_pt) -> tuple[float, float]:
        """(u, v) of a world point projected on the fog's tangent plane."""
        p = Vector(world_pt) - self.g.C
        return (p.dot(self.right), p.dot(self.up))

    def _material(self, name):
        m = bpy.data.materials.new(name)
        nt = m.node_tree
        nt.nodes.clear()
        out = nt.nodes.new('ShaderNodeOutputMaterial')
        vals = {}

        def val(key, v):
            nd = nt.nodes.new('ShaderNodeValue')
            nd.name = nd.label = key
            nd.outputs[0].default_value = v
            vals[key] = nd.outputs[0]
            return nd.outputs[0]

        def math_(op, a, b=None, c=None):
            nd = nt.nodes.new('ShaderNodeMath')
            nd.operation = op
            for i, x in enumerate((a, b, c)):
                if x is None:
                    continue
                if isinstance(x, (int, float)):
                    nd.inputs[i].default_value = x
                else:
                    nt.links.new(x, nd.inputs[i])
            return nd.outputs[0]

        uvn = nt.nodes.new('ShaderNodeUVMap')
        uvn.uv_map = 'UVMap'
        sep = nt.nodes.new('ShaderNodeSeparateXYZ')
        nt.links.new(uvn.outputs['UV'], sep.inputs[0])
        u, v = sep.outputs['X'], sep.outputs['Y']
        # breath blob: FogAmt * smooth falloff at FogR around (BU, BV), mottled by noise
        amt, fr = val('FogAmt', 0.0), val('FogR', 0.5)
        bu, bv = val('BU', 0.0), val('BV', 0.0)
        du, dv = math_('SUBTRACT', u, bu), math_('SUBTRACT', v, bv)
        dist = math_('SQRT', math_('ADD', math_('MULTIPLY', du, du), math_('MULTIPLY', dv, dv)))
        mr = nt.nodes.new('ShaderNodeMapRange')
        mr.interpolation_type = 'SMOOTHSTEP'
        nt.links.new(dist, mr.inputs['Value'])
        nt.links.new(fr, mr.inputs['From Min'])
        nt.links.new(math_('MULTIPLY', fr, 0.3), mr.inputs['From Max'])
        mr.inputs['To Min'].default_value = 0.0
        mr.inputs['To Max'].default_value = 1.0
        nz = nt.nodes.new('ShaderNodeTexNoise')
        nz.inputs['Scale'].default_value = 1.4
        nz.inputs['Detail'].default_value = 6.0
        nt.links.new(uvn.outputs['UV'], nz.inputs['Vector'])
        mott = math_('MULTIPLY_ADD', nz.outputs['Fac'], 0.8, 0.55)
        fog = math_('MULTIPLY', math_('MULTIPLY', mr.outputs['Result'], amt), mott)
        # fine droplet speckle
        vor = nt.nodes.new('ShaderNodeTexVoronoi')
        vor.inputs['Scale'].default_value = 26.0
        nt.links.new(uvn.outputs['UV'], vor.inputs['Vector'])
        spk = math_('MULTIPLY_ADD', vor.outputs['Distance'], 0.5, 0.75)
        fog = math_('MINIMUM', math_('MULTIPLY', fog, spk), 1.0)
        # hearts wiped through the fog
        img = bpy.data.images.get('sydney.heart')
        clears = []
        for k in (1, 2):
            hu, hv, hs, pr = val(f'H{k}U', 0.0), val(f'H{k}V', 0.0), val(f'H{k}S', 2.6), val(f'H{k}P', 0.0)
            cu = math_('ADD', math_('DIVIDE', math_('SUBTRACT', u, hu), hs), 0.5)
            cv = math_('ADD', math_('DIVIDE', math_('SUBTRACT', v, hv), hs), 0.5)
            cmb = nt.nodes.new('ShaderNodeCombineXYZ')
            nt.links.new(cu, cmb.inputs['X'])
            nt.links.new(cv, cmb.inputs['Y'])
            tex = nt.nodes.new('ShaderNodeTexImage')
            tex.image = img
            tex.extension = 'CLIP'
            tex.interpolation = 'Linear'
            nt.links.new(cmb.outputs['Vector'], tex.inputs['Vector'])
            sp = nt.nodes.new('ShaderNodeSeparateColor')
            nt.links.new(tex.outputs['Color'], sp.inputs['Color'])
            order, cov = sp.outputs['Red'], sp.outputs['Green']
            rev = math_('LESS_THAN', order, pr)
            clears.append(math_('MULTIPLY', rev, cov))
        clear = math_('MAXIMUM', clears[0], clears[1])
        # the wiped line is wet: slightly clearer than bare glass, with a faint bead at its edge
        fog = math_('MULTIPLY', fog, math_('SUBTRACT', 1.0, math_('MULTIPLY', clear, 0.97)))
        vals['fog'] = fog
        # shading: milky condensation (no refraction: dithered transparency lets Sydney show through it)
        dif = nt.nodes.new('ShaderNodeBsdfDiffuse')
        dif.inputs['Color'].default_value = kit.srgb('#D8E2EC')
        tl = nt.nodes.new('ShaderNodeBsdfTranslucent')
        tl.inputs['Color'].default_value = kit.srgb('#C8D6E6')
        gl = nt.nodes.new('ShaderNodeBsdfGlossy')
        gl.inputs['Roughness'].default_value = 0.35
        m1 = nt.nodes.new('ShaderNodeMixShader')
        m1.inputs['Fac'].default_value = 0.45
        nt.links.new(dif.outputs[0], m1.inputs[1])
        nt.links.new(tl.outputs[0], m1.inputs[2])
        milky = nt.nodes.new('ShaderNodeMixShader')
        milky.inputs['Fac'].default_value = 0.12
        nt.links.new(m1.outputs[0], milky.inputs[1])
        nt.links.new(gl.outputs[0], milky.inputs[2])
        lit = milky.outputs[0]
        if self.emit > 0.0:
            # self-lit: the fog sits in Sydney's shadow and is seen through the glass, so lit diffuse alone renders
            # it as a dark smudge; a faint glow keeps it reading as white condensation (keyable: vals['Emit'])
            em = nt.nodes.new('ShaderNodeEmission')
            em.inputs['Color'].default_value = kit.srgb(self.emit_color)
            nt.links.new(val('Emit', self.emit), em.inputs['Strength'])
            add = nt.nodes.new('ShaderNodeAddShader')
            nt.links.new(lit, add.inputs[0])
            nt.links.new(em.outputs[0], add.inputs[1])
            lit = add.outputs[0]
        tr = nt.nodes.new('ShaderNodeBsdfTransparent')
        mix = nt.nodes.new('ShaderNodeMixShader')
        nt.links.new(math_('MINIMUM', math_('MULTIPLY', fog, 0.95), 0.86), mix.inputs['Fac'])
        nt.links.new(tr.outputs[0], mix.inputs[1])
        nt.links.new(lit, mix.inputs[2])
        nt.links.new(mix.outputs[0], out.inputs['Surface'])
        m.surface_render_method = 'DITHERED'
        m.use_backface_culling = True
        m.diffuse_color = (0.9, 0.95, 1.0, 0.3)
        return m, {k: v for k, v in vals.items() if k != 'fog'}

    def key(self, name, t, value, interp='LINEAR'):
        sock = self.vals[name]
        geo.keyp(sock, 'default_value', t, value, interp=interp)

    def set(self, name, value):
        self.vals[name].default_value = value


# ------------------------------------------------------------------------------------------------ fx workaround


def fix_domain_range(dom, t0, t1, flow_obj=None):
    """Work around pdoom.fx.smoke.domain(): it assigns cache_frame_start before cache_frame_end, and Blender clamps
    the start to the default end (250), so a domain late in the song simulates from frame 250. Set the end first,
    then the start. flow_obj: the liquid body whose GEOMETRY inflow liquid.spill() keyed off at (250 + 1.5):
    move that key to the real first frame + 1.5."""
    from pdoom.fx import smoke as _smoke
    f0, f1 = _smoke._frames(t0, t1)
    ds = dom.modifiers['fluid'].domain_settings
    ds.cache_frame_end = f1
    ds.cache_frame_start = f0
    assert (ds.cache_frame_start, ds.cache_frame_end) == (f0, f1), (ds.cache_frame_start, ds.cache_frame_end)
    if flow_obj is not None:
        for fc in kit.fcurves(flow_obj):
            if fc.data_path.endswith('use_inflow'):
                for kp in fc.keyframe_points:
                    if 1.0 < kp.co.x < f0:
                        kp.co.x = f0 + 1.5
                fc.update()
    print(f'[run] fixed {dom.name} cache frames: {f0}-{f1}', flush=True)
    return f0, f1


# ------------------------------------------------------------------------------------------------ tears


def tear(name, coll, mat):
    o = kit.sphere(name, 0.16, (0, 0, 0), m=mat, coll=coll, subdiv=3)
    o.scale = (1.0, 1.0, 1.35)
    return o
