"""Materials for the in-picture lyrics: things that belong on the desk (painted wood, ivory tiles, brass, ink, chalk,
marker, cardboard, sticky notes, tape, neon, screen glow, fogged glass).

Per-letter state lives on each letter OBJECT as custom properties read by an Attribute node (type OBJECT), so one
material serves every letter and the state is keyed per letter:
  ly_on    0..1  lit / sung (emission of neon, screen text, glow blocks; ink darkness of 'dim' previews)
  ly_wipe  0..1  draw-on wipe from left to right across the letter (chalk, marker, fog writing, ink)
  ly_fade  0..1  opacity (fade exits)
and the object colour (Object Info > Color) is a per-object paint colour (block bodies, tape, sticky notes).
"""
from __future__ import annotations

import bpy

from .. import kit
from ..sets import materials as M
from . import text as T

_C: dict[str, bpy.types.Material] = {}

PAINT = ['#C8472F', '#2F5F9A', '#3F8A4E', '#E3A92F', '#7A4A9A', '#D2622E']   # vintage toy-block enamels
CREAM = '#F2EBDD'
INK = '#1A1614'
GLOW = '#FFB24A'


def _get(name):
    m = _C.get(name)
    if T.alive(m, bpy.data.materials):
        return m, False
    m = bpy.data.materials.new(name)
    try:
        m.use_nodes = True
    except Exception:
        pass
    _C[name] = m
    return m, True


def _n(nt, typ, loc=(0, 0), **props):
    n = nt.nodes.new(typ)
    n.location = loc
    for k, v in props.items():
        setattr(n, k, v)
    return n


def attr(nt, name, loc=(-900, 0)):
    """Attribute node reading the object's custom property `name` (0 if missing)."""
    a = _n(nt, 'ShaderNodeAttribute', loc)
    a.attribute_type = 'OBJECT'
    a.attribute_name = f'["{name}"]'
    return a.outputs['Fac']


def math(nt, op, a, b=None, loc=(0, 0), clamp=False, c=None):
    n = _n(nt, 'ShaderNodeMath', loc)
    n.operation = op
    n.use_clamp = clamp
    for i, v in enumerate((a, b, c)):
        if v is None:
            continue
        if isinstance(v, (int, float)):
            n.inputs[i].default_value = v
        else:
            nt.links.new(v, n.inputs[i])
    return n.outputs[0]


def wipe_mask(nt, soft=0.08, loc=(-700, -300), axis=0):
    """1 where the letter is already drawn: Generated coordinate (0..1 across the object's box) < ly_wipe."""
    tc = _n(nt, 'ShaderNodeTexCoord', (loc[0] - 400, loc[1]))
    sep = _n(nt, 'ShaderNodeSeparateXYZ', (loc[0] - 200, loc[1]))
    nt.links.new(tc.outputs['Generated'], sep.inputs[0])
    w = attr(nt, 'ly_wipe', (loc[0] - 200, loc[1] - 200))
    # (w * (1 + soft) - x) / soft, clamped
    a = math(nt, 'MULTIPLY', w, 1.0 + soft, (loc[0], loc[1] - 150))
    b = math(nt, 'SUBTRACT', a, sep.outputs[axis], (loc[0] + 150, loc[1]))
    return math(nt, 'DIVIDE', b, soft, (loc[0] + 300, loc[1]), clamp=True)


def _alpha(m, *factors):
    nt = m.node_tree
    b = M.principled(m)
    cur = None
    for f in factors:
        cur = f if cur is None else math(nt, 'MULTIPLY', cur, f)
    if cur is not None:
        nt.links.new(cur, b.inputs['Alpha'])
    try:
        m.surface_render_method = 'DITHERED'
    except Exception:
        pass
    m.use_transparent_shadow = True
    return m


def fade_alpha(m):
    """Multiply the material's alpha by the letter's ly_fade (fade exits)."""
    nt = m.node_tree
    b = M.principled(m)
    f = attr(nt, 'ly_fade', (-900, -900))
    if b.inputs['Alpha'].is_linked:
        src = b.inputs['Alpha'].links[0].from_socket
        nt.links.new(math(nt, 'MULTIPLY', src, f, (-200, -900)), b.inputs['Alpha'])
    else:
        nt.links.new(f, b.inputs['Alpha'])
    try:
        m.surface_render_method = 'DITHERED'
    except Exception:
        pass
    return m


