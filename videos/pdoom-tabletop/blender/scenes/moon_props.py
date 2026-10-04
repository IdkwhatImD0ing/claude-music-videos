"""Props for `moon` (scene-local): the paper moon on its string, the glowing lines that converge into the Omega
Point, and the brass FLOP/s odometer."""
from __future__ import annotations

import math

import bmesh
import bpy
import numpy as np
from mathutils import Matrix, Vector

from pdoom import kit
from pdoom import timing as tm
from pdoom.fx import _nodes as N
from pdoom.sets import geo
from pdoom.sets import materials as M
from pdoom.timing import FPS

# ------------------------------------------------------------------------------------------------ the paper moon

MOON_R = 9.0
INNER_R = 7.3
INNER_C = (3.6, 0.7)


def _inner_r(phi_deg):
    """The face profile along the crescent's inner edge (a nose, lips, a chin)."""
    def bump(c, w, h):
        return h * math.exp(-((phi_deg - c) / w) ** 2)
    return INNER_R - bump(176.0, 7.5, 1.35) - bump(197.0, 4.0, 0.5) - bump(206.0, 4.0, 0.45) - bump(226.0, 10.0, 0.6) \
        + bump(187.0, 3.0, 0.25)


def crescent_poly(n=220):
    cx, cz = INNER_C
    outer, inner = [], []
    for k in range(n):
        a = 2 * math.pi * k / n
        x, z = MOON_R * math.cos(a), MOON_R * math.sin(a)
        ang = math.degrees(math.atan2(z - cz, x - cx)) % 360
        if math.hypot(x - cx, z - cz) > _inner_r(ang):
            outer.append((a, x, z))
    for k in range(n * 2):
        a = 2 * math.pi * k / (n * 2)
        r = _inner_r(math.degrees(a) % 360)
        x, z = cx + r * math.cos(a), cz + r * math.sin(a)
        if math.hypot(x, z) < MOON_R:
            inner.append((a, x, z))
    # order: the outer arc counter-clockwise through the left (angle pi), the inner arc back clockwise
    outer.sort(key=lambda p: (p[0] - math.pi / 2) % (2 * math.pi))
    inner.sort(key=lambda p: -((p[0] - math.pi / 2) % (2 * math.pi)))
    return [(x, z) for _, x, z in outer] + [(x, z) for _, x, z in inner]


def moon_face_image(size=512):
    """Paper colour, a pencil-ink Méliès face: an almond eye, a brow, a smile and a blush. RGBA float."""
    ext = MOON_R + 0.5
    yy, xx = np.mgrid[0:size, 0:size]
    x = (xx + 0.5) / size * 2 * ext - ext
    z = (yy + 0.5) / size * 2 * ext - ext
    ink = np.zeros((size, size))
    blush = np.zeros((size, size))
    cx, cz = INNER_C
    # eye: an almond outline and a pupil, set into the crescent above the nose
    ex, ez = cx - 8.2, cz + 2.4
    e = ((x - ex) / 1.05) ** 2 + ((z - ez) / 0.55) ** 2
    ink = np.maximum(ink, np.clip(1 - np.abs(e - 1) / 0.28, 0, 1))
    ink = np.maximum(ink, np.clip((0.3 - np.hypot(x - ex - 0.25, z - ez)) / 0.05, 0, 1))
    # brow
    b = np.hypot(x - ex, z - (ez - 1.2))
    ink = np.maximum(ink, np.clip(1 - np.abs(b - 2.0) / 0.1, 0, 1) * ((z - (ez - 1.2)) > 1.55) * (x > ex - 1.4))
    # smile near the lips
    mx, mz = cx - 7.4, cz - 2.5
    m = np.hypot(x - (mx - 0.2), z - (mz + 1.1))
    ink = np.maximum(ink, np.clip(1 - np.abs(m - 1.2) / 0.09, 0, 1) * (z < mz + 0.7) * (x < mx + 0.4) * (x > mx - 1.1))
    # blush on the cheek
    blush = np.clip(1 - np.hypot(x - (cx - 9.0), z - (cz - 1.4)) / 1.1, 0, 1) ** 1.5
    img = np.zeros((size, size, 4), dtype=np.float32)
    paper = np.array([0.92, 0.80, 0.50])
    pink = np.array([0.85, 0.38, 0.30])
    inkc = np.array([0.08, 0.06, 0.05])
    col = paper[None, None] * (1 - blush[..., None] * 0.55) + pink[None, None] * blush[..., None] * 0.55
    col = col * (1 - ink[..., None]) + inkc[None, None] * ink[..., None]
    img[..., :3] = col
    img[..., 3] = 1.0
    im = bpy.data.images.new('moon.face', size, size, alpha=True)
    im.colorspace_settings.name = 'sRGB'
    im.pixels.foreach_set(img.ravel())
    im.update()
    try:
        im.pack()
    except Exception:
        pass
    return im, ext, (ex, ez)


