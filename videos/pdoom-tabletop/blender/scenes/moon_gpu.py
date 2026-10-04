"""The NVDA rocket for `moon` (scene-local): four little graphics cards stood on end and stacked face to face.

Each card: a green PCB with a row of gold PCIe fingers, an aluminium fin stack, a charcoal shroud with two fans, a
steel I/O bracket (with ports) at the top end, and along its top edge an acrylic light bar carrying one letter,
N V D A left to right. The light bars face the camera side of the rocket (-Y of the rocket), the stack runs along
+X, the rocket's up is +Z; its root is at the base centre (the smoke trail's nozzle).
"""
from __future__ import annotations

import math

import bpy
from mathutils import Matrix, Vector

from pdoom import kit
from pdoom.sets import geo
from pdoom.sets import materials as M
from pdoom.timing import FPS

L = 9.0          # card length (the rocket's height)
H = 3.6          # card height (gold fingers -> top edge), the rocket's depth
PITCH = 1.55     # stack spacing
NVDA_GREEN = '#76B900'


def _mats():
    return {
        'pcb': M.solid('gpu.pcb', '#1E6B2A', rough=0.35, coat=0.6, coat_rough=0.15, micro=(25.0, 0.02)),
        'gold': M.solid('gpu.gold', '#E7B84E', rough=0.15, metal=1.0),
        'fin': M.solid('gpu.fin', '#C8CCD2', rough=0.28, metal=1.0, micro=(60.0, 0.02)),
        'shroud': M.plastic('gpu.shroud', '#2A2C30', rough=0.32, coat=0.3),
        'fan': M.plastic('gpu.fan', '#141518', rough=0.4),
        'steel': M.solid('gpu.bracket', '#B8BDC4', rough=0.22, metal=1.0, micro=(40.0, 0.02)),
        'port': M.solid('gpu.port', '#0B0B0C', rough=0.5),
        'bar': M.solid('gpu.bar', '#0E1A0A', rough=0.08, coat=1.0, coat_rough=0.02),
        'chip': M.solid('gpu.chip', '#202226', rough=0.3, coat=0.4),
    }


def _glow_mat(name, color=NVDA_GREEN):
    m = kit.mat(name, '#050805', rough=0.3, emit=color, emit_strength=0.0, coat=0.8)
    return m