# ------------------------------------------------------------------------------------------------ wood and paint


def paint_body():
    """Painted wooden block: satin enamel in the OBJECT colour (one material for every block), faint grain under
    the paint and slightly worn (rougher, lighter) edges."""
    m, fresh = _get('ly.paint.body')
    if not fresh:
        return m
    nt = m.node_tree
    b = M.principled(m)
    oi = _n(nt, 'ShaderNodeObjectInfo', (-900, 200))
    # wear: lighten toward the edges using the pointiness-free trick of a noise on object coords
    tc = _n(nt, 'ShaderNodeTexCoord', (-1100, -200))
    wave = _n(nt, 'ShaderNodeTexWave', (-900, -200))
    wave.wave_type = 'BANDS'
    M.setin(wave, 'Scale', 1.3)
    M.setin(wave, 'Distortion', 6.0)
    M.setin(wave, 'Detail', 3.0)
    nt.links.new(tc.outputs['Object'], wave.inputs['Vector'])
    mix = _n(nt, 'ShaderNodeMix', (-600, 200), data_type='RGBA', blend_type='MULTIPLY')
    M.setin(mix, 'Factor', 0.12, 'VALUE')
    nt.links.new(oi.outputs['Color'], M.sin(mix, 'A', 'RGBA'))
    nt.links.new(wave.outputs['Color'], M.sin(mix, 'B', 'RGBA'))
    nt.links.new(M.sout(mix, 'Result', 'RGBA'), b.inputs['Base Color'])
    M.setin(b, 'Roughness', 0.42)
    M.setin(b, 'Coat Weight', 0.35)
    M.setin(b, 'Coat Roughness', 0.18)
    bump = _n(nt, 'ShaderNodeBump', (-300, -300))
    M.setin(bump, 'Strength', 0.08)
    M.setin(bump, 'Distance', 0.01)
    nt.links.new(wave.outputs['Fac'], bump.inputs['Height'])
    nt.links.new(bump.outputs['Normal'], b.inputs['Normal'])
    m.diffuse_color = kit.srgb(PAINT[0])
    return m


def paint(color=CREAM, name=None, rough=0.4):
    name = name or f'ly.paint.{color.lstrip("#")}'
    m, fresh = _get(name)
    if not fresh:
        return m
    b = M.principled(m)
    M.setin(b, 'Base Color', kit.srgb(color))
    M.setin(b, 'Roughness', rough)
    M.setin(b, 'Coat Weight', 0.3)
    M.setin(b, 'Coat Roughness', 0.2)
    m.diffuse_color = kit.srgb(color)
    return m


def beech():
    """Pale varnished beech (tile backs, stands, rails, stamp handles): the desk's wood texture bleached."""
    return M.tex_mat('ly.beech', 'desk_wood', 18, tint='#E6C08E', tint_amount=0.85, sat=0.55, val=2.6,
                     rough=(0.35, 0.55), normal=0.4, coat=0.3, coat_rough=0.2, fallback='#D9B687')


def glow_letter(color=GLOW, strength=9.0, base='#9C7A4E'):
    """Emissive letter paint lit by ly_on (0 dark, 1 full)."""
    name = f'ly.glow.{color.lstrip("#")}.{strength:g}'
    m, fresh = _get(name)
    if not fresh:
        return m
    nt = m.node_tree
    b = M.principled(m)
    M.setin(b, 'Base Color', kit.srgb(base))
    M.setin(b, 'Roughness', 0.3)
    M.setin(b, 'Emission Color', kit.srgb(color))
    on = attr(nt, 'ly_on')
    nt.links.new(math(nt, 'MULTIPLY', on, strength, (-500, -100)), b.inputs['Emission Strength'])
    m.diffuse_color = kit.srgb(color)
    return m


def acrylic(tint='#3B2C22'):
    """Smoked, frosted acrylic (the body of a light-up block)."""
    m, fresh = _get(f'ly.acrylic.{tint.lstrip("#")}')
    if not fresh:
        return m
    b = M.principled(m)
    M.setin(b, 'Base Color', kit.srgb(tint))
    M.setin(b, 'Roughness', 0.35)
    M.setin(b, 'Coat Weight', 0.6)
    M.setin(b, 'Coat Roughness', 0.18)
    M.setin(b, 'Subsurface Weight', 0.4)
    M.setin(b, 'Subsurface Radius', (1.0, 0.6, 0.3))
    M.setin(b, 'Subsurface Scale', 0.3)
    m.diffuse_color = kit.srgb(tint)
    return m