class PaperMoon:
    """A card crescent in the XZ plane (facing -Y), hanging by a thread from its top point. root = the pivot at the
    top of the thread (swing it); moon = the card."""

    def __init__(self, coll, loc, *, yaw_deg=0.0, thread=70.0):
        self.coll = coll
        poly = crescent_poly()
        img, ext, eye = moon_face_image()
        self.eye_local = Vector((eye[0], 0.0, eye[1]))
        m = bpy.data.materials.new('moon.paper')
        nt = m.node_tree
        b = nt.nodes.get('Principled BSDF')
        tex = nt.nodes.new('ShaderNodeTexImage')
        tex.image = img
        uvn = nt.nodes.new('ShaderNodeUVMap')
        nt.links.new(uvn.outputs['UV'], tex.inputs['Vector'])
        # paper grain on top of the painted face
        nz = nt.nodes.new('ShaderNodeTexNoise')
        nz.inputs['Scale'].default_value = 3.0
        nz.inputs['Detail'].default_value = 10.0
        bump = nt.nodes.new('ShaderNodeBump')
        bump.inputs['Strength'].default_value = 0.25
        bump.inputs['Distance'].default_value = 0.02
        nt.links.new(nz.outputs['Fac'], bump.inputs['Height'])
        nt.links.new(bump.outputs['Normal'], b.inputs['Normal'])
        nt.links.new(tex.outputs['Color'], b.inputs['Base Color'])
        b.inputs['Roughness'].default_value = 0.85
        b.inputs['Subsurface Weight'].default_value = 0.08
        b.inputs['Emission Color'].default_value = kit.srgb('#FFE2A0')
        b.inputs['Emission Strength'].default_value = 0.0
        self.mat = m
        self.emit = b.inputs['Emission Strength']
        # the card: an extruded crescent, UVs from x/z
        bm = bmesh.new()
        vs = [bm.verts.new((x, 0.12, z)) for x, z in poly]
        f = bm.faces.new(vs)
        ext_ = bmesh.ops.extrude_face_region(bm, geom=[f])
        top = [e for e in ext_['geom'] if isinstance(e, bmesh.types.BMVert)]
        bmesh.ops.translate(bm, verts=top, vec=(0, -0.24, 0))
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
        uv = bm.loops.layers.uv.new('UVMap')
        for face in bm.faces:
            for lp in face.loops:
                co = lp.vert.co
                lp[uv].uv = ((co.x + ext) / (2 * ext), (co.z + ext) / (2 * ext))
        me = bpy.data.meshes.new('moon.card')
        bm.to_mesh(me)
        bm.free()
        self.card = bpy.data.objects.new('moon.card', me)
        coll.objects.link(self.card)
        me.materials.append(m)
        geo.bevel(self.card, 0.05, 2)
        # the thread: from the card's top to the pivot above
        top_pt = max(poly, key=lambda p: p[1])
        self.hang = Vector((top_pt[0], 0.0, top_pt[1] - 0.3))
        self.root = kit.empty('moon.pivot', (0, 0, 0), coll, 'SPHERE', 1.0)
        self.root.rotation_mode = 'XYZ'
        loc = Vector(loc)
        self.root.location = loc + self.hang + Vector((0, 0, thread))      # loc is the card's centre
        self.root.rotation_euler = (0, 0, math.radians(yaw_deg))
        # card relative to the pivot: hang point straight below
        self.card.location = -self.hang - Vector((0, 0, thread))
        self.card.parent = self.root
        thr = geo.curve_tube('moon.thread', [tuple(self.hang), tuple(self.hang + Vector((0, 0, thread + 2.0)))],
                             0.03, coll=coll, m=M.solid('moon.thread', '#EDE8DC', rough=0.8))
        thr.location = -self.hang - Vector((0, 0, thread))
        thr.parent = self.root
        self.thread = thr
        self.thread_len = thread

    def eye_world(self):
        bpy.context.view_layer.update()
        return self.card.matrix_world @ self.eye_local

    def swing(self, t0, amp_deg=9.0, freq=0.9, damp=1.6, axis=0, t1=None):
        """A damped pendulum swing after an impact at t0 (keys every frame)."""
        t1 = t1 if t1 is not None else t0 + 4.0
        base = self.root.rotation_euler.copy()
        f0, f1 = int(math.floor(t0 * FPS)), int(math.ceil(t1 * FPS))
        for f in (tm.out_frames(f0 - 1, f1) if tm.SMOOTH else range(f0 - 1, f1 + 1)):
            t = f / FPS
            a = 0.0 if t < t0 else math.radians(amp_deg) * math.exp(-damp * (t - t0)) * \
                math.sin(2 * math.pi * freq * (t - t0))
            r = base.copy()
            r[axis] += a
            r[1 - axis if axis < 2 else 0] += 0.35 * a
            self.root.rotation_euler = r
            self.root.keyframe_insert('rotation_euler', frame=f)
        for fc in kit.fcurves(self.root):
            for kp in fc.keyframe_points:
                kp.interpolation = 'LINEAR'
        self.root.rotation_euler = base


