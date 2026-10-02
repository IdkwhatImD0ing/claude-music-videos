"""Materials for the characters: soft-touch vinyl, jelly, turned/painted wood, fabric, glossy paint, wire, lenses.

Shared looks are cached by name (one material for every Clawd's vinyl); per-character animated looks (glowing eyes,
glinting lenses, the painted face) are made per instance and expose Value/RGB nodes the rig keys by song time.
"""
from __future__ import annotations

import os

import bpy

from ..kit import srgb

HERE = os.path.dirname(os.path.abspath(__file__))
_CACHE: dict[str, bpy.types.Material] = {}


def _cached(name):
    m = _CACHE.get(name)
    if m is not None:
        try:
            if m.name in bpy.data.materials:
                return m
        except ReferenceError:
            pass
    return None


def _col(c):
    return srgb(c) if isinstance(c, str) else (tuple(c) + (1.0,) if len(c) == 3 else tuple(c))


def _new(name):
    m = bpy.data.materials.new(name)
    try:
        m.use_nodes = True
    except Exception:
        pass
    _CACHE[name] = m
    return m, m.node_tree, m.node_tree.nodes['Principled BSDF']


def _set(b, **kw):
    names = {'color': 'Base Color', 'rough': 'Roughness', 'metal': 'Metallic', 'spec': 'Specular IOR Level',
             'sss': 'Subsurface Weight', 'sss_radius': 'Subsurface Radius', 'sss_scale': 'Subsurface Scale',
             'coat': 'Coat Weight', 'coat_rough': 'Coat Roughness', 'sheen': 'Sheen Weight',
             'sheen_rough': 'Sheen Roughness', 'sheen_tint': 'Sheen Tint', 'trans': 'Transmission Weight',
             'ior': 'IOR', 'alpha': 'Alpha', 'emit': 'Emission Color', 'emit_strength': 'Emission Strength',
             'aniso': 'Anisotropic'}
    for k, v in kw.items():
        s = b.inputs[names[k]]
        if k in ('color', 'emit', 'sheen_tint'):
            v = _col(v)
        s.default_value = v


def _bump(nt, b, scale=70.0, strength=0.25, distance=0.004, detail=2.0, coords='Object'):
    """Fine surface texture (vinyl orange-peel, wood pores, paint)."""
    tc = nt.nodes.new('ShaderNodeTexCoord')
    nz = nt.nodes.new('ShaderNodeTexNoise')
    nz.inputs['Scale'].default_value = scale
    nz.inputs['Detail'].default_value = detail
    bp = nt.nodes.new('ShaderNodeBump')
    bp.inputs['Strength'].default_value = strength
    bp.inputs['Distance'].default_value = distance
    nt.links.new(tc.outputs[coords], nz.inputs['Vector'])
    nt.links.new(nz.outputs['Fac'], bp.inputs['Height'])
    nt.links.new(bp.outputs['Normal'], b.inputs['Normal'])
    for n in ('Coat Normal',):
        if n in b.inputs:
            pass
    return bp


def _color_var(nt, b, color, var=0.06, scale=0.35):
    """Slow, subtle tone variation (moulding/paint isn't perfectly even)."""
    tc = nt.nodes.new('ShaderNodeTexCoord')
    nz = nt.nodes.new('ShaderNodeTexNoise')
    nz.inputs['Scale'].default_value = scale
    nz.inputs['Detail'].default_value = 1.0
    mix = nt.nodes.new('ShaderNodeMix')
    mix.data_type = 'RGBA'
    mix.blend_type = 'MULTIPLY'
    sock = {s.identifier: s for s in mix.inputs}
    sock['Factor_Float'].default_value = 1.0
    sock['A_Color'].default_value = _col(color)
    rmp = nt.nodes.new('ShaderNodeMapRange')
    rmp.inputs['From Min'].default_value = 0.3
    rmp.inputs['From Max'].default_value = 0.7
    rmp.inputs['To Min'].default_value = 1 - var
    rmp.inputs['To Max'].default_value = 1 + var
    nt.links.new(tc.outputs['Object'], nz.inputs['Vector'])
    nt.links.new(nz.outputs['Fac'], rmp.inputs['Value'])
    comb = nt.nodes.new('ShaderNodeCombineColor')
    for k in ('Red', 'Green', 'Blue'):
        nt.links.new(rmp.outputs['Result'], comb.inputs[k])
    nt.links.new(comb.outputs['Color'], sock['B_Color'])
    out = next(s for s in mix.outputs if s.identifier == 'Result_Color')
    nt.links.new(out, b.inputs['Base Color'])
    return mix