def build_card(coll, name, letter, mats):
    """One card in card space: length +X (0..L), thickness +Y (PCB at 0, shroud side +Y), height +Z (gold
    fingers at z=0, top edge at z=H). Returns (root Empty, fan objects, glow materials)."""
    root = kit.empty(f'{name}', (0, 0, 0), coll, 'PLAIN_AXES', 0.5)
    parts = []
    pcb = geo.box(f'{name}.pcb', (L - 0.4, 0.16, H - 0.1), (L / 2 + 0.2, 0.0, H / 2 + 0.05), bev=0.03, m=mats['pcb'],
                  coll=coll)
    parts.append(pcb)
    # PCIe fingers: a row of gold pads along the bottom edge, both faces
    fing = geo.box(f'{name}.fingers', (0.09, 0.18, 0.55), (1.6, 0.0, 0.3), m=mats['gold'], coll=coll)
    arr = fing.modifiers.new('arr', 'ARRAY')
    arr.count, arr.relative_offset_displace = 30, (1.75, 0, 0)
    parts.append(fing)
    # fin stack between PCB and shroud
    fin = geo.box(f'{name}.fin', (0.035, 0.95, H - 0.9), (0.9, 0.62, H / 2 + 0.1), m=mats['fin'], coll=coll)
    arr = fin.modifiers.new('arr', 'ARRAY')
    arr.count, arr.relative_offset_displace = 46, (4.8, 0, 0)
    parts.append(fin)
    # shroud: a frame on the outer face (two fan windows), with a bevel
    sh = geo.box(f'{name}.shroud', (L - 0.7, 0.18, H - 0.55), (L / 2 + 0.35, 1.18, H / 2 + 0.2), bev=0.07, m=mats['shroud'],
                 coll=coll)
    parts.append(sh)
    top = geo.box(f'{name}.shroud.top', (L - 0.7, 1.12, 0.22), (L / 2 + 0.35, 0.66, H - 0.02), bev=0.06,
                  m=mats['shroud'], coll=coll)
    parts.append(top)
    bot = geo.box(f'{name}.shroud.bot', (L - 0.7, 0.9, 0.16), (L / 2 + 0.35, 0.72, 0.62), bev=0.05,
                  m=mats['shroud'], coll=coll)
    parts.append(bot)
    # light bar along the top edge (acrylic), the letter glowing near the bracket end
    bar_m = _glow_mat(f'{name}.barglow', NVDA_GREEN)
    bar = geo.box(f'{name}.bar', (L - 1.6, 0.8, 0.06), (L / 2 + 0.6, 0.66, H + 0.12), bev=0.02, m=bar_m, coll=coll)
    parts.append(bar)
    let_m = _glow_mat(f'{name}.letterglow', '#D8FF9A')
    tx = geo.text_mesh(f'{name}.letter', letter, 0.95, coll=coll, m=let_m, extrude=0.02)
    tx.matrix_world = Matrix.Translation((1.55, 0.66, H + 0.17)) @ \
        Matrix(((0, -1, 0, 0), (1, 0, 0, 0), (0, 0, 1, 0), (0, 0, 0, 1)))
    parts.append(tx)
    # bracket at x = 0 with two DisplayPorts and an HDMI, and its tab
    br = geo.box(f'{name}.bracket', (0.08, 1.45, H + 0.9), (0.0, 0.55, H / 2 + 0.3), bev=0.01, m=mats['steel'],
                 coll=coll)
    parts.append(br)
    tab = geo.box(f'{name}.tab', (0.8, 1.45, 0.08), (0.36, 0.55, H + 0.72), bev=0.01, m=mats['steel'], coll=coll)
    parts.append(tab)
    ports = []
    for k, (z, w) in enumerate(((0.9, 0.55), (1.7, 0.55), (2.5, 0.7))):
        p = geo.box(f'{name}.port{k}', (0.1, w, 0.3), (-0.03, 0.55, z), m=mats['port'], coll=coll)
        ports.append(p)
    parts += ports
    # a few chips on the PCB's back face
    for k, (x, z, s) in enumerate(((3.0, 1.6, 1.3), (5.2, 2.3, 0.7), (5.6, 1.2, 0.6), (6.6, 1.9, 0.6), (7.6, 1.2, 0.5))):
        c = geo.box(f'{name}.chip{k}', (s, 0.12, s), (x, -0.13, z), bev=0.02, m=mats['chip'], coll=coll)
        parts.append(c)
    # fans on the shroud face
    fans = []
    for k, x in enumerate((2.55, 6.55)):
        fan = _fan(coll, f'{name}.fan{k}', mats)
        fan.location = (x, 1.31, H / 2 + 0.2)
        fans.append(fan)
        ring = kit.cylinder(f'{name}.fanring{k}', 1.45, 0.08, (x, 1.29, H / 2 + 0.2), verts=40, m=mats['fan'],
                            coll=coll, rot=(math.radians(90), 0, 0))
        parts.append(ring)
    for o in parts + fans:
        kit.parent(o, root, keep_transform=False)
    return root, fans, (bar_m, let_m)