# ------------------------------------------------------------------------------------------------ converging lines


def line_mat(name='omega.lines'):
    """Emission from the per-point attributes 'col' (colour) and 'heat' (0..1): brighter and whiter as a line is
    pulled into the Omega Point."""
    if name in bpy.data.materials:
        return bpy.data.materials[name]
    m = bpy.data.materials.new(name)
    nt = m.node_tree
    nt.nodes.clear()
    out = nt.nodes.new('ShaderNodeOutputMaterial')
    ac = nt.nodes.new('ShaderNodeAttribute')
    ac.attribute_type = 'GEOMETRY'
    ac.attribute_name = 'col'
    ah = nt.nodes.new('ShaderNodeAttribute')
    ah.attribute_type = 'GEOMETRY'
    ah.attribute_name = 'heat'
    ab = nt.nodes.new('ShaderNodeAttribute')
    ab.attribute_type = 'GEOMETRY'
    ab.attribute_name = 'bright'
    mix = nt.nodes.new('ShaderNodeMix')
    mix.data_type = 'RGBA'
    sk = {s.identifier: s for s in mix.inputs}
    nt.links.new(ah.outputs['Fac'], sk['Factor_Float'])
    nt.links.new(ac.outputs['Color'], sk['A_Color'])
    sk['B_Color'].default_value = (1.0, 0.97, 0.9, 1.0)
    em = nt.nodes.new('ShaderNodeEmission')
    nt.links.new(next(s for s in mix.outputs if s.identifier == 'Result_Color'), em.inputs['Color'])
    mul = nt.nodes.new('ShaderNodeMath')
    mul.operation = 'MULTIPLY_ADD'
    mul.inputs[1].default_value = 5.0
    nt.links.new(ah.outputs['Fac'], mul.inputs[0])
    nt.links.new(ab.outputs['Fac'], mul.inputs[2])
    nt.links.new(mul.outputs[0], em.inputs['Strength'])
    nt.links.new(em.outputs[0], out.inputs['Surface'])
    m.diffuse_color = (0.5, 1.0, 0.2, 1.0)
    return m


