"""finale, the world part: kicks 5-8.

 K5  147.503-148.412  The city at night (1:1000 on the cutting mat): towers clad in paperclips, lit windows glowing
                      through, landmark towers that are giant paperclips standing on end, rivers of clips for streets
                      lined with tiny street lights; red beacons blink on the kick and the beats; the towers are
                      still rising.
 K6  148.412-149.321  The coast from the air: a relief model on a curved base (the planet's curve): land that
                      glitters like steel, city lights strung along the shore, a black sea with the moon's path on it,
                      the silver tide spreading out over the water; the planet's rim lit by the first dawn.
 K7  149.321-150.230  Space. The hand-painted globe (cotton-wool clouds, luminous-paint cities on the night side)
                      turns into a ball of paperclips in spreading patches; the sun from the left; a star cloth.
 K8  150.230-151.139  The Earth all clips, turning, rim-lit; a long pull back; the paper moon swings into the
                      foreground on its string, soft.
"""
from __future__ import annotations

import math
import random

import bmesh
import bpy
from mathutils import Matrix, Vector

from pdoom import kit
from pdoom import timing as tm
from pdoom.fx import _nodes as N
from pdoom.fx import clips as C
from pdoom.sets import geo as sgeo
from pdoom.sets import materials as M

from scenes import coda_moon as CM
from scenes import finale_common as F
from scenes import finale_models as MD

FPS = tm.FPS
V = Vector
K5, K6, K7, K8, K9 = F.KICKS[4], F.KICKS[5], F.KICKS[6], F.KICKS[7], F.KICKS[8]
O5 = V((12000.0, 0.0, 0.0))
O6 = V((15000.0, 0.0, 0.0))
O7 = V((18000.0, 0.0, 0.0))
SUN_DIR = V((-0.82, -0.52, 0.26)).normalized()        # toward the sun (from the Earth)


def build():
    city()
    coast()
    earth()


def _finish(coll, t_on, t_off):
    F.show(F.objects_in(coll), F.edge(t_on), F.edge(t_off))


# ================================================================================================ K5: the city


def _tower_bm(bm, x, y, w, d, h, mat=0, setback=True):
    MD._box_bm(bm, x - w / 2, x + w / 2, y - d / 2, y + d / 2, 0.0, h, mat)
    if setback and h > 25:
        MD._box_bm(bm, x - w * 0.35, x + w * 0.35, y - d * 0.35, y + d * 0.35, h, h + h * 0.08, mat)