def _fan(coll, name, mats):
    """A little axial fan (hub + 9 swept blades), facing +Y; spin it about its local Y."""
    hub = kit.cylinder(f'{name}.hub', 0.42, 0.2, (0, 0, 0), verts=24, m=mats['fan'], coll=coll,
                       rot=(math.radians(90), 0, 0))
    blades = []
    for k in range(9):
        b = geo.box(f'{name}.blade{k}', (0.42, 0.04, 0.9), (0, 0, 0), bev=0.015, m=mats['fan'], coll=coll)
        a = 2 * math.pi * k / 9
        b.matrix_world = Matrix.Rotation(a, 4, 'Y') @ Matrix.Translation((0, 0, 0.82)) @ \
            Matrix.Rotation(math.radians(28), 4, 'Z')
        blades.append(b)
    bpy.context.view_layer.update()
    for b in blades:
        geo.apply_mods(b)
        b.data.transform(b.matrix_world)
        b.matrix_world = Matrix.Identity(4)
    geo.apply_mods(hub)
    hub.data.transform(hub.matrix_world)
    hub.matrix_world = Matrix.Identity(4)
    fan = geo.join([hub] + blades, name)
    fan.rotation_mode = 'XYZ'
    return fan


class Rocket:
    """Four cards, N V D A. root = the base centre (animate it). letters(t, k) lights card k; fans spin up."""

    LETTERS = 'NVDA'

    def __init__(self, coll, loc=(0, 0, 0), yaw_deg=0.0):
        self.coll = coll
        mats = _mats()
        self.root = kit.empty('rocket', tuple(loc), coll, 'SINGLE_ARROW', 3.0)
        self.root.rotation_euler = (0, 0, math.radians(yaw_deg))
        self.cards, self.fans, self.glows = [], [], []
        n = len(self.LETTERS)
        for k, letter in enumerate(self.LETTERS):
            r, fans, glows = build_card(coll, f'gpu{k}', letter, mats)
            # card space -> rocket space: card X (length) -> down from the top, card Z (top edge) -> -Y (front),
            # card Y (thickness) -> +X (the stack)
            x0 = (k - (n - 1) / 2) * PITCH - 0.6
            Mc = Matrix(((0, 1, 0, x0), (0, 0, -1, H / 2), (-1, 0, 0, L + 0.25), (0, 0, 0, 1)))
            r.matrix_basis = Mc
            r.parent = self.root
            self.cards.append(r)
            self.fans += fans
            self.glows.append(glows)
        # brass standoffs binding the stack, and the gold contacts at the bottom as the engine bell
        brass = M.brass('gpu.brass', '#C9A259', rough=0.25)
        span = (n - 1) * PITCH + 1.6
        for j, (y, z) in enumerate(((-1.2, 1.2), (1.2, 1.2), (-1.2, L - 1.0), (1.2, L - 1.0))):
            rod = kit.cylinder(f'rocket.rod{j}', 0.14, span, (0, 0, 0), verts=12, m=brass, coll=coll,
                               rot=(0, math.radians(90), 0))
            rod.location = (-0.6 + 0.0, y, z)
            rod.parent = self.root
        bell = kit.cylinder('rocket.bell', 1.1, 0.9, (0, 0, 0), verts=32, m=M.chrome('rocket.chrome'), coll=coll)
        tap = bell.modifiers.new('taper', 'SIMPLE_DEFORM')
        tap.deform_method, tap.factor, tap.deform_axis = 'TAPER', 0.6, 'Z'
        bell.location = (-0.6, 0.0, -0.1)
        bell.parent = self.root
        self.bell = bell
        # the flame (an emissive teardrop under the bell), scaled by keys
        self.flame = self._flame()
        self.flame.parent = self.root
        self.flame.location = (-0.6, 0.0, -0.45)
        self.flame_light = kit.point('rocket.flamelight', (0, 0, 0), power=0.0, radius=1.0, color='#FF9A40',
                                     coll=coll)
        self.flame_light.parent = self.root
        self.flame_light.location = (-0.6, 0.0, -2.5)

    def _flame(self):
        bpy.ops.mesh.primitive_uv_sphere_add(radius=1.0, segments=24, ring_count=14, location=(0, 0, 0))
        f = bpy.context.object
        f.name = 'rocket.flame'
        kit.link(f, self.coll)
        for v in f.data.vertices:
            if v.co.z < 0:
                v.co.z *= 3.6
                k = 1.0 + v.co.z / 3.6 * 0.55
                v.co.x *= k
                v.co.y *= k
        for p in f.data.polygons:
            p.use_smooth = True
        m = bpy.data.materials.new('rocket.flame')
        nt = m.node_tree
        nt.nodes.clear()
        out = nt.nodes.new('ShaderNodeOutputMaterial')
        tc = nt.nodes.new('ShaderNodeTexCoord')
        sep = nt.nodes.new('ShaderNodeSeparateXYZ')
        nt.links.new(tc.outputs['Object'], sep.inputs[0])
        ramp = nt.nodes.new('ShaderNodeValToRGB')
        cr = ramp.color_ramp
        cr.elements[0].position, cr.elements[0].color = 0.0, kit.srgb('#FF4A10')
        cr.elements[1].position, cr.elements[1].color = 1.0, kit.srgb('#FFF6D8')
        e = cr.elements.new(0.6)
        e.color = kit.srgb('#FFB040')
        mr = nt.nodes.new('ShaderNodeMapRange')
        mr.inputs['From Min'].default_value = -3.6
        mr.inputs['From Max'].default_value = 0.6
        nt.links.new(sep.outputs['Z'], mr.inputs['Value'])
        nt.links.new(mr.outputs['Result'], ramp.inputs['Fac'])
        em = nt.nodes.new('ShaderNodeEmission')
        em.inputs['Strength'].default_value = 22.0
        nt.links.new(ramp.outputs['Color'], em.inputs['Color'])
        # fade the tail with a fresnel-ish facing term so it reads as a soft jet
        lw = nt.nodes.new('ShaderNodeLayerWeight')
        lw.inputs['Blend'].default_value = 0.45
        tr = nt.nodes.new('ShaderNodeBsdfTransparent')
        mix = nt.nodes.new('ShaderNodeMixShader')
        nt.links.new(lw.outputs['Facing'], mix.inputs['Fac'])
        nt.links.new(em.outputs[0], mix.inputs[1])
        nt.links.new(tr.outputs[0], mix.inputs[2])
        nt.links.new(mix.outputs[0], out.inputs['Surface'])
        m.surface_render_method = 'BLENDED'
        f.data.materials.append(m)
        f.visible_shadow = False
        f.scale = (0.001, 0.001, 0.001)
        return f

    def top_port(self, k=0):
        """World point of card k's top DisplayPort (where the basilisk plugs in) and the bracket's outward normal."""
        bpy.context.view_layer.update()
        card = self.cards[k]
        port = next(o for o in card.children if o.name.endswith('.port2'))
        p = card.matrix_world @ Vector((-0.03, 0.55, 2.5))
        n = (card.matrix_world.to_3x3() @ Vector((-1, 0, 0))).normalized()
        return p, n

    def light(self, k, t, on=True, strength=(1.3, 16.0)):
        bar_m, let_m = self.glows[k]
        for m, s in ((bar_m, strength[0]), (let_m, strength[1])):
            sock = kit.bsdf(m).inputs['Emission Strength']
            geo.keyp(sock, 'default_value', t - 1.0 / FPS, 0.0 if on else s, interp='LINEAR')
            geo.keyp(sock, 'default_value', t, s * 1.6 if on else 0.0, interp='LINEAR')
            geo.keyp(sock, 'default_value', t + 0.12, s if on else 0.0, interp='LINEAR')

    def spin_fans(self, t0, t1, rps_fn):
        """Spin the fans (smooth, per frame): rps_fn(t) revolutions per second."""
        ang = 0.0
        f0, f1 = int(math.floor(t0 * FPS)), int(math.ceil(t1 * FPS))
        for k, fan in enumerate(self.fans):
            ang = 0.37 * k
            for f in range(f0, f1 + 1):
                t = f / FPS
                ang += 2 * math.pi * rps_fn(t) / FPS
                fan.rotation_euler = (0.0, ang, 0.0)
                fan.keyframe_insert('rotation_euler', index=1, frame=f)
            for fc in kit.fcurves(fan):
                for kp in fc.keyframe_points:
                    kp.interpolation = 'LINEAR'