class Lines:
    """Glowing polylines drawn in (each point appears at its 'rev' time) and pulled into one point: from
    t_conv + delay a point slides (ease-in) to `target` over `dur` seconds. One mesh of edges, one node tree."""

    def __init__(self, name, coll, target):
        self.name = name
        self.coll = coll
        self.target = Vector(target)
        self.rows = {k: [] for k in ('p', 'rev', 'dl', 'rad', 'col', 'bright')}
        self.edges = []

    def add(self, pts, *, radius, color, bright=4.0, rev=None, delay=None):
        """pts: world points; rev: per-point reveal times (None: always); delay: per-point convergence delays."""
        i0 = len(self.rows['p'])
        c = kit.srgb(color)[:3] if isinstance(color, str) else color
        n = len(pts)
        for i, p in enumerate(pts):
            self.rows['p'].append(tuple(p))
            self.rows['rev'].append(-1e6 if rev is None else rev[i])
            self.rows['dl'].append(0.0 if delay is None else delay[i])
            self.rows['rad'].append(radius)
            self.rows['col'].append(c)
            self.rows['bright'].append(bright)
        for i in range(n - 1):
            self.edges.append((i0 + i, i0 + i + 1))

    def build(self, t_conv, dur=0.45):
        me = bpy.data.meshes.new(self.name)
        me.from_pydata(self.rows['p'], self.edges, [])
        for nm in ('rev', 'dl', 'rad', 'bright'):
            a = me.attributes.new(nm, 'FLOAT', 'POINT')
            a.data.foreach_set('value', np.asarray(self.rows[nm], dtype=np.float32))
        a = me.attributes.new('col', 'FLOAT_COLOR', 'POINT')
        cols = np.array([(*c, 1.0) for c in self.rows['col']], dtype=np.float32)
        a.data.foreach_set('color', cols.ravel())
        me.update()
        ob = bpy.data.objects.new(self.name, me)
        self.coll.objects.link(ob)
        g = N.Tree(f'{self.name}.gn')
        geo_in = g.input_geometry()
        tc = g.param('Converge', 'FLOAT', t_conv)
        t = g.time()

        def A(nm, kind='FLOAT'):
            return g.out(g.node('GeometryNodeInputNamedAttribute', data_type=kind, inputs={'Name': nm}), 'Attribute')
        rev = A('rev')
        geo_s = g.delete(geo_in, t < rev)
        u = g.clamp((t - (tc + A('dl'))) / dur)
        w = u * u * u
        pos = g.position()
        tgt = g.vec(*self.target)
        newp = pos + (tgt - pos) * w
        geo_s = g.set_position(geo_s, position=newp)
        heat = g.clamp(u * 1.6)
        # a fresh point flashes as it is drawn in
        fresh = g.clamp(1.0 - (t - rev) / 0.25)
        geo_s = g.store(geo_s, 'heat', g.max(heat, fresh * 0.5))
        crv = g.out(g.node('GeometryNodeMeshToCurve', inputs={'Mesh': geo_s}))
        rad = A('rad') * (1.0 - 0.75 * w)
        crv = g.out(g.node('GeometryNodeSetCurveRadius', inputs={'Curve': crv, 'Radius': rad}))
        prof = g.out(g.node('GeometryNodeCurvePrimitiveCircle', inputs={'Resolution': 6, 'Radius': 1.0}))
        c2m = g.node('GeometryNodeCurveToMesh', inputs={'Curve': crv, 'Profile Curve': prof, 'Fill Caps': True})
        if any(s.name == 'Scale' for s in c2m.inputs):     # 5.2: the profile is scaled by 'Scale', not the radius
            g.feed(g.inp(c2m, 'Scale'), g.out(g.node('GeometryNodeInputRadius')))
        mesh = g.out(c2m)
        mesh = g.set_material(mesh, line_mat())
        g.output(mesh)
        N.modifier(ob, g, 'lines')
        ob.visible_shadow = False
        self.obj = ob
        return ob


# ------------------------------------------------------------------------------------------------ the odometer


