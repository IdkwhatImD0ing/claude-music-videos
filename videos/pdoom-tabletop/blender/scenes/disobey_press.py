"""Props for disobey's "Post-Chinchilla, super-dense": a toy hydraulic press, a fluffy chinchilla plush (particle-hair
fur) and the tiny glowing cube it gets crushed into.

    pr = build_press(coll, loc=(x, y, 0), yaw=0)
    ch = build_chinchilla(coll, loc=pr.anvil_point(), yaw=0)
    crush(pr, ch, t_down=115.24, t_flat=116.02, t_cube=116.1, t_up=116.16, t_glow=116.56)

All sizes in cm (1 BU = 1 cm). The press is 22 cm tall; the plush sits 5.6 cm tall on the 7 x 7 cm anvil.
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
from pdoom.sets import geo as sgeo

FPS = tm.FPS


def _T(p):
    return Matrix.Translation(Vector(p))


def _R(ex, ey, ez):
    from mathutils import Euler
    return Euler((math.radians(ex), math.radians(ey), math.radians(ez)), 'XYZ').to_matrix().to_4x4()


def _paint(name, color, rough=0.32):
    return looks.gloss(name, color, rough=rough, coat=0.6, coat_rough=0.12, bump=0.05)


class Press:
    """Handles: root (Empty), platen (Empty: the moving head), anvil_top (z of the anvil surface, local),
    platen_rest (local z of the platen's bottom face at rest)."""

    def anvil_point(self):
        r = self.root
        from mathutils import Matrix as _M
        mw = _M.LocRotScale(r.location, r.rotation_euler.to_quaternion(), r.scale)
        return mw @ Vector((0, 0, self.anvil_top))


def build_press(coll, loc=(0, 0, 0), yaw: float = 0.0) -> Press:
    pr = Press()
    red = _paint('press.red', '#B8261E')
    dark = looks.satin('press.dark', '#26272B', rough=0.45)
    steel = looks.metal('press.steel', '#B9BEC4', rough=0.22)
    chrome = looks.metal('press.chrome', '#E4E8EC', rough=0.06)
    rubber = looks.satin('press.rubber', '#111111', rough=0.7)
    brass = looks.metal('press.brass', '#C49A45', rough=0.25)
    glass = looks.gloss('press.gaugeface', '#F1ECE0', rough=0.3, coat=1.0)
    root = kit.empty('press.root', loc, coll)
    root.rotation_euler.z = math.radians(yaw)
    pr.root = root

    def part(bm, name, mats, parent=root):
        ob = cgeo.to_object(bm, f'press.{name}', coll, mats, sharp=40.0)
        ob.parent = parent
        return ob

    # base plate, feet, the anvil (bolster)
    bm = bmesh.new()
    cgeo.rounded_box(bm, (13.0, 9.5, 1.3), 0.35, (0, 0, 0.95), seg=3, flat=(2, 2, 1))
    for sx in (-1, 1):
        for sy in (-1, 1):
            cgeo.rounded_box(bm, (1.6, 1.6, 0.32), 0.12, (sx * 5.6, sy * 3.8, 0.16), seg=2, flat=(0, 0, 0), mat=1)
    part(bm, 'base', [red, rubber])
    bm = bmesh.new()
    cgeo.rounded_box(bm, (7.4, 7.4, 1.0), 0.12, (0, 0, 2.1), seg=2, flat=(2, 2, 0))
    part(bm, 'anvil', [steel])
    pr.anvil_top = 2.6
    # columns and the crosshead + cylinder
    bm = bmesh.new()
    for sx in (-1, 1):
        cgeo.lathe(bm, [(0, 1.6), (0.52, 1.6), (0.52, 17.2), (0, 17.2)], segs=24, M=_T((sx * 5.2, 0, 0)))
        for z in (1.8, 16.9):
            cgeo.lathe(bm, [(0.52, z - 0.25), (0.82, z - 0.2), (0.82, z + 0.2), (0.52, z + 0.25)], segs=6,
                       M=_T((sx * 5.2, 0, 0)), mat=1)
    part(bm, 'columns', [chrome, dark])
    bm = bmesh.new()
    cgeo.rounded_box(bm, (13.2, 3.8, 2.6), 0.4, (0, 0, 17.3), seg=3, flat=(3, 1, 1))
    cgeo.lathe(bm, [(0, 18.5), (2.1, 18.5), (2.1, 22.6), (1.9, 22.9), (0, 22.9)], segs=40, mat=0)
    cgeo.lathe(bm, [(2.12, 18.9), (2.28, 19.0), (2.28, 19.4), (2.12, 19.5)], segs=40, mat=2)
    cgeo.lathe(bm, [(2.12, 21.9), (2.28, 22.0), (2.28, 22.4), (2.12, 22.5)], segs=40, mat=2)
    part(bm, 'crosshead', [red, dark, steel])
    # pump box with a lever and a pressure dial, and the hose
    bm = bmesh.new()
    cgeo.rounded_box(bm, (3.6, 3.0, 3.2), 0.3, (8.9, 0.3, 1.6), seg=2, flat=(1, 1, 1))
    cgeo.lathe(bm, [(0, 0), (0.95, 0), (1.0, 0.25), (0, 0.25)], segs=32, M=_T((8.9, -1.25, 2.1)) @ _R(90, 0, 0), mat=1)
    part(bm, 'pump', [red, brass])
    bm = bmesh.new()
    cgeo.lathe(bm, [(0, 0), (0.82, 0), (0.82, 0.02), (0, 0.02)], segs=32, M=_T((8.9, -1.52, 2.1)) @ _R(90, 0, 0))
    part(bm, 'pumpdial', [glass])
    bm = bmesh.new()
    pts = [(8.9, 1.4, 3.1), (8.9, 2.6, 5.5), (7.8, 2.4, 10.0), (4.2, 2.0, 15.6), (2.2, 1.6, 17.8)]
    cgeo.tube(bm, pts, [0.28] * len(pts), segs=12)
    part(bm, 'hose', [rubber])
    # the platen (moving head): ram rod up into the cylinder, guide sleeves on the columns
    platen = kit.empty('press.platen', (0, 0, 0), coll)
    platen.parent = root
    pr.platen = platen
    bm = bmesh.new()
    cgeo.rounded_box(bm, (7.2, 7.2, 1.2), 0.18, (0, 0, 0.6), seg=2, flat=(2, 2, 0), mat=1)
    cgeo.rounded_box(bm, (12.6, 2.6, 1.3), 0.3, (0, 0, 1.75), seg=2, flat=(3, 1, 0))
    for sx in (-1, 1):
        cgeo.lathe(bm, [(0.54, 1.0), (0.95, 1.0), (0.95, 2.5), (0.54, 2.5)], segs=24, M=_T((sx * 5.2, 0, 0)))
    cgeo.lathe(bm, [(0, 2.4), (0.72, 2.4), (0.72, 12.0), (0, 12.0)], segs=24, mat=2)
    part(bm, 'platen', [red, steel, chrome], parent=platen)
    pr.platen_rest = 9.6        # local z of the platen's bottom face at rest
    platen.location = (0, 0, pr.platen_rest)
    # the lever on the pump
    lever = kit.empty('press.lever', (8.9, 0.9, 3.2), coll)
    lever.parent = root
    bm = bmesh.new()
    cgeo.lathe(bm, [(0, 0), (0.15, 0), (0.15, 4.2), (0, 4.2)], segs=12, M=_R(0, -20, 0))
    cgeo.uv_sphere(bm, 0.42, segs=16, rings=8, M=_R(0, -20, 0) @ _T((0, 0, 4.3)), mat=1)
    ob = part(bm, 'lever', [chrome, _paint('press.knob', '#D8302A', 0.25)], parent=lever)
    pr.lever = lever
    pr.objs = [o for o in coll.objects if o.name.startswith('press.')]
    return pr


# ------------------------------------------------------------------------------------------------ the plush


class Plush:
    """root (Empty at the plush's base centre; key its scale to squash), parts, height, ears."""


EAR_PIVOT_Z = 5.0        # the ears hinge where they meet the head (local z)
EAR_LEN = 1.86           # hinge to ear tip, fur included
EAR_THICK = 0.44         # half the ear's thickness plus fur (what sticks up once it lies flat)


def _ear_fold(hp: float) -> float:
    """How far (radians) the ears must fold back so their tips stay under a platen at local height hp."""
    room = hp - 0.15 - EAR_PIVOT_Z         # tip height above the hinge ~ L cos(phi) + T (1 - cos(phi)): monotonic
    c = (room - EAR_THICK) / (EAR_LEN - EAR_THICK)
    return math.acos(max(math.cos(math.radians(85.0)), min(1.0, c)))


def _fur_mat(name, base, tip):
    m = bpy.data.materials.get(name)
    if m:
        return m
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    b = nt.nodes['Principled BSDF']
    hi = nt.nodes.new('ShaderNodeHairInfo')
    ramp = nt.nodes.new('ShaderNodeValToRGB')
    ramp.color_ramp.elements[0].color = kit.srgb(base)
    ramp.color_ramp.elements[1].color = kit.srgb(tip)
    ramp.color_ramp.elements[0].position = 0.1
    nt.links.new(hi.outputs['Intercept'], ramp.inputs['Fac'])
    nt.links.new(ramp.outputs['Color'], b.inputs['Base Color'])
    b.inputs['Roughness'].default_value = 0.55
    b.inputs['Sheen Weight'].default_value = 0.6
    b.inputs['Specular IOR Level'].default_value = 0.3
    m.diffuse_color = kit.srgb(tip)
    return m


def _fur(ob, name, mat_index, *, count=3200, length=0.42, children=36, seed=3, clump=0.25, rough=0.06):
    ps_mod = ob.modifiers.new(f'{name}.fur', 'PARTICLE_SYSTEM')
    psys = ps_mod.particle_system
    psys.seed = seed
    st = psys.settings
    st.name = f'{name}.fur'
    st.type = 'HAIR'
    st.count = count
    st.hair_length = length
    st.emit_from = 'FACE'
    st.use_advanced_hair = True
    st.material = mat_index + 1
    st.child_type = 'INTERPOLATED'
    st.child_percent = 4
    st.rendered_child_count = children
    st.child_length = 1.0
    st.clump_factor = clump
    st.roughness_1 = rough
    st.roughness_1_size = 0.3
    st.roughness_endpoint = 0.04
    st.roughness_2 = 0.02
    st.root_radius = 1.6
    st.tip_radius = 0.2
    st.radius_scale = 0.01
    st.use_close_tip = True
    st.render_step = 2
    st.display_step = 2
    st.hair_step = 4
    try:
        st.child_parting_factor = 0.0
    except Exception:
        pass
    return psys


def build_chinchilla(coll, loc=(0, 0, 0), yaw: float = 0.0) -> Plush:
    """A plush chinchilla sitting up, 5.6 cm tall: round grey body, pale belly, big round ears, bead eyes, pink nose,
    whiskers, little paws and a bushy tail. Fur: particle hair (static, deterministic)."""
    ch = Plush()
    grey = looks.felt('plush.grey', '#8E949C')
    belly = looks.felt('plush.belly', '#E6E2DA')
    ear_in = looks.felt('plush.earin', '#E7A9B0')
    fur_g = _fur_mat('plush.fur.grey', '#5E646C', '#B9BEC6')
    fur_b = _fur_mat('plush.fur.belly', '#BDB7AE', '#F4F1EA')
    bead = looks.gloss('plush.bead', '#050505', rough=0.05)
    nose = looks.gloss('plush.nose', '#E58C9A', rough=0.3, coat=0.4)
    whisk = looks.satin('plush.whisker', '#F2F0EA', rough=0.4)
    root = kit.empty('plush.root', loc, coll)
    root.rotation_euler.z = math.radians(yaw)
    ch.root = root
    ch.height = 5.9          # the head's top (5.6) plus its fur: the squash starts when the platen meets the fur
    ch.ears = []             # (object, fold pivot, fold axis): the ears fold back flat under the platen (crush)
    parts = []

    def part(bm, name, mats, sharp=None):
        ob = cgeo.to_object(bm, f'plush.{name}', coll, mats, sharp=sharp)
        ob.parent = root
        parts.append(ob)
        return ob

    # body (one mesh: pear-shaped, with the belly as a second material patch)
    bm = bmesh.new()
    cgeo.uv_sphere(bm, 1.0, segs=40, rings=24, scale=(2.2, 2.0, 2.05), M=_T((0, 0.25, 2.05)))
    cgeo.uv_sphere(bm, 1.0, segs=36, rings=20, scale=(1.75, 1.65, 1.6), M=_T((0, -0.35, 4.0)))
    for f in bm.faces:
        c = f.calc_center_median()
        if c.y < -1.2 and c.z < 3.6 and abs(c.x) < 1.4:
            f.material_index = 1
    body = part(bm, 'body', [grey, belly, fur_g, fur_b])
    # fur on everything but the belly patch gets grey, the belly patch gets light fur (two systems by vertex group)
    vg_g = body.vertex_groups.new(name='grey')
    vg_b = body.vertex_groups.new(name='belly')
    me = body.data
    bel = set()
    for p in me.polygons:
        if p.material_index == 1:
            bel.update(p.vertices)
    # bare the eyes and the nose (fur thins out around them) and keep the face fur short
    bare = [Vector((sx * 0.74, -1.86, 4.36)) for sx in (-1, 1)] + [Vector((0, -2.0, 3.85))]

    def wt(co):
        d = min((co - b).length for b in bare)
        return min(1.0, max(0.0, (d - 0.42) / 0.35))
    for v in me.vertices:
        w = wt(v.co)
        if v.index in bel:
            vg_b.add([v.index], w, 'REPLACE')
        else:
            vg_g.add([v.index], w, 'REPLACE')
    vg_len = body.vertex_groups.new(name='len')
    for v in me.vertices:
        face = v.co.y < -1.0 and v.co.z > 3.2
        vg_len.add([v.index], 0.5 if face else 1.0, 'REPLACE')
    ps = _fur(body, 'body', 2, count=4200, length=0.4, children=26, seed=5)
    ps.vertex_group_density = 'grey'
    ps.vertex_group_length = 'len'
    ps2 = _fur(body, 'belly', 3, count=900, length=0.34, children=26, seed=9)
    ps2.vertex_group_density = 'belly'
    # ears (big round discs), inner pink
    for sx in (-1, 1):
        bm = bmesh.new()
        cgeo.uv_sphere(bm, 1.0, segs=28, rings=14, scale=(1.05, 0.28, 1.15),
                       M=_T((sx * 1.25, 0.05, 5.55)) @ _R(8, 0, sx * -18))
        cgeo.uv_sphere(bm, 1.0, segs=24, rings=12, scale=(0.78, 0.12, 0.88),
                       M=_T((sx * 1.25, -0.2, 5.6)) @ _R(8, 0, sx * -18), mat=1)
        ear = part(bm, f'ear{sx}', [grey, ear_in, fur_g])
        _fur(ear, f'ear{sx}', 2, count=500, length=0.16, children=20, seed=11 + sx)
        a = math.radians(sx * -18)
        ch.ears.append((ear, Vector((sx * 1.25, 0.05, EAR_PIVOT_Z)), Vector((math.cos(a), math.sin(a), 0.0))))
    # eyes, nose, whiskers
    for sx in (-1, 1):
        bm = bmesh.new()
        cgeo.uv_sphere(bm, 0.36, segs=18, rings=10, M=_T((sx * 0.74, -1.8, 4.36)))
        part(bm, f'eye{sx}', [bead])
    bm = bmesh.new()
    cgeo.uv_sphere(bm, 1.0, segs=14, rings=8, scale=(0.3, 0.2, 0.2), M=_T((0, -2.05, 3.85)))
    part(bm, 'nose', [nose])
    bm = bmesh.new()
    for sx in (-1, 1):
        for k, (dz, ang) in enumerate(((0.08, 8), (-0.05, -4), (-0.16, -14))):
            a = math.radians(ang)
            p0 = Vector((sx * 0.25, -1.95, 3.8 + dz))
            d = Vector((sx * math.cos(a) * 0.95, -0.25, math.sin(a) * 0.95))
            cgeo.tube(bm, [p0, p0 + d * 0.5, p0 + d * 1.0 + Vector((0, 0, -0.08))], [0.02, 0.016, 0.01], segs=5)
    part(bm, 'whiskers', [whisk])
    # paws and feet
    bm = bmesh.new()
    for sx in (-1, 1):
        cgeo.uv_sphere(bm, 1.0, segs=16, rings=10, scale=(0.45, 0.4, 0.34), M=_T((sx * 0.75, -1.75, 2.75)))
        cgeo.uv_sphere(bm, 1.0, segs=16, rings=10, scale=(0.55, 0.85, 0.3), M=_T((sx * 1.05, -1.3, 0.3)))
    paws = part(bm, 'paws', [belly, fur_b])
    _fur(paws, 'paws', 1, count=500, length=0.14, children=16, seed=21)
    # bushy tail curling up the back
    bm = bmesh.new()
    pts = [(0, 1.9, 0.6), (0, 2.8, 1.0), (0, 3.2, 2.0), (0, 3.0, 3.1)]
    cgeo.tube(bm, pts, [0.55, 0.7, 0.62, 0.35], segs=16)
    tail = part(bm, 'tail', [grey, fur_g])
    _fur(tail, 'tail', 1, count=1200, length=0.75, children=26, seed=31, clump=0.35, rough=0.1)
    ch.parts = parts
    return ch


# ------------------------------------------------------------------------------------------------ the cube


def build_cube(coll, loc, size: float = 1.1):
    """The super-dense cube: a bevelled dark block with glowing seams in a grid, and a warm glow light."""
    m = bpy.data.materials.new('dense.cube')
    m.use_nodes = True
    nt = m.node_tree
    b = nt.nodes['Principled BSDF']
    b.inputs['Base Color'].default_value = kit.srgb('#1C1A20')
    b.inputs['Metallic'].default_value = 0.8
    b.inputs['Roughness'].default_value = 0.2
    tc = nt.nodes.new('ShaderNodeTexCoord')
    br = nt.nodes.new('ShaderNodeTexBrick')
    br.inputs['Scale'].default_value = 3.0
    br.inputs['Mortar Size'].default_value = 0.05
    br.inputs['Color1'].default_value = (0, 0, 0, 1)
    br.inputs['Color2'].default_value = (0, 0, 0, 1)
    br.inputs['Mortar'].default_value = (1, 1, 1, 1)
    br.offset = 0.0
    nt.links.new(tc.outputs['Object'], br.inputs['Vector'])
    v = nt.nodes.new('ShaderNodeValue')
    v.name = v.label = 'glow'
    v.outputs[0].default_value = 0.0
    mul = nt.nodes.new('ShaderNodeMath')
    mul.operation = 'MULTIPLY'
    add = nt.nodes.new('ShaderNodeMath')
    add.operation = 'MULTIPLY_ADD'
    add.inputs[1].default_value = 1.0
    add.inputs[2].default_value = 0.35
    nt.links.new(br.outputs['Fac'], add.inputs[0])
    nt.links.new(add.outputs[0], mul.inputs[0])
    nt.links.new(v.outputs[0], mul.inputs[1])
    b.inputs['Emission Color'].default_value = kit.srgb('#7FE7FF')
    nt.links.new(mul.outputs[0], b.inputs['Emission Strength'])
    cube = kit.box('dense.cube', (size, size, size), (0, 0, 0), bevel=0.08, segments=3, m=m, coll=coll)
    cube.location = Vector(loc) + Vector((0, 0, size / 2))
    ld = bpy.data.lights.new('dense.light', 'POINT')
    ld.energy = 0.0
    ld.shadow_soft_size = 0.5
    ld.color = kit.srgb('#8FE8FF')[:3]
    lo = bpy.data.objects.new('dense.light', ld)
    coll.objects.link(lo)
    lo.parent = cube
    lo.location = (0, 0, 0.0)
    return cube, m, ld


# ------------------------------------------------------------------------------------------------ the crush


def crush(pr: Press, ch: Plush, cube, cube_mat, cube_light, *, t_lever: float, t_down: float, t_flat: float,
          t_cube: float, t_up: float, t_glow: float, t_end: float):
    """Key the whole beat: the lever is pulled (t_lever), the platen descends (t_down -> t_flat, squashing the plush
    into a pancake), slams to cube height (t_cube) as the pancake implodes into the cube, lifts (t_up) and the cube
    glows brightest at t_glow. Everything smooth at 24 fps (props, not puppets)."""
    top = pr.anvil_top
    rest = pr.platen_rest
    h0 = ch.height
    cube_h = 1.1
    t_rise_end = t_up + 0.32

    def platen_z(t):
        if t < t_down:
            return rest
        if t < t_flat:          # hydraulic: a steady push, easing in
            u = (t - t_down) / (t_flat - t_down)
            u = u * u * (1.6 - 0.6 * u)
            return rest + (top + cube_h - rest) * u
        if t < t_up:
            return top + cube_h
        u = min(1.0, (t - t_up) / (t_rise_end - t_up))
        u = 1 - (1 - u) ** 3
        return top + cube_h + (rest - top - cube_h) * u

    f0 = int(math.floor((t_lever - 0.2) * FPS))
    f1 = int(math.ceil(t_end * FPS)) + 2
    for f in range(f0, f1 + 1):
        t = f / FPS
        z = platen_z(t)
        pr.platen.location = (0, 0, z)
        pr.platen.keyframe_insert('location', index=2, frame=f)
        # plush squash: its top follows the platen once touched
        h = min(h0, max(cube_h, z - top))
        sz = h / h0
        if t >= t_flat:
            u = min(1.0, max(0.0, (t - t_flat) / max(1e-3, t_cube - t_flat)))
            sxy = min(2.0, (1.0 / math.sqrt(sz)) ** 0.85) * (1 - u) + 0.02 * u
        else:
            sxy = min(2.0, (1.0 / math.sqrt(sz)) ** 0.85)      # (capped: the fur stays clear of the columns)
        ch.root.scale = (sxy, sxy, sz if t < t_cube else 0.02)
        ch.root.keyframe_insert('scale', frame=f)
        # the ears fold back flat as the platen comes down on them (hinged where they meet the head); once the
        # body squashes they stay folded under it (local platen height = h0)
        phi = _ear_fold(max(z - top, h) / sz)
        for ear, piv, axis in getattr(ch, 'ears', ()):
            Rm = Matrix.Rotation(-phi, 4, axis)
            ear.location = piv - (Rm @ piv)
            ear.rotation_euler = Rm.to_euler('XYZ')
            ear.keyframe_insert('location', frame=f)
            ear.keyframe_insert('rotation_euler', frame=f)
        # the cube appears as the pancake implodes
        if t < t_flat:
            cs = 0.0
        elif t < t_cube:
            cs = (t - t_flat) / (t_cube - t_flat)
        else:
            cs = 1.0
        cube.scale = (cs, cs, cs)
        cube.keyframe_insert('scale', frame=f)
        g = 0.0
        if t >= t_flat:
            g = 6.0 * min(1.0, (t - t_flat) / 0.06) + 30.0 * math.exp(-max(0.0, t - t_cube) * 9.0) * (t >= t_cube)
            g += 22.0 * math.exp(-((t - t_glow) / 0.07) ** 2)
        sgeo.keyp(cube_mat.node_tree.nodes['glow'].outputs[0], 'default_value', t, g, interp='LINEAR')
        sgeo.keyp(cube_light, 'energy', t, 180.0 * g, interp='LINEAR')
    kit.set_interp(pr.platen, 'LINEAR')
    kit.set_interp(ch.root, 'LINEAR')
    kit.set_interp(cube, 'LINEAR')
    for ear, _p, _a in getattr(ch, 'ears', ()):
        kit.set_interp(ear, 'LINEAR', 'location')
        kit.set_interp(ear, 'LINEAR', 'rotation_euler')
    # the plush exists only in its shot (its fur is costly to evaluate), and is gone once it implodes
    for ob in ch.parts:
        kit.visible(ob, t_lever - 0.1, t_cube + 0.01)
    # the lever is pulled down
    kit.key(pr.lever, 'rotation_euler', t_lever - 0.15, (0, 0, 0), interp='BEZIER')
    kit.key(pr.lever, 'rotation_euler', t_lever, (0, math.radians(-55), 0), interp='BEZIER')
    kit.key(pr.lever, 'rotation_euler', t_up, (0, math.radians(-55), 0), interp='BEZIER')
    kit.key(pr.lever, 'rotation_euler', t_up + 0.2, (0, 0, 0), interp='BEZIER')