# ------------------------------------------------------------------------------------------------ tiles


def ivory():
    return M.solid('ly.ivory', '#EFE4C8', rough=0.36, coat=0.45, coat_rough=0.12, sss=0.05, micro=(40.0, 0.01))


def engrave():
    return M.solid('ly.engrave', '#1C1612', rough=0.6)


# ------------------------------------------------------------------------------------------------ ink, chalk, marker


def ink(color='#B3261E', name=None, speckle=0.35):
    """Rubber-stamp ink: flat colour, speckled where the stamp didn't take, revealed by ly_wipe (1 = all)."""
    name = name or f'ly.ink.{color.lstrip("#")}'
    m, fresh = _get(name)
    if not fresh:
        return m
    nt = m.node_tree
    b = M.principled(m)
    M.setin(b, 'Base Color', kit.srgb(color))
    M.setin(b, 'Roughness', 0.55)
    M.setin(b, 'Specular IOR Level', 0.3)
    tc = _n(nt, 'ShaderNodeTexCoord', (-1200, -500))
    nz = _n(nt, 'ShaderNodeTexNoise', (-1000, -500))
    M.setin(nz, 'Scale', 38.0)
    M.setin(nz, 'Detail', 8.0)
    M.setin(nz, 'Roughness', 0.7)
    nt.links.new(tc.outputs['Object'], nz.inputs['Vector'])
    mr = _n(nt, 'ShaderNodeMapRange', (-800, -500))
    M.setin(mr, 'From Min', speckle * 0.62, 'VALUE')
    M.setin(mr, 'From Max', speckle * 0.62 + 0.08, 'VALUE')
    nt.links.new(nz.outputs['Fac'], M.sin(mr, 'Value', 'VALUE'))
    _alpha(m, M.sout(mr, 'Result', 'VALUE'), wipe_mask(nt), attr(nt, 'ly_fade', (-900, -900)))
    m.diffuse_color = kit.srgb(color)
    return m


def chalk(color='#F4F2EA'):
    """Chalk: matte, grainy (dithered holes), drawn on by ly_wipe."""
    m, fresh = _get(f'ly.chalk.{color.lstrip("#")}')
    if not fresh:
        return m
    nt = m.node_tree
    b = M.principled(m)
    M.setin(b, 'Base Color', kit.srgb(color))
    M.setin(b, 'Roughness', 0.95)
    M.setin(b, 'Specular IOR Level', 0.2)
    tc = _n(nt, 'ShaderNodeTexCoord', (-1200, -500))
    nz = _n(nt, 'ShaderNodeTexNoise', (-1000, -500))
    M.setin(nz, 'Scale', 60.0)
    M.setin(nz, 'Detail', 10.0)
    M.setin(nz, 'Roughness', 0.8)
    nt.links.new(tc.outputs['Object'], nz.inputs['Vector'])
    mr = _n(nt, 'ShaderNodeMapRange', (-800, -500))
    M.setin(mr, 'From Min', 0.26, 'VALUE')
    M.setin(mr, 'From Max', 0.46, 'VALUE')
    M.setin(mr, 'To Min', 0.35, 'VALUE')
    nt.links.new(nz.outputs['Fac'], M.sin(mr, 'Value', 'VALUE'))
    _alpha(m, M.sout(mr, 'Result', 'VALUE'), attr(nt, 'ly_fade', (-900, -900)))
    m.diffuse_color = kit.srgb(color)
    return m


def marker(color=INK):
    """Felt-tip marker: satin ink, drawn on left to right by ly_wipe."""
    m, fresh = _get(f'ly.marker.{color.lstrip("#")}')
    if not fresh:
        return m
    nt = m.node_tree
    b = M.principled(m)
    M.setin(b, 'Base Color', kit.srgb(color))
    M.setin(b, 'Roughness', 0.38)
    _alpha(m, wipe_mask(nt, soft=0.05), attr(nt, 'ly_fade', (-900, -900)))
    m.diffuse_color = kit.srgb(color)
    return m