def city():
    coll = kit.collection('finale.k5')
    O = O5
    rng = random.Random(5)
    F.grid_mesh('k5.table', (1400.0, 1200.0), 1, coll=coll, loc=O + V((0, 0, -0.3)), mats=[MD.cutting_mat()])
    # ground: the streets are rivers of clips (glitter), blocks a little raised
    F.box('k5.ground', (600.0, 380.0, 0.4), O + V((0, 30.0, -0.2)), F.glitter('k5.glitter', scale=4.0), coll)
    pitch, street = 22.0, 5.0
    fac = [MD.facade(f'k5.fac{k}', c, cell=(0.9, 1.25), win=(0.5, 0.46), lit=l, strength=3.2, seed=k * 3.1,
                     warm=wc)
           for k, (c, l, wc) in enumerate((('#23272E', 0.3, '#FFC27A'), ('#2E3137', 0.22, '#FFD9A8'),
                                           ('#1A1D22', 0.38, '#FFB870'), ('#34383E', 0.26, '#FFB25C')))]
    bm_clad = bmesh.new()        # towers that get a paperclip cladding (near the centre, in the focus band)
    bm_far = [bmesh.new() for _ in fac]
    tops = []
    tops_clad = []               # roofs of the clad towers (z of the roof at full height, without the beacon's lift)
    blocks = bmesh.new()
    for bi in range(-13, 14):
        for bj in range(-6, 12):
            cx, cy = bi * pitch, bj * pitch
            if abs(cx) > 290 or cy < -140 or cy > 250:
                continue
            MD._box_bm(blocks, O.x + cx - (pitch - street) / 2, O.x + cx + (pitch - street) / 2,
                       O.y + cy - (pitch - street) / 2, O.y + cy + (pitch - street) / 2, 0.0, 0.5)
            r = math.hypot(cx, cy - 40.0)
            n = rng.choice((1, 2, 2, 3, 4))
            cells = [(0, 0)] if n == 1 else [(-1, -1), (1, 1), (-1, 1), (1, -1)][:n]
            for (u, v) in cells:
                w = (pitch - street) / (1 if n == 1 else 2) - rng.uniform(0.8, 2.2)
                d = w * rng.uniform(0.7, 1.0)
                tx = cx + u * (pitch - street) / 4 * (0 if n == 1 else 1)
                ty = cy + v * (pitch - street) / 4 * (0 if n == 1 else 1)
                hmax = 14.0 + 78.0 * math.exp(-(r / 95.0) ** 2)
                h = rng.uniform(0.35, 1.0) * hmax * (1.0 if n == 1 else 0.8)
                if (bi, bj) in ((0, 2), (-2, 3), (2, 1)):
                    continue                       # the landmark paperclip towers stand here
                near = abs(cx) < 52 and -12 < cy < 92 and h > 16
                if near:
                    _tower_bm(bm_clad, O.x + tx, O.y + ty, w, d, h)
                else:
                    _tower_bm(bm_far[rng.randrange(len(fac))], O.x + tx, O.y + ty, w, d, h)
                if h > 45 and near:            # its roof rises with the clad towers' shape key (below)
                    tops_clad.append(V((O.x + tx, O.y + ty, h + h * 0.08)))
                elif h > 45:
                    tops.append(V((O.x + tx, O.y + ty, h + h * 0.08 + 0.4)))
    MD.obj(blocks, 'k5.blocks', coll, [MD.paint('k5.pavement', '#3A3C40', 0.8)])
    for k, b in enumerate(bm_far):
        MD.obj(b, f'k5.towers{k}', coll, [fac[k]])
    clad = MD.obj(bm_clad, 'k5.clad', coll, [fac[0]])
    # the clad towers rise out of the clips (shape key: tops up 12 %)
    base = [v.co.copy() for v in clad.data.vertices]
    sk_b = clad.shape_key_add(name='Basis')
    sk = clad.shape_key_add(name='rise')
    for i, c in enumerate(base):
        sk_b.data[i].co = (c.x, c.y, c.z * 0.86)
        sk.data[i].co = (c.x, c.y, c.z)
    RISE_KEYS = ((K5 - 0.3, -0.1), (K6 + 0.2, 1.05))
    for t, v in RISE_KEYS:
        sgeo.keyp(sk, 'value', t, v, interp='LINEAR')
    F.carpet('k5.cladclips', clad, scale=0.3, density=0.3, layers=1, lod=2, coll=coll, seed=81, tilt=0.5)
    clad.hide_render = False
    clad.pop('never_render', None)
    # the landmark towers: giant paperclips standing on end
    me = C.clip_mesh(0, name='k5.bigclip', collide_pad=False)
    for k, ((bi, bj), hgt, rz) in enumerate((((0, 2), 92.0, 12.0), ((-2, 3), 70.0, -30.0), ((2, 1), 60.0, 55.0))):
        ob = bpy.data.objects.new(f'k5.landmark{k}', me)
        coll.objects.link(ob)
        s = hgt / C.LENGTH
        ob.scale = (s, s, s)
        ob.rotation_euler = (math.radians(90), math.radians(-90), math.radians(rz))
        ob.location = O + V((bi * pitch, bj * pitch, hgt / 2 + 0.3))
        tops.append(ob.location + V((0, 0, hgt / 2 + 0.6)))
        # a plinth
        F.box(f'k5.plinth{k}', (6.0, 6.0, 1.0), O + V((bi * pitch, bj * pitch, 0.5)), MD.paint('k5.plinthm', '#6E6A62'),
              coll)
    # red beacons: blink on the kick and the beats
    bmat = M.emissive('k5.beacon', '#FF2A1A', 0.0)
    s_em = bmat.node_tree.nodes['Principled BSDF'].inputs['Emission Strength']
    for f in range(int((K5 - 0.3) * FPS), int((K6 + 0.3) * FPS) + 1):
        t = f / FPS
        pk = max([0.0] + [math.exp(-(t - b) / 0.12) for b in [K5] + tm.beats_between(K5, K6 + 0.1) if b <= t])
        sgeo.keyp(s_em, 'default_value', t, 0.25 + 2.0 * pk, interp='LINEAR')
    bm = bmesh.new()
    for p in tops:
        bmesh.ops.create_icosphere(bm, subdivisions=1, radius=0.45, matrix=Matrix.Translation(p))
    bc = MD.obj(bm, 'k5.beacons', coll, [bmat], sharp=None)
    bc.visible_shadow = False
    # the clad towers' beacons ride their roofs: the same Basis (z * 0.86) / 'rise' (z) shape key and keys as k5.clad
    bm = bmesh.new()
    dz = []
    for p in tops_clad:
        res = bmesh.ops.create_icosphere(bm, subdivisions=1, radius=0.45,
                                         matrix=Matrix.Translation((p.x, p.y, p.z * 0.86 + 0.4)))
        dz += [p.z * 0.14] * len(res['verts'])
    bcc = MD.obj(bm, 'k5.beacons.clad', coll, [bmat], sharp=None)
    bcc.visible_shadow = False
    bcc.shape_key_add(name='Basis')
    skc = bcc.shape_key_add(name='rise')
    for i, v in enumerate(bcc.data.vertices):
        skc.data[i].co = (v.co.x, v.co.y, v.co.z + dz[i])
    for t, v in RISE_KEYS:
        sgeo.keyp(skc, 'value', t, v, interp='LINEAR')
    # street lights: warm dots along the streets
    bm = bmesh.new()
    for bi in range(-14, 15):
        for bj in range(-7, 12):
            x0, y0 = bi * pitch + pitch / 2, bj * pitch + pitch / 2
            for k in range(4):
                for (x, y) in ((x0 - pitch / 2 + pitch * k / 4, y0), (x0, y0 - pitch / 2 + pitch * k / 4)):
                    if abs(x) < 295 and -150 < y < 255:
                        bmesh.ops.create_icosphere(bm, subdivisions=1, radius=0.28,
                                                   matrix=Matrix.Translation(O + V((x, y + 1.6, 0.9))))
    sl = MD.obj(bm, 'k5.streetlights', coll, [kit.emission_mat('k5.sodium', '#FFB25C', 14.0)], sharp=None)
    sl.visible_shadow = False
    # the sky behind the skyline: a curved painted backdrop
    sky = F.grid_mesh('k5.sky', (1600.0, 560.0), (24, 1), coll=coll, loc=O + V((0, 300.0, 180.0)))
    sky.rotation_euler = (math.radians(90), 0, 0)
    sky.data.materials.append(_sky_card('k5.skycard', '#4A3E52', '#060912', mid='#1C2744'))
    sky.visible_shadow = False
    # light: the moon behind (glints on the clip cladding), a cool fill, the city's own warm glow from below
    moon = kit.area('k5.moon', tuple(O + V((-120.0, 420.0, 300.0))), tuple(O + V((0, 30, 20))), power=2.4e6,
                    size=240.0, color='#8FA8E0', coll=coll)
    fill = kit.area('k5.fill', tuple(O + V((150.0, -380.0, 320.0))), tuple(O + V((0, 30, 0))), power=1.6e5,
                    size=260.0, color='#9FB0D8', coll=coll)
    glow = kit.area('k5.glow', tuple(O + V((0, 40.0, -30.0))), tuple(O + V((0, 40, 60))), power=0.0, size=300.0,
                    color='#FFB070', coll=coll)
    rimk = kit.spot('k5.rim', tuple(O + V((60.0, 420.0, 260.0))), tuple(O + V((0.0, 44.0, 45.0))), power=4.5e6,
                    angle_deg=30, blend=0.6, radius=6.0, color='#CFE0FF', coll=coll)
    for l in (moon, fill, glow, rimk):
        l.data.volume_factor = 0.0
    _finish(coll, K5, K6)
    F.Cam('cam.k5', K5, K6, F.path(O + V((-96.0, -300.0, 96.0)), O + V((-118.0, -352.0, 122.0)), K5, K6 + 0.1),
          F.path(O + V((0.0, 60.0, 34.0)), O + V((0.0, 64.0, 30.0)), K5, K6 + 0.1), lens=50.0, fstop=2.0,
          focus=O + V((0.0, 40.0, 30.0)), coll=kit.collection('finale.cams'))