def _digit_wheel(coll, name, glyphs, radius, width, mats):
    """A brass wheel (axis X) with glyphs engraved around its rim: glyph k faces -Y (the window) when the wheel is
    turned by -k * 360/len(glyphs) degrees about X... i.e. rotation_euler.x = k * step brings glyph k to the front."""
    n = len(glyphs)
    step = 2 * math.pi / n
    rim = kit.cylinder(f'{name}.rim', radius, width, (0, 0, 0), verts=64, m=mats['wheel'], coll=coll,
                       rot=(0, math.radians(90), 0))
    parts = [rim]
    for sx in (-1, 1):
        fl = kit.cylinder(f'{name}.flange{sx}', radius + 0.1, 0.12, (sx * (width / 2 + 0.03), 0, 0), verts=64,
                          m=mats['flange'], coll=coll, rot=(0, math.radians(90), 0))
        parts.append(fl)
    for k, ch in enumerate(glyphs):
        tx = geo.text_mesh(f'{name}.g{k}', ch, radius * 0.56, coll=coll, m=mats['ink'], extrude=0.012)
        # glyph k sits at angle -k * step around X from the front (-Y), reading upright when it is at the front
        a = -k * step
        R = Matrix.Rotation(a, 4, 'X')
        tx.matrix_world = R @ Matrix.Translation((0, -radius - 0.004, 0)) @ Matrix.Rotation(math.radians(90), 4, 'X')
        parts.append(tx)
    bpy.context.view_layer.update()
    for p in parts[1:]:
        p.data.transform(p.matrix_world)
        p.matrix_world = Matrix.Identity(4)
    geo.apply_mods(rim)
    rim.data.transform(rim.matrix_world)
    rim.matrix_world = Matrix.Identity(4)
    w = geo.join(parts, name)
    w.rotation_mode = 'XYZ'
    return w, step