# ------------------------------------------------------------------------------------------------ Clawd


def vinyl(name='chars.vinyl', color='#D97757', *, rough=0.46, sss=0.18, coat=0.22, bump=0.2):
    """Soft-touch vinyl: satin, a little subsurface glow at thin edges, faint orange-peel texture."""
    m = _cached(name)
    if m:
        return m
    m, nt, b = _new(name)
    _set(b, color=color, rough=rough, sss=sss, sss_radius=(1.0, 0.45, 0.25), sss_scale=0.25, coat=coat,
         coat_rough=0.35, sheen=0.15, sheen_rough=0.4, spec=0.45)
    _color_var(nt, b, color, var=0.05)
    _bump(nt, b, scale=90.0, strength=bump, distance=0.003)
    m.diffuse_color = _col(color)
    return m


def gloss(name, color, *, rough=0.1, coat=1.0, coat_rough=0.03, sss=0.0, bump=0.0):
    m = _cached(name)
    if m:
        return m
    m, nt, b = _new(name)
    _set(b, color=color, rough=rough, coat=coat, coat_rough=coat_rough, spec=0.5)
    if sss:
        _set(b, sss=sss, sss_radius=(1.0, 0.4, 0.3), sss_scale=0.1)
    if bump:
        _bump(nt, b, scale=60.0, strength=bump, distance=0.002)
    m.diffuse_color = _col(color)
    return m


def satin(name, color, *, rough=0.55, sss=0.0, coat=0.0, sheen=0.0, bump=0.0, bump_scale=70.0):
    m = _cached(name)
    if m:
        return m
    m, nt, b = _new(name)
    _set(b, color=color, rough=rough, coat=coat, coat_rough=0.3, sheen=sheen, spec=0.4)
    if sss:
        _set(b, sss=sss, sss_radius=(1.0, 0.35, 0.25), sss_scale=0.15)
    if bump:
        _bump(nt, b, scale=bump_scale, strength=bump, distance=0.003)
    m.diffuse_color = _col(color)
    return m


def glow_eye(name, color='#0B0909', *, rough=0.07):
    """A glossy black eye whose emission is keyed: nodes 'glow' (Value, strength) and 'glowcol' (RGB)."""
    m, nt, b = _new(name)
    _set(b, color=color, rough=rough, coat=1.0, coat_rough=0.02, spec=0.6)
    v = nt.nodes.new('ShaderNodeValue')
    v.name = v.label = 'glow'
    v.outputs[0].default_value = 0.0
    c = nt.nodes.new('ShaderNodeRGB')
    c.name = c.label = 'glowcol'
    c.outputs[0].default_value = srgb('#FFB24A')
    nt.links.new(v.outputs[0], b.inputs['Emission Strength'])
    nt.links.new(c.outputs[0], b.inputs['Emission Color'])
    m.diffuse_color = _col(color)
    return m


def jelly(name='chars.jelly', color='#6FB6FF'):
    """Sydney: translucent blue gelatin. Raytraced refraction + a soft inner glow so it reads inside a snow globe."""
    m = _cached(name)
    if m:
        return m
    m, nt, b = _new(name)
    _set(b, color=color, rough=0.12, trans=1.0, ior=1.33, coat=0.5, coat_rough=0.03, spec=0.7,
         emit=color, emit_strength=0.18)
    m.use_raytrace_refraction = True
    m.thickness_mode = 'SPHERE'
    # a fresnel-weighted tint: the jelly reads bluer at grazing angles, clearer face-on
    fr = nt.nodes.new('ShaderNodeLayerWeight')
    fr.inputs['Blend'].default_value = 0.35
    mix = nt.nodes.new('ShaderNodeMix')
    mix.data_type = 'RGBA'
    sk = {s.identifier: s for s in mix.inputs}
    sk['A_Color'].default_value = _col('#8FC6FF')
    sk['B_Color'].default_value = _col(color)
    nt.links.new(fr.outputs['Facing'], sk['Factor_Float'])
    nt.links.new(next(s for s in mix.outputs if s.identifier == 'Result_Color'), b.inputs['Base Color'])
    # thickness (cm) drives EEVEE's refraction/absorption depth
    th = nt.nodes.new('ShaderNodeValue')
    th.outputs[0].default_value = 2.5
    out = nt.nodes['Material Output']
    nt.links.new(th.outputs[0], out.inputs['Thickness'])
    m.diffuse_color = _col(color)
    return m