def _sky_card(name, low, high, strength=1.0, mid=None):
    m = bpy.data.materials.get(name)
    if m:
        return m
    m, _ = M.new_mat(name)
    nt = m.node_tree
    b = M.principled(m)
    M.setin(b, 'Base Color', (0, 0, 0, 1))
    tc = M.node(nt, 'ShaderNodeTexCoord', (-800, 0))
    sep = M.node(nt, 'ShaderNodeSeparateXYZ', (-600, 0))
    M.link(nt, M.sout(tc, 'Generated'), M.sin(sep, 'Vector'))
    ramp = M.node(nt, 'ShaderNodeValToRGB', (-400, 0))
    cr = ramp.color_ramp
    cr.elements[0].position, cr.elements[0].color = 0.0, kit.srgb(low)
    cr.elements[1].position, cr.elements[1].color = 0.7, kit.srgb(high)
    if mid is not None:
        e = cr.elements.new(0.3)
        e.color = kit.srgb(mid)
    M.link(nt, M.sout(sep, 'Y'), M.sin(ramp, 'Factor'))
    M.link(nt, M.sout(ramp, 'Color'), M.sin(b, 'Emission Color'))
    M.setin(b, 'Emission Strength', strength)
    return m


# ================================================================================================ K6: the coast


R6 = 2200.0          # the relief's planet radius (the horizon curves)
PATCH_C = O6 + V((0.0, 480.0, 0.0))   # the instanced clips' patch (the focus band), and its half-size
PATCH_H = (220.0, 110.0)