class Odometer:
    """A walnut-and-brass counter: a mantissa wheel, an 'E' flap, two exponent wheels, behind a glass window, with
    a FLOP/s plate and a little bulb on top. Faces -Y. root = the base centre (key it for jolts)."""

    def __init__(self, coll, loc, yaw_deg=0.0):
        self.coll = coll
        brass = M.brass('odo.brass', '#C9A259', rough=0.22)
        mats = {'wheel': M.solid('odo.band', '#EFE6CC', rough=0.3, coat=0.6, coat_rough=0.08),
                'flange': M.solid('odo.wheelbrass', '#D2AE62', rough=0.24, metal=1.0, micro=(30.0, 0.02)),
                'card': M.solid('odo.ivory', '#EDE3C8', rough=0.35, coat=0.5, coat_rough=0.1),
                'ink': M.solid('odo.ink', '#141110', rough=0.4),
                'brass': brass}
        walnut = M.tex_mat('odo.walnut', 'desk_wood', 20, tint='#5A3520', tint_amount=0.6, val=0.85,
                           rough=(0.25, 0.4), coat=0.8, coat_rough=0.05, fallback='#4A2E1C')
        self.root = kit.empty('odometer', tuple(loc), coll, 'ARROWS', 2.0)
        self.root.rotation_euler = (0, 0, math.radians(yaw_deg))
        parts = []
        body = geo.box('odo.body', (13.0, 6.0, 6.2), (0, 0, 3.4), bev=0.35, m=walnut, coll=coll)
        plinth = geo.box('odo.plinth', (14.2, 7.0, 0.5), (0, 0, 0.25), bev=0.12, m=walnut, coll=coll)
        parts += [body, plinth]
        # the window: the wheels stand proud of the body's front, inside a brass frame, behind a glass pane
        WZ, WX, WH = 3.9, 4.95, 0.64
        # a slim bezel: the wheels are sunk in the body, only their fronts show through the window
        for nm, size, loc in (('top', (2 * WX + 0.6, 0.62, 0.36), (0, -3.24, WZ + WH + 0.18)),
                              ('bot', (2 * WX + 0.6, 0.62, 0.36), (0, -3.24, WZ - WH - 0.18)),
                              ('l', (0.3, 0.62, 2 * WH + 0.72), (-WX - 0.15, -3.24, WZ)),
                              ('r', (0.3, 0.62, 2 * WH + 0.72), (WX + 0.15, -3.24, WZ))):
            parts.append(geo.box(f'odo.frame.{nm}', size, loc, bev=0.08, m=brass, coll=coll))
        glass = geo.box('odo.glass', (2 * WX + 0.1, 0.04, 2 * WH + 0.1), (0, -3.5, WZ),
                        m=M.glass('odo.glass', rough=0.02), coll=coll)
        parts.append(glass)
        # engraved brass plate below the window
        plate = geo.box('odo.plate', (5.2, 0.12, 0.9), (0, -3.05, 1.15), bev=0.05, m=brass, coll=coll)
        parts.append(plate)
        # the label's own ink (odo.ink is shared with the digits and the E): it glows on "FLOPs"
        self.label_mat = kit.mat('odo.labelink', '#141110', rough=0.4, emit='#FFC47A', emit_strength=0.0)
        lab = geo.text_mesh('odo.label', 'FLOP/s', 0.62, coll=coll, m=self.label_mat, extrude=0.01)
        lab.matrix_world = Matrix.Translation((0, -3.13, 1.12)) @ Matrix.Rotation(math.radians(90), 4, 'X')
        parts.append(lab)
        # the bulb on top (lights on "FLOPs")
        socket = kit.cylinder('odo.socket', 0.55, 0.6, (4.8, 0.8, 6.8), verts=24, m=brass, coll=coll)
        self.bulb_mat = kit.mat('odo.bulb', '#FFD9A0', rough=0.05, transmission=0.4, emit='#FFB24A', emit_strength=0.0,
                                coat=1.0)
        bulb = kit.sphere('odo.bulbglass', 0.6, (4.8, 0.8, 7.55), m=self.bulb_mat, coll=coll, subdiv=3)
        parts += [socket, bulb]
        # the wheels: mantissa, E flap, tens, ones (axis X), proud of the body inside the frame
        R_W, W_W = 2.0, 1.55
        self.wheels = {}
        digits = '0123456789'
        xs = {'m': -3.3, 'e1': 1.3, 'e0': 3.2}
        for key, x in xs.items():
            w, step = _digit_wheel(coll, f'odo.wheel.{key}', digits, R_W, W_W, mats)
            w.location = (x, -1.16, WZ)
            self.wheels[key] = w
            self.step = step
        # the E flap: a card on a horizontal pin through its middle; blank on the back, 'E' on the front
        self.flap = kit.empty('odo.flap', (-1.05, -3.2, WZ), coll, 'PLAIN_AXES', 0.3)
        self.flap.rotation_mode = 'XYZ'
        fl = geo.box('odo.flapcard', (1.4, 0.05, 1.22), (-1.05, -3.2, WZ), bev=0.02, m=mats['card'], coll=coll)
        e_txt = geo.text_mesh('odo.E', 'E', 1.05, coll=coll, m=mats['ink'], extrude=0.01)
        e_txt.matrix_world = Matrix.Translation((-1.05, -3.235, WZ - 0.05)) @ Matrix.Rotation(math.radians(90), 4, 'X')
        bpy.context.view_layer.update()
        for o in (fl, e_txt):
            mw = o.matrix_world.copy()
            o.parent = self.flap
            o.matrix_parent_inverse = self.flap.matrix_world.inverted()
            o.matrix_world = mw
        # the E starts hidden behind (the flap shows its back, a dot) : rotate the flap so its back faces front
        self.e_light = kit.point('odo.elight', (-1.05, -5.2, 5.2), power=0.0, radius=0.6, color='#FFD08A', coll=coll)
        self.bulb_light = kit.point('odo.bulblight', (4.8, 0.2, 7.6), power=0.0, radius=0.6, color='#FFB24A',
                                    coll=coll)
        for lt in (self.e_light, self.bulb_light):
            lt.data.specular_factor = 0.0          # no hot disc reflected in the window glass
        for o in parts + list(self.wheels.values()) + [self.flap, self.e_light, self.bulb_light]:
            if o.parent is None:
                o.parent = self.root
        self.parts = parts

    def key_wheel(self, key, t0, t1, value_fn):
        """Key a wheel's displayed value (float digits; 3.0 shows '3') every frame from t0 to t1 (smooth)."""
        w = self.wheels[key]
        f0, f1 = int(math.floor(t0 * FPS)), int(math.ceil(t1 * FPS))
        for f in (tm.out_frames(f0 - 1, f1 + 1) if tm.SMOOTH else range(f0 - 1, f1 + 2)):
            v = value_fn(f / FPS)
            w.rotation_euler = (v * self.step, 0.0, 0.0)
            w.keyframe_insert('rotation_euler', index=0, frame=f)
        for fc in kit.fcurves(w):
            for kp in fc.keyframe_points:
                kp.interpolation = 'LINEAR'