def paper(name, color='#F2D15C', *, rough=0.8):
    m = _cached(name)
    if m:
        return m
    m, nt, b = _new(name)
    _set(b, color=color, rough=rough, sss=0.25, sss_radius=(1, 0.9, 0.6), sss_scale=0.05, sheen=0.2, spec=0.3)
    _bump(nt, b, scale=40.0, strength=0.12, distance=0.004, detail=4.0)
    m.diffuse_color = _col(color)
    return m


def felt(name, color):
    m = _cached(name)
    if m:
        return m
    m, nt, b = _new(name)
    _set(b, color=color, rough=0.95, sheen=0.8, sheen_rough=0.6, spec=0.2)
    _bump(nt, b, scale=160.0, strength=0.35, distance=0.004, detail=6.0)
    m.diffuse_color = _col(color)
    return m


def metal(name, color='#B8893A', *, rough=0.28):
    m = _cached(name)
    if m:
        return m
    m, nt, b = _new(name)
    _set(b, color=color, rough=rough, metal=1.0)
    m.diffuse_color = _col(color)
    return m


# ------------------------------------------------------------------------------------------------ researcher


def _wood_grain(nt, light='#E2C497', dark='#C39A68', scale=2.2):
    """Turned-wood grain: long bands along Z (the lathe axis), warped by noise. Returns the colour socket."""
    tc = nt.nodes.new('ShaderNodeTexCoord')
    wv = nt.nodes.new('ShaderNodeTexWave')
    wv.wave_type = 'BANDS'
    wv.bands_direction = 'X'
    wv.inputs['Scale'].default_value = scale
    wv.inputs['Distortion'].default_value = 4.0
    wv.inputs['Detail'].default_value = 2.0
    wv.inputs['Detail Scale'].default_value = 1.2
    mp = nt.nodes.new('ShaderNodeMapping')
    mp.inputs['Scale'].default_value = (1.0, 1.0, 0.12)
    nt.links.new(tc.outputs['Object'], mp.inputs['Vector'])
    nt.links.new(mp.outputs['Vector'], wv.inputs['Vector'])
    ramp = nt.nodes.new('ShaderNodeValToRGB')
    ramp.color_ramp.elements[0].position = 0.45
    ramp.color_ramp.elements[0].color = _col(light)
    ramp.color_ramp.elements[1].position = 1.0
    ramp.color_ramp.elements[1].color = _col(dark)
    nt.links.new(wv.outputs['Fac'], ramp.inputs['Fac'])
    return ramp.outputs['Color']


def wood(name='chars.wood', light='#E6CBA0', dark='#D1AE7E'):
    """Natural varnished maple (hands, neck)."""
    m = _cached(name)
    if m:
        return m
    m, nt, b = _new(name)
    _set(b, rough=0.42, coat=0.55, coat_rough=0.18, spec=0.45, sss=0.08, sss_radius=(1, 0.6, 0.3), sss_scale=0.1)
    nt.links.new(_wood_grain(nt, light, dark), b.inputs['Base Color'])
    _bump(nt, b, scale=120.0, strength=0.08, distance=0.002)
    m.diffuse_color = _col(light)
    return m


def paint(name, color, *, rough=0.38, coat=0.45):
    """Glossy enamel paint on wood: a hint of the grain shows through as texture."""
    m = _cached(name)
    if m:
        return m
    m, nt, b = _new(name)
    _set(b, color=color, rough=rough, coat=coat, coat_rough=0.2, spec=0.45)
    _bump(nt, b, scale=45.0, strength=0.06, distance=0.003, detail=3.0)
    m.diffuse_color = _col(color)
    return m