def _land_mat(name='k6.land'):
    """The relief: land (noise > threshold) is steel glitter with luminous city dots strung along the coast; the
    sea is black-blue varnish with a fine ripple (the moon's path glints on it). The 'k6.coast' value node moves
    the coastline (keyed: the tide of clips spreads out over the water)."""
    m = bpy.data.materials.get(name)
    if m:
        return m
    m, _ = M.new_mat(name)
    nt = m.node_tree
    b = M.principled(m)
    Nn, S, L = M.node, M.sin, M.sout
    tc = Nn(nt, 'ShaderNodeTexCoord', (-1800, 0))
    obj = L(tc, 'Object')
    nz = Nn(nt, 'ShaderNodeTexNoise', (-1500, 200))
    M.setin(nz, 'Scale', 0.0022)
    M.setin(nz, 'Detail', 9.0)
    M.setin(nz, 'Roughness', 0.62)
    M.link(nt, obj, S(nz, 'Vector'))
    thr = Nn(nt, 'ShaderNodeValue', (-1500, 450))
    thr.name = thr.label = 'k6.coast'
    thr.outputs[0].default_value = 0.5
    sub = Nn(nt, 'ShaderNodeMath', (-1300, 300), operation='SUBTRACT')
    M.link(nt, L(nz, 'Factor'), sub.inputs[0])
    M.link(nt, thr.outputs[0], sub.inputs[1])
    land = Nn(nt, 'ShaderNodeMapRange', (-1100, 300))
    M.setin(land, 'From Min', 0.0, 'VALUE')
    M.setin(land, 'From Max', 0.004, 'VALUE')
    M.link(nt, sub.outputs[0], S(land, 'Value', 'VALUE'))
    # coast proximity (for the city lights): 1 near the shore on land
    near = Nn(nt, 'ShaderNodeMapRange', (-1100, 550))
    M.setin(near, 'From Min', 0.0, 'VALUE')
    M.setin(near, 'From Max', 0.05, 'VALUE')
    M.setin(near, 'To Min', 1.0, 'VALUE')
    M.setin(near, 'To Max', 0.0, 'VALUE')
    M.link(nt, sub.outputs[0], S(near, 'Value', 'VALUE'))
    # glitter (the clips) for land
    vo = Nn(nt, 'ShaderNodeTexVoronoi', (-1300, -200))
    M.setin(vo, 'Scale', 2.2)
    M.link(nt, obj, S(vo, 'Vector'))
    gl = Nn(nt, 'ShaderNodeValToRGB', (-1100, -200))
    gl.color_ramp.elements[0].color = kit.srgb('#5C636C')
    gl.color_ramp.elements[1].color = kit.srgb('#D6DAE0')
    M.link(nt, L(vo, 'Color'), S(gl, 'Factor'))
    sea_c = kit.srgb('#02050B')
    col = Nn(nt, 'ShaderNodeMix', (-700, 0), data_type='RGBA', blend_type='MIX')
    M.link(nt, L(land, 'Result', 'VALUE'), S(col, 'Factor', 'VALUE'))
    M.setin(col, 'A', sea_c, 'RGBA')
    M.link(nt, L(gl, 'Color'), S(col, 'B', 'RGBA'))
    M.link(nt, L(col, 'Result', 'RGBA'), S(b, 'Base Color'))
    met = Nn(nt, 'ShaderNodeMapRange', (-700, -250))
    M.setin(met, 'To Min', 0.0, 'VALUE')
    M.setin(met, 'To Max', 0.55, 'VALUE')
    M.link(nt, L(land, 'Result', 'VALUE'), S(met, 'Value', 'VALUE'))
    M.link(nt, L(met, 'Result', 'VALUE'), S(b, 'Metallic'))
    rg = Nn(nt, 'ShaderNodeMapRange', (-700, -450))
    M.setin(rg, 'To Min', 0.16, 'VALUE')
    M.setin(rg, 'To Max', 0.42, 'VALUE')
    M.link(nt, L(land, 'Result', 'VALUE'), S(rg, 'Value', 'VALUE'))
    M.link(nt, L(rg, 'Result', 'VALUE'), S(b, 'Roughness'))
    # ripples on the sea, facets on the land
    rip = Nn(nt, 'ShaderNodeTexNoise', (-1300, -600))
    M.setin(rip, 'Scale', 0.35)
    M.setin(rip, 'Detail', 3.0)
    M.link(nt, obj, S(rip, 'Vector'))
    bumpin = Nn(nt, 'ShaderNodeMix', (-900, -600), data_type='FLOAT', blend_type='MIX')
    M.link(nt, L(land, 'Result', 'VALUE'), S(bumpin, 'Factor', 'VALUE'))
    M.link(nt, L(rip, 'Factor'), S(bumpin, 'A', 'VALUE'))
    M.link(nt, L(vo, 'Distance'), S(bumpin, 'B', 'VALUE'))
    bp = Nn(nt, 'ShaderNodeBump', (-500, -600))
    M.setin(bp, 'Strength', 0.35)
    M.setin(bp, 'Distance', 0.2)
    M.link(nt, L(bumpin, 'Result', 'VALUE'), S(bp, 'Height'))
    M.link(nt, L(bp, 'Normal'), S(b, 'Normal'))
    # city lights along the coast: small voronoi dots, in clusters
    cd = Nn(nt, 'ShaderNodeTexVoronoi', (-1300, 800))
    M.setin(cd, 'Scale', 0.35)
    M.link(nt, obj, S(cd, 'Vector'))
    dot = Nn(nt, 'ShaderNodeMapRange', (-1100, 800))
    M.setin(dot, 'From Min', 0.12, 'VALUE')
    M.setin(dot, 'From Max', 0.04, 'VALUE')
    M.link(nt, L(cd, 'Distance'), S(dot, 'Value', 'VALUE'))
    cl = Nn(nt, 'ShaderNodeTexNoise', (-1300, 1050))
    M.setin(cl, 'Scale', 0.012)
    M.link(nt, obj, S(cl, 'Vector'))
    clm = Nn(nt, 'ShaderNodeMapRange', (-1100, 1050))
    M.setin(clm, 'From Min', 0.45, 'VALUE')
    M.setin(clm, 'From Max', 0.6, 'VALUE')
    M.link(nt, L(cl, 'Factor'), S(clm, 'Value', 'VALUE'))
    w = Nn(nt, 'ShaderNodeMath', (-900, 800), operation='MULTIPLY')
    M.link(nt, L(dot, 'Result', 'VALUE'), w.inputs[0])
    M.link(nt, L(clm, 'Result', 'VALUE'), w.inputs[1])
    w2 = Nn(nt, 'ShaderNodeMath', (-750, 800), operation='MULTIPLY')
    M.link(nt, w.outputs[0], w2.inputs[0])
    M.link(nt, L(land, 'Result', 'VALUE'), w2.inputs[1])
    w3 = Nn(nt, 'ShaderNodeMath', (-600, 800), operation='MULTIPLY_ADD')
    M.link(nt, L(near, 'Result', 'VALUE'), w3.inputs[0])
    w3.inputs[1].default_value = 0.8
    w3.inputs[2].default_value = 0.2
    w4 = Nn(nt, 'ShaderNodeMath', (-450, 800), operation='MULTIPLY')
    M.link(nt, w2.outputs[0], w4.inputs[0])
    M.link(nt, w3.outputs[0], w4.inputs[1])
    w5 = Nn(nt, 'ShaderNodeMath', (-300, 800), operation='MULTIPLY')
    M.link(nt, w4.outputs[0], w5.inputs[0])
    w5.inputs[1].default_value = 30.0
    M.link(nt, w5.outputs[0], S(b, 'Emission Strength'))
    M.setin(b, 'Emission Color', kit.srgb('#FFB65C'))
    M.setin(b, 'Coat Weight', 0.0)
    m.diffuse_color = kit.srgb('#5A6068')
    return m