# ------------------------------------------------------------------------------------------------ exhaust puffs


def _puff_mat(name, color, density, glow=0.0, glow_color='#FFB894'):
    """A soft ball of smoke for a unit sphere instance: density falls off to the rim (object coords), broken up by
    noise that differs per instance. glow: emission with the same falloff (hot exhaust; also keeps a dense puff from
    rendering as a dark self-shadowed lump)."""
    m = bpy.data.materials.get(name)
    if m is not None:
        return m
    m = bpy.data.materials.new(name)
    nt = m.node_tree
    nt.nodes.clear()
    out = nt.nodes.new('ShaderNodeOutputMaterial')
    tc = nt.nodes.new('ShaderNodeTexCoord')
    ln = nt.nodes.new('ShaderNodeVectorMath')
    ln.operation = 'LENGTH'
    nt.links.new(tc.outputs['Object'], ln.inputs[0])
    fall = nt.nodes.new('ShaderNodeMapRange')
    fall.interpolation_type = 'SMOOTHSTEP'
    fall.inputs['From Min'].default_value = 1.0
    fall.inputs['From Max'].default_value = 0.45
    nt.links.new(ln.outputs['Value'], fall.inputs['Value'])
    oi = nt.nodes.new('ShaderNodeObjectInfo')
    nz = nt.nodes.new('ShaderNodeTexNoise')
    nz.noise_dimensions = '4D'
    nz.inputs['Scale'].default_value = 1.6
    nz.inputs['Detail'].default_value = 3.0
    nt.links.new(tc.outputs['Object'], nz.inputs['Vector'])
    wr = nt.nodes.new('ShaderNodeMath')
    wr.operation = 'MULTIPLY'
    wr.inputs[1].default_value = 40.0
    nt.links.new(oi.outputs['Random'], wr.inputs[0])
    nt.links.new(wr.outputs[0], nz.inputs['W'])
    nm = nt.nodes.new('ShaderNodeMapRange')
    nm.inputs['From Min'].default_value = 0.3
    nm.inputs['From Max'].default_value = 0.7
    nm.inputs['To Min'].default_value = 0.45
    nm.inputs['To Max'].default_value = 1.4
    nt.links.new(nz.outputs['Fac'], nm.inputs['Value'])
    mul = nt.nodes.new('ShaderNodeMath')
    mul.operation = 'MULTIPLY'
    nt.links.new(fall.outputs['Result'], mul.inputs[0])
    nt.links.new(nm.outputs['Result'], mul.inputs[1])
    mul2 = nt.nodes.new('ShaderNodeMath')
    mul2.operation = 'MULTIPLY'
    mul2.inputs[1].default_value = density
    nt.links.new(mul.outputs[0], mul2.inputs[0])
    pv = nt.nodes.new('ShaderNodeVolumePrincipled')
    pv.inputs['Color'].default_value = kit.srgb(color)
    pv.inputs['Density Attribute'].default_value = ''
    pv.inputs['Anisotropy'].default_value = 0.3
    nt.links.new(mul2.outputs[0], pv.inputs['Density'])
    if glow > 0.0:
        mul3 = nt.nodes.new('ShaderNodeMath')
        mul3.operation = 'MULTIPLY'
        mul3.inputs[1].default_value = glow
        nt.links.new(mul.outputs[0], mul3.inputs[0])
        pv.inputs['Emission Color'].default_value = kit.srgb(glow_color)
        nt.links.new(mul3.outputs[0], pv.inputs['Emission Strength'])
    nt.links.new(pv.outputs['Volume'], out.inputs['Volume'])
    m.diffuse_color = kit.srgb(color)
    return m