def fabric(name='chars.coat', color='#F3F1EA'):
    """Lab-coat cotton: matte, sheen, a fine weave."""
    m = _cached(name)
    if m:
        return m
    m, nt, b = _new(name)
    _set(b, color=color, rough=0.85, sheen=0.5, sheen_rough=0.5, spec=0.3, sss=0.1, sss_radius=(1, 0.9, 0.8),
         sss_scale=0.05)
    # weave: two perpendicular fine wave textures
    tc = nt.nodes.new('ShaderNodeTexCoord')
    w1 = nt.nodes.new('ShaderNodeTexWave')
    w1.inputs['Scale'].default_value = 110.0
    w1.bands_direction = 'X'
    w2 = nt.nodes.new('ShaderNodeTexWave')
    w2.inputs['Scale'].default_value = 110.0
    w2.bands_direction = 'Z'
    for w in (w1, w2):
        w.inputs['Distortion'].default_value = 0.5
        nt.links.new(tc.outputs['Object'], w.inputs['Vector'])
    add = nt.nodes.new('ShaderNodeMath')
    add.operation = 'ADD'
    nt.links.new(w1.outputs['Fac'], add.inputs[0])
    nt.links.new(w2.outputs['Fac'], add.inputs[1])
    bp = nt.nodes.new('ShaderNodeBump')
    bp.inputs['Strength'].default_value = 0.18
    bp.inputs['Distance'].default_value = 0.002
    nt.links.new(add.outputs[0], bp.inputs['Height'])
    nt.links.new(bp.outputs['Normal'], b.inputs['Normal'])
    m.diffuse_color = _col(color)
    return m