def coast():
    coll = kit.collection('finale.k6')
    O = O6
    C0 = O - V((0.0, 0.0, R6))                 # the planet's centre; its surface top at O
    # the relief: a spherical cap, lightly displaced where there is land
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=448, v_segments=224, radius=R6)
    kill = [v for v in bm.verts if v.co.z < R6 * math.cos(math.radians(48))]
    bmesh.ops.delete(bm, geom=kill, context='VERTS')
    me = bpy.data.meshes.new('k6.relief')
    bm.to_mesh(me)
    bm.free()
    for p in me.polygons:
        p.use_smooth = True
    rel = bpy.data.objects.new('k6.relief', me)
    coll.objects.link(rel)
    rel.location = C0
    rel.data.materials.append(_land_mat())
    th = _land_mat().node_tree.nodes['k6.coast'].outputs[0]
    sgeo.keyp(th, 'default_value', K6 - 0.3, 0.505, interp='LINEAR')
    sgeo.keyp(th, 'default_value', K7 + 0.2, 0.47, interp='LINEAR')
    # real clips near the focus: a patch of land hugging the relief (a carpet)
    fx0 = O + V((0.0, 480.0, 0.0))
    patch = F.grid_mesh('k6.patch', (440.0, 220.0), (44, 22), coll=coll, loc=V((0, 0, 0)))
    for v in patch.data.vertices:
        p = fx0 + V((v.co.x, v.co.y, 0.0))
        d = (p - C0).normalized()
        v.co = C0 + d * (R6 + 0.4)
    F.carpet('k6.clips', patch, scale=0.34, density=0.24, layers=1, lod=3, coll=coll, seed=95, tilt=0.5)
    _patch_mask(patch, [(K6 - 0.3, 0.505), (K7 + 0.2, 0.47)])
    # the rim: an atmosphere shell, blue with the dawn warming one side
    atm = kit.sphere('k6.atmos', R6 * 1.009, tuple(C0), coll=coll, subdiv=6)
    atm.data.materials.append(_atmos_mat('k6.atmosmat', V((0.35, 1.0, -0.12)).normalized()))
    atm.visible_shadow = False
    stars = F.stars('k6.stars', O + V((0, 900, 0)), r0=6000.0, r1=9000.0, count=1500, seed=6,
                    size=(3.0, 9.0), coll=coll, cone=((0, 1, 0.45), 40))
    # moonlight from above the horizon ahead (its path glints on the sea), a cool fill from behind the camera
    moon = kit.sun('k6.moonsun', direction=(-0.35, -1.0, -0.62), strength=1.6, angle_deg=1.5, color='#9FB6E8',
                   coll=coll)
    fill = kit.area('k6.fill', tuple(O + V((-300.0, -600.0, 500.0))), tuple(O + V((0, 300, 0))), power=2.5e6,
                    size=500.0, color='#8FA0C8', coll=coll)
    fill.data.volume_factor = 0.0
    _finish(coll, K6, K7)
    F.Cam('cam.k6', K6, K7, F.path(O + V((0.0, 60.0, 160.0)), O + V((0.0, 10.0, 215.0)), K6, K7 + 0.1),
          F.path(O + V((0.0, 855.0, -262.0)), O + V((0.0, 830.0, -250.0)), K6, K7 + 0.1), lens=32.0, fstop=2.8,
          focus=O + V((0.0, 470.0, -51.0)), coll=kit.collection('finale.cams'))