def exhaust_puffs(name, coll, *, births, frame_at, nozzle=(0.0, 0.0, 0.0), color='#E6E0D6', density=1.2, glow=0.0,
                  glow_color='#FFB894',
                  life=0.065, full=0.036, r=(3.0, 4.4), push=(50.0, 90.0), drag=10.0, seed=7):
    """The youngest smoke right behind a flying nozzle, as a pure function of song time: one soft volume puff is
    born at each time in `births` at the nozzle (frame_at(t) -> the emitter's world Matrix at t; `nozzle` in its
    local space), pushed back along the emitter's -Z with drag, growing from r[0] to r[1] cm. A puff is fully dense
    until age `full`, then thins in two steps and is gone at `life`. Rides over a Mantaflow trail, whose cache only
    steps once per 24 fps frame, to fill the gap that opens behind a fast nozzle between two cache steps."""
    rng = np.random.default_rng(seed)
    n = len(births)
    p0, v0 = np.zeros((n, 3)), np.zeros((n, 3))
    for i, tb in enumerate(births):
        Mw = frame_at(tb)
        R3 = Mw.to_3x3()
        ax = (R3 @ Vector((0, 0, 1))).normalized()
        jit = Vector(rng.normal(0.0, 0.35, 3))
        p0[i] = Mw @ (Vector(nozzle) + jit)
        lat = Vector(rng.normal(0.0, 12.0, 3))
        lat -= ax * lat.dot(ax)
        v0[i] = -ax * rng.uniform(*push) + lat
    me = bpy.data.meshes.new(name)
    me.vertices.add(n)
    me.vertices.foreach_set('co', p0.astype(np.float32).ravel())
    for nm_, arr in (('p0', p0), ('v0', v0), ('birth', np.asarray(births, dtype=np.float64)),
                     ('rs', rng.uniform(0.85, 1.15, n))):
        arr = np.asarray(arr, dtype=np.float32)
        vec = arr.ndim == 2
        a = me.attributes.new(nm_, 'FLOAT_VECTOR' if vec else 'FLOAT', 'POINT')
        a.data.foreach_set('vector' if vec else 'value', arr.ravel())
    me.update()
    ob = bpy.data.objects.new(name, me)
    coll.objects.link(ob)
    # one unit-sphere prototype per density step (an instance carries its prototype's material)
    pc = kit.collection(f'{name}.protos')
    steps = ((0.0, full, 1.0), (full, full + (life - full) * 0.5, 0.55), (full + (life - full) * 0.5, life, 0.22))
    protos = []
    for k, (_, _, dk) in enumerate(steps):
        pr = kit.sphere(f'{name}.proto{k}', 1.0, (0, 0, -10000),
                        m=_puff_mat(f'{name}.mat{k}', color, density * dk, glow * dk ** 1.5, glow_color), coll=pc,
                        subdiv=3)
        pr.hide_render = True
        protos.append(pr)
    g = N.Tree(f'{name}.gn')
    geo_in = g.input_geometry()

    def attr(nm_, kind='FLOAT'):
        return g.out(g.node('GeometryNodeInputNamedAttribute', data_type=kind, inputs={'Name': nm_}), 'Attribute')

    a = g.time() - attr('birth')
    alive = g.bool_and(a >= 0.0, a < life)
    pts = g.out(g.node('GeometryNodeSetID', inputs={'Geometry': geo_in, 'ID': g.index()}))
    pts = g.delete(pts, g.bool_not(alive))
    ae = g.max(a, 0.0)
    F = (1.0 - g.exp(-drag * ae)) * (1.0 / drag)
    pts = g.set_position(pts, position=attr('p0', 'FLOAT_VECTOR') + attr('v0', 'FLOAT_VECTOR') * F)
    rad = (r[0] + (r[1] - r[0]) * g.clamp(ae * (1.0 / life))) * attr('rs')
    sc = g.vec(rad, rad, rad)
    outs = []
    for (lo, hi, _), pr in zip(steps, protos):
        sel = g.bool_and(a >= lo, a < hi)
        outs.append(g.instance(pts, g.object_geo(pr, as_instance=True, relative=False), scale=sc, selection=sel))
    g.output(g.join(*outs))
    N.modifier(ob, g, 'puffs')
    return ob