def face_head(name, atlas_path, *, cols=4, rows=3, yaw_span=120.0, pitch_lo=-75.0, pitch_span=120.0,
              hair='#3A2A20', skin_light='#EBD2AA', skin_dark='#D8B888'):
    """The researcher's head: varnished wood, a painted hair cap, and a painted face from an atlas.

    The face is projected by angle from the head centre (object coords, origin at the head centre, facing -Y):
    u = 0.5 + yaw / yaw_span, v = (pitch - pitch_lo) / pitch_span. Node 'face' (Value) picks the atlas slot."""
    m, nt, b = _new(name)
    N, L = nt.nodes, nt.links
    _set(b, rough=0.4, coat=0.55, coat_rough=0.16, spec=0.45, sss=0.08, sss_radius=(1, 0.6, 0.3), sss_scale=0.1)
    skin = _wood_grain(nt, skin_light, skin_dark)
    tc = N.new('ShaderNodeTexCoord')
    nrm = N.new('ShaderNodeVectorMath')
    nrm.operation = 'NORMALIZE'
    L.new(tc.outputs['Object'], nrm.inputs[0])
    sep = N.new('ShaderNodeSeparateXYZ')
    L.new(nrm.outputs['Vector'], sep.inputs[0])

    def math(op, a, b_=None, v=None):
        n = N.new('ShaderNodeMath')
        n.operation = op
        for i, x in enumerate((a, b_)):
            if x is None:
                continue
            if isinstance(x, (int, float)):
                n.inputs[i].default_value = x
            else:
                L.new(x, n.inputs[i])
        return n.outputs[0]

    X, Y, Z = sep.outputs['X'], sep.outputs['Y'], sep.outputs['Z']
    negY = math('MULTIPLY', Y, -1.0)
    yaw = math('ARCTAN2', X, negY)                      # radians, 0 at the front, + toward +X
    pitch = math('ARCSINE', Z)
    import math as _m
    u = math('ADD', math('DIVIDE', yaw, _m.radians(yaw_span)), 0.5)
    v = math('DIVIDE', math('SUBTRACT', pitch, _m.radians(pitch_lo)), _m.radians(pitch_span))
    # inside-the-slot mask
    inside = math('MULTIPLY',
                  math('MULTIPLY', math('GREATER_THAN', u, 0.0), math('LESS_THAN', u, 1.0)),
                  math('MULTIPLY', math('GREATER_THAN', v, 0.0), math('LESS_THAN', v, 1.0)))
    uc = math('MINIMUM', math('MAXIMUM', u, 0.002), 0.998)
    vc = math('MINIMUM', math('MAXIMUM', v, 0.002), 0.998)
    slot = N.new('ShaderNodeValue')
    slot.name = slot.label = 'face'
    slot.outputs[0].default_value = 0.0
    sidx = math('FLOOR', math('ADD', slot.outputs[0], 0.5))       # whole slots only (never slide between faces)
    col = math('MODULO', sidx, float(cols))
    row = math('FLOOR', math('DIVIDE', sidx, float(cols)))
    U = math('DIVIDE', math('ADD', col, uc), float(cols))
    V = math('DIVIDE', math('ADD', math('SUBTRACT', float(rows - 1), row), vc), float(rows))
    cmb = N.new('ShaderNodeCombineXYZ')
    L.new(U, cmb.inputs['X'])
    L.new(V, cmb.inputs['Y'])
    img = N.new('ShaderNodeTexImage')
    ima = bpy.data.images.load(atlas_path, check_existing=True)
    try:
        ima.pack()
    except Exception:
        pass
    ima.alpha_mode = 'STRAIGHT'
    img.image = ima
    img.interpolation = 'Cubic'
    img.extension = 'EXTEND'
    L.new(cmb.outputs['Vector'], img.inputs['Vector'])
    face_a = math('MULTIPLY', img.outputs['Alpha'], inside)
    # hair cap: above a hairline that is high at the front, low at the back, with a wavy fringe
    rxy = math('SQRT', math('ADD', math('MULTIPLY', X, X), math('MULTIPLY', Y, Y)))
    front = math('DIVIDE', negY, math('MAXIMUM', rxy, 1e-4))
    fringe = math('MULTIPLY', math('SINE', math('MULTIPLY', yaw, 9.0)), math('MULTIPLY', math('MAXIMUM', front, 0.0), 0.045))
    line = math('ADD', math('ADD', math('MULTIPLY', front, 0.56), 0.08), fringe)
    hair_m = N.new('ShaderNodeMapRange')
    L.new(math('SUBTRACT', Z, line), hair_m.inputs['Value'])
    hair_m.inputs['From Min'].default_value = -0.006
    hair_m.inputs['From Max'].default_value = 0.006
    # colour: skin -> hair -> face paint
    mix1 = N.new('ShaderNodeMix')
    mix1.data_type = 'RGBA'
    s1 = {s.identifier: s for s in mix1.inputs}
    L.new(hair_m.outputs['Result'], s1['Factor_Float'])
    L.new(skin, s1['A_Color'])
    s1['B_Color'].default_value = _col(hair)
    mix2 = N.new('ShaderNodeMix')
    mix2.data_type = 'RGBA'
    s2 = {s.identifier: s for s in mix2.inputs}
    L.new(face_a, s2['Factor_Float'])
    L.new(next(s for s in mix1.outputs if s.identifier == 'Result_Color'), s2['A_Color'])
    L.new(img.outputs['Color'], s2['B_Color'])
    L.new(next(s for s in mix2.outputs if s.identifier == 'Result_Color'), b.inputs['Base Color'])
    # paint is glossier than the varnished wood; hair paint slightly raised
    rough = math('ADD', 0.4, math('MULTIPLY', math('MAXIMUM', face_a, hair_m.outputs['Result']), -0.18))
    L.new(rough, b.inputs['Roughness'])
    bp = N.new('ShaderNodeBump')
    bp.inputs['Strength'].default_value = 0.35
    bp.inputs['Distance'].default_value = 0.01
    L.new(math('MAXIMUM', hair_m.outputs['Result'], math('MULTIPLY', face_a, 0.5)), bp.inputs['Height'])
    L.new(bp.outputs['Normal'], b.inputs['Normal'])
    m.diffuse_color = _col(skin_light)
    return m