def _patch_mask(patch, coast_keys):
    """Delete the carpet's clips where the relief is sea (the same noise as the land material, the same keyed
    coastline threshold)."""
    fld = bpy.data.objects.get('k6.clips')
    if fld is None:
        return
    mod = next(md for md in fld.modifiers if md.type == 'NODES')
    ng = mod.node_group
    it = ng.interface.new_socket('Coast', in_out='INPUT', socket_type='NodeSocketFloat')
    it.default_value = 0.5
    gin = next(n for n in ng.nodes if n.bl_idname == 'NodeGroupInput')
    inst_nodes = [n for n in ng.nodes if n.bl_idname == 'GeometryNodeInstanceOnPoints']
    for inst in inst_nodes:
        src = inst.inputs['Points'].links[0].from_socket
        pos = ng.nodes.new('GeometryNodeInputPosition')
        # the relief's object space = world - C0; the land noise is in the relief's object coords
        off = ng.nodes.new('ShaderNodeVectorMath')
        off.operation = 'SUBTRACT'
        ng.links.new(pos.outputs[0], off.inputs[0])
        c0 = O6 - V((0.0, 0.0, R6))
        off.inputs[1].default_value = tuple(c0)
        nz = ng.nodes.new('ShaderNodeTexNoise')
        nz.inputs['Scale'].default_value = 0.0022
        nz.inputs['Detail'].default_value = 9.0
        nz.inputs['Roughness'].default_value = 0.62
        ng.links.new(off.outputs[0], nz.inputs['Vector'])
        cmp = ng.nodes.new('FunctionNodeCompare')
        cmp.data_type = 'FLOAT'
        cmp.operation = 'LESS_THAN'
        ng.links.new(nz.outputs['Factor'], N.Tree.inp(cmp, 'A'))
        ng.links.new(gin.outputs['Coast'], N.Tree.inp(cmp, 'B'))
        # ellipse: ((x - cx) / hx)^2 + ((y - cy) / hy)^2 + edge noise > 1 -> delete
        rel = ng.nodes.new('ShaderNodeVectorMath')
        rel.operation = 'SUBTRACT'
        ng.links.new(pos.outputs[0], rel.inputs[0])
        rel.inputs[1].default_value = tuple(PATCH_C)
        scl = ng.nodes.new('ShaderNodeVectorMath')
        scl.operation = 'MULTIPLY'
        ng.links.new(rel.outputs[0], scl.inputs[0])
        scl.inputs[1].default_value = (1.0 / PATCH_H[0], 1.0 / PATCH_H[1], 0.0)
        ln = ng.nodes.new('ShaderNodeVectorMath')
        ln.operation = 'LENGTH'
        ng.links.new(scl.outputs[0], ln.inputs[0])
        en = ng.nodes.new('ShaderNodeTexNoise')
        en.inputs['Scale'].default_value = 0.03
        en.inputs['Detail'].default_value = 4.0
        ng.links.new(pos.outputs[0], en.inputs['Vector'])
        wn = ng.nodes.new('ShaderNodeTexWhiteNoise')
        wn.noise_dimensions = '3D'
        ng.links.new(pos.outputs[0], wn.inputs['Vector'])
        a1 = ng.nodes.new('ShaderNodeMath')
        a1.operation = 'MULTIPLY_ADD'
        ng.links.new(en.outputs['Factor'], a1.inputs[0])
        a1.inputs[1].default_value = 0.5
        ng.links.new(ln.outputs['Value'], a1.inputs[2])
        a2 = ng.nodes.new('ShaderNodeMath')
        a2.operation = 'MULTIPLY_ADD'
        ng.links.new(wn.outputs['Value'], a2.inputs[0])
        a2.inputs[1].default_value = 0.25
        ng.links.new(a1.outputs[0], a2.inputs[2])
        out_e = ng.nodes.new('ShaderNodeMath')
        out_e.operation = 'GREATER_THAN'
        ng.links.new(a2.outputs[0], out_e.inputs[0])
        out_e.inputs[1].default_value = 1.2
        orn = ng.nodes.new('FunctionNodeBooleanMath')
        orn.operation = 'OR'
        ng.links.new(cmp.outputs['Result'], orn.inputs[0])
        ng.links.new(out_e.outputs[0], orn.inputs[1])
        dl = ng.nodes.new('GeometryNodeDeleteGeometry')
        dl.domain = 'POINT'
        ng.links.new(src, dl.inputs['Geometry'])
        ng.links.new(orn.outputs[0], dl.inputs['Selection'])
        ng.links.new(dl.outputs[0], inst.inputs['Points'])
    for t, v in coast_keys:
        N.key_input(fld, mod, 'Coast', t, v, interp='LINEAR')