def screen_text(color='#9CF0B0', strength=4.0, dim=0.09):
    """Glowing screen text: dim (unsung) until ly_on rises to 1 (sung)."""
    m, fresh = _get(f'ly.screen.{color.lstrip("#")}.{strength:g}')
    if not fresh:
        return m
    nt = m.node_tree
    b = M.principled(m)
    M.setin(b, 'Base Color', (0, 0, 0, 1))
    M.setin(b, 'Roughness', 0.5)
    M.setin(b, 'Specular IOR Level', 0.0)
    M.setin(b, 'Emission Color', kit.srgb(color))
    on = attr(nt, 'ly_on')
    lvl = math(nt, 'MULTIPLY_ADD', on, 1.0 - dim, (-500, -200), c=dim)
    nt.links.new(math(nt, 'MULTIPLY', lvl, strength, (-300, -200)), b.inputs['Emission Strength'])
    _alpha(m, attr(nt, 'ly_fade', (-900, -900)))
    m.diffuse_color = kit.srgb(color)
    return m


def screen_panel(color='#0B1016'):
    """The dark terminal panel the screen text sits on (slightly emissive so it reads as a screen)."""
    m, fresh = _get(f'ly.panel.{color.lstrip("#")}')
    if not fresh:
        return m
    b = M.principled(m)
    M.setin(b, 'Base Color', kit.srgb(color))
    M.setin(b, 'Roughness', 0.3)
    M.setin(b, 'Emission Color', kit.srgb(color))
    M.setin(b, 'Emission Strength', 1.0)
    return m


# ------------------------------------------------------------------------------------------------ metal, neon, glass


def brass():
    return M.brass('ly.brass', color='#D2A451', rough=0.24)


def steel():
    return M.solid('ly.wire', '#C9CED6', rough=0.2, metal=1.0, micro=(80.0, 0.02))


def neon(color='#FF5A3C', strength=7.0):
    """A neon tube: tinted glass when off, glowing in its colour by ly_on."""
    m, fresh = _get(f'ly.neon.{color.lstrip("#")}.{strength:g}')
    if not fresh:
        return m
    nt = m.node_tree
    b = M.principled(m)
    M.setin(b, 'Base Color', kit.srgb(color))
    M.setin(b, 'Roughness', 0.15)
    M.setin(b, 'Coat Weight', 1.0)
    M.setin(b, 'Coat Roughness', 0.03)
    M.setin(b, 'Emission Color', kit.srgb(color))
    on = attr(nt, 'ly_on')
    nt.links.new(math(nt, 'MULTIPLY', on, strength, (-500, -200)), b.inputs['Emission Strength'])
    m.diffuse_color = kit.srgb(color)
    return m


def frost():
    """Fogged glass: rough, milky transmission (the wiped letters, clear glass in front of it, read as windows)."""
    m, fresh = _get('ly.frost')
    if not fresh:
        return m
    b = M.principled(m)
    M.setin(b, 'Base Color', kit.srgb('#E8ECEF'))
    M.setin(b, 'Roughness', 0.75)
    M.setin(b, 'Transmission Weight', 0.82)
    M.setin(b, 'IOR', 1.45)
    M.setin(b, 'Thin Wall', True)
    M.setin(b, 'Coat Weight', 0.3)
    M.setin(b, 'Coat Roughness', 0.35)
    M.glassify(m)
    return m


def clear_glass():
    return M.glass('ly.clearglass', rough=0.0)


# ------------------------------------------------------------------------------------------------ paper things


def paper(tint='#F4EFE4'):
    return M.paper(f'ly.paper.{tint.lstrip("#")}', tint=tint, tile=20)


def cardboard():
    return M.cardboard('ly.cardboard')


def sticky(color='#F6E27A'):
    return M.paper(f'ly.sticky.{color.lstrip("#")}', tint=color, tile=12)


def tape(color='#1F1F24'):
    """Embossing-tape plastic (glossy), in the object colour if color is None."""
    return M.solid(f'ly.tape.{color.lstrip("#")}', color, rough=0.22, coat=0.7, coat_rough=0.06)


def tape_letter():
    return M.solid('ly.tape.letter', '#E8E6E0', rough=0.45)


def rubber(color='#8E2A22'):
    return M.solid(f'ly.rubber.{color.lstrip("#")}', color, rough=0.7, spec=0.3)


def slate():
    return M.solid('ly.slate', '#20262A', rough=0.85, micro=(12.0, 0.03))