def lens(name):
    """Glasses lens: nearly clear glass with reflections, plus a keyed glint.
    Nodes: 'glint' (Value, strength), 'glint_pos' (Value, the sweep position -0.3..1.3), 'glintcol' (RGB),
    'fill' (Value 0..1: 0 = a moving band, 1 = the whole lens glows)."""
    m, nt, b = _new(name)
    N, L = nt.nodes, nt.links
    out = N['Material Output']
    _set(b, color='#FFFFFF', rough=0.03, coat=1.0, coat_rough=0.0, spec=0.8)
    tr = N.new('ShaderNodeBsdfTransparent')
    mix = N.new('ShaderNodeMixShader')
    mix.inputs['Fac'].default_value = 0.12
    L.new(tr.outputs[0], mix.inputs[1])
    L.new(b.outputs[0], mix.inputs[2])
    tc = N.new('ShaderNodeTexCoord')
    sep = N.new('ShaderNodeSeparateXYZ')
    L.new(tc.outputs['UV'], sep.inputs[0])

    def math(op, a, b_=None):
        n = N.new('ShaderNodeMath')
        n.operation = op
        for i, x in enumerate((a, b_)):
            if x is None:
                continue
            if isinstance(x, (int, float)):
                n.inputs[i].default_value = x
            else:
                L.new(x, n.inputs[i])
        return n.outputs[0]

    pos = N.new('ShaderNodeValue')
    pos.name = pos.label = 'glint_pos'
    pos.outputs[0].default_value = -1.0
    st = N.new('ShaderNodeValue')
    st.name = st.label = 'glint'
    st.outputs[0].default_value = 0.0
    fill = N.new('ShaderNodeValue')
    fill.name = fill.label = 'fill'
    fill.outputs[0].default_value = 0.0
    col = N.new('ShaderNodeRGB')
    col.name = col.label = 'glintcol'
    col.outputs[0].default_value = (1, 1, 1, 1)
    diag = math('MULTIPLY', math('ADD', sep.outputs['X'], sep.outputs['Y']), 0.5)
    band = math('SUBTRACT', 1.0, math('MINIMUM', math('DIVIDE', math('ABSOLUTE', math('SUBTRACT', diag, pos.outputs[0])), 0.14), 1.0))
    band2 = math('MULTIPLY', math('SUBTRACT', 1.0, math('MINIMUM', math('DIVIDE', math('ABSOLUTE', math('SUBTRACT', diag, math('SUBTRACT', pos.outputs[0], 0.24))), 0.05), 1.0)), 0.7)
    mask = math('MAXIMUM', math('MAXIMUM', band, band2), fill.outputs[0])
    em = N.new('ShaderNodeEmission')
    L.new(col.outputs[0], em.inputs['Color'])
    L.new(math('MULTIPLY', mask, st.outputs[0]), em.inputs['Strength'])
    add = N.new('ShaderNodeAddShader')
    L.new(mix.outputs[0], add.inputs[0])
    L.new(em.outputs[0], add.inputs[1])
    L.new(add.outputs[0], out.inputs['Surface'])
    m.surface_render_method = 'BLENDED'
    m.use_backface_culling = False
    try:
        m.use_transparent_shadow = True
    except Exception:
        pass
    m.diffuse_color = (0.9, 0.95, 1.0, 0.2)
    return m


def emitter_fade(name, color='#FFFFFF', strength=0.0, full=1.0):
    """emitter() that is see-through until its 'glow' reaches `full` (reflections that fade in from clear instead of
    showing as dark opaque decals at low strength)."""
    m = emitter(name, color, strength)
    N, L = m.node_tree.nodes, m.node_tree.links
    em, v, out = N['Emission'], N['glow'], N['Material Output']
    k = N.new('ShaderNodeMath')
    k.operation = 'MULTIPLY'
    k.use_clamp = True
    k.inputs[1].default_value = 1.0 / full
    L.new(v.outputs[0], k.inputs[0])
    tr = N.new('ShaderNodeBsdfTransparent')
    mix = N.new('ShaderNodeMixShader')
    L.new(k.outputs[0], mix.inputs[0])
    L.new(tr.outputs[0], mix.inputs[1])
    L.new(em.outputs[0], mix.inputs[2])
    L.new(mix.outputs[0], out.inputs['Surface'])
    try:
        m.surface_render_method = 'DITHERED'
    except Exception:
        pass
    return m


def emitter(name, color='#FFFFFF', strength=0.0):
    """Pure emission with a keyed 'glow' Value (reflections in glasses, the eye glow's decals)."""
    m, nt, b = _new(name)
    N, L = nt.nodes, nt.links
    out = N['Material Output']
    em = N.new('ShaderNodeEmission')
    v = N.new('ShaderNodeValue')
    v.name = v.label = 'glow'
    v.outputs[0].default_value = strength
    c = N.new('ShaderNodeRGB')
    c.name = c.label = 'glowcol'
    c.outputs[0].default_value = _col(color)
    L.new(c.outputs[0], em.inputs['Color'])
    L.new(v.outputs[0], em.inputs['Strength'])
    L.new(em.outputs[0], out.inputs['Surface'])
    return m