def _atmos_mat(name, dawn_dir):
    """A thin glowing rim: transparent, emission growing at grazing angles (Layer Weight facing), blue, warmer
    toward the dawn side."""
    m = bpy.data.materials.get(name)
    if m:
        return m
    m, _ = M.new_mat(name)
    nt = m.node_tree
    for n in list(nt.nodes):
        if n.bl_idname != 'ShaderNodeOutputMaterial':
            nt.nodes.remove(n)
    out = nt.nodes.get('Material Output')
    lw = M.node(nt, 'ShaderNodeLayerWeight', (-900, 0))
    M.setin(lw, 'Blend', 0.08)
    pw = M.node(nt, 'ShaderNodeMath', (-700, 0), operation='POWER')
    M.link(nt, M.sout(lw, 'Facing'), pw.inputs[0])
    pw.inputs[1].default_value = 3.0
    ng = M.node(nt, 'ShaderNodeNewGeometry', (-900, -300))
    dp = M.node(nt, 'ShaderNodeVectorMath', (-700, -300), operation='DOT_PRODUCT')
    M.link(nt, M.sout(ng, 'Normal'), dp.inputs[0])
    dp.inputs[1].default_value = tuple(dawn_dir)
    mr = M.node(nt, 'ShaderNodeMapRange', (-500, -300))
    M.setin(mr, 'From Min', -0.2, 'VALUE')
    M.setin(mr, 'From Max', 0.9, 'VALUE')
    M.link(nt, M.sout(dp, 'Value'), M.sin(mr, 'Value', 'VALUE'))
    mix = M.node(nt, 'ShaderNodeMix', (-300, -200), data_type='RGBA', blend_type='MIX')
    M.link(nt, M.sout(mr, 'Result', 'VALUE'), M.sin(mix, 'Factor', 'VALUE'))
    M.setin(mix, 'A', kit.srgb('#3F7BFF'), 'RGBA')
    M.setin(mix, 'B', kit.srgb('#FF9A4A'), 'RGBA')
    em = M.node(nt, 'ShaderNodeEmission', (-100, 0))
    M.link(nt, M.sout(mix, 'Result', 'RGBA'), M.sin(em, 'Color'))
    st = M.node(nt, 'ShaderNodeMath', (-300, 150), operation='MULTIPLY')
    M.link(nt, pw.outputs[0], st.inputs[0])
    st.inputs[1].default_value = 9.0
    M.link(nt, st.outputs[0], M.sin(em, 'Strength'))
    tr = M.node(nt, 'ShaderNodeBsdfTransparent', (-100, -200))
    add = M.node(nt, 'ShaderNodeAddShader', (100, 0))
    M.link(nt, M.sout(em, 'Emission'), add.inputs[0])
    M.link(nt, M.sout(tr, 'BSDF'), add.inputs[1])
    M.link(nt, add.outputs[0], out.inputs['Surface'])
    try:
        m.surface_render_method = 'BLENDED'
    except Exception:
        pass
    m.use_backface_culling = True
    return m


# ================================================================================================ K7 / K8: the Earth


def earth():
    coll = kit.collection('finale.k7')
    O = O7
    E = CM.clip_earth(coll, O, radius=30.0, progress=[(K7 - 0.2, 0.18), (K7 + 0.15, 0.3), (K8, 0.86),
                                                      (K8 + 0.01, 1.05)], scale=0.3, layers=2, density=0.8,
                      clouds=False)
    F.set_earth_sun(E['material'], SUN_DIR)
    spin = E['spin']
    kit.key(spin, 'rotation_euler', K7 - 0.3, (math.radians(8), 0.0, math.radians(-30.0)), interp='LINEAR')
    kit.key(spin, 'rotation_euler', K9 + 0.3, (math.radians(8), 0.0, math.radians(-4.0)), interp='LINEAR')
    stars = F.stars('k7.stars', O, r0=900.0, r1=1800.0, count=2600, seed=7, size=(0.8, 2.6), coll=coll)
    sun = kit.sun('k7.sun', direction=tuple(-SUN_DIR), strength=7.0, angle_deg=0.8, color='#FFF1DC', coll=coll)
    # a whisper of blue earthshine from the right so the night side isn't pure black
    es = kit.area('k7.earthshine', tuple(O + V((140.0, -60.0, 20.0))), tuple(O), power=26000.0, size=80.0,
                  color='#4A6AB0', coll=coll)
    es.data.volume_factor = 0.0
    # the paper moon, far out in front, swings into K8's foreground
    moon = CM.build_moon(coll, loc=O + V((170.0, -300.0, 10.0)), yaw=-20.0, roll=6.0, scale=1.0)
    kit.key(moon.root, 'location', K8 - 0.2, tuple(O + V((205.0, -300.0, 14.0))), interp='LINEAR')
    kit.key(moon.root, 'location', K9 + 0.2, tuple(O + V((150.0, -300.0, 8.0))), interp='LINEAR')
    kit.key(moon.root, 'rotation_euler', K8 - 0.2, (0.0, math.radians(8), math.radians(-34)), interp='LINEAR')
    kit.key(moon.root, 'rotation_euler', K9 + 0.2, (0.0, math.radians(4), math.radians(-18)), interp='LINEAR')
    moonkey = kit.spot('k8.moonkey', tuple(O + V((60.0, -520.0, 120.0))), tuple(O + V((170.0, -300.0, 0.0))),
                       power=1.2e6, angle_deg=28, blend=0.6, radius=4.0, color='#FFD6A0', coll=coll)
    moonkey.data.volume_factor = 0.0
    objs = F.objects_in(coll)
    moon_objs = set(moon.objects) | {moonkey}
    F.show([o for o in objs if o not in moon_objs], F.edge(K7), F.edge(K9))
    F.show([o for o in objs if o in moon_objs], F.edge(K8), F.edge(K9))
    if E['clouds'] is not None:
        # the cotton clouds belong to the painted world: gone once it's all clips
        hide = E['clouds']
        hide.animation_data_clear()
        F.show([hide], F.edge(K7), F.edge(K8))
    cams = kit.collection('finale.cams')
    F.Cam('cam.k7', K7, K8, F.path(O + V((36.0, -136.0, 22.0)), O + V((46.0, -168.0, 30.0)), K7, K8 + 0.1),
          F.path(O + V((2.0, 0.0, 0.0)), O + V((2.0, 0.0, 0.0)), K7, K8 + 0.1), lens=50.0, fstop=4.0,
          focus=O + V((10.0, -26.0, 4.0)), coll=cams)
    F.Cam('cam.k8', K8, K9, F.path(O + V((60.0, -420.0, 60.0)), O + V((80.0, -560.0, 84.0)), K8, K9 + 0.1),
          F.path(O + V((16.0, 0.0, 0.0)), O + V((22.0, 0.0, 0.0)), K8, K9 + 0.1), lens=50.0, fstop=2.8,
          focus=O + V((0.0, 0.0, 0.0)), coll=cams)
